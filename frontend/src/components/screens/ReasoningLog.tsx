/**
 * The run's own account of what it did, build phase 4.9, ticket T-4.9-04.
 *
 * The prototype's `.tracelog`: one row per step, carrying the time it happened,
 * which step produced it, and what that step said. It appears in two places and
 * is the same data in both, so it is one component rather than two renderings
 * that can drift: on the run screen while the run is live (F-4.8-D-10), and
 * behind the answer screen's `Show work` disclosure once it lands (F-4.8-D-05).
 *
 * What it does NOT render, deliberately: `guard.reason`, `error.message`, or
 * any other free-form backend text. `GuardrailBanner` and `CapMessage` both
 * refuse those fields on purpose, because Section 12.6's no-cost-figure rule
 * can only be guaranteed by never rendering them, and F-4.8-A-15 was that leak
 * reintroduced once already. The guard's line comes from the reviewed
 * `CATEGORY_COPY` table instead; `useRunView` owns that choice.
 */

import { Box, Typography } from "@mui/material";

import { designTokens } from "../../theme";
import type { ReasoningStep } from "./RunScreen";

export interface ReasoningLogProps {
  steps: ReasoningStep[];
  /** Distinguishes the live copy from the one behind `Show work`. */
  testId?: string;
}

export function ReasoningLog({ steps, testId = "reasoning-log" }: ReasoningLogProps) {
  if (steps.length === 0) return null;

  return (
    <Box
      data-testid={testId}
      sx={{
        border: `1px solid ${designTokens.line}`,
        borderRadius: 1,
        overflow: "hidden",
        bgcolor: designTokens.surface,
      }}
    >
      {steps.map((step, index) => (
        <Box
          key={`${step.step}-${index}`}
          sx={{
            display: "flex",
            gap: 2,
            alignItems: "baseline",
            p: "10px 14px",
            fontSize: 13.5,
            borderTop: index === 0 ? 0 : `1px solid ${designTokens.line}`,
            bgcolor: index % 2 === 1 ? designTokens.surfaceSunk : designTokens.surface,
          }}
        >
          <Box
            component="span"
            sx={{
              fontFamily: "ui-monospace, monospace",
              fontSize: 11.5,
              color: designTokens.inkMuted,
              flex: "none",
              minWidth: 44,
            }}
          >
            {step.at ?? ""}
          </Box>
          <Box
            component="span"
            sx={{
              fontFamily: "ui-monospace, monospace",
              fontSize: 11.5,
              fontWeight: 700,
              letterSpacing: ".06em",
              textTransform: "uppercase",
              color: designTokens.blue,
              flex: "none",
              minWidth: 52,
            }}
          >
            {step.step}
          </Box>
          <Typography component="span" sx={{ fontSize: 13.5, color: designTokens.ink }}>
            {step.text}
          </Typography>
        </Box>
      ))}
    </Box>
  );
}

export default ReasoningLog;
