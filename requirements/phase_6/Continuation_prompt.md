# Phase 6 continuation prompt

Phase 6 is the build. Read this file at the start of any session that continues build work. It is written to be sufficient on its own: reading it is the whole handoff, and no other instruction is needed to begin.

## Table of contents

- [Start here](#start-here)
- [State now](#state-now)
- [Which session to open, before anything else](#which-session-to-open-before-anything-else)
- [Finished phases](#finished-phases)
- [Open items](#open-items)
- [Handover](#handover)

## Start here

If you were handed this file and nothing else, this section is the instruction. Work it top to bottom, then stop reading and act.

### Step 1: know which session you are in

Run this first. It is one command and it decides what you are allowed to do:

```bash
echo "${ANTHROPIC_BASE_URL:-primary provider}"
```

- Prints `primary provider`: you are on the subscription. Every stage is available to you. Go to step 2.
- Prints a URL: you are on the alternate metered backend, and only some stages are yours to run. Read "Which session to open, before anything else" below for which, then come back. If the next action is one you may not run, stop and say so rather than running it anyway.

Do not skip this. The constraint is not recoverable once a session is running, and the failure is silent: a judge dispatched on the alternate backend runs on the builder's model and nothing reports the substitution.

### Step 2: do the next action

The next action is always one line, kept current here. Right now it is:

- FIX THE DISEASE NAMES. Not a build phase. `UI_feedback.md` is the brief.

Everything else on this page is context for that one line. What follows is the state as of 2026-08-31, rewritten rather than appended, so there is exactly one description of where things stand.

### Why that is the next action rather than a build phase

A live browser run on 2026-08-31 captured what an answer looks like to a person:

> The knowledge graph associates the gene BRCA1 with four disease records: MedGen:C0346153, MedGen:C2676676, MedGen:C3280442, and MedGen:C4554406.

Four opaque identifiers where disease names should be. The interface around that sentence is competent, the agent loop runs end to end, two tools fire, three claims are grounded and all three are cited. None of it matters, because a researcher cannot use that sentence.

The cause was established by querying the live graph rather than guessed: Disease nodes carry the SOURCE VOCABULARY in `name`, not a disease name. Sampled across 25 nodes it takes three distinct values, `MedGen`, `MeSH` and `SNOMEDCT_US`. Gene nodes are fine, 23 distinct values across 23 nodes. So a readable answer was NEVER EXPRESSIBLE from Layer 1, and exposing `name` to the Cypher generator would have made it worse, returning the word `SNOMEDCT_US` four times.

WHAT MAKES IT CHEAP, and this is the part worth not losing: `ncbi_efetch` ALREADY RUNS in that exact query, as the second of the two tools, and already reaches MedGen. The machinery to turn `MedGen:C0346153` into a disease name is already in the loop and is already being called. What it is not doing is using that call to label the entities in the answer. Verify that before promising it, but it looks closer to wiring than to building.

The full brief, including the two fix paths and why only one of them lives in this repository, is `UI_feedback.md`.

### Build phase 6.0, merged, and what merged open with it

MERGED as PR #91 on 2026-08-31, all four CI jobs green. It delivers technical specification Section 21's two genuinely missing halves:

- Section 21.3, the at-most-20 Layer 2 and Layer 3 calls per query. The dollar caps cannot see these calls, since NCBI and enrichment APIs are free, so nothing bounded how far one question could fan out.
- Section 21.4's unwired half, the queue wait ceiling read from the calling query's own latency budget. A `lookup` now fails fast at 1.5s and degrades; a deep-research query waits up to 5s.

MEASURING SECTION 21 BEFORE WRITING A TICKET IS WHAT MADE THE PHASE SMALL: five of its eight requirements were already built by the tool phases 3.1 to 3.5, because each tool needed its own rate pool the day it shipped. That measurement is the table at the top of `tracker/phase_6.0.md`.

THE DESIGN DECISION MOST LIKELY TO BE WRONGLY SIMPLIFIED BACK: the ceiling counts at the two Layer 2/3 TRANSPORT chokepoints and never at `act_node`. `act_node` iterates PLANNED calls, one to three per query, while Section 21.3 names retries, wider-than-expected fan-out and ELink traversals as where a 21st call arrives from, all of which happen inside a tool and below `act_node`. This is build phase 5.0's audit-hook argument arriving again for a second reason.

WHAT IT COST AND WHAT THAT BOUGHT: one judge round, no adversary round, twelve findings, four fixed. The judge found NINE, and three of them are CRITICAL saying one thing three ways, that the gate does not pin the production wiring. F-6.0-J-05, the whole Section 21.4 wiring can be deleted and every test stays green. F-6.0-J-07, the arm claiming to measure Section 21.2 builds its own limiter and never touches the shared registry. F-6.0-J-09, removing both production scope bindings changes no test. That is TEST DEBT rather than a broken product, and the distinction is why it merged: both features are verified working by execution, the wait ceiling proven wired by a premise arm failing against it live during the build.

ONE FINDING WAS FIXED BEFORE MERGE and only one, F-6.0-J-03, because it alone made answers strictly worse: the ceiling guard refused Layer 1 graph calls, so a query that spent its budget on `think_node`'s entity resolution answered with zero graph rows and refused where a partial cited answer was available.

THE ADVERSARY ROUND WAS NEVER RUN. Stopped mid-flight by product-owner decision once it was clear the phase was not the constraint. Recorded rather than quietly skipped.

THE MOST TRANSFERABLE RESULT IS A CRITIQUE OF THE LEAD'S OWN JUDGMENT rather than of any line of code: the whole phase was spent on a non-bottleneck while the evidence for the real one, the CURIE answer above, sat in a file the lead edited the same evening. `.claude/rules/attack-the-constraint.md` exists to prevent exactly that and was not applied. The board pointed at 6.0 and the lead followed it without saying out loud that it was not what stood between the product and a usable demo.

TWO PROCESS ERRORS from the same session, recorded rather than tidied away. The phase's own first mutation harness was VACUOUS, matching every arm against itself so it would have reported full coverage for an arm with no mutation, caught only because it reported 20 tests for a file defining 12 (F-6.0-03). And `git stash -u` was run while the judge agent was actively writing its report into the tree, which is the 2026-08-27 mutation-sweep hazard seen from the other side; no damage, but luck rather than care.

### Build phase 6.1, and why it should be split rather than opened

NOT STARTED, and assessed on 2026-08-31 as five unrelated things wearing one number:

| Item | Worth doing before users? |
|---|---|
| The security scan before first ship | Arguably yes, but the trigger was EXPOSURE and that already happened: the product went public on 2026-08-24 and shipping without the scan was a decision taken then. It is overdue, not new |
| F-1.2-04, signup's 409 leaking which emails are registered | Small and real. A handful of lines, not a phase |
| CI and CD gates finalized | ALREADY SHIPPED, in build phases 4.14, 4.12 and 4.15. The only residue is that CI is advisory rather than merge-blocking, which needs GitHub Pro or a public repository and is a billing decision |
| The accessibility pass | Real, and not a precondition for a feedback round with a few people |
| The `dev-standards` six-lens review | A review pass over code. It will find things, the way 6.0's judge round did |

The recommendation recorded with that assessment: pull the security scan and F-1.2-04 out as their own small tickets, and let the rest wait for user feedback.

### Step 3: how a phase runs across sessions

`/bossman` runs stages 1 to 11 and stops only at the phase boundary. The provider split cuts across those stages and cannot change inside a running session. Those two facts collide, so a budget-split phase is three sessions, not one:

| Session | Launch | Stages | Tell it |
|---------|--------|--------|---------|
| 1 | `claude` | 1 to 5 | "open the phase, stop once the premise gate is written and failing" |
| 2 | `claude-build` | 6 to 7 | "work the tickets, stop at the judge" |
| 3 | `claude` | 8 to 11 | "judge, adversary, gates, open the pull request" |

```mermaid
flowchart LR
    A[Session 1: stages 1-5] --> B[Session 2: stages 6-7] --> C[Session 3: stages 8-11]
```

Bossman does not stop at stage boundaries on its own, so each session needs its stop condition stated in the prompt.

The simpler default, and the right one while subscription budget is healthy: run the whole phase in one session on `claude`. The three-session split exists to rescue a week that would otherwise be lost, not as a daily routine. Reach for it when the limit is close, not before. In one line: use `claude` until it stops working, then use `claude-build`.

## State now

This section is DERIVED FROM `tracker/BOARD.md`. If the two disagree, the board wins and this section is stale. Open `tracker/board.html` in a browser for the same thing visually.

### The next action

Nothing is blocked, and NOTHING ON THE BOARD IS THE NEXT ACTION. That is deliberate, not an oversight.

| Next | What it is | Where it is tracked | Gated on |
|---|---|---|---|
| 1 | Fix the disease names, so an answer reads a disease rather than `MedGen:C0346153` | `UI_feedback.md`, the headline finding | Nothing. It is the constraint |
| 2 | The rest of the UI feedback: the fragmented answer flow, follow-ups that do not continue the thread, the placeholder integrations page, and an answer that never offers a next step | `UI_feedback.md`, complaints 1 to 5 | The first item, for complaint 5 specifically |
| 3 | Put it in front of people and hear back | Not a ticket yet | Items 1 and 2 |
| 4 | The security scan, and F-1.2-04's signup enumeration leak, pulled out of build phase 6.1 as their own small tickets | `requirements/Plan.md` Phase 7 | Nothing technically. Worth doing alongside item 3 since real users mean real exposure |
| 5 | Build phase 6.0's eight open judge findings, and what remains of 6.1 | `requirements/Plan.md` Phase 7 | User feedback |

SO: fix the disease names.

### The unit of work is no longer a build phase

Product-owner decision, 2026-08-31, and the most important line on this page for whoever reads it next. WORK IS NOW PICKED FROM open flags and `UI_feedback.md`, not from Section 25's build order.

Section 25 has run its course as a driver. Every numbered phase has merged or moved to `requirements/Plan.md` Phase 7, and `tracker/BOARD.md` carries NO open phase at all. What remains is of two kinds and neither is phase-shaped: findings attached to code, which are conditional and become work only when someone touches that code; and defects a real person hit on the live site.

Build phase 6.0 is the argument for the change rather than an aside. It was opened because the board said it was next. It delivered contention protection that is invisible with one user, and measuring its own specification section first showed five of its eight requirements were already built. Meanwhile the defect that makes every disease answer unreadable sat in `UI_feedback.md` the whole time. A phase number is a poor proxy for value once the specification is mostly built.

WHAT DOES NOT CHANGE, and do not let this be quietly lost: the premise gate written before the code and watched failing, the judge round, the write-first rule for findings, and a goal contract before any autonomous run. Those apply to a piece of work whatever it is called. `docs/build/Build_workflow_cadence.md` is scoped to a build phase and now needs a smaller sibling for flag-sized work. That sibling is NOT yet written, which is recorded here rather than assumed to exist.

WHAT WOULD REVERSE IT: a genuinely phase-sized deliverable, most likely whatever user feedback asks for that does not exist yet.

THE BOARD CARRIES NO OPEN PHASE AT ALL, as of later the same day: 6.1 left it too, joining 7.0 and 7.1. That is the honest state rather than a gap, because the thing standing between this product and a v1 real people can use is not a build phase. 6.1 needed handling the 7.x removals did not: those rows had EMPTY flag cells, while 6.1 carried two live findings, so their mentions moved to the phases that FOUND them (F-1.2-04 to build phase 1.2, ADV-03/06/07 to build phase 3.0) rather than being orphaned or deleted. What orders the work is this table.

### The evaluation track is CLOSED, and that is a decision rather than an oversight

Every phase in the evaluation track has merged, and the track is closed at that by product-owner decision on 2026-08-31. Do not open new evaluation work off the back of it.

What that leaves standing, stated plainly so a later reader does not mistake closed for finished:

- The 50-question golden dataset exists and its constraints were each read from a live NCBI lookup. The rows are factually sound.
- The grading harness merged and DOES NOT WORK. `replay()` refuses to run without `acknowledge_parked=True`. That is deliberate.
- Build phase 5.3's `must_reach` and `live_only` fields exist and NO golden row uses them.

Making the grader work, and authoring rows that use those fields, are post-v1 follow-up. They sit in `requirements/Plan.md` under Phase 7, not on the board, because putting them on the board would say they are queued work when they are not.

The one thing this affects downstream: build phase 7.0 benchmarks models against the golden dataset, and it will need a working grader. That dependency is real and is recorded in Phase 7 rather than being allowed to surprise whoever opens 7.0.

### Before you touch anything under `src/`

Read `docs/build/Debugging_guide.md`. It is a symptom index followed by one row for every Python file under `src/system_03_search_agent/`, and it is the fastest route from a failure to the file that owns it.

It also carries an obligation that CI enforces. Add, delete, rename or repurpose a file under `src/` and you update the guide in the SAME commit, then regenerate its manifest:

```bash
python tests/system_03_search_agent/test_debugging_guide_coverage.py
```

### Where the detail lives

Per-phase narrative is deliberately NOT repeated here, because a second copy drifts.

| What you want | Where it is |
|---|---|
| Current status, evidence, open flags | `tracker/BOARD.md`, or `tracker/board.html` in a browser |
| One file per phase, with tickets and findings | `tracker/phase_N.M.md` |
| The dated narrative of every phase | `requirements/Plan.md`, Revision history |
| What broke and what fixed it | `LEARNINGS.md` |
| Choices between alternatives | `DECISIONS.md` |
| Older Phase 6 state, kept for reference | `requirements/phase_6/Phase_6_history.md` |

## Which session to open, before anything else

Added 2026-08-04. The build harness has an alternate, metered model backend for when the primary provider's weekly budget runs out. It is scoped by ROLE, not by phase, and the choice is not recoverable after the fact, so make it before opening anything.

| Cadence stage | Launch with | Why |
|---------------|-------------|-----|
| 3, 5, 8, 9: decompose, premise gate, judge, adversary | `claude` | The only stages that genuinely need the primary provider. Everything spent elsewhere is taken from here |
| 1, 2, 4, 6, 7, 10, 11: open, learnings, dispatch, build, log, gates, close | `claude-build` | Cheap and metered. Every token spent here is a token those four stages keep |
| 8, 9 when the primary budget is gone | `claude-review` | Records findings, closes nothing, and stages 8 and 9 re-run on `claude` before anything merges |

Three rules that are not negotiable, each with a reason:

- Never open a phase on the alternate backend. Stages 3 and 5 are where a bad split or a weak gate cascades into every builder dispatched afterwards.
- A review produced on the alternate backend is non-binding. It records findings and closes no ticket.
- Do not spend the primary provider on builder volume. The scarce resource is not money, it is capacity for the four stages that cannot run anywhere else. Burn it on building and you reach the limit with those four unfinished, which stalls the phase completely.

Why this needs a separate session rather than a per-dispatch model argument: on the alternate backend a session-wide subagent model overrides both the per-invocation model parameter and any subagent's own frontmatter, so a judge dispatched at Depth silently runs on the builder's model. Role tiering there is done by launching a different command, full stop.

The capability bands and the alternate-backend column are in `docs/build/Build_workflow_cadence.md` under "Provider mapping". The three commands above are local wrappers; the model identifiers, prices and credential location behind them are deliberately not in any tracked file and live in a local, uncommitted note under `docs/build/multi-model-harness/`. If the wrappers are not on this machine, that folder will not be either, and plain `claude` is unaffected.

## Finished phases

The per-phase records that used to sit here were moved to `requirements/phase_6/Phase_6_history.md` on 2026-08-30, verbatim. Fourteen of them had accumulated, roughly half this file, describing phases that closed weeks ago.

For the full dated narrative of every phase, read `requirements/Plan.md`'s revision history, which is that fact's single owner.

## Open items

One decision below is still waiting on the product owner: whether `security/` stays gitignored. Still ignored today (`.gitignore:50`). This decides whether the Step 6.2 scan results are ever committed.

| Item | Description | Owner |
|------|-------------|-------|
| `GCK` resolves locally and is refused on the deployed API | Recorded as an unproven HYPOTHESIS rather than a finding, because its traceback could not be read: Railway's log stream returns container startup and `/health` lines and no request-level logs. The behaviour differs on IDENTICAL code, which is what makes it worth keeping. `tracker/phase_4.12.md` names what would settle it. Lifted here 2026-08-30 from the superseded "Read before opening the next phase" section before that section was archived | Whichever phase next touches entity resolution |
| F-3.1-41: stopword list vs. real gene symbols | Product decision, not a bug. Detailed in `tracker/phase_3.1.md` DECIDED 2026-08-15: folded into build phase 4.7's entity-resolution design, because the stopword list it turns on is the heuristic 4.7 replaces | Build phase 4.7 |
| F-3.1-42: lowercase gene mentions fall through silently | Product decision, not a bug. Detailed in `tracker/phase_3.1.md` DECIDED 2026-08-15 with F-3.1-41, same reason | Build phase 4.7 |
| F-3.1-50, F-3.1-51: RESOLVED, Step 6.2, 2026-08-10 | Re-checked live-exploitability now that `ncbi_efetch` is wired into `act_node` (T-3.4-05). F-3.1-50 confirmed live-reachable and real (`ncbi_datasets_actions`'s nested lists had no item-count bound); fixed, matching the sibling module's existing `_MAX_NESTED_ITEMS` pattern, regression test added. F-3.1-51 was a docstring overclaiming 429/503 coverage it never had; corrected | Closed |
| F-3.1-46: minor gap in code `act_node` cannot reach yet | Re-checked alongside F-3.1-50/51: `ncbi_coordinate_overlap`'s dict-recursion gap has no current caller that constructs a dict-valued field, so it stays latent, not live-reachable. No fix applied | Whenever the product owner decides, or before a future field addition nests a dict |
| F-2.2-T-01-residual | A declarative injected as a comma-spliced clause inside a single wh-question still licenses its own words. Needs clause-level rather than sentence-level filtering. Pinned by a strict xfail. Product-owner decision, Step 6.2, 2026-08-10: keep tracking rather than fix inline, real engineering work better scoped as its own task | Whenever picked up as a dedicated task |
| F-3.4-T06-01: staleness cannot fire | Section 7.4's staleness auto-cross-verify (build phase 3.4) is real, wired, and unit-tested, but every Layer 1 vertex this graph's current ingest returns carries only a generic BioLink property set, never a field named in the staleness field-class tables, so the check never fires against live data today. A System 1/2 ingest gap, not fixable from this repo. Confirmed still true at Step 6.2, 2026-08-10. Detailed in `tracker/phase_3.4.md` | Whenever System 1/2's ingest carries a richer per-domain property |
| F-3.4-A-04: premise gate coverage overclaim | `test_citation_trust_full_premise.py`'s own coverage statement claims a real concordant/discordant triangulation verdict is exercised; live-confirmed the flagship claim is structurally stuck at `insufficient` given the current single-second-origin wiring. Detailed in `tracker/phase_3.4.md` | Whenever a second live origin is wired, or the doc is corrected to state the real coverage |
| F-3.4-A-05: staleness-note precision gap | Dormant, depends on F-3.4-T06-01 firing first. When it does, the note "no live cross-check was dispatched" cannot distinguish "never dispatched" from "dispatched but timed out or errored". Detailed in `tracker/phase_3.4.md` | Whenever F-3.4-T06-01 is closed and this becomes live-reachable |
| F-3.4-A-06: source_url pattern end-anchor gap | `NCBI_SOURCE_URL_PATTERN`/`NCBI_EFETCH_RECORD_URL_PATTERN` are anchored at the start but carry no `$` end anchor, so a Pydantic `pattern=` only enforces a prefix match. Still not exploitable through any current call site (all seven verified URL-encode first, live-checked at Step 6.2, 2026-08-10). Product-owner decision, 2026-08-10: worth fixing properly, not urgent enough to rush. A naive `$` appended right after the host prefix would reject every real citation URL, since all of them carry a path or id after the host (`/gene/7157`); the real fix needs a character-class restriction on what may follow (e.g. `[A-Za-z0-9/_.\-]*$`), a scoped design decision, not a one-line edit. Detailed in `tracker/phase_3.4.md` | Scheduled as its own dedicated task, before build phase 6.1's hardening pass or before any new citation-building call site is added, whichever comes first |
| F-3.4-T03-01: guardrail step_error missing keys, RESOLVED Step 6.2, 2026-08-10 | `guardrail_node`'s `ClassificationUnavailableError` branch built a `step_error` dict missing the `fatal`/`scope` keys every other site supplies, crashing uncaught. Added both keys, matching every sibling `_step_error_kwargs`-shaped site. Detailed in `tracker/phase_3.4.md` | Closed |
| F-3.4-A-07's diagnostic gap, PARTIALLY RESOLVED Step 6.2, 2026-08-10 | The real provider error text (e.g. an OpenRouter 402) now reaches `HarnessCallError`'s internal message, so an "unexpected"-classed provider error is no longer root-causeable only by live manual reproduction. The end-user-facing message stays deliberately generic. The separate question, whether "unexpected" errors should auto-retry, is real harness-territory work, explicitly deferred rather than fixed here. Detailed in `tracker/phase_3.4.md` | A dedicated harness review round |
| Section 8.2 matching rule, RESOLVED Step 6.2, 2026-08-10 | The substring branch answered whether a clause MENTIONS the cited value, never whether it is TRUE about it. The prototype's two additions (`numbers_are_supported`, `claim_introduces_no_new_content`) are now written into the tech spec as Section 8.2 steps 5a and 5b | Closed |
| Section 23 offline gate, RESOLVED (as a decision) Step 6.2, 2026-08-10 | Now runnable for the first time (all seven tools merged). Product-owner decision: keep it scheduled for build phase 5.1 rather than run the smaller version early; running now would be setup work redone properly at 5.1, not saved work | Build phase 5.1 |
| `release-workflow` dispatch gap, RESOLVED Step 6.2, 2026-08-10 | Marked mandatory in `bossman-mode.md`, measured 0 of 6 real dispatches, an ownerless requirement by this repo's own `attack-the-constraint` standard. Rewrote the rule to name the judge round, adversary round, and stage-10 gates as the real phase-end requirement; `release-workflow` stays available as a direct invocation | Closed |
| Whole-repository security scan | No build-phase code has ever been scanned. One scan predates phase 1.0. Confirmed unchanged at Step 6.2, 2026-08-10: still PAUSED INDEFINITELY on cost | EXPOSURE (a deploy, a public URL, or first contact with a non-product-owner user), not a phase number |
| F-2.1-02, RESOLVED Step 6.2, 2026-08-10 | Section 6.1 documented a parameter mechanism that cannot work; corrected to describe the real shipped PREPARE/EXECUTE mechanism. `docs/ncbi/Tool_implementation_mechanics.md` and `.claude/rules/production-examples.md` were already correct before this reconciliation | Closed |
| F-2.1-01, RESOLVED Step 6.2, 2026-08-10 | The spec said 10 concept labels, the live graph has 11 (the eleventh is `NamedThing`). Corrected, five occurrences | Closed |
| F-2.1-16, RESOLVED Step 6.2, 2026-08-10 | `budget_for_step` diverges from Section 19.1's per-query-class shape by design (a separate per-tier budget for model-calling steps, deliberately chosen over the spec's single shape after the spec's own shape measurably failed). Section 19.1 corrected to describe the real two-shape budget | Closed |
| Env var name divergence, RESOLVED Step 6.2, 2026-08-10 | Section 24 named `PER_USER_DAILY_CAP_USD`; the code uses `PER_USER_DAILY_QUERY_CAP`, since it holds a query count, not dollars. Corrected | Closed |
| F-2.2-01 | Generation intermittently emits Cypher with no parentheses around node patterns, the graph rejects it, and nothing retries. Roughly 1 run in 10, last measured at build phase 2.2's open. Deliberately NOT fixed on `fix/c15-generation-bound`: the ticket's own acceptance criteria allowed either a retry or recording it as still open, and a retry would touch `cypher_query.py`'s error-handling path in the same review pass as a critical safety fix, which `tracker/fix_c15_generation_bound.md` argues against. Cannot be re-measured live from this environment (same tunnel constraint as T-3.0-07) | Whenever the live graph tunnel is reachable |
| F-2.1-J4-02, prompt injection | The guardrail now refuses the injected-instruction shape at admission, verified by 3.0's own premise gate. The `xfail` marker itself is NOT cleared: doing so needs 2.1's gate run five consecutive times against the live graph, and the SSH tunnel cannot be opened from this environment (the Layer-7 proxy cannot tunnel raw SSH, and `block-bash-delete.sh` blocks `ssh` as an execution wrapper). Roughly ten minutes of work whenever the tunnel is reachable | T-3.0-07, environment-gated, not phase-gated |
| F-3.0-01, RESOLVED Step 6.2, 2026-08-10 | Section 10.5 requires refusing a write-seeking request and named no `GuardPayload.category` for it; `off_topic` was reused and the real explanation lived only in the reason string. Added `write_seeking` as a new enum member (additive, v1-legal). Also found and fixed a second hand-maintained copy of the category set in the frontend's runtime type guard, which would have silently rejected a real `write_seeking` event at the UI layer | Closed |
| ADV-03, ADV-06, ADV-07 | Three guardrail defense-in-depth gaps where the Guard-tier classifier remains the covering layer: non-Latin-script injection phrases are invisible to the pre-filter's literal phrase list, the write-verb list has gaps, and `classifier.build_messages` does not escape a `</query>` in the payload. Re-homed 2026-08-04 from "the next round", which was never scheduled | 6.1 |
| ADV-02-residual | A non-English question written in pure ASCII with no cognate and no identifier is still refused as off-topic by the pre-filter. Measured: "Welche Krankheiten sind mit dem Gen assoziiert?" A keyword allowlist cannot do language detection, and per-language vocabulary is the infinite-blocklist trap. Mitigated: the classifier now judges off-topic, and the pre-filter abstains on any non-ASCII letter or on a query containing no English function word | 6.1, with the other guardrail hardening |
| F-2.1-07 | Gene symbol resolution beyond a one-entry seed table, needs the Layer 2 NCBI lookup. Also the real fix for build phase 2.2's symbol-versus-CURIE false reject | 3.1 |
| F-2.1-B10 | Same cause as F-2.1-07; an unresolvable symbol errors rather than refuses | 3.1 |
| PubTator3 relations endpoint | Path and fields still not live-verified as of build phase 3.3's close; `pubtator_annotate` has no `mode` for it. Confirmed still unverified at Step 6.2, 2026-08-10, deliberately not probed live this reconciliation (no build decision needed until someone spends the verification work) | A fast-follow ticket once verified |
| F-3.3-J-04: disclosure-policy asymmetry | `pubtator_annotate` withholds an over-cap field silently (`None`); `litvar2_lookup`, built the same phase, discloses every withholding via `fields_withheld`. Product decision, not a bug. Detailed in `tracker/phase_3.3.md` DECIDED 2026-08-15: one rule, if the system drops or shortens anything it discloses that it did. Also settles F-3.5-10 | Next backend ticket touching either tool |
| F-3.3-J-06: litvar2_lookup citation quality | RESOLVED, Step 6.2, 2026-08-10. Section 6.5 widened (additive) with two new fields: `variant_matches[].source_url`, this match's own dbSNP page, populated for every match with a real rsid regardless of match count (the output-level `source_url` stays correctly gated to the single-match case); and `pmid_source_urls`, one canonical PubMed URL per `pmids` entry. Two new regression tests | Closed |
| F-3.3-A-05: entity_lookup has no citation | RESOLVED, Step 6.2, 2026-08-10. Section 6.4's locked entity item schema widened (additive) with `source_url`, formalizing what build phase 3.3's code already shipped beyond the locked schema's `additionalProperties: false` (populated for the two live-verified db types, `ncbi_gene` and `ncbi_mesh`; `None` for `litvar`/`cvcl`, unverified record-page shapes, not attempted here) | Closed |
| F-3.3-RR-02: litvar2 empty-guard is count-based, not content-based | A row that parses as a dict but carries no identity (`_id`, `rsid` both absent) still ships as an all-`None` match under `status: "ok"`. Not reachable on live data today; deliberately not fixed a second time on a guard that already regressed once (F-3.3-RR-01) | Whenever live data actually produces this shape |
| F-3.3-A-10: non-rsid litvar_id source_url fallback | Cites a raw internal identifier as a human search term when the id doesn't match the `litvar@rs...##` shape; live-reachable (1 of 5 rows for `query="334"`) unlike most of this module's fallbacks | Whenever the product owner decides |
| F-3.3-A-11: cross-tool id-shape mismatch | `pubtator_annotate`'s `db_id` for a `litvar`-sourced entity and `litvar2_lookup`'s expected `litvar_id` are shaped differently; a plan-tier model could pass one tool's output into the other's input and get a 400. Still not reachable: build phase 3.4 (T-3.4-05, closing T-3.1-28) wired only `ncbi_efetch` into `act_node` as a second answer-bearing tool, neither `pubtator_annotate` nor `litvar2_lookup` | Whenever either tool is wired into `act_node` |
| F-3.3-A-12: undisclosed annotation/variant_matches truncation | `_MAX_ANNOTATIONS` and `_MAX_VARIANT_MATCHES` cap silently, with no companion total field, unlike `pmids`'s honest `total_pmids`. Not reachable on live data sampled this phase (max observed: 26 of 100, 5 of 10) | Whenever live data actually produces this shape |
| F-3.3-A-13: asymmetric batch-failure disposition | One malformed (non-numeric) PMID fails an `annotate_publications` batch closed with no partial result, while a numeric-but-nonexistent PMID in the same position preserves the rest of the batch (F-3.3-01's own disposition). Undocumented asymmetry, safe direction (refuses, does not fabricate) | Whenever the product owner decides |
| F-3.5-A-03: clinicaltrials_search query syntax risk | RESOLVED, Step 6.2, 2026-08-10, by disclosure. `query_cond` is parsed as an Essie expression, not a literal phrase, so a real clinical term containing `NOT` silently returns the exact inverse of what was asked, `status: "ok"`, confidently cited. Live-proven arithmetic (`Carcinoma` 27,619 minus `Carcinoma Otherwise Specified` 31 equals `Carcinoma NOT Otherwise Specified` 27,588). Product-owner decision: disclose the risk in the field's own schema description rather than escape caller text, since escaping would silently break a caller's intentional boolean search. The plan-tier model now sees the risk directly in the tool schema it is given | Closed |
| F-3.5-A-07: clinicaltrials_search weak-match shape, PARTIALLY RESOLVED Step 6.2, 2026-08-10 | The phase 3.3 weak-match shape (F-3.3-A-01/02/03) reproduces here undisclosed: `query_cond="5"`/`"the"`/`"a"` all return confident, wholly generic citations. The tool now sends `sort=@relevance`, the only concrete lever available, since ClinicalTrials.gov's `/studies` endpoint returns no per-result relevance score to disclose the way phase 3.3's fix did. Ordering improves; there is still no disclosable score | A future fix round, if the API ever exposes a disclosable relevance signal |
| F-3.5-A-09: pathogen_detection empty overloaded | RESOLVED, Step 6.2, 2026-08-10. Added `"timeout"` as a fourth `status` enum value (additive, Section 6.6 widened), and `_deadline_exceeded_output` now returns it instead of `"empty"`. `"empty"` now means only a genuine no-such-record; `"timeout"` means the wall-clock budget ran out before a qualifying row was found. No downstream consumer branched on the old 3-value set (pathogen_detection is not yet wired into `act_node`). Four tests updated | Closed |
| F-3.5-A-10: pathogen_detection dead cluster_list read | `_cluster_snp_neighbors`'s `cluster_list.tsv` membership check is unconditionally overwritten before use once the SNP scan's own results are known, so its only surviving effect is an existence check while consuming real time from the already budget-starved shared deadline | Whenever the product owner decides |
| F-3.5-A-11: pathogen_detection latent distance-column fallback | `_SNP_DISTANCES_DISTANCE_COLUMN_CANDIDATES`'s fallback to `delta_positions_unambiguous` is a genuinely different metric, not a synonym, and live sampling shows the two routinely disagree. Not observed firing on ~9,400 sampled rows; documented as a defense-in-depth-only risk | Whenever live data actually produces this shape |
| F-3.5-A-12: clinicaltrials_search overall_status enum gap | RESOLVED, Step 6.2, 2026-08-10. The locked 6-value input enum was narrower than the live API's real values, live-confirmed at 14 total (not the 12 estimated when this was filed) via `GET /api/v2/stats/field/values?fields=OverallStatus`. Widened (additive) to all 14 in Section 6.7 and the code schema. 8 new values added to the parametrized acceptance test | Closed |
| F-3.5-A-14: clinicaltrials_search punctuation error message | An unbalanced-punctuation `query_cond` (a stray closing paren) is correctly classified as a permanent HTTP 400 rejection, but the message gives no hint that punctuation is the likely cause | Whenever the product owner decides |
| F-2.2-06 | A truncated answer discloses the cut but not its scale on a listing query, since `total_available` is None for that shape. Upstream of the Write step | 3.x, whichever phase touches `cypher_query`'s totals |
| F-2.1-A5-05 | `mentioned_in` from BRCA1 costs 27 seconds forward plus the full budget reversed, despite being indexed, anchored, and LIMIT 25. Described, deliberately not reproduced | 3.x |
| F-06 | 2 of 6 model calls per query bypass the stable prompt prefix, a cost inefficiency, not a correctness defect. The Write step's own call is not one of them as of 2.2 | 4.0 |
| F-1.2-01 | The run registry never evicts a completed or abandoned run | 4.0 |
| F-1.2-02 | An abandoned client SSE connection does not halt the server-side task | 4.0 |
| F-1.2-03 | The per-run event queue is single-consumer | 4.0 |
| F-4.1-A-10: untrusted content relayed unlabelled to an agent consumer | Content originating in untrusted third-party sources (a PubMed abstract field, the narrative answer built from it) reaches an MCP caller byte-identical to the system's own words, with no field distinguishing the two. A product-level call, not a fix to invent mid-round. Detailed in `tracker/phase_4.1.md` | Whenever the product owner decides, or build phase 6.1's hardening pass, whichever comes first |
| F-4.1-A-15: caller-supplied session_id unbound to the caller | The MCP tool accepts a caller-supplied `session_id` with length validation only, no ownership check. Harmless today (nothing reads it yet); becomes a live authorization gap the moment a session-memory or interaction-capture consumer is wired. Detailed in `tracker/phase_4.1.md` | Build phase 4.5 or 4.6, whichever first wires a `Query.session_id` consumer, and before either ships |
| New-intake: design the MCP server stateless from the start, RESOLVED build phase 4.1, 2026-08-11 | An intake note on MCP's 2026-07-28 spec update (moved to a stateless request/response core, rich behavior pushed into versioned extensions, auth hardened to OAuth 2.0/OIDC) landed at Step 6.2, 2026-08-10. Followed: `adapters/mcp/server.py` mounts `streamable_http_app(stateless_http=True)`, no session state between calls. OAuth 2.0/OIDC alignment stays deliberately unbuilt in favor of reusing the existing bearer-JWT mechanism (see `tracker/phase_4.1.md`'s scope-boundary note); revisit if this ever faces real external auth rather than a custom token scheme. Full note: `personal-os-work/NIH/Agentic-Search/Reference/system-3-brainstorming/MCP_stateless_core_extensions_and_hardened_auth.md` | Closed |
| F-2.0-04 | Nothing writes `interactions` rows, so both daily cost caps read zero | 4.6 |
| F-2.0-10 | `trace_id` is client-supplied and never server-overwritten | 4.6 |
| New-intake: signal-based sampling for the manual feedback-loop review step | An intake note landed at Step 6.2, 2026-08-10: instead of random or longest-conversation sampling for which captured interactions a human reviews, score by signal (user had to correct the answer, a tool call looped, a refusal that should have answered) and review those first. One cited study reports 82 percent versus 54 percent informative-review yield from signal-based sampling. Applies to Decision G's manual-review stage. Full note: `personal-os-work/NIH/Agentic-Search/Reference/system/Serverless_on_prem_and_edge_designing_efficient_AI_systems.md` | 4.6, or 5.1 if the review step lands there instead |
| New-intake: OpenRouter Auto Router as a model-selection candidate | `openrouter/auto` classifies a prompt into one of about 30 task types and picks a model by the community's trailing 7-day spend share, reporting the model actually used in the response. It is explicitly non-deterministic and can pick a different model on every turn. DEFERRED 2026-08-30 by product-owner decision, because the eval harness being built at 5.1 and 5.2 cannot attribute a score when the model moves underneath it, and `prompt-cache-discipline` requires a tier's model to be held for a whole query. THREE distinct uses to evaluate separately: a benchmark candidate per tier at 7.0; an arm of the randomized routing at 7.1; and a FALLBACK when a pinned model is unavailable, which is resilience rather than selection and does not disturb determinism. Full reasoning in `DECISIONS.md`, 2026-08-30 | Build phase 7.0, with the 7.1 and fallback uses assessed separately |
| Golden fixture domain sign-off | Nobody is named to verify the clinical and human-variation expected answers | 5.1 |
| The golden 50 are a v1, and the settled set needs SME input | Product-owner decision, 2026-08-31: "this golden dataset is just a start based on the data that we found. Nothing else. Data + actually SME input will determine what should be the right answers." SUPERSEDES the 2026-08-30 resolution that named the product owner as the sign-off owner, which stands only for v1. WHAT IS SETTLED: every constraint in the 50 rows was read from a live NCBI lookup and independently re-verified, so the rows are factually sound. WHAT IS NOT: whether these are the right questions, and whether each expected answer is the one a domain expert would give. Neither is answerable from a lookup. THE PRACTICAL CONSEQUENCE, and the reason this is an open item rather than a note: no new golden questions get authored until SME review, because authoring against a set that review will move is what parked build phase 5.2. Build phase 5.3 therefore ships the schema that makes Layer 2 and Layer 3 requirements EXPRESSIBLE, and deliberately authors no rows that use it | An SME engagement, not a phase number. Blocks any golden-content work; blocks nothing mechanical |
| Curate LEARNINGS.md into the golden eval dataset | Product owner's idea, 2026-08-10, raised directly rather than via a new-intake note: several LEARNINGS.md findings (the bare-number and common-word weak-match cases from build phase 3.3, the third-person clinical questions from build phase 3.0, the two-gene dropped-answer case from build phase 3.4, the `NOT`-in-query risk from build phase 3.5) are concrete "a real user could ask this and get a confidently wrong answer" cases, currently pinned only as narrative plus scattered unit and regression tests, never as golden-set eval questions. Ideally LEARNINGS.md feeds the evaluation playbook, not just the codebase. Not an automatic import: most entries describe internal plumbing bugs rather than realistic user questions, and none carry a rubric score or expected citation yet, so this needs a real curation pass against the actual playbook rubric, not a bulk copy | 5.0, when the golden 50-query dataset is built |
| F-1.2-04 | Signup's 409 response undermines login's anti-enumeration guarantee. Pair with F-1.1-10, same defect class in the same endpoint | 6.1 |
| Python lockfile | Every backend dependency floats on `>=`, including security-critical ones | 6.1 |
| Stand up CI | No `.github/workflows/` exists; every gate every phase has passed was run by hand | 6.1 |
| Fix `pip install .` | Fails outright on a `package-dir` mapping error, pre-existing | 6.1 |

Unowned, needing an explicit decision rather than an assumed phase:

- F-1.1-10, F-1.1-11's `User-Agent` half, and F-1.1-18: deferred from build phase 1.1 to 1.2, and 1.2's own ticket list never touched any of the three.
- Auth-path logging: RFC 6819 family revocation still fires silently. Scheduled for build phase 1.2, did not happen, needs a new home.
- New-intake: a semantic guardrail layer, not just a shape one. An intake note landed at Step 6.2, 2026-08-10, arguing today's multi-agent schema gate only checks shape (valid JSON matching the schema), never meaning, and proposing a second layer between Act and Write that validates against MeSH, Gene Ontology, and NCBI taxonomy, catching a case like "this variant is linked to the wrong organism" that passes schema validation cleanly. A plausible enhancement to Section 10's guardrail design, not scoped anywhere yet and no trigger defined. Full note: `personal-os-work/NIH/Agentic-Search/Reference/system/Ontologies_as_guardrails_for_agentic_AI.md`

## Handover

- If a different agent takes over, read the "Running this project with a different agent" section in `CLAUDE.md`, which `AGENTS.md` mirrors.
- Short version: the file artifacts and the model tiering port cleanly, skills and rules port as content but not as invocation, and the four security hooks do not port at all.
- They are the only structural enforcement in this repo, so substituting them is the first handover step.

- One operational note that cost real time on 2026-08-03 and is not obvious from any other file: this machine's network dropped three times in one session, killing two premise-gate runs and three review agents, and every failure they produced looked like a code defect at first glance.
- Before diagnosing any model-dependent failure, check reachability with `curl -s -o /dev/null -w "%{http_code}" --max-time 15 https://openrouter.ai/api/v1/models`.
- An outage shows every premise-gate failure carrying `source='guardrail'`, the first model call in the loop, with an empty narrative and no citations, so nothing reaches synthesis at all.
- A genuine Write-step defect reaches synthesis and fails later.

Last updated: 2026-08-31.
