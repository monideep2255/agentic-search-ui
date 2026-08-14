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

import { useState } from "react";
import type { FormEvent } from "react";
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

export function HomeScreen({ onSubmit, footer }: HomeScreenProps) {
  const [question, setQuestion] = useState("");
  const [depth, setDepth] = useState<AudienceDepth>("researcher");

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const trimmed = question.trim();
    if (trimmed) onSubmit?.(trimmed, depth);
  };

  return (
    // A flex column that claims the shell's remaining height, so the hero can
    // run to the footer the way the prototype's does. Without this the hero is
    // content-height and the landing shows a grey void below it, which only
    // became visible once the rail beside it ran full height.
    <Box sx={{ display: "flex", flexDirection: "column", flex: 1, minHeight: 0 }}>
      <Box
        data-testid="home-hero"
        sx={{
          flex: 1,
          bgcolor: designTokens.navy,
          backgroundImage:
            "radial-gradient(900px 340px at 50% -10%, rgba(32,84,147,.6), transparent 70%)",
          px: 3,
          pt: { xs: 6, sm: 8 },
          pb: { xs: 5, sm: 7 },
          textAlign: "center",
        }}
      >
        <Typography variant="h1" component="h1" sx={{ color: "#FFFFFF", mb: 1.75 }}>
          Ask a biomedical question
        </Typography>
        <Typography
          sx={{
            color: designTokens.inkOnNavyMute,
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
            alignItems: "center",
            gap: 1.25,
            maxWidth: 620,
            mx: "auto",
            mb: 2.25,
            bgcolor: designTokens.surface,
            border: "2px solid transparent",
            borderRadius: 1,
            pl: 2,
            pr: 0.75,
            py: 0.75,
            textAlign: "left",
            "&:focus-within": { borderColor: designTokens.link },
          }}
        >
          <SearchIcon />
          <Box
            component="input"
            type="text"
            aria-label="Your question"
            placeholder="Which diseases are associated with BRCA1?"
            value={question}
            onChange={(event: React.ChangeEvent<HTMLInputElement>) =>
              setQuestion(event.target.value)
            }
            sx={{
              flex: 1,
              border: 0,
              outline: 0,
              font: "inherit",
              fontSize: 15.5,
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
          <Button
            type="submit"
            variant="contained"
            aria-label="Search the knowledge graph"
            sx={{ px: 2.25, py: 1.1, fontSize: 14, gap: 0.75 }}
          >
            Search
            <ArrowIcon />
          </Button>
        </Box>

        {/* `.depthwrap` sits BELOW the search bar in the prototype. */}
        <Box sx={{ mb: 2.5 }}>
          <DepthControl value={depth} onChange={setDepth} variant="onNavy" />
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
                  color: "#FFFFFF",
                  border: "1px solid rgba(255,255,255,.35)",
                  bgcolor: "rgba(255,255,255,.08)",
                  "&:hover": { bgcolor: "rgba(255,255,255,.18)" },
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
            borderTop: "1px solid rgba(255,255,255,.18)",
            display: "flex",
            flexWrap: "wrap",
            gap: "10px 28px",
            justifyContent: "center",
            fontSize: 12.5,
            color: designTokens.inkOnNavyMute,
          }}
        >
          {[
            ["Knowledge graph", "115M nodes, 693M edges"],
            ["Live NCBI APIs", "queried per question"],
            ["Literature and trials", "layered on top"],
          ].map(([label, detail]) => (
            <Box component="span" key={label}>
              <Box component="b" sx={{ color: "#FFFFFF", fontWeight: 700 }}>
                {label}
              </Box>{" "}
              {detail}
            </Box>
          ))}
        </Box>
      </Box>

      {footer ? (
        <Box sx={{ display: "flex", justifyContent: "center", py: 2.5 }}>{footer}</Box>
      ) : null}
    </Box>
  );
}

export default HomeScreen;
