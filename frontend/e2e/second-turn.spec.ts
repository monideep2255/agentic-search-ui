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
