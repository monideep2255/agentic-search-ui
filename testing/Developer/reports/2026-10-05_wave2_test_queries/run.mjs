// Usage: cd frontend && node ../testing/Developer/reports/2026-10-05_wave2_test_queries/run.mjs <label> <mode|-> "<question>" [pickIndex]
// or:    ... run.mjs pages
import { createRequire } from "node:module";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
const HERE = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(path.join(HERE, "..", "..", "..", "..", "frontend", "package.json"));
const { chromium } = require("@playwright/test");
const WEB = "https://search-agent-web-develop-2aeb.up.railway.app";
const [label, mode, question] = process.argv.slice(2);
const browser = await chromium.launch({ channel: "chrome" });

async function disclaimer(page) {
  const m = page.locator('[data-testid="disclaimer-modal"]');
  await m.waitFor({ state: "visible", timeout: 15000 }).catch(() => {});
  if (await m.isVisible().catch(() => false)) {
    await m.getByRole("checkbox").check();
    await m.getByRole("button", { name: /continue/i }).click();
    await m.waitFor({ state: "hidden", timeout: 10000 });
  }
}
async function dump(page, name) {
  const text = await page.locator("main").innerText().catch(() => "");
  const links = await page.locator("main a[href]").evaluateAll(as => as.map(a => `${a.innerText.trim().slice(0,80)} -> ${a.href}`));
  fs.writeFileSync(path.join(HERE, `${name}.txt`), text + "\n\n--- LINKS ---\n" + links.join("\n") + "\n");
  await page.screenshot({ path: path.join(HERE, `${name}.png`), fullPage: true });
}

if (label === "pages") {
  for (const w of [1280, 390]) {
    for (const p of ["integrations", "about"]) {
      const ctx = await browser.newContext({ viewport: { width: w, height: w === 1280 ? 900 : 844 }, reducedMotion: "reduce" });
      const page = await ctx.newPage();
      await page.goto(`${WEB}/${p}`, { waitUntil: "domcontentloaded" });
      await disclaimer(page);
      await page.waitForTimeout(3000);
      const ov = await page.evaluate(() => ({ sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth }));
      await dump(page, `${p}_${w}`);
      fs.appendFileSync(path.join(HERE, `${p}_${w}.txt`), `OVERFLOW scrollWidth=${ov.sw} clientWidth=${ov.cw}\n`);
      console.log(p, w, JSON.stringify(ov), page.url());
      await ctx.close();
    }
  }
  await browser.close(); process.exit(0);
}

const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 }, reducedMotion: "reduce" });
const page = await ctx.newPage();
await page.goto(WEB, { waitUntil: "domcontentloaded" });
await disclaimer(page);
if (mode !== "-") {
  await page.getByRole("button", { name: mode, exact: true }).first().click();
}
const t0 = Date.now();
await page.locator('main textarea[aria-label="Your question"]').first().fill(question);
await page.locator('main button[aria-label="Search the knowledge graph"]').first().click();
const done = page.locator('[data-testid="answer-meta"], [data-testid="clarifying-options"], [data-testid="run-stopped"]').first();
await done.waitFor({ state: "visible", timeout: 170000 }).catch(e => console.log("timeout waiting"));
let secs = (Date.now() - t0) / 1000;
let asked = false;
if (await page.locator('[data-testid="clarifying-options"]').isVisible().catch(() => false)) {
  asked = true;
  await dump(page, `${label}_askback`);
  const t1 = Date.now();
  await page.locator('[data-testid="clarifying-option"]').first().click();
  await page.locator('[data-testid="answer-meta"], [data-testid="run-stopped"]').first().waitFor({ state: "visible", timeout: 170000 }).catch(() => console.log("timeout 2"));
  secs = (Date.now() - t1) / 1000;
}
await page.waitForTimeout(2500);
await dump(page, label);
fs.appendFileSync(path.join(HERE, `${label}.txt`), `\nTIME_TO_ANSWER_SECONDS=${secs.toFixed(1)} askback=${asked}\n`);
console.log(label, secs.toFixed(1), "askback", asked);
await browser.close();
