// usage: node ask.mjs <name> "<question>" [outdir]
import { createRequire } from "node:module";
import fs from "node:fs";
import path from "node:path";
const req = createRequire(path.resolve(process.env.FRONTEND_DIR, "package.json"));
const { chromium } = req("@playwright/test");
const WEB = "https://search-agent-web-develop-2aeb.up.railway.app";
const [name, question, outdir = "."] = process.argv.slice(2);
const browser = await chromium.launch({ channel: "chrome" });
const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 }, reducedMotion: "reduce" });
const page = await ctx.newPage();
await page.goto(WEB, { waitUntil: "domcontentloaded" });
await page.waitForTimeout(2500);
try {
  const cb = page.getByRole("checkbox").first();
  await cb.check({ timeout: 8000 });
  await page.getByRole("button", { name: /continue/i }).first().click();
} catch (e) { /* no disclaimer */ }
const ta = page.locator('main textarea[aria-label="Your question"]');
await ta.waitFor({ timeout: 20000 });
await ta.fill(question);
const t0 = Date.now();
await page.locator('main button[aria-label="Search the knowledge graph"]').click();
let landed = "timeout";
while ((Date.now() - t0) < 170000) {
  await page.waitForTimeout(1500);
  if (await page.locator('[data-testid="answer-meta"]').count()) { landed = "answer"; break; }
  const t = await page.locator("main").innerText().catch(() => "");
  if (/could not be completed/i.test(t)) {
    await page.waitForTimeout(2500);
    landed = "other"; break;
  }
}

// save the ask-back first, then click the 5-year choice
{ const t1 = await page.locator("main").innerText();
  fs.mkdirSync(outdir,{recursive:true});
  fs.writeFileSync(path.join(outdir, name+"_step1_askback.txt"), t1);
  await page.screenshot({ path: path.join(outdir, name+"_step1_askback.png"), fullPage:true });
  const choice = page.getByText(/last 5 years/i).first();
  await choice.click();
  await page.locator('[data-testid="answer-meta"]').first().waitFor({state:'detached',timeout:5000}).catch(()=>{});
  const t2 = Date.now();
  while (Date.now()-t2 < 150000) { await page.waitForTimeout(2000); if (await page.locator('[data-testid="answer-meta"]').count()) { const x = await page.locator("main").innerText(); if (!/How far back/i.test(x)) break; } }
}
const secs = ((Date.now() - t0) / 1000).toFixed(1);
await page.waitForTimeout(1500);
const text = await page.locator("main").innerText().catch(() => "");
const links = await page.$$eval("main a[href]", as => as.map(a => `${a.innerText.trim().replace(/\s+/g," ")} -> ${a.href}`));
const btns = await page.$$eval("main button", bs => bs.map(b => b.innerText.trim().replace(/\s+/g," ")).filter(Boolean));
fs.mkdirSync(outdir, { recursive: true });
fs.writeFileSync(path.join(outdir, name + ".txt"), `QUESTION: ${question}\nLANDED=${landed} SECONDS=${secs}\n\n${text}\n\nBUTTONS:\n${btns.join("\n")}\n\nLINKS:\n${links.join("\n")}\n`);
await page.screenshot({ path: path.join(outdir, name + ".png"), fullPage: true });
console.log(name, landed, secs);
await browser.close();
