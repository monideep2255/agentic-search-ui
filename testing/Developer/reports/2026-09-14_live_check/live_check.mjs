// Live check of UI fix sets 8 and 9 on develop, at 1280 and 390 wide.
import { chromium } from "<repo-root>/frontend/node_modules/playwright/index.mjs";
import fs from "node:fs";

const WEB = "https://search-agent-web-develop-2aeb.up.railway.app";
const OUT = "/private/tmp/claude-501/-Users-<user>-Desktop-Tech-Skills-agentic-search-ui/4f191f8a-e777-42e2-84cd-0f89ca301845/scratchpad/live";
fs.mkdirSync(OUT, { recursive: true });
const results = [];
const log = (r) => { results.push(r); console.log(JSON.stringify(r)); fs.writeFileSync(`${OUT}/results.json`, JSON.stringify(results, null, 2)); };

async function openApp(browser, width) {
  const context = await browser.newContext({ viewport: { width, height: width > 500 ? 900 : 844 } });
  const page = await context.newPage();
  await page.goto(WEB, { waitUntil: "networkidle" });
  const dialog = page.getByRole("dialog");
  if (await dialog.isVisible().catch(() => false)) {
    await dialog.getByRole("checkbox").check();
    await dialog.getByRole("button", { name: /continue/i }).click();
  }
  return { context, page };
}

async function chooseMode(page, label) {
  const group = page.getByRole("group", { name: /answer mode/i }).or(page.getByLabel(/answer mode/i)).first();
  await group.getByText(label, { exact: true }).click();
}

async function watchRun(page, tag, answersBefore) {
  const handoff = { lines: [], badgesSeen: false, sawStreamingClaim: false };
  const started = Date.now();
  let shotDuringAct = false;
  while (Date.now() - started < 150000) {
    const h = page.locator('[data-testid="handoff"]').last();
    if (await h.isVisible().catch(() => false)) {
      const txt = (await h.innerText().catch(() => "")).trim();
      if (txt && !handoff.lines.includes(txt)) handoff.lines.push(txt);
      if (!shotDuringAct) { await page.screenshot({ path: `${OUT}/${tag}_handoff.png`, fullPage: false }); shotDuringAct = true; }
    }
    const lead = await page.getByText(/is handing off to/).first().innerText().catch(() => "");
    if (lead && !handoff.lines.includes(lead)) handoff.lines.push(lead);
    const answers = await page.locator('[data-tour="answer"]').count();
    const newSearch = await page.getByRole("button", { name: "New search", exact: true }).count();
    const running = await page.getByRole("button", { name: /^stop$/i }).count();
    if (running && (await page.locator('[data-testid*="claim-text-"]').count()) > 0) handoff.sawStreamingClaim = true;
    if (answers > answersBefore && newSearch > 0 && running === 0) break;
    await page.waitForTimeout(700);
  }
  return { handoff, elapsed_s: Math.round((Date.now() - started) / 100) / 10 };
}

async function measureAnswer(page, tag) {
  const answer = page.locator('[data-tour="answer"]').last();
  const body = (await answer.innerText().catch(() => "")) || "";
  const m = await answer.evaluate((el) => {
    const q = (s) => el.querySelectorAll(s).length;
    const claims = [...el.querySelectorAll('[data-testid*="claim-text-"]')];
    return {
      headings: q('[data-testid*="answer-heading-"]'),
      list_items: q("li"),
      tables: q('[data-testid*="answer-table"]'),
      bold: q("strong, b"),
      claims: claims.length,
      claims_without_marker: claims.filter((c) => !/\[\d+\]|Source \d+/.test(c.innerText) && c.querySelectorAll('[aria-label^="Source "]').length === 0 && !(c.parentElement && c.parentElement.querySelector('[aria-label^="Source "]'))).length,
      citation_chips: q('[aria-label^="Source "]'),
      notes: q('[data-testid*="answer-note-"], [data-testid*="answer-inline-note-"]'),
    };
  }).catch((e) => ({ error: String(e) }));
  const pageText = await page.locator("body").innerText();
  const trust = (pageText.match(/(Based on \d+ sources?[^\n]*|Confirmed by \d+[^\n]*)/) || [null])[0];
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
  const words = body.split(/\s+/).filter(Boolean).length;
  await page.screenshot({ path: `${OUT}/${tag}_answer.png`, fullPage: true });
  return {
    ...m, words_in_answer_block: words, trust_line: trust,
    medical_note: /research summary, not medical advice/i.test(body),
    raw_medgen_code: /MedGen:C\d+/.test(body),
    refusal: /could not find|No answer found|could not identify/i.test(body),
    horizontal_overflow: overflow,
    first_200: body.slice(0, 200),
  };
}

const browser = await chromium.launch();
try {
  // 1280: BRCA1 plain, follow-up, then GCK researcher
  {
    const { context, page } = await openApp(browser, 1280);
    const selected = await page.getByText("Plain language", { exact: true }).first().evaluate((el) => {
      const b = el.closest("button, [role=radio], [role=button]"); return b ? (b.getAttribute("aria-pressed") || b.getAttribute("aria-checked") || b.className) : "no-button";
    }).catch((e) => String(e));
    const main = page.getByRole("main");
    await main.getByRole("textbox", { name: /question/i }).fill("Which diseases are associated with BRCA1?");
    await main.getByRole("button", { name: /^search the knowledge graph$/i }).click();
    await page.waitForTimeout(1500);
    const lockedDuringRun = await page.locator('[data-testid="depth-locked"]').count().catch(() => 0);
    const run = await watchRun(page, "w1280_brca1_plain", 0);
    log({ width: 1280, case: "BRCA1 plain", default_mode_marker: selected, locked_marker_seen_during_run: lockedDuringRun, ...run, answer: await measureAnswer(page, "w1280_brca1_plain") });

    const before = await page.locator('[data-tour="answer"]').count();
    await page.getByRole("textbox", { name: /follow-up/i }).last().fill("What variants cause it?");
    await page.getByRole("textbox", { name: /follow-up/i }).last().press("Enter");
    const run2 = await watchRun(page, "w1280_followup", before);
    log({ width: 1280, case: "follow-up: What variants cause it?", ...run2, answer: await measureAnswer(page, "w1280_followup") });

    await page.getByRole("button", { name: "New search", exact: true }).first().click();
    await page.waitForTimeout(1000);
    await chooseMode(page, "Researcher");
    const main2 = page.getByRole("main");
    await main2.getByRole("textbox", { name: /question/i }).fill("Variants in GCK causing MODY");
    await main2.getByRole("button", { name: /^search the knowledge graph$/i }).click();
    const run3 = await watchRun(page, "w1280_gck_researcher", 0);
    log({ width: 1280, case: "GCK researcher", ...run3, answer: await measureAnswer(page, "w1280_gck_researcher") });
    await context.close();
  }
  // 390: BRCA1 plain, then EGFR trials in researcher
  {
    const { context, page } = await openApp(browser, 390);
    const main = page.getByRole("main");
    await main.getByRole("textbox", { name: /question/i }).fill("Which diseases are associated with BRCA1?");
    await main.getByRole("button", { name: /^search the knowledge graph$/i }).click();
    const run = await watchRun(page, "w390_brca1_plain", 0);
    log({ width: 390, case: "BRCA1 plain", ...run, answer: await measureAnswer(page, "w390_brca1_plain") });
    await context.close();
  }
} catch (e) {
  log({ fatal: String(e && e.stack || e) });
} finally {
  await browser.close();
}
