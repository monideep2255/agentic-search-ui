/**
 * Item 10.2, overnight run 2026-09-22/23: `SavedAnswerScreen`.
 *
 * Every test states, in a comment, the mutation it is proven to catch.
 */

import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { SavedAnswerScreen } from "./SavedAnswerScreen";
import type { HistoryAnswerResponse } from "../../lib/api";

const ANSWER: HistoryAnswerResponse = {
  trace_id: "t-1",
  question: "What is BRCA1?",
  asked_at: "2026-09-20T10:00:00Z",
  depth: "plain_language",
  answer_markdown: "BRCA1 is a gene associated with hereditary breast cancer.",
  citations: [
    {
      display_index: 1,
      source: "Gene",
      source_url: "https://www.ncbi.nlm.nih.gov/gene/672",
      layer: 1,
      entity_name: "BRCA1",
    },
    {
      display_index: 2,
      source: "Untrusted host",
      source_url: "https://evil.example/record",
      layer: 2,
    },
  ],
  trust_signal: "Grounded, every claim cited",
  trust_line: null,
};

describe("SavedAnswerScreen", () => {
  it("renders the stored answer text, its citations and the trust signal", () => {
    // Mutation: not rendering `answer_markdown`, or dropping the citation
    // list or the trust line, turns this red.
    render(
      <SavedAnswerScreen
        question={ANSWER.question}
        loading={false}
        answer={ANSWER}
        onRunAgain={() => undefined}
      />,
    );
    expect(
      screen.getByText("BRCA1 is a gene associated with hereditary breast cancer."),
    ).toBeInTheDocument();
    expect(within(screen.getByRole("list")).getByText(/1\.\s*BRCA1/)).toBeInTheDocument();
    expect(screen.getByText(/Grounded, every claim cited/)).toBeInTheDocument();
  });

  it("links a citation whose host is on the allowed NCBI list", () => {
    // Mutation: rendering every citation URL as a link regardless of host,
    // or rendering none at all, turns this red.
    render(
      <SavedAnswerScreen question={ANSWER.question} loading={false} answer={ANSWER} onRunAgain={() => undefined} />,
    );
    const link = screen.getByRole("link", { name: "https://www.ncbi.nlm.nih.gov/gene/672" });
    expect(link).toHaveAttribute("href", "https://www.ncbi.nlm.nih.gov/gene/672");
  });

  it("marks an off-host citation URL as not linked instead of rendering a link", () => {
    // Mutation: `isLinkableCitationUrl` not gating the link at all would
    // render a clickable link to an unrecognised host, turning this red.
    render(
      <SavedAnswerScreen question={ANSWER.question} loading={false} answer={ANSWER} onRunAgain={() => undefined} />,
    );
    expect(screen.queryByRole("link", { name: "https://evil.example/record" })).not.toBeInTheDocument();
    expect(screen.getByText(/Not linked: this URL is not on a recognised NCBI host\./)).toBeInTheDocument();
  });

  it("shows the saved-answer marker so the reader can tell this apart from a fresh answer", () => {
    // Mutation: removing the marker, or rendering it only conditionally on
    // something other than "this is the saved-answer screen", turns this
    // red. This is the control item 10.2's done-when names directly:
    // "the screen says that what is shown is the saved answer".
    render(
      <SavedAnswerScreen question={ANSWER.question} loading={false} answer={ANSWER} onRunAgain={() => undefined} />,
    );
    expect(screen.getByTestId("saved-answer-marker")).toHaveTextContent(/Saved answer/);
  });

  it("shows a loading state, not the marker's landed content, before the fetch resolves", () => {
    // Mutation: rendering `saved-answer-body` while `answer` is still null
    // turns this red with a crash (reading fields off null) or a silently
    // blank body, either of which is worse than an honest loading line.
    render(<SavedAnswerScreen question={ANSWER.question} loading answer={null} onRunAgain={() => undefined} />);
    expect(screen.getByTestId("saved-answer-loading")).toBeInTheDocument();
    expect(screen.queryByTestId("saved-answer-body")).not.toBeInTheDocument();
  });

  it("renders trust_line, not trust_signal, when the row carries a stored trust_line", () => {
    // Mutation: reading `trust_signal` instead of `trust_line`, or
    // rendering both at once, turns this red. Defect two,
    // `testing/Developer/reports/2026-09-23_overnight/findings.md`'s
    // "Worker B1" entry: a reopened answer must not read more confident
    // than the one the person saw, and the plain hedge sentence is what
    // carried that honesty on the live screen.
    render(
      <SavedAnswerScreen
        question={ANSWER.question}
        loading={false}
        answer={{ ...ANSWER, trust_line: "Sources disagree on at least one claim." }}
        onRunAgain={() => undefined}
      />,
    );
    expect(screen.getByTestId("saved-answer-trust-line")).toHaveTextContent(
      "Sources disagree on at least one claim.",
    );
    expect(screen.queryByText(/Grounded, every claim cited/)).not.toBeInTheDocument();
  });

  it("falls back to the plain trust_signal line when the row carries no trust_line", () => {
    // Mutation: rendering nothing at all when `trust_line` is null, rather
    // than falling back to the pre-existing `trust_signal` line, turns
    // this red. `ANSWER.trust_line` is `null` in this fixture.
    render(
      <SavedAnswerScreen question={ANSWER.question} loading={false} answer={ANSWER} onRunAgain={() => undefined} />,
    );
    expect(screen.getByTestId("saved-answer-trust-line")).toHaveTextContent(
      "Grounded, every claim cited",
    );
  });

  it("Run again is reachable by keyboard and calls onRunAgain, without starting a new search itself", async () => {
    // Mutation: Run again not being a real, focusable, native button (for
    // example a div with only an onClick) turns this red, since Tab plus
    // Enter would never reach it. A `<button>`'s accessible name is its
    // text content, so no extra `aria-label` mutation to name here beyond
    // the click actually firing.
    const onRunAgain = vi.fn();
    render(
      <SavedAnswerScreen question={ANSWER.question} loading={false} answer={ANSWER} onRunAgain={onRunAgain} />,
    );
    const user = userEvent.setup();
    await user.tab();
    // The marker banner carries no interactive element, so the first Tab
    // stop on this screen is Run again.
    expect(screen.getByRole("button", { name: /Run/ })).toHaveFocus();
    await user.keyboard("{Enter}");
    expect(onRunAgain).toHaveBeenCalledTimes(1);
  });
});
