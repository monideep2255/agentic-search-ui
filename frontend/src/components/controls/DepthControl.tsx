/**
 * Audience-level depth control, build phase 4.8, ticket T-4.8-04.
 *
 * Technical specification 12.9. Three-way, mirroring `Query.audience_depth`
 * exactly: clinical_brief, researcher as the default, deep_technical.
 *
 * The disabled state is the part that matters and is easy to skip. The depth a
 * run was dispatched with is LOCKED for that run, so the Write step never has
 * to reconcile a depth change against tokens it has already streamed. A user
 * who changes depth mid-answer would otherwise get a paragraph in one register
 * followed by a paragraph in another, with no way to tell which one the
 * citations were chosen for.
 *
 * STUB: the value is held locally. Wired by build phase 4.5, which sends it on
 * POST /v1/query. See `stubs/registry.ts`.
 */

import { Box, Typography } from "@mui/material";

import { designTokens } from "../../theme";

/** Mirrors Query.audience_depth. Do not add a fourth without a spec change. */
export type AudienceDepth = "clinical_brief" | "researcher" | "deep_technical";

const OPTIONS: { value: AudienceDepth; label: string }[] = [
  { value: "clinical_brief", label: "Clinical brief" },
  { value: "researcher", label: "Researcher" },
  { value: "deep_technical", label: "Deep technical" },
];

export interface DepthControlProps {
  value?: AudienceDepth;
  onChange?: (value: AudienceDepth) => void;
  /** True while a run is in flight. Section 12.9 requires the lock. */
  locked?: boolean;
  /** `onNavy` for the landing hero, where the label sits on the dark ground. */
  variant?: "onLight" | "onNavy";
}

export function DepthControl({
  value = "researcher",
  onChange,
  locked = false,
  variant = "onNavy",
}: DepthControlProps) {
  const onNavy = variant === "onNavy";
  return (
    <Box
      sx={{
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
        Answer depth
      </Typography>

      <Box
        role="group"
        aria-labelledby="depth-label"
        aria-label="Audience-level depth"
        sx={{
          display: "inline-flex",
          border: `1px solid ${designTokens.line}`,
          borderRadius: 1,
          overflow: "hidden",
          bgcolor: designTokens.surface,
        }}
      >
        {OPTIONS.map(({ value: option, label }, index) => {
          const selected = option === value;
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
    </Box>
  );
}

export default DepthControl;
