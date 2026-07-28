import { ChatShell } from "../components/chat/ChatShell";

interface ChatPageProps {
  initialQuery: string;
  onExit: () => void;
}

/**
 * Placeholder for the streaming chat experience. The query pipeline stepper,
 * answer stream, guardrail banner, cap message, and stop button are built in
 * T-1.2-05/06 once T-1.2-04's typed SSE consumption exists; this ticket only
 * renders inside ChatShell where they will land.
 */
export function ChatPage({ initialQuery, onExit }: ChatPageProps) {
  return (
    <ChatShell query={initialQuery}>
      <p role="status">
        Streaming answer pipeline not wired up yet. This placeholder will be
        replaced by the query pipeline stepper and answer stream in a later
        ticket.
      </p>
      <button type="button" onClick={onExit}>
        Back to search
      </button>
    </ChatShell>
  );
}
