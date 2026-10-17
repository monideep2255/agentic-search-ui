# Card 30 step 2b build report

Branch `fix/card30-variant-classifications-shown`, commit `6498efd7`, on develop `655e9dfe`.

## What changes, in the person's words

Under `Which BRCA1 variants are pathogenic?`, every listed graph variant shows ClinVar's classification of it ("Pathogenic", "Uncertain significance", "Conflicting classifications of pathogenicity"), read word for word from its ClinVar record. Researcher gets a "ClinVar classification" column. Plain language keeps it after the name: "c.1A>G (p.Xaa1Yaa), ClinVar classification: Pathogenic". When every listed variant shows one, step 1's line no longer appears. A variant whose classification could not be read keeps today's row, and the line still appears for the list. Nothing else changes.

## Diff by file

| File | Change |
|---|---|
| `synthesis/variant_classifications.py` (new) | `resolve_variant_classifications(curies)`: one ESummary (`db=clinvar`) per 50 `ClinVar:` CURIEs, at most 2 requests, 4 s timeout each, joined by the record's own id, value is `germline_classification.description` stripped. Unreadable (missing, not text, empty, over 100 characters, control character), ambiguous (same id twice with different values), absent, error, timeout: the CURIE is left out. Reads `call_budget.calls_made()`; at the 20-call ceiling it makes no request. No cache, on purpose, for clinical text |
| `synthesis/answer_layout.py` | `_ROW_TYPE_COLUMNS` gains `("SequenceVariant", "clinvar_classification")`; `plain_record_label` appends the classification after the name; `variant_classification_note(findings, classified=None)` returns None only when every shown graph variant finding's CURIE is classified; `with_variant_classification` puts the value on a copy of a graph variant's row fields |
| `core/graph.py` | Write starts the lookup as a task just before the MedGen name lookup and awaits it after the condition name lookup; `_answer_parts` takes `variant_classifications` and reads rows through `shown_row_fields`; both `_answer_parts` call sites pass it; the note selector gets the classified set. `build_synth_findings`, `build_synth_messages` and `contracts/events.py` untouched |

## Tests

| Test | Proves |
|---|---|
| `synthesis/test_variant_classifications.py` (29) | Join by id with records shuffled, dropped, merged (same value kept, different value ambiguous); verbatim value; timeout, exception, error, empty reply; empty and odd values; one request per 50 and at most two; duplicates and other vocabularies free; no CURIE no request; ceiling reached makes no request, one under it asks; the note stays until all shown variants are classified; row fields gain the value only for a graph variant. All fail on develop (module missing) |
| `core/test_write_answer_structure.py`, 8 `card30b` tests | Column and cells, four-cell cap, join by record not position, Plain label, one unread variant keeps its row and the line in both depths, empty lookup equals no lookup, no graph variants means no request, rs334 shape unchanged. Red on develop |
| `core/test_graph.py`, 2 `card30b` tests | Partly read list keeps line and "ask" floor with claim trust unchanged; fully read list drops the line, claim trust unchanged. Red on develop |

Probe against develop: the same Write run (gene rows both depths, rs334 shape, unread variants both depths, folded HNF1A table) dumped on develop's source and on mine, lookup returning nothing: every event identical except `call_elapsed_s` and `elapsed_ms`.

## Commands

| Command | Result |
|---|---|
| New tests plus `tests/system_03_search_agent/synthesis/` plus 12 core files referencing the MedGen lookup, the note, Write's name resolution or `SequenceVariant` | 1361 passed, 14 skipped, 1 xfailed |
| `ruff check` (no path) | passed |
| `isort --check-only --diff src tests services tracker alembic .claude .github` | passed |
| `ruff format --check` on the new files | passed |

## Timing for 40 BRCA1 variants, through the product's client, no model call

Live ESearch for 40 BRCA1 ClinVar ids, then `resolve_variant_classifications` on them, three runs: 0.27 s, 0.28 s, 2.32 s. The third run hit an HTTP 429 from NCBI after the earlier rapid calls and the client's retry waited 2 s. 40 of 40 resolved: 17 Uncertain significance, 12 Pathogenic, 8 Likely benign, 3 "no classification for the single variant". Typical is about 0.3 s, against the owner's "about a second"; a rate limit adds 2 s, and the 4 s timeout bounds the worst case.

## Things to decide or watch

- With every listed variant classified, the line goes, and step 1's "ask" floor goes with it, because step 1 floors only while the line's condition holds. The brief says the floor is unchanged; it is, while any shown row lacks a classification. A classification question over a fully classified list now answers as "answer". Say if the owner wants "ask" kept.
- ClinVar's own text "no classification for the single variant" counts as a read classification and is shown verbatim. A person may read it as an answer to "pathogenic?" (it says none). Say if that should count as unread.
- The lookup covers all prepared graph variants (up to 100), not only the displayed ones, so one unread variant that is not displayed keeps the line.
- The writer does not see the classification, so the prose can still say nothing about it; only the listing carries it.
- In the repository, `isort` run by hand on `core/graph.py` rewrites the `contracts.events` import block against ruff; I kept develop's form.

## Second commit: the floor no longer depends on the line (owner decision, 2026-10-17)

- Change: in Write the floor reads the classification decision picked `asks_classification` and a listed graph `SequenceVariant` row, not `variant_classification_note`. The line's own rule is unchanged. Through `trust_outcome` only; claim trust untouched.
- Kept from step 1: a finding that cites a classification field (`clinical_significance`, `germline_classification`) still lifts the floor, because the existing test `test_card30_no_floor_when_the_answer_shows_a_classification` pins it and the decision did not name it. Say if that should go.
- Tests: fully read list with the decision gives "ask" and no line; the same with `not_applicable` gives "answer" and no line; the partly read test (ask and line) stands.
- Mutation: restoring the floor to `classification_note is not None` turns `test_card30b_a_fully_read_list_drops_the_line_and_keeps_the_ask` red. Restored.
- Run: 1362 passed, 14 skipped, 1 xfailed on the same set; `ruff check` and the `isort` gate pass.

## Fix round (owner decision, 2026-10-17)

Develop merged first (cards 8 and 38 slice B): one conflict in `_ROW_TYPE_COLUMNS`, resolved by keeping both entries; the test set passed on the merge (1417 passed).

| Item | Change | Test | One property mutated, then restored |
|---|---|---|---|
| 1, J-30b-01 | `classification_text_suffix` adds "ClinVar classification: X. " after a graph variant row's cited sentence in the token text (clipped so the text stays inside 1000) | `test_card30b_the_text_surfaces_carry_each_classification`, `..._stays_inside_the_token_cap` | suffix returns "": red |
| 2, J-30b-02, A-30-01 | Variants that carry a disease mapping are not looked up, so query 79's table has three columns and card 23's line stays true | `test_card30b_the_variant_to_disease_table_has_no_classification` | lookup of mapped variants restored: red |
| 3, A-30-02 | `variant_classification_note` keeps the line while a live ClinVar record is on the page | `test_card30b_a_live_clinvar_row_keeps_the_line`, `test_a_live_clinvar_row_keeps_the_line` | live rows ignored: red |
| 4, J-30b-03, A-30-03 | `reserve_calls` leaves 4 calls for fallback names and 2 for the fold's lookup | `test_the_lookup_leaves_the_calls_the_name_lookups_need`, `test_card30b_at_18_calls_used_the_name_lookup_still_gets_its_call` | reserve removed: both red |
| 5, J-30b-05, A-30-04 | Timeout 1.5 s | `test_a_hung_reply_costs_at_most_one_and_a_half_seconds` | timeout 4 s: red |
| 6, J-30b-04 | `_RunDecisions.variant_lookup_task`, cancelled in `write_node`'s `finally` (one field beside the decisions, outside the stated fence) | `test_card30b_the_lookup_is_stopped_when_write_ends_early` | cancel removed: red |
| 7, J-30b-06 | Pinned | `test_only_the_germline_block_is_read` | oncogenicity read first: red |
| 8, A-30-05 | `testing/Test_queries_and_workflows.md` entries 22, 79, 115 say what a person now sees | none | none |

Query 79 at Plain language keeps step 1's line, since its variants are not looked up. Query 22 and BRCA1 answers that list live ClinVar records keep the line too (item 3), so the line goes only on a list with no live ClinVar record. The floor from the earlier commit is untouched.

Run: new tests, `synthesis/`, the 12 core files and `adapters/`: 2387 passed, 14 skipped, 1 xfailed. `ruff check` and the `isort` gate pass.
