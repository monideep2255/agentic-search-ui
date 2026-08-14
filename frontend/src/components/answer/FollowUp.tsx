/**
 * Follow-up questions and the history rail, build phase 4.8, ticket T-4.8-09.
 *
 * A follow-up runs a FULL search. It is not a chat turn that reuses a previous
 * answer, and the copy says so, because the difference is the product's whole
 * argument: prior context influences what gets looked up, never what gets
 * asserted. Section 14.1's personalization firewall keeps session memory in
 * orchestration and out of grounding, so a follow-up's citations are as
 * independently verifiable as a first question's.
 *
 * STUB: hints are canned and history is in-memory, lost on reload. Wired by
 * build phase 4.5 for the session and 4.6 for anything that must survive a
 * reload. See `stubs/registry.ts`.
 */

import { useState } from "react";
import type { FormEvent } from "react";
import { Box, Typography } from "@mui/material";

import { designTokens } from "../../theme";

export interface FollowUpProps {
  hints?: string[];
  onAsk?: (question: string) => void;
}

export function FollowUp({ hints = [], onAsk }: FollowUpProps) {
  const [text, setText] = useState("");

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const trimmed = text.trim();
    if (trimmed) {
      onAsk?.(trimmed);
      setText("");
    }
  };

  return (
    <Box
      data-testid="follow-up"
      sx={{ mt: 3, pt: 2.25, borderTop: `1px solid ${designTokens.line}` }}
    >
      <Box
        component="form"
        onSubmit={submit}
        sx={{
          display: "flex",
          alignItems: "center",
          gap: 1.25,
          border: `1px solid ${designTokens.lineStrong}`,
          borderRadius: 1,
          px: 1.75,
          py: 0.75,
          bgcolor: designTokens.surface,
          "&:focus-within": { borderColor: designTokens.link },
        }}
      >
        <Box
          component="input"
          type="text"
          aria-label="Ask a follow-up question"
          placeholder="Ask a follow-up"
          value={text}
          onChange={(event: React.ChangeEvent<HTMLInputElement>) => setText(event.target.value)}
          sx={{
            flex: 1,
            border: 0,
            outline: 0,
            font: "inherit",
            fontSize: 15,
            py: 0.75,
            bgcolor: "transparent",
          }}
        />
        <Box
          component="button"
          type="submit"
          sx={{
            font: "inherit",
            fontSize: 13.5,
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
          Ask
        </Box>
      </Box>

      {hints.length > 0 ? (
        <Box sx={{ display: "flex", flexWrap: "wrap", gap: 0.75, mt: 1.5 }}>
          {hints.map((hint) => (
            <Box
              key={hint}
              component="button"
              type="button"
              onClick={() => onAsk?.(hint)}
              sx={{
                font: "inherit",
                fontSize: 12.5,
                px: 1.4,
                py: 0.5,
                borderRadius: 999,
                cursor: "pointer",
                color: designTokens.inkMuted,
                bgcolor: designTokens.surfaceSunk,
                border: `1px solid ${designTokens.line}`,
                "&:hover": { color: designTokens.ink, borderColor: designTokens.lineStrong },
              }}
            >
              {hint}
            </Box>
          ))}
        </Box>
      ) : null}

      <Typography variant="caption" sx={{ display: "block", mt: 1.5, color: designTokens.inkFaint }}>
        A follow-up runs a full search. Earlier context guides what gets looked up, never what
        gets asserted, so every claim is cited from scratch.
      </Typography>
    </Box>
  );
}

export interface HistoryRailProps {
  items: { id: string; question: string }[];
  activeId?: string | null;
  onOpen?: (id: string) => void;
}

/**
 * The rail of this session's questions.
 *
 * Rendered only when there is something in it. An empty rail on a first visit
 * is furniture that makes the product look busier than it is.
 */
export function HistoryRail({ items, activeId, onOpen }: HistoryRailProps) {
  if (items.length === 0) return null;

  return (
    <Box
      component="aside"
      aria-label="Your searches"
      data-testid="history-rail"
      sx={{
        width: 240,
        flex: "none",
        borderRight: `1px solid ${designTokens.line}`,
        bgcolor: designTokens.surfaceSunk,
        py: 2.5,
        px: 1.5,
        display: { xs: "none", md: "block" },
      }}
    >
      <Typography
        variant="overline"
        component="p"
        // inkMuted, not inkFaint. inkFaint (#71767A) measures 4.73:1 on white,
        // which passes AA, but only 4.31:1 on surfaceSunk (#F7F8F9), which is
        // this rail's own ground. That is a design-system defect rather than a
        // one-off: the token is AA-safe on one surface and not the other, and
        // nothing in the design system says so. Recorded as a finding for the
        // next design pass; the token itself is frozen for this phase and is
        // not being changed unilaterally here.
        sx={{ color: designTokens.inkMuted, mb: 1.25, px: 0.75 }}
      >
        Your searches
      </Typography>
      {items.map((item) => (
        <Box
          key={item.id}
          component="button"
          type="button"
          onClick={() => onOpen?.(item.id)}
          sx={{
            display: "block",
            width: "100%",
            textAlign: "left",
            font: "inherit",
            fontSize: 13,
            px: 1,
            py: 1,
            mb: 0.4,
            borderRadius: 0.5,
            cursor: "pointer",
            border: 0,
            color: item.id === activeId ? designTokens.ink : designTokens.inkMuted,
            bgcolor: item.id === activeId ? designTokens.layer1Wash : "transparent",
            "&:hover": { bgcolor: designTokens.canvasDeep },
          }}
        >
          {item.question}
        </Box>
      ))}
    </Box>
  );
}

export default FollowUp;
