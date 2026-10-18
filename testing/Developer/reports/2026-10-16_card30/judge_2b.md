# Card 30 step 2b judge

Pull request #269, branch `fix/card30-variant-classifications-shown`, commits `6498efd7` and `14571f3a` on develop `655e9dfe`. Code, tests, local probes and a handful of free read-only ClinVar ESummary calls through the product's client; no model call, no spend.

## Table of contents

- [Findings](#findings)
- [Checks](#checks)
- [Break it](#break-it)
- [Verdict](#verdict)

## Findings

(Filed as established.)

### J-30b-01, major: on the command line, MCP and GraphQL a fully classified list loses step 1's line and shows no classification

- Where: the classification reaches the page only through `cells` (`with_variant_classification`, `src/system_03_search_agent/synthesis/answer_layout.py:425` to `:439`; `record_status_or_year` and `plain_record_label`, read at `src/system_03_search_agent/core/graph.py:13442` and `:13544`). A row token's `text` is still the grounded sentence ("SequenceVariant ClinVar:1, name: c.1A>G (p.Xaa1Yaa) [1]. "). The line is dropped on every surface once every graph variant is classified (`variant_classification_note(synth_findings, set(variant_classifications))`, `core/graph.py:15020`).
- Who reads `text` and never `cells`: the command line prints `payload.text` (`src/system_03_search_agent/adapters/cli/render.py:890` to `:896`), its JSON mode builds `"answer": joined_text(self._answer_parts)` (`render.py:1448`), MCP builds `raw_answer_text = joined_text(answer_parts)` (`src/system_03_search_agent/adapters/mcp/server.py:1270`), and GraphQL imports the same `joined_text` (`src/system_03_search_agent/adapters/graphql/fold.py:97`). `grep -n cells` over `adapters/cli`, `adapters/mcp` and `adapters/graphql` finds nothing. The saved answer does read `cells` (`src/system_03_search_agent/feedback/capture.py:190` onward), so it is fine.
- Evidence: `<scratchpad>/card30b_judge/test_zz_judge_ab_probe.py` runs the same Write cases on develop's base `655e9dfe` and on the branch, with the lookup returning every variant; `joined_text` over the token payloads, as those three surfaces do:

```
graph|asks_classification|full develop: has_line=True has_Pathogenic=False has_Benign=False
graph|asks_classification|full branch: has_line=False has_Pathogenic=False has_Benign=False
layout|variants|plain_language|full develop: has_line=True ...
layout|variants|plain_language|full branch: has_line=False has_Pathogenic=False has_Benign=False
layout|variants|researcher|full develop: has_line=True ...
layout|variants|researcher|full branch: has_line=False has_Pathogenic=False has_Benign=False
```

- What the person sees: on `s3 "Which BRCA1 variants are pathogenic?"`, or through an MCP agent, develop prints 40 variant names and then "ClinVar's classification of these variants ... was not retrieved, so this list does not say which are pathogenic." The branch prints the same 40 names and no line and no classification. Tonight 40 of 40 BRCA1 variants resolved (probe below), so this is the normal case, not an edge. The "ask" verdict stays (`core/graph.py:15035` to `:15039`), but the one sentence that says why is gone, and the list under "which are pathogenic" reads as the answer again: the card's own hazard, back on three surfaces.
- Worse than develop: yes. A sentence develop shows is lost on three surfaces, and the owner's acceptance ("the line itself still goes once every shown row carries a classification") does not cover a surface where no row carries one. Inside the card's fence in one round: either give text surfaces the value (for example a code-built suffix on the row token's text, outside the grounded sentence) or keep the line for a request that does not read cells. A test that runs `joined_text` over a fully classified list and asserts either every value or the line would pin it.

### J-30b-02, major: under the variant-to-disease table, card 23's line now says the classification "is not shown here" directly beneath a column showing it

- Where: card 23's line, `VARIANT_TO_DISEASE_SOURCE_NOTE` in `src/system_03_search_agent/synthesis/answer_layout.py` ("Each row lists the conditions the variant's ClinVar record names; the record's classification (for example pathogenic, benign or uncertain) is not shown here."), emitted whenever a `SequenceVariant` table is mapped (`variant_to_disease_source_note`, same file). The branch adds the "ClinVar classification" column to that same table (`_ROW_TYPE_COLUMNS`, `answer_layout.py:654`, read through `record_status_or_year`, `core/graph.py:13544`) and leaves the line as it is.
- Evidence: `<scratchpad>/card30b_judge/test_zz_judge_table_probe.py`, the step 1 HNF1A shaped rows (`_FOLDED_VARIANT_ROWS`, `_FOLDED_GENE_ROW`) at Researcher, lookup returning "Pathogenic", on develop `ec547c2a` with the pull request's diff applied:

```
table_header ["Variant", "Identifier", "Associated disease(s)", "ClinVar classification"]
table_row ["variant number 1", "ClinVar:1", "Maturity-onset diabetes of the young", "Pathogenic"]
table_row ["variant number 2", "ClinVar:2", "None named: the ClinVar record says not provided", "Pathogenic"]
note Each row lists the conditions the variant's ClinVar record names; the record's classification (for example pathogenic, benign or uncertain) is not shown here. ...
```

- What the person sees: query 79, "What diseases are caused by variants in the HNF1A gene?", at Researcher: a table whose last column gives each variant's ClinVar classification, and one line below it saying the classification is not shown. On develop that line is true.
- Worse than develop: yes, a stated fact on the page becomes false, on a gate query (79). The builder's develop comparison ran the folded HNF1A table with the lookup returning nothing, which is why it did not show. Inside the fence in one round: make card 23's line drop its classification clause when the table carries the column (or only for the rows that do), and pin it with a Write test at Researcher on the folded rows with the lookup returning values.

### J-30b-03, minor: near the 20-call ceiling the lookup can take the slot develop gives the condition name lookup

- Where: the task starts at `core/graph.py:14040`, before `await resolve_concept_ids(curie_fallback_curies)`, and the fold's condition names are looked up afterwards (`condition_names = await resolve_concept_ids(fold_condition_ids)`, a few lines below). `_requests_allowed` reads the count once, before its request (`variant_classifications.py`, `_requests_allowed`); the transport charges each attempt just before it goes out (`src/system_03_search_agent/tools/ncbi_transport.py:1605`).
- Evidence: `<scratchpad>/card30b_judge/ceiling_race_probe2.py`, no network (`httpx.AsyncClient.get` faked), Write's order: a fallback MedGen lookup, then the fold's MedGen lookup, with the classification task started first on the branch:

```
branch=False made_before=18 requests_reached=['medgen', 'medgen'] calls_made_after=20
branch=True made_before=18 requests_reached=['medgen', 'clinvar'] calls_made_after=20
```

  With one lookup only (`ceiling_race_probe.py`), the MedGen request charges first and the classification is the one refused, so develop's lookup keeps its slot.
- Reach: only when Write starts at 18 calls (or 17 with a 100 variant list), with both a fallback name lookup and a fold lookup to make, which is query 79's table shape. The person then sees disease codes or an empty reason in "Associated disease(s)" where develop shows names. I could not measure how often a Write starts at 18 calls without live runs.
- Worse than develop: yes, in that narrow case. Fixable in the fence: start the task after the name lookups have charged, or leave their slots out of `_requests_allowed`.

### J-30b-04, minor: the lookup's task is not cancelled when Write ends before awaiting it

- Where: `classification_task` is created at `core/graph.py:14040` and awaited at `:14083`; nothing cancels it if a stop or an exception ends Write in between (three awaits sit between them). Step 1's own decision task is dropped in `write_node`'s `finally`; this one is not.
- Effect: after a stop, up to two ESummary requests may still go out, bounded by the 4 s timeout, and their result is dropped. Nothing reaches the person.
- Worse than develop: no.

### J-30b-05, minor: about 0.3 to 0.8 s added at the median, all of it before the listing; up to 4 s on a slow NCBI

- Measured through the product's client, 40 BRCA1 ids, no model call: 0.61 s, 0.78 s, 0.32 s, 0.32 s (mine); the builder's 0.27 s, 0.28 s and 2.32 s (a 429 and the transport's retry). 40 of 40 resolved every time.
- Do they run together: only when a name lookup makes a request. For the BRCA1 shape no finding is a MedGen or MeSH fallback and no row is folded, so `resolve_concept_ids` and `resolve_descriptor_ids` return without a request and the whole lookup time is added. The await sits before the listing is built (`core/graph.py:14083` against the listing at `:14266`), so the records reach the screen that much later.
- Worst case: `_REQUEST_TIMEOUT_S = 4.0` per request, two requests in parallel, so 4 s; develop's MedGen lookup has no timeout of its own and relies on the transport's 15 s.
- Worse than develop: not at the median (under the owner's "about a second"). The tail is the owner's to accept; a 1.5 s timeout would bound it near the decision's wording.

### J-30b-06, minor: no test pins that the germline block, and only it, is read

- Mutation M2 (`<scratchpad>/card30b_judge/mutate.py`): `_classification_of` reads `oncogenicity_classification` first and falls back to `germline_classification`. Result: GREEN, `472 passed`. Every fake record in `tests/system_03_search_agent/synthesis/test_variant_classifications.py` carries a germline block alone (`_record`, line 28 onward).
- Why it matters: real BRCA1 records carry both. ClinVar 3257800 has germline "Pathogenic" and oncogenicity "Likely oncogenic"; 4849514 has oncogenicity "Likely oncogenic" and an empty germline (probe below). A later edit that read the wrong block would put a somatic oncogenicity word under "ClinVar classification" and stay green.
- Worse than develop: no; the code reads the germline block today. One fake record with a germline and an oncogenicity block, and one with oncogenicity alone, would pin it.

## Checks

| Check | Result | Evidence |
|---|---|---|
| The value is the one ClinVar's record holds | Yes. ESummary's `germline_classification.description`, stripped, nothing else (`_classification_of`, `variant_classifications.py`). For the 40 BRCA1 variants of the saved run, the resolver's value equals the raw ESummary's germline text 40 of 40, and each raw record's `title` equals the graph row's name (one graph row has no name) | `<scratchpad>/card30b_judge/live_probe.py`: `resolved 40 of 40`, `value mismatches where resolved: 0`; 23 Conflicting classifications of pathogenicity, 15 Uncertain significance, 2 Pathogenic, the diagnosis's figures |
| Germline, somatic, oncogenicity | Germline only. A record with a somatic or oncogenicity classification and an empty germline one is unread, so its row stays as develop's and the line stays (ClinVar 4852577 "Tier III - Unknown", 4849514 "Likely oncogenic": `product_reads: null`). A record with both shows the germline word (3257800: germline "Pathogenic", oncogenicity "Likely oncogenic", shown "Pathogenic") | `<scratchpad>/card30b_judge/odd_probe.py` with `BRCA1[gene] AND somatic[origin]` |
| A record with several conditions | ESummary's germline description is ClinVar's aggregate over them (1000551 has 3 trait sets and reads "Conflicting classifications of pathogenicity"), the same word the record page shows | `live_probe_out.json`, `germline_traits` |
| Against the record pages | Each page's "Germline Classification" shows the value shown: 1000183 "Uncertain significance", 1012155 "Pathogenic" (page also says "no assertion criteria provided", which the cell does not carry), 3257800 "Pathogenic" with "Likely oncogenic" under "Somatic Oncogenicity", 373892 "no classification for the single variant", 5016453 "VUS-mid" | five pages fetched to `<scratchpad>/card30b_judge/web/`, text extracted |
| ClinVar's own odd text | Shown verbatim, as the lead decided: "no classification for the single variant" (3 BRCA1 records, ClinVar's own germline text and the page's) and the newer "VUS-mid" and "VUS-high" (1 each in BRCA1's first 200) | `odd_probe.py` tallies |
| Joined by record id | Yes. Keyed by ESummary's own `uid` (`summary`, `ncbi_eutils_actions.py:1153` onward, `id=uid`); the graph CURIE's number is the ClinVar VariationID, which is the uid (titles above). A uid twice with different values is dropped | M1 and M6 red |
| Failure classes leave develop's row | Yes. Through the real `summary` and transport, network faked: 429 twice `{}` in 1.09 s, 503 `{}` 1.10 s, connect error `{}` 1.10 s, hang `{}` 4.00 s, 200 with an ERROR body `{}`, HTML body `{}`, a per uid error entry dropped and its neighbour kept. At 19 calls with a 429, the retry hits the ceiling, `CallBudgetExceededError` is caught, `{}`, `calls_made=20` | `<scratchpad>/card30b_judge/failure_probe.py` |
| The 20 call ceiling | Never passed: `_requests_allowed` makes no request at 20 and one at 19, and the transport charges each attempt. See J-30b-03 for the slot it can take | M4 red; `failure_probe.py` ceiling row |
| Speed | 0.3 to 0.8 s at the median, run alone for the BRCA1 shape; 4 s worst case (J-30b-05) | live timings |
| Column, Plain label, four cell cap, slice A1's closed table | One new key in the closed table, `("SequenceVariant", "clinvar_classification")`, matched on the exact row type; the column is the table's status slot, so the widest variant table is Variant, Identifier, Associated disease(s), ClinVar classification, four cells, inside `TokenPayload.cells` `max_length=4` (`contracts/events.py:428`). An unread row gets an empty cell. Plain reads "name, ClinVar classification: value" | A/B probe tokens; table probe header; M11, M12 red |
| Citation of the shown value | The cell sits on the variant row, whose marker cites that row's own ClinVar variation page (`_clinvar_url`, `tools/cypher_provenance.py:234`), the page that shows the classification. No citation is added or changed, the done payload (trust line, counts, decisions) is identical, claim trust is identical, and the record stays in the "Knowledge graph" Sources group although its classification was read live | A/B probe: `citations_same=True done_same=True claims_same=True` in all 21 cases |
| Writer input | Unchanged. Every writer call's messages are identical between develop's base and the branch, with and without classifications | A/B probe: `writer_same=True` on the 9 Write path cases; `build_synth_findings` and `build_synth_messages` untouched |
| Event schema | Unchanged | `git diff origin/develop...HEAD --stat -- src/system_03_search_agent/contracts/` prints nothing |
| Floor: not asked, no decision | "answer", as develop | A/B: `nodecision` and `not_applicable` rows `answer->answer` with every mapping |
| Floor: late or failed decision | No floor: `_classification_asked` and `_read_late_decision` are untouched by this diff, and step 1's tests for both pass | `test_card30_no_floor_without_the_decision`, `test_card30_a_decision_still_running_past_the_grace_is_not_a_floor` in the run below |
| Floor: rs334's answer | No floor and no lookup: a dbSNP `Variant record` is not a graph `SequenceVariant`, and a `clinical_significance` finding lifts it | `test_card30b_rs334_style_answer_is_unchanged`; M9 red |
| Floor: a fully classified list | "ask", the line gone, claim trust unchanged, per the lead's decision | A/B `graph/asks_classification/full`: `ask->ask`, notes 1 to 0; M8 red |
| No regression where no variant is listed | Byte identical: gene rows at both depths, every mapping | A/B `layout/genes/*` rows `events_same=True` |
| Merges onto today's develop | Clean onto `ec547c2a` (card 8's trust line); the touched tests pass there too | `git merge-tree` clean; run below |

Commands, in `<worktrees>/card30b-judge` at `14571f3a`:

| Command | Result |
|---|---|
| `pytest -q tests/system_03_search_agent/synthesis/ core/test_graph.py core/test_write_answer_structure.py` | `1174 passed, 10 skipped, 1 xfailed in 33.96s` |
| The same plus `adapters/cli/test_s3_as_printed.py` and `adapters/mcp/`, on develop `ec547c2a` with the diff applied | `1381 passed, 10 skipped, 1 xfailed, 2 warnings in 95.32s` |
| `ruff check` (gate03) | `All checks passed!` |
| `isort --check-only --diff src tests services tracker alembic .claude .github` (gate02) | exit 0 (`Skipped 2 files`) |
| gate01 compile and import | exit 0 |
| `ruff format --check` on the two new files | `2 files already formatted` |
| The same lint gates on the merged tree | `All checks passed!`, isort exit 0 |

## Break it

`<scratchpad>/card30b_judge/mutate.py`, one property per run over the four touched test files, the file restored and compared byte for byte after each; `git status --short` empty afterwards.

| Mutation | Result |
|---|---|
| M1 join by position | RED, `test_classification_joins_by_record_id_with_records_shuffled` |
| M2 read the oncogenicity block first | GREEN (J-30b-06) |
| M3 tidy the value | RED, the same join test |
| M4 ignore the call ceiling | RED, `test_at_the_ceiling_no_request_is_made` |
| M5 no timeout | RED, `test_a_hung_request_is_cut_off` |
| M6 an ambiguous id keeps the last value | RED, `test_two_records_with_one_id_and_different_values_are_ambiguous` |
| M7 the line drops when any variant is classified | RED, `test_the_line_stays_until_every_shown_variant_has_a_classification` |
| M8 the floor back on the line | RED, `test_card30b_a_fully_read_list_drops_the_line_and_keeps_the_ask` |
| M9 the floor ignores a shown classification field | RED, `test_card30_no_floor_when_the_answer_shows_a_classification` |
| M10 any layer gains the value | GREEN, equivalent today: only graph rows carry `SequenceVariant`, and only their CURIEs are looked up |
| M11 Plain label without the value | RED, `test_card30b_plain_language_keeps_the_classification_after_the_name` |
| M12 no column for the value | RED, `test_card30b_researcher_table_shows_each_classification_and_drops_the_line` |
| M13 one request at most | RED, `test_one_request_per_fifty_and_no_more_than_two` |
| M14 100 ids per request | RED, the same test |
| M15 the final listing without the values | RED, `test_card30b_a_partly_read_list_keeps_the_line_and_the_floor` |
| M16 the early listing without the values | RED, `test_card30b_researcher_table_shows_each_classification_and_drops_the_line` |
| M17 control characters accepted | RED, `test_an_empty_or_odd_value_is_unread[Patho\ngenic]` |
| M18 any prefix with a numeric id accepted | GREEN, equivalent today: Write passes graph `SequenceVariant` CURIEs only, all `ClinVar:`; no test uses another prefix with a numeric id |
| M19 the note ignores the classified set | RED, `test_card30b_researcher_table_shows_each_classification_and_drops_the_line` |
| M20 the lookup asks for every finding | RED, `test_card30b_no_graph_variants_makes_no_request` |

No test reads the text surfaces (J-30b-01) or card 23's line beside a filled column (J-30b-02); both findings came from probes, not from a mutation.

## Verdict

The lookup does what the owner decided on the web page and in the saved answer. It shows ClinVar's germline classification word for word, joined by record id. Every failure leaves develop's row, and it stays under the call ceiling, the event schema and the writer's input. The citations, trust line, counts and claim trust do not change. The floor holds on every path the lead named.

Two things are worse than develop, and both can be fixed inside the card's fence in one round:

- J-30b-01: on the command line, MCP and GraphQL, a fully classified list loses step 1's line and shows no classification.
- J-30b-02: at Researcher, card 23's line says the classification "is not shown here" under a column that shows it.

J-30b-03 is worse only in a narrow case near the call ceiling. J-30b-04 to J-30b-06 are not worse than develop.

VERDICT: FIX FIRST
