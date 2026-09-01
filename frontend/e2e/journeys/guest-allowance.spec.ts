/**
 * Journey 4: what the fifth and sixth guest questions look like.
 *
 * `UI_feedback.md` lists this as UNTESTED ENTIRELY. The server-side guest
 * allowance shipped in build phase 4.10 and carries five findings that are
 * about its PRESENTATION rather than its enforcement, all merged open:
 * `blocked_reason` is unread by the UI (F-4.10-05), the concurrent-run cap
 * equals the free allowance (F-4.10-A-10), a lifetime allowance is labelled
 * daily (F-4.10-A-11), the remaining-dots degrade toward a refusal
 * (F-4.10-A-12), and a first-time visitor never sees the dots at all
 * (F-4.10-A-13, a product decision).
 *
 * Every one of those is about what a person SEES when they run out, and
 * nobody has watched it happen in a browser. This films it.
 *
 * ## Cost, stated plainly because it is the expensive journey
 *
 * SIX real answers on the deployed app, which is the entire allowance of one
 * guest identity plus the refusal. That is the point rather than an
 * overrun: the allowance cannot be observed without exhausting it. Run it
 * deliberately and rarely.
 *
 * The questions are deliberately cheap and near-identical, so the run
 * exercises the ALLOWANCE rather than the agent, and so the response cache
 * has a chance to absorb some of the cost.
 */

import { expect, test } from "@playwright/test";

import {
  Filmstrip,
  JOURNEYS_ENABLED,
  ask,
  enterApp,
  filmUntilAnswered,
  outputDir,
} from "./_capture";

/** Six, because the allowance is five and the sixth is the case under test. */
const QUESTIONS = [
  "Which diseases are associated with BRCA1?",
  "Which diseases are associated with TP53?",
  "Which diseases are associated with BRCA2?",
  "Which diseases are associated with EGFR?",
  "Which diseases are associated with KRAS?",
  "Which diseases are associated with PTEN?",
];

test.describe(
  JOURNEYS_ENABLED ? "journey 4: guest allowance" : "journey 4 (skipped: RUN_LIVE_JOURNEYS=1)",
  () => {
    test.skip(
      !JOURNEYS_ENABLED,
      "spends a guest's ENTIRE five-answer allowance plus the refusal",
    );
    test.describe.configure({ timeout: 600_000 });

    test("ask six times as a guest", async ({ page }) => {
      const strip = new Filmstrip(
        page,
        outputDir("journey4_guest_allowance"),
        "Journey 4: guest allowance exhaustion",
      );
      await strip.begin();
      await page.setViewportSize({ width: 1440, height: 1000 });

      await enterApp(page);
      await strip.capture("before any question");

      for (const [index, question] of QUESTIONS.entries()) {
        const n = index + 1;
        strip.note("");
        strip.note(`--- question ${n} of ${QUESTIONS.length}: ${question}`);

        if (n > 1) {
          // Back to a fresh search rather than the follow-up field, since a
          // follow-up is a different code path and this journey is about the
          // allowance.
          await page
            .getByRole("button", { name: /new search/i })
            .click({ timeout: 10_000 })
            .catch(() => undefined);
        }

        const submitted = await ask(page, question);
        strip.note(`submit clicked: ${submitted}`);

        const landed = await filmUntilAnswered(page, strip, 30, `q${n}`);
        strip.note(landed === null ? `q${n} NOT ANSWERED in 30 frames` : `q${n} landed at frame ${landed}`);
        await strip.capture(`q${n} final`);

        // What the user is told about how much they have left, at every
        // step rather than only at the end. F-4.10-A-12 is that this
        // degrades toward a refusal, which is only visible as a SEQUENCE.
        const shown = await page
          .evaluate(() => document.body.innerText.slice(0, 900))
          .catch(() => "");
        strip.note(`  visible text after q${n}:`);
        strip.note("  ```");
        strip.note(shown);
        strip.note("  ```");
      }

      strip.write();
      expect(strip.frames, "the journey captured no frames").toBeGreaterThan(1);
    });
  },
);
