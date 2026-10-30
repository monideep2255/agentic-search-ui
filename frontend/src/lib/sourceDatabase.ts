/**
 * The database a citation's record page belongs to, in the words a reader
 * knows ("ClinVar", "OMIM", "Pathogen Detection"). Card 135.
 *
 * WHY THIS EXISTS. A source's `source` field is not always a database name.
 * A Layer 2 citation built by the fallback path in `core/graph.py` carries
 * the tool that fetched it (`ncbi_efetch`), and two tools set their own
 * internal strings (`pathogen_detection`, `clinicaltrials.gov`). Shown raw,
 * a reopened answer listed twenty rows each reading "pathogen_detection
 * LIVE", and the live answer read "pathogen_detection SAMN00715300".
 *
 * THE SAME TABLE AS THE TRUST LINE. The server already names a record's
 * database for the trust line's "from ClinVar and OMIM" (card 8):
 * `record_database` and `_DATABASE_NAMES` in
 * `src/system_03_search_agent/synthesis/trust.py`. This module ports both
 * unchanged, so a source's name and the trust line above it can never
 * disagree. `sourceDatabase.parity.test.ts` reads `trust.py` and holds the
 * two tables equal, both ways.
 *
 * Only the record PAGE is read here, never a guess from the tool: the page
 * names its database the same way whichever tool fetched it. A page on a
 * host this table does not know names no database, and the caller keeps
 * its existing label.
 */

const NCBI_HOST = "ncbi.nlm.nih.gov";

/** `trust.py`'s `_NCBI_DATABASE_NAMES`: an NCBI page's first path segment. */
export const NCBI_DATABASE_NAMES: Readonly<Record<string, string>> = {
  assembly: "Assembly",
  bioproject: "BioProject",
  biosample: "BioSample",
  clinvar: "ClinVar",
  datasets: "NCBI Datasets",
  dbvar: "dbVar",
  gds: "GEO DataSets",
  gene: "NCBI Gene",
  gtr: "GTR",
  medgen: "MedGen",
  mesh: "MeSH",
  nuccore: "Nucleotide",
  pathogens: "Pathogen Detection",
  pmc: "PMC",
  pubchem: "PubChem",
  pubmed: "PubMed",
  snp: "dbSNP",
  sra: "SRA",
  taxonomy: "Taxonomy",
};

/** `trust.py`'s `_NCBI_RESEARCH_NAMES`: an NCBI research resource. */
export const NCBI_RESEARCH_NAMES: Readonly<Record<string, string>> = {
  litvar2: "LitVar2",
  pubtator3: "PubTator3",
};

/** `trust.py`'s `_DATABASE_NAMES`, keyed exactly as `record_database` keys. */
export const DATABASE_NAMES: Readonly<Record<string, string>> = {
  ...Object.fromEntries(
    Object.entries(NCBI_DATABASE_NAMES).map(([path, name]) => [`${NCBI_HOST}/${path}`, name]),
  ),
  ...Object.fromEntries(
    Object.entries(NCBI_RESEARCH_NAMES).map(([path, name]) => [`${NCBI_HOST}/research/${path}`, name]),
  ),
  "omim.org": "OMIM",
  "clinicaltrials.gov": "ClinicalTrials.gov",
  clinvar: "ClinVar",
  medgen: "MedGen",
  mesh: "MeSH",
  ncbigene: "NCBI Gene",
  omim: "OMIM",
  pubmed: "PubMed",
  dbsnp: "dbSNP",
};

/**
 * `trust.py`'s `record_database`, page branch only: the database key a
 * record page names, or "" when it names none (no page, or not a URL).
 *
 * An NCBI subdomain keys as its path (`pubmed.ncbi.nlm.nih.gov` is
 * `ncbi.nlm.nih.gov/pubmed`), an NCBI research resource by its own name,
 * any other host as itself with `www.` dropped.
 */
export function recordDatabase(url: string | null | undefined): string {
  const raw = (url ?? "").trim().replace(/\/+$/, "");
  if (raw === "") return "";
  let parsed: URL;
  try {
    parsed = new URL(raw);
  } catch {
    return "";
  }
  const host = parsed.hostname.toLowerCase().replace(/^www\./, "");
  if (host === "") return "";
  if (host.endsWith(`.${NCBI_HOST}`)) {
    return `${NCBI_HOST}/${host.slice(0, -(NCBI_HOST.length + 1))}`;
  }
  if (host === NCBI_HOST) {
    const segments = parsed.pathname
      .split("/")
      .filter((segment) => segment !== "")
      .map((segment) => segment.toLowerCase());
    if (segments[0] === "research" && segments.length > 1) {
      return `${NCBI_HOST}/research/${segments[1]}`;
    }
    if (segments.length > 0) return `${NCBI_HOST}/${segments[0]}`;
  }
  return host;
}

/** The reader's name for the database a record page belongs to, or null when the table does not know it. */
export function databaseNameForUrl(url: string | null | undefined): string | null {
  return DATABASE_NAMES[recordDatabase(url)] ?? null;
}

/**
 * The reader's name for a CURIE prefix or an NCBI database path ("NCBIGene",
 * "MedGen", "gene", "snp"), or null. Used only to decide whether a record id's
 * prefix repeats the database already named in front of it.
 */
export function databaseNameForPrefix(prefix: string): string | null {
  const key = prefix.trim().toLowerCase();
  return DATABASE_NAMES[key] ?? NCBI_DATABASE_NAMES[key] ?? NCBI_RESEARCH_NAMES[key] ?? null;
}
