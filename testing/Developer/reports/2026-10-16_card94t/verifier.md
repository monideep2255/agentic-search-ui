# Card 94t fresh verifier

Fresh verifier, bossman dial position 2, 2026-10-16. Branch fix/card94-timeout-no-crash at 79030b05 (fix 609c9faf); origin/develop at 0fadfdf9 (card 115 merged).

## Findings

### V-94t-01: The branch merges cleanly into origin/develop and the merged tree passes the three gates
- Severity: none (verification record)
- What: in a scratch worktree at origin/develop 0fadfdf9, `git merge --no-ff 79030b05` completed with no conflict (merge base bce08af9; develop's card 115 change touches no file the branch touches). Merged tree b8d9f358 (scratch only, never pushed).
- Reproduction, on the merged tree: `ruff check` "All checks passed!", exit 0. Gate 2's command `isort --check-only --diff src tests services tracker alembic .claude .github` "Skipped 2 files", exit 0. `pytest tests/system_03_search_agent/core tests/system_03_search_agent/tools -m "not integration" -q`: `3204 passed, 132 skipped, 24 deselected, 5 warnings in 98.20s`, exit 0. Imports were confirmed to resolve to the worktree's own `src` (pyproject `pythonpath = ["src", "."]`), not the main checkout.

### V-94t-02: Queries 33 to 37 with nothing timing out give byte-identical event streams on develop, the branch and the merge
- Severity: none (verification record)
- What: my own probe (outside the repository) runs the real `think_node`, `plan_node`, `act_node` and `write_node` in order for each of queries 33 to 37's exact text, with only the model (litellm), `pathogen_detection`, `ncbi_efetch` and `cypher_query` stubbed. Every event (think, plan, tool_call, tool_result, token, citation, trust, cost, done) is dumped as JSON with timing keys, random call-id suffixes and the random persona fields removed.
- Reproduction: tool status "ok" (20 isolates, counts 140,476 / 3,100 / 2,678 / 88,025 / 1,500): `cmp dev br` and `cmp dev merge` both silent, 189,612 bytes, 88 events per query. The probe is real, not a no-op: Plan sent `['blaCTX-M']`, `['blaCTX-M']`, `['blaCTX-M-15']`, `['blaKPC', 'blaNDM', 'blaOXA-48', 'blaVIM', 'blaIMP']`, `['mcr']` per query, and each answer carries "Pathogen Detection lists 140,476 Escherichia coli isolates with these genes; the first 20 in the snapshot are shown." (and the analogues). Two develop runs are identical to each other (determinism control). Status "empty" and status "error" are also byte-identical across the three trees.
- Why it matters: the owner's bar, nothing worse than develop, holds for every non-timeout outcome I could drive.

### V-94t-03: Develop crashes Act on a tool-reported timeout for all five isolate queries; the branch and the merge answer with the timed-out note
- Severity: none (verification record)
- What: same probe as V-94t-02, the stubbed `pathogen_detection` returning the tool's own isolate_search timeout shape (status "timeout", `isolate_count=0`, `total_available=0`, `truncated=True`, `scan_complete=False`).
- Reproduction, develop 0fadfdf9, queries 33, 34, 35, 36, 37: each `CRASH in act ValidationError: 1 validation error for ToolResultPayload`. Write never runs.
- Reproduction, branch 79030b05 (merge b8d9f358 byte-identical): each query completes; `tool_result` pathogen_detection `status error`, `summary 'error: 0 record(s)'`; `failed_searches` `[{'kind': 'timed_out', 'tool': 'pathogen_detection', 'reason': 'error: 0 record(s)', ...}]`; trust `ask`, "Based on 1 source cited, not yet confirmed". Query 33's answer ends "The background search of Pathogen Detection did not finish because it took too long, so this answer may be missing sources from it. Ask again to retry."
- Only read, not run: that develop's whole-run wrapper turns the Act exception into the person-facing "This query failed unexpectedly before it could complete." (`run.py` `_crash_fallback_events`, trust `refuse`). I drove the nodes, not `run_streaming`.

### V-94t-04: A timeout never reads as "nothing found", and rows on a timeout output are not shown or counted as complete
- Severity: none (verification record)
- What: across the five branch timeout answers I searched the person's answer text for "lists 0", "no isolates", "none found", "nothing found", "found 0", "0 isolates", "all shown" and any "Pathogen Detection lists" count line: none present in any of the five; "did not finish because it took too long" present in all five. Control: the "empty" outcome on the same probe prints "Pathogen Detection lists 0 Escherichia coli isolates with these genes, all shown.", so the search would have caught a confident zero.
- Reproduction, partial rows (status "timeout" carrying 3 isolates, not producible by the real tool today, both builders set `isolate_count=0`): develop `CRASH ValidationError`; branch answer shows no isolate, no count line, trust `ask` "Based on 1 source cited, not yet confirmed", the timed-out note. The `tool_result` frame reads `status error, summary 'error: 3 record(s)', result_count 3` (developer instrument only; same shape as the adversary's A-94t-02, not re-filed).

### V-94t-05: Mutating one property (where the failure kind is read from) goes red, and green on restore
- Severity: none (verification record)
- What: a property the judge did not mutate. In `_execute_planned_call` I changed the failure-kind test from the raw tool output to the shaped status, `failure_kind=("timed_out" if shaped["status"] == "timeout" else None)`, a plausible refactor slip that can never fire because the shaped status is already "error".
- Reproduction, mutated: the author's `test_pathogen_timeout_no_crash.py` `3 failed in 4.07s`; my probe on query 33 gives `failed_searches` kind `'other'` and the note "The background search of Pathogen Detection did not finish, so this answer may be missing sources from it. Ask again to retry." (the "because it took too long" is lost).
- Reproduction, restored with `git checkout -- src/system_03_search_agent/core/graph.py`, `git status --short` empty: `3 passed in 3.62s`; probe kind `'timed_out'` and "did not finish because it took too long" back.

### V-94t-06: No other caller can carry a "timeout" status past the new mapping
- Severity: none (verification record)
- What: on the merged tree, the only importer of `PathogenDetectionOutput` outside the tool is `core/graph.py`: the shaping function (the fix) and `_isolate_count_note`, which returns None for any status outside ok and empty. No other module calls `pathogen_detection(` directly. The new reports and test carry no local machine path (grep for home, private and worktree paths: no match).

## Verdict: PASS

Verified with my own probes: the branch merges cleanly into origin/develop 0fadfdf9 and the merged tree passes ruff, isort gate 2 and the core and tools unit suite (3204 passed); develop crashes Act on a tool-reported timeout for queries 33 to 37 and the branch and merge answer with "did not finish because it took too long", trust `ask`; no timeout answer reads as nothing found or shows a count, including when a timeout output carries rows; queries 33 to 37 with ok, empty and error outcomes are byte-identical across develop, branch and merge; one mutation (failure kind read from the shaped status) goes red in the author's test and in my probe, green on restore. Only read, not run: develop's whole-run crash fallback text ("This query failed unexpectedly before it could complete."), and a real live timeout (none forced). No finding sits inside a fix made during this phase. Open minors from the judge and adversary (J-94t-03, J-94t-07, A-94t-01 to A-94t-04) stand as filed; none makes anything worse than develop for a person.
