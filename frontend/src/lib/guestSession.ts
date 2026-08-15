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
 * never spend another run, and continuing to send it would only produce a
 * 401 the user cannot act on. Always paired with `markGuestSessionMigrated`
 * on that path, so dropping the dead credential does not also forget that
 * this browser has already had its guest allowance.
 */
export function clearPersistedGuestToken(): void {
  try {
    window.localStorage.removeItem(GUEST_TOKEN_STORAGE_KEY);
  } catch {
    // Nothing to clean up if storage was never reachable in the first place.
  }
}

const GUEST_MIGRATED_STORAGE_KEY = "agentic-search-ui.guest-migrated.v1";

/**
 * Record that this browser's guest identity was converted into an account
 * (F-4.10-A-05, product-owner decision 2026-08-15).
 *
 * WHY A SECOND VALUE RATHER THAN JUST KEEPING THE TOKEN. The product
 * decision is that a visitor who signs out returns to the guest identity
 * they already had, with whatever searches remained. For an identity that
 * migrated, the server revoked it in the same transaction, so nothing
 * remains and the token is a dead credential: resurrecting it would land the
 * user on a 401 they cannot act on. The two facts therefore have to be
 * stored separately. The token is dropped, and the fact that there WAS one
 * is kept, so the next anonymous ask goes straight to the sign-in wall
 * rather than minting a brand-new identity with five fresh searches.
 *
 * That mint is the hole this closes. `App.tsx` used to clear the guest token
 * on sign-out AND on sign-in, so an ordinary sign in, sign out, ask five
 * more cycle handed out an unlimited number of free allowances with no
 * developer tools and no storage clearing involved, which is not what the
 * 2026-08-14 "anyone who clears it gets five more" decision accepted.
 *
 * Deliberately never cleared by the app. Clearing browser storage still
 * yields a fresh allowance, which IS the accepted tradeoff; the application
 * simply no longer does it on the user's behalf.
 */
export function markGuestSessionMigrated(): void {
  try {
    window.localStorage.setItem(GUEST_MIGRATED_STORAGE_KEY, "1");
  } catch {
    // Storage unreachable. Degrades to the pre-fix behaviour for this tab
    // only (a fresh identity on the next anonymous ask), never to a crash.
    // The server-side daily ceiling on anonymous runs is the real bound;
    // this marker is the client half of an honest UX, not a security
    // control, and it is written down here so nobody mistakes it for one.
  }
}

/** Whether this browser has already converted a guest identity into an account. */
export function guestSessionWasMigrated(): boolean {
  try {
    return window.localStorage.getItem(GUEST_MIGRATED_STORAGE_KEY) === "1";
  } catch {
    return false;
  }
}

/**
 * The caller's real search standing, in words, sourced ONLY from an
 * `AllowanceResponse` actually returned by `GET /v1/allowance`. `null`
 * means "not fetched yet," rendered as a statement that is honest about
 * not knowing, never as a guess.
 *
 * THE `counted: false` BRANCH, and why it no longer states a number
 * (F-4.10-A-06). It used to render "up to 100 searches a day", which
 * replaced one false statement with another in the opposite direction:
 * F-4.9-A-16 killed "unlimited searches" because a 100/day cap is shipped
 * in code, and this line then asserted that cap as a fact the system does
 * not deliver. `check_user_daily_query_cap` counts rows in `interactions`,
 * and nothing writes that table (F-2.0-04, build phase 4.6's to close), so
 * the cap cannot fire and every registered caller is effectively unmetered.
 * The server says exactly this on the wire, `counted: false`, and T-4.10-09's
 * own acceptance criterion anticipated it: "if the honest answer is 'not
 * counted yet', the copy says that rather than displaying an uncounted zero
 * as a count." Reading `counted` and then stating the number anyway is
 * consuming the honesty field as permission to be confident, which is the
 * opposite of what it is for.
 *
 * So the branch states what is true: no limit is in effect. "Yet" is
 * load-bearing rather than hedging, since the cap is real in code and
 * starts firing the moment interaction rows exist, at which point the
 * server flips `counted` to true and this function states the real count
 * instead, with no copy change needed here.
 *
 * `counted: true` (guests today, registered callers once F-2.0-04 closes)
 * states what is actually left.
 */
export function dailyLimitPhrase(allowance: AllowanceResponse | null): string {
  if (allowance === null) {
    return "checking your search limit…";
  }
  if (!allowance.counted) {
    return "no search limit in effect yet";
  }
  const left = Math.max(allowance.total - allowance.used, 0);
  return `${left} of ${allowance.total} searches left today`;
}

/** Sentence-cases a phrase built by `dailyLimitPhrase` for a standalone line. */
export function capitalizeFirst(text: string): string {
  return text.length === 0 ? text : text.charAt(0).toUpperCase() + text.slice(1);
}
