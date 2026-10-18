// Usage: node run_one.mjs <label> <mode: plain|researcher> <question> [pickSubstring]
import { createRequire } from "node:module";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(HERE, "../../../../..");
const req = createRequire(path.join(REPO, "frontend", "package.json"));
const { chromium } = req("playwright");
const WEB = "https://search-agent-web-develop-2aeb.up.railway.app";
const [label, mode, question, pick] = process.argv.slice(2);
const t0 = Date.now();
const browser = await chromium.launch({ channel: "chrome" });
const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 }, reducedMotion: "reduce" });
const page = await ctx.newPage();
const notes = [];
await page.goto(WEB, { waitUntil: "load" });
const modal = page.locator('[data-testid="disclaimer-modal"]');
await modal.waitFor({ state: "visible", timeout: 20000 });
await modal.getByRole("checkbox").check();
await modal.getByRole("button", { name: /continue/i }).click();
await modal.waitFor({ state: "hidden", timeout: 10000 });
if (mode === "researcher") {
  await page.getByRole("button", { name: /^Researcher$/ }).first().click();
}
const modeState = await page.locator('[aria-label="Answer mode, audience-level depth"] button[aria-pressed="true"]').allInnerTexts().catch(() => []);
notes.push("mode pressed: " + modeState.join("|"));
await page.locator('main textarea[aria-label="Your question"]').first().fill(question);
const tAsk = Date.now();
await page.locator('main button[aria-label="Search the knowledge graph"]').first().click();
const meta = page.locator('[data-testid="answer-meta"]');
const opts = page.locator('[data-testid="clarifying-option"]');
let tAnswer = null;
await Promise.race([
  meta.last().waitFor({ state: "visible", timeout: 170000 }),
  opts.first().waitFor({ state: "visible", timeout: 170000 }),
]).catch((e) => notes.push("wait1 error: " + e.message.split("\n")[0]));
if (pick && (await opts.count()) > 0) {
  const all = await opts.allInnerTexts();
  notes.push("clarifying options: " + JSON.stringify(all));
  let target = null;
  for (const cand of pick.split("||")) {
    const t = opts.filter({ hasText: cand }).first();
    if ((await t.count()) > 0) { target = t; notes.push("matched pick candidate: " + cand); break; }
  }
  if (!target) { notes.push("pick not found: " + pick); }
  else {
    const before = await meta.count();
    const tPick = Date.now();
    await target.click();
    notes.push("picked: " + pick);
    await page.waitForTimeout(2500);
    // wait until a new answer-meta appears beyond the clarification one
    const deadline = Date.now() + 170000;
    while (Date.now() < deadline) {
      const n = await meta.count();
      const txt = n ? await meta.last().innerText() : "";
      if (n > 0 && /Answered|answer|\d+(\.\d+)?s/.test(txt) && (n > before || !/Asked back|Clarif/i.test(txt))) {
        // ensure not still streaming
        await page.waitForTimeout(1500);
        break;
      }
      await page.waitForTimeout(1000);
    }
    tAnswer = Date.now() - tPick;
  }
} else {
  tAnswer = Date.now() - tAsk;
}
await page.waitForTimeout(2000);
const metaTexts = await meta.allInnerTexts().catch(() => []);
const text = await page.locator("main").first().innerText().catch(() => "");
const links = await page.locator("main a[href]").evaluateAll((as) => as.map((a) => `${a.innerText.trim().replace(/\s+/g, " ")} -> ${a.href}`));
await page.screenshot({ path: path.join(HERE, `${label}.png`), fullPage: true });
const clean = (s) => s.split(REPO).join("<repo-root>");
fs.writeFileSync(path.join(HERE, `${label}.txt`), clean(
  `QUESTION: ${question}\nMODE: ${mode}\n\n--- ANSWER TEXT ---\n${text}\n\n--- ANSWER META ---\n${metaTexts.join("\n")}\n\n--- LINKS (${links.length}) ---\n${links.join("\n")}\n`));
fs.writeFileSync(path.join(HERE, `${label}.meta.txt`), clean(
  `wall clock from ask to captured: ${((Date.now() - tAsk) / 1000).toFixed(1)}s\nanswer wait after pick or ask: ${tAnswer ? (tAnswer / 1000).toFixed(1) : "n/a"}s\n${notes.join("\n")}\n`));
await browser.close();
console.log(label, "done", notes.join(" ; "));
