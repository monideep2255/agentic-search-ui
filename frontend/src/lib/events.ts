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
    | "cost_capped"
    | "write_seeking"
    | "compute_request";
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
  /**
   * UI fix set 8 (R30). The helper scientist this call is handed to, one
   * per data layer, drawn per run on the server and excluding the lead.
   * OPTIONAL AND NULLABLE on the wire, mirroring `contracts/events.py`: an
   * older backend omits all three, and every consumer treats absent and
   * null identically (no handoff line renders). Presentation only.
   */
  persona?: string | null;
  persona_about?: string | null;
  persona_wikipedia?: string | null;
}

export interface PlanPayload {
  narrative: string;
  tool_calls: ToolCall[];
}

/**
 * T-4.16-01: `"running"` added, mirroring `contracts/events.py`.
 *
 * A `tool_start` is written the instant before a tool is dispatched, so its
 * outcome does not exist yet and every other member of this union would be
 * a claim about a call that has not run.
 *
 * THIS FILE IS LOAD-BEARING FOR THAT CHANGE, not merely a type mirror.
 * `isToolStartPayload` below is a runtime guard, and `parseAgentEvent`
 * THROWS on a payload it rejects. That throw propagates out of
 * `consumeEventStream` into `useAgentRun`'s catch, which sets
 * `status: "error"` and abandons the stream.
 *
 * So while this union said only `ok | empty | error`, shipping the backend
 * half alone would have killed EVERY query in the browser at the first tool
 * frame, with no answer rendered at all. Not a missing chip, a dead run. A
 * contract widened on the producer and not on its validator does not
 * degrade, it fails hard on the first message.
 */
export type ToolStartStatus = "running" | "ok" | "empty" | "error";

/** A result knows its outcome, so `"running"` is not one of its values. */
export type ToolResultStatus = Exclude<ToolStartStatus, "running">;

export interface ToolStartPayload {
  call_id: string;
  tool: ToolName;
  layer: Layer;
  status: ToolStartStatus;
  /** UI fix set 8 (R30): the same helper the planned `ToolCall` carries. Optional, nullable. */
  persona?: string | null;
  persona_about?: string | null;
  persona_wikipedia?: string | null;
}

export interface ToolResultPayload extends ToolStartPayload {
  /**
   * Deliberately re-narrowed rather than inherited, matching
   * `ToolResultPayload` in `contracts/events.py`. Inheriting the wider
   * union would make "the tool finished, and it is still running" a
   * representable state.
   */
  status: ToolResultStatus;
  summary: string;
  result_count: number;
  truncated: boolean;
}

/**
 * UI fix set 9 (2026-09-13). What a token chunk IS, mirroring
 * `TokenPayload.kind` in `contracts/events.py`. Absent or null means an older
 * producer, classified as before.
 */
export const TOKEN_KINDS = [
  "claim",
  "note",
  "heading",
  "paragraph_break",
  "list_item",
  "table_header",
  "table_row",
] as const;
export type TokenKind = (typeof TOKEN_KINDS)[number];

export interface TokenPayload {
  text: string;
  marker_ids: string[];
  // UI fix set 9, additive and optional per Section 2.6.
  kind?: TokenKind | null;
  cells?: string[] | null;
  emphasis?: string[] | null;
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
  // T-4.10-07 (F-4.8-D-02, F-4.8-D-03): additive, optional fields for the
  // source card's header (entity_name) and its SNAPSHOT row
  // (snapshot_date). Both are optional here, not just nullable, so a
  // fixture or payload built before this phase (in either language) still
  // type-checks and validates unchanged, per Section 2.6's additive-only
  // rule; a real citation from the server always sends both, null when it
  // has no real, non-fabricated value (see contracts/events.py's
  // CitationPayload docstring for what each one means and when it is
  // null).
  snapshot_date?: string | null;
  entity_name?: string | null;
}

export interface TrustSignalPayload {
  outcome: TrustOutcome;
  risk_tier: string;
  grounded: boolean;
  triangulated: boolean | null;
  // T-6.2 no-data-refusal fix. Additive per Section 2.6: `contracts/
  // events.py`'s `TrustSignalPayload` has carried these three since build
  // phase 2.2 (`scope`) and build phase 4.3 (`message`, `fallback_link`),
  // and every payload built before that still validates unchanged because
  // all three are optional here too.
  //
  // `scope` distinguishes Section 8.3's per-claim verdict ("claim") from
  // Section 8.4's whole-response verdict ("answer"). `message` and
  // `fallback_link` carry Section 8.4's refuse payload: the refusal
  // sentence and its NCBI cross-database search link, as two separate,
  // independently capped fields rather than one string a consumer would
  // have to split. `useRunView` reads all three to find the answer-level
  // refusal signal and render it through the same notice a guardrail
  // refusal uses, instead of matching on the refusal SENTENCE's wording.
  scope?: "claim" | "answer" | null;
  message?: string | null;
  fallback_link?: string | null;
}

export interface ErrorPayload {
  fatal: boolean;
  scope: "tool" | "step" | "run";
  source: string;
  // "cancelled" added at build phase 4.0 (F-4.0-A-04): a synthetic
  // terminal event for a caller-stopped or abandonment-cancelled run.
  // Keep this union in sync with contracts/events.py's ErrorPayload; the
  // Step 6.2 F-3.0-01 fix found this exact hand-maintained-copy gap once
  // already for a different enum on this same file's category set.
  error_class: "transient" | "recoverable" | "unexpected" | "cancelled";
  message: string;
  retry_after_s: number;
}

export interface DonePayload {
  total_cost_usd: number;
  total_tool_calls: number;
  elapsed_ms: number;
  trust_outcome: TrustOutcome;
  /**
   * UI fix set 9, item 9.9. The one plain trust line for the answer ("Based
   * on 1 source, not yet confirmed"), built in code by the backend. Optional
   * and nullable; null on a refusal, absent from an older backend.
   */
  trust_line?: string | null;
  /**
   * T-6.2-08. An offer of somewhere to go next, or null when there is
   * nowhere honest. OPTIONAL on the wire: an older backend omits it
   * entirely, so this is `?` as well as nullable, and every consumer must
   * treat absent and null identically.
   *
   * It is built in code from the findings the answer did not report, never
   * generated, so it can never propose a topic the retrieval did not
   * actually find. See `DonePayload.next_step` in `contracts/events.py`.
   */
  next_step?: string | null;
  /**
   * UI fix set 7 (R21). The QUESTION to send if the reader accepts the
   * offer, as opposed to `next_step` above, which is the sentence the offer
   * is made in.
   *
   * The two were one field, and accepting sent the offer's own wording to
   * the agent: "Yes, go deeper" dispatched "Would you like me to go through
   * the 3 further disease records found for this question?", a yes/no
   * sentence about the interface rather than a question about biology.
   *
   * OPTIONAL AND NULLABLE, on the same terms as `next_step`: a backend that
   * predates this field omits it, and every consumer must treat absent and
   * null identically by falling back to `next_step`, which is exactly what
   * was sent before this field existed.
   */
  next_step_query?: string | null;
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
    [
      "ok",
      "off_topic",
      "medical_advice",
      "injection",
      "rate_limited",
      "cost_capped",
      "write_seeking",
      "compute_request",
    ].includes(value.category) &&
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

/**
 * UI fix set 8: the three persona fields are optional on both frames that
 * carry them, so absent and null both pass and any other type is refused.
 */
function hasOptionalPersonaFields(value: Record<string, unknown>): boolean {
  return (
    (value.persona === undefined || isNullableString(value.persona)) &&
    (value.persona_about === undefined || isNullableString(value.persona_about)) &&
    (value.persona_wikipedia === undefined || isNullableString(value.persona_wikipedia))
  );
}

function isToolCall(value: unknown): value is ToolCall {
  return (
    isRecord(value) &&
    isToolName(value.tool) &&
    typeof value.call_id === "string" &&
    isLayer(value.layer) &&
    hasOptionalPersonaFields(value)
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

function isToolStartStatus(value: unknown): value is ToolStartStatus {
  return (
    value === "running" || value === "ok" || value === "empty" || value === "error"
  );
}

function isToolStartPayload(value: unknown): value is ToolStartPayload {
  return (
    isRecord(value) &&
    typeof value.call_id === "string" &&
    isToolName(value.tool) &&
    isLayer(value.layer) &&
    isToolStartStatus(value.status) &&
    hasOptionalPersonaFields(value)
  );
}

function isToolResultPayload(value: unknown): value is ToolResultPayload {
  if (!isToolStartPayload(value)) {
    return false;
  }
  // T-4.16-01. `isToolStartPayload` now admits `"running"`, and this guard
  // delegates to it, so without this line widening the start payload would
  // have silently widened the RESULT payload too and let a finished call
  // report itself as still running. The re-narrowing that
  // `ToolResultPayload` states in its type has to be enforced here as well,
  // because the type is erased at runtime and this guard is what actually
  // decides.
  if (value.status === "running") {
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

function isOptionalStringArray(value: unknown): boolean {
  return value === undefined || value === null || isStringArray(value);
}

function isTokenPayload(value: unknown): value is TokenPayload {
  return (
    isRecord(value) &&
    typeof value.text === "string" &&
    isStringArray(value.marker_ids) &&
    (value.kind === undefined ||
      value.kind === null ||
      (TOKEN_KINDS as readonly unknown[]).includes(value.kind)) &&
    isOptionalStringArray(value.cells) &&
    isOptionalStringArray(value.emphasis)
  );
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
    typeof value.license === "string" &&
    (value.snapshot_date === undefined || isNullableString(value.snapshot_date)) &&
    (value.entity_name === undefined || isNullableString(value.entity_name))
  );
}

function isTrustSignalPayload(value: unknown): value is TrustSignalPayload {
  return (
    isRecord(value) &&
    isTrustOutcome(value.outcome) &&
    typeof value.risk_tier === "string" &&
    typeof value.grounded === "boolean" &&
    (value.triangulated === null || typeof value.triangulated === "boolean") &&
    (value.scope === undefined ||
      value.scope === null ||
      value.scope === "claim" ||
      value.scope === "answer") &&
    (value.message === undefined || isNullableString(value.message)) &&
    (value.fallback_link === undefined || isNullableString(value.fallback_link))
  );
}

function isErrorPayload(value: unknown): value is ErrorPayload {
  return (
    isRecord(value) &&
    typeof value.fatal === "boolean" &&
    (value.scope === "tool" || value.scope === "step" || value.scope === "run") &&
    typeof value.source === "string" &&
    typeof value.error_class === "string" &&
    ["transient", "recoverable", "unexpected", "cancelled"].includes(value.error_class) &&
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
    isTrustOutcome(value.trust_outcome) &&
    (value.trust_line === undefined || isNullableString(value.trust_line))
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
