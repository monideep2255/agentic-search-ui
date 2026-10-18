# Card 54 diagnosis: a reopened long answer loses citations after the fiftieth

## Table of contents

- [What the reader sees](#what-the-reader-sees)
- [Every bound on the path](#every-bound-on-the-path)
- [Why the screen showed 49 and not 50](#why-the-screen-showed-49-and-not-50)
- [The right ceiling](#the-right-ceiling)
- [Size cost per stored row](#size-cost-per-stored-row)

## What the reader sees

A reopened long answer (HNF1A, 61 sources) lists 49 rows under "Based on 61 sources cited", and markers above [50] point at nothing. The REST citations export stops at 50 the same way.

## Every bound on the path

Path: live answer, then `citation` events, then the stored `interactions.citations` row, then the saved-answer reply and the history count, then the screen. The REST export reads the same events.

| Place | File and line | Bound | Verdict |
|---|---|---|---|
| Live display slots | `core/graph.py` `_MAX_FINDINGS_FOR_DISPLAY` (= `_PLAN_TOOL_CALL_ROW_LIMIT`, line 5369) | 100 | The true ceiling, keep |
| Capture truncation | `feedback/capture.py` line 53 `_MAX_CITATIONS`, applied at line 416 | 50 | Cause, raised |
| Stored row model | `feedback/contracts.py` line 200 `InteractionRow.citations` | `max_length=50` | Cause, raised |
| Saved-answer reply model | `adapters/web_sse/app.py` line 891 `SavedAnswerResponse.citations` | `max_length=50` | Cause, raised |
| Saved-answer slice | `adapters/web_sse/app.py` line 1124 `citations[:50]` | 50 | Cause, raised |
| REST export cap | `adapters/web_sse/app.py` line 271 `_MAX_CITATIONS_PER_RUN`, used at lines 1761 and 1841 | 50 | Cause, raised |
| MCP and GraphQL | `adapters/mcp/server.py` line 196 | 100 | Already correct |
| Database column | `alembic/versions/0001_user_data_schema.py` `interactions.citations` JSONB | none | No schema change needed |
| History count | `feedback/history.py` `_citation_count` | none, counts distinct pages of what is stored | Follows the stored list |
| Frontend saved-answer screen | `frontend/src/components/screens/SavedAnswerScreen.tsx` | none (no slice) | No change |

## Why the screen showed 49 and not 50

The stored list held 50 entries. The history count and the screen count distinct record pages, and gene 6927 was cited twice (markers "45, 49"), so 50 entries are 49 pages. The trust line is stored text from answer time and counted 61.

## The right ceiling

100. A live answer builds one citation per display slot, and the slots are capped at `_MAX_FINDINGS_FOR_DISPLAY`, 100. MCP and GraphQL already use 100 (phase 8.10). Anything lower drops citations a live answer showed. Anything higher is a number the run can never reach. One named constant, `MAX_CITATIONS_PER_ANSWER` in `feedback/contracts.py`, now feeds all five places. A test pins it to `_MAX_FINDINGS_FOR_DISPLAY`.

## Size cost per stored row

- A typical citation payload is about 500 bytes of JSON with a 200 character claim, and at most about 1.6 KB with the 1000 character claim maximum.
- At 100 citations that is about 50 KB typical and about 160 KB worst case per row, up from about 25 KB and 80 KB at 50. Only answers that actually cite more than 50 pay it.
- JSONB values over 2 KB go to out-of-line storage (TOAST) and are compressed. The history list reads the column to count pages, so it reads up to twice as many entries for those long answers only.
- `answer_markdown` has its own check constraint (32000 characters, alembic 0010) on a separate column. It is unaffected.
