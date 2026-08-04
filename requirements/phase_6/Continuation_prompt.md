# Phase 6 continuation prompt

Phase 6 is the build. Read this file at the start of any session that continues build work.

## Table of contents

- [State now](#state-now)
- [Read before opening the next phase](#read-before-opening-the-next-phase)
- [Build phase 3.0, done](#build-phase-30-done)
- [What build phase 3.1 delivers, and where it already stands](#what-build-phase-31-delivers-and-where-it-already-stands)
- [What Step 6.2 delivers, later](#what-step-62-delivers-later)
- [Open items](#open-items)
- [Handover](#handover)

## State now

Seven build phases are done and merged into `main`. The first six complete the Step 6.1 prototype group; 3.0 is the first Step 6.3 v1 phase:

| Phase | Delivered | PR |
|-------|-----------|-----|
| 1.0 | FastAPI skeleton, the typed event contract, Pydantic boundary validation | #5 |
| 1.1 | Auth service, the PostgreSQL user-data schema | #6 |
| 2.0 | Real LangGraph agent loop, the three-tier harness | #9 |
| 1.2 | React shell, SSE streaming, chat UI wired end to end | #12 |
| 2.1 | cypher_query over Layer 1, first live graph access | #15 |
| 2.2 | Deterministic cite-or-refuse, Layer 1 provenance, the first trust signal | #18 |
| 3.0 | The full Section 10 guardrail, replacing the passthrough stub | #19 |

Current counts, stated once here:

- Python tests: 1324
- Frontend tests: 120
- Playwright end-to-end tests: 3
- Premise gate, cypher_query: 9 of 9
- Premise gate, write-step grounding: 11 passed, 1 xfailed by design
- Premise gate, guardrail: 20 of 20
- Decisions logged: 207
- Learnings entries: 48, plus a retrospective

Next is build phase 3.1, `ncbi_efetch`, the first Layer 2 tool. It depends on 2.0 and 3.0, both merged. It is ALREADY OPEN on branch `phase/3.1-ncbi-efetch` at stage 3: twelve tickets are decomposed in `tracker/phase_3.1.md` and no tool code exists. Stage 5, the blocking premise gate, has not started.

Step 6.2 moved on 2026-08-03. It now runs AFTER the 3.x tool phases rather than between 2.2 and 3.0, because its own written reasoning names 3.x as the code its security scan most exists for, and because reconciling the frozen documents after the tool phases is better input than reconciling before them. Its security scan is separately PAUSED INDEFINITELY on cost, with one condition that turns it back on: exposure. First contact with a real user, a deploy, or a public URL triggers it, whichever comes first.

Per-phase detail lives in `tracker/phase_N.M.md`. Phase narrative lives in `requirements/Plan.md`'s Revision history. Status and open flags live in `tracker/BOARD.md`. This file points at those, it does not copy them.

## Read before opening the next phase

In this order:

1. `tracker/phase_3.1.md`. The phase is already open and decomposed, so this is the current state, not a starting point to re-derive. It leads with the phase's scale for a reason, and with a recommended build order that front-loads the gene-symbol resolution.
2. `requirements/Technical_specification.md` Section 6.2, the `ncbi_efetch` specification, plus Section 21.1 for the rate limits. Section 25 for the build order.
3. `docs/ncbi/Tool_implementation_mechanics.md`, the `ncbi_efetch` trap list. The load-bearing one: E-utilities returns HTTP 200 for a genuinely empty result AND for several error classes, so every E-utilities action decides its status from the response BODY, never the HTTP status. Datasets v2 and PubChem are the exact opposite and branch on status. Both conventions live on the same tool.
4. `LEARNINGS.md`, filtered to the tool-phase and model-generated-output entries. `docs/build/Build_workflow_cadence.md` stage 5's blocking premise gate applies to every tool phase from 3.1 to 3.5.
5. `docs/build/Build_velocity_post_mortem.md`, for the measured account of what the build process costs. Note its 2026-08-04 correction: the pre-flight check it recommends covers the product's model provider only and does NOT cover agent dispatch, which is the more expensive of the two to lose.

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

## What build phase 3.1 delivers, and where it already stands

Branch: `phase/3.1-ncbi-efetch`, already cut. Depends on 2.0 and 3.0, both merged. From Section 25:

> `ncbi_efetch` (E-utilities for PubMed, ClinVar, OMIM; Datasets API v2 for Gene, Genome, Orthologs, Taxonomy)

Current state: stage 3 complete. Twelve tickets decomposed in `tracker/phase_3.1.md`, branch cut, NO tool code written. Stage 5, the blocking premise gate, has not started.

Why this phase matters more than its position in the order suggests: it owns finding F-2.1-07. `_KNOWN_GENE_SYMBOL_CURIES` (`core/graph.py:839`) holds exactly one entry, `BRCA1`, so "What diseases are linked to TP53?" resolves nothing and answers nothing today. That is the single thing standing between this repo and a prototype that can be shown to a person, and `tracker/phase_3.1.md`'s recommended build order front-loads it deliberately.

Read `tracker/phase_3.1.md` before touching anything. It leads with the phase's scale, which is wider than 2.1 on every axis: seven actions, three API families, fourteen databases accepted by `search`, eight with a verified per-database field set, and two error conventions that are exact opposites. 2.1 was one tool, one action, one host, and it took four days and five review rounds.

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
| F-2.2-01 | Generation intermittently emits Cypher with no parentheses around node patterns, the graph rejects it, and nothing retries. Roughly 1 run in 10. Re-homed 2026-08-04: rides with F-2.1-C15 rather than a tool phase, since 3.1 to 3.5 never open `cypher_generation.py` | The `fix/c15-generation-bound` branch, immediately after 3.1 merges |
| F-2.1-J4-02, prompt injection | The guardrail now refuses the injected-instruction shape at admission, verified by 3.0's own premise gate. The `xfail` marker itself is NOT cleared: doing so needs 2.1's gate run five consecutive times against the live graph, and the SSH tunnel cannot be opened from this environment (the Layer-7 proxy cannot tunnel raw SSH, and `block-bash-delete.sh` blocks `ssh` as an execution wrapper). Roughly ten minutes of work whenever the tunnel is reachable | T-3.0-07, environment-gated, not phase-gated |
| F-2.1-C15, generation half | Nothing stops generation producing an unbounded traversal in the first place. Attempted by a builder during 3.0 which inverted its contract, implemented a validator rule with no analysis, and left a rule that rejects `[:orthologous_to {weight: 2*3}]` as unbounded. Reverted; the attempt is preserved as a diff. DATED 2026-08-04 by the product owner rather than left as an open slot, because this is the finding where a generated query took the graph server down for every user | The `fix/c15-generation-bound` branch, immediately after 3.1 merges |
| F-3.0-01 | Section 10.5 requires refusing a write-seeking request and names no `GuardPayload.category` for it. `off_topic` is used and the real explanation lives only in the reason string. Needs either a new enum member (additive, v1-legal) or a spec amendment | Step 6.2 |
| ADV-03, ADV-06, ADV-07 | Three guardrail defense-in-depth gaps where the Guard-tier classifier remains the covering layer: non-Latin-script injection phrases are invisible to the pre-filter's literal phrase list, the write-verb list has gaps, and `classifier.build_messages` does not escape a `</query>` in the payload. Re-homed 2026-08-04 from "the next round", which was never scheduled | 6.1 |
| ADV-02-residual | A non-English question written in pure ASCII with no cognate and no identifier is still refused as off-topic by the pre-filter. Measured: "Welche Krankheiten sind mit dem Gen assoziiert?" A keyword allowlist cannot do language detection, and per-language vocabulary is the infinite-blocklist trap. Mitigated: the classifier now judges off-topic, and the pre-filter abstains on any non-ASCII letter or on a query containing no English function word | 6.1, with the other guardrail hardening |
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

Last updated: 2026-08-04.
