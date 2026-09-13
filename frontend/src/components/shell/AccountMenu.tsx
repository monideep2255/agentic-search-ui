/**
 * The account control, build phase 4.9, ticket T-4.9-10.
 *
 * Closes F-4.8-A-20. The shipped control was a single button labelled
 * "Account" whose only action was sign-out, with no menu and no confirmation,
 * so the account's own identity was nowhere on screen and the one destructive
 * action was one stray click away.
 *
 * Transcribed from the prototype's `.acct`: a pill carrying the account's
 * initials and email with a chevron, opening a menu that names the account and
 * puts sign-out at the bottom, under its own heading, rather than making it the
 * control's only behaviour.
 *
 * Two items the prototype's menu carries are NOT built here, and the omission
 * is deliberate rather than overlooked: the recent-searches list, which the
 * stored-searches rail beside it already shows, and the API-key row, which
 * belongs to the integrations screen that owns that surface.
 */

import { useEffect, useId, useRef, useState } from "react";
import { Box, Typography } from "@mui/material";

import { designTokens } from "../../theme";

export interface AccountMenuProps {
  /** The signed-in account. Shown in the pill and again in the menu header. */
  email: string;
  onSignOut?: () => void;
  /**
   * Navigate to a screen the menu links to.
   *
   * `"docs"` was the second value until fix set 5 (R18, 2026-09-13) folded
   * the Docs screen into Integrations. The menu's two separate rows became
   * one, "Integrations and API documentation", since both now reach the same
   * page, so `"integrations"` is the only destination left.
   */
  onNavigate?: (screen: "integrations") => void;
  /**
   * The account's real search standing, in words, e.g. "no search limit in
   * effect yet" (T-4.10-09 closing F-4.9-A-16, corrected by F-4.10-A-06:
   * the 100/day cap cannot fire while nothing writes `interactions`, so
   * naming the number was false in the opposite direction).
   *
   * Built by `lib/guestSession.ts`'s `dailyLimitPhrase` from
   * `GET /v1/allowance`, the SAME function `HistoryRail`'s footer line
   * uses, so the two surfaces can never disagree with each other. `App.tsx`
   * owns fetching the allowance and computing this string; this component
   * only renders what it is given. Undefined (before the fetch resolves,
   * or if it fails) falls back to a plain "Signed in" with no claim about
   * a number at all, which is the honest option when the real figure is
   * not yet known.
   */
  limitCopy?: string;
}

/** The prototype's `.av`: the account's first two characters, uppercased. */
function initialsOf(email: string): string {
  return email.slice(0, 2).toUpperCase();
}

export function AccountMenu({ email, onSignOut, onNavigate, limitCopy }: AccountMenuProps) {
  const [open, setOpen] = useState(false);
  const menuId = useId();
  const wrapRef = useRef<HTMLDivElement | null>(null);

  /*
   * Close on an outside click or on Escape.
   *
   * A menu that only closes by re-clicking its own trigger is a menu that
   * covers the page until the user finds that trigger again. Escape is the
   * keyboard equivalent and is what a screen reader user will reach for.
   */
  useEffect(() => {
    if (!open) return;
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

  const item = {
    display: "block",
    width: "100%",
    textAlign: "left" as const,
    background: "none",
    border: 0,
    p: "7px 10px",
    borderRadius: 0.5,
    font: "inherit",
    fontSize: 13,
    color: designTokens.ink,
    cursor: "pointer",
    "&:hover": { bgcolor: designTokens.surfaceSunk },
  };

  return (
    <Box ref={wrapRef} sx={{ position: "relative", ml: 1 }}>
      <Box
        component="button"
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={open ? menuId : undefined}
        // The accessible name is the email at every width, even below 720px
        // where the visible email is hidden (see the span below), so a
        // screen reader, a speech-input user and every browser spec that
        // finds this control by the account's email keep working on a
        // phone. The initials the phone still shows are the email's first
        // two characters, so the visible text stays inside the name.
        aria-label={email}
        sx={{
          display: "flex",
          alignItems: "center",
          gap: 1,
          cursor: "pointer",
          border: "1px solid rgba(255,255,255,.4)",
          bgcolor: "rgba(255,255,255,.08)",
          borderRadius: 999,
          p: "3px 11px 3px 3px",
          color: "#FFFFFF",
          font: "inherit",
          fontSize: 12.5,
          "&:hover": { bgcolor: "rgba(255,255,255,.18)" },
        }}
      >
        <Box
          component="span"
          aria-hidden="true"
          sx={{
            width: 24,
            height: 24,
            borderRadius: "50%",
            /*
             * `navy`, and the design system now says navy too.
             *
             * This shipped as a DEVIATION (F-4.9-D-14): the prototype had
             * `rgba(255,255,255,.22)`, which composites over the app bar's
             * blue to #5F84B1 and puts white 11px bold text at 3.87:1 against
             * a 4.5:1 requirement. The design-system contrast pass of
             * 2026-08-14 fixed it at source, so code and design agree again
             * and this is a transcription rather than a departure.
             */
            bgcolor: designTokens.navy,
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            fontWeight: 700,
            fontSize: 11,
          }}
        >
          {initialsOf(email)}
        </Box>
        {/*
          Fix set 4 (R46, 2026-09-13), measured on the live app at 390px
          signed in: the full email in this pill pushed the bar to 465px
          and the page scrolled sideways. Below 720px, the same breakpoint
          the nav items and the overflow menu use, the pill shows the
          initials and the chevron only; the email stays in the menu this
          opens and in the control's accessible name above.
        */}
        <Box component="span" sx={{ "@media (max-width:720px)": { display: "none" } }}>
          {email}
        </Box>
        <Box component="span" aria-hidden="true" sx={{ fontSize: 10, opacity: 0.8 }}>
          ▾
        </Box>
      </Box>

      {open ? (
        <Box
          id={menuId}
          role="menu"
          sx={{
            position: "absolute",
            right: 0,
            top: "calc(100% + 9px)",
            width: 274,
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
          <Box sx={{ p: "9px 10px 10px", borderBottom: `1px solid ${designTokens.line}` }}>
            <Typography
              component="span"
              sx={{
                display: "block",
                color: designTokens.ink,
                fontSize: 13.5,
                fontWeight: 700,
                mb: "2px",
                overflow: "hidden",
                textOverflow: "ellipsis",
              }}
            >
              {email}
            </Typography>
            <Typography component="span" sx={{ fontSize: 12, color: designTokens.inkMuted }}>
              {/*
                F-4.9-A-16, closed by T-4.10-09. This read "Signed in ·
                unlimited searches" against a real, shipped, enforced
                100/day cap (`harness/cost_control.py`). `limitCopy` is
                built from `GET /v1/allowance`, never a second hardcoded
                figure; "Signed in" alone (no number claim at all) is the
                fallback while that fetch is in flight or if it fails.
              */}
              Signed in{limitCopy ? ` · ${limitCopy}` : ""}
            </Typography>
          </Box>

          <Typography
            component="p"
            sx={{
              fontSize: 10,
              letterSpacing: ".1em",
              textTransform: "uppercase",
              color: designTokens.inkFaint,
              p: "11px 10px 4px",
              fontWeight: 700,
              m: 0,
            }}
          >
            Account
          </Typography>
          <Box
            component="button"
            type="button"
            role="menuitem"
            onClick={() => {
              setOpen(false);
              onNavigate?.("integrations");
            }}
            sx={item}
          >
            Integrations and API documentation
          </Box>
          {/*
            ONE item rather than two, fix set 5 (R18, 2026-09-13). This menu
            carried "API key and integrations" and "Documentation" as separate
            rows. Both now reach the same page, since the Docs screen's
            content is the "API documentation" section inside Integrations, and
            two rows with one destination is a menu that lies about how many
            places it can take you. The label also drops "API key", a surface
            the product-owner decision of 2026-08-13 removed.
          */}
          <Box
            component="button"
            type="button"
            role="menuitem"
            onClick={() => {
              setOpen(false);
              onSignOut?.();
            }}
            sx={{ ...item, color: designTokens.risk }}
          >
            Log out
          </Box>
        </Box>
      ) : null}
    </Box>
  );
}

export default AccountMenu;
