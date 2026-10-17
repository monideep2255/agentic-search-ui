# Card 8 third fresh verifier report: the second attempt

Pull request #266, branch `fix/card8-trust-line-r2`, head `68c876a5`, on develop `655e9dfe`. The branch is develop, a merge `96feebf7` of the closed #259's commits `62c6f1d3` and `fff8b91b`, and one new commit `68c876a5` (the explainer sentence). Verified in a detached worktree at `68c876a5`, 2026-10-17. Role: fresh verifier of a second attempt, no fix round. Probes in `<scratchpad>/card8_ver3/`. The whole branch was re-derived against develop `655e9dfe`.

## Table of contents

- [Findings](#findings)
- [The branch is what it says](#the-branch-is-what-it-says)
- [Verdict code is byte identical](#verdict-code-is-byte-identical)
- [The explainer against the code, both directions](#the-explainer-against-the-code-both-directions)
- [Database names against what is cited](#database-names-against-what-is-cited)
- [Card 30 and card 37 on develop](#card-30-and-card-37-on-develop)
- [The 200 character cap](#the-200-character-cap)
- [Surfaces](#surfaces)
- [Tests and lint](#tests-and-lint)
- [Live runs](#live-runs)
- [CI on the pull request](#ci-on-the-pull-request)
- [Verdict](#verdict)

## Findings

Nothing on this branch shows any person something worse than develop. Two minor items, both not worse than develop:

### V-8-04 (carried, minor): on the BRCA1 disease question MedGen folds into "3 other databases"

- Reproduced live (query 1, below): "Based on 21 sources cited from ClinicalTrials.gov, ClinVar, PubMed and 3 other databases; their values could not be compared". The four disease records the question asks about are MedGen's (4 pages), and the three named have 5 pages each.
- Exactly the owner's rule ("at four or more, the three most cited, then "and N other databases""), and true. Not worse than develop. For the owner's retest.

### V-8-06, minor: a disagreement floored to "ask" now reads with no caution word at all

- Case H of the explainer probe (below): ClinVar says "Pathogenic", dbSNP says "Benign" (both cited, `discordant`, `flag`), and a floor (fallback, failed search, omitted records, unaddressed entity, card 30) lifts the answer to `ask`, which outranks `flag` (`_SEVERITY`, `trust.py:474`, unchanged).
- Branch: "Based on 2 sources cited from ClinVar and dbSNP". Develop: "Based on 2 sources cited, not yet confirmed". Neither says the sources disagree; that ranking is pre-existing.
- The branch line claims nothing false (no "Confirmed", no agreement), and the explainer is true of it: the values were compared, so no clause. The lost words are "not yet confirmed", which the owner's decision names and removes. Not worse than develop under the owner's rule. Rare: it needs two in-table values that disagree plus a floor; dbSNP's usual multi-value significance is outside the bucket table and takes the clause instead (case I, query 23). Recorded so the owner can decide whether a floored disagreement should keep "Sources disagree".

## The branch is what it says

- `git diff 78c68c1c fff8b91b | git patch-id --stable` and `git diff 655e9dfe 96feebf7 | git patch-id --stable` both print `55ad0fe9bdf9635114ec849a473fbcb88af93939`, 25 files, 527 insertions, 83 deletions: the merge carries the closed #259's change exactly, with no conflict edits.
- `git diff 78c68c1c 655e9dfe --stat` touches no `synthesis/trust.py`, so develop's trust code is the one the first two verifiers read.
- `68c876a5` changes two files: `AnswerScreen.tsx` (the explainer sentence and its comment) and `AnswerScreen.card22.test.tsx` (the pinned sentence).

## Verdict code is byte identical

AST comparison of every top level definition of `synthesis/trust.py`, develop `655e9dfe` against the branch (`<scratchpad>/card8_ver3/same.py`):

```
DIFF _DATABASE_NAMES (only branch)
DIFF _NCBI_DATABASE_NAMES (only branch)
DIFF _NCBI_RESEARCH_NAMES (only branch)
DIFF _databases_phrase (only branch)
DIFF _join_names (only branch)
DIFF answer_trust_line
identical: 24 of develop's 25
decide identical
DECISION_TABLE identical
triangulate identical
aggregate identical
bucket_for identical
record_database identical
_databases_backing identical
_origin_of identical
trust_for_claims identical
_SEVERITY identical
_NCBI_HOST identical
```

- `git diff --quiet origin/develop...HEAD` is clean for `src/system_03_search_agent/core`, `adapters/cli`, `adapters/graphql`, `adapters/web_sse`, `feedback`, `synthesis/answer_layout.py`, `synthesis/findings.py`, `frontend/src/hooks` and `SavedAnswerScreen.tsx`.
- Inside `answer_trust_line` the `refuse`, `flag` and "Confirmed by" returns are unchanged (diff hunk at `trust.py:794` to `810`); only develop's two "not yet confirmed" returns and its final return are replaced by the database phrase and the clause.

## The explainer against the code, both directions

The sentence under test (`frontend/src/components/screens/AnswerScreen.tsx:131` to `137`): "A Based on line names the databases the cited pages come from, the three most cited when there are four or more. When an answer rests on two or more databases and the values behind one of its high-stakes facts could not be compared, the line adds "their values could not be compared"." The first two sentences ("Sources cited counts ...", "Confirmed means ...") are develop's, unchanged.

The code's condition (`synthesis/trust.py:804` to `809`): outcome `ask`, two or more cited databases (`_databases_phrase`, distinct `record_database` keys over cited pages), and a high-risk claim with triangulation `insufficient`.

Why the two match, from the code:

- `insufficient` for a high-risk claim means `triangulate` found no other origin stating that field, or a value outside the bucket table (`trust.py:383` to `400`). In both, no comparison of values was made. So whenever the clause shows, "the values behind one of its high-stakes facts could not be compared" holds.
- A high-risk `insufficient` claim always decides `ask` (`DECISION_TABLE`, `trust.py:414`), and every later step in Write only aggregates toward `ask` or `refuse` (`core/graph.py:14874`, `14912`, `14964`, `14983`, `15001`, all `aggregate([trust_outcome, "ask"])`); a refusal has no line. So the `ask` term never hides the clause from an answer that meets the sentence's condition.
- Conversely, when no clause shows, either the answer rests on one database, or every high-stakes fact came back `concordant` or `discordant`, which means values were compared (`trust.py:401`). The V-8-05 case (graph row and live fetch of one ClinVar record) is `concordant`: the values were compared, so the new sentence promises no clause there. V-8-05 is closed by `68c876a5`.
- `claim_trusts` and `claims` at the call site are one per grounded claim (`core/graph.py:14831`, `15445`, `trust_for_claims` dedupes by citation), so the high-stakes fact behind a clause is always one the answer cites. The comparison itself may use uncited findings (`all_findings` is the whole pool); cases M and N show the sentence stays true either way.

Probe `<scratchpad>/card8_ver3/probe_explainer.py`, real `trust_for_claims` verdicts, branch and develop lines for the same inputs, and whether the sentence's condition holds, judged from how each case was built:

```
A ClinVar alone states the high fact, MedGen name beside
  trusts  [('high', 'insufficient', 'ask'), ('low', 'insufficient', 'answer')] outcome ask
  branch : Based on 2 sources cited from ClinVar and MedGen; their values could not be compared
  develop: Based on 2 sources cited, not yet confirmed
  explainer condition holds: True  clause shown: True  AGREE
B ClinVar and dbSNP state it, one value outside the bucket table
  branch : Based on 2 sources cited from ClinVar and dbSNP; their values could not be compared
  explainer condition holds: True  clause shown: True  AGREE
C ClinVar only, every page ClinVar, high fact alone
  branch : Based on 2 sources cited, all from ClinVar
  explainer condition holds: False  clause shown: False  AGREE
F graph ClinVar row and live fetch of the same record agree, MedGen beside
  trusts  [('high', 'concordant', 'answer'), ('high', 'concordant', 'answer'), ('low', 'insufficient', 'answer')] outcome answer
  branch : Based on 2 sources cited from ClinVar and MedGen
  develop: Based on 2 sources cited, not yet confirmed
  explainer condition holds: False  clause shown: False  AGREE
F-floor same as F, answer floored at ask (fallback, failed search, card 30)
  branch : Based on 2 sources cited from ClinVar and MedGen
  explainer condition holds: False  clause shown: False  AGREE
F-odd graph and live of one record, value outside the table, MedGen beside
  branch : Based on 2 sources cited from ClinVar and MedGen; their values could not be compared
  explainer condition holds: True  clause shown: True  AGREE
M ClinVar fact matched by an UNCITED dbSNP record, MedGen beside
  branch : Based on 2 sources cited from ClinVar and MedGen
  explainer condition holds: False  clause shown: False  AGREE
N ClinVar fact against an UNCITED dbSNP value outside the table, MedGen beside
  branch : Based on 2 sources cited from ClinVar and MedGen; their values could not be compared
  explainer condition holds: True  clause shown: True  AGREE
G ClinVar and dbSNP agree, both cited
  branch : Confirmed by 2 independent databases
  develop: Confirmed by 2 independent databases
  explainer condition holds: False  clause shown: False  AGREE
H ClinVar and dbSNP DISAGREE, floored at ask, nothing uncomparable
  trusts  [('high', 'discordant', 'flag'), ('high', 'discordant', 'flag')] outcome ask
  branch : Based on 2 sources cited from ClinVar and dbSNP
  develop: Based on 2 sources cited, not yet confirmed
  explainer condition holds: False  clause shown: False  AGREE
I ClinVar and dbSNP disagree, and a second high fact is uncomparable
  branch : Based on 3 sources cited from ClinVar and dbSNP; their values could not be compared
  explainer condition holds: True  clause shown: True  AGREE
J card 30 shape: graph variant names only, all low risk, floored at ask, two databases
  trusts  [('low', 'insufficient', 'answer'), ('low', 'insufficient', 'answer')] outcome ask
  branch : Based on 2 sources cited from ClinVar and NCBI Gene
  develop: Based on 2 sources cited, not yet confirmed
  explainer condition holds: False  clause shown: False  AGREE
```

(Lines trimmed for length; the full output is `<scratchpad>/card8_ver3/probe_explainer.out`.) 12 of 12 cases agree in both directions. Case H is V-8-06.

- "A Based on line names the databases the cited pages come from, the three most cited when there are four or more": true. `_databases_phrase` (`trust.py:658` to `685`) keys each cited page by `record_database`, sorts by pages then name, and at four or more shows `known[:3]` (`trust.py:677`). A key outside the closed table is counted as "N other databases", never printed; no tool's URL builder produces one today (first verifier's sweep, V-8-03; the table is unchanged since).
- What the old paragraph said and the new one drops: "or this answer may be incomplete, for example because a search did not finish or more records were found than it lists". Each floor that made that true carries its own note in the answer body (`partial_answer_note`, `incomplete_answer_note`, `failed_search_note`, `structured_fallback_note`, card 30's classification note; `core/graph.py:14906` to `15000`), and query 22 below shows three of them on screen. The owner's decision names the rewrite.
- The explainer is shown only on the live answer screen (`AnswerScreen.tsx:2616`); the saved answer screen shows the stored line with no explainer (`SavedAnswerScreen.tsx:333` to `340`, unchanged), so an old saved "not yet confirmed" row is never paired with the new sentence.

## Database names against what is cited

- Each name comes from the cited page's host and path (`record_database`, `trust.py:537` to `583`, byte identical to develop), so a graph ClinVar row and a live ClinVar fetch are one database (cases F, F-floor, F-odd: "from ClinVar and MedGen", ClinVar once; query 22 live: 59 ClinVar pages over graph and live, named once).
- A LitVar2 citation whose page is the dbSNP page names dbSNP (query 23 live), which is the page the reader opens.
- The databases named plus "N other" never exceed the pages: each page has exactly one key, and `_databases_phrase` counts pages by the same `source_page_key(...) or citation_id` as `citation_count` (`trust.py:670` to `671`, `773` to `778`).
- Live, each line checked against an independent tally of the citation events' URLs (`<scratchpad>/card8_ver3/tally.py`, which does not call `record_database`); see Live runs.

## Card 30 and card 37 on develop

- Card 30 floors through `trust_outcome` only: `if classification_note is not None and classification_asked and trust_outcome != "refuse": trust_outcome = aggregate([trust_outcome, "ask"])` (`core/graph.py:15000` to `15001`); no `ClaimTrust` is touched. The clause reads `claim_trusts`, so card 30 cannot add it. Case J above and query 22 live: no clause.
- Card 37 slice A1 changes the record's display label and table columns (`synthesis/answer_layout.py`, `name_mixed_variant_extras`, `_row_type_label`), not `source_url`; the line keys on `source_url`. Query 23 live: "Based on 1 source cited, from dbSNP", one database, so no clause, which is the owner's rule.

## The 200 character cap

- `DonePayload.trust_line` keeps `max_length=200` (`contracts/events.py:621`); MCP keeps it on both outputs (`adapters/mcp/server.py:456` to `459`, `542`).
- Probe `<scratchpad>/card8_ver3/probe_cap.py`: the three longest names with over 3000 pages each plus 60 unknown hosts, clause on: 145 characters, "Based on 9057 sources cited from Pathogen Detection, ClinicalTrials.gov, NCBI Datasets and 60 other databases; their values could not be compared". Every one to three database combination of the table with the clause: at most 122. No line contains "not yet confirmed" and none starts with "Confirmed" (asserted in the probe).
- Shapes: "Based on 1 source cited, from MedGen", "Based on 2 sources cited, all from MedGen", "Based on 1 source cited, from 1 other database" (unreachable today), "Based on 2 sources cited from ClinVar and 1 other database".
- Live lines: 124, 88 and 35 characters.

## Surfaces

- Command line: `_trust_line_text` passes `done.trust_line` through `_single_line` and joins parts with " · " (`adapters/cli/render.py:961` to `979`, `295`); the semicolon is not special. `adapters/cli/` unchanged against develop.
- MCP: `trust_line = (done_payload.trust_line or "").strip() or None` (`adapters/mcp/server.py:1218`); saved answers through MCP read `saved.trust_line` (`:1671`). Only a comment changed in this file.
- GraphQL: `acc.trust_line = (payload.trust_line or "").strip() or None` (`adapters/graphql/fold.py:858`), reported by `_parity_fields` (`:940` to `988`). `adapters/graphql/` unchanged.
- Saved answers: `feedback/` and `adapters/web_sse/` unchanged; the stored line is shown as stored.
- Nothing parses the old words: `grep -rniI "not yet confirmed\|which differ" src frontend/src` outside tests finds only comments. The check mark and tone still key on the first word "Confirmed" (`useRunView.ts:1018`, `SavedAnswerScreen.tsx:335`, both unchanged), and every new line starts "Based on" (`trust.py:797`).
- Speed: the line adds one loop over the cited claims and no model call.

## Tests and lint

- Python, the files the diff touches and neighbours (`synthesis/`, `harness/test_tiers.py`, `core/test_write_answer_structure.py`, cli `test_s3_as_printed.py`, graphql `test_parity_fields.py` and `test_types.py`, mcp `test_no_cost_and_auth.py` and `test_parity_tools.py`, feedback `test_capture_saved_answer.py` and `test_outage_note_dated.py`, web_sse `test_saved_answer_endpoint.py`, core `test_write_failed_search.py`): `1266 passed, 10 skipped, 1 xfailed, 2 warnings in 65.97s`.
- Frontend, from `frontend/`, `npx vitest run` on the six test files the diff touches (`AnswerScreen.card22`, `SavedAnswerScreen`, `riskTag.parity`, `set9AnswerStructure`, `answerLayout`, `answerPagination`): `Test Files 6 passed (6)`, `Tests 99 passed (99)`. `npx tsc --noEmit`: exit 0, no output.
- CI's lint gates exactly: gate 3 `ruff check` printed `All checks passed!`, exit 0; gate 2 `isort --check-only --diff src tests services tracker alembic .claude .github` printed `Skipped 2 files`, exit 0; gate 1 `compileall` and the three imports, exit 0.
- Break it, one property each, restored with `git checkout`:

| Mutation of `trust.py` | `test_trust_line.py` |
|---|---|
| Clause over every claim, not only high risk | `1 failed, 52 passed` (`test_ask_two_databases_all_low_risk_has_no_clause`) |
| Clause at one database | `3 failed, 50 passed` |
| `medgen` named "OMIM" | `12 failed, 41 passed` |
| Clause on `answer` as well as `ask` | `53 passed`; unreachable, since a high-risk `insufficient` claim always decides `ask` (above). Evidence, not a finding |

- The explainer test (`AnswerScreen.card22.test.tsx`) pins the new sentence's condition text and that "not yet confirmed" is absent, so restoring either earlier sentence turns it red.

## Live runs

Three runs through `core.run.run_streaming()` on this worktree, Researcher, develop's settings as card 115's adversary used them (`CLASSIFIER_PROVIDER=jev`, guard and plan models as develop, `PER_QUERY_COST_CAP_USD=0.25`), session ids `card8-ver3-q1`, `card8-ver3-q22`, `card8-ver3-q23`. Script `<scratchpad>/card8_ver3/live.py` wraps `answer_trust_line` to record its inputs and develop's line for the same inputs. A first launch failed at argument parsing before any import or model call (a shell word-splitting slip in my loop), so it spent nothing.

| Query | Outcome | Trust line, pasted | Develop line, same inputs | Pages per database, independent tally | Seconds | Spend |
|---|---|---|---|---|---|---|
| 1, `Which diseases are associated with BRCA1?` | ask | Based on 21 sources cited from ClinicalTrials.gov, ClinVar, PubMed and 3 other databases; their values could not be compared | Based on 21 sources cited, not yet confirmed | pubmed 5, clinvar 5, clinicaltrials.gov 5, medgen 4, gene 1, omim.org 1; 21 pages | 15.3 | $0.0112 |
| 22, `Which clinically significant variants have been reported in CFTR?` | ask | Based on 71 sources cited from ClinVar, ClinicalTrials.gov, PubMed and 2 other databases | Based on 71 sources cited, not yet confirmed | clinvar 59, pubmed 5, clinicaltrials.gov 5, gene 1, omim.org 1; 71 pages | 17.9 | $0.0111 |
| 23, `What is rs334 and what condition is it associated with?` | ask | Based on 1 source cited, from dbSNP | Based on 1 source cited, not yet confirmed | snp 1 (two citations, `dbsnp` and `litvar2`, one page); 1 page | 11.6 | $0.0051 |

- Query 1: the three named are the three most cited (5 each, ties by name); "3 other databases" are MedGen 4, NCBI Gene 1, OMIM 1. The four high-risk claims are MedGen disease names, `insufficient`, the only other origin for `name` being `clinicaltrials_search`, whose values are outside the bucket table. The clause is true and the owner's rule. V-8-04.
- Query 22 (card 30): all 72 claims `low/insufficient`, outcome `ask` from the floors; no clause. Card 30's note is on screen ("ClinVar's classification of these variants (for example pathogenic, benign or uncertain) was not retrieved ..."), with the truncation note and the structured fallback note.
- Query 23 (card 37): one high-risk claim, dbSNP's `clinical_significance` "not-provided, protective, likely-benign, pathogenic, other", `insufficient`, no other origin; one database, so no clause.
- Every run's distinct cited pages equal the line's N (21, 71, 1). Total spend $0.0274, within $0.40.
- Each run logs a non fatal `CallerIdentityRequired` from session memory and interaction capture, because my script passes no owner id; the answer completes and `done` is emitted.

## CI on the pull request

- `gh pr view 266`: head `68c876a53d5fa19d2c9e6ca3dd61c1d2ebe00a67`, open, mergeable.
- Run 39002786205, head sha the same, `completed`, `success`. `gh pr checks 266`:

```
Accessibility (10)	pass	2m7s
Frontend gates (7, 8)	pass	2m8s
Integration suite (5)	pass	44s
Python gates (1, 2, 3, 4, 6, 9)	pass	7m30s
```

- Gate 4 log: `7975 passed, 143 skipped, 24 deselected, 1 xfailed, 7 warnings in 332.04s`.

## Verdict

- The branch is develop plus the closed #259's exact change plus one explainer sentence. Verdict code byte identical; `core/`, every adapter but one comment, `feedback/` and the saved answer screen unchanged.
- The explainer is true of the code in both directions over 12 constructed cases and three live runs, including the graph row plus live fetch of one ClinVar record (V-8-05 closed) and a fact only one database states.
- Database names match the cited pages in all three live runs; card 30's floor adds no false clause; card 37's dbSNP answer reads "from dbSNP"; the cap holds at 145 characters worst case; every surface passes the text through; CI is green.
- V-8-04 and V-8-06 are minor and not worse than develop under the owner's decision.
- Tree: `git status --short` shows only `?? frontend/node_modules`, the expected link.

VERDICT: PASS
