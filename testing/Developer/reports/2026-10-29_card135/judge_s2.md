# Card 135 slice S2 judge report, one round

Judge for commit b99eef1c on fix/card135-saved-answer-matches-live, against origin/develop. Findings are appended as they are established; the verdict is at the end.

## Findings

### J-135S2-01: reopened graph sources lose the record's plain name ("BRCA1", the disease name, the variant name) that develop showed
- Severity: minor (owner judgement; not blocking under the card's own acceptance, which asks for the live label)
- Evidence: probe `sourceLabel` against develop's `entity_name ?? source` and develop's live `sourceDisplayName`, real producer shapes from `core/graph.py:11631` (graph: `source` = CURIE prefix, `source_id` = full CURIE, `entity_name` = row `name`):
  - graph gene: develop saved "BRCA1", develop live "NCBIGene 672", branch saved and live "NCBIGene 672"
  - graph disease: develop saved "Breast-ovarian cancer, familial 1", live "MedGen C0346153", branch "MedGen C0346153"
  - graph ClinVar: develop saved "NM_007294.4(BRCA1):c.68_69del", live "ClinVar VCV000017661", branch "ClinVar VCV000017661"
  - The live Sources row (`AnswerScreen.tsx:2425`) renders only `source.name`; `entity_name` is read by no non-test frontend file except `lib/api.ts` and `lib/events.ts` parsers (grep). So the live screen never shows the entity name in that row or near it.
- What a person sees: a clinician reopening a saved disease answer reads "1. MedGen C0346153" where develop read "1. Breast-ovarian cancer, familial 1". The id is gained and now matches live, the plain name is lost. The diagnosis (`diagnosis.md:87`) allowed "entity_name can follow the id"; the builder chose parity with live instead. Not a confident wrong record, a less readable one. Owner may want "NCBIGene 672 (BRCA1)" on both screens as a follow-up.
- NOT FIXED

### J-135S2-02: the saved screen treats any stored citation number as a marker anywhere in the text; the live screen only strips the numbers that sentence itself cites
- Severity: minor (unsure it is reachable with real producer output)
- Evidence: `savedAnswerMarkdown.tsx` `savedCitations` builds one answer-wide `known` set and `withCitationMarkers` converts any `[n]` in it; live `useRunView.ts:892-918` builds `citedIndexes` from that token's own citations only. Probe: markdown "The cohort in study [99] reported a rate." with citations 1 to 21 keeps "[99]" as text (correct), but the same sentence with "[12]" and a citation 12 elsewhere in the answer would render a raised 12 on the saved screen where live shows "[12]" text.
- What a person sees: only if a stored answer's prose contains a bracketed number that coincides with another sentence's citation, the reopened page shows a source marker that the live page did not. `capture.py` writes markers per claim, so I could not produce this from a real run; filed because R-05 is the rule the builder cites.
- NOT FIXED

### J-135S2-03: the saved marker card's mono tool row renders empty
- Severity: minor (declared by the builder as a known gap)
- Evidence: `savedAnswerMarkdown.tsx` `savedCitations` sets `tool: ""`; probe clicking a saved marker gives card text "[1] L2 · livePathogen Detection SAMN1Open the record" with an empty span between name and link. Live fills it with `payload.field || payload.source` (`useRunView.ts:670`).
- What a person sees: the reopened card has one line fewer than the live card (the field name, for example "amr_genes"). Not worse than develop, where no card existed at all.
- NOT FIXED

### J-135S2-04: a tool-named source with the placeholder id "unknown" now reads as the bare database name, with no record id
- Severity: minor (not worse than develop)
- Evidence: probe `sourceLabel("ncbi_efetch", "unknown", "https://www.ncbi.nlm.nih.gov/gene/672")` gives "NCBI Gene"; develop live gave "ncbi_efetch unknown", develop saved gave "ncbi_efetch". Same for `litvar2_lookup` + "unknown" giving "LitVar2" and `cypher_query` + "unknown" giving "NCBI Gene". Producers: `core/graph.py:12578-12579` (efetch defensive fallback), `core/graph.py:11634-11635` (graph row with no CURIE), `core/graph.py:12746-12747`. The first two are documented as should-not-be-reached; the graph CURIE comes from `raw_row.get("curie") or raw_row.get("id")` (`cypher_provenance.py:489`), so a graph node with an entity name and no CURIE is not a shape I could reach.
- What a person sees: in the rare fallback, "3. NCBI Gene" with the record link printed under it, where develop printed "3. ncbi_efetch". The id is still in the visible link. This is the only real-data route to a database name with no id; "1. Gene" exactly (the builder's fixture, `source: "Gene"`, no `source_id`) matches no producer: graph sends "NCBIGene", Layer 2 sends "gene", and `CitationPayload.source_id` is required (`contracts/events.py:482`).
- NOT FIXED

## Evidence

### Source labels for real producer shapes (judge's own probe of `sourceLabel` and `sourceDisplayName`)

| Shape (producer) | Develop saved row | Develop live row | Branch, live and saved |
|---|---|---|---|
| Graph gene (`core/graph.py:11631`) | BRCA1 | NCBIGene 672 | NCBIGene 672 |
| Graph disease, MedGen | Breast-ovarian cancer, familial 1 | MedGen C0346153 | MedGen C0346153 |
| Graph disease, MONDO | hereditary breast ovarian cancer | MONDO 0011450 | MONDO 0011450 |
| Graph ClinVar | NM_007294.4(BRCA1):c.68_69del | ClinVar VCV000017661 | ClinVar VCV000017661 |
| Live gene (`ncbi_efetch.py:194`, `db` = gene) | gene | gene 672 | gene 672 |
| Live ClinVar | clinvar | clinvar 17661 | clinvar 17661 |
| dbSNP (`ncbi_dbsnp.py:1672`) | dbsnp | dbsnp rs80357906 | dbsnp rs80357906 |
| PubMed via PubTator (`pubtator_annotate.py:1035`) | pubmed | pubmed 34083286 | pubmed 34083286 |
| PubTator entity, `ncbi_gene` | ncbi_gene | ncbi_gene 672 | NCBI Gene 672 |
| PubTator entity, `ncbi_mesh` | ncbi_mesh | ncbi_mesh D001943 | MeSH D001943 |
| LitVar2 (`litvar2_lookup.py:1091`) | litvar2 | litvar2 rs80357906 | litvar2 rs80357906 |
| Trial (`clinicaltrials_search.py:664`) | clinicaltrials.gov | clinicaltrials.gov NCT00590109 | ClinicalTrials.gov NCT00590109 |
| Isolate (`pathogen_detection.py:1501`, real URL `pathogens/isolates#/search/biosample_acc:`) | pathogen_detection | pathogen_detection SAMN00715300 | Pathogen Detection SAMN00715300 |
| efetch fallback, CURIE | ncbi_efetch | ncbi_efetch NCBIGene:672 | NCBI Gene 672 |
| efetch fallback, OMIM page | ncbi_efetch | ncbi_efetch 113705 | OMIM 113705 |
| efetch fallback, "unknown" | ncbi_efetch | ncbi_efetch unknown | NCBI Gene (J-135S2-04) |
| Tool name on an unknown host, empty URL, `javascript:` URL, look-alike host | tool name | tool name and id | unchanged, never guessed |

Every changed live label names the database its record page belongs to. Live rows never show `entity_name` (`AnswerScreen.tsx:2425` renders `source.name` only).

### Database table and `recordDatabase` parity

- 26 URLs (case, port, trailing slash, subdomain, research path, `www.`, `ftp://`, trailing-dot host, encoded slash, user info, `javascript:`, "not a url") through Python `trust.record_database` and TS `recordDatabase`: zero diff lines.
- Parity test mutated both ways, each restored: trust.py "ClinVar" renamed gives 2 failed; trust.py adds a `_DATABASE_NAMES` key gives 1 failed; trust.py adds a research name gives 1 failed; TS adds a research key gives 1 failed; TS drops the `omim` literal gives 1 failed.

### Citation markers on the saved screen (judge's render probe, desktop and phone identical)

| Stored text | Rendered (^ is the marker's word joiner) |
|---|---|
| `BRCA1 is a gene [1].` | "BRCA1 is a gene.^1" |
| `[1][2][3].` | "coli.^1, 2, 3" |
| `[1]...[20].` | "coli.^1–20", one marker |
| `[1][3][7][9]` | "1 +3" |
| `Another [1][99].` | "Another [99].^1" |
| `study [99] reported` | unchanged text, no marker |
| `BRCA1 [1] and TP53 [2] are genes.` | "BRCA1^1 and TP53^2 are genes." |
| `, ; : ! ? ...` after a marker | punctuation moved before the marker in each case |
| `(see gene [1])` | "(see gene^1)" |
| `id [1000] and [12345]` | unchanged |
| `[1](javascript:alert(1))` | marker then the text "(javascript:alert(1))", no anchor |
| `<img src=x onerror=alert(1)> <script>...</script> [1]` | literal text, zero img, script or `javascript:` anchors in the DOM |
| Table `C236-11 [1] / acrF [2]` | first cell marker, second cell "acrF [2]" as data |
| No `citations` prop | every `[n]` stays text |
| Citation with `layer: null` | marker shown, card says "listed under Sources below" |
| Click a saved marker | card "[1] L2 · live / Pathogen Detection SAMN1 / Open the record" |

### Tests and mutations

- `npx vitest run src/components/screens/ src/hooks/ src/components/answer/ src/lib/`: "Test Files 47 passed (47), Tests 463 passed (463)".
- `npx tsc --noEmit -p .`: exit 0, no output.
- `npx vitest run src/App.savedAnswer.test.tsx src/lib/api.fetchHistoryAnswer.test.ts`: "Tests 15 passed (15)".
- Judge's own mutations, each restored: saved marker card named by raw `source`, 1 failed; "unknown" placeholder printed, 1 failed; phone table first cell raw, 2 failed; list items raw, 1 failed.
- Builder's mutations re-run: live list back to `sourceDisplayName`, 2 failed (matches); R-05 broken (`if (n > 0)`), 8 failed (matches).

### Not verified by the judge

- No browser: the live and saved screens at 1280 and 390 were not driven. The product review the builder asks for is still needed.
- No real stored answer was reopened against a running backend; the shapes come from the producer code and the builder's fixtures.

## Verdict

PASS. No blocking finding. Each finding is minor. Nothing a reader sees is worse than develop except the loss of the graph record's plain name on the reopened list (J-135S2-01), which the card's acceptance asks for, and which the owner may want restored on both screens.
