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
 * Every read is `.catch()`ed to a placeholder. A journey must survive a
 * missing element: the run screen not being there IS the observation on a
 * run that failed, and throwing here would discard the remaining frames.
 */
async function describeFrame(page: Page): Promise<string> {
  const text = async (testId: string): Promise<string> => {
    try {
      const el = page.getByTestId(testId);
      if (!(await el.isVisible())) return "-";
      return ((await el.textContent()) ?? "").trim() || "-";
    } catch {
      return "-";
    }
  };

  const liveStep = await page
    .locator('[data-state="live"]')
    .first()
    .getAttribute("data-testid")
    .catch(() => null);

  const chips = await page
    .locator('[data-testid^="tool-chip"]')
    .count()
    .catch(() => 0);

  const answered = await page
    .getByTestId("answer-screen")
    .isVisible()
    .catch(() => false);

  return [
    `elapsed=${await text("run-elapsed")}`,
    `live=${liveStep ?? "-"}`,
    `chips=${chips}`,
    `answered=${answered}`,
  ].join("  ");
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

      await main
        .getByRole("button", { name: /search|ask|submit/i })
        .first()
        .click()
        .catch(() => undefined);

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
