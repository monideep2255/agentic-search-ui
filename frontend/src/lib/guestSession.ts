/**
 * Guest token persistence and the shared "how many searches are left"
 * copy, build phase 4.10, tickets T-4.10-08 and T-4.10-09.
 *
 * PERSISTENCE. Design decision 1 (`tracker/phase_4.10.md`): the guest
 * identity is a signed token minted on first visit. It is clearable, and
 * anyone who clears it gets a fresh five-search allowance; that is an
 * accepted product-owner decision, not an oversight (`TestAcceptedBehaviour`
 * in the backend premise gate asserts it directly). Persisting it here
 * means an ordinary reload does NOT silently hand the visitor a fresh
 * allowance, which reload otherwise would if the token lived only in React
 * state.
 *
 * Every storage call is wrapped: `localStorage` throws in a handful of real
 * environments (private browsing in some browsers, a full quota, a
 * sandboxed iframe), and a guest session that cannot survive a reload is
 * still a working guest session for the current tab. A storage failure
 * degrades to "acts like state," never to a crash.
 *
 * COPY. `dailyLimitPhrase` is the single function both `AccountMenu`'s menu
 * line and `HistoryRail`'s footer line are built from (T-4.10-09's
 * acceptance criterion: "the rail footer must say the same thing as the
 * account menu, from the same source"). It reads only the fields
 * `GET /v1/allowance` actually returned, never a second hardcoded number,
 * and it never renders an uncounted zero as though it were a measured
 * count (F-4.9-A-16, the same dishonesty class the client-side search
 * counter was removed for).
 */

import type { AllowanceResponse } from "./api";

const GUEST_TOKEN_STORAGE_KEY = "agentic-search-ui.guest-token.v1";

/** The persisted guest token, if a prior visit minted and stored one. */
export function loadPersistedGuestToken(): string | null {
  try {
    return window.localStorage.getItem(GUEST_TOKEN_STORAGE_KEY);
  } catch {
    return null;
  }
}

/** Store a freshly minted guest token so a reload does not lose it. */
export function persistGuestToken(token: string): void {
  try {
    window.localStorage.setItem(GUEST_TOKEN_STORAGE_KEY, token);
  } catch {
    // Storage unreachable. The token still works for this tab's lifetime
    // via React state; only reload-persistence is lost, which is a lesser
    // failure than crashing the ask that is in flight right now.
  }
}

/**
 * Drop the persisted guest token. Called once a guest session has been
 * migrated at signup/login (design decision 4): the server revokes that
 * session in the same transaction, so the token this tab was holding can
 * never spend another run, and holding onto it would only produce a
 * confusing 401/403 on the NEXT anonymous ask this tab makes (after a
 * sign-out, say). Also used defensively when the server reports a guest
 * token as no longer valid for any other reason.
 */
export function clearPersistedGuestToken(): void {
  try {
    window.localStorage.removeItem(GUEST_TOKEN_STORAGE_KEY);
  } catch {
    // Nothing to clean up if storage was never reachable in the first place.
  }
}

/**
 * The real per-day search limit, in words, sourced ONLY from an
 * `AllowanceResponse` actually returned by `GET /v1/allowance`. `null`
 * means "not fetched yet," rendered as a statement that is honest about
 * not knowing, never as a guess.
 *
 * `counted: false` (every registered caller today, F-2.0-04: nothing
 * writes `interactions` rows yet) states the LIMIT, not a usage count,
 * because the usage count is not a real measurement yet. `counted: true`
 * (guests, and registered callers once F-2.0-04 closes) states what is
 * actually left.
 */
export function dailyLimitPhrase(allowance: AllowanceResponse | null): string {
  if (allowance === null) {
    return "checking your daily limit…";
  }
  if (!allowance.counted) {
    return `up to ${allowance.total} searches a day`;
  }
  const left = Math.max(allowance.total - allowance.used, 0);
  return `${left} of ${allowance.total} searches left today`;
}

/** Sentence-cases a phrase built by `dailyLimitPhrase` for a standalone line. */
export function capitalizeFirst(text: string): string {
  return text.length === 0 ? text : text.charAt(0).toUpperCase() + text.slice(1);
}
