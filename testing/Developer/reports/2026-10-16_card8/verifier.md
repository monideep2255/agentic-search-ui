# Card 8 fresh verifier report: the trust line names its databases

Pull request #259, branch `fix/card8-trust-line-names-databases`, head `62c6f1d3` on develop `78c68c1c`. Verified in a detached worktree at the head, 2026-10-16. Role: fresh verifier, carrying the correctness check and the hunt for a lying trust signal (dial 1, no judge or adversary ran).

## Table of contents

- [Findings](#findings)
- [Verdict code is byte identical](#verdict-code-is-byte-identical)
- [Tests](#tests)
- [Database names against what is cited](#database-names-against-what-is-cited)
- [The clause](#the-clause)
- [The 200 character cap](#the-200-character-cap)
- [Surfaces](#surfaces)
- [The explainer](#the-explainer)
- [Break it](#break-it)
- [Live runs](#live-runs)
- [Verdict](#verdict)

## Findings

### V-8-01, major: CI gate 4 is red on the pull request, three unit tests fail

Confirmed on the pull request's own run: `gh run view 38994713238 --log-failed`, "Gate 4: Unit test suite ... 3 failed, 7931 passed". The three:

- `test_the_stated_numbers_stay_as_on_develop[researcher]` and `[plain_language]` (below).
- `tests/system_03_search_agent/harness/test_tiers.py::test_no_model_id_shaped_string_outside_the_default_table`, reproduced locally (`1 failed, 21 passed`). The repository-wide guard against hardcoded model ids reads every `ncbi.nlm.nih.gov/<db>` key of the new `_DATABASE_NAMES` (`synthesis/trust.py:616` to `636`) as a `provider/model` string: "model-id-shaped string found outside harness/tiers.py's _DEFAULT_MODELS values ...: ["synthesis/trust.py:616: 'ncbi.nlm.nih.gov/assembly'", ...]". Fix inside the fence: build the keys from `_NCBI_HOST` (as `record_database` already does, `f"{_NCBI_HOST}/clinvar"`), never by loosening the guard.

The pinned-text failure:

- Evidence: `tests/system_03_search_agent/core/test_write_answer_structure.py:1908` to `1935`, `_DEVELOP_NUMBERS` pins "Based on 7 sources cited" and "Based on 1 source cited". On the branch:

```
FAILED tests/system_03_search_agent/core/test_write_answer_structure.py::test_the_stated_numbers_stay_as_on_develop[researcher]
FAILED tests/system_03_search_agent/core/test_write_answer_structure.py::test_the_stated_numbers_stay_as_on_develop[plain_language]
E         At index 1 diff: 'Based on 7 sources cited, all from ClinVar' != 'Based on 7 sources cited'
```

- Gate 4 runs `pytest -m "not integration" -q` over the whole suite (`.github/gates/gate04_unit_suite.sh`), so this file is in it. The build report lists the fixtures it updated and this one is not among them.
- Worse than develop for a person: no. The new line is the specified wording ("all from ClinVar" for seven ClinVar pages). It blocks the merge rule, which needs CI green. Fix inside the fence: update the pinned strings (test text only; the case_a and case_b rows will also need "from NCBI Gene").

### V-8-02, major: the rewritten explainer says two databases stated the high-stakes fact, which the clause does not require

- The new `TRUST_LINE_EXPLAINER` (`frontend/src/components/screens/AnswerScreen.tsx:131` to `137`) says: "When two or more databases state a high-stakes fact in values that cannot be matched, the line says their values could not be compared."
- The code adds the clause when the answer cites two or more databases overall and any high-risk claim came back `insufficient` (`synthesis/trust.py:802` to `807`). `triangulate` returns `insufficient` also when no other origin stated anything in that field (`trust.py:388` to `390`, `if not independent_origins: return "insufficient"`). So the second database need not state the fact at all.
- Probe `<scratchpad>/card8_ver/probe_clause.py`, real `trust_for_claims` verdicts, one ClinVar `clinical_significance` "Pathogenic" beside one MedGen disease name:

```
one ClinVar significance beside a MedGen name
  trusts [('high', 'insufficient', 'ask'), ('low', 'insufficient', 'answer')] outcome ask
  branch : Based on 2 sources cited from ClinVar and MedGen; their values could not be compared
  develop: Based on 2 sources cited, not yet confirmed
```

  Only ClinVar stated the significance. A reader who opens the explainer is told two databases stated it.
- Develop's explainer for the same answer was exact: "Not yet confirmed means a high-stakes fact has not been found in a second independent database, or this answer may be incomplete".
- Worse than develop: yes, in the explainer only. It tells the reader more evidence exists than the answer bears. The line's own words are the owner's and are not the finding (the diagnosis named the inexactness, "Needs the owner", row 2, and the owner kept them). Fixable in one round inside the fence: copy only, for example "When a high-stakes fact could not be checked against a second database, the line says their values could not be compared." The test at `AnswerScreen.card22.test.tsx:373` and `:374` pins only "names the databases" and "values could not be compared", so a corrected sentence keeps it green.

### V-8-03, minor: the display-name sweep compares the table with itself, so a wrong name stays green

- `test_every_page_database_maps_to_a_proper_name` and `test_every_curie_fallback_maps_to_a_proper_name` (`test_trust_line.py`) assert the line equals `_DATABASE_NAMES[key]`, the table under test. Mutation: `"clinvar": "ClinVar"` changed to `"clinvar": "dbSNP"` in the CURIE fallbacks, result `53 passed`. Only the names pinned literally elsewhere (MedGen, OMIM, ClinVar page, PubMed, NCBI Gene, ClinicalTrials.gov, dbSNP) are guarded.
- I read all 30 entries by hand against the tools' URL builders (`tools/ncbi_eutils_actions.py:494` to `520`, `ncbi_datasets_actions.py:324` to `336`, `pathogen_detection.py:632`, `litvar2_lookup.py:433`, `pubtator_annotate.py:438`, `clinicaltrials_search.py:266`): every mapping is correct today. Not worse than develop. A literal expected-name table in the test would close it.

### V-8-04, minor: on the BRCA1 disease question MedGen, the source of every disease record, folds into "3 other databases"

- Live run, query 1 (below): "Based on 21 sources cited from ClinicalTrials.gov, ClinVar, PubMed and 3 other databases; their values could not be compared". Pages per database: ClinVar 5, ClinicalTrials.gov 5, PubMed 5, MedGen 4, NCBI Gene 1, OMIM 1.
- This is exactly the owner's rule ("at four or more, the three most cited, then 'and N other databases'"), and it is true. But the four disease records the question asks for all come from MedGen, and the owner's own example for this question named "MedGen and OMIM". Not worse than develop and not a lie; recorded for the owner's retest, since a reader may expect the line to name where the answer's subject came from.

## Verdict code is byte identical

- AST comparison of every top-level definition in `synthesis/trust.py`, develop against the branch (`<scratchpad>/card8_ver/same.py`):

```
DIFF _DATABASE_NAMES
DIFF _databases_phrase
DIFF _join_names
DIFF answer_trust_line
decide identical
DECISION_TABLE identical
triangulate identical
aggregate identical
bucket_for identical
record_database identical
_databases_backing identical
```

- `git diff --quiet origin/develop...HEAD -- src/system_03_search_agent/core/` prints "core/ unchanged"; `frontend/src/hooks` and `SavedAnswerScreen.tsx` are unchanged too.
- Inside `answer_trust_line` the `refuse`, `flag` and "Confirmed by" branches are untouched; only the old two "not yet confirmed" returns and the final return were replaced (`trust.py:796` to `808`).
- The check mark and the tone key on the first word: `useRunView.ts:1018` `summary.startsWith("Confirmed") ? "good" : "plain"`, `SavedAnswerScreen.tsx:335` `answer.trust_line.startsWith("Confirmed")`. No new line starts with "Confirmed": every new line starts with `base = f"Based on {citation_count} {noun} cited"` (`trust.py:796`), and `test_only_the_confirmed_branch_starts_with_confirmed` sweeps over a thousand combinations.

## Tests

- The Python files the diff touches (new `test_trust_line.py`, `test_trust_line_names_its_count.py`, `test_answer_layout.py`, cli `test_s3_as_printed.py`, graphql `test_parity_fields.py`, mcp `test_no_cost_and_auth.py` and `test_parity_tools.py`, feedback `test_capture_saved_answer.py` and `test_outage_note_dated.py`): `446 passed, 2 warnings in 32.33s`. The new file alone: `53 passed`.
- Neighbours (graphql `test_types.py`, web_sse `test_saved_answer_endpoint.py`, core `test_graph.py`, `test_write_answer_structure.py`, `test_write_failed_search.py`, `test_layer_handoff.py`, `test_pubtator_act_cap.py`, all of `synthesis/`): `2 failed, 1271 passed, 10 skipped, 1 xfailed`, the two being V-8-01.
- Frontend, the six vitest files the diff touches: `Test Files 6 passed (6)`, `Tests 99 passed (99)`. `npx tsc --noEmit` printed nothing.
- `ruff check` over the repository: `All checks passed!`. isort on the two Python files the card adds to: clean.

## Database names against what is cited

- Every page key `record_database` can produce from the tools' URL builders maps to its correct name (V-8-03 lists the builders read). A key outside the table counts under "other databases" and is never printed: `parts = [_DATABASE_NAMES[key] for key in shown]` with `shown` drawn only from known keys (`trust.py:672` to `679`).
- A graph ClinVar row and a live ClinVar fetch are one database. Probe (real `trust_for_claims`), graph row and live fetch of one ClinVar record, both "Pathogenic": branch "Based on 1 source cited, from ClinVar". Live, query 22: the Sources list carries 54 pages labelled `ClinVar` (graph) and 5 labelled `clinvar` (live), and the line names ClinVar once.
- A PubMed page is PubMed: `pubmed.ncbi.nlm.nih.gov` keys to `ncbi.nlm.nih.gov/pubmed` (`record_database`, `trust.py:572`), named "PubMed" in all three live runs.
- The count: each page has exactly one `record_database` key, and `_databases_phrase` keys pages the same way `citation_count` does (`source_page_key(...) or citation_id`), so the databases named plus "N other" never exceed the pages, and the N in "Based on N sources cited" is card 22's count, untouched (`trust.py:771` to `776`). Live, each run's distinct cited pages equal the line's N: 21 and 21, 13 and 13, 71 and 71.
- Rows with no page cannot reach the line: `findings.py:588` to `589` skips a row with no `source_url`, so the empty key and the CURIE fallback are unreachable in practice.

## The clause

- Condition (`trust.py:802` to `807`): `trust_outcome == "ask"`, `database_count >= 2`, and a claim in `high` (risk tier high) with triangulation `insufficient`.
- Floor-only ask: live query 22, outcome `ask`, every claim low risk (`"low/insufficient": 72`), two or more databases: no clause. Unit: `test_ask_two_databases_from_a_floor_only_has_no_clause`.
- All-low-risk ask: same live run; unit `test_ask_two_databases_all_low_risk_has_no_clause`.
- Single-database ask: unit `test_ask_one_database_has_no_clause`; probe "graph and live ClinVar" reads "from ClinVar" with no clause.
- Live query 1: outcome `ask`, four high-risk disease names from MedGen `insufficient`, six databases: clause shown, which the owner's rule requires.
- Pre-existing, not worse: when one claim is discordant and another uncomparable, `aggregate` ranks `ask` over `flag` (`trust.py:477`), so develop said "not yet confirmed" and the branch says "their values could not be compared"; neither says the sources disagree. Probe output: "Based on 3 sources cited from ClinVar, dbSNP and LitVar2; their values could not be compared" against develop "Based on 3 sources cited, not yet confirmed".

## The 200 character cap

- At most three names are printed, and the longest is 18 characters ("Pathogen Detection", "ClinicalTrials.gov"). Probe `<scratchpad>/card8_ver/probe_cap.py`, all 23 page databases plus an unknown one, 1521 pages, the clause on: 145 characters, "Based on 1521 sources cited from ClinicalTrials.gov, NCBI Datasets, Pathogen Detection and 21 other databases; their values could not be compared". The new test's sweep asserts the cap over more than a thousand lines. Live lines: 124, 86 and 88 characters.

## Surfaces

- Saved answer: the stored line is read back unchanged (`feedback/history.py:426` `trust_line=row.answer_trust_line`, `adapters/web_sse/app.py:1164`) and shown as stored (`SavedAnswerScreen.tsx:333` to `335`, unchanged). Old rows keep "not yet confirmed", as the diagnosis accepts. `test_saved_answer_endpoint.py` and `SavedAnswerScreen.test.tsx` pass.
- Command line: `_trust_line_text` prints `done.trust_line` through `_single_line` (`adapters/cli/render.py:961` to `979`); the semicolon is not special. `test_s3_as_printed.py` passes with the new text.
- MCP: `trust_line` passes through with `max_length=200` (`adapters/mcp/server.py:456` to `459`, `1218`); its tests pass.
- GraphQL: `_parity_fields` reports the line unchanged when the fold's verdict equals `done`'s (`adapters/graphql/fold.py:945` to `975`); `test_parity_fields.py` passes.
- Nothing in `src/` or `frontend/src/` parses the old words; a grep for "not yet confirmed" finds only comments and evidence files.

## The explainer

- True: "A Based on line names the databases the cited pages come from, the three most cited when there are four or more."
- Not true in every case the clause shows: V-8-02.

## Break it

Each mutation one property, restored with `git checkout -- <file>`, tree clean after (`git status --short` shows only the linked `frontend/node_modules`):

| Mutation | Result |
|---|---|
| Clause over `claim_trusts` instead of `high` (the `high` filter dropped) | `1 failed, 52 passed`, `test_ask_two_databases_all_low_risk_has_no_clause` |
| Unknown keys printed raw | `2 failed, 51 passed` |
| Clause at one database (`database_count >= 1`) | `3 failed, 50 passed` |
| Four names shown instead of three | `3 failed, 50 passed` |
| Clause on `answer` too | `53 passed`. Unreachable: `answer` with a high-risk `insufficient` claim cannot occur, since `insufficient` decides `ask` and every later step only lowers the outcome (`core/graph.py:14796` to `14907`). Evidence, not a finding |
| CURIE fallback `clinvar` named "dbSNP" | `53 passed`, V-8-03 |

## Live runs

Through `core.run.run_streaming()` on this worktree, develop's settings (`CLASSIFIER_PROVIDER=jev`, guard and plan models as develop, `PER_QUERY_COST_CAP_USD=0.25`, synthesis model from the local environment), Researcher, session ids `card8-ver-q1`, `card8-ver-q66`, `card8-ver-q22`. Script `<scratchpad>/card8_ver/live.py` wraps `answer_trust_line` to record its inputs and develop's line for the same inputs.

| Query | Outcome | Branch line | Develop line, same inputs | Pages per database | Seconds | Spend |
|---|---|---|---|---|---|---|
| 1, BRCA1 diseases | ask | Based on 21 sources cited from ClinicalTrials.gov, ClinVar, PubMed and 3 other databases; their values could not be compared | Based on 21 sources cited, not yet confirmed | ClinVar 5, ClinicalTrials.gov 5, PubMed 5, MedGen 4, NCBI Gene 1, OMIM 1 | 12.6 | $0.0115 |
| 66, Marfan features | answer | Based on 13 sources cited from ClinicalTrials.gov, PubMed, MedGen and 1 other database | Based on 13 sources cited | ClinicalTrials.gov 5, PubMed 5, MedGen 2, MeSH 1 | 14.9 | $0.0086 |
| 22, CFTR variants | ask | Based on 71 sources cited from ClinVar, ClinicalTrials.gov, PubMed and 2 other databases | Based on 71 sources cited, not yet confirmed | ClinVar 59, ClinicalTrials.gov 5, PubMed 5, NCBI Gene 1, OMIM 1 | 14.0 | $0.0085 |

- Each line's databases match the run's citation events tallied by page (query 1: 21 distinct pages over 31 citation events; query 66: 13 over 95; query 22: 71 over 72).
- A fourth run, the first attempt at query 1, crashed inside my own probe (a tuple key in `json.dumps` in the wrapper, `live.py:96`), not in the product; fixed and rerun. Total spend about $0.03 over four runs, within $0.75.
- The trust line costs no model call and a loop over the cited claims, so speed is unchanged.

## Verdict

Two things are worse or block the merge, both fixable inside the card's fence in one round:

- V-8-01: CI gate 4 red, three tests (two pinned strings, one model-id guard tripped by the new table's literal keys).
- V-8-02: the rewritten explainer says two databases stated the high-stakes fact whenever the clause shows; the code does not require it, and develop's explainer was exact.

V-8-03 and V-8-04 are minor and not worse than develop.

VERDICT: FIX FIRST
