import { expect, test } from "@playwright/test";

test("diagnose 320px overflow", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 900 });
  await page.goto("/");
  const dialog = page.getByTestId("disclaimer-modal");
  if (await dialog.isVisible().catch(() => false)) {
    await dialog.getByRole("checkbox").check();
    await dialog.getByRole("button", { name: /continue/i }).click();
  }
  await page.waitForTimeout(300);

  const info = await page.evaluate(() => {
    const results: Array<{ depth: number; tag: string; cls: string; text: string; left: number; right: number; width: number }> = [];
    const toolbar = document.querySelector("header .MuiToolbar-root") || document.querySelector("header");
    function walk(el: Element | null, depth: number) {
      if (!el) return;
      const rect = el.getBoundingClientRect();
      results.push({
        depth,
        tag: el.tagName,
        cls: (el.className || "").toString().slice(0, 70),
        text: (el.textContent || "").trim().slice(0, 30),
        left: Math.round(rect.left),
        right: Math.round(rect.right),
        width: Math.round(rect.width),
      });
      for (const child of Array.from(el.children)) walk(child, depth + 1);
    }
    walk(toolbar, 0);
    return { docScrollWidth: document.documentElement.scrollWidth, results };
  });

  // eslint-disable-next-line no-console
  console.log("docScrollWidth", info.docScrollWidth);
  for (const r of info.results) {
    // eslint-disable-next-line no-console
    console.log(`${"  ".repeat(r.depth)}${r.tag} [${r.cls}] "${r.text}" left=${r.left} right=${r.right} width=${r.width}`);
  }
  expect(true).toBe(true);
});
