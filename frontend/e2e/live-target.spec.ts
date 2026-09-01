/**
 * Build phase 6.2, T-6.2-12. The structural half: no spec in this directory
 * may hardcode a deployment URL.
 *
 * Rewiring the two live diagnostics to `live-target.ts` fixes the two that
 * existed. It does nothing about the third one someone writes next week,
 * and the cost of that one is not a failing test: it is a browser run
 * quietly measuring production while its author believes they are looking
 * at their own branch, which is exactly how every measurement in
 * `UI_feedback.md` came to be taken against the wrong build.
 *
 * This is the same shape as build phase 4.14's fix for the CI gates, and
 * for the same reason. A convention that lives only in the two files that
 * currently follow it is not enforcement. Checking the whole directory is.
 *
 * Offline, so it runs in the ordinary suite rather than behind
 * `RUN_LIVE_DIAGNOSTICS`.
 */

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { expect, test } from "@playwright/test";

import { LIVE_API_URL, LIVE_WEB_URL } from "./live-target";

// `__dirname` does not exist here: this project is ESM, and Playwright
// reported it as a ReferenceError at collection time rather than as a
// failing test, so the arm would have been silently absent.
const E2E_DIR = path.dirname(fileURLToPath(import.meta.url));

// The one file allowed to name a deployment, because naming them is its
// entire job.
const TARGET_MODULE = "live-target.ts";

const DEPLOYMENT_HOST = /https:\/\/[a-z0-9-]*\.up\.railway\.app/gi;

function specFiles(): string[] {
  return fs
    .readdirSync(E2E_DIR)
    .filter((name) => name.endsWith(".ts") && name !== TARGET_MODULE)
    .sort();
}

test.describe("live target", () => {
  test("no spec hardcodes a deployment URL", () => {
    const offenders: string[] = [];

    for (const name of specFiles()) {
      const source = fs.readFileSync(path.join(E2E_DIR, name), "utf8");
      for (const match of source.matchAll(DEPLOYMENT_HOST)) {
        // A URL inside a comment is prose, not a target. Only an
        // occurrence that could be assigned or passed to `goto` matters,
        // and the cheap discriminator is whether it sits in a string
        // literal.
        const quoted =
          source[match.index! - 1] === '"' || source[match.index! - 1] === "'" ||
          source[match.index! - 1] === "`";
        if (quoted) offenders.push(`${name}: ${match[0]}`);
      }
    }

    expect(
      offenders,
      `these specs name a deployment directly instead of importing it from ` +
        `${TARGET_MODULE}. A hardcoded target cannot be pointed at the branch ` +
        `under test, and the failure is silent: the run passes while measuring ` +
        `the wrong build.\n  ${offenders.join("\n  ")}`,
    ).toEqual([]);
  });

  test("the default target is develop, never production", () => {
    // The direction of this assertion is the point. Defaulting to
    // production is not a preference this repository is neutral about: it
    // is what produced a whole feedback document measured against the
    // wrong build.
    expect(
      LIVE_WEB_URL,
      "the default web target must not be production",
    ).not.toContain("production");
    expect(
      LIVE_API_URL,
      "the default API target must not be production",
    ).not.toContain("production");
    expect(LIVE_WEB_URL).toContain("develop");
    expect(LIVE_API_URL).toContain("develop");
  });
});
