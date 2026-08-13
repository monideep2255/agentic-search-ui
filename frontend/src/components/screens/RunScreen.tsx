/**
 * The run screen, build phase 4.8, ticket T-4.8-05.
 *
 * The stepper carries the wait, and it renders all five loop steps always,
 * because the shape of the loop is the product's story: a question crosses a
 * guardrail, gets understood, gets planned, reads records, and only then gets
 * written. Collapsing that to a spinner throws away the one thing that
 * distinguishes this from a chat box.
 *
 * Tool chips land as each tool fires, coloured by the data layer they read, so
 * the colour system is visible during the wait rather than only in the answer.
 *
 * Source of truth: `docs/build/design/design-system/components/pipeline-stepper.html`
 * and `screens/streaming.html`.
 */

import { Box, Button, Typography } from "@mui/material";

import { designTokens, layerColour } from "../../theme";
import { PersonaCaption } from "../shell/PersonaChip";

/** The five nodes of the agent loop, in order. Never a subset. */
export const STEPS = ["Guard", "Think", "Plan", "Act", "Write"] as const;
export type StepName = (typeof STEPS)[number];

export interface ToolCall {
  name: string;
  detail: string;
  layer: 1 | 2 | 3;
}

export interface RunScreenProps {
  question: string;
  /** The live step, or null before the run starts. */
  activeStep?: StepName | null;
  toolCalls?: ToolCall[];
  personaName?: string;
  onStop?: () => void;
  onNewSearch?: () => void;
}

export function RunScreen({
  question,
  activeStep = "Guard",
  toolCalls = [],
  personaName = "Mendel",
  onStop,
  onNewSearch,
}: RunScreenProps) {
  const activeIndex = activeStep ? STEPS.indexOf(activeStep) : -1;

  return (
    <Box sx={{ maxWidth: 900, mx: "auto", px: 3, py: 3.5 }}>
      <Box
        sx={{
          bgcolor: designTokens.surface,
          border: `1px solid ${designTokens.line}`,
          borderRadius: 1,
          p: { xs: 2.5, sm: 3.25 },
        }}
      >
        <Box
          sx={{
            display: "flex",
            gap: 1.75,
            alignItems: "flex-start",
            pb: 2,
            mb: 2.5,
            borderBottom: `1px solid ${designTokens.line}`,
          }}
        >
          <Typography variant="h3" component="h1" sx={{ flex: 1 }}>
            {question}
          </Typography>
          <Button onClick={onStop} sx={{ fontSize: 12.5, color: designTokens.inkMuted, border: `1px solid ${designTokens.lineStrong}`, px: 1.6, py: 0.6 }}>
            Stop
          </Button>
          <Button onClick={onNewSearch} sx={{ fontSize: 12.5, color: designTokens.inkMuted, border: `1px solid ${designTokens.line}`, px: 1.6, py: 0.6 }}>
            New search
          </Button>
        </Box>

        <Box sx={{ display: "flex", alignItems: "flex-start" }}>
          {STEPS.map((step, index) => {
            const done = activeIndex > index;
            const live = activeIndex === index;
            return (
              <Box
                key={step}
                data-testid={`step-${step}`}
                data-state={live ? "live" : done ? "done" : "pending"}
                sx={{
                  flex: 1,
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  gap: 1,
                  position: "relative",
                  "&::before": {
                    content: '""',
                    position: "absolute",
                    top: 7,
                    left: "-50%",
                    width: "100%",
                    height: 2,
                    bgcolor: done || live ? designTokens.blue : designTokens.line,
                    display: index === 0 ? "none" : "block",
                  },
                }}
              >
                <Box
                  sx={{
                    width: 16,
                    height: 16,
                    borderRadius: "50%",
                    position: "relative",
                    zIndex: 1,
                    border: "2px solid",
                    borderColor: done || live ? designTokens.blue : designTokens.lineStrong,
                    bgcolor: done ? designTokens.blue : designTokens.surface,
                    boxShadow: live ? `0 0 0 4px ${designTokens.layer1Wash}` : "none",
                  }}
                />
                <Typography
                  variant="overline"
                  sx={{
                    fontSize: 11.5,
                    letterSpacing: "0.06em",
                    color: done || live ? designTokens.ink : designTokens.inkFaint,
                  }}
                >
                  {step}
                </Typography>
              </Box>
            );
          })}
        </Box>

        <PersonaCaption name={personaName} step={activeStep ?? null} />

        {toolCalls.length > 0 ? (
          <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1.25, mt: 2.25, alignItems: "center" }}>
            <Typography variant="body2" sx={{ color: designTokens.inkMuted }}>
              Querying
            </Typography>
            {toolCalls.map((call) => {
              const colour = layerColour(call.layer);
              return (
                <Box
                  key={`${call.name}-${call.detail}`}
                  data-testid={`tool-${call.name}`}
                  data-layer={call.layer}
                  sx={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 0.75,
                    fontFamily: "ui-monospace, monospace",
                    fontSize: 11.5,
                    fontWeight: 600,
                    px: 1,
                    py: 0.4,
                    borderRadius: 0.5,
                    border: `1px solid ${designTokens.line}`,
                    borderLeft: `4px solid ${colour.main}`,
                    bgcolor: colour.wash,
                  }}
                >
                  {call.name}
                  <Box component="span" sx={{ color: designTokens.inkMuted, fontWeight: 400 }}>
                    {call.detail}
                  </Box>
                </Box>
              );
            })}
          </Box>
        ) : null}
      </Box>
    </Box>
  );
}

export default RunScreen;
