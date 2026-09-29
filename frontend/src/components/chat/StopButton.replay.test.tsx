/**
 * Card 58: Stop, replayed against a real develop stream as the screen shows it.
 *
 * The product owner, 2026-09-27: "once the agent starts to write the answer,
 * the stop button just becomes gray ... a user should be able to stop the
 * answer at any point of time until the answer pops out."
 *
 * WHY A REPLAY. Stop went grey because it followed the ARRIVED stream while
 * the screen follows the PACED one: `usePacedEvents` holds each stage for a
 * reading beat and `useAnswerReveal` holds the answer behind the writing
 * banner. On develop the whole answer, its trust signals and `done` arrive
 * in one burst, so the arrived stream says "finished" while the screen is
 * still showing the helpers handing back. No hand-built fixture measures
 * that gap honestly; the timing of a real run does.
 *
 * THE STREAM is G-013, "what diseases are linked to brca1?", recorded on
 * develop on 2026-09-26 (`testing/Developer/reports/2026-09-26_answer_speed/
 * live_develop/dev_00_G-013.json`), the run with the longest grey stretch
 * among the eleven recorded. Kept per event: arrival time in ms after the
 * question was sent, type, tool name and status, token kind, and token text
 * cut to 72 characters. The recording kept no other payloads, so plan,
 * think, citation and trust payloads are filled with plain values; nothing
 * the pacing, the reveal or Stop reads depends on them. The `step` frame is
 * left out, as the web client drops it by name.
 *
 * THE CHAIN is the one `App` renders from: arrived events, then
 * `usePacedEvents`, then `useRunView`, then `useAnswerReveal`, with Stop
 * decided by `deriveStopOffered` from the arrived events and the revealed
 * view, exactly as `App` passes them.
 */

import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useAnswerReveal } from "../../hooks/useAnswerReveal";
import { usePacedEvents } from "../../hooks/usePacedEvents";
import { useRunView } from "../../hooks/useRunView";
import type { AgentEvent, Layer, ToolName } from "../../lib/events";
import { deriveStopOffered } from "./StopButton";

type Row =
  | [number, "guard" | "think" | "plan" | "citation" | "trust_signal"]
  | [number, "tool_start" | "tool_result", string, string]
  | [number, "token", string, string]
  | [number, "done", string];

// G-013 on develop, 2026-09-26. [arrival ms, type, ...detail].
const G013: Row[] = [
  [1426, "guard"],
  [4744, "think"],
  [4745, "plan"],
  [4745, "tool_start", "cypher_query", "running"],
  [4745, "tool_start", "ncbi_efetch", "running"],
  [4745, "tool_start", "pubtator_annotate", "running"],
  [4745, "tool_start", "clinicaltrials_search", "running"],
  [4745, "tool_start", "ncbi_efetch", "running"],
  [4745, "tool_start", "ncbi_efetch", "running"],
  [4747, "tool_start", "ncbi_efetch", "running"],
  [4747, "tool_start", "ncbi_efetch", "running"],
  [4747, "tool_start", "pubtator_annotate", "running"],
  [4747, "tool_start", "ncbi_efetch", "running"],
  [4747, "tool_start", "ncbi_efetch", "running"],
  [4747, "tool_start", "ncbi_efetch", "running"],
  [4747, "tool_start", "cypher_query", "running"],
  [4941, "tool_result", "ncbi_efetch", "ok"],
  [4941, "tool_result", "ncbi_efetch", "ok"],
  [4969, "tool_result", "pubtator_annotate", "ok"],
  [4975, "tool_result", "clinicaltrials_search", "ok"],
  [4991, "tool_result", "ncbi_efetch", "ok"],
  [5026, "tool_result", "ncbi_efetch", "ok"],
  [5112, "tool_result", "ncbi_efetch", "ok"],
  [5343, "tool_result", "cypher_query", "ok"],
  [5588, "tool_result", "cypher_query", "ok"],
  [5725, "tool_result", "pubtator_annotate", "ok"],
  [5768, "tool_result", "ncbi_efetch", "ok"],
  [6032, "tool_result", "ncbi_efetch", "ok"],
  [6078, "tool_result", "ncbi_efetch", "ok"],
  [17254, "token", "claim", "Found 4 disease records for BRCA1: Familial cancer of breast [1], Famili…"],
  [17269, "token", "paragraph_break", "\n\n"],
  [17269, "token", "claim", "BRCA1 is linked to four diseases in the knowledge graph: familial cancer…"],
  [17269, "token", "paragraph_break", "\n\n"],
  [17269, "token", "claim", "Mutations in this gene are responsible for approximately 40% of inherite…"],
  [17269, "token", "paragraph_break", "\n\n"],
  [17269, "token", "heading", "Disease records found\n\n"],
  [17269, "token", "table_header", ""],
  [17269, "token", "table_row", "Disease name: Familial cancer of breast [1]. "],
  [17269, "token", "table_row", "Disease name: Familial breast-ovarian cancer susceptibility 1 [2]. "],
  [17269, "token", "table_row", "Disease name: Pancreatic cancer susceptibility 4 [3]. "],
  [17269, "token", "table_row", "Disease name: Fanconi anemia complementation group S [4]. "],
  [17269, "token", "paragraph_break", "\n\n"],
  [17269, "token", "heading", "Gene records found\n\n"],
  [17269, "token", "table_header", ""],
  [17269, "token", "table_row", "Gene symbol: BRCA1 [6]. "],
  [17269, "token", "table_row", "Gene name: BRCA1 [10]. "],
  [17269, "token", "paragraph_break", "\n\n"],
  [17269, "token", "heading", "Pubmed records found\n\n"],
  [17269, "token", "table_header", ""],
  [17269, "token", "table_row", "Pubmed title: BRCA1-BARD1 promotes RAD51-mediated homologous DNA pairing…"],
  [17269, "token", "table_row", "Pubmed title: BRCA1: An Endocrine and Metabolic Regulator [12]. "],
  [17269, "token", "table_row", "Pubmed title: Preneoplastic stromal cells promote BRCA1-mediated breast…"],
  [17269, "token", "table_row", "Pubmed title: Mechanism of BRCA1-BARD1 function in DNA end resection and…"],
  [17269, "token", "table_row", "Pubmed title: Targeting GPX4-mediated ferroptosis protection sensitizes…"],
  [17270, "token", "paragraph_break", "\n\n"],
  [17270, "token", "heading", "Clinvar records found\n\n"],
  [17270, "token", "table_header", ""],
  [17270, "token", "table_row", "Clinvar title: NM_007294.4(BRCA1):c.5243_5277+2788del [8]. "],
  [17270, "token", "table_row", "Clinvar title: NM_007294.4(BRCA1):c.5277+2916_5277+2946delinsGG [13]. "],
  [17270, "token", "table_row", "Clinvar title: NG_005905.2:g.(147057_150288)_(160933_166866)del [16]. "],
  [17270, "token", "table_row", "Clinvar title: GRCh37/hg19 17q21.31(chr17:41267743-41267796)x3 [19]. "],
  [17270, "token", "table_row", "Clinvar title: NM_007294.4(BRCA1):c.2145C>G (p.Thr715=) [22]. "],
  [17270, "token", "paragraph_break", "\n\n"],
  [17270, "token", "heading", "Omim records found\n\n"],
  [17270, "token", "table_header", ""],
  [17270, "token", "table_row", "BRCA1 DNA REPAIR-ASSOCIATED PROTEIN [9]. "],
  [17270, "token", "table_row", "BRCA1 [9]. "],
  [17270, "token", "paragraph_break", "\n\n"],
  [17270, "token", "heading", "Clinical trial records found\n\n"],
  [17270, "token", "table_header", ""],
  [17270, "token", "table_row", "Clinical trial name: Germline BRCA1 and BRCA2 Mutations in Jewish Women…"],
  [17270, "token", "table_row", "Clinical trial name: BRCA1 Haploinsufficiency and Gene Expression [14]. "],
  [17270, "token", "table_row", "Clinical trial name: Study to Evaluate Treatment Customized According to…"],
  [17270, "token", "table_row", "Clinical trial name: Letrozole in Preventing Breast Cancer in Postmenopa…"],
  [17270, "token", "table_row", "Clinical trial name: Recombinant Human Chorionic Gonadotropin in Prevent…"],
  [17270, "citation"],
  [17270, "citation"],
  [17270, "citation"],
  [17270, "citation"],
  [17270, "citation"],
  [17270, "citation"],
  [17270, "citation"],
  [17270, "citation"],
  [17270, "citation"],
  [17270, "citation"],
  [17270, "citation"],
  [17271, "citation"],
  [17271, "citation"],
  [17271, "citation"],
  [17271, "citation"],
  [17271, "citation"],
  [17271, "citation"],
  [17271, "citation"],
  [17271, "citation"],
  [17271, "citation"],
  [17271, "citation"],
  [17271, "citation"],
  [17271, "citation"],
  [17271, "trust_signal"],
  [17271, "trust_signal"],
  [17272, "trust_signal"],
  [17272, "trust_signal"],
  [17272, "trust_signal"],
  [17272, "trust_signal"],
  [17272, "trust_signal"],
  [17272, "trust_signal"],
  [17272, "trust_signal"],
  [17272, "trust_signal"],
  [17272, "trust_signal"],
  [17272, "trust_signal"],
  [17272, "trust_signal"],
  [17278, "trust_signal"],
  [17278, "trust_signal"],
  [17278, "trust_signal"],
  [17278, "trust_signal"],
  [17278, "trust_signal"],
  [17278, "trust_signal"],
  [17278, "trust_signal"],
  [17278, "trust_signal"],
  [17278, "trust_signal"],
  [17278, "trust_signal"],
  [17278, "trust_signal"],
  [17278, "done", "ask"],
];

const LAYER: Record<string, Layer> = {
  cypher_query: "layer_1_graph",
  ncbi_efetch: "layer_2_api",
  pubtator_annotate: "layer_3_enrichment",
  clinicaltrials_search: "layer_3_enrichment",
};

/** The replay as the events the client would have parsed, in arrival order. */
function buildEvents(rows: Row[]): { at: number; event: AgentEvent }[] {
  const starts = rows.filter((row) => row[1] === "tool_start") as [number, string, string, string][];
  const calls = starts.map((row, index) => ({
    tool: row[2] as ToolName,
    call_id: `c${index}`,
    layer: LAYER[row[2]] ?? "layer_2_api",
  }));
  const closed = new Set<string>();
  let started = 0;
  let citations = 0;
  const trustTotal = rows.filter((row) => row[1] === "trust_signal").length;
  let trustSeen = 0;
  const outcome = (rows.find((row) => row[1] === "done") as [number, "done", string])[2];
  return rows.map((row, seq) => {
    const [at, type] = row;
    let payload: unknown;
    switch (type) {
      case "guard":
        payload = { passed: true, category: "ok", reason: null };
        break;
      case "think":
        payload = { narrative: "", query_class: "multi_hop", resolved_entities: [], clarifying_question: null };
        break;
      case "plan":
        payload = { narrative: "", tool_calls: calls };
        break;
      case "tool_start": {
        const call = calls[started];
        started += 1;
        payload = { call_id: call.call_id, tool: call.tool, layer: call.layer, status: "running" };
        break;
      }
      case "tool_result": {
        // Each result closes the first still-open call of the same tool.
        const call = calls.find((c) => c.tool === row[2] && !closed.has(c.call_id))!;
        closed.add(call.call_id);
        payload = {
          call_id: call.call_id, tool: call.tool, layer: call.layer, status: row[3],
          summary: "", result_count: 1, truncated: false,
        };
        break;
      }
      case "token":
        payload = { text: row[3], marker_ids: [], kind: row[2] };
        break;
      case "citation":
        citations += 1;
        payload = {
          citation_id: `k${citations}`, display_index: citations, source: "NCBI Gene",
          source_id: "672", source_url: "https://www.ncbi.nlm.nih.gov/gene/672",
          layer: "layer_1_graph", field: "x", claim_text: "x", evidence_kind: "curated assertion",
          assertion_confidence: "high", population_ancestry_context: null, license: "public domain",
        };
        break;
      case "trust_signal":
        trustSeen += 1;
        payload =
          trustSeen === trustTotal
            ? { outcome, risk_tier: "low", grounded: true, triangulated: null, scope: "answer" }
            : { outcome: "answer", risk_tier: "low", grounded: true, triangulated: null, scope: "claim" };
        break;
      case "done":
        payload = { total_cost_usd: 0, total_tool_calls: 10, elapsed_ms: 16975, trust_outcome: outcome };
        break;
    }
    return {
      at,
      event: {
        type, version: "v1", trace_id: "g013", seq,
        ts: "2026-09-26T21:32:33Z", payload,
      } as unknown as AgentEvent,
    };
  });
}

/** Stop's rule before card 58, verbatim: on after a passing guard, off at the first trust signal, done or fatal error. */
function stopEnabledBeforeCard58(events: AgentEvent[]): boolean {
  const guardPassed = events.some((event) => event.type === "guard" && event.payload.passed);
  if (!guardPassed) return false;
  return !events.some(
    (event) =>
      event.type === "trust_signal" ||
      event.type === "done" ||
      (event.type === "error" && event.payload.fatal === true),
  );
}

/** The chain `App` renders from, for one run. */
function useScreen(events: AgentEvent[]) {
  const paced = usePacedEvents(events, { runKey: "run-g013", stopped: false });
  const pacedView = useRunView(paced);
  const shown = useAnswerReveal(pacedView, { runKey: "run-g013", stopped: false });
  return {
    shown,
    offered: deriveStopOffered(events, { landed: shown.landed, claimsShown: shown.claims.length }),
  };
}

interface Sample {
  at: number;
  arrived: AgentEvent[];
  sentences: number;
  landed: boolean;
  offered: boolean;
}

const STEP_MS = 50;

/** Play the replay in real arrival order on fake time, sampling every step. */
async function replay(rows: Row[]): Promise<Sample[]> {
  const timeline = buildEvents(rows);
  const all = timeline.map((entry) => entry.event);
  const end = timeline[timeline.length - 1].at + 20_000;
  const { result, rerender } = renderHook(({ events }) => useScreen(events), {
    initialProps: { events: [] as AgentEvent[] },
  });
  const samples: Sample[] = [];
  let delivered = 0;
  for (let at = 0; at <= end; at += STEP_MS) {
    await act(async () => {
      vi.advanceTimersByTime(at === 0 ? 0 : STEP_MS);
    });
    let next = delivered;
    while (next < timeline.length && timeline[next].at <= at) next += 1;
    if (next !== delivered) {
      delivered = next;
      rerender({ events: all.slice(0, delivered) });
      await act(async () => {});
    }
    samples.push({
      at,
      arrived: all.slice(0, delivered),
      sentences: result.current.shown.claims.length,
      landed: result.current.shown.landed,
      offered: result.current.offered,
    });
  }
  return samples;
}

/** The longest unbroken stretch, in ms, over which `predicate` held. */
function longestStretch(samples: Sample[], predicate: (sample: Sample) => boolean): number {
  let longest = 0;
  let run = 0;
  for (const sample of samples) {
    run = predicate(sample) ? run + STEP_MS : 0;
    longest = Math.max(longest, run);
  }
  return longest;
}

describe("card 58: Stop on the G-013 develop stream, as the screen shows it", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-09-26T21:32:32Z"));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("stays on from the passed guard until the first sentence is on screen, then goes off", async () => {
    const samples = await replay(G013);
    const waiting = (s: Sample) => s.sentences === 0 && !s.landed;
    const guardAt = G013.find((row) => row[1] === "guard")![0];
    const doneAt = G013.find((row) => row[1] === "done")![0];
    const firstSentence = samples.find((s) => s.sentences > 0);

    // POPULATE-CHECKS. The replay reached a first sentence and landed, the
    // server finished before that sentence was on screen, and the rule Stop
    // had before card 58 greyed it over a long stretch with nothing to read.
    // Without these the arms below could pass against a replay that never
    // reproduced the defect.
    expect(firstSentence, "the replay never showed a sentence").toBeDefined();
    expect(samples[samples.length - 1].landed, "the replay never landed").toBe(true);
    expect(doneAt).toBeLessThan(firstSentence!.at);
    const greyWithNothingToRead = longestStretch(
      samples,
      (s) => waiting(s) && s.at >= guardAt && !stopEnabledBeforeCard58(s.arrived),
    );
    expect(greyWithNothingToRead).toBeGreaterThanOrEqual(10_000);

    // THE RULE. Offered at every moment after the guard passed while no
    // sentence is on screen, however long ago the server finished.
    const offMidWait = samples.filter((s) => s.at >= guardAt && waiting(s) && !s.offered);
    expect(
      offMidWait.map((s) => s.at),
      "Stop was off while the reader had no answer to read",
    ).toEqual([]);

    // And off from the first sentence on, since the server had finished and
    // there was nothing left to stop.
    const onWithAnswer = samples.filter((s) => s.sentences > 0 && s.offered);
    expect(onWithAnswer.map((s) => s.at), "Stop stayed on with the answer on screen").toEqual([]);
    expect(samples[samples.length - 1].offered).toBe(false);
  });
});
