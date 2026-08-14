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
  items: { id: string; question: string; meta?: string }[];
  activeId?: string | null;
  onOpen?: (id: string) => void;
  /** Collapse the rail (F-4.8-P-03). Omitted, the in-rail control is absent. */
  onCollapse?: () => void;
  /** The prototype's `.rnew`, which returns to the landing screen. */
  onNewSearch?: () => void;
  /** The signed-in account, named in the prototype's `.rfoot`. */
  accountEmail?: string;
}

/** The prototype's `.rmin` chevron, pointing left, toward the collapse. */
function CollapseIcon() {
  return (
    <svg
      width={15}
      height={15}
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.7}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M9.5 4 5.5 8l4 4" />
      <path d="M12.5 3.2v9.6" />
    </svg>
  );
}

/** The prototype's `#railStub` chevron, pointing right, toward the expand. */
function ExpandIcon() {
  return (
    <svg
      width={15}
      height={15}
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.7}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M6.5 4 10.5 8l-4 4" />
      <path d="M3.5 3.2v9.6" />
    </svg>
  );
}

export interface CollapsedRailProps {
  /** How many searches the collapsed rail is holding. */
  count: number;
  onExpand?: () => void;
}

/**
 * What a collapsed rail leaves behind: the prototype's `#railStub`.
 *
 * A collapsed rail that vanishes entirely gives the user nothing to aim at to
 * get it back, and no indication that anything is being held. The strip is 46px
 * of vertical label plus a count, which is the design's answer to both.
 *
 * It occupies the rail's own slot in the layout, so collapsing does not reflow
 * the page into a different shape than expanding restores.
 */
export function CollapsedRail({ count, onExpand }: CollapsedRailProps) {
  return (
    <Box
      component="button"
      type="button"
      onClick={onExpand}
      aria-label="Show your searches"
      data-testid="collapsed-rail"
      sx={{
        width: 46,
        flex: "none",
        border: 0,
        borderRight: `1px solid ${designTokens.line}`,
        // `--surface`, the prototype's own `#railStub` value, and the same
        // white the rail beside it now uses. An earlier version made this
        // `surfaceSunk` to match a rail that had drifted off the baseline;
        // bringing the rail back to `--surface` removed the reason for that.
        bgcolor: designTokens.surface,
        color: designTokens.inkMuted,
        cursor: "pointer",
        display: { xs: "none", md: "flex" },
        flexDirection: "column",
        alignItems: "center",
        gap: 1.75,
        py: 2,
        // `#railStub:hover{background:var(--surface-sunk);color:var(--ink)}`.
        "&:hover": { bgcolor: designTokens.surfaceSunk, color: designTokens.ink },
      }}
    >
      <ExpandIcon />
      <Typography
        component="span"
        sx={{
          writingMode: "vertical-rl",
          fontSize: 11.5,
          letterSpacing: ".1em",
          textTransform: "uppercase",
          fontWeight: 700,
        }}
      >
        Your searches
      </Typography>
      {count > 0 ? (
        <Box
          component="span"
          sx={{
            fontSize: 11,
            fontWeight: 700,
            color: "#FFFFFF",
            bgcolor: designTokens.blue,
            borderRadius: 999,
            minWidth: 19,
            px: 0.6,
            py: 0.25,
            lineHeight: 1.3,
            textAlign: "center",
          }}
        >
          {count}
        </Box>
      ) : null}
    </Box>
  );
}

/**
 * The rail of this session's questions.
 *
 * Transcribed from `prototype/app.html`'s `renderRail()` and its `#rail` CSS,
 * which is the approved baseline: a `.rtop` row pairing "+ New search" with the
 * collapse control, the `.rh` heading, either the `.ri` list or the `.rempty`
 * message, and the `.rfoot` naming the signed-in account.
 *
 * It renders even when empty, per the prototype's own `avail = st.loggedIn &&
 * onSearch`, which does not consider the history length. An earlier version
 * returned null on an empty list, reasoning that an empty rail is furniture.
 * That was a design change made at the code layer and is reverted here.
 */
export function HistoryRail({
  items,
  activeId,
  onOpen,
  onCollapse,
  onNewSearch,
  accountEmail,
}: HistoryRailProps) {
  return (
    <Box
      component="aside"
      aria-label="Your searches"
      data-testid="history-rail"
      sx={{
        // `#rail{width:248px;background:var(--surface);padding:14px 12px}`.
        width: 248,
        flex: "none",
        borderRight: `1px solid ${designTokens.line}`,
        bgcolor: designTokens.surface,
        p: "14px 12px",
        // `display:flex;flex-direction:column` is what lets `.rfoot`'s
        // `margin-top:auto` push the footer to the bottom of a full-height
        // rail, so it is structural rather than cosmetic.
        display: { xs: "none", md: "flex" },
        flexDirection: "column",
        overflowY: "auto",
      }}
    >
      {/* `.rtop`: the New search action and the collapse control, one row. */}
      <Box sx={{ display: "flex", gap: 1, alignItems: "stretch" }}>
        <Box
          component="button"
          type="button"
          onClick={onNewSearch}
          sx={{
            display: "flex",
            alignItems: "center",
            gap: 1,
            flex: 1,
            bgcolor: designTokens.blue,
            color: "#FFFFFF",
            border: 0,
            borderRadius: 0.5,
            p: "9px 12px",
            font: "inherit",
            fontSize: 13,
            fontWeight: 600,
            cursor: "pointer",
            "&:hover": { bgcolor: designTokens.navy },
          }}
        >
          + New search
        </Box>
        {onCollapse ? (
          <Box
            component="button"
            type="button"
            onClick={onCollapse}
            aria-label="Hide your searches"
            sx={{
              flex: "none",
              width: 34,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              bgcolor: "transparent",
              border: `1px solid ${designTokens.line}`,
              borderRadius: 0.5,
              color: designTokens.inkMuted,
              cursor: "pointer",
              "&:hover": {
                borderColor: designTokens.lineStrong,
                color: designTokens.ink,
                bgcolor: designTokens.surfaceSunk,
              },
            }}
          >
            <CollapseIcon />
          </Box>
        ) : null}
      </Box>

      {/*
        `.rh`. inkFaint is the prototype's own token here, and it is AA-safe on
        this rail now that the rail is `--surface`: #71767A measures 4.73:1 on
        white. The previous version used inkMuted precisely BECAUSE the rail was
        `surfaceSunk`, where inkFaint drops to 4.31:1 and fails. Restoring the
        prototype's surface is what makes restoring its token safe, so these two
        changes belong together rather than one at a time.
      */}
      <Typography
        component="p"
        sx={{
          fontSize: 10.5,
          letterSpacing: ".12em",
          textTransform: "uppercase",
          fontWeight: 700,
          color: designTokens.inkFaint,
          p: "10px 8px 6px",
          m: 0,
        }}
      >
        Your searches
      </Typography>

      {items.length === 0 ? (
        // `.rempty`, verbatim from the prototype.
        <Typography
          component="p"
          sx={{
            p: "6px 10px",
            fontSize: 12.5,
            color: designTokens.inkFaint,
            lineHeight: 1.5,
            m: 0,
          }}
        >
          Searches you run in this session appear here, with their sources attached.
        </Typography>
      ) : (
        items.map((item) => (
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
              lineHeight: 1.45,
              p: "9px 10px",
              borderRadius: 0.5,
              cursor: "pointer",
              border: 0,
              // `.ri` is `--ink` and `.ri.on` is `--l1-wash` + `--blue` + 600.
              // The previous version dimmed the INACTIVE rows to inkMuted,
              // which the prototype does not do.
              color: item.id === activeId ? designTokens.blue : designTokens.ink,
              fontWeight: item.id === activeId ? 600 : 400,
              bgcolor: item.id === activeId ? designTokens.layer1Wash : "transparent",
              "&:hover": {
                bgcolor:
                  item.id === activeId ? designTokens.layer1Wash : designTokens.surfaceSunk,
              },
            }}
          >
            {/* `.rq`: two lines, then ellipsis. */}
            <Box
              component="span"
              sx={{
                display: "-webkit-box",
                WebkitLineClamp: 2,
                WebkitBoxOrient: "vertical",
                overflow: "hidden",
              }}
            >
              {item.question}
            </Box>
            {/* `.rm`: this search's own tool, layer and source counts. Absent
                until its run lands, which the prototype allows for too. */}
            {item.meta ? (
              <Box
                component="span"
                sx={{
                  display: "block",
                  fontSize: 11.5,
                  /*
                   * The prototype's `.rm` is `--ink-faint` on every row. That
                   * passes AA on the rail's white ground (4.73:1) and FAILS on
                   * the active row's `--l1-wash` (3.92:1, measured by axe, not
                   * assumed). WCAG 2.1 AA is a merge gate in this repository,
                   * so the active row steps up to inkMuted (5.74:1) rather
                   * than shipping a violation.
                   *
                   * This is a deviation from the prototype forced by a defect
                   * IN the prototype, and it is the second instance of the
                   * same one: inkFaint is AA-safe on some of the design
                   * system's own surfaces and not others, and nothing in the
                   * design system says so. Filed as F-4.8-D-08.
                   */
                  color:
                    item.id === activeId ? designTokens.inkMuted : designTokens.inkFaint,
                  fontWeight: 400,
                  mt: "2px",
                }}
              >
                {item.meta}
              </Box>
            ) : null}
          </Box>
        ))
      )}

      {/*
        `.rfoot`. `margin-top:auto` pins it to the bottom of the rail. The email
        is the account that just signed in, not a placeholder; when it is absent
        the whole footer is omitted rather than showing an empty line.
      */}
      {accountEmail ? (
        <Box
          sx={{
            mt: "auto",
            borderTop: `1px solid ${designTokens.line}`,
            p: "12px 10px 4px",
            fontSize: 12,
            color: designTokens.inkFaint,
          }}
        >
          {/*
            Two block spans rather than the prototype's raw `<br>`. Visually
            identical, and it gives the email its own element so a check can
            assert the account name on its own instead of matching a run-on
            string.
          */}
          <Box component="span" sx={{ display: "block" }}>
            {accountEmail}
          </Box>
          <Box component="span" sx={{ display: "block" }}>
            Unlimited searches
          </Box>
        </Box>
      ) : null}
    </Box>
  );
}

export default FollowUp;
