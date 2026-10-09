# Card 37 judge report, round 1

Judge base: HEAD bcdfee5ea3ca97c418fd6c4f1e34ed44b94b7e6d, compared with origin/develop. Findings are written as they are established.

## Findings

### J-37-01: the citation for rs334 still takes its confidence from a near miss when the near miss is LitVar2's first match

- Severity: minor (outside this card's fence, present before the fix, not caused by it)
- Evidence: the fix filters the shaped rows only (`core/graph.py:4892` to `:4907`). The unfiltered typed output is still kept as `layer_raw_output=output` (`core/graph.py:8314`) and `_layer3_base_citation` calls `litvar2_build_citation(raw_output, ...)` (`core/graph.py:11811`), which reads `result.variant_matches[0]` for `assertion_confidence` (`tools/litvar2_lookup.py:1071` to `:1078`). The caller then overwrites `source_id`, `source_url`, `field` and `claim_text` but not `assertion_confidence` (`core/graph.py:11876` to `:11884`). Probe, two matches, rs334 second:

  ```
  rs334348 hedged rs334348 https://www.ncbi.nlm.nih.gov/research/litvar2/?query=rs334
  rs334 asserted rs334 https://www.ncbi.nlm.nih.gov/research/litvar2/?query=rs334
  ```

  The first line is the base citation when rs334348 is first: "hedged", from rs334348's own significance text. That confidence survives onto rs334's chip.
- Why it matters: rs334348 no longer appears as a row, but it can still decide whether rs334's citation reads as asserted or hedged.
- Smallest fix: a follow-up card, not this one. Pick the raw match whose `rsid` equals the row's `rsid` in `_layer3_base_citation` for `litvar2_lookup`, or carry the confidence through the row.

### J-37-02: two hand mutations of the filter stay green

- Severity: minor (neither is reachable on today's production path)
- Evidence: six mutations of `core/graph.py`, each run against `tests/system_03_search_agent/core/test_litvar2_exact_rsid.py` and restored with `git checkout`:

  ```
  == M1 filter removed
  3 failed, 2 passed in 2.50s
  == M2 prefix compare
  3 failed, 2 passed in 2.93s
  == M3 query not casefolded
  1 failed, 4 passed in 2.33s
  == M4 filter applied to non-rsid queries
  2 failed, 3 passed in 2.31s
  == M5 match side not casefolded
  5 passed in 2.20s
  == M6 fullmatch to match
  5 passed in 2.01s
  ```

  M5: the tool never gives an uppercase `rsid` a `source_url` (probe: `('RS334', 'litvar@RS334##', None)`), so the row is skipped before the comparison; the match-side `casefold` is unreachable, not a defect. M6: `re.match` would turn a query such as "rs334 HBB" into a filter that drops every row. Production queries are always a bare rs id from `_rsids_in_text` (`core/graph.py:5329`), so this cannot happen today, but no test holds the "a query that is not a bare rs id is left unfiltered" sentence for a query that starts with an rs id.
- Smallest fix: one test, `_input("rs334 HBB")` with matches rs334 and rs334348, asserting both rows remain.

## Checks with evidence

- Correctness, production path: probe through `_build_layer_tool_calls` (the planner), the real `litvar2_lookup` parse with a stubbed transport, and the shaping call exactly as `core/graph.py:8296` makes it. Question "What is rs334 and what condition is it associated with?", planned query `rs334`:

  ```
  raw: ['rs334348', 'rs334', 'rs334353', 'rs334773'] | shaped: ok ['rs334']
  raw: ['rs334348', 'rs334353'] | shaped: empty []
  ```

  "Compare rs334 and rs3343", first LitVar2 call: `raw: ['rs334', 'rs3343'] | shaped: ok ['rs334']`. The asked variant's own record still shows; the near misses do not.
- Matches with no `rsid`, or an uppercase one, have no `source_url` from the tool and were already skipped before this change: `[(None, 'litvar@rs334##', None), ('RS334', 'litvar@RS334##', None)]`. No regression there.
- Other consumers: the shaped rows feed findings and the citation lookup `_layer3_row_for_synth_finding` (`core/graph.py:11764`), which matches by `source_url`, so a dropped row is never cited. The raw output still reaches the citation builder: J-37-01.
- Comparison is an exact string equality of the whole rs id after `strip().casefold()`, not a numeric parse. Equal to a parsed-number compare except for a leading zero (rs0334), which `_rsids_in_text` can produce but dbSNP never issues. Not filed.
- Security: no free-text decision; the regex reads the tool's own planned query, itself extracted by `_RSID_PATTERN` (`core/graph.py:5439`). No query, no log line added. `ruff check` on both changed Python files: "All checks passed!".
- Tests: `test_litvar2_exact_rsid.py` "5 passed in 2.33s"; `tests/system_03_search_agent/core` "1390 passed, 56 skipped, 2 warnings in 54.71s".
- Restore check: `git diff --stat HEAD` empty after the mutations.

## Verdict

MERGE. J-37-01 and J-37-02 are minor and can follow as their own card.
