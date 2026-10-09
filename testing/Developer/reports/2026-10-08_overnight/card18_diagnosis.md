# Card 18 diagnosis: a record with several sentences shows as several list rows

Diagnosis only, 2026-10-08 overnight, read against `develop` at `c916cfa3`. Paths are relative to `<repo-root>`. No code was changed and no model was called. One local probe called `_answer_tokens` directly with made-up findings; its script is not committed.

## Table of contents

- [Status today](#status-today)
- [What a person sees](#what-a-person-sees)
- [The cause](#the-cause)
- [The parked helper](#the-parked-helper)
- [The smallest fix](#the-smallest-fix)
- [Overlap with phase 8.7 and the guardrail](#overlap-with-phase-87-and-the-guardrail)
- [Needs the owner](#needs-the-owner)
- [Proposed test query](#proposed-test-query)

## Status today

Mostly fixed on develop, by two commits made for other cards. One case is left.

| Case | Develop today | Fixed by |
|---|---|---|
| A record whose sentences together fit in 1000 characters | One row | `e5052b1b` (2026-10-05, "List one row per record when two claims cite it"), then `180825dd` (2026-10-07, card 104, #205) |
| A record whose sentences together pass 1000 characters | Several rows, the same title, identifier and citation chip on each | Not fixed |

Probe, three sentences all citing one PubMed record, run through `core.graph._answer_tokens` at both depths:

| Sentence length | Depth | Rows | Row text lengths |
|---|---|---|---|
| About 76 characters each | Researcher | 1 | 228 |
| About 76 characters each | Plain language | 1 | 228 |
| About 436 characters each | Researcher | 2 | 872, 436 |
| About 436 characters each | Plain language | 2 | 872, 436 |

In the long case both rows carry the same cells (`['x', 'PMID:12345678']` at Researcher) and the same marker (`['pm-1']`).

## What a person sees

Asking about a topic whose papers have long abstracts, a person can see the same paper listed twice or three times in a row in the sources table. Each row has the same title, the same PubMed number and the same citation number. It looks like the answer was never checked.

## The cause

| Where | What it does |
|---|---|
| `src/system_03_search_agent/core/graph.py:12237`, `merge_into` (inside `_answer_tokens`) | A repeat of a shown record joins the first row when every cell agrees. |
| `core/graph.py:12266` to `12267` | `if len(ids) > 20 or len(text) > 1000: continue`. When the joined text would pass 1000 characters, the merge is skipped and the repeat becomes its own row. |
| `src/system_03_search_agent/contracts/events.py:383` | `text: str = Field(..., max_length=1000)` on the answer token. This is why the merge stops at 1000. |
| `core/graph.py:12436` (`plain_listing`) and `12596` to `12611` (`grouped_listing`) | Both call `merge_into`; when it returns false, both emit a new row. |

Each sentence of a long abstract is grounded on its own and carries the same record marker (item 11.34, by design). So a long abstract that survives as three sentences reaches the listing as three repeats of one record. The web row shows the record's label and chips, not the token's text (`frontend/src/components/screens/AnswerScreen.tsx:369`), so the reader sees only the repeated title.

## The parked helper

`merge_sentences_by_citation` on `parked/phase-8.4-2026-09-25` (`9c46d708`, `synthesis/answer_layout.py`) merges by `citation_id` with no length cap. Develop's `merge_into` already does the same job and more (page key, cell agreement, mapping cells, citation order). Lifting the helper would add a second merge path. Do not lift it.

## The smallest fix

In `merge_into`, when the repeat brings no new citation and its cells agree, fold it into the first row even when the joined text would pass 1000 characters. The first row keeps its text as it is. Nothing a web reader sees is lost, since the row shows the same title, identifier and chip.

| Field | Value |
|---|---|
| Files and functions | `src/system_03_search_agent/core/graph.py`, `_answer_tokens`, the inner `merge_into` (lines 12237 to 12278); a test in `tests/system_03_search_agent/core/test_write_answer_structure.py` beside `test_one_record_cited_by_two_claims_is_one_row` (line 888) |
| Answer path | Yes |
| Dial position | 2, runnable behaviour |
| Size | S |
| Migration, package, event schema | None. Raising the 1000-character cap instead would be an event-schema change, dial 3. |

The cost to say plainly: the command line and the saved-answer markdown print a row's text, so they would print the first sentences of that record and not the later ones. The sentences still back the answer's citation (`claim_text`, card 57). If the owner wants the command line to keep every sentence, the alternative is a continuation token that is not a row, which is M.

## Overlap with phase 8.7 and the guardrail

| Fence | Phase 8.7 | Guardrail |
|---|---|---|
| `core/graph.py` `_answer_tokens`, `merge_into` | Yes: `_answer_tokens` is on tonight's rewrite list | None |

Build it after 8.7 merges, against 8.7's `_answer_tokens`.

## Needs the owner

No. The fix only stops a visible duplicate; it adds no decision. The command-line trade above is small enough to state in the build report.

## Proposed test query

Existing query 75 ("A papers list reads as clean prose, with no record repeated") covers it, if one line is added under "What you should see":

```markdown
- In Researcher, no paper appears on two rows of its table, even when its abstract is long; each row has its own title or PubMed number.
```
