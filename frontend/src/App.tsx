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

import { theme } from "./theme";
import {
  ApiError,
  createRun,
  fetchMe,
  fetchPersona,
  getAllowance,
  mintGuest,
  stopRun,
} from "./lib/api";
import type { AllowanceResponse } from "./lib/api";
import {
  capitalizeFirst,
  clearPersistedGuestToken,
  dailyLimitPhrase,
  guestSessionWasMigrated,
  loadPersistedGuestToken,
  markGuestSessionMigrated,
  persistGuestToken,
} from "./lib/guestSession";
import { useAgentRun } from "./hooks/useAgentRun";
import { useRunView, EMPTY_RUN_VIEW } from "./hooks/useRunView";
import { AuthGate } from "./components/auth/AuthGate";
import { AppShell } from "./components/shell/AppShell";
import { useScreenRoute } from "./lib/routing";
import { HomeScreen } from "./components/screens/HomeScreen";
import { RunScreen } from "./components/screens/RunScreen";
import type { StepName } from "./components/screens/RunScreen";
import { AnswerScreen } from "./components/screens/AnswerScreen";
import type { PreviousTurn } from "./components/screens/AnswerScreen";
import { AboutScreen, DocsScreen, IntegrationsScreen } from "./components/screens/InfoScreens";
import { GuestAllowance, SignInWall } from "./components/guest/GuestAllowance";
import type { SignInWallReason } from "./components/guest/GuestAllowance";
import { CollapsedRail, FollowUp, HistoryRail } from "./components/answer/FollowUp";
import { DisclaimerModal, hasAcceptedDisclaimer } from "./components/shell/DisclaimerModal";
import type { AudienceDepth } from "./components/controls/DepthControl";

type SearchView =
  | { name: "home" }
  | { name: "run"; question: string }
  | { name: "answer"; question: string }
  // F-4.10-R-02: the wall has three triggers and they are not the same
  // message. Carrying the reason in the view rather than deriving it at
  // render time is what makes each sentence answerable to the state that
  // produced it.
  | { name: "wall"; reason: SignInWallReason }
  | { name: "signin" };

/** Canned follow-up hints. Stubbed; build phase 4.5 derives these for real.
 *  These are QUESTIONS, never answer content, which is why they are allowed. */
const FOLLOW_UP_HINTS = [
  "What variants cause it?",
  "Which trials are recruiting?",
  "What does the literature add?",
];

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
  const [guestMigrated, setGuestMigrated] = useState<boolean>(guestSessionWasMigrated);
  /**
   * The caller's own search allowance, read ONLY from `GET /v1/allowance`
   * (or the equivalent fields on a fresh `POST /auth/guest` response).
   * Never computed or incremented client-side: the client-side counter
   * this field replaces was exactly the fabrication class build phase
   * 4.8's judge round filed. `null` before any fetch has resolved.
   */
  const [allowance, setAllowance] = useState<AllowanceResponse | null>(null);
  const [token, setToken] = useState<string | null>(null);
  /** The signed-in account, named in the rail's footer (the prototype's `.rfoot`). */
  const [accountEmail, setAccountEmail] = useState<string | null>(null);
  const [runId, setRunId] = useState<string | null>(null);
  const [accepted, setAccepted] = useState(hasAcceptedDisclaimer);
  const [history, setHistory] = useState<{ id: string; question: string; meta?: string }[]>([]);
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
  /** True while a stopped run should stay stopped (F-4.8-A-10). */
  const [stopped, setStopped] = useState(false);
  /**
   * Whether the stored-searches rail is open (F-4.8-P-03).
   *
   * Open by default, matching the prototype's `railOpen:true`. Held here rather
   * than inside `HistoryRail`, because the collapsed state must survive the
   * rail unmounting: the app bar's toggle and the collapsed strip both need it,
   * and a collapse the user chose must outlive the next question.
   */
  const [railOpen, setRailOpen] = useState(true);

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
  const [persona, setPersona] = useState<string | null>(null);

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
      .then((result) => setPersona(result.persona_name))
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
  const step: StepName | null = view.activeStep;

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
    setHistory((current) =>
      current.map((item) =>
        item.question === question && item.meta !== view.meta
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
      // F-4.10-A-05. This browser already turned its guest allowance into an
      // account, and the server revoked that guest session when it did.
      // Minting a fresh identity here is the hole: it is how sign in, sign
      // out, ask five more, repeat handed out unlimited free allowances with
      // nobody clearing anything. Checked BEFORE any state is touched, so the
      // question never reaches the history list or the run screen for a run
      // that is not going to start.
      //
      // The wall rather than an error, because the wall is the one thing the
      // visitor can act on: signing in works immediately and is exactly what
      // it offers. A dead-credential 401 would be a message with no next
      // step in it.
      if (!signedIn && guestToken === null && guestMigrated) {
        // `reason: "migrated"`, and this is the case F-4.10-R-02 named
        // first. Nothing here says how many searches were used, because
        // nothing here knows: this browser reaches the wall with anywhere
        // between zero and five spent, including a visitor who created an
        // account without ever asking a question. "You have used your free
        // searches" was false exactly when it was shown.
        setSearchView({ name: "wall", reason: "migrated" });
        return;
      }
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
      setHistory((current) =>
        current.some((item) => item.question === question)
          ? current
          : [{ id: `${current.length}`, question }, ...current],
      );
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
      setSearchView({ name: "run", question });

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
        setPersona(response.persona_name);

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
        if (error instanceof ApiError && error.status === 403 && error.reason === "guest_allowance_exhausted") {
          // Design decision 5 (`tracker/phase_4.10.md`): the wall appears
          // ONLY on an exact server refusal, never on a client prediction
          // and never on the concurrent-run cap's 429, which is a transient
          // "try again shortly" handled by the branch below.
          //
          // The one trigger the wall's original sentence was written for,
          // and the one it is still true on: five answers delivered, five
          // spent.
          setSearchView({ name: "wall", reason: "allowance_exhausted" });
          return;
        }
        if (error instanceof ApiError && error.status === 403 && error.reason === "guest_attempt_limit_reached") {
          // F-4.10-R-01's refusal. Also a 403 and also permanent for this
          // identity, so it is also the wall rather than a transient error,
          // but a DIFFERENT sentence: this visitor may have had every one of
          // their questions refused and received no answer at all, so
          // telling them they used their free searches would be false.
          setSearchView({ name: "wall", reason: "attempt_limit" });
          return;
        }
        if (error instanceof ApiError && error.status === 401 && !signedIn) {
          // The guest token this tab was holding did not work. It is dropped
          // either way, so the same 401 does not repeat forever, but WHY it
          // failed decides what happens next, and collapsing the two was the
          // second, independent path to a free allowance the adversary named
          // (F-4.10-A-05).
          setGuestToken(null);
          clearPersistedGuestToken();
          if (error.reason === "guest_session_revoked") {
            // The server revoked this session at migration, from this tab or
            // another one. That means the allowance was already converted
            // into an account, so the next ask must NOT mint a fresh identity
            // with five more searches. Remember it and show the wall, which
            // is the actionable surface: signing in works right now.
            markGuestSessionMigrated();
            setGuestMigrated(true);
            // The same state as the pre-flight check above, reached from the
            // server instead of from storage, so the same sentence
            // (F-4.10-R-02). `runs_used` is equally unknown here.
            setSearchView({ name: "wall", reason: "migrated" });
            return;
          }
          // Anything else, most realistically a guest token past its 7-day
          // TTL, is not about the allowance at all, and a returning visitor
          // must not be walled for it. The next ask mints a fresh identity,
          // which is the behaviour that was always correct for this case.
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
    [signedIn, token, guestToken, guestMigrated, sessionId, view, searchView],
  );

  const body = () => {
    if (screen === "integrations") return <IntegrationsScreen />;
    if (screen === "docs") return <DocsScreen />;
    if (screen === "about") return <AboutScreen />;

    switch (searchView.name) {
      case "signin":
        return (
          <AuthGate
            guestToken={guestToken}
            onAuthenticated={(next: string, email: string) => {
              setToken(next);
              setAccountEmail(email);
              setSearchView({ name: "home" });
              // T-4.10-06: a guest session held at sign-in is migrated and
              // revoked server-side in the same request (the backend's
              // `_migrate_guest_session`), so the token this tab was
              // holding can never spend another run and must be dropped.
              //
              // F-4.10-A-05 corrects what this used to do NEXT, which was
              // nothing: dropping the token also forgot that there had been
              // one, so the sign-out below minted a fresh identity with five
              // fresh searches, every cycle, forever. The credential goes and
              // the fact stays. Recorded only when a guest token was actually
              // held, since a visitor who signed in without ever asking
              // anonymously has migrated nothing and must not be walled for
              // it.
              if (guestToken !== null) {
                markGuestSessionMigrated();
                setGuestMigrated(true);
              }
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
            reachedSteps={view.reachedSteps}
            toolCalls={view.toolCalls}
            steps={view.steps}
            personaName={persona}
            stopEnabled={view.stopEnabled && !stopped}
            refusal={view.refusal}
            capMessage={view.capMessage}
            failure={streamError}
            onStop={() => {
              // A-10. `deriveStopEnabled` only goes false on a terminal event,
              // and stopping ABORTS the stream so no terminal event ever
              // arrives: Stop stayed enabled forever and the stepper kept
              // asserting live work. `StopButton` solved this with local
              // `hasStopped` state; reusing its derive helper without its state
              // reused half the answer. This latches the other half.
              setStopped(true);
              stop();
              if (runId && authToken) void stopRun(runId, authToken).catch(() => undefined);
            }}
            onNewSearch={() => {
              // T-4.16-02: a new search is a new conversation, so the
              // thread does not carry across. The follow-up field is the
              // control that continues one; this is the control that does
              // not, and they sit on the same screen.
              setThread([]);
              setSearchView({ name: "home" });
            }}
          />
        );
      case "answer":
        return (
          <AnswerScreen
            question={searchView.question}
            previousTurns={thread}
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
            /*
             * `view.failure` BEFORE `streamError` (F-4.9-A-01). The other
             * order put the raw stream error ahead of the curated string, so
             * on the fatal path the curated one was unreachable dead code.
             */
            failure={dispatchError ?? view.failure ?? streamError}
            capMessage={view.capMessage}
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
                onAsk={(next) => void ask(next, depth, true)}
              />
            }
            flaggedSources={flagged}
            onFlagSource={(n) =>
              setFlagged((current) =>
                current.includes(n) ? current.filter((x) => x !== n) : [...current, n],
              )
            }
            onNewSearch={() => {
              // T-4.16-02: a new search is a new conversation, so the
              // thread does not carry across. The follow-up field is the
              // control that continues one; this is the control that does
              // not, and they sit on the same screen.
              setThread([]);
              setSearchView({ name: "home" });
            }}
          />
        );
      case "wall":
        return (
          <SignInWall
            reason={searchView.reason}
            onSignIn={() => setSearchView({ name: "signin" })}
          />
        );
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
            /*
             * T-4.10-08. F-4.8-A-21 was about a CLIENT-SIDE counter that
             * leaked the signed-in user's count to the next anonymous
             * visitor after sign-out. There is no client-side count left to
             * leak: `allowance` is set to `null` on sign-out and sign-in
             * alike (see those handlers), and only ever repopulated from a
             * fresh `GET /v1/allowance` or `POST /auth/guest` response for
             * WHOEVER the caller currently is. The dots render only once a
             * real guest allowance has been fetched (after the first ask,
             * since minting is lazy); before that, or once signed in, the
             * footer is simply absent rather than showing a guessed count.
             */
            footer={
              !signedIn && allowance?.kind === "guest" ? (
                /*
                 * F-4.10-V-03. `blocked_reason` was on the wire and honest
                 * from the moment the server learned to send it, and
                 * nothing read it, so the dots kept promising a search the
                 * next request refused. Passed straight through rather than
                 * re-derived here: the server owns which bound fires first,
                 * and a second opinion computed in the client is how the
                 * reporting path and the enforcement path start disagreeing
                 * again (F-4.10-A-03).
                 */
                <GuestAllowance
                  used={allowance.used}
                  total={allowance.total}
                  blockedReason={allowance.blocked_reason ?? null}
                />
              ) : null
            }
          />
        );
    }
  };

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
        personaName={persona}
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
          // F-4.8-A-11, A-12 and A-13. Signing out previously left the previous
          // account's answer, source cards, trust pills and history rail on
          // screen, and the NEXT account inherited that history. Worse,
          // `runId` survived, so `useAgentRun` refired the old run's event
          // stream with the new account's bearer token, producing a 403 that
          // nothing surfaced. On a shared workstation that is a colleague's
          // research queries and results.
          //
          // Everything session-scoped is cleared here, in one place, so a new
          // sign-in starts from nothing.
          askSeq.current += 1;
          stop();
          setToken(null);
          setAccountEmail(null);
          setRunId(null);
          setStopped(false);
          setHistory([]);
          setFlagged([]);
          setDispatchError(null);
          // T-4.10-08: the allowance belonged to the account that just
          // signed out; the next caller (signed in or anonymous) gets its
          // own, fetched fresh, never a stale number inherited across the
          // sign-out.
          setAllowance(null);
          // F-4.10-A-05, product-owner decision 2026-08-15: the guest token
          // and the migrated marker are deliberately NOT cleared here, and
          // this is the one exception to this handler's "everything
          // session-scoped is cleared here, in one place" rule. A guest
          // identity is not scoped to an account session; it is scoped to
          // the browser, and it outlives signing in and out of an account
          // exactly as it outlives a reload. Clearing it unconditionally is
          // what made the accepted "clearing the token gives you five more"
          // tradeoff reachable without anyone clearing anything: sign in,
          // sign out, ask five more, repeat. A visitor who signs out returns
          // to the guest identity they already had, with whatever searches
          // remained, and a visitor whose identity was migrated returns to
          // the sign-in wall, which is the truthful answer for a session the
          // server revoked.
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
          setRailOpen(true);
          setSearchView({ name: "home" });
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
              {body()}
            </Box>
          </Box>
        ) : (
          body()
        )}
      </AppShell>
      </div>
      {/* Rendered OUTSIDE the inert subtree, or it would disable itself. */}
      {!accepted ? <DisclaimerModal onAccept={() => setAccepted(true)} /> : null}
    </ThemeProvider>
  );
}

export default App;
