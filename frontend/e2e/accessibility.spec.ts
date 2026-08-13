/**
 * Accessibility, build phase 4.8, ticket T-4.8-13.
 *
 * This is the premise gate's fifth clause. It lives here rather than in the
 * vitest suite because contrast needs a real browser: jsdom computes no colours,
 * so a contrast assertion there would pass against anything and be exactly the
 * kind of check that cannot fail.
 *
 * What it covers, stated so the gap is arguable rather than discovered:
 *
 *   Covered      WCAG 2.1 A and AA on every screen, via axe, including colour
 *                contrast against the real rendered palette; and the two
 *                duplicate-accessible-name defects this phase found by hand,
 *                asserted so they cannot come back.
 *   Not covered  keyboard traps beyond what axe detects, screen-reader
 *                announcement order, and reduced-motion behaviour. Those need
 *                a human or an assistive technology, not an automated rule.
 *
 * `@axe-core/playwright` is already a dependency, so this adds no new supply
 * chain surface.
 */

import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

/** Dismiss the disclaimer, which gates every screen behind it. */
async function enterApp(page: import("@playwright/test").Page) {
  await page.goto("/");
  const dialog = page.getByTestId("disclaimer-modal");
  if (await dialog.isVisible().catch(() => false)) {
    await dialog.getByRole("checkbox").check();
    await dialog.getByRole("button", { name: /continue/i }).click();
    await expect(dialog).toBeHidden();
  }
}

const analyse = (page: import("@playwright/test").Page) =>
  new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();

test.describe("accessibility", () => {
  test("the disclaimer gate is clean before anything else renders", async ({ page }) => {
    await page.goto("/");
    const results = await analyse(page);
    expect(results.violations).toEqual([]);
  });

  test("the landing screen is clean", async ({ page }) => {
    await enterApp(page);
    await expect(page.getByRole("heading", { name: /ask a biomedical question/i })).toBeVisible();
    const results = await analyse(page);
    expect(results.violations).toEqual([]);
  });

  for (const screen of ["Integrations", "Docs", "About"] as const) {
    test(`the ${screen.toLowerCase()} screen is clean`, async ({ page }) => {
      await enterApp(page);
      await page.getByRole("navigation", { name: /main/i }).getByRole("button", { name: screen }).click();
      const results = await analyse(page);
      expect(results.violations).toEqual([]);
    });
  }

  test("the run and answer screens are clean", async ({ page }) => {
    await enterApp(page);
    const main = page.getByRole("main");
    await main.getByRole("textbox", { name: /question/i }).fill("Which diseases are associated with BRCA1?");
    await main.getByRole("button", { name: /^ask$/i }).click();

    // Mid-run.
    await expect(page.getByText("Guard")).toBeVisible();
    expect((await analyse(page)).violations).toEqual([]);

    // Landed. Asserted on the first source card rather than on a heading or a
    // loose string: the sources label is a paragraph, not a heading, and a
    // text match on "Grounded" would also hit the trust pill's own copy.
    await expect(page.getByTestId("source-1")).toBeVisible({ timeout: 15_000 });
    expect((await analyse(page)).violations).toEqual([]);
  });

  test("no two visible controls share an accessible name", async ({ page }) => {
    // Both defects this asserts against were real and were found by hand while
    // building: an unlabelled navigation landmark, and the app bar offering
    // "Log in" while the sign-in form was already open. axe does not flag
    // either, because duplicate names across landmarks are legal, so this
    // check is deliberately stricter than the standard.
    await enterApp(page);

    const names = await page.evaluate(() => {
      const visible = (el: Element) => {
        const rect = el.getBoundingClientRect();
        return rect.width > 0 && rect.height > 0;
      };
      return Array.from(document.querySelectorAll("button, a[href], input, [role=button]"))
        .filter(visible)
        .map((el) =>
          (
            el.getAttribute("aria-label") ??
            el.textContent ??
            ""
          )
            .trim()
            .toLowerCase(),
        )
        .filter((name) => name.length > 0);
    });

    const seen = new Map<string, number>();
    for (const name of names) seen.set(name, (seen.get(name) ?? 0) + 1);
    const duplicates = [...seen.entries()].filter(([, count]) => count > 1);

    expect(duplicates, `controls sharing a name: ${JSON.stringify(duplicates)}`).toEqual([]);
  });
});
