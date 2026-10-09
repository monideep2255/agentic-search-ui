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
import { designTokens } from "../../theme";

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
  // The stored outcome word, as the backend stores it (`answer`, `flag` or
  // `ask`). Card 71 fix round: this was a made-up sentence, which hid that
  // the no-trust-line fallback printed the raw word after a tick.
  trust_signal: "answer",
  trust_line: null,
};

const NO_CHECK = "Not verified · no grounding check was recorded";

function renderSaved(answer: HistoryAnswerResponse) {
  return render(
    <SavedAnswerScreen question={answer.question} loading={false} answer={answer} onRunAgain={() => undefined} />,
  );
}

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
    expect(screen.getByTestId("saved-answer-trust-line")).toHaveTextContent(NO_CHECK);
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
    expect(screen.queryByText(NO_CHECK)).not.toBeInTheDocument();
    expect(screen.queryByTestId("saved-answer-trust-fallback")).not.toBeInTheDocument();
  });

  it("with no trust_line and no stored tier, says no grounding check was recorded, in the risk colour", () => {
    // Card 71 fix round. Mutation: rendering nothing when `trust_line` is
    // null, or the old tick plus raw outcome word, turns this red.
    renderSaved(ANSWER);
    const span = screen.getByTestId("saved-answer-trust-fallback");
    expect(span).toHaveTextContent(NO_CHECK);
    expect(span).toHaveStyle({ color: designTokens.risk });
    expect(screen.getByTestId("saved-answer-trust-line")).not.toHaveTextContent("✓");
  });

  it("a capped answer (flag, no trust line, no tier) reopens as Not verified, never a tick and the word flag", () => {
    // A-71T-10. The per-question cost limit ends a run with done(flag), no
    // trust_line and no trust_signal; live shows the red NO_CHECK words.
    // Mutation: restoring the old fallback (a tick beside `trust_signal`)
    // turns this red.
    renderSaved({ ...ANSWER, trust_signal: "flag", risk_tier: null });
    const line = screen.getByTestId("saved-answer-trust-line");
    expect(line).toHaveTextContent(NO_CHECK);
    expect(line).not.toHaveTextContent("✓");
    expect(line).not.toHaveTextContent(/\bflag\b/);
    expect(screen.getByTestId("saved-answer-trust-fallback")).toHaveStyle({ color: designTokens.risk });
  });

  it.each([["flag"], ["ask"]])(
    "an %s outcome with a stored tier and no trust_line shows no tick and no raw outcome word",
    (outcome) => {
      // Mutation: letting any outcome with a tier take the grounded tick
      // turns this red. Only an "answer" outcome is a grounded answer.
      renderSaved({ ...ANSWER, trust_signal: outcome, risk_tier: "high" });
      const line = screen.getByTestId("saved-answer-trust-line");
      expect(line).toHaveTextContent(`${NO_CHECK}·High-risk claim`);
      expect(line).not.toHaveTextContent("✓");
      expect(line).not.toHaveTextContent(new RegExp(`\\b${outcome}\\b`));
    },
  );

  it("an answer outcome with a stored tier and no trust_line shows the live grounded words with a tick", () => {
    // The live answer's words for a grounded run with trust signals and no
    // trust line. Mutation: changing the words, or the tick, turns this red.
    renderSaved({ ...ANSWER, risk_tier: "low" });
    const span = screen.getByTestId("saved-answer-trust-fallback");
    expect(span).toHaveTextContent("✓Grounded · every claim cited");
    expect(span).toHaveStyle({ color: designTokens.ink });
    expect(screen.queryByTestId("saved-answer-trust-risk")).not.toBeInTheDocument();
  });

  it("shows the High-risk claim tag for a high tier, in the risk colour, beside the trust line", () => {
    // Card 71. Mutation: not reading `risk_tier` (the pre-card behaviour),
    // changing the words, or dropping the tag's test id turns this red.
    render(
      <SavedAnswerScreen
        question={ANSWER.question}
        loading={false}
        answer={{ ...ANSWER, trust_line: "Based on 2 sources cited, not yet confirmed", risk_tier: "high" }}
        onRunAgain={() => undefined}
      />,
    );
    const tag = screen.getByTestId("saved-answer-trust-risk");
    expect(tag).toHaveTextContent("High-risk claim");
    // J-71T-08: the colour and weight are what make it stand out on the
    // live answer. Mutation: a grey or bold tag turns this red.
    expect(tag).toHaveStyle({ color: designTokens.risk, fontWeight: 400 });
    expect(screen.getByTestId("saved-answer-trust-line")).toContainElement(tag);
    expect(screen.getByTestId("saved-answer-trust-line")).toHaveTextContent(
      "Based on 2 sources cited, not yet confirmed",
    );
  });

  it.each([
    ["moderate", "moderate risk claim"],
    ["critical", "critical risk claim"],
    ["severe", "severe risk claim"],
  ])("shows the live words for a stored %s tier", (tier, words) => {
    // J-71T-09: the other known tiers and a tier the live screen does not
    // know. Mutation: returning no tag for anything but "high" turns this red.
    renderSaved({ ...ANSWER, trust_line: "Based on 2 sources cited, not yet confirmed", risk_tier: tier });
    const tag = screen.getByTestId("saved-answer-trust-risk");
    expect(tag).toHaveTextContent(words);
    expect(tag).toHaveStyle({ color: designTokens.risk, fontWeight: 400 });
  });

  it.each([[null], [undefined], [""], ["low"], ["unknown"]])(
    "shows no risk tag when the stored tier is %s",
    (tier) => {
      // Card 71: an answer saved before the tier was stored shows no tag
      // rather than a wrong one. Mutation: treating a missing tier as high
      // (or rendering the tag unconditionally) turns this red.
      render(
        <SavedAnswerScreen
          question={ANSWER.question}
          loading={false}
          answer={{ ...ANSWER, risk_tier: tier }}
          onRunAgain={() => undefined}
        />,
      );
      expect(screen.getByTestId("saved-answer-trust-line")).toBeInTheDocument();
      expect(screen.queryByTestId("saved-answer-trust-risk")).not.toBeInTheDocument();
      expect(screen.queryByText(/risk claim/i)).not.toBeInTheDocument();
    },
  );

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
