import { useState, type FormEvent } from "react";
import { ApiError } from "./api/client";
import { useSubmitQuery } from "./api/useSubmitQuery";
import { ResponsePanel } from "./ResponsePanel";

export default function App() {
  const [question, setQuestion] = useState("");
  const { mutate, data, error, isPending } = useSubmitQuery();

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = question.trim();
    if (!trimmed) return;
    mutate({ question: trimmed });
  }

  return (
    <main className="page">
      <h1>NL Query Assistant</h1>

      <form className="query-form" onSubmit={handleSubmit}>
        <input
          type="text"
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          placeholder="Ask a question about your data…"
          aria-label="Question"
        />
        <button type="submit" disabled={isPending || question.trim() === ""}>
          {isPending ? "Asking…" : "Ask"}
        </button>
      </form>

      {error && (
        <section className="response-panel response-panel--error" role="alert">
          <p className="response-panel__body">
            {error instanceof ApiError ? error.message : "Something went wrong."}
          </p>
          {error instanceof ApiError && error.traceId && (
            <footer className="response-panel__footer">trace_id: {error.traceId}</footer>
          )}
        </section>
      )}

      {data && <ResponsePanel response={data} />}
    </main>
  );
}
