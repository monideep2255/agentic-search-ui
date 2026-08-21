/**
 * T-4.6-09: the feedback surface wired to `POST /v1/query/{run_id}/feedback`.
 *
 * `postFeedback` is mocked at the module level (the same tool
 * `StopButton.test.tsx` uses for the same reason: this component calls it
 * directly, and these tests need precise control over exactly when and how
 * that call's promise resolves or rejects, including the 409 race). The
 * real `FeedbackNotYetCapturedError` class is kept (`...actual`, not a
 * hand-rolled stand-in), so the component's `instanceof` check under test is
 * the real one, not a mock that happens to look right.
 *
 * Every test below states, in a comment, the mutation it is proven to catch.
 */

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../lib/api")>("../../lib/api");
  return {
    ...actual,
    postFeedback: vi.fn(),
  };
});

import { FeedbackNotYetCapturedError, postFeedback } from "../../lib/api";
import { FeedbackSurface } from "./FeedbackSurface";

const postFeedbackMock = vi.mocked(postFeedback);

describe("FeedbackSurface", () => {
  beforeEach(() => {
    postFeedbackMock.mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("does not offer Send until a rating or a citation flag exists", () => {
    // Mutation: dropping the `canSend` guard (rendering Send unconditionally)
    // turns this red, since the button would exist with no rating chosen.
    render(<FeedbackSurface runId="run-1" authToken="token-1" />);
    expect(screen.getByRole("button", { name: /^helpful$/i })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^send feedback$/i })).not.toBeInTheDocument();
  });

  it("shows reason chips and a comment field only after a down vote", async () => {
    // Mutation: removing the `rating === "down"` gate turns this red, since
    // the chips would render immediately for an up vote too.
    const user = userEvent.setup();
    render(<FeedbackSurface runId="run-1" authToken="token-1" />);

    expect(screen.queryByText(/wrong answer/i)).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /^helpful$/i }));
    expect(screen.queryByText(/wrong answer/i)).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /not helpful/i }));
    expect(screen.getByText(/wrong answer/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/what went wrong/i)).toBeInTheDocument();
  });

  it("sends the full payload: rating, joined reasons, trimmed comment, run id and token", async () => {
    // Mutation: sending `reasons` as an array instead of `reasons.join("; ")`,
    // or forwarding the untrimmed comment, or swapping the run id and token
    // arguments, each turn this red.
    const user = userEvent.setup();
    postFeedbackMock.mockResolvedValueOnce(undefined);
    render(<FeedbackSurface runId="run-42" authToken="guest-token-1" />);

    await user.click(screen.getByRole("button", { name: /not helpful/i }));
    await user.click(screen.getByRole("button", { name: /wrong answer/i }));
    await user.click(screen.getByRole("button", { name: /too slow/i }));
    await user.type(screen.getByLabelText(/what went wrong/i), "  cited the wrong gene  ");
    await user.click(screen.getByRole("button", { name: /^send feedback$/i }));

    await waitFor(() => expect(postFeedbackMock).toHaveBeenCalledTimes(1));
    expect(postFeedbackMock).toHaveBeenCalledWith(
      "run-42",
      {
        rating: "down",
        comment: "cited the wrong gene",
        flagged_reason: "Wrong answer; Too slow",
        citation_flags: [],
      },
      "guest-token-1",
    );
  });

  it("works the same for a guest token as for a real access token", async () => {
    // Mutation: a change that special-cases or rejects a non-JWT-shaped
    // token turns this red, since a guest token is an opaque string with no
    // particular shape.
    const user = userEvent.setup();
    postFeedbackMock.mockResolvedValueOnce(undefined);
    render(<FeedbackSurface runId="run-1" authToken="guest-only-token" />);

    await user.click(screen.getByRole("button", { name: /^helpful$/i }));
    await user.click(screen.getByRole("button", { name: /^send feedback$/i }));

    await waitFor(() => expect(postFeedbackMock).toHaveBeenCalledTimes(1));
    expect(postFeedbackMock).toHaveBeenCalledWith(
      "run-1",
      expect.objectContaining({ rating: "up" }),
      "guest-only-token",
    );
  });

  it("includes every currently flagged citation, using the display index as the id", async () => {
    // Mutation: mapping citation_flags from an empty array instead of the
    // `flaggedSources` prop, or dropping the `reason` field, turns this red.
    const user = userEvent.setup();
    postFeedbackMock.mockResolvedValueOnce(undefined);
    render(<FeedbackSurface runId="run-1" authToken="token-1" flaggedSources={[1, 3]} />);

    // No rating chosen at all: a flagged citation alone is enough to send.
    await user.click(screen.getByRole("button", { name: /^send feedback$/i }));

    await waitFor(() => expect(postFeedbackMock).toHaveBeenCalledTimes(1));
    expect(postFeedbackMock).toHaveBeenCalledWith(
      "run-1",
      expect.objectContaining({
        rating: null,
        citation_flags: [
          { citation_id: "1", reason: "Citation does not support the claim" },
          { citation_id: "3", reason: "Citation does not support the claim" },
        ],
      }),
      "token-1",
    );
  });

  it("shows a thank-you message on success", async () => {
    // Mutation: rendering the thank-you unconditionally (not gated on
    // status === "sent") turns this red at the FIRST assertion, since the
    // message would already be present before Send is even clicked.
    const user = userEvent.setup();
    postFeedbackMock.mockResolvedValueOnce(undefined);
    render(<FeedbackSurface runId="run-1" authToken="token-1" />);

    expect(screen.queryByText(/thanks/i)).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /^helpful$/i }));
    await user.click(screen.getByRole("button", { name: /^send feedback$/i }));

    expect(await screen.findByText(/thanks/i)).toBeInTheDocument();
    expect(screen.getByText(/thanks/i)).toHaveAttribute("role", "status");
  });

  it("does not send anything on Skip, and hides the panel", async () => {
    // Mutation: wiring Skip's onClick to `send` instead of `setDismissed`
    // (the original stub's actual bug) turns this red, since postFeedback
    // would be called.
    const user = userEvent.setup();
    render(<FeedbackSurface runId="run-1" authToken="token-1" />);

    await user.click(screen.getByRole("button", { name: /^helpful$/i }));
    await user.click(screen.getByRole("button", { name: /^skip$/i }));

    expect(postFeedbackMock).not.toHaveBeenCalled();
    expect(screen.queryByTestId("feedback")).not.toBeInTheDocument();
  });

  it("shows a 'still finishing up' status on the not-yet-captured race, distinct from an ordinary error", async () => {
    // Mutation: routing FeedbackNotYetCapturedError through the same
    // `setStatus("error")` branch as any other failure turns this red,
    // since the status region would read the generic error copy (or not
    // render at all, if the branch is dropped outright) instead of this
    // race-specific one. `retryAfterS` is large (60s) so the scheduled
    // retry cannot fire during this test and race the assertion below.
    const user = userEvent.setup();
    postFeedbackMock.mockRejectedValueOnce(new FeedbackNotYetCapturedError(60));
    render(<FeedbackSurface runId="run-1" authToken="token-1" />);

    await user.click(screen.getByRole("button", { name: /^helpful$/i }));
    await user.click(screen.getByRole("button", { name: /^send feedback$/i }));

    await waitFor(() => expect(postFeedbackMock).toHaveBeenCalledTimes(1));
    const status = screen.getByTestId("feedback-status");
    expect(status).toHaveTextContent(/still finishing up/i);
    expect(status).toHaveAttribute("role", "status");
    expect(screen.queryByText(/thanks/i)).not.toBeInTheDocument();
  });

  it("retries automatically on the not-yet-captured race, then succeeds, without losing the rating", async () => {
    // Mutation: treating FeedbackNotYetCapturedError as an ordinary failure
    // (skipping the retry branch) turns this red, since only one call would
    // ever fire and the panel would land on the generic error message
    // instead of eventually sending.
    const user = userEvent.setup();
    postFeedbackMock
      .mockRejectedValueOnce(new FeedbackNotYetCapturedError(0))
      .mockResolvedValueOnce(undefined);
    render(<FeedbackSurface runId="run-1" authToken="token-1" />);

    await user.click(screen.getByRole("button", { name: /^helpful$/i }));
    await user.click(screen.getByRole("button", { name: /^send feedback$/i }));

    expect(await screen.findByText(/thanks/i)).toBeInTheDocument();
    expect(postFeedbackMock).toHaveBeenCalledTimes(2);
    // The retried call carries the SAME rating as the first, proving the
    // payload was rebuilt from the surface's own state rather than replayed
    // as a stale closure that could have gone missing.
    expect(postFeedbackMock).toHaveBeenNthCalledWith(
      2,
      "run-1",
      expect.objectContaining({ rating: "up" }),
      "token-1",
    );
  });

  it("gives up after the bounded number of not-yet-captured retries and offers a manual retry", async () => {
    // Mutation: removing the `MAX_NOT_YET_CAPTURED_RETRIES` bound (retrying
    // forever) turns this red, since the awaited alert would never appear;
    // raising or lowering the bound changes the exact call count asserted.
    const user = userEvent.setup();
    postFeedbackMock.mockRejectedValue(new FeedbackNotYetCapturedError(0));
    render(<FeedbackSurface runId="run-1" authToken="token-1" />);

    await user.click(screen.getByRole("button", { name: /^helpful$/i }));
    await user.click(screen.getByRole("button", { name: /^send feedback$/i }));

    const alert = await screen.findByRole("alert", undefined, { timeout: 3000 });
    expect(alert).toHaveTextContent(/still saving/i);
    // One initial attempt plus MAX_NOT_YET_CAPTURED_RETRIES (3) retries.
    expect(postFeedbackMock).toHaveBeenCalledTimes(4);
    expect(screen.getByRole("button", { name: /^retry$/i })).toBeInTheDocument();
  });

  it("shows a visible, actionable error on an ordinary failure, and Retry sends again", async () => {
    // Mutation: swallowing the error (no setStatus("error") call) turns this
    // red at the first assertion; wiring Retry to a no-op instead of `send`
    // turns it red at the second postFeedback call count.
    const user = userEvent.setup();
    postFeedbackMock
      .mockRejectedValueOnce(new Error("network down"))
      .mockResolvedValueOnce(undefined);
    render(<FeedbackSurface runId="run-1" authToken="token-1" />);

    await user.click(screen.getByRole("button", { name: /^helpful$/i }));
    await user.click(screen.getByRole("button", { name: /^send feedback$/i }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/could not send your feedback/i);
    expect(screen.queryByText(/thanks/i)).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /^retry$/i }));
    expect(await screen.findByText(/thanks/i)).toBeInTheDocument();
    expect(postFeedbackMock).toHaveBeenCalledTimes(2);
  });

  it("fails visibly, without calling postFeedback, when the run id or token is missing", async () => {
    // Mutation: dropping the `runId === null || authToken === null` guard
    // (calling postFeedback with a null runId) turns this red, since
    // postFeedback would be invoked with a malformed URL argument.
    const user = userEvent.setup();
    render(<FeedbackSurface runId={null} authToken={null} />);

    await user.click(screen.getByRole("button", { name: /^helpful$/i }));
    await user.click(screen.getByRole("button", { name: /^send feedback$/i }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/feedback is not available/i);
    expect(postFeedbackMock).not.toHaveBeenCalled();
  });

  it("is keyboard-operable: Tab reaches the thumbs and Enter activates them", async () => {
    // Mutation: rendering the thumb as a non-interactive element (e.g. a
    // plain <span> with an onClick) turns this red, since it would never
    // receive focus via Tab.
    const user = userEvent.setup();
    render(<FeedbackSurface runId="run-1" authToken="token-1" />);

    await user.tab();
    expect(screen.getByRole("button", { name: /^helpful$/i })).toHaveFocus();
    await user.keyboard("{Enter}");
    expect(screen.getByRole("button", { name: /^helpful$/i })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });
});
