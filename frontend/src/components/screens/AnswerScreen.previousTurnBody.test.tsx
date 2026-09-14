/**
 * UI fix set 7 items 7.4 and 7.5: a folded turn keeps its whole answer, the
 * spacing between turns reads, and a clarification lands in the follow-up
 * field.
 *
 * The product owner on 2026-09-13, retesting fix set 7 on develop:
 *
 *   "The formatting and spacing between the answers is way off. Improve the
 *   spacing. Also in the folded answer the sources and everything else run
 *   previously must still be visible. Basically, the previous answer with
 *   all sources must be retained, think of threads that enter the drop down
 *   like structure. Also the follow up must retain context or ask
 *   clarification if the question is not clear. Because if this is a
 *   discussion, it must flow."
 *
 * WHAT WAS WRONG. The thread rendered a hand-written precis of each earlier
 * turn: the claim TEXTS, with no citation chips, and one line reading
 * "5 sources · Grounded". Every source card, every record link, every trust
 * pill and the whole status line were dropped. On a product whose argument
 * is that a claim is worth no more than the record under it, that is the
 * answer minus the reason to believe it. The spacing had the prototype's
 * `.thread{margin-top:26px}` verbatim, which was correct while the thread
 * sat BELOW the answer and wrong the moment R22 moved it above: the gap
 * went to the side facing the card's own padding and the side facing the
 * new question got none.
 *
 * COVERAGE STATEMENT, per `goal-contracts`:
 *
 *   Exercised     that a folded turn's source card opens to a real record
 *                 ANCHOR and that its trust pill is present, reached by
 *                 clicking rather than by reading props; that the live body
 *                 and a folded body given the same content render the SAME
 *                 elements, which is the property that keeps them from
 *                 drifting; that the thread carries a bottom margin ahead
 *                 of the question heading; that the follow-up field takes
 *                 focus on a clarification and does not otherwise; and that
 *                 a folded turn carries neither the flag control nor the
 *                 feedback surface nor the follow-up field.
 *
 *   NOT exercised whether a closed `<details>` visually hides its body.
 *                 jsdom renders `<details>` children whatever the `open`
 *                 attribute says, so every presence assertion below would
 *                 hold for a browser too but says nothing about what a
 *                 reader can see at a glance. Geometry and visibility live
 *                 in `e2e/second-turn.spec.ts`, which opens a folded turn
 *                 in a real browser and looks for the record link inside
 *                 it.
 *
 *                 The pixel values themselves, beyond the one margin this
 *                 file pins. A spacing scale is not a layout.
 */

import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { AnswerScreen } from "./AnswerScreen";
import type { AnswerBodyContent, PreviousTurn } from "./AnswerScreen";
import { FollowUp } from "../answer/FollowUp";

const RECORD_URL = "https://www.ncbi.nlm.nih.gov/gene/672";

/** One landed answer, used for both the live turn and the archived one. */
const CONTENT: AnswerBodyContent = {
  claims: [
    { text: "BRCA1 is associated with hereditary breast cancer.", layer: 1, citations: [1] },
  ],
  sources: [
    {
      n: 1,
      layer: 1,
      name: "NCBI Gene",
      tool: "cypher_query",
      evidence: "curated assertion",
      confidence: "high",
      license: "public domain",
      url: RECORD_URL,
    },
  ],
  trust: [{ kind: "good", label: "Grounded · every claim cited" }],
  meta: "1 tool · 1 source from 1 layer",
  outcome: "Answered",
  outcomeTone: "good",
  elapsedMs: 4200,
  steps: [{ step: "Think", at: "0.2s", text: "One gene, one lookup." }],
  systemNotes: [],
};

const TURN: PreviousTurn = {
  ...CONTENT,
  question: "What gene is BRCA1?",
  meta: CONTENT.meta as string,
};

describe("a folded turn keeps the whole answer it had (item 7.4)", () => {
  it("opens to a real record anchor and a trust pill, not a source count", async () => {
    const user = userEvent.setup();
    render(
      <AnswerScreen
        question="What variants cause it?"
        previousTurns={[TURN]}
        claims={[]}
        sources={[]}
      />,
    );

    const previous = screen.getByTestId("previous-turn-0");
    // POPULATE-CHECK. Without it, every assertion below could be satisfied
    // by a screen with no thread at all, which is how "the sources are
    // missing" and "the turn is missing" become indistinguishable.
    expect(previous).toHaveTextContent("What gene is BRCA1?");

    // The status line the old precis dropped entirely.
    expect(screen.getByTestId("previous-turn-0-answer-meta")).toHaveTextContent("Answered");
    expect(screen.getByTestId("previous-turn-0-answer-meta")).toHaveTextContent("4.2s");

    // The claim, WITH its citation chip. The old body rendered the text and
    // no chip, so a reader could not tell a cited sentence from an uncited
    // one on an earlier turn.
    expect(screen.getByTestId("previous-turn-0-claim-text-0")).toHaveTextContent(
      "hereditary breast cancer",
    );
    expect(screen.getByTestId("previous-turn-0-citation-1")).toBeInTheDocument();

    // The verdict pill, reached by its own kind rather than by matching the
    // summary line's prose.
    expect(screen.getByTestId("previous-turn-0-trust-good")).toHaveTextContent("Grounded");

    // AND THE SOURCE ITSELF, opened the way a reader opens it: the
    // disclosure, then the card. Clicking rather than asserting presence is
    // what makes this an arm about a usable record instead of about a hidden
    // subtree.
    await user.click(
      within(screen.getByTestId("previous-turn-0-sources-disclosure")).getByText("Sources"),
    );
    const card = screen.getByTestId("previous-turn-0-source-1");
    await user.click(within(card).getByText("NCBI Gene"));

    const link = within(card).getByRole("link", { name: RECORD_URL });
    expect(link).toHaveAttribute("href", RECORD_URL);
  });

  /**
   * THE ANTI-DRIFT CONTROL, and the reason this file exists rather than a
   * handful of extra assertions in `AnswerScreen.thread.test.tsx`.
   *
   * The defect was not a missing field. It was a SECOND RENDERER: a folded
   * turn had its own markup that happened to look similar and fell behind.
   * Listing the fields it should carry would only restate the same bet, so
   * the property asserted is structural: given identical content, the
   * folded body and the live body render the same elements.
   *
   * A hand-written folded renderer fails this whatever it remembers to
   * include, because it would have to reproduce every test id exactly.
   */
  it("renders the same elements as the live body, given the same answer", () => {
    render(
      <AnswerScreen
        question="What variants cause it?"
        previousTurns={[TURN]}
        {...CONTENT}
        onFlagSource={() => {}}
      />,
    );

    const idsUnder = (root: HTMLElement, prefix: string) =>
      Array.from(root.querySelectorAll("[data-testid]"))
        .map((element) => element.getAttribute("data-testid") ?? "")
        .map((id) => (id.startsWith(prefix) ? id.slice(prefix.length) : `UNPREFIXED:${id}`))
        .sort();

    const live = idsUnder(screen.getByTestId("answer-body"), "");
    const folded = idsUnder(screen.getByTestId("previous-turn-0-answer-body"), "previous-turn-0-");

    // POPULATE-CHECK, and it is doing real work: two EMPTY lists are equal,
    // so without this an `AnswerBody` that rendered nothing at all would
    // pass the comparison below with a clean green tick.
    expect(live).toContain("answer-meta");
    expect(live).toContain("claim-text-0");
    expect(live).toContain("source-1");
    expect(live).toContain("trust-good");
    expect(live.length).toBeGreaterThan(5);

    expect(folded).toEqual(live);
  });

  it("gives a folded turn no controls that act on the live run", () => {
    render(
      <AnswerScreen
        question="What variants cause it?"
        previousTurns={[TURN]}
        {...CONTENT}
        onFlagSource={() => {}}
        followUp={<div data-testid="fake-follow-up">follow up</div>}
      />,
    );

    // One flag control, on the live answer, not two. An archived source
    // flagged against this run's id would file a report about the wrong
    // answer.
    expect(screen.getAllByRole("button", { name: /flag: does not support/i })).toHaveLength(1);
    // And exactly one follow-up field and one feedback surface, both
    // belonging to the answer in front of the reader.
    expect(screen.getAllByTestId("fake-follow-up")).toHaveLength(1);
    expect(screen.getAllByTestId("feedback")).toHaveLength(1);
  });
});

describe("the spacing between turns (item 7.4)", () => {
  it("leaves a gap between the folded rows and the new question", () => {
    render(
      <AnswerScreen
        question="What variants cause it?"
        previousTurns={[TURN, { ...TURN, question: "And in mice?" }]}
        claims={[]}
        sources={[]}
      />,
    );

    const thread = screen.getByTestId("thread");
    // POPULATE-CHECK: two rows, so the row gap below is a statement about
    // rows that exist.
    expect(screen.getByTestId("previous-turn-1")).toBeInTheDocument();

    const style = getComputedStyle(thread);
    // 26px, MUI spacing 3.25, which is the prototype's own
    // `.thread{margin-top:26px}` moved to the side that now faces the
    // current turn. The old code had it as a margin-TOP, where the card's
    // own padding already sat, and nothing at the bottom, so a folded row
    // ended hard against the heading.
    expect(style.marginBottom).toBe("26px");
    expect(style.marginTop).not.toBe("26px");
    // The prototype's `gap:14px` between rows, unchanged and pinned so a
    // future spacing pass cannot quietly close it.
    expect(style.rowGap === "14px" || style.gap === "14px").toBe(true);
  });
});

describe("a clarification flows into the follow-up field (item 7.5)", () => {
  const CLARIFICATION = "Do you mean the human BRCA1 gene, or the mouse Brca1 gene?";

  it("focuses the follow-up field so the reader answers in place", () => {
    render(
      <AnswerScreen
        question="Tell me about brca1"
        claims={[]}
        sources={[]}
        clarifying
        refusalLabel="One more detail needed"
        refusal={CLARIFICATION}
        followUp={<FollowUp />}
      />,
    );

    // POPULATE-CHECK: the question really is on screen, so "the field is
    // focused" is about a clarification a reader can see and answer.
    expect(screen.getByTestId("answer-refusal")).toHaveTextContent(CLARIFICATION);
    expect(screen.getByTestId("answer-refusal")).toHaveTextContent("One more detail needed");

    const field = screen.getByRole("textbox", { name: /ask a follow-up question/i });
    expect(document.activeElement).toBe(field);
  });

  it("leaves focus alone on an ordinary answer", () => {
    // The other half. Without it, a screen that focused the follow-up field
    // on every render would pass the arm above and would steal focus from a
    // reader part-way through reading an answer.
    render(
      <AnswerScreen question="What gene is BRCA1?" {...CONTENT} followUp={<FollowUp />} />,
    );

    const field = screen.getByRole("textbox", { name: /ask a follow-up question/i });
    expect(field).toBeInTheDocument();
    expect(document.activeElement).not.toBe(field);
  });
});
