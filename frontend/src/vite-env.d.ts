/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Base URL of the deployed backend API (e.g. "https://api.example.com").
   * Leave unset for local dev — requests stay relative and go through the
   * Vite dev server's proxy (vite.config.ts) to http://localhost:8000. */
  readonly VITE_API_BASE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
