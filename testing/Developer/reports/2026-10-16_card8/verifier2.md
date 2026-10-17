# Card 8 second fresh verifier report: after the fix round

Pull request #259, branch `fix/card8-trust-line-names-databases`, build commit `62c6f1d3`, fix commit `fff8b91b`, on develop `78c68c1c`. Verified in a detached worktree at `fff8b91b`, 2026-10-16. Role: fresh verifier after the one fix round. Probes in `<scratchpad>/card8_ver2/`.

## Table of contents

- [Findings](#findings)
- [The rebuilt table against the first commit's table](#the-rebuilt-table-against-the-first-commits-table)
- [V-8-01: gate 4 and the guard](#v-8-01-gate-4-and-the-guard)
- [V-8-02: the explainer against the code's condition](#v-8-02-the-explainer-against-the-codes-condition)
- [V-8-03: the name test is independent of the table](#v-8-03-the-name-test-is-independent-of-the-table)
- [Broad checks against the new commit](#broad-checks-against-the-new-commit)
- [Tests and lint](#tests-and-lint)
- [Live runs](#live-runs)
- [CI on the pushed commit](#ci-on-the-pushed-commit)
- [Verdict](#verdict)

## Findings

### V-8-05, major: the rewritten explainer promises the clause in a case where the code adds none

Inside the fix commit's new copy (`fff8b91b`, `frontend/src/components/screens/AnswerScreen.tsx:136` to `138`), so this is a finding inside a fix made in this card (Review rounds, Rule 4). Regression of: V-8-02.

- The sentence: "When an answer rests on two or more databases and a high-stakes fact could not be checked against a second one, the line adds "their values could not be compared"."
- The code's condition (`synthesis/trust.py:804` to `809`): outcome `ask`, two or more cited databases, and a high-risk claim whose triangulation is `insufficient`.
- `triangulate` counts independence by `_origin_of` (`trust.py:353` to `365`: the CURIE prefix, else the TOOL), not by database. A graph ClinVar row (`cypher_query`) and a live fetch of the same ClinVar record (`ncbi_efetch`) are two origins, so the high-stakes fact comes back `concordant`, not `insufficient`, though no second database ever checked it. The trust code itself records that this pairing occurs in real answers (`trust.py:730` to `731`, card 22: "a graph ClinVar row beside a live fetch of the same record read "Confirmed by 2"").
- Probe `<scratchpad>/card8_ver2/probe_explainer.py`, real `trust_for_claims` verdicts, case F (graph ClinVar significance "Pathogenic", live fetch of the same record "Pathogenic", one MedGen disease name):

```
F high fact checked only against a live fetch of the same ClinVar record, MedGen beside
  trusts [('high', 'concordant', 'answer'), ('high', 'concordant', 'answer'), ('low', 'insufficient', 'answer')] outcome answer dbs ['ncbi.nlm.nih.gov/clinvar', 'ncbi.nlm.nih.gov/medgen']
  branch : Based on 2 sources cited from ClinVar and MedGen
  develop: Based on 2 sources cited, not yet confirmed
```

- The answer rests on two databases and the high-stakes fact was not checked against a second database, which is exactly the explainer's condition, yet the line carries no clause. A reader who opens the explainer and sees no clause is told, by the sentence's own condition, that every high-stakes fact was checked against a second database. Only ClinVar stated it.
- The same holds for a floor `ask` with a concordant same-database fact (the clause needs `insufficient`).
- Develop for the same answer: the line "not yet confirmed" and the explainer "Not yet confirmed means a high-stakes fact has not been found in a second independent database, or this answer may be incomplete", which is exact for case F.
- The line's own loss of "not yet confirmed" is the owner's accepted change and is not this finding. The finding is the explainer's new sentence, which says more than the answer bears for a reachable state.
- Worse than develop: yes, in the explainer only, for an answer whose high-stakes fact was matched only within one database. Fixable inside the fence by copy alone, describing the code's actual condition, for example "When an answer rests on two or more databases and a high-stakes fact had no other record to compare with, or values that could not be matched, the line adds ...". In case F the fact was compared with another record and matched, so that sentence stays true, and "Confirmed means two or more independent databases agree" (unchanged) tells the reader it was not two databases. The pinned test at `AnswerScreen.card22.test.tsx:374` to `376` (the sentence at `:375`) pins the current sentence and would need the same edit.
- The direction V-8-02 found is closed: whenever the clause shows, a high-risk claim is `insufficient`, which means either no other origin stated that field or a value fell outside the bucket table (`trust.py:388` to `400`), so the fact was not checked against a second database. The sentence is true whenever the clause shows; it is false only in the converse.

## The rebuilt table against the first commit's table

- Probe `<scratchpad>/card8_ver2/table_diff.py` evaluates only the `_NCBI_HOST`, `_NCBI_DATABASE_NAMES`, `_NCBI_RESEARCH_NAMES` and `_DATABASE_NAMES` assignments of each commit's `synthesis/trust.py` and compares the two dicts:

```
first commit entries: 30  fix commit entries: 30
keys only in first: []
keys only in fix: []
name differences: {}
identical dicts: True
order identical: False
```

- The insertion order differs (the CURIE fallbacks and the two non NCBI hosts now follow the comprehensions). Order cannot reach the reader: `_databases_phrase` iterates `pages` (claim order), filters by `key in _DATABASE_NAMES`, and sorts by `(-pages, name.casefold())` (`trust.py:672` to `675`); the table is only looked up, never iterated.
- `_NCBI_HOST = "ncbi.nlm.nih.gov"` is defined at `trust.py:534`, before the table, and is the same constant `record_database` builds every NCBI key from (`trust.py:569` to `576`), so the two cannot drift apart.
- Every key `record_database` can return is either one of these 30 (same name in both commits) or absent from both (counted under "other databases" in both). So the fix commit names every database exactly as the first commit did.

## V-8-01: gate 4 and the guard

- The guard is untouched: `git diff --stat origin/develop...HEAD -- tests/system_03_search_agent/harness/ src/system_03_search_agent/harness/` prints nothing.
- The guard scans string constants under `src/` only (`harness/test_tiers.py:246`, `_SRC_ROOT.rglob("*.py")`, `ast.Constant`). The new keys are f-strings over `_NCBI_HOST` (`trust.py:638` to `639`), the same construction `record_database` uses (`trust.py:569` to `576`); the literal `ncbi.nlm.nih.gov/...` keys in `_EXPECTED` sit in `tests/`, outside its scan. This is the fix the first verifier named, not a loosening.
- The two pinned tests now carry the new text (`test_write_answer_structure.py:1909` to `1940`), counts unchanged: "Based on 7 sources cited, all from ClinVar" and "Based on 1 source cited, from NCBI Gene".
- Local, the three previously red tests plus the new file: `77 passed in 23.46s` (`test_tiers.py`, `test_trust_line.py`, `test_the_stated_numbers_stay_as_on_develop`).
- CI gate 4 on `fff8b91b`: `7934 passed, 143 skipped, 24 deselected, 1 xfailed` (below). Closed.

## V-8-02: the explainer against the code's condition

- The direction the first verifier found is closed: every time the clause shows, a high-risk claim is `insufficient`, which `triangulate` returns only when no other origin stated the field or a value fell outside the bucket table (`trust.py:388` to `400`). In both, the fact was not checked against a second database, so "a high-stakes fact could not be checked against a second one" is true. Case A of the probe (one ClinVar significance beside a MedGen name, the one-database-states-the-fact case) reads "Based on 2 sources cited from ClinVar and MedGen; their values could not be compared", and the explainer is true of it.
- The converse is false in a reachable case, V-8-05: a high-stakes fact matched only between a graph row and a live fetch of the same ClinVar record is `concordant`, so no clause shows, although the explainer's condition holds.
- The `ask` term the explainer omits is harmless: a high-risk `insufficient` claim decides `ask` (`DECISION_TABLE`, `trust.py:415`), `aggregate` takes the most restrictive (`_SEVERITY`, `trust.py:474`), and every later step in Write only aggregates with `ask` (`core/graph.py:14796`, `14798`, `14836`, `14888`, `14907`), so a Based on line with such a claim is always an `ask` line.
- All six probe cases, real verdicts, branch against develop (`<scratchpad>/card8_ver2/probe_explainer.py`):

| Case | Branch | Develop | Explainer exact |
|---|---|---|---|
| A, high fact in ClinVar only, MedGen beside | Based on 2 sources cited from ClinVar and MedGen; their values could not be compared | Based on 2 sources cited, not yet confirmed | yes |
| B, ClinVar and dbSNP, one value outside the table | Based on 2 sources cited from ClinVar and dbSNP; their values could not be compared | Based on 2 sources cited, not yet confirmed | yes |
| C, high fact in ClinVar, every page ClinVar | Based on 2 sources cited, all from ClinVar | Based on 2 sources cited, not yet confirmed | yes, one database |
| E, all low risk, two databases | Based on 2 sources cited from MedGen and NCBI Gene | Based on 2 sources cited | yes |
| F, graph and live ClinVar agree, MedGen beside | Based on 2 sources cited from ClinVar and MedGen | Based on 2 sources cited, not yet confirmed | no, V-8-05 |
| G, ClinVar and dbSNP agree | Confirmed by 2 independent databases | Confirmed by 2 independent databases | yes |

## V-8-03: the name test is independent of the table

- `_EXPECTED` and `_CURIE_EXPECTED` (`test_trust_line.py:260` to `293`) are written out by hand: each key, a real page, and the literal name. The two sweep tests assert against those literals, not `_DATABASE_NAMES`, and `test_the_expected_mapping_covers_every_table_key` fails if the table gains or loses a key.
- One-entry mutations of `trust.py`, each restored with `git checkout`:

| Mutation | Result |
|---|---|
| NCBI path `medgen` named "OMIM" | `11 failed, 42 passed` |
| CURIE `dbsnp` named "SNP" | `1 failed, 52 passed` |
| research path `pubtator3` named "PubTator" | `1 failed, 52 passed` |
| `clinicaltrials.gov` entry removed | `2 failed, 51 passed` |

- The builder's own mutation (`clinvar` to "ClinVarX", 7 red) is consistent. Closed.

## Broad checks against the new commit

- Verdict code byte identical to develop, by AST (`<scratchpad>/card8_ver2/same.py`): `decide`, `DECISION_TABLE`, `triangulate`, `aggregate`, `bucket_for`, `record_database`, `_databases_backing`, `_origin_of`, `trust_for_claims`, `_SEVERITY`, `_NCBI_HOST` identical; 24 of develop's 25 top level definitions identical, the 25th being `answer_trust_line`. Inside it only the docstring and the three old "Based on" returns changed; the `refuse`, `flag` and "Confirmed by" branches are unchanged.
- Unchanged against develop: `src/system_03_search_agent/core/`, `adapters/cli/`, `adapters/graphql/`, `adapters/web_sse/`, `feedback/`, `frontend/src/hooks/`, `SavedAnswerScreen.tsx`. `adapters/mcp/server.py`, `contracts/events.py` and `frontend/src/lib/events.ts` change one comment line each.
- "Confirmed" keying untouched: `useRunView.ts:1018` `summary.startsWith("Confirmed") ? "good" : "plain"`, `SavedAnswerScreen.tsx:335` `answer.trust_line.startsWith("Confirmed")`. Every new line starts with `base = f"Based on ..."`.
- 200 character cap: at most three names (longest 18 characters). Probe `<scratchpad>/card8_ver2/probe_cap.py`, over 9000 pages across the longest names plus 40 unknown hosts, clause on: 145 characters, "Based on 9040 sources cited from ClinicalTrials.gov, NCBI Datasets, Pathogen Detection and 40 other databases; their values could not be compared". MCP keeps `max_length=200` (`adapters/mcp/server.py:456` to `459`).
- Surfaces pass the text through unchanged: command line, MCP, GraphQL and saved answer files are unchanged except the comment, and their tests pass with the new text (below). A saved answer shows its stored line (`SavedAnswerScreen.tsx:333` to `335`, unchanged).
- Speed: the line adds one loop over the cited claims and no model call.

## Tests and lint

- `tests/system_03_search_agent/synthesis/`, `harness/test_tiers.py`, `core/test_write_answer_structure.py`, adapters cli `test_s3_as_printed.py`, graphql `test_parity_fields.py`, mcp `test_no_cost_and_auth.py` and `test_parity_tools.py`, feedback `test_capture_saved_answer.py` and `test_outage_note_dated.py`: `1146 passed, 10 skipped, 1 xfailed, 2 warnings in 58.33s`.
- Neighbours `web_sse/test_saved_answer_endpoint.py`, `graphql/test_types.py`, `core/test_write_failed_search.py`: `91 passed, 2 warnings in 11.61s`.
- Frontend, the six vitest files the diff touches: `Test Files 6 passed (6)`, `Tests 99 passed (99)`. `npx tsc --noEmit`: exit 0, no output.
- `ruff check` with no path: `All checks passed!`, exit 0. `isort --check-only --diff src tests services tracker alembic .claude .github`: exit 0, "Skipped 2 files".

## Live runs

Two runs through `core.run.run_streaming()` on this worktree, develop's settings as the card 115 adversary used them (`CLASSIFIER_PROVIDER=jev`, guard and plan models as develop, `PER_QUERY_COST_CAP_USD=0.25`), Researcher, session ids `card8-ver2-q1` and `card8-ver2-q22`. Script `<scratchpad>/card8_ver2/live.py` (the first verifier's, session prefix changed) records the line's inputs; `<scratchpad>/card8_ver2/tally.py` tallies the citation events' pages per database from their URLs, independently of `record_database`.

| Query | Outcome | Trust line, pasted | Pages per database from the citation events | Seconds | Spend |
|---|---|---|---|---|---|
| 1, `Which diseases are associated with BRCA1?` | ask | Based on 21 sources cited from ClinicalTrials.gov, ClinVar, PubMed and 3 other databases; their values could not be compared | pubmed 5, clinvar 5, clinicaltrials.gov 5, medgen 4, gene 1, omim.org 1 (21 pages) | 11.9 | $0.0105 |
| 22, `Which clinically significant variants have been reported in CFTR?` | ask | Based on 71 sources cited from ClinVar, ClinicalTrials.gov, PubMed and 2 other databases | clinvar 59, pubmed 5, clinicaltrials.gov 5, gene 1, omim.org 1 (71 pages) | 13.8 | $0.0111 |

- Query 1: six databases, the three named are the three most cited (5 each, ties by name), and "3 other databases" are MedGen, NCBI Gene and OMIM. The four high-risk claims are MedGen disease names, `insufficient` (no other origin but `clinicaltrials_search` stated a name, outside the bucket table), so the clause is the owner's rule. The first verifier's V-8-04 (MedGen folding into "other") reproduces; not worse than develop.
- Query 22: 54 graph and 5 live ClinVar pages name ClinVar once; all 72 claims low risk, so no clause on a floor `ask`. Correct.
- Develop's line for the same inputs: "Based on 21 sources cited, not yet confirmed" and "Based on 71 sources cited, not yet confirmed".
- Both runs log a non fatal `CallerIdentityRequired` from session memory because the script passes no owner id; the answer completes. Total spend about $0.022, within $0.30.

## CI on the pushed commit

- `gh pr view 259`: head `fff8b91ba55145fcea2a816728940e5bdd557ba8`, open. Run 38999720545, head sha the same, `completed success`.
- `gh pr checks 259`: Accessibility (10) pass, Frontend gates (7, 8) pass, Integration suite (5) pass, Python gates (1, 2, 3, 4, 6, 9) pass.
- Gate 4 log: `7934 passed, 143 skipped, 24 deselected, 1 xfailed, 7 warnings in 341.68s`.

## Verdict

- V-8-01 and V-8-03 are closed; the rebuilt table names every database exactly as the first commit did; CI is green; the verdict code, surfaces, keying and cap are as on develop or better.
- One thing is worse than develop: V-8-05, the fix round's new explainer sentence promises the clause whenever a high-stakes fact could not be checked against a second database, and the code omits it when the fact was matched only within one database (graph and live fetch of one ClinVar record). The reader of the explainer is told more checking happened than did. It is copy only, inside the fence, but it sits inside this card's fix (Review rounds, Rule 4), and the card's one fix round is spent (Rule 3), so it goes to the lead and the owner as named.
- Tree: `git status --short` shows only `?? frontend/node_modules`, the expected link.

VERDICT: FIX FIRST
