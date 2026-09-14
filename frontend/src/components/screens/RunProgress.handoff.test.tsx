/**
 * UI fix set 8 (R30, R31, R43): the lead hands off to three named scientists.
 *
 * What these arms decide: that during Act the lead's caption reads the
 * handoff sentence; that one line per layer renders, naming the helper and
 * what they are doing; that each line's badge state follows the layer's own
 * call statuses (working until the result lands, done after, failed only
 * when every call errored); that each helper carries the same info control
 * the lead's chip has; and that a chip list with no persona (an older
 * backend) renders no handoff at all, which is the graceful-degradation
 * path.
 *
 * MUTATION-CHECKED before commit, by hand: with `deriveHandoff`'s `working`
 * line replaced by `false`, the "working until the result lands" arm goes
 * red; with the lead exclusion irrelevant here (the server draws), the
 * sentence arm goes red when `handoffSentence` drops the Oxford "and".
 *
 * NOT decided here: pixel layout at 390px. That is the browser suite's job
 * (`accessibility.spec.ts` asserts no horizontal scroll on the run screen);
 * this file pins the facts the paint is built from, exposed as `data-state`.
 */

import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { RunProgress, deriveHandoff, handoffSentence, type ToolCall } from "./RunProgress";

const HELPERS: ToolCall[] = [
  {
    name: "cypher_query",
    detail: "running",
    layer: 1,
    status: "running",
    persona: "Franklin",
    personaAbout: "Took Photo 51.",
    personaWikipedia: "https://en.wikipedia.org/wiki/Rosalind_Franklin",
  },
  {
    name: "ncbi_efetch",
    detail: "running",
    layer: 2,
    status: "running",
    persona: "Koch",
    personaAbout: "Postulates.",
    personaWikipedia: "https://en.wikipedia.org/wiki/Robert_Koch",
  },
  {
    name: "pubtator_annotate",
    detail: "running",
    layer: 3,
    status: "running",
    persona: "Carson",
    personaAbout: "Silent Spring.",
    personaWikipedia: "https://en.wikipedia.org/wiki/Rachel_Carson",
  },
  {
    name: "clinicaltrials_search",
    detail: "running",
    layer: 3,
    status: "running",
    persona: "Carson",
    personaAbout: "Silent Spring.",
    personaWikipedia: "https://en.wikipedia.org/wiki/Rachel_Carson",
  },
];

function landed(calls: ToolCall[], names: string[], status: "ok" | "empty" | "error"): ToolCall[] {
  return calls.map((call) => (names.includes(call.name) ? { ...call, status, detail: "3 rows" } : call));
}

describe("deriveHandoff", () => {
  it("yields one line per layer, in layer order, named for the helper", () => {
    const lines = deriveHandoff(HELPERS);
    expect(lines.map((line) => [line.layer, line.name, line.state])).toEqual([
      [1, "Franklin", "working"],
      [2, "Koch", "working"],
      [3, "Carson", "working"],
    ]);
  });

  it("keeps a layer working until every call on it has landed", () => {
    const one = deriveHandoff(landed(HELPERS, ["pubtator_annotate"], "ok"));
    expect(one.find((line) => line.layer === 3)?.state).toBe("working");
    const both = deriveHandoff(landed(HELPERS, ["pubtator_annotate", "clinicaltrials_search"], "ok"));
    expect(both.find((line) => line.layer === 3)?.state).toBe("done");
  });

  it("reports failed only when every call on the layer errored, and empty as done", () => {
    const oneErrored = deriveHandoff(landed(landed(HELPERS, ["pubtator_annotate"], "error"), ["clinicaltrials_search"], "ok"));
    expect(oneErrored.find((line) => line.layer === 3)?.state).toBe("done");
    const allErrored = deriveHandoff(landed(HELPERS, ["pubtator_annotate", "clinicaltrials_search"], "error"));
    expect(allErrored.find((line) => line.layer === 3)?.state).toBe("failed");
    const empty = deriveHandoff(landed(HELPERS, ["ncbi_efetch"], "empty"));
    expect(empty.find((line) => line.layer === 2)?.state).toBe("done");
  });

  it("yields nothing for a chip list that carries no persona (an older backend)", () => {
    const bare: ToolCall[] = HELPERS.map(({ name, detail, layer }) => ({ name, detail, layer }));
    expect(deriveHandoff(bare)).toEqual([]);
  });
});

describe("handoffSentence", () => {
  it("joins three names with commas and an and", () => {
    expect(handoffSentence(["Franklin", "Koch", "Carson"])).toBe(
      "is handing off to Franklin, Koch and Carson",
    );
    expect(handoffSentence(["Franklin", "Koch"])).toBe("is handing off to Franklin and Koch");
    expect(handoffSentence(["Franklin"])).toBe("is handing off to Franklin");
    expect(handoffSentence([])).toBe("");
  });
});

describe("RunProgress handoff during Act", () => {
  it("shows the lead handing off, then one line per layer with a working badge", () => {
    render(
      <RunProgress
        question="Which diseases are associated with BRCA1?"
        activeStep="Act"
        startedAt={Date.now()}
        personaName="Mendel"
        personaAbout="Peas."
        personaWikipedia="https://en.wikipedia.org/wiki/Gregor_Mendel"
        toolCalls={HELPERS}
      />,
    );

    expect(screen.getByTestId("persona-caption")).toHaveTextContent(
      "Mendel is handing off to Franklin, Koch and Carson",
    );
    const handoff = screen.getByTestId("handoff");
    expect(within(handoff).getAllByRole("listitem")).toHaveLength(3);
    expect(screen.getByTestId("handoff-layer-1")).toHaveTextContent("L1Franklin is searching the knowledge graph");
    expect(screen.getByTestId("handoff-layer-2")).toHaveTextContent("Koch is checking live NCBI records");
    expect(screen.getByTestId("handoff-layer-3")).toHaveTextContent("Carson is reading the literature and trials");
    for (const layer of [1, 2, 3]) {
      expect(screen.getByTestId(`handoff-layer-${layer}`)).toHaveAttribute("data-state", "working");
    }
    // Each helper carries the same info control the lead's chip has.
    expect(screen.getByRole("button", { name: "About Franklin" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "About Koch" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "About Carson" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "About Mendel" })).toBeInTheDocument();
  });

  it("turns a layer's badge to done when its results land, and the lead returns to writing on Write", () => {
    const calls = landed(HELPERS, ["cypher_query", "ncbi_efetch"], "ok");
    const { rerender } = render(
      <RunProgress question="q" activeStep="Act" startedAt={Date.now()} personaName="Mendel" toolCalls={calls} />,
    );
    expect(screen.getByTestId("handoff-layer-1")).toHaveAttribute("data-state", "done");
    expect(screen.getByTestId("handoff-layer-2")).toHaveAttribute("data-state", "done");
    expect(screen.getByTestId("handoff-layer-3")).toHaveAttribute("data-state", "working");

    rerender(
      <RunProgress question="q" activeStep="Write" startedAt={Date.now()} personaName="Mendel" toolCalls={calls} />,
    );
    expect(screen.getByTestId("persona-caption")).toHaveTextContent("Mendel is writing the answer");
    // REQUIREMENT CHANGE, 2026-09-14 (approved Streaming.dc.html): during Write
    // the writing banner names the helpers, so the handoff lines give way.
    expect(screen.getByTestId("writing-banner")).toBeInTheDocument();
    expect(screen.queryByTestId("handoff")).toBeNull();
  });

  it("says a layer did not answer when every call on it errored", () => {
    render(
      <RunProgress
        question="q"
        activeStep="Act"
        startedAt={Date.now()}
        personaName="Mendel"
        toolCalls={landed(HELPERS, ["ncbi_efetch"], "error")}
      />,
    );
    const line = screen.getByTestId("handoff-layer-2");
    expect(line).toHaveAttribute("data-state", "failed");
    expect(line).toHaveTextContent("Koch is checking live NCBI records · did not answer");
  });

  it("renders no handoff, and the plain Act caption, when the backend sent no persona", () => {
    const bare: ToolCall[] = HELPERS.map(({ name, detail, layer }) => ({ name, detail, layer }));
    render(
      <RunProgress question="q" activeStep="Act" startedAt={Date.now()} personaName="Mendel" toolCalls={bare} />,
    );
    expect(screen.queryByTestId("handoff")).toBeNull();
    expect(screen.getByTestId("persona-caption")).toHaveTextContent("Mendel is reading the records");
  });

  it("renders no handoff once stopped", () => {
    render(
      <RunProgress question="q" activeStep="Act" stopped startedAt={null} personaName="Mendel" toolCalls={HELPERS} />,
    );
    expect(screen.queryByTestId("handoff")).toBeNull();
  });
});
