import { useState, type ReactNode } from "react";

interface ChatShellProps {
  query: string;
  children: ReactNode;
}

/**
 * Layout wrapper for the chat experience. Holds the current run's session
 * state, the `run_id` once a run exists. Run creation (T-1.2-01/02) and SSE
 * consumption (T-1.2-04) are wired in later tickets; this ticket provides
 * only the shell that will eventually hold that state, per the phase 1.2
 * scope note.
 */
export function ChatShell({ query, children }: ChatShellProps) {
  const [runId] = useState<string | null>(null);

  return (
    <div className="chat-shell" data-run-id={runId ?? undefined}>
      <header className="chat-shell__header">
        <p className="chat-shell__query">{query}</p>
      </header>
      <div className="chat-shell__body">{children}</div>
    </div>
  );
}
