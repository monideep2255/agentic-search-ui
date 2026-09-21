/**
 * Fix set 3, item 3.4: decision U7, requirement R45 (`DECISIONS.md` row
 * 2026-09-12).
 *
 * Pressing Stop on the run screen aborted the stream and latched `stopped`
 * in `App.tsx`, which nulled the active step and the elapsed counter and
 * left every stepper node reading "pending". Nothing on screen said the run
 * had stopped, or offered a way to do anything about it.
 *
 * These arms pin the replacement: a "Search stopped" block with "Run again"
 * and "New search" buttons, the stepper and the reasoning/tool-call area
 * gone while it shows, and exactly one "New search" button on the page so
 * the strict-mode `getByRole` lookup the browser specs use still resolves.
 *
 * WHAT THESE ARMS DO NOT COVER: the server-side proof that Stop actually
 * halted the run, which lives in `frontend/e2e/query-stream-and-stop.spec.ts`
 * against a live backend. This file pins the component's own rendering only.
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { RunScreen } from "./RunScreen";

describe("run screen after Stop", () => {
  it("shows the stopped block with exactly one Run again and one New search button, and no Stop", () => {
    render(
      <RunScreen
        question="Which diseases are associated with BRCA1?"
        activeStep={null}
        startedAt={null}
        stopped
        stopEnabled={false}
      />,
    );

    const stopped = screen.getByTestId("run-stopped");
    expect(stopped).toHaveTextContent("Search stopped");

    // The stepper and the reasoning/tool-call area are gone, not merely
    // covered: a frozen stepper underneath the stopped block would still
    // read as an unfinished run to anything that queries for it.
    for (const step of ["Guard", "Think", "Plan", "Act", "Write"]) {
      expect(screen.queryByTestId(`step-${step}`)).toBeNull();
    }

    expect(
      screen.getByRole("button", { name: "New search" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Run again" }),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Stop" })).toBeNull();
  });

  it("calls onRunAgain once from Run again and onNewSearch once from New search", async () => {
    const onRunAgain = vi.fn();
    const onNewSearch = vi.fn();
    const user = userEvent.setup();

    render(
      <RunScreen
        question="q"
        activeStep={null}
        startedAt={null}
        stopped
        onRunAgain={onRunAgain}
        onNewSearch={onNewSearch}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Run again" }));
    await user.click(screen.getByRole("button", { name: "New search" }));

    expect(onRunAgain).toHaveBeenCalledTimes(1);
    expect(onNewSearch).toHaveBeenCalledTimes(1);
  });

  it("renders no stopped block, and keeps Stop, when stopped is false", () => {
    render(
      <RunScreen question="q" activeStep="Act" startedAt={Date.now()} stopped={false} />,
    );

    expect(screen.queryByTestId("run-stopped")).toBeNull();
    expect(screen.getByRole("button", { name: "Stop" })).toBeInTheDocument();
    expect(screen.getByTestId("step-Guard")).toBeInTheDocument();
  });
});
