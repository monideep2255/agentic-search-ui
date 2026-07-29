import { useEffect, useReducer, useRef, useState } from "react";
import { openEventStream } from "../lib/api";
import { parseAgentEvent, type AgentEvent } from "../lib/events";

/**
 * `useAgentRun`: consumes `GET /v1/query/{run_id}/events` and exposes the
 * decoded `AgentEvent` stream, in arrival order, to a React component.
 *
 * ---------------------------------------------------------------------
 * DEVIATION FROM Technical_specification.md SECTION 12.2, DOCUMENTED
 * ---------------------------------------------------------------------
 * Section 12.2 shows a `new EventSource(url, { withCredentials: true })`
 * snippet. That snippet assumes cookie-based session auth: the browser
 * attaches the session cookie automatically, and `withCredentials: true`
 * just tells `EventSource` to include it on a cross-origin request.
 *
 * This backend does not use cookie auth. Every protected route,
 * including the events route, resolves the caller through
 * `src/system_03_search_agent/auth/dependencies.py`'s `get_current_user`,
 * which requires a `Bearer` token in the `Authorization` header (see that
 * module: "Returns 401 for a missing header, a malformed header (no
 * `Bearer` scheme)..."). There is no session cookie anywhere in this
 * system for `withCredentials` to send.
 *
 * The native browser `EventSource` API has no mechanism to set custom
 * request headers. It sends whatever cookies the browser already holds
 * for the target origin and nothing else, so
 * `new EventSource(url, { withCredentials: true })` against this backend
 * would arrive with no `Authorization` header at all and get a 401 on
 * every request, before a single event was ever streamed.
 *
 * The alternative this hook does NOT use: putting the access token in
 * the URL as a query parameter (`?token=...`) so `EventSource` picks it
 * up implicitly server-side. That was explicitly ruled out for this
 * ticket: a bearer token in a URL is logged by the server's access log,
 * by any intermediate proxy, and by the browser's own history, which is
 * a real credential-exposure risk, not a style preference.
 *
 * Instead, this hook builds SSE consumption on top of `fetch()` with a
 * `ReadableStream` reader (via `lib/api.ts`'s `openEventStream`, which
 * sends the real `Authorization: Bearer <token>` header `fetch` allows
 * and `EventSource` does not), and hand-parses the `text/event-stream`
 * wire format as chunks arrive. The exact frame shape parsed here was
 * read directly from two sources, not assumed:
 *
 *   - `src/system_03_search_agent/adapters/web_sse/app.py`'s
 *     `_event_stream` generator: `yield {"event": sanitized.type, "data":
 *     sanitized.model_dump_json()}` per real event, forwarded through
 *     `sse-starlette`'s `EventSourceResponse`.
 *   - `sse_starlette/event.py`'s `ServerSentEvent.encode()` (the
 *     installed version, 3.4.6, pinned in this repo's venv): each frame
 *     is `event: <type><sep>data: <json><sep><sep>`, where `<sep>`
 *     defaults to `"\r\n"` (`ServerSentEvent.DEFAULT_SEPARATOR`), so a
 *     frame ends in a blank line the same way the more familiar `"\n\n"`
 *     convention does, just with `\r\n` line endings by default. The
 *     parser below normalizes `\r\n` and lone `\r` to `\n` before
 *     splitting, so it accepts either line-ending convention rather than
 *     hard-coding the current default. `sse-starlette` also periodically
 *     sends a comment-only ping frame (`: ping - <timestamp>` with no
 *     `event:`/`data:` line) to keep the connection alive through
 *     proxies; the parser recognizes and silently discards these rather
 *     than treating them as malformed.
 * ---------------------------------------------------------------------
 */

// ---------------------------------------------------------------------------
// SSE wire-format parsing. Exported for direct unit testing of edge cases
// (a frame split across two chunk boundaries, a comment-only ping frame,
// mixed line endings) independently of the hook's async lifecycle.
// ---------------------------------------------------------------------------

export interface RawSseFrame {
  event: string | null;
  data: string | null;
}

/**
 * Splits an accumulated text buffer into complete SSE frames (each
 * terminated by a blank line) and whatever incomplete trailing text
 * remains for the next chunk. Normalizes `\r\n` and lone `\r` to `\n`
 * first, since `sse-starlette`'s configured separator is not a wire-level
 * contract this client should hard-code to one exact byte sequence.
 */
export function splitSseFrames(buffer: string): { frames: string[]; remainder: string } {
  const normalized = buffer.replace(/\r\n|\r/g, "\n");
  const parts = normalized.split("\n\n");
  const remainder = parts.pop() ?? "";
  return { frames: parts, remainder };
}

/**
 * Parses one complete frame's lines into its `event:` name and its
 * (possibly multi-line, per the SSE spec) `data:` payload. Comment lines
 * (starting `:`, used for `sse-starlette`'s keep-alive pings) and `id:`/
 * `retry:` lines (not used by this backend) are recognized and ignored
 * rather than causing a parse error.
 */
export function parseSseFrame(frameText: string): RawSseFrame {
  let event: string | null = null;
  const dataLines: string[] = [];
  // Strips a trailing `\r` per line defensively: `splitSseFrames` already
  // normalizes `\r\n`/`\r` to `\n` before frames reach here, but this
  // function's contract (a frame's raw text in, its parsed fields out)
  // should not silently depend on always being called after that
  // normalization. Splitting on a bare `\n` first and trimming a leftover
  // `\r` per line handles both an already-normalized frame and a raw
  // `\r\n`-separated one identically.
  for (const rawLine of frameText.split("\n")) {
    const line = rawLine.endsWith("\r") ? rawLine.slice(0, -1) : rawLine;
    if (line.length === 0 || line.startsWith(":")) {
      continue;
    }
    if (line.startsWith("event:")) {
      event = line.slice("event:".length).trimStart();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice("data:".length).trimStart());
    }
    // `id:` and `retry:` lines are part of the SSE spec but are never
    // emitted by `_event_stream`; intentionally not parsed.
  }
  return { event, data: dataLines.length > 0 ? dataLines.join("\n") : null };
}

/**
 * Reads `response.body` as it arrives, decodes it as UTF-8 text,
 * incrementally splits it into SSE frames, parses and schema-validates
 * each one via `parseAgentEvent`, and invokes `onEvent` for each decoded
 * `AgentEvent` in the exact order the server sent them (a single
 * sequential read loop over one stream; nothing here reorders events).
 *
 * Stops reading (and cancels the underlying reader, releasing the
 * connection) the moment a `done` event or a fatal `error` event
 * (`payload.fatal === true`) is dispatched, matching this ticket's
 * acceptance criteria. A non-fatal `error` event is dispatched like any
 * other event and does NOT stop the loop.
 */
export async function consumeEventStream(
  response: Response,
  onEvent: (event: AgentEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  if (response.body === null) {
    throw new Error("event stream response has no body to read");
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";
  try {
    while (true) {
      if (signal?.aborted) {
        return;
      }
      const { done, value } = await reader.read();
      if (done) {
        return;
      }
      buffer += decoder.decode(value, { stream: true });
      const { frames, remainder } = splitSseFrames(buffer);
      buffer = remainder;

      for (const frameText of frames) {
        const frame = parseSseFrame(frameText);
        if (frame.event === null || frame.data === null) {
          // A comment-only frame (a keep-alive ping) or a blank frame.
          // Nothing to dispatch.
          continue;
        }

        let rawData: unknown;
        try {
          rawData = JSON.parse(frame.data);
        } catch (parseError) {
          throw new Error(
            `could not parse SSE frame data as JSON (event=${frame.event}): ${String(parseError)}`,
          );
        }

        const agentEvent = parseAgentEvent(frame.event, rawData);
        onEvent(agentEvent);

        if (agentEvent.type === "done") {
          await reader.cancel();
          return;
        }
        if (agentEvent.type === "error" && agentEvent.payload.fatal === true) {
          await reader.cancel();
          return;
        }
      }
    }
  } finally {
    try {
      reader.releaseLock();
    } catch {
      // Already released by the `reader.cancel()` calls above, or the
      // stream already ran to completion. Either way, nothing left to do.
    }
  }
}

// ---------------------------------------------------------------------------
// The hook.
// ---------------------------------------------------------------------------

export type AgentRunStatus = "idle" | "connecting" | "streaming" | "done" | "error";

interface EventsState {
  events: AgentEvent[];
}

type EventsAction = { kind: "append"; event: AgentEvent } | { kind: "reset" };

function eventsReducer(state: EventsState, action: EventsAction): EventsState {
  switch (action.kind) {
    case "append":
      // A fresh array reference in arrival order; `action.event` is
      // always appended last, so array index order is always the order
      // events were dispatched by `consumeEventStream`'s single
      // sequential read loop.
      return { events: [...state.events, action.event] };
    case "reset":
      return { events: [] };
  }
}

export interface UseAgentRunResult {
  /** Every decoded event received so far, in arrival order. */
  events: AgentEvent[];
  status: AgentRunStatus;
  /** Set when `status` is `"error"`; the error message, never a raw object. */
  error: string | null;
  /**
   * Closes the stream immediately from the client side, without waiting
   * on any network round trip. Exposed for a later ticket's stop button
   * (T-1.2-06), which additionally calls `lib/api.ts`'s `stopRun` to
   * cancel the run server-side; this hook only owns the client-side
   * connection lifecycle, not the server call.
   */
  stop: () => void;
}

/**
 * Opens a fetch-based SSE consumption of `GET /v1/query/{run_id}/events`
 * for `runId`, authenticated with `token` (see this module's docstring
 * for why `fetch` is used instead of the native `EventSource`).
 *
 * Re-opens the stream whenever `runId` or `token` changes, and does
 * nothing (`status: "idle"`) while either is `null`, which lets a caller
 * mount this hook before a run has been created yet (before
 * `lib/api.ts`'s `createRun` has returned a `run_id`).
 *
 * Cleans up (aborts the in-flight `fetch`, via `AbortController`) on
 * unmount and whenever `runId`/`token` changes and a new stream is about
 * to open, so navigating away from an active run, or starting a new one,
 * never leaks an open connection.
 */
export function useAgentRun(runId: string | null, token: string | null): UseAgentRunResult {
  const [state, dispatch] = useReducer(eventsReducer, { events: [] });
  const [status, setStatus] = useState<AgentRunStatus>("idle");
  const [error, setError] = useState<string | null>(null);
  const controllerRef = useRef<AbortController | null>(null);

  useEffect(() => {
    if (runId === null || token === null) {
      setStatus("idle");
      setError(null);
      return;
    }

    const controller = new AbortController();
    controllerRef.current = controller;
    let cancelled = false;

    dispatch({ kind: "reset" });
    setError(null);
    setStatus("connecting");

    (async () => {
      try {
        const response = await openEventStream(runId, token, { signal: controller.signal });
        if (cancelled) {
          return;
        }
        setStatus("streaming");
        // Tracked outside React state (a plain closure variable, not a
        // ref or setState) because it only needs to be read once,
        // synchronously, right after `consumeEventStream` resolves, to
        // decide the terminal status below. `dispatch` calls inside the
        // callback are synchronous function calls even though React
        // batches the resulting re-render, so by the time the `await`
        // below resolves, every event this run will ever produce has
        // already been both captured in `lastEvent` and dispatched.
        let lastEvent: AgentEvent | null = null;
        await consumeEventStream(
          response,
          (event) => {
            lastEvent = event;
            if (cancelled) {
              return;
            }
            dispatch({ kind: "append", event });
          },
          controller.signal,
        );
        if (cancelled) {
          return;
        }
        // A type assertion, not a narrowing check: `lastEvent` is
        // mutated inside a nested callback passed to
        // `consumeEventStream`, and TypeScript's control-flow analysis
        // does not track assignments made inside a function it cannot
        // see is synchronous-and-already-resolved at this point, so it
        // otherwise narrows this read to `never`. The runtime value is
        // exactly what the callback last set it to.
        const finalEvent = lastEvent as AgentEvent | null;
        if (finalEvent !== null && finalEvent.type === "error" && finalEvent.payload.fatal === true) {
          // A fatal `error` event is a real, reportable failure the
          // caller should surface (a later ticket's GuardrailBanner/
          // CapMessage read this), not merely "the stream ended".
          setStatus("error");
          setError(finalEvent.payload.message);
        } else {
          // Either a `done` event, or the stream ended (server closed
          // the connection, network EOF) without one. Both are treated
          // as a completed run rather than leaving `status` stuck on
          // `"streaming"` forever.
          setStatus("done");
        }
      } catch (caught) {
        // An abort (unmount, or a new runId/token superseding this
        // effect) is expected control flow, never surfaced as an error.
        if (cancelled || controller.signal.aborted) {
          return;
        }
        setStatus("error");
        setError(caught instanceof Error ? caught.message : String(caught));
      }
    })();

    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [runId, token]);

  const stop = () => {
    controllerRef.current?.abort();
    setStatus((previous) => (previous === "done" || previous === "error" ? previous : "done"));
  };

  return { events: state.events, status, error, stop };
}
