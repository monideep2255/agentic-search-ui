/**
 * Card 135: the web app's database names are the trust line's, both ways.
 *
 * `lib/sourceDatabase.ts` ports `trust.py`'s `_NCBI_DATABASE_NAMES`,
 * `_NCBI_RESEARCH_NAMES` and the literal entries of `_DATABASE_NAMES`. This
 * reads the Python file itself, so a name added or changed on either side
 * without the other turns this red, and "from ClinVar and OMIM" on the trust
 * line can never sit above a source list that names those records otherwise.
 *
 * It also pins `recordDatabase` against the cases `record_database`'s
 * docstring names.
 */

import { readFileSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

import {
  DATABASE_NAMES,
  NCBI_DATABASE_NAMES,
  NCBI_RESEARCH_NAMES,
  databaseNameForUrl,
  recordDatabase,
} from "./sourceDatabase";

const TRUST_PY = readFileSync(
  path.resolve(__dirname, "../../../src/system_03_search_agent/synthesis/trust.py"),
  "utf8",
);

/** The `"key": "value"` entries of one dict literal in `trust.py`, by its name. */
function pythonDict(name: string): Record<string, string> {
  const start = TRUST_PY.indexOf(`\n${name}: dict[str, str] = {`);
  expect(start, `${name} not found in trust.py`).toBeGreaterThanOrEqual(0);
  // To the brace that closes this literal, counting the nested `**{...}`.
  const open = TRUST_PY.indexOf("{", start);
  let depth = 0;
  let close = open;
  for (; close < TRUST_PY.length; close += 1) {
    if (TRUST_PY[close] === "{") depth += 1;
    if (TRUST_PY[close] === "}") depth -= 1;
    if (depth === 0) break;
  }
  const body = TRUST_PY.slice(open, close)
    // The two spread comprehensions are derived, not literal entries.
    .replace(/^\s*\*\*.*$/gm, "");
  return Object.fromEntries(Array.from(body.matchAll(/"([^"]+)":\s*"([^"]+)"/g), (m) => [m[1], m[2]]));
}

describe("the database name table, against trust.py", () => {
  it("names every NCBI database path exactly as trust.py does", () => {
    expect(NCBI_DATABASE_NAMES).toEqual(pythonDict("_NCBI_DATABASE_NAMES"));
  });

  it("names every NCBI research resource exactly as trust.py does", () => {
    expect(NCBI_RESEARCH_NAMES).toEqual(pythonDict("_NCBI_RESEARCH_NAMES"));
  });

  it("carries trust.py's other keys exactly, and nothing more", () => {
    const literal = pythonDict("_DATABASE_NAMES");
    const derived = Object.keys(DATABASE_NAMES).filter((key) => key.startsWith("ncbi.nlm.nih.gov/"));
    expect(derived).toHaveLength(
      Object.keys(NCBI_DATABASE_NAMES).length + Object.keys(NCBI_RESEARCH_NAMES).length,
    );
    const rest = Object.fromEntries(
      Object.entries(DATABASE_NAMES).filter(([key]) => !key.startsWith("ncbi.nlm.nih.gov/")),
    );
    expect(rest).toEqual(literal);
  });
});

describe("recordDatabase", () => {
  it("keys a page the way trust.py's record_database does", () => {
    expect(recordDatabase("https://www.ncbi.nlm.nih.gov/clinvar/variation/267740/")).toBe(
      "ncbi.nlm.nih.gov/clinvar",
    );
    expect(recordDatabase("https://pubmed.ncbi.nlm.nih.gov/21990134/")).toBe("ncbi.nlm.nih.gov/pubmed");
    expect(recordDatabase("https://www.ncbi.nlm.nih.gov/research/litvar2/docsum")).toBe(
      "ncbi.nlm.nih.gov/research/litvar2",
    );
    expect(recordDatabase("https://www.omim.org/entry/113705")).toBe("omim.org");
    expect(recordDatabase("https://omim.org/entry/113705")).toBe("omim.org");
    expect(recordDatabase("https://clinicaltrials.gov/study/NCT1")).toBe("clinicaltrials.gov");
    expect(recordDatabase("https://www.ncbi.nlm.nih.gov/")).toBe("ncbi.nlm.nih.gov");
  });

  it("names no database for no page or a string that is not a URL", () => {
    expect(recordDatabase("")).toBe("");
    expect(recordDatabase(null)).toBe("");
    expect(recordDatabase("not a url")).toBe("");
    expect(databaseNameForUrl("https://example.org/x")).toBeNull();
  });
});
