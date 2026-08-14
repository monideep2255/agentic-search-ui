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

/**
 * Every bare system-status note `write_node` emits as a token.
 *
 * F-4.8-R-04. The A-14 fix lifted ONE of these off the provenance spine and
 * left two rendering as uncited grey claims. Both of the others are
 * DISCLOSURES, about truncation and about an unaddressed entity, so the trust
 * spine was misreporting on exactly the outputs that exist to be trustworthy:
 * a fully-cited answer displayed uncited segments.
 *
 * These are notes ABOUT the answer, never assertions about biology, so none of
 * them may occupy a segment. Matched on prefixes because the text is composed
 * in Python and cannot be imported across the boundary.
 */
const SYSTEM_NOTE_PREFIXES = [
  CAP_NOTE_PREFIX,
  "Note: this result was truncated",
  "Note: this answer does not address the following entities",
];

const isSystemNote = (text: string) =>
  SYSTEM_NOTE_PREFIXES.some((prefix) => text.trimStart().startsWith(prefix));
import type { ReasoningStep, StepName, ToolCall } from "../components/screens/RunScreen";
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
  /**
   * The run's own account of what it did, oldest first (F-4.8-D-10).
   *
   * Available while the run is live, not only once it lands, because the
   * prototype shows it on the run screen as well as behind the answer
   * screen's `Show work`.
   */
  steps: ReasoningStep[];
  /**
   * The terminal outcome word, from the run's own `done` event (F-4.8-D-05).
   *
   * The prototype's status strip leads with it: "Answered". Null until a run
   * terminates, and null on a fatal error, which is not an outcome the strip
   * should dress up as one.
   */
  outcome: string | null;
  /** Wall-clock the run reported, in ms, from `done.elapsed_ms`. */
  elapsedMs: number | null;
  /**
   * How many DISTINCT layers the run actually touched (F-4.8-D-12).
   *
   * Exposed as a number rather than left inside `meta`'s prose so the trust
   * pill can state it. "Cross-checked across layers" is true of any run that
   * touched more than one and therefore says nothing.
   */
  layerCount: number;
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
   * System notes the answer carried: truncation, unaddressed entities.
   *
   * These are DISCLOSURES about the answer, so removing them from the claim
   * list must not mean discarding them. They are shown as notices instead,
   * which is what they are.
   */
  systemNotes: string[];
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
  steps: [],
  outcome: null,
  elapsedMs: null,
  layerCount: 0,
  landed: false,
  failure: null,
  refusal: null,
  capMessage: null,
  systemNotes: [],
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
    // F-4.8-R-03. `sources` dropped a citation whose display_index was not a
    // usable positive integer, and deduped by index. The claim chips were built
    // from the SAME events with neither check, so a chip could render "[0]"
    // with no source card behind it, and a chip could point at a source card
    // that was not the citation the wire bound it to.
    //
    // One index map, built once, used by both. A citation that cannot be
    // numbered is not usable as a citation anywhere.
    const usableIndexes = new Set<number>();
    const citationById = new Map<string, (typeof events)[number]>();
    for (const event of events) {
      if (event.type !== "citation") continue;
      const index = event.payload.display_index;
      if (!Number.isInteger(index) || index < 1) continue;
      if (usableIndexes.has(index)) continue;
      usableIndexes.add(index);
      citationById.set(event.payload.citation_id, event);
    }

    const emitted = new Set<number>();
    const sources: Source[] = [];
    for (const event of events) {
      if (event.type !== "citation") continue;
      const payload = event.payload;
      const index = payload.display_index;
      // Same rule as the chips above, and deliberately the same set membership:
      // a citation is either usable everywhere or nowhere.
      if (!citationById.has(payload.citation_id)) continue;
      if (emitted.has(index)) continue;
      emitted.add(index);
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
    const claims: Claim[] = [];
    const systemNotes: string[] = [];
    for (const event of events) {
      if (event.type !== "token") continue;
      // R-08: a repeated marker_id must not produce a repeated chip.
      const seenMarkers = new Set<string>();
      const cited = (event.payload.marker_ids ?? [])
        .filter((id) => {
          if (seenMarkers.has(id)) return false;
          seenMarkers.add(id);
          return true;
        })
        .map((id) => citationById.get(id))
        .filter((match): match is NonNullable<typeof match> => match !== undefined);

      // The backend embeds its own [N] markers in the prose. The UI renders
      // chips from marker_ids instead, so the raw markers are stripped rather
      // than shown alongside them, which previously produced "...edge [2]. 1".
      //
      // F-4.8-R-05. The first version stripped EVERY 1-3 digit bracketed
      // number, so "The cohort in study [12] reported a 40 percent rate."
      // silently became "The cohort in study reported a 40 percent rate." That
      // is a lossy, undisclosed edit of synthesized answer text, which is the
      // same class of defect as fabricating one.
      //
      // Only the numbers this token actually cites are removed, taken from its
      // own citations rather than from a pattern. A bracketed number the
      // backend did not emit as a marker is prose and is left alone.
      const citedIndexes = new Set(
        cited.map((match) => (match.type === "citation" ? match.payload.display_index : -1)),
      );
      const text = event.payload.text
        .replace(/\s*\[(\d{1,3})\]/g, (whole, digits) =>
          citedIndexes.has(Number(digits)) ? "" : whole,
        )
        .trim();
      if (!text) continue;

      // A system-status note is not an assertion about biology, so it must
      // never occupy a segment on the provenance spine. Collected instead, so
      // the disclosures are still shown, just not as claims.
      if (isSystemNote(text)) {
        systemNotes.push(text);
        continue;
      }

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
        // F-4.8-D-12. This read "Cross-checked across layers", which is true of
        // any run that touched more than one and therefore tells the reader
        // nothing. The prototype states the count, so the reader can weigh it.
        // `layerCount` is computed below from the run's own tool calls; the
        // pill is pushed after it exists.
        trust.push({ kind: "plain", label: "__LAYER_COUNT__" });
      }
    }

    /*
     * The run's own account of itself (F-4.8-D-10, F-4.8-D-05).
     *
     * Built from the events in arrival order, so it reads as a log rather than
     * a summary. Timings are relative to the FIRST event rather than absolute,
     * which is what the prototype's `.tracelog` shows and the only form that
     * means anything to a reader.
     *
     * The guard's line comes from `CATEGORY_COPY`, never from
     * `guard.reason`. That field is free-form backend text, and
     * `GuardrailBanner` and `CapMessage` both refuse to render backend message
     * fields on purpose: Section 12.6's no-cost-figure rule can only be
     * guaranteed by never rendering them. F-4.8-A-15 was that leak
     * reintroduced once already. `think.narrative` and `plan.narrative` are a
     * different thing, the agent's own narration written to be shown, and the
     * prototype shows them.
     */
    const firstTs = events.length > 0 ? Date.parse(events[0]!.ts) : NaN;
    const relative = (ts: string): string | null => {
      const at = Date.parse(ts);
      if (!Number.isFinite(firstTs) || !Number.isFinite(at)) return null;
      return `${Math.max(0, (at - firstTs) / 1000).toFixed(1)}s`;
    };
    const steps: ReasoningStep[] = [];
    for (const event of events) {
      if (event.type === "guard") {
        /*
         * CATEGORY_COPY is REFUSAL copy, and its `ok` entry is a fallback
         * ("This question could not be processed"), not a description of a
         * guard that passed. The first version of this log used it for every
         * guard event, so a run that sailed through the guardrail opened its
         * own reasoning log with a refusal message. Caught by looking at the
         * rendered screen, not by any assertion.
         *
         * A passing guard gets a fixed string. A failing one still gets the
         * reviewed refusal copy, and `guard.reason` is still never rendered:
         * it is free-form backend text, and Section 12.6's no-cost-figure rule
         * can only be guaranteed by never rendering those fields.
         */
        steps.push({
          step: "Guard",
          at: relative(event.ts),
          text: event.payload.passed
            ? "In scope. The question can be grounded in NCBI records."
            : (CATEGORY_COPY[event.payload.category] ?? CATEGORY_COPY.ok),
        });
      } else if (event.type === "think" && event.payload.narrative) {
        steps.push({ step: "Think", at: relative(event.ts), text: event.payload.narrative });
      } else if (event.type === "plan" && event.payload.narrative) {
        steps.push({ step: "Plan", at: relative(event.ts), text: event.payload.narrative });
      } else if (event.type === "tool_result") {
        steps.push({
          step: "Act",
          at: relative(event.ts),
          text: `${event.payload.tool} — ${event.payload.result_count} ${
            event.payload.result_count === 1 ? "result" : "results"
          }`,
        });
      }
    }

    /*
     * DERIVED, not read. The wire's `done` payload carries `trust_outcome`,
     * `elapsed_ms`, `total_cost_usd` and `total_tool_calls`, and no status
     * word at all, so the prototype's "Answered" has to come from what the run
     * actually produced.
     *
     * A fatal error is deliberately NOT dressed up as an outcome, and a
     * refusal says so rather than claiming an answer, which is the same
     * cite-or-refuse honesty the trust pills already carry.
     */
    const OUTCOME_BY_TRUST: Record<string, string> = {
      answer: "Answered",
      flag: "Answered",
      ask: "Needs a narrower question",
      refuse: "Refused",
    };
    const outcome =
      fatalError !== undefined
        ? null
        : done && done.type === "done"
          ? (OUTCOME_BY_TRUST[done.payload.trust_outcome] ?? "Answered")
          : null;
    const elapsedMs =
      done && done.type === "done" && typeof done.payload.elapsed_ms === "number"
        ? done.payload.elapsed_ms
        : null;

    const layersUsed = new Set(toolCalls.map((call) => call.layer));
    const layerCount = layersUsed.size;
    // Resolve the triangulation pill now that the count is known (F-4.8-D-12).
    for (const signal of trust) {
      if (signal.label === "__LAYER_COUNT__") {
        signal.label = `${layerCount} ${layerCount === 1 ? "layer" : "layers"} agreed`;
      }
    }
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
      steps,
      outcome,
      elapsedMs,
      layerCount,
      landed,
      failure,
      refusal,
      capMessage,
      // The cap note is already surfaced as `capMessage`, so it is not
      // repeated here.
      systemNotes: systemNotes.filter((note) => !note.trimStart().startsWith(CAP_NOTE_PREFIX)),
      stopEnabled: deriveStopEnabled(events),
    };
  }, [events]);
}

export default useRunView;
