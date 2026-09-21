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
 * So this now describes WHO EACH MODE IS FOR, which is the thing that
 * actually differs and the thing a reader is choosing between.
 */
export const ANSWER_MODE_EXPLAINER =
  "Plain language: for a reader with no biology background, in everyday words, " +
  "covering everything the sources show with every sentence tied to its source. " +
  "Researcher: for someone who knows the field and NCBI, with the specifics, " +
  "the detail and the records listed or tabled, every claim cited. " +
  "A change applies to your next question.";

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
        <PersonaInfo
          name="Answer modes"
          about={ANSWER_MODE_EXPLAINER}
          wikipedia={null}
          variant={variant}
          align="left"
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
