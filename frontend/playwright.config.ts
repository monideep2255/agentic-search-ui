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
      // Fix set 6 item 6.1 (requirement D3): S3_E2E_REAL_MODEL is passed
      // THROUGH when it is set, and absent otherwise, so an ordinary run is
      // byte-for-byte the run it always was. `webServer.env` replaces the
      // inherited environment rather than extending it, which is why the
      // flag has to be forwarded by name here; it also means nothing else
      // from a developer's shell reaches the backend, which is the property
      // that keeps the default suite offline.
      //
      // `reuseExistingServer` is the trap worth naming: a fake-mode backend
      // already listening on this port is REUSED, flag or no flag, so
      // setting the flag alone does not guarantee a real backend.
      // `e2e/real-answer.spec.ts` therefore asks `/__e2e__/mode` before it
      // asks a question, and fails loudly rather than passing against the
      // fake.
      env: {
        PORT: String(BACKEND_PORT),
        ...(process.env.S3_E2E_REAL_MODEL
          ? { S3_E2E_REAL_MODEL: process.env.S3_E2E_REAL_MODEL }
          : {}),
      },
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
      // `--host 127.0.0.1` is load-bearing, not tidiness. Without it Vite binds
      // to [::1] only (IPv6 loopback), while the `url` below waits on
      // 127.0.0.1 (IPv4 loopback), so Playwright's readiness probe never
      // succeeds and every run dies on "Timed out waiting 30000ms from
      // config.webServer".
      //
      // This is the root cause of the webServer timeout carried as a
      // "pre-existing environment quirk" since build phase 3.3. The earlier
      // diagnosis started the dev server by hand and got HTTP 200 from
      // `localhost`, which resolves to ::1 on macOS, so it confirmed a
      // different address than the one Playwright actually probes.
      command: `npm run dev -- --port ${FRONTEND_PORT} --strictPort --host 127.0.0.1`,
      cwd: __dirname,
      // T-6.2-11: overridable, default UNCHANGED. A journey that films a
      // frontend change needs the real API behind it, because the mock
      // backend answers in milliseconds and the whole subject of journey 2
      // is a 12 to 14 second wait. Pointing the local frontend at a
      // deployed API is the only way to film a frontend change BEFORE it is
      // deployed, which is exactly when someone wants to look at it.
      //
      // Every ordinary run is unaffected: without the variable this is the
      // mock backend it always was, so no suite silently starts reaching
      // the internet.
      env: {
        VITE_API_BASE_URL: process.env.S3_E2E_API_BASE_URL ?? BACKEND_URL,
      },
      url: FRONTEND_URL,
      reuseExistingServer: !process.env.CI,
      timeout: 30_000,
      stdout: "pipe",
      stderr: "pipe",
    },
  ],
});
