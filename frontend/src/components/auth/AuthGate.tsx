import { useId, useState } from "react";
import type { FormEvent } from "react";
import { Box, Button, Stack, TextField, Typography } from "@mui/material";
import { ApiError, login, signup } from "../../lib/api";
import { designTokens } from "../../theme";

interface AuthGateProps {
  /**
   * Called once with the access token and the account's email address.
   *
   * The email is passed alongside the token because the rail's footer names the
   * signed-in account (`prototype/app.html`'s `.rfoot`), and this is the one
   * place the value is already known: it is what the user typed into the form
   * the server has just authenticated. Sourcing it here rather than from a
   * follow-up `GET /auth/me` avoids a second round trip for a value already in
   * hand, and keeps it real data rather than a stub.
   */
  onAuthenticated: (token: string, email: string) => void;
  /**
   * A guest session this tab is holding, if any (T-4.10-06, design
   * decision 4). Passed through to `signup`/`login` as the optional
   * `guest_token` body field so the server can migrate that guest's live
   * runs to the new account and revoke the guest session. `null` (the
   * default) when this tab never minted one, e.g. a visitor who clicks
   * "Log in" from the nav bar before ever asking a question.
   */
  guestToken?: string | null;
}

type AuthMode = "login" | "signup";

/**
 * T-1.2-08's minimal real auth entry point. No cookie-based session and no
 * login UI has ever existed in this codebase or the locked spec (Section
 * 12.1's component table names no auth/login component at all), so this
 * is the smallest real mechanism that gets a genuine `access_token` from
 * the real backend into `ChatPage`, not a finished auth product: no
 * password reset, no remember-me, no multi-account switching
 * (`v1-scope-boundary.md`, `boil-the-lake.md`'s lake-not-ocean
 * distinction for this ticket).
 *
 * DOCUMENTED CHOICE, this ticket's prompt asks it to be an explicit call:
 * two buttons ("Log in", "Sign up") rather than trying login first and
 * falling back to signup on a failure that "looks like" a missing
 * account. `src/system_03_search_agent/auth/router.py`'s `login` endpoint
 * returns the identical 401 status and the identical
 * "invalid email or password" detail string for BOTH an unknown email and
 * a known email with the wrong password (`_INVALID_CREDENTIALS_DETAIL`,
 * confirmed by reading the router directly, not guessed). This is
 * deliberate: it is what stops the endpoint from disclosing which emails
 * are registered. It also means a login failure cannot be told apart from
 * a "no such account" case by status or by body, so a try-login-then-
 * fall-back-to-signup flow is not just harder to get right here, it would
 * have to weaken the backend's own anti-enumeration guarantee (by probing
 * differently, or by treating every failure as "maybe no account" and
 * signing up anyway, which would silently paper over a real wrong-
 * password case). Two explicit actions need no such disambiguation and
 * leave the backend's guarantee intact.
 */
export function AuthGate({ onAuthenticated, guestToken = null }: AuthGateProps) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const emailId = useId();
  const passwordId = useId();

  const runAuth = async (mode: AuthMode) => {
    setPending(true);
    setError(null);
    try {
      // The `guest_token` field is genuinely OPTIONAL, not merely typed
      // that way: it is omitted from the body entirely when this tab
      // never minted one, rather than sent as an explicit `undefined`, so
      // a caller comparing the exact request body sent (as
      // `AuthGate.test.tsx` does) sees byte-identical payloads for a
      // visitor who never touched the guest path.
      const credentials = guestToken
        ? { email, password, guest_token: guestToken }
        : { email, password };
      if (mode === "signup") {
        await signup(credentials);
      }
      // A successful signup carries no token of its own (`SignupResponse`
      // has only `id`/`email`); both actions converge on the same
      // token-acquisition call so there is exactly one path that ever
      // calls `onAuthenticated`.
      const result = await login(credentials);
      onAuthenticated(result.access_token, email);
      // No `finally`/reset of `pending` on the success path: the parent
      // stops rendering this component once it holds a token (see
      // `App.tsx`), so there would be nothing left to update.
    } catch (caught) {
      // Never logs `password`. Never logs the raw caught value or its
      // message (which, for a `login` 401, is literally the string
      // "invalid email or password" and must not be echoed anywhere a
      // reader could use to distinguish it from a network or server
      // error); only the HTTP status, the same convention
      // `StopButton.tsx`'s own `console.warn` call uses for its failure
      // logging.
      const status = caught instanceof ApiError ? String(caught.status) : "unknown";
      console.warn(`auth request failed (mode=${mode}, status=${status})`);
      // A single fixed sentence per mode, never the caught error's own
      // message: even though `ApiError`'s message is this module's own
      // constructed string today (safe), rendering a fixed sentence here
      // means a future change to that message text can never leak
      // backend-internal detail into the DOM, the same defense
      // `GuardrailBanner.tsx` and `CapMessage.tsx` already use for their
      // own fixed copy.
      setError(
        mode === "signup"
          ? "Could not create that account. That email may already be registered."
          : "Could not log in with that email and password.",
      );
      setPending(false);
    }
  };

  const fieldsFilled = email.length > 0 && password.length > 0;

  // The fields live in a real <form> so pressing Enter submits the default
  // action, log in, the same way any browser form behaves. Sign up stays a
  // plain type="button" outside the submit path: it is the secondary
  // action here and Enter should not trigger it.
  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (pending || !fieldsFilled) return;
    void runAuth("login");
  };

  // The field label above each input matches the design system's micro-label
  // (`.lbl` in `docs/build/design/design-system/foundations/colors.html`, the
  // same spec `search-bar.html`'s field convention uses): 10.5px, uppercase,
  // 0.1em tracking, weight 700, `ink-faint`. It is a real <label> rendered as
  // a styled Typography, not an MUI floating label, because the design system
  // has no floating-label component anywhere and inventing one here would be
  // the one-off vocabulary this pass exists to avoid. `htmlFor`/`id` still do
  // the association, so this keeps the same accessible-name wiring the
  // original raw <label>/<input> pair had.
  const fieldLabelSx = {
    display: "block",
    fontSize: "10.5px",
    letterSpacing: "0.1em",
    textTransform: "uppercase" as const,
    fontWeight: 700,
    color: designTokens.inkFaint,
    mb: 0.75,
  };

  // The input shell copies `search-bar.html`, the one designed text-input
  // precedent in the system: a 2px `line-strong` border (deliberately
  // heavier than the 1px used elsewhere, "so it holds its own"), `surface`
  // background, and radius `r` (the theme's default `shape.borderRadius`,
  // hence `borderRadius: 1` rather than a literal pixel value). A default
  // MUI outlined 1px border reads as a foreign control next to that bar.
  const inputSx = {
    "& .MuiOutlinedInput-root": {
      bgcolor: designTokens.surface,
      borderRadius: 1,
      "& fieldset": { borderColor: designTokens.lineStrong, borderWidth: "2px" },
      "&:hover fieldset": { borderColor: designTokens.lineStrong },
      "&.Mui-focused fieldset": { borderColor: designTokens.blue, borderWidth: "2px" },
    },
    "& .MuiOutlinedInput-input": {
      padding: "10px 14px",
      fontSize: "15.5px",
      color: designTokens.ink,
    },
  };

  return (
    // A <section>, not a <main>. Build phase 4.8 renders this inside AppShell,
    // which owns the page's single main landmark, and two main landmarks on one
    // page is invalid: assistive technology offers "jump to main content" and
    // then cannot say which. Labelled so the section is announced by name.
    //
    // This screen has no designed precedent of its own: guest-states.html
    // designs the wall this screen is reached from and has zero input
    // fields (`grep -c "<input"` on it returns 0). The outer width, 900,
    // matches that wall's own outer wrapper so the two screens share one
    // page rhythm; the card inside is narrower, sized to a form rather than
    // to the wall's centred sentence.
    <Box
      component="section"
      data-testid="auth-gate"
      aria-labelledby="auth-gate-title"
      sx={{ maxWidth: 900, mx: "auto", px: 3, py: 3.5 }}
    >
      <Box
        sx={{
          maxWidth: 440,
          mx: "auto",
          border: `1px solid ${designTokens.lineStrong}`,
          borderRadius: 1,
          bgcolor: designTokens.surface,
          p: { xs: 3, sm: 4.5 },
        }}
      >
        <Typography id="auth-gate-title" variant="h2" component="h1" sx={{ fontSize: 22, mb: 1 }}>
          Sign in to search
        </Typography>
        <Typography sx={{ color: designTokens.inkMuted, mb: 2.5, fontSize: 14.5 }}>
          Log in to your account, or create one to keep going.
        </Typography>
        <Box component="form" onSubmit={handleSubmit} noValidate>
          <Stack spacing={2}>
            <Box>
              <Typography component="label" htmlFor={emailId} sx={fieldLabelSx}>
                Email
              </Typography>
              <TextField
                id={emailId}
                name="email"
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                autoComplete="email"
                fullWidth
                sx={inputSx}
              />
            </Box>
            <Box>
              <Typography component="label" htmlFor={passwordId} sx={fieldLabelSx}>
                Password
              </Typography>
              <TextField
                id={passwordId}
                name="password"
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                // "current-password" on both paths, including signup. One
                // field serves both actions, and the browser has to guess
                // before either button is pressed. A returning user logging
                // in is the far more common case for that field, and
                // "new-password" here would make the browser offer to save
                // a fresh password on every ordinary login too.
                autoComplete="current-password"
                fullWidth
                sx={inputSx}
              />
            </Box>
            {error !== null ? (
              <Typography role="alert" sx={{ color: designTokens.risk, fontSize: 13.5 }}>
                {error}
              </Typography>
            ) : null}
            <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5}>
              {/*
                Primary button: no colour override needed. The theme's
                default `contained` button already IS the design system's
                primary button (`.go` in search-bar.html): palette.primary
                resolves to designTokens.blue with white contrast text,
                MuiButton's own styleOverrides already sets borderRadius 4
                (`--r-sm`) and disableElevation, and typography.button
                already sets weight 600 and no uppercase transform. Only the
                font size and padding are `.go`-specific and not part of the
                theme default, so only those are set here.
              */}
              <Button
                type="submit"
                variant="contained"
                disabled={pending || !fieldsFilled}
                sx={{ fontSize: "14px", padding: "9px 18px" }}
              >
                {pending ? "Working…" : "Log in"}
              </Button>
              {/*
                Secondary button: the design system's only secondary-action
                precedent is the "Not now" dismiss in guest-states.html's
                soft-prompt state (`.mini.alt`): transparent background,
                `ink-muted` text, `line` border. There is no designed
                full-size secondary action button, so this scales that
                same language up to this screen's button size rather than
                inventing an unrelated one.
              */}
              <Button
                type="button"
                variant="outlined"
                onClick={() => void runAuth("signup")}
                disabled={pending || !fieldsFilled}
                sx={{
                  fontSize: "14px",
                  padding: "9px 18px",
                  color: designTokens.inkMuted,
                  borderColor: designTokens.line,
                  "&:hover": {
                    borderColor: designTokens.lineStrong,
                    bgcolor: designTokens.surfaceSunk,
                  },
                }}
              >
                {pending ? "Working…" : "Sign up"}
              </Button>
            </Stack>
          </Stack>
        </Box>
      </Box>
    </Box>
  );
}
