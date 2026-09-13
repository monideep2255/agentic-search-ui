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
 * STUB: hints are canned. History is durable across a reload as of build
 * phase 4.13 (T-4.13-03): `HistoryRail` still only renders whatever list
 * `App.tsx` gives it, but that list is now seeded from `GET /v1/history`,
 * not held in memory alone. Only the question survives; the `interactions`
 * row it is read from stores no answer narrative, so a restored item
 * re-asks its question rather than replaying an old answer (decision
 * D-4.13-01, `tracker/phase_4.13.md`). See `stubs/registry.ts`.
 */

import { useState } from "react";
import type { FormEvent } from "react";
import { Box, Drawer, Typography, useMediaQuery, useTheme } from "@mui/material";

import { designTokens } from "../../theme";

export interface FollowUpProps {
  hints?: string[];
  onAsk?: (question: string) => void;
  /**
   * T-6.2-08. The backend's offer of somewhere to go next, or null.
   *
   * Rendered as ONE offer above the hint row rather than as a fourth hint,
   * and the distinction is the point rather than styling. The hints are a
   * fixed MENU that is the same on every answer; this is a single sentence
   * about THIS answer, derived from what this retrieval actually left out.
   * Folding it into the menu would make a specific, earned offer look like
   * the generic three.
   *
   * Accepting it dispatches through the same `onAsk` as anything typed, so
   * it continues the thread rather than starting over. That ordering was
   * the product-owner's condition on this feature: an offer the system
   * makes and then forgets making is worse than no offer.
   */
  nextStep?: string | null;
}

export function FollowUp({ hints = [], onAsk, nextStep = null }: FollowUpProps) {
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
      data-tour="followup"
      sx={{ mt: 3, pt: 2.25, borderTop: `1px solid ${designTokens.line}` }}
    >
      {/*
        The prototype's `<label for="fubox">Continue this conversation</label>`
        (F-4.8-D-11). The form had no heading at all, so the field read as an
        afterthought under the answer rather than the invitation it is.
      */}
      <Typography
        component="p"
        sx={{
          fontSize: 10.5,
          letterSpacing: ".12em",
          textTransform: "uppercase",
          fontWeight: 700,
          color: designTokens.inkFaint,
          m: 0,
          mb: 1,
        }}
      >
        Continue this conversation
      </Typography>
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

      {nextStep ? (
        <Box
          data-testid="next-step-offer"
          sx={{
            mt: 1.75,
            p: 1.5,
            borderRadius: 0.5,
            border: `1px solid ${designTokens.line}`,
            bgcolor: designTokens.surfaceSunk,
            display: "flex",
            alignItems: "center",
            gap: 1.5,
            flexWrap: "wrap",
          }}
        >
          <Typography sx={{ fontSize: 14, flex: 1, minWidth: 220 }}>
            {nextStep}
          </Typography>
          {/*
            A real button, not a chip styled like one. Accepting an offer is
            the same action as typing the question, so it goes through the
            same `onAsk` and therefore continues the thread.
          */}
          <Box
            component="button"
            type="button"
            data-testid="next-step-accept"
            onClick={() => onAsk?.(nextStep)}
            sx={{
              font: "inherit",
              fontSize: 13.5,
              fontWeight: 600,
              px: 1.6,
              py: 0.75,
              borderRadius: 0.5,
              cursor: "pointer",
              color: "#FFFFFF",
              bgcolor: designTokens.blue,
              border: 0,
            }}
          >
            Yes, go deeper
          </Box>
        </Box>
      ) : null}

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
  /**
   * The account's real daily search limit, in words (T-4.10-09, closing
   * F-4.9-A-16: this line used to read a hardcoded "Unlimited searches"
   * against a real, enforced 100/day cap). Built by
   * `lib/guestSession.ts`'s `dailyLimitPhrase`, the SAME function
   * `AccountMenu`'s menu line uses, so the two surfaces cannot disagree.
   * `App.tsx` owns the fetch and the capitalization; this component only
   * renders what it is given, falling back to a plain, honest "no number
   * claimed" line while the fetch is in flight or if it fails.
   */
  searchLimitLabel?: string;
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
  const theme = useTheme();
  // Fix set 4 (R46, decision U9, 2026-09-13). A 40px strip beside phone
  // content is not the design, only this component's own desktop fallback,
  // and the app bar's rail toggle (now visible at every width, see
  // `AppShell.tsx`) is the way back in below `md`. Returning null here
  // rather than continuing to rely on the `display: { xs: "none" }` below
  // matches what the mounting side in `App.tsx` now expects: a phone never
  // renders this strip at all.
  const isNarrow = useMediaQuery(theme.breakpoints.down("md"));
  if (isNarrow) return null;

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
        display: "flex",
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
  searchLimitLabel,
}: HistoryRailProps) {
  const theme = useTheme();
  // Fix set 4 (R46, decision U9, 2026-09-13): history reachable on a phone.
  //
  // NO PHONE DESIGN EXISTS FOR THIS RAIL. `docs/build/design/README.md`
  // records `prototype/app.html:65` simply hiding `#rail` at 860px and
  // calling that a known defect, not a design. So this is built from the
  // rail itself, unchanged, plus the nearest designed phone-pattern
  // neighbour this app already has: `NavOverflowMenu` in
  // `components/shell/AppShell.tsx`, a control that opens to reach content
  // a narrow bar has no room for inline. The product owner's instruction
  // (U9) was a panel that slides in and closes, which is what a MUI
  // `Drawer` gives the same rail content without restyling it.
  const isNarrow = useMediaQuery(theme.breakpoints.down("md"));

  const rail = (
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
        //
        // Unconditionally flex, not the old `{ xs: "none", md: "flex" }`.
        // Below `md` this element now renders only inside the `Drawer`
        // below, built by the `isNarrow` branch, which already decides
        // whether this tree mounts at all; a second, CSS-level hide here
        // would just fight that decision.
        display: "flex",
        flexDirection: "column",
        overflowY: "auto",
        // Product-owner feedback, 2026-09-13: signed in, the search bar sat
        // low on the landing screen while a signed-out visitor saw it
        // centred. The rail was the cause. Its history list is longer than
        // the viewport, and a flex row is as tall as its tallest child, so
        // the hero beside it grew to the list's height and centred its
        // content halfway down a page that scrolled behind the sticky
        // footer. Pinning the rail to the viewport, the same way the app
        // bar and footer already are (set 2, R9 and R11), lets the row keep
        // the viewport's height whatever the list holds, so the hero is
        // centred exactly as it is with no rail at all, and the list
        // scrolls inside the rail. 54px is the app bar's `minHeight`, 44px
        // the footer's rendered height (12px padding each side around a
        // 20px caption line). Not applied inside the phone drawer, which
        // already gives the rail the full height on its own.
        ...(isNarrow
          ? {}
          : {
              position: "sticky",
              top: 54,
              alignSelf: "flex-start",
              maxHeight: "calc(100dvh - 54px - 44px)",
            }),
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
        // `.rempty`. NO LONGER the prototype's own text verbatim: that copy
        // read "Searches you run in this session appear here", which build
        // phase 4.13 (T-4.13-03) made false the moment the rail started
        // seeding from `GET /v1/history` rather than living only in React
        // state. The prototype predates durable history and was never
        // updated; this is the one place this component deliberately
        // diverges from it, and it diverges on a factual claim, not on
        // presentation.
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
          Your searches appear here, with their sources attached.
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
            {/* `.rm`. For a live run, this session's own tool, layer and
                source counts, absent until the run lands, which the
                prototype allows for too. For a row restored from
                `GET /v1/history` (F-4.13-A-10), the endpoint carries no
                tool or layer count, only `citation_count` and `asked_at`,
                so `App.tsx`'s `formatHistoryMeta` renders the closest
                honest substitute instead: a source count and a short
                date. Either way this component only renders whatever
                `item.meta` already is; it does not know which shape
                produced it. */}
            {item.meta ? (
              <Box
                component="span"
                sx={{
                  display: "block",
                  fontSize: 11.5,
                  /*
                   * `--ink-faint` on every row, exactly as the prototype has
                   * it. This carried a conditional step-up to inkMuted on the
                   * active row until 2026-08-14, because the old #71767A
                   * measured 3.92:1 on `--l1-wash` against a 4.5:1
                   * requirement. F-4.8-D-08 fixed the token in the design
                   * system itself (#666B70, now 4.60:1 on that same ground),
                   * which removed the reason for the deviation, so the
                   * deviation goes with it.
                   */
                  color: designTokens.inkFaint,
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
            {searchLimitLabel ?? "Search limit applies"}
          </Box>
        </Box>
      ) : null}
    </Box>
  );

  if (!isNarrow) return rail;

  // Below `md`: the same rail, sliding in over the page rather than sitting
  // beside it. `open` is always true while this component is mounted;
  // `App.tsx` decides whether `HistoryRail` mounts at all (the same
  // `railOpen` state the desktop column already used), so the Drawer only
  // ever needs to reflect that one decision, never track a second copy of
  // it. `onClose` fires on a backdrop tap or Escape and runs through the
  // same `onCollapse` the rail's own `.rtop` control already calls, so
  // there is exactly one way to close this panel, not two competing ones.
  return (
    <Drawer
      anchor="left"
      variant="temporary"
      open
      onClose={onCollapse}
      ModalProps={{ keepMounted: false }}
      // `slotProps.paper`, not the deprecated `PaperProps`: this MUI major
      // version stopped forwarding `PaperProps` to the paper slot at all
      // (it already sets `role="dialog"` itself for a temporary drawer,
      // which is how this panel gets that role), so `PaperProps` here would
      // silently do nothing rather than merely being old-fashioned.
      slotProps={{
        paper: {
          "aria-label": "Your searches",
          sx: {
            width: 280,
            maxWidth: "85vw",
            bgcolor: designTokens.surface,
            borderRight: `1px solid ${designTokens.line}`,
          },
        },
      }}
    >
      {rail}
    </Drawer>
  );
}

export default FollowUp;
