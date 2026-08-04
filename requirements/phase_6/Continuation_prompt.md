# Phase 6 continuation prompt

Phase 6 is the build. Read this file at the start of any session that continues build work.

## Table of contents

- [State now](#state-now)
- [Read before opening Step 6.2](#read-before-opening-step-62)
- [Build phase 2.2, done](#build-phase-22-done)
- [What Step 6.2 delivers](#what-step-62-delivers)
- [Open items](#open-items)
- [Handover](#handover)

## State now

Six build phases are done and merged into `main`, which completes the Step 6.1 prototype group:

| Phase | Delivered | PR |
|-------|-----------|-----|
| 1.0 | FastAPI skeleton, the typed event contract, Pydantic boundary validation | #5 |
| 1.1 | Auth service, the PostgreSQL user-data schema | #6 |
| 2.0 | Real LangGraph agent loop, the three-tier harness | #9 |
| 1.2 | React shell, SSE streaming, chat UI wired end to end | #12 |
| 2.1 | cypher_query over Layer 1, first live graph access | #15 |
| 2.2 | Deterministic cite-or-refuse, Layer 1 provenance, the first trust signal | #18 |

Current counts, stated once here:

- Python tests: 1154
- Frontend tests: 120
- Playwright end-to-end tests: 3
- Premise gate, cypher_query: 9 of 9
- Premise gate, write-step grounding: 11 passed, 1 xfailed by design
- Decisions logged: 198
- Learnings entries: 43, plus a retrospective

Next is NOT a build phase. Step 6.2, the one reconciliation pause, sits between 2.2 and 3.0 and is a hard prerequisite for any Step 6.3 work. Do not open build phase 3.0 before it closes.

Per-phase detail lives in `tracker/phase_N.M.md`. Phase narrative lives in `requirements/Plan.md`'s Revision history. Status and open flags live in `tracker/BOARD.md`. This file points at those, it does not copy them.

## Read before opening Step 6.2

In this order:

1. `requirements/Plan.md` Step 6.2. It is the authoritative list of what the reconciliation covers, and build phase 2.2 added six items to it.
2. `LEARNINGS.md`, all of it rather than a filtered slice. Plan.md names it as the input to this reconciliation: the docs get updated from a captured record rather than memory.
3. `tracker/phase_2.2.md`'s close-status section, for the two findings that phase deliberately left open.
4. `docs/build/Build_velocity_post_mortem.md`, for the measured account of what the build process costs and which parts earn it.

## Build phase 2.2, done

Merged as PR #18 on 2026-08-03, in one session, after three independent review rounds.

What changed, stated against what was there before: `write_node` previously made a synth-tier model call with a bare user question and discarded the response entirely. No narrative reached any surface, and `trust_outcome` was derived from whether a fetched row happened to carry a `source_url`. The Write step now produces grounded, cited prose in which a citation means a specific sentence was checked against a specific field value, rather than that a row was fetched.

Release gate outcome:

| Gate | Result |
|------|--------|
| Premise gate | 11 passed, 1 xfailed by design, 0 failed |
| Eval gate, citation-synthesizer component | Passed, 12 of 12 runs. Across both runs of the day, 23 of 24 clean |
| Python suite | 1154 passed, 1 xfailed |
| Frontend | 120 passed, 15 files |
| `ruff check src/` | Clean |
| Doc drift | 0 stale, 0 structural |

Rounds 1 and 2 each returned a failing verdict, and each round's worst defect was in the previous round's fix, which is the pattern `LEARNINGS.md`'s build phase 2.1 retrospective predicts. What they caught, all closed and mutation-tested: a negation grounding as support for the record it denies, a framing prefix smuggling uncited fabrications including a treatment-discontinuation instruction, question-seeding licensing its own affirmation, an ASCII-only tokenizer that made every non-Latin script invisible to both gates, and non-renderable values shipping as facts.

`eval-harness` ran for the first time in this project. It ran as the citation-synthesizer component gate rather than the full v1 must-pass gate, and said so explicitly: that gate's questions span PubMed, ClinVar, GTR, MedGen, SRA, BioProject and ClinicalTrials, none of which have a tool until build phases 3.1 to 3.5.

## What Step 6.2 delivers

From `requirements/Plan.md` Step 6.2, which is the authoritative list. Shape of it:

- Reconcile the PRD, technical specification and strategic memo against what the prototype taught. This is the one planned spec update before those three lock at v1.
- Reconcile the evaluation playbook, which is a living document rather than frozen.
- Sweep the accumulated new-intake folder, the one scheduled review point since Phase 4 locked.
- Carry build phase 2.1's premise-gate change into the tech spec, since Section 25 could not gain a ticket mid-build.
- Carry build phase 2.2's four grounding findings, including whether Section 8.2's matching rule survives contact with the spec as written.
- Decide whether Section 23's offline gate can be claimed at all before Layers 2 and 3 exist.
- Weigh the build-velocity post-mortem's recommendations.
- Run the whole-repository security scan. A hard prerequisite for starting Step 6.3, and nothing in the build has ever been scanned.

## Open items

One decision below is still waiting on the product owner: whether `security/` stays gitignored. Still ignored today (`.gitignore:50`). This decides whether the Step 6.2 scan results are ever committed.

| Item | Description | Owner |
|------|-------------|-------|
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
| F-2.2-01 | Generation intermittently emits Cypher with no parentheses around node patterns, the graph rejects it, and nothing retries. Roughly 1 run in 10 | 3.0 or 3.1, whichever touches generation first |
| F-2.1-J4-02, prompt injection | Mitigated by delimiting the question, not closed. `xfail(strict=False)`, clearing the marker is part of 3.0's Guardrail definition of done | 3.0 |
| F-2.1-C15, generation half | Nothing yet stops generation from producing an unbounded traversal in the first place | 3.0 |
| F-2.1-07 | Gene symbol resolution beyond a one-entry seed table, needs the Layer 2 NCBI lookup. Also the real fix for build phase 2.2's symbol-versus-CURIE false reject | 3.1 |
| F-2.1-B10 | Same cause as F-2.1-07; an unresolvable symbol errors rather than refuses | 3.1 |
| PubTator3 relations endpoint | Path and fields not yet live-verified | 3.3 |
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

Last updated: 2026-08-03.
