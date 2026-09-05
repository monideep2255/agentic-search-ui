/**
 * TEMPORARY. Not part of the suite. Measures horizontal overflow on the app
 * bar after the AppShell.tsx changes of 2026-09-05 (disclaimer band removed,
 * nav overflow menu added below 720px, rail toggle hidden below md). Written
 * to answer the verification requirement in the task brief: a screenshot is
 * clipped to the viewport and cannot show bleed, so this measures
 * `document.documentElement.scrollWidth` against `clientWidth` instead, at
 * every required width. Moved out of `e2e/` once the measurements are taken.
 */

import { expect, test } from "@playwright/test";

const WIDTHS = [320, 390, 480, 719, 721, 1440];

async function enterApp(page: import("@playwright/test").Page) {
  await page.goto("/");
  const dialog = page.getByTestId("disclaimer-modal");
  if (await dialog.isVisible().catch(() => false)) {
    await dialog.getByRole("checkbox").check();
    await dialog.getByRole("button", { name: /continue/i }).click();
    await expect(dialog).toBeHidden();
  }
}

test.describe("temporary: app bar horizontal overflow", () => {
  for (const width of WIDTHS) {
    test(`no horizontal overflow at ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 });
      await enterApp(page);
      // Let MUI's transitions and the layout settle.
      await page.waitForTimeout(300);

      const { scrollWidth, clientWidth } = await page.evaluate(() => ({
        scrollWidth: document.documentElement.scrollWidth,
        clientWidth: document.documentElement.clientWidth,
      }));

      // eslint-disable-next-line no-console
      console.log(`[overflow] ${width}px: scrollWidth=${scrollWidth} clientWidth=${clientWidth}`);
      expect(scrollWidth, `document is ${scrollWidth - clientWidth}px wider than the viewport at ${width}px`).toBeLessThanOrEqual(clientWidth);

      // Below 720px, the overflow trigger should exist and opening it must
      // not itself introduce horizontal overflow.
      if (width < 720) {
        const trigger = page.getByRole("button", { name: /more pages/i });
        await expect(trigger).toBeVisible();
        await trigger.click();
        await page.waitForTimeout(150);
        const afterOpen = await page.evaluate(() => ({
          scrollWidth: document.documentElement.scrollWidth,
          clientWidth: document.documentElement.clientWidth,
        }));
        // eslint-disable-next-line no-console
        console.log(
          `[overflow] ${width}px with menu open: scrollWidth=${afterOpen.scrollWidth} clientWidth=${afterOpen.clientWidth}`,
        );
        expect(
          afterOpen.scrollWidth,
          `menu open makes the document ${afterOpen.scrollWidth - afterOpen.clientWidth}px wider than the viewport at ${width}px`,
        ).toBeLessThanOrEqual(afterOpen.clientWidth);
      } else {
        await expect(page.getByRole("button", { name: /more pages/i })).toBeHidden();
      }
    });
  }
});
