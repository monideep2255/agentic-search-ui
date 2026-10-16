# Judge report, card 94t (pull request #246)

Judge, dial position 2, one round. Diff bce08af9...609c9faf. Findings are appended as established.

## Findings

### J-94t-01: Claim 1 holds. Develop loses the answer on a timeout status, the branch keeps it and shows the existing note
- Severity: none (verification record)
- What: my own probe drives the real `act_node` (stubbed `cypher_query` returning one Gene row, stubbed `pathogen_detection` returning status "timeout", mode isolate_search), then the real `write_node` with only the Synth call faked (the `test_write_answer_structure` helpers), the Act output's `failed_searches` and `layer3_raw_outputs` fed in.
- Reproduction, develop (bce08af9): `ACT RAISED: ValidationError 1 validation error for ToolResultPayload`, raised in `_close_tool_call` (graph.py 8838) via `_run_one` and `_gather_planned_calls`. Act never returns, so there is no answer.
- Reproduction, branch (609c9faf): `tool_result: pathogen_detection status= error summary= 'error: 0 record(s)'`; `failed_searches: [{"tool": "pathogen_detection", "layer": "layer_2_api", "reason": "error: 0 record(s)", "kind": "timed_out", "source": ""}]`; the cypher finding stands. Write emits the note token: "The background search of Pathogen Detection did not finish because it took too long, so this answer may be missing sources from it. Ask again to retry." Final trust_signal outcome `ask`; done `trust_line: 'Based on 3 sources cited, not yet confirmed'`.
- Why it matters: the person's words are met for this path.

### J-94t-02: Claim 3 holds on Write. A tool-reported timeout gives the same answer stream as develop's existing timed-out search
- Severity: none (verification record)
- What: three arms on the branch through the same probe: TIMEOUT (tool returns status "timeout"), HANG (tool sleeps past Act's own budget, patched to 0.2 s, develop's existing `_error_outcome(failure_kind="timed_out")` path), ERROR (tool returns status "error"). Every Write event (tokens, citations, trust signals, cost, done) dumped with timing keys removed, then diffed.
- Reproduction: `diff stream_TIMEOUT stream_HANG` is empty for isolate_search, isolate_lookup and cluster_snp_neighbors, and for isolate_search with `isolate_question` set (both then show "Searching Escherichia coli isolates in Pathogen Detection for AMR genotypes starting blaCTX-M." and the timed-out note). The probe is not blind: `diff stream_TIMEOUT stream_ERROR` differs on exactly one line, the note ("...did not finish because it took too long..." against "...did not finish, so...").
- Both arms: final trust outcome `ask`, `trust_line: 'Based on 3 sources cited, not yet confirmed'`, `total_cost_usd: 1.9999999999999998e-05`, `total_tool_calls: 2`. HANG on develop gives the same values.
- Why it matters: the timed-out search is floored to "not yet confirmed" and costs the same as any other failed search.

### J-94t-03: The Act-level stream record of a tool-reported timeout reads "error: 0 record(s)", not "timed out" as develop's other timed-out search does
- Severity: minor
- What: the new path sets `failure_kind="timed_out"` but keeps the generic summary `f"{status}: {row_count} record(s)"`. So the `tool_result` frame's `summary` and `failed_searches[].reason` say "error: 0 record(s)", while develop's harness-timeout path for the same tool says "call did not complete within its 150s budget". `_FAILURE_KIND_WORDS`' own comment (card 63) names this shape, "reads as a search that ran and found nothing", as the defect it fixed for ncbi_efetch, whose summary carries `_failure_kind_words(...)`.
- Reproduction (branch, my probe): TIMEOUT arm `tool_result: pathogen_detection status= error summary= 'error: 0 record(s)'`, reason "error: 0 record(s)"; HANG arm `summary= 'call did not complete within its 0.2s budget'`.
- Why it matters: not the person's answer screen. The note under the answer is chosen from the typed `kind` and is identical (J-94t-02); the web client parses `summary` but I found no screen that renders it. It is what the developer instrument and the deploy log show, so a timed-out Pathogen Detection scan reads there as a failed search with no cause. Develop's ERROR arm has the same summary, so this is consistency with an existing pattern rather than a regression. Also noted, unsure whether it matters: the shaped error dict keeps `truncated: True` and `total_available: 0` (the HANG error dict has neither key); the Write stream diff shows no consumer reacts to them today.
- NOT FIXED

### J-94t-04: Claim 2 holds. No other status or tool changes, and no consumer treated "timeout" specially
- Severity: none (verification record)
- What: `git diff bce08af9...609c9faf --stat` touches graph.py (10 lines), the new test and build.md only. Grepping `src/` and `frontend/src` for `"timeout"` comparisons finds no reader of a shaped tool status equal to "timeout"; the hits are other vocabularies (graph HTTP transport, ncbi_transport, audit, call_log, jev_client, decide). Only `PathogenDetectionOutput.status` allows "timeout" (`^(ok|empty|error|timeout)$`); every other tool schema is `^(ok|empty|error)$`, so the new `failure_kind` expression in the shared Layer 2/3 branch can only fire for pathogen_detection. The one reader of the raw output, `_isolate_count_note`, returns None for any status outside ok and empty, unchanged and still fed the raw "timeout" (layer_raw_output is the unshaped tool output). Tool code, schema, cache and call budget untouched.
- Reproduction: the grep output above; ERROR and HANG arms give byte-identical Write streams on develop and on the branch (J-94t-02's runs).

### J-94t-05: Break it. Each of the two changed properties goes red when mutated alone, and green on restore
- Severity: none (verification record)
- Mutation A, the trust-critical one: `status = "error"` changed to `status = "empty"` (a timeout reported as "nothing found"). My probe: `tool_result ... status= empty summary= 'empty: 0 record(s)'`, `failed_searches: []`, no note, done `trust_outcome: 'answer'`, `trust_line: 'Based on 3 sources cited'` (no "not yet confirmed"). The author's test: `3 failed`. Restored with `git checkout`: `3 passed`.
- Mutation B: `failure_kind=None`. My probe: kind `"other"`, note "The background search of Pathogen Detection did not finish, so this answer may be missing sources from it. Ask again to retry." (loses "because it took too long"). The author's test: `3 failed`. Restored: `3 passed`, `git status --short` clean.
- Why it matters: the test discriminates both halves of the change, including the one that would turn a cut-off scan into a confident absence.

### J-94t-06: Gates green on the branch, run by the judge
- Severity: none (verification record)
- Reproduction, in a detached worktree at 609c9faf: `ruff check` "All checks passed!", exit 0. Gate 2's own command `isort --check-only --diff src tests services tracker alembic .claude .github` exit 0. `pytest tests/system_03_search_agent/core tests/system_03_search_agent/tools -m "not integration" -q`: `3204 passed, 132 skipped, 24 deselected, 5 warnings in 96.30s`, the same counts as build.md.

### J-94t-07: The build report's live runs do not exercise the timeout path
- Severity: minor (evidence gap, not a code defect)
- What: build.md's live table (queries 33 and 42) shows answers with isolates and no errors, so the Pathogen Detection scan finished in time in both. Neither run produced a status "timeout", so they show no regression on the success path and say nothing about the fix. The fix itself is shown offline only, by the author's test and by this judge's probes (J-94t-01, J-94t-02, J-94t-05).
- Why it matters: anyone reading the live table as proof that a timed-out search keeps the answer would be wrong. No live call is needed to settle it, because the tool's timeout output is a fixed constructor (`_deadline_exceeded_output` and the isolate_search timeout builder in pathogen_detection.py, both `isolate_count=0`, `truncated=True`), and the probe uses that same shape.
- NOT FIXED

## Verdict: SHIP

Verified with my own probes: develop crashes Act on a timeout status (ValidationError in `_close_tool_call`); the branch keeps the answer and shows "The background search of Pathogen Detection did not finish because it took too long, so this answer may be missing sources from it. Ask again to retry."; the Write stream, trust (`ask`, "not yet confirmed") and cost are byte-identical to develop's existing timed-out search in all three modes and with an isolate question set; each changed property goes red alone; the gates pass. Only read, not run: that no screen renders the `tool_result` summary (J-94t-03), and that the cache and call-budget code is unaffected. J-94t-03 and J-94t-07 are minor and do not block. No finding sits inside a fix made during this phase.
