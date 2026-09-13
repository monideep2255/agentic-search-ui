/**
 * T-4.16-05, the product owner's defect 6 from the live demo: "NO
 * CLIENT-SIDE ROUTING. Every page is served at `/` and the URL never
 * changes." The four routes below were given verbatim by them.
 *
 * WHY A BROWSER TEST. Every assertion here is about `window.location` and
 * the browser's own session history, which jsdom simulates and a real
 * browser actually implements. The back button in particular is a browser
 * behaviour, not a React one: nothing in a component tree can prove that
 * `popstate` fires and is handled. This is the same reasoning that put the
 * feedback thumb geometry in a browser rather than in vitest.
 *
 * The two directions are tested separately and deliberately. A forward-only
 * implementation, one that pushes on navigate and ignores `popstate`, gives
 * a URL that changes while the page does not, which is WORSE than no
 * routing because the address bar then lies. `routing.spec` would pass its
 * deep-link and its push arms and fail only the back arm, so that arm is
 * the one carrying the weight.
 */

import { expect, test, type Page } from "@playwright/test";

/**
 * `nav` is the button label, `heading` is the `<h1>` that screen actually
 * renders, and the two DIFFER on two of the four. The first draft of this
 * file assumed they matched and looked for /about/i on the About screen,
 * whose heading is "How an answer is built". That was a fixture error
 * reported as a routing failure, which is a fair warning about how a wrong
 * expectation reads: the test said "/about did not render its own screen"
 * and the routing was fine.
 */
const ROUTES = [
  { path: "/", nav: "Search", heading: null },
  { path: "/integrations", nav: "Integrations", heading: /^Integrations$/ },
  { path: "/about", nav: "About", heading: /How an answer is built/i },
] as const;

/**
 * Paths with no nav item, which therefore appear only in the deep-link arm.
 *
 * `/docs` was the fourth screen until fix set 5 (R18, 2026-09-13) folded the
 * Docs content into the Integrations page. The path is kept as an alias rather
 * than dropped, so an existing bookmark still lands somewhere useful, and this
 * arm is what proves it does. `lib/routing.ts`'s `LEGACY_PATHS` is the
 * mechanism.
 */
const LEGACY_ROUTES = [{ path: "/docs", heading: /^Integrations$/ }] as const;

async function enterApp(page: Page, path = "/"): Promise<void> {
  await page.goto(path);
  const dialog = page.getByTestId("disclaimer-modal");
  if (await dialog.isVisible().catch(() => false)) {
    await dialog.getByRole("checkbox").check();
    await dialog.getByRole("button", { name: /continue/i }).click();
    await expect(dialog).toBeHidden();
  }
}

const nav = (page: Page) => page.getByRole("navigation", { name: /main/i });

test.describe("client-side routing", () => {
  test("each nav item changes the URL to its own route", async ({ page }) => {
    await enterApp(page);

    // POPULATE-CHECK. If the nav did not render, every click below would
    // fail on its own rather than reporting that the fixture was wrong,
    // and a reader of the failure would look at routing instead of at the
    // shell.
    await expect(nav(page), "the main navigation did not render").toBeVisible();

    for (const route of ROUTES) {
      await nav(page).getByRole("button", { name: route.nav, exact: true }).click();
      await expect(
        page,
        `clicking ${route.nav} did not put ${route.path} in the address bar`,
      ).toHaveURL(new RegExp(`${route.path.replace("/", "\\/")}$`));
    }
  });

  test("a deep link renders its own screen, not the landing screen", async ({ page }) => {
    for (const route of ROUTES) {
      if (route.heading === null) continue;
      await enterApp(page, route.path);
      await expect(
        page.getByRole("main").getByRole("heading", { name: route.heading }),
        `${route.path} did not render its own screen`,
      ).toBeVisible();
      await expect(page).toHaveURL(new RegExp(`${route.path.replace("/", "\\/")}$`));
    }
  });

  test("a retired path still lands on the page that holds its content", async ({ page }) => {
    // R18. `/docs` had a screen of its own and now has an alias. A reader who
    // bookmarked it must not get the landing screen, which is what deleting
    // the route without the alias would have given them: `screenForPath`
    // falls back to `search` for anything it does not recognise, so the
    // failure would have been silent and plausible rather than a 404.
    for (const route of LEGACY_ROUTES) {
      await enterApp(page, route.path);
      await expect(
        page.getByRole("main").getByRole("heading", { name: route.heading }),
        `${route.path} did not land on the page holding its content`,
      ).toBeVisible();
    }
  });

  /**
   * THE ARM THAT CARRIES THE WEIGHT. A push-only implementation passes both
   * arms above and fails this one, and a URL that changes while the page
   * does not is worse than no routing at all.
   */
  test("the back button returns to the previous screen, not just the previous URL", async ({
    page,
  }) => {
    await enterApp(page);
    await nav(page).getByRole("button", { name: "Integrations", exact: true }).click();
    await expect(page.getByRole("main").getByRole("heading", { name: /^Integrations$/ })).toBeVisible();

    await nav(page).getByRole("button", { name: "About", exact: true }).click();
    await expect(page.getByRole("main").getByRole("heading", { name: /How an answer is built/i })).toBeVisible();

    await page.goBack();
    await expect(page, "the URL did not go back").toHaveURL(/\/integrations$/);
    await expect(
      page.getByRole("main").getByRole("heading", { name: /^Integrations$/ }),
      "the URL went back but the page did not, so the address bar is lying",
    ).toBeVisible();

    await page.goForward();
    await expect(page).toHaveURL(/\/about$/);
    await expect(page.getByRole("main").getByRole("heading", { name: /How an answer is built/i })).toBeVisible();
  });

  test("an unknown path falls back to the landing screen rather than a blank page", async ({
    page,
  }) => {
    await enterApp(page, "/not-a-real-page");
    await expect(
      page.getByRole("main").getByRole("textbox", { name: /question/i }),
      "an unknown path rendered neither its own screen nor the landing screen",
    ).toBeVisible();
  });
});
