/**
 * UI fix set 7, R22: the conversation reads top to bottom on one screen.
 *
 * The product owner: "The first answer should minimise and the chat should
 * continue on the same screen. That is one of the most important things."
 *
 * Two properties follow, and this file pins both at the component level,
 * where they are cheap to state and impossible to satisfy accidentally:
 *
 *   Earlier turns sit ABOVE the current turn, oldest first. This is a
 *   deliberate departure from the prototype, which puts the thread below
 *   the answer, so it is asserted on DOM ORDER rather than on mere presence.
 *   Presence was already true before this change and would pass either way.
 *
 *   A run in flight replaces the ANSWER BODY and nothing else. The thread
 *   above it and the question heading stay exactly where they are, which is
 *   what "the same screen" means in DOM terms.
 *
 * `compareDocumentPosition` is the check rather than reading text order out
 * of `textContent`, because it answers the question actually asked, which
 * element comes first in the document, and cannot be satisfied by a string
 * that happens to contain both.
 */

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AnswerScreen } from "./AnswerScreen";
import type { PreviousTurn } from "./AnswerScreen";

const turn = (question: string): PreviousTurn => ({
  question,
  meta: "1 source · 1 tool",
  claims: [{ text: `An earlier claim about ${question}`, layer: 1, citations: [1] }],
  sources: [
    {
      n: 1,
      layer: 1,
      name: "NCBI Gene",
      tool: "cypher_query",
      evidence: "curated assertion",
      confidence: "high",
      license: "public domain",
      url: "https://www.ncbi.nlm.nih.gov/gene/672",
    },
  ],
  trust: [{ kind: "good", label: "Grounded" }],
});

/** True when `first` precedes `second` in document order. */
const precedes = (first: Element, second: Element): boolean =>
  (first.compareDocumentPosition(second) & Node.DOCUMENT_POSITION_FOLLOWING) !== 0;

describe("the conversation thread's position", () => {
  it("renders earlier turns above the current turn's heading", () => {
    render(
      <AnswerScreen
        question="What variants cause it?"
        previousTurns={[turn("What gene is BRCA1?")]}
        claims={[{ text: "The current answer.", layer: 1, citations: [] }]}
        sources={[]}
      />,
    );

    const thread = screen.getByTestId("thread");
    const heading = screen.getByRole("heading", { name: "What variants cause it?" });
    const current = screen.getByTestId("claim-text-0");

    // POPULATE-CHECK. Without it an arm that found neither element would
    // fail on absence rather than on order, and a build that dropped the
    // thread entirely would read as "order fine, nothing to compare".
    expect(thread).toBeInTheDocument();
    expect(current).toHaveTextContent("The current answer.");

    expect(precedes(thread, heading)).toBe(true);
    expect(precedes(thread, current)).toBe(true);
  });

  it("orders the turns oldest first", () => {
    render(
      <AnswerScreen
        question="Third"
        previousTurns={[turn("First"), turn("Second")]}
        claims={[]}
        sources={[]}
      />,
    );

    const first = screen.getByTestId("previous-turn-0");
    const second = screen.getByTestId("previous-turn-1");
    expect(first).toHaveTextContent("First");
    expect(second).toHaveTextContent("Second");
    expect(precedes(first, second)).toBe(true);
  });

  it("keeps every earlier turn collapsed and keyboard reachable", () => {
    render(
      <AnswerScreen
        question="Second"
        previousTurns={[turn("First")]}
        claims={[]}
        sources={[]}
      />,
    );

    const previous = screen.getByTestId("previous-turn-0");
    expect(previous.tagName.toLowerCase()).toBe("details");
    expect(previous).not.toHaveAttribute("open");
    // A `<summary>` is focusable by the browser without any tabindex of its
    // own, which is the whole reason a real `<details>` is used here rather
    // than a div with a click handler. Asserting the element is what keeps
    // a future refactor from silently trading that away.
    expect(previous.querySelector("summary")).not.toBeNull();
  });
});

describe("a run in flight renders inside the answer screen", () => {
  const PROGRESS = <div data-testid="fake-progress">running</div>;

  /*
   * UI fix set 9, item 9.6 CHANGED THIS ARM'S REQUIREMENT, and it is named
   * rather than quietly loosened. It used to assert that no claim renders
   * while a run is in flight, because a claim beside a live stepper could be
   * the previous run's text (F-4.8-J-03). The answer now streams in, so the
   * in-flight run's own claims DO render under the progress. What keeps
   * F-4.8-J-03 closed is upstream and unchanged: `App` renders
   * `EMPTY_RUN_VIEW` until the new run's id exists, so the claims this screen
   * is handed during a run are always that run's. The follow-up field, the
   * sources and the trust line still wait for the run to land.
   */
  it("streams the run's own claims under the progress, keeping the thread and heading", () => {
    render(
      <AnswerScreen
        question="What variants cause it?"
        previousTurns={[turn("What gene is BRCA1?")]}
        progress={PROGRESS}
        claims={[{ text: "A claim from the run in flight.", layer: 1, citations: [1] }]}
        sources={[
          { n: 1, layer: 1, name: "MedGen C1", tool: "name", evidence: "e", confidence: "c", license: "l", url: "https://www.ncbi.nlm.nih.gov/medgen/1" },
        ]}
        trust={[{ kind: "plain", label: "Based on 1 source" }]}
        followUp={<div data-testid="fake-follow-up">follow up</div>}
      />,
    );

    expect(screen.getByTestId("fake-progress")).toBeInTheDocument();
    // The thread and the new question are both still here: this is the
    // "same screen" property, stated as what a reader can still see.
    expect(screen.getByTestId("thread")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "What variants cause it?" }),
    ).toBeInTheDocument();

    // The claim streams in under the progress, and nothing that belongs to a
    // finished answer does.
    expect(screen.getByTestId("streaming-answer")).toContainElement(
      screen.getByTestId("claim-text-0"),
    );
    expect(screen.queryByTestId("sources-disclosure")).toBeNull();
    expect(screen.queryByTestId("trust-line")).toBeNull();
    // The follow-up field goes with it: there is no answer to follow up on
    // yet, and offering one would let a third run start over a second.
    expect(screen.queryByTestId("fake-follow-up")).toBeNull();
  });

  it("puts the answer back in place when no progress is passed", () => {
    // The other half of the arm above. Without it, a component that
    // rendered the progress and NEVER the answer would pass the first arm
    // and be broken in the way that matters most.
    render(
      <AnswerScreen
        question="What variants cause it?"
        previousTurns={[turn("What gene is BRCA1?")]}
        claims={[{ text: "The landed answer.", layer: 1, citations: [] }]}
        sources={[]}
        followUp={<div data-testid="fake-follow-up">follow up</div>}
      />,
    );

    expect(screen.getByTestId("claim-text-0")).toHaveTextContent("The landed answer.");
    expect(screen.getByTestId("fake-follow-up")).toBeInTheDocument();
    expect(screen.getByTestId("thread")).toBeInTheDocument();
  });
});
