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
  await page.getByRole("button", { name: "Log in" }).click();

  const main = page.getByRole("main");
  await main
    .getByRole("textbox", { name: /question/i })
    .fill("Which diseases are associated with BRCA1?");
  await main.getByRole("button", { name: /^search the knowledge graph$/i }).click();
  await expect(page.getByTestId("history-rail")).toBeVisible({ timeout: 30_000 });

  /*
   * WAIT FOR THE RUN TO LAND before returning (F-4.9-J-03).
   *
   * Every clause in this file measures geometry, and this helper used to
   * return as soon as the rail appeared, which is while the run is still
   * streaming. Build phase 4.9 added the run screen's reasoning log, so the
   * layout now shifts UNDER the measurement: a judge measured the content's
   * left edge moving 111px and the shell growing from 566 to 577px mid-run.
   *
   * The suite was 29 of 29 twice on `develop` and 28 of 29 in two of three
   * runs on this branch, a different geometry clause each time. The lead
   * reported that as worker contention and was wrong; this is the mechanism.
   *
   * `answer-meta` exists only once the run has terminated, so waiting on it
   * means every measurement below is taken against a settled page.
   */
  await expect(page.getByTestId("answer-meta")).toBeVisible({ timeout: 30_000 });
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
    //
    // Since 2026-09-13 the rail is pinned to the viewport (product-owner
    // feedback: the landing search bar sat low when signed in, because the
    // rail's list stretched the row beside it). So "reaches the footer" is
    // now measured as the space between the app bar and the footer, at
    // every scroll position, rather than as the shell's whole height: on a
    // page taller than the viewport the shell is taller than any one
    // screenful, and a rail that filled it would be the defect again.
    const viewport = page.viewportSize()!;
    const header = (await page.getByRole("banner").boundingBox())!;
    const footer = (await page.getByRole("contentinfo").boundingBox())!;
    expect(rail.height).toBeCloseTo(viewport.height - header.height - footer.height, -1);
    expect(rail.y).toBeCloseTo(header.height, -1);
    await expect(page.getByTestId("history-rail")).toHaveCSS("position", "sticky");

    await toggle(page).click();
    const strip = (await page.getByTestId("collapsed-rail").boundingBox())!;
    expect(strip.height).toBeCloseTo(shell.height, -1);
  });

  test("carries each search's own tool, layer and source counts", async ({ page }) => {
    await signInAndAsk(page);

    /*
     * Wait for the run to LAND, which is when the counts exist at all.
     *
     * Waits on the answer screen's status strip, not on "New search": the run
     * screen carries that button too, so the old wait could pass mid-run and
     * then read a rail item that had no counts on it yet.
     */
    await expect(page.getByTestId("answer-meta")).toBeVisible({ timeout: 30_000 });

    /*
     * `.rm` in the prototype, `"3 tools · 3 layers · 3 sources"`.
     *
     * Asserted as AGREEMENT with the answer screen's own status line rather
     * than against a literal string. A literal would pass against a hardcoded
     * label; this can only pass if the rail is reading the run it belongs to.
     * It is deliberately indifferent to what the counts actually are, since the
     * mock backend's run legitimately produces zeroes.
     */
    /*
     * INVERTED in build phase 4.9, and deliberately not relaxed.
     *
     * The answer screen's strip now leads with the outcome and the elapsed
     * time before the counts (F-4.8-D-05), so it is a SUPERSET of the rail's
     * label rather than equal to it. The guarantee is unchanged, and still
     * cannot pass against a hardcoded label: the rail's counts must appear
     * verbatim inside the answer's own strip, so the rail is still reading the
     * run it belongs to.
     */
    const railItem = page.getByTestId("history-rail").getByRole("button", {
      name: /diseases are associated with BRCA1/i,
    });
    const railText = (await railItem.textContent())!.trim();
    // The wording changed in the F-4.9-R-02 fix, from three bare nouns to
    // "N tools · N sources from N layers", so each figure states what it
    // counts. The GUARANTEE is untouched: the rail's label must still appear
    // verbatim inside the answer's own strip.
    const counts = railText.match(/\d+ tools? · \d+ sources?(?: from \d+ layers?)?/);
    expect(counts, `the rail item carried no counts: ${railText}`).not.toBeNull();

    await expect(page.getByTestId("answer-meta")).toContainText(counts![0]);
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
    await page.getByRole("button", { name: "Log in" }).click();
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

  test("below the design's breakpoint, the rail moves into a sliding panel rather than vanishing", async ({
    page,
  }) => {
    await signInAndAsk(page);

    // Collapse WHILE STILL WIDE, before resizing, and the reason is load-
    // bearing rather than tidiness. `signInAndAsk` leaves the rail open, and
    // a MUI `Drawer` marks everything OUTSIDE it `aria-hidden` while open,
    // which is the standard, correct behaviour for any modal panel. Resizing
    // narrow with the rail already open would carry that open state straight
    // into the Drawer branch, so the very toggle this test means to check
    // would be behind an open modal and invisible to a role query by design,
    // not by defect. Collapsing first means the resize lands on a CLOSED
    // rail, which is the state an actual phone visitor re-entering this
    // screen narrow would be in too.
    await toggle(page).click();
    await expect(page.getByTestId("history-rail")).toBeHidden();
    await page.setViewportSize(NARROW_VIEWPORT);

    // REWRITTEN fix set 4 (R46, decision U9, 2026-09-13). This test used to
    // assert the rail, the strip, and the toggle were ALL hidden below
    // `md`, which was correct for what shipped on 2026-09-05 and is wrong
    // now: `.claude/rules/goal-contracts.md`'s second case, the check was
    // right for its own moment and the product moved. History is reachable
    // on a phone as of this fix, so a signed-in user below `md` gets the
    // toggle, visible, and the rail, inside a sliding panel rather than
    // hidden. The strip alone keeps the old guarantee: `CollapsedRail`
    // still has no phone design, the app bar toggle is the way back in
    // below `md`, so the strip stays hidden there rather than occupying
    // space beside content a phone has none to spare.
    await expect(toggle(page)).toBeVisible();
    await expect(page.getByRole("dialog", { name: /your searches/i })).toBeHidden();
    await expect(page.getByTestId("collapsed-rail")).toBeHidden();

    await toggle(page).click();
    const panel = page.getByRole("dialog", { name: /your searches/i });
    await expect(panel).toBeVisible();
    await expect(panel.getByTestId("history-rail")).toBeVisible();

    // Closing through the PANEL'S OWN control, not the app bar toggle: the
    // toggle sits outside the open modal and is `aria-hidden` while it is
    // open, by the same MUI Modal behaviour this test's comment above
    // explains, so a role query cannot reach it until the panel closes.
    await panel.getByRole("button", { name: /^hide your searches$/i }).click();
    await expect(panel).toBeHidden();
  });
});

/*
 * Fix set 4, R46 (decision U9, 2026-09-13): history reachable on a phone.
 *
 * A real phone viewport, not `NARROW_VIEWPORT` (800px, below `md` but wider
 * than any phone this app actually ships to). 390px is the width the rest
 * of this fix loop already measures against (see `AppShell.tsx`'s own
 * comments), so this describe block uses the same number rather than a
 * second, independently chosen one.
 */
test.describe("the stored-searches rail on a phone", () => {
  test.use({ viewport: { width: 390, height: 844 } });

  test("opens as a sliding panel from the app bar and closes with no horizontal scroll", async ({
    page,
  }) => {
    await page.goto("/");
    const disclaimer = page.getByTestId("disclaimer-modal");
    if (await disclaimer.isVisible().catch(() => false)) {
      await disclaimer.getByRole("checkbox").check();
      await disclaimer.getByRole("button", { name: /continue/i }).click();
    }
    await page
      .getByRole("navigation", { name: /main/i })
      .getByRole("button", { name: /log in/i })
      .click();
    await page.getByLabel("Email").fill(`rail-${randomUUID()}@example.com`);
    await page.getByLabel("Password").fill(TEST_PASSWORD);
    await page.getByRole("button", { name: "Log in" }).click();

    const panel = page.getByRole("dialog", { name: /your searches/i });

    /*
     * Today, `railOpen` starts `true` EVEN ON A PHONE, so the panel opens
     * the instant sign-in lands and, being an open modal, marks everything
     * outside it, `<main>` included, `aria-hidden`: a real, temporary
     * sequencing gap, not a defect in the panel itself, that the
     * orchestrator's later change to `App.tsx` closes by starting the
     * drawer CLOSED on a phone instead. Nothing INSIDE an open modal is
     * inert, only what sits outside it, so the panel's own close control is
     * still reachable, and closing it here is exactly what a real phone
     * visitor would have to do today before asking anything. Once the
     * orchestrator's change lands this `if` finds nothing open and does
     * nothing, which is what lets this one test pass under both states
     * rather than pinning whichever happened to be true the day it was
     * written.
     */
    // A one-shot `isVisible()` here raced the panel's own mount: login
    // resolves, then the rail mounts asynchronously a beat later, so a
    // single immediate check can read "not open yet" moments before it
    // opens and aria-hides `<main>` out from under an in-flight `.fill()`.
    // `waitFor` POLLS, which is what lets this branch see the panel if it
    // is going to open at all, rather than only if it already has.
    const opened = await panel
      .waitFor({ state: "visible", timeout: 5_000 })
      .then(() => true)
      .catch(() => false);
    if (opened) {
      await panel.getByRole("button", { name: /^hide your searches$/i }).click();
      await expect(panel).toBeHidden();
    }

    const main = page.getByRole("main");
    await main
      .getByRole("textbox", { name: /question/i })
      .fill("Which diseases are associated with BRCA1?");
    await main.getByRole("button", { name: /^search the knowledge graph$/i }).click();
    await expect(page.getByTestId("answer-meta")).toBeVisible({ timeout: 30_000 });

    // NOW exercise the real open path from the app bar toggle, which is
    // reachable here because the panel is closed and nothing is inert.
    const alreadyOpen = (await toggle(page).getAttribute("aria-expanded")) === "true";
    if (!alreadyOpen) {
      await toggle(page).click();
    }

    await expect(panel).toBeVisible();
    await expect(panel.getByTestId("history-rail")).toBeVisible();

    /*
     * NOT an absolute `scrollWidth <= innerWidth` assertion, and the reason
     * is measured rather than assumed. At 390px this app already carries a
     * pre-existing, already-documented horizontal bleed with no rail open
     * at all: `AppShell.tsx`'s own comment on the brand button records the
     * `<nav>` box staying a fixed, unshrinking width below `md`, and a
     * direct check here (drawer open vs. drawer closed, same page, same
     * login) measured IDENTICAL `scrollWidth` in both states, 604px against
     * a 390px viewport either way. So an absolute assertion would fail for
     * a reason this fix does not cause and is not scoped to repair, which
     * is worse than not checking at all: it would point the next reader at
     * the drawer for a defect that lives in the app bar. The property this
     * fix actually owns, and the one worth pinning, is that OPENING THE
     * DRAWER ADDS NO WIDTH the page did not already carry.
     */
    const scrollWidthOpen = await page.evaluate(() => document.documentElement.scrollWidth);

    // Close button named "Hide your searches", the rail's own `.rtop`
    // control, not a second one: the task's instruction is exactly one
    // control carries that accessible name in each mode. Closed from
    // INSIDE the panel, not the app bar toggle, which sits outside the open
    // modal and is unreachable by role query while it is open.
    await panel.getByRole("button", { name: /^hide your searches$/i }).click();
    await expect(panel).toBeHidden();

    const scrollWidthClosed = await page.evaluate(() => document.documentElement.scrollWidth);
    expect(scrollWidthOpen).toBe(scrollWidthClosed);
  });
});
