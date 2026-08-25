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

import { describe, expect, it } from "vitest";

import { sourceDisplayName } from "./useRunView";

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
