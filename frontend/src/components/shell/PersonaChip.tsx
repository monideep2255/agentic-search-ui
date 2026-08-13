/**
 * The named scientist persona, build phase 4.8, ticket T-4.8-03.
 *
 * Technical specification 12.7 and 14.2. Presentation only: the persona never
 * changes which tools run, which records are retrieved, or what the trust
 * signal says. Section 14.1's personalization firewall puts personalization in
 * orchestration and synthesis style, never in grounding.
 *
 * The spec is explicit about the register, and it is a product decision rather
 * than a taste one: "a small, static label and a muted icon, never an animated
 * mascot or a cartoon avatar", on the 2026-07-21 reasoning that the persona
 * should build connection without undercutting the provenance-forward
 * positioning. So there is no animation here, and there never should be.
 *
 * STUB: the name is drawn from a placeholder list. Wired by build phase 4.5
 * from `persona_name` on the POST /v1/query response. See `stubs/registry.ts`.
 */

import { Box, Typography } from "@mui/material";

import { designTokens } from "../../theme";

/**
 * A placeholder for the curated top-100 biomedical-scientist list, which is
 * its own Phase 6 task. Ten is enough to prove the component; the real list is
 * a research task, not a styling one.
 */
export const PLACEHOLDER_PERSONAS = [
  "Mendel",
  "Franklin",
  "McClintock",
  "Ramon y Cajal",
  "Hodgkin",
  "Elion",
  "Nirenberg",
  "Blackburn",
  "Tsien",
  "Sanger",
] as const;

/**
 * Draw a persona for a session.
 *
 * Deterministic rather than random, so a demo reads the same way twice and a
 * test does not need to stub a clock or a generator.
 */
export function drawPersona(seed = 0): string {
  return PLACEHOLDER_PERSONAS[Math.abs(seed) % PLACEHOLDER_PERSONAS.length];
}

/** The muted icon the spec calls for: a plain figure, not a face, not a mascot. */
function PersonIcon({ size = 12 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
      <circle cx="8" cy="5.2" r="2.9" />
      <path d="M2.6 14a5.4 5.4 0 0 1 10.8 0z" />
    </svg>
  );
}

export interface PersonaChipProps {
  name: string;
  /** `onNavy` for the app bar; `onLight` for a plain surface. */
  variant?: "onLight" | "onNavy";
}

export function PersonaChip({ name, variant = "onNavy" }: PersonaChipProps) {
  const onNavy = variant === "onNavy";
  return (
    <Box
      data-testid="persona-chip"
      sx={{
        display: "inline-flex",
        alignItems: "center",
        gap: 1,
        borderRadius: 999,
        px: 1.6,
        py: 0.6,
        pl: 0.9,
        border: "1px solid",
        borderColor: onNavy ? "rgba(255,255,255,.28)" : designTokens.line,
        bgcolor: onNavy ? "rgba(255,255,255,.10)" : designTokens.surface,
        // inkOnNavyMute (#A9C3DC) fails WCAG AA here: the chip's own
        // translucent background composites to ~#36659E over the app bar, and
        // that pair measures about 2.7:1 against a 4.5:1 requirement. The
        // bright ink token measures 5.4:1 on the same ground. Caught by the
        // e2e contrast check, not by eye.
        color: onNavy ? designTokens.inkOnNavy : designTokens.inkMuted,
        whiteSpace: "nowrap",
      }}
    >
      <Box
        component="span"
        sx={{
          width: 22,
          height: 22,
          borderRadius: "50%",
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          flex: "none",
          border: "1px solid",
          borderColor: onNavy ? "rgba(255,255,255,.28)" : designTokens.line,
          bgcolor: onNavy ? "rgba(255,255,255,.14)" : designTokens.surfaceSunk,
          color: onNavy ? "#FFFFFF" : designTokens.inkFaint,
        }}
      >
        <PersonIcon />
      </Box>
      <Typography variant="body2" component="span" sx={{ fontSize: 13 }}>
        Working as{" "}
        <Box component="b" sx={{ fontWeight: 700, color: onNavy ? "#FFFFFF" : designTokens.ink }}>
          {name}
        </Box>
      </Typography>
    </Box>
  );
}

/**
 * What each loop step is called while it is the live one.
 *
 * Section 12.7: the caption updates from the active step's own `narrative`
 * field. It is a caption on work that is genuinely happening, not a mascot
 * with a script, which is why the wording describes the step rather than
 * performing enthusiasm.
 */
export const STEP_NARRATIVE: Record<string, string> = {
  Guard: "is checking the question is answerable and in scope",
  Think: "is working out what the question is asking for",
  Plan: "is choosing which sources to read",
  Act: "is reading the records",
  Write: "is writing the answer, citing as it goes",
};

export interface PersonaCaptionProps {
  name: string;
  /** The live step, or null when no run is in flight. */
  step: string | null;
}

/** The per-step caption on the run screen. Renders nothing when idle. */
export function PersonaCaption({ name, step }: PersonaCaptionProps) {
  if (!step) return null;
  return (
    <Box
      data-testid="persona-caption"
      sx={{ display: "flex", alignItems: "center", gap: 1.2, mt: 2, minHeight: 22 }}
    >
      <Box
        component="span"
        sx={{
          width: 20,
          height: 20,
          borderRadius: "50%",
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          flex: "none",
          border: `1px solid ${designTokens.line}`,
          bgcolor: designTokens.surfaceSunk,
          color: designTokens.inkFaint,
        }}
      >
        <PersonIcon />
      </Box>
      <Typography variant="body2" sx={{ color: designTokens.inkMuted }}>
        <Box component="b" sx={{ fontWeight: 700, color: designTokens.ink }}>
          {name}
        </Box>{" "}
        {STEP_NARRATIVE[step] ?? "is working"}
      </Typography>
    </Box>
  );
}

export default PersonaChip;
