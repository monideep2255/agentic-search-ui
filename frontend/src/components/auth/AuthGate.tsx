import { useId, useState } from "react";
import { ApiError, login, signup } from "../../lib/api";

interface AuthGateProps {
  onAuthenticated: (token: string) => void;
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
export function AuthGate({ onAuthenticated }: AuthGateProps) {
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
      if (mode === "signup") {
        await signup({ email, password });
      }
      // A successful signup carries no token of its own (`SignupResponse`
      // has only `id`/`email`); both actions converge on the same
      // token-acquisition call so there is exactly one path that ever
      // calls `onAuthenticated`.
      const result = await login({ email, password });
      onAuthenticated(result.access_token);
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

  return (
    <main className="auth-gate">
      <h1>Sign in to search</h1>
      <div className="auth-gate__form">
        <label htmlFor={emailId}>Email</label>
        <input
          id={emailId}
          name="email"
          type="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          autoComplete="email"
        />
        <label htmlFor={passwordId}>Password</label>
        <input
          id={passwordId}
          name="password"
          type="password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          autoComplete="current-password"
        />
        {error !== null ? (
          <p role="alert" className="auth-gate__error">
            {error}
          </p>
        ) : null}
        <div className="auth-gate__actions">
          <button
            type="button"
            onClick={() => void runAuth("login")}
            disabled={pending || !fieldsFilled}
          >
            {pending ? "Working…" : "Log in"}
          </button>
          <button
            type="button"
            onClick={() => void runAuth("signup")}
            disabled={pending || !fieldsFilled}
          >
            {pending ? "Working…" : "Sign up"}
          </button>
        </div>
      </div>
    </main>
  );
}
