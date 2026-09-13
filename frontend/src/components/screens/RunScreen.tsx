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
 * WHAT THIS FILE IS AFTER UI FIX SET 7 (R22): the PAGE, and nothing else.
 * Everything inside the card moved to `RunProgress.tsx` so the answer screen
 * can render the same stepper, counter, Stop and reasoning log inline while a
 * follow-up runs, instead of the whole screen being replaced by this one. The
 * product owner's words were "it goes to a new page, which it should not".
 *
 * This screen is still what a FIRST question gets: a question asked from the
 * landing screen, or reopened from the history rail, starts a conversation
 * rather than continuing one, and there is no earlier turn to keep on screen.
 *
 * Source of truth: `docs/build/design/design-system/components/pipeline-stepper.html`
 * and `screens/streaming.html`.
 */

import { Box } from "@mui/material";

import { designTokens } from "../../theme";
import { RunProgress } from "./RunProgress";
import type { RunProgressProps } from "./RunProgress";

export { STEPS } from "./RunProgress";
export type { ReasoningStep, StepName, ToolCall } from "./RunProgress";

/**
 * The full-screen run's props.
 *
 * `question` is required here, unlike on `RunProgress`, where the inline
 * continuation omits it because the answer screen renders the heading
 * itself. A full-screen run with no question would be a page with no subject.
 */
export interface RunScreenProps extends Omit<RunProgressProps, "question"> {
  question: string;
}

export function RunScreen(props: RunScreenProps) {
  return (
    // Set 2, R8: `width: 100%` because `mx: auto` in a flex column stops the
    // box stretching, which made this card shrink to its content and grow
    // when the answer screen replaced it. Both screens are now the full 900.
    // `my: auto` centres the card vertically, product-owner feedback
    // 2026-09-12, the same as the log-in screen.
    <Box sx={{ width: "100%", maxWidth: 900, mx: "auto", my: "auto", px: 3, py: 3.5 }}>
      <Box
        sx={{
          bgcolor: designTokens.surface,
          border: `1px solid ${designTokens.line}`,
          borderRadius: 1,
          p: { xs: 2.5, sm: 3.25 },
        }}
      >
        <RunProgress {...props} />
      </Box>
    </Box>
  );
}

export default RunScreen;
