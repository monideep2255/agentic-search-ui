/**
 * UI fix 11.27, 2026-09-14: "There is too much bold. Only the title or main
 * point should be bold."
 *
 * WHAT THIS PINS:
 * - in a landed answer, the only bold words in the answer body are the lead
 *   summary's main point, whatever the backend put in `emphasis` on the lead,
 *   on other prose sentences, on table rows and on stacked rows;
 * - the main point is the emphasised term the question names, else the lead's
 *   first emphasised term; a lead with no emphasis bolds nothing;
 * - the status word, the sources count and every trust span are regular
 *   weight, measured as computed style, with a populate-check that computed
 *   weights are real in this environment (the question and a section heading
 *   read 700);
 * - the question heading stays bold, at 1280 and at the 390 phone layout.
 *
 * WHAT IT DOES NOT PIN: small-caps labels (section headings, table headers,
 * the Sources label) and citation markers, which stay 700 by design and are
 * excluded by name below; the collapsed source cards' own headers.
 */

import { render, screen } from "@testing-library/react";
import { ThemeProvider } from "@mui/material";
import { afterEach, describe, expect, it, vi } from "vitest";

import { theme } from "./theme";
import { AnswerScreen, mainPointFor } from "./components/screens/AnswerScreen";
import type { Claim, Source, TrustSignal } from "./components/screens/AnswerScreen";

const QUESTION = "Which diseases are associated with BRCA1?";

const sources: Source[] = [1, 2, 3].map((n) => ({
  n,
  layer: 2,
  name: `medgen C${n}`,
  tool: "ncbi_efetch",
  evidence: "curated assertion",
  confidence: "high",
  license: "public domain",
  url: `https://www.ncbi.nlm.nih.gov/medgen/C${n}`,
}));

const researcherClaims: Claim[] = [
  {
    text: "NCBI records link familial cancer of breast and pancreatic cancer susceptibility 4 to BRCA1. ",
    layer: 2,
    citations: [1, 2],
    kind: "claim",
    paragraph: 0,
    // Longest first, the order `emphasis_for` returns: the question-named
    // term is deliberately neither first in this list nor first in the text.
    emphasis: ["pancreatic cancer susceptibility 4", "familial cancer of breast", "BRCA1"],
  },
  {
    text: "A second sentence names Fanconi anemia complementation group S. ",
    layer: 2,
    citations: [3],
    kind: "claim",
    paragraph: 0,
    emphasis: ["Fanconi anemia complementation group S"],
  },
  {
    text: "Disease name: Familial cancer of breast [1]. ",
    layer: 2,
    citations: [1],
    kind: "table_row",
    paragraph: 1,
    heading: "Diseases linked to BRCA1",
    tableHeader: ["Disease", "MedGen record"],
    cells: ["Familial cancer of breast", "C0346153"],
    emphasis: ["Familial cancer of breast"],
  },
  {
    text: "Disease name: Pancreatic cancer susceptibility 4 [2]. ",
    layer: 2,
    citations: [2],
    kind: "table_row",
    paragraph: 1,
    cells: ["Pancreatic cancer susceptibility 4", "C3280442"],
    emphasis: ["Pancreatic cancer susceptibility 4"],
  },
];

const trust: TrustSignal[] = [
  { kind: "good", label: "Confirmed by 2 sources" },
  { kind: "risk", label: "High-risk claim" },
];

function setViewport(phone: boolean) {
  vi.stubGlobal(
    "matchMedia",
    (query: string) =>
      ({
        matches: phone && query.includes("max-width:720px"),
        media: query,
        addEventListener: () => undefined,
        removeEventListener: () => undefined,
        addListener: () => undefined,
        removeListener: () => undefined,
        onchange: null,
        dispatchEvent: () => false,
      }) as MediaQueryList,
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

function renderAnswer(claims: Claim[]) {
  return render(
    <ThemeProvider theme={theme}>
      <AnswerScreen
        question={QUESTION}
        claims={claims}
        sources={sources}
        meta="2 tools · 3 sources from 1 layer"
        outcome="Answered"
        outcomeTone="good"
        elapsedMs={6200}
        trust={trust}
        systemNotes={["Disease names are shown as NCBI MedGen records them.", "This is a research summary, not medical advice."]}
      />
    </ThemeProvider>,
  );
}

const weight = (element: Element) => Number.parseInt(getComputedStyle(element).fontWeight || "400", 10);

/** Every element with its own text whose computed weight is 600 or more. */
function boldTextElements(root: Element): Element[] {
  return [root, ...root.querySelectorAll("*")].filter((element) => {
    const ownText = [...element.childNodes].some(
      (node) => node.nodeType === Node.TEXT_NODE && (node.textContent ?? "").trim().length > 0,
    );
    return ownText && weight(element) >= 600;
  });
}

describe("UI fix 11.27: only the title and the main point are bold", () => {
  it("picks the question-named emphasised term of the lead, else its first, else nothing", () => {
    expect(mainPointFor(researcherClaims, QUESTION)).toEqual({ index: 0, term: "BRCA1" });
    expect(mainPointFor(researcherClaims, "Tell me about hereditary cancer")).toEqual({
      index: 0,
      term: "familial cancer of breast",
    });
    expect(mainPointFor(researcherClaims.map(({ emphasis: _e, ...claim }) => claim), QUESTION)).toBeNull();
    // A table row is never the lead summary.
    expect(mainPointFor(researcherClaims.slice(2), QUESTION)).toBeNull();
  });

  for (const phone of [false, true]) {
    it(`bolds the main point alone in a Researcher answer (${phone ? "390" : "1280"})`, () => {
      setViewport(phone);
      renderAnswer(researcherClaims);

      // Populate-checks: computed weights are real here, and the layout is the one asked for.
      expect(weight(screen.getByRole("heading", { level: 1, name: QUESTION }))).toBe(700);
      expect(weight(screen.getByRole("heading", { level: 2, name: "Diseases linked to BRCA1" }))).toBe(700);
      expect(screen.queryAllByTestId("answer-table")).toHaveLength(phone ? 0 : 1);
      // Populate-check: the backend asked for five bold terms across four claims.
      expect(researcherClaims.flatMap((claim) => claim.emphasis ?? [])).toHaveLength(6);

      const claims = screen.getByTestId("claims");
      const strong = claims.querySelectorAll("strong, b");
      expect(strong).toHaveLength(1);
      expect(screen.getByTestId("answer-main-point")).toHaveTextContent(/^BRCA1$/);

      const labels = new Set(
        [...claims.querySelectorAll("h2, th, button")].flatMap((label) => [label, ...label.querySelectorAll("*")]),
      );
      const bold = boldTextElements(claims).filter((element) => !labels.has(element));
      expect(bold.map((element) => element.textContent)).toEqual(["BRCA1"]);
    });
  }

  it("keeps the status word, the sources count, notes and every trust span at regular weight", () => {
    setViewport(false);
    renderAnswer(researcherClaims);
    const strip = screen.getByTestId("answer-meta");
    expect(strip).toHaveTextContent("Answered");
    expect(boldTextElements(strip)).toEqual([]);
    expect(weight(screen.getByTestId("sources-count"))).toBe(400);
    expect(boldTextElements(screen.getByTestId("answer-notes")).map((e) => e.textContent)).toEqual(["Notes"]);
    expect(boldTextElements(screen.getByTestId("answer-medical-note"))).toEqual([]);
    const line = screen.getByTestId("trust-line");
    expect(screen.getByTestId("trust-risk")).toHaveTextContent("High-risk claim");
    expect(boldTextElements(line)).toEqual([]);
  });

  it("bolds nothing but the title when the lead carries no emphasis (Plain language today)", () => {
    setViewport(false);
    renderAnswer(researcherClaims.map(({ emphasis: _e, ...claim }) => claim));
    expect(weight(screen.getByRole("heading", { level: 1, name: QUESTION }))).toBe(700);
    expect(screen.getByTestId("claims").querySelectorAll("strong, b")).toHaveLength(0);
  });
});
