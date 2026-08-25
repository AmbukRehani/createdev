import type { ErrorEnvelope, QueryRequest, QueryResponse } from "./types";

// Empty string in local dev — requests stay relative and go through the
// Vite dev server's proxy. Set VITE_API_BASE_URL at build time to point a
// deployed frontend (e.g. on Vercel) at a separately-hosted backend.
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

export class ApiError extends Error {
  readonly code: string;
  readonly traceId: string | null;
  readonly status: number;

  constructor(message: string, code: string, traceId: string | null, status: number) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.traceId = traceId;
    this.status = status;
  }
}

function isErrorEnvelope(value: unknown): value is ErrorEnvelope {
  return (
    typeof value === "object" &&
    value !== null &&
    "error" in value &&
    typeof (value as { error?: unknown }).error === "object"
  );
}

export async function postQuery(request: QueryRequest): Promise<QueryResponse> {
  const res = await fetch(`${API_BASE_URL}/api/v1/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });

  const body: unknown = await res.json();

  if (!res.ok) {
    if (isErrorEnvelope(body)) {
      throw new ApiError(body.error.message, body.error.code, body.trace_id, res.status);
    }
    throw new ApiError("Request failed.", "unknown_error", null, res.status);
  }

  return body as QueryResponse;
}
