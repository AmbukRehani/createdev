import { ConfidenceBadge } from "./ConfidenceBadge";
import { API_BASE_URL } from "./api/client";
import type { QueryResponse } from "./api/types";

interface ResponsePanelProps {
  response: QueryResponse;
}

export function ResponsePanel({ response }: ResponsePanelProps) {
  const body =
    response.route === "answer" ? response.answer : response.clarifying_question;

  return (
    <section className="response-panel" aria-live="polite">
      <p className="response-panel__body">{body}</p>
      <ConfidenceBadge confidence={response.confidence} />
      <footer className="response-panel__footer">
        trace_id:{" "}
        <a
          href={`${API_BASE_URL}/api/v1/traces/${response.trace_id}`}
          target="_blank"
          rel="noreferrer"
          className="response-panel__trace-link"
        >
          {response.trace_id}
        </a>{" "}
        &middot; cost_usd: {response.cost_usd.toFixed(6)}
      </footer>
    </section>
  );
}
