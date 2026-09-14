/**
 * The progress of one run: the stepper, the elapsed counter, Stop, the
 * persona caption, the tool chips, the reasoning log, and the stopped block.
 *
 * EXTRACTED FROM `RunScreen.tsx` for UI fix set 7 (R22), unchanged in
 * behaviour. The product owner's complaint was that a follow-up "goes to a
 * new page, which it should not": the answer screen was replaced wholesale
 * by the run screen, so the conversation disappeared for the length of the
 * second run. The fix renders this same progress INSIDE the answer screen,
 * under the new question and below the collapsed earlier turns.
 *
 * So this file holds the card's CONTENTS and no card of its own. Two
 * callers wrap it:
 *
 *   `RunScreen.tsx`, the full-screen first run, which supplies the page
 *   frame, the question heading and the New search button.
 *
 *   `AnswerScreen.tsx`, the inline continuation, which already renders the
 *   question heading and New search in its own header, so it passes no
 *   question and `showNewSearch={false}`. A second copy of either would be a
 *   duplicate heading and a duplicate control, and it would break the strict
 *   `New search` lookups the browser suite makes.
 *
 * Extraction rather than a second implementation is the point: there is one
 * stepper, one live region, one stopped block, so an inline run cannot drift
 * into a second visual language for progress.
 *
 * Source of truth: `docs/build/design/design-system/components/pipeline-stepper.html`
 * and `screens/streaming.html`.
 */

import { Box, Button, Typography } from "@mui/material";

import { designTokens, layerColour } from "../../theme";
import { useElapsedSeconds } from "../../hooks/useElapsedSeconds";
import { ReasoningLog } from "./ReasoningLog";
import { PersonaCaption, PersonaInfo } from "../shell/PersonaChip";

/**
 * The live step's pulse (T-6.2-05).
 *
 * The live dot already had a static ring, which distinguishes it from the
 * other four and does not distinguish a working run from a dead page. This
 * is the only element on screen that moves continuously, so across the
 * several-second gaps between step transitions there is always something
 * saying the run is alive.
 *
 * `prefers-reduced-motion` is honoured by the caller: a user who has asked
 * the system for less motion gets the static ring back, and the elapsed
 * counter still carries the liveness signal for them, which is why that
 * counter is text rather than an animation.
 */
const LIVE_PULSE = {
  "@keyframes s3-step-pulse": {
    "0%": { boxShadow: `0 0 0 0 ${designTokens.layer1Wash}` },
    "70%": { boxShadow: `0 0 0 7px rgba(0,0,0,0)` },
    "100%": { boxShadow: `0 0 0 0 rgba(0,0,0,0)` },
  },
  animation: "s3-step-pulse 1.8s ease-out infinite",
  "@media (prefers-reduced-motion: reduce)": {
    animation: "none",
    boxShadow: `0 0 0 4px ${designTokens.layer1Wash}`,
  },
} as const;

/** The five nodes of the agent loop, in order. Never a subset. */
export const STEPS = ["Guard", "Think", "Plan", "Act", "Write"] as const;
export type StepName = (typeof STEPS)[number];

export interface ToolCall {
  name: string;
  detail: string;
  layer: 1 | 2 | 3;
  /**
   * UI fix set 8 (R30, R31). The call's outcome so far, from its own
   * frames: "running" until its `tool_result` arrives, then that frame's
   * status. Optional so every fixture built before this set still
   * type-checks; absent reads as "running".
   */
  status?: "running" | "ok" | "empty" | "error";
  /** The helper scientist this call was handed to, from the wire. Null or absent: no handoff line. */
  persona?: string | null;
  personaAbout?: string | null;
  personaWikipedia?: string | null;
}

/** What each helper is doing, by layer: the sentence after the name (R31). */
export const HANDOFF_NARRATIVE: Record<1 | 2 | 3, string> = {
  1: "is searching the knowledge graph",
  2: "is checking live NCBI records",
  3: "is reading the literature and trials",
};

export interface HandoffLine {
  layer: 1 | 2 | 3;
  name: string;
  about: string | null;
  wikipedia: string | null;
  /** working until every call on the layer has landed; failed when every one errored. */
  state: "working" | "done" | "failed";
}

/**
 * One line per layer the run handed off, in layer order, from the chip list.
 *
 * UI fix set 8 (R30). Pure and exported so the derivation carries its own
 * tests. A layer appears only when at least one of its calls named a
 * helper, so an older backend that sends no persona yields an empty list
 * and the screen is exactly what it was before this set. The state is read
 * off the calls' own statuses, never off the elapsed time or the step:
 *
 *   working: at least one call on the layer has not landed
 *   failed:  every call landed and every one reported an error
 *   done:    otherwise (at least one landed ok or empty)
 *
 * An empty result is "done", not "failed": the scientist looked and found
 * nothing, which is an answer.
 */
export function deriveHandoff(toolCalls: ToolCall[]): HandoffLine[] {
  const lines: HandoffLine[] = [];
  for (const layer of [1, 2, 3] as const) {
    const calls = toolCalls.filter((call) => call.layer === layer);
    const named = calls.find((call) => typeof call.persona === "string" && call.persona.length > 0);
    if (!named || typeof named.persona !== "string") continue;
    const statuses = calls.map((call) => call.status ?? "running");
    const working = statuses.some((status) => status === "running");
    const failed = !working && statuses.every((status) => status === "error");
    lines.push({
      layer,
      name: named.persona,
      about: named.personaAbout ?? null,
      wikipedia: named.personaWikipedia ?? null,
      state: working ? "working" : failed ? "failed" : "done",
    });
  }
  return lines;
}

/** "A, B and C", "A and B", or "A": the lead's handoff sentence (R30). */
export function handoffSentence(names: string[]): string {
  if (names.length === 0) return "";
  if (names.length === 1) return `is handing off to ${names[0]}`;
  return `is handing off to ${names.slice(0, -1).join(", ")} and ${names[names.length - 1]}`;
}

/**
 * One line of the run's own account of what it did (F-4.8-D-10).
 *
 * The prototype's `.tracelog`: a timestamp, the step that produced it, and the
 * step's narrative. It is the same data behind the answer screen's `Show work`
 * disclosure, so both render this shape rather than deriving it twice.
 */
export interface ReasoningStep {
  step: StepName;
  /** Seconds since the run's first event, e.g. "1.5s". Null when not derivable. */
  at: string | null;
  text: string;
}

export interface RunProgressProps {
  /**
   * The question being run, rendered as this card's heading.
   *
   * NULL when a caller already renders the question itself, which is the
   * inline continuation on the answer screen. Two headings for one question
   * is not a style preference: the answer screen's is the `h1` a reader and
   * a screen reader both land on, and a second copy underneath it would
   * announce the same question twice.
   */
  question?: string | null;
  /** The live step, or null before the run starts or after it lands. */
  activeStep?: StepName | null;
  /**
   * Steps the run actually reached. A landed run has no live step, so without
   * this the whole stepper would read as pending the moment it finished.
   */
  reachedSteps?: StepName[];
  toolCalls?: ToolCall[];
  /**
   * The run's own account of what it did so far (F-4.8-D-10).
   *
   * The prototype's run screen carries a `REASONING` disclosure listing each
   * step with its elapsed time. Without it the stepper says WHICH step is
   * running and nothing says what any of them decided, so the agent's
   * reasoning was unreachable while the run was live and again afterwards.
   */
  steps?: ReasoningStep[];
  /** Server-assigned persona (T-4.5-10); null until the first run returns. */
  personaName?: string | null;
  /** The scientist's about line and Wikipedia address, for the caption's "i" card. */
  personaAbout?: string | null;
  personaWikipedia?: string | null;
  onStop?: () => void;
  /** Start a fresh search. */
  onNewSearch?: () => void;
  /**
   * Whether this block renders its own New search control, in the header
   * and in the stopped block.
   *
   * FALSE for the inline continuation alone, whose own screen already
   * carries New search beside the question. A second one would be two
   * controls with the same name on one page, which is a real ambiguity for
   * a reader and also breaks the strict `New search` lookups the browser
   * suite makes.
   *
   * AN EXPLICIT FLAG, not `onNewSearch !== undefined`. That inference was
   * written first and `RunScreen.stopped.test.tsx` caught it within the
   * hour: a caller that simply forgot the handler would silently lose the
   * control instead of rendering a dead one, so a missing wire and a
   * deliberate omission would look identical at the call site.
   */
  showNewSearch?: boolean;
  /**
   * Whether Stop has already latched (decision U7, requirement R45,
   * `DECISIONS.md` row 2026-09-12).
   *
   * Pressing Stop used to leave the stepper frozen mid-run with no word on
   * what happened, since `activeStep` and `startedAt` both go null but
   * nothing replaces the stepper they were driving. This prop swaps the
   * stepper and the reasoning area for an explicit "Search stopped" block
   * with a way forward, instead of a page that merely stopped moving.
   *
   * The design system has no designed "stopped" screen (checked
   * `docs/build/design/README.md`'s coverage table and
   * `design-system/prototype/app.html`), so this is built from the nearest
   * designed neighbours rather than invented: the run screen's own card,
   * the `.btn` filled blue button already used here for "New search", and
   * the `designTokens.inkMuted` body-text token used for the elapsed
   * counter above.
   */
  stopped?: boolean;
  /** Re-runs the same question unchanged (decision U7). */
  onRunAgain?: () => void;
  /**
   * Whether Stop is still meaningful.
   *
   * Derived from the run's own events by `deriveStopEnabled`, which has 19
   * tests behind it. An earlier version of this screen offered Stop
   * unconditionally, including after the run had already finished.
   */
  stopEnabled?: boolean;
  /**
   * When this run started, as `Date.now()`. Drives the elapsed counter
   * (T-6.2-05). Null before a run starts and after it lands, which is what
   * stops the counter rather than a separate flag.
   */
  startedAt?: number | null;
  /** Guardrail refusal copy, when the question was turned away. */
  refusal?: string | null;
  /** Cap copy, when the run stopped early on its processing budget. */
  capMessage?: string | null;
  /** A stream-level failure, surfaced rather than left as a silent hang. */
  failure?: string | null;
}

/**
 * A refusal or cap notice.
 *
 * Deliberately plain and free of any cost figure: the copy comes from a fixed
 * lookup table with no interpolation slot, so a dollar amount cannot reach a
 * user-facing refusal even by accident.
 */
function Notice({ testId, tone, text }: { testId: string; tone: "warn"; text: string }) {
  return (
    <Box
      data-testid={testId}
      role="status"
      sx={{
        mt: 2.25,
        px: 1.75,
        py: 1.4,
        fontSize: 13.5,
        borderRadius: 0.5,
        border: `1px solid ${designTokens.warn}`,
        borderLeftWidth: 4,
        bgcolor: tone === "warn" ? designTokens.warnWash : designTokens.surfaceSunk,
      }}
    >
      {text}
    </Box>
  );
}

export function RunProgress({
  question = null,
  activeStep = "Guard",
  reachedSteps = [],
  toolCalls = [],
  steps = [],
  personaName = null,
  personaAbout = null,
  personaWikipedia = null,
  onStop,
  onNewSearch,
  showNewSearch = true,
  stopped = false,
  onRunAgain,
  stopEnabled = true,
  startedAt = null,
  refusal = null,
  capMessage = null,
  failure = null,
}: RunProgressProps) {
  const activeIndex = activeStep ? STEPS.indexOf(activeStep) : -1;
  const reached = new Set(reachedSteps);
  const elapsed = useElapsedSeconds(startedAt);
  const running = startedAt !== null && activeStep !== null;
  // UI fix set 8 (R30): the handoff, derived from the chips' own frames.
  // Shown from Act onward while the run is live; the lead's own caption
  // reads the handoff sentence during Act only, and returns to "is writing
  // the answer" on Write, which is the coordinator writing underneath.
  const handoff = !stopped && activeStep !== null ? deriveHandoff(toolCalls) : [];
  const leadNarrative =
    activeStep === "Act" && handoff.length > 0
      ? handoffSentence(handoff.map((line) => line.name))
      : null;

  return (
    <>
      <Box
        data-testid="run-header"
        sx={{
          display: "flex",
          gap: 1.75,
          alignItems: "flex-start",
          // Wraps below 720px so the counter, Stop and New search drop under
          // the question instead of pushing the card past the screen edge:
          // measured 2026-09-13 at 390px, New search sat at 461px on a
          // 390px viewport while the page scrolled sideways.
          flexWrap: "wrap",
          pb: 2,
          mb: 2.5,
          borderBottom: `1px solid ${designTokens.line}`,
        }}
      >
        {question !== null ? (
          <Typography variant="h3" component="h1" sx={{ flex: 1 }}>
            {question}
          </Typography>
        ) : (
          // The inline continuation renders the heading itself, so this is
          // only the spacer that keeps the counter and Stop to the right.
          // `minWidth: 0` so it can give way at 390px instead of pushing
          // the controls off the card.
          <Box sx={{ flex: 1, minWidth: 0 }} />
        )}
        {running && !stopped ? (
          <Typography
            data-testid="run-elapsed"
            variant="body2"
            // aria-hidden is load-bearing, not an oversight. This value
            // changes every second, and inside a live region a screen
            // reader would read out "one second, two seconds, three
            // seconds" for the whole run and bury the step transitions
            // that carry the meaning. Those are announced separately
            // below, once per change.
            aria-hidden="true"
            sx={{
              color: designTokens.inkMuted,
              fontVariantNumeric: "tabular-nums",
              alignSelf: "center",
              minWidth: 34,
              textAlign: "right",
            }}
          >
            {elapsed}s
          </Typography>
        ) : null}
        {/* Stop and this header's own New search both disappear once
            stopped, decision U7: the stopped block below carries its own
            New search, and a second "New search" on the same screen
            breaks the `getByRole("button", { name: "New search", exact:
            true })` strict-mode lookup the browser specs use. */}
        {!stopped ? (
          <>
            <Button
              onClick={onStop}
              disabled={!stopEnabled}
              sx={{
                fontSize: 12.5,
                color: designTokens.inkMuted,
                border: `1px solid ${designTokens.lineStrong}`,
                px: 1.6,
                py: 0.6,
              }}
            >
              Stop
            </Button>
            {/* Set 2, R12: filled blue with white text, the design system's `.btn`, so it reads apart from Stop. */}
            {showNewSearch ? (
              <Button variant="contained" onClick={onNewSearch} sx={{ fontSize: 12.5, px: 1.6, py: 0.6 }}>
                New search
              </Button>
            ) : null}
          </>
        ) : null}
      </Box>

      {stopped ? (
        // Decision U7, requirement R45: Stop used to leave the stepper
        // frozen with five pending dots and nothing said. This block
        // replaces the stepper and the reasoning/tool-call area below it
        // with an explicit state and a way forward, built from the run
        // screen's own card, the `.btn` filled button already on this
        // screen, and the `designTokens.inkMuted` body token, since the
        // design system itself has no "stopped" screen to copy from.
        <Box data-testid="run-stopped" role="status" sx={{ py: 1 }}>
          <Typography variant="h3" sx={{ color: designTokens.ink }}>
            Search stopped
          </Typography>
          <Typography variant="body2" sx={{ color: designTokens.inkMuted, mt: 1, mb: 2.5 }}>
            No answer was produced. Run the same question again, or start a new one.
          </Typography>
          <Box sx={{ display: "flex", gap: 1.25 }}>
            <Button variant="contained" onClick={onRunAgain} sx={{ fontSize: 12.5, px: 1.6, py: 0.6 }}>
              Run again
            </Button>
            {showNewSearch ? (
              <Button
                variant="outlined"
                onClick={onNewSearch}
                sx={{
                  fontSize: 12.5,
                  color: designTokens.ink,
                  borderColor: designTokens.lineStrong,
                  px: 1.6,
                  py: 0.6,
                }}
              >
                New search
              </Button>
            ) : null}
          </Box>
        </Box>
      ) : (
        <>
          <Box sx={{ display: "flex", alignItems: "flex-start" }}>
            {STEPS.map((step, index) => {
              // Done if the run genuinely reached it, or if it precedes the live
              // step. The first clause is what keeps a finished run's stepper
              // truthful after activeStep goes null.
              const live = activeIndex === index;
              const done = !live && (reached.has(step) || activeIndex > index);
              return (
                <Box
                  key={step}
                  data-testid={`step-${step}`}
                  data-state={live ? "live" : done ? "done" : "pending"}
                  sx={{
                    flex: 1,
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "center",
                    gap: 1,
                    position: "relative",
                    "&::before": {
                      content: '""',
                      position: "absolute",
                      top: 7,
                      left: "-50%",
                      width: "100%",
                      height: 2,
                      bgcolor: done || live ? designTokens.blue : designTokens.line,
                      display: index === 0 ? "none" : "block",
                    },
                  }}
                >
                  <Box
                    sx={{
                      width: 16,
                      height: 16,
                      borderRadius: "50%",
                      position: "relative",
                      zIndex: 1,
                      border: "2px solid",
                      borderColor: done || live ? designTokens.blue : designTokens.lineStrong,
                      bgcolor: done ? designTokens.blue : designTokens.surface,
                      boxShadow: live ? `0 0 0 4px ${designTokens.layer1Wash}` : "none",
                      // Only the LIVE dot pulses, and only while a run is
                      // actually in flight. A landed run keeps its static
                      // ring: an animation still running after the answer
                      // arrived would say the system is working when it is
                      // not, which is the same class of lie as a progress
                      // bar that never completes.
                      ...(live && running ? LIVE_PULSE : {}),
                    }}
                  />
                  <Typography
                    variant="overline"
                    sx={{
                      fontSize: 11.5,
                      letterSpacing: "0.06em",
                      color: done || live ? designTokens.ink : designTokens.inkFaint,
                    }}
                  >
                    {step}
                  </Typography>
                </Box>
              );
            })}
          </Box>

          {/*
            The screen-reader half of T-6.2-05. The visible progress is the
            pulse and the ticking counter, and neither is announceable: one is
            an animation and the other would spam. This announces the step
            instead, once per change, which is the information a sighted user
            reads off the stepper.
          */}
          <Box
            data-testid="run-step-announcement"
            role="status"
            aria-live="polite"
            sx={{
              position: "absolute",
              // Explicit pixels, not bare numbers: in the sx prop a bare `1`
              // on width or height means 100 PERCENT, so this region was the
              // full viewport width from its own left offset and pushed the
              // page to 1521px of scroll width at 1280px (measured live on
              // 2026-09-13 while checking the scientist card). The standard
              // visually-hidden recipe wants one pixel.
              width: "1px",
              height: "1px",
              overflow: "hidden",
              clip: "rect(0 0 0 0)",
              whiteSpace: "nowrap",
            }}
          >
            {running && activeStep ? `${activeStep} step running` : ""}
          </Box>
        </>
      )}

      {/* The refusal, cap and failure Notices keep rendering regardless
          of `stopped`: none of them were part of the frozen-screen
          complaint, and a run can stop on its own cap or failure path
          before the user ever presses Stop. */}
      {refusal ? <Notice testId="guardrail-notice" tone="warn" text={refusal} /> : null}
      {capMessage ? <Notice testId="cap-notice" tone="warn" text={capMessage} /> : null}
      {failure ? <Notice testId="run-failure" tone="warn" text={failure} /> : null}

      <PersonaCaption
        name={personaName}
        step={activeStep ?? null}
        about={personaAbout}
        wikipedia={personaWikipedia}
        narrative={leadNarrative}
      />

      {/*
        UI fix set 8 (R30, R31): one line per layer the lead handed off,
        each with its layer badge and its scientist's info control.

        NO HANDOFF DESIGN EXISTS. Checked `docs/build/design/README.md`'s
        coverage table, `components/persona.html` (chip and per-step
        caption only) and `prototype/app.html` (one `.pcap` caption per
        step, no helpers). Built from the two nearest designed neighbours
        rather than invented: the persona caption above (`.pcap`: 13.5px
        muted text, bold ink name, 22px minimum height, the same
        `PersonaInfo` control) and the layer badge from
        `identity/layer-badges.html` (`.dot`: a 12px square, 3px radius,
        filled with the layer colour; `.n`: mono 11px, .06em tracking,
        bold, in the layer colour). Every value below names its token:
        `layerColour(n).main` and `.wash` for the badge, `designTokens.ink`,
        `inkMuted` and `surface` for the text and the working dot,
        `designTokens.line` for the failed dot's border. Nothing here is a
        new colour, radius or type size.

        Working versus done is the dot: outlined in the layer colour while
        the scientist is still working, filled once that layer's results
        landed, bordered in the line colour with the word "did not answer"
        when every call on the layer errored. State is exposed as
        `data-state` so a test reads the fact, not the paint.

        `flexWrap: "wrap"` on each line is what keeps 390px honest: a long
        name plus the sentence plus the info control drops the sentence
        under the badge instead of pushing the card past the screen edge.
      */}
      {handoff.length > 0 ? (
        <Box
          data-testid="handoff"
          role="list"
          aria-label="Scientists working on this search"
          sx={{ display: "flex", flexDirection: "column", gap: 0.75, mt: 1.25 }}
        >
          {handoff.map((line) => {
            const colour = layerColour(line.layer);
            const filled = line.state === "done";
            return (
              <Box
                key={line.layer}
                role="listitem"
                data-testid={`handoff-layer-${line.layer}`}
                data-state={line.state}
                sx={{
                  position: "relative",
                  display: "flex",
                  alignItems: "center",
                  flexWrap: "wrap",
                  gap: 1.2,
                  minHeight: 22,
                  pl: 0.5,
                }}
              >
                <Box
                  component="span"
                  aria-hidden="true"
                  sx={{
                    width: 12,
                    height: 12,
                    borderRadius: "3px",
                    flex: "none",
                    border: "2px solid",
                    borderColor: line.state === "failed" ? designTokens.line : colour.main,
                    bgcolor: filled ? colour.main : designTokens.surface,
                    transition: "background-color .2s ease",
                  }}
                />
                <Box
                  component="span"
                  sx={{
                    fontFamily: "ui-monospace, monospace",
                    fontSize: 11,
                    letterSpacing: "0.06em",
                    fontWeight: 700,
                    color: colour.main,
                    flex: "none",
                  }}
                >
                  L{line.layer}
                </Box>
                <Typography variant="body2" sx={{ color: designTokens.inkMuted }}>
                  <Box component="b" sx={{ fontWeight: 700, color: designTokens.ink }}>
                    {line.name}
                  </Box>{" "}
                  {HANDOFF_NARRATIVE[line.layer]}
                  {line.state === "failed" ? " · did not answer" : ""}
                </Typography>
                <PersonaInfo
                  name={line.name}
                  about={line.about}
                  wikipedia={line.wikipedia}
                  variant="onLight"
                  align="left"
                />
              </Box>
            );
          })}
        </Box>
      ) : null}

      {!stopped && toolCalls.length > 0 ? (
        <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1.25, mt: 2.25, alignItems: "center" }}>
          <Typography variant="body2" sx={{ color: designTokens.inkMuted }}>
            Querying
          </Typography>
          {toolCalls.map((call) => {
            const colour = layerColour(call.layer);
            return (
              <Box
                key={`${call.name}-${call.detail}`}
                data-testid={`tool-${call.name}`}
                data-layer={call.layer}
                sx={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 0.75,
                  fontFamily: "ui-monospace, monospace",
                  fontSize: 11.5,
                  fontWeight: 600,
                  px: 1,
                  py: 0.4,
                  borderRadius: 0.5,
                  border: `1px solid ${designTokens.line}`,
                  borderLeft: `4px solid ${colour.main}`,
                  bgcolor: colour.wash,
                }}
              >
                {call.name}
                <Box component="span" sx={{ color: designTokens.inkMuted, fontWeight: 400 }}>
                  {call.detail}
                </Box>
              </Box>
            );
          })}
        </Box>
      ) : null}

      {/* The reasoning log, F-4.8-D-10. Same component as the answer
          screen's `Show work`, so the two cannot drift apart. */}
      {!stopped && steps.length > 0 ? (
        <Box sx={{ mt: 2.5 }}>
          <Typography
            component="p"
            sx={{
              fontSize: 10.5,
              letterSpacing: ".12em",
              textTransform: "uppercase",
              fontWeight: 700,
              color: designTokens.inkFaint,
              m: 0,
              mb: 1,
            }}
          >
            Reasoning
          </Typography>
          <ReasoningLog steps={steps} />
        </Box>
      ) : null}
    </>
  );
}

export default RunProgress;
