// Mirrors backend/app/schemas/query.py. Keep in sync by hand — there is no
// codegen step yet.

export interface QueryRequest {
  question: string;
  trace_id?: string | null;
}

export interface UsageEntry {
  node: "understand" | "respond";
  model: string;
  prompt_tokens: number;
  completion_tokens: number;
  latency_ms: number;
}

export type QueryResponse =
  | {
      trace_id: string;
      route: "answer";
      answer: string;
      intent: string | null;
      params: Record<string, unknown>;
      row_count: number | null;
      clarifying_question: null;
      candidate_intents: string[];
      confidence: number;
      latency_ms: number;
      usage: UsageEntry[];
      cost_usd: number;
    }
  | {
      trace_id: string;
      route: "clarified";
      answer: null;
      intent: null;
      params: Record<string, unknown>;
      row_count: null;
      clarifying_question: string;
      candidate_intents: string[];
      confidence: number;
      latency_ms: number;
      usage: UsageEntry[];
      cost_usd: number;
    };

// DESIGN.md §6 error envelope, produced by app/core/errors.py for every
// non-2xx response.
export interface ErrorEnvelope {
  trace_id: string | null;
  route: "error";
  error: {
    code: string;
    message: string;
  };
}
