/**
 * Refresh-token persistence, so a reload does not sign the account out.
 *
 * Fix set 4, requirement R46, product-owner decision U8 (2026-09-12,
 * `testing/UI_fix_plan.md`): keep people signed in across a reload, with
 * their history where they left it. Until this file existed, `App.tsx`
 * held the access token in React state alone, so every reload dropped a
 * signed-in visitor back to signed out and the history rail came back
 * empty. The backend has issued a rotating refresh token since build
 * phase 1.1; the frontend simply discarded it.
 *
 * WHAT IS PERSISTED, AND WHAT IS NOT. The 30-day rotating REFRESH token is
 * written to `localStorage`, and the 15-minute ACCESS token is never
 * written anywhere: it stays in memory for the tab's lifetime and is
 * re-minted from the refresh token on the next load. `localStorage` is the
 * same storage class the guest bearer token already uses
 * (`guestSession.ts`, key `agentic-search-ui.guest-token.v1`), so this adds
 * no new exposure class to the product: a browser that can read one can
 * already read the other, and the guest token authenticates real runs
 * today.
 *
 * WHY NOT AN httpOnly COOKIE, which is the stronger option and was
 * rejected FOR NOW rather than dismissed. An httpOnly cookie is
 * unreachable from page scripts, which is a genuine improvement over any
 * value in `localStorage`. It does not fit today's deployment: the web app
 * and the API are two separate Railway services on two different origins
 * (`docs/build/Release_flow.md`), so the cookie would have to be
 * `SameSite=None; Secure` to be sent at all, which reopens cross-site
 * request forgery and therefore needs a CSRF token design, plus a CORS
 * review with credentials enabled across both deployments. That is a
 * larger change than this fix, on the security-sensitive path, and it is
 * recorded here as the upgrade to make rather than left implied. The
 * DECISIONS.md row dated 2026-08-27 deferred exactly this work and named
 * the same three alternatives.
 *
 * WHAT LIMITS THE DAMAGE IF THE STORED VALUE IS READ. The token rotates on
 * every use: `POST /auth/refresh` revokes the presented token in the same
 * transaction that mints its replacement, and presenting an
 * already-revoked token revokes the whole family and answers 401
 * (`auth/router.py`'s `refresh` and `_revoke_family_on_reuse`). So a stolen
 * copy is good for at most one use, and using it locks the real holder out
 * in a way they can see, rather than granting quiet indefinite access. The
 * chain also carries a hard 90-day ceiling that rotation never renews.
 *
 * Every storage call is wrapped, the same way `guestSession.ts` wraps its
 * own: `localStorage` throws in real environments (private browsing in
 * some browsers, a full quota, a sandboxed iframe). A storage failure
 * degrades to "acts like state", meaning the account stays signed in for
 * this tab and only reload-persistence is lost, never to a crash.
 */

const REFRESH_TOKEN_STORAGE_KEY = "agentic-search-ui.refresh-token.v1";

/**
 * The persisted refresh token, if a prior visit stored one.
 *
 * `null` covers three cases the caller must treat alike: nothing was ever
 * stored, the value was cleared, and storage is unreachable. All three mean
 * "there is no session to restore, so this visitor is a guest until they
 * log in".
 */
export function loadPersistedRefreshToken(): string | null {
  try {
    const stored = window.localStorage.getItem(REFRESH_TOKEN_STORAGE_KEY);
    // An empty string is not a usable credential, and `POST /auth/refresh`
    // would reject it with a 422 (`RefreshRequest`'s `min_length=1`), so it
    // is normalised to "no session" here rather than sent.
    return stored !== null && stored.length > 0 ? stored : null;
  } catch {
    return null;
  }
}

/**
 * Store a refresh token so the next load can restore the session.
 *
 * Called at sign-in with the token `POST /auth/login` returned, and again
 * after every rotation with the REPLACEMENT the server just issued. The
 * rotated value must be written on every success: the token that was
 * presented is already revoked server-side, so keeping it would leave the
 * browser holding a credential guaranteed to fail, and failing it again
 * would revoke the whole family.
 */
export function persistRefreshToken(token: string): void {
  try {
    window.localStorage.setItem(REFRESH_TOKEN_STORAGE_KEY, token);
  } catch {
    // Storage unreachable. The account stays signed in for this tab via
    // React state; only surviving a reload is lost, which is a lesser
    // failure than breaking a sign-in that has already succeeded.
  }
}

/**
 * Drop the persisted refresh token.
 *
 * Three callers, all in `App.tsx`: log out (paired with `POST /auth/logout`
 * so the server revokes it too), a failed restore on load, and a failed
 * keep-alive rotation. The last two clear it because the value is known
 * dead, and re-sending a dead token is how a family gets revoked.
 */
export function clearPersistedRefreshToken(): void {
  try {
    window.localStorage.removeItem(REFRESH_TOKEN_STORAGE_KEY);
  } catch {
    // Nothing to clean up if storage was never reachable in the first place.
  }
}
