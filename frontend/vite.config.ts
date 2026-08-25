import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // Build phase 4.12. `vite preview` refuses any request whose Host header it
  // does not recognise, and returns 403 with "Blocked request. This host ...
  // is not allowed." That is a deliberate anti-DNS-rebinding control, not a
  // bug, and it fires the moment the preview server sits behind a proxy on a
  // hostname the build never knew about.
  //
  // Set HERE rather than as a `--allowedHosts` CLI flag, which was tried
  // first and silently did not arrive: the deploy log showed vite receiving
  // only `--host 0.0.0.0 --port 8080`, the flag having been dropped somewhere
  // in the `npm run preview -- ...` chain. Vite's own error message names this
  // file as the place to fix it, and a config value cannot be lost in
  // argument forwarding.
  //
  // The host is listed explicitly rather than using `allowedHosts: true`,
  // which disables the check entirely. This is a demo deployment, but a
  // blanket allow would be a control switched off to make one URL work.
  preview: {
    allowedHosts: ["search-agent-web-production.up.railway.app"],
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/setupTests.ts"],
    globals: true,
    // T-1.2-07: without this, vitest's default test glob
    // (`**/*.{test,spec}.*`) also matches `e2e/*.spec.ts`, the Playwright
    // spec this ticket adds. Playwright specs import `test`/`expect` from
    // `@playwright/test`, drive a real browser, and are run by `npx
    // playwright test`, never by vitest; letting vitest pick one up would
    // fail it outright (no browser, no page fixture) and is unrelated to
    // this project's unit-test suite. Judgment call, logged in
    // DECISIONS.md.
    exclude: ["**/node_modules/**", "**/dist/**", "e2e/**"],
    /*
     * 15s, not vitest's 5s default. Build phase 4.9.
     *
     * TWO causes were found, and this is only the second of them, which is
     * worth stating because the first explanation was incomplete and the
     * incomplete version would have looked like it worked.
     *
     * The first and larger cause was a leak in this phase's own gate: a
     * `ReadableStream` left unclosed to simulate a run in flight held a reader
     * open for the file's lifetime, and unrelated tests in other files then
     * timed out at 15s and once at 23s. Closing it fixed six consecutive runs.
     *
     * The second is genuine contention. With the leak fixed but the default
     * timeout restored, three of five full runs still failed, always on a
     * ~5000ms timeout, always a different set, and every implicated file
     * passed alone. This phase took the suite from 131 tests to 146 and the
     * new ones render the whole App and stream real SSE frames through it.
     *
     * A deadline, not an assertion. Every check must still pass, and a genuine
     * hang still fails the run, 15s later. Verified at six consecutive clean
     * full runs with both fixes in place, against three failures in five
     * without this one.
     */
    testTimeout: 15_000,
  },
});
