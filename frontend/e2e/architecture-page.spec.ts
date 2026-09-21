/**
 * The Architecture page at two widths (product-owner request of 2026-09-13).
 *
 * The page carries FOUR stops, not three: layer 1, layer 2, layer 3, and a
 * closing block saying all three feed the search agent. The count is asserted
 * below so a stop lost in a restructure fails here rather than going unnoticed
 * behind a green overflow check.
 *
 * WHY A BROWSER TEST RATHER THAN MORE VITEST. The page's unit test proves
 * every figure reaches the DOM. It cannot prove the page FITS: jsdom has no
 * layout engine, so `scrollWidth` there is whatever jsdom invents, and a
 * table or a code block running off the side of a phone is invisible to
 * every DOM assertion. `.claude/rules/design-consistency.md` and the
 * repository's own responsive rule both turn on that one measurement, so it
 * is measured here.
 *
 * 390 IS THE NUMBER THAT MATTERS. It is the width the design system's
 * prototype is checked at, and the page carries two things that overflow
 * naturally if nothing bounds them: the example Cypher, which is a `<pre>`
 * with `white-space: pre` and therefore cannot wrap, and the four-up
 * snapshot figure grid. The first is given its own horizontal scroller, the
 * second collapses to two columns. Both are exercised below by measuring the
 * document rather than by reading the stylesheet.
 *
 * 1280 IS CHECKED TOO because the app bar gained a fourth nav item with this
 * page, and a bar that overflows pushes the whole document sideways.
 */

import { expect, test, type Page } from "@playwright/test";

async function enterApp(page: Page, path = "/"): Promise<void> {
  await page.goto(path);
  const dialog = page.getByTestId("disclaimer-modal");
  if (await dialog.isVisible().catch(() => false)) {
    await dialog.getByRole("checkbox").check();
    await dialog.getByRole("button", { name: /continue/i }).click();
    await expect(dialog).toBeHidden();
  }
}

/** True when the document is wider than the window, which is what a reader
 *  experiences as the page sliding sideways. One pixel of slack absorbs
 *  sub-pixel rounding, which is real and is not a defect. */
async function overflow(page: Page): Promise<number> {
  return page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
}

test.describe("the architecture page", () => {
  for (const { label, width, height } of [
    { label: "desktop", width: 1280, height: 900 },
    { label: "phone", width: 390, height: 844 },
  ] as const) {
    test(`renders its three layers at ${label} width with no sideways scroll`, async ({
      page,
    }) => {
      await page.setViewportSize({ width, height });
      await enterApp(page, "/architecture");

      // POPULATE-CHECK. Without it, a page that failed to render would pass
      // the overflow assertion trivially: an empty document never overflows,
      // so the arm would report "no sideways scroll" about nothing at all.
      const stack = page.getByTestId("architecture-layers");
      await expect(stack, "the architecture page did not render").toBeVisible();
      await expect(stack.getByRole("heading", { level: 3 })).toHaveCount(4);
      await expect(page.getByTestId("architecture-snapshot")).toContainText("115,406,761");

      expect(
        await overflow(page),
        `the document is wider than the ${width}px viewport, so the page scrolls sideways`,
      ).toBeLessThanOrEqual(1);
    });
  }

  test("the About strip reaches this page without a reload", async ({ page }) => {
    await enterApp(page, "/about");

    await page.getByRole("button", { name: "Explore the architecture" }).click();

    await expect(page).toHaveURL(/\/architecture$/);
    await expect(
      page.getByRole("main").getByRole("heading", { name: /^Architecture$/ }),
    ).toBeVisible();
  });
});
