# Build phase 8.7: answers that answer, sooner

A person asks a question and waits about 17 seconds in silence, and the first sentence they finally read counts records instead of answering. This phase:

- makes the first sentence answer the question;
- puts the records on screen at about 8 seconds;
- moves the writing to the model the owner chose.

Opened 2026-09-27 at 04:29 UTC on the owner's overnight decision (`DECISIONS.md`, 2026-09-27, "The overnight run"), which lets it merge overnight if its golden run holds.

Cards: 2 (the first sentence), 50 (nobody waits in silence), 5 (models by tier, the Opus writer). Sources:

- `testing/Developer/reports/2026-09-26_phase_8.7/design.md`: the first sentence, design C.
- `testing/Developer/reports/2026-09-26_answer_speed/report.md`: where the seconds go, options B, C, E and H, tickets S1 to S3.
- `testing/Developer/reports/2026-09-26_writer_bench_3/results.md`: Opus 5.5 at minimal effort confirmed over three runs.

## Table of contents

- [Goal contract](#goal-contract)
- [Budget](#budget)
- [Tickets](#tickets)
- [Builder split](#builder-split)
- [Dispatch plan](#dispatch-plan)
- [Review focus](#review-focus)
- [Out of scope, and why](#out-of-scope-and-why)
- [History](#history)
- [Findings](#findings)

## Goal contract

### Done when

- The first sentence answers the question when a cited record carries the answer, and says plainly which fact the records lack when none does (card 2).
- The records the answer is built from, with their citations, are on screen within about 8 seconds at the median, and the written summary appears above them without the list jumping (card 50, option E).
- The written summary reaches the screen sooner than today's median of 16.8 seconds to the first word, and the screen no longer holds back what has already arrived (card 50, option B and the pacing lag).
- No literature search holds an answer more than 6 seconds; a search cut off says so in the existing note (option C).
- The writer is Opus 5.5 at minimal reasoning effort, with a per-model effort setting and a per-question cap of 25 cents (card 5).

### Verify

- The golden consistency run, three passes over the 50 golden questions: at least 101 of 150 answered, no more than 42 answered summaries withdrawn, must-cite hits recorded, and two columns added from the runs file: the first word's time, and whether the first sentence is the code-built count line or a model-led one.
- The product reviewer on develop: every changed screen at 1280 and 390 beside `docs/build/design/design-system/screens/streaming.html` and `prototype/app.html`, and the five-line rubric's line 1, "does the first sentence answer the question", which may score "states a gap honestly".
- Test queries 1, 2, 17, 72 and 98.

### Output

- A pull request from `phase/8.7-answers-sooner` into `develop`.
- This ledger, with every dispatch, finding and golden number.

### Constraints

- Cite-or-refuse is unchanged. Only sentences the grounding pass already accepted can lead, and a failed, late or unreadable lead decision leaves today's code-built line leading.
- The trust verdict is unchanged.
- The lead decision is a classifier's, Jev's with the owner's fallback rule of phase 8.6, never a match on the question's words (`DECISIONS.md`, 2026-09-24, no hardcoded decisions).
- The stable prompt prefix stays byte-identical (`prompt-cache-discipline`).
- The event contract change is one additive field, bounded like every other field, which puts this phase at dial position 3.
- Card 58's Stop rules stay true: Stop works until the first sentence is on screen, and nothing from a stopped answer shows.
- Model spend stops at the shared account's $8 floor. It held $42.78 at 04:09 UTC, about two golden runs with Opus at roughly $17 each.

### Blocked-stop

- The golden run answers fewer than 101 of 150: stop, and the owner decides.
- PubMed stays down at NCBI: no golden run, so no merge.
- A second failing review on anything: stop that piece, untouched.
- The account reaches its floor: stop spending, whatever is left.

## Budget

- Wall clock: 8 hours from 04:29 UTC on 2026-09-27.
- Dial: position 3, for the event contract's additive field. A numbered phase keeps its branch and pull request anyway.
- Dispatches, 8 of 8 planned: builders A and C now, builder B after card 58 merges, the judge, the adversary, one fix agent, a fresh verifier, and the product reviewer.

| Role | Model | Effort | Started | Ended | Tokens |
|---|---|---|---|---|---|

Resumed 2026-10-08 (night of 2026-10-08 to 09):

- Wall clock: 8 hours from 00:13 UTC on 2026-10-09.
- Dispatches: up to 12, the owner's answer before sleeping (`DECISIONS.md`, 2026-10-08). Planned: builders W (steps 5 and 6), S (steps 2 and 7), F (step 4), R (step 8, after W), the judge, the adversary, one fix agent, a fresh verifier, the product reviewer.
- Spend: at most $20 of OpenRouter credit, read from the credits endpoint before and after each live run. $36.11 left at 00:11 UTC. If it runs out before the live checks finish, the phase still merges on CI and a fresh verifier, with the unrun checks named (the owner's answer).
- Gate: the test queries document; no golden run (the owner's choice).

| Role | Model | Effort | Started | Ended | Tokens |
|---|---|---|---|---|---|
| builder W, steps 5 and 6 | depth | high | 00:15 | 01:08 | 369,476 |
| builder R, step 8 | depth | high | 01:12 | 01:28 | 198,995 |
| integration fixer | depth | high | 01:15 | 01:37 | 190,370 |
| judge | depth | high | 01:48 | 02:13 | 253,632 |
| adversary | depth | high | 01:48 | 02:06 | 307,374 |
| fix agent 1, the gap clause | depth | high | 02:17 | 02:31 | 188,211 |
| fix agent 2, cap, old clients, tests | depth | high | 02:17 | 02:58 | 372,962 |
| fresh verifier | depth | high | 03:19 | 03:40 | 268,023 |
| builder S, steps 2 and 7 | balance | medium | 00:15 | 00:29 | 160,731 |
| builder F, step 4 | balance | medium | 00:15 | 00:22 | 105,106 |

## Tickets

### T-8.7-01: The first sentence answers the question, and the write step waits less (cards 2 and 50)

- Builder: A. Answer path: yes. Status: todo.
- Acceptance, in the owner's words:
  - "The first sentence answers what I asked, or tells me the records do not say."
  - "The list of records the answer is built from appears within a second of the last search finishing."
  - "The written summary arrives sooner."
- Scope:
  - Design C: after grounding, one classifier decision, Jev with the phase 8.6 fallback, sees the question and the first one or two already-grounded sentences and decides whether one of them answers it. Yes: it leads, and the count line follows. No, or any failure: the code-built line leads, extended to name the field the records lack.
  - Option E's server half: ground the listing before the writer call, and send the count line and the listing live, numbered by the listing, carrying the new placement field.
  - Option B, measured under the Opus writer: Opus needed the completeness draft on only 8 of 18 bench questions against glm's 18 of 18, so writing both drafts side by side may cost more than it saves. Measure both orders on the bench questions and keep the faster one within the 25-cent cap, and say which and why.
- Files: `core/graph.py`, only `_write_answer` and the write helpers; `synthesis/findings.py`; `synthesis/answer_layout.py`; `harness/decide.py` for the new decision; their tests.

### T-8.7-02: Act waits less, and Opus writes (cards 50 and 5)

- Builder: C. Answer path: yes. Status: todo.
- Acceptance:
  - "No answer waits more than 6 seconds on a literature search, and when one is cut off, the answer says one of its searches did not finish."
  - "The answer is written by Opus at minimal effort, and a question never costs more than 25 cents."
- Scope:
  - Option C: a 6 second cap on each PubTator call, down from 20.
  - Option H's Act half: name lookups during Act.
  - Option K's first step only: a probe proving whether the reader's output reaches any answer. The skip itself waits for a later phase.
  - The synth tier's default becomes `anthropic/claude-opus-5.5`, with a per-model effort table so Opus runs at `minimal` while every other model keeps `none`; the model is priced before it is called; the per-question cap becomes $0.25.
  - `docs/architecture/Model_architecture.md` says so, in the same commit.
- Files: `core/graph.py`, only `_LAYER_TOOL_ACT_TIMEOUT_SECONDS` and `act_node`; `harness/coordinator_worker.py`; `harness/tiers.py`; `harness/harness.py`'s effort table; `harness/cost_control.py`; `docs/architecture/Model_architecture.md`; their tests.

### T-8.7-03: The screen shows what has arrived (card 50)

- Builder: B, after card 58 merges into `develop` and `develop` merges into this branch. Answer path: no, but runnable behaviour. Status: todo.
- Acceptance:
  - "Within about 8 seconds at the median I see the records with their citations."
  - "The summary appears above the list without the list jumping, and nothing shown is taken back."
  - "Stop still works until the first sentence is on screen."
- Scope:
  - `contracts/events.py`: one additive placement field on `TokenPayload`, bounded.
  - `frontend/src/lib/events.ts`, `hooks/useRunView.ts`, `hooks/usePacedEvents.ts`, `hooks/useAnswerReveal.ts` and the answer screen components: render the listing as it arrives, keep a writing slot above it, insert the summary when it lands, and remove the pacing lag that held arrived text back by up to 13 seconds.
- Design source: `docs/build/design/design-system/screens/streaming.html` and `prototype/app.html`.

## Builder split

| Builder | Tickets | Fence | Model |
|---|---|---|---|
| A | T-8.7-01 | the write step's functions in `core/graph.py`, `synthesis/`, `harness/decide.py` | Opus 5.5 |
| C | T-8.7-02 | Act's functions in `core/graph.py`, the harness tier, effort and cost files, the model map | Opus 5.5 |
| B | T-8.7-03 | `contracts/events.py` and `frontend/` | Opus 5.5 |

A and C touch disjoint functions of `core/graph.py`. The lead fixes the placement field's name and bound in T-8.7-03 before A starts, so A and B agree: `placement`, one of `"listing"` or `"summary"`, default `"summary"`.

## Dispatch plan

1. Builders A and C, now, each in a worktree the lead creates from the pushed phase branch.
2. Builder B, after card 58 lands on `develop`.
3. The judge and the adversary, on the merged branch.
4. One fix agent and a fresh verifier.
5. The golden run, by the lead, once PubMed answers and the balance allows. Then the product reviewer on develop.

## Review focus

- The judge: cite-or-refuse and the trust verdict unchanged; the lead decision failing closed; the prompt prefix byte-identical; the cost cap enforced with Opus's real price; the event field's bound; Stop's rules.
- The adversary: a first sentence that answers confidently from a record that does not carry it; a listing shown that the written answer then contradicts; a summary that pushes the list; a cost overrun.

## Out of scope, and why

- The graph indexes for G-016 and G-021: they belong to the data engineering repository.
- The Pathogen Detection isolate table: a follow-up ticket.
- Guardrail and Think overlapping: the locked specification's Section 10.1 says a refused question never reaches Think, so it is the owner's decision.
- Shorter writer replies: measured after this phase in one golden run.
- A streaming writer, sentence by sentence as the model writes: revisited after B and E, since it clashes with two drafts.

## History

- 2026-09-27 04:29: phase opened on the owner's overnight decision. Transport preflight READY: the product model, the harness model and the graph each answered. PubMed's search is down at NCBI ("Cannot connect to SOLR" at 04:11 UTC), so the golden run waits for it.
- 2026-09-27 04:33: builders A (T-8.7-01) and C (T-8.7-02) dispatched from 4990d821, dispatches 1 and 2 of 8, each in a worktree the lead created, `.claude/worktrees/p87s1` and `p87s3`, since an isolated worktree cannot run the project's Python here. Each may spend at most $1 on live model calls, so the shared account keeps about $34 for two golden runs. Builder B waits for card 58 to land on develop.
- 2026-09-27 04:45: builder C found two things the goal contract did not know.
  - The per-question cap is a deployment variable, `PER_QUERY_COST_CAP_USD`, with deliberately no code default. The owner's decision covers 25 cents on develop, so the lead sets it when this phase merges.
  - Develop's system daily cap is $10. At Opus's mean cost of about $0.126 a question, that is about 79 questions, and one 150-question golden run costs about $19. Raising a daily cap is the owner's decision. The question is queued for the owner, with a notification sent at 04:45 UTC. Until they answer, this phase builds and is reviewed, but its golden run and merge wait.
- 2026-09-27 05:11: card 58 landed on develop (e8169d5c), and develop was merged into this branch (1f16d2bf). Builder B (T-8.7-03) dispatched from 1f16d2bf, dispatch 3 of 8, in `.claude/worktrees/p87s2`.
- 2026-09-27 05:08: a second copy of this lead's conversation, opened by the owner in the belief that the session had been cut off, resumed six of this session's agents by their saved IDs at about 04:55 UTC, builders A and C among them. It stopped every copy and stood down by 05:07. Each builder was told to keep only edits it can account for before its next commit. Duplicate work that is on-brief is reviewed and kept, never rewritten. Nothing from the copy reached `develop` or any remote.
- 2026-09-27 05:31: the owner chose the second window as lead. The first lead's window had lost its connection to the editor, so it looked cut off. Its process was stopped, and the six agents it had running were resumed from the new window: builders A, B and C, cards 53 and 62, and card 63's judge. The release fix agent was resumed to finish its data engineering half.
- 2026-09-27 05:36: the owner raised develop's daily model-spend cap from $10 to $25 (`DECISIONS.md`, the same day), set on develop's API service at 05:36. The golden run now waits only on PubMed, which still answered HTTP 500 at 05:36.
- 2026-09-27 06:45: the machine restarted, with seven agents running and several unit suites in parallel, at a load average of 100 to 200. Every agent stopped at about 06:41, and the restart cleared the temporary folder holding the reviewers' probes. Work in the worktrees survived.
- 2026-09-27 14:36: the owner parked the phase, to finish only the release job that day (`DECISIONS.md`, the same day). Where each builder stopped, on local branches that are not pushed:
  - Builder A, `feat/8.7-s1` at 32e5945e: T-8.7-01 built, but its unit suite never finished and the lead committed the working tree unreviewed, only to keep it safe. Next: review its own diff, run the suite, commit.
  - Builder B, `feat/8.7-s2` at cb407508: the placement field is committed (1e030148), and the screen work is committed unreviewed by the lead. It stopped when the write of a new test file, `frontend/src/components/screens/AnswerScreen.listingFirst.test.tsx`, was refused, and did not route around it. Still to do: the AnswerScreen and App-level Stop tests, reshaping `App.stopUntilAnswer.test.tsx` (7 arms fail by design until then), the mutation reds and the gates. Open item for the lead: MCP, GraphQL, the command line and the feedback capture join token text in arrival order, so they need to order by `placement` once builder A sends the listing first.
  - Builder C, `feat/8.7-s3` at da2c04f6: T-8.7-02 committed in six commits, all mutations red. It stopped during its final gates.

- 2026-10-09 00:13 UTC: phase resumed overnight on the owner's decision of 2026-10-08, from `testing/Developer/reports/2026-10-05_phase_8.7_resume/plan.md`. Step 0: develop (c916cfa3) merged into this branch, clean. Steps 1 and 3: builder C's six commits cherry-picked, all clean; two of its tests were stale against today's develop (the old writer's installed price now estimates slightly above the static figure; card 91 names the unfinished search) and were brought up to date (586d7151). 46 of 46 of its tests pass.
- 2026-10-09 00:15 UTC: builders W, S and F dispatched from 586d7151, each in a worktree the lead created (`asu-8.7-w`, `asu-8.7-screen`, `asu-8.7-field`) on local branches `feat/8.7-w`, `feat/8.7-screen`, `feat/8.7-field`. Builder R (step 8) waits for W, since both edit `core/graph.py`.

- 2026-10-09 00:23 UTC: builder F's step 4 merged into this branch (f0022125): `TokenPayload.placement` (cherry-pick of 1e030148, clean) and one reading-order helper, `contracts/token_order.py`, used by MCP, GraphQL, the command line, feedback capture, the trace source and one script. The guard held every commit the builder tried, so the lead reviewed the staged diff and committed it (d44d44da). Its runs: adapters 857, contracts 214, feedback 220 passed.
- 2026-10-09 00:30 UTC: builder S's steps 2 and 7 merged (af8be31c), committed by the lead for the same reason. cb407508 had three conflicts, resolved around card 59's `stopping` and `answerStood` and card 23's `openTableRow`; six arms of `App.stopUntilAnswer.test.tsx` and two of `App.stopAfterAnswer.test.tsx` reshaped to the owner's Stop rule of 2026-09-27. On the merged branch: `tsc` clean, 77 of 77 in the placement, listing-first and lib tests. Open for review: the writing mark above the records is cb407508's choice and is not in `streaming.html`; the Stop count in `summarySentencesShown` has no biting test.

- 2026-10-09 01:08 UTC: builder W's steps 5 and 6 merged (ae1b0bef), step 6 committed by the lead after the guard held the builder's commit. Builder W's open questions, for review: two Opus drafts price at $0.264 against the 25-cent cap, so the second draft never starts and option B's speed gain will not show; shown-order numbering holds in Plain language but not in grouped Researcher answers; a listing citation's chip never gains the prose quote.
- 2026-10-09 01:17 UTC: the full unit suite on the merged branch: 14 failed, 7350 passed, 143 skipped. Five Stop tests whose premise was a stop before any answer, five ordering tests, two rewording-repair arms, and two debugging-guide coverage tests for the new `contracts/token_order.py`. An integration fixer takes all 14 in `feat/8.7-int`; builder R takes step 8 in `feat/8.7-r` (act_node only). OpenRouter unchanged at $36.11: no live spend yet.

- 2026-10-09 01:30 UTC: the times in this resume's entries were first written from the lead's estimate and some were wrong by up to 80 minutes; they are corrected here from the commit times and the task notifications. Builder R's step 8 done (a68cb417): the reader pass no longer runs on the answer path; a paper's hidden instructions stay blocked by `_sanitized_citeable_row`, which never depended on the reader; `_prefetch_answer_names` no longer runs and is dead code, so step 3's name-lookup gain is gone. Waits for the integration fixer before it merges, since both edit core tests.

- 2026-10-09 01:46 UTC: the writer's finalist check on the branch, $3.67 of the $20 ceiling: no question over 25 cents (most $0.208), first records at a median 9.3 s on the streaming path against 27.3 s for the whole answer, query 88 refused 2 of 2. Report: `testing/Developer/reports/2026-10-08_phase_8.7/live_check.md`. Pull request #218 opened.
- 2026-10-09 02:13 UTC: the judge (FIX FIRST, J01 and J02 major, J03 for the owner) and the adversary (six majors: A01 old command-line clients fail, A02, A03 and A13 a wrong "no clinical features" clause, A06 a question at $0.27, A10 the cap setting at merge). One fix round in two agents split by file: the gap clause rebuilt to hold by construction (62d0889b); placement and the early listing opt-in per request with `?reads=placement`, and the cap a true bound (07b46ff3). Develop merged in (20a8e246); full suite 7468 passed.
- 2026-10-09 03:40 UTC: the fresh verifier confirmed all 12 fixes and found nothing refused or capped under develop's settings (its current writer, a 25-cent cap), but two things worse than develop with no owner decision: on the web a citation chip under a summary sentence no longer shows the words it was checked against (A04, card 57), and every summary waits up to about 3.5 s for Jev's lead-sentence pick (A07); and one minor regression inside fix commit 95680687, the token contract's serialization schema reads `{}` (F-8.7-V01). Under the owner's bar, "a fresh verifier finds nothing worse than develop", the phase does not merge tonight; there is no third round. Pull request #218 stays open for the owner. Dispatches used: 10 of 12.

## Findings
