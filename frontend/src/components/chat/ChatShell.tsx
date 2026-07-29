import type { ReactNode } from "react";

interface ChatShellProps {
  query: string;
  children: ReactNode;
}

/**
 * Page layout wrapper for the chat experience: the query header plus a body
 * region for whatever `ChatPage` renders into it. Run and token state ended
 * up living in `App.tsx`/`ChatPage.tsx` instead of here (T-1.2-08's actual
 * wiring), since both need to reach `useAgentRun`, `createRun`, and every
 * chat component directly; a layout-only wrapper has no reason to hold that
 * state just to pass it straight through unused.
 */
export function ChatShell({ query, children }: ChatShellProps) {
  return (
    <div className="chat-shell">
      <header className="chat-shell__header">
        <p className="chat-shell__query">{query}</p>
      </header>
      <div className="chat-shell__body">{children}</div>
    </div>
  );
}
