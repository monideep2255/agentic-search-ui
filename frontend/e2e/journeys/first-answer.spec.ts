/**
 * Journey 1: first visit to first answer.
 *
 * `docs/build/UI_feedback.md`'s journey table, covering complaints 1 and 2: the landing
 * screen, the disclaimer, the question typed, every intermediate state
 * during the wait, and the final answer.
 *
 * Distinct from journey 2, which films only the WAIT at one frame a second.
 * This one films the whole arc a first-time visitor walks, including the two
 * screens journey 2 skips past: what someone sees before they have typed
 * anything, and what they are left looking at once the answer lands. Those
 * are where complaint 1 lives, and journey 2 cannot see either.
 *
 * CAPTURES, does not assert. See `_capture.ts`.
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

test.describe(
  JOURNEYS_ENABLED ? "journey 1: first answer" : "journey 1 (skipped: RUN_LIVE_JOURNEYS=1)",
  () => {
    test.skip(!JOURNEYS_ENABLED, "reaches the deployed app and spends a real guest answer");
    test.describe.configure({ timeout: 180_000 });

    test("first visit through to the answer", async ({ page }) => {
      const strip = new Filmstrip(page, outputDir("journey1_first_answer"), "Journey 1: first visit to first answer");
      await strip.begin();

      await page.setViewportSize({ width: 1440, height: 1000 });

      // Before the disclaimer is dismissed. A first-time visitor's actual
      // first screen, which every other spec in this repository clicks
      // through in its setup and therefore never looks at.
      await page.goto(process.env.S3_LIVE_WEB_URL ?? "", { waitUntil: "domcontentloaded" }).catch(() => undefined);
      await enterApp(page);
      await strip.capture("landing");

      const typed = await ask(page, BRCA1_QUESTION);
      strip.note(`submit clicked: ${typed}`);

      const landedAt = await filmUntilAnswered(page, strip, 30);
      strip.note(landedAt === null ? "NOT ANSWERED within 30 frames" : `answer landed at frame ${landedAt}`);

      // The answer screen itself, which is where complaint 1 is about.
      await strip.capture("answer");
      const blind = await missingSelectors(page, ["answer-meta"]);
      if (blind.length > 0) strip.note(`BLIND SELECTORS on the answer screen: ${blind.join(", ")}`);

      strip.write();
      expect(strip.frames, "the journey captured no frames").toBeGreaterThan(1);
    });
  },
);
