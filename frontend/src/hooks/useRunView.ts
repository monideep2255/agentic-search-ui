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
import { deriveStopEnabled } from "../components/chat/StopButton";
import { CATEGORY_COPY } from "../components/chat/GuardrailBanner";
import { isCapShapedError, CAP_MESSAGE_COPY } from "../components/chat/CapMessage";

/**
 * The opening of `cost_control.PER_QUERY_CAP_PARTIAL_RESULT_NOTE`.
 *
 * Matched as a prefix rather than imported: it lives in Python and cannot cross
 * the boundary. Kept short so a reworded tail does not break the match, and
 * documented here so the two stay findable together.
 */
const CAP_NOTE_PREFIX = "This query reached its resource limit";
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
  /**
   * Every step the run actually reached, in order.
   *
   * Separate from `activeStep` because a landed run has no live step, and an
   * earlier version rendered the whole stepper as pending once the run
   * finished: the five steps had visibly happened and the UI then said none of
   * them had. What a run DID is not recoverable from where it IS.
   */
  reachedSteps: StepName[];
  toolCalls: ToolCall[];
  claims: Claim[];
  sources: Source[];
  trust: TrustSignal[];
  meta: string;
  /** True once a terminal event has arrived, so the answer screen can show. */
  landed: boolean;
  /** A refusal or fatal error message, if the run produced one. */
  failure: string | null;
  /**
   * The guardrail's own refusal copy, when a guard event failed.
   *
   * Reuses `GuardrailBanner`'s reviewed table rather than paraphrasing it. That
   * table is deliberately interpolation-free so no cost figure can ever reach a
   * refusal message, which is a structural guarantee rather than careful
   * wording, and reimplementing it here would quietly discard that.
   */
  refusal: string | null;
  /** Cap copy, when the run stopped early on its processing budget. */
  capMessage: string | null;
  /**
   * Whether Stop should still be offered.
   *
   * Reuses `StopButton`'s `deriveStopEnabled`, which has 19 tests behind it and
   * disables on any terminal event. The first version of the new run screen
   * offered Stop unconditionally, including after the run had finished.
   */
  stopEnabled: boolean;
}

/**
 * The view before any run exists.
 *
 * Exported so a caller can render "no run yet" without inventing a shape, and
 * specifically so `App` can discard a previous run's events the moment a new
 * question is asked (F-4.8-J-03).
 */
export const EMPTY_RUN_VIEW: RunView = {
  activeStep: null,
  reachedSteps: [],
  toolCalls: [],
  claims: [],
  sources: [],
  trust: [],
  meta: "",
  landed: false,
  failure: null,
  refusal: null,
  capMessage: null,
  stopEnabled: false,
};

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

    const reachedSteps: StepName[] = [];
    if (has("guard")) reachedSteps.push("Guard");
    if (has("think")) reachedSteps.push("Think");
    if (has("plan")) reachedSteps.push("Plan");
    if (has("tool_start") || has("tool_result")) reachedSteps.push("Act");
    if (has("token")) reachedSteps.push("Write");

    const done = events.find((event) => event.type === "done");
    // Only a FATAL error is terminal. A non-fatal one (a cap notice, a degraded
    // tool) leaves the run streaming, and treating it as terminal navigated the
    // user away mid-answer.
    const fatalError = events.find(
      (event) => event.type === "error" && event.payload.fatal === true,
    );
    const landed = done !== undefined || fatalError !== undefined;
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
    //
    // F-4.8-A-25 and A-18. `display_index` is validated on the wire only as a
    // number, so 0 and -3 rendered as chips "[0]" and "[-3]", and two citations
    // sharing an index produced two source cards both labelled [1] with the
    // same React key and the same data-testid, in two different layer colours.
    // A citation that cannot be numbered cannot be cited, so it is dropped from
    // the source list rather than shown with a nonsense label.
    const seenIndexes = new Set<number>();
    const sources: Source[] = [];
    for (const event of events) {
      if (event.type !== "citation") continue;
      const payload = event.payload;
      const index = payload.display_index;
      // A citation that cannot be numbered cannot be cited, so it is dropped
      // rather than rendered with a nonsense label.
      if (!Number.isInteger(index) || index < 1) continue;
      if (seenIndexes.has(index)) continue;
      seenIndexes.add(index);
      sources.push({
        n: index,
        layer: layerNumber(payload.layer),
        name: `${payload.source} ${payload.source_id}`.trim(),
        tool: payload.field || payload.source,
        evidence: payload.evidence_kind,
        confidence: payload.assertion_confidence,
        license: payload.license,
        url: payload.source_url,
      });
    }
    sources.sort((a, b) => a.n - b.n);

    // Claims come straight off the token events, bound to their citations by
    // `marker_ids`. This replaced a substring heuristic, and the replacement is
    // the whole point rather than a refinement.
    //
    // WHAT WENT WRONG. `_narrative_chunks` in core/graph.py emits ONE TOKEN PER
    // SENTENCE, each carrying `marker_ids`: the citation_id values that sentence
    // cites. Its docstring states the contract outright: "A surface binds a
    // token to its citation by that key, then looks up the number." That
    // binding is exact, validated on the wire, and it was discarded here in
    // favour of re-splitting the joined narrative and matching each sentence
    // against `claim_text` with `String.includes`.
    //
    // The cost of that invention, all of it found by one adversary round:
    //   - a citation whose claim_text was "cancer" cited EVERY sentence
    //     containing the word, including "Every patient with this cancer should
    //     stop chemotherapy immediately"
    //   - a claim_text spanning a sentence boundary matched nothing, so a
    //     correctly cited answer rendered as entirely uncited
    //   - the backend splits on [.;?!] and this split on [.!?], so a
    //     semicolon-joined claim became one segment in the wrong layer colour
    //   - a second citation on one sentence was silently dropped
    //
    // The general lesson, which this repository's `attack-the-constraint` rule
    // already states: when a component is fed by an assembly step, read what it
    // was GIVEN before debugging what it produced. The binding was on the wire.
    const citationById = new Map<string, (typeof events)[number]>();
    for (const event of events) {
      if (event.type === "citation") citationById.set(event.payload.citation_id, event);
    }

    const claims: Claim[] = [];
    for (const event of events) {
      if (event.type !== "token") continue;
      // The backend embeds its own [N] markers in the prose. The UI renders
      // chips from marker_ids instead, so the raw markers are stripped rather
      // than shown alongside them, which previously produced "...edge [2]. 1".
      const text = event.payload.text.replace(/\s*\[\d{1,3}\]/g, "").trim();
      if (!text) continue;

      const cited = (event.payload.marker_ids ?? [])
        .map((id) => citationById.get(id))
        .filter((match): match is NonNullable<typeof match> => match !== undefined);

      // The cap note is a system status message, not an assertion about
      // biology, so it must never occupy a segment on the provenance spine.
      if (text.startsWith(CAP_NOTE_PREFIX)) continue;

      claims.push({
        text,
        // The spine colours a claim by the layer that backed it. With several
        // citations the first is used, which is the order the backend numbered
        // them in; a claim citing two layers is still one claim.
        layer:
          cited.length > 0 && cited[0].type === "citation"
            ? layerNumber(cited[0].payload.layer)
            : null,
        citations: cited.map((match) =>
          match.type === "citation" ? match.payload.display_index : 0,
        ),
      });
    }

    // Trust signals. Worst-wins is the server's job; this only renders what
    // arrived, and never manufactures a positive verdict from nothing.
    // F-4.8-J-06. This took the FIRST trust_signal and discarded every later
    // one, so a run whose verdict was downgraded mid-stream still displayed as
    // fully grounded and low risk. That is precisely the critical build phase
    // 4.1 closed at the MCP fold, reintroduced at the UI layer.
    //
    // Folded worst-wins instead: grounded only if EVERY signal says so, and the
    // highest risk tier any signal reported. The previous comment here claimed
    // "worst-wins is the server's job; this only renders what arrived", which
    // was a property the code did not have. Per `self-eval-loop`, a comment
    // asserting a property needs a test asserting the same property, and clause
    // 3d now does.
    const trustEvents = events.filter((event) => event.type === "trust_signal");
    const trust: TrustSignal[] = [];
    if (trustEvents.length > 0) {
      // F-4.8-A-19. `indexOf` returns -1 for an unknown tier, which LOST to
      // "low" at 0, so a tier the backend renames or adds would silently
      // disappear rather than show. `risk_tier` is typed as a bare string on
      // the wire, not a Literal, so unknown values are expected rather than
      // impossible. An unrecognised tier now outranks every known one: the safe
      // direction for a risk signal is to over-report, never to vanish.
      const RISK_ORDER = ["low", "moderate", "high", "critical"];
      const rank = (tier: string) => {
        const index = RISK_ORDER.indexOf(tier);
        return index === -1 ? Number.MAX_SAFE_INTEGER : index;
      };
      const worstRisk = trustEvents
        .map((event) => (event.type === "trust_signal" ? event.payload.risk_tier : "low"))
        .reduce((worst, tier) => (rank(tier) > rank(worst) ? tier : worst));
      const payload = {
        grounded: trustEvents.every(
          (event) => event.type === "trust_signal" && event.payload.grounded,
        ),
        risk_tier: worstRisk,
        triangulated: trustEvents.every(
          (event) => event.type === "trust_signal" && event.payload.triangulated === true,
        ),
      };
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

    // F-4.8-A-15, two defects in three lines.
    //
    // First, `payload.message` is free-form backend text. `GuardrailBanner` and
    // `CapMessage` both refuse to render that field ON PURPOSE, documenting
    // that Section 12.6's no-cost-figure rule can only be guaranteed by never
    // rendering it. Rendering it here reintroduced exactly the leak those two
    // components were written to prevent, so a fixed string is used instead.
    //
    // Second, the variable was named `fatal` but selected any error event, so a
    // NON-fatal error set `landed` and navigated the user off a still-streaming
    // run. `consumeEventStream` and `deriveStopEnabled` both treat only fatal
    // errors as terminal; this now agrees with them.
    const failure = fatalError
      ? "This run could not be completed. Try asking again, or rephrase the question."
      : null;

    const failedGuard = events.find(
      (event) => event.type === "guard" && event.payload.passed === false,
    );
    const refusal =
      failedGuard && failedGuard.type === "guard"
        ? (CATEGORY_COPY[failedGuard.payload.category] ?? CATEGORY_COPY.ok)
        : null;

    // F-4.8-A-14. `_partial_result_for_cap` emits only a `token` plus
    // `done{trust_outcome:"flag"}` and NO error event, so `isCapShapedError`
    // could never fire on the real cap path. The system's own status note then
    // rendered as an uncited claim on the provenance spine, promising "the
    // answer below" where there was none.
    //
    // The note is recognised by its own text, lifted out of the claim list, and
    // shown as the cap notice it is.
    const capFromError = events.some(isCapShapedError);
    // Detected on the TOKEN EVENTS, not on `claims`.
    //
    // The first version of this fix looked for the note in `claims`, having
    // already skipped it when building `claims` a few lines above, so it could
    // never be found and the notice never rendered. Filtering something out and
    // then searching the filtered result for it is the same ordering mistake
    // this repository keeps recording: a fix round is where the next defect
    // hides, because attention is on the finding named.
    const capFromNote = events.some(
      (event) => event.type === "token" && event.payload.text.trimStart().startsWith(CAP_NOTE_PREFIX),
    );
    const capMessage = capFromError || capFromNote ? CAP_MESSAGE_COPY : null;

    return {
      activeStep,
      reachedSteps,
      toolCalls,
      claims,
      sources,
      trust,
      meta,
      landed,
      failure,
      refusal,
      capMessage,
      stopEnabled: deriveStopEnabled(events),
    };
  }, [events]);
}

export default useRunView;
