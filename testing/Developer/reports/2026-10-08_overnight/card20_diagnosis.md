# Card 20 diagnosis: an isolate search can filter only by gene prefix

Base: develop at c916cfa3. Read-only diagnosis, no model calls made. The parked tag was read with `git show` and `git merge-tree` only; nothing was checked out.

## Table of contents

- [Status today](#status-today)
- [What a person sees](#what-a-person-sees)
- [The cause](#the-cause)
- [The smallest fix](#the-smallest-fix)
- [Overlap](#overlap)
- [Needs the owner](#needs-the-owner)
- [Proposed test query](#proposed-test-query)

## Status today

Still happens. The year and location filters exist only in commit 94b0ba41 (card 28, "narrow isolate_search by location and collection year"), reachable from the local tag `parked/phase-8.4-2026-09-25`. `git merge-base --is-ancestor 94b0ba41 develop` says it is not on develop. The develop schema `PathogenIsolateSearchInput` (`tools/pathogen_detection_schemas.py:228`) has only `taxon`, `amr_gene_prefixes` and `max_isolates`.

## What a person sees

- They ask `Show me the ones from 2023` after an isolate search, or `E. coli isolates with blaKPC from the USA since 2020`.
- The search runs on gene prefix alone. The year and the place are dropped. The disclosure line in the narrative (`isolate_search.disclosure`) does not say it dropped them, so the isolate table looks like an answer to the whole question.

## The cause

| Part | Evidence |
|---|---|
| The tool cannot filter | No year or location field on `PathogenIsolateSearchInput` (`pathogen_detection_schemas.py:268` onward), and the scan in `tools/pathogen_detection.py` matches only gene prefixes. The cell `collection_date` and `geo_loc_name` are already read and shown (`pathogen_detection.py:354`, `590`), just not used to filter. |
| The planner never carries them | `isolate_search.plan_calls` (`core/isolate_search.py:355`) builds the call from organism and prefixes only. |
| The work was parked | The tag holds 94b0ba41: 192, 186 and 134 changed lines in the three source files, plus tests, with a live proof (E. coli, blaKPC, USA, since 2020: 580 matches of 584,992 rows, exact count, 21.26 s). |

## The smallest fix

Split the parked commit in two.

| Half | What | Reuse |
|---|---|---|
| Tool side | Optional `location` (boundary-aware prefix of `geo_loc_name`) and `collection_year_min` and `collection_year_max` on the schema and the scan. Deterministic filtering over a cell: code verifying data. | Take from 94b0ba41. `git merge-tree` of that commit onto develop auto-merges all three source files; only `tests/system_03_search_agent/core/test_isolate_search.py` conflicts. |
| Where the values come from | The parked commit reads the year with five regexes ("since", "before", "between", "through", "in" plus four digits). Do not reuse that. It is a word-pattern decision, against the standing rule that a classifier model decides and code only verifies, and `in 2021` is the same bug class that limited a search to the year 2000 for "in 2000 patients" (F-8.2-J01). | Have the model that already tags entities in Think (`_ThinkExtractedEntity`, `core/graph.py:2934` area) or the Plan step return a structured year range and place. Code then verifies: integers inside 1900 to 2100, and the digits appear in the question text. Location text is mapped to the INSDC spelling ("USA", not "the United States") by the model, then verified against values present in the file. |

Also needed: say so in the disclosure line when a filter was asked for and could not be applied (a place the file does not spell that way).

| Item | Value |
|---|---|
| File fence | `tools/pathogen_detection_schemas.py` (`PathogenIsolateSearchInput`), `tools/pathogen_detection.py` (scan filter), `core/isolate_search.py` (`plan_calls`, `disclosure`), plus Think's entity extraction in `core/graph.py` for the model-filled values. |
| Answer path | Yes, it changes which isolates are returned and counted. |
| Dial position | 2 for the tool half. The model-filled half edits a Think prompt and structured output, still 2, but a stable-prefix change, so run the prefix-hash check. |
| Size | M for the tool half plus disclosure; L if the Think and Plan extraction is included. |
| Migration | No. |

## Overlap

- The tool half touches none of phase 8.7's list or the guardrail.
- The Think extraction half edits `core/graph.py` (not `_answer_tokens`, `_write_answer`, `write_node`, `act_node` themselves), so it is near but outside 8.7. The count sentence `count_sentence` is used by the Write step; leave it unchanged.
- Card 94 (the isolate answer table) runs in the same files. Check the board before starting.

## Needs the owner

Yes, one design choice: whether year and place come from the model in Think (cost: one more field in a call that already happens, no extra call) or from a separate small classifier call. The owner's own 2026-09-25 decision (card 28) already says the filters should exist. No migration, no package.

## Proposed test query

The existing query 41 (isolate query 9, `Show me the ones from 2023`) covers the year, and today says a year filter "is not built yet". When this ships, change its expected text. Add to section 5 of `testing/Test_queries_and_workflows.md`:

### An isolate search narrowed by year and place (card 20)

Queries to try:

- `Which E. coli isolates carry blaKPC genes in the USA since 2020?`
- After it, `Show me only the ones from 2023`.
- `E. coli isolates with blaKPC from Atlantis` (a place that is not in the file).

What you should see:

- Every isolate shown has a collection date in the stated years and a place starting with the stated country.
- The count sentence is exact for the narrowed set and names the year and place used.
- The last query says no isolates matched that place, or that the place could not be matched. It does not quietly search everywhere.
- Why it matters: a person asking for recent US isolates should not receive isolates from every year and country that merely look like an answer.
