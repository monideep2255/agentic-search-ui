# Workstream 3 plan: isolates and specific data tools

Scout W3 (`isolates_and_tools`), 2026-10-05, read-only, against develop `9a13e983`. Cards 94, 20, 92 and 29. No live questions were asked: the two diagnosed cards already carry live evidence from today, and cards 20 and 29 are known by code and tag, not by behaviour. Paths are relative to `<repo-root>`; `core/` means `src/system_03_search_agent/core/`.

## Table of contents

- [Card table](#card-table)
- [Card 94 split into build steps](#card-94-split-into-build-steps)
- [Card 92: do other allow-lists drop rows the same way](#card-92-do-other-allow-lists-drop-rows-the-same-way)
- [Root causes shared by several cards](#root-causes-shared-by-several-cards)
- [Suggested order inside the workstream](#suggested-order-inside-the-workstream)
- [What I did not check](#what-i-did-not-check)

## Card table

| Field | Card 94 | Card 20 | Card 92 | Card 29 |
|---|---|---|---|---|
| 1. Feature in plain words | An isolate question gives a table of isolates with their resistance genes, a note on which genes were searched, a true colistin count and the full details of one isolate | I can narrow an isolate search by year and place, not only by gene | A chromosome range question lists the copy number variant (dbVar) records for that stretch | Under each cited paper I see the one sentence of its own abstract that answers my question |
| 2. Impact | Wrong or degraded answer. The colistin "0 isolates" is a confident wrong record; the rest is missing detail | Degraded: the question is answered without the narrowing the person asked for, or the follow-up is refused | Degraded: a whole kind of record the question deserves is silently absent | Screen or wording only (an addition; nothing is wrong today) |
| 3. Status today | Still happens. Seven live guest runs on develop, 2026-10-05, each point reproduced (`testing/Developer/reports/2026-10-05_card94/diagnosis.md`). Count differences are newer snapshots, not a defect | Still true on develop: the tool takes gene prefixes only, no year or place field (`tools/pathogen_detection_schemas.py`, `PathogenIsolateSearchInput`). A year bound exists on the parked tag only (see Code) | Still happens. 4 of 4 live guest runs, 2026-10-05, 0 dbVar citations, 5 ClinVar ones (`testing/Developer/reports/2026-10-05_card92/diagnosis.md`) | Built but not live. Sentence finder, citation field and source card sit on the local tag `parked/phase-8.8-snippets-2026-09-25` (11 files, 1,022 lines); the hookup in `core/graph.py` was never written. Phase 8.6, its stated precondition, has merged (card 40 and card 8 rows) |
| 4. Root cause | Known, five causes (A to E below) | Known. Year: no field in the tool on develop. Location: no field, and picking a place from free text needs a classifier decision in the plan step. Follow-up carry-over is card 94 cause D | Known: `core/graph.py` `_BREADTH_FIELDS_BY_PURPOSE["dbvar_overlap"]` leads with `variant_type`, which `tools/ncbi_coordinate_overlap.py` `_build_record` stores as a list; `synthesis/findings.py` treats any list as a container and the row is skipped | Not a defect. Missing hookup: `core/graph.py` `_pubmed_abstract_rows` and the citation build never call `pick_snippet` |
| 5. Shared cause | A (genes missing in Plain language): card 38 (ESBL isolates do not say which gene). D (guard burst on 2026-09-29): card 72. D (follow-up refused): card 20 and card 35 in kind | Card 94 cause D (the follow-up "from 2023" is refused before it could filter) | Card 38 (a first field decides what a row can say), card 57 in kind (the shown quote versus the checked quote). See the audit below | Card 57 (which words a reader sees under a citation); card 89 (the writing step's choice of abstract sentences) |
| 6. Code it touches | A: `core/graph.py` `plain_listing` (about 11420), `synthesis/answer_layout.py` `TABLE_COLUMNS` (303), `record_status_or_year` (510). B: `core/graph.py` `_isolate_count_note` (8919), the notes tuple in `write_node` (12789), `core/isolate_search.py` `disclosure` (377). C: `core/isolate_search.py` (175, colistin family), `tools/pathogen_detection.py` (496 to 520), `tests/.../core/test_isolate_search.py` (188 to 192). D: `core/graph.py` isolate branch of `plan_node` (6373), `_is_memory_bound_follow_up` (5834), `core/run.py` `_remember_turn` (615). E: `core/graph.py` `think_node` (3774 to 3784), a new planner for `isolate_lookup` | `core/isolate_search.py` (`parse_isolate_question`, `plan_calls`), `tools/pathogen_detection.py` (the scan), `tools/pathogen_detection_schemas.py`, `core/graph.py` plan branch for isolates | `core/graph.py` `_BREADTH_FIELDS_BY_PURPOSE` (6877), `_pick_representative_field` (8550); `tools/ncbi_coordinate_overlap.py` `_build_record` (465); `synthesis/findings.py` (352, 449, 604) | New `synthesis/snippets.py` (parked), `contracts/events.py` (`CitationPayload.snippet`), `core/graph.py` `_pubmed_abstract_rows` and the citation build, `frontend/src/components/screens/AnswerScreen.tsx`, `useRunView.ts`, `events.ts` |
| 7. Size | Whole card L; steps below are S to M each | M if year only through a classifier decision and a tool field; L with location | S to M (option B plus a test), plus a golden run | M: the hookup, a cost cap, a live check at 390 pixels, then the golden run |
| 8. Depends on, blocks | Depends on: owner answer on A1 (below). D3 goes to card 72. Blocks: card 20 (a year filter has nothing to refine until D lands), card 38 (closed by A) | Depends on: card 94 C and D. Blocks: nothing | Depends on: nothing. Blocks: nothing, but sits in `core/graph.py` beside card 94's steps, so build in sequence | Depends on: cards 88 and 89 landing, because all three change which sentences a cited paper contributes and where the notes and quotes are built. Blocks: nothing |
| 9. Needs the owner | Yes, one question: A1 (see below) | Yes, one question (see below) | No. A decision for the test document only: query 29's text never names dbVar, so either the question or the expectation changes | Yes, one question (see below) |

Owner questions, each with a recommendation:

- Card 94, step A1: "In Plain language, may an isolate answer show a small table of strain and resistance genes instead of names only?" Recommend yes. Your item 12.9 rule 2 says Plain language lists titles only, which is right for a gene question and removes the whole answer for an isolate question; your own test document expects the table in the default mode. The exception is keyed on the record type, never on the question.
- Card 20: "Should a year or place in an isolate question be read by a classifier decision with code verifying, and should the parked regex year parser be dropped?" Recommend yes. The parked branch's `_find_collection_years` is a fixed date-phrase pattern, which is the shape your no-hardcoded-decisions rule rules out; the tool-side year bound is fine, the reading of the question is not.
- Card 29: "Does the sentence quote ship on every cited paper, capped at the first five papers that carry an abstract, at about a hundredth of a cent per answer?" Recommend yes, with the cap. Builder M measured the cost; the hookup also adds up to five decision calls to a 20 second target, so it needs the timing check on five runs.

## Card 94 split into build steps

The diagnosis names five causes (groups A to E). Each is its own build step with its own proof. Group letters match `testing/Developer/reports/2026-10-05_card94/diagnosis.md`.

| Step | Cause and fix | What the person feels | Size | Touches | Answer path, proof | Waits on |
|---|---|---|---|---|---|---|
| 94-C | The colistin family searches `mcr-` and the matcher's boundary rule rejects every real mcr gene (`mcr-1.1`), so the answer states a false "0 isolates". Change the prefix to `mcr`; add a test that runs every `GENE_FAMILIES` prefix through the tool's predicate against a real gene name | A colistin question stops saying zero | S, under half a day. One token, one test, provable offline | `core/isolate_search.py:175`, `tools/pathogen_detection.py:496`, the existing pin in `test_isolate_search.py:188` | Yes: golden at least 101 of 150, then a live run showing the real count | Nothing. Do first |
| 94-B | The "which genes were searched, which were left out" sentence lives only in Think's narrative. Add a note built from `isolate_search.disclosure` beside `_isolate_count_note` | The blaCTX-M note, and prefixes named on Klebsiella answers, appear under the answer | S | `core/graph.py` `_isolate_count_note`, the notes tuple, `core/isolate_search.py` `disclosure` | Notes only, no new facts; golden as an alarm if bundled with C | Nothing |
| 94-A1 | Plain language shows the type's mapped column (genes) for a record type whose mapping is the answer | The default mode shows genes | S | `core/graph.py` `plain_listing`, `synthesis/answer_layout.py` `TABLE_COLUMNS` | Display only; the cited and listed records do not change | Owner question above |
| 94-A2 | A place column from `geo_loc_name`; write "not recorded" for a missing date or place | Blank cells stop looking like lost data; place appears | S | `synthesis/answer_layout.py` `record_status_or_year` (510), the row builder at `core/graph.py` 4499 on | Display only | A1 (same listing code) |
| 94-A3 | Show the BioSample accession beside the strain in Plain language | The accession the test document asks for | S | same | Display only | A1 |
| 94-D | The isolate turn stores no entity in session memory, so "Show me the ones from 2023" is refused as off topic. Publish the organism in the isolate branch's `PlanPayload.resolved_entities` (D1), and remember the isolate search with one classifier decision "does this follow-up refine the previous isolate search?", code verifying the remembered search exists (D2). Ship D1 and D2 together | The follow-up is no longer refused; for a year the product cannot yet filter, it asks honestly | M, one to two days. A new decision point and memory field | `core/graph.py` 6373, 5834, 5864; `core/run.py` 615 | Yes: golden at least 101 of 150, five repeated live runs of the follow-up | Nothing hard; card 20 builds on it |
| 94-D3 | The 2026-09-29 fast fatal ("could not be completed", 6 seconds, no tool) is probably the unusable-reply sibling of card 72. Add one fresh guard request on an unusable reply inside card 72's design | Fewer "try again" failures in a burst | Not sized here: belongs to card 72 | `core/graph.py` 1949 to 1970 | Guardrail only | Card 84's design, per card 72's row |
| 94-E | A BioSample accession wins over the isolate rule, and nothing plans `pathogen_detection` `isolate_lookup`. A classifier decision "is this asking about the isolate's Pathogen Detection record?" adds one `isolate_lookup` call beside the BioSample summary; the taxon comes from the organism the question names, or from the BioSample summary, verified against `ORGANISMS` | A single isolate shows strain, place, date, genes and a Pathogen Detection link | M. A metadata scan can reach about 18 seconds on a large taxon, against the 20 second target, so the build includes a timing check on five runs | `core/graph.py` `think_node` 3774 to 3784, a new planner, `tools/pathogen_detection.py` `isolate_lookup` mode | Yes: golden at least 101 of 150 and the timing check | Nothing hard. If it is slow, the cap on scan time is the lever |

Notes on sequence: C and B can ship together in one pass (both small, both in the isolate files); A1 to A3 are one listing change and should be one pass; D and E each touch `think_node` or `plan_node` and must not run in parallel with each other or with card 92's step in `core/graph.py`.

## Card 92: do other allow-lists drop rows the same way

Short answer: no other allow-list in `core/graph.py` has a list-valued first field today, so no other row is dropped the same way. Two neighbouring risks exist, and one of them shares the same code line.

How the drop works, so the audit is precise: `_BREADTH_FIELDS_BY_PURPOSE` (the only field allow-list in `core/graph.py`) keeps the listed keys in order; `_pick_representative_field` (8550) returns the first non-blank key; `synthesis/findings.py` (352) then rejects any list, dict, tuple or set value, and for a row with no CURIE (every `ncbi_efetch` row) the row is skipped (449, 604). The pick never moves to the second field.

Per purpose, first field and its type, read from the allow-list and the record builders:

| Purpose | First field | Type | Hit by the drop |
|---|---|---|---|
| `dbvar_overlap` | `variant_type` | list (`dbvarvarianttypelist`, `tools/ncbi_coordinate_overlap.py:465`) | Yes. This is card 92 |
| `clinvar_overlap` | `title` | string | No |
| `clinvar_summary` | `title` | string | No |
| `pubmed_abstracts`, `omim_summary`, `gds_summary`, `biosample_summary`, `taxonomy_summary`, `medgen_summary` | `title`, `scientificname` | strings | No |
| `bioproject_summary`, `assembly_summary` | `project_title`, `assemblyname` | strings | No |
| `sra_summary` | `runs` | string (reduced to accessions by `_sra_run_accessions`) | No |

The layer 2 and 3 shapers (`_layer_tool_output_to_structured_fields`, for dbSNP, LitVar2, PubTator, ClinicalTrials and Pathogen Detection) already join lists to strings before building rows (for example `", ".join(snp.clinical_significance)`, `", ".join(isolate.amr_genotypes)`), so they are not exposed.

Two near misses that share the cause:

- Later fields that are lists or objects: `clinvar_summary.germline_classification` (an object, per `tools/ncbi_eutils_actions.py` line 99 to 100), `clinvar_summary.genes`, `omim_summary.alttitles`, `clinvar_overlap.gene_symbol`. They are never the pick while the leading string is present, so nothing is dropped today. If a ClinVar record ever arrives with a blank title, the pick lands on the object or list and the row is skipped with no note. This is a latent gap, not a seen defect.
- The dbVar row's own `gene_name` is also a list, so the card 92 fix must flatten or relabel it too, not only `variant_type`; otherwise the second field fails identically.

Recommendation for the build (a small addition to the diagnosis, which recommends option B): add a test that walks every `_BREADTH_FIELDS_BY_PURPOSE` purpose with a realistic record from the tool's builder and asserts the row yields a finding. That test would have caught card 92 and closes the latent gap for the other purposes. It is the same kind of guard as card 94's step C2 (every gene family against a real gene name): one general rule, "every declared shape is run against one real example in CI".

## Root causes shared by several cards

| Shared cause | Cards | One fix that would close them together |
|---|---|---|
| A declared list of prefixes, fields or families is never run against one real example, so a list that can match nothing passes CI and fails silently: colistin `mcr-` matches no mcr gene (card 94 C), a dbVar first field that is a list yields no row (card 92) | 94, 92 | A "real example per entry" test for each declared list: every `GENE_FAMILIES` prefix against a real gene name; every `_BREADTH_FIELDS_BY_PURPOSE` purpose against a real record. Plus, when a planned call yields rows that all vanish at the write step, a note says so instead of silence (the diagnosis for card 92 proposes this) |
| Notes and disclosures written into Think's narrative reach "Show work" only, never the answer's Notes | 94 (B), 92 (the "does not address the following entities" side effect), card 91 (a background search failure the note cannot name) | One path for "what the search did and did not do" into the Notes tuple in `write_node`, fed by code-built disclosures. 94-B is the first user; the others can join it. Not verified for 91, flagged only |
| Plain language shows titles only, which removes the answer when the answer is a mapped column | 94 (A), card 38 (ESBL isolates do not say which gene each carries) | A1: a record type's mapped column survives in Plain language. It would close the user-visible half of card 38 for isolates (card 38 also names TP53 orthologs and CFTR papers, which this does not cover) |
| An isolate turn leaves no memory, so any follow-up is read alone | 94 (D), 20 (a year or place cannot refine a search nobody remembers) | D1 plus D2 together. Card 20's year filter has no way to run until D lands |
| A first field decides what a row can say, and the rest is ignored (the pick returns one field per row) | 92, 38, in kind 57 | Not a single fix. A label built in code per record type (92 option B) is the pattern; it can be reused for the rows 38 says are too thin |
| The abstract sentence the person sees versus the one that was checked | 29, 57, 89 | Land 89 first, then wire 29 so the quoted sentence is the one the grounding pass accepted, which also gives card 57 its answer (the shown quote equals the checked quote). Not verified in code, a design hypothesis |

## Suggested order inside the workstream

1. 94-C, the colistin prefix, with the "real example per entry" test. It is the one place the product states a false fact, it is a one-token change, and it proves offline before any live run.
2. 94-B, the disclosure note. Small, notes only, and it makes every zero and every family answer checkable. Ship with C in one pass.
3. Card 92, option B with the gene-name join, plus the all-purposes row test. It is an answer-path change in `core/graph.py`; it is independent of the isolate work, so it can be built by a second builder, but not on the same function as step 4 at the same time.
4. 94-A1 to A3 after the owner answers: display only, one listing pass, closes the most visible half of card 94 and the user-visible half of card 38.
5. 94-D (D1 plus D2): larger and needs a new decision point, but it unblocks card 20 and fixes the refusal after every isolate answer. D3 goes to card 72's design.
6. 94-E, the single-isolate lookup, with its timing check. Last in card 94 because it adds up to 18 seconds of risk to the 20 second target.
7. Card 20 (year first, location after), once D has landed and the owner has decided on the classifier question. Year is one tool field plus one decision; location also needs the plan step to name a place, so it is the larger half.
8. Card 29, after cards 88 and 89 land, so the three changes to how cited sentences are chosen do not collide. The code is already built; what is left is the hookup, the five-paper cap, a 390 pixel check and a timing check.

## What I did not check

- No live question was asked; I relied on the two diagnoses of 2026-10-05 for cards 94 and 92 and did not rerun them.
- Whether the parked tag for card 29 still applies cleanly after phase 8.6 and later changes to `core/graph.py` (it is a diff of 11 files against an older base); I read the builder's report, not a trial merge.
- Whether the parked year parser for card 20 still exists in a reachable branch: the branch `phase/8.4-answers-worth-reading` named in the board is not a local or remote branch now; only the tag `parked/phase-8.4-2026-09-25` is. I read its `isolate_search.py` diff, not its tests.
- The remaining Layer 1 allow-lists outside `core/graph.py` (for example `synthesis/answer_layout.py` column maps) for list-valued fields; the audit covered `core/graph.py` as asked.
- Card 91's note path was named as a possible shared cause only from the card's wording, not from its diagnosis file.
- No real-record check that a ClinVar record can arrive with a blank title (the latent gap); this is a code reading.
- The size estimates are mine, from the diagnoses' risk notes; none is timed.
