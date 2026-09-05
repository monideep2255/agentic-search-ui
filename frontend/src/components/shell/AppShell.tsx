/**
 * The app shell, build phase 4.8, ticket T-4.8-03.
 *
 * The chrome every screen sits inside: the app bar, the permanent disclaimer
 * strip, and the footer.
 *
 * The disclaimer strip is NOT dismissible, deliberately. It is a standing
 * statement that this is a research tool and not medical advice, and a strip
 * a user can close is one they will close. The premise gate asserts its
 * presence, so removing it fails the build rather than quietly shipping.
 *
 * Source of truth: `docs/build/design/design-system/components/app-bar.html`
 * and the approved prototype.
 */

import type { ReactNode } from "react";
import { AppBar, Box, Button, IconButton, Toolbar, Typography } from "@mui/material";

import { designTokens } from "../../theme";
import { Logo } from "../brand/Logo";
import { PersonaChip } from "./PersonaChip";
import { AccountMenu } from "./AccountMenu";

/** The screens reachable from the bar. */
export type ScreenName = "search" | "integrations" | "docs" | "about";

const NAV: { key: ScreenName; label: string }[] = [
  // Order transcribed from the prototype's `.nav` (F-4.8-D-09). Docs and About
  // were the other way round, which every membership assertion accepted.
  { key: "search", label: "Search" },
  { key: "integrations", label: "Integrations" },
  { key: "about", label: "About" },
  { key: "docs", label: "Docs" },
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

function WarningIcon() {
  return (
    <svg width={14} height={14} viewBox="0 0 16 16" fill="currentColor" aria-hidden="true" style={{ flex: "none" }}>
      <path d="M8 1.2 15 14H1L8 1.2Zm0 4.3a.8.8 0 0 0-.8.8v3a.8.8 0 0 0 1.6 0v-3a.8.8 0 0 0-.8-.8Zm0 5.5a.9.9 0 1 0 0 1.8.9.9 0 0 0 0-1.8Z" />
    </svg>
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
      <AppBar position="static" component="header">
        {/*
            THE BAR WRAPS TO TWO ROWS BELOW `sm`, and this is a gap being
            filled rather than a design being implemented. Measured
            2026-09-05 at 390px: the brand button had `minWidth: 0` and no
            wrap control, so "NCBI Agentic Search" broke across three lines
            and OVERLAPPED the Search nav item, with "Log in" clipped at the
            right edge. `testing/UI_feedback.md` records this viewport as an
            "8px horizontal bleed", which is the measurement rather than the
            defect: the bar collides with itself, and journey 7's own
            evidence from 2026-09-01 shows it identically.

            `docs/build/design/design-system/components/app-bar.html` carries
            NO responsive rule and no media query, so there is no designed
            mobile bar to copy. The one `flex-wrap` in that file belongs to
            the specimen page's own layout helper, not to the component.
            Per `.claude/rules/design-consistency.md`, the gap is named here
            rather than filled silently, and what is built uses only the
            foundations: every value below is a breakpoint or a spacing step,
            no new colour and no new type size.
          */}
          <Toolbar
            sx={{
              minHeight: 54,
              gap: { xs: 1, sm: 2 },
              px: { xs: 1.5, sm: 2.25 },
              flexWrap: { xs: "wrap", sm: "nowrap" },
              py: { xs: 1, sm: 0 },
            }}
          >
          {/*
            First in the bar, left of the brand, exactly where the prototype's
            `#railBtn` sits. `aria-expanded` carries the rail's real state, so
            a screen reader user is told what the control will do rather than
            having to press it to find out.
          */}
          {showRailToggle ? (
            <IconButton
              onClick={onToggleRail}
              aria-label="Show or hide your searches"
              aria-expanded={railOpen}
              sx={{
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
              // Without these the label wrapped mid-word into the nav.
              whiteSpace: "nowrap",
              flexShrink: 0,
              "&:hover": { bgcolor: "transparent" },
            }}
          >
            <Logo size={21} variant="onNavy" />
            NCBI Agentic Search
          </Button>

          <Box
            component="nav"
            aria-label="Main"
            sx={{
              ml: { xs: 0, sm: "auto" },
              width: { xs: "100%", sm: "auto" },
              display: "flex",
              alignItems: "center",
              flexWrap: "wrap",
              gap: 0.25,
            }}
          >
            {NAV.map(({ key, label }) => (
              <Button
                key={key}
                onClick={() => onNavigate?.(key)}
                sx={{
                  fontSize: 13,
                  fontWeight: 500,
                  px: { xs: 0.9, sm: 1.4 },
                  py: 0.75,
                  whiteSpace: "nowrap",
                  color: current === key ? "#FFFFFF" : "rgba(255,255,255,.86)",
                  borderRadius: current === key ? 0 : 1,
                  boxShadow: current === key ? "inset 0 -2px 0 #fff" : "none",
                  "&:hover": { color: "#FFFFFF", bgcolor: "rgba(255,255,255,.08)" },
                }}
              >
                {label}
              </Button>
            ))}

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
                  ml: { xs: "auto", sm: 1 },
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

      {/* Permanent. Not dismissible, by design. */}
      <Box
        sx={{
          display: "flex",
          alignItems: "center",
          gap: 1.1,
          px: 2.25,
          py: 1.1,
          fontSize: 12.5,
          bgcolor: designTokens.warnWash,
          color: designTokens.ink,
          borderBottom: `1px solid ${designTokens.line}`,
        }}
      >
        <WarningIcon />
        Research tool. Answers are cited to NCBI records and are not medical advice.
      </Box>

      {/*
        A flex column, so a child that asks for `flex: 1` gets the whole
        remaining height. Without it `<main>` has no definite height and the
        search rail could not run the full height of the shell the way the
        prototype's does.
      */}
      <Box component="main" sx={{ flex: 1, display: "flex", flexDirection: "column" }}>
        {children}
      </Box>

      <Box
        component="footer"
        sx={{
          bgcolor: designTokens.navy,
          color: designTokens.inkOnNavyMute,
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
