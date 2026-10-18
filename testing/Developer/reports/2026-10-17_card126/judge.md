# Card 126 judge: the disagree line under an ask floor

One round, dial position 2. Branch `fix/card126-disagree-line`, commit 6a8af489. Findings are written as they are established; the verdict is at the end.

## Findings

### J-126-01: the owner's own example, ClinVar "Pathogenic" against dbSNP "Benign" with both rows from the graph, still never says the sources disagree

- Severity: major (acceptance gap; not worse than develop)
- What: triangulation decides independence by `_origin_of`, which returns the TOOL name for any field other than `curie` (`synthesis/trust.py:353` to `366`). Two graph rows, one ClinVar page and one dbSNP page, both come from `cypher_query`, so `triangulate` (`trust.py:368` to `401`) finds no independent origin and returns `insufficient`, never `discordant`. The new clause (`trust.py:788` to `793`) keys on `triangulation == "discordant"`, so it never fires for this shape, with or without a floor.
- Reproduction: `<scratchpad>/probe_chain.py`, which runs write_node's own chain (`trust_for_claims` as at `core/graph.py:15000`, `_apply_conflict_flags_to_claim_trusts` as at `15038`, `aggregate` as at `15041`, an ask floor as at `15132` to `15170`, then `answer_trust_line` as at `15615`). Case A, two `cypher_query` findings, `clinical_significance` "Pathogenic" on `clinvar/variation/17661` and "Benign" on `snp/rs80357713`. Branch and develop print the same:
  `A graph+graph ClinVar/dbSNP | floor=True | outcome=ask | trusts=[('c-1', 'high', 'insufficient', 'ask'), ('c-2', 'high', 'insufficient', 'ask')] | line='Based on 2 sources cited from ClinVar and dbSNP; their values could not be compared'`
- The builder's test `test_discordant_high_risk_claim_under_an_ask_floor_says_sources_disagree` uses exactly these two findings (both `tool="cypher_query"`, `test_trust_line_discordant_under_ask.py:17` to `36`) but hand-builds `ClaimTrust("c-1", "high", True, "discordant", "flag")`. Production would never produce that trust from those findings, so the test proves the function, not the card.
- Why it matters: the card's sentence (`testing/UI_fix_plan.md` row 126) names this pair. A person whose two cited graph records disagree reads "their values could not be compared" beside two values that plainly can be compared. The root cause predates this card (`_origin_of`'s docstring says a graph ClinVar row and a live ClinVar fetch are one origin, while the code makes them two, and makes graph ClinVar and graph dbSNP one). Outside the card's file fence; the owner decides whether card 126 is done without it.
- Not worse than develop: develop prints the identical line.
- NOT FIXED

### J-126-02: the disagree line now fires when the record that disagrees is not cited, leaving the reader one source they can open

- Severity: major (unsure whether a person is worse off: the warning is true but cannot be traced)
- What: `triangulate` compares a cited claim against every prepared finding, `synth_findings` (`core/graph.py:15000`), cited or not. When the disagreeing record is left out of the answer, `omitted_findings` is non-empty and the `ask` floor at `core/graph.py:15132` fires, so this shape always arrives under a floor, which is exactly the case card 126 changes. The new "cited only" test checks the wrong side: it requires the DISCORDANT CLAIM to be cited (`trust.citation_id in cited_ids`, `trust.py:791`), never the record it disagrees with.
- Reproduction: `<scratchpad>/probe_chain.py` case D: the cited claim is a graph ClinVar "Pathogenic" row; the uncited prepared finding is a live dbSNP "Benign" row.
  - Develop: `D uncited dbSNP Benign | floor=True | outcome=ask | trusts=[('c-1', 'high', 'discordant', 'flag')] | line='Based on 1 source cited, from ClinVar'`
  - Branch: `D uncited dbSNP Benign | floor=True | outcome=ask | trusts=[('c-1', 'high', 'discordant', 'flag')] | line='Sources disagree on at least one claim'`
- Why it matters: the owner's decision reads "When cited databases disagree" (`DECISIONS.md`, 2026-10-17, card 126 row) and the builder's comment says "Cited claims only" (`trust.py:787`). Here a person sees "Sources disagree on at least one claim" over a Sources list holding one ClinVar page, with nothing on screen that disagrees with it. The project's V-22-01 rule for the "Confirmed" line (count only what the reader can open) is the mirror of this. Rare: the findings tail normally cites every left-out finding (`core/graph.py:15114` to `15124`), so this needs a finding the tail could not ground, or no tail.
- Unsure: the statement is true about what the system read, and an incomplete-answer note accompanies it. The owner should say whether an untraceable "disagree" is wanted.
- NOT FIXED

### J-126-03: the "cited only" clause is a no-op in production, and its comment claims a property the code does not deliver

- Severity: minor
- What: in production `claim_trusts` is built from `grounding.claims` (`core/graph.py:15000`, `trust_for_claims` iterates `claims` and copies each `claim.finding.citation_id`, `trust.py:516` to `533`), `_apply_conflict_flags_to_claim_trusts` keeps every `citation_id` (`core/graph.py:12275` to `12290`), and `answer_trust_line` receives the same `grounding.claims` (`core/graph.py:15615`). So every trust's `citation_id` is in `cited_ids` by construction and `trust.citation_id in cited_ids` (`trust.py:791`) is always true. The comment at `trust.py:787`, "Cited claims only: the trusts must belong to a claim in this answer", reads as a guard on what the reader can open; what matters for that (J-126-02) is unguarded.
- Reproduction: every production-chain case in `<scratchpad>/chain_wt.out` shows each trust's id among the cited claims. Mutation M4 below (drop `and trust.citation_id in cited_ids`) leaves every production-chain probe line byte identical and turns exactly one unit test red, the one that hand-builds a trust with id `c-99` that no claim carries.
- Why it matters: a confident comment above a check that never bites is the class `Review_rounds.md` names ("a comment that claims a property is a claim to be tested"). The test pins an unreachable input.
- NOT FIXED

### J-126-04: the fix names one mechanism, triangulation, not the category; the other path that says "sources disagree" still loses the line under a floor

- Severity: minor (not worse than develop)
- What: two mechanisms set a claim's outcome to `flag`: `decide` for a discordant high-risk claim (`trust.py:413`), and Section 7.2's graph-versus-live conflict check, which floors a claim at `flag` and leaves its `triangulation` untouched (`core/graph.py:12275` to `12290`). Without a floor both read "Sources disagree on at least one claim". Under a floor the branch rescues only the first, because the clause tests `triangulation == "discordant"` (`trust.py:790`) rather than the claim's own `outcome == "flag"`. `Review_rounds.md` Rule 2 rejects a fix that enumerates instances where a category exists.
- Reproduction: `<scratchpad>/probe_chain.py`, branch:
  - Case J, a graph ClinVar row "Pathogenic" and a live fetch of the same record "Likely pathogenic" (high risk, `concordant` by bucket, `flag` by the conflict check): `floor=False ... line='Sources disagree on at least one claim'`, `floor=True ... line='Based on 1 source cited, from ClinVar'`.
  - Case F, the same with a low-risk field (`chromosome` "17" against "13"): `floor=False ... 'Sources disagree on at least one claim'`, `floor=True ... 'Based on 1 source cited, from ClinVar'`.
  - Develop prints the same four lines.
- Why it matters: the same answer, one record's graph copy and its live copy giving different values, says "Sources disagree" or says nothing depending on whether an unrelated search also failed. That is card 126's own complaint, on the sibling path. Whether a same-bucket difference (Pathogenic against Likely pathogenic) or a low-risk one counts as "disagree on a high-stakes fact" is the owner's reading; the inconsistency is the finding.
- NOT FIXED

### J-126-05: the high-risk restriction is also unreachable in production, so its test pins an input production never builds

- Severity: minor
- What: `decide` gives every low-risk claim `triangulation="insufficient"` (`trust.py:445` to `452`), so a low-risk discordant trust never exists. `test_discordant_low_risk_claim_does_not_trigger_the_warning` hand-builds `ClaimTrust("c-1", "low", True, "discordant", "ask")`.
- Reproduction: mutation M3 below (iterate every trust instead of `high`) turns that one test red and leaves every production-chain probe line identical to the unmutated branch ("probe chain: identical to unmutated branch").
- Why it matters: harmless today; it is a guard on an impossible input, recorded so nobody reads the test as covering a real case.
- NOT FIXED

## Break it, one property at a time

Run in `<scratchpad>/wt` (detached at 6a8af489) by `<scratchpad>/run_mut.sh`: mutate `synthesis/trust.py`, run `test_trust_line.py`, `test_trust_line_names_its_count.py`, `test_trust_line_discordant_under_ask.py` and `test_answer_layout.py` (239 tests, baseline `239 passed in 35.41s`), rerun the production-chain probe and diff its lines against the unmutated branch, then `git checkout` the file (`git status --short` empty after each).

| Id | Property broken | Tests | Production-chain probe |
|----|-----------------|-------|------------------------|
| M1 | Discordant check made false (`False and ...`) | `1 failed, 238 passed`, `test_discordant_high_risk_claim_under_an_ask_floor_says_sources_disagree` | B, C, D under a floor revert to develop's "Based on" lines |
| M3 | Every tier instead of `high` | `1 failed, 238 passed`, `test_discordant_low_risk_claim_does_not_trigger_the_warning` | identical (J-126-05) |
| M4 | Cited-only clause dropped | `1 failed, 238 passed`, `test_discordant_claim_that_is_not_cited_does_not_trigger_the_warning` | identical (J-126-03) |
| M5 | `any` to `all` | `48 failed, 191 passed` | I (low risk, no high claims) reads "Sources disagree" |
| M6 | Plain `flag` arm dropped | `1 failed, 238 passed`, `test_answer_layout.py::test_trust_line_flag_and_refuse` (the new file's `test_plain_flag_is_unchanged` stays green: its trust is discordant, so the new arm covers it) | F without a floor loses "Sources disagree" |
| M7 | `!= "concordant"` instead of `== "discordant"` | `10 failed, 229 passed` | A, E, H read "Sources disagree" |

Every mutation turned at least one test red. Two of the reds (M3, M4) guard inputs production cannot build.

Correction to J-126-05: `decide`'s low-risk branch is `trust.py:451` to `458`, not `445` to `452`.

## Verified with my own probes

### Through the real caller, `write_node`

`<scratchpad>/test_probe_write_node.py`, copied into each tree as `tests/system_03_search_agent/core/test_zz_judge_probe.py` and run with `pytest -s`. It reuses `test_write_answer_structure.py`'s model stub (`_install`, `_env`) and calls `graph_module.write_node` with two Act findings: a graph ClinVar row `clinical_significance` "Pathogenic" (`cypher_query`) and a dbSNP row "Benign" from either `cypher_query` or `ncbi_dbsnp`, with and without `state["failed_searches"]` (the floor at `core/graph.py:15151`). The writer stub cites both. Both records are cited in every run (citation events for `cq-1-1` ClinVar and `cq-2-2` dbSNP).

| Second record's tool | Failed search | Develop line | Branch line | Outcome, both |
|---|---|---|---|---|
| cypher_query | no | "Based on 2 sources cited from ClinVar and dbSNP; their values could not be compared" | same | ask |
| cypher_query | yes | same as above | same | ask |
| ncbi_dbsnp | no | "Sources disagree on at least one claim" | same | flag |
| ncbi_dbsnp | yes | "Based on 2 sources cited from ClinVar and dbSNP" | "Sources disagree on at least one claim" | ask |

Branch output, last row, pasted: `PROBE second=ncbi_dbsnp failed=True outcome=ask line='Sources disagree on at least one claim'` with `signals=[('cq-1-1', 'high', False, 'flag'), ('cq-2-2', 'high', False, 'flag'), (None, 'high', None, 'ask')]`. The answer-level trust signal stays `ask`, so `_SEVERITY` and the aggregate are unchanged, as the acceptance requires. `4 passed` in each tree.

So checklist item 1 holds where triangulation says `discordant`: `claim_trusts` comes from `trust_for_claims(grounding.claims, ...)` (`core/graph.py:15000`), keeps its ids through `_apply_conflict_flags_to_claim_trusts` (`15038`), and `answer_trust_line` gets the same `grounding.claims` (`15615`), so the ids match and the clause fires. The first two rows are J-126-01.

### Every other line identical to develop

`<scratchpad>/fuzz.py`, seed 126, run in both trees and diffed (`<scratchpad>/fuzz_dev.jsonl`, `<scratchpad>/fuzz_wt.jsonl`):

- 4,000 cases through the production chain (random tools, layers, fields, values, pages, cited subsets, floor on or off, 5 percent forced refuse) and 3,000 raw cases (any outcome, any hand-built trusts, including states production never builds).
- `cases 7000 identical 6641`. All 359 differences are develop's line becoming "Sources disagree on at least one claim" with a cited high-risk discordant trust and an outcome other than `flag` or `refuse`: `unexpected differences: 0`.
- In the production-chain half, every changed case had outcome `ask` (225 of 225); no `answer` outcome ever carried a discordant trust. The 65 changed raw `answer` cases are hand-built states.
- Branch tally, production half: `('refuse', True, False)` 11 cases, so refuse still returns no line with a discordant claim; `('flag', False, True)` 6 cases, the conflict path (J-126-04).
- The named set from the brief, from `<scratchpad>/chain_dev.out` and `<scratchpad>/chain_wt.out`: plain flag (B, C no floor), ask insufficient (A, H), floor-only ask (G with floor), concordant confirmed (G no floor, "Confirmed by 2 independent databases"), single database (H), low-risk (I, F) all print the same line on both trees. Refuse returns None in both (fuzz).

### Other consumers of the line

- Web live answer: `useRunView.ts:1009` to `1021` shows `done.trust_line` as given; only `startsWith("Confirmed")` is keyed, which the new line never matches. The status word for `ask` with a trust line is "Answered" in the warn tone (`useRunView.ts:1191` to `1204`), so a floored disagreement shows "Answered" (warn) beside "Sources disagree", while a plain flag shows "Answered" (good). Not contradictory; unchanged code.
- Saved answer: `SavedAnswerScreen.tsx:333` to `340` prints the stored line; nothing re-derives it.
- CLI `render.py:961` to `979`, MCP `server.py:1218`, GraphQL `fold.py:972` to `976`: pass the string through; the GraphQL pairing check compares outcomes, not text.
- Explainer `AnswerScreen.tsx:131` to `137` does not describe the disagree line, so it stays true.
- Tests and fixtures that pin "Sources disagree": `test_trust_line.py`, `test_answer_layout.py`, `test_saved_answer_endpoint.py`, `test_capture_saved_answer.py`; the first two ran green on the branch (`239 passed`), the last two only store and echo a string. No golden or eval fixture under `src`, `tests` or `evals` pins the old floored line.
- No finding here.

### Gates

- `ruff check` (whole repository, as gate 3): `All checks passed!`
- `isort --check-only --diff src tests services tracker alembic .claude .github` (gate 2): no diff, `Skipped 2 files`.
- `tests/tracker` and `tests/ci`: `709 passed in 550.41s`.
- The new test file and `build.md`: no em or en dash, no bold, no local path (grep exit 1, no match).
- Builder's report check: it ran `test_trust_line_names_its_count.py` and the new file only; `test_trust_line.py` and `test_answer_layout.py`, which also pin trust lines, were not named. Both pass on the branch.

Correction to "Other consumers": the evaluation folder is `eval`, not `evals`; `grep` over `eval` and `testing` (reports excluded) finds only `testing/Developer/scripts/local_loop_run_depth.py`, which copies `trust_line` through.

Clean-up: both probe worktrees were removed with `git worktree remove` after moving the probe test file out; the builder's worktree was never edited (`git status --short` empty).

## Verdict

PASS, with no blocking finding. Two majors go to the owner, and J-126-01 means the acceptance sentence holds only in part.

- Nothing a person reads is worse than develop, with one possible exception, J-126-02 (unsure). The outcome and `_SEVERITY` are unchanged, which I checked through the real `write_node`. Every line other than the intended one is identical: 7,000 differential cases, 0 unexpected differences.
- The new line appears through the real caller when the two cited records come from different tools.
- J-126-01: when both disagreeing records come from the graph, as in the card's own ClinVar against dbSNP example, the line still says "their values could not be compared". That happens on develop too. The cause is `_origin_of`, outside this card's fence. The owner decides whether card 126 is done without it.

| Id | Severity | Worse than develop for a person | One line |
|----|----------|---------------------------------|----------|
| J-126-01 | major | no, identical | Graph-only ClinVar against dbSNP disagreement never reads "Sources disagree", because triangulation treats one tool as one origin; the builder's main test hand-builds a trust production cannot produce from its own findings |
| J-126-02 | major (unsure) | possibly: a new "Sources disagree" the reader cannot trace | The line fires when the disagreeing record is uncited and the floor comes from that omission; "cited only" checks the claim, not its counterpart |
| J-126-03 | minor | no | The cited-only clause can never be false in production; its comment claims a guard it does not give (mutation M4: one unit test red, production probe identical) |
| J-126-04 | minor | no, identical | The fix keys on `triangulation == "discordant"`, not on the claim's `flag` outcome, so the Section 7.2 graph-against-live conflict still loses "Sources disagree" under a floor |
| J-126-05 | minor | no | The high-risk restriction guards an input production never builds (mutation M3: one unit test red, production probe identical) |

Verified with my own probes:

- the production-chain probe;
- the real `write_node` probe;
- the 7,000-case differential;
- six one-property mutations;
- ruff over the whole repository and gate 2's isort;
- `tests/tracker` and `tests/ci`;
- the four trust-line test files (239 passed).

Only read, not run:

- the frontend, CLI, MCP and GraphQL pass-through code;
- the explainer text.

The frontend was not touched, and its tests were not run. No finding sits inside a fix made during this card's own review rounds; this is round one.
