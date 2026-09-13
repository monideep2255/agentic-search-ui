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

/**
 * The one sign-in entry point: an email, a password, and a single Log in
 * button. No password reset, no remember-me, no multi-account switching
 * (`v1-scope-boundary.md`).
 *
 * ONE BUTTON, product-owner decisions R5 and X3 (2026-09-12,
 * `testing/UI_fix_plan.md` set 1). This replaces the earlier two-button
 * form, which existed to protect the login endpoint's anti-enumeration
 * guarantee: `POST /auth/login` returns the same 401 for an unknown email
 * and a wrong password. Log in now tries signup first, and signup already
 * discloses registration with its 409, so the flow is:
 *
 * - signup 201: a new account was created, then log in.
 * - signup 409: the email is registered, so log in with the password.
 * - login 401 after a 409: the password is wrong for a registered email,
 *   and the screen says so. Decision X3 accepted that this reveals which
 *   emails are registered, in exchange for one button.
 *
 * The guest token goes to exactly one of the two calls. Signup migrates and
 * revokes the guest session when it creates the account, so sending it again
 * to login would only replay a no-op; when signup answers 409, nothing was
 * migrated and login carries it instead.
 */
export function AuthGate({ onAuthenticated, guestToken = null }: AuthGateProps) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const emailId = useId();
  const passwordId = useId();

  const logIn = async () => {
    setPending(true);
    setError(null);
    // The `guest_token` field is omitted from the body entirely when this
    // tab never minted one, rather than sent as an explicit `undefined`, so
    // a visitor who never touched the guest path sends the plain payload.
    const plain = { email, password };
    const withGuest = guestToken ? { ...plain, guest_token: guestToken } : plain;
    try {
      let created = false;
      try {
        await signup(withGuest);
        created = true;
      } catch (caught) {
        if (!(caught instanceof ApiError && caught.status === 409)) throw caught;
      }
      const result = await login(created ? plain : withGuest);
      onAuthenticated(result.access_token, email);
      // No reset of `pending` on the success path: the parent stops
      // rendering this component once it holds a token (see `App.tsx`).
    } catch (caught) {
      // Never logs `password` or the caught message, only the HTTP status.
      const status = caught instanceof ApiError ? caught.status : null;
      console.warn(`auth request failed (status=${status ?? "unknown"})`);
      // Fixed sentences, never the caught error's own message, so a change
      // to server detail text can never leak into the DOM.
      setError(
        status === 401
          ? "That password does not match this email. Check it and try again."
          : status === 422
            ? "Enter a valid email address and a password."
            : "Could not log in right now. Check your connection and try again.",
      );
      setPending(false);
    }
  };

  const fieldsFilled = email.length > 0 && password.length > 0;

  // The fields live in a real <form> so pressing Enter logs in, the same way
  // any browser form behaves.
  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (pending || !fieldsFilled) return;
    void logIn();
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
          Log in
        </Typography>
        <Typography sx={{ color: designTokens.inkMuted, mb: 2.5, fontSize: 14.5 }}>
          Use your email and a password. A new email creates your account.
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
                // "current-password" even though a new email creates an
                // account: a returning user logging in is the far more common
                // case, and "new-password" would make the browser offer to
                // save a fresh password on every ordinary login.
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
            {/*
              The theme's default `contained` button already IS the design
              system's primary button (`.go` in search-bar.html): blue with
              white text, radius `--r-sm`, weight 600. Only the `.go` font
              size and padding are set here.
            */}
            <Button
              type="submit"
              variant="contained"
              disabled={pending || !fieldsFilled}
              sx={{ fontSize: "14px", padding: "9px 18px", alignSelf: "flex-start" }}
            >
              {pending ? "Working…" : "Log in"}
            </Button>
          </Stack>
        </Box>
      </Box>
    </Box>
  );
}
