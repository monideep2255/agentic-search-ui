/**
 * The guided onboarding tour, product-owner request of 2026-09-13: "for a
 * first-time user, a guided onboarding that walks them through all the
 * features that are available and gets them to do a query and see the
 * answer in the end, so people have a complete tour."
 *
 * THE ONE DESIGN DECISION THAT SHAPES EVERYTHING HERE: the tour is
 * NON-BLOCKING and is never started for the visitor. Two reasons, both
 * load-bearing.
 *
 *   1. A visitor who came to search must not be trapped. The dimmed backdrop
 *      and the highlight ring are `pointer-events: none`, so the page under
 *      them stays fully usable while the tour is up; only the card itself
 *      takes clicks. There is no focus trap and no `aria-modal`, because the
 *      card is a coach mark beside the product, not a modal in front of it.
 *   2. Every browser spec enters the app in a fresh context and would
 *      otherwise meet an auto-started tour on every run.
 *
 * So a first visit shows a small invite card on the home screen
 * (`TourInvite`), the home screen's footer strip carries a permanent "Take
 * the tour" link, and the tour itself opens only from one of those two.
 * Dismissing the invite or finishing the tour writes `TOUR_SEEN_KEY` to
 * `localStorage`, so the invite never returns; the footer link always works.
 *
 * WHERE THE STATE LIVES. `App.tsx` owns `open` and `step`, passes them down,
 * and derives `runState` and `outcome` from the same `searchView` and
 * `view` it renders every screen from. This component never reads the
 * agent's event stream itself, which keeps the F-4.8-J-01 rule intact: the
 * tour describes the answer on screen, it never produces one.
 *
 * HOW A STEP FINDS ITS TARGET. Each step names one or more `data-tour`
 * attributes (`search-box`, `depth`, `seeds`, `persona`, `nav`, `login`,
 * `answer`, `citations`, `sources`, `followup`) that `HomeScreen.tsx`,
 * `AppShell.tsx`, `AnswerScreen.tsx` and `FollowUp.tsx` carry on the
 * existing elements. The first attribute that resolves to a visible element
 * wins; a step whose target is absent (the persona chip below 900px, the
 * Sources disclosure on an answer with no sources) shows its card with no
 * ring rather than failing. Targets are located by attribute rather than by
 * accessible name so the product's copy can change without the tour
 * pointing at nothing.
 *
 * STEP 7 IS THE ONE THAT ACTS. It asks `App` to fill the question box with
 * `TOUR_QUESTION` and offers "Run it for me", which calls the SAME `ask`
 * every other surface uses. While the run is on the progress screen the
 * tour shows a short watching note docked at the bottom, well clear of the
 * Stop button in the run card's header, and it advances to step 8 on its
 * own when the answer lands. If the system refuses (it does so about one
 * time in three for this question today, a known defect owned by a later
 * fix set), step 8 says so in plain words and ends the tour, because a
 * refusal is by design and not something the tour should apologise for.
 *
 * DESIGN. No coach-mark surface exists in the design system
 * (`docs/build/design/README.md`'s coverage table), so per the repository's
 * design-consistency rule this is built from the nearest designed neighbour
 * and the foundations, and the derivation is stated:
 * the card reuses the account menu popover's surface, border, radius and
 * shadow (`AccountMenu.tsx`); the highlight ring is `designTokens.link`,
 * the same colour the search bar's focus border takes; the invite card is
 * the `GuestAllowance.tsx` centred card; the dim is `designTokens.ink` at
 * 45 percent, computed from the token rather than written as a literal.
 * The phone layout follows `prototype/app.html`'s 720px breakpoint: below
 * it the card docks to the bottom edge at full width.
 */

import type React from "react";
import { useEffect, useId, useRef, useState } from "react";
import type { KeyboardEvent as ReactKeyboardEvent } from "react";
import { Box, Button, Typography, useMediaQuery } from "@mui/material";

import { designTokens } from "../../theme";
import { InfoIcon } from "../shell/PersonaChip";

/** The per-browser flag that hides the first-visit invite for good. */
export const TOUR_SEEN_KEY = "agentic-search-ui.tour-seen.v1";

/** The question step 7 fills in and "Run it for me" sends. */
export const TOUR_QUESTION = "Which diseases are associated with BRCA1?";

/** The design's phone breakpoint, `prototype/app.html:403`. */
const NARROW_QUERY = "(max-width:720px)";

/** Whether this browser has dismissed the invite or finished the tour. */
export function hasSeenTour(): boolean {
  try {
    return window.localStorage.getItem(TOUR_SEEN_KEY) === "1";
  } catch {
    // Storage unreachable: the invite shows again, which costs a click and
    // nothing else. Failing open is the right direction for an invitation.
    return false;
  }
}

/** Remember that the invite was dismissed or the tour finished. */
export function markTourSeen(): void {
  try {
    window.localStorage.setItem(TOUR_SEEN_KEY, "1");
  } catch {
    // Storage unreachable. The invite simply shows again on the next load,
    // the same degradation `lib/guestSession.ts` accepts for its own flags.
  }
}

/** Where the run the tour is watching has got to, derived by `App`. */
export type TourRunState = "idle" | "running" | "answered";

/** What the answer screen is showing, once `runState` is `answered`. */
export type TourOutcome = "answer" | "refusal" | "failure";

export interface TourStep {
  id: string;
  title: string;
  /**
   * Two or three plain sentences, one paragraph each. The token `{{info}}`
   * renders as the circled "i" icon the chip itself uses, so a sentence can
   * point at the control by showing it rather than by spelling it.
   */
  body: string[];
  /** `data-tour` values, in preference order. Empty means no ring. */
  targets: string[];
}

/**
 * A sentence with its `{{info}}` tokens swapped for the chip's own circled
 * "i", drawn inline at text size. Anything else renders as written.
 */
function renderSentence(sentence: string): React.ReactNode {
  const parts = sentence.split("{{info}}");
  if (parts.length === 1) return sentence;
  return parts.flatMap((part, index) =>
    index === 0
      ? [part]
      : [
          <Box
            key={`info-${index}`}
            component="span"
            aria-label="circled i"
            role="img"
            sx={{
              display: "inline-flex",
              verticalAlign: "-2px",
              color: designTokens.ink,
              mx: "1px",
            }}
          >
            <InfoIcon size={14} />
          </Box>,
          part,
        ],
  );
}

/** Index of the step that runs a question. Everything before it is reading. */
export const RUN_STEP_INDEX = 6;

/**
 * The nine steps, in order. Step 8's copy branches on the run's outcome and
 * lives in `outcomeStep` below; the entry here is the cited-answer branch.
 */
export const TOUR_STEPS: TourStep[] = [
  {
    id: "welcome",
    title: "Welcome to NCBI Agentic Search",
    body: [
      "Ask a biomedical question in plain words. The answer is built from the NCBI knowledge graph and from live NCBI APIs, queried as you ask.",
      "Every claim carries a numbered source you can open. When the records do not support an answer, the system says so rather than guessing.",
    ],
    targets: [],
  },
  {
    id: "search-box",
    title: "The question box",
    body: [
      "Type your question here. Enter sends it, and Shift+Enter starts a new line.",
      "The arrow button sends it too. A question can run to about 2,000 characters.",
    ],
    targets: ["search-box"],
  },
  {
    id: "depth",
    // UI fix set 9 (2026-09-14): two modes, worded as the mode control's own
    // info card (`ANSWER_MODE_EXPLAINER` in `controls/DepthControl.tsx`).
    title: "Answer mode",
    body: [
      "Plain language, the default, is written for a reader with no biology background, in everyday words. Researcher is for someone who knows the field and NCBI, with the specifics and the records listed.",
      "The sources stay the same in both modes, and every claim is cited. A change applies to your next question.",
    ],
    targets: ["depth"],
  },
  {
    id: "seeds",
    title: "Seed questions",
    body: [
      "Not sure where to start? These four are real questions from the evaluation set.",
      "Click one and it runs as written, at the depth you chose.",
    ],
    targets: ["seeds"],
  },
  {
    id: "persona",
    title: "Your scientist",
    body: [
      "Each session works as a scientist from the history of biomedical science. It is decoration only and changes nothing about the answer.",
      "The {{info}} beside the name tells you who they were, with a link to read more. On a phone the name sits behind the bar's menu.",
    ],
    targets: ["persona"],
  },
  {
    id: "nav",
    title: "The app bar",
    body: [
      "Integrations lists the other ways in: the API, GraphQL, the command line and the export. About explains how the system works.",
      "Log in keeps your search history across reloads. On a phone the history opens as a drawer from the bar.",
    ],
    targets: ["nav", "login"],
  },
  {
    id: "run",
    title: "Now run one",
    body: [
      "The question box holds a real question, ready to send. Press the arrow to send it, or let the tour send it for you.",
      "The next screen shows the five steps the system takes: Guard, Think, Plan, Act and Write.",
    ],
    targets: ["search-box"],
  },
  {
    id: "citations",
    title: "Citations",
    body: [
      "Each numbered chip beside a sentence is a source. Click one and its record opens below. The colour of its left edge says which layer it came from: graph, live API, or literature.",
      "The line under the answer says how far to trust it, and Show work opens the steps the system took.",
    ],
    targets: ["citations", "answer"],
  },
  {
    id: "sources",
    title: "Sources and follow-up",
    body: [
      "Open Sources to see every record behind the answer. Each card links to the NCBI record it came from.",
      "The follow-up field carries the conversation forward, so the next question builds on this one.",
    ],
    targets: ["sources", "followup"],
  },
];

export const TOUR_STEP_COUNT = TOUR_STEPS.length;

/** Step 8 when the run did not produce a cited answer. */
const REFUSAL_STEP: TourStep = {
  id: "refusal",
  title: "This time the system refused",
  body: [
    "This time the system refused rather than guess; that is by design. The records did not support an answer it could cite.",
    "Run it again from the home page, or ask another question. The tour ends here.",
  ],
  targets: ["answer"],
};

const FAILURE_STEP: TourStep = {
  id: "failure",
  title: "The run did not finish",
  body: [
    "The question could not be completed this time. The message above says what happened.",
    "Run it again from the home page. The tour ends here.",
  ],
  targets: ["answer"],
};

/** The step to show at `index`, given what the answer screen is showing. */
export function stepAt(index: number, outcome: TourOutcome | null): TourStep {
  if (index === RUN_STEP_INDEX + 1) {
    if (outcome === "refusal") return REFUSAL_STEP;
    if (outcome === "failure") return FAILURE_STEP;
  }
  return TOUR_STEPS[Math.min(Math.max(index, 0), TOUR_STEP_COUNT - 1)];
}

/**
 * A token colour with an alpha channel, computed rather than written, so no
 * rgba literal has to restate a hex the design system already owns.
 */
function withAlpha(hex: string, alpha: number): string {
  const value = hex.replace("#", "");
  const r = parseInt(value.slice(0, 2), 16);
  const g = parseInt(value.slice(2, 4), 16);
  const b = parseInt(value.slice(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

/**
 * Transcribed from `AccountMenu.tsx`'s popover, the nearest designed
 * neighbour for a small lifted card: the same surface, border, radius and
 * shadow, so the tour card reads as the same family of control.
 */
const POPOVER_SURFACE = {
  bgcolor: designTokens.surface,
  border: `1px solid ${designTokens.line}`,
  borderRadius: 1,
  boxShadow: "0 14px 34px rgba(0,0,0,.2)",
  color: designTokens.ink,
} as const;

/** A rect worth drawing: jsdom and a display-none element both measure 0. */
function usableRect(rect: DOMRect | null): DOMRect | null {
  return rect && rect.width > 0 && rect.height > 0 ? rect : null;
}

/**
 * Find the first target that actually occupies space. An empty claims grid
 * on an answer with no claims is present in the DOM and zero pixels tall,
 * so presence alone is not the test; the step's next target is.
 */
function findTarget(targets: string[]): HTMLElement | null {
  for (const name of targets) {
    const candidates = document.querySelectorAll<HTMLElement>(`[data-tour="${name}"]`);
    for (const el of Array.from(candidates)) {
      if (usableRect(el.getBoundingClientRect())) return el;
    }
  }
  return null;
}

/**
 * The target's viewport rectangle, kept current across scroll, resize and
 * layout changes while the step is showing.
 */
function useTargetRect(targets: string[], active: boolean): DOMRect | null {
  const [rect, setRect] = useState<DOMRect | null>(null);
  const key = targets.join("|");

  useEffect(() => {
    if (!active) {
      setRect(null);
      return undefined;
    }
    let frame = 0;
    const measure = () => {
      const el = findTarget(targets);
      setRect(el ? usableRect(el.getBoundingClientRect()) : null);
    };
    const el = findTarget(targets);
    if (el && typeof el.scrollIntoView === "function") {
      const reduce =
        typeof window.matchMedia === "function" &&
        window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      el.scrollIntoView({ block: "center", behavior: reduce ? "auto" : "smooth" });
    }
    measure();
    // A second measurement after the scroll above has settled; `smooth`
    // scrolling finishes well after the first paint.
    const settle = window.setTimeout(measure, 350);
    const onChange = () => {
      if (typeof window.requestAnimationFrame !== "function") {
        measure();
        return;
      }
      window.cancelAnimationFrame(frame);
      frame = window.requestAnimationFrame(measure);
    };
    window.addEventListener("resize", onChange);
    window.addEventListener("scroll", onChange, true);
    const observer =
      typeof ResizeObserver === "function" ? new ResizeObserver(onChange) : null;
    observer?.observe(document.body);
    return () => {
      window.clearTimeout(settle);
      if (typeof window.cancelAnimationFrame === "function") window.cancelAnimationFrame(frame);
      window.removeEventListener("resize", onChange);
      window.removeEventListener("scroll", onChange, true);
      observer?.disconnect();
    };
    // `key` stands in for `targets`, which is a fresh array on every render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, key]);

  return rect;
}

export interface TourInviteProps {
  onStart?: () => void;
  onDismiss?: () => void;
}

/**
 * The first-visit card on the home screen. Built on `GuestAllowance.tsx`'s
 * centred-card precedent: `surface` on `canvas`, a `line` border, the
 * theme's radius, no shadow (a data surface, not a lifted one).
 */
export function TourInvite({ onStart, onDismiss }: TourInviteProps) {
  return (
    <Box
      data-testid="tour-invite"
      sx={{
        maxWidth: 720,
        mx: "auto",
        mt: 3,
        px: 2.25,
        py: 1.5,
        display: "flex",
        flexWrap: "wrap",
        alignItems: "center",
        justifyContent: "center",
        gap: 1.25,
        bgcolor: designTokens.surface,
        border: `1px solid ${designTokens.line}`,
        borderRadius: 1,
        textAlign: "left",
      }}
    >
      <Typography sx={{ fontSize: 14, color: designTokens.ink, flex: "1 1 220px" }}>
        <Box component="b" sx={{ fontWeight: 700 }}>
          New here?
        </Box>{" "}
        Take the two-minute tour: every feature, then a real question with its answer.
      </Typography>
      <Box sx={{ display: "flex", gap: 0.75, alignItems: "center", flex: "none" }}>
        <Button variant="contained" onClick={onStart} sx={{ fontSize: 13, px: 1.6, py: 0.6 }}>
          Start the tour
        </Button>
        <Button onClick={onDismiss} sx={{ fontSize: 13, color: designTokens.inkMuted, px: 1.2 }}>
          Not now
        </Button>
      </Box>
    </Box>
  );
}

export interface OnboardingTourProps {
  open: boolean;
  /** Zero-based step index; `App` owns it. */
  step: number;
  onStepChange: (step: number) => void;
  /** Skip or Done. The caller marks the tour seen and closes it. */
  onClose: () => void;
  runState: TourRunState;
  outcome: TourOutcome | null;
  /** "Run it for me": the caller sends `TOUR_QUESTION` through `ask`. */
  onRunForMe?: () => void;
}

export function OnboardingTour({
  open,
  step,
  onStepChange,
  onClose,
  runState,
  outcome,
  onRunForMe,
}: OnboardingTourProps) {
  const narrow = useMediaQuery(NARROW_QUERY, { noSsr: true });
  const titleId = useId();
  const bodyId = useId();
  const cardRef = useRef<HTMLDivElement | null>(null);
  const returnFocusTo = useRef<HTMLElement | null>(null);

  const watching = open && runState === "running";
  const current = stepAt(step, outcome);
  const rect = useTargetRect(current.targets, open && !watching);

  /*
   * Auto-advance. A run that starts before step 7 (a seed chip clicked
   * mid-tour) jumps the tour to step 7 so the watching note and the answer
   * steps still follow; an answer landing while step 7 is showing moves to
   * step 8. Both are effects of state `App` derived, never of this
   * component reading the stream.
   */
  useEffect(() => {
    if (!open) return;
    if (runState !== "idle" && step < RUN_STEP_INDEX) onStepChange(RUN_STEP_INDEX);
    else if (runState === "answered" && step === RUN_STEP_INDEX) onStepChange(RUN_STEP_INDEX + 1);
  }, [open, runState, step, onStepChange]);

  /* Focus moves into the card on open and on every step; it returns on close. */
  useEffect(() => {
    if (open) {
      if (returnFocusTo.current === null) {
        returnFocusTo.current = document.activeElement as HTMLElement | null;
      }
      cardRef.current?.focus();
      return;
    }
    const previous = returnFocusTo.current;
    returnFocusTo.current = null;
    if (previous && typeof previous.focus === "function" && document.contains(previous)) {
      previous.focus();
    }
  }, [open, step, watching]);

  /*
   * Escape skips the tour from anywhere on the page, not only while the card
   * holds focus: the visitor is free to click into the page under the tour,
   * and Escape must still be the way out afterwards.
   */
  useEffect(() => {
    if (!open) return undefined;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  const isRunStep = step === RUN_STEP_INDEX;
  const isOutcomeStep = step === RUN_STEP_INDEX + 1;
  const isLast = step >= TOUR_STEP_COUNT - 1;
  const endsHere = isLast || (isOutcomeStep && outcome !== "answer");
  const canBack = step > 0 && !isOutcomeStep;
  const canNext = !isRunStep && !endsHere;

  const next = () => {
    if (canNext) onStepChange(step + 1);
  };
  const back = () => {
    if (canBack) onStepChange(step - 1);
  };
  const onCardKeyDown = (event: ReactKeyboardEvent<HTMLDivElement>) => {
    if (event.key === "ArrowRight") {
      event.preventDefault();
      if (endsHere) onClose();
      else next();
    } else if (event.key === "ArrowLeft") {
      event.preventDefault();
      back();
    } else if (event.key === "Enter" && event.target === event.currentTarget) {
      event.preventDefault();
      if (endsHere) onClose();
      else if (!isRunStep) next();
    }
  };

  const zIndex = 1300;
  const fade = {
    "@keyframes tourFadeIn": { from: { opacity: 0 }, to: { opacity: 1 } },
    animation: "tourFadeIn .15s ease-out",
    "@media (prefers-reduced-motion: reduce)": { animation: "none" },
  };

  if (watching) {
    return (
      <Box
        ref={cardRef}
        tabIndex={-1}
        role="status"
        data-testid="tour-watching"
        onKeyDown={onCardKeyDown}
        sx={{
          ...POPOVER_SURFACE,
          ...fade,
          position: "fixed",
          zIndex,
          bottom: narrow ? 0 : 24,
          right: narrow ? 0 : 24,
          left: narrow ? 0 : "auto",
          width: narrow ? "100%" : 320,
          borderRadius: narrow ? "8px 8px 0 0" : 1,
          p: 2,
          outline: "none",
          display: "flex",
          alignItems: "center",
          gap: 1.5,
        }}
      >
        <Typography sx={{ fontSize: 13.5, color: designTokens.ink, flex: 1 }}>
          Watching the five steps. The answer appears when Write finishes; Stop halts the run at
          any point.
        </Typography>
        <Button onClick={onClose} sx={{ fontSize: 13, color: designTokens.inkMuted, flex: "none" }}>
          Skip tour
        </Button>
      </Box>
    );
  }

  /* Card geometry. Viewport coordinates, because the ring and the card are
     both `position: fixed` and re-measure on scroll. */
  const viewportW = typeof window !== "undefined" ? window.innerWidth : 1280;
  const viewportH = typeof window !== "undefined" ? window.innerHeight : 800;
  const gutter = 16;
  const ringPad = 6;
  const cardW = Math.min(360, viewportW - gutter * 2);
  const estimatedCardH = 260;
  let cardStyle: Record<string, number | string>;
  if (narrow) {
    cardStyle = { left: 0, right: 0, bottom: 0, width: "100%", borderRadius: "8px 8px 0 0" };
  } else if (rect) {
    const roomBelow = viewportH - (rect.bottom + ringPad) >= estimatedCardH + gutter;
    const roomAbove = rect.top - ringPad >= estimatedCardH + gutter;
    const left = Math.min(
      Math.max(rect.left + rect.width / 2 - cardW / 2, gutter),
      viewportW - gutter - cardW,
    );
    if (roomBelow) cardStyle = { left, top: rect.bottom + ringPad + 12, width: cardW };
    else if (roomAbove) cardStyle = { left, bottom: viewportH - rect.top + ringPad + 12, width: cardW };
    // A target taller than the room around it (the whole answer panel):
    // the card takes the bottom-right corner, the same spot the watching
    // note uses, so the ringed panel stays readable rather than covered.
    else cardStyle = { right: gutter + 8, bottom: gutter + 8, width: cardW };
  } else {
    cardStyle = { left: "50%", top: "50%", transform: "translate(-50%, -50%)", width: cardW };
  }

  return (
    <>
      {/*
        The dim and the cut-out are ONE element: a ring drawn on the target
        with a very large box shadow in the dim colour. `pointer-events:
        none` so the page under it stays usable, which is the non-blocking
        rule in the file docstring. With no target, the same element is a
        plain full-viewport dim.
      */}
      <Box
        aria-hidden="true"
        data-testid="tour-backdrop"
        sx={{
          ...fade,
          position: "fixed",
          zIndex,
          pointerEvents: "none",
          ...(rect
            ? {
                left: rect.left - ringPad,
                top: rect.top - ringPad,
                width: rect.width + ringPad * 2,
                height: rect.height + ringPad * 2,
                borderRadius: 1.5,
                border: `2px solid ${designTokens.link}`,
                boxShadow: `0 0 0 9999px ${withAlpha(designTokens.ink, 0.45)}`,
              }
            : { inset: 0, bgcolor: withAlpha(designTokens.ink, 0.45) }),
        }}
      />
      <Box
        ref={cardRef}
        tabIndex={-1}
        role="dialog"
        aria-labelledby={titleId}
        aria-describedby={bodyId}
        data-testid="tour-card"
        data-step={current.id}
        onKeyDown={onCardKeyDown}
        sx={{
          ...POPOVER_SURFACE,
          ...fade,
          position: "fixed",
          zIndex: zIndex + 1,
          p: 2.25,
          outline: "none",
          "&:focus-visible": { borderColor: designTokens.link },
          ...cardStyle,
        }}
      >
        <Typography
          component="p"
          sx={{
            fontSize: 11,
            letterSpacing: ".12em",
            textTransform: "uppercase",
            fontWeight: 700,
            color: designTokens.inkFaint,
            m: 0,
            mb: 0.75,
          }}
        >
          Step {step + 1} of {TOUR_STEP_COUNT}
        </Typography>
        <Typography id={titleId} variant="h3" component="h2" sx={{ color: designTokens.ink, mb: 1 }}>
          {current.title}
        </Typography>
        <Box id={bodyId}>
          {current.body.map((sentence) => (
            <Typography
              key={sentence}
              variant="body2"
              sx={{ color: designTokens.inkMuted, mb: 1, "&:last-of-type": { mb: 0 } }}
            >
              {renderSentence(sentence)}
            </Typography>
          ))}
        </Box>
        <Box sx={{ display: "flex", alignItems: "center", gap: 0.75, mt: 2, flexWrap: "wrap" }}>
          {canBack ? (
            <Button onClick={back} sx={{ fontSize: 13, color: designTokens.inkMuted, px: 1.2 }}>
              Back
            </Button>
          ) : null}
          {isRunStep ? (
            <Button variant="contained" onClick={onRunForMe} sx={{ fontSize: 13, px: 1.6, py: 0.6 }}>
              Run it for me
            </Button>
          ) : endsHere ? (
            <Button variant="contained" onClick={onClose} sx={{ fontSize: 13, px: 1.6, py: 0.6 }}>
              Done
            </Button>
          ) : (
            <Button variant="contained" onClick={next} sx={{ fontSize: 13, px: 1.6, py: 0.6 }}>
              Next
            </Button>
          )}
          {endsHere ? null : (
            <Button
              onClick={onClose}
              sx={{ fontSize: 13, color: designTokens.inkMuted, px: 1.2, ml: "auto" }}
            >
              Skip tour
            </Button>
          )}
        </Box>
      </Box>
    </>
  );
}

export default OnboardingTour;
