# Bossman redesign deletion inventory

What decision 5 of the 2026-09-24 bossman redesign, and the redesign's move from per-round report files to ledger rows, would delete. Nothing listed here has been deleted. The lead shows this list to the product owner, and nothing is removed until they approve it.

The decision, from `DECISIONS.md` (2026-09-24): "Delete premise gates, mutation harness files and coverage claims for everything except answer behaviour; mutation stays as one judge checklist line." The source is `docs/build/Bossman_mode_redesign.md`: Part 3's decision 5, and Part 2's Step 2.

Measured on 2026-09-24 against the working tree.

## Table of contents

- [The totals](#the-totals)
- [How a file was classed](#how-a-file-was-classed)
- [Test files to delete](#test-files-to-delete)
- [Test files the owner should rule on](#test-files-the-owner-should-rule-on)
- [Test files kept as answer behaviour](#test-files-kept-as-answer-behaviour)
- [Frontend test files to delete](#frontend-test-files-to-delete)
- [Tracker report files to delete](#tracker-report-files-to-delete)
- [Premise-gate and mutation text removed from skills and docs](#premise-gate-and-mutation-text-removed-from-skills-and-docs)
- [What else must change in the same commit as the deletions](#what-else-must-change-in-the-same-commit-as-the-deletions)

## The totals

| Group | Files | Lines | Tests collected |
|---|---|---|---|
| Python test files to delete | 23 | 22,037 | 563 |
| Python test files for the owner to rule on | 7 | 4,222 | 100 |
| Python test files kept as answer behaviour: premise gates | 15 | 10,819 | 178 |
| Python test files kept as answer behaviour: mutation harnesses | 4 | 2,149 | 75 |
| Frontend test files to delete | 5 | 3,079 | 87 |
| Tracker per-round report files to delete | 50 | 20,465 | n/a |

The Python test count, from `pytest --collect-only -q`, the invocation `.github/gates/gate04_unit_suite.sh` runs (`-m "not integration"`), with each deleted file passed as `--ignore` so a broken import would show as a collection error. None did.

| Suite | Today | After the delete list | After the delete list and the owner-ruled list |
|---|---|---|---|
| Unit gate, `-m "not integration"` | 5,952 of 5,975 | 5,389 of 5,412 | 5,289 of 5,312 |
| Every test collected | 5,975 | 5,412 | 5,312 |
| Frontend unit tests (vitest) | 546 | 459 | 459 |

Every premise file is collected in the unit gate. Most of their arms skip there, since the live arms need `RUN_PREMISE_GATE=1` and CI leaves it unset, so the drop in tests that actually execute in CI is smaller than the drop in tests collected. That split was not measured.

The redesign's own figure for the report files, 51 files and 20,932 lines, included `tracker/locked_docs_readability_report.md`, a doc-readability run report rather than a review round. It is left out here and should not be deleted: `requirements/Plan.md`, `requirements/phase_6/Phase_6_history.md` and `tracker/doc_readability_runs.md` link to it.

## How a file was classed

A file is answer behaviour when a broken version of what it checks would change what a person reads in an answer. Those files stay. What a person reads means:

- The words.
- The records the answer names, and its citations.
- Whether the question is answered or refused.

A file that checks a delivery surface, auth, CI, deployment, observability, rate limiting or the evaluation instruments is not answer behaviour, whatever else it protects. Those files are on the delete list.

Four groups did not fit cleanly. They are listed for the owner to rule on rather than decided here.

The decision says mutation harness files go "for everything except answer behaviour", so the four mutation harnesses that guard answer-behaviour gates are listed as kept. The redesign's Step 1 would go further and keep only the golden run as the answer-path premise check. If the owner reads the decision that way, those four files, 2,149 lines and 75 tests, join the delete list.

How imports were checked:

- A search for `import`, `from`, `importlib` and quoted path loads of each module, across `tests/`, `.github/`, `tracker/`, `src/` and `services/`.
- Then proof: the suite collected with every deleted file ignored, and no kept file failed to collect.
- Mentions in docstrings and comments are listed separately. Deleting a file leaves them stale rather than broken.

## Test files to delete

Every file under `tests/system_03_search_agent/` is written from that folder down.

| File | Lines | Tests | What it checks | Why it is not answer behaviour | Imported by, or read by CI | Security or cost property at stake |
|---|---|---|---|---|---|---|
| `tests/ci/test_ci_workflow_premise.py` | 689 | 31 | Each CI gate step runs exactly one canonical script; the workflow stays unfiltered on pull requests (arm P8) | CI configuration | Its mutation file, below, at module level. `.github/workflows/ci.yml` line 48 says "The premise gate's P8 arm fails if one appears"; that comment becomes false. `tests/ci/test_gate_scripts.py` names it in a docstring | Yes: a neutralised gate reads green. Check `tests/ci/test_gate_scripts.py` covers the canonical-command property before deleting |
| `tests/ci/test_ci_workflow_mutation.py` | 532 | 44 | That the CI premise arms can fail | Mutation harness over CI configuration | Nothing | Goes with the file above |
| `adapters/cli/test_phase_4_2_premise.py` | 1,745 | 28 | `s3 ask` streams the same cited answer as the web app, with the credential file at mode 600 and refresh-token rotation | CLI delivery surface | Nothing. Named in docstrings of five `adapters/cli/` tests and in `src/.../adapters/cli/render.py` | Yes: credential file permissions and rotation |
| `adapters/graphql/test_phase_4_3_premise.py` | 2,478 | 64 | GraphQL returns the REST answer as typed fields; a refusal is a success; no cost field; document depth, alias and token bounds; introspection off | GraphQL delivery surface | Nothing. Named in docstrings of four `adapters/graphql/` tests | Yes: hostile-document bounds and auth. `adapters/graphql/test_security.py` covers part; check the rest |
| `adapters/mcp/test_phase_4_1_premise.py` | 2,219 | 49 | One MCP tool, one JSON result, cite-or-refuse, no cost field, no core loop without a valid bearer token | MCP delivery surface | Nothing. Named in docstrings of six tests and `src/.../feedback/coverage.py` | Yes: auth before the loop, no cost field |
| `adapters/web_sse/test_phase_4_0_premise.py` | 975 | 26 | Resumable streams, multi-consumer reads, eviction, cancellation on abandonment, the citations export, server-side `operator_mode` | REST and SSE transport | Nothing. Named in docstrings of five tests | Yes: `operator_mode` derived server-side |
| `adapters/web_sse/test_phase_4_10_premise.py` | 2,182 | 36 | A guest completes five runs without an account, the server decides when the fifth is spent, and no guest can read, stop or spend another caller's runs | Guest allowance and run ownership | Nothing. `.github/scripts/assert_no_db_skips.py` names it in its docstring only | Yes: guest isolation. `data/test_guest_sessions.py` and `auth/test_get_caller_guest_liveness.py` cover parts; check the rest |
| `adapters/web_sse/test_phase_4_13_premise.py` | 752 | 11 | Search history survives a reload, shows only the caller's own questions, and follows a guest into a new account | History read path | Nothing. Named in docstrings of three tests | Yes: one person never sees another's questions |
| `core/test_feedback_capture_premise.py` | 1,254 | 20 | Every completed query leaves exactly one `interactions` row attributed to the asker | Interaction capture | Nothing. Named in `tests/conftest.py` (a comment), `tools/test_demo_deploy_premise.py` (a path list), four feedback tests and `src/.../feedback/coverage.py` | Yes: the per-user and system daily caps count these rows |
| `core/test_rate_limit_concurrency_premise.py` | 631 | 9 | At most 20 Layer 2 and Layer 3 calls per query, counted at the transport chokepoints; the queue wait ceiling follows the query's latency budget | Rate limiting | Imported by its mutation file only | Yes: the per-query call ceiling |
| `core/test_rate_limit_concurrency_mutation.py` | 420 | 13 | That the rate-limit arms can fail | Mutation harness | Nothing | Goes with the file above |
| `eval/test_phase_5_2_premise.py` | 643 | 25 | The parked grading harness: rubric, hard-fails, pass@k | The evaluation instrument, parked because it does not work | Its mutation file, below. The 5.1 premise names it in a docstring | No |
| `eval/test_phase_5_2_mutation.py` | 464 | 28 | That the grading arms can fail | Mutation harness over the parked grader | Nothing | No |
| `eval/test_phase_5_2_regression_mutation.py` | 154 | 11 | That the P12 regression arms can fail | Mutation harness over the parked grader | Nothing | No |
| `eval/test_phase_5_3_premise.py` | 509 | 21 | Golden schema v2, `must_reach` and `live_only` | The evaluation instrument; no golden row uses either field | Its mutation file, below | No |
| `eval/test_phase_5_3_mutation.py` | 325 | 15 | That the 5.3 arms can fail | Mutation harness | Nothing | No |
| `export/test_kgx_export_premise.py` | 427 | 8 | A KGX export of TP53 holds exactly the 12 disease edges read from the live graph | The KGX export surface | Nothing. Named in docstrings of two export tests and the demo-deploy path list | No |
| `observability/test_observability_premise.py` | 708 | 9 | The real bypass callers reach the audit chokepoints; tracing carries no account data | Observability | Nothing | Yes: account data kept out of traces, audit completeness |
| `observability/test_observability_mutation.py` | 1,626 | 30 | That the six observability properties can fail | Mutation harness | Nothing | Goes with the file above |
| `tools/test_demo_deploy_premise.py` | 408 | 28 | Build phase 4.12's code-side deliverables, including the proxy's handling of `X-Forwarded-For`, and that premise files skip honestly | Deployment | Its mutation file only. `services/graph_query_service/app.py` names it in a comment | Yes: the forwarded-address rule the graph service's rate limit rests on |
| `tools/test_demo_deploy_mutation.py` | 394 | 14 | That the demo-deploy arms can fail | Mutation harness | Nothing | Goes with the file above |
| `tools/test_release_environments_premise.py` | 1,334 | 15 | Develop and production are separate apps with separate databases and signing keys, and the release flow | Release and deployment | Its mutation file only | Yes: separate signing keys per app |
| `tools/test_release_environments_mutation.py` | 1,168 | 28 | That the release arms can fail | Mutation harness | Nothing | Goes with the file above |

Where the last column says yes, deleting the file may delete the only test of a security or cost control, which `production-standards` requires. The recommendation, not a decision: before deleting, check whether an ordinary test pins the property, and where none does, move that one arm into an ordinary test file first. An ordinary test is not a premise gate, so this keeps decision 5 and the security standard together.

## Test files the owner should rule on

| File | Lines | Tests | What it checks | Why it is borderline | Imported by |
|---|---|---|---|---|---|
| `core/test_phase_4_16_premise.py` | 496 | 5 | The Act step's events reach the wire as each tool runs, not all at the end | It is about when a person sees progress, not what the answer says. The product reviewer's time to answer measures the effect a person feels | `core/test_write_streaming_premise.py`, `core/test_write_streaming_mutation.py` and its own mutation file import it at module level |
| `core/test_phase_4_16_mutation.py` | 325 | 7 | That the 4.16 arms can fail | Goes with the file above | Nothing |
| `core/test_write_streaming_premise.py` | 446 | 4 | The Write step's answer events stream as they are produced | Same as 4.16 | Its mutation file |
| `core/test_write_streaming_mutation.py` | 178 | 5 | That the streaming arms can fail | Goes with the file above | Nothing |
| `eval/test_phase_5_1_premise.py` | 303 | 10 | The golden dataset cannot be authored circularly, and its rows meet the schema | The blocking golden run reads this dataset's questions, so these arms guard the input to decision 3's check | Its mutation file |
| `eval/test_phase_5_1_mutation.py` | 206 | 10 | That the 5.1 arms can fail | Goes with the file above | Nothing |
| `tools/test_graph_query_service_premise.py` | 2,268 | 59 | The HTTPS graph transport returns the same rows the direct connection did, behind a bearer credential, a row limit and a per-caller rate limit | A transport fault would change which records an answer names, and the file also pins the service's security budget | Nothing. Named in docstrings of three tests and `services/graph_query_service/README.md` |

The four streaming files must be deleted or kept together: three of them import `core/test_phase_4_16_premise.py` at module level, and deleting it alone breaks collection.

## Test files kept as answer behaviour

Premise gates, 15 files, 10,819 lines, 178 tests:

- `tools/test_cypher_query_premise.py`: does `cypher_query` answer the question asked. `tracker/check_doc_drift.py` reads its test count, so it must stay for the drift checker too.
- `tools/test_ncbi_efetch_premise.py`, `tools/test_ncbi_dbsnp_premise.py`, `tools/test_pubtator_annotate_premise.py`, `tools/test_litvar2_lookup_premise.py`, `tools/test_pathogen_detection_premise.py`, `tools/test_clinicaltrials_search_premise.py`: the six other live tool gates, whether each tool tells the truth about what its source returns.
- `core/test_write_grounding_premise.py`: cite-or-refuse on the written answer. `eval/test_write_step_eval_gate.py` imports from it.
- `core/test_guardrail_premise.py`: whether a question is admitted or refused.
- `core/test_cq_routing_premise.py`: whether the loop resolves the question's actual subject.
- `core/test_discontinued_gene_premise.py`: a withdrawn gene is never answered as its successor.
- `core/test_injection_steering_premise.py`: injected text never chooses which gene is looked up.
- `core/test_personalization_premise.py`: depth and memory never change which claims are grounded.
- `core/test_answer_readability_premise.py`: an answer names diseases in words.
- `synthesis/test_citation_trust_full_premise.py`: the trust signal is true once a second layer can check it.

Mutation harnesses over answer-behaviour gates, 4 files, 2,149 lines, 75 tests, kept under the decision's wording and open to the owner's reading above: `core/test_cq_routing_mutation.py`, `core/test_discontinued_gene_mutation.py`, `core/test_injection_steering_mutation.py`, `synthesis/test_depth_directive_mutation.py`.

`tests/system_03_search_agent/graph_gate.py`, the shared live-graph helper, stays: six kept premise files use it.

## Frontend test files to delete

| File | Lines | Tests | What it checks | Why it is not answer behaviour | Imported by |
|---|---|---|---|---|---|
| `frontend/src/landingAlignmentPremise.test.tsx` | 91 | 3 | The landing screen's controls in the prototype's order and labels | Presentation. The product reviewer's side-by-side at 1280 and 390 replaces it | Nothing |
| `frontend/src/phase410Premise.test.tsx` | 699 | 17 | The guest allowance's frontend half | Guest flow presentation | Nothing. `src/App.test.tsx` and `e2e/auth-signin-and-errors.spec.ts` mention it |
| `frontend/src/phase48Premise.test.tsx` | 954 | 26 | Every prototype screen exists in the app, built from design tokens | Presentation | Nothing |
| `frontend/src/phase49Premise.test.tsx` | 812 | 21 | The run and answer screens show what the prototype shows, in its order, including the trust pills' wording | Presentation. The trust pills' honesty is the adversary's target and the rubric's | Nothing |
| `frontend/src/railCollapsePremise.test.tsx` | 523 | 20 | The history rail collapses from the app bar and from the rail | Presentation | Nothing. `src/components/answer/HistoryRail.phone.test.tsx`, `src/App.test.tsx` and `e2e/rail-collapse.spec.ts` mention it |

Test counts are from `npx vitest list` on these five files. `tracker/check_doc_drift.py` computes the frontend total, so the tracked count in `CLAUDE.md` moves from 546 to 459 in the same commit.

## Tracker report files to delete

The redesign's rule is ledger rows only: a reviewer's finding lives in `tracker/phase_N.M.md`, not in a per-round report. For each report, the finding ids it names were checked against its phase file.

- Every id is already in the ledger except `F-4.3-A-12`. It is named in `tracker/phase_4.3_rereview2_report.md` and `tracker/phase_4.3_review5_report.md`, and absent from `tracker/phase_4.3.md`.
- Three reports carry no id in the `F-N.M-...` form: the 4.6 adversary report, the 4.6 re-verify report and the 4.3 sixth review.
- An id in the ledger means the row exists. The reproduction detail may live only in the report, so the owner decides whether that detail matters before deletion.

"Linked from" is a search for the report's exact file name across tracked files. `CLAUDE.md` also names the 4.3 reports in a shortened list (`_adversary_report.md, _rereview_report.md` and so on), which that search does not catch.

| Report file | Lines | Finding ids | Ids not in the phase file | Linked from |
|---|---|---|---|---|
| `tracker/phase_2.1_adversary_report.md` | 577 | 13 | 0 | `tracker/phase_2.1.md` |
| `tracker/phase_4.10_adversary_report.md` | 47 | 18 | 0 | `tracker/phase_4.10_rereview_report.md` |
| `tracker/phase_4.10_judge_report.md` | 387 | 17 | 0 | `tracker/phase_4.10_rereview_report.md` |
| `tracker/phase_4.10_rereview_report.md` | 288 | 26 | 0 | nothing, by exact file name |
| `tracker/phase_4.10_verify_report.md` | 197 | 16 | 0 | nothing, by exact file name |
| `tracker/phase_4.11_adversary_report.md` | 300 | 8 | 0 | nothing, by exact file name |
| `tracker/phase_4.11_judge_report.md` | 412 | 22 | 0 | nothing, by exact file name |
| `tracker/phase_4.11_reverify_r3_report.md` | 206 | 12 | 0 | nothing, by exact file name |
| `tracker/phase_4.11_reverify_report.md` | 568 | 18 | 0 | nothing, by exact file name |
| `tracker/phase_4.13_final_verify_report.md` | 324 | 24 | 0 | `tracker/phase_4.13.md` |
| `tracker/phase_4.13_judge_report.md` | 267 | 14 | 0 | `tests/system_03_search_agent/adapters/web_sse/test_history_endpoint.py` |
| `tracker/phase_4.13_reverify_report.md` | 247 | 9 | 0 | `tracker/phase_4.13.md` |
| `tracker/phase_4.14_adversary_report.md` | 452 | 14 | 0 | nothing, by exact file name |
| `tracker/phase_4.14_judge_report.md` | 342 | 16 | 0 | nothing, by exact file name |
| `tracker/phase_4.14_reverify_report.md` | 729 | 31 | 0 | nothing, by exact file name |
| `tracker/phase_4.15_adversary_report.md` | 108 | 19 | 0 | nothing, by exact file name |
| `tracker/phase_4.15_gapcheck_report.md` | 223 | 6 | 0 | nothing, by exact file name |
| `tracker/phase_4.15_judge_report.md` | 301 | 17 | 0 | nothing, by exact file name |
| `tracker/phase_4.15_reverify_report.md` | 159 | 11 | 0 | nothing, by exact file name |
| `tracker/phase_4.2_adversary_report.md` | 60 | 19 | 0 | `src/system_03_search_agent/adapters/cli/credentials.py`, `tracker/phase_4.2.md` |
| `tracker/phase_4.2_judge_report.md` | 50 | 5 | 0 | `src/system_03_search_agent/adapters/cli/credentials.py`, `tracker/phase_4.2.md` |
| `tracker/phase_4.2_rereview_report.md` | 41 | 11 | 0 | `tracker/phase_4.2.md` |
| `tracker/phase_4.3_adversary_report.md` | 1000 | 28 | 0 | `tracker/phase_4.3.md` |
| `tracker/phase_4.3_judge_report.md` | 711 | 8 | 0 | `AGENTS.md`, `CLAUDE.md`, `requirements/phase_6/Phase_6_history.md`, `tracker/phase_4.3.md`, `tracker/phase_4.3_review5_report.md` |
| `tracker/phase_4.3_rereview2_report.md` | 367 | 1 | 1 | `tracker/phase_4.3_review5_report.md` |
| `tracker/phase_4.3_rereview_report.md` | 487 | 3 | 0 | `tracker/phase_4.3.md` |
| `tracker/phase_4.3_review5_report.md` | 375 | 1 | 1 | nothing, by exact file name |
| `tracker/phase_4.3_review6_report.md` | 147 | 0 | 0 | nothing, by exact file name |
| `tracker/phase_4.4_adversary_report.md` | 598 | 15 | 0 | `requirements/phase_6/Phase_6_history.md`, `tracker/phase_4.4.md` |
| `tracker/phase_4.4_judge_report.md` | 299 | 14 | 0 | `requirements/phase_6/Phase_6_history.md`, `tracker/phase_4.4.md` |
| `tracker/phase_4.5_adversary_report.md` | 520 | 29 | 0 | `requirements/Plan.md`, `tests/system_03_search_agent/core/test_plan_memory_binding.py`, `tracker/phase_4.5.md` |
| `tracker/phase_4.5_judge_report.md` | 606 | 29 | 0 | `requirements/Plan.md`, `tests/system_03_search_agent/core/test_plan_memory_binding.py`, `tracker/phase_4.5.md` |
| `tracker/phase_4.6_adversary_report.md` | 389 | 0 | 0 | `tests/system_03_search_agent/adapters/web_sse/test_feedback_endpoint.py`, `tests/system_03_search_agent/feedback/test_contracts.py`, `tracker/phase_4.6.md` |
| `tracker/phase_4.6_judge_report.md` | 417 | 11 | 0 | `tests/system_03_search_agent/adapters/web_sse/test_feedback_endpoint.py`, `tests/system_03_search_agent/core/test_feedback_capture_premise.py`, `tests/system_03_search_agent/feedback/test_review.py` |
| `tracker/phase_4.6_reverify_report.md` | 362 | 0 | 0 | nothing, by exact file name |
| `tracker/phase_4.7_adversary_report.md` | 687 | 21 | 0 | `tests/system_03_search_agent/core/test_injection_steering_premise.py`, `tracker/BOARD.md`, `tracker/board.html`, `tracker/fix_a01_injection_guardrail.md`, `tracker/fix_a02_discontinued_gene.md`, `tracker/phase_4.7_reverify_report.md` |
| `tracker/phase_4.7_judge_report.md` | 217 | 5 | 0 | `requirements/Plan.md` |
| `tracker/phase_4.7_reverify_report.md` | 467 | 12 | 0 | nothing, by exact file name |
| `tracker/phase_4.9_adversary_report.md` | 440 | 27 | 0 | nothing, by exact file name |
| `tracker/phase_4.9_judge_report.md` | 463 | 17 | 0 | nothing, by exact file name |
| `tracker/phase_4.9_rereview_report.md` | 579 | 35 | 0 | nothing, by exact file name |
| `tracker/phase_5.0_adversary_report.md` | 1120 | 41 | 0 | nothing, by exact file name |
| `tracker/phase_5.0_judge_report.md` | 691 | 11 | 0 | `tracker/phase_5.0_adversary_report.md` |
| `tracker/phase_5.1_adversary_report.md` | 510 | 29 | 0 | `tracker/BOARD.md`, `tracker/board.html`, `tracker/phase_5.1.md`, `tracker/phase_5.2.md` |
| `tracker/phase_5.1_judge_report.md` | 284 | 18 | 0 | `tracker/BOARD.md`, `tracker/board.html`, `tracker/phase_5.1.md`, `tracker/phase_5.2.md` |
| `tracker/phase_5.2_rereview_report.md` | 741 | 16 | 0 | `tracker/phase_5.2.md` |
| `tracker/phase_5.2_review4_report.md` | 412 | 17 | 0 | `tracker/phase_5.2.md` |
| `tracker/phase_5.3_adversary_report.md` | 701 | 28 | 0 | `tracker/phase_5.3.md` |
| `tracker/phase_5.3_judge_report.md` | 219 | 16 | 0 | `tracker/phase_5.3.md` |
| `tracker/phase_6.0_judge_report.md` | 371 | 12 | 0 | `requirements/Plan.md` |

## Premise-gate and mutation text removed from skills and docs

Already removed in this change, so the owner can see what went. Every earlier version is in git at the commit this change branches from.

`.claude/skills/bossman-mode/SKILL.md`:

- The description's step list, "decompose, dispatch a team, premise gate, judge round, adversary round, gates, PR".
- The reading-table rows "the premise gate and why it blocks" and "gate mutation".
- The paragraph "Stage 5, the premise gate, is mandatory and blocking for any phase whose deliverable is model-generated. Write the gate, watch it fail, and only then build."

`.claude/skills/bossman-mode/reference/Review_rounds.md`:

- "Mutation-test every gate before it counts as evidence", with the eleven recorded vacuous-assertion instances and build phase 4.3's fourteen. Now one judge checklist line, "break it, does a test go red".
- "The populate-check, from build phase 4.11, on every bound arm". Folded into that line's second question.
- "Beware safety-by-proxy". Folded into that line's first question.
- The judge's duty to close the board, and the Playwright-plus-owner rule for interface phases. Now the owner's verdict closes, and the product reviewer drives the screens.
- The fifth-pass sentence naming "the phase's own premise gate", now "the phase's own checks".

`.claude/skills/bossman-mode/reference/Phase_execution.md`:

- Step 1's "Never invent a phase or reorder the sequence". The reorder half is gone under decision 1; "never invent a phase" stays.
- "Stages 3 and 5, decomposition and premise gate design" in the provider note. Now "the split".
- The researcher and test writer roles, and the research step.

`docs/build/Build_workflow_cadence.md`:

- The section "Stage 5, the premise gate, and why it blocks". Replaced by "The answer-path premise check", which keeps the BRCA1 case and the four properties for answer behaviour only. Dropped from it: the cost figures (about 40 minutes to write, $0.013 a run, against ten review passes of 20 to 30 minutes), the note that it caught two of 2.1's late regressions, the paragraph on stating its own coverage (F-2.1-A5-03, still required by `goal-contracts` for the gates that remain), and the paragraph on why it blocks rather than being merely required.
- The stage-table row "Write the premise gate and WATCH IT FAIL. Blocks stage 6", and the diagram edge "must fail first".
- The model-assignment row "Lead, premise gate design (stage 5)", and the effort-basis paragraph treating that step like decomposition.
- "premise gate design" in the provider-mapping list of stages that do not fail over.
- The weak point "The premise gate at stage 5 is only as good as its question set".

Other text the cadence rewrite dropped, listed so nothing goes silently:

- "Before 2026-08-02, of these ten model-driven stages", five at high effort and seven on the depth tier.
- The per-skill dispatch counts measured for stage 10: `verify` 1 of 5 phases, `dev-standards` 1 of 5, `eval-harness` first dispatched on build phase 2.2. `release-workflow`'s 0 of 6 is kept.
- The note that the Sub-planner and Integrator rows were removed for zero dispatches.
- The stale weak point on Playwright 1.62.0 in build phase 1.2 and build phase 4.5's UI gate.
- The lead's routine stages on the balance tier. The redesign puts the lead, the session itself, on the depth tier.

`docs/build/Phase_6_execution_flow.html` never carried a premise-gate stage. Its stage 8b, the round budget, became stage 6. Its researcher and test writer cards were removed.

No text about premise gates or mutation was removed from `.claude/rules/`. The bossman-mode rule gained a deny for writing either outside answer behaviour.

## What else must change in the same commit as the deletions

In the deletion commit, so nothing is left broken or false:

- `.github/workflows/ci.yml` line 48: "The premise gate's P8 arm fails if one appears" is false once `tests/ci/test_ci_workflow_premise.py` goes. A branch and pull request are needed anyway, since the file is under `.github/`.
- `tests/conftest.py`'s `RUN_PREMISE_GATE` opt-in and the matching sanctioned skip in `.github/scripts/assert_no_db_skips.py` stay: the kept gates use both.
- The tracked counts in `CLAUDE.md` and `AGENTS.md`: `python3 tracker/check_doc_drift.py --check` computes the new Python and frontend totals.
- `docs/build/Debugging_guide.md` names none of the deleted files by name, so its coverage test is unaffected. Its symptom row "Live premise arms do not run", for any `*_premise.py`, stays true for the kept gates.
- Links to deleted report files from `requirements/Plan.md` (the 4.5 judge and adversary, 4.7 judge and 6.0 judge reports), from phase files, from `src/system_03_search_agent/adapters/cli/credentials.py` (the 4.2 reports), and from test docstrings (the 4.5, 4.6 and 4.13 reports). Point each at the phase file's Findings section.

Harness text outside this change that still describes a removed step, for the lead:

- `.claude/agents/phase-reviewer.md`: its example report path is a per-round file under `tracker/`, and it is "dispatched by name at cadence stages 8 and 9". Now the phase file's Findings section, at stage 6. `CLAUDE.md`'s sub-agent table repeats the stage numbers.
- `.claude/skills/task-tracker/SKILL.md`: `done` is "Judge only" (lines 85 to 87 and 176), and `tracker/BOARD.md`'s status table repeats it; the owner's verdict sets `done` now. Line 171 makes the premise gate the first ticket of a model-generated phase, true now only for answer behaviour.
- `docs/build/README.md` line 23 and `docs/build/design/Design_to_build_workflow.md` line 63 still call stage 5, the premise gate, mandatory for every phase.
- `docs/build/Golden_dataset_method.md` steps 4 and 5 run the 5.1 premise gate, which is on the owner-ruled list.
- `docs/build/Release_flow.md` lines 39 and 84 rely on the 4.15 premise gate's P5 and P11 arms; P11 "fails if it is ever turned back off", a repository setting nothing else watches once `tools/test_release_environments_premise.py` goes.
- The 4.8 frontend premise gate, `frontend/src/phase48Premise.test.tsx`, is described as asserting against the design system in `docs/build/README.md` lines 57 and 90, `docs/build/design/README.md` lines 5 and 100, `docs/build/design/Design_to_build_workflow.md` (lines 43, 118, 125, 156 and 229), `docs/build/design/make_cards.py` line 5 and `docs/build/design/Phase_4.8_visual_design.html` line 279. After deletion the product reviewer's side-by-side is what checks the design.
- `.claude/rules/goal-contracts.md`, "A verify surface must state its own coverage": still right for the gates that remain, all answer behaviour. Decision 5's "coverage claims" are completeness sentences ("every arm is covered"), not a gate's statement of what it omits, so the rule was left as it is.

## Done 2026-09-24

Executed under the "Safe first" form the product owner approved the same day.

Deleted, no property to move first:

- All 50 tracker per-round report files listed above.
- The 6 Python test files marked "No" in the Security or cost column: both `eval/test_phase_5_2_*` files (premise, mutation, regression mutation), both `eval/test_phase_5_3_*` files (premise, mutation), and `export/test_kgx_export_premise.py`.
- All 5 frontend test files listed above (the frontend table carries no security-or-cost column, so none qualified to be kept back).

Moved into an ordinary unit test, proven red then green by a temporary one-line break in `src/` (restored exactly; `git diff --stat src/` is clean), then deleted:

| Property | New test file | Premise/mutation file(s) deleted |
|---|---|---|
| A gate step's `run:` cannot be neutralised (CI) | `tests/ci/test_gate_invocation_canonical.py` | `test_ci_workflow_premise.py`, `test_ci_workflow_mutation.py` |
| Credential file refused wider than mode 600 | already covered by existing `tests/system_03_search_agent/adapters/cli/test_credentials.py`; no new file needed | `adapters/cli/test_phase_4_2_premise.py` |
| No cost figure or field; `operator_mode` pinned false (GraphQL) | `tests/system_03_search_agent/adapters/graphql/test_no_cost_channel.py` | `adapters/graphql/test_phase_4_3_premise.py` |
| No cost field; missing/invalid/guest token refused before a run is created (MCP) | `tests/system_03_search_agent/adapters/mcp/test_no_cost_and_auth.py` | `adapters/mcp/test_phase_4_1_premise.py` |
| `operator_mode` not settable from a request body | `tests/system_03_search_agent/adapters/web_sse/test_operator_mode_not_client_settable.py` | `adapters/web_sse/test_phase_4_0_premise.py` |
| A caller never reads/stops/spends another caller's run | already covered by existing `tests/system_03_search_agent/core/test_run_registry.py` (`test_a_different_owner_is_refused`, `test_a_guest_and_a_user_are_never_confused`); no new file needed | `adapters/web_sse/test_phase_4_10_premise.py` |
| One person never sees another's history rows | already covered by existing `tests/system_03_search_agent/feedback/test_history.py` (`test_owner_scoping_returns_only_the_callers_own_rows`); no new file needed | `adapters/web_sse/test_phase_4_13_premise.py` |
| A second insert under the same trace id changes nothing (exactly one interactions row) | already covered by existing `tests/system_03_search_agent/feedback/test_writer.py` (`test_a_second_insert_under_the_same_trace_id_changes_nothing`); no new file needed | `core/test_feedback_capture_premise.py` |
| At most 20 Layer 2/3 calls per query | `tests/system_03_search_agent/harness/test_call_budget_ceiling.py` | `core/test_rate_limit_concurrency_premise.py`, `core/test_rate_limit_concurrency_mutation.py` |
| The two real bypass callers (`think_node` symbol resolution, KGX export traversal) are audited | `tests/system_03_search_agent/observability/test_audit_bypass_callers.py` | `observability/test_observability_premise.py`, `observability/test_observability_mutation.py` |
| The `X-Forwarded-For` rightmost-element rule and the Caddyfile directive | `tests/services/graph_query_service/test_forwarded_address.py` | `tools/test_demo_deploy_premise.py`, `tools/test_demo_deploy_mutation.py` |

Kept back, blocked-stop: `tools/test_release_environments_premise.py` and `tools/test_release_environments_mutation.py`. The flagged property, that the two Railway deployments hold different `AUTH_SECRET` signing keys, is read through the Railway CLI against the live production and develop services (`_signing_key_for`, gated on `RUN_PREMISE_GATE=1`) and cannot be pinned by an ordinary unit test without that live service. Left in place rather than deleted.

Not done, left for the owner or the lead, named rather than silently skipped:

- `.github/workflows/ci.yml` line 48's comment ("The premise gate's P8 arm fails if one appears") is now false; this session could not edit it (outside the write scope given for this task, and a `.github/` change needs a branch and PR under `git-workflow.md` regardless).
- The narrative cross-references to the 50 deleted report files, in `requirements/Plan.md` (not writable here), `src/system_03_search_agent/adapters/cli/credentials.py` (not writable here), and several `tracker/phase_N.M.md` files, `tracker/BOARD.md`, `tracker/board.html`, `tracker/fix_a01_injection_guardrail.md`, `tracker/fix_a02_discontinued_gene.md`, `requirements/phase_6/Phase_6_history.md`, and a handful of test docstrings. An early attempt at a mechanical find-and-replace produced malformed, repetitive prose and was reverted rather than shipped; each of these is hand-written narrative and deserves a hand edit pointing at the owning phase file's Findings section, not a scripted substitution.
- The tracked counts in `CLAUDE.md` and `AGENTS.md`: per this task's brief, the lead updates these afterwards via `python3 tracker/check_doc_drift.py --check`.
