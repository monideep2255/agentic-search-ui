# Card 23 adversary report

Fresh-context adversary round, 2026-10-06, branch fix/card23-source-note. Findings are appended as they are established.

## Table of contents

- [Findings](#findings)
- [What held](#what-held)
- [Not covered](#not-covered)
- [Verdict](#verdict)

## Findings

### A-23-01: when the variant table is the last group, the web screen moves the line into the Notes list after the answer
- Blocking: no (non-blocking, but it breaks the card's "directly under the table" contract on the main surface)
- Input: any Researcher, Clinical brief or Deep technical answer whose last record group is the variant-to-disease table, for example the variant fold with no gene record after it (the gene context call failed or was not planned). Reproduced with the real `write_node` and the existing `_FOLDED_VARIANT_ROWS` fixture, model call and MedGen lookup faked: `raw/adversary/probe.py alone`.
- What the person sees: the table, then nothing under it; after the whole answer, a "Notes" heading whose first bullet is "Variant-to-disease links are ClinVar assertions, ..." and whose second is "2 variant links to ClinVar placeholder conditions ... are not listed."
- Evidence: token stream is `table_row, table_row, paragraph_break, note(source line), paragraph_break, note(placeholder)`. A line-for-line port of `frontend/src/hooks/useRunView.ts:684-821` places a note only as `noteBefore` of the next claim with a kind; with no claim after it, `systemNotes.push(...pendingNotes)` (line 821) sends it to the Notes list (`AnswerScreen.tsx:1677`). Probe output: "frontend in-place notes: []", "frontend Notes list after answer: ['Variant-to-disease links are ClinVar assertions, ...', '2 variant links to ClinVar placeholder ...']". Same for `clinical_brief` and `deep_technical`. With a gene row after the variants (P2) the line is placed in place, before the "Gene records found" heading, as build.md says. The saved answer (`answer_markdown_from`) keeps the line in place in both cases.
- Why it matters: the line stops being attached to the table it describes; the builder's own placement arm only tests the case with a gene table after it, so nothing guards the alone case. The line is self-describing, so it does not lie there; it is misplaced. Build.md already lists this under "Not covered".
- Suggested fix: in `useRunView.ts`, attach a note that immediately follows a table's last `table_row` to that table (an `noteAfter` on the last row, or a pending flag flushed into the records block), and add a frontend test for the table-last case. Or emit a sentinel the screen can key on.
- NOT FIXED

### A-23-02: "read live from NCBI" is untrue for a cached title, which can be up to a week old and makes no NCBI call
- Blocking: no (wording; the builder already flagged it and offered a timing-free alternative)
- Input: the same disease asked about twice in one server process within seven days, with MedGen's title changing in between.
- What the person sees: the second answer's cell shows the old title under a line saying the names were "read live from NCBI".
- Evidence: `raw/adversary/probe_cache.py`, E-utilities search and summary patched. Output: "answer 1: {'MedGen:C0011860': 'Diabetes mellitus, type 2'} NCBI calls so far: 2", then "answer 2, six days later, NCBI now says 'Type 2 diabetes mellitus (renamed upstream)' -> {'MedGen:C0011860': 'Diabetes mellitus, type 2'} NCBI calls so far: 2". The second answer made zero NCBI calls (`disease_names.py` `_CACHE_TTL_S` = 7 days, negative results cached too). A saved answer reopened from history also keeps the line verbatim however old it is.
- Why it matters: the line is a trust signal; "live" is a checkable claim about timing that the code does not guarantee. Low practical harm (titles rarely change), but it is the kind of small overstatement the line exists to avoid.
- Suggested fix: drop "live", for example "Disease names are MedGen titles, looked up from NCBI." This is the owner's pinned wording, so it is the owner's call.
- NOT FIXED

### A-23-03: the disease cell is not always the MedGen title verbatim; it is a reordered form of it
- Blocking: no (unsure whether the owner reads "MedGen titles" as verbatim)
- Input: any linked disease whose MedGen title is in the inverted form.
- What the person sees: "Diabetes mellitus type 2" where MedGen's title is "Diabetes mellitus, type 2"; "Familial breast-ovarian cancer susceptibility 1" where the title is "Breast-ovarian cancer, familial, susceptibility to, 1".
- Evidence: `raw/adversary/probe_cache.py`, real `table_second_cell` over `readable_disease_name` (`disease_names.py:375`): "MedGen title: 'Breast-ovarian cancer, familial, susceptibility to, 1' cell shown: 'Familial breast-ovarian cancer susceptibility 1'". The word "to" is dropped. Every word otherwise comes from the title, by a closed rule.
- Why it matters: a reader who pastes the cell into MedGen expecting an exact title match will not always find it. The line is close to true, not exactly true.
- Suggested fix: none needed if the owner accepts "titles" for the reading-order form; otherwise "Disease names come from MedGen titles".
- NOT FIXED

### A-23-04: on the command line client (and by the same join, the MCP answer) the line describes disease names that are not on the page
- Blocking: no (the command line table rendering was already lossy before this card; the card adds a line about content that surface never shows)
- Input: the P1 fixture through the real CLI `Renderer` (`adapters/cli/render.py`, which prints `token.text` verbatim and ignores `cells`).
- What the person sees, exact stdout from `raw/adversary/probe.py alone`:
  "Variant-to-disease mapping" / "SequenceVariant ClinVar:1, name: variant number 1 [1]. SequenceVariant ClinVar:2, name: variant number 2 [3]." / "Variant-to-disease links are ClinVar assertions, each cited to its variation record. Disease names are MedGen titles read live from NCBI."
  No disease name appears in any row; the only disease name on the page is in the opening summary and the separate disease list.
- Evidence: above. The MCP server builds its answer as `"".join(answer_parts)` (`adapters/mcp/server.py:1241`), the same token texts, read only, not run.
- Why it matters: build.md withholds the line from Plain language because "a line about links would describe something not on the page". The same reasoning applies on the command line and to an MCP caller, where the line now names a variant-to-disease pairing the text never shows.
- Suggested fix: either render a table row's `cells` on the CLI (the real fix, a separate card) or document the gap; the line itself is not wrong.
- NOT FIXED

### A-23-05: "ClinVar assertions" sits under rows ClinVar classifies as likely benign or uncertain, and the table never shows the classification
- Blocking: yes, as the owner's call. The line is true in ClinVar's own vocabulary (an assertion is a classification for a variant and condition, benign included) and misleading in the reader's. The wording is the owner's pinned text of 2026-09-25, and the table showing these rows predates this card, so this goes to the owner rather than back to the builder.
- Input: query 79, "What diseases are caused by variants in the HNF1A gene?", Researcher. The builder's own live answer r1 (raw events in the session scratchpad, not in the repository), checked against live ClinVar ESummary on 2026-10-06.
- What the person sees: the heading "Variant-to-disease mapping", a row "NM_000545.8(HNF1A):c.1011C>T (p.Ser337=)" with "Maturity-onset diabetes of the young" in the disease column, and under the table "Variant-to-disease links are ClinVar assertions, each cited to its variation record." No clinical significance appears anywhere in the answer (searched the whole token stream for benign, pathogenic, significance, uncertain: zero hits).
- Evidence: the table's rows with a disease name and ClinVar's current germline classification of each, from `esummary.fcgi?db=clinvar&id=1025247,1134661,1036297,1043641,1173962`:
  - 1134661 c.1011C>T (p.Ser337=): "Likely benign", shown linked to Maturity-onset diabetes of the young
  - 1036297 c.355G>A (p.Val119Ile): "Uncertain significance", shown linked to Maturity-onset diabetes of the young
  - 1043641 c.1524G>T (p.Glu508Asp): "Uncertain significance", shown linked to Maturity-onset diabetes of the young
  - 1025247 c.780G>A (p.Thr260=): "Conflicting classifications of pathogenicity", shown linked to Maturity-onset diabetes of the young
  - 1173962 c.737T>G (p.Val246Gly): "Likely pathogenic"
  The System 1 ClinVar parser writes one `has_phenotype` edge per MedGen id in `PhenotypeIDS` for every variant whatever its `ClinicalSignificance` (`parse_variant_summary.py`, reference repository, read only), and `answer_layout._STATUS_FIELDS` has no significance field, so the table cannot show it.
- Why it matters: from the reader's chair, a question about which diseases variants "cause", a table pairing a variant with a disease, and a line saying each pairing is a ClinVar assertion, together read as "ClinVar says this variant causes this disease". For a likely benign variant ClinVar says the opposite. This is the confident wrong record the product rule ranks worst, and the new line is what lends it authority. A clinician would feel deceived on opening the cited variation record.
- Suggested fix, for the owner: either show each row's ClinVar classification in the table (the node already carries `clinical_significance`, so a "Classification" column is retrieved data, not inference), or reword the line so it does not imply causation, for example "Each row is a ClinVar record that names the condition, whatever ClinVar's classification; open the record to see it."
- NOT FIXED

### A-23-06: a link shown under the line is no longer in the variation record it is "cited to"
- Blocking: no (graph snapshot drift, not this card's code; the line makes it checkable and so more visible)
- Input: the same live answer r1, row "NM_000545.8(HNF1A):c.737T>G (p.Val246Gly)", cell "Maturity-onset diabetes of the young type 3; Monogenic diabetes".
- What the person sees: a reader who follows the line's promise and opens the cited variation record (ClinVar 1173962) finds only "Monogenic diabetes"; "Maturity-onset diabetes of the young type 3" is not in the record today.
- Evidence: live ClinVar ESummary for 1173962 on 2026-10-06: trait names `['Monogenic diabetes']`, the string "young type 3" absent from the whole record. Control: 1173963 in the same call does contain it. The graph's `has_phenotype` edges come from a ClinVar variant-summary snapshot, so ClinVar can have moved on since.
- Why it matters: "each cited to its variation record" invites the reader to check, and the check can fail. The line says nothing about the links being a snapshot while the disease names are "read live", so the two halves of the line have different ages without saying so.
- Suggested fix: say the links come from the knowledge graph's ClinVar snapshot (the snapshot date is already on each graph citation as `graph_snapshot_version`), for example "Variant-to-disease links are from ClinVar, as of the graph's last load, each cited to its variation record."
- NOT FIXED

### A-23-07: build.md's live table claims a property its script does not measure, and its count disagrees with the raw output
- Blocking: no (evidence quality)
- Input: `raw/analyse_live.py` and `raw/live_summary.txt` against build.md's "Live runs" table.
- What the reader of build.md sees: the column "Disease names that are a cited MedGen record's title" reading "6 of 6".
- Evidence: `analyse_live.py` counts `min(len(names), len(medgen))`, that is, whether a row carries at least as many MedGen markers as it shows names. It never compares a name to any title, so a row naming the wrong disease beside a MedGen marker would pass. `live_summary.txt` prints "disease names with a MedGen record cited on the row: 17 of 17" for both runs, not 6 of 6 (6 is the count of distinct names).
- Independent check: I compared the six distinct names in r1 against live MedGen ESummary titles for C0342276, C0011854, C0011860, C1838100, C2675866, C3888631: all six are the MedGen title exactly, and each row's names match its MedGen markers in order. So the claim holds for this answer; the builder's check would not have shown it if it had not.
- Suggested fix: correct the column's name and number in build.md, or make the script compare each name with the cited record's title.
- NOT FIXED

### A-23-08: outside the card, found on the way: 22 or more uncached linked diseases fail the whole MedGen lookup, and any failed lookup is cached as "no title" for a week
- Blocking: no for card 23 (the line fails closed: no names, no table, no line). Pre-existing in `synthesis/disease_names.py`; it decides how often the table this card annotates exists at all.
- Input A: an answer whose variant rows link to 22 or more distinct uncached MedGen ids (a well-studied gene; placeholders count too). Input B: one transient E-utilities failure, then the same diseases asked again on a healthy NCBI.
- What the person sees: A, no "Variant-to-disease mapping" table, only "Sequence variant records found" with no disease column. B, the same for up to seven days on that server process, though NCBI has recovered.
- Evidence: the one ESearch ORs every id into `term`, which `NcbiEfetchSearchInput` caps at 500 characters; real-format ids give "21 ids, term 479 chars: accepted", "22 ids, term 502 chars: REJECTED ValidationError", while `_MAX_IDS_PER_CALL` is 25. Through the real `write_node` with 30 linked ids (`raw/adversary/probe_mixed.py`, M3): log "MedGen concept search failed: ValidationError", headings `['Sequence variant records found']`, source line count 0. Negative caching (`raw/adversary/probe_negative_cache.py`): "answer 1 during a blip: {'MedGen:C0011860': None} calls 1", "answer 2, NCBI healthy: {'MedGen:C0011860': None} calls 1", and only a cold process recovers the title. `resolve_concept_ids` calls `_cache_put(local, None)` for every looked-up id after a failed search, so a failure is stored as "MedGen holds no such id".
- Why it matters: the reader loses the disease column for a week after one network blip, and never gets it for large genes. Not a lie; a missing answer.
- Suggested fix (a separate card): chunk the ESearch so each term stays under 500 characters, and cache None only when the search succeeded and the id was genuinely absent, never after an exception or a non-ok status.
- NOT FIXED

## What held

Each item below was probed, not only read, unless it says read.

| Attack | Result | How |
|---|---|---|
| A row that is not a ClinVar assertion under the line | Held. The line needs `mapped`, which needs every row in the group to carry `clinvar_condition_ids`; only `_apply_fold` writes it, only on the two fold templates, both over `has_phenotype`, whose only System 1 writer is the ClinVar variant-summary parser | Read (`cypher_query.py:1840`, `cypher_templates.py:497`, `:516`, reference parser). Probed the mix: folded variants plus a non-fold variant from a second graph call give no table and no line (`probe_mixed.py` M1) |
| Accession, coordinate window, model-written graph query, follow-up turn | Held by the same invariant: none of these paths writes the fold field, so no mapping table and no line. No follow-up path carries a previous turn's findings | Read (grep for every writer of the field, and for carried findings) |
| A row whose citation is not its variation record | Held. In the builder's live r1, 38 of 38 rows' first marker is a `/clinvar/variation/` URL; the graph's ClinVar CURIE maps only to that URL (`cypher_provenance.py:235`, `:406`) | Re-read the raw r1 events myself |
| A disease name that is not a MedGen title (fallback, placeholder, the question's words) | Held for names: names come only from `resolve_concept_ids` over MedGen, an unresolved or placeholder id shows nothing. All six live names in r1 equal the live MedGen title exactly. Exceptions are A-23-02 (cache age) and A-23-03 (reading-order form) | `probe_cache.py`; live MedGen ESummary for the six ids |
| MedGen down | Held, fails closed: no disease column, no table, no line | `probe_mixed.py` M2 |
| Line on the wrong table | Held: no line under the gene-to-disease table, the plain variant list, Plain language; one line only, as the builder's arms show | Builder's arms re-run (5 passed) and `probe.py` P1 to P4 |
| Clinical brief and deep technical depths | Held: same line, same place as Researcher | `probe.py` P3 |
| Structured fallback path | Held: the line sits under the table, before the next group | `probe.py` P4 |
| Saved answer reopened from history | Held: `answer_markdown_from` keeps the line as its own paragraph directly after the table, even when the table is last | `probe.py` P1 saved markdown |
| A second variant-to-disease table in one answer | Not reachable: one group per record noun per listing, and the fallback and the tail never both list | Read (`graph.py` `grouped_listing`, `_write_answer`) |

## Not covered

- No local live answer was run; the two allowed runs were not needed, because the builder's raw r1 events plus live NCBI ESummary calls (free, public) settled A-23-05 to A-23-07.
- The web screen was not rendered or screenshotted; note placement was checked with a Python port of `useRunView.ts:684-821`, not the TypeScript itself.
- The MCP and GraphQL surfaces were read, not run.
- An archived, folded previous turn on the answer screen was not exercised.
- A question that really ends on the variant table live (A-23-01) was not found; how often it happens in production is unmeasured.
- Seen in passing, outside this card: with MedGen down, the "Disease records found" table showed the graph's vocabulary artifacts "OMIM included" and "OMIM allelic variant" as disease names (`probe_mixed.py` M2, test fixture names). Not investigated.

## Verdict

FAIL, on one blocking item that is the owner's call.

- A-23-05, blocking: the line calls every row a "ClinVar assertion" under a table that shows likely benign and uncertain variants beside a disease, with no classification anywhere, in an answer to "what diseases are caused by". The wording is the owner's pinned text, so this goes to the owner.
- Non-blocking: A-23-01 (line moves to the Notes list when the table is last), A-23-02 ("live" overstates a week-long cache), A-23-03 (reading-order titles), A-23-04 (CLI and MCP show the line without the disease column), A-23-06 (graph snapshot drift against the cited record), A-23-07 (build.md's live metric), A-23-08 (pre-existing MedGen lookup failures, outside the card).

None of these sits inside a fix made during a review round of this card: this is round 1. A-23-05 sits in the card's own new line.

Verified with my own probes: the line's placement in every depth and in the fallback, the frontend placement (by port), the CLI output, the saved markdown, the mixed-group and MedGen-down cases, the cache age, the reading-order rewrite, the 500-character lookup failure, the negative cache, the citation of every live row, the six live names against MedGen, and the ClinVar classifications of five live rows. Only read: the fold-field invariant (writers found by grep), System 1's edge writer, the MCP join, the absence of carried findings across turns.
