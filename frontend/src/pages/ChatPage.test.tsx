import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ChatPage } from "./ChatPage";

// `lib/api.ts` is mocked at the module level so this suite controls
// exactly what `createRun` and `openEventStream` "return", without a real
// network call, the same convention `StopButton.test.tsx` established for
// `stopRun`. `useAgentRun` itself is deliberately NOT mocked: it calls
// `openEventStream` internally, so mocking `lib/api.ts` here exercises the
// real hook, the real SSE frame parsing, and this file's real wiring, per
// this ticket's instruction to test real wiring rather than a fully
// stubbed hook.
vi.mock("../lib/api", () => ({
  createRun: vi.fn(),
  openEventStream: vi.fn(),
  stopRun: vi.fn(),
}));

import { createRun, openEventStream, stopRun } from "../lib/api";

const createRunMock = vi.mocked(createRun);
const openEventStreamMock = vi.mocked(openEventStream);
const stopRunMock = vi.mocked(stopRun);

/**
 * Mirrors `useAgentRun.test.ts`'s own SSE frame builder: `sse_starlette`'s
 * default `\r\n` separator, per that module's docstring citation.
 */
function buildFrame(type: string, envelope: unknown): string {
  return `event: ${type}\r\ndata: ${JSON.stringify(envelope)}\r\n\r\n`;
}

function buildEnvelope(type: string, seq: number, payload: unknown) {
  return { type, version: "v1", trace_id: "trace-1", seq, ts: "2026-07-28T12:00:00Z", payload };
}

function makeSseStream(chunks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  let index = 0;
  return new ReadableStream<Uint8Array>({
    pull(controller) {
      if (index >= chunks.length) {
        controller.close();
        return;
      }
      controller.enqueue(encoder.encode(chunks[index]));
      index += 1;
    },
  });
}

/** A minimal stand-in for `Response`, matching only what `useAgentRun` reads. */
function makeStreamingResponse(body: ReadableStream<Uint8Array> | null): Response {
  return { ok: true, status: 200, body } as unknown as Response;
}

/** A promise that never settles, for tests only checking the wiring or the
 * pre-guard loading state, not stream content. */
function pendingForever<T>(): Promise<T> {
  return new Promise<T>(() => {});
}

describe("ChatPage", () => {
  beforeEach(() => {
    createRunMock.mockReset();
    openEventStreamMock.mockReset();
    stopRunMock.mockReset();
    stopRunMock.mockResolvedValue({ stopped: true });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("calls createRun with the initial query, a session id, and the token", async () => {
    createRunMock.mockResolvedValue({ run_id: "run-1", persona_name: "stub" });
    openEventStreamMock.mockReturnValue(pendingForever());

    render(<ChatPage initialQuery="What is rs334?" token="test-token" onExit={vi.fn()} />);

    await waitFor(() => expect(createRunMock).toHaveBeenCalledTimes(1));
    expect(createRunMock).toHaveBeenCalledWith(
      { text: "What is rs334?", session_id: expect.any(String) },
      "test-token",
    );
  });

  it("opens the event stream with the run id createRun returned and the same token", async () => {
    createRunMock.mockResolvedValue({ run_id: "run-42", persona_name: "stub" });
    openEventStreamMock.mockReturnValue(pendingForever());

    render(<ChatPage initialQuery="test" token="test-token" onExit={vi.fn()} />);

    await waitFor(() => expect(openEventStreamMock).toHaveBeenCalledTimes(1));
    expect(openEventStreamMock).toHaveBeenCalledWith(
      "run-42",
      "test-token",
      expect.objectContaining({ signal: expect.anything() }),
    );
  });

  it("renders the loading skeleton before any guard event has arrived", async () => {
    createRunMock.mockResolvedValue({ run_id: "run-1", persona_name: "stub" });
    openEventStreamMock.mockReturnValue(pendingForever());

    render(<ChatPage initialQuery="test" token="test-token" onExit={vi.fn()} />);

    expect(await screen.findByRole("status")).toBeInTheDocument();
  });

  it("renders the pipeline stepper, answer stream, and stop button once a guard event has arrived, and stops showing the loading skeleton", async () => {
    createRunMock.mockResolvedValue({ run_id: "run-1", persona_name: "stub" });
    const guardEnvelope = buildEnvelope("guard", 0, { passed: true, category: "ok", reason: null });
    const tokenEnvelope = buildEnvelope("token", 1, { text: "CFTR is a gene.", marker_ids: [] });
    openEventStreamMock.mockResolvedValue(
      makeStreamingResponse(
        makeSseStream([buildFrame("guard", guardEnvelope), buildFrame("token", tokenEnvelope)]),
      ),
    );

    render(<ChatPage initialQuery="test" token="test-token" onExit={vi.fn()} />);

    expect(await screen.findByText("CFTR is a gene.")).toBeInTheDocument();
    expect(screen.getByRole("list", { name: /search progress/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^stop$/i })).toBeInTheDocument();
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("renders the guardrail banner and a disabled stop button when the guard event failed", async () => {
    createRunMock.mockResolvedValue({ run_id: "run-1", persona_name: "stub" });
    const guardFailedEnvelope = buildEnvelope("guard", 0, {
      passed: false,
      category: "off_topic",
      reason: null,
    });
    openEventStreamMock.mockResolvedValue(
      makeStreamingResponse(makeSseStream([buildFrame("guard", guardFailedEnvelope)])),
    );

    render(<ChatPage initialQuery="test" token="test-token" onExit={vi.fn()} />);

    expect(await screen.findByRole("alert")).toHaveTextContent(/outside biomedical research/i);
    expect(screen.getByRole("button", { name: /^stop$/i })).toBeDisabled();
  });

  it("shows an error message, not a crash, when createRun fails, and never opens the event stream", async () => {
    createRunMock.mockRejectedValue(new Error("createRun failed with 500: internal error"));
    openEventStreamMock.mockReturnValue(pendingForever());

    render(<ChatPage initialQuery="test" token="test-token" onExit={vi.fn()} />);

    expect(await screen.findByRole("alert")).toHaveTextContent(/could not start this search/i);
    expect(openEventStreamMock).not.toHaveBeenCalled();
  });

  it("shows an error message, not a crash, when the event stream itself fails before any guard event arrives", async () => {
    createRunMock.mockResolvedValue({ run_id: "run-1", persona_name: "stub" });
    openEventStreamMock.mockRejectedValue(new Error("openEventStream failed with 401: expired token"));

    render(<ChatPage initialQuery="test" token="test-token" onExit={vi.fn()} />);

    expect(await screen.findByRole("alert")).toHaveTextContent(/could not start this search/i);
  });

  it("calls onExit when the back-to-search button is clicked, even while a run is still loading", async () => {
    createRunMock.mockResolvedValue({ run_id: "run-1", persona_name: "stub" });
    openEventStreamMock.mockReturnValue(pendingForever());
    const user = userEvent.setup();
    const onExit = vi.fn();

    render(<ChatPage initialQuery="test" token="test-token" onExit={onExit} />);
    await user.click(screen.getByRole("button", { name: /back to search/i }));

    expect(onExit).toHaveBeenCalledTimes(1);
  });

  it("renders the initial query in the chat shell header", async () => {
    createRunMock.mockResolvedValue({ run_id: "run-1", persona_name: "stub" });
    openEventStreamMock.mockReturnValue(pendingForever());

    render(<ChatPage initialQuery="What is rs334?" token="test-token" onExit={vi.fn()} />);

    expect(screen.getByText("What is rs334?")).toBeInTheDocument();
  });
});
