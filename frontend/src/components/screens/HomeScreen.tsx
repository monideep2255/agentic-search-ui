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
}

/** The prototype's `button.go` arrow, from `#s-landing`. */
function ArrowIcon() {
  return (
    <svg
      width={13}
      height={13}
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      aria-hidden="true"
    >
      <path d="M2 8h11M9 4l4 4-4 4" />
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
/**
 * Product-owner decision, 2026-09-13, option B ("flexible"): the Search
 * button sits top-right, level with the icon, while the question is one
 * visual line, and drops to bottom-right once it wraps. A small tolerance
 * absorbs sub-pixel rounding in `scrollHeight` so the state does not flap
 * right at the boundary.
 */
const MULTILINE_TOLERANCE_PX = 2;

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
}: HomeScreenProps) {
  const [question, setQuestion] = useState("");
  const [localDepth, setLocalDepth] = useState<AudienceDepth>("researcher");
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  // Whether the question currently occupies more than one visual line.
  // Empty or placeholder-only, and a question that fits on one line, are
  // both "false": the Search button then sits top-right, level with the
  // icon (option B, product-owner decision 2026-09-13). Anything that
  // wraps flips this to "true" and the button drops to bottom-right.
  const [isMultiline, setIsMultiline] = useState(false);

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

  // Whether the question's own content, not the 3-row minimum the box is
  // held to, spans more than one visual line. Two separate things hold the
  // box at 3 rows even for one line of text, and both have to be lifted for
  // the instant of measurement, or `scrollHeight` reports "multiline" for a
  // one-line or empty box: the CSS `minHeight` floor (cleared via the
  // inline style), and the `rows` HTML attribute, which drives the
  // browser's own intrinsic sizing independently of any CSS height rule
  // (measured: with only `minHeight` cleared, `scrollHeight` still read the
  // 3-row height; setting `rows` to 1 as well brought it down to the true
  // one-line content height).
  const measureIsMultiline = (el: HTMLTextAreaElement): boolean => {
    const previousMinHeight = el.style.minHeight;
    const previousRows = el.rows;
    el.style.minHeight = "0px";
    el.rows = 1;
    const style = window.getComputedStyle(el);
    const paddingTop = parseFloat(style.paddingTop) || 0;
    const paddingBottom = parseFloat(style.paddingBottom) || 0;
    const contentHeight = el.scrollHeight - paddingTop - paddingBottom;
    el.style.minHeight = previousMinHeight;
    el.rows = previousRows;
    return contentHeight > QUESTION_LINE_HEIGHT_PX + MULTILINE_TOLERANCE_PX;
  };

  // Auto-grow: reset to the CSS min-height, then read the content's natural
  // height and grow to it. The `maxHeight` in sx below still clamps this, so
  // growth past six rows turns into an internal scrollbar rather than an
  // ever-taller box. The multiline check reuses the same "reset height,
  // read scrollHeight" measurement rather than a second layout pass.
  const resizeQuestionField = (el: HTMLTextAreaElement | null) => {
    if (!el) return;
    el.style.height = "auto";
    setIsMultiline(measureIsMultiline(el));
    el.style.height = `${el.scrollHeight}px`;
  };

  // Recompute on mount (in case the initial render already differs from the
  // `false` default, e.g. restored state) and on window resize, since the
  // line count is width-dependent: the same text wraps at 720px and does
  // not at 1280px.
  useEffect(() => {
    resizeQuestionField(textareaRef.current);
    const handleResize = () => resizeQuestionField(textareaRef.current);
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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
          sx={{
            display: "flex",
            // Top-aligned, not centred: the icon sits at the top-left of the
            // box (`SearchIcon` below) and the Search button's own slot Box
            // sets its `alignSelf` per line count, top-right level with the
            // icon on one line, bottom-right once the box grows past one
            // (see the slot Box's comment further down).
            alignItems: "flex-start",
            // Wraps only below 720px, where the Search button takes its own
            // full-width row (see its sx) and the question field keeps the
            // whole width. Measured 2026-09-12: beside the button at 390px the
            // field was 176px wide and a 240-character question scrolled.
            flexWrap: "wrap",
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
            // Below 720px the button drops to its own full-width row (see its
            // sx). `search-bar.html`'s 16px/6px split exists to clear the
            // icon on one line; once the button is on its own row, a left
            // inset of 16px against a right inset of 6px reads as off-centre,
            // so both sides match here.
            "@media (max-width:720px)": { pl: 0.75 },
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
            "Search", with the prototype's right arrow: `button.go` in
            `#s-landing`.

            This read "Ask" until 2026-08-14. The reason was real (F-4.8-L-03):
            the nav already has a destination called Search, and two visible
            controls sharing an accessible name is a genuine problem for anyone
            navigating by control list, which `e2e/accessibility.spec.ts`
            enforces. The reasoning was sound and the remedy overshot, changing
            what the user SEES to fix a problem that lives in the accessible
            name.

            So the visible label is the design's, and the collision is resolved
            on the accessible name instead. WCAG 2.5.3 (Label in Name) requires
            that name to CONTAIN the visible text, or a speech-input user
            saying "Search" cannot operate the control, which is why it is not
            renamed to something unrelated.
          */}
          {/*
            Product-owner decision 2026-09-13, option B ("flexible"): one
            line, the button sits top-right level with the icon; wrapped,
            it drops to bottom-right as before. The slot Box below matches
            the icon box's own `mt` and height exactly in the one-line case,
            so `alignItems: "center"` centers the button on the identical
            line box the icon is centered on, regardless of the button's
            own rendered height. In the wrapped case the slot just hugs the
            button and pins it to the row's bottom-right corner, the same
            effect `alignSelf: "flex-end"` gave the button directly before
            this box existed. Below 720px both collapse to the same
            full-width row as always.
          */}
          <Box
            sx={{
              flex: "none",
              display: "flex",
              justifyContent: "flex-end",
              ...(isMultiline
                ? { alignSelf: "flex-end", alignItems: "flex-end", height: "auto", mt: 0 }
                : {
                    alignSelf: "flex-start",
                    alignItems: "center",
                    height: `${QUESTION_LINE_HEIGHT_PX}px`,
                    mt: 0.75,
                  }),
              "@media (max-width:720px)": {
                width: "100%",
                height: "auto",
                mt: 0,
                alignSelf: "stretch",
                alignItems: "stretch",
              },
            }}
          >
            <Button
              type="submit"
              variant="contained"
              aria-label="Search the knowledge graph"
              sx={{
                px: 2.25,
                py: 1.1,
                fontSize: 14,
                gap: 0.75,
                flex: "none",
                // prototype/app.html's 720px breakpoint: below it the button
                // takes its own row, so the question field gets the full width.
                "@media (max-width:720px)": { width: "100%" },
              }}
            >
              Search
              <ArrowIcon />
            </Button>
          </Box>
        </Box>

        {/* `.depthwrap` sits BELOW the search bar in the prototype. */}
        <Box sx={{ mb: 2.5 }}>
          <DepthControl value={depth} onChange={setDepth} variant="onLight" />
        </Box>

        <Box
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
