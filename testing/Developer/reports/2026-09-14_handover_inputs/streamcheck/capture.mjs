// Playwright capture of the develop web UI's "writing" state and answer
// streaming behaviour, for the streaming investigation.
import { chromium } from "<repo-root>/frontend/node_modules/playwright/index.mjs";
import fs from "fs";
import path from "path";

const OUT_DIR = "/private/tmp/claude-501/-Users-<user>-Desktop-Tech-Skills-agentic-search-ui/4f191f8a-e777-42e2-84cd-0f89ca301845/scratchpad/streamcheck";
const FRAMES_DIR = path.join(OUT_DIR, "frames");
fs.mkdirSync(FRAMES_DIR, { recursive: true });

const URL = "https://search-agent-web-develop-2aeb.up.railway.app";

async function main() {
  const browser = await chromium.launch();
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await context.newPage();

  await page.goto(URL, { waitUntil: "domcontentloaded" });

  // Accept the disclaimer: checkbox then Continue.
  await page.waitForTimeout(1000);
  try {
    const checkbox = page.getByRole("checkbox");
    await checkbox.first().check({ timeout: 10000 });
    const continueBtn = page.getByRole("button", { name: /continue/i });
    await continueBtn.first().click({ timeout: 10000 });
  } catch (e) {
    console.log("disclaimer step warning:", e.message);
  }

  await page.waitForTimeout(500);

  const questionBox = page.locator("main").getByRole("textbox", { name: /question/i });
  await questionBox.first().waitFor({ state: "visible", timeout: 15000 });
  await questionBox.first().fill("Which diseases are associated with BRCA1?");

  const searchBtn = page.getByRole("button", { name: /^search the knowledge graph$/i });
  await searchBtn.first().waitFor({ state: "visible", timeout: 15000 });

  const timeline = [];
  const t0 = Date.now();
  await searchBtn.first().click();

  const maxMs = 60000;
  const intervalMs = 250;
  let frameIdx = 0;
  let answerLanded = false;

  while (Date.now() - t0 < maxMs && !answerLanded) {
    const now = Date.now() - t0;
    const shotName = `frame_${String(frameIdx).padStart(4, "0")}_t${now}ms.png`;
    const shotPath = path.join(FRAMES_DIR, shotName);
    try {
      await page.screenshot({ path: shotPath });
    } catch (e) {
      console.log("screenshot failed:", e.message);
    }

    let bodyText = "";
    try {
      bodyText = await page.evaluate(() => document.body.innerText);
    } catch (e) {
      bodyText = "";
    }

    let claimCount = 0;
    try {
      claimCount = await page.locator('[data-testid*="claim-text-"]').count();
    } catch (e) {
      claimCount = -1;
    }

    const hasWriting = bodyText.includes("is writing the answer");
    const hasWritingDots = bodyText.toLowerCase().includes("writing...") || bodyText.toLowerCase().includes("writing…");
    const hasFoundRecords = /Found \d+ disease records?/i.test(bodyText);

    timeline.push({
      frame: frameIdx,
      t_ms: now,
      file: shotName,
      has_is_writing_the_answer: hasWriting,
      has_writing_dots: hasWritingDots,
      has_found_disease_records: hasFoundRecords,
      claim_count: claimCount,
      body_text_len: bodyText.length,
    });

    // crude landing check: claims present and no more spinner-ish writing text
    if (claimCount > 0 && !hasWriting) {
      answerLanded = true;
    }

    frameIdx += 1;
    await page.waitForTimeout(intervalMs);
  }

  // one final screenshot after landing (or timeout)
  const finalShot = path.join(FRAMES_DIR, `frame_${String(frameIdx).padStart(4, "0")}_final.png`);
  await page.screenshot({ path: finalShot });

  fs.writeFileSync(path.join(OUT_DIR, "timeline.json"), JSON.stringify(timeline, null, 2));
  console.log("Saved", timeline.length, "frames. answerLanded=", answerLanded);

  await browser.close();
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
