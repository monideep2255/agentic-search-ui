/**
 * Shared machinery for the journeys in this directory.
 *
 * Build phase 6.2, T-6.2-11. Extracted after journey 2 rather than before,
 * because journey 2 hit three defects that every other journey would
 * otherwise have inherited one copy each of:
 *
 *   - The capture helper used auto-waiting Playwright locators, so on a page
 *     with no matching element it blocked for the FULL test timeout and the
 *     journey filmed one frame before dying. `snapshot` below is a single
 *     `page.evaluate`, which reads the DOM as it is and returns. It cannot
 *     wait, so it cannot hang.
 *   - Two of its five fields named testids that DO NOT EXIST and reported a
 *     plausible constant rather than an error, which nearly produced a
 *     confident wrong conclusion about the product (F-6.2-06). Hence
 *     `assertSelectorsExist` below: a journey states which testids it
 *     depends on, and is told at run time if one of them matches nothing.
 *   - It hardcoded nothing, but only because `live-target.ts` already
 *     existed. Journeys import their target from there (T-6.2-12).
 *
 * ## The rule for everything in this directory
 *
 * From `docs/build/UI_feedback.md`: "None of them assert. They CAPTURE. A journey that
 * fails a strict assertion stops and tells you nothing about the other seven
 * steps, and the point here is to see the whole flow."
 *
 * So a journey carries no `expect` about the product. If the answer never
 * arrives, a filmstrip of it never arriving is the evidence wanted. The only
 * assertions allowed are about the JOURNEY: that it captured frames, and
 * that the testids it reads actually exist. Those two are what stop a broken
 * instrument from being read as a broken product.
 */

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import type { Page } from "@playwright/test";

import { LIVE_WEB_URL, describeTarget } from "../live-target";

const HERE = path.dirname(fileURLToPath(import.meta.url));

export const EVIDENCE_ROOT = path.resolve(
  HERE,
  "../evidence",
);

/** Gate for every journey. They reach the internet and spend real budget. */
export const JOURNEYS_ENABLED = process.env.RUN_LIVE_JOURNEYS === "1";

export const BRCA1_QUESTION = "Which diseases are associated with BRCA1?";

/**
 * A dated output directory, one per journey, so a later run is compared
 * against a named earlier one rather than against memory.
 */
export function outputDir(journey: string): string {
  const date = new Date().toISOString().slice(0, 10);
  const dir = path.join(EVIDENCE_ROOT, `${date}_${journey}`);
  fs.mkdirSync(dir, { recursive: true });
  return dir;
}

export class Filmstrip {
  private readonly lines: string[] = [];
  private frame = 0;

  constructor(
    private readonly page: Page,
    private readonly dir: string,
    title: string,
  ) {
    this.lines.push(`# ${title}`, "");
  }

  async begin(): Promise<void> {
    this.lines.push(`target: ${await describeTarget()}`, "");
  }

  note(text: string): void {
    this.lines.push(text);
  }

  /** One frame plus its one-line state summary. Never throws. */
  async capture(label: string): Promise<void> {
    const name = `frame-${String(this.frame).padStart(2, "0")}.png`;
    this.frame += 1;
    let state = "page unavailable";
    try {
      state = await snapshot(this.page);
    } catch {
      /* a closed or navigating page IS the observation; keep filming */
    }
    try {
      await this.page.screenshot({ path: path.join(this.dir, name) });
    } catch {
      /* same */
    }
    this.lines.push(`${name}  ${label.padEnd(22)} ${state}`);
  }

  get frames(): number {
    return this.frame;
  }

  write(): void {
    fs.writeFileSync(
      path.join(this.dir, "filmstrip.md"),
      this.lines.join("\n") + "\n",
    );
  }
}

/**
 * The page's visible state at this instant, as one line.
 *
 * Every testid here is one this repository actually renders, checked rather
 * than guessed after F-6.2-06. `assertSelectorsExist` is how a journey keeps
 * that true as the UI changes.
 */
export async function snapshot(page: Page): Promise<string> {
  return page.evaluate(() => {
    const text = (testId: string): string => {
      const el = document.querySelector(`[data-testid="${testId}"]`);
      return el?.textContent?.trim().slice(0, 40) || "-";
    };
    const live = document.querySelector('[data-state="live"]');
    return [
      `elapsed=${text("run-elapsed")}`,
      `live=${live?.getAttribute("data-testid") ?? "-"}`,
      `chips=${document.querySelectorAll('[data-testid^="tool-"]').length}`,
      `stepper=${document.querySelectorAll('[data-testid^="step-"]').length > 0}`,
      `answered=${document.querySelector('[data-testid="answer-meta"]') !== null}`,
    ].join("  ");
  });
}

/**
 * Report which of the testids a journey depends on match nothing right now.
 *
 * The direct fix for F-6.2-06. That defect was not a typo so much as a
 * missing feedback loop: a selector matching nothing is indistinguishable
 * from a thing that is legitimately absent, and both render as a tidy `0`.
 * Returning the misses lets a journey WRITE THEM INTO ITS OWN FILMSTRIP, so
 * a reader of the evidence sees "this field was blind" instead of a
 * plausible number.
 *
 * Deliberately not an assertion. A testid can be legitimately absent on the
 * screen a journey happens to be on, and failing there would break the
 * capture-not-assert rule.
 */
export async function missingSelectors(
  page: Page,
  testIds: string[],
): Promise<string[]> {
  return page.evaluate(
    (ids) => ids.filter((id) => document.querySelector(`[data-testid="${id}"]`) === null),
    testIds,
  );
}

/** Land on the app and clear the disclaimer gate if it is showing. */
export async function enterApp(page: Page, url: string = LIVE_WEB_URL): Promise<void> {
  await page.goto(url, { waitUntil: "domcontentloaded" });
  const dialog = page.getByTestId("disclaimer-modal");
  if (await dialog.isVisible().catch(() => false)) {
    await dialog.getByRole("checkbox").check().catch(() => undefined);
    await dialog
      .getByRole("button", { name: /continue/i })
      .click()
      .catch(() => undefined);
  }
}

/**
 * Ask a question. Returns whether the submit actually landed.
 *
 * Whether the click worked is RECORDED rather than swallowed: journey 2's
 * first run silently failed to submit, and a filmstrip that cannot say so
 * makes a broken journey look like a broken product.
 */
export async function ask(page: Page, question: string): Promise<boolean> {
  const main = page.getByRole("main");
  const filled = await main
    .getByRole("textbox", { name: /question/i })
    .fill(question, { timeout: 10_000 })
    .then(() => true)
    .catch(() => false);
  if (!filled) return false;
  return main
    .getByRole("button", { name: /search the knowledge graph/i })
    .click({ timeout: 10_000 })
    .then(() => true)
    .catch(() => false);
}

/**
 * Film until the answer lands or the frame budget runs out.
 *
 * Returns the frame at which it landed, or null. Null is a legitimate
 * result: journey 2 recorded a develop run that had not answered after 25
 * seconds, which is the single most useful thing it found.
 */
export async function filmUntilAnswered(
  page: Page,
  strip: Filmstrip,
  maxFrames: number,
  label = "waiting",
): Promise<number | null> {
  for (let frame = 1; frame <= maxFrames; frame += 1) {
    await strip.capture(label);
    const landed = await page
      .evaluate(() => document.querySelector('[data-testid="answer-meta"]') !== null)
      .catch(() => false);
    if (landed) return frame;
    await page.waitForTimeout(1000);
  }
  return null;
}
