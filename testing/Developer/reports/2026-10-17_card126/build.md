# Card 126 build: the disagree line under an ask floor

## The change

- File: `src/system_03_search_agent/synthesis/trust.py`, function `answer_trust_line`.
- The line is now "Sources disagree on at least one claim" when the outcome is `flag`, or when any high-risk claim has `triangulation == "discordant"` and belongs to a cited claim of the answer. Refuse (or no claims) still returns None first.
- `_SEVERITY` and the aggregate outcome are untouched; the answer stays "ask".
- Cited only: a trust counts only if its `citation_id` is the id of a claim in `claims`, the same list the function already reads.
- The docstring bullet for `flag` now names the new case.

## Places checked, none needed a change

- `frontend/src/components/screens/AnswerScreen.tsx` `TRUST_LINE_EXPLAINER`: describes "Sources cited", "Confirmed" and "Based on" lines and never mentions the disagree line, so it stays true.
- `src/system_03_search_agent/adapters/cli/render.py`: `_trust_line_text` prints the server's `done.trust_line` as sent; it does not key off the text.
- Reopened-answer path (`feedback/history.py`, `SavedAnswerScreen.tsx`, `data/models.py` line 236): the stored line is the one the server sent; the comment's example "Sources disagree on at least one claim" remains true. Nothing re-derives the line.
- `core/graph.py`, `adapters/web_sse/app.py`, `graphql`, `mcp`: pass the string through.

## Tests

New file `tests/system_03_search_agent/synthesis/test_trust_line_discordant_under_ask.py` (8 cases): case H shape; plain flag; low-risk discordant under ask keeps "Based on"; uncited discordant keeps "Based on"; insufficient keeps "; their values could not be compared"; floor-only ask keeps "Based on"; concordant keeps "Confirmed by 2 independent databases"; refuse gives None.

Run with the existing `test_trust_line_names_its_count.py`: `60 passed`. `ruff check` and `isort --check-only` clean on both touched Python files.

## Mutations (one property each, restored after)

- Drop the discordant check: `1 failed, 59 passed`, case H red.
- Check all claims instead of high-risk ones: `1 failed, 59 passed`, the low-risk case red.
- Let refuse through: `1 failed, 59 passed`, the refuse case red.

The frontend was not touched, so no frontend tests were run.
