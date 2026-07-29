import type { AgentEvent, ToolCall, ToolName } from "../../lib/events";

/**
 * `QueryPipelineStepper` renders `guard`, `think`, `plan`, `tool_start`, and
 * `tool_result` events as an ordered list of curated steps (Technical_
 * specification.md Section 12.3), each moving through `pending`, `active`,
 * and `done`/`error` as its events arrive.
 *
 * PROP SHAPE, DOCUMENTED CHOICE (T-1.2-05's prompt asks this to be an
 * explicit call): this component takes the full `events: AgentEvent[]`
 * array, the same array `useAgentRun` exposes, rather than a slice a parent
 * pre-filters. Every component in this ticket (`QueryPipelineStepper`,
 * `AnswerStream`, `GuardrailBanner`, `CapMessage`) does the same, so
 * `ChatPage` (a later ticket's wiring) can pass one array to all of them
 * without needing to know which event types each one reads. Each component
 * filters for exactly the types Section 12's spec says it owns and ignores
 * the rest, which also makes each component independently testable with a
 * plain array literal, no fixture-slicing helper required.
 *
 * No `citation`-dependent rendering path exists here, not even a
 * placeholder: no real `citation` event exists until build phases 2.2 and
 * 3.4 (tracker/phase_1.2.md's Scope note), and `v1-scope-boundary.md`
 * forbids building against data that does not exist yet.
 */

export type StepStatus = "pending" | "active" | "done" | "error";

export interface PipelineStep {
  id: string;
  label: string;
  status: StepStatus;
  detail?: string;
}

interface QueryPipelineStepperProps {
  events: AgentEvent[];
}

type GuardEvent = Extract<AgentEvent, { type: "guard" }>;
type ThinkEvent = Extract<AgentEvent, { type: "think" }>;
type PlanEvent = Extract<AgentEvent, { type: "plan" }>;
type ToolStartEvent = Extract<AgentEvent, { type: "tool_start" }>;
type ToolResultEvent = Extract<AgentEvent, { type: "tool_result" }>;

function findLastOfType<T extends AgentEvent>(
  events: AgentEvent[],
  predicate: (event: AgentEvent) => event is T,
): T | null {
  for (let index = events.length - 1; index >= 0; index -= 1) {
    const event = events[index];
    if (predicate(event)) {
      return event;
    }
  }
  return null;
}

const isGuardEvent = (event: AgentEvent): event is GuardEvent => event.type === "guard";
const isThinkEvent = (event: AgentEvent): event is ThinkEvent => event.type === "think";
const isPlanEvent = (event: AgentEvent): event is PlanEvent => event.type === "plan";
const isToolStartEvent = (event: AgentEvent): event is ToolStartEvent => event.type === "tool_start";
const isToolResultEvent = (event: AgentEvent): event is ToolResultEvent => event.type === "tool_result";

const TOOL_LABELS: Record<ToolName, string> = {
  cypher_query: "Querying the knowledge graph",
  ncbi_efetch: "Fetching an NCBI record",
  ncbi_dbsnp: "Looking up variant data",
  pubtator_annotate: "Checking literature annotations",
  litvar2_lookup: "Checking variant literature",
  pathogen_detection: "Checking pathogen data",
  clinicaltrials_search: "Searching clinical trials",
};

interface Phase {
  id: string;
  label: string;
  kind: "core" | "tool";
  started: boolean;
  terminal: StepStatus | null;
  detail?: string;
}

/**
 * Pure derivation of the stepper's rendered steps from the raw event array.
 * Exported for direct unit testing of state transitions without needing to
 * render the component.
 *
 * Ordering rule: `guard`, `think`, and `plan` have no event marking their
 * own start distinct from their own completion, so exactly one of them is
 * ever `active` at a time (a single cursor advancing left to right, per
 * Section 12.3's pending/active/done-or-error sequence). Tool steps DO have
 * an independent start signal (`tool_start`), so more than one tool step
 * can legitimately be `active` at once if the Act step runs tools
 * concurrently; each tool step's `active` state is judged independently
 * rather than sharing the single core-phase cursor.
 *
 * A guard failure (`payload.passed === false`) blocks every later phase at
 * `pending` forever: the run does not proceed to `think` after a guardrail
 * rejection, so nothing after `guard` should ever show `active`.
 */
export function deriveSteps(events: AgentEvent[]): PipelineStep[] {
  const guard = findLastOfType(events, isGuardEvent);
  const think = findLastOfType(events, isThinkEvent);
  const plan = findLastOfType(events, isPlanEvent);

  const toolStarts = new Map<string, ToolStartEvent>();
  const toolResults = new Map<string, ToolResultEvent>();
  for (const event of events) {
    if (isToolStartEvent(event)) {
      toolStarts.set(event.payload.call_id, event);
    } else if (isToolResultEvent(event)) {
      toolResults.set(event.payload.call_id, event);
    }
  }

  const plannedCalls: ToolCall[] = plan?.payload.tool_calls ?? [];
  const plannedIds = new Set(plannedCalls.map((call) => call.call_id));
  // Defensive: represent a tool_start/tool_result whose call_id was never
  // seen in a `plan` event (out-of-order delivery, or a future server
  // change this client has not been updated for) rather than silently
  // dropping it. `ai-security-standards.md`: treat upstream event data as
  // untrusted until verified, never assume the happy-path ordering holds.
  const extraCalls: ToolCall[] = [...toolStarts.values()]
    .filter((event) => !plannedIds.has(event.payload.call_id))
    .map((event) => ({
      call_id: event.payload.call_id,
      tool: event.payload.tool,
      layer: event.payload.layer,
    }));

  const allCalls = [...plannedCalls, ...extraCalls];

  const phases: Phase[] = [
    {
      id: "guard",
      label: "Guardrail check",
      kind: "core",
      started: true,
      terminal: guard ? (guard.payload.passed ? "done" : "error") : null,
      detail: guard?.payload.reason ?? undefined,
    },
    {
      id: "think",
      label: "Understanding your question",
      kind: "core",
      started: true,
      terminal: think ? "done" : null,
      detail: think?.payload.narrative,
    },
    {
      id: "plan",
      label: "Planning the search",
      kind: "core",
      started: true,
      terminal: plan ? "done" : null,
      detail: plan?.payload.narrative,
    },
    ...allCalls.map((call): Phase => {
      const result = toolResults.get(call.call_id);
      return {
        id: `tool:${call.call_id}`,
        label: TOOL_LABELS[call.tool],
        kind: "tool",
        started: toolStarts.has(call.call_id),
        terminal: result ? (result.payload.status === "error" ? "error" : "done") : null,
        detail: result?.payload.summary,
      };
    }),
  ];

  const steps: PipelineStep[] = [];
  let blocked = false;
  let coreActiveAssigned = false;

  for (const phase of phases) {
    if (phase.terminal) {
      steps.push({ id: phase.id, label: phase.label, status: phase.terminal, detail: phase.detail });
      if (phase.terminal === "error") {
        blocked = true;
      }
      continue;
    }

    if (blocked) {
      steps.push({ id: phase.id, label: phase.label, status: "pending" });
      continue;
    }

    if (phase.kind === "tool") {
      steps.push({ id: phase.id, label: phase.label, status: phase.started ? "active" : "pending" });
      continue;
    }

    if (!coreActiveAssigned) {
      steps.push({ id: phase.id, label: phase.label, status: "active" });
      coreActiveAssigned = true;
    } else {
      steps.push({ id: phase.id, label: phase.label, status: "pending" });
    }
  }

  return steps;
}

const STATUS_MARK: Record<StepStatus, string> = {
  pending: "…",
  active: "●",
  done: "✓",
  error: "✕",
};

const STATUS_LABEL: Record<StepStatus, string> = {
  pending: "pending",
  active: "in progress",
  done: "done",
  error: "error",
};

export function QueryPipelineStepper({ events }: QueryPipelineStepperProps) {
  const steps = deriveSteps(events);

  return (
    <ol className="pipeline-stepper" aria-live="polite" aria-atomic="false" aria-label="Search progress">
      {steps.map((step) => (
        <li
          key={step.id}
          className={`pipeline-step pipeline-step--${step.status}`}
          data-status={step.status}
        >
          <span className="pipeline-step__mark" aria-hidden="true">
            {STATUS_MARK[step.status]}
          </span>
          <span className="pipeline-step__label">
            {step.label}
            <span className="pipeline-step__status-text"> ({STATUS_LABEL[step.status]})</span>
          </span>
          {step.detail ? <p className="pipeline-step__detail">{step.detail}</p> : null}
        </li>
      ))}
    </ol>
  );
}
