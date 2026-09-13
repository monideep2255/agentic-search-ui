/**
 * The landing screen, build phase 4.8, ticket T-4.8-04.
 *
 * The navy hero is the single saturated surface in the whole product, kept as
 * a settled decision on 2026-08-12. Everything else stays flat so this one can
 * be loud; the phase exists because the shipped interface was too unstyled to
 * demo, and an all-white landing risks returning to exactly that.
 *
 * The headline is the primary voice here and is set larger and tighter than
 * any section heading, because it has to hold the screen on its own rather
 * than defer to the app bar above it.
 *
 * Source of truth: `docs/build/design/design-system/screens/home.html`.
 */

import { useEffect, useRef, useState } from "react";
import type { FormEvent, KeyboardEvent } from "react";
import { Box, Button, Typography } from "@mui/material";

import { designTokens } from "../../theme";
import { DepthControl } from "../controls/DepthControl";
import type { AudienceDepth } from "../controls/DepthControl";

/**
 * Seed questions. Real must-pass questions from the evaluation set, not
 * invented ones, so the landing shows what the product is genuinely for.
 *
 * Identifiers are monospace; gene symbols are not. Settled 2026-08-12: the
 * test is not "is this biomedical" but "would someone compare this character
 * by character". BRCA1 inside a phrase is read as a word.
 */
const SEEDS: { text: string; mono?: string; tail?: string }[] = [
  { text: "Diseases linked to BRCA1" },
  { text: "Clinical significance of ", mono: "rs334" },
  { text: "Variants in GCK causing MODY" },
  { text: "Trials recruiting for ALS" },
];

export interface HomeScreenProps {
  onSubmit?: (question: string, depth: AudienceDepth) => void;
  /** Rendered under the hero. The guest allowance counter lives here. */
  footer?: React.ReactNode;
  /**
   * The depth to show, when a parent owns it. Pass `depth` and
   * `onDepthChange` together, or neither.
   *
   * This screen used to own the depth outright, in local state seeded from
   * the literal `"researcher"`, and nothing could change that seed. Section
   * 14.5 says depth defaults to the account's last-used value once auth is
   * live, and `App` had been reading that value from `GET /auth/me` since
   * build phase 4.5 and had nowhere to put it: the control the user actually
   * sees was a different piece of state entirely, so a returning caller
   * whose account said `deep_technical` was shown `researcher` and the first
   * question they asked was sent at `researcher`. Found while fixing
   * F-4.5-J-15's server half.
   *
   * Left OPTIONAL so this screen still renders standalone, uncontrolled,
   * exactly as it did before, which is how the design-system tests mount it.
   */
  depth?: AudienceDepth;
  /** Called instead of the internal setter when `depth` is supplied. */
  onDepthChange?: (depth: AudienceDepth) => void;
  /**
   * The onboarding tour's first-visit invite (2026-09-13 product-owner
   * request), rendered under the seed chips. `App` decides whether it shows;
   * this screen only gives it a place. Null or undefined renders nothing.
   */
  tourInvite?: React.ReactNode;
  /**
   * Adds "Take the tour" as a fourth item in the footer strip, so the tour
   * can be restarted at any time after the invite is gone. Absent by default,
   * which keeps the standalone design-system mounts unchanged.
   */
  onTakeTour?: () => void;
  /**
   * A question the tour asks this screen to put in the box (its step 7,
   * `OnboardingTour.tsx`). Applied ONLY when the box is empty, so a question
   * the visitor has already typed is never overwritten; the tour's copy is
   * written for both cases. Null or undefined leaves the box alone.
   */
  prefillQuestion?: string | null;
}

/**
 * The submit icon: an up arrow, the shape every chat-style composer uses
 * for "send". Product-owner decision 2026-09-13, replacing the prototype's
 * "Search" text plus right arrow (`button.go` in `#s-landing`) with an
 * icon-only button. The design system has no icon-only submit, so this is
 * built from its nearest designed neighbours: the `.go` button's fill,
 * radius and weight, and the icon-only `aria-label` buttons in
 * `components/feedback.html`.
 */
function ArrowUpIcon() {
  return (
    <svg
      width={18}
      height={18}
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M8 13V3M3.5 7.5 8 3l4.5 4.5" />
    </svg>
  );
}

/**
 * Product-owner request, 2026-09-12: the search box should hold at least a
 * tweet's worth of text, 240 characters, without scrolling. At the current
 * 15.5px size that is about 3 visible rows; it then grows with the question
 * up to about 6 rows before it scrolls, so a long question never crowds out
 * the rest of the hero.
 */
const QUESTION_FONT_SIZE = 15.5;
const QUESTION_LINE_HEIGHT = 1.5;
const QUESTION_MIN_ROWS = 3;
const QUESTION_MAX_ROWS = 6;
const QUESTION_LINE_HEIGHT_PX = QUESTION_FONT_SIZE * QUESTION_LINE_HEIGHT;
const QUESTION_MIN_HEIGHT = QUESTION_LINE_HEIGHT_PX * QUESTION_MIN_ROWS;
const QUESTION_MAX_HEIGHT = QUESTION_LINE_HEIGHT_PX * QUESTION_MAX_ROWS;
/**
 * Phones get more rows before the box scrolls, measured on develop at 390px:
 * with six rows a 240-character question scrolled, because the field is far
 * narrower than on desktop.
 */
const QUESTION_MAX_ROWS_NARROW = 10;
const QUESTION_MAX_HEIGHT_NARROW = QUESTION_LINE_HEIGHT_PX * QUESTION_MAX_ROWS_NARROW;
/** The server truncates `text` at 2000 characters; the field matches it. */
const QUESTION_MAX_LENGTH = 2000;
function SearchIcon() {
  return (
    <svg
      width={18}
      height={18}
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.7}
      aria-hidden="true"
      style={{ color: designTokens.inkFaint, flex: "none" }}
    >
      <circle cx={7} cy={7} r={4.6} />
      <path d="m10.5 10.5 4 4" />
    </svg>
  );
}

export function HomeScreen({
  onSubmit,
  footer,
  depth: controlledDepth,
  onDepthChange,
  tourInvite = null,
  onTakeTour,
  prefillQuestion = null,
}: HomeScreenProps) {
  const [question, setQuestion] = useState("");
  const [localDepth, setLocalDepth] = useState<AudienceDepth>("researcher");
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  // Controlled when the parent supplies a value, uncontrolled otherwise. One
  // `depth` and one `setDepth` below, so no call site has to know which mode
  // it is in and the two can never be read from different places.
  const depth = controlledDepth ?? localDepth;
  const setDepth = (next: AudienceDepth) => {
    if (controlledDepth !== undefined) onDepthChange?.(next);
    else setLocalDepth(next);
  };

  // Shared by the form's onSubmit and the Enter-to-send key handler below, so
  // there is exactly one place that decides an empty or whitespace-only
  // question never submits.
  const trySubmit = () => {
    const trimmed = question.trim();
    if (trimmed) onSubmit?.(trimmed, depth);
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    trySubmit();
  };

  // Enter sends the question, matching every chat-style composer; Shift+Enter
  // inserts a newline, which is the one case that must NOT submit.
  const handleQuestionKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      trySubmit();
    }
  };

  // Auto-grow: reset to the CSS min-height, then read the content's natural
  // height and grow to it. The `maxHeight` in sx below still clamps this, so
  // growth past six rows turns into an internal scrollbar rather than an
  // ever-taller box.
  const resizeQuestionField = (el: HTMLTextAreaElement | null) => {
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight}px`;
  };

  // Recompute on mount, in case the initial render already differs from the
  // 3-row minimum (e.g. restored state), and on window resize, since the
  // same text wraps at 720px and does not at 1280px.
  useEffect(() => {
    resizeQuestionField(textareaRef.current);
    const handleResize = () => resizeQuestionField(textareaRef.current);
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  // The tour's step 7 fills the box, only while it is empty (see the prop).
  useEffect(() => {
    if (!prefillQuestion) return;
    setQuestion((current) => (current.trim() === "" ? prefillQuestion : current));
    // The auto-grow above reads the rendered textarea, so it runs after the
    // state write has painted rather than in the same tick.
    const frame = window.setTimeout(() => resizeQuestionField(textareaRef.current), 0);
    return () => window.clearTimeout(frame);
  }, [prefillQuestion]);

  return (
    // A flex column that claims the shell's remaining height, so the hero can
    // run to the footer the way the prototype's does. Without this the hero is
    // content-height and the landing shows a grey void below it, which only
    // became visible once the rail beside it ran full height.
    <Box sx={{ display: "flex", flexDirection: "column", flex: 1, minHeight: 0 }}>
      {/*
        Product-owner decision, 2026-09-12, overruling the design system's
        navy landing hero (`screens/home.html`): "The home page contrast is
        horrible. Lets have consistency." The home page now sits on the same
        light `canvas` ground as every other screen, between the same blue
        header and footer, with ink text and white controls.
      */}
      <Box
        data-testid="home-hero"
        sx={{
          flex: 1,
          bgcolor: designTokens.canvas,
          px: 3,
          py: { xs: 5, sm: 6 },
          textAlign: "center",
          // Product-owner feedback, 2026-09-12: centred between the header
          // and footer, the same as the log-in screen. The inner wrapper
          // below takes the full width, so its children keep their own
          // `maxWidth` and `mx: auto` centring.
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
        }}
      >
        <Box sx={{ width: "100%" }}>
        <Typography variant="h1" component="h1" sx={{ color: designTokens.ink, mb: 1.75 }}>
          Ask a biomedical question
        </Typography>
        <Typography
          sx={{
            color: designTokens.inkMuted,
            maxWidth: "46ch",
            mx: "auto",
            mb: 3.75,
            fontSize: 16,
          }}
        >
          Answered from the NCBI knowledge graph and live NCBI APIs. Every claim carries its
          source.
        </Typography>

        <Box
          component="form"
          onSubmit={submit}
          data-tour="search-box"
          sx={{
            display: "flex",
            // Top-aligned, not centred: the icon sits at the top-left of the
            // box (`SearchIcon` below) and the submit button pins itself to
            // the bottom-right with its own `alignSelf` (see below).
            alignItems: "flex-start",
            gap: 1.25,
            maxWidth: 720,
            mx: "auto",
            mb: 2.25,
            bgcolor: designTokens.surface,
            // `search-bar.html`: a 2px `line-strong` border, so a white bar
            // holds its own on the light ground.
            border: `2px solid ${designTokens.lineStrong}`,
            borderRadius: 1,
            pl: 2,
            pr: 0.75,
            py: 0.75,
            textAlign: "left",
            "&:focus-within": { borderColor: designTokens.link },
          }}
        >
          {/*
            Centred on the QUESTION_LINE_HEIGHT_PX line box, with the same
            top inset (0.75, matching the textarea's own `py`) so the glass
            sits level with the first line of text, at 3 rows or grown, not
            just nudged down by a fixed padding guess.
          */}
          <Box
            sx={{
              // `mt`, not `pt`: padding on a border-box element eats into the
              // fixed height below, shrinking the centred area and pulling
              // the icon 3px above the text's first line. A margin pushes
              // the whole line box down instead, so it lands exactly where
              // the textarea's own padding puts its first line.
              mt: 0.75,
              height: `${QUESTION_LINE_HEIGHT_PX}px`,
              flex: "none",
              display: "flex",
              alignItems: "center",
            }}
          >
            <SearchIcon />
          </Box>
          <Box
            component="textarea"
            ref={textareaRef}
            aria-label="Your question"
            placeholder="Which diseases are associated with BRCA1?"
            value={question}
            maxLength={QUESTION_MAX_LENGTH}
            rows={QUESTION_MIN_ROWS}
            onKeyDown={handleQuestionKeyDown}
            onChange={(event: React.ChangeEvent<HTMLTextAreaElement>) => {
              setQuestion(event.target.value);
              resizeQuestionField(event.target);
            }}
            sx={{
              flex: 1,
              border: 0,
              outline: 0,
              resize: "none",
              font: "inherit",
              fontSize: QUESTION_FONT_SIZE,
              lineHeight: QUESTION_LINE_HEIGHT,
              minHeight: QUESTION_MIN_HEIGHT,
              maxHeight: QUESTION_MAX_HEIGHT,
              minWidth: 0,
              "@media (max-width:720px)": { maxHeight: QUESTION_MAX_HEIGHT_NARROW },
              overflowY: "auto",
              color: designTokens.ink,
              bgcolor: "transparent",
              py: 0.75,
            }}
          />
          {/*
            Product-owner decision 2026-09-13, after trying the text button
            top-right, bottom-right and flexible between the two: an icon-only
            submit, always at the bottom-right corner, at every width. On
            phones it no longer takes a full-width row of its own, since a
            36px square leaves the field its width (measured 2026-09-12 it was
            the 100px-plus text button that squeezed the field to 176px).

            Accessible name: this read "Ask" until 2026-08-14 because the nav
            already has a destination called Search, and two controls sharing
            an accessible name is a real problem for anyone navigating by
            control list, which `e2e/accessibility.spec.ts` enforces. With no
            visible text, WCAG 2.5.3 (Label in Name) no longer constrains the
            name, but it keeps "Search" in it so a speech-input user who reads
            the page as a search box can still say the obvious word.
          */}
          <Button
            type="submit"
            variant="contained"
            aria-label="Search the knowledge graph"
            sx={{
              // A square: the `.go` button's 36px rendered height, with
              // `minWidth` cleared so MUI's 64px text-button floor does not
              // widen it.
              width: 36,
              height: 36,
              minWidth: 0,
              p: 0,
              flex: "none",
              alignSelf: "flex-end",
            }}
          >
            <ArrowUpIcon />
          </Button>
        </Box>

        {/* `.depthwrap` sits BELOW the search bar in the prototype. */}
        <Box data-tour="depth" sx={{ mb: 2.5, display: "inline-block" }}>
          <DepthControl value={depth} onChange={setDepth} variant="onLight" />
        </Box>

        <Box
          data-tour="seeds"
          sx={{
            display: "flex",
            flexWrap: "wrap",
            gap: 1,
            justifyContent: "center",
            maxWidth: 660,
            mx: "auto",
          }}
        >
          {SEEDS.map((seed) => {
            const label = seed.mono ? `${seed.text}${seed.mono}` : seed.text;
            return (
              <Box
                key={label}
                component="button"
                type="button"
                onClick={() => onSubmit?.(label, depth)}
                sx={{
                  font: "inherit",
                  fontSize: 13,
                  px: 1.75,
                  py: 0.75,
                  borderRadius: 999,
                  cursor: "pointer",
                  color: designTokens.ink,
                  border: `1px solid ${designTokens.line}`,
                  bgcolor: designTokens.surface,
                  "&:hover": { borderColor: designTokens.lineStrong, bgcolor: designTokens.surfaceSunk },
                }}
              >
                {seed.text}
                {seed.mono ? (
                  <Box component="span" sx={{ fontFamily: "ui-monospace, monospace" }}>
                    {seed.mono}
                  </Box>
                ) : null}
              </Box>
            );
          })}
        </Box>

        {tourInvite}

        <Box
          sx={{
            maxWidth: 900,
            mx: "auto",
            mt: 4.25,
            pt: 2.5,
            borderTop: `1px solid ${designTokens.line}`,
            display: "flex",
            flexWrap: "wrap",
            gap: "10px 28px",
            justifyContent: "center",
            fontSize: 12.5,
            color: designTokens.inkMuted,
          }}
        >
          {[
            ["Knowledge graph", "115M nodes, 693M edges"],
            ["Live NCBI APIs", "queried per question"],
            ["Literature and trials", "layered on top"],
          ].map(([label, detail]) => (
            <Box component="span" key={label}>
              <Box component="b" sx={{ color: designTokens.ink, fontWeight: 700 }}>
                {label}
              </Box>{" "}
              {detail}
            </Box>
          ))}
          {onTakeTour ? (
            // The fourth item: a text button in the strip's own muted voice,
            // underlined so it reads as the one item here that does something.
            <Box
              component="button"
              type="button"
              onClick={onTakeTour}
              sx={{
                font: "inherit",
                fontSize: "inherit",
                color: designTokens.inkMuted,
                background: "none",
                border: 0,
                p: 0,
                cursor: "pointer",
                textDecoration: "underline",
                textUnderlineOffset: "3px",
                "&:hover": { color: designTokens.link },
              }}
            >
              Take the tour
            </Box>
          ) : null}
        </Box>
        </Box>
      </Box>

      {footer ? (
        <Box sx={{ display: "flex", justifyContent: "center", py: 2.5 }}>{footer}</Box>
      ) : null}
    </Box>
  );
}

export default HomeScreen;
