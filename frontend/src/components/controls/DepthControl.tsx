/**
 * The answer mode control. Build phase 4.8 ticket T-4.8-04, reshaped by UI fix
 * set 9, items 9.1, 9.2 and 9.12 (2026-09-13).
 *
 * The product owner: "The researcher and deep technical modes can be combined
 * into one." So the control offers two modes, Plain language (the default) and
 * Researcher. `Query.audience_depth` still accepts `clinical_brief` and
 * `deep_technical` for GraphQL, the CLI and MCP; this control never sends them,
 * and `displayedMode` shows either one as the nearer of the two buttons.
 *
 * The disabled state still matters. The mode a run was dispatched with is
 * LOCKED for that run, so the Write step never reconciles a change against
 * tokens it has already streamed. A change made afterwards applies to the next
 * question, because `App` reads the mode when a question is asked.
 *
 * DESIGN SOURCES, per `design-consistency`: `components/depth-control.html` and
 * the prototype's `.depth` and `.depthwrap .lock` rules for the buttons and the
 * lock line; the info affordance is `PersonaInfo`, the circled "i" and its card
 * the persona chip already ships, reused rather than rebuilt. No new colour,
 * radius or type size: 12.5px and 12px are the prototype's own.
 */

import { Box, Typography } from "@mui/material";

import { designTokens } from "../../theme";
import { PersonaInfo } from "../shell/PersonaChip";

/** Mirrors Query.audience_depth. The UI offers two of these four. */
export type AudienceDepth = "plain_language" | "researcher" | "clinical_brief" | "deep_technical";

/** The web UI's default mode, decision A3. */
export const DEFAULT_ANSWER_MODE: AudienceDepth = "plain_language";

const OPTIONS: { value: "plain_language" | "researcher"; label: string }[] = [
  { value: "plain_language", label: "Plain language" },
  { value: "researcher", label: "Researcher" },
];

/** What the info card says about the two modes (item 9.2).
 *
 * REWRITTEN 2026-09-21 for item 11.31. The previous wording promised "about
 * 250 words in three paragraphs", which described a depth directive that no
 * longer exists: every length instruction was removed that day, because the
 * product owner's criterion is audience fit rather than a count ("Number of
 * words do not define an answer"). A number here is also a promise the
 * product cannot keep, since the same question at the same mode measured 66,
 * 101 and 113 words on three consecutive runs.
 *
 * REWRITTEN AGAIN 2026-09-25 for item 13.2, two problems with one fix. The
 * card was a single run-on paragraph, "hard to read" in the product owner's
 * own words, and the same day the product owner separately ruled out the
 * wording it used to describe who each mode was for: "do not belittle the
 * user... do not target a persona... we do not belittle our users." So this
 * now describes WHAT EACH MODE GIVES, never who is reading it, split into
 * one block per mode with the label set apart from its description and the
 * closing line last. `ANSWER_MODE_BLOCKS` is the structured source of
 * truth; `ANSWER_MODE_EXPLAINER` below stays exported as the flat string,
 * rebuilt from the same blocks, for any caller that still wants plain text.
 */
export const ANSWER_MODE_BLOCKS: { testId: string; label: string; description: string }[] = [
  {
    testId: "answer-mode-plain_language",
    label: "Plain language:",
    description: "the answer in simple terms, easy to understand.",
  },
  {
    testId: "answer-mode-researcher",
    label: "Researcher:",
    description:
      "the answer in technical terms, with the specifics and the records listed or in tables.",
  },
];

/** The closing block, unlabeled, always last. */
export const ANSWER_MODE_CLOSING =
  "Both modes cite every claim. A change applies to your next question.";

export const ANSWER_MODE_EXPLAINER =
  ANSWER_MODE_BLOCKS.map((block) => `${block.label} ${block.description}`).join(" ") +
  " " +
  ANSWER_MODE_CLOSING;

/**
 * The info card's body: each mode as its own block, its label set apart
 * from its description, reusing the exact bold-`ink`-label,
 * muted-`inkMuted`-body, 13.5px, 1.45 line-height treatment `PersonaInfo`'s
 * own name-and-about pair already uses below in `shell/PersonaChip.tsx`,
 * and the same "8px" gap that card already uses between its about
 * paragraph and its Wikipedia link. Closing line last. Passed as
 * `PersonaInfo`'s `about` in place of a plain string, which `PersonaInfo`
 * now accepts additively (`React.ReactNode`) precisely so this card can be
 * structured while the persona chip's own plain-string call keeps
 * rendering exactly as before.
 */
function AnswerModesExplainer() {
  return (
    <>
      {ANSWER_MODE_BLOCKS.map(({ testId, label, description }) => (
        <Typography
          key={testId}
          component="p"
          data-testid={testId}
          sx={{ fontSize: 13.5, color: designTokens.inkMuted, m: 0, mb: "8px", lineHeight: 1.45 }}
        >
          <Box component="b" sx={{ fontWeight: 700, color: designTokens.ink }}>
            {label}
          </Box>{" "}
          {description}
        </Typography>
      ))}
      <Typography
        component="p"
        data-testid="answer-mode-closing"
        sx={{ fontSize: 13.5, color: designTokens.inkMuted, m: 0, lineHeight: 1.45 }}
      >
        {ANSWER_MODE_CLOSING}
      </Typography>
    </>
  );
}

/** The button a stored or wire value lights up. */
export function displayedMode(value: AudienceDepth): "plain_language" | "researcher" {
  return value === "researcher" || value === "deep_technical" ? "researcher" : "plain_language";
}

export interface DepthControlProps {
  value?: AudienceDepth;
  onChange?: (value: AudienceDepth) => void;
  /** True while a run is in flight. Section 12.9 requires the lock. */
  locked?: boolean;
  /** `onNavy` for the landing hero, where the label sits on the dark ground. */
  variant?: "onLight" | "onNavy";
}

export function DepthControl({
  value = DEFAULT_ANSWER_MODE,
  onChange,
  locked = false,
  variant = "onNavy",
}: DepthControlProps) {
  const onNavy = variant === "onNavy";
  const shown = displayedMode(value);
  return (
    <Box
      sx={{
        position: "relative",
        display: "flex",
        alignItems: "center",
        gap: 1.5,
        flexWrap: "wrap",
        justifyContent: "center",
      }}
    >
      <Typography
        variant="caption"
        component="span"
        id="depth-label"
        sx={{ color: onNavy ? designTokens.inkOnNavyMute : designTokens.inkMuted }}
      >
        Answer mode
      </Typography>

      <Box
        role="group"
        // The visible label is "Answer mode"; the accessible name carries it
        // (WCAG 2.5.3, label in name) plus the contract's own term, so a
        // screen reader and every existing query for the depth control agree.
        aria-label="Answer mode, audience-level depth"
        sx={{
          display: "inline-flex",
          border: `1px solid ${designTokens.line}`,
          borderRadius: 1,
          overflow: "hidden",
          bgcolor: designTokens.surface,
        }}
      >
        {OPTIONS.map(({ value: option, label }, index) => {
          const selected = option === shown;
          return (
            <Box
              key={option}
              component="button"
              type="button"
              aria-pressed={selected}
              disabled={locked}
              onClick={() => !locked && onChange?.(option)}
              sx={{
                font: "inherit",
                fontSize: 12.5,
                fontWeight: selected ? 700 : 400,
                px: 1.7,
                py: 0.85,
                border: 0,
                borderLeft: index === 0 ? 0 : `1px solid ${designTokens.line}`,
                cursor: locked ? "not-allowed" : "pointer",
                opacity: locked ? 0.5 : 1,
                bgcolor: selected ? designTokens.layer1Wash : "transparent",
                color: selected ? designTokens.layer1 : designTokens.inkMuted,
                "&:hover": { color: locked ? undefined : designTokens.ink },
              }}
            >
              {label}
            </Box>
          );
        })}
      </Box>

      <Box component="span" sx={{ position: "relative", display: "inline-flex" }}>
        {/*
          `align="right"`, not "left" as this card first shipped with the item
          9.2 explainer (a plain string then). Measured live at 390px for
          item 13.2: this control is CENTERED, so the "i" sits at roughly
          x=345 of 390, and a left-aligned 358px card (`calc(100vw - 32px)`)
          spans 345 to 703, off the right edge entirely. Anchoring the card's
          right edge to the icon instead, the same align PersonaChip's own
          app-bar chip already uses because its icon also sits toward a
          screen edge, spans 5 to 363: on-screen with margin either side.
        */}
        <PersonaInfo
          name="Answer modes"
          about={<AnswerModesExplainer />}
          wikipedia={null}
          variant={variant}
          align="right"
        />
      </Box>

      {locked ? (
        <Typography
          component="span"
          data-testid="depth-locked"
          sx={{ fontSize: 12, color: designTokens.inkFaint }}
        >
          Locked while this search runs
        </Typography>
      ) : null}
    </Box>
  );
}

export default DepthControl;
