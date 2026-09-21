/**
 * Journey 2: the wait itself, as a per-second filmstrip.
 *
 * Build phase 6.2, T-6.2-11. `docs/build/UI_feedback.md` names this as the journey to
 * build FIRST, and gives the reason: the fragmentation complaint is
 * currently described in prose, and a filmstrip of the twelve-second wait
 * turns it into something anyone can look at and immediately agree or
 * disagree with.
 *
 * It earned that billing on its first working run. Against develop it showed
 * fifteen consecutive seconds in which NOTHING on screen changed, the same
 * live step and the same two tool chips throughout, with no answer at
 * twenty-five seconds where `docs/build/UI_feedback.md` had measured twelve to fourteen
 * (F-6.2-07).
 *
 * ## Three defects this file hit, which `_capture.ts` now owns for everyone
 *
 * Recorded here rather than only in the ledger, because each was a defect in
 * the INSTRUMENT that read as a defect in the product:
 *
 *   - The capture helper used auto-waiting Playwright locators, so on a page
 *     with no live step it blocked for the full 180-second timeout and the
 *     journey filmed one frame before dying.
 *   - Two of its five fields named testids that DO NOT EXIST and reported a
 *     plausible constant rather than an error, which nearly produced a
 *     confident wrong conclusion about the agent (F-6.2-06).
 *   - It silently swallowed a failed submit, so a broken journey looked like
 *     a broken product.
 *
 * CAPTURES, does not assert. See `_capture.ts` for that rule and why.
 */

import { expect, test } from "@playwright/test";

import {
  BRCA1_QUESTION,
  Filmstrip,
  JOURNEYS_ENABLED,
  ask,
  enterApp,
  filmUntilAnswered,
  missingSelectors,
  outputDir,
} from "./_capture";

/** The measured wait exceeded 25 seconds, so the budget is wider than that. */
const MAX_FRAMES = 35;

test.describe(
  JOURNEYS_ENABLED ? "journey 2: the wait" : "journey 2 (skipped: RUN_LIVE_JOURNEYS=1)",
  () => {
    test.skip(!JOURNEYS_ENABLED, "reaches the deployed app and spends a real guest answer");
    test.describe.configure({ timeout: 180_000 });

    test("film the wait, one frame a second", async ({ page }) => {
      const strip = new Filmstrip(page, outputDir("journey2_wait"), "Journey 2: the wait");
      await strip.begin();

      await page.setViewportSize({ width: 1440, height: 1000 });
      await enterApp(page);

      // Frame 0 is BEFORE submit, deliberately. The complaint starts at the
      // moment of submission, so the strip has to include what the page
      // looked like immediately before it.
      await strip.capture("before submit");

      strip.note(`submit clicked: ${await ask(page, BRCA1_QUESTION)}`);

      const landedAt = await filmUntilAnswered(page, strip, MAX_FRAMES);
      strip.note(
        landedAt === null
          ? `NOT ANSWERED within ${MAX_FRAMES} frames`
          : `answer landed at frame ${landedAt}`,
      );

      // Which of this strip's fields were blind on the final screen, written
      // into the evidence itself. F-6.2-06's durable fix: a reader sees
      // "this field was blind" rather than a plausible number.
      const blind = await missingSelectors(page, ["answer-meta", "run-elapsed"]);
      if (blind.length > 0) {
        strip.note(`selectors matching nothing at the end: ${blind.join(", ")}`);
      }

      strip.write();
      expect(strip.frames, "the journey captured no frames").toBeGreaterThan(1);
    });
  },
);
