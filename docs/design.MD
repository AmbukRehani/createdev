# Design NL Query Assistant

## 1. Problem Statement
User should be able to talk through the data using AI Chat Interface with the query given by user. Understand the intent from the query, pass that intent and extract specific template and finally extract parameters and fill those in extracted template to run against the database and return the rows to NL Agent to give final output user can understand

## 2. Out of Scope
RAG, Auth

## 3. Agent Flow
Uses a Plan Execute Graph Structure where one Agents output is an input for another Agent

  a. understand(state) -> {intent, params, confidence}
  Should take in input as current state(query) and classify the intent on the basis of query. Generate a confidence score: TEMPLATE. If confidence score is less, clarify from user
  Always generate the typed output

  b. process(state):
  Looks the template sql by intent. Bind the params and, executes read-only with LIMIT mid model summarizes the returned rows, grounded in them.


  The model never writes SQL. It picks the intent and fills typed slots. There is no guess fallback: below threshold the user gets a question. 

## 4.Open questions for architect
  Do you think we should include multiple tenants or keep it for single tenant?

## 5. Data model
Postgres, single tenant (pending §4). All ids `UUID DEFAULT gen_random_uuid()`, all times `TIMESTAMPTZ`.

**query_templates** — the only place SQL exists. Seeded/curated, never written by the model.

| column | type | notes |
| --- | --- | --- |
| id | UUID PK | |
| intent | TEXT UNIQUE NOT NULL | the key `understand()` returns |
| description | TEXT NOT NULL | fed to the classifier prompt; this is what intent matching reads |
| sql_text | TEXT NOT NULL | named binds only (`:since`, `:status`); no string interpolation, no LIMIT |
| params_schema | JSONB NOT NULL | JSON Schema for the typed slots; drives param extraction + validation |
| enabled | BOOLEAN NOT NULL DEFAULT true | soft-disable without deleting |
| created_at | TIMESTAMPTZ NOT NULL DEFAULT now() | |

`params_schema` is hand-authored, not derived: SQL carries bind *names* only, while slot filling
needs types, formats, enums and descriptions. The two must agree — see the §8 invariant.

Row count is not a template concern. The executor appends a single global `MAX_ROWS` cap from
config, so the model has no say in it and cannot be prompted into one.

**audit_trail** — one row per `/v1/query` call, written on every route including failures.

| column | type | notes |
| --- | --- | --- |
| id | UUID PK | |
| trace_id | UUID NOT NULL | indexed; the §7 correlation id |
| question | TEXT NOT NULL | verbatim user input |
| answer | TEXT NULL | NULL when route ≠ 'answer' |
| intent | TEXT NULL REFERENCES query_templates(intent) | NULL when nothing cleared threshold |
| params | JSONB NOT NULL DEFAULT '{}' | post-validation, as bound |
| confidence | NUMERIC(4,3) NOT NULL | 0.000–1.000 |
| route | TEXT NOT NULL | CHECK IN ('answer','clarified','error') |
| row_count | INTEGER NULL | rows the template returned |
| latency_ms | INTEGER NOT NULL | end-to-end |
| created_at | TIMESTAMPTZ NOT NULL DEFAULT now() | indexed |

**llm_usage** — one row per node invocation, not per request.

| column | type | notes |
| --- | --- | --- |
| id | UUID PK | |
| trace_id | UUID NOT NULL | indexed; joins to audit_trail |
| node | TEXT NOT NULL | CHECK IN ('understand','respond') |
| model | TEXT NOT NULL | resolved model id, not the tier name |
| prompt_tokens | INTEGER NOT NULL | |
| completion_tokens | INTEGER NOT NULL | |
| latency_ms | INTEGER NOT NULL | |
| created_at | TIMESTAMPTZ NOT NULL DEFAULT now() | |

**Deliberately excluded:** returned rows (PII — summarize, don't retain), `cost` (derive from
model+tokens at read time), `user_id` (auth out of scope), embedding columns (RAG out of scope),
`tenant_id` (blocked on §4).

## 6. API Design
JSON in, JSON out, on every endpoint. `trace_id` is echoed on every response including errors.

**POST /v1/query** — `{"question": string, "trace_id": uuid|null}`

200, route=answer:
```json
{"trace_id":"uuid","route":"answer","answer":"string","intent":"string",
 "params":{},"confidence":0.93,"row_count":12,"latency_ms":840}
```
200, route=clarified (below threshold — a question, never a guess):
```json
{"trace_id":"uuid","route":"clarified","clarifying_question":"string",
 "confidence":0.41,"candidate_intents":["string"],"latency_ms":310}
```
422 (bad body) / 500 (node or SQL failure):
```json
{"trace_id":"uuid","route":"error","error":{"code":"string","message":"string"}}
```

**GET /v1/traces/{trace_id}** — audit row plus its usage rows, for the §7 UI hop.
```json
{"trace_id":"uuid","question":"string","answer":"string|null","intent":"string|null",
 "params":{},"confidence":0.93,"route":"answer","row_count":12,"latency_ms":840,
 "created_at":"2026-08-20T00:00:00Z",
 "usage":[{"node":"understand","model":"string","prompt_tokens":0,
           "completion_tokens":0,"latency_ms":0}]}
```
404: `{"error":{"code":"trace_not_found","message":"string"}}`

**GET /v1/templates** — what the assistant can actually answer; drives UI affordances.
```json
{"templates":[{"intent":"string","description":"string","params_schema":{}}]}
```

**GET /health** — `{"status":"ok","db":"ok","version":"string"}`

## 7. Observability
One `trace_id` per request: minted by the UI if absent, else server-side, returned in the body and
in an `X-Trace-Id` header, persisted on `audit_trail` and every `llm_usage` row.

structlog JSON to stdout, `trace_id` bound once at request entry and inherited by both nodes. Each
node emits enter/exit: `understand` logs `{intent, confidence, params, model, tokens, latency_ms}`;
`process` logs `{intent, bound_params, row_count, sql_latency_ms, model, tokens, latency_ms}`.
Never log returned rows — count only, matching §5's exclusion.

## 8. Evaluation
A golden set of `(question → expected intent, expected params)` cases stored as fixtures, run under
pytest/pytest-asyncio with the LLM stubbed for unit runs and live for a nightly eval run.

Metrics per run: intent accuracy, param exact-match rate, clarify rate (should be high on
deliberately ambiguous cases, near zero on clear ones), false-answer rate (wrong intent answered
confidently — the metric that matters most), p50/p95 latency, tokens per query.

Invariant tests, independent of model quality:
- the model never emits SQL; every executed statement came from `query_templates`
- every execution is read-only and capped at `MAX_ROWS`
- per template, the bind names parsed from `sql_text` exactly equal the property names in
  `params_schema` — catches drift at review time instead of at query time

## 9. Model Routing
`understand` → cheap tier: classification into a fixed intent set with a typed schema, no prose.
`respond` → mid tier: grounded summarization of returned rows, where fluency shows.

Tier→model mapping lives in config, not in code, so it moves without a deploy. The resolved model
id is written to `llm_usage.model` so a routing change is visible in cost data. Pinned SDK versions
per `docs/versions.md`.
