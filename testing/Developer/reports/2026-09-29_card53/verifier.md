# Card 53 fresh verifier report

Fresh verifier, 2026-09-29, branch fix/card53-stale-facts at bdd50aa9. Verdicts re-derived from the code, appended as established.

## Verdicts on judge and adversary findings

Plan-path probe (mine, `ver53/test_ver_plan.py`, `plan_node` with stubbed `_literature_choice` and `resolve_concept_ids`), 15 cases, planned layer 3 tools:
- gene by symbol BRCA1, classifier not_literature or wants_literature: pubtator_annotate, clinicaltrials_search (query `BRCA1`) both times.
- gene by identifier NCBIGene:672: none. Gene by full name "breast cancer 1": both, on `BREAST CANCER 1`.
- disease GERD, not_literature: both, on `gastroesophageal reflux disease`. wants_literature: topic search only (a second-round pubtator_annotate markup, no ClinicalTrials.gov).
- disease GERD with MedGen lookup down: `['cypher_query']` only. Disease as a typed non-MedGen CURIE (MONDO:0007254): `['cypher_query']` only.
- no-entity literature question, either choice: topic search. Isolate (blaKPC): `['pathogen_detection', 'ncbi_efetch']`.
- rs ids (three in the text, dbSNP CURIE resolved), not_literature: two litvar2_lookup; wants_literature: topic search, no LitVar2.

- F-53-J01: FIXED. `catalogue.py:41-53,128-132` now names the three constants as the source of truth and says the rule gives Pathogen Detection only a floor; `test_timeouts_match_the_budgets_the_code_enforces` compares against `CYPHER_QUERY_TIMEOUT_SECONDS`, `DEFAULT_TIMEOUT_S`, `_TOTAL_BUDGET_S`. All five web tools import `ncbi_transport` (grep: clinicaltrials 9, pubtator 13, litvar2 11, dbsnp 21, efetch 3 references).
- F-53-J02: FIXED. "No decision gates them" and "every question that names ... a disease" are gone from all three files; the page names the classifier path. My probe confirms the classifier moves GERD from both calls to topic search, and the page's exception "a question with no gene that a classifier reads as asking for papers" covers it. A gene by symbol is not affected by the classifier (probe: identical plans), matching "with no gene".
- F-53-A01: FIXED on the page. Probe: NCBIGene:672 plans no layer 3; the page names "a gene named only by an identifier". Behaviour unchanged, which the page now states.
- F-53-A02: FIXED on the page. Probe: isolate plans `['pathogen_detection', 'ncbi_efetch']`; the page names "a question about bacterial isolates".
- F-53-A10: FIXED. `_build_layer_tool_calls` plans `entity_lookup` and `variant_search` (graph.py:4608, 4635); the page now says PubTator3 "looks the name up in its index" and LitVar2 "finds a named variant and counts the papers". "up to two rs variant ids" matches `rsids[:2]` (probe: three rs ids, two LitVar2 calls).
- F-53-J06: FIXED. `act_node` gathers `first_stage` then `second_stage` (graph.py:7990, 8035); both pages and the InfoScreens comment now describe the second round and "the answer waits for both rounds".
- F-53-A08: FIXED. About stop 3 now says 30 s graph, 15 s web API, 120 s Pathogen Detection; `ncbi_transport.DEFAULT_TIMEOUT_S = 15.0` serves all five web tools including ClinicalTrials.gov, `pathogen_detection._TOTAL_BUDGET_S = 120.0`.
- F-53-A09: FIXED. "and one access path within it" removed; the sentence now claims one layer per tool only.
- F-53-A12: FIXED. Page and card say 100 rows; `_PLAN_TOOL_CALL_ROW_LIMIT = 100` is what every planned graph call asks for.
- F-53-J04: FIXED. README prerequisite line removed, stack row says in-process only; `grep -rn "import redis\|from redis" src/` returns nothing.
- F-53-J05: OPEN AS NAMED, correctly out of scope. Card 53's row (`testing/UI_fix_plan.md`) names CLAUDE.md, AGENTS.md, README, the diagram, the deep dive and the catalogue, not `.claude/rules/`; a rule edit to `ai-security-standards.md` (the security layer) needs the owner's item-by-item yes. Still true today: `ai-security-standards.md:19` and `tool-call-budgets.md:35` name LitSense. Not a disguised miss, but nothing carries it forward: grep of the main checkout's board and HANDOFF.md for F-53-J05 finds no card. Name it at merge.
- F-53-A11: OPEN AS NAMED for the product half (the silent single graph call, `graph.py:5715-5738`, is behaviour, not a stated fact). The page half is only partly true, see F-53-V01. My probe reproduces it: GERD with the MedGen lookup down plans `['cypher_query']`.
- F-53-J03, A03, A04, A05, A06, A07: see the checker section below.

## New findings

### F-53-V01: the rewritten layer 3 stop says a disease gets PubTator3 and ClinicalTrials.gov, and names three exceptions, but two more paths plan neither and are not named
- Severity: minor (unsure: the blanket "Not every question gets them" keeps the paragraph literally true)
- What: `ArchitectureScreen.tsx` layer 3 stop, second paragraph, written in `2e3b212d`: "PubTator3 and ClinicalTrials.gov for a gene named by its symbol or, when no gene was found, for a disease ... Not every question gets them. A gene named only by an identifier, a question about bacterial isolates, and a question with no gene that a classifier reads as asking for papers are each searched another way." Two further paths plan no layer 3 and are not searched another way either, they get the graph call alone: a disease whose MedGen name lookup fails (A11), and a disease named by a typed non-MedGen identifier, since `_first_disease_curie` accepts only `MedGen:` and the exact-id pre-pass (`graph.py:5063`) passes any typed CURIE through verbatim.
- Reproduction: my `plan_node` probe. `disease GERD medgen-down -> ['cypher_query']`; `disease non-MedGen CURIE (MONDO:0007254) -> ['cypher_query']`; `disease GERD lit=not_literature -> [... 'pubtator_annotate', 'clinicaltrials_search' ...]`.
- Why it matters: a reader whose disease question returns no trials reads the page as "this disease has no trials", when on those two paths ClinicalTrials.gov was never asked. The facts checker's `layers.l3_other_ways` guards the three named exceptions only, so it cannot notice a fourth. Also inside this round's newest text.
- NOT FIXED

## The checker, rebuilt by category

Method: `git archive HEAD` into `ver53/base`, harness `ver53/mut.py` with my own edits in `ver53/muts.py`, each applied alone, `check_facts.py --root <copy> --reference <data-engineering>` as its own process, file restored (confirmed afterwards with `diff -rq` against a fresh archive: identical). Baseline on the copy: `places: PASS 226, FAIL 0, GAP 0, ERROR 0 | PASS`, exit 0. 22 edits: 10 caught, 12 passed.

Caught (exit 1): V-M01 synonym "All questions get them."; V-M02 reordered clause (disease first); V-M03 "up to ten rs variant ids" (`says "ten" | true: ... rsid_cap: 2`); V-M04 "2 minutes for Pathogen Detection"; V-M04b "30 minutes" for the graph; V-M08 and V-M08b guarded sentence and whole paragraph deleted; V-M10c "Five tools cover that". (V-M03b, a TRUE edit "twenty" for "20", also fails: a false alarm, not a hole.)

### F-53-V02: a false sentence placed right after a guarded one passes; the whole-sentence rule fixed A03 only inside one sentence
- Severity: major (inside this round's fix `e0b4fbb2`, whose stated category is "a false clause after a guarded span")
- What: `sentence_problem` checks only the sentences a place's match touches, so the same false qualifier the adversary's M05 put after a comma is certified when it is put after a full stop, and on the KGX manifest that ships in every export.
- Reproduction:
  - V-M05, ArchitectureScreen.tsx: `Not every question gets them.<strong> Every gene question does, however it is named.</strong> A gene` -> `facts: 81 | stale 0 | ... places: PASS 226, FAIL 0, GAP 0, ERROR 0 | PASS`, exit 0. The page now says a gene named by an identifier gets layer 3, which the next sentence and the code (my probe: NCBIGene:672 plans none) contradict.
  - V-M09, ArchitectureScreen.tsx: `up to two rs variant ids. This happens only in Researcher mode. Not every` -> `PASS 226 ... | PASS`, exit 0. M05's exact falsehood, one full stop later.
  - V-M05b, ArchitectureScreen.tsx: the graph budget sentence kept, then a new `<StopText>` `That is per table; a query may bring back up to 5,000 rows in all.` -> `PASS 226 ... | PASS`, exit 0.
  - V-M09b, manifest.py `_LAYER_NOTE`: `... are not present in this file. A copy of every live record the search agent fetched for the seed is included beside nodes.tsv.` -> `PASS 226 ... | PASS`, exit 0. fix.md says the manifest is "checked whole, so a word added to either fails the check"; a sentence added passes.
- Why it matters: a later edit that qualifies a guarded fact in its own sentence ships green, and fix.md's table records A03 as "Fixed by category".
- NOT FIXED

### F-53-V03: the true wording kept anywhere a reader never sees still vouches for a false page; only top-level unused `const` was closed
- Severity: major (inside this round's fix `e0b4fbb2`, recorded as A05 "Fixed by category": "comments, docstrings and constants nothing uses are blanked first")
- What: `visible()` blanks comments and `_unused_constants` blanks top-level `const` declarations nothing reads (`check_facts.py:532-554`). Every other non-rendered carrier is still read as page text. In each case below the rendered paragraph was replaced with `Plan adds PubTator3, LitVar2 and ClinicalTrials.gov to every question, whatever it names.` (false three ways) and the true paragraph kept in the carrier named.
- Reproduction, each `places: PASS 226, FAIL 0, GAP 0, ERROR 0 | PASS`, exit 0:
  - V-M06b: an unused `function LegacyLayerThreeNote() { return (<StopText>...</StopText>); }` above `ArchitectureScreen`.
  - V-M07: `{false && (<>...true paragraph...</>)}` beside the false one.
  - V-M07b: the true paragraph in a `data-note="..."` attribute of the StopText that renders the false one.
  - V-M07c: `type _LegacyNote = "...true paragraph...";` at top level.
  - V-M07d: `const legacyNote = "...";` as an unused local inside `ArchitectureScreen`.
- Why it matters: the layer 3 stop can promise every question all three sources while the checker certifies the three facts that say otherwise (`layers.l3_triggers`, `l3_not_every_question`, `l3_other_ways`). A dead component or a `{flag && ...}` branch is a common real-world shape after a page rewrite, more common than an unused top-level constant.
- NOT FIXED

### F-53-V04: a guarded sentence moved to another part of the same page passes
- Severity: minor
- What: a place names a file, not where in it; `expect` counts matches in the whole file.
- Reproduction: V-M06, the layer 3 "Plan decides which of them a question gets ... searched another way." paragraph cut from the Layer 3 stop and pasted into the Layer 1 stop above "What the search agent calls to read it" -> `PASS 226 ... | PASS`, exit 0. Under Layer 1, "which of them" now reads as the graph tool.
- Why it matters: the page's words are all still true, but the reader sees them under the wrong layer. Low likelihood; filed because the brief names this category.
- NOT FIXED

### F-53-V05: factual sentences on both pages have no place at all, including the cite-or-refuse promise
- Severity: major (the card's contract is that the checker fails when any sentence about how the product works stops being true; fix.md's A07 row fixed three named sentences, not the category)
- Reproduction, each `places: PASS 226, FAIL 0, GAP 0, ERROR 0 | PASS`, exit 0:
  - V-M10d, ArchitectureScreen.tsx stop 4: `A claim with no such link is not cited, and an answer with nothing citeable behind it is refused rather than written.` -> `A claim with no such link is cited to the model's own knowledge, and an answer with nothing citeable behind it is written from the model's memory.`
  - V-M10, ArchitectureScreen.tsx stop 4: `Each carries its own time limit in code rather than one the model chooses.` -> `Each carries a time limit the model chooses for it on each question.`
  - V-M10b, InfoScreens.tsx About stop 3: `A call that reaches its limit stops there and says which limit it hit, rather than leaving you waiting.` -> `A call that reaches its limit is retried until it succeeds, however long that takes.`
- Why it matters: the reversed cite-or-refuse sentence is the product's trust claim, and the checker, which `/verify` runs, certifies the page with it reversed. fix.md's "limits" section names block-exempt structures and word-pinned sentences; it does not say that whole prose sentences on the two pages have no place. Not new code, but the card's stated outcome.
- NOT FIXED

### Self-test and mutation test, run by me
- `check_facts.py --self-test` on the worktree: `self-test: 226 of 226 comparisons proven to pass and to fail; 81 of 81 readers proven to follow a changed source; 14 parser cases; 0 failures` and `extension 238 of 238; removal 206 of 206; comment 194 of 194; unused 110 of 110; negation 264 of 264`, exit 0.
- `check_facts.py --mutation-test`: `mutation-test: 30 of 30 break-it edits caught`, exit 0. These are the registry's own edits (`MUTATIONS`), not mine.
- The self-test CAN fail, proven on a scratch copy of the engine: with `sentence_problem` forced to return "" it reports `131 failures`, `extension 206 of 238`, `negation 165 of 264`; with `_unused_constants` forced to return [] it reports `110 failures`, `unused 0 of 110`, exit 1. Engine restored and compared with `cmp`.
- What the self-test does not cover: its "unused" proof moves a statement into a top-level unused constant only, and its "extension" proof adds words inside the sentence only. F-53-V02 and F-53-V03 are the shapes one step outside each proof, which is why 226 of 226 and my 12 passes are both true at once.

### Verdicts on the checker findings (own edits, same harness)
- F-53-J03: FIXED. V-R01, CLAUDE.md `Layer 3: Enrichment APIs (PubTator3, ClinicalTrials.gov, apart from LitVar2)` -> `FAIL 1 ... NOT PASSED`, exit 1. `names_only` rejects any word outside `LIST_WORDS`, none of which negates.
- F-53-A04: FIXED. V-R02, one of five tool cards `budget: "15 s"` -> `PASS 221, FAIL 1 ... NOT PASSED`, exit 1 (was a silent drop to 201). Deletions V-M08 and V-M08b also FAIL.
- F-53-A06: FIXED for the sentences as written. V-M02 (reordered conditions), V-M03 ("up to ten"), V-R03 (manifest "only" -> "first") all FAIL. Two gaps remain beside it: the unnamed no-layer-3 paths (F-53-V01) and a sentence added to the manifest note (F-53-V02, V-M09b).
- F-53-A07: FIXED. V-R04 "Six stops" FAILs `about.stop_count`. The wider category, factual sentences with no place, is F-53-V05.
- F-53-A03: NOT FIXED as titled ("a false qualifier written after a guarded span"). Inside the sentence it is fixed (V-R05 `in total, per layer.` FAILs). After the full stop it passes: V-M09 `... up to two rs variant ids. This happens only in Researcher mode.` -> PASS 226, exit 0. The fix's own words, "fails a page whose guarded sentence gains a clause", are true; fix.md's "Fixed by category" is not. See F-53-V02. This sits inside this round's fix `e0b4fbb2`.
- F-53-A05: NOT FIXED as titled ("passes when the true wording survives anywhere in the file"). Comments and top-level unused constants are closed (V-R06, a JSX comment, FAILs 3 facts). An unused function, a `{false && ...}` branch, a `data-` attribute, a type alias and an unused local constant all still vouch (V-M06b, V-M07, V-M07b, V-M07c, V-M07d, each PASS 226, exit 0). See F-53-V03. This sits inside this round's fix `e0b4fbb2`.

### F-53-V06: the About walk still says BRCA1's live layers are searched at the same time as the graph; four of its calls go out after the graph returns
- Severity: minor (the J06 category, one sentence the fix round did not reach; About stop 3 just above it does describe the second round)
- What: `InfoScreens.tsx` JOURNEY_LAYERS n=1: "One query returns the stored links from BRCA1 to its diseases, while the live layers are searched at the same time." The fact `loop.layer_one_read_first` certifies "at the same time" from `asyncio.gather` alone.
- Reproduction: my probe `ver53/test_ver_rounds.py`, `plan_node` on "Which diseases are associated with BRCA1?" with NCBIGene:672 from mention BRCA1: 13 planned calls, 4 of them `_PlannedFollowUpCall` (round two): `ncbi_efetch pubmed_abstracts`, `pubtator_annotate pubtator_publications`, `ncbi_efetch clinvar_summary`, `ncbi_efetch omim_summary`. Act gathers them only after the first round, graph query included, has returned (`graph.py:7990`, `8035`). The same plan also carries two `cypher_query` calls (the second the GO terms context call).
- Why it matters: small; the walk is the worked example of that exact question, and the checker would pass the sentence whatever the second round did.
- NOT FIXED

## Privacy

`git diff origin/develop...HEAD | grep -n -E "<home-path>|@gmail|password"`: three hits, all read. Diff line 3225 is registry prose quoting the Integrations page ("exchanges the same email and password you use here for that token"); 4233 is the README stack row "argon2id password hashing"; 5065 is judge.md describing its own scan. No path, address or secret. A second grep for the owner's names, the checkout folder name and dotted IPv4 addresses returned nothing.

## Gates, run once by me

- Facts checker on the local files: `facts: 81 | stale 0 | not fully checked 0 | places: PASS 226, FAIL 0, GAP 0, ERROR 0 | PASS`, exit 0.
- `--self-test`: `226 of 226 comparisons proven to pass and to fail; 81 of 81 readers proven to follow a changed source; 14 parser cases; 0 failures`, exit 0. `--mutation-test`: `30 of 30 break-it edits caught`, exit 0.
- vitest, the five touched suites (About, Architecture, Integrations, events, events.persona), run on a `git archive HEAD` copy with the main checkout's `node_modules` linked in, since the worktree has none: `Test Files  5 passed (5)`, `Tests  63 passed (63)`, exit 0.
- `pytest tests/system_03_search_agent/tools/test_catalogue.py`: `6 passed`. Proven able to fail: with `_PATHOGEN_DETECTION_BUDGET` set back to 60.0 in a scratch copy, `FAILED ... test_timeouts_match_the_budgets_the_code_enforces`, `1 failed, 5 passed`.

## Verified by my own probes versus only read

- Ran: every plan-path claim of the layer 3 stop (15 `plan_node` cases, `ver53/test_ver_plan.py`), the round split for BRCA1 (`ver53/test_ver_rounds.py`), 28 checker edits of my own (`ver53/muts.py`: 22 by category plus 6 reviewer-category re-checks), the self-test's ability to fail (engine broken two ways), the catalogue test's ability to fail, the four gates above, the privacy grep.
- Read only: the per-tool timeouts behind About stop 3 (`ncbi_transport.DEFAULT_TIMEOUT_S`, the five tools' imports of it, `_TOTAL_BUDGET_S`), the export package's imports for "Layer 1 ... only" (graph modules only), the non-NCBI hosts of the layer 3 tools, J05's rule text, A09's removed clause.

## Verdict

Summary: J01, J02, J03, J04, J06, A01, A02, A04, A06, A07, A08, A09, A10, A12 FIXED. J05 and A11 OPEN AS NAMED, correctly out of scope (J05 needs a card, since nothing carries it). A03 and A05 NOT FIXED as titled: each was fixed for the reviewer's shape and the same falsehood passes one step outside it, inside this round's fix `e0b4fbb2` (the review loop's stop condition). New: V02, V03, V05 major; V01, V04, V06 minor.

The pages and the manifest are true on every path I ran, with V01 and V06 as small overstatements. The checker is what falls short of the card's contract: 12 of my 22 false edits pass it, the cite-or-refuse sentence among them.

MERGE WITH NAMED ITEMS: F-53-V02, F-53-V03 and F-53-V05 (checker holes, two inside this round's fix, so the owner decides between merging with a follow-up card or one more checker round), F-53-A03 and F-53-A05 (NOT FIXED as titled, the same holes), F-53-J05 (needs a card), F-53-A11 (product behaviour, needs a card), F-53-V01, F-53-V04, F-53-V06.
