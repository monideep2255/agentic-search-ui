import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { defineConfig } from "vitest/config";
import type { Plugin } from "vite";
import react from "@vitejs/plugin-react";

// Card 60, second pass. `comments.legal` below keeps a package's own
// `@license` source comment, and that is all React, react-dom, and the
// scheduler need since Meta's build already puts one in every file. MUI
// carries no such comment in its compiled output at all, and neither do most
// other MIT dependencies, so `comments.legal` alone still drops MUI's notice.
// MIT requires the license TEXT to travel with the copy, not a source
// comment if one happens to exist, so this plugin reads each bundled
// package's own LICENSE file off disk and writes it into one file the build
// output carries alongside the bundle.
function thirdPartyNoticesPlugin(): Plugin {
  const SECTION_DELIMITER = "=".repeat(80);
  const LICENSE_FILENAMES = ["LICENSE", "LICENSE.md", "LICENCE"];

  // A module id looks like ".../node_modules/react/cjs/react.production.js"
  // or, scoped, ".../node_modules/@mui/material/index.js". The package root
  // is everything up to and including the (possibly scoped) package
  // directory; matching on the LAST "node_modules" segment handles a nested
  // copy correctly, since that is the copy actually bundled.
  function packageRootAndName(moduleId: string): { root: string; name: string } | null {
    const match = moduleId.match(/^(.*\/node_modules\/((?:@[^/]+\/)?[^/]+))\//);
    if (!match) return null;
    return { root: match[1], name: match[2] };
  }

  function licenseText(root: string): string {
    for (const filename of LICENSE_FILENAMES) {
      const licensePath = path.join(root, filename);
      if (existsSync(licensePath)) {
        return readFileSync(licensePath, "utf-8").trim();
      }
    }
    return "no license file found";
  }

  function packageVersion(root: string): string {
    const packageJsonPath = path.join(root, "package.json");
    if (!existsSync(packageJsonPath)) return "unknown";
    try {
      const parsed = JSON.parse(readFileSync(packageJsonPath, "utf-8")) as { version?: unknown };
      return typeof parsed.version === "string" ? parsed.version : "unknown";
    } catch {
      return "unknown";
    }
  }

  return {
    name: "third-party-notices",
    generateBundle(_options, bundle) {
      const packages = new Map<string, string>();
      for (const file of Object.values(bundle)) {
        if (file.type !== "chunk") continue;
        for (const moduleId of file.moduleIds) {
          const found = packageRootAndName(moduleId);
          if (found && !packages.has(found.name)) {
            packages.set(found.name, found.root);
          }
        }
      }

      // Sorted so the file's content, and therefore its hash-free bytes, is
      // reproducible across builds of the same dependency set.
      const names = [...packages.keys()].sort((a, b) => a.localeCompare(b));
      const sections = names.map((name) => {
        const root = packages.get(name) as string;
        return [
          SECTION_DELIMITER,
          `PACKAGE: ${name}`,
          `VERSION: ${packageVersion(root)}`,
          "LICENSE:",
          licenseText(root),
        ].join("\n");
      });
      sections.push(SECTION_DELIMITER);

      this.emitFile({
        type: "asset",
        fileName: "THIRD_PARTY_NOTICES.txt",
        source: sections.join("\n\n") + "\n",
      });
    },
  };
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), thirdPartyNoticesPlugin()],
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
  // Card 60. React, React DOM, its scheduler and MUI are MIT licensed, and MIT
  // requires their copyright and permission notices to travel with every copy.
  // Vite 8 minifies JavaScript with Oxc through Rolldown, not esbuild: the
  // `esbuild` block above only reaches the CSS minifier in this version, so
  // `esbuild.legalComments` is a no-op for the JS bundle. The setting has to
  // go here instead, on the output rolldown actually builds with.
  build: {
    rolldownOptions: {
      output: {
        comments: { legal: true },
      },
    },
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
