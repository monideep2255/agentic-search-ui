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
  /** The live step, or null before the run starts or after it lands. */
  activeStep?: StepName | null;
  /**
   * Steps the run actually reached. A landed run has no live step, so without
   * this the whole stepper would read as pending the moment it finished.
   */
  reachedSteps?: StepName[];
  toolCalls?: ToolCall[];
  personaName?: string;
  onStop?: () => void;
  onNewSearch?: () => void;
  /**
   * Whether Stop is still meaningful.
   *
   * Derived from the run's own events by `deriveStopEnabled`, which has 19
   * tests behind it. An earlier version of this screen offered Stop
   * unconditionally, including after the run had already finished.
   */
  stopEnabled?: boolean;
  /** Guardrail refusal copy, when the question was turned away. */
  refusal?: string | null;
  /** Cap copy, when the run stopped early on its processing budget. */
  capMessage?: string | null;
  /** A stream-level failure, surfaced rather than left as a silent hang. */
  failure?: string | null;
}

/**
 * A refusal or cap notice.
 *
 * Deliberately plain and free of any cost figure: the copy comes from a fixed
 * lookup table with no interpolation slot, so a dollar amount cannot reach a
 * user-facing refusal even by accident.
 */
function Notice({ testId, tone, text }: { testId: string; tone: "warn"; text: string }) {
  return (
    <Box
      data-testid={testId}
      role="status"
      sx={{
        mt: 2.25,
        px: 1.75,
        py: 1.4,
        fontSize: 13.5,
        borderRadius: 0.5,
        border: `1px solid ${designTokens.warn}`,
        borderLeftWidth: 4,
        bgcolor: tone === "warn" ? designTokens.warnWash : designTokens.surfaceSunk,
      }}
    >
      {text}
    </Box>
  );
}

export function RunScreen({
  question,
  activeStep = "Guard",
  reachedSteps = [],
  toolCalls = [],
  personaName = "Mendel",
  onStop,
  onNewSearch,
  stopEnabled = true,
  refusal = null,
  capMessage = null,
  failure = null,
}: RunScreenProps) {
  const activeIndex = activeStep ? STEPS.indexOf(activeStep) : -1;
  const reached = new Set(reachedSteps);

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
          <Button
            onClick={onStop}
            disabled={!stopEnabled}
            sx={{
              fontSize: 12.5,
              color: designTokens.inkMuted,
              border: `1px solid ${designTokens.lineStrong}`,
              px: 1.6,
              py: 0.6,
            }}
          >
            Stop
          </Button>
          <Button onClick={onNewSearch} sx={{ fontSize: 12.5, color: designTokens.inkMuted, border: `1px solid ${designTokens.line}`, px: 1.6, py: 0.6 }}>
            New search
          </Button>
        </Box>

        <Box sx={{ display: "flex", alignItems: "flex-start" }}>
          {STEPS.map((step, index) => {
            // Done if the run genuinely reached it, or if it precedes the live
            // step. The first clause is what keeps a finished run's stepper
            // truthful after activeStep goes null.
            const live = activeIndex === index;
            const done = !live && (reached.has(step) || activeIndex > index);
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

        {refusal ? (
          <Notice testId="guardrail-notice" tone="warn" text={refusal} />
        ) : null}
        {capMessage ? (
          <Notice testId="cap-notice" tone="warn" text={capMessage} />
        ) : null}
        {failure ? <Notice testId="run-failure" tone="warn" text={failure} /> : null}

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
