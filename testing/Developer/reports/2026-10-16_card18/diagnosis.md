# Card 18 diagnosis: a record with several sentences shows as several list rows

Diagnosis only, 2026-10-16, read against develop `78c68c1c`. Paths are relative to `<repo-root>`. No code was changed and no model was called. One local probe called `_answer_tokens` with made-up findings; its script sits in the worker's scratchpad and is not committed. This re-checks `testing/Developer/reports/2026-10-08_overnight/card18_diagnosis.md`, whose line numbers are stale.

## Table of contents

- [Status today](#status-today)
- [What a person sees](#what-a-person-sees)
- [The cause](#the-cause)
- [The smallest fix](#the-smallest-fix)
- [What each surface prints after the fix](#what-each-surface-prints-after-the-fix)
- [Tests](#tests)
- [Overlap with tonight's other cards](#overlap-with-tonights-other-cards)
- [Needs the owner](#needs-the-owner)
- [Test query](#test-query)

## Status today

Still happens, in the same narrow case. Phase 8.7 did not touch the merge rule; it moved it. `_answer_tokens` is now a one-line wrapper over `_answer_parts` (`src/system_03_search_agent/core/graph.py:12849`), and the merge lives in the inner `merge_into` (`core/graph.py:13167`).

Probe: three sentences citing one PubMed record (`pm-1`), through `_answer_tokens`, at both depths.

| Sentence length | Depth | Rows | Row text lengths | Cells on each row |
|---|---|---|---|---|
| About 76 characters | Researcher | 1 | 219 | title, PMID:12345678 |
| About 76 characters | Plain language | 1 | 219 | title |
| About 436 characters | Researcher | 2 | 866, 433 | the same two cells on both rows |
| About 436 characters | Plain language | 2 | 866, 433 | the same one cell on both rows |

In the long case both rows carry marker `pm-1` and identical cells.

## What a person sees

A researcher asks about a topic whose papers have long abstracts. The sources list shows the same paper two or three times in a row, with the same title, PubMed number and citation number. It reads as if the answer was not checked.

## The cause

| Link | Evidence |
|---|---|
| Each grounded sentence of a long abstract carries the record's marker, so one paper reaches the listing as several sentences | `core/graph.py:13367` (`plain_listing` loop) and `13406` (`grouped_listing`) |
| `merge_into` folds a repeat into the first row when cells agree | `core/graph.py:13167` to `13208` |
| It refuses when the joined text passes 1000 characters, and the repeat becomes its own row | `core/graph.py:13200`: `if len(ids) > 20 or len(text) > 1000: continue` |
| 1000 is the answer token's schema cap | `contracts/events.py:396`: `text: str = Field(..., max_length=1000)` (marker list cap 20 at line 397) |
| Both listings fall through to a new row when `merge_into` returns false | `core/graph.py:13380` to `13384` (`plain_listing`) |

The row on the web shows the cells, not the text (`frontend/src/components/screens/AnswerScreen.tsx:532` to `538`), so the repeat is pure duplication there.

The parked helper (`04_9c46d708_*.diff`, `merge_sentences_by_citation`) is still not worth lifting: `merge_into` already does its job plus page key, cell agreement and citation order. It would add a second merge path.

## The smallest fix

In `merge_into`, when the repeat brings no new citation marker and its cells agree, fold it into the first row even if the joined text would pass 1000. The first row's text stays as it is (the repeat's sentence is not appended when it does not fit). The schema cap stays at 1000.

| Item | Value |
|---|---|
| What changes, in the person's words | A paper with a long abstract is listed once, not two or three times |
| File fence | `src/system_03_search_agent/core/graph.py`, inner `merge_into` of `_answer_parts`, lines 13190 to 13208 only |
| Logic | After computing `ids`: if `len(ids) > 20`, skip as now. Compute `adds_marker = any(m not in first.token.marker_ids for m in ids)`. If the joined text fits in 1000, append as now. If it does not fit and `adds_marker` is false, keep `first.token.text`, set cells and fields as now, return True. If it does not fit and `adds_marker` is true, skip as now (a new citation never gets dropped) |
| Answer path | Yes (it changes which tokens the stream carries) |
| Dial | 2, runnable behaviour. The event schema is untouched; raising `max_length` would be dial 3 |
| Size | S |
| Migration, package, event schema, new setting | None |

Ways it could make an answer worse, and how a test catches each:

| Risk | Catch |
|---|---|
| A repeat that adds a citation is folded and the citation vanishes | Test: second sentence cites another marker, joined text over 1000, so two rows remain |
| Two different records are folded | Test: two PubMed records with long sentences keep two rows (key is the page) |
| A mapping row's disease cell and chips disagree | The existing `mapping_cell != merged[at]` check runs before the new branch; keep it first |
| The first row's text is cut mid sentence | The fix never truncates; a test asserts `len(text) <= 1000` and that it ends on a whole sentence |

## What each surface prints after the fix

| Surface | Today (long case) | After the fix | Does a reader lose a sentence? |
|---|---|---|---|
| Web | Two rows, one title each | One row | No. The row shows cells and chips, never the sentence |
| Saved-answer markdown | Two rows with the same cells and `[1]` | One row. `answer_markdown_from` prints cells plus markers for a row, and never the token text (`feedback/capture.py:214` to `240`) | No |
| Command line | Row 1 text, then row 2 text, so every sentence prints (`adapters/cli/render.py:890` to `896` writes `payload.text`) | Row 1 text only. The later sentence that did not fit no longer prints | Yes, in the long case only: a sentence the command line prints today stops printing. Citation number set is unchanged |

The sentence is still grounded; the citation's own `claim_text` does not depend on the row. The cost is one repeated sentence about a paper already listed in the command line. Whether the sentence also appears in the summary prose is not settled here and does not change the call.

## Tests

Add to `tests/system_03_search_agent/core/test_write_answer_structure.py`, beside `test_one_record_cited_by_two_claims_is_one_row` (line 888), same shape (`_answer_tokens` with one PubMed `SynthFinding` and `CitationPayload`, both depths):

| Test | Fails on develop | Passes on the fix |
|---|---|---|
| `test_long_abstract_sentences_of_one_record_are_one_row`: three sentences of about 436 characters citing `pm-1`; assert exactly one row at each depth, `len(text) <= 1000`, `marker_ids == ["pm-1"]` | Yes (2 rows) | Yes |
| `test_long_repeat_with_a_new_citation_stays_its_own_row`: second sentence cites `pm-2` on the same page; assert the citation is still on a row | Passes already | Must keep passing |
| `test_two_records_with_long_sentences_stay_two_rows` | Passes already | Must keep passing |

## Overlap with tonight's other cards

| Card | Their fence | Overlap with this fix |
|---|---|---|
| 30 | `synthesis/answer_layout.py` a note; `core/graph.py` a Think classifier decision and `_write_answer` | `_write_answer` and `_answer_parts` are neighbours in `graph.py`; no shared lines. Merge-order conflict only if the note is added inside `_answer_parts` listing code |
| 105 | `core/breadth_plan.py`, `tools/cypher_templates.py`, Plan wiring | None |
| 37, 38 | `tools/cypher_templates.py`, `tools/cypher_query.py`, `synthesis/answer_layout.py`, `synthesis/findings.py`, `core/graph.py` `_layer_tool_output_to_structured_fields` and `write_node` | `write_node` calls the listing code; they may change what findings reach it (more papers, more repeats) but not `merge_into`. Rebase risk in `graph.py` only |
| 8 | The trust-line wording | None |

The fix touches only `merge_into`, so it can ride with any of them. Run the 37 and 38 tests after it, since they change which rows exist.

## Needs the owner

Yes, one small choice. In the long case the command line would stop printing the later sentence of an already listed paper.

| Option | Cost in plain words |
|---|---|
| A (recommended): fold, keep the first sentences only | The list is clean on every surface. A command-line reader sees fewer repeated sentences about one paper, never a missing paper or citation |
| B: keep every sentence for the command line with a continuation token that is not a row | Nothing lost, but a new token shape that the web and the markdown must ignore. Size M, and it touches the event contract's meaning (dial 3) |
| C: leave it | Duplicate rows stay for long abstracts only |

Recommendation: A. The sentence is a repeat of a paper already named and cited, and a researcher would rather not see the paper twice.

## Test query

Existing query 75 in `testing/Test_queries_and_workflows.md` ("A papers list reads as clean prose, with no record repeated", line 1566) covers it. Propose one added line under "What you should see", as the 2026-10-08 diagnosis did:

```markdown
- In Researcher, no paper appears on two rows of its table, even when its abstract is long; each row has its own title or PubMed number.
```
