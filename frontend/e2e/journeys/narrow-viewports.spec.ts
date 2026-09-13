/**
 * Journey 7: journey 1 repeated at three widths.
 *
 * `docs/build/UI_feedback.md` complaint 1, the one item in that document explicitly
 * marked NOT YET DIAGNOSED, with the reason stated: judging responsiveness
 * against the approved design needs a browser and a side-by-side, not a
 * curl.
 *
 * 390px, 768px and 1440px, the widths that document names. This journey
 * produces the left-hand column of that comparison; the prototype is the
 * right-hand column and belongs to T-6.2-10, which must first establish
 * whether any gap is a REGRESSION since build phase 4.9 or a gap that phase
 * never covered, because those are different jobs.
 *
 * Spends NO guest answer: it films the landing and chrome at each width
 * rather than running a query three times. Complaint 1 is about layout, and
 * a query would triple the cost to film the same boxes.
 */

import { expect, test } from "@playwright/test";

import { Filmstrip, JOURNEYS_ENABLED, enterApp, outputDir } from "./_capture";

const WIDTHS = [390, 768, 1440];

test.describe(
  JOURNEYS_ENABLED ? "journey 7: narrow viewports" : "journey 7 (skipped: RUN_LIVE_JOURNEYS=1)",
  () => {
    test.skip(!JOURNEYS_ENABLED, "reaches the deployed app");
    test.describe.configure({ timeout: 180_000 });

    test("the app at 390, 768 and 1440", async ({ page }) => {
      const strip = new Filmstrip(page, outputDir("journey7_viewports"), "Journey 7: narrow viewports");
      await strip.begin();

      for (const width of WIDTHS) {
        await page.setViewportSize({ width, height: 900 });
        await enterApp(page);
        await page.waitForTimeout(500);
        await strip.capture(`${width}px landing`);

        // Horizontal overflow is the one layout defect a screenshot CANNOT
        // show, because the frame is clipped to the viewport. Measured
        // rather than looked at.
        const overflow = await page
          .evaluate(() => ({
            scroll: document.documentElement.scrollWidth,
            client: document.documentElement.clientWidth,
          }))
          .catch(() => null);
        if (overflow) {
          const bleeds = overflow.scroll > overflow.client + 1;
          strip.note(
            `  ${width}px: scrollWidth ${overflow.scroll} vs clientWidth ${overflow.client}` +
              (bleeds ? "  HORIZONTAL OVERFLOW" : ""),
          );
        }

        // "docs" removed with the tab itself, fix set 5 (R18, 2026-09-13).
        for (const screen of ["integrations", "about"]) {
          await page
            .getByRole("navigation", { name: /main/i })
            .getByRole("link", { name: new RegExp(screen, "i") })
            .click({ timeout: 5_000 })
            .catch(() => undefined);
          await page.waitForTimeout(400);
          await strip.capture(`${width}px ${screen}`);
        }
      }

      strip.write();
      expect(strip.frames, "the journey captured no frames").toBeGreaterThan(1);
    });
  },
);
