import { useEffect, useState } from "react";
import { ChatShell } from "../components/chat/ChatShell";
import { QueryPipelineStepper } from "../components/chat/QueryPipelineStepper";
import { AnswerStream } from "../components/chat/AnswerStream";
import { GuardrailBanner } from "../components/chat/GuardrailBanner";
import { CapMessage } from "../components/chat/CapMessage";
import { LoadingSkeleton, type LoadingSkeletonState } from "../components/chat/LoadingSkeleton";
import { StopButton } from "../components/chat/StopButton";
import { useAgentRun } from "../hooks/useAgentRun";
import { createRun } from "../lib/api";

interface ChatPageProps {
  initialQuery: string;
  token: string;
  onExit: () => void;
}

/**
 * T-1.2-08: wires the six already-merged chat components (T-1.2-05/06)
 * together against a real run, replacing the T-1.2-03 placeholder. Every
 * one of those components takes the same `events: AgentEvent[]` array
 * `useAgentRun` exposes (`QueryPipelineStepper.tsx`'s "PROP SHAPE"
 * docstring states this is deliberate, exactly so this ticket could pass
 * one array to all of them), so this file is genuinely assembly: no
 * imported component's own `.tsx` source changes.
 *
 * On mount, this calls `createRun` to obtain a `run_id`, then mounts
 * `useAgentRun(runId, token)` once that id is known. `useAgentRun` itself
 * already does nothing (`status: "idle"`) while `runId` is `null`, so the
 * "waiting on createRun" window and the "waiting on the first SSE event"
 * window are both covered by the same loading-skeleton branch below with
 * no extra flag needed for the first one.
 */
export function ChatPage({ initialQuery, token, onExit }: ChatPageProps) {
  // One fresh session id per page mount, not per keystroke or re-render:
  // `useState`'s lazy initializer runs exactly once per mount.
  // `crypto.randomUUID()` is a Web Crypto API method available in every
  // browser this app targets and in this repo's jsdom test environment.
  const [sessionId] = useState(() => crypto.randomUUID());
  const [runId, setRunId] = useState<string | null>(null);
  const [createRunError, setCreateRunError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setRunId(null);
    setCreateRunError(null);

    createRun({ text: initialQuery, session_id: sessionId }, token)
      .then((response) => {
        if (!cancelled) {
          setRunId(response.run_id);
        }
      })
      .catch((caught) => {
        if (cancelled) {
          return;
        }
        // `caught.message` here is `ApiError`'s own constructed string
        // (e.g. "createRun failed with 401: ..."), never a raw response
        // body or object; see `lib/api.ts`'s `throwIfNotOk`. Rendered as
        // plain JSX text below, so React's default escaping still applies
        // even though this string is already backend-controlled and safe.
        setCreateRunError(caught instanceof Error ? caught.message : String(caught));
      });

    return () => {
      cancelled = true;
    };
    // Re-runs if the query or token changes (a new query submitted from
    // this same mounted page, or a future ticket rotating the token).
    // `sessionId` is intentionally stable for the component's lifetime,
    // not itself a re-run trigger, and is still listed here since the
    // effect closes over it.
  }, [initialQuery, token, sessionId]);

  const { events, status, error: runError, stop } = useAgentRun(runId, token);

  const hasGuardEvent = events.some((event) => event.type === "guard");
  // A stream-level failure (the SSE connection itself never came up, or
  // dropped) before a single `guard` event ever arrived would otherwise
  // leave this page stuck on the loading skeleton forever with no
  // indication anything went wrong; `useAgentRun`'s own `error` field
  // exists precisely to report this, so it is surfaced here rather than
  // silently discarded. Once a `guard` event HAS arrived, a later error is
  // handled by the existing components below (GuardrailBanner/CapMessage),
  // not this branch.
  const runFailedBeforeGuard = status === "error" && !hasGuardEvent;

  // LoadingSkeleton and the real pipeline UI are mutually exclusive
  // (Section 12.5's `guard_pending` state is explicitly "no stepper
  // content"): show the skeleton until a `guard` event has actually
  // arrived, covering both "createRun hasn't resolved yet" (`status`
  // stays `"idle"`, since `useAgentRun` does nothing while `runId` is
  // null) and "streaming but the very first event hasn't landed yet".
  const showLoading = createRunError === null && !runFailedBeforeGuard && !hasGuardEvent;
  const loadingState: LoadingSkeletonState = status === "streaming" ? "guard_pending" : "cold_start";

  return (
    <ChatShell query={initialQuery}>
      {createRunError !== null || runFailedBeforeGuard ? (
        <div role="alert" className="chat-page__error">
          Could not start this search: {createRunError ?? runError ?? "an unknown error occurred"}
        </div>
      ) : showLoading ? (
        <LoadingSkeleton state={loadingState} />
      ) : (
        <>
          <QueryPipelineStepper events={events} />
          <GuardrailBanner events={events} />
          <AnswerStream events={events} />
          <CapMessage events={events} />
          {runId !== null ? (
            <StopButton events={events} runId={runId} token={token} stop={stop} />
          ) : null}
        </>
      )}
      <button type="button" onClick={onExit}>
        Back to search
      </button>
    </ChatShell>
  );
}
