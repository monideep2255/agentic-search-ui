import path from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig, devices } from "@playwright/test";

/**
 * T-1.2-07: drives a real browser against the real Vite dev server AND the
 * real FastAPI backend. The backend's outbound LLM call is faked (never a
 * real provider, never a real API key), everything else, auth, the run
 * registry, real SSE streaming, real cost-cap enforcement, the real
 * five-node LangGraph loop, is exercised for real. See
 * `tests/e2e_support/mock_llm_backend.py`'s module docstring for the full
 * "why" behind every non-obvious choice this config depends on: the fixed
 * `PER_QUERY_COST_CAP_USD=0.02` (the one code path in this build phase
 * that emits a real `token` event), the CORS middleware (why a Vite proxy
 * was rejected in favor of it), and the `/__e2e__/run_status` route (the
 * only way to prove a stopped run's server-side task was genuinely
 * cancelled, not just that the browser stopped listening).
 *
 * Both servers use fixed, non-default ports (5273 frontend, 8931 backend)
 * with no fallback (`--strictPort` on the Vite side), so this suite never
 * silently attaches to a developer's own already-running dev server
 * (default 5173) or backend (README's default 8000) and never collides
 * with one either.
 */

const FRONTEND_PORT = 5273;
const BACKEND_PORT = 8931;
const FRONTEND_URL = `http://127.0.0.1:${FRONTEND_PORT}`;
// Exported (a named export alongside this file's default export) so the
// spec file can poll `mock_llm_backend.py`'s `/__e2e__/run_status` route
// without duplicating this port as an untracked magic number.
export const BACKEND_URL = `http://127.0.0.1:${BACKEND_PORT}`;

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(__dirname, "..");

export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  retries: 0,
  reporter: "list",
  use: {
    baseURL: FRONTEND_URL,
    trace: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: [
    {
      // Runs from the repo root, not `frontend/`: `tests.e2e_support
      // .mock_llm_backend` is a module under the repo's top-level `tests`
      // package (the same package pytest already runs from), not part of
      // the frontend build.
      command: "python3 -m tests.e2e_support.mock_llm_backend",
      cwd: REPO_ROOT,
      env: { PORT: String(BACKEND_PORT) },
      url: `${BACKEND_URL}/health`,
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
      stdout: "pipe",
      stderr: "pipe",
    },
    {
      // `VITE_API_BASE_URL` points `lib/api.ts`'s fetch calls at the
      // backend's absolute URL; without it `DEFAULT_BASE_URL` defaults to
      // same-origin, which would target the Vite dev server itself.
      command: `npm run dev -- --port ${FRONTEND_PORT} --strictPort`,
      cwd: __dirname,
      env: { VITE_API_BASE_URL: BACKEND_URL },
      url: FRONTEND_URL,
      reuseExistingServer: !process.env.CI,
      timeout: 30_000,
      stdout: "pipe",
      stderr: "pipe",
    },
  ],
});
