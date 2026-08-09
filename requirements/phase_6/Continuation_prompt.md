# Phase 6 continuation prompt

Phase 6 is the build. Read this file at the start of any session that continues build work. It is written to be sufficient on its own: reading it is the whole handoff, and no other instruction is needed to begin.

## Table of contents

- [Start here](#start-here)
- [State now](#state-now)
- [Which session to open, before anything else](#which-session-to-open-before-anything-else)
- [Read before opening the next phase](#read-before-opening-the-next-phase)
- [Build phase 3.0, done](#build-phase-30-done)
- [Build phase 3.1, done](#build-phase-31-done)
- [Build phase 3.2, done](#build-phase-32-done)
- [Build phase 3.3, done](#build-phase-33-done)
- [Build phase 3.5, done](#build-phase-35-done)
- [What build phase 3.4 delivers](#what-build-phase-34-delivers)
- [What Step 6.2 delivers, later](#what-step-62-delivers-later)
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

The next action is always one line, kept current at the top of "State now" below. Right now it is:

> Build phase 3.5 (`pathogen_detection` and `clinicaltrials_search`) is DONE, completing the seven-tool roster. Closed 2026-08-08 after a judge round and an adversary round that found the judge round's own fix had introduced two new critical regressions, both closed and live re-verified. Next: build phase 3.4 (citation trust extended to Layers 2 and 3, the two-tier risk gate, data freshness and conflict resolution), now unblocked since Section 25's dependency on 2.2 and 3.1 through 3.5 is fully merged.

Full detail on what PR #23 (build phase 3.1's re-review debt) fixed, the two things deliberately left as open product decisions rather than fixed unilaterally (F-3.1-41, F-3.1-42), and three new minor follow-ups filed by the final reviewer (F-3.1-50, F-3.1-51, plus one already-tracked as F-3.1-46), is `tracker/phase_3.1.md`'s Findings table, current as of 2026-08-07. Full detail on the F-2.1-C15 fix, including the bypass a fresh-context review found in its own first version before merge and the second review that confirmed the fix, is `tracker/fix_c15_generation_bound.md`.

### Step 3: how a phase runs across sessions

`/bossman` runs stages 1 to 11 and stops only at the phase boundary. The provider split cuts across those stages and cannot change inside a running session. Those two facts collide, so a budget-split phase is three sessions, not one:

| Session | Launch | Stages | Tell it |
|---------|--------|--------|---------|
| 1 | `claude` | 1 to 5 | "open the phase, stop once the premise gate is written and failing" |
| 2 | `claude-build` | 6 to 7 | "work the tickets, stop at the judge" |
| 3 | `claude` | 8 to 11 | "judge, adversary, gates, open the pull request" |

Bossman does not stop at stage boundaries on its own, so each session needs its stop condition stated in the prompt.

The simpler default, and the right one while subscription budget is healthy: run the whole phase in one session on `claude`. The three-session split exists to rescue a week that would otherwise be lost, not as a daily routine. Reach for it when the limit is close, not before. In one line: use `claude` until it stops working, then use `claude-build`.

## State now

NEXT ACTION, the single line "Start here" step 2 refers to. Keep it current: whoever finishes a stage updates this line before ending the session, because it is what the next session reads first.

> Build phase 3.5 (`pathogen_detection` and `clinicaltrials_search`) is DONE, completing the seven-tool roster. Closed 2026-08-08 after a judge round and an adversary round that found the judge round's own fix had introduced two new critical regressions, both closed and live re-verified. Next: build phase 3.4 (citation trust extended to Layers 2 and 3, the two-tier risk gate, data freshness and conflict resolution), now unblocked since Section 25's dependency on 2.2 and 3.1 through 3.5 is fully merged.

Build phase 3.1 merged as PR #22 (superseded by PR #23) on 2026-08-05 without the adversarial pass over its own fix round, which was the stated pre-merge condition. That gap closed across three re-review rounds, all 2026-08-07: a first re-review found the merged commit FAIL (11 of 26 findings closed clean, 15 reopened, 9 new defects including two critical), a fix round closed nearly all of it, a second re-review of THAT fix round found one more critical soundness gap (alias-matching in gene resolution could silently return a confidently WRONG gene, not just fail to resolve) plus a scattering of smaller issues, and a FOURTH reviewer, dispatched specifically because every fix so far had only been checked in the same session that wrote it, independently re-verified the whole branch fresh against live NCBI and returned APPROVE. Merged as PR #23. Full account: `tracker/phase_3.1.md`'s Findings table, including the "Final independent review" section at the bottom.

Two things were deliberately left open rather than fixed, both genuine product decisions, not bugs: whether the stopword list should exclude entries that are themselves real gene symbols (F-3.1-41), and what happens when a gene is mentioned in lowercase (F-3.1-42). Three more minor, non-blocking findings from the final review are carried to before `ncbi_efetch` gets wired into `act_node` (F-3.1-50, F-3.1-51, and F-3.1-46 already tracked).

F-2.1-C15's generation half, the finding where a generated query took the graph server down for every user, closed on `fix/c15-generation-bound` the same day: `validate_cypher` now rejects any generated Cypher carrying a variable-length relationship pattern (`[:orthologous_to*]` or similar) before execution, the mechanism behind the original OOM. The existing `_MEMORY_GUARD_SQL` session-level mitigation is unchanged. This fix's own first version, sliced from the existing relationship-hop regex, was itself found bypassable by a fresh-context adversarial review before merge: a nested bracket (a list-valued property) alongside the variable-length spec defeated it, the same non-nesting-regex defect class already fixed once in this file for node patterns (F-2.1-A9) and never generalized to relationship hops. Rebuilt as a standalone, wildcard-free pattern matched directly against the quote-masked query string, independent of the hop regex entirely. A second independent review confirmed the bypass closed, found no new one, checked for ReDoS (none), and found one narrow, non-blocking gap against full Cypher grammar unreachable by this system's actual generation, documented rather than fixed. F-2.2-01 (a separate, lower-severity generation flake, roughly 1 run in 10) was deliberately left open rather than folded into the same branch, per the ticket's own allowed alternative. Full account: `tracker/fix_c15_generation_bound.md`.

Eleven build phases are done, all eleven merged into `main`. The first six complete the Step 6.1 prototype group; 3.0 through 3.5 are the first five Step 6.3 v1 phases:

| Phase | Delivered | PR |
|-------|-----------|-----|
| 1.0 | FastAPI skeleton, the typed event contract, Pydantic boundary validation | #5 |
| 1.1 | Auth service, the PostgreSQL user-data schema | #6 |
| 2.0 | Real LangGraph agent loop, the three-tier harness | #9 |
| 1.2 | React shell, SSE streaming, chat UI wired end to end | #12 |
| 2.1 | cypher_query over Layer 1, first live graph access | #15 |
| 2.2 | Deterministic cite-or-refuse, Layer 1 provenance, the first trust signal | #18 |
| 3.0 | The full Section 10 guardrail, replacing the passthrough stub | #19 |
| 3.1 | ncbi_efetch, the first Layer 2 tool: seven actions across three API families, live gene-symbol resolution replacing the one-entry hardcoded table | Merged as PR #22 on 2026-08-05, PR #23 on 2026-08-07 |
| 3.2 | ncbi_dbsnp, the second Layer 2 tool: Variation Services normalization plus dbSNP ESummary clinical and population data, six review passes | #25 |
| 3.3 | pubtator_annotate and litvar2_lookup, the two Layer 3 enrichment tools, ten review rounds | #26 |
| 3.5 | pathogen_detection and clinicaltrials_search, completing the seven-tool roster. A judge round and an adversary round that found the judge round's own fix had introduced two new critical regressions of the identical shape, both closed and live re-verified | Merged on `phase/3.5-pathogen-clinicaltrials-tools` |

Current counts, stated once here:

- Python tests: 2331 (2220 passed, 110 skipped, 1 xfailed)
- Frontend tests: 120
- Playwright end-to-end tests: 3 (unverifiable in this and the prior session; a webServer-orchestration timeout unrelated to any file either phase touched, confirmed by starting the dev server directly, HTTP 200)
- Premise gate, cypher_query: 9 of 9
- Premise gate, write-step grounding: 11 passed, 1 xfailed by design
- Premise gate, guardrail: 20 of 20
- Premise gate, ncbi_efetch: 19 passed, 1 skipped (tunnel)
- Premise gate, ncbi_dbsnp: 8 of 8, live, no tunnel-gated skip
- Premise gate, pubtator_annotate + litvar2_lookup: 12 of 12, live, no tunnel-gated skip
- Premise gate, pathogen_detection: 5 of 5, live, no tunnel-gated skip
- Premise gate, clinicaltrials_search: 3 of 3, live, no tunnel-gated skip
- Decisions logged: 235
- Learnings entries: 59, plus a retrospective

Build phase 3.5, `pathogen_detection` and `clinicaltrials_search`, closed 2026-08-08 on `phase/3.5-pathogen-clinicaltrials-tools`, completing the seven-tool roster (see "Build phase 3.5, done" below). Next in the build order is build phase 3.4, citation trust extended to Layers 2 and 3: Section 25's dependency graph named it as depending on 2.2 and 3.1 through 3.5, all of which are now merged, so 3.4 is the phase whose dependencies are finally all satisfied.

The build phase 3.1 tool surface is complete and its findings are settled: 40 of 42 numbered findings closed, F-3.1-04 carried to T-3.1-28 (the answer-path half: Act-step wiring, Layer 2 citation, trust gate), and exactly two left open on genuine product decisions, F-3.1-41 and F-3.1-42, detailed in `tracker/phase_3.1.md`.

Step 6.2 moved on 2026-08-03. It now runs AFTER the 3.x tool phases rather than between 2.2 and 3.0, because its own written reasoning names 3.x as the code its security scan most exists for, and because reconciling the frozen documents after the tool phases is better input than reconciling before them. Its security scan is separately PAUSED INDEFINITELY on cost, with one condition that turns it back on: exposure. First contact with a real user, a deploy, or a public URL triggers it, whichever comes first.

Per-phase detail lives in `tracker/phase_N.M.md`. Phase narrative lives in `requirements/Plan.md`'s Revision history. Phase status and the flags that gate a phase live in `tracker/BOARD.md`.

One exception to the one-owner convention, stated rather than left to be discovered. The Open items table below is NOT a copy of `tracker/BOARD.md`. Measured 2026-08-04: of its 28 tracked identifiers, 14 also appear on the board and 14 appear nowhere else in the repository. So the table is the full forward backlog by owner and is the sole record for half its rows, while the board carries the subset that blocks a specific phase from closing. Where an item appears in both, the board's "Resolve before" column is authoritative.

That split is a known wart rather than a design: the board is the incomplete one. Folding the 14 orphans into it would break the renderer's invariant that every phase's flag count matches the Open flags table, so it is a deliberate task and not a tidy-up. Until then, do not delete a row here on the assumption the board already has it.

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

## Read before opening the next phase

In this order:

1. `tracker/phase_3.5.md` in full, most importantly its "Judge round" and "Adversary round" sections. The load-bearing lesson build phase 3.4 must not repeat: a fix for a discard-real-data defect can itself reintroduce the identical defect one call downstream, and only live re-verification against a real repro case (not the mocked unit suite, which stayed green through two real regressions) catches it. Build phase 3.4 touches provenance and the trust gate directly, the same risk class.
2. `requirements/Technical_specification.md` Section 9 (the provenance type's four added fields for Layer 2/3), Section 7 (layer authority, freshness, and conflict resolution, already partly implemented per `production-standards.md`'s "Layer authority, freshness, and degradation gate"), and Section 25's own line for build phase 3.4: provenance extended to Layers 2 and 3, the two-tier risk gate (standard cite-or-refuse versus a higher-stakes substantiation-and-triangulation gate), data freshness and conflict resolution.
3. The two carried spec-versus-reality gaps most directly relevant to this phase: Section 8.2's matching rule (open item below, whether the substring-mention check the prototype uses actually proves a clause is TRUE about a cited value, not just that it mentions it) and F-2.2-A-05 (the flagship gene-disease claim classifying `low` risk since a `Disease` endpoint row is indistinguishable from an identifier lookup at the current boundary; this phase's two-tier risk gate is exactly where that gets a real fix).
4. `LEARNINGS.md`, filtered to the trust-gate, provenance, and fix-regression entries, now including the 2026-08-08 rows from build phase 3.5 (the worktree-dispatch-before-commit gap, the model-id-guard collision, and the discard-real-data-one-layer-downstream retrospective).
5. `docs/build/Build_velocity_post_mortem.md`, for the measured account of what the build process costs.

## Build phase 3.0, done

Merged as PR #19 on 2026-08-04, in one session, after one judge round and one adversary round.

What changed, stated against what was there before: `guardrail_node` previously made a throwaway Guard-tier call, discarded the response, and emitted a hardcoded `passed=True, category="ok"` for every query. It now runs Section 10.1's pipeline: the cheap non-LLM pre-filter (10.2), boundary validation closed to spec (10.3), Guard-tier classification of injection AND off-topic (10.4), and the forbidden-type and read-only screen (10.5).

Release gate outcome:

| Gate | Result |
|------|--------|
| Premise gate | 20 passed, 0 failed, re-run after every fix round |
| Python suite | 1261 passed, 62 skipped, 1 xfailed |
| `ruff check src/` | Clean |
| Guardrail unit tests | 148 across 6 files |
| Judge round 1 | FAIL, 2 confirmed defects, both fixed |
| Adversary round 1 | 8 findings, 4 acted on |
| Doc drift | 0 stale, 0 structural |

The premise gate has TWO ARMS, and that design decision is the phase's most transferable output. A guardrail has no safe direction of failure: `return refuse` scores one hundred percent on every attack test ever written and destroys the product. So nine of its eighteen cases are legitimate questions that must be ADMITTED, anchored on the v1 must-pass moat questions, including three collision traps where a real biomedical question shares a word with a block rule.

Three defects are worth carrying forward as patterns rather than as fixed bugs:

- The judge returned FAIL with all 34 acceptance criteria individually passing. `"What is the capital of the USA?"` was fully admitted, because the pre-filter's deliberately over-broad symbol pattern was excused by a code comment claiming the classifier would refuse it, and the classifier judged only injection. A deliberate weakness justified by "another layer covers it" is a claim about a DIFFERENT module and must be verified there. It is the F-2.1-J5-01 pattern, committed by an agent that had cited F-2.1-J5-01 by name an hour earlier.
- The adversary found four third-person clinical questions passing every layer. `"Should this patient be started on tamoxifen given her BRCA1 status?"` is not obfuscated. The pre-filter keyed on first person, the forbidden screen on literals, the classifier on injection, and nothing owned advice about a third party. A composition defect, invisible to 148 per-layer unit tests.
- The first allowlist refused the flagship question, because it carried `disease` and the question said `diseases`. Fixed by stemming the input rather than enumerating plurals, which is the allowlist-over-blocklist lesson already recorded on 2026-08-03.

Two tickets did not land and are carried, both on `tracker/BOARD.md` with dated positions: T-3.0-07 (clearing the F-2.1-J4-02 xfail needs the graph tunnel, which cannot be opened from this environment) and T-3.0-08 (F-2.1-C15's generation half, untouched, now dated to immediately after 3.1 merges).

## Build phase 3.1, done

Merged as PR #22 on 2026-08-05, then closed out fully via PR #23 on 2026-08-07 after its outstanding re-review debt was paid off. The answer-path half (Act-step wiring, Layer 2 citation, trust gate) is carried to T-3.1-28 by the product owner's decision.

What shipped: the `ncbi_efetch` tool, seven actions across three API families. E-utilities body-inspecting actions (search, summary, fetch, link), Datasets v2 gene/genome reports (status-coded), PubChem PUG REST property lookup (status-coded), and a five-step dbVar/ClinVar coordinate-overlap procedure with live-verified chromosome normalization. Live gene-symbol resolution via NCBI Datasets v2 and ESearch, replacing the one-entry hardcoded table.

PR #22 merged without the adversarial pass over its own fix round, the stated pre-merge condition, a recorded product-owner decision. PR #23 is that gap closed, across three re-review rounds run 2026-08-07:

| Round | Result |
|-------|--------|
| 1: six fresh-context reviewers, one per file cluster plus an adversary | FAIL. 11 of 26 findings closed clean, 15 reopened, 9 new defects including two critical (gene-symbol resolution completely broken; a field-tag fix using invalid Entrez syntax) |
| Fix round: six parallel builders in isolated worktrees | Closed nearly all of round 1's findings. Integrating their branches surfaced two cross-file seams no single builder could see alone |
| 2: three more fresh-context reviewers, live against NCBI | Found a genuine soundness gap neither round caught: NCBI's `[sym]` tag and the Datasets symbol endpoint both match on gene aliases, so an "unambiguous" match could silently return a confidently WRONG gene. Also a pre-existing bug that left one round-1 critical fix unreachable in production, a second URL-encoding gap, and a regression in round 2's own wait-budget fix. All fixed same-day |
| Final: one more fresh-context reviewer, dispatched specifically to avoid trusting same-session self-verification | APPROVE. Live re-confirmed both critical fixes and the alias-matching fix, re-ran the full gate suite independently, confirmed no test assertion was weakened, spot-checked 10 closed findings. Three new minor non-blocking findings filed. Merged as commit `97aec83` |

Final release gate, as measured for PR #23: 1798 Python tests (1715 passed, 82 skipped, 1 xfailed), `ruff check src/ tests/` at the same 4 pre-existing errors this branch found and confirmed unrelated, doc drift clean, premise gate 19 passed / 1 skipped (tunnel-gated case 16). Full per-finding detail, all 42 numbered findings, and the final reviewer's evidence: `tracker/phase_3.1.md`.

Transferable lessons for the remaining tool phases:
- Capture fixtures from live responses, never author them from a reading of the docs. Two of round 1's criticals were hidden by fixtures hand-written from documentation, which tested the author's belief rather than the interface; the same pattern reappeared inside a FIX round's own new test fixtures during round 2.
- A tool that talks to a live external API needs an adversary who probes the actual API, not just a judge who reads the code. Every critical, in both the original phase and its fix round, came from the gap between what the API actually returns and what someone believed it returns.
- A same-session self-check is not an independent review, however thorough. Measured 3-for-3 this same day: the original merge, the six-builder fix round, and two of the lead's own individual patches each had a real defect only a fresh pass caught. Budget for the fresh pass, every time, not just once per phase.

## Build phase 3.2, done

Closed 2026-08-08 on `phase/3.2-ncbi-dbsnp`, merged as PR #25, after six full review passes: a blocking premise gate written and watched failing first, an adversary round, a judge round (FAIL), a fix round, an independent fresh-context re-review of that fix round, and a second fix round.

What shipped: the `ncbi_dbsnp` tool, variant normalization and dbSNP record retrieval over two sequential API families, NCBI Variation Services (primary, canonical SPDI normalization) and dbSNP ESummary via E-utilities (secondary, clinical and population fields). A new `variation` rate-limit family (~1 req/s, its own pool, separate from `eutils`) landed in `tools/ncbi_transport.py`. Registered into the tool schema and the stable prompt prefix, `TOOL_REGISTRY_VERSION` bumped v2 to v3 (now `cypher_query`, `ncbi_dbsnp`, `ncbi_efetch`). As with 3.1, whether the tool is dispatched as an answer-bearing tool from `act_node` is the same open product-owner scope decision carried to T-3.1-28; this phase delivers the tool itself, not the wiring.

Pre-build live probing against Variation Services and dbSNP ESummary, before any fixture was written, surfaced two findings at design time rather than at review time: F-3.2-01 (`global_mafs[].freq` is a compound string, `"A=0.027356/137"`, not separate fields) and F-3.2-02 (`clinical_significance` and `fxn_class` are comma-separated strings in raw ESummary, not arrays). Both closed in the tool's first version, pinned by the premise gate.

| Round | Result |
|-------|--------|
| Premise gate, written first | 8 failed, 0 passed, every failure `ModuleNotFoundError` (the correct direction, no tool code existed yet) |
| Adversary, live against real NCBI endpoints | 14 findings, 2 critical: `_cap()` silently truncated over-length values and shipped them as `status: "ok"` (a dropped clinical term, a wrong-length variant), and a bare numeric rsid (`query_type: "rsid"`) returned a confident, cited, unrelated variant, since every integer is valid input to `refsnp/{id}` |
| Judge, FAIL | Independently reproduced both criticals live, plus 6 new findings: the premise gate's own coverage statement omitted the two gaps that mattered most (`goal-contracts.md`'s coverage-declaration discipline), and `ClassificationResult` carried no HTTP status field, so a 429 and a 404 were indistinguishable downstream |
| Fix round 1 | All 5 confirmed-blocking findings closed: refuse-not-truncate over silent truncation, an `rs`-prefix shape requirement at the schema layer (closes the bare-numeric-rsid gap before any network call), an `allele_role` label on population frequencies, HTTP status threaded locally into `ncbi_dbsnp.py`'s error messages |
| Independent fresh-context re-review | 2 new findings inside the fix round's own code: the refuse-not-truncate policy refused roughly 10.4 percent of real clinically-cited variants outright, since two standard ClinVar vocabulary terms (`conflicting-interpretations-of-pathogenicity`, 44 chars; `no-classifications-from-unflagged-records`, 41 chars) exceed the locked spec's 40-char item cap; and a genuine deterministic input error (a reference-sequence mismatch, itself a 5xx) was told to the agent as "retry, may be transient," the exact opposite of the truth |
| Fix round 2 | Both closed. The truncation fix changed from whole-call refusal to field-level withholding (`fields_withheld`), naming what was dropped rather than blocking the whole record; `spdi_canonical` stays whole-call refusal, the one field without which there is no variant identity to attach anything else to. The 5xx message now distinguishes a deterministic, permanent input rejection from a genuinely transient one |

Final gates, lead-verified independently a third time: full suite 1830 passed, 90 skipped, 1 xfailed (net +29 from the phase's 1801 baseline at judge round 1), the live `ncbi_dbsnp` premise gate, 8 of 8, no tunnel-gated skip (unlike `ncbi_efetch`'s), `ruff check` clean on every file this phase touches. Every finding this phase's review found was real; zero rejected across two full review rounds. Full per-finding detail, all 16 adversary findings and 6 judge findings, and the ledger close: `tracker/phase_3.2.md`.

Three spec-versus-reality gaps carried to Step 6.2, none fixed unilaterally: Section 25's build-order line for this phase names a dbVar two-step coordinate-overlap sub-tool that already shipped in build phase 3.1 as `tools/ncbi_coordinate_overlap.py`; Section 6.3 names `spdi/{spdi}/canonical_representative` as the SPDI normalization endpoint, live-confirmed broken server-side (HTTP 500 on every well-formed input tried, including NCBI's own documented example), substituted with the live-working `/spdi/{spdi}/contextual`, unverified beyond not crashing on malformed input since the premise gate's `spdi` coverage is error-path only; and the locked `clinical_significance` 40-char item cap itself, too tight for real, standard ClinVar vocabulary.

Transferable lessons, extending 3.1's list: pre-build live probing before any fixture is written catches a defect class (compound-string fields, comma-joined arrays) that a fixture authored from documentation cannot, and a gate's own "not exercised" coverage statement can itself be incomplete in exactly the direction that turns out to matter most, which is why stating coverage is not the same as stating it correctly.

## Build phase 3.3, done

Closed 2026-08-08 on `phase/3.3-enrichment-tools`, merged as PR #26, after ten review rounds: a blocking premise gate written and watched failing first (12 failed, 0 passed, every failure `ModuleNotFoundError`), a judge round (FAIL, 6 findings), a fix round, an independent fresh-context re-review of that fix round (FAIL, found a real regression the fix round introduced), a second fix round, an adversary round against the live APIs (13 findings, 1 critical, 6 major), a third fix round, a fourth fix round closing several findings that had initially been left as documented product decisions but turned out on reconsideration to be addressable without one (a citation for `entity_lookup`, a real dbSNP citation over LitVar2's own unverifiable client-rendered UI, and disclosure parity between the two sibling tools), an independent re-review of that fourth round (FAIL, found a real regression: a multi-match result citing only its first, unrelated match as if it covered the whole answer, plus a vacuous regression test), and a fifth fix round closing both. Every round's findings, closures, and carried-open dispositions are in `tracker/phase_3.3.md`'s Findings table; this section is the narrative, not the record.

What shipped: `pubtator_annotate` (PubTator3: entity normalization for free text, entity annotation on publications) and `litvar2_lookup` (LitVar2: variant-to-literature evidence), the first two Layer 3 enrichment tools and the first tools whose retrieved content is genuinely untrusted external text rather than a structured API record. Two new rate-limit families (`"pubtator"`, `"litvar2"`, 5 req/s provisional throttle each) landed in `tools/ncbi_transport.py`, alongside a shared `{"detail": ...}` error-message branch both tools' live error bodies use. Registered into the tool schema and the stable prompt prefix, `TOOL_REGISTRY_VERSION` bumped v3 to v4 (now `cypher_query`, `litvar2_lookup`, `ncbi_dbsnp`, `ncbi_efetch`, `pubtator_annotate`, alphabetical). As with 3.1 and 3.2, whether either tool is dispatched as an answer-bearing tool from `act_node` is the same open product-owner scope decision carried to T-3.1-28; this phase delivers the tools themselves, not the wiring.

Pre-build live probing (before any fixture was written) found three findings at design time: F-3.3-01 (PubTator3 silently drops nonexistent PMIDs from a mixed batch under `status: "ok"`, closed with an additive `pmids_not_found` field), F-3.3-02 (a third, undocumented PubTator3 error shape, a bare JSON array of strings, on an empty query; closed with `minLength: 1` at the schema layer), and F-3.3-03 (`litvar2_lookup`'s locked `clinical_significance` item cap, `maxLength: 30`, too tight for real ClinVar vocabulary, the same class of finding phase 3.2 made for `ncbi_dbsnp`'s cap; closed with withhold-not-truncate and an additive `fields_withheld` field, the same precedent `ncbi_dbsnp.py` set).

| Round | Result |
|-------|--------|
| Judge round 1 | FAIL. Two majors, both inside the F-3.3-03 fix path, both with zero test coverage: `fields_withheld` had no pre-construction count cap against the schema's own `max_length=20`, so more than 20 withholding notes crashed a successful call into `status: "error"` (F-3.3-J-01); `_variant_search` returned a fabricated `status: "ok"` with an empty `variant_matches` when a non-empty API body yielded zero parseable matches, the exact shape the phase premise forbids (F-3.3-J-02). Plus a minor index bug (F-3.3-J-03) and a gate-coverage gap (F-3.3-J-05), both fixed; two genuine product-owner decisions surfaced rather than fixed (F-3.3-J-04, a disclosure-policy asymmetry between the two sibling tools; F-3.3-J-06, `litvar2_lookup`'s citation pointing at a search UI rather than a per-record page, spec-bound) |
| Fix round 1 | Closed J-01, J-02, J-03, J-05, with new regression tests for each |
| Independent re-review of fix round 1 | FAIL. Found the fix round's own F-3.3-J-02 closure had introduced a real regression (F-3.3-RR-01, major): the new `status: "empty"` guard discarded the `fields_withheld` disclosure notes already computed for the excluded rows, so a wholly-excluded response became byte-identical to a genuine no-match, and the same commit had removed the one test that would have caught it. Also filed a minor, deliberately-unfixed gap (F-3.3-RR-02: the guard is count-based, not content-based) |
| Fix round 2 | Closed RR-01 by routing the pre-existing disclosure notes through the `empty` path instead of discarding them, and restored the removed test assertion. RR-02 left open and documented, judged too risky to touch a second time on a guard that had already regressed once |
| Adversary round, live against real PubTator3 and LitVar2 | 13 findings, 1 critical: both tools silently discarded the upstream API's own relevance signal (a `match` field on every autocomplete row), so a bare number (`query="334"`) or a common word (`query="the"`) returned confidently cited but wholly unrelated data under `status: "ok"` (F-3.3-A-01/02/03). Six more majors: `pmids_not_found` diffed raw strings, not identities, so a leading-zero PMID could be reported missing while its data was simultaneously returned (F-3.3-A-04); F-3.3-02's own fix had a gap, `pmids=[]` still reached the live API (F-3.3-A-06); a content-free fallback error message (F-3.3-A-07); `error` not documented as untrusted content, though already capped (F-3.3-A-08); `entity_lookup` ships no citation at all, spec-bound (F-3.3-A-05). Six minors, mostly documented rather than fixed |
| Fix round 3 | Closed A-01/A-02/A-03 together (an additive, optional `matched_on` field disclosing the raw upstream signal, deliberately disclosure-only, no auto-refusal heuristic built), A-04 (PMID identity normalized before the diff), A-06 (`min_length=1` on `pmids`), A-07 (the generic-fallback short-circuit fixed), A-08 and A-09 (documentation-only). Left A-05, A-10, A-11, A-12, A-13 open and documented, each per its own reachability or scope-decision reasoning |

Final gates, lead-verified independently: full suite 2037 passed, 102 skipped, 1 xfailed, 0 failed (2140 total, after the fourth and fifth fix rounds added coverage); the live combined premise gate, 12 of 12, no tunnel-gated skip; `ruff check` clean on every file this phase touched (the whole-repo `ruff check .` found 16 pre-existing errors, all in files this phase never touched, confirmed via `git log main..HEAD`). Two entries added to LEARNINGS.md by hand after `tracker/check_learnings_coverage.py 3.3` returned a false "nothing to cover": the script only recognizes a narrative `### F-x:` block with a `Status:` line, and this phase's judge and adversary findings live in table rows, a parsing gap now flagged on `tracker/BOARD.md` rather than silently trusted. One check could not be completed in this session: the Playwright end-to-end suite's webServer orchestration timed out waiting for the mock backend, though the backend itself starts and answers `/health` with 200 when run directly; a pre-existing environment quirk unrelated to any file this phase touched, not a code defect.

Full per-finding detail, every judge, re-review, adversary, and fix-round finding with file:line citations: `tracker/phase_3.3.md`.

## Build phase 3.5, done

Closed 2026-08-08 on `phase/3.5-pathogen-clinicaltrials-tools`, completing the seven-tool roster: `pathogen_detection` (bulk isolate, cluster, and AMR-genotype access over the NCBI Pathogen Detection FTP snapshot tree, Section 6.6) and `clinicaltrials_search` (the disease-to-trials path over ClinicalTrials.gov API v2, Section 6.7). A new `"clinicaltrials"` rate-limit family landed in `tools/ncbi_transport.py`; a new streaming-only FTP transport module, `tools/pathogen_ftp_transport.py`, was built for the pathogen tool, since bulk FTP retrieval shares no HTTP-status-coded convention with any prior tool. Registered into the tool schema and the stable prompt prefix, `TOOL_REGISTRY_VERSION` bumped v4 to v5 (now all seven tools, alphabetical). As with every prior tool phase, whether either tool is dispatched as an answer-bearing tool from `act_node` is the same open product-owner scope decision carried to T-3.1-28; this phase delivers the tools themselves, not the wiring.

Pre-build live probing found the phase's own binding constraint before any tool code existed: the Salmonella `SNP_distances.tsv` snapshot file measured roughly 411 GB, three orders of magnitude past a normal bulk TSV, ruling out a full download and forcing a wall-clock-bounded streamed scan instead (decision logged in DECISIONS.md, 2026-08-08).

A dispatch-ordering gap cost a real fix-and-reconcile pass, now recorded in `LEARNINGS.md`: two worktree-isolated builders were dispatched before the lead's own shared prerequisites (the transport module, both premise gates) were committed to the phase branch, so neither builder's worktree could see them. One builder read outside its own worktree to work around it; the other correctly refused to fabricate the missing dependency and flagged every resulting assumption instead. The lead reconciled both against the real, now-committed files and live data after the fact.

| Round | Result |
|-------|--------|
| Judge round | FAIL. One critical: the streaming transport's early-exit logic assumed a filter key is always unique per row, so a shared cluster id stopped the scan after its first matching row and reported an incomplete 4-member cluster as a complete 2-member one. Plus three majors (an unbounded 120-second wait on an optional enrichment step, three of four network read sites reporting a routine snapshot rotation as an unclassified tool defect, stale module docstrings still describing the dispatch-ordering accident as the shipped state) and two minors |
| Fix round 1 | All findings closed, lead-verified with a live premise gate pass, 8 of 8 |
| Adversary round, live against real NCBI/ClinicalTrials.gov endpoints | 15 findings, TWO NEW criticals, both regressions the judge round's own fix introduced, both coexisting with the green judge verdict and the passing premise gate: `cluster_snp_neighbors` could no longer ever return a successful result at all (the fix's own early-exit removal had no fallback, so a cutoff scan always discarded what it had already found); `clinicaltrials_search` pagination errored on every second page, since ClinicalTrials.gov omits its total-count field from every paginated response regardless of what the first fix assumed |
| Fix round 2 | Both criticals closed, plus 3 more majors and 2 minors. Live re-verified against the adversary's own exact repro case |
| Live re-verification | Found the cluster_snp_neighbors fix incomplete: an upstream scan step was consuming the entire shared deadline, starving its own mandatory follow-up read of any budget one call downstream, so the tool still returned an empty result even after the first half of the fix landed |
| Fix round 2b | Closed by reserving a fixed slice of the shared budget for the mandatory follow-up read, regardless of how long the upstream scan runs. Live re-verified a second time: exact match to the adversary's own hand-computed ground truth |

Two majors and five moderate-or-minor adversary findings were deliberately carried open rather than fixed this round, each with its own named reason in `tracker/phase_3.5.md`: a query-syntax-parsing risk (`query_cond` is parsed as an Essie expression, so a term containing `NOT` can silently invert a search), an undisclosed weak-match shape reproducing phase 3.3's own finding on a different tool, a status value overloaded for two different meanings, a spec-locked `overall_status` enum narrower than the live API's real values, and others.

Final gates, lead-verified independently: full suite 2331 Python tests (2220 passed, 110 skipped, 1 xfailed, up from the phase's 2140 baseline), both live premise gates re-confirmed multiple times across both fix rounds (pathogen_detection 5 of 5, clinicaltrials_search 3 of 3, no tunnel-gated skip on either), `ruff check` clean on every file this phase touched. Frontend suite unaffected (no frontend files touched this phase); Playwright's webServer orchestration hit the same pre-existing, already-documented timeout from build phase 3.3, confirmed unrelated by starting the dev server directly (HTTP 200).

Full per-finding detail, every judge, adversary, and fix-round finding with file:line citations: `tracker/phase_3.5.md`.

The transferable lesson, the sharpest one this phase produced: a fix for a discard-real-data defect is exactly the kind of change most likely to reintroduce the identical defect one layer over, since the fixer's attention is on the one call site the finding named, not on every other call site sharing the same resource-exhaustion shape. Only live re-verification against the adversary's own repro case, re-run after every round of changes, caught both regressions here; a fully green mocked test suite caught neither.

## What build phase 3.4 delivers

From Section 25:

> Provenance extended to Layer 2 and 3 (the four added fields), the two-tier risk gate (standard cite-or-refuse versus the higher-stakes substantiation-and-triangulation gate), data freshness and conflict resolution

Depends on 2.2, 3.1, 3.2, 3.3, 3.5, all merged. The last prerequisite phase before the delivery-surface and observability build phases (4.0 onward). Two open items below are directly this phase's job to resolve, not carry further: Section 8.2's matching rule (whether the substring-mention check the prototype uses proves a clause is TRUE about a cited value, not just that it mentions it) and F-2.2-A-05 (the flagship gene-disease claim classifying `low` risk since a `Disease` endpoint row is indistinguishable from an identifier lookup at the current boundary, exactly what a real two-tier risk gate should fix). Read `tracker/phase_3.5.md`'s transferable lesson before opening this phase: a fix touching the trust or provenance path deserves live re-verification against a real repro case after every round, not just a green mocked suite, since this phase's whole subject is the mechanism that decides whether an answer is trustworthy enough to show.

## What Step 6.2 delivers, later

Runs after the 3.x tool phases, not next. From `requirements/Plan.md` Step 6.2, which is the authoritative list. Shape of it:

- Reconcile the PRD, technical specification and strategic memo against what the prototype taught. This is the one planned spec update before those three lock at v1.
- Reconcile the evaluation playbook, which is a living document rather than frozen.
- Sweep the accumulated new-intake folder, the one scheduled review point since Phase 4 locked.
- Carry build phase 2.1's premise-gate change into the tech spec, since Section 25 could not gain a ticket mid-build.
- Carry build phase 2.2's four grounding findings, including whether Section 8.2's matching rule survives contact with the spec as written.
- Decide whether Section 23's offline gate can be claimed at all before Layers 2 and 3 exist.
- Weigh the build-velocity post-mortem's recommendations.
- The whole-repository security scan is PAUSED INDEFINITELY on cost, and is no longer a prerequisite for Step 6.3. Exposure is the one thing that turns it back on.

## Open items

One decision below is still waiting on the product owner: whether `security/` stays gitignored. Still ignored today (`.gitignore:50`). This decides whether the Step 6.2 scan results are ever committed.

| Item | Description | Owner |
|------|-------------|-------|
| F-3.1-41: stopword list vs. real gene symbols | Product decision, not a bug. Detailed in `tracker/phase_3.1.md` | Whenever the product owner decides |
| F-3.1-42: lowercase gene mentions fall through silently | Product decision, not a bug. Detailed in `tracker/phase_3.1.md` | Whenever the product owner decides |
| F-3.1-50, F-3.1-51, F-3.1-46: minor gaps in code `act_node` cannot reach yet | Filed by the final independent review on PR #23. None live-exploitable until `ncbi_efetch` is wired into `act_node` | Before `ncbi_efetch` is wired into `act_node` (3.2 or later) |
| F-2.2-T-01-residual | A declarative injected as a comma-spliced clause inside a single wh-question still licenses its own words. Needs clause-level rather than sentence-level filtering. Pinned by a strict xfail | Step 6.2 |
| F-2.2-A-05 | The flagship gene-disease claim classifies `low` risk, since a `Disease` endpoint row is byte-identical to an identifier-lookup row at `risk_tier_for`'s boundary. Needs the traversed edge label plumbed through `Finding` and `SynthFinding`. Guarded against a naive widen | Step 6.2 |
| Section 8.2 matching rule | The substring branch answers whether a clause MENTIONS the cited value, never whether it is TRUE about it. The prototype closes this with two checks the spec does not describe | Step 6.2 |
| Section 23 offline gate | Its v1 must-pass questions need tools that arrive in build phases 3.1 to 3.5, so the full gate is not runnable yet | Step 6.2 |
| `release-workflow` dispatch gap | Marked mandatory in `bossman-mode.md`, 0 of 6 real dispatches. An ownerless requirement by this repo's own `attack-the-constraint` standard | Step 6.2 |
| Whole-repository security scan | No build-phase code has ever been scanned. One scan predates phase 1.0 | Step 6.2 |
| F-2.1-02 | Section 6.1 documents a parameter mechanism that cannot work; the same wrong claim also sits in `docs/ncbi/Tool_implementation_mechanics.md` and `.claude/rules/production-examples.md` | Step 6.2 |
| F-2.1-01 | The spec says 10 concept labels, the live graph has 11 (the eleventh is `NamedThing`) | Step 6.2 |
| F-2.1-16 | `budget_for_step` diverges from Section 19.1's per-query-class shape, approved but unreconciled | Step 6.2 |
| Env var name divergence | Section 24 names `PER_USER_DAILY_CAP_USD`; the code uses `PER_USER_DAILY_QUERY_CAP`, since it holds a query count, not dollars | Step 6.2 |
| F-2.2-01 | Generation intermittently emits Cypher with no parentheses around node patterns, the graph rejects it, and nothing retries. Roughly 1 run in 10, last measured at build phase 2.2's open. Deliberately NOT fixed on `fix/c15-generation-bound`: the ticket's own acceptance criteria allowed either a retry or recording it as still open, and a retry would touch `cypher_query.py`'s error-handling path in the same review pass as a critical safety fix, which `tracker/fix_c15_generation_bound.md` argues against. Cannot be re-measured live from this environment (same tunnel constraint as T-3.0-07) | Step 6.2, or whenever the live graph tunnel is next reachable |
| F-2.1-J4-02, prompt injection | The guardrail now refuses the injected-instruction shape at admission, verified by 3.0's own premise gate. The `xfail` marker itself is NOT cleared: doing so needs 2.1's gate run five consecutive times against the live graph, and the SSH tunnel cannot be opened from this environment (the Layer-7 proxy cannot tunnel raw SSH, and `block-bash-delete.sh` blocks `ssh` as an execution wrapper). Roughly ten minutes of work whenever the tunnel is reachable | T-3.0-07, environment-gated, not phase-gated |
| F-3.0-01 | Section 10.5 requires refusing a write-seeking request and names no `GuardPayload.category` for it. `off_topic` is used and the real explanation lives only in the reason string. Needs either a new enum member (additive, v1-legal) or a spec amendment | Step 6.2 |
| ADV-03, ADV-06, ADV-07 | Three guardrail defense-in-depth gaps where the Guard-tier classifier remains the covering layer: non-Latin-script injection phrases are invisible to the pre-filter's literal phrase list, the write-verb list has gaps, and `classifier.build_messages` does not escape a `</query>` in the payload. Re-homed 2026-08-04 from "the next round", which was never scheduled | 6.1 |
| ADV-02-residual | A non-English question written in pure ASCII with no cognate and no identifier is still refused as off-topic by the pre-filter. Measured: "Welche Krankheiten sind mit dem Gen assoziiert?" A keyword allowlist cannot do language detection, and per-language vocabulary is the infinite-blocklist trap. Mitigated: the classifier now judges off-topic, and the pre-filter abstains on any non-ASCII letter or on a query containing no English function word | 6.1, with the other guardrail hardening |
| F-2.1-07 | Gene symbol resolution beyond a one-entry seed table, needs the Layer 2 NCBI lookup. Also the real fix for build phase 2.2's symbol-versus-CURIE false reject | 3.1 |
| F-2.1-B10 | Same cause as F-2.1-07; an unresolvable symbol errors rather than refuses | 3.1 |
| PubTator3 relations endpoint | Path and fields still not live-verified as of build phase 3.3's close; `pubtator_annotate` has no `mode` for it, deferred to a fast-follow addition once verified | Step 6.2, or a fast-follow ticket once verified |
| F-3.3-J-04: disclosure-policy asymmetry | `pubtator_annotate` withholds an over-cap field silently (`None`); `litvar2_lookup`, built the same phase, discloses every withholding via `fields_withheld`. Product decision, not a bug. Detailed in `tracker/phase_3.3.md` | Whenever the product owner decides |
| F-3.3-J-06: litvar2_lookup citation quality | The single top-level `source_url` cites a search UI parameterized by the caller's own query, not a record page; the 50 shipped PMIDs carry no per-PMID citation. Spec-bound (Section 6.5 provides one top-level field only) | Step 6.2 |
| F-3.3-A-05: entity_lookup has no citation | `pubtator_annotate`'s `entity_lookup` mode ships no `source_url` at all, spec-bound (Section 6.4's entity item schema names no such field), the sharpest of this phase's carried provenance gaps against CLAUDE.md's "Citations: non-negotiable" | Step 6.2 |
| F-3.3-RR-02: litvar2 empty-guard is count-based, not content-based | A row that parses as a dict but carries no identity (`_id`, `rsid` both absent) still ships as an all-`None` match under `status: "ok"`. Not reachable on live data today; deliberately not fixed a second time on a guard that already regressed once (F-3.3-RR-01) | Whenever live data actually produces this shape |
| F-3.3-A-10: non-rsid litvar_id source_url fallback | Cites a raw internal identifier as a human search term when the id doesn't match the `litvar@rs...##` shape; live-reachable (1 of 5 rows for `query="334"`) unlike most of this module's fallbacks | Whenever the product owner decides |
| F-3.3-A-11: cross-tool id-shape mismatch | `pubtator_annotate`'s `db_id` for a `litvar`-sourced entity and `litvar2_lookup`'s expected `litvar_id` are shaped differently; a plan-tier model could pass one tool's output into the other's input and get a 400. Not reachable until `act_node` wiring (T-3.1-28) | T-3.1-28, when either tool is wired into `act_node` |
| F-3.3-A-12: undisclosed annotation/variant_matches truncation | `_MAX_ANNOTATIONS` and `_MAX_VARIANT_MATCHES` cap silently, with no companion total field, unlike `pmids`'s honest `total_pmids`. Not reachable on live data sampled this phase (max observed: 26 of 100, 5 of 10) | Whenever live data actually produces this shape |
| F-3.3-A-13: asymmetric batch-failure disposition | One malformed (non-numeric) PMID fails an `annotate_publications` batch closed with no partial result, while a numeric-but-nonexistent PMID in the same position preserves the rest of the batch (F-3.3-01's own disposition). Undocumented asymmetry, safe direction (refuses, does not fabricate) | Whenever the product owner decides |
| F-3.5-A-03: clinicaltrials_search query syntax risk | `query_cond` is parsed as an Essie expression, not a literal phrase, so a real clinical term containing `NOT` silently returns the exact inverse of what was asked, `status: "ok"`, confidently cited. Live-proven arithmetic (`Carcinoma` 27,619 minus `Carcinoma Otherwise Specified` 31 equals `Carcinoma NOT Otherwise Specified` 27,588). Needs either escaping caller text or disclosing the parsing risk in the schema | Step 6.2 or a future fix round |
| F-3.5-A-07: clinicaltrials_search weak-match shape | The phase 3.3 weak-match shape (F-3.3-A-01/02/03) reproduces here undisclosed: `query_cond="5"`/`"the"`/`"a"` all return confident, wholly generic citations, and the tool never sends `sort=@relevance`. Unlike phase 3.3's fix, ClinicalTrials.gov's `/studies` endpoint does not appear to return a per-result relevance score to disclose the same way; a real fix needs a result-ordering decision, not just a disclosure field | Step 6.2 or a future fix round |
| F-3.5-A-09: pathogen_detection empty overloaded | `status: "empty"` still means both "genuinely absent" and "the wall clock ran out", distinguishable only via the free-text `error` field. Partially mitigated by the cluster_snp_neighbors fix (a cutoff that found real matches now returns `ok`, not `empty`), but the two remaining cases have no distinct machine-readable signal. A schema-level fix is a locked-schema change | Step 6.2 |
| F-3.5-A-10: pathogen_detection dead cluster_list read | `_cluster_snp_neighbors`'s `cluster_list.tsv` membership check is unconditionally overwritten before use once the SNP scan's own results are known, so its only surviving effect is an existence check while consuming real time from the already budget-starved shared deadline | Whenever the product owner decides |
| F-3.5-A-11: pathogen_detection latent distance-column fallback | `_SNP_DISTANCES_DISTANCE_COLUMN_CANDIDATES`'s fallback to `delta_positions_unambiguous` is a genuinely different metric, not a synonym, and live sampling shows the two routinely disagree. Not observed firing on ~9,400 sampled rows; documented as a defense-in-depth-only risk | Whenever live data actually produces this shape |
| F-3.5-A-12: clinicaltrials_search overall_status enum gap | The locked 6-value input enum (Section 6.7 line 1378) is narrower than the live API's 12 real values (`WITHDRAWN`, `SUSPENDED`, `ENROLLING_BY_INVITATION`, and others), so a caller filtering on a value the API itself returned in a result gets a `ValidationError`. Same class as phase 3.2's carried Section 6.3 gaps | Step 6.2 |
| F-3.5-A-14: clinicaltrials_search punctuation error message | An unbalanced-punctuation `query_cond` (a stray closing paren) is correctly classified as a permanent HTTP 400 rejection, but the message gives no hint that punctuation is the likely cause | Whenever the product owner decides |
| F-2.2-06 | A truncated answer discloses the cut but not its scale on a listing query, since `total_available` is None for that shape. Upstream of the Write step | 3.x, whichever phase touches `cypher_query`'s totals |
| F-2.1-A5-05 | `mentioned_in` from BRCA1 costs 27 seconds forward plus the full budget reversed, despite being indexed, anchored, and LIMIT 25. Described, deliberately not reproduced | 3.x |
| F-06 | 2 of 6 model calls per query bypass the stable prompt prefix, a cost inefficiency, not a correctness defect. The Write step's own call is not one of them as of 2.2 | 4.0 |
| F-1.2-01 | The run registry never evicts a completed or abandoned run | 4.0 |
| F-1.2-02 | An abandoned client SSE connection does not halt the server-side task | 4.0 |
| F-1.2-03 | The per-run event queue is single-consumer | 4.0 |
| F-2.0-04 | Nothing writes `interactions` rows, so both daily cost caps read zero | 4.6 |
| F-2.0-10 | `trace_id` is client-supplied and never server-overwritten | 4.6 |
| Golden fixture domain sign-off | Nobody is named to verify the clinical and human-variation expected answers | 5.1 |
| F-1.2-04 | Signup's 409 response undermines login's anti-enumeration guarantee. Pair with F-1.1-10, same defect class in the same endpoint | 6.1 |
| Python lockfile | Every backend dependency floats on `>=`, including security-critical ones | 6.1 |
| Stand up CI | No `.github/workflows/` exists; every gate every phase has passed was run by hand | 6.1 |
| Fix `pip install .` | Fails outright on a `package-dir` mapping error, pre-existing | 6.1 |

Unowned, needing an explicit decision rather than an assumed phase:

- F-1.1-10, F-1.1-11's `User-Agent` half, and F-1.1-18: deferred from build phase 1.1 to 1.2, and 1.2's own ticket list never touched any of the three.
- Auth-path logging: RFC 6819 family revocation still fires silently. Scheduled for build phase 1.2, did not happen, needs a new home.

## Handover

If a different agent takes over, read the "Running this project with a different agent" section in `CLAUDE.md`, which `AGENTS.md` mirrors. Short version: the file artifacts and the model tiering port cleanly, skills and rules port as content but not as invocation, and the four security hooks do not port at all. They are the only structural enforcement in this repo, so substituting them is the first handover step.

One operational note that cost real time on 2026-08-03 and is not obvious from any other file: this machine's network dropped three times in one session, killing two premise-gate runs and three review agents, and every failure they produced looked like a code defect at first glance. Before diagnosing any model-dependent failure, check reachability with `curl -s -o /dev/null -w "%{http_code}" --max-time 15 https://openrouter.ai/api/v1/models`. An outage shows every premise-gate failure carrying `source='guardrail'`, the first model call in the loop, with an empty narrative and no citations, so nothing reaches synthesis at all. A genuine Write-step defect reaches synthesis and fails later.

Last updated: 2026-08-08.
