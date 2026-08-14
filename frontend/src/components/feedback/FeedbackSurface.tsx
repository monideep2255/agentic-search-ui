/**
 * The feedback surface, build phase 4.8, ticket T-4.8-07.
 *
 * Answer-level rating, plus the thing a cite-or-refuse system actually needs:
 * a per-citation flag saying this source does not support the claim attached
 * to it. That produces a labelled pair rather than an opinion, and it is the
 * highest-value signal this product can collect.
 *
 * The reason chips are not generic. Every entry maps to a failure mode this
 * system has genuinely produced and logged: an unsupported citation, a
 * confidently wrong answer, a dropped entity in a multi-part question, and a
 * refusal that should have answered. A reason list built from real failures is
 * worth more at review time than "not helpful", and it is what makes
 * signal-based review sampling possible later.
 *
 * STUB: everything here is accepted and discarded. Wired by build phase 4.6,
 * which already names feedback as an `interactions` field. See
 * `stubs/registry.ts`.
 */

import { useState } from "react";
import { Box, Typography } from "@mui/material";

import { designTokens } from "../../theme";

/** Each maps to a failure mode this system has actually produced. */
const REASONS = [
  "Citation does not support the claim",
  "Wrong answer",
  "Missing a source I expected",
  "Should have refused",
  "Too slow",
] as const;

function Thumb({ down = false }: { down?: boolean }) {
  return (
    <svg
      width={15}
      height={15}
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.4}
      strokeLinejoin="round"
      aria-hidden="true"
      transform={down ? "rotate(180 8 8)" : undefined}
    >
      <path d="M5.5 7 8.2 2.2a1.3 1.3 0 0 1 2.4.7V6h2.6a1.3 1.3 0 0 1 1.28 1.55l-.85 4.2A1.3 1.3 0 0 1 12.15 13H5.5z" />
      <rect x={1.6} y={7} width={3.9} height={6} rx={0.8} />
    </svg>
  );
}

export function FeedbackSurface() {
  const [rating, setRating] = useState<"up" | "down" | null>(null);
  const [reasons, setReasons] = useState<string[]>([]);
  const [sent, setSent] = useState(false);

  if (sent) {
    return (
      <Box sx={{ mt: 3, pt: 2.25, borderTop: `1px solid ${designTokens.line}` }}>
        <Typography variant="body2" sx={{ color: designTokens.ok, fontWeight: 600 }}>
          Thanks. This goes to the review queue.
        </Typography>
      </Box>
    );
  }

  const toggleReason = (reason: string) =>
    setReasons((current) =>
      current.includes(reason) ? current.filter((r) => r !== reason) : [...current, reason],
    );

  const button = (kind: "up" | "down") => {
    const active = rating === kind;
    const danger = kind === "down";
    return (
      <Box
        component="button"
        type="button"
        aria-label={danger ? "Not helpful" : "Helpful"}
        aria-pressed={active}
        onClick={() => setRating(kind)}
        sx={{
          width: 30,
          height: 30,
          p: 0,
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          borderRadius: 0.5,
          cursor: "pointer",
          border: "1px solid",
          borderColor: active
            ? danger
              ? designTokens.risk
              : designTokens.blue
            : designTokens.line,
          color: active
            ? danger
              ? designTokens.risk
              : designTokens.blue
            : designTokens.inkMuted,
          bgcolor: active
            ? danger
              ? designTokens.riskWash
              : designTokens.layer1Wash
            : designTokens.surface,
          "&:hover": { borderColor: designTokens.lineStrong, color: designTokens.ink },
        }}
      >
        <Thumb down={danger} />
      </Box>
    );
  };

  return (
    <Box
      data-testid="feedback"
      sx={{
        mt: 3,
        pt: 2.25,
        borderTop: `1px solid ${designTokens.line}`,
        display: "flex",
        flexDirection: "column",
        gap: 1.5,
      }}
    >
      <Box sx={{ display: "flex", alignItems: "center", gap: 1, flexWrap: "wrap" }}>
        <Typography variant="body2" sx={{ color: designTokens.inkMuted }}>
          Was this answer helpful?
        </Typography>
        {button("up")}
        {button("down")}
      </Box>

      {rating === "down" ? (
        <>
          <Box sx={{ display: "flex", flexWrap: "wrap", gap: 0.75 }}>
            {REASONS.map((reason) => {
              const on = reasons.includes(reason);
              return (
                <Box
                  key={reason}
                  component="button"
                  type="button"
                  aria-pressed={on}
                  onClick={() => toggleReason(reason)}
                  sx={{
                    font: "inherit",
                    fontSize: 12.5,
                    px: 1.4,
                    py: 0.5,
                    borderRadius: 999,
                    cursor: "pointer",
                    border: "1px solid",
                    borderColor: on ? designTokens.risk : designTokens.line,
                    color: on ? designTokens.risk : designTokens.inkMuted,
                    bgcolor: on ? designTokens.riskWash : designTokens.surface,
                  }}
                >
                  {reason}
                </Box>
              );
            })}
          </Box>

          <Box
            component="input"
            type="text"
            aria-label="What went wrong"
            placeholder="What went wrong? (optional)"
            sx={{
              maxWidth: 470,
              font: "inherit",
              fontSize: 13.5,
              px: 1.4,
              py: 1.1,
              borderRadius: 0.5,
              border: `1px solid ${designTokens.lineStrong}`,
              bgcolor: designTokens.surface,
            }}
          />
        </>
      ) : null}

      {rating !== null ? (
        <Box sx={{ display: "flex", gap: 1 }}>
          <Box
            component="button"
            type="button"
            onClick={() => setSent(true)}
            sx={{
              font: "inherit",
              fontSize: 12.5,
              fontWeight: 600,
              px: 1.75,
              py: 0.9,
              border: 0,
              borderRadius: 0.5,
              cursor: "pointer",
              color: "#FFFFFF",
              bgcolor: designTokens.blue,
            }}
          >
            Send feedback
          </Box>
          <Box
            component="button"
            type="button"
            onClick={() => setSent(true)}
            sx={{
              font: "inherit",
              fontSize: 12.5,
              px: 1.75,
              py: 0.9,
              borderRadius: 0.5,
              cursor: "pointer",
              color: designTokens.inkMuted,
              bgcolor: "transparent",
              border: `1px solid ${designTokens.line}`,
            }}
          >
            Skip
          </Box>
        </Box>
      ) : null}
    </Box>
  );
}

export default FeedbackSurface;
