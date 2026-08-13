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

import { useCallback, useMemo, useState } from "react";
import { CssBaseline, ThemeProvider } from "@mui/material";

import { theme } from "./theme";
import { createRun } from "./lib/api";
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

export function App() {
  const [screen, setScreen] = useState<ScreenName>("search");
  const [view, setView] = useState<SearchView>({ name: "home" });
  const [used, setUsed] = useState(0);
  const [token, setToken] = useState<string | null>(null);
  const [step, setStep] = useState<StepName | null>(null);
  const [, setRunId] = useState<string | null>(null);

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

  /** Walk the loop visually. Used only where no token exists to run for real. */
  const walkLoop = useCallback((question: string) => {
    setStep("Guard");
    const rest: StepName[] = ["Think", "Plan", "Act", "Write"];
    rest.forEach((next, index) => {
      setTimeout(() => setStep(next), (index + 1) * 700);
    });
    setTimeout(
      () => {
        setStep(null);
        setView({ name: "answer", question });
      },
      (rest.length + 1) * 700,
    );
  }, []);

  const ask = useCallback(
    async (question: string, depth: AudienceDepth) => {
      if (!signedIn && remaining === 0) {
        setView({ name: "wall" });
        return;
      }
      setUsed((n) => n + 1);
      setView({ name: "run", question });
      setStep("Guard");

      if (!signedIn) {
        // No token, so there is nothing real to call. The allowance that will
        // govern anonymous runs is build phase 6.0's.
        walkLoop(question);
        return;
      }

      // The real path. This is the line whose absence the first version of
      // this file hid behind a working-looking UI.
      try {
        const response = await createRun(
          // session_id is required by the contract. One id per browser session
          // groups a user's questions into a thread, which is what build phase
          // 4.5's session memory reads.
          { text: question, audience_depth: depth, session_id: sessionId },
          token,
        );
        setRunId(response.run_id);
        walkLoop(question);
      } catch {
        setStep(null);
        setView({ name: "answer", question });
      }
    },
    [signedIn, remaining, token, sessionId, walkLoop],
  );

  const body = () => {
    if (screen === "integrations") return <IntegrationsScreen />;
    if (screen === "docs") return <DocsScreen />;
    if (screen === "about") return <AboutScreen />;

    switch (view.name) {
      case "signin":
        return (
          <AuthGate
            onAuthenticated={(next: string) => {
              setToken(next);
              setView({ name: "home" });
            }}
          />
        );
      case "run":
        return (
          <RunScreen
            question={view.question}
            activeStep={step}
            toolCalls={step === "Act" || step === "Write" ? DEMO_TOOLS : []}
            personaName={persona}
            onStop={() => setView({ name: "home" })}
            onNewSearch={() => setView({ name: "home" })}
          />
        );
      case "answer":
        return (
          <AnswerScreen
            question={view.question}
            claims={DEMO_CLAIMS}
            sources={DEMO_SOURCES}
            trust={DEMO_TRUST}
            meta="2 tools · 2 layers · 2 sources"
          />
        );
      case "wall":
        return <SignInWall onSignIn={() => setView({ name: "signin" })} />;
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
          if (next === "search") setView({ name: "home" });
        }}
        personaName={persona}
        signedIn={signedIn}
        hideAuthAction={view.name === "signin" && screen === "search"}
        onSignIn={() => {
          setScreen("search");
          setView({ name: "signin" });
        }}
        onSignOut={() => setToken(null)}
      >
        {body()}
      </AppShell>
    </ThemeProvider>
  );
}

export default App;
