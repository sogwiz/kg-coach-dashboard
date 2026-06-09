/// <reference types="vite/client" />

interface ImportMetaEnv {
  /**
   * Base URL prepended to every backend API request.
   *
   * - Local dev: leave unset ("") so paths stay /api/* and /health and the
   *   Vite proxy (vite.config.ts) forwards them to the FastAPI dev server.
   * - Vercel (multi-service deploy): set to "/_/backend" so requests hit the
   *   backend service's routePrefix; Vercel strips the prefix and FastAPI
   *   sees /api/* and /health at its own root.
   */
  readonly VITE_API_BASE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
