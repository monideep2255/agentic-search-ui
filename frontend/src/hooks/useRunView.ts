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
  // 2026-09-05 no-data-refusal fix. `_build_repair_cap_note`
  // (`core/graph.py`) is a fourth system note, the same DISCLOSURE shape as
  // its three siblings above, and it matched none of them: it rendered as
  // an uncited grey claim on the provenance spine the same day this list's
  // brittleness as a classification mechanism was the reason the no-data
  // refusal below no longer uses a prefix list at all. Kept here anyway,
  // because this note genuinely has no better signal on the wire, unlike
  // the refusal case: it ships inside the normal grounded-answer branch,
  // alongside real citations, so there is no scope="answer" trust_signal
  // to key off. A prefix stays the only option for this one note.
  "Note: this answer's completeness check could not run to the end",
];

const isSystemNote = (text: string) =>
  SYSTEM_NOTE_PREFIXES.some((prefix) => text.trimStart().startsWith(prefix));
import type { ReasoningStep, StepName, ToolCall } from "../components/screens/RunScreen";
import type { Claim, Source, TrustSignal } from "../components/screens/AnswerScreen";

/**
 * How a source reads on a citation chip and a source card.
 *
 * T-4.16-03. The deployed demo rendered "MedGen MedGen:C0346153", against a
 * design card that says "MedGen C0677776". This was a plain
 * `${source} ${source_id}` join, and it is wrong for exactly one of the two
 * shapes the wire actually carries, so it looked right wherever anyone
 * checked it:
 *
 * - Layer 2 (`tools/ncbi_efetch.py`) sends the NCBI database name and the
 *   bare record id: `source: "gene"`, `source_id: "672"`. Joining gives
 *   "gene 672", which is correct.
 * - Layer 1 (`core/graph.py`'s `_citation_from_row`) sends the CURIE PREFIX
 *   and the FULL CURIE: `source: "MedGen"`, `source_id: "MedGen:C0346153"`.
 *   Joining repeats the prefix.
 *
 * NEITHER PRODUCER IS WRONG, which is why the fix is here. `core/graph.py`
 * documents its choice deliberately: "the CURIE prefix names the source
 * database, the full CURIE is the source id", and `source_id` being a
 * resolvable CURIE is what makes a Layer 1 citation traceable. Changing it
 * to a bare local id to suit a label would trade a provenance field for a
 * display convenience, which is the wrong direction in a system whose whole
 * argument is that a citation can be followed.
 *
 * So the redundancy is removed at the point of display only, and only when
 * the id genuinely repeats the source: `source_id` is stripped of a leading
 * `source:` prefix, compared case-insensitively because the two fields are
 * assembled by different modules and nothing guarantees they agree on case.
 *
 * DELIBERATELY NOT NORMALISED: the case of `source` itself. Layer 2 sends
 * "gene" and the design card shows "Gene". Capitalising would be right for
 * that one value and wrong for the next, since this field also carries
 * "dbSNP" and "MedGen", whose casing is meaningful and would survive a
 * naive title-case only by accident. Guessing a display rule for values
 * this function has not seen is how the next wrong label ships. Recorded in
 * `tracker/phase_4.16.md` for the design card to settle.
 *
 * MUTATION-PROVEN before commit. Restoring the plain join reproduces the
 * deployed string exactly, "MedGen MedGen:C0346153", and turns TWO of the
 * five arms in `useRunView.sourceName.test.ts` red while THREE stay green.
 * Those three are the Layer 2 and non-matching-prefix cases, which is to
 * say: a test covering only the shape someone happened to check would have
 * passed on the broken code.
 */
export function sourceDisplayName(source: string, sourceId: string): string {
  const prefix = `${source}:`;
  const deduped = sourceId.toLowerCase().startsWith(prefix.toLowerCase())
    ? sourceId.slice(prefix.length)
    : sourceId;
  return `${source} ${deduped}`.trim();
}

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
   * T-6.2-08. The backend's offer of somewhere to go next, or null.
   *
   * Read from the `done` payload, where it is OPTIONAL: a backend that
   * predates this field omits it, so absent and null must behave
   * identically and the `?? null` below is what guarantees that.
   */
  nextStep: string | null;
  /** How the outcome word should read: a success, a caution, or a refusal. */
  outcomeTone: "good" | "warn" | "risk" | null;
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
  nextStep: null,
  outcomeTone: null,
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
        name: sourceDisplayName(payload.source, payload.source_id),
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
    // A NO-DATA refusal, 2026-09-05 product-owner decision.
    //
    // WHAT WENT WRONG. `write_node` (`core/graph.py`) has two sites that
    // decide it cannot honestly answer: the unresolved-entity early exit
    // (an entity never resolved) and the general `trust_outcome == "refuse"`
    // branch (synthesis ran but produced nothing citeable). Both emit the
    // refusal sentence as an ordinary `token` event, so with no other
    // signal it fell through the claims loop below exactly like a real
    // narrative sentence and rendered as ONE UNCITED GREY CLAIM on the
    // provenance spine, the one surface whose entire job is to show a claim
    // next to the source that backs it. A refusal has no source to show.
    //
    // CLASSIFICATION MECHANISM CHOSEN: a `trust_signal` event whose
    // `scope === "answer"` and `outcome === "refuse"`. Rejected the obvious
    // alternative, adding the refusal sentence's opening words to
    // `SYSTEM_NOTE_PREFIXES` above, for the reason that list already
    // demonstrates: a fourth system note, `_build_repair_cap_note`, was
    // added to the backend without a matching prefix here and rendered as
    // an uncited claim the same day this fix was written, and a prefix list
    // is a bet that nobody reworks a sentence without knowing this file
    // depends on its exact opening words. The `trust_signal` fields are not
    // prose: `TrustSignalPayload.scope`, `.outcome`, `.message` and
    // `.fallback_link` are a typed, schema-validated contract
    // (`contracts/events.py`, Section 8.4's refuse payload, additive since
    // build phases 2.2 and 4.3), and both refusal sites already emit one,
    // proven by reading `core/graph.py` rather than guessing: the
    // unresolved-entity branch at its `sink.emit("trust_signal", ...
    // scope="answer")` call, and the general refuse branch at its own
    // `scope="answer"` call a few hundred lines later. No third site emits
    // a bare refusal token without this signal: the two `HarnessCallError`
    // early exits ship `error` plus `done`, never a `token`, so they cannot
    // reach the claims loop at all.
    //
    // Exhaustiveness this relies on: within `write_node`, the branch that
    // emits `scope="answer"` with `outcome="refuse"` is mutually exclusive
    // with the branch that emits real narrative tokens (`if trust_outcome
    // == "refuse": ... else: for chunk in _narrative_chunks(...): ...`), so
    // a run carrying this signal never also carries a genuine claim. Every
    // token in such a run IS the refusal, in full, which is why the loop
    // below skips all of them rather than trying to tell a refusal token
    // apart from a claim token one at a time.
    const answerRefusalSignal = events.find(
      (event): event is Extract<AgentEvent, { type: "trust_signal" }> =>
        event.type === "trust_signal" &&
        event.payload.scope === "answer" &&
        event.payload.outcome === "refuse",
    );

    const claims: Claim[] = [];
    const systemNotes: string[] = [];
    for (const event of events) {
      if (event.type !== "token") continue;
      // The whole point of `answerRefusalSignal`: none of this run's tokens
      // are a claim, so none are added to the spine or to `systemNotes`
      // either. The refusal text itself is rendered through `refusal`
      // below, from the trust_signal's own `message` and `fallback_link`
      // fields, never from this token's text.
      if (answerRefusalSignal) continue;
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
    /*
     * Counted from the SOURCES, not the tool calls (F-4.9-A-05, F-4.9-A-06),
     * and computed HERE because the trust block below needs it: a pill
     * claiming agreement must know how many layers there were to agree.
     */
    const layerCountFromSources = new Set(sources.map((source) => source.layer)).size;

    const trustEvents = events.filter((event) => event.type === "trust_signal");
    const trust: TrustSignal[] = [];
    /*
     * F-4.9-A-01 and F-4.9-A-02, both critical, both about what SILENCE means.
     *
     * A-01: a run that died fatally kept whatever positive verdict it had
     * emitted before dying, so "Grounded · every claim cited" sat over a
     * crashed, partial answer. This is build phase 4.1's closed critical, whose
     * fix was to floor the top-level trust signal on any fatal or cancelled
     * run, reintroduced here at the UI layer. The verdict is floored the same
     * way, and the positive signals are dropped rather than shown alongside.
     *
     * A-02: a run that emitted NO trust signal at all rendered no pill at all,
     * so a dropped or never-emitted event turned the guarded state into the
     * unguarded one silently. In a cite-or-refuse system the absence of a
     * grounding verdict must read as "not verified", never as no comment.
     */
    if (fatalError !== undefined) {
      trust.push({
        kind: "risk",
        label: "Not verified · the run did not finish",
      });
    } else if (trustEvents.length === 0 && landed) {
      trust.push({
        kind: "risk",
        label: "Not verified · no grounding check was recorded",
      });
    } else if (trustEvents.length > 0) {
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
      // T-4.3-05 (build phase 4.3): the backend now emits "unknown" for a
      // refusal path where no risk assessment ever ran (`core/graph.py`'s
      // two refusal sites and `adapters/mcp/server.py`'s fully-silent
      // fallback, closing F-4.1-J3-02), never a hardcoded "low". "unknown"
      // is therefore an EXPECTED value now, distinct from a genuinely
      // elevated tier the F-4.8-A-19 comment above was written to over-
      // report on. Before this fix, "unknown" !== "low" would have pushed
      // a spurious "unknown risk claim" pill on every refusal, alongside
      // the "Not fully grounded" pill the `grounded: false` branch above
      // already pushes for the same run; that pairing would have implied
      // an assessed elevated risk where none was ever computed. Excluding
      // it here restores the pre-existing display for a refusal (only
      // "Not fully grounded") while still over-reporting, unchanged, for
      // any OTHER unrecognised string a future backend value might send.
      if (payload.risk_tier && payload.risk_tier !== "low" && payload.risk_tier !== "unknown") {
        trust.push({ kind: "risk", label: `${payload.risk_tier} risk claim` });
      }
      // R-01: "agreed" needs at least two things to agree. The A-05 fix moved
      // the nonsense rather than removing it, so "0 layers agreed" was still
      // reachable, now from a run that queried layers and cited nothing.
      if (payload.triangulated === true && layerCountFromSources >= 2) {
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
      /*
       * T-4.16-03. Was "Needs a narrower question", which described the
       * wrong thing entirely and was seen on the live demo above a grounded
       * answer carrying five resolving citations. The question was fine.
       *
       * `ask` does not mean the question was too broad. Locked spec section
       * 8.3.3, in its own words: "Ask is reserved for a high-stakes claim
       * resting on a single independent-origin source. It errs toward
       * caution rather than a confident answer." It is the
       * `(high, grounded, insufficient)` row of `synthesis/trust.py`'s
       * DECISION_TABLE: the claim IS grounded, and the layers could not be
       * compared against each other, so triangulation is unavailable rather
       * than failed.
       *
       * Telling a reader to narrow their question is therefore not merely
       * unhelpful, it misattributes the caution to something they did. On a
       * product whose entire argument is that its status line can be
       * believed, a status line that blames the reader for the evidence is
       * a trust defect rather than a copy nit.
       *
       * The wording states the evidence, matching the neighbouring pills,
       * which all report rather than instruct. Product-owner decision,
       * 2026-08-25: the trust-pills design card has NO `ask` state, so
       * there was nothing to build against and this was settled directly.
       * `tracker/phase_4.16.md` records it for the card to absorb.
       */
      ask: "Single source, not independently confirmed",
      refuse: "Refused",
    };
    /*
     * The AFFORDANCE each outcome deserves (F-4.9-A-03, critical).
     *
     * The screen rendered `✓ {outcome}` in the success green for all four, so
     * a refusal read "✓ Refused" and an ask-back read "✓ Needs a narrower
     * question", both ticked and both green. A green tick beside "Refused" is
     * the single most misread pair on this screen: at a glance it says "done,
     * fine". Carried here rather than in the component so the mapping lives
     * beside the words it dresses.
     */
    const OUTCOME_TONE: Record<string, "good" | "warn" | "risk"> = {
      answer: "good",
      flag: "good",
      ask: "warn",
      refuse: "risk",
    };
    const outcome =
      fatalError !== undefined
        ? null
        : done && done.type === "done"
          ? (OUTCOME_BY_TRUST[done.payload.trust_outcome] ?? "Answered")
          : null;
    const outcomeTone =
      fatalError !== undefined || !done || done.type !== "done"
        ? null
        : (OUTCOME_TONE[done.payload.trust_outcome] ?? "good");
    const elapsedMs =
      done && done.type === "done" && typeof done.payload.elapsed_ms === "number"
        ? done.payload.elapsed_ms
        : null;
    // T-6.2-08. `?? null` rather than a truthiness check, so an offer is
    // read when present and absent and null collapse to the same thing.
    const nextStep =
      done && done.type === "done" && typeof done.payload.next_step === "string"
        ? (done.payload.next_step ?? null)
        : null;

    /*
     * Counted from the SOURCES, not the tool calls (F-4.9-A-05, F-4.9-A-06).
     *
     * Two defects came from counting tool calls. A run whose citations arrive
     * without `tool_result` events printed "0 layers agreed" beside source
     * cards from two different layers. And a run that queried three layers but
     * found citations in two put "3 layers" in the status strip directly above
     * source cards showing two, contradicting itself on one screen.
     *
     * "How many layers agreed" is a claim about the ANSWER's grounding, so it
     * has to be counted from what actually grounded the answer. The tools a
     * run ran and found nothing in are still visible in the reasoning log,
     * which is where a record of work belongs.
     */
    const layerCount = layerCountFromSources;
    // Resolve the triangulation pill now that the count is known (F-4.8-D-12).
    for (const signal of trust) {
      if (signal.label === "__LAYER_COUNT__") {
        signal.label = `${layerCount} ${layerCount === 1 ? "layer" : "layers"} agreed`;
      }
    }
    /*
     * Each figure NAMES what it counts (F-4.9-R-02).
     *
     * The tools figure counts calls the run made; the layers figure counts
     * layers the answer actually rests on. Those are different bases, and the
     * old wording put them side by side as bare nouns, so "4 tools · 2 layers"
     * read as a contradiction of the reasoning log directly above it. Saying
     * "from N layers" ties the layer count to the sources it describes.
     */
    const meta = landed
      ? `${toolCalls.length} ${toolCalls.length === 1 ? "tool" : "tools"} · ` +
        `${sources.length} ${sources.length === 1 ? "source" : "sources"}` +
        (sources.length > 0
          ? ` from ${layerCount} ${layerCount === 1 ? "layer" : "layers"}`
          : "")
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
    /*
     * A curated string per fatal CLASS (F-4.9-R-03).
     *
     * The F-4.9-A-01 fix collapsed every fatal error onto one sentence, so a
     * run the USER stopped was told "This run could not be completed. Try
     * asking again", which is both wrong and faintly accusatory. `error_class`
     * is a four-value Literal on the wire (`contracts/events.py`), a closed
     * enum carrying no free text, so branching on it keeps the no-backend-text
     * guarantee that fix was about while restoring the distinction it lost.
     */
    const FATAL_COPY: Record<string, string> = {
      cancelled: "This run was stopped before it finished, so no answer was written.",
      transient: "This run could not be completed. Try asking again in a moment.",
      recoverable: "This run could not be completed. Try asking again, or rephrase the question.",
      unexpected: "This run could not be completed. Try asking again, or rephrase the question.",
    };
    const failure =
      fatalError && fatalError.type === "error"
        ? (FATAL_COPY[fatalError.payload.error_class] ?? FATAL_COPY.unexpected)
        : null;

    const failedGuard = events.find(
      (event) => event.type === "guard" && event.payload.passed === false,
    );
    // The two refusal shapes read identically from here down (2026-09-05
    // product-owner decision): both set `refusal`, both render through the
    // same `Notice` in `RunScreen` and `AnswerScreen` (`data-testid=
    // "guardrail-notice"` / `"answer-refusal"`), and neither's text can
    // reach the claims list, since a guardrail refusal never emits a
    // `token` at all and a no-data refusal's tokens were removed from
    // `claims` above.
    //
    // Guardrail copy stays exactly as it was: a fixed, interpolation-free
    // table keyed on `category`, never the backend's free-form `reason`.
    // The no-data refusal has no such table, because the sentence itself
    // (unresolved entity, withdrawn record, no groundable finding) is the
    // content, not a category to look up; it is read from the
    // `answerRefusalSignal` trust_signal's own `message` and
    // `fallback_link` fields rather than from the token text, for the
    // reason given at `answerRefusalSignal`'s definition above. Joined
    // with one space, the same join `synthesis/refuse.py`'s
    // `build_refusal_text` and `core/graph.py`'s
    // `_build_unresolved_entity_refusal_text` both use to build the token
    // text this is standing in for, so the rendered sentence reads the
    // same either way.
    const refusal =
      failedGuard && failedGuard.type === "guard"
        ? (CATEGORY_COPY[failedGuard.payload.category] ?? CATEGORY_COPY.ok)
        : answerRefusalSignal && answerRefusalSignal.type === "trust_signal"
          ? [answerRefusalSignal.payload.message, answerRefusalSignal.payload.fallback_link]
              .filter((part): part is string => typeof part === "string" && part.length > 0)
              .join(" ") || null
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
      outcomeTone,
      elapsedMs,
      nextStep,
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
