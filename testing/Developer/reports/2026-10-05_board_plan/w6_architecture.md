# Workstream 6, architecture and process direction (scout name: architecture)

Read-only scout report, 2026-10-05, for cards 5, 6, 7, 9, 39, 40, 42, 52 and 55. No live questions were asked; every status below comes from code on `develop`, git history and the documents the cards point to. Paths are relative to `<repo-root>`.

## Table of contents

- [The one-line verdict per card](#the-one-line-verdict-per-card)
- [Card table](#card-table)
- [Built versus only written about, with evidence](#built-versus-only-written-about-with-evidence)
- [Root causes shared by several cards](#root-causes-shared-by-several-cards)
- [Suggested order inside the workstream](#suggested-order-inside-the-workstream)
- [What was not checked](#what-was-not-checked)

## The one-line verdict per card

| Card | Verdict |
|---|---|
| 5 | Half built. Jev classifier and open-weight guard and plan tiers are live. The Opus writer and per-model effort are written and parked on unmerged branches. |
| 6 | The loop exists as Guardrail, Think, Plan, Act, Write. The "check intermediate results and adjust" steps are not built (harness review item C7). |
| 7 | Discussion only. Nothing built. The scoping document's own options one to four are unbuilt. |
| 9 | A grader exists in code but refuses to run without a judge. Nothing judges answer quality automatically. Parked behind a closed track. |
| 39 | Built. The deep dive is merged at `visualizations/System_3_deep_dive.md`. The board row is stale. |
| 40 | Mostly built. Build-harness fixes merged (PR #110 and hook PRs). Of the product-harness list, C4, C5 and C6 are in code; C1 was reverted in part, C2, C3, C7 and C8 are not built. |
| 42 | Approved but half built. `/verify` exists and ran. `/design` does not exist. Bossman mode does not call either. |
| 52 | Designed only. Zero code. |
| 55 | Decided and written only. No runner exists. |

## Card table

Columns: 1 the feature, 2 impact on the person, 3 status today, 4 root cause, 5 shared cause, 6 code touched, 7 size, 8 depends on and blocks, 9 needs the owner.

### Card 5: models chosen per task by tier

1. The right model does each job: cheap open-weight models for small decisions, a frontier model where quality needs it, the owner's chosen writer on the answer.
2. Wrong or degraded answer, and slow (the writer is 73 percent of the wait per `2026-09-25_harness_review/product_harness.md`).
3. Still happens in part. Code default synth is still `z-ai/glm-5.2` (`src/system_03_search_agent/harness/tiers.py:_DEFAULT_MODELS`). `_TIER_REASONING["synth"]` is still `{"effort": "none"}` (`harness/harness.py`). Phase 8.7's three builders are parked and unmerged: `origin/feat/8.7-s1`, `s2`, `s3`; `git merge-base --is-ancestor origin/feat/8.7-s1 develop` says not merged. `tracker/phase_8.7.md` exists only on those branches, not on develop (the brief's path does not resolve on develop). Built and live: Jev decisions (build phases 8.2 and 8.6, `harness/jev_client.py`, `harness/decide.py`), guard and plan tiers on open-weight models, the retry that drops the `reasoning` block when a provider refuses it (`harness/harness.py`, C4). `harness/task_tiers.py` is a table nothing calls (its own docstring says so).
4. Known: a per-model reasoning setting does not exist; `_TIER_REASONING` is keyed by tier, so Opus (which refuses `effort: none`) cannot be set without it. Point b of the owner's direction (APIs as MCP-style functions) is card 11.32, not started.
5. Cards 2 and 50 (same phase 8.7 branches); card 40 item C8 (writer prefix trim) edits the same call.
6. `harness/tiers.py`, `harness/harness.py:call_tier` and `_TIER_REASONING`, `harness/cost_control.py` (cap 10 to 25 cents, per `DECISIONS.md` 2026-09-27; code value not checked), `core/graph.py` write helpers.
7. M, already designed.
8. Depends on nothing unmerged except the owner's wish to resume 8.7. Blocks card 50's timing target and card 52.
9. No new decision. The writer choice and the 25-cent cap are decided (2026-09-27). Only: "Resume parked phase 8.7 now?" Recommendation: yes after cards 88 and 89 land, since it changes the writer for every answer.

### Card 6: the agentic loop

1. The product works like an agent: plans, uses tools, checks what came back, adjusts when it fails, then writes.
2. Wrong or degraded answer: a list that looks like an answer when the records cannot answer it.
3. Partly built. Plan, act and write run (`core/graph.py`). Failure handling exists per step (timeouts, one retry, repair pass). No step reads the tool results and re-plans: `grep` for replan or adjust in `core/graph.py` finds nothing of that kind. The harness review ranks it as C7 and sizes it "Large, a build phase", not opened.
4. Known: no decision point after `act_node` and no re-entry to `plan_node`; reasons the review measured: missing field (organism, title, gene), empty graph, failed search.
5. Cards 2 and 52 (the honest first sentence "the records do not say") and 7 (soft edges need a second hop). Phase 8.9's asked-for-field work is the cheaper half of the same gap.
6. A new decision through `harness/decide.py`, `core/graph.py` (`act_node`, `plan_node`), `core/state.py` additive fields.
7. L, and discussion first.
8. Depends on phase 8.9 (the writer is handed the asked-for field) and card 5. Blocks nothing yet.
9. Yes: "Open C7, one bounded re-plan, before or after the writer move?" Recommendation: after 8.7 and 8.9, because C7 should be measured against answers that already carry the right fields.

### Card 7: hard and soft edges over a fuller graph

1. Answers that connect the dots across papers, genes, variants and trials, not only direct links.
2. Wrong or degraded answer (the owner called answers "surface level").
3. Still open, unchanged. `tools/cypher_templates.py:_HOPS` holds only single-hop shapes. `cited_in` and `subclass_of` appear only in `tools/graph_schema_constants.py`, in no template. The documented AGE limit (edge alternation is a SyntaxError) is still described in `cypher_templates.py`. The scoping document `2026-09-23_overnight/soft_edges_scoping.md` finds 20 of 37 questions answered by hard edges alone, 5 needing two hops all on one path, and the real limit being the grounding gate, not retrieval.
4. Known and measured: the graph holds identifiers, not facts (Gene has seven properties); the grounding gate quotes but cannot explain; Disease `name` holds vocabulary labels (a System 1 and 2 matter).
5. Card 57 and the grounding-gate decision (option two of the scoping); card 6 (second hop is a re-plan); card 61-style `participates_in`-only breadth wiring.
6. `tools/cypher_templates.py`, `tools/cypher_query.py`, `synthesis/grounding.py`.
7. Discussion first.
8. Depends on the owner settling the grounding-gate question, and on System 1 and 2 for disease names. Blocks nothing.
9. Yes: "May the grounding gate be relaxed for a cited path (a structured claim checked field by field), or does the product stay a quoter?" Recommendation: no change now; build only the three clean single-edge templates, presented as cited paths. Vectors and RAG: skip, they sit on the v1 out-of-scope list and the scoping counted zero questions needing them.

### Card 9: judge answer quality once answering is reliable

1. Someone or something reads the answers and says whether they are good, not only whether they cite.
2. Not seen by a user directly; it steers what gets fixed.
3. Not built. `src/system_03_search_agent/eval/rubric_grader.py` raises `NoJudgeConfiguredError` when no judge is supplied (the default judge was removed in phase 5.2 because it scored a refusal as a pass). The only live quality read today is the product reviewer's manual "answered well" rubric (1 of 10 at the 8.6 review). `testing/Test_queries_and_workflows.md` line 1932 says "not built". The evaluation track closed 2026-08-31; follow-up lives in `requirements/Plan.md` Phase 7. Precondition ("once answering is reliable") is also not met: the golden floor sits at 101 or 102 of 150.
4. Known: no judge model wired and no calibrated rubric.
5. Card 55 (the test-queries gate needs the same model grader for "what you should see"), card 40 (builder reports are unchecked, "answered is not good").
6. `eval/rubric_grader.py`, `eval/aggregate.py`, a judge wrapper through `harness/harness.py`.
7. M after card 55 chooses a grader.
8. Depends on card 55's grader design. Blocks nothing.
9. No. Recommendation: fold into card 55 and close this card as superseded once 55's model grader exists, keeping an expert check on a few answers as card 55 says.

### Card 39: architecture visualization deep dive

1. A picture and plain account of the models, harness and system.
2. Not seen by a user.
3. Already fixed. `visualizations/System_3_deep_dive.md` is merged (commits `4994a80e`, `8435150b`, `2310b925`, `7b26c987`), corrected against develop on 2026-09-27 (card 53). The board row still says "Queued". Companion: `docs/architecture/Model_architecture.md`.
4. Not applicable.
5. Card 51 (documents going stale): both drift as 8.7 or 8.9 land.
6. Documents only.
7. S to refresh after any model change.
8. None. A refresh follows card 5 when the writer changes.
9. No. Recommendation: move the card to done, and add "refresh after card 5" to the card 5 ticket list.

### Card 40: make the harness work well (both reviews)

1. The build team and the product's question-to-answer path stop wasting time and money.
2. Slow, and wrong or degraded answer (product side); not seen by a user (build side).
3. Mostly done, partly open. Build side (PR #110 "chore/build-harness", plus hook-gap PRs #117 and #121, #122): bookkeeping removal, one cadence with the risk dial, three hook fixes, lighter rulebook, all merged (`git log`). Product side, from `product_harness.md`: C4 built (reasoning-refusal retry, `harness/harness.py`), C5 built (`LLMResponse.elapsed_s`), C6 built (`_price_per_token` called before dispatch, `harness/harness.py:call_tier`). C1 (skip the second writer call): `_code_built_lines_will_cite` exists but phase 8.6's fix round reverted its widening (F-8.6-J01, A04); the second call still fires on most answers, per the card 50 timing. C2 is phase 8.9 (planned, not opened; `tracker/phase_8.9.md` says "planned, not opened"). C3 trust-line wording waits on card 8's words. C7 and C8 not built. The row's "Being built" text is stale.
4. Known: second writer call fires because the cited-by-record comparison is tricky; writer prefix is 32,914 characters of which 27,669 are tool schemas.
5. Cards 5, 2 and 50 (C1 and C8 are speed levers inside the same write step); card 6 (C7); card 8 (C3).
6. `core/graph.py:_code_built_lines_will_cite` and the write path, `harness/cache.py`, `synthesis/trust.py:answer_trust_line`.
7. M for the remainder, excluding C7.
8. C1 and C8 should be built after card 5's writer move (the repair is needed on 8 of 18 Opus questions against 18 of 18 for glm, so the right fix depends on the writer). C2 blocks card 52.
9. Yes: "The wording of the trust line (C3, card 8)". Recommendation: "From one database, MedGen" style, as the review proposes.

### Card 42: the build team verifies the way a person uses the product

1. The owner's retest confirms; the team has already driven the app and fixed what failed.
2. Not seen by a user directly; prevents wrong screens reaching them.
3. Approved 2026-09-26 (`DECISIONS.md` row 744), half built. Built: `.claude/skills/verify/` with `scripts/capture.mjs`, `scripts/check_facts.py`, `scripts/facts_registry.py`, `specs/home_and_answer.json`; the pre-commit skill was renamed so `/verify` is free; ran once (`2026-09-26_verify_home_and_answer/report.md`). Not built: `/design` (no `.claude/skills/design`), and bossman mode does not call `/verify` (grep of `.claude/skills/bossman-mode/SKILL.md` shows only the product-reviewer row). Only one spec exists, so only the home and answer screens are covered. The "seven-day close" (`DECISIONS.md` row 745) is decided but not wired.
4. Known: the two remaining proposal steps never got their own branch.
5. Card 55 (the runner it needs, and screens go through `/verify`), card 51 (page-facts check, already merged as PR #122).
6. `.claude/skills/design/` (new), `.claude/skills/bossman-mode/SKILL.md`, `.claude/skills/verify/specs/`. Everything under `.claude/` needs a branch and the owner's itemized yes.
7. M.
8. Depends on nothing. Card 55 reuses it.
9. Yes: "Approve `.claude/` changes for `/design` and the bossman call, as the item-by-item list in the memory rule requires." Recommendation: yes, in two pull requests.

### Card 52: every answer ends by offering the next useful step

1. After an answer, two or three clickable follow-up questions drawn from what the answer found.
2. Screen or wording only for the offer; the user-visible gain is a continuing conversation.
3. Not built. `contracts/events.py` carries only `next_step` (a go-deeper yes or no) and `next_step_query`. There is no `next_steps` list field. The design (`2026-09-26_conversation_next_steps/design.md`) measured the existing offer firing on 0 of 6 live answers, because `core/graph.py:_build_next_step_offer` declines when findings mix record types. The ask-back before a search (`core/clarify.py`, item 12.3) is live and is the shape the owner pointed at.
4. Known: design option A cannot widen without a menu; chosen option C is writer proposes, code verifies, Jev decides.
5. Cards 2, 48 and 50 (same write call and the done event); card 5 (writer); phase 8.9 (the offer is only honest after the asked-for field lands).
6. `core/graph.py` (write step, `_build_next_step_offer`), `synthesis/sentence_check.py` (extra yes-or-no items), `contracts/events.py` (additive field, dial position 3), `frontend/src` answer screen, and the MCP, CLI and GraphQL adapters, none of which carry the offer today.
7. L.
8. Depends on phases 8.7 and 8.9. Blocks nothing.
9. Yes, five decisions are recorded as waiting in the card; recommendation per the design is yes to each. Ask when the phase opens, not now.

### Card 55: the test queries document is the gate

1. Work counts as done when every feature's "what you should see" passes, run by the team, with an expert checking a few key answers.
2. Not seen directly; it decides what reaches the user.
3. Written, not built. `DECISIONS.md` rows 766 and 770 decided it and reworded seven entries. No runner exists: no script in `testing/Developer/scripts/` or `.claude/` reads `testing/Test_queries_and_workflows.md`, and CI (`.github/workflows/ci.yml`) does not either. The golden consistency run (answered count) remains the blocking gate, as the card says it will until this runs once.
4. Known: the entries are prose, each needs a check shape (exact script, model-graded, or `/verify` screen), and the grader is the card 9 gap.
5. Cards 9 and 42, and card 40 (reviewer reports unchecked).
6. A new runner under `testing/Developer/scripts/`, `eval/` grader reuse, `.claude/` gate wording (branch and owner yes).
7. L (design first, then build, then a baseline run with spend).
8. Depends on card 9's judge choice and card 42's `/verify` specs. Blocks closing cards 9 and 42 and any claim of "done".
9. Yes: "Spend for the first baseline run, and who is the expert for the key answers?" Recommendation: a capped run on the entries marked exact-check first (cheap), model-graded entries second.

## Built versus only written about, with evidence

| Item | Built in code | Only written |
|---|---|---|
| Jev as classifier (point a, c) | `harness/jev_client.py`, `harness/decide.py:decide`, 8.6 decisions in `core/graph.py` | None |
| Open-weight guard and plan models | `harness/tiers.py` defaults, develop override | None |
| Opus writer, per-model effort, 25-cent cap | None on develop | Phase 8.7 branches `feat/8.7-s1..s3`, parked 2026-09-27 |
| Tool calls as MCP-style functions (point b) | `tools/catalogue.py` exists as a closed list; `plan.resource` decision not wired (`Model_architecture.md`) | Card 11.32 |
| Model check on reworded sentences | `synthesis/sentence_check.py`, Jev only, fails closed | None |
| Check and adjust loop (steps 4 and 5 of the owner's loop) | Per-step retry, repair pass, timeouts | C7 re-plan |
| Soft edges | One-hop templates only | Scoping options one to four |
| Judge of answer quality | `eval/rubric_grader.py` (refuses without a judge) | Card 9 and 10.4 |
| Next-step conversation | Go-deeper `next_step` and ask-back for 1 to 3 words | Design for card 52 |
| Verify loop | `/verify`, one spec, page-facts checker | `/design`, bossman wiring |
| Test-queries gate | None | Decision rows 766 and 770 |
| `task_tiers.py` table | The table | Its own docstring: nothing calls it, so it changes no behavior |

## Root causes shared by several cards

1. The write step is one overloaded call with the wrong writer and a heavy prefix. Cards 5, 40 (C1, C8), 52, 2 and 50 all edit `core/graph.py`'s write helpers and `harness/harness.py:call_tier`. One build, phase 8.7 resumed, closes the writer, the reasoning setting, and gives C1 and C8 a measured basis. Cards 52 must be built after it, since its candidate questions ride in the same call.
2. No quality judge, so "done" is an alarm, not a measurement. Cards 9, 55, 42 and 40's "answered is not good" all need one model grader with a rubric taken from the owner's own "what you should see" lines. One fix: build card 55's runner with a model grader and let card 9 be closed as the same work. Card 5 also needs it to pick the writer without relying on the golden count.
3. The answer path cannot adjust when records lack the field asked for. Cards 6, 7, 52 and phase 8.9's field work share this: no step reads results and re-aims. Phase 8.9 fixes the cheap cases (title, species, gene); C7 is the general form. Card 7's soft edges also need that second hop.
4. `.claude/` changes need one itemized approval. Cards 40 (C3 words are not under `.claude/`, but hooks were), 42 and 55 each touch it. Ask the owner for one itemized sign-off covering `/design`, the bossman call and the gate wording, in one question each.
5. Stale board text. Cards 39 and 40 read as queued or being built when they are done or mostly done; card 5 reads as if the writer is imminent. Fix the rows in the next plan edit.

## Suggested order inside the workstream

1. Card 39: mark done. One line; removes a false queued item.
2. Card 40 remainder, only C1 and C8, after step 3. Left here as a pointer; do not build before the writer is chosen.
3. Card 5: resume phase 8.7 (writer, per-model effort, cap). It touches every answer and unblocks C1, C8 and card 52.
4. Card 42: write `/design`, wire `/verify` into bossman mode. Cheap, and every later phase gets checked on screen first.
5. Card 55: build the runner and the grader, then run the baseline. Closes card 9 as the same work.
6. Phase 8.9 (outside this workstream, listed because 6 and 52 wait on it).
7. Card 52: after 8.7 and 8.9.
8. Card 6 (C7) and card 7: discussion first, after the answers carry the right fields. Card 7's single-edge templates can go sooner if the owner approves.

## What was not checked

- No live questions were run, so card 52's "0 of 6" and the writer's current timing are quoted from the 2026-09-26 reports, not re-measured.
- Production's model variables and develop's present `SYNTH_MODEL` were not read from Railway; the code default and docs were used.
- The code value of the per-question cost cap (10 or 25 cents) was not read; only the decision row.
- The content of the unmerged 8.7 branches was read only for the ledger, not their code.
- Whether the owner's retest queries for cards 5 and 40 already passed was not checked; `testing/Test_queries_and_workflows.md` was grepped only for card 9 and 55 lines.
- `tracker/phase_8.7.md` is not on develop; its text came from `origin/feat/8.7-s1`.
