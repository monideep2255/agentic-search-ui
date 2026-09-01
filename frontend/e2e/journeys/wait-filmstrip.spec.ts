/**
 * Journey 2: the wait itself, as a per-second filmstrip.
 *
 * Build phase 6.2, T-6.2-11. `UI_feedback.md` names this as the journey to
 * build FIRST, and gives the reason: the fragmentation complaint is
 * currently described in prose, and a filmstrip of the twelve-second wait
 * turns it into something anyone can look at and immediately agree or
 * disagree with.
 *
 * ## This CAPTURES, it does not ASSERT
 *
 * That is the rule for every journey in this directory, from
 * `UI_feedback.md`: "None of them assert. They CAPTURE. A journey that
 * fails a strict assertion stops and tells you nothing about the other
 * seven steps, and the point here is to see the whole flow."
 *
 * So this file has no `expect` on the product. It walks the flow, takes a
 * frame a second, and writes them out. If the answer never arrives, the
 * filmstrip of it never arriving is exactly the evidence wanted. The one
 * thing it does enforce is on ITSELF: that it captured frames at all, since
 * a journey that silently captured nothing is worse than one that failed.
 *
 * ## Where the frames go
 *
 * `docs/build/design/evidence/<date>_journey2_wait/`, dated, so a later run
 * can be compared against this one rather than against memory. Committing
 * them is deliberate: the whole point is that a human or an agent can look
 * at the same pictures later.
 *
 * Runs against DEVELOP by default, via `live-target.ts` (T-6.2-12). Gated
 * behind RUN_LIVE_JOURNEYS, since it reaches the public internet and spends
 * one of a real guest's five answers.
 */

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { expect, test, type Page } from "@playwright/test";

import { LIVE_WEB_URL, describeTarget } from "../live-target";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const EVIDENCE_DIR = path.resolve(HERE, "../../../docs/build/design/evidence");

const QUESTION = "Which diseases are associated with BRCA1?";

/** How long to keep filming. The measured wait is 12 to 14 seconds. */
const MAX_FRAMES = 25;

const ENABLED = process.env.RUN_LIVE_JOURNEYS === "1";

function outputDir(): string {
  const date = new Date().toISOString().slice(0, 10);
  const dir = path.join(EVIDENCE_DIR, `${date}_journey2_wait`);
  fs.mkdirSync(dir, { recursive: true });
  return dir;
}

async function enterApp(page: Page): Promise<void> {
  await page.goto(LIVE_WEB_URL, { waitUntil: "domcontentloaded" });
  const dialog = page.getByTestId("disclaimer-modal");
  if (await dialog.isVisible().catch(() => false)) {
    await dialog.getByRole("checkbox").check();
    await dialog.getByRole("button", { name: /continue/i }).click();
  }
}

/**
 * What the page shows at this instant, in one line, so the filmstrip is
 * readable without opening 25 images.
 *
 * ONE `page.evaluate`, and that is the whole design of this function rather
 * than a style choice. The first version used Playwright locators, and
 * `locator.getAttribute()` AUTO-WAITS: with no live step on the page it
 * blocked for the full 180-second test timeout on the first frame, so the
 * journey captured frame 0 and then died having filmed nothing. A capture
 * helper that can block is a capture helper that can lose the recording.
 *
 * `page.evaluate` reads the DOM as it is at this instant and returns. It
 * cannot wait, so it cannot hang. The whole call is wrapped so that a page
 * that has navigated or closed yields a placeholder rather than throwing,
 * because a missing page IS the observation on a run that died.
 */
async function describeFrame(page: Page): Promise<string> {
  try {
    return await page.evaluate(() => {
      const text = (testId: string): string => {
        const el = document.querySelector(`[data-testid="${testId}"]`);
        return el?.textContent?.trim() || "-";
      };
      const live = document.querySelector('[data-state="live"]');
      const liveName = live?.getAttribute("data-testid") ?? "-";
      // `tool-${call.name}` (RunScreen.tsx), NOT `tool-chip`. The first
      // version of this helper guessed `tool-chip` and `answer-screen`, and
      // NEITHER EXISTS. Both reported a plausible constant rather than an
      // error, `chips=0` and `answered=false` on every frame of a real run,
      // so the filmstrip read as "no tool ever fired and the answer never
      // landed" when in fact the instrument was blind. A capture that
      // silently reports a plausible wrong value is worse than one that
      // crashes, and it nearly produced a confident wrong conclusion about
      // the product from evidence that was about this file.
      const chips = document.querySelectorAll('[data-testid^="tool-"]').length;
      const answered = document.querySelector('[data-testid="answer-meta"]') !== null;
      const stepper = document.querySelectorAll('[data-testid^="step-"]').length > 0;
      return [
        `elapsed=${text("run-elapsed")}`,
        `live=${liveName}`,
        `chips=${chips}`,
        `stepper=${stepper}`,
        `answered=${answered}`,
      ].join("  ");
    });
  } catch {
    return "page unavailable";
  }
}

test.describe(
  ENABLED ? "journey 2: the wait" : "journey 2: the wait (skipped: set RUN_LIVE_JOURNEYS=1)",
  () => {
    test.skip(!ENABLED, "reaches the deployed app and spends a real guest answer");
    test.describe.configure({ timeout: 180_000 });

    test("film the wait, one frame a second", async ({ page }) => {
      const dir = outputDir();
      const target = await describeTarget();
      const log: string[] = [`# Journey 2: the wait`, ``, `target: ${target}`, ``];

      await page.setViewportSize({ width: 1440, height: 1000 });
      await enterApp(page);

      const main = page.getByRole("main");
      await main
        .getByRole("textbox", { name: /question/i })
        .fill(QUESTION)
        .catch(() => undefined);

      // Frame 0 is BEFORE submit, deliberately. The complaint starts at the
      // moment of submission, so the filmstrip has to include what the page
      // looked like immediately before it.
      await page.screenshot({ path: path.join(dir, "frame-00.png") });
      log.push(`frame-00  (before submit)  ${await describeFrame(page)}`);

      // The accessible name is "Search the knowledge graph"
      // (`HomeScreen.tsx`). Whether the click LANDED is recorded rather than
      // swallowed: the first run of this journey silently failed to submit
      // and the filmstrip could not say so, which made a broken journey look
      // like a broken product.
      const submitted = await main
        .getByRole("button", { name: /search the knowledge graph/i })
        .click({ timeout: 10_000 })
        .then(() => true)
        .catch(() => false);
      log.push(`submit clicked: ${submitted}`);

      let captured = 1;
      for (let frame = 1; frame <= MAX_FRAMES; frame += 1) {
        const line = await describeFrame(page);
        const name = `frame-${String(frame).padStart(2, "0")}.png`;
        await page.screenshot({ path: path.join(dir, name) });
        log.push(`${name}  ${line}`);
        captured += 1;

        if (line.includes("answered=true")) {
          log.push(``, `answer landed at frame ${frame}`);
          break;
        }
        await page.waitForTimeout(1000);
      }

      fs.writeFileSync(path.join(dir, "filmstrip.md"), log.join("\n") + "\n");
      console.log(`[journey 2] ${captured} frames -> ${dir}`);

      // The ONLY assertion, and it is about this journey rather than about
      // the product: a run that captured nothing is not evidence, and a
      // silent zero-frame pass would be read as "the wait looked fine".
      expect(captured, "the journey captured no frames").toBeGreaterThan(1);
    });
  },
);
