import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { AgentEvent, ErrorPayload, GuardPayload } from "../../lib/events";
import { deriveStopEnabled, StopButton } from "./StopButton";

// `lib/api.ts`'s `stopRun` is mocked at the module level (rather than
// stubbing global `fetch`, which is how `useAgentRun.test.ts` covers the
// hook layer) because this component calls `stopRun` directly and this
// suite needs precise control over exactly when that call's promise
// resolves, including "never, within this test" for the slow-backend
// timing assertion below. No sibling `.test.tsx` in this directory mocks a
// module yet (`AnswerStream.test.tsx`/`QueryPipelineStepper.test.tsx` take
// only a plain `events` array, no network calls), so `vi.mock` is the
// standard vitest tool for this job, applied here for the first time in
// this directory rather than invented from nothing.
vi.mock("../../lib/api", () => ({
  stopRun: vi.fn(),
}));

import { stopRun } from "../../lib/api";

const stopRunMock = vi.mocked(stopRun);

function envelope<TType extends string, TPayload>(
  type: TType,
  payload: TPayload,
  seq: number,
): Extract<AgentEvent, { type: TType }> {
  return {
    type,
    version: "v1",
    trace_id: "trace-1",
    seq,
    ts: new Date(2026, 0, 1, 0, 0, seq).toISOString(),
    payload,
  } as unknown as Extract<AgentEvent, { type: TType }>;
}

const GUARD_PASSED: GuardPayload = { passed: true, category: "ok", reason: null };
const GUARD_FAILED: GuardPayload = { passed: false, category: "off_topic", reason: null };
const NON_FATAL_ERROR: ErrorPayload = {
  fatal: false,
  scope: "tool",
  source: "ncbi_efetch",
  error_class: "transient",
  message: "retrying",
  retry_after_s: 1,
};
const FATAL_ERROR: ErrorPayload = {
  fatal: true,
  scope: "run",
  source: "agent_loop",
  error_class: "unexpected",
  message: "unrecoverable",
  retry_after_s: 0,
};

const guardPassedEvent = envelope("guard", GUARD_PASSED, 0);
const guardFailedEvent = envelope("guard", GUARD_FAILED, 0);
const trustSignalEvent = envelope(
  "trust_signal",
  { outcome: "answer", risk_tier: "low", grounded: true, triangulated: true },
  5,
);
const doneEvent = envelope(
  "done",
  { total_cost_usd: 0.01, total_tool_calls: 1, elapsed_ms: 500, trust_outcome: "answer" },
  6,
);
const nonFatalErrorEvent = envelope("error", NON_FATAL_ERROR, 2);
const fatalErrorEvent = envelope("error", FATAL_ERROR, 2);

describe("deriveStopEnabled", () => {
  it("is disabled before any guard event has arrived", () => {
    expect(deriveStopEnabled([])).toBe(false);
  });

  it("is disabled when the guard event failed", () => {
    expect(deriveStopEnabled([guardFailedEvent])).toBe(false);
  });

  it("is enabled after a passing guard event", () => {
    expect(deriveStopEnabled([guardPassedEvent])).toBe(true);
  });

  it("is disabled again after a trust_signal event", () => {
    expect(deriveStopEnabled([guardPassedEvent, trustSignalEvent])).toBe(false);
  });

  it("is disabled again after a done event", () => {
    expect(deriveStopEnabled([guardPassedEvent, doneEvent])).toBe(false);
  });

  it("is disabled again after a fatal error event", () => {
    expect(deriveStopEnabled([guardPassedEvent, fatalErrorEvent])).toBe(false);
  });

  it("stays enabled after a non-fatal error event", () => {
    expect(deriveStopEnabled([guardPassedEvent, nonFatalErrorEvent])).toBe(true);
  });
});

describe("StopButton", () => {
  beforeEach(() => {
    stopRunMock.mockReset();
    stopRunMock.mockResolvedValue({ stopped: true });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("is disabled before a passing guard event has arrived", () => {
    render(<StopButton events={[]} runId="run-1" token="test-token" stop={vi.fn()} />);
    expect(screen.getByRole("button", { name: /stop/i })).toBeDisabled();
  });

  it("is enabled after a guard event with passed: true", () => {
    render(<StopButton events={[guardPassedEvent]} runId="run-1" token="test-token" stop={vi.fn()} />);
    expect(screen.getByRole("button", { name: /stop/i })).toBeEnabled();
  });

  it("is disabled again after a trust_signal event", () => {
    render(
      <StopButton
        events={[guardPassedEvent, trustSignalEvent]}
        runId="run-1"
        token="test-token"
        stop={vi.fn()}
      />,
    );
    expect(screen.getByRole("button", { name: /stop/i })).toBeDisabled();
  });

  it("is disabled again after a done event", () => {
    render(
      <StopButton events={[guardPassedEvent, doneEvent]} runId="run-1" token="test-token" stop={vi.fn()} />,
    );
    expect(screen.getByRole("button", { name: /stop/i })).toBeDisabled();
  });

  it("is disabled again after a fatal error event, but not after a non-fatal one", () => {
    const { rerender } = render(
      <StopButton
        events={[guardPassedEvent, nonFatalErrorEvent]}
        runId="run-1"
        token="test-token"
        stop={vi.fn()}
      />,
    );
    expect(screen.getByRole("button", { name: /stop/i })).toBeEnabled();

    rerender(
      <StopButton
        events={[guardPassedEvent, nonFatalErrorEvent, fatalErrorEvent]}
        runId="run-1"
        token="test-token"
        stop={vi.fn()}
      />,
    );
    expect(screen.getByRole("button", { name: /stop/i })).toBeDisabled();
  });

  it("clicking while enabled calls the local stop() callback and stopRun with the run id and token", async () => {
    const user = userEvent.setup();
    const stopMock = vi.fn();
    render(
      <StopButton events={[guardPassedEvent]} runId="run-42" token="test-token" stop={stopMock} />,
    );

    await user.click(screen.getByRole("button", { name: /stop/i }));

    expect(stopMock).toHaveBeenCalledTimes(1);
    expect(stopRunMock).toHaveBeenCalledTimes(1);
    expect(stopRunMock).toHaveBeenCalledWith("run-42", "test-token");
  });

  it("calls the local stop() callback synchronously, before a slow stopRun response resolves", async () => {
    const user = userEvent.setup();
    const stopMock = vi.fn();
    let resolveStopRun: (() => void) | undefined;
    stopRunMock.mockReturnValueOnce(
      new Promise((resolve) => {
        resolveStopRun = () => resolve({ stopped: true });
      }),
    );

    render(<StopButton events={[guardPassedEvent]} runId="run-1" token="test-token" stop={stopMock} />);

    await user.click(screen.getByRole("button", { name: /stop/i }));

    // The slow `stopRun` call has NOT resolved yet at this point (its
    // resolver is only invoked below), and both the local callback and the
    // button's own disabled state have already updated. This is the actual
    // proof of "immediately responsive": if the click handler awaited
    // `stopRun` before doing either of these, this assertion would run
    // before `stopMock` had fired.
    expect(stopMock).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("button", { name: /stop/i })).toBeDisabled();

    // Clean up the still-pending promise so it does not leak into a later
    // test.
    resolveStopRun?.();
  });

  it("does not throw and does not call stopRun again when clicking an already-finished (disabled) run", async () => {
    const user = userEvent.setup();
    const stopMock = vi.fn();
    render(
      <StopButton events={[guardPassedEvent, doneEvent]} runId="run-1" token="test-token" stop={stopMock} />,
    );

    const button = screen.getByRole("button", { name: /stop/i });
    expect(button).toBeDisabled();

    // A real disabled native <button> blocks the click at the DOM level;
    // this is the actual mechanism protecting an already-finished run, not
    // just an internal no-op branch in the handler.
    await expect(user.click(button)).resolves.not.toThrow();

    expect(stopMock).not.toHaveBeenCalled();
    expect(stopRunMock).not.toHaveBeenCalled();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("double-clicking while enabled only fires stopRun once, since the first click disables the button", async () => {
    const user = userEvent.setup();
    const stopMock = vi.fn();
    render(<StopButton events={[guardPassedEvent]} runId="run-1" token="test-token" stop={stopMock} />);

    const button = screen.getByRole("button", { name: /stop/i });
    await user.click(button);
    expect(button).toBeDisabled();

    // userEvent respects the `disabled` attribute the same way a real user
    // would; a second click is a no-op at the DOM level, not a second
    // handler invocation.
    await expect(user.click(button)).resolves.not.toThrow();

    expect(stopMock).toHaveBeenCalledTimes(1);
    expect(stopRunMock).toHaveBeenCalledTimes(1);
  });

  it("is keyboard-operable: reachable by Tab, activatable by Enter and Space", async () => {
    const user = userEvent.setup();
    const stopMock = vi.fn();
    render(<StopButton events={[guardPassedEvent]} runId="run-1" token="test-token" stop={stopMock} />);

    await user.tab();
    expect(screen.getByRole("button", { name: /stop/i })).toHaveFocus();

    await user.keyboard("{Enter}");
    expect(stopMock).toHaveBeenCalledTimes(1);
    expect(stopRunMock).toHaveBeenCalledTimes(1);
  });

  it("activates on Space when focused", async () => {
    const user = userEvent.setup();
    const stopMock = vi.fn();
    render(<StopButton events={[guardPassedEvent]} runId="run-1" token="test-token" stop={stopMock} />);

    screen.getByRole("button", { name: /stop/i }).focus();
    await user.keyboard(" ");

    expect(stopMock).toHaveBeenCalledTimes(1);
    expect(stopRunMock).toHaveBeenCalledTimes(1);
  });

  it("is not reachable by Tab while disabled (before guard passes)", async () => {
    const user = userEvent.setup();
    render(<StopButton events={[]} runId="run-1" token="test-token" stop={vi.fn()} />);

    await user.tab();
    expect(screen.getByRole("button", { name: /stop/i })).not.toHaveFocus();
  });
});
