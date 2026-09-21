/**
 * A refusal is a first-class state, not an error (R13, R14, R44).
 *
 * Product-owner decision U6, 2026-09-12. A refusal used to render as an
 * amber alarm box, with red trust pills under it ("Not fully grounded",
 * "Not verified ...") and a red "⚠ Refused" in the meta line above, while
 * the NCBI address the refusal was handing the reader sat inside the
 * sentence as plain, unclickable text. Four signals, none of them wrong on
 * its own terms, together reading as a malfunction on the one path where
 * the system is doing exactly what it was built to do.
 * `design-system/components/trust-pills.html` states the intent in its own
 * note: "Refusal is a first-class state, not an error."
 *
 * LEVEL CHOSEN. Two of these arms drive `useRunView` on a real
 * `AgentEvent[]` and render `AnswerScreen` with the view it produced,
 * rather than with hand-built props. The pill-clearing and the outcome-word
 * suppression live in the hook, and a component test with a hand-made
 * `trust={[]}` prop would pass against the unfixed hook: it would be
 * asserting its own fixture. The two link arms are hand-built props on
 * purpose, because the host pin lives in the component and nothing upstream
 * can make a hostile address reach it.
 *
 * Each arm names the mutation it is proven to catch.
 */

import { render, screen } from "@testing-library/react";
import { renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { AgentEvent } from "../../lib/events";
import { useRunView } from "../../hooks/useRunView";
import type { RunView } from "../../hooks/useRunView";
import { AnswerScreen, isLinkableRefusalLink } from "./AnswerScreen";

let seq = 0;

function envelope<TType extends AgentEvent["type"]>(
  type: TType,
  payload: Extract<AgentEvent, { type: TType }>["payload"],
): AgentEvent {
  seq += 1;
  return {
    type,
    version: "v1",
    trace_id: "trace-refusal",
    seq,
    ts: `2026-09-12T12:00:0${seq % 10}Z`,
    payload,
  } as AgentEvent;
}

/** The view the real hook derives, so no arm asserts its own fixture. */
function viewFor(events: AgentEvent[]): RunView {
  const { result } = renderHook(() => useRunView(events));
  return result.current;
}

/** `AnswerScreen` given a real derived view, as `App` passes it. */
function renderWithView(view: RunView, question: string) {
  render(
    <AnswerScreen
      question={question}
      claims={view.claims}
      sources={view.sources}
      trust={view.trust}
      meta={view.meta}
      outcome={view.outcome}
      outcomeTone={view.outcomeTone}
      elapsedMs={view.elapsedMs}
      refusal={view.refusal}
      refusalLabel={view.refusalLabel}
      refusalLink={view.refusalLink}
      failure={view.failure}
    />,
  );
}

const REFUSE_MESSAGE = "I could not find grounded evidence for this. Try NCBI's cross-database search:";
const FALLBACK_LINK = "https://www.ncbi.nlm.nih.gov/search/all/?term=BRCA9";

describe("a refusal reads as a calm labelled block, never as an error", () => {
  it("shows an off_topic guard refusal as a neutral label, with no pill and no outcome word", () => {
    /*
     * Mutation: restoring `trust` or `outcome` on the refusal path in
     * `useRunView`'s return turns this red, because the red pill or the
     * "⚠ Refused" word reappears on the screen.
     */
    const view = viewFor([
      envelope("guard", { passed: false, category: "off_topic", reason: "asked about a recipe" }),
      envelope("done", {
        total_cost_usd: 0.0,
        total_tool_calls: 0,
        elapsed_ms: 50,
        trust_outcome: "refuse",
      }),
    ]);
    renderWithView(view, "What is a good pasta recipe?");

    const block = screen.getByTestId("answer-refusal");
    expect(block).toHaveTextContent("Outside biomedical research");
    expect(block).toHaveTextContent(/I can help with a gene, variant, pathogen, or paper question/);

    // No pill of any kind: the whole trust strip is absent, not merely
    // recoloured, because it has no claims to report on.
    expect(screen.queryByTestId("trust-risk")).not.toBeInTheDocument();
    expect(screen.queryByTestId("trust-good")).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/trust signals/i)).not.toBeInTheDocument();

    // No outcome word, and therefore no glyph in front of one.
    expect(screen.queryByText(/refused/i)).not.toBeInTheDocument();
    expect(screen.getByTestId("answer-meta")).not.toHaveTextContent("⚠");
  });

  it("renders the NCBI fallback address as a real link on an answer-level refusal", () => {
    /*
     * R14. Mutation: joining `message` and `fallback_link` back into one
     * string, or dropping the anchor for a plain span, turns this red,
     * since there is then no element with the `link` role.
     */
    const view = viewFor([
      envelope("guard", { passed: true, category: "ok", reason: null }),
      envelope("token", { text: `${REFUSE_MESSAGE} ${FALLBACK_LINK}`, marker_ids: [] }),
      envelope("trust_signal", {
        outcome: "refuse",
        risk_tier: "unknown",
        grounded: false,
        triangulated: null,
        scope: "answer",
        message: REFUSE_MESSAGE,
        fallback_link: FALLBACK_LINK,
      }),
      envelope("done", {
        total_cost_usd: 0.01,
        total_tool_calls: 0,
        elapsed_ms: 700,
        trust_outcome: "refuse",
      }),
    ]);
    renderWithView(view, "Is BRCA9 associated with any disease?");

    const block = screen.getByTestId("answer-refusal");
    expect(block).toHaveTextContent("No answer found in NCBI records");
    expect(block).toHaveTextContent(/I could not find grounded evidence for this/);

    // The visible text of the anchor is the address itself, so a reader can
    // see where it goes before following it.
    const link = screen.getByRole("link", { name: FALLBACK_LINK });
    expect(link).toHaveAttribute("href", FALLBACK_LINK);
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");

    expect(screen.queryByTestId("trust-risk")).not.toBeInTheDocument();
    expect(screen.queryByText(/^⚠ Refused$/)).not.toBeInTheDocument();
  });

  it("shows a non-NCBI fallback address as plain text, never as a link", () => {
    /*
     * `production-standards` requires a HOST pin rather than a scheme
     * check, on the side of the stack that builds the link. Mutation:
     * replacing `isLinkableRefusalLink` with a `startsWith("https://")`
     * test turns this red, because the lookalike host would then render as
     * an anchor.
     *
     * Hand-built props here on purpose: `useRunView` passes
     * `fallback_link` through unchanged, exactly as the wire delivers it,
     * so the component is the only place this can be caught.
     */
    const hostile = "https://ncbi.nlm.nih.gov.evil.example/search/all/?term=BRCA9";
    render(
      <AnswerScreen
        question="Is BRCA9 associated with any disease?"
        claims={[]}
        sources={[]}
        refusal={REFUSE_MESSAGE}
        refusalLabel="No answer found in NCBI records"
        refusalLink={hostile}
      />,
    );

    const block = screen.getByTestId("answer-refusal");
    // The address is still SHOWN: hiding it would lose the one thing the
    // refusal was trying to hand the reader.
    expect(block).toHaveTextContent(hostile);
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });

  it("pins the host rule itself, subdomains included", () => {
    // Mutation: dropping either clause of the host check turns one of
    // these red. The `.ncbi.nlm.nih.gov` suffix form is what makes the
    // lookalike above fail while a real subdomain passes.
    expect(isLinkableRefusalLink("https://www.ncbi.nlm.nih.gov/search/all/?term=BRCA9")).toBe(true);
    expect(isLinkableRefusalLink("https://ncbi.nlm.nih.gov/gene")).toBe(true);
    expect(isLinkableRefusalLink("https://pubmed.ncbi.nlm.nih.gov/123/")).toBe(true);
    expect(isLinkableRefusalLink("http://www.ncbi.nlm.nih.gov/search")).toBe(false);
    expect(isLinkableRefusalLink("https://ncbi.nlm.nih.gov.evil.example/x")).toBe(false);
    expect(isLinkableRefusalLink("https://xncbi.nlm.nih.gov/x")).toBe(false);
    expect(isLinkableRefusalLink("javascript:alert(1)")).toBe(false);
    expect(isLinkableRefusalLink("not a url at all")).toBe(false);
  });

  it("keeps the red not-verified pill when the run DIED", () => {
    /*
     * F-4.9-A-01's control, from the other side. A fatal run is a failure,
     * not a refusal, so it keeps its red pill and its red failure notice.
     * Mutation: widening R13's silencing to cover the fatal path turns
     * this red, which is the regression that would reopen a closed
     * critical.
     */
    const view = viewFor([
      envelope("guard", { passed: true, category: "ok", reason: null }),
      envelope("trust_signal", {
        outcome: "answer",
        risk_tier: "low",
        grounded: true,
        triangulated: null,
        scope: "answer",
      }),
      envelope("error", {
        fatal: true,
        scope: "run",
        source: "write_node",
        error_class: "unexpected",
        message: "synth tier failed after $0.019 of $0.02 spent",
        retry_after_s: 0,
      }),
    ]);
    renderWithView(view, "Which diseases are associated with BRCA1?");

    expect(screen.getByTestId("trust-risk")).toHaveTextContent(
      "Not verified · the run did not finish",
    );
    // And the run's failure is still an error box, not a calm grey block.
    expect(screen.getByTestId("answer-failure")).toBeInTheDocument();
    expect(screen.queryByTestId("answer-refusal")).not.toBeInTheDocument();
    // The positive verdict the run emitted before dying must not survive.
    expect(screen.queryByTestId("trust-good")).not.toBeInTheDocument();
  });
});
