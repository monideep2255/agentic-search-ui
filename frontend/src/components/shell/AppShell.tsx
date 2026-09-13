/**
 * The app shell, build phase 4.8, ticket T-4.8-03.
 *
 * The chrome every screen sits inside: the app bar and the footer.
 *
 * UPDATED 2026-09-05, product-owner decision: the shell used to also carry a
 * permanent, non-dismissible disclaimer strip on every screen. That strip is
 * gone. The disclaimer is now shown exactly once, on the home page, the first
 * time a visitor arrives in a session, by `DisclaimerModal.tsx`, which this
 * file does not render and does not own. See the comment left in its place,
 * below, for the reasoning.
 *
 * Source of truth: `docs/build/design/design-system/components/app-bar.html`
 * and the approved prototype.
 */

import { useEffect, useId, useRef, useState } from "react";
import type { ReactNode } from "react";
import { AppBar, Box, Button, IconButton, Toolbar, Typography } from "@mui/material";

import { designTokens } from "../../theme";
import { Logo } from "../brand/Logo";
import { PersonaChip } from "./PersonaChip";
import { AccountMenu } from "./AccountMenu";

/**
 * The screens reachable from the bar.
 *
 * `docs` is GONE, fix set 5 (R18, 2026-09-13). The product owner could not
 * tell what the Docs tab was for, and its content was a short technical
 * reference for the integration surfaces, so it is now the "API
 * documentation" section inside `IntegrationsScreen`. `/docs` still routes,
 * to Integrations, so an existing link is not broken (see `lib/routing.ts`'s
 * `LEGACY_PATHS`).
 */
export type ScreenName = "search" | "integrations" | "about";

const NAV: { key: ScreenName; label: string }[] = [
  // Order transcribed from the prototype's `.nav` (F-4.8-D-09). Docs and About
  // were the other way round, which every membership assertion accepted.
  // Docs itself was removed by R18; the remaining three keep that order.
  { key: "search", label: "Search" },
  { key: "integrations", label: "Integrations" },
  { key: "about", label: "About" },
];

export interface AppShellProps {
  children: ReactNode;
  /** Which nav item reads as current. */
  current?: ScreenName;
  onNavigate?: (screen: ScreenName) => void;
  /** The session's persona. Stubbed; wired by build phase 4.5. */
  /** Server-assigned persona (T-4.5-10); null until the first run returns. */
  personaName?: string | null;
  signedIn?: boolean;
  accountEmail?: string;
  /** Forwarded to `AccountMenu`'s `limitCopy` (T-4.10-09). See that prop's own docstring. */
  accountLimitCopy?: string;
  onSignIn?: () => void;
  onSignOut?: () => void;
  /**
   * Suppress the bar's own auth action.
   *
   * Set while the sign-in screen is already open. Offering "Log in" in the bar
   * next to a sign-in form gives the page two controls with the same
   * accessible name and no way for a screen reader user to tell them apart,
   * which is a real defect rather than a test inconvenience.
   */
  hideAuthAction?: boolean;
  /**
   * Show the stored-searches toggle at the far left of the bar (F-4.8-P-03).
   *
   * The prototype gates this on `avail = st.loggedIn && onSearch`, so the
   * caller decides: a control that toggles a rail which is not on screen is
   * worse than no control. Absent by default, which keeps every existing
   * caller's bar unchanged.
   */
  showRailToggle?: boolean;
  /** Whether the rail is currently open. Drives `aria-expanded`. */
  railOpen?: boolean;
  onToggleRail?: () => void;
}

/** The rail toggle's mark, transcribed from the prototype's `#railBtn`. */
function RailToggleIcon() {
  return (
    <svg
      width={18}
      height={18}
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.7}
      strokeLinecap="round"
      aria-hidden="true"
    >
      <path d="M2 4h12M2 8h12M2 12h12" />
    </svg>
  );
}

/**
 * The nav overflow trigger's mark: three dots, the ordinary shorthand for
 * "more". No foundation in the design system supplies this mark, since the
 * design has no overflow menu at all below 720px (`prototype/app.html:403`
 * simply drops the other pages). Drawn in the same stroke language as
 * `RailToggleIcon` above it, rather than inventing a new visual idiom, per
 * `.claude/rules/design-consistency.md`'s instruction to build a missing
 * surface from the foundations and the nearest designed neighbour.
 */
function MoreIcon() {
  return (
    <svg width={18} height={18} viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
      <circle cx="3" cy="8" r="1.4" />
      <circle cx="8" cy="8" r="1.4" />
      <circle cx="13" cy="8" r="1.4" />
    </svg>
  );
}

/**
 * The overflow menu that reaches the nav items a narrow bar has no room for.
 *
 * OVERRULES `prototype/app.html:403`, product-owner decision, 2026-09-05. The
 * design hides every nav item but the current page below 720px and provides
 * no way to reach the others, which is what shipped first here, transcribed
 * faithfully. The product owner overruled it: it made Integrations and About
 * unreachable on a phone with no path back to them. This menu is
 * the fix, and a future reader must not "correct" it back to the design.
 * Since R18 removed the Docs tab it holds two items rather than three, which
 * is what decision X6 records.
 *
 * No design exists for this control at all, so its wiring is copied from
 * `AccountMenu.tsx`, the nearest working precedent in this product: the same
 * `aria-haspopup="menu"`, `aria-expanded`, `aria-controls`, `role="menu"` and
 * `role="menuitem"` attributes, and the same close-on-outside-mousedown and
 * close-on-Escape behaviour. Its trigger, though, matches the bar's own icon
 * buttons (`RailToggleIcon`'s pattern) rather than `AccountMenu`'s pill,
 * since it sits among plain nav buttons and a full pill would not fit the
 * widths this control exists to serve.
 *
 * Renders nothing when there is nothing left to show, which keeps a caller
 * from having to compute that itself.
 */
function NavOverflowMenu({
  items,
  onNavigate,
}: {
  items: { key: ScreenName; label: string }[];
  onNavigate?: (screen: ScreenName) => void;
}) {
  const [open, setOpen] = useState(false);
  const menuId = useId();
  const wrapRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open) return undefined;
    const onDown = (event: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(event.target as Node)) setOpen(false);
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  if (items.length === 0) return null;

  return (
    <Box
      ref={wrapRef}
      sx={{
        position: "relative",
        // Hidden above 720px, the same breakpoint the inline nav items use
        // to decide whether they need this menu at all: above it, every item
        // fits inline and there is nothing for this control to hold.
        display: "none",
        "@media (max-width:720px)": { display: "block" },
      }}
    >
      <IconButton
        onClick={() => setOpen((value) => !value)}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={open ? menuId : undefined}
        aria-label="More pages"
        sx={{
          color: "#FFFFFF",
          p: 0.75,
          borderRadius: 1,
          "&:hover": { bgcolor: "rgba(255,255,255,.16)" },
        }}
      >
        <MoreIcon />
      </IconButton>
      {open ? (
        <Box
          id={menuId}
          role="menu"
          sx={{
            position: "absolute",
            right: 0,
            top: "calc(100% + 9px)",
            width: 190,
            bgcolor: designTokens.surface,
            border: `1px solid ${designTokens.line}`,
            borderRadius: 1,
            boxShadow: "0 14px 34px rgba(0,0,0,.2)",
            zIndex: 60,
            p: 0.75,
            color: designTokens.ink,
            textAlign: "left",
          }}
        >
          {items.map(({ key, label }) => (
            <Box
              key={key}
              component="button"
              type="button"
              role="menuitem"
              onClick={() => {
                setOpen(false);
                onNavigate?.(key);
              }}
              sx={{
                display: "block",
                width: "100%",
                textAlign: "left",
                background: "none",
                border: 0,
                p: "7px 10px",
                borderRadius: 0.5,
                font: "inherit",
                fontSize: 13,
                color: designTokens.ink,
                cursor: "pointer",
                "&:hover": { bgcolor: designTokens.surfaceSunk },
              }}
            >
              {label}
            </Box>
          ))}
        </Box>
      ) : null}
    </Box>
  );
}

export function AppShell({
  children,
  current = "search",
  onNavigate,
  personaName = null,
  signedIn = false,
  accountEmail,
  accountLimitCopy,
  onSignIn,
  onSignOut,
  hideAuthAction = false,
  showRailToggle = false,
  railOpen = true,
  onToggleRail,
}: AppShellProps) {
  return (
    <Box sx={{ minHeight: "100vh", display: "flex", flexDirection: "column", bgcolor: designTokens.canvas }}>
      {/* Set 2, R9 (2026-09-12): the bar stays put while the page scrolls. */}
      <AppBar position="sticky" component="header">
        {/*
            THE MOBILE BAR FOLLOWS THE PROTOTYPE, and the first attempt at
            this did not, which is the correction worth recording.

            The defect was real and measured 2026-09-05 at 390px: the brand
            button had `minWidth: 0` and no wrap control, so "NCBI Agentic
            Search" broke across three lines and OVERLAPPED the Search nav
            item, with "Log in" clipped at the right edge. Journey 7's
            evidence from 2026-09-01 shows the same collision, and
            `docs/build/UI_feedback.md` records the viewport as an "8px
            horizontal bleed", which was the measurement rather than the
            defect.

            THE FIRST FIX WRAPPED THE BAR TO TWO ROWS AND WAS INVENTED.
            `components/app-bar.html` carries no responsive rule, and that
            was read as "no mobile design exists". It does exist, in
            `prototype/app.html`, which is the assembled design and part of
            the same system: line 403 is
            `.nav button:not(.on):not(.login){display:none}` at 720px, and
            line 404 tightens `.appbar` to `padding:0 14px;gap:10px`. So the
            design keeps ONE row and drops the nav items a phone cannot fit,
            leaving the current page and the auth action. That is what is
            implemented below, at the design's own 720px rather than at a
            MUI breakpoint, because the design names a pixel value.

            `.claude/rules/design-consistency.md` exists because of exactly
            this: a missing design and a design you did not find look
            identical from the browser, and only one of them licenses
            invention.

            UPDATED 2026-09-05, product-owner decision, OVERRULING
            `prototype/app.html:403`. The consequence named above stopped
            being a flagged product question and became a defect to fix:
            below 720px, Integrations and About were unreachable, with
            no menu to reach them from, on a phone. The design's own choice
            still drops those items from the inline row below 720px, and
            that part is unchanged below. What changed is that they no
            longer vanish: `NavOverflowMenu`, defined above, reaches them
            from one control in the bar. A future reader must not "fix" this
            back to the design; the design is what created the defect.
          */}
          <Toolbar
            sx={{
              minHeight: 54,
              gap: 2,
              px: { xs: 1.5, sm: 2.25 },
              "@media (max-width:720px)": { px: "14px", gap: "10px" },
            }}
          >
          {/*
            First in the bar, left of the brand, exactly where the prototype's
            `#railBtn` sits. `aria-expanded` carries the rail's real state, so
            a screen reader user is told what the control will do rather than
            having to press it to find out.

            `display: { xs: "none", md: "flex" }` added 2026-09-05, product-
            owner decision, and REMOVED here, fix set 4 (R46, decision U9,
            2026-09-13). It hid this button below `md` because the rail it
            operates, `HistoryRail` and `CollapsedRail` in
            `components/answer/FollowUp.tsx`, both carried
            `display: { xs: "none", md: "flex" }` and neither rendered below
            `md`, so a signed-in visitor on a phone would have seen a
            visible, enabled control that did nothing.

            That is no longer true. `HistoryRail` now renders below `md` as a
            sliding panel (a MUI `Drawer`) instead of a column, and
            `CollapsedRail` returns null there since a 40px strip beside phone
            content was never the design and this toggle is the way back in.
            So this button now has something to operate at every width, and
            hiding it would make history unreachable on a phone, which is the
            defect U9 exists to close. Visible at every width; `md: "flex"`
            stays as the value, it no longer differs from what renders below
            it.
          */}
          {showRailToggle ? (
            <IconButton
              onClick={onToggleRail}
              aria-label="Show or hide your searches"
              aria-expanded={railOpen}
              sx={{
                display: "flex",
                color: "#FFFFFF",
                p: 0.75,
                borderRadius: 1,
                mr: -1,
                "&:hover": { bgcolor: "rgba(255,255,255,.16)" },
              }}
            >
              <RailToggleIcon />
            </IconButton>
          ) : null}

          <Button
            onClick={() => onNavigate?.("search")}
            sx={{
              color: "#FFFFFF",
              fontWeight: 700,
              fontSize: 15,
              letterSpacing: "-0.01em",
              gap: 1.1,
              p: 0,
              minWidth: 0,
              /*
               * ADDED 2026-09-05 alongside the overflow menu. `flexShrink: 0`
               * used to sit here, and removing it is deliberate, not a
               * regression of the fix its own comment describes.
               *
               * Measured at 320px: with `NavOverflowMenu`'s trigger added to
               * the nav, the bar's natural content width is 373px against a
               * 320px viewport, 53px of horizontal bleed, verified with a
               * Playwright probe comparing `document.documentElement
               * .scrollWidth` to `clientWidth` (the same technique this
               * task's verification step calls for; a screenshot cannot show
               * this). A SMALLER, 21px version of the same bleed exists at
               * 320px without the overflow menu at all, so this is not new
               * in kind, only in size: `flexShrink: 0` on both the brand and
               * the nav meant neither side would yield, and the browser let
               * the overflow spill out silently instead of shrinking
               * anything.
               *
               * The nav below is now `flexShrink: 0` instead: it keeps
               * every button at its full authored size, current page, the
               * overflow trigger, and Log in or the account pill, none of
               * which have anywhere safe to lose width. The brand is the
               * one side that CAN give: the text span just below carries
               * `overflow: hidden` and `textOverflow: ellipsis`, so at a
               * width this tight the brand truncates instead of the page
               * gaining a horizontal scrollbar. At every width this task
               * requires zero overflow at (390px and up), the brand still
               * renders in full, since flexbox only shrinks a `flex-shrink:
               * 1` item when the row is actually short on room.
               *
               * RE-MEASURED fix set 4 (R46, decision U9, 2026-09-13), after
               * making the rail toggle visible at every width rather than
               * hiding it below `md`. The toggle's own marginal cost, isolated
               * within one page load by diffing the toolbar's `scrollWidth`
               * with the toggle's `display` flipped to `none` and back, is 32
               * pixels. That is not the dominant term: at 320px the `<nav>`
               * element alone (this file's right-hand `flexShrink: 0` box)
               * measured 567px wide with the toggle absent, a pre-existing
               * bleed this change does not cause and fixing it is out of this
               * task's scope. So the bar does not fit at 320px either before
               * or after this change, and adding the toggle makes an already
               * unfitting bar 32px wider rather than making a fitting one
               * overflow. Recorded rather than silently absorbed, per
               * `.claude/rules/design-consistency.md`: naming a gap is not
               * the same as filling it.
               */
              whiteSpace: "nowrap",
              "&:hover": { bgcolor: "transparent" },
            }}
          >
            <Logo size={21} variant="onNavy" />
            <Box
              component="span"
              sx={{ minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}
            >
              NCBI Agentic Search
            </Box>
          </Button>

          <Box
            component="nav"
            aria-label="Main"
            sx={{
              ml: "auto",
              display: "flex",
              alignItems: "center",
              gap: 0.25,
              minWidth: 0,
              // See the brand button's comment just above: this side holds
              // its full authored width, and the brand absorbs the shrink.
              flexShrink: 0,
            }}
          >
            {NAV.map(({ key, label }) => (
              <Button
                key={key}
                onClick={() => onNavigate?.(key)}
                sx={{
                  fontSize: 13,
                  fontWeight: 500,
                  px: 1.4,
                  py: 0.75,
                  whiteSpace: "nowrap",
                  // prototype/app.html:403. Only the current page survives
                  // inline below 720px; `NavOverflowMenu` below carries the
                  // rest, which the design itself does not (see the comment
                  // above the toolbar).
                  "@media (max-width:720px)": {
                    display: current === key ? "inline-flex" : "none",
                  },
                  color: current === key ? "#FFFFFF" : "rgba(255,255,255,.86)",
                  borderRadius: current === key ? 0 : 1,
                  boxShadow: current === key ? "inset 0 -2px 0 #fff" : "none",
                  "&:hover": { color: "#FFFFFF", bgcolor: "rgba(255,255,255,.08)" },
                }}
              >
                {label}
              </Button>
            ))}

            <NavOverflowMenu items={NAV.filter(({ key }) => key !== current)} onNavigate={onNavigate} />

            <Box sx={{ ml: 1, display: { xs: "none", md: "block" } }}>
              <PersonaChip name={personaName} variant="onNavy" />
            </Box>

            {hideAuthAction ? null : signedIn ? (
              // F-4.8-A-20. This was a lone button whose only action was
              // sign-out. The prototype's control names the account and puts
              // sign-out inside a menu, which is both what the design says and
              // one fewer way to lose a session by accident.
              <AccountMenu
                email={accountEmail ?? "your account"}
                onSignOut={onSignOut}
                onNavigate={(screen) => onNavigate?.(screen)}
                limitCopy={accountLimitCopy}
              />
            ) : (
              <Button
                onClick={onSignIn}
                sx={{
                  ml: 1,
                  fontSize: 13,
                  fontWeight: 600,
                  whiteSpace: "nowrap",
                  color: "#FFFFFF",
                  border: "1px solid rgba(255,255,255,.55)",
                  borderRadius: 1,
                  px: 1.5,
                  py: 0.6,
                }}
              >
                Log in
              </Button>
            )}
          </Box>
        </Toolbar>
      </AppBar>

      {/*
        REMOVED 2026-09-05, product-owner decision. A permanent, non-
        dismissible amber band used to sit here, on every screen, forever,
        stating the same research-tool disclaimer `DisclaimerModal.tsx`
        already shows once per session. The product owner's instruction: the
        disclaimer belongs on the home page, the first time a visitor
        arrives in a session, not as a standing strip a returning visitor
        pays for on every screen after they have already read it. It also
        wrapped to two lines at 390px, costing roughly 44px above the fold on
        a phone before a reader ever reached the question field.

        This reverses build phase 4.8's own "NOT dismissible, deliberately"
        decision for this surface, recorded in this file's earlier docstring
        and enforced by that phase's premise gate. The reversal is the
        product owner's, not a quiet rollback: the modal `App.tsx` renders
        stays exactly as it was, gated once per session on
        `sessionStorage`, and this file no longer duplicates it.
      */}

      {/*
        A flex column, so a child that asks for `flex: 1` gets the whole
        remaining height. Without it `<main>` has no definite height and the
        search rail could not run the full height of the shell the way the
        prototype's does.
      */}
      <Box component="main" sx={{ flex: 1, display: "flex", flexDirection: "column" }}>
        {children}
      </Box>

      {/*
        Set 2, R9 and R11 (2026-09-12). The same blue as the app bar, product-
        owner decision Q1, with `inkOnNavy` text: `inkOnNavyMute` is too faint
        on blue for 12px text. Sticky at the bottom so it no longer jumps as
        the screen above it changes height.
      */}
      <Box
        component="footer"
        sx={{
          position: "sticky",
          bottom: 0,
          zIndex: 1,
          bgcolor: designTokens.blue,
          color: designTokens.inkOnNavy,
          textAlign: "center",
          py: 1.5,
        }}
      >
        <Typography variant="caption">NCBI Agentic Search</Typography>
      </Box>
    </Box>
  );
}

export default AppShell;
