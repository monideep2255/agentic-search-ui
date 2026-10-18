# w2-notes: say what was searched and what failed (cards 94 group B, 91, 77)

Branch `fix/card94-91-77-say-what-was-searched`. Paths are relative to `<repo-root>`.

## Change in plain words

| Card | Before | Now |
|---|---|---|
| 94, group B | The isolate disclosure (organism, gene prefixes searched, what a family left out) reached only the Think narrative | The same sentence is a note under the answer (`_isolate_disclosure_note`, `core/graph.py`), built from `isolate_search.disclosure`, so nothing new is decided in code |
| 91 | "One of the background searches did not finish" named no source and no reason | `_build_unfinished_search_note` names the kind of source from the typed `tool` and `source` keys (PubMed, the knowledge graph, ClinicalTrials.gov, NCBI records, and so on) and, when every failed call has the same typed kind, the reason: NCBI busy gives "Ask again in a minute", too slow gives "took too long". With nothing typed it is the old sentence. The outage note is unchanged |
| 77 | A resolved disease whose MedGen name lookup failed planned the single graph call and said nothing | `plan_node` sets `disease_lookup_failed`; `write_node` adds the note "I could not look up this condition's name, so I did not search the literature or clinical trials for it. Ask again to retry." What is searched is unchanged |

State key `disease_lookup_failed` added to `core/state.py`.

## Tests

New file `tests/system_03_search_agent/core/test_say_what_was_searched.py`, 9 tests. Red proof: with `src` restored to the base commit, 8 of 9 fail (the ninth is the "nothing typed keeps the old sentence" guard, which is meant to pass on both). Each has a populate sibling (an ordinary answer or a lookup that worked carries no such note).

Changed expectations, because the sentence they pinned is now more specific by design: `test_write_failed_search.py` (4 tests) and `test_breadth_wiring.py` (the timeout test). No check was loosened; they now assert the source and reason are named.

## Gates

- Gate 2 (isort) and gate 3 (ruff, whole repository): green.
- Gate 4 (unit suite): 6531 passed; the only failures in the full run were 6 tests needing a local Postgres on port 5432 (`test_no_cost_channel` 3, `test_think_retry` 3), which fail the same way with no change of mine, plus the 6 tests above that I updated and re-ran green.

## Not covered

- No live runs: the lead's test queries 33, 36 and 25 on develop are the gate.
- Which notes show for a rate limit depends on the call recording `kind`; a failure recorded as `other` gets the source name but no reason.
- The wording of the isolate note is the existing disclosure sentence, capitalised; the expected wording in queries 33 and 36 (why blaTEM and blaSHV were left out, prefixes named) comes from each family's own `omitted` text, which is unchanged.
