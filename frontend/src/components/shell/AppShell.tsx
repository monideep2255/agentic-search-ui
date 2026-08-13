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
import { AppBar, Box, Button, Toolbar, Typography } from "@mui/material";

import { designTokens } from "../../theme";
import { Logo } from "../brand/Logo";
import { PersonaChip } from "./PersonaChip";

/** The screens reachable from the bar. */
export type ScreenName = "search" | "integrations" | "docs" | "about";

const NAV: { key: ScreenName; label: string }[] = [
  { key: "search", label: "Search" },
  { key: "integrations", label: "Integrations" },
  { key: "docs", label: "Docs" },
  { key: "about", label: "About" },
];

export interface AppShellProps {
  children: ReactNode;
  /** Which nav item reads as current. */
  current?: ScreenName;
  onNavigate?: (screen: ScreenName) => void;
  /** The session's persona. Stubbed; wired by build phase 4.5. */
  personaName?: string;
  signedIn?: boolean;
  accountEmail?: string;
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
  personaName = "Mendel",
  signedIn = false,
  accountEmail,
  onSignIn,
  onSignOut,
  hideAuthAction = false,
}: AppShellProps) {
  return (
    <Box sx={{ minHeight: "100vh", display: "flex", flexDirection: "column", bgcolor: designTokens.canvas }}>
      <AppBar position="static" component="header">
        <Toolbar sx={{ minHeight: 54, gap: 2, px: { xs: 1.5, sm: 2.25 } }}>
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
              "&:hover": { bgcolor: "transparent" },
            }}
          >
            <Logo size={21} variant="onNavy" />
            NCBI Agentic Search
          </Button>

          <Box
            component="nav"
            aria-label="Main"
            sx={{ ml: "auto", display: "flex", alignItems: "center", gap: 0.25 }}
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
              <Button
                onClick={onSignOut}
                sx={{
                  ml: 1,
                  fontSize: 13,
                  color: "rgba(255,255,255,.92)",
                  border: "1px solid rgba(255,255,255,.55)",
                  borderRadius: 1,
                  px: 1.5,
                  py: 0.6,
                }}
              >
                {accountEmail ?? "Account"}
              </Button>
            ) : (
              <Button
                onClick={onSignIn}
                sx={{
                  ml: 1,
                  fontSize: 13,
                  fontWeight: 600,
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

      <Box component="main" sx={{ flex: 1 }}>
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
