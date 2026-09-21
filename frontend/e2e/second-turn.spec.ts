/**
 * T-4.16-02, the product owner's defect 2 from the live demo: "Then chat
 * does not continue", a second turn cannot be taken.
 *
 * WHY THIS IS A BROWSER TEST AND NOT A JSDOM ONE. `App.tsx`'s `ask()` reads
 * correct on inspection: it bumps `askSeq`, clears `runId`, moves to the run
 * view, calls `createRun`, and adopts the new run id. Nothing in the source
 * says why a second turn would fail. That is precisely the situation this
 * repository has recorded four times now, in `LEARNINGS.md` rows 107 to 109
 * and again in build phase 4.16's own defect 7: a defect that survives
 * reading is found by running the thing and looking at it.
 *
 * A follow-up runs a FULL search rather than reusing the previous answer,
 * per `components/answer/FollowUp.tsx`. So the property under test is not
 * "the answer references turn one", it is simply "a second question asked
 * from the answer screen produces a second answer".
 */

import { randomUUID } from "node:crypto";
import { expect, test, type Page } from "@playwright/test";

const TEST_PASSWORD = "Str0ngPassw0rd!";
const freshEmail = () => `e2e-second-turn-${randomUUID()}@example.com`;

/**
 * Matches `mock_llm_backend.py`'s `_SLOW_QUERY_MARKER`, which makes every
 * model call sleep two seconds. Used by the width arms below so a run is
 * genuinely in flight while the page is measured, rather than racing a
 * backend that answers in about a second.
 */
const SLOW_QUERY_MARKER = "E2E_SLOW_STOP_TEST";

/** The record an archived source card must still link to. */
const CITED_RECORD_URL = "https://www.ncbi.nlm.nih.gov/gene/672";

/** One SSE frame in the shape `adapters/web_sse` actually writes. */
function frame(seq: number, type: string, payload: unknown): string {
  const envelope = {
    type,
    version: "v1",
    trace_id: "second-turn-spec",
    seq,
    ts: "2026-09-13T00:00:00Z",
    payload,
  };
  return `id: ${seq}\nevent: ${type}\ndata: ${JSON.stringify(envelope)}\n\n`;
}

/**
 * An answer with one CITED claim, one source card and a verdict pill.
 *
 * Transcribed from `trust-surface.spec.ts`'s own scripted stream rather than
 * invented, so the two suites cannot disagree about what a cited answer
 * looks like on the wire.
 */
const CITED_STREAM = [
  frame(0, "guard", { passed: true, category: "ok", reason: null }),
  frame(1, "think", {
    narrative: "Resolving the gene named in the question.",
    query_class: "single_hop",
    resolved_entities: [],
    clarifying_question: null,
  }),
  frame(2, "plan", { narrative: "Query the graph.", tool_calls: [] }),
  frame(3, "tool_result", {
    call_id: "c1",
    tool: "cypher_query",
    layer: "layer_1_graph",
    status: "ok",
    summary: "",
    result_count: 25,
    truncated: false,
  }),
  frame(4, "token", {
    text: "BRCA1 is associated with hereditary breast and ovarian cancer syndrome [1]. ",
    marker_ids: ["cid-1"],
  }),
  frame(5, "citation", {
    citation_id: "cid-1",
    display_index: 1,
    source: "NCBI Gene",
    source_id: "672",
    source_url: CITED_RECORD_URL,
    layer: "layer_1_graph",
    field: "cypher_query",
    claim_text: "BRCA1 is associated with hereditary breast and ovarian cancer syndrome",
    evidence_kind: "curated assertion",
    assertion_confidence: "high",
    population_ancestry_context: null,
    license: "public domain",
  }),
  frame(6, "trust_signal", {
    outcome: "flag",
    risk_tier: "high",
    grounded: false,
    triangulated: null,
  }),
  /*
   * EVERY FIELD `isDonePayload` REQUIRES, and this is not padding.
   *
   * `trust-surface.spec.ts`'s own `done` frame omits `total_cost_usd` and
   * `total_tool_calls`, so `parseAgentEvent` rejects it and the run ends on
   * a parse error instead of landing. That suite never notices, because
   * nothing in it waits on `answer-meta`, which is written only from a
   * LANDED run's own counts; its citation and source assertions are
   * satisfied by the frames that arrived before the bad one. Copying the
   * fixture without copying the omission is deliberate, and the omission is
   * reported rather than fixed here, since that file belongs to another
   * ticket.
   */
  frame(7, "done", {
    trust_outcome: "flag",
    elapsed_ms: 1200,
    total_cost_usd: 0.004,
    total_tool_calls: 1,
  }),
].join("");

async function enterApp(page: Page): Promise<void> {
  await page.goto("/");
  const dialog = page.getByTestId("disclaimer-modal");
  if (await dialog.isVisible().catch(() => false)) {
    await dialog.getByRole("checkbox").check();
    await dialog.getByRole("button", { name: /continue/i }).click();
    await expect(dialog).toBeHidden();
  }
}

async function signUpFreshAccount(page: Page): Promise<void> {
  await enterApp(page);
  await page
    .getByRole("navigation", { name: /main/i })
    .getByRole("button", { name: /log in/i })
    .click();
  await page.getByLabel("Email").fill(freshEmail());
  await page.getByLabel("Password").fill(TEST_PASSWORD);
  await page.getByRole("button", { name: "Log in" }).click();
  await expect(
    page.getByRole("main").getByRole("textbox", { name: /question/i }),
  ).toBeVisible({ timeout: 20_000 });
}

async function askFromHome(page: Page, question: string): Promise<void> {
  const main = page.getByRole("main");
  await main.getByRole("textbox", { name: /question/i }).fill(question);
  await main.getByRole("button", { name: /^search the knowledge graph$/i }).click();
}

/**
 * WAIT FOR SOMETHING ONLY THE ANSWER SCREEN HAS.
 *
 * The first version of this helper waited for the "New search" button, copied
 * from `feedback-submission.spec.ts`. That is an assertion that cannot fail:
 * "New search" is rendered by BOTH `RunScreen.tsx` (line 168) and
 * `AnswerScreen.tsx` (line 305), so it is visible from the instant a question
 * is dispatched, before a single event has arrived. Both second-turn tests
 * below passed against it in well under two seconds and proved nothing at all.
 *
 * It was caught by screenshotting the deployed demo after this helper said an
 * answer had landed, and seeing the run screen with five pending pips and no
 * answer on it. Reading the helper had not revealed it, which is this
 * repository's recorded pattern for exactly this defect class: the mutation or
 * the picture is the check, never the reading.
 *
 * `answer-meta` is on `AnswerScreen` alone and is written from the landed
 * run's own event counts, so it cannot render before the run finishes.
 */
const answerLanded = (page: Page) =>
  expect(page.getByTestId("answer-meta")).toBeVisible({ timeout: 60_000 });

test.describe("a conversation continues past the first turn", () => {
  test("a follow-up question from the answer screen produces a second answer", async ({
    page,
  }) => {
    const pageErrors: string[] = [];
    page.on("pageerror", (error) => pageErrors.push(error.message));

    await signUpFreshAccount(page);

    await askFromHome(page, "What gene is BRCA1?");
    await answerLanded(page);

    const followUp = page.getByTestId("follow-up");
    // POPULATE-CHECK. Without it, a missing follow-up field would make the
    // rest of this arm unreachable rather than false, and the test would
    // report a pass on a screen that offers no way to continue at all.
    await expect(followUp, "the answer screen offers no follow-up field").toBeVisible();

    await followUp.getByRole("textbox").fill("What diseases are associated with it?");
    await followUp.getByRole("textbox").press("Enter");

    // The second run must actually land. This is the whole complaint: not
    // that the answer is wrong, that there is no second answer at all.
    await answerLanded(page);

    // And an uncaught exception during the second turn is a failure even if
    // something eventually rendered, since that is how "chat does not
    // continue" would present without a visible error.
    expect(pageErrors, "the second turn raised an uncaught error").toEqual([]);
  });

  /**
   * THE SAME JOURNEY WITHOUT AN ACCOUNT, which is how the demo is actually
   * used and therefore how the defect was actually seen. A visitor to the
   * public URL asks a question as a guest; nobody signs up first. The guest
   * path is genuinely different code (`App.tsx`'s `ask()` mints an identity
   * lazily on the first question, then reuses `guestToken`, and the
   * allowance is decremented server-side per run), so a second turn that
   * works signed in proves nothing about it.
   */
  test("a guest can also take a second turn", async ({ page }) => {
    const pageErrors: string[] = [];
    page.on("pageerror", (error) => pageErrors.push(error.message));
    await enterApp(page);

    await askFromHome(page, "What gene is BRCA1?");
    await answerLanded(page);

    const followUp = page.getByTestId("follow-up");
    await expect(followUp, "the answer screen offers no follow-up field").toBeVisible();

    await followUp.getByRole("textbox").fill("What diseases are associated with it?");
    await followUp.getByRole("textbox").press("Enter");

    await answerLanded(page);
    expect(pageErrors, "the second turn raised an uncaught error").toEqual([]);
  });

  /**
   * T-4.16-02, THE ACTUAL DEFECT, settled by the product owner on
   * 2026-08-25: "follow up is part of the current search".
   *
   * The prototype says the same in code. `askFollowUp` calls
   * `archiveCurrent()`, which moves the finished turn into a collapsed
   * `<details class="prev">` inside `<div class="thread">` and only then
   * renders the new answer above it. Nothing built that, so every
   * follow-up REPLACED the answer and the previous turn vanished. The
   * dispatch always worked, which is why two rounds of hunting for a failed
   * second turn found nothing.
   *
   * So the property is not "a second answer appears", which the arms above
   * already cover. It is "the first one is still there".
   *
   * UI FIX SET 7 (R22) EXTENDED IT TO "still there THE WHOLE TIME", and
   * moved the thread above the current turn. The earlier version of this
   * arm was satisfied by a thread that reappeared once the second run
   * landed, which is exactly what the old code did, so the product owner
   * still met a screen with no conversation on it for the ten or twenty
   * seconds that matter most. The in-flight assertions below are what
   * close that.
   *
   * MUTATION-PROVEN, and the asymmetry IS the finding. Disabling the
   * archive turns this arm and the one below red, and leaves BOTH arms
   * above GREEN. Those two are the ones that asked "can a second turn be
   * taken", the question this phase spent two rounds answering with "yes,
   * everywhere, on every path". They were right and they were measuring
   * the wrong property, which is why the defect survived being looked for
   * directly, twice, in two environments.
   */
  test("an earlier turn stays on the page, collapsed, after a follow-up", async ({
    page,
  }) => {
    await signUpFreshAccount(page);

    const first = "What gene is BRCA1?";
    await askFromHome(page, first);
    await answerLanded(page);

    // POPULATE-CHECK. Before the follow-up there is nothing to keep, so a
    // thread MUST be absent here. Without this the arm could pass against
    // a build that renders a thread unconditionally, which would prove
    // nothing about archiving.
    await expect(
      page.getByTestId("thread"),
      "a thread rendered before any follow-up was asked",
    ).toHaveCount(0);

    const followUp = page.getByTestId("follow-up");
    await followUp.getByRole("textbox").fill("What diseases are associated with it?");
    await followUp.getByRole("textbox").press("Enter");

    /*
     * UI FIX SET 7 (R22). CHANGED HERE, deliberately, and this is the half
     * of the property that did not exist before.
     *
     * This arm used to wait for the second answer and only then look for
     * the thread, which was the strongest statement available while a
     * follow-up still swapped the whole screen for the run screen: the
     * thread genuinely WAS off the page for the length of the second run,
     * and that is exactly what the product owner then complained about
     * ("it goes to a new page, which it should not").
     *
     * So the thread is now asserted WHILE the second run is in flight, not
     * merely after it lands. `data-tour="answer"` is on the answer screen's
     * card and nowhere else, so its presence beside a live stepper is the
     * direct proof that no full-screen run replaced this screen.
     */
    await expect(
      page.getByTestId("step-Guard"),
      "the follow-up shows no progress at all",
    ).toBeVisible({ timeout: 10_000 });
    await expect(
      page.getByTestId("previous-turn-0"),
      "the earlier turn left the page while the follow-up was running, " +
        "which is the 'new page' defect R22 exists to close",
    ).toBeVisible();
    await expect(
      page.locator('[data-tour="answer"]'),
      "a full-screen run screen replaced the answer screen",
    ).toBeVisible();

    await answerLanded(page);

    const previous = page.getByTestId("previous-turn-0");
    await expect(
      previous,
      "the earlier turn is gone after a follow-up, so the screen does not read " +
        "as a conversation. This is the defect: the dispatch works and the " +
        "history does not survive it.",
    ).toBeVisible();
    await expect(previous).toContainText(first);

    // Collapsed by default, and genuinely expandable rather than merely
    // present: a summary nobody can open is a label, not a record.
    await expect(previous).not.toHaveAttribute("open", /.*/);
    await previous.getByRole("group").or(previous).locator("summary").click();
    await expect(previous).toHaveAttribute("open", /.*/);
  });

  /**
   * UI fix set 7 (R22): the conversation fits the answer column at both
   * ends of the range, mid-run as well as after.
   *
   * Two elements arrived on this screen in this change and both are wider
   * than they look: the collapsed thread rows, which carry a question and a
   * meta line on one baseline, and the inline progress, whose stepper lays
   * five labelled nodes across the full card. At 390px either can push the
   * page sideways, and a page that scrolls sideways on a phone is how the
   * nav overflow defect presented on 2026-09-05.
   *
   * MEASURED ON THE DOCUMENT, not on the card. A card that fits inside a
   * body that has already overflowed is the shape of every false pass here:
   * the question is whether the PAGE scrolls, so the page is what is
   * measured. One pixel of slack for sub-pixel rounding, which Chromium
   * produces on fractional layouts and is not a scrollbar.
   *
   * THE SLOW MARKER AND THE ATOMIC MEASUREMENT ARE BOTH LOAD-BEARING, and
   * the first draft had neither. It asserted `step-Guard` visible and then
   * measured in a second round trip, which is two observations of a page
   * that is changing between them: this backend answers in about a second,
   * so the measurement could land on the finished answer instead. Mutation
   * caught it. Forcing a 2000px stepper turned the 390px arm red and left
   * the 1280px arm GREEN, not because 1280px is safe but because that arm
   * happened to measure after the run had landed and the stepper it was
   * sent to measure no longer existed.
   *
   * So the follow-up now carries `E2E_SLOW_STOP_TEST`, which makes the
   * backend sleep in every model call, and presence and width are read in
   * ONE `evaluate` so the page cannot change between them. Re-run against
   * the same 2000px mutation, both arms go red.
   */
  for (const width of [390, 1280]) {
    test(`the thread and the inline run fit the page at ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 800 });
      await enterApp(page);

      await askFromHome(page, "What gene is BRCA1?");
      await answerLanded(page);

      const followUp = page.getByTestId("follow-up");
      await followUp
        .getByRole("textbox")
        .fill(`${SLOW_QUERY_MARKER} what diseases are associated with it?`);
      await followUp.getByRole("textbox").press("Enter");

      await expect(page.getByTestId("step-Guard")).toBeVisible({ timeout: 10_000 });

      const during = await page.evaluate(() => ({
        overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
        stepper: document.querySelector('[data-testid="step-Guard"]') !== null,
        thread: document.querySelector('[data-testid="previous-turn-0"]') !== null,
      }));
      // POPULATE-CHECKS, read in the same frame as the width. Both new
      // elements must be on the page AT THE MOMENT it was measured, or this
      // arm measured a page that has neither and passed for it.
      expect(during.stepper, "the run had already landed when the page was measured").toBe(true);
      expect(during.thread, "the earlier turn was not on the page when it was measured").toBe(true);
      expect(during.overflow, "the page scrolls sideways while the follow-up runs").toBeLessThanOrEqual(1);

      await answerLanded(page);
      const after = await page.evaluate(() => ({
        overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
        thread: document.querySelector('[data-testid="previous-turn-0"]') !== null,
      }));
      expect(after.thread, "the earlier turn left the page once the follow-up landed").toBe(true);
      expect(after.overflow, "the page scrolls sideways once the follow-up lands").toBeLessThanOrEqual(1);
    });
  }

  /**
   * UI FIX SET 7 ITEM 7.4: an opened earlier turn is the whole answer.
   *
   * The product owner on 2026-09-13, retesting set 7 on develop: "in the
   * folded answer the sources and everything else run previously must still
   * be visible. Basically, the previous answer with all sources must be
   * retained."
   *
   * The arm above proves an earlier turn STAYS and OPENS. It cannot say what
   * opening it shows, and what it showed was a precis: claim text with no
   * citation chips, and one line reading "1 source · Not fully grounded".
   * Every source card, record link, trust pill and the status line were
   * dropped, on a product whose argument is that a claim is worth no more
   * than the record under it.
   *
   * THE STREAM IS SCRIPTED, for the same reason `trust-surface.spec.ts`
   * scripts its own and in the same words: this suite's mock backend cannot
   * emit a citation, since its only token is the cost-cap partial-result
   * note, so a default run archives a turn with no sources and the arm
   * would pass on a screen that had nothing to lose. The app is untouched
   * and runs its real parsing and rendering; only the bytes on the wire are
   * ours. Both turns are served the same answer, which is fine here: the
   * property is what an ARCHIVED turn keeps, not that two turns differ.
   */
  for (const width of [1280, 390]) {
  test(`an opened earlier turn still carries its sources and its verdict at ${width}px`, async ({
    page,
  }) => {
    /*
     * THE VIEWPORT IS SET BEFORE ANYTHING RENDERS, not resized at the end,
     * and that ordering is load-bearing rather than tidy.
     *
     * The first draft ran the journey at the default width and then called
     * `setViewportSize({ width: 390 })` immediately before measuring. It
     * passed, then reported 151px of overflow on a later run. The layout was
     * fine both times: the history rail is a 248px column above `md` and a
     * drawer below it, chosen by `useMediaQuery`, which re-renders on a
     * resize EVENT. Measuring in the same tick as the resize reads a 390px
     * viewport that still has the desktop column beside it, and 151px is
     * what is left of that column once the answer card has shrunk. So the
     * arm was measuring its own race, and the two outcomes differed only by
     * machine load.
     *
     * Setting the size up front, the way the width arms above already do it,
     * removes the race rather than papering over it with a wait: every
     * measurement below is of a page that has only ever been this wide.
     */
    await page.setViewportSize({ width, height: 900 });
    await page.route("**/v1/query/*/events*", (route) =>
      route.fulfill({
        status: 200,
        headers: { "content-type": "text/event-stream", "cache-control": "no-cache" },
        body: CITED_STREAM,
      }),
    );

    await signUpFreshAccount(page);
    await askFromHome(page, "Which diseases are associated with BRCA1?");
    await answerLanded(page);

    // POPULATE-CHECK, and it is the one that matters most here: the LIVE
    // answer must actually carry a source card, or "the archived turn kept
    // its sources" would be a statement about an answer that never had any.
    await expect(
      page.getByTestId("sources-disclosure"),
      "populate-check failed: the live answer rendered no sources to archive",
    ).toBeVisible();

    const followUp = page.getByTestId("follow-up");
    await followUp.getByRole("textbox").fill("And in mice?");
    await followUp.getByRole("textbox").press("Enter");
    await answerLanded(page);

    const previous = page.getByTestId("previous-turn-0");
    await expect(previous).toBeVisible();
    // The turn's OWN summary: first in document order, ahead of the nested
    // summaries the sources disclosure and each source card bring with them.
    await previous.locator("summary").first().click();
    await expect(previous).toHaveAttribute("open", /.*/);

    // The status line, which the precis dropped entirely.
    await expect(
      page.getByTestId("previous-turn-0-answer-meta"),
      "an opened earlier turn shows no status line",
    ).toBeVisible();
    // The verdict, as a pill rather than as words inside a summary sentence.
    // `.first()` because the test id names the pill's KIND, not the pill, and
    // this answer earns two risk pills: "Not fully grounded" from
    // `grounded: false` and "high risk claim" from the tier. The live answer
    // resolves to two as well; that is the id's shape, not this turn's.
    const verdict = page.getByTestId("previous-turn-0-trust-risk").first();
    await expect(verdict, "an opened earlier turn shows no trust pill").toBeVisible();
    await expect(verdict).toContainText("Not fully grounded");
    // The citation chip beside the claim, so a cited sentence is still
    // distinguishable from an uncited one on an earlier turn.
    await expect(page.getByTestId("previous-turn-0-citation-1")).toBeVisible();

    // AND THE RECORD ITSELF, reached the way a reader reaches it: the
    // disclosure, then the card, then the link.
    const disclosure = page.getByTestId("previous-turn-0-sources-disclosure");
    await expect(
      disclosure,
      "an opened earlier turn offers no sources at all, which is the defect " +
        "item 7.4 exists to close",
    ).toBeVisible();
    await disclosure.getByText("Sources", { exact: true }).click();

    const card = page.getByTestId("previous-turn-0-source-1");
    await expect(card).toBeVisible();
    await card.locator("summary").first().click();

    const link = card.getByRole("link");
    await expect(link, "an archived source card carries no record link").toBeVisible();
    await expect(link).toHaveAttribute("href", CITED_RECORD_URL);

    /*
     * AND IT FITS, WITH EVERYTHING OPEN.
     *
     * The width arms above measure a page whose thread rows are COLLAPSED,
     * which is the only state that existed to measure before this change.
     * An opened turn now nests a source card inside a folded body inside the
     * answer card, three sets of side padding deep, holding a record URL
     * that does not wrap at spaces. At 390px that is a genuinely new way to
     * push the page sideways, and it is measured here rather than assumed.
     *
     * Measured on the DOCUMENT, not the card, for the reason the arms above
     * give: a card that fits inside a body which has already overflowed is
     * the shape of every false pass. Presence and width are read in ONE
     * `evaluate`, so the page cannot change between the two observations.
     * One pixel of slack for Chromium's sub-pixel rounding, which is not a
     * scrollbar.
     */
    const measured = await page.evaluate(() => ({
      overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      open: document.querySelector('[data-testid="previous-turn-0-source-1"]') !== null,
    }));
    expect(measured.open, "the archived source card was gone when the page was measured").toBe(
      true,
    );
    expect(
      measured.overflow,
      `an opened earlier turn scrolls the page sideways at ${width}px`,
    ).toBeLessThanOrEqual(1);
  });
  }

  test("New search starts a fresh conversation rather than extending one", async ({
    page,
  }) => {
    await signUpFreshAccount(page);
    await askFromHome(page, "What gene is BRCA1?");
    await answerLanded(page);

    const followUp = page.getByTestId("follow-up");
    await followUp.getByRole("textbox").fill("What diseases are associated with it?");
    await followUp.getByRole("textbox").press("Enter");
    await answerLanded(page);
    // POPULATE-CHECK: the thread must exist before this arm can show it is
    // cleared, or "no thread" would be true for the wrong reason.
    await expect(
      page.getByTestId("previous-turn-0"),
      "populate-check failed: no thread to clear",
    ).toBeVisible();

    await page.getByRole("button", { name: "New search", exact: true }).first().click();
    await askFromHome(page, "What is TP53?");
    await answerLanded(page);

    await expect(
      page.getByTestId("thread"),
      "the previous conversation carried into a new search",
    ).toHaveCount(0);
  });
});
