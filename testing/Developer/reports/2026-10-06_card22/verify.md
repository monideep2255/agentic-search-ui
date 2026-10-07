# Card 22 fresh verification, after the fix round

Verifier: fresh checker, bossman dial position 2. Branch fix/card22-name-every-total at 0de831a2, base develop d8179c4e. Findings are appended as they are established.

## Findings

### V-22-01: "Confirmed by N independent databases" now counts uncited records, so a one-source answer reads "Confirmed by 3"
- Severity: major. Regression from the fix round (commit 488999b5, `_databases_backing` reading the whole `synth_findings` pool).
- Where: `src/system_03_search_agent/synthesis/trust.py:586-602` (`_databases_backing` over `all_findings`), `:704-715` (the confirmed branch), `src/system_03_search_agent/core/graph.py:13871-13873` (passes `synth_findings`).
- What: N is now counted over every finding the model was shown, cited or not, and agreement is still by field and bucket with no subject check. An answer that cites ONE ClinVar record, with uncited LitVar2 and dbSNP findings in the pool stating "Pathogenic" (for any variant), reads "Confirmed by 3 independent databases" above a Sources list of one card. On develop the same input read "Based on 1 source", because develop required two databases among the cited claims.
- Reproduction: my probe `p_confirm.py` (scratch), real `trust_for_claims`, `aggregate`, `answer_trust_line`, run against both worktrees with the same inputs. Case F, cited `[ClinVar graph row, clinical_significance=Pathogenic, ClinVar:17661]`, pool adds uncited `litvar2_lookup` (`.../research/litvar2/...`, Pathogenic) and `ncbi_dbsnp` (`.../snp/rs80357713`, pathogenic). develop: `line='Based on 1 source'`. branch: `line='Confirmed by 3 independent databases'`. Case H, cited graph ClinVar row plus a live efetch of the same record, uncited LitVar2: branch `'Confirmed by 2 independent databases'`, though every cited source is one database. Case L (cited ClinVar variant 55555 and dbSNP rs999, two different variants): `'Confirmed by 2'` on both, inherited.
- Why it matters: from the reader's chair, two of the three databases the line names are not on the screen and cannot be opened, and because `triangulate` and the new count compare by field and value only, the uncited "agreeing" records can be about a different variant. The fix round set out to stop N naming more databases than back the fact; on a single-citation answer it now names more than develop did and more than the reader can verify. The fix round's own docstring and query 107 say N counts "the databases whose records state the confirmed fact", which a reader takes to mean the cited records. Possible fixes (not mine to pick): count agreement among the cited claims' findings only, or require at least two cited databases before saying confirmed, as develop did.
- NOT FIXED

### V-22-02: the restatement gate now compares a sentence against the wrong listed row when a graph and a live finding share one page
- Severity: minor. Regression from the fix round (commit e18aea37, `shown_by_url` re-keyed by `source_page_key`).
- Where: `src/system_03_search_agent/synthesis/answer_layout.py:866-870` (dict keyed by page key, last finding wins), `:881`.
- What: `one_finding_per_record` still groups by exact `source_url`, so the graph gene finding (`.../gene/672`) and the live Datasets finding (`.../gene/672/`) are two listed rows. The gate's lookup is now keyed by page, so both collapse to one dict entry and whichever finding comes last is the one every sentence on that page is compared against. A sentence that only restates the other row is no longer dropped and sits above the list that repeats it.
- Reproduction: my probe `p_gate.py` (scratch), real `run_grounding_pass` and `drop_record_restatements`, same inputs on both worktrees. Findings `c1` graph `symbol=BRCA1` at `.../gene/672`, `c2` live `description=BRCA1 DNA repair associated` at `.../gene/672/`; listing rows on both: `['c1', 'c2']`. Narrative "Gene BRCA1 symbol [1]." develop: `dropped=1 kept=()`. branch: `dropped=0 kept=('Gene BRCA1 symbol [1].',)`. With the findings in the other order, the live sentence survives instead: branch `dropped=0 kept=('BRCA1 DNA repair associated description [1].',)`, develop `dropped=1`.
- Why it matters: the reader sees one record said twice, in the prose and in the list row under it, which item 12.12 exists to stop. It only fires on the graph-plus-live pair this card made one page, so it is narrow. The fix round's commit claims the gate "still finds its record"; it finds a record, not necessarily the cited one. A keyed list of findings per page, matched by `citation_id` first, would keep develop's behaviour.
- NOT FIXED

### V-22-03: two parts of the fix round have no test: the restatement gate's re-key and the graph passing the findings pool
- Severity: minor (test gap). Both inside the fix round (commits e18aea37 and 488999b5).
- Where: `src/system_03_search_agent/synthesis/answer_layout.py:866-881`; `src/system_03_search_agent/core/graph.py:13871-13873`.
- What and reproduction: in a scratch worktree of 0de831a2 I applied each mutation alone, ran `pytest -m 'not integration' tests/system_03_search_agent/synthesis tests/system_03_search_agent/core`, and restored with `git checkout --`.
  - Gate put fully back to develop's exact-URL key (all three lines, dict, filter and lookup): "1994 passed, 66 skipped", the same as unmutated. The fix-round report's test for A-22-03 (`test_the_opening_line_counts_one_record_per_page`) covers the opening line only. (Mutating only the dict line fails 4 older paper tests, but only because dict and lookup then disagree, not because anything pins the new key.)
  - `answer_trust_line(...)` called from `_write_answer` without `all_findings=synth_findings`: "1994 passed, 66 skipped". The pool behaviour is pinned only by direct calls in `test_trust_line_names_its_count.py`, so the wiring itself is unguarded. Note that this mutation also removes V-22-01's over-count, so whoever decides V-22-01 should know nothing holds the wiring either way.
- Why it matters: J-22-07's lesson was a merge rule nothing held; the same shape recurs here, and V-22-02 is a live defect in exactly the untested lines.
- NOT FIXED

### V-22-04: the rebuilt "Confirmed by" tests pin three different variants agreeing as confirmation of one fact
- Severity: minor (a test asserting the wrong thing; inherited behaviour, new test text). Inside the fix round (commit 488999b5).
- Where: `tests/system_03_search_agent/synthesis/test_answer_layout.py:338-376` (`CLINVAR_A` is ClinVar variation 17661, `CLINVAR_B` is 17662, `LITVAR` is rs80357906).
- What: the docstring says the rebuilt test uses "records that actually state the same fact". They state the same VALUE, "Pathogenic", for three different variants, and the test requires "Confirmed by 2 independent databases". The fix-round report lists subject-blind agreement as known and left for a card, but this test now holds it as correct, so the card that fixes it will have to break a test that says it is right. The LitVar2 URL in the test (`.../research/litvar2/docsum?...`) is also not what `litvar2_lookup` emits for a variant with a significance (`.../snp/{rsid}`, `tools/litvar2_lookup.py:756`), so the test does not exercise how a real LitVar2 record is keyed (as dbSNP).
- Reproduction: read, and confirmed by running my own case L in `p_confirm.py`: ClinVar variation 55555 plus dbSNP rs999, both "Pathogenic", reads "Confirmed by 2 independent databases" on branch and develop.
- Why it matters: from the reader's chair, "Confirmed by 2 independent databases" over a variant means two databases agree about that variant. The test makes the opposite reading the specified behaviour.
- NOT FIXED

### V-22-01 addendum: the exact overclaim, with uncited records about a different variant
- Reproduction: my probe `p_confirm2.py`, same inputs on both worktrees. Cited: one graph ClinVar row, variation 17661, "Pathogenic". Uncited in the pool: a dbSNP record for a different variant (`.../snp/rs999`) and a PubTator record, both "Pathogenic" in `clinical_significance`. develop: `'Based on 1 source'`. branch: `'Confirmed by 3 independent databases'`.
- This is A-22-10's symptom ("Confirmed by 2 above a Sources list of 1") come back in a new form through the fix for it: a database count larger than the sources the reader can open, now with no cited second database at all. It sits inside a fix made during this round, which is the review loop's stop condition.

## Prior findings, checked by my own probes

| Finding | Status on 0de831a2 | How I checked |
|---|---|---|
| J-22-02, A-22-09 (cross-layer card labelled "L1 · graph", live group gone) | Fixed | Re-ran the adversary's `probe_xlayer.test.tsx` and its end-to-end harness against the branch: meta "2 tool calls · 1 source cited from 2 layers", card "[1][2] NCBIGene 672 L1 · graph, L2 · live", groups 1 and 2 both present, chip 2 "Source 2, layer 2", at 1280 and 390. My own grouping probe: both citation orders, three layers on one page, a page cited only from layers 2 and 3, all file the card under the lowest layer and keep every other group with its own markers. develop on the same render: two cards, heading 3 where the branch says 2. |
| J-22-07 (no test holds the merged card's group) | Fixed | Mutation V-F1 (card under first-cited layer): 1 failed. |
| J-22-04, A-22-05 (saved answer 16 over 18 rows) | Fixed | Re-ran adversary P5: `rows 16, geneRows 1`, trust line "Based on 16 sources cited, not yet confirmed". |
| J-22-05, A-22-06 (rail 16 then 18 after reload) | Fixed | `p_hist.py` on `_citation_count`: BRCA1 stored payloads develop 18, branch 16; rows with no link, strings, empty list, non-list and None unchanged from develop. Label "sources cited" held by mutation V-F9. Not driven through a real reload. |
| A-22-01 (one ClinVar record twice reads "Confirmed by 2") | Fixed for the reproduced shape | Re-ran adversary case 1: "Based on 1 source cited, not yet confirmed". See V-22-01 for the same symptom through the pool. |
| A-22-02, J-22-03 (N counts every cited database) | Fixed for the reproduced shape | Re-ran adversary case 2 and my case B: 2, not 5. |
| A-22-10 (Confirmed by 2 above 1 source) | Fixed for the reproduced shape, reopened in another form | V-22-01: "Confirmed by 3" above 1 source. |
| J-22-08 (info card one cause) | Fixed | Text reads both causes; mutation V-F7 caught. |
| A-22-03 (opening line counts slash pair twice) | Fixed | Re-ran adversary `probe_summary.py`: "Found 1 gene record for BRCA1: BRCA1 [1]." and "I found 1 gene related to BRCA1 [1]." |
| A-22-04 (truncation and remaining counts) | Fixed | Mutations V-M9, V-M10 caught by `core/test_graph.py`; behaviour read, not driven. |
| J-22-06, A-22-08 (command line 16 over 18) | Fixed | Re-ran adversary `probe_cli.py`: 16 reference lines, "[1][6][9] NCBIGene - .../gene/672/". |
| J-22-09, A-22-10 and A-22-11 (stale comments) | Fixed | grep finds neither "17 sources cited" in `useRunView.ts` nor "keyed by exact" or "source(s))" in `trust.py`. |
| J-22-01, A-22-07 (whitespace sets differ) | Not fixed, as briefed | Not re-probed. |

Genuine two-database agreement is not lost: my cases C (ClinVar and LitVar2), D (ClinVar and dbSNP) and E (three databases) read "Confirmed by 2", "2" and "3" on the branch as on develop. The cases that drop to "not yet confirmed" are the ones that are one database: a graph row and a live fetch of one ClinVar record, `omim.org` and `www.omim.org`, `pubmed.ncbi.nlm.nih.gov` and `www.ncbi.nlm.nih.gov/pubmed`. Note for the owner, not a finding: a real LitVar2 significance record cites the dbSNP page, so LitVar2 beside dbSNP now counts as one database where develop said two.

## Mutations

Each applied alone in a scratch worktree of 0de831a2 and restored with `git checkout --`; `git status` clean of tracked changes after every run.

| Mutation (commit) | Result |
|---|---|
| V-M1 page key keeps the trailing slash (316606cc) | Caught, 1 failed |
| V-M2 confirmed at one database (488999b5) | Caught, 1 failed |
| V-M3 NCBI subdomain keyed as its own host (488999b5) | Caught, 1 failed |
| V-M4 agreement pool ignored (488999b5) | Caught, 1 failed |
| V-M11 `_write_answer` does not pass the pool (488999b5) | Survived, synthesis and core suites 1994 passed (V-22-03) |
| V-M5 opening line keyed by exact URL (e18aea37) | Caught, 1 failed |
| V-M6 restatement gate fully back to exact URL (e18aea37) | Survived, 1994 passed (V-22-03) |
| V-M7 command line one line per citation (a673c3c3) | Caught, 1 failed |
| V-M8 rail count ignores the page (b924ecdc) | Caught, 1 failed |
| V-F9 rail label drops "cited" (b924ecdc) | Caught, 1 failed |
| V-M9 truncation note counts citations (dcf7c720) | Caught, 1 failed |
| V-M10 remaining count counts citations (dcf7c720) | Caught, 1 failed |
| V-F1 card under first-cited layer (7216cd06) | Caught, 1 failed |
| V-F2 no also-cited, group vanishes (7216cd06) | Caught, 3 failed |
| V-F3 label names one layer (7216cd06) | Caught, 1 failed |
| V-F4 badge own cards only (7216cd06) | Caught, 1 failed |
| V-F5 also line not rendered (7216cd06) | Caught, 1 failed |
| V-F6 meta counts only groups with own cards (7216cd06) | Caught, 2 failed |
| V-F7 info card one cause (77f41ab5) | Caught, 1 failed |
| V-F8 saved rows one per citation (6b4455c7) | Caught, 2 failed |

Frontend mutations ran the whole vitest suite (513 tests); backend ones ran the card's test files plus `test_answer_quality.py`, `cli/test_render.py`, `feedback/test_history.py`, or the named slice of `core/test_graph.py`.

## Gates

| Gate | Result |
|---|---|
| gate02, `isort --check-only --diff src tests services tracker alembic .claude .github` | Pass, "Skipped 2 files", exit 0 |
| gate03, `ruff check` with no path, in this worktree | Fails, 10 errors, all in the untracked reviewer probes `raw/adversary/probe_cli.py` (3), `probe_confirmed.py` (2), `probe_parity.py` (3), `probe_summary.py` (2). Nothing else fails: a clean checkout of 0de831a2 reads "All checks passed!". |
| gate04 and 04b, clean checkout of 0de831a2 | Pass, "7068 passed, 143 skipped, 24 deselected, 1 xfailed" in 390.73s; 04b "every skip sanctioned"; `feedback/test_history.py` ran 27 cases, 0 skipped |
| gate08, `npm run build && npm test` plus the licence-notice check, clean checkout | Pass, build exit 0, "Test Files 59 passed (59), Tests 513 passed (513)", licence check ok |
| `CI=1 npx playwright test e2e/card22-name-every-total.spec.ts`, ports 5273 and 8931 free first | Pass, "4 passed (18.4s)" |
| `check_public_leaks.py --base origin/develop` | PASS, 0 findings over 12 commits; 12 binary files listed, all untracked |

## Verdict

FAIL.

The fix round fixed every finding it marked fixed, each reproduced the way its reviewer reproduced it, and every gate passes on a clean checkout. It fails on one regression inside its own fix: V-22-01. The new "Confirmed by N independent databases" counts records the answer never cites, with no subject check, so an answer citing one ClinVar record reads "Confirmed by 3 independent databases" where develop read "Based on 1 source". That is the overclaim the round set out to remove, in a new form, and it fires rule 4: escalate to the owner rather than merge tonight.

Also from the fix round, lower severity: V-22-02 (the restatement gate compares a sentence against the wrong listed row for the graph-plus-live pair, so a restatement survives), V-22-03 (two parts of the round are untested: the gate's re-key and the pool wiring), V-22-04 (a rebuilt test pins three different variants as agreeing on one fact).

Verified with my own probes: the confirmed line on 15 inputs against develop and the branch; the grouping and render of cross-layer pages; the rail count; the restatement gate; the adversary's frontend, end-to-end and backend probes re-run against the branch; 20 mutations; every gate. Only read: the truncation note's wording (held by mutation, not driven end to end), the MCP and GraphQL surfaces, the history reload in a real browser.
