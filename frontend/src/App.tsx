/**
 * The assembled app, build phase 4.8, ticket T-4.8-12.
 *
 * REWRITTEN in the fix round after judge findings F-4.8-J-01, J-02, J-03,
 * J-08, J-12 and J-17. Four of those were critical and three were user-facing
 * trust defects, so the relevant reasoning is recorded here rather than in a
 * commit message nobody reads twice.
 *
 * THE RULE THIS FILE NOW FOLLOWS: nothing that looks like an answer is ever
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
 * So an anonymous visitor now meets the sign-in wall the moment they ask.
 * The cost is real and is stated plainly for the product owner: the approved
 * five-free-searches journey cannot be delivered until an anonymous path to
 * the backend exists, which is build phase 6.0's. Showing the wall is honest;
 * showing a fabricated citation is not. Reverting this decision means giving
 * anonymous callers a real backend route, not restoring the demo data.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Box, CssBaseline, ThemeProvider } from "@mui/material";

import { theme } from "./theme";
import { createRun, stopRun } from "./lib/api";
import { useAgentRun } from "./hooks/useAgentRun";
import { useRunView, EMPTY_RUN_VIEW } from "./hooks/useRunView";
import { AuthGate } from "./components/auth/AuthGate";
import { AppShell } from "./components/shell/AppShell";
import type { ScreenName } from "./components/shell/AppShell";
import { drawPersona } from "./components/shell/PersonaChip";
import { HomeScreen } from "./components/screens/HomeScreen";
import { RunScreen } from "./components/screens/RunScreen";
import type { StepName } from "./components/screens/RunScreen";
import { AnswerScreen } from "./components/screens/AnswerScreen";
import { AboutScreen, DocsScreen, IntegrationsScreen } from "./components/screens/InfoScreens";
import { GuestAllowance, SignInWall } from "./components/guest/GuestAllowance";
import { FeedbackSurface } from "./components/feedback/FeedbackSurface";
import { CollapsedRail, FollowUp, HistoryRail } from "./components/answer/FollowUp";
import { DisclaimerModal, hasAcceptedDisclaimer } from "./components/shell/DisclaimerModal";
import type { AudienceDepth } from "./components/controls/DepthControl";

type SearchView =
  | { name: "home" }
  | { name: "run"; question: string }
  | { name: "answer"; question: string }
  | { name: "wall" }
  | { name: "signin" };

/** The allowance the approved design calls for. Not yet deliverable: see the
 *  file docstring. Kept so the counter and soft prompt stay designed and
 *  reachable the moment build phase 6.0 provides an anonymous backend path. */
const FREE_SEARCHES = 5;

/** Canned follow-up hints. Stubbed; build phase 4.5 derives these for real.
 *  These are QUESTIONS, never answer content, which is why they are allowed. */
const FOLLOW_UP_HINTS = [
  "What variants cause it?",
  "Which trials are recruiting?",
  "What does the literature add?",
];

export function App() {
  const [screen, setScreen] = useState<ScreenName>("search");
  const [searchView, setSearchView] = useState<SearchView>({ name: "home" });
  const [used, setUsed] = useState(0);
  const [token, setToken] = useState<string | null>(null);
  const [runId, setRunId] = useState<string | null>(null);
  const [accepted, setAccepted] = useState(hasAcceptedDisclaimer);
  const [history, setHistory] = useState<{ id: string; question: string }[]>([]);
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

  // Section 14.2, presentation only. Stubbed; wired by build phase 4.5.
  const persona = useMemo(() => drawPersona(0), []);

  const signedIn = token !== null;

  /**
   * Whether the rail, its strip and its toggle exist at all (F-4.8-P-03).
   *
   * The prototype's `avail = st.loggedIn && onSearch`, plus this app's own
   * existing rule that an empty rail renders nothing. Computed once and used by
   * all three controls, so the toggle can never be offered for a rail that is
   * not there, and the strip can never appear where the rail would not have.
   */
  const railAvailable = signedIn && screen === "search" && history.length > 0;

  // `status` and `error` were both discarded here (F-4.8-A-09). If the event
  // stream failed to open at all, a 500, a malformed frame, or, realistically,
  // a 401 from a token that expired between createRun and openEventStream, the
  // run screen sat with five pending steps and Stop disabled, silently, for
  // ever. F-4.8-J-12 closed exactly this hole for createRun and left the
  // identical one a single call downstream.
  const { events, status, error: streamError, stop } = useAgentRun(runId, token);
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

  const ask = useCallback(
    async (question: string, chosenDepth: AudienceDepth) => {
      setDepth(chosenDepth);
      // F-4.8-J-01. An anonymous visitor has no token and therefore no run.
      // There is nothing truthful to show them, so they are asked to sign in
      // rather than shown something invented.
      if (!signedIn) {
        setSearchView({ name: "wall" });
        return;
      }

      setUsed((n) => n + 1);
      setFlagged([]);
      setDispatchError(null);
      setHistory((current) =>
        current.some((item) => item.question === question)
          ? current
          : [{ id: `${current.length}`, question }, ...current],
      );
      const seq = ++askSeq.current;
      setRunId(null);
      setStopped(false);
      setSearchView({ name: "run", question });

      try {
        const response = await createRun(
          { text: question, audience_depth: chosenDepth, session_id: sessionId },
          token,
        );
        // A-02: a newer ask started while this one was in flight. Adopting this
        // run now would attach its answer to the newer question's heading.
        if (seq !== askSeq.current) return;
        setRunId(response.run_id);
      } catch (error) {
        if (seq !== askSeq.current) return;
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
    [signedIn, token, sessionId],
  );

  const body = () => {
    if (screen === "integrations") return <IntegrationsScreen />;
    if (screen === "docs") return <DocsScreen />;
    if (screen === "about") return <AboutScreen />;

    switch (searchView.name) {
      case "signin":
        return (
          <AuthGate
            onAuthenticated={(next: string) => {
              setToken(next);
              setSearchView({ name: "home" });
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
              if (runId && token) void stopRun(runId, token).catch(() => undefined);
            }}
            onNewSearch={() => setSearchView({ name: "home" })}
          />
        );
      case "answer":
        return (
          <AnswerScreen
            question={searchView.question}
            claims={view.claims}
            sources={view.sources}
            trust={view.trust}
            meta={view.meta}
            // F-4.8-J-02. A refusal or a fatal error arrives with a `done` or
            // `error` event, which lands the user here immediately. Passing
            // these only to RunScreen meant the entire user-facing output of
            // build phase 3.0's guardrail was unreachable: a refused question
            // rendered as a blank page.
            refusal={view.refusal}
            failure={dispatchError ?? streamError ?? view.failure}
            capMessage={view.capMessage}
            feedback={<FeedbackSurface key={searchView.question} />}
            followUp={
              <FollowUp
                hints={FOLLOW_UP_HINTS}
                onAsk={(next) => void ask(next, depth)}
              />
            }
            flaggedSources={flagged}
            onFlagSource={(n) =>
              setFlagged((current) =>
                current.includes(n) ? current.filter((x) => x !== n) : [...current, n],
              )
            }
            onNewSearch={() => setSearchView({ name: "home" })}
          />
        );
      case "wall":
        return <SignInWall onSignIn={() => setSearchView({ name: "signin" })} />;
      default:
        return (
          <HomeScreen
            onSubmit={ask}
            // F-4.8-A-21. This counted the SIGNED-IN user's searches and then
            // showed that count to the next anonymous visitor after sign-out,
            // and the very next ask contradicted it with "you have used your
            // free searches". `used` is now reset on sign-out, and an anonymous
            // visitor cannot run at all, so the honest count is always zero
            // until build phase 6.0 provides an anonymous path.
            footer={signedIn || used === 0 ? null : <GuestAllowance used={used} total={FREE_SEARCHES} />}
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
          setRunId(null);
          setStopped(false);
          setHistory([]);
          setFlagged([]);
          setDispatchError(null);
          setUsed(0);
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
          <Box sx={{ display: "flex", alignItems: "stretch", minHeight: "100%" }}>
            {railAvailable && !railOpen ? (
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
            />
            )}
            <Box sx={{ flex: 1, minWidth: 0 }}>{body()}</Box>
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
