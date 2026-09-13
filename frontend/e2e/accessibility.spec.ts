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

import { randomUUID } from "node:crypto";
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

/** Sign up, so the screens scanned below are the real ones and not a stub. */
async function signIn(page: import("@playwright/test").Page) {
  await enterApp(page);
  await page
    .getByRole("navigation", { name: /main/i })
    .getByRole("button", { name: /log in/i })
    .click();
  await page.getByLabel("Email").fill(`a11y-${randomUUID()}@example.com`);
  await page.getByLabel("Password").fill("Str0ngPassw0rd!");
  await page.getByRole("button", { name: "Log in" }).click();
  await expect(
    page.getByRole("main").getByRole("textbox", { name: /question/i }),
  ).toBeVisible();
}

const analyse = (page: import("@playwright/test").Page) =>
  new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();

test.describe("accessibility", () => {
  // Set 2, R10 (2026-09-12) added a 0.2s fade between screens. axe measures
  // contrast at one instant, so a scan taken mid-fade read partly transparent
  // text as low contrast: 3 of 3 repeated runs failed with the fade, 3 of 3
  // passed with it switched off. The app turns the fade off for reduced
  // motion, so scanning with that preference checks the settled colours a
  // reader actually sees. Not covered: contrast during the 0.2s fade itself.
  test.use({ contextOptions: { reducedMotion: "reduce" } });

  test("the disclaimer gate is clean before anything else renders", async ({ page }) => {
    await page.goto("/");
    const results = await analyse(page);
    expect(results.violations).toEqual([]);
  });

  test("the disclaimer gate cannot be escaped with the keyboard", async ({ page }) => {
    // F-4.8-A-08, and F-4.8-R-06's observation that the fix had NO test
    // anywhere and could not have a vitest one: `focusable()` filters on
    // `offsetParent`, which is always null in jsdom, so the trap is silently
    // inert there and a unit test would pass against a broken guard.
    //
    // The original defect: the modal blocked the mouse only. All fifteen app
    // controls stayed in the tab order behind it, and the adversary signed up,
    // asked a question and read a complete cited answer by keyboard alone with
    // the disclaimer still on screen, while `aria-modal="true"` told a screen
    // reader the background was inert.
    await page.goto("/");
    const dialog = page.getByTestId("disclaimer-modal");
    await expect(dialog).toBeVisible();

    // Tab many times. Focus must never leave the dialog.
    const escaped: string[] = [];
    for (let i = 0; i < 25; i += 1) {
      await page.keyboard.press("Tab");
      const inside = await page.evaluate(() => {
        const modal = document.querySelector('[data-testid="disclaimer-modal"]');
        return modal ? modal.contains(document.activeElement) : false;
      });
      if (!inside) {
        escaped.push(
          await page.evaluate(() => document.activeElement?.textContent?.trim() ?? "unknown"),
        );
      }
    }
    expect(escaped, `focus escaped the disclaimer to: ${escaped.join(", ")}`).toEqual([]);

    // Shift+Tab must not escape backwards either.
    for (let i = 0; i < 10; i += 1) {
      await page.keyboard.press("Shift+Tab");
    }
    expect(
      await page.evaluate(() => {
        const modal = document.querySelector('[data-testid="disclaimer-modal"]');
        return modal ? modal.contains(document.activeElement) : false;
      }),
    ).toBe(true);

    // Escape must not dismiss a medical disclaimer by reflex.
    await page.keyboard.press("Escape");
    await expect(dialog).toBeVisible();

    // And the app behind it must not be operable: the question field is the
    // control the adversary reached, so it is the one asserted.
    const reached = await page.evaluate(() => {
      const field = document.querySelector('input[aria-label="Your question"]') as HTMLElement | null;
      if (!field) return "absent";
      field.focus();
      return document.activeElement === field ? "focusable" : "blocked";
    });
    expect(reached, "the question field must not be reachable behind the gate").not.toBe(
      "focusable",
    );
  });

  test("the app fills the viewport rather than a leftover 720px column", async ({ page }) => {
    // Found by LOOKING at the running app, after 147 unit tests, 17 end-to-end
    // tests and a full WCAG pass had all stayed green through it.
    //
    // `#root { max-width: 720px }` was build phase 1.2's scaffold for a single
    // centred chat column. It survived the restyle and squeezed the entire
    // redesigned application into a 720px strip with bare canvas either side,
    // wrapping the app bar's own wordmark onto three lines. Every screen was
    // restyled; the container they sit in was not.
    //
    // This is the cheapest possible guard on the layout gap that
    // tracker/phase_4.8.md declares as deliberately ungated. It does not check
    // that the design is right, only that the app is not boxed into a corner
    // of the window, which is the failure that actually happened.
    await enterApp(page);

    const { barWidth, viewportWidth } = await page.evaluate(() => ({
      barWidth: document.querySelector("header")?.getBoundingClientRect().width ?? 0,
      viewportWidth: window.innerWidth,
    }));

    expect(
      barWidth / viewportWidth,
      `the app bar spans ${Math.round((barWidth / viewportWidth) * 100)}% of the viewport`,
    ).toBeGreaterThan(0.95);
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

  test("the sign-in screen is clean", async ({ page }) => {
    // ADDED after this suite missed a real defect. AuthGate rendered its own
    // <main> while AppShell already owned one, so the sign-in screen carried
    // two main landmarks, which is invalid. axe would have caught it; this
    // suite simply never visited the screen. A gate that skips a screen has
    // not checked it, however green the rest of the run looks.
    await enterApp(page);
    await page
      .getByRole("navigation", { name: /main/i })
      .getByRole("button", { name: /log in/i })
      .click();
    await expect(page.getByLabel("Email")).toBeVisible();

    expect(await page.getByRole("main").count(), "exactly one main landmark").toBe(1);
    expect((await analyse(page)).violations).toEqual([]);
  });

  test("the run and answer screens are clean", async ({ page }) => {
    // SIGNS IN, after judge finding F-4.8-J-09. This previously ran anonymous
    // and therefore scanned the fabricated demo answer, never the real one:
    // variable claim counts, spine gaps for uncited claims, risk-tier pills and
    // an empty-claims state were all outside its reach while its own coverage
    // statement claimed "every screen".
    await signIn(page);
    const main = page.getByRole("main");
    await main.getByRole("textbox", { name: /question/i }).fill("Which diseases are associated with BRCA1?");
    await main.getByRole("button", { name: /^search the knowledge graph$/i }).click();

    // Mid-run. Anchored on the STEPPER's own hook, not on the text "Guard":
    // build phase 4.9 added the reasoning log, which names each step too, so a
    // bare text match now resolves to two elements and trips strict mode
    // intermittently, depending on whether the log has rendered yet.
    await expect(page.getByTestId("step-Guard")).toBeVisible();
    expect((await analyse(page)).violations).toEqual([]);

    // Landed. Waits on the "New search" action rather than a source card: this
    // now scans a REAL run, and this backend's only token is the cap-exceeded
    // partial result, which carries no citations. Waiting for `source-1` waited
    // for something the real answer legitimately does not have.
    await expect(page.getByRole("button", { name: "New search", exact: true })).toBeVisible({
      timeout: 20_000,
    });
    expect((await analyse(page)).violations).toEqual([]);
  });

  test("no two visible controls share an accessible name", async ({ page }) => {
    // Both defects this asserts against were real and were found by hand while
    // building: an unlabelled navigation landmark, and the app bar offering
    // "Log in" while the sign-in form was already open. axe does not flag
    // either, because duplicate names across landmarks are legal, so this
    // check is deliberately stricter than the standard.
    // Checked on the LANDING and then again on the SIGN-IN screen. The comment
    // below names two defects this guards; one of them, the app bar offering
    // "Log in" beside an open sign-in form, can only appear on the sign-in
    // screen, which this test never visited (F-4.8-J-10). Removing
    // `hideAuthAction` would not have failed it.
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

    const tally = (list: string[]) => {
      const seen = new Map<string, number>();
      for (const name of list) seen.set(name, (seen.get(name) ?? 0) + 1);
      return [...seen.entries()].filter(([, count]) => count > 1);
    };

    expect(tally(names), `landing: ${JSON.stringify(tally(names))}`).toEqual([]);

    // Now the sign-in screen, where the second named defect actually lives.
    await page
      .getByRole("navigation", { name: /main/i })
      .getByRole("button", { name: /log in/i })
      .click();
    await expect(page.getByLabel("Email")).toBeVisible();

    const signInNames = await page.evaluate(() => {
      const visible = (el: Element) => {
        const rect = el.getBoundingClientRect();
        return rect.width > 0 && rect.height > 0;
      };
      return Array.from(document.querySelectorAll("button, a[href], input, [role=button]"))
        .filter(visible)
        .map((el) => (el.getAttribute("aria-label") ?? el.textContent ?? "").trim().toLowerCase())
        .filter((name) => name.length > 0);
    });

    expect(
      tally(signInNames),
      `sign-in screen: ${JSON.stringify(tally(signInNames))}`,
    ).toEqual([]);
  });
});
