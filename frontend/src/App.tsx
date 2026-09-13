/**
 * The assembled app, build phase 4.8, ticket T-4.8-12.
 *
 * REWRITTEN in the fix round after judge findings F-4.8-J-01, J-02, J-03,
 * J-08, J-12 and J-17. Four of those were critical and three were user-facing
 * trust defects, so the relevant reasoning is recorded here rather than in a
 * commit message nobody reads twice.
 *
 * THE RULE THIS FILE FOLLOWS: nothing that looks like an answer is ever
 * rendered from anything but the agent's own event stream. No demo claims, no
 * demo citations, no demo trust signals, on any path, for any visitor.
 *
 * What that replaced, and why it was wrong. The previous version rendered a
 * canned BRCA1 answer for an anonymous visitor, complete with a real NCBI
 * source URL, a full provenance card and the pill "Grounded, every claim
 * cited", REGARDLESS OF THE QUESTION ASKED. The judge probed it with "What is
 * the capital of the USA?" and got a confident cited answer about hereditary
 * breast and ovarian cancer. It also bypassed build phase 3.0's guardrail
 * completely, on the most-travelled path in the product.
 *
 * The justification at the time was that a stub is "marked in code, never on
 * screen", which is the rule this repository sets for stubbed surfaces. That
 * rule is correct for a search counter and indefensible for answer content in
 * a cite-or-refuse system: `production-standards`' grounding gate and
 * CLAUDE.md's "Citations: non-negotiable" both forbid presenting a claim the
 * agent never produced.
 *
 * BUILD PHASE 4.10 UPDATE (T-4.10-08). Until this phase, an anonymous
 * visitor met the sign-in wall the moment they asked, because no backend
 * route existed for a caller with no account: showing the wall was honest,
 * fabricating an answer was not. That backend route now exists
 * (`POST /auth/guest`, the four `/v1/query*` endpoints accepting a guest
 * bearer token, `GET /v1/allowance`), so the rule above still holds exactly
 * as written, and an anonymous visitor now satisfies it the same way a
 * signed-in one does: by actually asking the agent and rendering only what
 * its real event stream produces. The wall is no longer shown merely
 * because the visitor has no account; it is shown only when the SERVER
 * refuses a run with the reason `guest_allowance_exhausted`, per design
 * decision 5 (`tracker/phase_4.10.md`). The five-search allowance itself is
 * counted by the server (`guest_sessions.runs_used`, spent by one atomic
 * `UPDATE`), never guessed at client-side: the client-side counter this
 * file used to increment on every ask was exactly the fabrication class
 * build phase 4.8's judge round filed (F-4.8-J-01's dishonesty class, one
 * layer up), and it is gone, not merely renamed.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { Box, CssBaseline, ThemeProvider } from "@mui/material";

import { designTokens, theme } from "./theme";
import {
  ApiError,
  createRun,
  fetchHistory,
  fetchMe,
  fetchPersona,
  getAllowance,
  logoutSession,
  mintGuest,
  refreshSession,
  stopRun,
} from "./lib/api";
import type { AllowanceResponse, HistoryItem } from "./lib/api";
import {
  capitalizeFirst,
  clearPersistedGuestToken,
  dailyLimitPhrase,
  loadPersistedGuestToken,
  persistGuestToken,
} from "./lib/guestSession";
import {
  clearPersistedRefreshToken,
  loadPersistedRefreshToken,
  persistRefreshToken,
} from "./lib/authSession";
import { useAgentRun } from "./hooks/useAgentRun";
import { useRunView, EMPTY_RUN_VIEW } from "./hooks/useRunView";
import { AuthGate } from "./components/auth/AuthGate";
import { AppShell } from "./components/shell/AppShell";
import { useScreenRoute } from "./lib/routing";
import { HomeScreen } from "./components/screens/HomeScreen";
import { RunScreen } from "./components/screens/RunScreen";
import { RunProgress } from "./components/screens/RunProgress";
import type { StepName } from "./components/screens/RunScreen";
import { AnswerScreen } from "./components/screens/AnswerScreen";
import type { PreviousTurn } from "./components/screens/AnswerScreen";
import { ArchitectureScreen } from "./components/screens/ArchitectureScreen";
import { AboutScreen, IntegrationsScreen } from "./components/screens/InfoScreens";
import { CollapsedRail, FollowUp, HistoryRail } from "./components/answer/FollowUp";
import { DisclaimerModal, hasAcceptedDisclaimer } from "./components/shell/DisclaimerModal";
import type { AudienceDepth } from "./components/controls/DepthControl";
import {
  OnboardingTour,
  RUN_STEP_INDEX,
  TOUR_QUESTION,
  TourInvite,
  hasSeenTour,
  markTourSeen,
} from "./components/tour/OnboardingTour";
import type { TourOutcome, TourRunState } from "./components/tour/OnboardingTour";

type SearchView =
  | { name: "home" }
  | { name: "run"; question: string }
  /**
   * The answer screen.
   *
   * `continued` is true when this view was reached by asking a follow-up
   * from the answer screen itself, which is the one case where the screen
   * must NOT be swapped for the run screen (UI fix set 7, R22): the earlier
   * turn collapses into the thread above and the new run's progress renders
   * inline underneath, on the same screen.
   *
   * A flag on the view rather than a separate piece of state, because it is
   * a property of WHICH SCREEN IS SHOWING and must be cleared by every
   * transition that leaves it. Held separately it would have to be reset in
   * five places and would eventually be missed in one.
   */
  | { name: "answer"; question: string; continued?: boolean }
  | { name: "signin" };

/** Canned follow-up hints. Stubbed; build phase 4.5 derives these for real.
 *  These are QUESTIONS, never answer content, which is why they are allowed. */
const FOLLOW_UP_HINTS = [
  "What variants cause it?",
  "Which trials are recruiting?",
  "What does the literature add?",
];

/**
 * Verbatim duplicates of `GuestAllowance.tsx`'s own `BLOCKED_COPY` entries
 * for the two 429 reasons `createRun` returns when a shared daily guest
 * ceiling, not this caller's personal allowance, is what is blocking the
 * question (`adapters/web_sse/app.py`'s `anon_daily_cap_reached` and
 * `anon_source_daily_cap_reached`). Before this fix, `ask`'s catch block
 * branched only on the two 403 personal-allowance reasons, so both of
 * these purpose-written sentences existed on the server and on the wire
 * and were never read: a guest hitting either ceiling saw the generic
 * "the question could not be sent" fallback instead of the true reason.
 *
 * These are transcribed rather than imported because `BLOCKED_COPY` is
 * private to `GuestAllowance.tsx`, and this fix does not modify that file.
 * If either sentence there ever changes, this map must change with it in
 * the same edit.
 */
const DAILY_CAP_COPY: Record<"anon_daily_cap_reached" | "anon_source_daily_cap_reached", string> = {
  anon_daily_cap_reached: "Guest searches are paused for today",
  anon_source_daily_cap_reached: "This network has used its guest searches for today",
};

/**
 * One rail item.
 *
 * `id` INVARIANT, stated here because F-4.13-RV-01 shipped for want of it
 * being written down anywhere: an id must be unique across the whole list
 * and must stay the same for that row's whole life. It is therefore NEVER
 * derived from the row's position or from the list's length. The list can
 * SHRINK, since `ask` filters the re-asked question out before unshifting a
 * fresh row, so a positional id is reused the moment a re-ask keeps the
 * length flat, and three consumers read the id as though it were unique:
 * `FollowUp.tsx` renders it as React's `key` and compares it to `activeId`,
 * and `onOpen` below resolves a click with `history.find`, first match wins.
 * Two rows sharing an id means clicking one question runs a different one.
 *
 * Two id sources, and they cannot collide with each other: a restored row
 * takes the server's `trace_id` (`mergeServerHistory`), and a locally
 * created row takes `nextLocalHistoryId()`, which is `local-` plus a
 * per-tab counter that only ever increases.
 *
 * `traceId` is T-4.13-03: it is only present once the item's
 * run has actually been admitted (`response.run_id` from `createRun`, set
 * in `ask` below), and it is the SAME value the server's `GET /v1/history`
 * calls `trace_id` for that run (`app.py`'s "run_id/trace_id wiring"
 * comment). It exists to give `mergeServerHistory` a stable key; nothing
 * renders it. It is deliberately NOT reused as `id`: it does not exist yet
 * when the row is created, and a row must be clickable before its run has
 * been admitted.
 */
type HistoryEntry = { id: string; question: string; meta?: string; traceId?: string };

/**
 * Mints the id of a locally created rail row (F-4.13-RV-01's fix).
 *
 * A plain module-scoped counter, NOT `crypto.randomUUID()`. Both were
 * checked rather than assumed. `randomUUID` is present in this project's
 * vitest environment (jsdom 29 on Node 24 reports `crypto.randomUUID:
 * "function"` for both `globalThis` and `window`), but in a real browser it
 * is only defined in a secure context, so a build served over plain HTTP on
 * a LAN address, and Safari before 15.4, both hand back `undefined` and
 * throw at the call site. A counter needs no environment support at all,
 * and it is deterministic, which a test can read.
 *
 * `local-` prefixed so a locally minted id can never be mistaken for, or
 * collide with, a server `trace_id`, which is a UUID.
 *
 * Module scope rather than a `useRef`, so the counter cannot be reset by a
 * remount while stale rows are still on screen, and so this stays a plain
 * function rather than something a `setHistory` updater has to close over.
 * Never called from inside a state updater: an updater must be pure, and
 * React invokes it twice under StrictMode.
 */
let localHistoryIdCounter = 0;
function nextLocalHistoryId(): string {
  localHistoryIdCounter += 1;
  return `local-${localHistoryIdCounter}`;
}

/**
 * F-4.13-A-10's fix. The prototype's `.rm` for a restored row is `(item.meta
 * || '').split(' · ').slice(1).join(' · ')` (`app.html` around
 * line 1263): the seed data's own `meta` minus its leading duration, i.e.
 * "N tools · N layers · N sources". `GET /v1/history`'s
 * `HistoryItem` (`adapters/web_sse/app.py`) carries none of that: only
 * `trace_id`, `question`, `asked_at`, `trust_signal` and `citation_count`.
 * The prototype's exact content is therefore not derivable, so this uses
 * the closest honest substitute the endpoint DOES return: `citation_count`
 * (the same "N sources" idea, one count short of three) and a short date
 * built from `asked_at`, which is what actually resolves the finding, since
 * a bare question with no date is what made a re-asked duplicate invisible
 * (F-4.13-A-10's own "reason" cell).
 *
 * Never throws and never renders "Invalid Date": an unparseable or absent
 * `asked_at` is omitted rather than surfaced as a broken-looking date.
 *
 * The guard below is `Number.isNaN(getTime())`, which decides VALIDITY and
 * cannot decide TYPE: `new Date(1)` and `new Date(true)` are both perfectly
 * valid 1970 dates, so a non-string `asked_at` would render a real-looking
 * date this function has no basis for. That is a type question and it is
 * answered one layer up, at the fetch boundary, by
 * `api.ts`'s `withValidatedOptionalFields`, which drops any of these three
 * fields not carrying its declared type. Both checks are load-bearing and
 * neither substitutes for the other: this one catches a well-typed string
 * that is not a date ("not-a-date"), that one catches a value that is not a
 * string at all.
 */
function formatHistoryMeta(item: HistoryItem): string | undefined {
  const parts: string[] = [];
  if (item.citation_count !== undefined && item.citation_count !== null) {
    const count = item.citation_count;
    parts.push(`${count} source${count === 1 ? "" : "s"}`);
  }
  if (item.asked_at) {
    const askedAt = new Date(item.asked_at);
    if (!Number.isNaN(askedAt.getTime())) {
      parts.push(askedAt.toLocaleDateString(undefined, { month: "short", day: "numeric" }));
    }
  }
  return parts.length > 0 ? parts.join(" · ") : undefined;
}

/**
 * T-4.13-03. Folds the server's own restored questions into the rail
 * without showing a run this tab already ran twice.
 *
 * KEY: `traceId`, matched against the server's `trace_id`, never `question`
 * text. The same question asked on two separate occasions is two separate,
 * real `interactions` rows (a researcher re-checking the same gene is a
 * realistic case, not an edge case), and collapsing on text would silently
 * drop one of them. `traceId` is set on a local item the moment `createRun`
 * resolves (see `ask`), well before the seeding effect's fetch could ever
 * observe that row, so the match is exact rather than a best guess.
 *
 * A local item with no `traceId` yet (a run still in flight, or one whose
 * best-effort capture write never landed, Section 16) is always kept
 * unconditionally: the server response cannot contain a row for it, so
 * there is no duplicate to resolve, only a real item that must not be
 * dropped.
 *
 * Server items already carry no local counterpart are appended AFTER the
 * current list, so this tab's own live activity (and its richer `meta`,
 * computed from the actual event stream rather than absent) stays above
 * older restored history, and a caller reloading with no local items yet
 * sees exactly the server's own newest-first order.
 */
function mergeServerHistory(current: HistoryEntry[], serverItems: HistoryItem[]): HistoryEntry[] {
  const localTraceIds = new Set(
    current
      .map((item) => item.traceId)
      .filter((traceId): traceId is string => traceId !== undefined),
  );
  const restored: HistoryEntry[] = serverItems
    .filter((item) => !localTraceIds.has(item.trace_id))
    .map((item) => ({
      id: item.trace_id,
      question: item.question,
      traceId: item.trace_id,
      meta: formatHistoryMeta(item),
    }));
  return [...current, ...restored];
}

/**
 * Whether the stored-searches rail starts open.
 *
 * Open by default at `md` and above, matching the prototype's
 * `railOpen:true`. Below `md` the rail is a temporary drawer (fix set 4,
 * decision U9, `HistoryRail` in `components/answer/FollowUp.tsx`), and a
 * drawer that opens itself the moment sign-in lands is a modal sitting on
 * top of the search box with everything behind it `aria-hidden`, measured
 * by the drawer's own browser spec. So on a phone it starts closed and the
 * app bar toggle opens it. 900px is MUI's `md` breakpoint, the same value
 * `useMediaQuery(theme.breakpoints.down("md"))` reads in the rail.
 * Guarded because jsdom has no `matchMedia`; there the desktop default
 * holds, which is what every existing rail test assumes.
 */
function railOpenByDefault(): boolean {
  try {
    return typeof window.matchMedia !== "function" || window.matchMedia("(min-width:900px)").matches;
  } catch {
    return true;
  }
}

export function App() {
  // T-4.16-05. Was `useState<ScreenName>("search")`, which is why every
  // page served at `/` and the URL never changed. `useScreenRoute` is the
  // same state plus the two directions of history sync; see
  // `lib/routing.ts` for why this adds no router dependency.
  const [screen, setScreen] = useScreenRoute();
  /**
   * The finished turns of the conversation now on screen (T-4.16-02).
   *
   * Held here rather than in `AnswerScreen` because it must survive that
   * component unmounting while the next run is on the run screen, and
   * because only this level knows the difference between continuing a
   * conversation and starting one.
   *
   * Cleared by "New search" and by signing out, never trimmed: a reader who
   * asked six follow-ups is entitled to all six, and the prototype's own
   * `#thread` grows without a cap.
   *
   * The sign-out half of that sentence was false until this fix. `setThread`
   * appeared only in the three New-search handlers, never in the sign-out
   * handler, so on a shared browser the first person's collapsed turns,
   * their questions, claims, sources and trust verdicts, stayed on screen
   * for whoever signed in next. Closed by adding `setThread([])` to the
   * sign-out handler below, which is what makes this sentence true rather
   * than merely stated.
   */
  const [thread, setThread] = useState<PreviousTurn[]>([]);
  const [searchView, setSearchView] = useState<SearchView>({ name: "home" });
  /**
   * A guest identity this tab is holding (T-4.10-08), or `null` before one
   * has ever been minted. Seeded from `localStorage` on mount so a reload
   * does not silently hand the visitor a fresh allowance (design decision
   * 1: the token is clearable, and clearing it on purpose IS how a fresh
   * allowance is obtained, but a plain reload must not do that by
   * accident). Minted lazily, on the first anonymous ask, not eagerly here
   * on mount: eager minting would fire an unauthenticated write on every
   * page load, including one that never asks anything.
   */
  const [guestToken, setGuestToken] = useState<string | null>(loadPersistedGuestToken);
  /**
   * Whether this browser has already converted a guest identity into an
   * account (F-4.10-A-05). Seeded from storage on mount, the same way the
   * token itself is, because it has to outlive both a reload and a
   * sign-out to be worth anything.
   *
   * It exists because the token alone cannot carry the fact. A migrated
   * guest session is revoked server-side in the same transaction, so its
   * token is a dead credential that must not be sent again; but forgetting
   * it entirely is what let an ordinary sign in, sign out, ask cycle mint a
   * brand-new identity with five fresh searches, indefinitely. The token is
   * dropped and the fact is kept. See `lib/guestSession.ts` for the full
   * argument, including why this is an honesty control rather than a
   * security one (the server's daily anonymous ceiling is the real bound).
   */
  /**
   * The caller's own search allowance, read ONLY from `GET /v1/allowance`
   * (or the equivalent fields on a fresh `POST /auth/guest` response).
   * Never computed or incremented client-side: the client-side counter
   * this field replaces was exactly the fabrication class build phase
   * 4.8's judge round filed. `null` before any fetch has resolved.
   */
  const [allowance, setAllowance] = useState<AllowanceResponse | null>(null);
  /**
   * The account's 15-minute access token, in memory only, never persisted.
   *
   * Starting `null` on every mount used to mean every reload signed the
   * account out. It still starts `null`, and the difference fix set 4
   * (requirement R46, decision U8) makes is that a persisted REFRESH token
   * can now re-mint it: the restore effect below reads that token on load,
   * exchanges it, and sets this. So this value is still short-lived and
   * still never written to storage, while the session it belongs to
   * survives a reload. See `lib/authSession.ts` for what is persisted, why
   * `localStorage` adds no new exposure class here, and why an httpOnly
   * cookie was rejected for now.
   */
  const [token, setToken] = useState<string | null>(null);
  /**
   * Whether the one restore attempt this mount is allowed has already been
   * started (fix set 4, R46).
   *
   * A ref rather than state because nothing renders from it and it must be
   * readable and writable synchronously, before any await.
   *
   * IT EXISTS FOR ONE REASON: a refresh token is single-use. `POST
   * /auth/refresh` revokes the token it is given in the same transaction
   * that mints the replacement, and presenting a revoked token revokes the
   * whole family and answers 401 (F-1.1-07). React StrictMode invokes a
   * mount effect, cleans it up, and invokes it again, so without this guard
   * a development load would send the same token twice and the second send
   * would destroy the session the first one had just restored. The guard
   * makes "at most one refresh per stored token" a property of the code
   * rather than a hope about the renderer.
   */
  const restoreStarted = useRef(false);
  /** The signed-in account, named in the rail's footer (the prototype's `.rfoot`). */
  const [accountEmail, setAccountEmail] = useState<string | null>(null);
  const [runId, setRunId] = useState<string | null>(null);
  const [accepted, setAccepted] = useState(hasAcceptedDisclaimer);
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [flagged, setFlagged] = useState<number[]>([]);
  const [dispatchError, setDispatchError] = useState<string | null>(null);
  /**
   * The depth the user last chose (F-4.8-A-22).
   *
   * Follow-ups and history re-asks hardcoded "researcher", silently discarding
   * a deep_technical or clinical_brief selection the user had made on the
   * landing screen.
   */
  const [depth, setDepth] = useState<AudienceDepth>("researcher");
  /**
   * Monotonic ask counter, for request sequencing (F-4.8-A-02).
   *
   * The J-03 fix gated the view on `runId`, which closes the null window but
   * not a STALE RESPONSE: a slow `createRun` from an abandoned question still
   * called `setRunId` after a newer question had replaced the heading, so the
   * adversary saw the answer to "what causes cancer" under the heading "what is
   * BRCA1". The history rail makes that reachable with two clicks.
   *
   * A ref rather than state: it must be readable synchronously inside the async
   * callback without re-rendering, and it is never rendered.
   */
  const askSeq = useRef(0);
  /**
   * The rail row the run now in flight belongs to (F-4.13-FV-01).
   *
   * The meta effect below used to find its row by QUESTION TEXT, which was
   * safe for exactly as long as `ask` was the only writer to `history`,
   * because `ask` guarantees at most one row per question text. Build phase
   * 4.13 added a second writer, `mergeServerHistory`, which de-duplicates on
   * `traceId` and never on text, so two rows carrying the same question can
   * coexist for the first time. Then one landing run rewrote BOTH, and a row
   * restored from weeks ago reported this run's source count and date.
   *
   * A ref rather than state on purpose: nothing renders from this, and making
   * it state would re-run the effect on every ask for no benefit.
   */
  const activeEntryId = useRef<string | null>(null);
  /** True while a stopped run should stay stopped (F-4.8-A-10). */
  const [stopped, setStopped] = useState(false);
  // T-6.2-05. When the current run started, client-side, driving the
  // elapsed counter on the run screen. Deliberately NOT `view.elapsedMs`,
  // which comes from the server's `done` payload and therefore only
  // exists once the answer has already landed: the number a user needs
  // is the one during the 12 to 14 second wait, not after it.
  const [runStartedAt, setRunStartedAt] = useState<number | null>(null);
  /**
   * Whether the stored-searches rail is open (F-4.8-P-03).
   *
   * Open by default, matching the prototype's `railOpen:true`. Held here rather
   * than inside `HistoryRail`, because the collapsed state must survive the
   * rail unmounting: the app bar's toggle and the collapsed strip both need it,
   * and a collapse the user chose must outlive the next question.
   */
  const [railOpen, setRailOpen] = useState(railOpenByDefault);

  /**
   * The onboarding tour (2026-09-13 product-owner request), see
   * `components/tour/OnboardingTour.tsx` for the design. `tourOpen` and
   * `tourStep` live here because step 7 has to reach `ask` and because the
   * tour reads the same `searchView` and `view` every screen renders from.
   * `tourSeen` mirrors the per-browser flag so the invite disappears the
   * moment it is dismissed, without a re-read of storage.
   */
  const [tourOpen, setTourOpen] = useState(false);
  const [tourStep, setTourStep] = useState(0);
  const [tourSeen, setTourSeen] = useState(hasSeenTour);
  const startTour = useCallback(() => {
    setTourStep(0);
    setTourOpen(true);
  }, []);
  const endTour = useCallback(() => {
    setTourOpen(false);
    markTourSeen();
    setTourSeen(true);
  }, []);
  const dismissTourInvite = useCallback(() => {
    markTourSeen();
    setTourSeen(true);
  }, []);

  /**
   * The conversation id sent with every question.
   *
   * F-4.8-R-02. This was `useMemo(..., [])`, so it survived sign-out: account A
   * and account B sent the IDENTICAL session_id, which is the key the backend
   * groups in-conversation memory under. The sign-out fix enumerated eight
   * pieces of state and missed this one, while its own comment claimed
   * "everything session-scoped is cleared here, in one place".
   *
   * It is state rather than a memo now, so signing out can mint a new one.
   */
  const newSessionId = () =>
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : `session-${Date.now()}-${Math.floor(Math.random() * 1e6)}`;
  const [sessionId, setSessionId] = useState(newSessionId);

  // Section 14.2, presentation only. T-4.5-10 replaced the local
  // `drawPersona(0)` stub with the name the SERVER assigns: it arrives once,
  // on the `POST /v1/query` response body, and is never repeated on a
  // streamed event. Drawing it here would have been a fabrication of exactly
  // the class F-4.8-J-01 was filed for, since the client cannot know which
  // scientist the account is bound to.
  //
  // Null until the first run returns. `PersonaChip` renders nothing rather
  // than a placeholder in that window, because a name that changes once the
  // first answer lands reads as a bug to the user.
  //
  // `about` and `wikipedia` (2026-09-13 product-owner request: visitors do
  // not know who these scientists are) ride along as the same object so the
  // chip's info affordance can never show one persona's name next to
  // another's biography. Both are null whenever the backend has not sent
  // them yet, which is the same graceful degradation as the name itself:
  // the chip's info button simply does not render, never a fabricated bio.
  const [persona, setPersona] = useState<{
    name: string;
    about: string | null;
    wikipedia: string | null;
  } | null>(null);

  // Fetch the persona before the first question, so the chip build phase 4.8
  // put in the shell has a real name rather than a locally invented one.
  // Best-effort: a failure leaves the chip absent, which is the honest
  // degradation, never a fabricated scientist.
  //
  // ONE effect owns this, and F-4.5-A-12 is why it is stated that way. There
  // used to be two: this one, keyed on `[sessionId]` and always anonymous,
  // and the `/auth/me` effect below, keyed on `[token]`, both calling
  // `setPersona`. Nothing ordered them and nothing cancelled one when the
  // other ran, so for a signed-in user the chip showed whichever HTTP
  // response happened to land second, and then changed again when the first
  // run returned. `PersonaChip`'s own docstring says a name that changes
  // after load "reads as a bug to the user", which is exactly what two
  // unordered writers to one piece of state produce.
  //
  // The dependency array carries `token` as well as `sessionId` because the
  // ANSWER depends on both: the server keys the persona on the account when
  // a credential is presented and on the session otherwise. Signing in or out
  // re-runs this effect, and its cleanup aborts the in-flight request from
  // the previous identity, so a slow anonymous response can never overwrite a
  // fresh signed-in one.
  useEffect(() => {
    const controller = new AbortController();
    fetchPersona(sessionId, { signal: controller.signal, token })
      .then((result) =>
        setPersona({
          name: result.persona_name,
          about: result.persona_about ?? null,
          wikipedia: result.persona_wikipedia ?? null,
        }),
      )
      .catch(() => undefined);
    return () => controller.abort();
  }, [sessionId, token]);

  // T-4.5-08, Section 14.5: "once auth is live, depth defaults to the user's
  // last-used value". Seeded from the account rather than from localStorage,
  // because the preference belongs to the account and should follow it to
  // another device.
  //
  // This effect deliberately does NOT touch the persona. `MeResponse` still
  // carries `persona_name` and it is still correct; adopting it here is what
  // made this effect the second writer in F-4.5-A-12's race. The persona
  // effect above is the single owner, and it now asks with this same token,
  // so it returns the account-keyed name without a second request racing it.
  //
  // Best-effort: a failure leaves the control at whatever it already shows,
  // which is the contract default. A preference that fails to load must never
  // block asking a question.
  useEffect(() => {
    if (token === null) return undefined;
    const controller = new AbortController();
    fetchMe(token, { signal: controller.signal })
      .then((me) => {
        if (
          me.audience_depth === "clinical_brief" ||
          me.audience_depth === "researcher" ||
          me.audience_depth === "deep_technical"
        ) {
          setDepth(me.audience_depth);
        }
      })
      .catch(() => undefined);
    return () => controller.abort();
  }, [token]);

  /**
   * T-4.13-03: seed the rail from the server once a signed-in principal
   * exists, and again every time `token` changes, which is what "again
   * after sign-in" means in practice here. `token` starts `null` on every
   * mount (it is not persisted, unlike the guest token; see its own
   * comment above), so this effect does not yet reach a person who reloads
   * while still signed in from an earlier visit, only one who reloads and
   * signs back in, or one already signed in this tab. Fixing that is a
   * token-persistence gap outside this ticket's scope, not a defect in the
   * merge below.
   *
   * Scoped to `signedIn`, not to `authToken` (which would also cover a
   * guest token): `railAvailable` below only renders the rail for a
   * signed-in account, matching `tracker/phase_4.13.md`'s own coverage
   * note that `GET /v1/history` is scoped for a guest principal only so
   * the isolation property holds whether or not any UI calls it, not
   * because this UI calls it for one.
   *
   * Best-effort, per production-standards' graceful-degradation gate: a
   * failed, malformed, or 401 fetch (a token that expired between mount
   * and this effect, most realistically) leaves whatever is already on
   * screen, including this session's own live items, rather than blanking
   * the rail. The `AbortController` cleanup also means a slow fetch from
   * an account that has since signed out, or switched to a different
   * account, can never resolve into `setHistory` after the fact, which is
   * what keeps a second identity from ever inheriting the first's list.
   */
  useEffect(() => {
    if (token === null) return undefined;
    const controller = new AbortController();
    fetchHistory(token, { signal: controller.signal })
      .then((response) => {
        setHistory((current) => mergeServerHistory(current, response.items));
      })
      .catch(() => undefined);
    return () => controller.abort();
  }, [token]);

  /**
   * The account's search allowance, keyed on the token rather than on the
   * sign-in handler alone (fix set 4, R46). The sign-in handler already
   * fetches it, but a session restored from the persisted refresh token
   * never passes through that handler, so after a reload the rail footer
   * sat on "Checking your search limit…" indefinitely, measured on the
   * live app the day the restore shipped. Keying on the token also refetches
   * after each 12-minute rotation, which is cheap and keeps the number
   * honest. Never computed client-side: the value is whatever
   * `GET /v1/allowance` returned, or null while nothing has.
   */
  useEffect(() => {
    if (token === null) return undefined;
    const controller = new AbortController();
    getAllowance(token, { signal: controller.signal })
      .then((fetched) => setAllowance(fetched))
      .catch(() => undefined);
    return () => controller.abort();
  }, [token]);

  /**
   * Fetch a returning guest's own allowance once, at mount.
   *
   * Before this fix, `allowance` was seeded `null` on every mount and the
   * only two writers were a landed run and a fresh sign-in, so a guest who
   * had already spent part of yesterday's five, and whose token was
   * restored from storage by `guestToken`'s own initializer above, saw no
   * dots at all until their NEXT ask spent a third search: the server
   * already knew the count, and nothing on mount ever asked it.
   *
   * This is a DIFFERENT question from F-4.10-A-13 (`tracker/phase_4.10.md`),
   * which asks whether a BRAND NEW visitor, one with no persisted token at
   * all, should see dots before their first ask. That is an open
   * product-owner design question and is deliberately left alone here: a
   * first-time visitor still mints no guest identity until they actually
   * ask (T-4.10-08), `guestToken` is still `null` for them at mount, this
   * effect still does nothing for them, and the footer is still absent
   * until their first ask, exactly as before this fix.
   *
   * Deliberately `[]` rather than `[guestToken]`: this fetches the
   * ALREADY-PERSISTED token's own standing once, at load. A guest token
   * minted later, on the first ask, already gets its `used`/`total` from
   * the mint response itself (see `ask` below), so re-running this effect
   * on that later change would be a redundant fetch, not a missing one.
   *
   * Best-effort per production-standards' graceful-degradation gate: a
   * failed or malformed fetch leaves `allowance` at `null`, exactly the
   * behaviour before this fix, never a broken-looking footer.
   */
  useEffect(() => {
    if (guestToken === null) return undefined;
    const controller = new AbortController();
    let cancelled = false;
    // `async`/`await` rather than `.then` chained directly onto the call:
    // `await` accepts any value, not only a genuine promise, so a caller
    // whose fetch layer is stubbed with something other than a real
    // `Promise` (a test double with no implementation configured, most
    // realistically) still resolves cleanly here instead of throwing on
    // `.then` of something that is not thenable. `fetched` is still
    // checked for truthiness before use, so that same case degrades to
    // "nothing to apply" rather than writing a malformed value into state.
    void (async () => {
      try {
        const fetched = await getAllowance(guestToken, { signal: controller.signal });
        if (!cancelled && fetched) setAllowance(fetched);
      } catch {
        // Best-effort per production-standards' graceful-degradation gate:
        // a failed or malformed fetch leaves `allowance` exactly as it was.
      }
    })();
    return () => {
      cancelled = true;
      controller.abort();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /**
   * Everything a signed-out visitor must not be holding, cleared in one
   * place.
   *
   * Factored out of the account menu's Log out handler for fix set 4
   * (requirement R46) so the keep-alive effect below can reach the SAME end
   * state when a session dies on its own. A session that cannot be renewed
   * is a session that has ended, and the two paths differing would be the
   * bug: one of them would leave the previous account's questions, answers
   * and rail on screen.
   *
   * Log out still calls `stop()` itself immediately before calling this,
   * which is deliberate rather than an omission. `stop` comes from
   * `useAgentRun`, which is initialised further down this file and is
   * therefore not in scope here; and it is not needed for correctness,
   * because `useAgentRun` aborts its in-flight stream whenever `runId` or
   * `token` changes and this function clears both.
   *
   * `[]` dependencies: every value it touches is either a `useState` setter
   * (stable by contract), a ref, or `newSessionId`, which reads nothing
   * from the render it was created in.
   */
  const clearAccountState = useCallback(() => {
    // F-4.8-A-11, A-12 and A-13. Signing out previously left the previous
    // account's answer, source cards, trust pills and history rail on
    // screen, and the NEXT account inherited that history. Worse,
    // `runId` survived, so `useAgentRun` refired the old run's event
    // stream with the new account's bearer token, producing a 403 that
    // nothing surfaced. On a shared workstation that is a colleague's
    // research queries and results.
    //
    // Everything session-scoped is cleared here, in one place, so a new
    // sign-in starts from nothing. That claim was false for `thread`:
    // this handler cleared the run and the rail but left the previous
    // turns rendered by AnswerScreen on screen, so on a shared
    // workstation the next person to sign in saw the last person's
    // collapsed questions, claims, sources and trust verdicts.
    // `setThread([])` below closes it, so the claim is something this
    // handler actually does rather than something its comment merely
    // asserted.
    askSeq.current += 1;
    setToken(null);
    setAccountEmail(null);
    // Fix set 4 (R46): the persisted credential goes with the state it
    // belongs to. Log out revokes it server-side as well (see the handler);
    // this line is what stops the NEXT load from restoring a session the
    // person has just left.
    clearPersistedRefreshToken();
    // The guard belongs to the session that just ended, so it is released
    // with it. This changes nothing today, and the honest reason to keep it
    // is stated rather than dressed up: the restore effect has `[]`
    // dependencies, so it runs once per mount and a reload remounts with a
    // fresh ref anyway. It is here so that if the effect is ever re-keyed to
    // run again within one mount, a flag left `true` by a previous session
    // cannot silently refuse the restore.
    restoreStarted.current = false;
    setRunId(null);
    setStopped(false);
    setThread([]);
    setHistory([]);
    setFlagged([]);
    setDispatchError(null);
    // T-4.10-08: the allowance belonged to the account that just
    // signed out; the next caller (signed in or anonymous) gets its
    // own, fetched fresh, never a stale number inherited across the
    // sign-out.
    setAllowance(null);
    // R-02: a new conversation, not the previous account's.
    setSessionId(newSessionId());
    // R-11: the next person at this workstation has not read the
    // disclaimer, and has not chosen a depth. The modal's own docstring
    // argues session scope precisely so a notice one person dismissed is
    // not treated as read by the next.
    setAccepted(false);
    setDepth("researcher");
    // P-03: the next person at this workstation did not collapse the
    // rail, so they do not inherit a collapsed one.
    setRailOpen(railOpenByDefault());
    // Set 1 (R6): Log out lands on the search home page from any screen,
    // including Integrations and About (Docs folded into Integrations, fix set 5).
    setScreen("search");
    setSearchView({ name: "home" });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /**
   * Restore the signed-in session on load, fix set 4, requirement R46,
   * product-owner decision U8 (2026-09-12): "keep people signed in across a
   * reload, with history where they left it."
   *
   * The mechanism, in order: read the persisted refresh token, exchange it
   * at `POST /auth/refresh` for a fresh access token plus a fresh refresh
   * token, store the ROTATED one, then read `GET /auth/me` for the email
   * the app bar and the rail footer name. Setting `token` is also what
   * makes the history rail refill: the `GET /v1/history` seeding effect
   * above is keyed on `token`, so it runs the moment this resolves, with no
   * user action. That effect's own comment used to say it "does not yet
   * reach a person who reloads while still signed in"; this is the change
   * that makes it reach them.
   *
   * FAILURE IS SILENT, BY DESIGN. A 401 (expired, revoked, or replayed
   * token), a network failure, and a malformed response all land in the
   * same place: the stored value is dropped and the visitor is an ordinary
   * guest looking at the landing screen. There is nothing for them to act
   * on, and an error banner about a credential they never knew existed
   * would be noise. This is `production-standards`' graceful-degradation
   * gate: the page renders, the product works, one convenience is absent.
   *
   * THE STORED TOKEN IS READ AND CLEARED BEFORE THE REQUEST IS SENT, not
   * after it succeeds. The server revokes the presented token as part of
   * rotating it, so the value stops being usable the instant it is sent;
   * clearing first means no second code path, and no second React
   * invocation, can find it and send it again. A replay would revoke the
   * entire family (F-1.1-07), which would sign the person out of every
   * device rather than merely failing here.
   *
   * NO `AbortController` CLEANUP, and this effect deliberately differs from
   * its neighbours above on that point. Aborting a rotation is not a
   * cancellation, it is a loss: the server has already revoked the old
   * token by the time the response is discarded, so the browser ends up
   * holding nothing and the session is gone. Under StrictMode, whose
   * mount-cleanup-mount sequence runs the cleanup while this request is
   * still in flight, an abort here would sign the account out on every
   * development load. The `restoreStarted` guard is what bounds this
   * instead: at most one request, ever, per mount.
   */
  useEffect(() => {
    if (restoreStarted.current) return;
    restoreStarted.current = true;
    const stored = loadPersistedRefreshToken();
    if (stored === null) return;
    clearPersistedRefreshToken();
    void (async () => {
      try {
        const rotated = await refreshSession(stored);
        // Truthiness-checked rather than assumed, the same reasoning the
        // allowance effect above gives: a stubbed or malformed response
        // degrades to "nothing to restore" instead of writing a broken
        // value into state.
        if (!rotated?.access_token || !rotated.refresh_token) return;
        // Stored BEFORE any state write, so the one live credential is
        // never lost to whatever happens next in this function.
        persistRefreshToken(rotated.refresh_token);
        setToken(rotated.access_token);
        const me = await fetchMe(rotated.access_token);
        if (me?.email) setAccountEmail(me.email);
      } catch {
        // Silent, per this effect's docstring. The token was already
        // cleared above, so there is nothing left to clean up.
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /**
   * Keep the session alive while the tab stays open (fix set 4, R46).
   *
   * The access token lives 15 minutes (`auth/tokens.py`), so without this a
   * person reading one long answer would find their next question rejected
   * with a 401. Rotating every 12 minutes leaves a three-minute margin for
   * a slow round trip, and each rotation carries the 30-day idle window
   * forward, so a tab left open does not quietly expire either. The 90-day
   * absolute ceiling is carried forward unchanged by the server and is
   * never renewed by rotation (`router.py`'s `refresh`), so this cannot
   * extend a session indefinitely.
   *
   * Read-and-clear before sending, for the same single-use reason the
   * restore effect gives. A failure ends the session through
   * `clearAccountState`, the same end state as pressing Log out, rather
   * than leaving the app looking signed in with a credential that no longer
   * works.
   *
   * If storage is unreachable there is nothing to read, so this does
   * nothing and the session simply expires with the access token, exactly
   * as it did before this fix. That is the degradation `lib/authSession.ts`
   * describes, not a new failure.
   */
  useEffect(() => {
    if (token === null) return undefined;
    // Twelve minutes, under the access token's 15-minute lifetime. Declared
    // inside the effect so it is not a reactive value the dependency list
    // has to carry.
    const ROTATE_EVERY_MS = 12 * 60 * 1000;
    const timer = window.setInterval(() => {
      const stored = loadPersistedRefreshToken();
      // Nothing stored means nothing to rotate: a sign-in that happened
      // while storage was unreachable, most realistically. Leave the
      // session alone rather than signing a working tab out.
      if (stored === null) return;
      clearPersistedRefreshToken();
      void (async () => {
        try {
          const rotated = await refreshSession(stored);
          if (!rotated?.access_token || !rotated.refresh_token) {
            clearAccountState();
            return;
          }
          persistRefreshToken(rotated.refresh_token);
          setToken(rotated.access_token);
        } catch {
          clearAccountState();
        }
      })();
    }, ROTATE_EVERY_MS);
    return () => window.clearInterval(timer);
  }, [token, clearAccountState]);

  const signedIn = token !== null;
  /**
   * The bearer token every `/v1/query*` call actually authenticates with
   * (T-4.10-08): the real access token once signed in, the guest token
   * before that. `useAgentRun`, the run screen's Stop action and the ask
   * flow below all read this one value rather than each re-deriving it, so
   * there is exactly one place "which token authenticates this caller"
   * can disagree with itself.
   */
  const authToken = token ?? guestToken;
  /**
   * The account menu's line and the rail footer's line (T-4.10-09) are
   * built from this ONE string, computed once here from whatever
   * `allowance` currently holds, so the two surfaces are structurally
   * unable to disagree with each other. `dailyLimitPhrase` never renders
   * an uncounted zero as a measured count (F-4.9-A-16); see its own
   * docstring in `lib/guestSession.ts`.
   */
  const dailyLimitLine = dailyLimitPhrase(allowance);

  /**
   * Whether the rail, its strip and its toggle exist at all (F-4.8-P-03).
   *
   * The prototype's `avail = st.loggedIn && onSearch`, transcribed. It does
   * NOT consider the history length: the rail renders its own empty state
   * before the first search, so the toggle is available from sign-in. An
   * earlier version added `history.length > 0`, which matched the shipped
   * rail's return-null-when-empty behaviour rather than the design.
   *
   * Computed once and used by all three controls, so the toggle can never be
   * offered for a rail that is not there, and the strip can never appear where
   * the rail would not have.
   */
  const railAvailable = signedIn && screen === "search" && searchView.name !== "signin";

  // `status` and `error` were both discarded here (F-4.8-A-09). If the event
  // stream failed to open at all, a 500, a malformed frame, or, realistically,
  // a 401 from a token that expired between createRun and openEventStream, the
  // run screen sat with five pending steps and Stop disabled, silently, for
  // ever. F-4.8-J-12 closed exactly this hole for createRun and left the
  // identical one a single call downstream.
  const { events, status, error: streamError, stop } = useAgentRun(runId, authToken);
  const streamed = useRunView(events);

  /**
   * F-4.8-J-03. `useAgentRun` does not clear its buffer when `runId` goes null,
   * so between asking a new question and `createRun` returning, the PREVIOUS
   * run's events were still live: `landed` was still true, the answer screen
   * opened immediately, and run one's cited answer rendered under question
   * two's heading. The judge reproduced a claim about aspirin and COX-1 shown
   * under "What is the treatment for scurvy?".
   *
   * Gating on `runId` closes that window at the point of use, without reaching
   * into a hook other screens share.
   */
  const view = runId === null ? EMPTY_RUN_VIEW : streamed;

  /*
   * What the tour is told about the run it is watching, derived from the
   * same two values the screens render from so it can never describe a
   * different run than the one on screen. A stopped run reads as `idle`:
   * the stopped block's own "Run again" is the way forward there, and the
   * tour's step 7 card still offers "Run it for me".
   */
  /**
   * Whether the answer screen is currently showing a RUN rather than an
   * answer (UI fix set 7, R22).
   *
   * True from the moment a follow-up is dispatched until its run terminates,
   * which is the window in which `AnswerScreen` renders `RunProgress` in
   * place of the answer body.
   *
   * `runId` is deliberately NOT part of this. It is null for the few
   * hundred milliseconds between the ask and `createRun` returning, and
   * requiring it would render an empty answer under the new question for
   * exactly that long, which is the blank-frame class F-4.8-J-03 was filed
   * for, arrived at from the other side.
   *
   * A stopped run keeps this true on purpose: `stop()` leaves `status` at
   * `done` and never lands the view, so `RunProgress` shows its own
   * "Search stopped" block inline, the same as the full-screen run does.
   * The two exits are a terminal event (`view.landed`) and a stream that
   * failed to open at all (`status === "error"`, or a dispatch that never
   * reached the server), and both put the answer body back with its own
   * failure notice.
   */
  const inlineRunActive =
    searchView.name === "answer" &&
    searchView.continued === true &&
    !view.landed &&
    status !== "error" &&
    dispatchError === null;
  const tourRunState: TourRunState =
    (searchView.name === "run" || inlineRunActive) && !stopped
      ? "running"
      : searchView.name === "answer"
        ? "answered"
        : "idle";
  const tourOutcome: TourOutcome | null =
    searchView.name !== "answer" || inlineRunActive
      ? null
      : view.refusal !== null || view.refusalLabel !== null
        ? "refusal"
        : (dispatchError ?? view.failure ?? streamError)
          ? "failure"
          : "answer";
  // Product-owner feedback, 2026-09-12: "2-3 seconds of staring at the
  // screen and nothing happens". The server reports a step only once it has
  // FINISHED, so before the first event `activeStep` was null and the run
  // screen showed no pulse, no counter and no caption while Guard was
  // running. Guard is what is happening from the moment a question is sent,
  // so it is shown live until the stream says otherwise.
  const step: StepName | null =
    view.activeStep ??
    ((searchView.name === "run" && !view.landed) || inlineRunActive ? "Guard" : null);

  useEffect(() => {
    if ((view.landed || status === "error") && searchView.name === "run") {
      setSearchView({ name: "answer", question: searchView.question });
    }
  }, [view.landed, status, searchView]);

  /*
   * The prototype's `.rm`: each rail item carries its own run's counts.
   *
   * Written when the run LANDS, not when the question is asked, because the
   * counts do not exist until then. It is the same `view.meta` string the
   * answer screen shows, taken from the run's own events, so the rail cannot
   * disagree with the answer it points at.
   */
  useEffect(() => {
    if (!view.landed || !view.meta) return;
    const question = searchView.name === "answer" || searchView.name === "run"
      ? searchView.question
      : null;
    if (question === null) return;
    // F-4.13-FV-01. Matched on the row's own IDENTITY, not on its question
    // text. Text stopped identifying a row the moment `mergeServerHistory`
    // became a second writer to this list, and a restored row asking the
    // same question is a DIFFERENT run with its own count and its own date.
    // The question is still compared, as a guard rather than as the key: if
    // the ref has moved on to another ask, its row will not match this
    // landing run's question and nothing is written.
    const entryId = activeEntryId.current;
    if (entryId === null) return;
    setHistory((current) =>
      current.map((item) =>
        item.id === entryId && item.question === question && item.meta !== view.meta
          ? { ...item, meta: view.meta }
          : item,
      ),
    );
  }, [view.landed, view.meta, searchView]);

  const ask = useCallback(
    async (
      question: string,
      chosenDepth: AudienceDepth,
      /**
       * T-4.16-02. True only from the follow-up field, which continues the
       * conversation; false from the landing screen and from the history
       * rail, which start one.
       *
       * The flag is passed rather than inferred from `searchView.name`,
       * because "the answer screen is showing" is not the same fact as
       * "the reader chose to continue": "New search" is also on the answer
       * screen and means the opposite.
       */
      continuesThread = false,
    ) => {
      setDepth(chosenDepth);
      // Set 1 (R1 to R3, 2026-09-12): there is no guest allowance and no
      // sign-in wall any more. A browser whose guest session was moved into
      // an account simply mints a fresh guest identity on its next signed-out
      // question. What bounds anonymous spend is the server's anonymous daily
      // cap and per-connection share, not a per-browser count.
      // F-4.8-J-01's rule survives unchanged (see the file docstring): no
      // answer content is ever rendered from anything but a real run's own
      // event stream. What changed in build phase 4.10 is that an
      // anonymous visitor now HAS a real run to ask for, via a guest
      // identity, instead of being turned away at this point. The
      // `if (!signedIn) return wall` intercept that used to sit here is
      // gone; an anonymous caller now proceeds exactly like a signed-in one,
      // just with a guest token instead of an access token.
      setFlagged([]);
      setDispatchError(null);
      // F-4.13-A-07's fix. The old form only ADDED an entry when the
      // question text was not already present, so re-asking a question
      // already in the rail, live or restored, did nothing here, and the
      // meta effect a few lines below then relabeled that unmoved item
      // with THIS run's numbers once it landed: a restored row's meta was
      // overwritten by a run it did not represent. The prototype's own
      // `start()` never relabels in place; it filters the old entry out and
      // unshifts a fresh one to the top (`app.html`, around line 1262,
      // `st.history = st.history.filter(...); st.history.unshift(...)`),
      // which is what a re-ask actually is: a new run for an old question,
      // not an edit of the old run's record. Transcribed the same way here,
      // so the freshly unshifted entry starts with no `meta` and no
      // `traceId` of its own, exactly like a brand-new question.
      //
      // F-4.13-FV-02. This comment used to claim the rail holds "at most one
      // item per question text". THAT IS FALSE and stating it was actively
      // harmful, because a comment asserting an invariant is where the next
      // reader stops checking. The filter here dedups by text only among the
      // rows present AT THE MOMENT OF THE ASK; `mergeServerHistory` is a
      // second writer that keys on `traceId` and never on text, so a server
      // copy of the same question arriving afterwards is kept, and two rows
      // then share a text. What actually holds is narrower and is the thing
      // to rely on: every row's `id` is unique, a local one from
      // `nextLocalHistoryId()` and a restored one from its server `trace_id`.
      // F-4.13-FV-01 is what it cost to learn that, and the meta effect
      // above now keys on identity for exactly this reason.
      //
      // F-4.13-RV-01's fix. The id was `String(current.length)`, which the
      // filter above silently invalidated: the filter can SHRINK the list,
      // so a re-ask that removes one row and adds one leaves the length
      // flat and the next question reuses the id the re-asked row holds.
      // The fix is the identity, not the reducer: filter-then-unshift is
      // what the prototype does and it is correct, and the prototype can do
      // it safely because its row identity is not a positional counter.
      // The full invariant is stated on `HistoryEntry` above. Minted HERE,
      // outside the updater, because a state updater must be pure and React
      // invokes it twice under StrictMode.
      const entryId = nextLocalHistoryId();
      // F-4.13-FV-01: the meta effect writes this run's counts onto THIS
      // row and no other. Set before the state update rather than after, so
      // a run that lands unusually fast cannot find a stale id here.
      activeEntryId.current = entryId;
      setHistory((current) => [
        { id: entryId, question },
        ...current.filter((item) => item.question !== question),
      ]);
      const seq = ++askSeq.current;
      /*
       * T-4.16-02. Archive the turn now on screen BEFORE anything resets,
       * which is what the prototype's `archiveCurrent()` does at the top of
       * `askFollowUp`.
       *
       * Ordering is load-bearing. `setRunId(null)` on the next line makes
       * `view` fall back to `EMPTY_RUN_VIEW`, so a read taken after it
       * would archive an empty turn: the right question with no answer
       * under it. Guarded on `landed` so a run stopped or failed mid-flight
       * is not filed away as if it had answered.
       */
      if (continuesThread && view.landed && searchView.name === "answer") {
        const finished = searchView.question;
        setThread((current) => [
          ...current,
          {
            question: finished,
            meta: view.meta,
            claims: view.claims,
            sources: view.sources,
            trust: view.trust,
          },
        ]);
      }
      setRunId(null);
      setStopped(false);
      setRunStartedAt(Date.now());
      /*
       * UI FIX SET 7 (R22). The product owner: "it goes to a new page, which
       * it should not. The first answer should minimise and the chat should
       * continue on the same screen. That is one of the most important
       * things."
       *
       * This line is where that went wrong. A follow-up moved to the `run`
       * view, which swaps the WHOLE screen for `RunScreen`, so the
       * conversation, the thread archived two lines above included, left the
       * page for the length of the second run and came back afterwards.
       *
       * A continuation now STAYS on the answer screen and marks itself
       * `continued`, which is what makes the render below pass the run's
       * progress to `AnswerScreen` as an inline node instead of rendering a
       * second screen. The first question from the landing, a question
       * reopened from the history rail, "Run again" and the tour all pass
       * `continuesThread` false and still get the full-screen run: they
       * start a conversation rather than continue one, so there is nothing
       * on screen to keep.
       */
      setSearchView(
        continuesThread
          ? { name: "answer", question, continued: true }
          : { name: "run", question },
      );

      try {
        let runToken: string;
        if (signedIn) {
          // `signedIn` is derived from `token !== null` at the same render,
          // so the two can never disagree here.
          runToken = token as string;
        } else if (guestToken !== null) {
          runToken = guestToken;
        } else {
          // T-4.10-08: minted lazily, on the FIRST question an anonymous
          // visitor actually asks, never eagerly on page load. Eager
          // minting would fire an unauthenticated write on every visit,
          // including one that never asks anything.
          // `sessionId` is passed so the mint response's own `persona_name`
          // is keyed the way every later query from this guest is keyed
          // (F-4.5-A-12). This app does not read that field, since the
          // persona effect above already owns the chip, but a wire value
          // that cannot be correct for any client is worse than one that is.
          const minted = await mintGuest({ sessionId });
          if (!minted || typeof minted.guest_token !== "string") {
            throw new Error("could not start a guest session; check your connection and try again");
          }
          if (seq !== askSeq.current) {
            // A newer ask superseded this one while the mint was in
            // flight. The freshly minted token is still good and worth
            // keeping for the NEXT ask, so it is stored; this stale
            // request stops here rather than starting a run under an
            // abandoned question (the same A-02 discipline below).
            setGuestToken(minted.guest_token);
            persistGuestToken(minted.guest_token);
            return;
          }
          runToken = minted.guest_token;
          setGuestToken(minted.guest_token);
          persistGuestToken(minted.guest_token);
          setAllowance({
            kind: "guest",
            used: minted.used,
            total: minted.total,
            counted: true,
          });
        }

        const response = await createRun(
          { text: question, audience_depth: chosenDepth, session_id: sessionId },
          runToken,
        );
        // A-02: a newer ask started while this one was in flight. Adopting this
        // run now would attach its answer to the newer question's heading.
        if (seq !== askSeq.current) return;
        setRunId(response.run_id);
        // T-4.5-10: adopt the server's persona. Set every run rather than
        // only the first, so a sign-in that changes the identity behind the
        // session is reflected without a reload.
        setPersona({
          name: response.persona_name,
          about: response.persona_about ?? null,
          wikipedia: response.persona_wikipedia ?? null,
        });
        // T-4.13-03: give this rail item the trace id its `interactions`
        // row will carry, so `mergeServerHistory` can recognise the SAME
        // run when the server later echoes it back, rather than matching
        // on question text (see that function's own docstring for why
        // text is the wrong key). Matched by `question`, the same way the
        // meta-on-landing effect above matches this run's item: the
        // in-session dedup a few lines up already guarantees at most one
        // item exists per question text, so this cannot mis-tag a sibling.
        setHistory((current) =>
          current.map((item) =>
            item.question === question && item.traceId === undefined
              ? { ...item, traceId: response.run_id }
              : item,
          ),
        );

        if (!signedIn) {
          // T-4.10-08: the dots must read the SERVER's own count, never a
          // client guess (the exact fabrication class F-4.8-J-01 was filed
          // for, one layer up). Best-effort: a failed refresh here leaves
          // the previous, still-true count on screen rather than inventing
          // a new one, per production-standards' graceful-degradation gate.
          getAllowance(runToken)
            .then((fresh) => setAllowance(fresh))
            .catch(() => undefined);
        }
      } catch (error) {
        if (seq !== askSeq.current) return;
        if (
          error instanceof ApiError &&
          error.status === 429 &&
          (error.reason === "anon_daily_cap_reached" ||
            error.reason === "anon_source_daily_cap_reached")
        ) {
          // Not the wall: both reasons are transient, clearing at UTC
          // midnight, and neither is this identity's own allowance being
          // spent, so a permanent sign-in prompt would overstate what
          // happened. The answer screen's failure banner, the same surface
          // every other dispatch failure below already uses, gets the
          // sentence the server already wrote for this exact reason.
          setDispatchError(DAILY_CAP_COPY[error.reason]);
          setSearchView({ name: "answer", question });
          return;
        }
        if (error instanceof ApiError && error.status === 401 && !signedIn) {
          // The guest token this tab was holding did not work: revoked when
          // another tab logged in, or past its 7-day TTL. Dropped so the same
          // 401 does not repeat; the next ask mints a fresh identity, and the
          // banner below tells the visitor to send the question again.
          setGuestToken(null);
          clearPersistedGuestToken();
          setDispatchError("Your guest session had ended. Send the question again to continue.");
          setSearchView({ name: "answer", question });
          return;
        }
        // F-4.8-J-12. This previously swallowed the exception and dropped the
        // user on an empty answer screen with no explanation. An error message
        // must say what happened; silence is the one unacceptable option.
        setDispatchError(
          error instanceof Error && error.message
            ? error.message
            : "The question could not be sent. Check your connection and try again.",
        );
        setSearchView({ name: "answer", question });
      }
    },
    // `view` and `searchView` joined the list when T-4.16-02 made `ask`
    // archive the turn on screen: a stale closure here would file away the
    // PREVIOUS conversation's last turn under this one's question.
    [signedIn, token, guestToken, sessionId, view, searchView],
  );

  /**
   * Abort the run in flight, wherever its Stop button is rendered.
   *
   * Extracted for UI fix set 7 (R22): there are now two places a Stop can be
   * pressed, the full-screen run and the inline continuation, and two copies
   * of this would be two chances for one of them to stop the browser without
   * stopping the server.
   *
   * A-10. `deriveStopEnabled` only goes false on a terminal event, and
   * stopping ABORTS the stream so no terminal event ever arrives: Stop
   * stayed enabled forever and the stepper kept asserting live work.
   * `StopButton` solved this with local `hasStopped` state; reusing its
   * derive helper without its state reused half the answer. This latches
   * the other half.
   */
  const stopCurrentRun = () => {
    setStopped(true);
    stop();
    if (runId && authToken) void stopRun(runId, authToken).catch(() => undefined);
  };

  /**
   * T-4.16-02: a new search is a new conversation, so the thread does not
   * carry across. The follow-up field is the control that continues one;
   * this is the control that does not, and they sit on the same screen.
   */
  const startNewSearch = () => {
    setThread([]);
    setSearchView({ name: "home" });
  };

  const body = () => {
    if (screen === "integrations") return <IntegrationsScreen />;
    if (screen === "about")
      return (
        <AboutScreen
          onNavigateToSearch={() => {
            setScreen("search");
            setSearchView({ name: "home" });
          }}
          onNavigateToArchitecture={() => setScreen("architecture")}
        />
      );
    // The two info pages cross-link to each other through the same screen
    // switch the nav uses, so nothing reloads and the in-memory access token
    // survives the move.
    if (screen === "architecture")
      return <ArchitectureScreen onNavigateToAbout={() => setScreen("about")} />;

    switch (searchView.name) {
      case "signin":
        return (
          <AuthGate
            guestToken={guestToken}
            onAuthenticated={(next: string, email: string, refresh: string) => {
              setToken(next);
              setAccountEmail(email);
              // Fix set 4 (R46, decision U8): the refresh token
              // `POST /auth/login` returned is persisted here, and it is the
              // only thing that lets the next load restore this session. The
              // access token stays in memory.
              persistRefreshToken(refresh);
              // Same release as `clearAccountState`, for the same reason
              // stated there: no effect today, and it keeps the flag
              // meaning "no restore has been attempted for the session this
              // tab is now holding" rather than something older.
              restoreStarted.current = false;
              setSearchView({ name: "home" });
              // T-4.10-06: a guest session held at sign-in is migrated and
              // revoked server-side in the same request (the backend's
              // `_migrate_guest_session`), so the token this tab was
              // holding can never spend another run and must be dropped.
              // After Log out, the next signed-out question mints a fresh one.
              setGuestToken(null);
              clearPersistedGuestToken();
              setAllowance(null);
              getAllowance(next)
                .then((fetched) => setAllowance(fetched))
                .catch(() => undefined);
            }}
          />
        );
      case "run":
        return (
          <RunScreen
            question={searchView.question}
            activeStep={stopped ? null : step}
            // Null once the run is no longer in flight, which is what stops
            // the counter and the pulse. A landed or stopped run that kept
            // counting would assert work that is not happening.
            startedAt={stopped || view.landed ? null : runStartedAt}
            reachedSteps={view.reachedSteps}
            toolCalls={view.toolCalls}
            steps={view.steps}
            personaName={persona?.name ?? null}
            personaAbout={persona?.about ?? null}
            personaWikipedia={persona?.wikipedia ?? null}
            stopEnabled={view.stopEnabled && !stopped}
            refusal={view.refusal}
            capMessage={view.capMessage}
            failure={streamError}
            stopped={stopped}
            onRunAgain={() => {
              // Decision U7: "Run again" re-asks the exact same question at
              // the depth it was last asked, rather than sending the reader
              // back to the landing screen first. `ask` already flips
              // `stopped` back to false and switches the view to "run" on
              // the next event, the same as a fresh ask.
              void ask(searchView.question, depth);
            }}
            onStop={stopCurrentRun}
            onNewSearch={startNewSearch}
          />
        );
      case "answer": {
        // UI fix set 7 (R22). The SAME component the full-screen run
        // renders, given the SAME values, so the inline wait and the
        // full-screen wait cannot look or behave differently. Built here
        // rather than inside `AnswerScreen` because every value it needs is
        // this component's state and the answer screen has no business
        // deriving a run's progress.
        //
        // Neither `question` nor `onNewSearch` is passed: `AnswerScreen`'s
        // own header already renders the question as the page's `h1` and
        // carries New search beside it, and a second copy of either would
        // be a duplicate heading and a duplicate control on one screen.
        const inlineProgress = inlineRunActive ? (
          <RunProgress
            activeStep={stopped ? null : step}
            startedAt={stopped ? null : runStartedAt}
            reachedSteps={view.reachedSteps}
            toolCalls={view.toolCalls}
            steps={view.steps}
            personaName={persona?.name ?? null}
            personaAbout={persona?.about ?? null}
            personaWikipedia={persona?.wikipedia ?? null}
            stopEnabled={view.stopEnabled && !stopped}
            refusal={view.refusal}
            capMessage={view.capMessage}
            failure={streamError}
            stopped={stopped}
            showNewSearch={false}
            onStop={stopCurrentRun}
            onRunAgain={() => {
              // `true` for the third argument, unlike the full-screen run's
              // Run again: re-running a stopped follow-up must stay in the
              // conversation rather than throwing the thread away. Nothing
              // is archived by it, because `ask` only archives a run that
              // LANDED and a stopped one never did.
              void ask(searchView.question, depth, true);
            }}
          />
        ) : null;
        return (
          <AnswerScreen
            question={searchView.question}
            previousTurns={thread}
            progress={inlineProgress}
            claims={view.claims}
            sources={view.sources}
            trust={view.trust}
            meta={view.meta}
            outcome={view.outcome}
            outcomeTone={view.outcomeTone}
            elapsedMs={view.elapsedMs}
            steps={view.steps}
            // F-4.8-J-02. A refusal or a fatal error arrives with a `done` or
            // `error` event, which lands the user here immediately. Passing
            // these only to RunScreen meant the entire user-facing output of
            // build phase 3.0's guardrail was unreachable: a refused question
            // rendered as a blank page.
            refusal={view.refusal}
            // R13, R14 and R44. The label and the NCBI address travel as
            // their own fields now, so the refusal reads as a calm labelled
            // block with a real link rather than an amber alarm holding an
            // address nobody can click.
            refusalLabel={view.refusalLabel}
            refusalLink={view.refusalLink}
            /*
             * `view.failure` BEFORE `streamError` (F-4.9-A-01). The other
             * order put the raw stream error ahead of the curated string, so
             * on the fatal path the curated one was unreachable dead code.
             */
            failure={dispatchError ?? view.failure ?? streamError}
            capMessage={view.capMessage}
            systemNotes={view.systemNotes}
            /*
             * F-4.6-08. `AnswerScreen` builds `FeedbackSurface` itself
             * (T-4.6-09) and needs the real POST target and bearer token to
             * do it, the same values `useAgentRun` and the Stop action
             * already read below. `runId` is `App`'s own state and `null`
             * until a run has actually landed one, which is exactly the
             * case `FeedbackSurface` degrades visibly for rather than
             * posting to a malformed URL, so passing it through unguarded
             * here is correct, not a gap to work around.
             */
            runId={runId}
            authToken={authToken}
            followUp={
              <FollowUp
                hints={FOLLOW_UP_HINTS}
                // T-6.2-08. Accepting the offer goes through the SAME `ask`
                // as anything typed, so it continues the thread rather than
                // starting over. That was the product owner's condition on
                // this feature: an offer the system makes and then forgets
                // making is worse than no offer.
                nextStep={view.nextStep}
                /*
                 * UI fix set 7 (R21). What the offer SAYS and what accepting
                 * it ASKS are two different strings, and conflating them is
                 * the defect: "Yes, go deeper" used to send the offer's own
                 * yes/no wording ("Would you like me to go through the 3
                 * further disease records found for this question?") to the
                 * agent as if it were a question about biology. The backend
                 * now sends the searchable question alongside the offer;
                 * absent, `FollowUp` falls back to the offer text, which is
                 * exactly today's behaviour and what an older backend gives.
                 */
                nextStepQuery={view.nextStepQuery}
                onAsk={(next) => void ask(next, depth, true)}
              />
            }
            flaggedSources={flagged}
            onFlagSource={(n) =>
              setFlagged((current) =>
                current.includes(n) ? current.filter((x) => x !== n) : [...current, n],
              )
            }
            onNewSearch={startNewSearch}
          />
        );
      }
      default:
        return (
          <HomeScreen
            onSubmit={ask}
            /*
             * T-4.5-08, Section 14.5. `depth` is App's state, seeded from
             * `GET /auth/me`, so the control a returning caller sees starts
             * where they left it. Until this prop existed, `HomeScreen` owned
             * its own depth and App's seeded value reached only the follow-up
             * ask, never the landing control or the first question.
             */
            depth={depth}
            onDepthChange={setDepth}
            // The tour's three touch points on this screen. The invite shows
            // until it is dismissed or the tour finishes, and never while
            // the tour itself is up; the footer link is always there; the
            // prefill is step 7's question, and only while step 7 shows.
            tourInvite={
              !tourSeen && !tourOpen ? (
                <TourInvite onStart={startTour} onDismiss={dismissTourInvite} />
              ) : null
            }
            onTakeTour={startTour}
            prefillQuestion={tourOpen && tourStep === RUN_STEP_INDEX ? TOUR_QUESTION : null}
            /*
             * Set 1 (R2, 2026-09-12): no guest dots. There is no per-guest
             * allowance to show. When the anonymous daily cap is reached,
             * the home footer says so in words; otherwise nothing renders.
             */
            footer={
              !signedIn &&
              allowance?.kind === "guest" &&
              (allowance.blocked_reason === "anon_daily_cap_reached" ||
                allowance.blocked_reason === "anon_source_daily_cap_reached") ? (
                <Box component="span" sx={{ fontSize: 12.5, color: designTokens.inkMuted }}>
                  {DAILY_CAP_COPY[allowance.blocked_reason]}
                </Box>
              ) : null
            }
          />
        );
    }
  };

  /*
   * Set 2, R10 (2026-09-12): a short fade between home, progress, answer and
   * the other pages, instead of a hard cut. Keyed on the view, so it plays
   * once per screen change and never on a re-render within a screen. Off for
   * anyone who asked for reduced motion.
   */
  const fadedBody = () => (
    <Box
      key={`${screen}:${searchView.name}`}
      sx={{
        flex: 1,
        display: "flex",
        flexDirection: "column",
        "@keyframes screenFadeIn": {
          from: { opacity: 0, transform: "translateY(4px)" },
          to: { opacity: 1, transform: "none" },
        },
        animation: "screenFadeIn .2s ease-out",
        "@media (prefers-reduced-motion: reduce)": { animation: "none" },
      }}
    >
      {body()}
    </Box>
  );

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      {/*
        F-4.8-A-08 and F-4.8-R-06. `inert` on the whole shell, not just a
        keydown handler on the dialog.

        A Tab-key trap only intercepts Tab. It does nothing about programmatic
        focus, about a browser-chrome round trip (Ctrl+L then Shift+Tab back
        into the page), or about a screen reader's virtual cursor, none of
        which emit a Tab keydown. The re-review demonstrated the first of those
        reaching the question field with the gate still up.

        `inert` removes the subtree from focus, from hit-testing and from the
        accessibility tree at once, which also makes the dialog's own
        `aria-modal="true"` true rather than a claim.
      */}
      <div inert={!accepted}>
      <AppShell
        current={screen}
        onNavigate={(next) => {
          setScreen(next);
          if (next === "search") setSearchView({ name: "home" });
        }}
        personaName={persona?.name ?? null}
        personaAbout={persona?.about ?? null}
        personaWikipedia={persona?.wikipedia ?? null}
        signedIn={signedIn}
        hideAuthAction={searchView.name === "signin" && screen === "search"}
        // T-4.9-10: the account menu names the account, so the bar needs the
        // email too, not only the rail's footer.
        accountEmail={accountEmail ?? undefined}
        accountLimitCopy={dailyLimitLine}
        showRailToggle={railAvailable}
        railOpen={railOpen}
        onToggleRail={() => setRailOpen((open) => !open)}
        onSignIn={() => {
          setScreen("search");
          setSearchView({ name: "signin" });
        }}
        onSignOut={() => {
          // Fix set 4 (R46, decision U8): revoke the refresh token this
          // browser is holding, so a value left in storage by any earlier
          // write cannot be exchanged for a session after the person has
          // left. `POST /auth/logout` revokes exactly the token it is given
          // (`router.py`'s `logout`).
          //
          // FIRE AND FORGET, deliberately. The local state below is cleared
          // whether or not the request lands: a person who presses Log out
          // on a flaky connection must end up signed out on this machine,
          // never left looking signed in while a revocation retries. A 401
          // here means the token was already dead, which is the end state
          // this call was asking for anyway. Read BEFORE `clearAccountState`,
          // which clears the stored value.
          const storedRefresh = loadPersistedRefreshToken();
          if (storedRefresh !== null) {
            void logoutSession(storedRefresh).catch(() => undefined);
          }
          // `stop()` stays here rather than moving into `clearAccountState`:
          // it comes from `useAgentRun`, which is initialised after that
          // function is defined. Aborting immediately rather than at the next
          // render is the only thing this adds, since clearing `runId` and
          // `token` aborts the stream regardless.
          stop();
          // Every piece of session-scoped state this handler used to clear
          // inline now lives in `clearAccountState` above, unchanged, so the
          // keep-alive effect reaches the identical end state when a session
          // dies on its own. The reasoning for each line, F-4.8-A-11 through
          // A-13, R-02, R-11, P-03 and set 1's R6, moved with the code.
          clearAccountState();
        }}
      >
        {screen === "search" ? (
          // `flex: 1` rather than `minHeight: "100%"`: a percentage height
          // resolves against a parent with a definite height, and `<main>` has
          // none, so the rail stopped where the content ended instead of
          // reaching the footer as the prototype's does.
          <Box sx={{ display: "flex", alignItems: "stretch", flex: 1, minHeight: 0 }}>
            {/*
              THREE outcomes, not two (F-4.8-P-04): no rail, the collapsed
              strip, or the rail. This was a two-way ternary whose else branch
              rendered the rail unconditionally, so a signed-out visitor got a
              full rail with its empty state, which the prototype does not have.

              It was invisible while `HistoryRail` returned null on an empty
              list. Removing that guard, correctly, to match the prototype's
              own empty state, unmasked the defect the guard had been hiding.
              Found by screenshotting the app beside the prototype; every
              assertion in this repository passed throughout, because they
              checked the toggle's absence and never the rail's.
            */}
            {!railAvailable ? null : !railOpen ? (
              <CollapsedRail count={history.length} onExpand={() => setRailOpen(true)} />
            ) : (
            <HistoryRail
              items={history}
              activeId={
                searchView.name === "answer" || searchView.name === "run"
                  ? history.find((item) => item.question === searchView.question)?.id ?? null
                  : null
              }
              // F-4.8-J-08. This previously switched the heading to a past
              // question while leaving the CURRENT run's answer on screen,
              // which is the same fabrication shape as J-03 by another route.
              // Re-asking is the only truthful option available: this session's
              // earlier runs are not retained, and retaining them is build
              // phase 4.5's work, not something to fake here.
              onOpen={(id) => {
                const item = history.find((entry) => entry.id === id);
                if (item) void ask(item.question, depth);
              }}
              onCollapse={() => setRailOpen(false)}
              onNewSearch={() => {
              // T-4.16-02: a new search is a new conversation, so the
              // thread does not carry across. The follow-up field is the
              // control that continues one; this is the control that does
              // not, and they sit on the same screen.
              setThread([]);
              setSearchView({ name: "home" });
            }}
              accountEmail={accountEmail ?? undefined}
              searchLimitLabel={capitalizeFirst(dailyLimitLine)}
            />
            )}
            {/*
              A flex COLUMN, not just a flex item. `alignItems: "stretch"` on
              the row gives this box the full height, but a screen inside it
              can only claim that height if this box lays its children out.
            */}
            <Box sx={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column" }}>
              {fadedBody()}
            </Box>
          </Box>
        ) : (
          fadedBody()
        )}
      </AppShell>
      </div>
      {/* Rendered OUTSIDE the inert subtree, or it would disable itself. */}
      {!accepted ? <DisclaimerModal onAccept={() => setAccepted(true)} /> : null}
      {/*
        Also outside the inert subtree, and only once the disclaimer is
        accepted: the tour can only be opened from the home screen, which is
        inert until then, so this is belt and braces rather than a gate.
        "Run it for me" goes through the SAME `ask` as the arrow button and
        the seed chips, at the depth the visitor has chosen.
      */}
      {accepted ? (
        <OnboardingTour
          open={tourOpen}
          step={tourStep}
          onStepChange={setTourStep}
          onClose={endTour}
          runState={tourRunState}
          outcome={tourOutcome}
          onRunForMe={() => void ask(TOUR_QUESTION, depth)}
        />
      ) : null}
    </ThemeProvider>
  );
}

export default App;
