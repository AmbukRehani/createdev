# createdev

A natural-language query assistant over a hiring database. Ask a question in plain English; a
two-node LangGraph pipeline classifies it into a curated SQL template, fills the parameters,
executes it read-only, and answers grounded in the real rows — or asks you to clarify if it isn't
confident enough. See [docs/design.MD](docs/design.MD) for the full design.

## Interact with the app

Once it's running (see [Run it locally](#run-it-locally-end-to-end) below), open the frontend and
ask something like:

- `top sources by hires in 2025`
- `average time to hire in Engineering in 2025`
- `interview pass rate for Senior Backend Engineer`
- `how are we doing` — deliberately vague; should come back asking you to clarify instead of
  guessing
- `time to hire in Enginering` — a typo'd department name; may clarify either via the confidence
  gate or by listing the real department names, depending on how confident the model is

Or call the API directly:

```bash
curl -s -X POST http://localhost:8000/api/v1/query \
  -H 'content-type: application/json' \
  -d '{"question":"top sources by hires in 2025"}' | python3 -m json.tool
```

Every response carries a `trace_id`. Look up what actually happened for one call — which nodes
ran, what each cost, how long each took:

```bash
curl -s http://localhost:8000/api/v1/traces/<trace_id> | python3 -m json.tool
```

Or see aggregate spend over a time window (default 24h):

```bash
curl -s "http://localhost:8000/api/v1/admin/cost?hours=24" | python3 -m json.tool
```

## Run it locally (end to end)

Prerequisites: Docker, Python 3.10 (pinned — see [docs/versions.md](docs/versions.md)), Node 18+,
and an OpenAI API key with access to whatever models you configure below.

**1. Start Postgres**

```bash
docker compose up -d
```

**2. Backend**

```bash
cd backend
python3 -m venv menv
source menv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env and fill in at least:
#   DATABASE_URL       postgresql+asyncpg://app:app@localhost:5432/hiretoday  (matches compose.yaml)
#   OPENAI_API_KEY      your key
#   MODEL_UNDERSTAND    a model your key has access to, e.g. gpt-4o-mini
#   MODEL_RESPOND       a model your key has access to, e.g. gpt-4o-mini
#   CONFIDENCE_THRESHOLD  e.g. 0.75
#   MAX_ROWS            e.g. 30

alembic upgrade head
python -m app.scripts.seed_sample_data
python -m app.scripts.seed_query_templates

uvicorn app.main:app --reload --port 8000
```

Confirm it's up: `curl http://localhost:8000/healthz` should return `{"status":"ok"}`.

**3. Frontend**

```bash
cd frontend
npm install
npm run dev
```

Open the URL Vite prints (typically `http://localhost:5173`). In dev, requests to `/api/*` are
proxied to `http://localhost:8000` automatically — no extra config needed.

## Deploying

### Frontend on Vercel

`frontend/vercel.json` is already set up (framework `vite`, build command, output directory). To
deploy:

1. Import the repo into Vercel, and set the project's **Root Directory** to `frontend`.
2. Set the **`VITE_API_BASE_URL`** environment variable to your hosted backend's URL (no trailing
   slash) — see [frontend/.env.example](frontend/.env.example). Locally this is left blank so
   requests stay relative and go through the Vite dev proxy; in production there's no dev proxy,
   so the frontend needs an absolute backend URL baked in at build time.
3. Deploy.

### Backend

Vercel runs Python as short-lived serverless functions — that's a mismatch for this backend, which
holds a pooled async Postgres connection, runs Alembic migrations, and makes LLM calls that can
take several seconds with retries. Host it somewhere that runs a normal long-lived process instead
— Railway, Render, and Fly.io are all reasonable fits for a FastAPI + Postgres app; this repo
doesn't include host-specific config for any of them, so treat the steps below as what any of them
need, not a tested walkthrough for one in particular:

1. A reachable Postgres instance (the `compose.yaml` one is local-only — most hosts offer a
   managed Postgres add-on, or use something like Neon/Supabase).
2. Set the same environment variables as `backend/.env.example` on the host.
3. Run `alembic upgrade head` and the two seed scripts once against that database (a one-off
   deploy step or shell session — not something that runs automatically on app startup, by
   design).
4. Start the app with `uvicorn app.main:app --host 0.0.0.0 --port $PORT` (or whatever port
   convention the host expects).
5. **Set `CORS_ORIGINS`** on the backend to include your Vercel deployment's URL — without this,
   the browser will block the frontend's requests even though the backend itself is reachable.

## Development

```bash
cd backend && pytest -v          # unit tests — FakeLLM throughout, no test touches a real provider
cd frontend && npm run typecheck # TypeScript, no emit
```

`.vscode/launch.json` has ready-made debug configs for stepping through a live request or a test
in VS Code.
