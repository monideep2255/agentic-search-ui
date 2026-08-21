/**
 * T-4.6-09: `AnswerScreen` builds `FeedbackSurface` itself now, rather than
 * rendering an opaque `feedback` node, specifically so it can pass the real
 * `runId`, `authToken` and `flaggedSources`. This file pins that wiring: not
 * `FeedbackSurface`'s own behaviour (covered by
 * `components/feedback/FeedbackSurface.test.tsx`), but that `AnswerScreen`
 * actually forwards its own props down rather than dropping them or wiring
 * them to the wrong field.
 *
 * `postFeedback` is mocked at the module level, the same tool
 * `FeedbackSurface.test.tsx` uses, with the real `ApiError`/
 * `FeedbackNotYetCapturedError` classes kept via `...actual`.
 *
 * Every test states, in a comment, the mutation it is proven to catch.
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../lib/api")>("../../lib/api");
  return {
    ...actual,
    postFeedback: vi.fn(),
  };
});

import { postFeedback } from "../../lib/api";
import { AnswerScreen } from "./AnswerScreen";
import type { Claim, Source } from "./AnswerScreen";

const postFeedbackMock = vi.mocked(postFeedback);

const SOURCE: Source = {
  n: 1,
  layer: 1,
  name: "NCBI Gene 672",
  tool: "cypher_query",
  evidence: "curated assertion",
  confidence: "high",
  license: "public domain",
  url: "https://www.ncbi.nlm.nih.gov/gene/672",
};

const CLAIM: Claim = { text: "BRCA1 is associated with HBOC.", layer: 1, citations: [1] };

describe("AnswerScreen wires runId, authToken and flaggedSources into FeedbackSurface", () => {
  beforeEach(() => {
    postFeedbackMock.mockReset();
    postFeedbackMock.mockResolvedValue(undefined);
  });

  it("passes its own runId and authToken through to the feedback POST", async () => {
    // Mutation: forwarding a hardcoded or swapped runId/authToken (or
    // omitting them) turns this red, since postFeedback would be called
    // with different arguments than the ones this test passes in.
    const user = userEvent.setup();
    render(
      <AnswerScreen
        question="Which diseases are associated with BRCA1?"
        claims={[CLAIM]}
        sources={[SOURCE]}
        runId="run-answer-9"
        authToken="token-answer-9"
      />,
    );

    await user.click(screen.getByRole("button", { name: /^helpful$/i }));
    await user.click(screen.getByRole("button", { name: /^send feedback$/i }));

    await vi.waitFor(() => expect(postFeedbackMock).toHaveBeenCalledTimes(1));
    expect(postFeedbackMock).toHaveBeenCalledWith(
      "run-answer-9",
      expect.objectContaining({ rating: "up" }),
      "token-answer-9",
    );
  });

  it("forwards flaggedSources into the feedback surface's citation_flags", async () => {
    // Mutation: not passing `flaggedSources` down to `FeedbackSurface` (or
    // passing an empty array regardless of the prop) turns this red, since
    // the sent payload's citation_flags would be empty even though a
    // source was flagged.
    const user = userEvent.setup();
    render(
      <AnswerScreen
        question="Which diseases are associated with BRCA1?"
        claims={[CLAIM]}
        sources={[SOURCE]}
        runId="run-1"
        authToken="token-1"
        flaggedSources={[1]}
      />,
    );

    // No rating needed: a flagged citation alone is enough to send.
    await user.click(screen.getByRole("button", { name: /^send feedback$/i }));

    await vi.waitFor(() => expect(postFeedbackMock).toHaveBeenCalledTimes(1));
    expect(postFeedbackMock).toHaveBeenCalledWith(
      "run-1",
      expect.objectContaining({
        citation_flags: [{ citation_id: "1", reason: "Citation does not support the claim" }],
      }),
      "token-1",
    );
  });

  it("still renders the feedback prompt, and degrades visibly, when runId/authToken are not yet supplied", async () => {
    // Mutation: requiring `runId`/`authToken` (dropping their optionality)
    // turns this red at the render call itself, a TypeScript failure this
    // runtime test cannot directly assert but which `npx tsc --noEmit`
    // gates; at the behavioural level, a mutation that skips the "not
    // available" guard would instead call postFeedback with a null runId.
    const user = userEvent.setup();
    render(
      <AnswerScreen
        question="Which diseases are associated with BRCA1?"
        claims={[CLAIM]}
        sources={[SOURCE]}
      />,
    );

    expect(screen.getByTestId("feedback")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /^helpful$/i }));
    await user.click(screen.getByRole("button", { name: /^send feedback$/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/feedback is not available/i);
    expect(postFeedbackMock).not.toHaveBeenCalled();
  });

  it("remounts the feedback surface, clearing any prior rating, when the question changes", async () => {
    // Mutation: dropping `key={question}` on the rendered FeedbackSurface
    // turns this red, since React would reuse the same component instance
    // across questions and the second question would still show the first
    // question's chosen rating as pressed.
    const user = userEvent.setup();
    const { rerender } = render(
      <AnswerScreen
        question="First question?"
        claims={[CLAIM]}
        sources={[SOURCE]}
        runId="run-1"
        authToken="token-1"
      />,
    );
    await user.click(screen.getByRole("button", { name: /^helpful$/i }));
    expect(screen.getByRole("button", { name: /^helpful$/i })).toHaveAttribute(
      "aria-pressed",
      "true",
    );

    rerender(
      <AnswerScreen
        question="Second question?"
        claims={[CLAIM]}
        sources={[SOURCE]}
        runId="run-2"
        authToken="token-1"
      />,
    );
    expect(screen.getByRole("button", { name: /^helpful$/i })).toHaveAttribute(
      "aria-pressed",
      "false",
    );
  });
});
