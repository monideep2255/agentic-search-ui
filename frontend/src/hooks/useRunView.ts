/**
 * Map the real agent event stream onto the phase 4.8 screens.
 *
 * Build phase 4.8, ticket T-4.8-12. This module exists because of a gap the
 * premise gate did not catch and the old e2e suite did.
 *
 * WHAT WENT WRONG. The first assembly called `createRun` and then rendered a
 * canned five-step walk, so the run screen advanced on a timer regardless of
 * what the agent actually did. `createRun` being called was enough to satisfy
 * gate clause 3b, and every screen rendered, so nothing looked broken. But the
 * only code that consumed the event stream lived in `ChatPage`, which the new
 * routing had orphaned. A module with no callers is LEARNINGS.md's row 28 and
 * this phase hit that shape twice.
 *
 * So this hook is the join: it takes the events `useAgentRun` actually
 * receives and derives exactly what `RunScreen` and `AnswerScreen` render.
 * Nothing here invents state. If the agent emits no `tool_start`, no tool chip
 * appears; if it emits no citation, the claim shows as uncited and the
 * provenance spine shows the gap, which is the entire point of the spine.
 *
 * The step derivation is deliberately event-driven rather than time-driven.
 * `Write` is live once tokens arrive, `Act` once a tool starts, and so on, so
 * the stepper reports what happened rather than what was expected to happen.
 */

import { useMemo } from "react";

import type { AgentEvent, Layer } from "../lib/events";
import type { StepName, ToolCall } from "../components/screens/RunScreen";
import type { Claim, Source, TrustSignal } from "../components/screens/AnswerScreen";

/** The wire's layer strings, mapped to the design system's 1, 2, 3. */
export function layerNumber(layer: Layer): 1 | 2 | 3 {
  switch (layer) {
    case "layer_1_graph":
      return 1;
    case "layer_2_api":
      return 2;
    default:
      return 3;
  }
}

export interface RunView {
  /** The live step, or null when the run has reached a terminal event. */
  activeStep: StepName | null;
  toolCalls: ToolCall[];
  claims: Claim[];
  sources: Source[];
  trust: TrustSignal[];
  meta: string;
  /** True once a terminal event has arrived, so the answer screen can show. */
  landed: boolean;
  /** A refusal or fatal error message, if the run produced one. */
  failure: string | null;
}

/**
 * Derive the run and answer views from the events received so far.
 *
 * Pure and memoised on the event array, so it recomputes only as events
 * arrive rather than on every render.
 */
export function useRunView(events: AgentEvent[]): RunView {
  return useMemo(() => {
    const has = (type: AgentEvent["type"]) => events.some((event) => event.type === type);

    // Step derivation, latest-wins. Ordered from last to first so the most
    // advanced observed step is the live one.
    let activeStep: StepName | null = null;
    if (has("token")) activeStep = "Write";
    else if (has("tool_start")) activeStep = "Act";
    else if (has("plan")) activeStep = "Plan";
    else if (has("think")) activeStep = "Think";
    else if (has("guard")) activeStep = "Guard";

    const done = events.find((event) => event.type === "done");
    const fatal = events.find((event) => event.type === "error");
    const landed = done !== undefined || fatal !== undefined;
    if (landed) activeStep = null;

    // Tool chips, one per started call, deduplicated by call_id because a
    // tool_result repeats its call's identity.
    const seenCalls = new Set<string>();
    const toolCalls: ToolCall[] = [];
    for (const event of events) {
      if (event.type !== "tool_start" && event.type !== "tool_result") continue;
      const payload = event.payload;
      if (seenCalls.has(payload.call_id)) continue;
      seenCalls.add(payload.call_id);
      toolCalls.push({
        name: payload.tool,
        detail: event.type === "tool_result" ? `${event.payload.result_count} rows` : "running",
        layer: layerNumber(payload.layer),
      });
    }

    // Sources come from citation events, in the order the agent numbered them.
    const sources: Source[] = events
      .filter((event) => event.type === "citation")
      .map((event) => {
        const payload = event.payload;
        return {
          n: payload.display_index,
          layer: layerNumber(payload.layer),
          name: `${payload.source} ${payload.source_id}`.trim(),
          tool: payload.field || payload.source,
          evidence: payload.evidence_kind,
          confidence: payload.assertion_confidence,
          license: payload.license,
          url: payload.source_url,
        };
      })
      .sort((a, b) => a.n - b.n);

    // Claims are the streamed narrative, split into sentences and matched to
    // the citation whose claim_text they carry. A sentence with no matching
    // citation is UNCITED and must render as a gap on the spine: that is the
    // cite-or-refuse promise made visible, so it is never quietly hidden.
    const narrative = events
      .filter((event) => event.type === "token")
      .map((event) => event.payload.text)
      .join("");

    const sentences = narrative
      .split(/(?<=[.!?])\s+/)
      .map((text) => text.trim())
      .filter((text) => text.length > 0);

    const claims: Claim[] = sentences.map((text) => {
      const match = events.find(
        (event) => event.type === "citation" && text.includes(event.payload.claim_text),
      );
      if (match && match.type === "citation") {
        return {
          text,
          layer: layerNumber(match.payload.layer),
          citation: match.payload.display_index,
        };
      }
      return { text, layer: null, citation: null };
    });

    // Trust signals. Worst-wins is the server's job; this only renders what
    // arrived, and never manufactures a positive verdict from nothing.
    const trustEvent = events.find((event) => event.type === "trust_signal");
    const trust: TrustSignal[] = [];
    if (trustEvent && trustEvent.type === "trust_signal") {
      const payload = trustEvent.payload;
      trust.push(
        payload.grounded
          ? { kind: "good", label: "Grounded · every claim cited" }
          : { kind: "risk", label: "Not fully grounded" },
      );
      if (payload.risk_tier && payload.risk_tier !== "low") {
        trust.push({ kind: "risk", label: `${payload.risk_tier} risk claim` });
      }
      if (payload.triangulated === true) {
        trust.push({ kind: "plain", label: "Cross-checked across layers" });
      }
    }

    const layersUsed = new Set(toolCalls.map((call) => call.layer));
    const meta = landed
      ? `${toolCalls.length} ${toolCalls.length === 1 ? "tool" : "tools"} · ` +
        `${layersUsed.size} ${layersUsed.size === 1 ? "layer" : "layers"} · ` +
        `${sources.length} ${sources.length === 1 ? "source" : "sources"}`
      : "";

    const failure =
      fatal && fatal.type === "error"
        ? (fatal.payload as { message?: string }).message ?? "The run could not be completed."
        : null;

    return { activeStep, toolCalls, claims, sources, trust, meta, landed, failure };
  }, [events]);
}

export default useRunView;
