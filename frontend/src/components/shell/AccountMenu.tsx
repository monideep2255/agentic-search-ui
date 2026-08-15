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
  /** Navigate to a screen the menu links to. */
  onNavigate?: (screen: "integrations" | "docs") => void;
}

/** The prototype's `.av`: the account's first two characters, uppercased. */
function initialsOf(email: string): string {
  return email.slice(0, 2).toUpperCase();
}

export function AccountMenu({ email, onSignOut, onNavigate }: AccountMenuProps) {
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
             * `navy`, not the prototype's `rgba(255,255,255,.22)`.
             *
             * That translucent white composites over the app bar's blue to
             * #5F84B1, and white 11px bold text on it measures 3.87:1 against
             * a 4.5:1 requirement, measured by axe rather than assumed. WCAG
             * 2.1 AA is a merge gate here. Navy is the design system's own
             * colour and takes the same white to about 13:1.
             *
             * Third instance of the same shape: the prototype is internally
             * inconsistent about contrast, and "matches the design" and
             * "passes the accessibility gate" are two checks that disagree.
             * Filed as F-4.9-D-14, alongside F-4.8-D-08.
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
        {email}
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
              Signed in · unlimited searches
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
            API key and integrations
          </Box>
          <Box
            component="button"
            type="button"
            role="menuitem"
            onClick={() => {
              setOpen(false);
              onNavigate?.("docs");
            }}
            sx={item}
          >
            Documentation
          </Box>
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
