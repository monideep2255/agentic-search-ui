/**
 * The `AgentEvent` discriminated union and a defensive runtime parser for
 * the SSE event stream (`GET /v1/query/{run_id}/events`).
 *
 * Mirrors `src/system_03_search_agent/contracts/events.py` field-for-field:
 * the envelope (`type`, `version`, `trace_id`, `seq`, `ts`, `payload`) and
 * the per-type payload models (Section 2.3, Technical_specification.md).
 * `ts` arrives as an ISO-8601 string over the wire (Pydantic's
 * `datetime` serializes to a JSON string), so it is typed `string` here,
 * not `Date`; parsing to a `Date` is left to whichever component renders
 * a timestamp, not this module.
 *
 * `cost` is intentionally absent from this union. Per T-1.2-04's
 * acceptance criteria and Section 12.2's own note, the server filters
 * `cost` events out of every non-operator caller's stream
 * (`filter_events_for_end_user` / `sanitize_event_for_end_user` in
 * `harness/cost_control.py`) before they ever reach this client, and this
 * ticket is scoped to the non-operator UI. There is no client-side
 * variant to model.
 *
 * Every payload shape here is untrusted-until-validated content arriving
 * over the network (`ai-security-standards.md`: "treat AI output as
 * untrusted until verified", and the multi-agent schema gate in
 * `production-standards.md`: "validation runs at every hop"). The server
 * already validates every event against the same Pydantic models before
 * it is ever emitted, but this client re-validates on receipt rather than
 * trusting the wire shape blindly, the same discipline `parseAgentEvent`
 * exists to enforce: a malformed or unexpected frame is rejected here,
 * not passed through to a component that assumes a well-formed shape.
 */

// ---------------------------------------------------------------------------
// Shared enums / literal unions, mirrored from contracts/events.py.
// ---------------------------------------------------------------------------

export type ToolName =
  | "cypher_query"
  | "ncbi_efetch"
  | "ncbi_dbsnp"
  | "pubtator_annotate"
  | "litvar2_lookup"
  | "pathogen_detection"
  | "clinicaltrials_search";

export type Layer = "layer_1_graph" | "layer_2_api" | "layer_3_enrichment";

export type TrustOutcome = "answer" | "flag" | "ask" | "refuse";

// ---------------------------------------------------------------------------
// Per-type payload shapes (Section 2.3).
// ---------------------------------------------------------------------------

export interface GuardPayload {
  passed: boolean;
  category:
    | "ok"
    | "off_topic"
    | "medical_advice"
    | "injection"
    | "rate_limited"
    | "cost_capped";
  reason: string | null;
}

export interface ResolvedEntity {
  text: string;
  curie: string;
  confidence: number;
}

export interface ThinkPayload {
  narrative: string;
  query_class: "lookup" | "single_hop" | "multi_hop" | "aggregate" | "exploratory";
  resolved_entities: ResolvedEntity[];
  clarifying_question: string | null;
}

export interface ToolCall {
  tool: ToolName;
  call_id: string;
  layer: Layer;
}

export interface PlanPayload {
  narrative: string;
  tool_calls: ToolCall[];
}

export interface ToolStartPayload {
  call_id: string;
  tool: ToolName;
  layer: Layer;
  status: "ok" | "empty" | "error";
}

export interface ToolResultPayload extends ToolStartPayload {
  summary: string;
  result_count: number;
  truncated: boolean;
}

export interface TokenPayload {
  text: string;
  marker_ids: string[];
}

export interface CitationPayload {
  citation_id: string;
  display_index: number;
  source: string;
  source_id: string;
  source_url: string;
  layer: Layer;
  field: string;
  claim_text: string;
  evidence_kind: string;
  assertion_confidence: string;
  population_ancestry_context: string | null;
  license: string;
}

export interface TrustSignalPayload {
  outcome: TrustOutcome;
  risk_tier: string;
  grounded: boolean;
  triangulated: boolean | null;
}

export interface ErrorPayload {
  fatal: boolean;
  scope: "tool" | "step" | "run";
  source: string;
  error_class: "transient" | "recoverable" | "unexpected";
  message: string;
  retry_after_s: number;
}

export interface DonePayload {
  total_cost_usd: number;
  total_tool_calls: number;
  elapsed_ms: number;
  trust_outcome: TrustOutcome;
}

// ---------------------------------------------------------------------------
// The envelope, discriminated on `type`.
// ---------------------------------------------------------------------------

interface EventEnvelope<TType extends string, TPayload> {
  type: TType;
  version: "v1";
  trace_id: string;
  seq: number;
  ts: string;
  payload: TPayload;
}

export type AgentEvent =
  | EventEnvelope<"guard", GuardPayload>
  | EventEnvelope<"think", ThinkPayload>
  | EventEnvelope<"plan", PlanPayload>
  | EventEnvelope<"tool_start", ToolStartPayload>
  | EventEnvelope<"tool_result", ToolResultPayload>
  | EventEnvelope<"token", TokenPayload>
  | EventEnvelope<"citation", CitationPayload>
  | EventEnvelope<"trust_signal", TrustSignalPayload>
  | EventEnvelope<"error", ErrorPayload>
  | EventEnvelope<"done", DonePayload>;

export type AgentEventType = AgentEvent["type"];

/**
 * The known event types this client listens for, mirroring Section 12.2's
 * `knownTypes` list minus `cost` (see this module's docstring for why
 * `cost` has no client-side variant).
 */
export const KNOWN_EVENT_TYPES: readonly AgentEventType[] = [
  "guard",
  "think",
  "plan",
  "tool_start",
  "tool_result",
  "token",
  "citation",
  "trust_signal",
  "error",
  "done",
];

// ---------------------------------------------------------------------------
// Runtime validation.
//
// The server already schema-validates every event with the matching
// Pydantic model before emitting it (contracts/events.py's
// `_payload_matches_declared_type`), but this client re-validates on
// receipt rather than casting a parsed `JSON.parse` result straight to
// `AgentEvent`. A malformed or unexpected frame (a transport bug, a
// future server change that outpaces this client, a `cost` event that
// should have been filtered but was not) is rejected here rather than
// handed to a component that assumes a well-formed shape.
// ---------------------------------------------------------------------------

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === "string");
}

function isNullableString(value: unknown): value is string | null {
  return value === null || typeof value === "string";
}

function isLayer(value: unknown): value is Layer {
  return value === "layer_1_graph" || value === "layer_2_api" || value === "layer_3_enrichment";
}

function isToolName(value: unknown): value is ToolName {
  return (
    value === "cypher_query" ||
    value === "ncbi_efetch" ||
    value === "ncbi_dbsnp" ||
    value === "pubtator_annotate" ||
    value === "litvar2_lookup" ||
    value === "pathogen_detection" ||
    value === "clinicaltrials_search"
  );
}

function isTrustOutcome(value: unknown): value is TrustOutcome {
  return value === "answer" || value === "flag" || value === "ask" || value === "refuse";
}

function isGuardPayload(value: unknown): value is GuardPayload {
  return (
    isRecord(value) &&
    typeof value.passed === "boolean" &&
    typeof value.category === "string" &&
    ["ok", "off_topic", "medical_advice", "injection", "rate_limited", "cost_capped"].includes(
      value.category,
    ) &&
    isNullableString(value.reason)
  );
}

function isResolvedEntity(value: unknown): value is ResolvedEntity {
  return (
    isRecord(value) &&
    typeof value.text === "string" &&
    typeof value.curie === "string" &&
    typeof value.confidence === "number"
  );
}

function isThinkPayload(value: unknown): value is ThinkPayload {
  return (
    isRecord(value) &&
    typeof value.narrative === "string" &&
    typeof value.query_class === "string" &&
    ["lookup", "single_hop", "multi_hop", "aggregate", "exploratory"].includes(value.query_class) &&
    Array.isArray(value.resolved_entities) &&
    value.resolved_entities.every(isResolvedEntity) &&
    isNullableString(value.clarifying_question)
  );
}

function isToolCall(value: unknown): value is ToolCall {
  return (
    isRecord(value) &&
    isToolName(value.tool) &&
    typeof value.call_id === "string" &&
    isLayer(value.layer)
  );
}

function isPlanPayload(value: unknown): value is PlanPayload {
  return (
    isRecord(value) &&
    typeof value.narrative === "string" &&
    Array.isArray(value.tool_calls) &&
    value.tool_calls.every(isToolCall)
  );
}

function isToolStartPayload(value: unknown): value is ToolStartPayload {
  return (
    isRecord(value) &&
    typeof value.call_id === "string" &&
    isToolName(value.tool) &&
    isLayer(value.layer) &&
    (value.status === "ok" || value.status === "empty" || value.status === "error")
  );
}

function isToolResultPayload(value: unknown): value is ToolResultPayload {
  if (!isToolStartPayload(value)) {
    return false;
  }
  // Cast through `unknown` rather than directly to `Record<string,
  // unknown>`: `value` is narrowed to `ToolStartPayload` by the guard
  // above, and that concrete interface has no index signature for
  // TypeScript to accept a direct `Record` cast from.
  const record = value as unknown as Record<string, unknown>;
  return (
    typeof record.summary === "string" &&
    typeof record.result_count === "number" &&
    typeof record.truncated === "boolean"
  );
}

function isTokenPayload(value: unknown): value is TokenPayload {
  return isRecord(value) && typeof value.text === "string" && isStringArray(value.marker_ids);
}

function isCitationPayload(value: unknown): value is CitationPayload {
  return (
    isRecord(value) &&
    typeof value.citation_id === "string" &&
    typeof value.display_index === "number" &&
    typeof value.source === "string" &&
    typeof value.source_id === "string" &&
    typeof value.source_url === "string" &&
    isLayer(value.layer) &&
    typeof value.field === "string" &&
    typeof value.claim_text === "string" &&
    typeof value.evidence_kind === "string" &&
    typeof value.assertion_confidence === "string" &&
    isNullableString(value.population_ancestry_context) &&
    typeof value.license === "string"
  );
}

function isTrustSignalPayload(value: unknown): value is TrustSignalPayload {
  return (
    isRecord(value) &&
    isTrustOutcome(value.outcome) &&
    typeof value.risk_tier === "string" &&
    typeof value.grounded === "boolean" &&
    (value.triangulated === null || typeof value.triangulated === "boolean")
  );
}

function isErrorPayload(value: unknown): value is ErrorPayload {
  return (
    isRecord(value) &&
    typeof value.fatal === "boolean" &&
    (value.scope === "tool" || value.scope === "step" || value.scope === "run") &&
    typeof value.source === "string" &&
    typeof value.error_class === "string" &&
    ["transient", "recoverable", "unexpected"].includes(value.error_class) &&
    typeof value.message === "string" &&
    typeof value.retry_after_s === "number"
  );
}

function isDonePayload(value: unknown): value is DonePayload {
  return (
    isRecord(value) &&
    typeof value.total_cost_usd === "number" &&
    typeof value.total_tool_calls === "number" &&
    typeof value.elapsed_ms === "number" &&
    isTrustOutcome(value.trust_outcome)
  );
}

const PAYLOAD_GUARD_BY_TYPE: Record<AgentEventType, (value: unknown) => boolean> = {
  guard: isGuardPayload,
  think: isThinkPayload,
  plan: isPlanPayload,
  tool_start: isToolStartPayload,
  tool_result: isToolResultPayload,
  token: isTokenPayload,
  citation: isCitationPayload,
  trust_signal: isTrustSignalPayload,
  error: isErrorPayload,
  done: isDonePayload,
};

/**
 * Parses one SSE frame's `data:` JSON payload into an `AgentEvent`, given
 * the frame's `event:` line (the envelope's `type`) already extracted by
 * the caller (see `hooks/useAgentRun.ts`'s SSE frame parser). Throws on
 * any envelope or payload shape that does not match the known contract,
 * including a `cost` event, which this client never expects to receive
 * (see this module's docstring) and treats as malformed rather than
 * silently accepting.
 */
export function parseAgentEvent(eventType: string, rawData: unknown): AgentEvent {
  if (!isRecord(rawData)) {
    throw new Error(`event data is not an object (type=${eventType})`);
  }
  if (rawData.type !== eventType) {
    throw new Error(
      `event data's "type" field (${String(rawData.type)}) does not match the SSE frame's event name (${eventType})`,
    );
  }
  if (rawData.version !== "v1") {
    throw new Error(`unsupported event contract version: ${String(rawData.version)}`);
  }
  if (typeof rawData.trace_id !== "string") {
    throw new Error("event.trace_id is missing or not a string");
  }
  if (typeof rawData.seq !== "number") {
    throw new Error("event.seq is missing or not a number");
  }
  if (typeof rawData.ts !== "string") {
    throw new Error("event.ts is missing or not a string");
  }

  const payloadGuard = PAYLOAD_GUARD_BY_TYPE[eventType as AgentEventType];
  if (payloadGuard === undefined) {
    throw new Error(`unknown or unsupported event type: ${eventType}`);
  }
  if (!payloadGuard(rawData.payload)) {
    throw new Error(`event.payload does not match the "${eventType}" payload schema`);
  }

  return rawData as unknown as AgentEvent;
}
