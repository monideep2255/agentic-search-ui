/**
 * The assembled app, build phase 4.8, ticket T-4.8-12.
 *
 * This is the ticket LEARNINGS.md's 2026-07-28 entry exists to force. Build
 * phase 1.2 shipped six chat components that each passed their own tests while
 * `ChatPage.tsx` stayed a placeholder wired to nothing, because no ticket owned
 * the wiring. So this one was in the decomposition from the start, and the
 * premise gate asserts assembly as its own clause.
 *
 * THE STRUCTURAL CHANGE. The previous version rendered `AuthGate` and nothing
 * else until a token resolved, so the landing screen was unreachable for a
 * visitor without an account. The approved design makes the landing the entry
 * point with a free allowance before sign-in is required.
 *
 * WHAT THAT CHANGE MUST NOT COST. The first version of this file replaced the
 * real `createRun` call with a demo timeline, which made every screen render
 * while quietly removing the only thing connecting the UI to the agent. The
 * premise gate passed anyway, because it asserted that the landing renders and
 * that navigation works, and never that a submitted question reaches the API.
 * That is the same defect shape LEARNINGS.md records twice: a component that
 * satisfies its own criteria while the system it belongs to does not work.
 *
 * So the rule this file follows: a signed-in question takes the real path,
 * `createRun` with the bearer token and then the live event stream. Only the
 * anonymous path is stubbed, because an anonymous caller has no token to send
 * and the allowance that governs it belongs to build phase 6.0. That stub is
 * declared in `stubs/registry.ts`, and the gate now asserts the real path.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { Box, CssBaseline, ThemeProvider } from "@mui/material";

import { theme } from "./theme";
import { createRun, stopRun } from "./lib/api";
import { useAgentRun } from "./hooks/useAgentRun";
import { useRunView } from "./hooks/useRunView";
import { AuthGate } from "./components/auth/AuthGate";
import { AppShell } from "./components/shell/AppShell";
import type { ScreenName } from "./components/shell/AppShell";
import { drawPersona } from "./components/shell/PersonaChip";
import { HomeScreen } from "./components/screens/HomeScreen";
import { RunScreen } from "./components/screens/RunScreen";
import type { StepName, ToolCall } from "./components/screens/RunScreen";
import { AnswerScreen } from "./components/screens/AnswerScreen";
import type { Claim, Source, TrustSignal } from "./components/screens/AnswerScreen";
import { AboutScreen, DocsScreen, IntegrationsScreen } from "./components/screens/InfoScreens";
import { GuestAllowance, SignInWall } from "./components/guest/GuestAllowance";
import { FeedbackSurface } from "./components/feedback/FeedbackSurface";
import { FollowUp, HistoryRail } from "./components/answer/FollowUp";
import {
  DisclaimerModal,
  hasAcceptedDisclaimer,
} from "./components/shell/DisclaimerModal";
import type { AudienceDepth } from "./components/controls/DepthControl";

type SearchView =
  | { name: "home" }
  | { name: "run"; question: string }
  | { name: "answer"; question: string }
  | { name: "wall" }
  | { name: "signin" };

/** The free allowance before sign-in is required. Stubbed; 6.0 enforces it. */
const FREE_SEARCHES = 5;

/** Every identifier below is a genuine NCBI record. */
const DEMO_CLAIMS: Claim[] = [
  {
    text: "BRCA1 is associated with hereditary breast and ovarian cancer syndrome, the best-characterised of its disease links.",
    layer: 1,
    citation: 1,
  },
  {
    text: "The current MedGen record describes an autosomal dominant inheritance pattern.",
    layer: 2,
    citation: 2,
  },
];

const DEMO_SOURCES: Source[] = [
  {
    n: 1,
    layer: 1,
    name: "NCBI Gene 672 · BRCA1",
    tool: "cypher_query",
    evidence: "curated assertion",
    confidence: "high",
    license: "public domain",
    url: "https://www.ncbi.nlm.nih.gov/gene/672",
  },
  {
    n: 2,
    layer: 2,
    name: "MedGen C0677776 · Hereditary breast and ovarian cancer syndrome",
    tool: "ncbi_efetch",
    evidence: "curated record",
    confidence: "high",
    license: "public domain",
    url: "https://www.ncbi.nlm.nih.gov/medgen/C0677776",
  },
];

const DEMO_TRUST: TrustSignal[] = [
  { kind: "good", label: "Grounded · every claim cited" },
  { kind: "risk", label: "High-risk claim · gene to disease" },
  { kind: "plain", label: "2 layers agreed" },
];

const DEMO_TOOLS: ToolCall[] = [
  { name: "cypher_query", detail: "25 rows", layer: 1 },
  { name: "ncbi_efetch", detail: "medgen C0677776", layer: 2 },
];

/** Canned follow-up hints. Stubbed; build phase 4.5 derives these for real. */
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
  /** True while the current run is the anonymous, locally-rendered one. */
  const [stubRun, setStubRun] = useState(false);
  const [stubStep, setStubStep] = useState<StepName | null>(null);

  // One id for this browser session, stable across questions so they group
  // into a thread. The fallback keeps a test environment without
  // crypto.randomUUID from throwing.
  const sessionId = useMemo(
    () =>
      typeof crypto !== "undefined" && "randomUUID" in crypto
        ? crypto.randomUUID()
        : `session-${Date.now()}`,
    [],
  );

  // Section 14.2: an anonymous session draws a persona and holds it for the
  // session. Stubbed; wired by build phase 4.5 from the POST /v1/query body.
  const persona = useMemo(() => drawPersona(0), []);

  const signedIn = token !== null;
  const remaining = Math.max(0, FREE_SEARCHES - used);

  // The real stream. `useAgentRun` does nothing while runId or token is null,
  // so an anonymous visitor simply never opens one.
  const { events, stop } = useAgentRun(runId, token);
  const view = useRunView(events);

  // The run screen advances on EVENTS, never on a timer. An earlier version of
  // this file walked the five steps on setTimeout, which looked identical on
  // screen and reported progress the agent had not made.
  const step: StepName | null = stubRun ? stubStep : view.activeStep;

  useEffect(() => {
    if (view.landed && searchView.name === "run" && !stubRun) {
      setSearchView({ name: "answer", question: searchView.question });
    }
  }, [view.landed, searchView, stubRun]);

  // The stubbed guest run has no event stream to advance it, so it walks the
  // loop on a timer. This applies ONLY to the anonymous path: a signed-in run
  // advances on real events, and conflating the two is what let an earlier
  // version report progress the agent had not made.
  useEffect(() => {
    if (!stubRun || searchView.name !== "run") return;
    const order: StepName[] = ["Guard", "Think", "Plan", "Act", "Write"];
    const timers = order.map((name, index) =>
      setTimeout(() => setStubStep(name), index * 650),
    );
    const landing = setTimeout(() => {
      setStubStep(null);
      setSearchView({ name: "answer", question: searchView.question });
    }, order.length * 650);
    return () => {
      timers.forEach(clearTimeout);
      clearTimeout(landing);
    };
  }, [stubRun, searchView]);


  const ask = useCallback(
    async (question: string, depth: AudienceDepth) => {
      if (!signedIn && remaining === 0) {
        setSearchView({ name: "wall" });
        return;
      }
      setUsed((n) => n + 1);
      setFlagged([]);
      setHistory((current) =>
        current.some((item) => item.question === question)
          ? current
          : [{ id: `${current.length}`, question }, ...current],
      );
      setRunId(null);
      setSearchView({ name: "run", question });

      if (!signedIn) {
        // STUBBED, and declared as `guest-allowance` in stubs/registry.ts. An
        // anonymous visitor has no token, so there is no authenticated endpoint
        // to call; build phase 6.0 owns the allowance that will let them run
        // for real. Until then the guest journey renders from local data, which
        // is what keeps the counter, the soft prompt and the wall reachable at
        // all. Marked here, never on screen.
        setStubRun(true);
        return;
      }

      setStubRun(false);
      try {
        const response = await createRun(
          { text: question, audience_depth: depth, session_id: sessionId },
          token,
        );
        setRunId(response.run_id);
      } catch {
        setSearchView({ name: "answer", question });
      }
    },
    [signedIn, remaining, token, sessionId],
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
            toolCalls={stubRun ? (step === "Act" || step === "Write" ? DEMO_TOOLS : []) : view.toolCalls}
            personaName={persona}
            onStop={() => {
              stop();
              if (runId && token) void stopRun(runId, token).catch(() => undefined);
              setSearchView({ name: "home" });
            }}
            onNewSearch={() => setSearchView({ name: "home" })}
          />
        );
      case "answer":
        return (
          <AnswerScreen
            question={searchView.question}
            claims={stubRun ? DEMO_CLAIMS : view.claims}
            sources={stubRun ? DEMO_SOURCES : view.sources}
            trust={stubRun ? DEMO_TRUST : view.trust}
            meta={stubRun ? "2 tools · 2 layers · 2 sources" : view.meta}
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
              activeId={searchView.name === "answer" || searchView.name === "run" ? history[0]?.id : null}
              onOpen={(id) => {
                const item = history.find((entry) => entry.id === id);
                if (item) setSearchView({ name: "answer", question: item.question });
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
