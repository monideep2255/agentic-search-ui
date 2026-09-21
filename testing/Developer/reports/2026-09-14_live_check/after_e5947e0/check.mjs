// Verification of commit e5947e0 on develop: new answer layout, writing banner,
// clean copy (no visible "Source N, layer L" / "Sources X to Y" text), and the
// GCK/MODY and gene-to-disease answer fixes.
import { chromium } from "/Users/anuradhachakraborti/Desktop/Tech Skills/agentic-search-ui/frontend/node_modules/playwright/index.mjs";
import fs from "node:fs";

const WEB = "https://search-agent-web-develop-2aeb.up.railway.app";
const OUT = "/Users/anuradhachakraborti/Desktop/Tech Skills/agentic-search-ui/testing/Developer/reports/2026-09-14_live_check/after_e5947e0";
fs.mkdirSync(OUT, { recursive: true });

const results = [];
const log = (r) => {
  results.push(r);
  console.log(JSON.stringify(r));
  fs.writeFileSync(`${OUT}/results.json`, JSON.stringify(results, null, 2));
};

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

async function submitQuestion(page, question) {
  const main = page.getByRole("main");
  await main.getByRole("textbox", { name: /question/i }).fill(question);
  await main.getByRole("button", { name: /^search the knowledge graph$/i }).click();
}

// Poll for the writing banner every 250ms and record whether it appeared
// BEFORE the first answer sentence (claim) is visible.
async function watchWritingBannerBeforeFirstClaim(page, timeoutMs = 120000) {
  const started = Date.now();
  let bannerSeenAt = null;
  let bannerText = null;
  let firstClaimSeenAt = null;
  while (Date.now() - started < timeoutMs) {
    const now = Date.now();
    const banner = page.locator('[data-testid="writing-banner"]');
    const bannerVisible = await banner.isVisible().catch(() => false);
    if (bannerVisible && bannerSeenAt === null) {
      bannerSeenAt = now;
      bannerText = (await banner.innerText().catch(() => "")).trim();
    }
    const claim = page.locator('[data-testid*="claim-text-"]').first();
    const claimVisible = await claim.isVisible().catch(() => false);
    if (claimVisible && firstClaimSeenAt === null) {
      const txt = (await claim.innerText().catch(() => "")).trim();
      if (txt.length > 0) firstClaimSeenAt = now;
    }
    const answers = await page.locator('[data-tour="answer"]').count();
    const newSearch = await page.getByRole("button", { name: "New search", exact: true }).count();
    const running = await page.getByRole("button", { name: /^stop$/i }).count();
    if (answers > 0 && newSearch > 0 && running === 0) break;
    await page.waitForTimeout(250);
  }
  return {
    bannerSeenAt,
    bannerText,
    firstClaimSeenAt,
    bannerBeforeFirstClaim:
      bannerSeenAt !== null && (firstClaimSeenAt === null || bannerSeenAt <= firstClaimSeenAt),
    elapsed_s: Math.round((Date.now() - started) / 100) / 10,
  };
}

async function waitForAnswerSettled(page, timeoutMs = 120000) {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    const answers = await page.locator('[data-tour="answer"]').count();
    const newSearch = await page.getByRole("button", { name: "New search", exact: true }).count();
    const running = await page.getByRole("button", { name: /^stop$/i }).count();
    if (answers > 0 && newSearch > 0 && running === 0) break;
    await page.waitForTimeout(500);
  }
  return Math.round((Date.now() - started) / 100) / 10;
}

async function measureAnswer(page) {
  const answer = page.locator('[data-tour="answer"]').last();
  const body = (await answer.innerText().catch(() => "")) || "";
  const m = await answer.evaluate((el) => {
    const q = (s) => el.querySelectorAll(s).length;
    return {
      headings: q('[data-testid*="answer-heading-"]'),
      tables: q('[data-testid*="answer-table"]'),
      table_rows: q('[data-testid*="answer-table"] tbody tr'),
      list_items: q("li"),
      notes: q('[data-testid*="answer-note-"], [data-testid*="answer-inline-note-"]'),
    };
  }).catch((e) => ({ error: String(e) }));
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1);
  return {
    ...m,
    body_excerpt: body.slice(0, 300),
    refusal: /could not find|no answer found|could not identify/i.test(body),
    horizontal_overflow_scrollWidth_le_clientWidthPlus1: !overflow,
  };
}

const browser = await chromium.launch();
try {
  // (a) BRCA1, Plain language, 1280 -- banner-before-first-claim, headings + table.
  {
    const { context, page } = await openApp(browser, 1280);
    await submitQuestion(page, "Which diseases are associated with BRCA1?");
    const bannerCheck = await watchWritingBannerBeforeFirstClaim(page);
    await page.waitForTimeout(500);
    const measured = await measureAnswer(page);
    await page.screenshot({ path: `${OUT}/a_brca1_plain_1280.png`, fullPage: true });
    log({ item: "a_plain", width: 1280, question: "Which diseases are associated with BRCA1?", mode: "plain_language", bannerCheck, measured });

    // (e) Copy check: select the whole answer text and read the selection.
    const answerLoc = page.locator('[data-tour="answer"]').last();
    const selectionText = await answerLoc.evaluate((el) => {
      const range = document.createRange();
      range.selectNodeContents(el);
      const sel = window.getSelection();
      sel.removeAllRanges();
      sel.addRange(range);
      const text = sel.toString();
      sel.removeAllRanges();
      return text;
    });
    const forbidden1 = /Source \d+, layer/i.test(selectionText);
    const forbidden2 = /Sources \d+ to/i.test(selectionText);
    fs.writeFileSync(`${OUT}/e_selection_text.txt`, selectionText);
    log({
      item: "e_copy",
      width: 1280,
      selection_length: selectionText.length,
      contains_source_layer_text: forbidden1,
      contains_sources_range_text: forbidden2,
      pass: !forbidden1 && !forbidden2,
      selection_excerpt: selectionText.slice(0, 400),
    });

    await context.close();
  }

  // (a) BRCA1, Researcher, 1280.
  {
    const { context, page } = await openApp(browser, 1280);
    await chooseMode(page, "Researcher");
    await submitQuestion(page, "Which diseases are associated with BRCA1?");
    const bannerCheck = await watchWritingBannerBeforeFirstClaim(page);
    await page.waitForTimeout(500);
    const measured = await measureAnswer(page);
    await page.screenshot({ path: `${OUT}/a_brca1_researcher_1280.png`, fullPage: true });
    log({ item: "a_researcher", width: 1280, question: "Which diseases are associated with BRCA1?", mode: "researcher", bannerCheck, measured });
    await context.close();
  }

  // (b) HNF1A variant-to-disease, Researcher, 1280.
  {
    const { context, page } = await openApp(browser, 1280);
    await chooseMode(page, "Researcher");
    await submitQuestion(page, "What diseases are caused by variants in the HNF1A gene?");
    await waitForAnswerSettled(page);
    await page.waitForTimeout(500);
    const measured = await measureAnswer(page);
    const answer = page.locator('[data-tour="answer"]').last();
    const headingTexts = await answer.locator('[data-testid*="answer-heading-"]').allInnerTexts();
    const hasVariantToDiseaseHeading = headingTexts.some((t) => /variant-to-disease/i.test(t));
    const tableRowCount = await answer.locator('[data-testid*="answer-table"] tbody tr').count();
    await page.screenshot({ path: `${OUT}/b_hnf1a_researcher_1280.png`, fullPage: true });
    log({
      item: "b_hnf1a",
      width: 1280,
      question: "What diseases are caused by variants in the HNF1A gene?",
      mode: "researcher",
      headingTexts,
      hasVariantToDiseaseHeading,
      tableRowCount,
      measured,
    });
    await context.close();
  }

  // (c) GCK / MODY, 1280.
  {
    const { context, page } = await openApp(browser, 1280);
    await submitQuestion(page, "Variants in GCK causing MODY");
    await waitForAnswerSettled(page);
    await page.waitForTimeout(500);
    const measured = await measureAnswer(page);
    const answer = page.locator('[data-tour="answer"]').last();
    const tableRowCount = await answer.locator('[data-testid*="answer-table"] tbody tr').count();
    await page.screenshot({ path: `${OUT}/c_gck_mody_1280.png`, fullPage: true });
    log({
      item: "c_gck_mody",
      width: 1280,
      question: "Variants in GCK causing MODY",
      answered: !measured.refusal,
      tableRowCount,
      measured,
    });
    await context.close();
  }

  // (d) MODY genes, 1280.
  {
    const { context, page } = await openApp(browser, 1280);
    await submitQuestion(page, "What genes are associated with MODY?");
    await waitForAnswerSettled(page);
    await page.waitForTimeout(500);
    const measured = await measureAnswer(page);
    const answer = page.locator('[data-tour="answer"]').last();
    const tableRowCount = await answer.locator('[data-testid*="answer-table"] tbody tr').count();
    await page.screenshot({ path: `${OUT}/d_mody_genes_1280.png`, fullPage: true });
    log({
      item: "d_mody_genes",
      width: 1280,
      question: "What genes are associated with MODY?",
      answered: !measured.refusal,
      tableRowCount,
      measured,
    });
    await context.close();
  }

  // (f) BRCA1 plain language at 390 wide: stacked rows, no horizontal overflow, banner does not overflow.
  {
    const { context, page } = await openApp(browser, 390);
    await submitQuestion(page, "Which diseases are associated with BRCA1?");
    const bannerCheck = await watchWritingBannerBeforeFirstClaim(page);
    // Check banner overflow while it's likely still around, or re-check after if gone.
    let bannerOverflow = null;
    const bannerLoc = page.locator('[data-testid="writing-banner"]');
    if (await bannerLoc.isVisible().catch(() => false)) {
      bannerOverflow = await bannerLoc.evaluate((el) => el.scrollWidth > el.clientWidth + 1);
    }
    await page.waitForTimeout(500);
    const measured = await measureAnswer(page);
    const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth);
    const clientWidth = await page.evaluate(() => document.documentElement.clientWidth);
    // At phone width (<=720px) a records block renders as a stacked <ul data-testid="answer-records-N">
    // of <li data-testid="claim-text-N"> rows instead of a <table data-testid="answer-table">
    // (AnswerScreen.tsx renderRecords, the `phone` branch). So the pass condition for "stacked rows"
    // is zero answer-table elements and at least one answer-records list with li rows.
    const answer = page.locator('[data-tour="answer"]').last();
    const tableCount = await answer.locator('[data-testid*="answer-table"]').count();
    const recordsListCount = await answer.locator('[data-testid*="answer-records-"]').count();
    const stackedLiCount = await answer.locator('[data-testid*="answer-records-"] li').count();
    const stackedRowsConfirmed = tableCount === 0 && recordsListCount > 0 && stackedLiCount > 0;
    await page.screenshot({ path: `${OUT}/f_brca1_plain_390.png`, fullPage: true });
    log({
      item: "f_phone_390",
      tableCount,
      recordsListCount,
      stackedLiCount,
      stackedRowsConfirmed,
      width: 390,
      question: "Which diseases are associated with BRCA1?",
      bannerCheck,
      bannerOverflow,
      scrollWidth,
      clientWidth,
      scrollWidth_le_clientWidthPlus1: scrollWidth <= clientWidth + 1,
      measured,
    });
    await context.close();
  }
} catch (e) {
  log({ fatal: String((e && e.stack) || e) });
} finally {
  await browser.close();
}
