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

import { useCallback, useEffect, useMemo, useState } from "react";
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
import { FollowUp, HistoryRail } from "./components/answer/FollowUp";
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

  const sessionId = useMemo(
    () =>
      typeof crypto !== "undefined" && "randomUUID" in crypto
        ? crypto.randomUUID()
        : `session-${Date.now()}`,
    [],
  );

  // Section 14.2, presentation only. Stubbed; wired by build phase 4.5.
  const persona = useMemo(() => drawPersona(0), []);

  const signedIn = token !== null;

  const { events, stop } = useAgentRun(runId, token);
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
    if (view.landed && searchView.name === "run") {
      setSearchView({ name: "answer", question: searchView.question });
    }
  }, [view.landed, searchView]);

  const ask = useCallback(
    async (question: string, depth: AudienceDepth) => {
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
      setRunId(null);
      setSearchView({ name: "run", question });

      try {
        const response = await createRun(
          { text: question, audience_depth: depth, session_id: sessionId },
          token,
        );
        setRunId(response.run_id);
      } catch (error) {
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
            activeStep={step}
            reachedSteps={view.reachedSteps}
            toolCalls={view.toolCalls}
            personaName={persona}
            stopEnabled={view.stopEnabled}
            refusal={view.refusal}
            capMessage={view.capMessage}
            onStop={() => {
              // Stay on the run. Navigating home here discarded everything the
              // run had already streamed, which punishes the user for stopping
              // and loses partial results they may have wanted. The original
              // phase 1.2 behaviour kept the page; the Stop button disables
              // itself once the run is terminal, and "New search" is right
              // there when they want to move on.
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
            failure={dispatchError ?? view.failure}
            capMessage={view.capMessage}
            feedback={<FeedbackSurface key={searchView.question} />}
            followUp={
              <FollowUp
                hints={FOLLOW_UP_HINTS}
                onAsk={(next) => void ask(next, "researcher")}
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
            footer={
              signedIn || used === 0 ? null : (
                <GuestAllowance used={used} total={FREE_SEARCHES} />
              )
            }
          />
        );
    }
  };

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <AppShell
        current={screen}
        onNavigate={(next) => {
          setScreen(next);
          if (next === "search") setSearchView({ name: "home" });
        }}
        personaName={persona}
        signedIn={signedIn}
        hideAuthAction={searchView.name === "signin" && screen === "search"}
        onSignIn={() => {
          setScreen("search");
          setSearchView({ name: "signin" });
        }}
        onSignOut={() => setToken(null)}
      >
        {!accepted ? <DisclaimerModal onAccept={() => setAccepted(true)} /> : null}
        {screen === "search" ? (
          <Box sx={{ display: "flex", alignItems: "stretch", minHeight: "100%" }}>
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
                if (item) void ask(item.question, "researcher");
              }}
            />
            <Box sx={{ flex: 1, minWidth: 0 }}>{body()}</Box>
          </Box>
        ) : (
          body()
        )}
      </AppShell>
    </ThemeProvider>
  );
}

export default App;
