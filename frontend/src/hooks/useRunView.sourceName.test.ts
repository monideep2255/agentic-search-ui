/**
 * T-4.16-03: a citation chip must not repeat its own source.
 *
 * The deployed demo rendered "MedGen MedGen:C0346153" against a design card
 * that reads "MedGen C0677776". See `sourceDisplayName`'s own docstring for
 * why the fix is at display time rather than on the wire.
 *
 * BOTH WIRE SHAPES ARE EXERCISED, and that is the point of this file. The
 * old plain join was correct for the Layer 2 shape and wrong for the Layer 1
 * shape, so a test covering either one alone would have gone green on the
 * broken code. The Layer 2 case here is not padding: it is the regression
 * guard on the half that already worked.
 */

import { readFileSync } from "node:fs";
import path from "node:path";

import { renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { AgentEvent } from "../lib/events";
import { DATABASE_NAMES } from "../lib/sourceDatabase";
import { sourceDisplayName, sourceLabel, useRunView } from "./useRunView";

describe("sourceDisplayName", () => {
  it("does not repeat the source when source_id is a full CURIE (Layer 1)", () => {
    expect(sourceDisplayName("MedGen", "MedGen:C0346153")).toBe("MedGen C0346153");
    expect(sourceDisplayName("NCBIGene", "NCBIGene:672")).toBe("NCBIGene 672");
  });

  it("leaves a bare record id alone (Layer 2)", () => {
    expect(sourceDisplayName("gene", "672")).toBe("gene 672");
    expect(sourceDisplayName("pubmed", "21990134")).toBe("pubmed 21990134");
  });

  it("strips the prefix regardless of case, since two modules assemble the pair", () => {
    expect(sourceDisplayName("MedGen", "medgen:C0346153")).toBe("MedGen C0346153");
  });

  it("never strips a colon that is not this source's own prefix", () => {
    // A different prefix must survive intact: silently trimming it would
    // destroy the one thing that makes the id resolvable.
    expect(sourceDisplayName("MedGen", "MONDO:0007254")).toBe("MedGen MONDO:0007254");
  });

  it("tolerates an empty id without leaving a trailing space", () => {
    expect(sourceDisplayName("MedGen", "")).toBe("MedGen");
  });
});

/**
 * Card 135: a source is named by its database, read off the record page,
 * whenever the wire's `source` is a tool's internal string. One helper names
 * the live Sources list, the marker card and the reopened saved list.
 *
 * Mutations these catch: calling `sourceDisplayName` again on the live list
 * (the tool-name cases go red), relabelling a source that already names a
 * database (the gene answer case goes red), guessing a database for an
 * unknown host (the fallback case goes red), and dropping the record id.
 */
describe("sourceLabel", () => {
  // One record page per key in the trust line's table, with the name it
  // must read. A Layer 2 tool name as `source` forces the page to decide.
  const PAGE_FOR_KEY: Record<string, string> = {
    "ncbi.nlm.nih.gov/assembly": "https://www.ncbi.nlm.nih.gov/assembly/GCF_000005845.2",
    "ncbi.nlm.nih.gov/bioproject": "https://www.ncbi.nlm.nih.gov/bioproject/PRJNA1",
    "ncbi.nlm.nih.gov/biosample": "https://www.ncbi.nlm.nih.gov/biosample/SAMN00715300",
    "ncbi.nlm.nih.gov/clinvar": "https://www.ncbi.nlm.nih.gov/clinvar/variation/267740/",
    "ncbi.nlm.nih.gov/datasets": "https://www.ncbi.nlm.nih.gov/datasets/gene/672/",
    "ncbi.nlm.nih.gov/dbvar": "https://www.ncbi.nlm.nih.gov/dbvar/variants/nsv1",
    "ncbi.nlm.nih.gov/gds": "https://www.ncbi.nlm.nih.gov/gds/200000001",
    "ncbi.nlm.nih.gov/gene": "https://www.ncbi.nlm.nih.gov/gene/672",
    "ncbi.nlm.nih.gov/gtr": "https://www.ncbi.nlm.nih.gov/gtr/tests/1/",
    "ncbi.nlm.nih.gov/medgen": "https://www.ncbi.nlm.nih.gov/medgen/C0346153",
    "ncbi.nlm.nih.gov/mesh": "https://www.ncbi.nlm.nih.gov/mesh/D001943",
    "ncbi.nlm.nih.gov/nuccore": "https://www.ncbi.nlm.nih.gov/nuccore/NM_007294.4",
    "ncbi.nlm.nih.gov/pathogens": "https://www.ncbi.nlm.nih.gov/pathogens/isolates/#SAMN00715300",
    "ncbi.nlm.nih.gov/pmc": "https://pmc.ncbi.nlm.nih.gov/articles/PMC1/",
    "ncbi.nlm.nih.gov/pubchem": "https://pubchem.ncbi.nlm.nih.gov/compound/2244",
    "ncbi.nlm.nih.gov/pubmed": "https://pubmed.ncbi.nlm.nih.gov/21990134/",
    "ncbi.nlm.nih.gov/snp": "https://www.ncbi.nlm.nih.gov/snp/rs80357906",
    "ncbi.nlm.nih.gov/sra": "https://www.ncbi.nlm.nih.gov/sra/SRX1",
    "ncbi.nlm.nih.gov/taxonomy": "https://www.ncbi.nlm.nih.gov/taxonomy/562",
    "ncbi.nlm.nih.gov/research/litvar2": "https://www.ncbi.nlm.nih.gov/research/litvar2/docsum?variant=rs1",
    "ncbi.nlm.nih.gov/research/pubtator3": "https://www.ncbi.nlm.nih.gov/research/pubtator3/publication/1",
    "omim.org": "https://www.omim.org/entry/113705",
    "clinicaltrials.gov": "https://clinicaltrials.gov/study/NCT01234567",
  };

  it("has a record page for every page key in the table", () => {
    const pageKeys = Object.keys(DATABASE_NAMES).filter((key) => key.includes("."));
    expect(Object.keys(PAGE_FOR_KEY).sort()).toEqual(pageKeys.sort());
  });

  it.each(Object.entries(PAGE_FOR_KEY))("names %s by its database, then the record id", (key, url) => {
    expect(sourceLabel("ncbi_efetch", "R1", url)).toBe(`${DATABASE_NAMES[key]} R1`);
  });

  it("names the three sources the reopened answer showed raw", () => {
    expect(
      sourceLabel(
        "pathogen_detection",
        "SAMN00715300",
        "https://www.ncbi.nlm.nih.gov/pathogens/isolates/#SAMN00715300",
      ),
    ).toBe("Pathogen Detection SAMN00715300");
    expect(
      sourceLabel("clinicaltrials.gov", "NCT01234567", "https://clinicaltrials.gov/study/NCT01234567"),
    ).toBe("ClinicalTrials.gov NCT01234567");
    expect(sourceLabel("ncbi_efetch", "NCBIGene:672", "https://www.ncbi.nlm.nih.gov/gene/672/")).toBe(
      "NCBI Gene 672",
    );
  });

  it("keeps a prefix that names a different vocabulary, and drops the no-id placeholder", () => {
    expect(sourceLabel("ncbi_efetch", "MONDO:0007254", "https://www.ncbi.nlm.nih.gov/medgen/C1")).toBe(
      "MedGen MONDO:0007254",
    );
    expect(sourceLabel("ncbi_efetch", "unknown", "https://www.ncbi.nlm.nih.gov/gene/672")).toBe("NCBI Gene");
  });

  it("falls back to today's label on a page the table does not know, never a guess", () => {
    expect(sourceLabel("pathogen_detection", "SAMN1", "https://example.org/isolate/SAMN1")).toBe(
      "pathogen_detection SAMN1",
    );
    expect(sourceLabel("ncbi_efetch", "672", "")).toBe("ncbi_efetch 672");
  });

  it("never rewrites a source that already names its database", () => {
    // The shapes a gene answer carries today: graph CURIE prefixes and the
    // NCBI database names Layer 2 sends. Each reads exactly as before.
    const cases: [string, string, string][] = [
      ["NCBIGene", "NCBIGene:672", "https://www.ncbi.nlm.nih.gov/gene/672"],
      ["MedGen", "MedGen:C0346153", "https://www.ncbi.nlm.nih.gov/medgen/C0346153"],
      ["ClinVar", "VCV000267740", "https://www.ncbi.nlm.nih.gov/clinvar/variation/267740/"],
      ["gene", "672", "https://www.ncbi.nlm.nih.gov/gene/672"],
      ["dbsnp", "rs80357906", "https://www.ncbi.nlm.nih.gov/snp/rs80357906"],
      ["omim", "omim:113705", "https://omim.org/entry/113705"],
      ["MedGen", "MONDO:0007254", "https://www.ncbi.nlm.nih.gov/medgen/C1"],
    ];
    for (const [source, id, url] of cases) {
      expect(sourceLabel(source, id, url)).toBe(sourceDisplayName(source, id));
    }
  });
});

describe("the live Sources list, card 135", () => {
  interface FixtureCitation {
    display_index: number;
    source_url: string;
    layer: string;
    source: string;
    source_id: string;
    field: string;
  }
  const BRCA1 = JSON.parse(
    readFileSync(path.resolve(__dirname, "../../e2e/fixtures/card22_brca1_citations.json"), "utf8"),
  ) as { citations: FixtureCitation[] };

  let seq = 0;
  function citationEvent(c: FixtureCitation): AgentEvent {
    seq += 1;
    return {
      type: "citation",
      version: "v1",
      trace_id: "t135",
      seq,
      ts: "2026-10-29T00:00:00Z",
      payload: {
        citation_id: `c${c.display_index}`,
        display_index: c.display_index,
        source: c.source,
        source_id: c.source_id,
        source_url: c.source_url,
        layer: c.layer,
        field: c.field,
        claim_text: "A claim.",
        evidence_kind: "curated assertion",
        assertion_confidence: "high",
        population_ancestry_context: null,
        license: "public domain",
      },
    } as unknown as AgentEvent;
  }

  it("names a normal gene answer's sources exactly as before", () => {
    // Mutation: relabel every source from its page and "NCBIGene 672"
    // becomes "NCBI Gene 672", red.
    const { result } = renderHook(() => useRunView(BRCA1.citations.map(citationEvent)));
    expect(result.current.sources.map((s) => s.name)).toEqual(
      BRCA1.citations.map((c) => sourceDisplayName(c.source, c.source_id)),
    );
    expect(result.current.sources[0].name).toBe("NCBIGene 672");
  });

  it("names a tool-named source by its database", () => {
    // Mutation: the live list calling `sourceDisplayName` again reads
    // "pathogen_detection SAMN00715300", red.
    const isolate: FixtureCitation = {
      display_index: 1,
      source: "pathogen_detection",
      source_id: "SAMN00715300",
      source_url: "https://www.ncbi.nlm.nih.gov/pathogens/isolates/#SAMN00715300",
      layer: "layer_2_api",
      field: "isolate",
    };
    const { result } = renderHook(() => useRunView([citationEvent(isolate)]));
    expect(result.current.sources[0].name).toBe("Pathogen Detection SAMN00715300");
  });
});
