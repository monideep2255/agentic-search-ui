# Card 94 verifier: the place half after the fix round

Fresh verifier, 2026-10-09. Branch `fix/card94-isolate-place-lookup` at `0e0d53d1`, base `develop` at `b01dee92`. Paths are relative to `<repo-root>`. No live model calls. Findings are appended as they are established.

## Findings

Checks established so far, each by my own probe (no finding yet):

- graph.py against `b01dee92`, every function compared by AST: only `_answer_parts` and its inner `grouped_listing` differ; `plan_node` is identical. The five hunks are two imports, the `places` list with the forced "Collected" label, the widened `zip`, and the cell built by `collected_with_place`. Query 42 in `testing/Test_queries_and_workflows.md` is untouched (the doc diff is the date line and the flagship entry only).
- Differential capture: develop's own versions of 20 test files run once on develop's source and once on this branch's source, every `_answer_parts` result recorded (440 calls each, random ids normalised). 437 are identical, across researcher (319), plain language (66) and clinical brief (52), covering Disease, Gene, SequenceVariant, Clinical trial, Publication, OntologyClass, Article, MedGen, OMIM, ClinVar and GEO groups. The 3 that differ are the three isolate tables, and only by the place text.
- Fix-round tests on `3174a51d`'s source (scratch archive): 11 failed, 2 passed (the blank cases), the failures being assertion failures on the old values. Here: pass. One mutation (case folding removed from `_is_placeholder`): 4 failed, restored with `git checkout`.
- Every isolate cell reads its own record: one write run, six isolates with six different places, at all three reading depths, gave per row "2013, <its own place>", "2013, USA: Unknown County", "2013, place not recorded" for "Not Collected", a 128 character place ending in "…", and "Not recorded" for both "missing: third party data" with date "missing" and "null" with no date.
- Markup in a place: that same run's real token events rendered through `useRunView` and `AnswerScreen`, and its real `answer_markdown_from` output rendered through `SavedAnswerMarkdown`, in jsdom (a scratch copy of the frontend outside the worktree). Place `<img src=x onerror="window.__pwn=1"> | **bold** [link](https://evil.example) \ end`: no `img`, no link to evil.example, no bold in any table, the saved row stays four cells, the cell text equals the value byte for byte, live and saved, all three depths. 6 passed. A place holding newlines and pipes stays one escaped markdown row in the saved answer.
- `raw/lookup_parked.patch` still applies (`git apply --check`).

### F-94-V-01: Placeholder words outside the fixed list still show as a place
- Severity: minor (unsure how often these occur in Pathogen Detection data)
- What: `_is_placeholder` matches an exact word list plus a "missing:" prefix. Other no-place forms pass through as if they were a place.
- Reproduction: `isolate_place("Pathogen Detection isolate", {"geo_loc_name": v})` then `collected_with_place("2013", ...)` gave "2013, not determined", "2013, not available", "2013, none", "2013, None", "2013, -", "2013, ?", "2013, N.A.", "2013, Unspecified", "2013, not recorded", and "2013, missing : x" (space before the colon). Every form the brief names (the five INSDC words, "missing: reason", NULL, unknown, N/A, NA, any case, blank) reads "place not recorded", and "USA: Unknown County" and "USA: Missing Creek" still show.
- Why it matters: a reader sees "2013, not determined" or "2013, -" where the product says "place not recorded" elsewhere. It names no wrong place, so nothing is made up, and develop showed no place at all, so it is not worse than develop for a person.
- NOT FIXED

No other defect found. Nothing here sits inside a defect of the fix round itself: the fix round's two changes (placeholder words, the cut mark) both behave as stated under my probes.

## Gates, run by me

| Gate | Result |
|---|---|
| `test_isolate_search_wiring.py`, `test_write_answer_structure.py`, `test_accession_wiring.py` and the seven synthesis files that import `answer_layout`, not integration | 394 passed |
| `ruff check`, no path | All checks passed |
| `isort --check-only --diff src tests services tracker alembic .claude .github` | exit 0, 2 files skipped by config |

## What I verified by probe and what I only read

- Verified by my own probe: `plan_node` identical to develop (AST); only `_answer_parts` changed; non-isolate tables unchanged at three depths (differential capture, 437 of 440 identical, the 3 others isolate only); per-row place, placeholder words, a real place containing such a word, the cut mark; markup as text live and saved; fix-round tests red on `3174a51d` and green here; one mutation caught; the gates above.
- Read only: query 42's text equals develop's (from the diff: the doc's only hunks are the date line and query 33); the lookup timings and crash reasons in `build.md`'s "Parked" table (live measurements I did not repeat, no live calls allowed); that `geo_loc_name` is at most 150 characters (schema).

## Verdict

PASS against the merge bar: nothing worse than develop for a person. The lookup is gone, every non-isolate table is unchanged, and the isolate cell shows when and where from the record's own fields. F-94-V-01 is minor and not worse than develop.

MERGE
