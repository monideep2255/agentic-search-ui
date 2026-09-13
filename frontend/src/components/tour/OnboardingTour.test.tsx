/**
 * The onboarding tour (2026-09-13 product-owner request).
 *
 * Pins, stated so the gap is arguable:
 *   - the nine steps render in order, each with its "Step n of 9" counter
 *   - Next, Back, Skip tour and Escape do what they say
 *   - focus lands in the card when it opens
 *   - step 7 offers "Run it for me" and no Next; the tour waits for the run
 *   - a run that lands while step 7 shows advances to step 8 on its own,
 *     and a run that starts earlier jumps the tour to step 7
 *   - the refusal branch's wording and its Done
 *   - through `App`: the invite shows only while the per-browser flag is
 *     unset, "Not now" hides it and writes the flag, and "Take the tour"
 *     in the footer strip opens the tour with or without the invite
 *
 * Not covered here: the highlight ring's geometry. jsdom measures every
 * element at zero, so the ring is never drawn under vitest; the screenshots
 * taken for this change are the evidence for that half.
 */

import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useState } from "react";

import App from "../../App";
import {
  OnboardingTour,
  RUN_STEP_INDEX,
  TOUR_SEEN_KEY,
  TOUR_STEP_COUNT,
  TOUR_STEPS,
  hasSeenTour,
  markTourSeen,
} from "./OnboardingTour";
import type { TourOutcome, TourRunState } from "./OnboardingTour";
import { DISCLAIMER_KEY } from "../shell/DisclaimerModal";

vi.mock("../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../lib/api")>("../../lib/api");
  return {
    ApiError: actual.ApiError,
    fetchPersona: vi.fn(async () => ({ persona_name: "Mendel" })),
    fetchMe: vi.fn(async () => ({
      id: "u-1",
      email: "a@example.com",
      audience_depth: "researcher",
      persona_name: "Mendel",
    })),
    login: vi.fn(),
    signup: vi.fn(),
    createRun: vi.fn(),
    openEventStream: vi.fn(() => new Promise(() => {})),
    stopRun: vi.fn(),
    mintGuest: vi.fn(async () => ({
      guest_token: "guest-token-1",
      guest_id: "guest-1",
      used: 0,
      total: 5,
    })),
    getAllowance: vi.fn(async () => ({ kind: "user", used: 0, total: 100, counted: false })),
    fetchHistory: vi.fn(async () => ({ items: [], count: 0 })),
    refreshSession: vi.fn(),
    logoutSession: vi.fn(async () => ({ status: "ok" })),
  };
});

/** Holds the step the way `App` does, so Next and Back have something to move. */
function Harness({
  runState = "idle",
  outcome = null,
  onClose = () => undefined,
  onRunForMe = () => undefined,
  onStepChange,
  initialStep = 0,
}: {
  runState?: TourRunState;
  outcome?: TourOutcome | null;
  onClose?: () => void;
  onRunForMe?: () => void;
  onStepChange?: (step: number) => void;
  initialStep?: number;
}) {
  const [step, setStep] = useState(initialStep);
  return (
    <>
      <button type="button">Before the tour</button>
      <div data-tour="search-box">the search box</div>
      <OnboardingTour
        open
        step={step}
        onStepChange={(next) => {
          onStepChange?.(next);
          setStep(next);
        }}
        onClose={onClose}
        runState={runState}
        outcome={outcome}
        onRunForMe={onRunForMe}
      />
    </>
  );
}

const dialog = () => screen.getByRole("dialog");

describe("OnboardingTour", () => {
  it("renders the nine steps in order, each with its counter", async () => {
    const user = userEvent.setup();
    render(<Harness />);

    for (let index = 0; index < RUN_STEP_INDEX; index += 1) {
      expect(within(dialog()).getByRole("heading", { name: TOUR_STEPS[index].title })).toBeVisible();
      expect(dialog()).toHaveTextContent(`Step ${index + 1} of ${TOUR_STEP_COUNT}`);
      await user.click(within(dialog()).getByRole("button", { name: "Next" }));
    }

    // Step 7 runs a question rather than offering Next.
    expect(within(dialog()).getByRole("heading", { name: "Now run one" })).toBeVisible();
    expect(dialog()).toHaveTextContent(`Step ${RUN_STEP_INDEX + 1} of ${TOUR_STEP_COUNT}`);
    expect(within(dialog()).queryByRole("button", { name: "Next" })).toBeNull();
    expect(within(dialog()).getByRole("button", { name: "Run it for me" })).toBeVisible();
    expect(TOUR_STEP_COUNT).toBe(9);
  });

  it("Back returns to the previous step and is absent on the first", async () => {
    const user = userEvent.setup();
    render(<Harness />);

    expect(within(dialog()).queryByRole("button", { name: "Back" })).toBeNull();
    await user.click(within(dialog()).getByRole("button", { name: "Next" }));
    expect(dialog()).toHaveTextContent("Step 2 of 9");
    await user.click(within(dialog()).getByRole("button", { name: "Back" }));
    expect(dialog()).toHaveTextContent("Step 1 of 9");
  });

  it("Skip tour and Escape both close it", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(<Harness onClose={onClose} />);

    await user.click(within(dialog()).getByRole("button", { name: "Skip tour" }));
    expect(onClose).toHaveBeenCalledTimes(1);

    await user.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalledTimes(2);
  });

  it("moves focus into the card on open, and the arrow keys step", async () => {
    const user = userEvent.setup();
    render(<Harness />);

    expect(dialog()).toHaveAttribute("aria-labelledby");
    expect(dialog().contains(document.activeElement)).toBe(true);

    await user.keyboard("{ArrowRight}");
    expect(dialog()).toHaveTextContent("Step 2 of 9");
    await user.keyboard("{ArrowLeft}");
    expect(dialog()).toHaveTextContent("Step 1 of 9");
  });

  it("'Run it for me' calls the handler, and a running run shows the watching note", async () => {
    const user = userEvent.setup();
    const onRunForMe = vi.fn();
    const { rerender } = render(
      <Harness initialStep={RUN_STEP_INDEX} onRunForMe={onRunForMe} />,
    );

    await user.click(within(dialog()).getByRole("button", { name: "Run it for me" }));
    expect(onRunForMe).toHaveBeenCalledTimes(1);

    rerender(<Harness initialStep={RUN_STEP_INDEX} onRunForMe={onRunForMe} runState="running" />);
    expect(screen.queryByRole("dialog")).toBeNull();
    const note = screen.getByTestId("tour-watching");
    expect(note).toHaveTextContent(/watching the five steps/i);
    expect(within(note).getByRole("button", { name: "Skip tour" })).toBeVisible();
  });

  it("advances to step 8 when the answer lands on step 7", async () => {
    const onStepChange = vi.fn();
    render(<Harness initialStep={RUN_STEP_INDEX} runState="answered" outcome="answer" onStepChange={onStepChange} />);

    await waitFor(() => expect(onStepChange).toHaveBeenCalledWith(RUN_STEP_INDEX + 1));
    expect(within(dialog()).getByRole("heading", { name: "Citations" })).toBeVisible();
    // Back is not offered once the run has happened: there is no "run one"
    // to go back to.
    expect(within(dialog()).queryByRole("button", { name: "Back" })).toBeNull();
  });

  it("jumps to step 7 when a run starts before the tour reached it", async () => {
    const onStepChange = vi.fn();
    render(<Harness initialStep={2} runState="running" onStepChange={onStepChange} />);
    await waitFor(() => expect(onStepChange).toHaveBeenCalledWith(RUN_STEP_INDEX));
  });

  it("ends on step 9 with Done", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(<Harness initialStep={RUN_STEP_INDEX + 1} runState="answered" outcome="answer" onClose={onClose} />);

    await user.click(within(dialog()).getByRole("button", { name: "Next" }));
    expect(dialog()).toHaveTextContent("Step 9 of 9");
    expect(within(dialog()).getByRole("heading", { name: "Sources and follow-up" })).toBeVisible();
    expect(within(dialog()).queryByRole("button", { name: "Next" })).toBeNull();
    expect(within(dialog()).queryByRole("button", { name: "Skip tour" })).toBeNull();
    await user.click(within(dialog()).getByRole("button", { name: "Done" }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("says so, and ends, when the run refused", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(<Harness initialStep={RUN_STEP_INDEX + 1} runState="answered" outcome="refusal" onClose={onClose} />);

    expect(dialog()).toHaveTextContent(
      "This time the system refused rather than guess; that is by design.",
    );
    expect(dialog()).toHaveTextContent(/run it again from the home page/i);
    expect(within(dialog()).queryByRole("button", { name: "Next" })).toBeNull();
    await user.click(within(dialog()).getByRole("button", { name: "Done" }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("renders nothing when closed", () => {
    render(
      <OnboardingTour
        open={false}
        step={0}
        onStepChange={() => undefined}
        onClose={() => undefined}
        runState="idle"
        outcome={null}
      />,
    );
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(screen.queryByTestId("tour-backdrop")).toBeNull();
  });
});

describe("the seen flag", () => {
  beforeEach(() => window.localStorage.clear());

  it("is unset until marked, then set", () => {
    expect(hasSeenTour()).toBe(false);
    markTourSeen();
    expect(hasSeenTour()).toBe(true);
    expect(window.localStorage.getItem(TOUR_SEEN_KEY)).toBe("1");
  });
});

describe("the invite, through App", () => {
  beforeEach(() => {
    window.localStorage.clear();
    // The tour renders only once the disclaimer is accepted, and the modal
    // is session-scoped, so this is the state a visitor is in on the home
    // screen after the one click the modal asks for.
    window.sessionStorage.setItem(DISCLAIMER_KEY, "true");
  });

  it("shows the invite to a first-time visitor and hides it after 'Not now', for good", async () => {
    const user = userEvent.setup();
    render(<App />);

    const invite = screen.getByTestId("tour-invite");
    expect(within(invite).getByRole("button", { name: "Start the tour" })).toBeVisible();
    await user.click(within(invite).getByRole("button", { name: "Not now" }));

    expect(screen.queryByTestId("tour-invite")).toBeNull();
    expect(window.localStorage.getItem(TOUR_SEEN_KEY)).toBe("1");
  });

  it("does not show the invite once the flag is set", () => {
    markTourSeen();
    render(<App />);
    expect(screen.queryByTestId("tour-invite")).toBeNull();
    // The footer link is what remains.
    expect(screen.getByRole("button", { name: "Take the tour" })).toBeVisible();
  });

  it("'Start the tour' opens step 1 and hides the invite while the tour is up", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("button", { name: "Start the tour" }));
    expect(within(dialog()).getByRole("heading", { name: /welcome/i })).toBeVisible();
    expect(dialog()).toHaveTextContent("Step 1 of 9");
    expect(screen.queryByTestId("tour-invite")).toBeNull();
  });

  it("'Take the tour' reopens it after it was skipped, and finishing marks it seen", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("button", { name: "Start the tour" }));
    await user.click(within(dialog()).getByRole("button", { name: "Skip tour" }));
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(window.localStorage.getItem(TOUR_SEEN_KEY)).toBe("1");
    expect(screen.queryByTestId("tour-invite")).toBeNull();

    await user.click(screen.getByRole("button", { name: "Take the tour" }));
    expect(dialog()).toHaveTextContent("Step 1 of 9");
    await act(async () => {
      await user.keyboard("{Escape}");
    });
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("step 7 fills the empty question box with the tour's question", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("button", { name: "Start the tour" }));
    for (let index = 0; index < RUN_STEP_INDEX; index += 1) {
      await user.click(within(dialog()).getByRole("button", { name: "Next" }));
    }
    expect(within(dialog()).getByRole("heading", { name: "Now run one" })).toBeVisible();
    expect(
      within(screen.getByRole("main")).getByRole("textbox", { name: /question/i }),
    ).toHaveValue("Which diseases are associated with BRCA1?");
  });
});
