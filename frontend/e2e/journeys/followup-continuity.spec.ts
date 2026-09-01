/**
 * Journey 3: does a follow-up continue the thread?
 *
 * `UI_feedback.md` complaint 3, and the journey table's exact framing: ask,
 * then ask a DEPENDENT follow-up such as "what variants cause it", and
 * capture whether the second answer knows what "it" refers to.
 *
 * This journey is evidence for a PRODUCT DECISION, not a bug report, and
 * that shapes what it does. `frontend/src/stubs/registry.ts` already states
 * the current behaviour in the product's own words, "a follow-up field with
 * suggested hints, which starts a fresh run", and the interface says so to
 * the user too. So the question is not whether the code matches its spec. It
 * is what a person experiences when they type "what variants cause it", and
 * that is a thing to look at rather than assert.
 *
 * T-6.2-07 is the ticket, and it is blocked on the product owner choosing
 * what a follow-up turn carries forward. This strip is what that choice
 * should be made against.
 *
 * Spends TWO guest answers.
 */

import { expect, test } from "@playwright/test";

import {
  BRCA1_QUESTION,
  Filmstrip,
  JOURNEYS_ENABLED,
  ask,
  enterApp,
  filmUntilAnswered,
  outputDir,
} from "./_capture";

/**
 * The pronoun is the whole point. "it" is resolvable only from the previous
 * turn, so an answer that handles this has carried something forward and an
 * answer that asks which disease has not.
 */
const DEPENDENT_FOLLOW_UP = "What variants cause it?";

test.describe(
  JOURNEYS_ENABLED ? "journey 3: follow-up continuity" : "journey 3 (skipped: RUN_LIVE_JOURNEYS=1)",
  () => {
    test.skip(!JOURNEYS_ENABLED, "spends TWO real guest answers");
    test.describe.configure({ timeout: 240_000 });

    test("a dependent follow-up, and whether the thread survives it", async ({ page }) => {
      const strip = new Filmstrip(page, outputDir("journey3_followup"), "Journey 3: follow-up continuity");
      await strip.begin();
      await page.setViewportSize({ width: 1440, height: 1000 });

      await enterApp(page);
      strip.note(`turn 1: ${BRCA1_QUESTION}`);
      strip.note(`submit clicked: ${await ask(page, BRCA1_QUESTION)}`);
      const first = await filmUntilAnswered(page, strip, 30, "turn 1");
      strip.note(first === null ? "turn 1 NOT ANSWERED" : `turn 1 landed at frame ${first}`);
      await strip.capture("turn 1 answer");

      // The follow-up field is a different control from the landing search
      // box, and it is the one under test.
      const followUp = page.getByRole("textbox", { name: /follow-up/i });
      const asked = await followUp
        .fill(DEPENDENT_FOLLOW_UP, { timeout: 10_000 })
        .then(async () => {
          await page.getByRole("button", { name: /^ask$/i }).click({ timeout: 10_000 });
          return true;
        })
        .catch(() => false);
      strip.note(`turn 2 (${DEPENDENT_FOLLOW_UP}) submitted: ${asked}`);

      const second = await filmUntilAnswered(page, strip, 30, "turn 2");
      strip.note(second === null ? "turn 2 NOT ANSWERED" : `turn 2 landed at frame ${second}`);
      await strip.capture("turn 2 answer");

      // Recorded, never asserted: whether the second answer resolved the
      // pronoun is a judgement a human makes from the text, and encoding a
      // guess at it here would turn a product question into a red test.
      const answerText = await page
        .evaluate(() => document.body.innerText.slice(0, 1200))
        .catch(() => "");
      strip.note("");
      strip.note("turn 2 answer text, for the reader to judge whether 'it' resolved:");
      strip.note("```");
      strip.note(answerText);
      strip.note("```");

      strip.write();
      expect(strip.frames, "the journey captured no frames").toBeGreaterThan(1);
    });
  },
);
