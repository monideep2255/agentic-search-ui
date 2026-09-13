/**
 * Fix set 6 item 6.1, requirement D3: the first automated assertion in this
 * repository on a REAL answer body.
 *
 * WHAT THE GAP WAS. Every other spec in this directory drives
 * `tests/e2e_support/mock_llm_backend.py` with its outbound model call faked,
 * which is correct for an ordinary run: it is fast, deterministic, offline and
 * free. It also means no automated run has ever seen an answer a model wrote.
 * The answer-shaping work arriving in fix sets 7 to 10 could therefore only be
 * checked by hand, one question at a time.
 *
 * HOW THIS RUNS. Opt in with S3_E2E_REAL_MODEL=1 (`npm run test:real-answer`).
 * The flag reaches the backend through `playwright.config.ts`, the backend
 * loads the repository `.env`, skips the model fakes, and every guard, think,
 * plan and write call reaches the configured provider. So this spends real
 * model budget and reaches the public internet on every run, which is why it
 * is skipped by default and why it asks exactly one question (two at the
 * most, see the retry below).
 *
 * IT PROVES THE BACKEND IS REAL BEFORE IT ASKS. `playwright.config.ts` sets
 * `reuseExistingServer`, so a fake-mode backend already listening on the port
 * is reused and the flag alone guarantees nothing. Asserting on a fake
 * answer's shape would pass, silently, and certify nothing. The first thing
 * this spec does is ask the backend `/__e2e__/mode` and stop if it says fake.
 *
 * WHY ONE RETRY, AND ONLY ONE. The product refuses this exact question about
 * one time in three today: see `testing/Product/Product_workflows.md`'s
 * "Already known" and the paused consistency baseline in
 * `requirements/phase_6/Continuation_prompt.md`. Fix set 10 owns making it
 * reliable, not this spec. So a first-attempt refusal is retried once through
 * "New search", and two refusals FAIL with the refusal text in the message.
 * That is deliberate: the run then reports the product's own defect rather
 * than hiding it behind a tolerant assertion, and a third attempt would start
 * grinding budget against a known-open ticket.
 *
 * COVERAGE STATEMENT (`goal-contracts.md`: a verify surface must state its
 * own coverage).
 *
 * What it exercises: a real guard, think, plan, act and write pass over the
 * real Layer 1 graph and the real model; that the answer is not a refusal;
 * that it renders at least one claim and at least one citation chip; that at
 * least one source card links to an `https://` URL on an NCBI host; that the
 * meta strip reports at least one source; that the researcher depth names a
 * disease in words and leaks no raw `MedGen:` code (fix set 6 item 6.2).
 *
 * What it does NOT exercise: whether any stated fact is TRUE. Nothing here
 * checks a claim against NCBI, compares a gene-disease association to the
 * record it cites, or judges the answer's quality. This is a shape and
 * grounding check only. It also asserts nothing about latency beyond the
 * 120-second landing ceiling, tests one question at one depth, and cannot
 * distinguish a good answer from a shallow one.
 *
 * One further omission, named because the first real run found it and this
 * spec deliberately does not assert on it: the `MedGen:` check covers the
 * claim SENTENCE, not the citation chip's own label. A chip renders its
 * source's name verbatim, and a MedGen source's name is still the raw CURIE,
 * so a reader today sees "MedGen:C0346153" in the chip beside a sentence
 * that correctly says "Familial cancer of breast". That is a defect in the
 * source name, one layer away from the answer text fix set 6 item 6.2 made,
 * and it belongs to whoever owns the source-naming fix. Asserting it here
 * would mean a spec that fails every run over a ticket it does not own,
 * which is how a gate stops being read.
 */

import { randomUUID } from "node:crypto";
import { expect, test, type Page } from "@playwright/test";

import { BACKEND_URL } from "../playwright.config";

const REAL_MODEL_ENABLED = process.env.S3_E2E_REAL_MODEL === "1";

const TEST_PASSWORD = "Str0ngPassw0rd!";
const QUESTION = "Which diseases are associated with BRCA1?";

/** A real answer is slow. 120 seconds is the ceiling, not the expectation. */
const LANDING_TIMEOUT_MS = 120_000;

/**
 * At least one of these words must appear in the answer's claims. They are
 * the diseases BRCA1 is actually associated with, plus two generic terms, so
 * a correct answer written in any reasonable phrasing matches. This is a
 * "names a disease in words" check, never a correctness check.
 */
const DISEASE_IN_WORDS = /breast|ovarian|cancer|Fanconi|carcinoma/i;

/** An NCBI host, pinned the way `production-standards.md` requires. */
const NCBI_HOST = /^https:\/\/([A-Za-z0-9-]+\.)*ncbi\.nlm\.nih\.gov\//;

async function dismissDisclaimerIfShown(page: Page): Promise<void> {
  const dialog = page.getByTestId("disclaimer-modal");
  if (await dialog.isVisible().catch(() => false)) {
    await dialog.getByRole("checkbox").check();
    await dialog.getByRole("button", { name: /continue/i }).click();
    await expect(dialog).toBeHidden();
  }
}

// The same fresh-account helper `history-reload.spec.ts` uses: a new email
// every run, so no assertion here depends on a previous run's state.
async function signUpFreshAccount(page: Page, email: string): Promise<void> {
  await page.goto("/");
  await dismissDisclaimerIfShown(page);
  await page
    .getByRole("navigation", { name: /main/i })
    .getByRole("button", { name: /log in/i })
    .click();
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(TEST_PASSWORD);
  await page.getByRole("button", { name: "Log in" }).click();
  await expect(page.getByRole("main").getByRole("textbox", { name: /question/i })).toBeVisible({
    timeout: 20_000,
  });
}

async function askAndWaitForLanding(page: Page): Promise<void> {
  await page.getByRole("main").getByRole("textbox", { name: /question/i }).fill(QUESTION);
  await page
    .getByRole("main")
    .getByRole("button", { name: /^search the knowledge graph$/i })
    .click();
  // Either terminal surface ends the wait: the meta strip a landed answer
  // carries, or the refusal block. Waiting on the answer alone would burn the
  // whole ceiling on a refusal that had already arrived.
  await expect(
    page.locator('[data-testid="answer-meta"], [data-testid="answer-refusal"]').first(),
  ).toBeVisible({ timeout: LANDING_TIMEOUT_MS });
}

test.describe(
  REAL_MODEL_ENABLED
    ? "a real answer (S3_E2E_REAL_MODEL=1)"
    : "a real answer (skipped: set S3_E2E_REAL_MODEL=1)",
  () => {
    test.skip(
      !REAL_MODEL_ENABLED,
      "reaches a real model provider and the public internet, and spends real budget",
    );
    // The global config timeout is 30 seconds, which a real answer exceeds on
    // its own before either retry.
    test.describe.configure({ timeout: 300_000 });

    test("names diseases in words, cites them, and links a source to an NCBI record", async ({
      page,
      request,
    }) => {
      // STEP 1, BEFORE ANY BUDGET IS SPENT: prove this backend is the real
      // one. `request` is Playwright's own Node-side HTTP client, so this
      // never goes through the browser.
      const modeResponse = await request.get(`${BACKEND_URL}/__e2e__/mode`);
      expect(
        modeResponse.ok(),
        `the backend at ${BACKEND_URL} did not answer /__e2e__/mode; it is probably an older ` +
          "build. Stop every process on that port and re-run.",
      ).toBe(true);
      const mode = (await modeResponse.json()) as { model?: string };
      expect(
        mode.model,
        "the backend is in FAKE model mode, so this spec would assert on a canned answer. A " +
          "mock backend was almost certainly already listening on the port and got reused " +
          "(playwright.config.ts sets reuseExistingServer). Stop it and re-run.",
      ).toBe("real");

      await signUpFreshAccount(page, `e2e-real-${randomUUID()}@example.com`);

      // STEP 2: ask, with one retry reserved for the known refusal (see this
      // file's docstring). `attempt` is the loop's own record so the failure
      // message can say which attempts refused.
      const refusals: string[] = [];
      for (let attempt = 1; attempt <= 2; attempt++) {
        if (attempt > 1) {
          await page.getByRole("button", { name: "New search", exact: true }).click();
          await expect(
            page.getByRole("main").getByRole("textbox", { name: /question/i }),
          ).toBeVisible({ timeout: 20_000 });
        }
        await askAndWaitForLanding(page);

        const refusal = page.getByTestId("answer-refusal");
        if ((await refusal.count()) === 0) break;
        refusals.push(((await refusal.first().textContent()) ?? "").trim());
      }

      expect(
        refusals.length,
        `the product refused this question on ${refusals.length} of 2 attempts, so there is no ` +
          "real answer to assert on. This is the known reliability defect fix set 10 owns, " +
          `reported rather than tolerated. Refusals: ${JSON.stringify(refusals)}`,
      ).toBeLessThan(2);
      await expect(page.getByTestId("answer-refusal")).toHaveCount(0);

      // STEP 3: the answer body itself.
      const claims = page.getByTestId(/^claim-text-/);
      await expect(claims, "a landed answer rendered no claims at all").not.toHaveCount(0);
      await expect(
        page.getByTestId(/^citation-/).first(),
        "no claim carried a citation chip, so nothing in this answer is grounded",
      ).toBeVisible();

      /*
       * THE CLAIM PROSE ONLY: the DIRECT text-node children of each claim
       * element, which is the sentence a reader reads.
       *
       * `allInnerTexts()` was the first version and it measured a superset,
       * which the first real run proved rather than an argument: a claim
       * element also contains a visually hidden "Source 1, layer 2" summary
       * for assistive technology (both clipped, so `innerText` keeps them)
       * and one citation chip per source, whose visible label is the
       * source's own name. So the joined text carried
       * "MedGen:C0346153" from the CHIP while the sentence itself correctly
       * read "Familial cancer of breast", and the run failed on a string the
       * requirement was never about.
       *
       * That chip label is a real, separate defect, reported rather than
       * asserted here: this spec owns the sentence, and a chip assertion
       * would fail every run against a ticket it does not own. See the
       * coverage statement at the top of this file.
       */
      const claimText = (
        await claims.evaluateAll((nodes) =>
          nodes.map((node) =>
            Array.from(node.childNodes)
              .filter((child) => child.nodeType === Node.TEXT_NODE)
              .map((child) => child.textContent ?? "")
              .join(""),
          ),
        )
      ).join("\n");
      // POPULATE-CHECK: without it, both assertions below would pass against
      // an answer whose claims rendered empty, and the "no MedGen: code"
      // assertion in particular would pass on an empty string.
      expect(
        claimText.trim().length,
        "populate-check failed: the claims rendered but carry no text",
      ).toBeGreaterThan(0);
      expect(
        claimText,
        "the answer names no disease in words. Fix set 6 item 6.2 requires the researcher " +
          `depth to resolve concept ids to names. Claims were: ${claimText}`,
      ).toMatch(DISEASE_IN_WORDS);
      expect(
        claimText,
        "a raw MedGen concept id reached the reader. This is the exact defect that reversed " +
          `the build ordering on 2026-08-31. Claims were: ${claimText}`,
      ).not.toMatch(/MedGen:/);

      // STEP 4: the sources, opened the way `trust-surface.spec.ts` opens
      // them (build phase 4.9 collapsed them behind a disclosure).
      const disclosure = page.getByTestId("sources-disclosure");
      await expect(disclosure, "a landed answer rendered no sources disclosure").toBeVisible();
      await disclosure.getByText("Sources", { exact: true }).click();

      const cards = page.getByTestId(/^source-\d+$/);
      await expect(cards, "the sources disclosure opened on no source cards").not.toHaveCount(0);

      const hrefs = await cards.locator("a").evaluateAll((anchors) =>
        anchors.map((anchor) => anchor.getAttribute("href") ?? ""),
      );
      expect(
        hrefs.length,
        "populate-check failed: no source card rendered a Record link at all, so the host " +
          "assertion below would have had nothing to reject",
      ).toBeGreaterThan(0);
      expect(
        hrefs.some((href) => NCBI_HOST.test(href)),
        `no source linked to an NCBI record. Links were: ${JSON.stringify(hrefs)}`,
      ).toBe(true);

      // STEP 5: the meta strip's own count, which reads "N tools · M sources
      // from K layers". Asserted separately from the cards above because the
      // strip and the cards are two independent renderings of the same run,
      // and a disagreement between them is itself a defect.
      const metaText = ((await page.getByTestId("answer-meta").textContent()) ?? "").trim();
      const sourceCount = Number(/(\d+)\s+sources?/.exec(metaText)?.[1] ?? "0");
      expect(
        sourceCount,
        `the meta strip reports no sources. It read: ${JSON.stringify(metaText)}`,
      ).toBeGreaterThanOrEqual(1);
    });
  },
);
