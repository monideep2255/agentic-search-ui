import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
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
  },
});
