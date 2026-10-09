import { mkdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const shots = path.resolve(__dirname, "..", "..", "testing/Developer/reports/2026-10-06_factory_card44");

test.use({ contextOptions: { reducedMotion: "reduce" } });

for (const width of [390, 1280]) {
  test(`the hovered tour button meets small-text contrast at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 900 });
    await page.goto("/");
    const dialog = page.getByTestId("disclaimer-modal");
    if (await dialog.isVisible().catch(() => false)) {
      await dialog.getByRole("checkbox").check();
      await dialog.getByRole("button", { name: /continue/i }).click();
    }

    const button = page.getByTestId("take-the-tour");
    await expect(button).toBeVisible();
    await button.hover();
    if (process.env.FACTORY_SHOTS === "1") {
      await mkdir(shots, { recursive: true });
      await page.screenshot({
        path: path.join(shots, `home_${width}.png`),
        fullPage: true,
        mask: [page.getByText(/Working as /)],
        maskColor: "#f0f0f0",
      });
    }

    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
      .include('[data-testid="take-the-tour"]')
      .analyze();
    expect(results.violations.filter((violation) => violation.id === "color-contrast")).toEqual([]);
  });
}
