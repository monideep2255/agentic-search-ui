/**
 * Build phase 6.2, T-6.2-05: the wait shows continuous progress.
 *
 * Complaint 2 in `UI_feedback.md`, measured rather than described: the run
 * takes 12 to 14 seconds and the sequence a user experiences is a gap, some
 * tool chips, another gap of several seconds, then the answer all at once.
 * The stepper named the live step and the tool chips coloured themselves,
 * and NEITHER MOVED, so across a five-second gap the page was
 * indistinguishable from one that had died.
 *
 * The acceptance criterion is "no interval longer than two seconds in which
 * the interface shows no sign of progress". These arms hold the component to
 * the version of that a unit test can actually decide: there exists an
 * element that changes on its own, once a second, for as long as the run is
 * in flight, and it stops when the run does.
 *
 * WHAT THESE ARMS DO NOT COVER, stated because a green run here is not the
 * whole criterion: they cannot see whether the change is VISIBLE, and they
 * cannot see the pulse, which is CSS. T-6.2-11's journey 2 captures the wait
 * as a per-second filmstrip, which is the arm that shows a human what a
 * human would see. This file pins the mechanism; that one pins the
 * experience.
 */

import { render, screen, act } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { RunScreen } from "./RunScreen";

describe("run screen progress during the wait", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  function advance(seconds: number) {
    act(() => {
      vi.advanceTimersByTime(seconds * 1000);
    });
  }

  it("shows an elapsed counter that advances every second while running", () => {
    render(
      <RunScreen
        question="Which diseases are associated with BRCA1?"
        activeStep="Act"
        startedAt={Date.now()}
      />,
    );

    const elapsed = () => screen.getByTestId("run-elapsed").textContent;

    expect(elapsed()).toBe("0s");
    advance(1);
    expect(elapsed()).toBe("1s");
    advance(1);
    expect(elapsed()).toBe("2s");

    // The real complaint is about the several-second gap between step
    // transitions, so the arm walks through one without touching any other
    // prop. Nothing about the run changes here except time passing, which
    // is exactly the situation in which the old screen went still.
    for (let second = 3; second <= 14; second += 1) {
      advance(1);
      expect(elapsed()).toBe(`${second}s`);
    }
  });

  it("never leaves more than two seconds without the display changing", () => {
    // The criterion stated directly rather than inferred from the arm above.
    // Written as its own arm because the one above would still pass if the
    // counter ticked once every ten seconds: it only ever advances a second
    // at a time and asserts after each.
    render(
      <RunScreen question="q" activeStep="Plan" startedAt={Date.now()} />,
    );

    let previous = screen.getByTestId("run-elapsed").textContent;
    let longestUnchangedSeconds = 0;
    let unchangedRun = 0;

    for (let second = 0; second < 20; second += 1) {
      advance(1);
      const current = screen.getByTestId("run-elapsed").textContent;
      unchangedRun = current === previous ? unchangedRun + 1 : 0;
      longestUnchangedSeconds = Math.max(longestUnchangedSeconds, unchangedRun);
      previous = current;
    }

    expect(
      longestUnchangedSeconds,
      "the interface went this many consecutive seconds without any visible " +
        "change, which is the complaint this ticket exists to fix",
    ).toBeLessThanOrEqual(2);
  });

  it("stops counting when the run is no longer in flight", () => {
    // A counter still running after the answer landed asserts work that is
    // not happening, which is the same class of lie as a progress bar that
    // never completes.
    const { rerender } = render(
      <RunScreen question="q" activeStep="Write" startedAt={Date.now()} />,
    );
    advance(3);
    expect(screen.getByTestId("run-elapsed").textContent).toBe("3s");

    rerender(<RunScreen question="q" activeStep={null} startedAt={null} />);
    expect(screen.queryByTestId("run-elapsed")).toBeNull();
  });

  it("announces the step rather than the ticking number", () => {
    // The accessibility half, and the reason the counter is aria-hidden. A
    // number changing every second inside a live region would be read out
    // for the whole run and would bury the step transitions that carry the
    // meaning.
    render(
      <RunScreen question="q" activeStep="Act" startedAt={Date.now()} />,
    );

    expect(screen.getByTestId("run-elapsed")).toHaveAttribute(
      "aria-hidden",
      "true",
    );

    const announcement = screen.getByTestId("run-step-announcement");
    expect(announcement).toHaveAttribute("aria-live", "polite");
    expect(announcement.textContent).toBe("Act step running");
  });

  it("says nothing to a screen reader once the run has landed", () => {
    render(<RunScreen question="q" activeStep={null} startedAt={null} />);
    expect(screen.getByTestId("run-step-announcement").textContent).toBe("");
  });
});
