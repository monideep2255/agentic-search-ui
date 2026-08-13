/**
 * The disclaimer modal, build phase 4.8, ticket T-4.8-10.
 *
 * Checkbox-gated and shown once per session rather than once per device, so a
 * returning visitor on a shared machine sees it again. Session storage, not
 * local storage: the reference implementation made the same call, and the
 * reasoning holds. A medical disclaimer a user dismissed six months ago on
 * someone else's browser has not been read by the person reading now.
 *
 * This is the one lifted surface in the whole product. Everything else is flat
 * on a tinted canvas with hairline borders, so the single shadow here does real
 * work: it is the one thing that should feel like it sits above the page.
 *
 * Not a stub. The gate is real and it blocks the app until accepted.
 */

import { useEffect, useRef, useState } from "react";
import { Box, Button, Typography } from "@mui/material";

import { designTokens } from "../../theme";

export const DISCLAIMER_KEY = "medicalDisclaimerAccepted";

/** Read once at mount. Session-scoped, and safe where storage is unavailable. */
export function hasAcceptedDisclaimer(): boolean {
  try {
    return window.sessionStorage.getItem(DISCLAIMER_KEY) === "true";
  } catch {
    // Private mode, or a test environment without storage. Failing closed
    // means the disclaimer shows, which is the safe direction for a medical
    // notice: seeing it twice costs a click, missing it costs more.
    return false;
  }
}

export function rememberDisclaimer(): void {
  try {
    window.sessionStorage.setItem(DISCLAIMER_KEY, "true");
  } catch {
    // Nothing to do. The modal simply shows again next session.
  }
}

export interface DisclaimerModalProps {
  onAccept: () => void;
}

export function DisclaimerModal({ onAccept }: DisclaimerModalProps) {
  const [checked, setChecked] = useState(false);
  const dialogRef = useRef<HTMLDivElement | null>(null);

  /**
   * F-4.8-A-08. This modal blocked the MOUSE only.
   *
   * There was no focus trap and no `inert` on the background, so the entire app
   * stayed in the tab order behind it. The adversary signed up, asked a
   * question and read a complete cited answer using the keyboard alone, with
   * the unaccepted disclaimer still on screen. This component's own docstring
   * claimed "The gate is real and it blocks the app until accepted."
   *
   * `aria-modal="true"` made it worse rather than better: it tells a screen
   * reader the background is inert while it was still fully reachable.
   *
   * The trap below is deliberately hand-rolled and small: focus moves into the
   * dialog on mount, Tab and Shift+Tab cycle within it, and Escape does
   * nothing, because a medical disclaimer must not be dismissible by reflex.
   */
  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;

    const focusable = () =>
      Array.from(
        dialog.querySelectorAll<HTMLElement>(
          'button:not([disabled]), input:not([disabled]), [href], [tabindex]:not([tabindex="-1"])',
        ),
      ).filter((el) => el.offsetParent !== null);

    focusable()[0]?.focus();

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        return;
      }
      if (event.key !== "Tab") return;
      const items = focusable();
      if (items.length === 0) return;
      const first = items[0];
      const last = items[items.length - 1];
      const active = document.activeElement as HTMLElement | null;

      if (!dialog.contains(active)) {
        event.preventDefault();
        first.focus();
        return;
      }
      if (event.shiftKey && active === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && active === last) {
        event.preventDefault();
        first.focus();
      }
    };

    document.addEventListener("keydown", onKeyDown, true);
    return () => document.removeEventListener("keydown", onKeyDown, true);
  }, []);

  return (
    <Box
      sx={{
        position: "fixed",
        inset: 0,
        zIndex: 1300,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        p: 3,
        bgcolor: "rgba(11,33,56,.55)",
      }}
    >
      <Box
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="disclaimer-title"
        data-testid="disclaimer-modal"
        sx={{
          bgcolor: designTokens.surface,
          borderRadius: 1,
          maxWidth: 520,
          width: "100%",
          overflow: "hidden",
          // The only shadow in the product.
          boxShadow: "0 1px 2px rgba(17,47,78,.1), 0 20px 50px rgba(17,47,78,.3)",
        }}
      >
        <Box
          sx={{
            px: 2.5,
            py: 2,
            borderBottom: `1px solid ${designTokens.line}`,
            display: "flex",
            alignItems: "center",
            gap: 1.25,
          }}
        >
          <svg width={18} height={18} viewBox="0 0 16 16" fill={designTokens.warn} aria-hidden="true">
            <path d="M8 1.2 15 14H1L8 1.2Zm0 4.3a.8.8 0 0 0-.8.8v3a.8.8 0 0 0 1.6 0v-3a.8.8 0 0 0-.8-.8Zm0 5.5a.9.9 0 1 0 0 1.8.9.9 0 0 0 0-1.8Z" />
          </svg>
          <Typography id="disclaimer-title" variant="h4" component="h2">
            Before you start
          </Typography>
        </Box>

        <Box sx={{ px: 2.5, py: 2.25, display: "flex", flexDirection: "column", gap: 1.5 }}>
          <Typography sx={{ fontWeight: 600, fontSize: 14 }}>
            This tool answers research questions. It does not give medical advice, diagnosis, or
            treatment recommendations.
          </Typography>
          <Typography variant="body2" sx={{ color: designTokens.inkMuted }}>
            Answers are assembled from NCBI records and cited back to them. Always speak to a
            qualified health professional about a medical condition.
          </Typography>
          <Box
            sx={{
              border: `1px solid ${designTokens.warn}`,
              borderLeftWidth: 4,
              borderRadius: 0.5,
              bgcolor: designTokens.warnWash,
              px: 1.6,
              py: 1.4,
              fontSize: 13,
            }}
          >
            Prototype. Coverage varies by organism and database. Treat every answer as a starting
            point for verification, not an endpoint.
          </Box>

          <Box component="label" sx={{ display: "flex", gap: 1.25, alignItems: "flex-start", fontSize: 13.5, cursor: "pointer" }}>
            <Box
              component="input"
              type="checkbox"
              checked={checked}
              onChange={(event: React.ChangeEvent<HTMLInputElement>) =>
                setChecked(event.target.checked)
              }
              sx={{ mt: 0.4 }}
            />
            <span>
              I understand this is a research tool and does not provide medical advice.
            </span>
          </Box>
        </Box>

        <Box sx={{ px: 2.5, pb: 2.5 }}>
          <Button
            variant="contained"
            fullWidth
            disabled={!checked}
            onClick={() => {
              rememberDisclaimer();
              onAccept();
            }}
            sx={{ py: 1.25 }}
          >
            Continue
          </Button>
        </Box>
      </Box>
    </Box>
  );
}

export default DisclaimerModal;
