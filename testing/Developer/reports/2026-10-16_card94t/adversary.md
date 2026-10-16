# Adversary report, card 94t (PR 246)

Method: real think, plan, act and write nodes with only the model and the two tools stubbed (probe outside the repository), plus live runs of queries 35, 36, 37 on the PR and on develop (about $0.07 in all, deepseek/deepseek-v4-flash and z-ai/glm-5.2).

### A-94t-01: a timed-out search still reads "error: 0 record(s)" in the failure reason and the tool_result summary
- Severity: minor
- What: the PR sets failure_kind to timed_out but leaves the summary as "{status}: {row_count} record(s)". Card 63's own comment says a failed search must not read as one that ran and found nothing, and names the kind in words ("timed out") for efetch.
- Reproduction: stubbed pathogen_detection returning status "timeout", then act_node. failed_searches = [{'tool': 'pathogen_detection', 'reason': 'error: 0 record(s)', 'kind': 'timed_out'}]. The efetch failure in the same run reads 'summary error: other failure'.
- Why it matters: the developer instrument and deploy log show a timeout as "error: 0 record(s)". The person is not affected: the note under the answer says "because it took too long".
- NOT FIXED

### A-94t-02: a timeout output that carried rows would be shaped as status error with rows
- Severity: unsure
- What: the schema allows isolates on a status "timeout" output. The shaping keeps the rows and only renames the status.
- Reproduction: PathogenDetectionOutput(status="timeout", isolates=[one isolate], isolate_count=1, total_available=1) through _layer_tool_output_to_structured_fields printed: TIMEOUT WITH ROWS -> error 1 1 1 (status, row_count, total_available, len(rows)). Both timeout builders in the tool (_deadline_exceeded_output, _isolate_search_timeout_output) return no isolates, so the real tool cannot reach this today.
- Why it matters: if a later change returned partial rows with "timeout", the tool_result would say "error: 1 record(s)" and the count would be inconsistent. Probe 1 (partial rows shown as complete) is otherwise clean: a cut scan with matches is status ok, "at least N" count, unchanged by this PR.
- NOT FIXED

### A-94t-03: after a timeout the top of the answer is a taxonomy-only summary; the unfinished note is last
- Severity: minor
- What: for the isolate question with the taxonomy lookup fine and the isolate search timed out, the answer shows "Taxonomy records found", "Found 1 taxonomy record for Escherichia coli", then the disclosure "Searching Escherichia coli isolates in Pathogen Detection for AMR genotypes starting blaCTX-M; ..." and, last, "The background search of Pathogen Detection did not finish because it took too long, so this answer may be missing sources from it. Ask again to retry."
- Reproduction: probe case timeout, taxfail False: trust ask, trust_line "Based on 1 source cited, not yet confirmed". Identical to a non-timeout error except the words "because it took too long". It never says no isolates were found, and the count line is absent (probe 2 clean).
- Why it matters: a reader who stops at the first heading sees only a taxonomy record. The disclosure sentence says "Searching ... isolates" with no result. Same on develop for any other failed search, so not a regression. The note could say the isolate list is missing, not "sources".
- NOT FIXED

### A-94t-04: the new test stops at Act
- Severity: minor
- What: test_pathogen_timeout_no_crash.py asserts only act_node's findings and failed_searches. Nothing asserts Write's note ("took too long"), the absent count sentence, or the trust outcome after a timeout.
- Reproduction: read of the test; my probe shows those three hold today (trust ask, note present, no "Pathogen Detection lists" line), so the behaviour is right but unpinned.
- Why it matters: a later change to _isolate_count_note (which relies on status not in ok/empty) could turn a timeout into a "lists 0 isolates, all shown" sentence with no test going red.
- NOT FIXED

### Checks that came back clean
- Probe 2: timeout never reads as "no isolates found". The empty case prints "Pathogen Detection lists 0 Escherichia coli isolates with these genes, all shown."; the timeout case prints no count line at all.
- Probe 3: timeout vs develop's error: both trust "ask", both total_cost_usd 0.0 in the stub run; wording differs only by "because it took too long". With the taxonomy lookup also failed, both refuse ("One of my searches did not finish ..."). Develop before the PR crashes Act (build report: literal_error), so there is no develop timeout behaviour to compare.
- Probe 4, live, nothing timed out, PR vs develop, same rows (row hash identical): q35 274a5e5b (2,716 Salmonella, trust answer), q36 bd835a59 (88,701, ask), q37 97a5648a (12,587, ask). Costs 0.0049 to 0.0073 per run. Citation event counts varied between runs of the same code (q35: 21, 25, 32; q36 and q37 21), so that is model variance, not the PR. Query 35 took 33.8 to 37.7 s on both, over the 20 s ceiling in memory, not caused by the PR. Count 2,716 differs from the 2,678 the test document states (snapshot drift, same on develop).
- Not exercised: a real timeout live (cannot be forced cheaply); only stubs.

Verdict: PASS. No finding blocks. Verified by my own probes: Act no longer crashes (stubbed, all five outcomes), Write wording, trust and cost, live equality on queries 35 to 37. Only read: the real tool's timeout builders return no isolates.
