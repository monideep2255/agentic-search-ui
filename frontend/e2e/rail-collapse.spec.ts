/**
 * The stored-searches rail's collapse control, measured in a real browser.
 *
 * F-4.8-P-03. The vitest premise gate (`src/railCollapsePremise.test.tsx`)
 * asserts DOM order and state; this file asserts GEOMETRY and the responsive
 * rule, which jsdom cannot see. Both blind spots are named in that file's
 * coverage statement, and this is what closes them.
 *
 * WHY GEOMETRY IS A SEPARATE CHECK AND NOT A NICETY. Mutation-testing the
 * vitest gate proved the gap rather than assuming it: adding `order: -1` to the
 * content column moves the rail to the visual RIGHT of the page while leaving
 * DOM order untouched, and every clause in the vitest gate stayed green. That
 * is the same class of defect as this phase's two post-merge layout findings
 * and all three of the product owner's, every one of which survived a green
 * suite because nothing in this repository measured where anything landed.
 *
 * The tolerance below is deliberately loose. The point is to catch a rail that
 * has moved to the other side of the page or stopped occupying its slot, not to
 * pin a padding value that a future design pass may legitimately change.
 */

import { randomUUID } from "node:crypto";
import { expect, test, type Page } from "@playwright/test";

const TEST_PASSWORD = "Str0ngPassw0rd!";

/** The prototype's `#railStub` width, from `prototype/app.html`. */
const STRIP_WIDTH = 46;

/** The prototype's `@media (max-width:860px)` rule hides rail and strip. */
const NARROW_VIEWPORT = { width: 800, height: 900 };

const toggle = (page: Page) =>
  page.getByRole("banner").getByRole("button", { name: /show or hide your searches/i });

/**
 * Sign up, ask one question, and land with a rail that holds something.
 *
 * The run does not need to complete: the rail is populated at ask time, and
 * this file is about the rail rather than the answer. Waiting for the run
 * heading is what proves we left the landing screen.
 */
async function signInAndAsk(page: Page): Promise<void> {
  await page.goto("/");
  const dialog = page.getByTestId("disclaimer-modal");
  if (await dialog.isVisible().catch(() => false)) {
    await dialog.getByRole("checkbox").check();
    await dialog.getByRole("button", { name: /continue/i }).click();
  }
  await page
    .getByRole("navigation", { name: /main/i })
    .getByRole("button", { name: /log in/i })
    .click();
  await page.getByLabel("Email").fill(`rail-${randomUUID()}@example.com`);
  await page.getByLabel("Password").fill(TEST_PASSWORD);
  await page.getByRole("button", { name: "Sign up" }).click();

  const main = page.getByRole("main");
  await main
    .getByRole("textbox", { name: /question/i })
    .fill("Which diseases are associated with BRCA1?");
  await main.getByRole("button", { name: /^search the knowledge graph$/i }).click();
  await expect(page.getByTestId("history-rail")).toBeVisible({ timeout: 30_000 });
}

/** The box of the screen's own content, anchored on its heading's glyphs. */
async function contentLeftEdge(page: Page): Promise<number> {
  const box = await page
    .getByRole("heading", { name: /diseases are associated with BRCA1/i })
    .first()
    .boundingBox();
  if (!box) throw new Error("the screen heading has no box to measure against");
  return box.x;
}

test.describe("the stored-searches rail collapses", () => {
  test("sits to the left of the screen's content, not merely before it in the DOM", async ({
    page,
  }) => {
    await signInAndAsk(page);

    const rail = await page.getByTestId("history-rail").boundingBox();
    expect(rail).not.toBeNull();
    const contentX = await contentLeftEdge(page);

    // The rail's RIGHT edge must not pass the content's LEFT edge. This is the
    // assertion `order: -1` defeats in jsdom and cannot defeat here.
    expect(rail!.x + rail!.width).toBeLessThanOrEqual(contentX + 1);
  });

  test("collapses to a strip that holds the rail's own slot", async ({ page }) => {
    await signInAndAsk(page);
    const railBox = (await page.getByTestId("history-rail").boundingBox())!;

    await toggle(page).click();

    const strip = page.getByTestId("collapsed-rail");
    await expect(strip).toBeVisible();
    const stripBox = (await strip.boundingBox())!;

    // Same left edge as the rail it replaced: collapsing narrows the column,
    // it does not move it.
    expect(Math.abs(stripBox.x - railBox.x)).toBeLessThanOrEqual(2);
    expect(stripBox.width).toBeCloseTo(STRIP_WIDTH, 0);
    // And it is genuinely narrower, or "collapsed" means nothing.
    expect(stripBox.width).toBeLessThan(railBox.width);

    const contentX = await contentLeftEdge(page);
    expect(stripBox.x + stripBox.width).toBeLessThanOrEqual(contentX + 1);
  });

  test("gives the content the width the rail gave up", async ({ page }) => {
    await signInAndAsk(page);
    const openContentX = await contentLeftEdge(page);

    await toggle(page).click();
    await expect(page.getByTestId("collapsed-rail")).toBeVisible();
    const collapsedContentX = await contentLeftEdge(page);

    // A collapse that leaves the content where it was has not reflowed
    // anything, which is the visible half of what the control promises.
    expect(collapsedContentX).toBeLessThan(openContentX);
  });

  test("restores the rail from the strip, back to its original box", async ({ page }) => {
    await signInAndAsk(page);
    const before = (await page.getByTestId("history-rail").boundingBox())!;

    await toggle(page).click();
    await page.getByRole("button", { name: /^show your searches$/i }).click();

    const after = (await page.getByTestId("history-rail").boundingBox())!;
    expect(Math.abs(after.x - before.x)).toBeLessThanOrEqual(2);
    expect(Math.abs(after.width - before.width)).toBeLessThanOrEqual(2);
  });

  /*
   * BASELINE ALIGNMENT against `prototype/app.html`, added 2026-08-14.
   *
   * These are the measurements jsdom cannot make: `#rail`'s own width and
   * surface, and the fact that both the rail and its strip run the full height
   * of the shell rather than stopping where the content happens to end.
   */
  test("matches the prototype's rail width and surface", async ({ page }) => {
    await signInAndAsk(page);
    const rail = page.getByTestId("history-rail");

    // `#rail{width:248px; background:var(--surface)}`. The shipped rail was
    // 240px on `surfaceSunk`, filed as F-4.8-D-06 and now closed rather than
    // carried.
    expect((await rail.boundingBox())!.width).toBeCloseTo(248, 0);
    await expect(rail).toHaveCSS("background-color", "rgb(255, 255, 255)");
  });

  test("matches the prototype's strip surface", async ({ page }) => {
    await signInAndAsk(page);
    await toggle(page).click();

    // `#railStub{background:var(--surface)}`, the same white as the rail it
    // replaces, so one control does not change colour as it collapses.
    await expect(page.getByTestId("collapsed-rail")).toHaveCSS(
      "background-color",
      "rgb(255, 255, 255)",
    );
  });

  test("runs the full height of the shell, open and collapsed", async ({ page }) => {
    await signInAndAsk(page);
    const shell = (await page.getByRole("main").boundingBox())!;

    const rail = (await page.getByTestId("history-rail").boundingBox())!;
    // The prototype's rail reaches the footer. The shipped rail stopped where
    // the answer card ended, leaving a torn edge down the left of the page.
    expect(rail.height).toBeCloseTo(shell.height, -1);

    await toggle(page).click();
    const strip = (await page.getByTestId("collapsed-rail").boundingBox())!;
    expect(strip.height).toBeCloseTo(shell.height, -1);
  });

  test("carries each search's own tool, layer and source counts", async ({ page }) => {
    await signInAndAsk(page);

    // Wait for the run to land, which is when the counts exist at all.
    await expect(page.getByRole("button", { name: "New search", exact: true })).toBeVisible({
      timeout: 30_000,
    });

    /*
     * `.rm` in the prototype, `"3 tools · 3 layers · 3 sources"`.
     *
     * Asserted as AGREEMENT with the answer screen's own status line rather
     * than against a literal string. A literal would pass against a hardcoded
     * label; this can only pass if the rail is reading the run it belongs to.
     * It is deliberately indifferent to what the counts actually are, since the
     * mock backend's run legitimately produces zeroes.
     */
    const answerMeta = (await page.getByTestId("answer-meta").textContent())!.trim();
    expect(answerMeta).toMatch(/tools? · .* layers? · .* sources?/);

    const railItem = page.getByTestId("history-rail").getByRole("button", {
      name: /diseases are associated with BRCA1/i,
    });
    await expect(railItem).toContainText(answerMeta);
  });

  test("fills the landing beside a full-height rail", async ({ page }) => {
    await page.goto("/");
    const dialog = page.getByTestId("disclaimer-modal");
    if (await dialog.isVisible().catch(() => false)) {
      await dialog.getByRole("checkbox").check();
      await dialog.getByRole("button", { name: /continue/i }).click();
    }
    await page
      .getByRole("navigation", { name: /main/i })
      .getByRole("button", { name: /log in/i })
      .click();
    await page.getByLabel("Email").fill(`rail-${randomUUID()}@example.com`);
    await page.getByLabel("Password").fill(TEST_PASSWORD);
    await page.getByRole("button", { name: "Sign up" }).click();
    await expect(page.getByTestId("history-rail")).toBeVisible({ timeout: 30_000 });

    /*
     * The prototype's landing hero runs to the footer. The shipped hero was
     * content-height, so once the rail became full height the landing showed a
     * white column beside a grey void.
     *
     * Pre-existing rather than introduced by the rail work, and only visible
     * because of it, which is the argument for fixing it in the same pass.
     */
    const main = (await page.getByRole("main").boundingBox())!;
    const hero = (await page.getByTestId("home-hero").boundingBox())!;
    expect(hero.y + hero.height).toBeCloseTo(main.y + main.height, -1);
  });

  test("hides rail and strip below the design's breakpoint", async ({ page }) => {
    await signInAndAsk(page);
    await page.setViewportSize(NARROW_VIEWPORT);

    // The prototype's own media query. jsdom cannot evaluate this, which is
    // why the vitest gate declares it as NOT exercised rather than claiming it.
    await expect(page.getByTestId("history-rail")).toBeHidden();

    await expect(toggle(page)).toBeVisible();
    await toggle(page).click();
    await expect(page.getByTestId("collapsed-rail")).toBeHidden();
  });
});
