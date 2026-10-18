# Reference document sync, 2026-10-17

Two checks, run on the `chore/doc-sync-2026-10-17` worktree:

- The reference documents in the fence, checked against the code and configuration: `docs/architecture/`, `docs/Context_budget.md`, `docs/Agent_mods.md` and `docs/build/*.md`.
- Every relative link in the repository's tracked Markdown, checked by script. `docs/build/Handoff_history.md` and `docs/build/Factory_onboarding.md` were outside the fence and not edited. Nothing under `requirements/` was edited.

## Table of contents

- [How each claim was checked](#how-each-claim-was-checked)
- [Part 1: reference documents](#part-1-reference-documents)
- [Documents checked with nothing false found](#documents-checked-with-nothing-false-found)
- [Part 2: broken relative links](#part-2-broken-relative-links)
- [For the owner](#for-the-owner)

## How each claim was checked

| Claim family | Checked against |
|---|---|
| Model tiers, defaults, prices, effort | `src/system_03_search_agent/harness/tiers.py`, `harness.py`, `cost_control.py`, `decide.py`, `jev_client.py`, `env.example`, `tests/system_03_search_agent/harness/test_tiers.py` and `test_opus_writer.py` |
| Model call sites and Jev decisions | every `_dispatch_tier_call`, `call_tier` and `point=` in `src/system_03_search_agent/` |
| Context budget and mods | `.claude/skills/mod-*/hooks/config.ts`, each rule's `paths:` frontmatter in `.claude/rules/` |
| Release flow | `.github/workflows/release.yml`, `ci.yml`, `.github/release/*.sh`, `railway.json`, the repository's rulesets read through the GitHub API |
| Debugging guide | `tests/system_03_search_agent/test_debugging_guide_coverage.py` (7 passed before and after), every backticked path resolved by script, every environment read in `src/` and `services/` compared with `env.example` |
| Build cadence | `.claude/skills/bossman-mode/SKILL.md` and its four reference files |

Develop's and production's Railway variables were not re-read; statements dated to an earlier Railway read stay as dated.

## Part 1: reference documents

| File:line | What was false | Change, or why left |
|---|---|---|
| `docs/architecture/Model_architecture.md:27` | "Every model call ... goes through `Harness.call_tier` ... LiteLLM to OpenRouter": Jev's calls go through `harness/jev_client.py` straight to OpenRouter's decisions endpoint | One sentence added naming Jev as the exception |
| `docs/architecture/Model_architecture.md:53, 60-62, 66, 70, 78, 141, 174` | Stale line numbers: `tiers.py:172, 69-71, 221`, `harness.py:374, 587, 820, 503`, `graph.py:785`, `coordinator_worker.py:471`, `cost_control.py:473` | Corrected to `tiers.py:192, 72-74, 241`, `harness.py:403, 667, 952, 534`, `graph.py:820`, `coordinator_worker.py:493`, `cost_control.py:536` |
| `docs/architecture/Model_architecture.md:75` | Names a `ClarifyDecision` shape, which does not exist, and `graph.py:2125`, which is now the guardrail's classifier call | `ClarifyChoices`, located by function: `_write_clarify_choices` |
| `docs/architecture/Model_architecture.md:80` | `graph.py:9790` no longer the writer call | Located by function: `_write_answer`, the first-draft call |
| `docs/architecture/Model_architecture.md:144-146` | The estimate was described as `_PRICED_TOKEN_PROFILE` at 23,000 prompt and 2,000 output tokens, $0.132 a call. Since the fix round F-8.7-J04 and F-8.7-A06, output is priced at the tier's whole 4,000-token ceiling, and a call through `_dispatch_tier_call` is bounded on its actual prompt (`Harness.call_cost_bound_usd`) | Rewritten to the current rule: $0.172 with no prompt in hand; the $0.132 figure and the 54-question replay kept as history of the first 2,000-token figure |
| `docs/architecture/Model_architecture.md:152` | "$0.132 estimate" | "$0.172 with no prompt in hand" |
| `docs/architecture/Model_architecture.md:171` | "The run and the merge wait for the owner's answer on the daily cap": answered on 2026-09-27, develop's cap rose to $25 (DECISIONS.md) | States the answer |
| `docs/architecture/Model_architecture.md:211-212` | The list of Jev decisions on develop omitted two that exist: `plan.paper_links` (card 74) and `write.lead_sentence` (build phase 8.7, card 2) | Two bullets added, each with its file |
| `docs/architecture/Model_architecture.md:248` | The fallback price table was said to apply only when litellm has no price; it also applies when litellm maps a named model at zero or an unusable value | Clause added |
| `docs/architecture/Model_architecture.md:251` | "Both may name only models that are `_DEFAULT_MODELS` values": the scan also allows `_FALLBACK_PRICES_USD_PER_TOKEN` keys, and z-ai/glm-5.2 is one without being a default | Corrected |
| `docs/architecture/Model_architecture.md:253` | "litellm's map prices glm-5.2 ($0.6496 and $2.0416 per million in 1.93.0)": since the CI repair of 2026-10-15 the fallback table prices it at $0.037 and $7 per million, because the map litellm fetches at start has no entry | Corrected, test named |
| `docs/architecture/Model_architecture.md:268-270` | "What this document did not check" still says the Jev seam is planned, not built | Left: a dated statement of what was not checked on 2026-09-25, history |
| `docs/architecture/Three_layer_data_architecture.md:5` | The document says "this repository" for Systems 1 and 2; it came from the data engineering repository, and those systems are not built here | One note added under the intro; headings left, since renaming them changes anchors (owner item 3) |
| `docs/architecture/Three_layer_data_architecture.md:61-65` | "Excluded entirely (not in any layer)" lists PubChem and SRA, which System 3 reaches live today (`tools/ncbi_pubchem_actions.py`, `core/paper_links.py`) | Note added under the table; the table kept as the data engineering plan |
| `docs/Context_budget.md:68, 70` | The path lists for ai-security-standards and the production rules were short: they also cover shell files, migrations, `.claude/` agents, skills, hooks and settings, `services/` and `alembic/` | Lists completed |
| `docs/Context_budget.md:76-77` | Six path-scoped rules were missing from the list: bossman-mode, decision-logging, goal-contracts, plan-then-fan-out, self-eval-loop, preserve-your-thinking | Two bullets added |
| `docs/Agent_mods.md:95` | "it currently reports `omim.org`": `omim.org` and `www.omim.org` are on the mod's `acknowledged` list, so it does not | Corrected |
| `docs/build/Release_flow.md:66` | "retrying up to five times": `release_attempts=5` is five tries in all | "trying up to five times" |
| `docs/build/Release_flow.md:95` | "a documentation-only change runs no workflow (`paths-ignore`)": `paths-ignore` filters only the push trigger, and every pull request runs the gates | The reason kept as the one given then, with what holds today |
| `docs/build/Release_flow.md:96` | "Until that rule is set, an account with write access can push straight to `production`": the ruleset "Only the owner changes develop and production" covers `production` since 2026-09-27, with the admin role able to bypass | Corrected to name the ruleset and the admin bypass |
| `docs/build/Build_workflow_cadence.md:55, 59` | "Nothing in these three places names a product directly", listing `Phase_6_execution_flow.html`: that page carries its own copy of the provider table as it stood on 2026-09-24 | Says the record page is the one that names a product |
| `docs/build/Agent_teams_tmux_quickstart.md:16` | "Activate: `/bossman`": the invocation is the exact name, `/bossman-mode` | Corrected |
| `docs/build/Agent_teams_tmux_quickstart.md:37` | "runs a tmux preflight at Step 1": it is step 3 of opening a phase in `reference/Phase_execution.md` | Corrected |
| `docs/build/Verify_loop_proposal.md:3` | "A proposal, not yet approved": approved as proposed on 2026-09-26; `precommit` and `/verify` are built, `/design` is not | Status sentence corrected |
| `docs/build/Factory_review_loop.md:3` | "It is built under `.claude/skills/factory-loop/`": that folder is not in the repository; the build is a saved patch while the loop is paused | Says it was built for that folder, which is absent while paused |
| `docs/build/UI_feedback.md:56` | `feedback/inbox/` and `feedback/README.md` do not exist; the inbox moved to `testing/Product/feedback/` | Paths corrected |
| `docs/build/Golden_dataset_method.md:241` | "run the 26 premise arms": the command runs the whole eval folder, and the 5.1 premise and mutation files now collect 20 tests | Count dropped, wording says what the command runs |
| `docs/build/Debugging_guide.md:739, 744-745, 772-774` | The variable table lacked six names: `GRAPH_BOX_HOST`, `MCP_ALLOWED_HOSTS`, `MCP_ALLOWED_ORIGINS` (declared) and `CLASSIFIER_PROVIDER`, `JEV_MODEL`, `LOOP_STALL_WATCH` (read, undeclared) | Six rows added |
| `docs/build/Debugging_guide.md:755` | `OPENROUTER_API_KEY` "read indirectly by LiteLLM" only: `decide.py`, `sentence_check.py` and `core/graph.py` read it directly for Jev | Row corrected |
| `docs/build/Debugging_guide.md:796, 802, 811-813, 819` | "Seventeen names are read ... and absent" and "ten names ... seven bullets": twenty are, with three missing from the list | Counts removed from the prose, three bullets added, `GRAPH_BOX_HOST` added to the read-by-nothing list |
| `docs/build/Debugging_guide.md:832-837` | "`env.example` declares 40 variables", "Seventeen", "Twelve of the forty", and `OPENROUTER_API_KEY` among the unread | Dated to 2026-10-17: 43 declared, 20 read and absent, 12 of 43 unread by Python, `GRAPH_BOX_HOST` in for `OPENROUTER_API_KEY` |

"Last updated" moved to 2026-10-17 in `Build_workflow_cadence.md`, `Factory_review_loop.md`, `UI_feedback.md` and `Golden_dataset_method.md`, the changed files that carry one. No new vendor name was added: the model ids and provider names in `Model_architecture.md` were already there, and the edits reuse them. The house style checker finds no new hard finding in any edited file; the findings it reports were there before.

## Documents checked with nothing false found

| Document | Note |
|---|---|
| `docs/build/Search_and_conversation_behaviour.md` | Every function and file it names exists |
| `docs/build/Feedback_review_ritual.md` | Every command and flag matches the argument parsers of `feedback/review.py` and `feedback/promotion.py` |
| `docs/build/Build_workflow_cadence.md`, the rest | The tier roles, the 8 dispatches, the Depth stages that never fail over and the four reference files match the skill |
| `docs/build/README.md` | Nothing false; its tables list four of the folder's Markdown documents and leave out the rest, an index gap rather than a false statement (owner item 4) |
| `docs/build/Bossman_mode_redesign.md`, `Bossman_redesign_deletion_inventory.md`, `Build_velocity_post_mortem.md` | Dated diagnoses and inventories; every path they name that is gone is named as deleted or as history |
| `docs/architecture/System_3_architecture_brainstorming.md`, `Biolink_repos_explained.md`, `Multi_agent_system_design_explained.md` | A dated brainstorm, a dated external reference and an external reading; their paths name the reference repositories, not this one |
| `docs/build/Debugging_guide.md`, the inventory | The coverage test passes; every path the guide names exists |

## Part 2: broken relative links

Scope: 225 tracked `.md` files, every tracked Markdown file outside `testing/Developer/reports/` and `reference/` (`testing/User-feedback/` does not exist). 1,310 relative links and anchors checked, anchors computed GitHub style from each target's headings and its `<a id>` and `<a name>` tags. Eight are broken, in three files. All are report only.

| File:line | Target | Problem | Likely right target |
|---|---|---|---|
| `docs/data-engineering/Project_overview_A_to_Z.md:91` | `../README.md#monthly-cost` | Resolves to `docs/README.md`, which has no such heading | `../../README.md#cost-model`, the root README's cost table, or the data engineering repository's README on GitHub, where the text came from |
| `requirements/Plan.md:870` | `#build-phase-history` | No such heading in `Plan.md` | `#claudemds-build-phase-history-as-it-stood-on-2026-09-24` |
| `requirements/Plan.md:871` | `#build-phase-history` (twice on the line) | Same | Same |
| `requirements/Plan.md:875` | `#current-focus` | Same | `#claudemds-current-focus-rows-2-and-4-as-they-stood-on-2026-09-24` |
| `testing/UI_fixes_done.md:486` | `#detail-1129` | The anchor lives in the board, not this file | `UI_fix_plan.md#detail-1129` |
| `testing/UI_fixes_done.md:487` | `#detail-1132` | Same | `UI_fix_plan.md#detail-1132` |
| `testing/UI_fixes_done.md:488` | `#detail-1138` | Same | `UI_fix_plan.md#detail-1138` |

`requirements/Plan.md` is a locked contract, so its three lines are the owner's to change. The script is kept outside the repository; the method is in the scope paragraph above.

## For the owner

Each item is listed, not decided.

1. An Opus writer's repair pass under a $0.25 cap is unmeasured since the fix round priced output at the 4,000-token ceiling. The bench replay that admitted all 24 repairs used the earlier 2,000-token figure. It matters only when a deployment's writer becomes Opus (card 5).
2. Release flow: every pull request runs the gates, so the old reason for not requiring checks no longer holds. Whether the rulesets should now require the CI gates is your call.
3. `docs/architecture/Three_layer_data_architecture.md` is a copy from the data engineering repository whose headings still say "this repository". A note now says so. Rewriting it for this repository, or replacing it with a pointer, is your call.
4. `docs/build/README.md` indexes four of the folder's Markdown documents. Whether it should list the rest is a structure change, left for you or the doc-sync owner.
5. Outside this fence: `.claude/README.md`, "Reference docs", says `Search_and_conversation_behaviour.md` covers four situations; the document covers five. The same table says `Build_workflow_cadence.md` is the one place the loop names a provider, and the 2026-09-24 page carries a copy.
6. Develop's `SYNTH_MODEL`, `GUARD_MODEL` and `PLAN_MODEL` were not re-read from Railway; `Model_architecture.md` keeps them as read on 2026-09-25 and 2026-10-15.
