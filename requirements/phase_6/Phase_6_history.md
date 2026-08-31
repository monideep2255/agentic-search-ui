# Build phase history, Phase 6

The finished-phase records that used to sit inside `requirements/phase_6/Continuation_prompt.md`.

They were moved here on 2026-08-30, VERBATIM and byte-identical, because the continuation prompt exists to tell the next session what to do now, and roughly half of it had become a record of what was done weeks ago. The `phase-checkpoint` skill says a superseded section is deleted rather than left below the new one; these were never removed, so fourteen accumulated.

They were MOVED rather than deleted. `requirements/Plan.md`'s revision history covers the same phases at a summary level, but not at this detail: build phase 3.5's section here carries the new `clinicaltrials` rate-limit family, the streaming-only FTP transport module and the `TOOL_REGISTRY_VERSION` bump, none of which the Plan.md entry states. Deleting on the assumption that Plan.md was a superset would have lost them.

Coverage is deliberately uneven, and that is inherited rather than introduced: sections exist for build phases 3.0 through 3.5, 4.0, 4.1, 4.3, 4.4, 4.8, 4.9, 4.10 and Step 6.2, and for nothing after that. Whoever stopped appending simply stopped. For 4.11 onward, `requirements/Plan.md`'s revision history is the record.

Nothing here is current. Read it as history.

## Table of contents

- [Build phase 4.4, done](#build-phase-44-done)
- [Build phase 3.0, done](#build-phase-30-done)
- [Build phase 3.1, done](#build-phase-31-done)
- [Build phase 3.2, done](#build-phase-32-done)
- [Build phase 3.3, done](#build-phase-33-done)
- [Build phase 3.4, done](#build-phase-34-done)
- [Build phase 3.5, done](#build-phase-35-done)
- [Step 6.2, done](#step-62-done)
- [Build phase 4.3, done](#build-phase-43-done)
- [Build phase 4.0, done](#build-phase-40-done)
- [Build phase 4.1, done](#build-phase-41-done)
- [Build phase 4.10, done](#build-phase-410-done)
- [Build phase 4.9, done](#build-phase-49-done)
- [Build phase 4.8, done](#build-phase-48-done)
- [Two more superseded sections, moved 2026-08-30](#two-more-superseded-sections-moved-2026-08-30)
- [The next session starts here](#the-next-session-starts-here)
- [Read before opening the next phase](#read-before-opening-the-next-phase)
- [State now as it stood on 2026-08-31, before the board became the source](#state-now-as-it-stood-on-2026-08-31-before-the-board-became-the-source)

## Build phase 4.4, done

Merged as PR #51 on 2026-08-19. The fifth of the six delivery surfaces, and the first phase to run under the review cap.

What shipped: a query-scoped subgraph export. Seed CURIEs, bounded hops over Layer 1 through the existing read-only path, writing `nodes.tsv`, `edges.tsv` and a manifest. Not a full-graph snapshot.

Four things it leaves for whoever builds next, in order of how much they cost to learn:

- A STATED BLIND SPOT IS NOT A SAFE ONE. The premise gate passed 6 of 6 while the default invocation returned 500 Articles and zero of the twelve disease edges the gate itself pinned. Five of six cases passed an explicit edge-label list; the default path was tested by nothing, and the gate's coverage statement had named that omission from day one. Test the path a real caller hits first, before the path that is convenient to write.
- CONSTRUCT THE INPUT THAT MAKES YOUR ASSERTION FAIL. The lead's own second gate case passed on first run against code that was provably lying, because it used a single-label list where the two sets it compared cannot diverge by construction. An assertion you cannot make fail is decoration.
- RE-MEASURE A BASELINE, NEVER CARRY IT FORWARD. The recorded suite baseline said 6 known failures; the real figure was 10, and had been wrong for some time. Proving the 10 were pre-existing took one throwaway worktree at the pre-phase commit and about eight minutes, and converted a plausible argument into evidence.
- FIX THE SCHEDULER, NOT THE ORDER. The critical was one shared budget consumed sequentially, so the highest-cardinality label starved twelve others. Reordering the list or special-casing that label would have moved the starvation one position along.

- Two findings carried forward with owners, both on `tracker/BOARD.md`: the console script cannot be verified end to end until `pip install .` is fixed (build phase 6.1, shared with build phase 4.2's `s3`), and the export CLI classifies an input problem by catching `ValueError`, a proxy rather than a declaration, verified latent.

Full record: `tracker/phase_4.4.md`, plus `tracker/phase_4.4_judge_report.md` and `tracker/phase_4.4_adversary_report.md`.

### What build phase 4.3 leaves for whoever opens 4.4

Four things. The first two are the most transferable results this project has produced, and they cost six review rounds and two criticals to learn.

- CHECK THE VALUE, NOT ITS PROVENANCE. Build phase 4.3 shipped the same critical twice, three rounds apart, in the same decision: may the caller see this exception? Each version answered it with a PROXY for safety, the package a class was declared in, then its class family, then the phase the error came from. Each proxy was defeated by the first case its author had not imagined, and two of them returned a live database DSN with credentials. The property that mattered was a fact about the STRING, and all three were merely correlates of it. The fourth attempt checks the text against shapes captured from the installed library. Whenever a check must decide about a value, check the value.
- A REVIEW LOOP NEEDS A MERGE BAR OR IT CANNOT TERMINATE. Five rounds were briefed as "find anything", which on a surface this size always has an answer, so nothing could end the loop. A done-when had been written for the build and never for the review. The phase converged in one round after the product owner set one: a critical or a REACHABLE major blocks, minors and latent findings are tracked with an owner. Write the review's done-when when you write the build's.
- THE MAKER-CHECKER SPLIT APPLIES TO FIXES, NOT ONLY TO REVIEWS. Five of six fix rounds here were run by the lead, who then wrote the tests pinning those fixes, and six of the phase's FOURTEEN vacuous gate arms came from exactly that. The round that finally closed the phase was fixed by a fresh agent with the lead verifying. It closed both blockers, found a second half of one finding nobody had filed, and correctly DISPUTED the review on a third.
- CAPTURE FROM THE INSTALLED LIBRARY, NEVER FROM WHAT YOU EXPECT IT TO SAY. A message allowlist written from belief blunted fifteen ordinary caller errors into a generic literal, missing the real wording by ONE WORD in three places, while the file's own header claimed everything in it had been verified against the installed package. A comment claiming verification is not verification.

Then build phases 4.5 to 4.7, in Section 25's order.

### Carried into 4.4 and beyond

`tracker/phase_4.3.md`'s findings table records a disposition for every finding that phase did not close, and `tracker/BOARD.md` carries the five that remain open as flags. The one worth knowing before touching the GraphQL surface again: the masking layer is BYPASSED for an error that escapes Strawberry's operation context (an unknown fragment spread reaches it), so the premise "every error passes the content rule" is false on a live path. It discloses only the caller's own text today, which is why it did not block, and build phase 6.1 owns it.

The product-decision queue is EMPTY. The eight items cleared on 2026-08-15 stayed cleared, and build phase 4.3 added none.

## Build phase 3.0, done

Merged as PR #19 on 2026-08-04, in one session, after one judge round and one adversary round.

- What changed, stated against what was there before: `guardrail_node` previously made a throwaway Guard-tier call, discarded the response, and emitted a hardcoded `passed=True, category="ok"` for every query.
- It now runs Section 10.1's pipeline: the cheap non-LLM pre-filter (10.2), boundary validation closed to spec (10.3), Guard-tier classification of injection AND off-topic (10.4), and the forbidden-type and read-only screen (10.5).

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

- What shipped: the `ncbi_efetch` tool, seven actions across three API families.
- E-utilities body-inspecting actions (search, summary, fetch, link), Datasets v2 gene/genome reports (status-coded), PubChem PUG REST property lookup (status-coded), and a five-step dbVar/ClinVar coordinate-overlap procedure with live-verified chromosome normalization.
- Live gene-symbol resolution via NCBI Datasets v2 and ESearch, replacing the one-entry hardcoded table.

PR #22 merged without the adversarial pass over its own fix round, the stated pre-merge condition, a recorded product-owner decision. PR #23 is that gap closed, across three re-review rounds run 2026-08-07:

| Round | Result |
|-------|--------|
| 1: six fresh-context reviewers, one per file cluster plus an adversary | FAIL. 11 of 26 findings closed clean, 15 reopened, 9 new defects including two critical (gene-symbol resolution completely broken; a field-tag fix using invalid Entrez syntax) |
| Fix round: six parallel builders in isolated worktrees | Closed nearly all of round 1's findings. Integrating their branches surfaced two cross-file seams no single builder could see alone |
| 2: three more fresh-context reviewers, live against NCBI | Found a genuine soundness gap neither round caught: NCBI's `[sym]` tag and the Datasets symbol endpoint both match on gene aliases, so an "unambiguous" match could silently return a confidently WRONG gene. Also a pre-existing bug that left one round-1 critical fix unreachable in production, a second URL-encoding gap, and a regression in round 2's own wait-budget fix. All fixed same-day |
| Final: one more fresh-context reviewer, dispatched specifically to avoid trusting same-session self-verification | APPROVE. Live re-confirmed both critical fixes and the alias-matching fix, re-ran the full gate suite independently, confirmed no test assertion was weakened, spot-checked 10 closed findings. Three new minor non-blocking findings filed. Merged as commit `97aec83` |

- Final release gate, as measured for PR #23: 1798 Python tests (1715 passed, 82 skipped, 1 xfailed), `ruff check src/ tests/` at the same 4 pre-existing errors this branch found and confirmed unrelated, doc drift clean, premise gate 19 passed / 1 skipped (tunnel-gated case 16).
- Full per-finding detail, all 42 numbered findings, and the final reviewer's evidence: `tracker/phase_3.1.md`.

Transferable lessons for the remaining tool phases:
- Capture fixtures from live responses, never author them from a reading of the docs. Two of round 1's criticals were hidden by fixtures hand-written from documentation, which tested the author's belief rather than the interface; the same pattern reappeared inside a FIX round's own new test fixtures during round 2.
- A tool that talks to a live external API needs an adversary who probes the actual API, not just a judge who reads the code. Every critical, in both the original phase and its fix round, came from the gap between what the API actually returns and what someone believed it returns.
- A same-session self-check is not an independent review, however thorough. Measured 3-for-3 this same day: the original merge, the six-builder fix round, and two of the lead's own individual patches each had a real defect only a fresh pass caught. Budget for the fresh pass, every time, not just once per phase.

## Build phase 3.2, done

Closed 2026-08-08 on `phase/3.2-ncbi-dbsnp`, merged as PR #25, after six full review passes: a blocking premise gate written and watched failing first, an adversary round, a judge round (FAIL), a fix round, an independent fresh-context re-review of that fix round, and a second fix round.

- What shipped: the `ncbi_dbsnp` tool, variant normalization and dbSNP record retrieval over two sequential API families, NCBI Variation Services (primary, canonical SPDI normalization) and dbSNP ESummary via E-utilities (secondary, clinical and population fields).
- A new `variation` rate-limit family (~1 req/s, its own pool, separate from `eutils`) landed in `tools/ncbi_transport.py`.
- Registered into the tool schema and the stable prompt prefix, `TOOL_REGISTRY_VERSION` bumped v2 to v3 (now `cypher_query`, `ncbi_dbsnp`, `ncbi_efetch`).
- As with 3.1, whether the tool is dispatched as an answer-bearing tool from `act_node` is the same open product-owner scope decision carried to T-3.1-28; this phase delivers the tool itself, not the wiring.

Pre-build live probing against Variation Services and dbSNP ESummary, before any fixture was written, surfaced two findings at design time rather than at review time: F-3.2-01 (`global_mafs[].freq` is a compound string, `"A=0.027356/137"`, not separate fields) and F-3.2-02 (`clinical_significance` and `fxn_class` are comma-separated strings in raw ESummary, not arrays). Both closed in the tool's first version, pinned by the premise gate.

| Round | Result |
|-------|--------|
| Premise gate, written first | 8 failed, 0 passed, every failure `ModuleNotFoundError` (the correct direction, no tool code existed yet) |
| Adversary, live against real NCBI endpoints | 14 findings, 2 critical: `_cap()` silently truncated over-length values and shipped them as `status: "ok"` (a dropped clinical term, a wrong-length variant), and a bare numeric rsid (`query_type: "rsid"`) returned a confident, cited, unrelated variant, since every integer is valid input to `refsnp/{id}` |
| Judge, FAIL | Independently reproduced both criticals live, plus 6 new findings: the premise gate's own coverage statement omitted the two gaps that mattered most (`goal-contracts.md`'s coverage-declaration discipline), and `ClassificationResult` carried no HTTP status field, so a 429 and a 404 were indistinguishable downstream |
| Fix round 1 | All 5 confirmed-blocking findings closed: refuse-not-truncate over silent truncation, an `rs`-prefix shape requirement at the schema layer (closes the bare-numeric-rsid gap before any network call), an `allele_role` label on population frequencies, HTTP status threaded locally into `ncbi_dbsnp.py`'s error messages |
| Independent fresh-context re-review | 2 new findings inside the fix round's own code: the refuse-not-truncate policy refused roughly 10.4 percent of real clinically-cited variants outright, since two standard ClinVar vocabulary terms (`conflicting-interpretations-of-pathogenicity`, 44 chars; `no-classifications-from-unflagged-records`, 41 chars) exceed the locked spec's 40-char item cap; and a genuine deterministic input error (a reference-sequence mismatch, itself a 5xx) was told to the agent as "retry, may be transient," the exact opposite of the truth |
| Fix round 2 | Both closed. The truncation fix changed from whole-call refusal to field-level withholding (`fields_withheld`), naming what was dropped rather than blocking the whole record; `spdi_canonical` stays whole-call refusal, the one field without which there is no variant identity to attach anything else to. The 5xx message now distinguishes a deterministic, permanent input rejection from a genuinely transient one |

- Final gates, lead-verified independently a third time: full suite 1830 passed, 90 skipped, 1 xfailed (net +29 from the phase's 1801 baseline at judge round 1), the live `ncbi_dbsnp` premise gate, 8 of 8, no tunnel-gated skip (unlike `ncbi_efetch`'s), `ruff check` clean on every file this phase touches.
- Every finding this phase's review found was real; zero rejected across two full review rounds.
- Full per-finding detail, all 16 adversary findings and 6 judge findings, and the ledger close: `tracker/phase_3.2.md`.

- Three spec-versus-reality gaps carried to Step 6.2, none fixed unilaterally: Section 25's build-order line for this phase names a dbVar two-step coordinate-overlap sub-tool that already shipped in build phase 3.1 as `tools/ncbi_coordinate_overlap.py`; Section 6.3 names `spdi/{spdi}/canonical_representative` as the SPDI normalization endpoint, live-confirmed broken server-side (HTTP 500 on every well-formed input tried, including NCBI's own documented example), substituted with the live-working `/spdi/{spdi}/contextual`, unverified beyond not crashing on malformed input since the premise gate's `spdi` coverage is error-path only; and the locked `clinical_significance` 40-char item cap itself, too tight for real, standard ClinVar vocabulary.

- Transferable lessons, extending 3.1's list: pre-build live probing before any fixture is written catches a defect class (compound-string fields, comma-joined arrays) that a fixture authored from documentation cannot, and a gate's own "not exercised" coverage statement can itself be incomplete in exactly the direction that turns out to matter most, which is why stating coverage is not the same as stating it correctly.

## Build phase 3.3, done

- Closed 2026-08-08 on `phase/3.3-enrichment-tools`, merged as PR #26, after ten review rounds: a blocking premise gate written and watched failing first (12 failed, 0 passed, every failure `ModuleNotFoundError`), a judge round (FAIL, 6 findings), a fix round, an independent fresh-context re-review of that fix round (FAIL, found a real regression the fix round introduced), a second fix round, an adversary round against the live APIs (13 findings, 1 critical, 6 major), a third fix round, a fourth fix round closing several findings that had initially been left as documented product decisions but turned out on reconsideration to be addressable without one (a citation for `entity_lookup`, a real dbSNP citation over LitVar2's own unverifiable client-rendered UI, and disclosure parity between the two sibling tools), an independent re-review of that fourth round (FAIL, found a real regression: a multi-match result citing only its first, unrelated match as if it covered the whole answer, plus a vacuous regression test), and a fifth fix round closing both.
- Every round's findings, closures, and carried-open dispositions are in `tracker/phase_3.3.md`'s Findings table; this section is the narrative, not the record.

- What shipped: `pubtator_annotate` (PubTator3: entity normalization for free text, entity annotation on publications) and `litvar2_lookup` (LitVar2: variant-to-literature evidence), the first two Layer 3 enrichment tools and the first tools whose retrieved content is genuinely untrusted external text rather than a structured API record.
- Two new rate-limit families (`"pubtator"`, `"litvar2"`, 5 req/s provisional throttle each) landed in `tools/ncbi_transport.py`, alongside a shared `{"detail": ...}` error-message branch both tools' live error bodies use.
- Registered into the tool schema and the stable prompt prefix, `TOOL_REGISTRY_VERSION` bumped v3 to v4 (now `cypher_query`, `litvar2_lookup`, `ncbi_dbsnp`, `ncbi_efetch`, `pubtator_annotate`, alphabetical).
- As with 3.1 and 3.2, whether either tool is dispatched as an answer-bearing tool from `act_node` is the same open product-owner scope decision carried to T-3.1-28; this phase delivers the tools themselves, not the wiring.

- Pre-build live probing (before any fixture was written) found three findings at design time: F-3.3-01 (PubTator3 silently drops nonexistent PMIDs from a mixed batch under `status: "ok"`, closed with an additive `pmids_not_found` field), F-3.3-02 (a third, undocumented PubTator3 error shape, a bare JSON array of strings, on an empty query; closed with `minLength: 1` at the schema layer), and F-3.3-03 (`litvar2_lookup`'s locked `clinical_significance` item cap, `maxLength: 30`, too tight for real ClinVar vocabulary, the same class of finding phase 3.2 made for `ncbi_dbsnp`'s cap; closed with withhold-not-truncate and an additive `fields_withheld` field, the same precedent `ncbi_dbsnp.py` set).

| Round | Result |
|-------|--------|
| Judge round 1 | FAIL. Two majors, both inside the F-3.3-03 fix path, both with zero test coverage: `fields_withheld` had no pre-construction count cap against the schema's own `max_length=20`, so more than 20 withholding notes crashed a successful call into `status: "error"` (F-3.3-J-01); `_variant_search` returned a fabricated `status: "ok"` with an empty `variant_matches` when a non-empty API body yielded zero parseable matches, the exact shape the phase premise forbids (F-3.3-J-02). Plus a minor index bug (F-3.3-J-03) and a gate-coverage gap (F-3.3-J-05), both fixed; two genuine product-owner decisions surfaced rather than fixed (F-3.3-J-04, a disclosure-policy asymmetry between the two sibling tools; F-3.3-J-06, `litvar2_lookup`'s citation pointing at a search UI rather than a per-record page, spec-bound) |
| Fix round 1 | Closed J-01, J-02, J-03, J-05, with new regression tests for each |
| Independent re-review of fix round 1 | FAIL. Found the fix round's own F-3.3-J-02 closure had introduced a real regression (F-3.3-RR-01, major): the new `status: "empty"` guard discarded the `fields_withheld` disclosure notes already computed for the excluded rows, so a wholly-excluded response became byte-identical to a genuine no-match, and the same commit had removed the one test that would have caught it. Also filed a minor, deliberately-unfixed gap (F-3.3-RR-02: the guard is count-based, not content-based) |
| Fix round 2 | Closed RR-01 by routing the pre-existing disclosure notes through the `empty` path instead of discarding them, and restored the removed test assertion. RR-02 left open and documented, judged too risky to touch a second time on a guard that had already regressed once |
| Adversary round, live against real PubTator3 and LitVar2 | 13 findings, 1 critical: both tools silently discarded the upstream API's own relevance signal (a `match` field on every autocomplete row), so a bare number (`query="334"`) or a common word (`query="the"`) returned confidently cited but wholly unrelated data under `status: "ok"` (F-3.3-A-01/02/03). Six more majors: `pmids_not_found` diffed raw strings, not identities, so a leading-zero PMID could be reported missing while its data was simultaneously returned (F-3.3-A-04); F-3.3-02's own fix had a gap, `pmids=[]` still reached the live API (F-3.3-A-06); a content-free fallback error message (F-3.3-A-07); `error` not documented as untrusted content, though already capped (F-3.3-A-08); `entity_lookup` ships no citation at all, spec-bound (F-3.3-A-05). Six minors, mostly documented rather than fixed |
| Fix round 3 | Closed A-01/A-02/A-03 together (an additive, optional `matched_on` field disclosing the raw upstream signal, deliberately disclosure-only, no auto-refusal heuristic built), A-04 (PMID identity normalized before the diff), A-06 (`min_length=1` on `pmids`), A-07 (the generic-fallback short-circuit fixed), A-08 and A-09 (documentation-only). Left A-05, A-10, A-11, A-12, A-13 open and documented, each per its own reachability or scope-decision reasoning |

- Final gates, lead-verified independently: full suite 2037 passed, 102 skipped, 1 xfailed, 0 failed (2140 total, after the fourth and fifth fix rounds added coverage); the live combined premise gate, 12 of 12, no tunnel-gated skip; `ruff check` clean on every file this phase touched (the whole-repo `ruff check .` found 16 pre-existing errors, all in files this phase never touched, confirmed via `git log main..HEAD`).
- Two entries added to LEARNINGS.md by hand after `tracker/check_learnings_coverage.py 3.3` returned a false "nothing to cover": the script only recognizes a narrative `### F-x:` block with a `Status:` line, and this phase's judge and adversary findings live in table rows, a parsing gap now flagged on `tracker/BOARD.md` rather than silently trusted.
- One check could not be completed in this session: the Playwright end-to-end suite's webServer orchestration timed out waiting for the mock backend, though the backend itself starts and answers `/health` with 200 when run directly; a pre-existing environment quirk unrelated to any file this phase touched, not a code defect.

Full per-finding detail, every judge, re-review, adversary, and fix-round finding with file:line citations: `tracker/phase_3.3.md`.

## Build phase 3.4, done

Closed 2026-08-10 on `phase/3.4-citation-trust-full`, merged as PR #28, the last of the six Step 6.3 tool-and-trust phases (3.0 through 3.5). Depended on 2.2 and 3.1 through 3.5, all merged before this phase opened.

- What shipped:
  - Section 9.1/9.2 provenance (the four `CitationPayload` fields, `evidence_kind`/`assertion_confidence`/`population_ancestry_context`/`license`) extended to all six Layer 2/3 tools via a shared per-tool default table (`synthesis/provenance_defaults.py`) and one `build_citation`/`build_layer2_citation` function per tool.
  - The F-2.2-A-05 fix (the flagship gene-disease claim now classifies `high` risk via the traversed `gene_associated_with_condition` edge label, read straight off the already-generated Cypher text, not the bare `Disease` node type).
  - T-3.1-28 folded in, wiring `act_node` to dispatch `ncbi_efetch` as a second answer-bearing tool alongside `cypher_query` for a Gene-anchored question, the first dual-layer dispatch this repo has ever run.
  - Section 7.1 (live-wins-for-currency) and Section 7.4 (staleness auto-cross-verify) as `write_node` post-processing.
  - And Section 7.2 (conflict detection), a code-level field comparison that floors a genuine cross-layer disagreement's `trust_outcome` at `flag`.
- Section 7.3's `as_of` wire marker was deliberately scoped out (T-3.4-06, `DECISIONS.md`, 2026-08-09): it needs a new SSE event type, a bigger contract decision than this phase's time budget could safely absorb.

- Ten review rounds before close: a blocking premise gate written first and watched failing (4 of 10 failing on real missing behavior, 6 on `ModuleNotFoundError`, the correct direction), a first judge round (5 of 7 tickets closed clean, 2 held against two new findings), a fix round closing both, a judge confirmation round (all 7 of 7 tickets `done`), an adversary round against the live system (7 findings, 1 critical), a fix round closing the critical and two majors, and a final judge confirmation round verifying that fix round live rather than trusting its own report.

| Round | Result |
|-------|--------|
| Premise gate, written first | 4 of 10 fail on real missing behavior (Layer 2 absent from a dual-layer question, F-2.2-A-05 live-reproduced, `triangulated` stuck at `None`), 6 fail on `ModuleNotFoundError`/`ImportError`, no syntax or fixture error in the gate itself |
| Judge round 1 | 5 of 7 tickets closed `done` outright. Two new findings on the remaining two: F-3.4-J-01 (LEARNINGS.md carried zero entries for a phase that found and fixed four real, time-costly defects, `check_learnings_coverage.py`'s own regex silently missing this file's flat-bullet finding format), F-3.4-J-02 (an arithmetic error in the pass@8 grading docstring, conflating "probability all 8 fail" with "probability all 8 succeed", claiming under 0.002% when the real figure is roughly 10%) |
| Fix round | Both closed: three substantive dated LEARNINGS.md rows added by hand; the docstring, assertion message, and DECISIONS.md corrected to the right figure, an exact, logic-untouched diff |
| Judge round 2 (confirmation) | Independently re-verified rather than trusted: recomputed `0.75**8` by hand, confirmed the LEARNINGS.md rows are substantive, re-ran the live gate (10 of 10, zero regression from the docstring-only edit). All 7 of 7 tickets `done` |
| Adversary round, live against the real system | 7 findings, 1 critical: a two-gene query silently drops the second gene under a confident `answer` outcome, no citation, no disclosure (F-3.4-A-01). 2 majors: a realistic two-hop query shape reopens F-2.2-A-05's own risk-misclassification for the ambiguous-edge case (F-3.4-A-02); the exact-field-name pairing every Section 7 mechanism depends on never fires for this system's own most common dual-layer citation pair, Gene `name` vs `symbol` (F-3.4-A-03). 3 moderate (a premise-gate coverage overclaim, a dormant staleness-note precision gap, a URL-pattern end-anchor gap), 1 informational (an OpenRouter per-call affordability failure that limited this round's own live-testing budget, resolved by a product-owner credit top-up) |
| Fix round | Closed the critical and both majors. F-3.4-A-01: `write_node` now floors `trust_outcome` at `ask` and discloses which named entity went unaddressed, whenever surviving citations cover a strict subset of a multi-entity question's own entities. F-3.4-A-02: a second, independent "ambiguous edges include a high-risk one" signal, closing without ever guessing a specific wrong edge. F-3.4-A-03: one explicit alias table entry (Gene `name` to `symbol`) plus a containment-based compatibility check, closing a false-negative without manufacturing a false conflict on every normal dual-layer answer. A fourth, unfiled defect surfaced and was closed in the same round: the alias fix, once it made field-name pairing reachable in practice, exposed that the pairing had never verified "same subject entity", and could pair two different genes' facts as if they were one |
| Judge round 3 (final confirmation) | Read every changed line by hand, re-ran the full non-live suite and lint independently, live-verified F-3.4-A-02 and F-3.4-A-03 itself since the fix round could not (a shared OpenRouter credit exhaustion blocked the fix round's own live re-run mid-round). Verdict: acceptable to ship. Zero regressions in the full suite or lint |

- Three real defects were found and fixed while live re-verifying the dual-layer dispatch mechanism itself, none caused by a mistake in the dispatch code (each reproduced with `ncbi_efetch` excluded): F-3.4-T05-01 (a "derived" sibling row silently overwrote a real row's traversed edge type on collision), F-3.4-T05-02 (a Layer 2 finding's normal `total_available=None` poisoned a known Layer 1 total), F-3.4-T05-03 (a heuristic tuned for a MedGen ETL leak false-positived on the legitimate 5-character gene symbol "BRCA1").
- A fourth, F-3.4-T05-04, was two things at once: a real, separately-confirmed crash risk (an uncaught `pydantic.ValidationError` on an OMIM-sourced citation URL, fixed) and genuine Synth sampling variance in how reliably the model cites both layers in one narrative (not a code defect; mitigated by grading that one gate case pass@8 rather than on a single run, F-3.4-T05-05).

- Final gates, judge-verified independently: full non-live suite 2406 passed, 66 skipped, 1 xfailed, 3 pre-existing failures (guardrail_node's `step_error` gap, F-3.4-T03-01, confirmed present on the unmodified base commit, not a phase 3.4 regression, carried open), zero new failures from this phase.
- Live premise gate (`test_citation_trust_full_premise.py`), 10 of 10, no tunnel-gated skip.
- `ruff check` clean on every file this phase touched.
- Four items carried open rather than fixed this round, each with its own named reason in `tracker/phase_3.4.md`: F-3.4-T06-01 (Section 7.4's staleness check is real and wired but cannot fire against this graph's current ingest, a System 1/2 gap, not a System 3 defect), F-3.4-A-04 (the premise gate's own coverage claim overclaims a real triangulation verdict it cannot yet produce with only one second origin wired), F-3.4-A-05 (dormant, depends on F-3.4-T06-01), F-3.4-A-06 (a URL-pattern end-anchor gap, not currently exploitable through this phase's own code).
- F-3.4-T03-01, found incidentally and confirmed pre-existing, is build phase 3.0 territory and was not this phase's to fix.

Full per-finding detail, every ticket, judge round, adversary finding, and fix round: `tracker/phase_3.4.md`.

The transferable lesson: a fix round is exactly where a regression hides best, because the fixer's attention is on the finding named, not on every call site sharing the same shape. Both F-3.4-A-01's own investigation (which surfaced a second, unfiled defect in F-3.4-A-03's fix) and the judge's insistence on live-verifying the fix round itself rather than trusting its report caught what a same-session self-check would have missed, the same pattern `tracker/phase_3.5.md` already named for the prior phase.

## Build phase 3.5, done

- Closed 2026-08-08 on `phase/3.5-pathogen-clinicaltrials-tools`, completing the seven-tool roster: `pathogen_detection` (bulk isolate, cluster, and AMR-genotype access over the NCBI Pathogen Detection FTP snapshot tree, Section 6.6) and `clinicaltrials_search` (the disease-to-trials path over ClinicalTrials.gov API v2, Section 6.7).
- A new `"clinicaltrials"` rate-limit family landed in `tools/ncbi_transport.py`; a new streaming-only FTP transport module, `tools/pathogen_ftp_transport.py`, was built for the pathogen tool, since bulk FTP retrieval shares no HTTP-status-coded convention with any prior tool.
- Registered into the tool schema and the stable prompt prefix, `TOOL_REGISTRY_VERSION` bumped v4 to v5 (now all seven tools, alphabetical).
- As with every prior tool phase, whether either tool is dispatched as an answer-bearing tool from `act_node` is the same open product-owner scope decision carried to T-3.1-28; this phase delivers the tools themselves, not the wiring.

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

- Two majors and five moderate-or-minor adversary findings were deliberately carried open rather than fixed this round, each with its own named reason in `tracker/phase_3.5.md`: a query-syntax-parsing risk (`query_cond` is parsed as an Essie expression, so a term containing `NOT` can silently invert a search), an undisclosed weak-match shape reproducing phase 3.3's own finding on a different tool, a status value overloaded for two different meanings, a spec-locked `overall_status` enum narrower than the live API's real values, and others.

- Final gates, lead-verified independently: full suite at the time stood at 2331 Python tests (2220 passed, 110 skipped, 1 xfailed, up from the phase's 2140 baseline), both live premise gates re-confirmed multiple times across both fix rounds (pathogen_detection 5 of 5, clinicaltrials_search 3 of 3, no tunnel-gated skip on either), `ruff check` clean on every file this phase touched.
- Frontend suite unaffected (no frontend files touched this phase); Playwright's webServer orchestration hit the same pre-existing, already-documented timeout from build phase 3.3, confirmed unrelated by starting the dev server directly (HTTP 200).

Full per-finding detail, every judge, adversary, and fix-round finding with file:line citations: `tracker/phase_3.5.md`.

The transferable lesson, the sharpest one this phase produced: a fix for a discard-real-data defect is exactly the kind of change most likely to reintroduce the identical defect one layer over, since the fixer's attention is on the one call site the finding named, not on every other call site sharing the same resource-exhaustion shape. Only live re-verification against the adversary's own repro case, re-run after every round of changes, caught both regressions here; a fully green mocked test suite caught neither.

## Step 6.2, done

Closed 2026-08-10, across eight PRs (#29 through #36) merged to `develop`. Ran immediately after build phase 3.4's merge, per the 2026-08-03 resequencing decision naming the 3.x tool phases as the code this reconciliation most exists for. Measured against `Plan.md`'s own Step 6.2 section, the authoritative list of what it was scoped to deliver:

- Default branch renamed `main` to `develop` (PR #29): every genuine branch reference swept across 8 rule/skill files, README, and Section 24 of the tech spec, `main agent`/`main loop`/`main session` references left untouched.
- PR #30 resolved all 4 grounding findings carried from earlier in the build: Section 8.2's matching rule and F-2.2-05's number-formatting fix absorbed into the tech spec as new steps 5a and 5b; F-2.2-A-05 confirmed already closed previously (the tracker had gone stale saying otherwise, corrected); F-2.2-T-01-residual kept open by explicit product-owner decision, real engineering work, already safely pinned by a strict xfail.
- PR #31 folded an earlier premise-gate cadence change into the tech spec as a new Section 23 subsection, the process change Section 25's locked build order could not gain a ticket for mid-build.
- The two remaining process decisions resolved (PR #32): Section 23's offline gate stays scheduled for build phase 5.1 rather than run early, even though it became runnable for the first time this reconciliation; the `release-workflow` phase-end mandate, measured at 0-of-6 real dispatches, rewritten in `bossman-mode.md` to name the judge round, adversary round, and stage-10 gates as the real requirement.
- Every item explicitly tagged "Step 6.2" as owner in the Open items table below closed (PR #34, 14 items):
  - four pure spec corrections (10 vs 11 concept labels, the broken `%s` parameter-mechanism claim, the two-shape per-step timeout budget, the `PER_USER_DAILY_QUERY_CAP` env var name)
  - plus real fixes spanning a live safety gap (F-3.1-50's unbounded list truncation, live-reachable since build phase 3.4 wired `ncbi_efetch` into `act_node`), a new `write_seeking` guardrail category (F-3.0-01, also catching a second hand-maintained copy of the category set in the frontend that would have silently rejected the event), two Layer 3 citation schema widenings (F-3.3-J-06, F-3.3-A-05), a `pathogen_detection` status split (F-3.5-A-09), and a live-probed 14-value `overall_status` enum widen (F-3.5-A-12, live-confirmed via `GET /api/v2/stats/field/values`, 14 real values against the 12 previously estimated).
- F-3.4-A-06 scheduled as its own dedicated task rather than rushed: the naive one-line fix would have broken every real citation URL.
- The new-intake folder swept (PR #35): 19 notes triaged into `personal-os-work`'s permanent Reference folders via `git mv`, none forcing a locked-document edit. 3 phase-relevant suggestions, MCP server statelessness for build phase 4.1, signal-based feedback-loop review sampling for build phase 4.6, a semantic guardrail layer with no phase yet, got a one-line pointer in the Open items table below rather than only living in the note.
- An informal manual smoke test run against the live system (PR #36): the 7 v1 must-pass moat questions asked directly through the real FastAPI backend, real LLM calls, real NCBI APIs, answers read by hand, deliberately not the formal graded eval-harness gate (that stays deferred to build phase 5.1). The live knowledge graph was unreachable from the session that ran it (the SSH tunnel cannot be opened from a sandboxed coding session; a structural limitation, not a defect), so Layer 1 answers were read as untested-here rather than failed. Surfaced F-2.0-15: `think_node`'s real query classification was never built past its build-phase-2.0 stub (`query_class` hardcoded to `"lookup"`, entity resolution always empty), causing 4 of 7 must-pass questions to refuse outright ("I could not identify that gene," a false-positive gene-symbol guess off database names like GTR, AMR, SRA mentioned in the question) and a 5th to answer near-empty. Filed in `tracker/BOARD.md`'s Open flags table; product-owner decision, 2026-08-10, assigns it to build phase 4.7 as that phase's real deliverable, not just its closest candidate.

- The whole-repository security scan stays PAUSED INDEFINITELY on cost, unchanged by this reconciliation.
- Exposure, a deploy, a public URL, or first contact with a user who is not the product owner, is the only thing that turns it back on.

## Build phase 4.3, done

Merged as PR #48 on 2026-08-17, after SIX independent review rounds. It is the most-reviewed phase in this build, and the reason is worth reading before opening any phase that touches an error path or a security boundary.

What shipped: a GraphQL surface at `/graphql`, served by Strawberry from the same FastAPI process, sharing the REST surface's auth and its tools. Four operations (`ask`, `run`, `citations`, `stopRun`) over the one agent core.

Three scope readings the locked documents did not settle, each recorded before any code was written, since Section 13 names this surface and then explicitly declines to specify it:

- "Shared tools" means through the one core, NOT a resolver per tool. Section 13.2 had already ruled on that exact PRD phrase for MCP: a per-tool passthrough lets a caller bypass cite-or-refuse and the cost caps entirely.
- Registered accounts only, no guest path, matching both existing programmatic surfaces. The guest allowance is an ordering, not a function, and reproducing it on a second surface doubles a surface with a known accepted residual.
- Request/response only. Subscriptions were available, and deliberately not built, so this surface advertises no WebSocket protocol at all.

| Round | Result |
|-------|--------|
| Lead's own mutation sweep | 5 vacuous gate arms found in the lead's own gate, before any reviewer saw it |
| Judge | FAIL. 3 major, 8 minor, plus 5 more vacuous arms. Premise clause C5 (anything dropped is disclosed) NOT MET |
| Adversary | 1 CRITICAL, 13 major, 6 minor. The critical was a working credential-disclosure primitive the lead had rated minor: an exception was trusted because of the PACKAGE its class was declared in, and a crafted class returned a live DSN |
| Re-review of the fix round | FAIL, 5 major. The critical's own fix had silently masked two actionable errors, and its commit message stated a claim about Python inheritance that was false |
| Fifth round | FAIL, 1 CRITICAL. A run that died could report an answer, citations and a healthy trust signal, because the fatal disclosure lived only in a capped list and was evicted. Also: the second disclosure proxy had leaked again |
| Sixth round, the first run against a MERGE BAR | DO-NOT-MERGE, 2 blocking. Both the lead's. Fixed by a fresh agent with the lead verifying, then MERGED |

Final gates:

- 3308 Python tests as measured at this phase's close on 2026-08-17 (3188 passing, the same six live-network-gated cases carried since build phase 4.0). This is a historical figure and does not track the current count
- the GraphQL package alone 206 to 300 tests
- 181 frontend
- ruff clean
- doc drift 0 stale 0 structural

Five findings are carried open with owners, all on `tracker/BOARD.md`. The one to know: the masking layer is bypassed for an error escaping Strawberry's operation context, reachable via an unknown fragment spread, disclosing only the caller's own text. Build phase 6.1 owns it.

Full per-round detail: `tracker/phase_4.3.md`, plus one report per round at `tracker/phase_4.3_judge_report.md`, `_adversary_report.md`, `_rereview_report.md`, `_rereview2_report.md`, `_review5_report.md`, `_review6_report.md`.

## Build phase 4.0, done

Merged to `develop` as PR #39, 2026-08-11, from `phase/4.0-rest-sse-hardening`, now deleted. Depended on 2.2, already merged. Full ticket-level record, every judge and adversary finding with its evidence: `tracker/phase_4.0.md`. This section is a pointer plus current state, not a copy.

- What shipped: `core/run_registry.py` rebuilt with a multi-consumer, `seq`-indexed event log (closing F-1.2-03), lazy eviction past a retention window (F-1.2-01), and cumulative-unwatched-time abandonment cancellation (F-1.2-02, redesigned mid-phase after an adversary found the original timer-reset version bypassable by reconnect churn).
- `adapters/web_sse/app.py`'s `GET /events` gained real resumability (a wire-level SSE `id:` line, strict cursor validation), a new `GET /citations` export endpoint, and operator-mode visibility now derived purely server-side.
- The legacy buffered `POST /query` endpoint is removed.

| Round | Verdict | What it found or confirmed |
| --- | --- | --- |
| Judge 1 | FAIL | 2 blocking: no SSE `id:` line (real resumability was never possible for a standards-conforming client), an unverifiable "failing-first" premise-gate claim. 5 non-blocking |
| Fix round 1 | n/a | All 7 closed |
| Judge 2 | PASS | Independently re-verified all 7 with live probes, not the fix round's own new tests |
| Adversary round | 14 filed | 4 major, 5 moderate, 5 minor, all real and reproduced twice. Two root causes explained 9 of the 14: "watched" meant connected, not delivered (a churn or an idle socket could bypass abandonment), and a cancelled run was treated identically to a completed one everywhere downstream (no terminal event, an undisclosed partial citation export) |
| Fix round 2 | n/a | 8 fixed, judge-confirmed; 2 resolved by documenting them as intentional; 4 carried open with a named owner each |
| Judge 3 | PASS | Independently re-verified all 8 fixes with fresh live probes. Filed one new finding (a CORS `expose_headers` gap making the new disclosure headers unreadable cross-origin) and corrected the lead's own citation of `v1-scope-boundary.md` for the carried findings, which was imprecise |
| Fix round 3 | n/a | CORS gap closed; carried-finding reasoning corrected; all four carries recorded in `tracker/BOARD.md`'s Open flags table with a named owner |
| Judge 4 | PASS | Confirmed the CORS fix live. Filed one tracker-tooling defect (a board status typo blocking `render_board.py`), not shipped code |

Test counts at close:

- Python suite 2517 collected (2397 passing, 113 skipped, 1 xfailed, 6 failed on the same pre-existing live-network-opt-in-gated tests every prior phase has carried, confirmed unrelated by `git diff` showing zero touched lines in that directory)
- this phase's own premise gate file fully green at 26 tests
- frontend 120 of 120
- Playwright blocked by the same pre-existing webServer-orchestration timeout documented since build phase 3.3 (confirmed environmental, not a regression, by starting the dev server directly and getting a real 200)

- Four adversary findings carried open, each with a named owner on `tracker/BOARD.md`'s Open flags table rather than left only in `tracker/phase_4.0.md`, per judge round 3's explicit condition (the F-2.0-15 precedent: a well-reasoned deferral with no owner fell through twelve phases): F-4.0-A-10/A-11 (unbounded run creation, and the O(n) eviction sweep's cost under it) to build phase 6.0; F-4.0-A-12 (the citations export drops the upstream truncation disclosure) to whichever phase next touches `write_node`'s `DonePayload` construction; F-4.0-A-14 (an idle socket suppresses the abandonment check) to a future round revisiting `RunRegistry` abandonment logic.
- One judge finding, F-4.0-J-08 (a now-stale frontend comment about the SSE `id:` field), carried to build phase 4.2 where the client actually starts consuming it.

## Build phase 4.1, done

Merged to `develop` as PR #40, 2026-08-11, from `phase/4.1-mcp-server`, now deleted. Depended on 3.4, already merged; also drew on build phase 4.0, since it wraps the same `RunRegistry`/`run_streaming` core that phase finalized. Full ticket-level record, every judge and adversary finding with its evidence: `tracker/phase_4.1.md`. This section is a pointer plus current state, not a copy.

- What shipped: `adapters/mcp/server.py`, an outbound-only MCP server exposing a single advertised tool, `ask_biomedical_question`.
- The tool folds the same core `run()` loop build phase 4.0 finalized (iterating `RunRegistry.subscribe` to the terminal event) into one JSON result, never a stream: no `think`, `plan`, or `tool_start` event ever reaches the caller, and the internal `token`/`tool_result`/`citation`/`trust_signal` events fold into a final `answer`, `citations`, `trust_signal`, `run_id` shape matching Section 13.2's locked schema exactly.
- Auth reuses the same bearer-JWT decode-then-lookup logic every other surface already uses, extracted into a small shared callable rather than duplicated; a missing, malformed, or invalid token fails before `create_run` is ever called, so no run and no budget is spent.
- `operator_mode` is hard-pinned false for this surface in code, so no MCP response can ever carry a cost field regardless of the authenticated account's allowlist status.
- `list_tools()` advertises exactly one tool; none of the seven internal tools (`cypher_query`, `ncbi_efetch`, `ncbi_dbsnp`, `pubtator_annotate`, `litvar2_lookup`, `pathogen_detection`, `clinicaltrials_search`) is ever separately reachable.
- New dependency: the official `mcp` Python SDK (`mcp>=2.0`), supply-chain checked and product-owner approved before any code (see `tracker/phase_4.1.md`'s pre-build source read).

- The phase premise was amended at judge round 3 to state three guarantees the original eight clauses were silent on, all found necessary by the adversary round: a run that dies on a fatal error or is cancelled never presents its partial text as a complete answer (the top-level `trust_signal` floors to no better than `flag`, never raises); the top-level `trust_signal` never asserts a verdict the run's own events contradict, aggregating claim-scoped signals worst-wins when no answer-scope signal arrived; and the tool call carries its own 240-second wall-clock budget independent of the core it waits on.

| Round | Verdict | What it found or confirmed |
| --- | --- | --- |
| Judge 1 | FAIL | A gate-integrity bug in the premise gate's own leak-detection assertions: two test assertions compared a key name against a list of values, so they could never fail regardless of what the code under test actually did. One blocking, three non-blocking |
| Fix round 1 | n/a | All four closed |
| Judge 2 | PASS | Independently re-confirmed all four fixes |
| Adversary round | 16 filed | 2 critical, 4 major, 4 moderate, 6 minor, against the live mounted app. Both criticals shared one shape: the fold loop asserted a positive trust verdict, a complete grounded low-risk answer, that the run's own events sometimes directly contradicted (a fatal or cancelled run's partial text presented as complete; a silent fallback branch manufacturing `grounded`/`risk_tier` from nothing) |
| Fix round 2 | n/a | 12 closed outright; one closed on its `grounded` half with the `risk_tier` half carried as F-4.1-J3-02; one closed with its underlying `core/graph.py` raw-exception-stringification pattern carried as F-4.1-J3-01; two carried open as genuine product-level calls, F-4.1-A-10 and F-4.1-A-15 |
| Judge 3 | PASS | Fresh-context, independently re-derived both criticals and the two structural surface guarantees (the single-tool surface, the never-cost rule) directly against the code rather than trusting either prior round's report, including live counterfactual mutation testing |

- Test counts at close: Python suite 2565 collected (2445 passing, 113 skipped, 1 xfailed, 6 failed on the same pre-existing live-network-opt-in-gated set every prior phase has carried, confirmed unrelated), this phase's own premise gate file fully green at 48 tests.
- `/verify` READY, `dev-standards` READY with 0 blocking issues, `eval-harness` determined not applicable in full (an outbound protocol adapter over the same already-graded core, reasoning documented in `tracker/phase_4.1.md`).
- Learnings-coverage verified by hand: `check_learnings_coverage.py`'s table-row parsing gap (the same one already flagged for build phase 3.3) means the script cannot see this phase's table-format findings, so its "nothing to cover" result was not trusted.

- Two adversary findings carried open, each with a named owner on `tracker/BOARD.md`'s Open flags table: F-4.1-A-10 (content originating in untrusted third-party sources, a PubMed abstract field reaching `citations[].claim_text` and the narrative `answer` built from it, relays to an MCP caller with no field, wrapper, or flag distinguishing relayed source text from the system's own words; no clean small fix exists, since labelling would need either a new response field or a framing convention no other surface uses, and whether the obligation runs outward when this system becomes somebody else's tool is a product-level call) to whenever the product owner decides, or build phase 6.1's hardening pass, whichever comes first; F-4.1-A-15 (a caller-supplied `session_id` passed straight into `Query` with length validation only, no check that it belongs to the authenticated `User`; harmless today since nothing reads `Query.session_id` yet, becomes a live authorization gap the moment build phase 4.5 or 4.6 wires a consumer) to build phase 4.5 or 4.6, whichever first wires a `Query.session_id` consumer, and before either ships.

The same day, build phase 4.8 (Web UI visual design) was inserted into the build order immediately after this phase, ahead of 4.2 through 4.7 (see "State now" above and `DECISIONS.md`'s 2026-08-11 entries).

## Build phase 4.10, done

Merged as PR #46 on 2026-08-15. The anonymous run path and the server-side guest allowance, split out of build phase 6.0 and pulled ahead of 4.2 to 4.7 by product-owner directive on 2026-08-14.

- What shipped: a signed guest identity whose key is domain-separated from the access-token key; the allowance counted server-side by one conditional UPDATE; run ownership for a caller with no `users` row via a namespaced `owner_id`; migration of a guest's live runs at signup; three bounds on anonymous spend; `snapshot_date` and `entity_name` on `CitationPayload`; F-4.0-A-10 closed; and three false user-visible strings replaced with true ones.

Seven rounds, four of them FAIL. The order matters because each critical was created by the fix for the previous one:

| Round | Worst finding |
|-------|---------------|
| Judge, FAIL | Two premise-gate clauses could not fail. The domain-separation clause forged its token for a UUID with no row, so its asserted 401 came from the unknown-guest path, never from signature rejection |
| Adversary | 40 paid pipelines in 0.25 seconds from a caller with no account. Both pre-existing cost caps are structurally unable to reach a guest, so nothing was behind it |
| Re-review, FAIL | The refund that closed the above removed the only per-identity bound: one token, 200 pipelines, 1.68 seconds, the whole day gone |
| Verification, FAIL | The attempt ceiling that closed THAT was defeated by using 20 identities: 200 pipelines, 1.56 seconds, the same outcome |

The fourth bound is the first one minting does not increase: a source's share of the day, so 20 identities or 200 buy the same 20 runs.

Five lessons, all in `LEARNINGS.md` and all measured rather than argued:

- Every bound keyed on something the caller can mint more of is defeated by minting more. Three rounds proved it before the fourth changed what the bound was keyed on.
- A gate can be green while the property it claims is absent, five distinct ways in one phase: a 401 from the wrong path, a clause masked by a second cap of the same value, a clause hollowed out without being edited, a clause importing the constant it should pin, and a mutation that did not fire.
- A lead's brief can be factually wrong and a builder will implement it faithfully. The phase's worst finding traces to a cost claim asserted without being checked against `core/graph.py`.
- A real accepted risk can be used to wave through a much larger unaccepted one on the strength of the two sounding similar. "Clearing your browser gives five more searches" and "a script mints identities in parallel" differ by 157 paid pipelines per second.
- A control with no safe direction of failure needs both arms. The mint throttle's first version refused the gate's own admit arm, one screen below where that rule is written down.

Full account: `tracker/phase_4.10.md`, and the four review reports beside it.

## Build phase 4.9, done

Merged as PR #44 on 2026-08-14, followed by the design-system pass as PR #45.

- What shipped: the nine fidelity gaps between the running app and the approved prototype, plus the account menu.
- The nav order, the status strip with its outcome word and `Show work` disclosure, a reasoning log shared by the run screen and that disclosure, collapsible sources with a count, each source's layer named in words, citation chips carrying their source identity, the follow-up moved above the rating, the trust pill stating a layer count, and the prototype's account menu.

Four of those nine were found by SCREENSHOTTING the running app beside the prototype in the same four states, which had never been done in this repository before. That comparison also found a live bug in the same pass, F-4.8-P-04, an anonymous visitor being shown the whole stored-searches rail.

- Three review rounds, all three FAIL, and the order they ran in is the point:

| Round | Verdict | Findings | What it caught that the previous one could not |
|-------|---------|----------|-----------------------------------------------|
| Adversary | | 19: 4 critical | Product lies: raw cost figures on screen, trust pills surviving a crash |
| Judge | FAIL | 14: 3 major | The GATE was blind, not the product |
| Re-review of the fix round | FAIL | 14: 5 major | Three regressions the fix round itself introduced |

Three lessons worth carrying, all in `LEARNINGS.md`:

- The judge deleted the sources count badge and the gate stayed green, because `toHaveTextContent("3")` read the whole `<details>` and the fixture's third source id contains a "3". Sixteen of the lead's own mutations had missed it, because the lead chose them where the lead was already looking.
- The fixture was collinear on every axis it asserted, so it graded the shape of the code rather than its behaviour. Rebuilding it honestly immediately exposed two shipped defects it had been structurally incapable of seeing.
- Three of the four critical fixes were themselves wrong, which is the pattern this repository has measured across four consecutive phases.

Two findings need a PRODUCT decision rather than a fix, and are carried: F-4.9-A-09 (this phase's source collapse put the off-host citation warning two disclosures deep, so a security mitigation is now opt-in) and F-4.9-A-08 (a stopped run gives no terminal signal because the client aborts the stream before the backend's `cancelled` event arrives).

Full account: `tracker/phase_4.9.md`, and the three filed reports beside it.

## Build phase 4.8, done

- Merged to `develop` as PR #41 on 2026-08-13, plus a post-merge fix as `e08c656`.
- The web UI's visual design: MUI adopted, a real theme transcribed from the approved design system, and every screen built in build phase 1.2 restyled.
- All 15 tickets closed.
- Full ticket-level account, every finding and its state: `tracker/phase_4.8.md`.

- Gated first by a design review that ran OUTSIDE the build cadence, which is the one structural difference between this phase and every phase before it.
- A visual deliverable has no natural failing test, so the design system serves as the premise gate's fixture, and a fixture that moves mid-build is not a fixture.
- The product owner iterated on a clickable prototype in Claude Design, the lead pulled and validated it, corrections went back, and an explicit approval opened the phase.

Three independent review rounds ran. ALL THREE returned FAIL, filing 56 findings between them: 48 closed, 8 carried with a named owner each on `tracker/BOARD.md`. Each round's worst defect sat inside the previous round's fix, which is the pattern the build phase 2.1 retrospective predicts.

| Round | Worst finding |
|-------|---------------|
| 1, judge | An anonymous visitor asking ANY question was shown a fabricated, fully cited answer carrying a real NCBI source URL and a "Grounded, every claim cited" pill, bypassing the build phase 3.0 guardrail on the most-travelled path in the product |
| 2, adversary | The root cause of a whole family: `marker_ids`, the wire's exact token-to-citation binding, had no production consumer at all, and the UI re-derived the binding with a substring heuristic, so a citation whose `claim_text` was "cancer" cited every sentence containing the word |
| 3, re-review | Round 2's own fix skipped the run screen for every question after the first, making Stop unreachable on a cost-capped loop |
| Post-merge visual pass | Two major layout defects found by starting the application and looking at it: the whole app rendered in a 720px strip, and the provenance spine's segments drifted out of register with the claims they describe |

Two long-standing repository defects were unmasked and fixed along the way, neither of them this phase's own work:

- The Playwright `webServer` timeout carried as "environmental" since build phase 3.3 was Vite binding IPv6-only against an IPv4 probe. The earlier diagnosis had queried `localhost`, which resolves differently, so the evidence gathered proved a different address than the one failing.
- Behind it, the e2e mock backend's Guard-tier response had not matched the classifier's schema since build phase 3.0. No browser test in this repository had run green for five phases.

Gates at close:

- premise gate 24
- vitest 147
- Playwright 19 executed cases
- typecheck clean
- production build succeeds
- doc drift clean

Six assertions that could not fail were found in this phase, four of them the lead's own, every one caught by deliberately breaking the code and watching the clause stay green rather than by reading it. The generalization, now consistent enough to be predictive: an assertion written against the structure that produced the output tends to restate that structure instead of testing it.


## Two more superseded sections, moved 2026-08-30

These were not labelled "done" but described a state later merges had replaced. "Read before opening the next phase" listed build phases 4.14 and 4.13 as still to come, and both merged weeks earlier, so it was actively misleading rather than merely stale.

One live item was LIFTED OUT of them before the move, rather than archived with them: the `GCK` defect, where a symbol resolves locally and is refused on the deployed API on identical code. It now sits in the continuation prompt's Open items table, and it was already recorded in `tracker/phase_4.12.md`.

## The next session starts here

BUILD PHASE 4.16, THE UI DEFECTS, IS MERGED as PR #63 on 2026-08-25 and is LIVE at https://search-agent-web-production.up.railway.app.

MEASURED ON THE DEPLOYED API AFTER THE MERGE, which is the evidence that the top fix worked rather than the claim:

| Event | Elapsed |
|-------|---------|
| guard | 2.21s |
| think | 4.77s |
| plan | 5.53s |
| tool_start | 5.53s |
| tool_result | 8.35s |
| tool_start | 8.35s |
| tool_result | 8.61s |
| answer | 15.02s |

- The 10.9-second silence is GONE and the Act step reports itself twice.
- ONE RESIDUAL, named rather than glossed: 6.4 seconds still pass between the last `tool_result` and the answer, because the Write step synthesises and emits nothing while it does. That is the same defect class one step further along and it is T-4.16-08.

WHAT SHIPPED, in one line each:

- `tool_start` and `tool_result` emitted AT DISPATCH from `act_node`, through LangGraph's custom stream, so the Act step is visible for the first time on every surface. Both are also returned through `sink.result()` so the replay buffer, the run record and the capture row still see them; `run_streaming` de-duplicates on `seq`.
- `ToolStartPayload.status` gains `"running"`, additive under pattern 10, because a start event is written before dispatch and every existing member would have asserted an outcome that does not exist yet. `ToolResultPayload` re-narrows so "finished and still running" stays unrepresentable.
- A conversation thread on the answer screen: each finished turn collapses into a `<details>` and stays, per the prototype's `archiveCurrent()`. "New search" clears it; the follow-up field extends it.
- Client-side routing over the History API, no router dependency, with the back and forward buttons working.
- The integrations page corrected to the five surfaces that shipped, guarded by a PYTHON test that cross-checks every command it prints against `pyproject.toml` and every path against the FastAPI route table.
- A citation chip no longer repeats its own source, fixed at display time so the wire keeps a resolvable CURIE.
- The `ask` outcome reads "Single source, not independently confirmed" instead of blaming the reader's question.
- The feedback thumb-down renders inside its own button: its rotation was on the outermost `<svg>`, where `transform` is a CSS transform in the element's own pixel space rather than an SVG one in viewBox coordinates.

THE POST-MERGE RE-MEASURE IS DONE, and F-4.16-03 is CLOSED by it. All four answer-screen gaps that traced to the missing tool events closed on deploy exactly as predicted, verified by screenshotting the live product. The two separate defects were already fixed in the phase itself.

- WHAT TO READ BEFORE OPENING ANY PHASE THAT WRITES A TEST: `tracker/phase_4.16.md`'s account of six assertions that could not fail, five written by the lead, none caught by reading.
- The transferable rule is that a test can be correct, honest, and measuring the wrong property, which is how the reported defect survived two direct investigations.

## Read before opening the next phase

- Build phase 4.12, the demo deployment, MERGED as PR #62 on 2026-08-24, on `phase/4.12-demo-deploy`.
- The two fix branches below merged on 2026-08-24, PR #59 and PR #60, and their rows are kept struck through rather than deleted so the trail from build phase 4.7's adversary round to their closure stays readable, and so the residuals each one carried stay visible.

### What is next, in order

Build phase 4.12 is MERGED and the product is live. The product owner ranked THE UI DEFECTS first, on 2026-08-25: they shipped as BUILD PHASE 4.16, MERGED as PR #63 on 2026-08-25 (full detail in "State now" and "The next session starts here" above).

1. THE UI DEFECTS, six of them, recorded in the product owner's own words in `tracker/phase_4.12.md`.
   - Start with streaming: defects 1 and 3 are plausibly one defect, since the API emits `token` events across a 15.8-second answer and a reader seeing none of them incrementally experiences "super slow".
   - Defect 4, answer presentation, has a defined source of truth in `docs/build/design/Design_to_build_workflow.md` and must not be guessed at.
   - Defect 6 needs a router only: the app is served by `serve -s dist`, which is SPA mode, so deep links resolve once routes exist.
   - DONE, as build phase 4.16, PR #63, 2026-08-25.
2. BUILD PHASE 4.14, CI, newly inserted 2026-08-24. Section 24's ten gates, already specified. Pulled forward because 4.12 wired CD, so a merge to `develop` auto-deploys to a public URL and nothing runs the 3930-test suite on a pull request. NEXT.
3. BUILD PHASE 4.13, durable cross-reload history, still unstarted.

Then 5.0 and 5.1 (LangSmith tracing, PostHog, the 50-query golden dataset and the eval harness), then 6.0 and 6.1, then 7.0 and 7.1.

ONE OPEN DEFECT WORTH READING BEFORE TOUCHING ENTITY RESOLUTION: `GCK` resolves locally and is refused on the deployed API, on identical code. Recorded as an unproven HYPOTHESIS rather than a finding, because its traceback could not be read: Railway's log stream returns container startup and `/health` lines and no request-level logs. `tracker/phase_4.12.md` names what would settle it.

## State now as it stood on 2026-08-31, before the board became the source

This is the Phase 6 continuation prompt's `State now` section as it read on 2026-08-31, moved here verbatim when that file was cut back to a board-derived summary. It is kept because it carries per-phase narrative that exists nowhere else, and it is history rather than current state: read `tracker/BOARD.md` for what is true now.

NEXT ACTION, the single line "Start here" step 2 refers to. Keep it current: whoever finishes a stage updates this line before ending their session.

- BEFORE ANY WORK UNDER `src/`, READ `docs/build/Debugging_guide.md`. Merged as PR #90 on 2026-08-31, not a Section 25 build phase. It is a symptom index followed by one row for every Python file under `src/system_03_search_agent/`, plus the frontend, test, tracker and CI files a debugger opens. It is the fastest route from a failure to the file that owns it.
- THAT GUIDE CARRIES AN OBLIGATION, and it is enforced rather than requested. Add, delete, rename or repurpose a file under `src/` and you update the guide in the SAME commit, then regenerate its manifest with `python tests/system_03_search_agent/test_debugging_guide_coverage.py`. Three arms ride CI gate 4: a missing row, a path that does not exist, and a file whose docstring summary line changed since its row was written. Each has a mutation case proving it can go red.
- BUILD PHASE 5.3 MERGED as PR #89 on 2026-08-31 and ITS CHECKPOINT HAS NOT BEEN RUN. This file's State now below, `requirements/Plan.md`'s Revision history, and `PROGRESS.md` all still describe 5.1 and 5.2 as the newest work. Whoever owns 5.3 owes those three updates; they are deliberately not written here, since writing another phase's record from outside it is how a wrong fact enters the permanent narrative.
- BUILD PHASE 5.1, THE 50-QUERY GOLDEN DATASET, IS MERGED as PR #85 on 2026-08-30, all four CI gates green. It is the evaluation set: 50 biomedical questions whose constraints were established from LIVE NCBI lookups on a path that deliberately touches none of the agent's own machinery, then independently re-verified by every review round. Three search categories, named by the product owner: KISS (one exact answer), KISSES (all known results), discovery (a thread of dependent turns), each graded against a different metric because each fails differently. Method: `docs/build/Golden_dataset_method.md`.
- BUILD PHASE 5.2, THE GRADING HARNESS, IS MERGED as PR #86 on 2026-08-30 AND IS PARKED. IT DOES NOT WORK. Four independent review rounds returned FAIL with roughly ninety findings, and its own suite is GREEN with every defect live, which is what makes it dangerous rather than merely unfinished. `replay()` raises `HarnessParkedError` unless the caller passes `acknowledge_parked=True`. Read `tracker/phase_5.2.md`'s banner before touching any of it.
- WHY IT WAS PARKED RATHER THAN FIXED, and this is the product-owner's reasoning rather than the reviewers': the 50 questions are a FIRST ATTEMPT, not a settled target. This is a prototype and the question set will change. A grader precise enough to catch an invented fact about the right gene is precision spent against a moving specification, and the instrument cannot be more settled than the thing it measures. By `attack-the-constraint`, the bottleneck is the question set.
- THE ROOT DEFECT, worth reading before any resumption: grounding compared the agent's prose against the agent's OWN citation payload, because a trace carries the agent's description of a record rather than the record. An answer about a gene that does not exist, citing a record that does not exist, scored 16 of 16 with no hard-fail. The identical circularity had been designed OUT of the dataset builder in the same phase, with a docstring explaining why, and was then designed back IN one file over.
- THE NEXT ACTION IS A PRODUCT-OWNER DECISION, not a build step: settle whether the 50 questions are the right 50. Everything downstream depends on it, including whether a grader is worth building precisely. `docs/build/Golden_dataset_method.md` documents how to change the set, and `eval/golden/build_dataset.py` re-verifies every constraint against live NCBI, so revising questions is cheap and safe. Deciding what to ask is the expensive part.
- AFTER THAT, Section 25's order resumes at build phase 6.0, rate limiting and concurrency. Build phase 7.0, model-bench, is where the parked grader would need to work, since it benchmarks candidate models per tier against the golden dataset.
- ALSO MERGED 2026-08-30, harness rather than product: PR #87 took the Write tool off review agents and grew `/standup` to seven lines; PR #88 states the branch steady state. `.claude/agents/phase-reviewer.md` is the agent to dispatch at cadence stages 8 and 9 from now on, and it has Read, Grep, Glob and Bash and NO Write, because a review round dispatched with full access deleted a tracked file outside its brief.
- WHAT FOUR FAILED ROUNDS COST AND TAUGHT, in one line each. A fabricated answer passed 34 of 50 rows while every arm was green. A hollow measurement was reported to the product owner as proof: "a fabricated answer now passes 0 of 50", produced by a probe using a judge under which nothing could pass at all. The durable repair is a PAIRED PROBE, grading a fabricated and a correct answer with the same judge and requiring the scores to differ, which no constant judge can satisfy. Both are in `LEARNINGS.md`.
- Build phase 4.16 is MERGED as PR #63 on 2026-08-25.
- Seven defects closed: the Act step now emits `tool_start` and `tool_result` AT DISPATCH via LangGraph's custom stream; a conversation thread keeps earlier turns on screen; client-side routing over `/`, `/integrations`, `/about`, `/docs` with no router dependency; the integrations page names the five surfaces that actually shipped; a citation chip no longer repeats its own source; the `ask` outcome no longer blames the reader for single-source evidence; and the feedback thumb no longer renders outside its own button.
- Then build phase 4.13 (durable cross-reload history).
- WHAT THIS PHASE COST AND TAUGHT, and it is not the features. SIX assertions that could not fail were found, FIVE of them written by the lead during this phase, every one caught by mutation or by a screenshot and NONE by reading:
  - A landed-signal that waited for the "New search" button, which BOTH the run screen and the answer screen render, so it passed the instant a question was dispatched. Two second-turn tests passed in under two seconds proving nothing. Caught by screenshotting the deployed demo and seeing a run screen with five pending pips.
  - An integrations guard whose fixture read the raw file and matched the old wrong values inside the COMMENT documenting them, where the tempting fix was deleting the comment.
  - That same guard's populate-check asserting page CONTENT rather than fixture health, so under mutation it fired first and masked all four real failures, reporting a broken harness for an intact page.
  - That same guard's surfaces arm using a substring, so "GraphQL" passed against "GraphQLXX".
- THE DEEPEST ONE IS NOT ON THAT LIST.
- Both of this phase's existing second-turn arms were CORRECT, honest, and blind: they asked "can a second turn be taken" and answered yes, on every path, in two environments, while the actual defect was that the previous turn vanished.
- A test can be right and measuring the wrong property, and that is why defect 2 survived two rounds of being looked for directly.
- THREE HARNESS GAPS FOUND, each recorded with an owner rather than worked around.
- The guest path had NEVER been exercisable in the browser suite, because the e2e mock omits `ANON_DAILY_RUN_CAP` and `_read_int_env` raises rather than defaulting, so every anonymous run 500'd; no spec had ever asked a question without signing up first, which is the only way the demo is used.
- The browser suite cannot reach a REAL tool dispatch at all, since the mock fakes only the model and `plan_node` needs a live NCBI lookup first, which is also why `query-stream-and-stop`'s `answer-cap` arm fails.
- And two live diagnostic specs were written claiming "skipped by default" with no skip, which would have fired at the public demo on every CI run.
- A DESIGN-SYSTEM GAP WORTH FIXING BEFORE THE NEXT UI PHASE: the follow-up field and the conversation thread exist ONLY in `prototype/app.html` and in NO component card, and `design-system/components/trust-pills.html` has no `ask` state.
- `Design_to_build_workflow.md` makes the cards the thing builders build against and gates assert on, so a surface absent from them is a surface nothing can grade.
- That is how a missing conversation thread shipped through build phases 4.8 and 4.9 with every gate green.

Separately from any build phase, the HARNESS itself changed on 2026-08-25 across three pull requests:

- PR #64: the `doc-readability` skill, a preservation script plus a `doc-auditor` agent that together enforce a no-information-lost guarantee on any restructured document.
- PR #65: a cost-model correction, replacing an estimated hosting figure with a measured one.
- PR #66: a phase checkpoint followed by a five-document readability pass over `Plan.md`, this file, `PROGRESS.md`, `CLAUDE.md` and `AGENTS.md`. It also carried the most serious gate fix so far, described below, and produced `tracker/locked_docs_readability_report.md`, a report-only analysis of the two LOCKED requirements documents that is ready to execute the moment the Step 6.2 reconciliation lifts the lock. Neither locked document was edited.

- Running the new gate against real documents found EIGHT defects in the gate itself, every one a FALSE POSITIVE, which is the direction that gets a gate switched off rather than trusted. Where each came from:
  - `docs/build/Build_workflow_cadence.md`, four: union candidates ranked by raw overlap so a diagram outranked the bullets a sentence split into; the candidate pool truncated away a bullet holding only an identifier; the negation check read a single anchor; the comma-chain arm counted across a whole line and required no coordinator.
  - `README.md`, three: a bare noun list flagged as a wall; a heading designator read as title case and reported twice; inline code DELETED before counting series items, which inflated the average and fired a false wall.
  - The five-document batch, one, and it is the worst: the gate was NON-DETERMINISTIC. String hashing is randomized per process and the candidate ranking followed set order, so byte-identical input produced different answers between runs. Fixed by sorting; proven by running a real pair under six hash seeds. A gate whose answer moves is worse than no gate, because a real finding becomes indistinguishable from noise.
- The determinism TEST was itself vacuous on its first two attempts, and that is recorded because it is the trap: with the fix reverted, the bundled fixture, a fixture built deliberately to force ties, and a real 355-line pair with zero findings ALL passed. Only a real pair carrying findings caught it. A green determinism result on a clean pair proves nothing.
- All six were FALSE POSITIVES, closed by calibrating the gate rather than by changing the documents.
- Full evidence, one row per run: `tracker/doc_readability_runs.md`.

- Build phase 3.1 merged as PR #22 (superseded by PR #23) on 2026-08-05 without the adversarial pass over its own fix round, which was the stated pre-merge condition.
- That gap closed across three re-review rounds, all 2026-08-07: a first re-review found the merged commit FAIL (11 of 26 findings closed clean, 15 reopened, 9 new defects including two critical), a fix round closed nearly all of it, a second re-review of THAT fix round found one more critical soundness gap (alias-matching in gene resolution could silently return a confidently WRONG gene, not just fail to resolve) plus a scattering of smaller issues, and a FOURTH reviewer, dispatched specifically because every fix so far had only been checked in the same session that wrote it, independently re-verified the whole branch fresh against live NCBI and returned APPROVE.
- Merged as PR #23.
- Full account: `tracker/phase_3.1.md`'s Findings table, including the "Final independent review" section at the bottom.

Two things were deliberately left open rather than fixed, both genuine product decisions, not bugs: whether the stopword list should exclude entries that are themselves real gene symbols (F-3.1-41), and what happens when a gene is mentioned in lowercase (F-3.1-42). Three more minor, non-blocking findings from the final review are carried to before `ncbi_efetch` gets wired into `act_node` (F-3.1-50, F-3.1-51, and F-3.1-46 already tracked).

- F-2.1-C15's generation half, the finding where a generated query took the graph server down for every user, closed on `fix/c15-generation-bound` the same day: `validate_cypher` now rejects any generated Cypher carrying a variable-length relationship pattern (`[:orthologous_to*]` or similar) before execution, the mechanism behind the original OOM.
- The existing `_MEMORY_GUARD_SQL` session-level mitigation is unchanged.
- This fix's own first version, sliced from the existing relationship-hop regex, was itself found bypassable by a fresh-context adversarial review before merge: a nested bracket (a list-valued property) alongside the variable-length spec defeated it, the same non-nesting-regex defect class already fixed once in this file for node patterns (F-2.1-A9) and never generalized to relationship hops.
- Rebuilt as a standalone, wildcard-free pattern matched directly against the quote-masked query string, independent of the hop regex entirely.
- A second independent review confirmed the bypass closed, found no new one, checked for ReDoS (none), and found one narrow, non-blocking gap against full Cypher grammar unreachable by this system's actual generation, documented rather than fixed.
- F-2.2-01 (a separate, lower-severity generation flake, roughly 1 run in 10) was deliberately left open rather than folded into the same branch, per the ticket's own allowed alternative.
- Full account: `tracker/fix_c15_generation_bound.md`.

- Twelve build phases are done, all twelve merged into `develop` (renamed from `main` at Step 6.2).
- The first six complete the Step 6.1 prototype group; 3.0 through 3.5 are all six of the Step 6.3 tool-and-trust v1 phases, and with 3.4's merge every one of them is now closed:

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
| 3.4 | Provenance extended to Layers 2 and 3 (the four added CitationPayload fields), the two-tier risk gate, data freshness and conflict resolution, T-3.1-28 (Act-step dispatch of a second layer) folded in. Two judge rounds, an adversary round (7 findings, 1 critical), a fix round, a final confirmation round | #28 |
| 3.5 | pathogen_detection and clinicaltrials_search, completing the seven-tool roster. A judge round and an adversary round that found the judge round's own fix had introduced two new critical regressions of the identical shape, both closed and live re-verified | Merged on `phase/3.5-pathogen-clinicaltrials-tools` |

Current counts, stated once here:

- Python tests: 4652 at the 2026-08-30 merge (4480 passing, 171 skipped, 1 xfailed, ZERO FAILED) on `develop` after build phases 5.1 and 5.2 merged as PR #85 and PR #86 on 2026-08-30
  - The figure at build phase 4.14's close was 4226 (4066 passing) on `phase/4.14-ci-gates`, measured 2026-08-25; build phase 4.13 adds 60, which are the premise gate's 11 arms plus the unit, endpoint, auth-liveness and boundary arms its three review rounds produced.
  - The figure at build phase 4.12's close was 4090 (3930 passing) on `phase/4.12-demo-deploy`; build phase 4.16 adds 12, being a 5-arm premise gate and a 7-case mutation harness.
  - THE STANDING SIX-FAILURE BASELINE IS GONE, and it was never six broken tests: all six were in `test_citation_trust_full_premise.py`, all six pass under `RUN_PREMISE_GATE=1`, and that file FAILED where it should have SKIPPED because its `live_only` mark gated on a model key existing rather than on outbound HTTP being permitted. Build phase 4.12 fixed it.
  - The figure before that was 4046 (3887 passing, 6 failed) on `develop` with both fix branches merged (PR #59, F-4.7-A-02, and PR #60, F-4.7-A-01), against a baseline RE-MEASURED in a throwaway worktree at `4d759da`: 3826 passing, 146 skipped, 6 failed. Neither branch's own figure is reproduced here, deliberately: each measured only its own branch, and the merged tree is neither of them, so carrying either number forward would record a total that was never true of this commit.
  - The figure recorded at build phase 4.7's close was 3979 total / 3826 passing, and the total was already 13 stale when that line was written, which is the exact failure the rest of this bullet warns about. The 6 are all PRE-EXISTING and none belong to build phase 4.7: all six are in `test_citation_trust_full_premise.py`, and they fail because that file's live Layer 2 and Layer 3 calls are blocked in the ordinary unit run.
  - RE-MEASURED AT THIS BRANCH POINT rather than carried forward, which is the practice this line exists to enforce: the figure recorded at build phase 4.4's close was 10, and the 3 `test_cypher_query_e2e.py` failures in it are simply gone, because build phase 4.11 moved Layer 1 behind an HTTPS service and those tests no longer depend on a hand-opened tunnel. The seventh `test_citation_trust_full_premise.py` failure recorded there is also gone. Neither disappearance was caused by build phase 4.7.
  - A stale baseline is how a genuine regression hides, since the next reader compares against a number that was never true, so re-measure at each phase close rather than carrying it forward, and say which commit you measured at.
- Frontend tests: 235
- Playwright end-to-end tests: 43 declarations, 50 executed cases, of which 2 are LIVE DIAGNOSTICS gated off by default behind `RUN_LIVE_DIAGNOSTICS=1` because they reach the deployed demo and spend real budget.
  - Re-run in full on 2026-08-25 during build phase 4.16.
  - The one failure is `query-stream-and-stop.spec.ts`'s "a signed-in query streams through the pipeline and produces an answer", waiting for `answer-cap`, and it is PROVEN PRE-EXISTING rather than asserted: the same spec was run at `e486310`, build phase 4.16's branch point, where it fails identically with none of that phase's changes present. Unowned as of this line.
  - The previous figure here, 29 declarations and 30 executed ALL PASSING, was measured at build phase 4.10's close on 2026-08-15 and had been carried forward through five merged phases without re-measurement, which is exactly what this file's own baseline rule forbids.
  - A webServer timeout seen during that run was an orphaned probe process squatting on the backend port, diagnosed rather than assumed, since this suite once carried an IPv6-binding defect as "environmental" for five phases. First green as of 2026-08-13, the first green run since build phase 3.0.
  - The previous note here said these were "unverifiable, a webServer-orchestration timeout unrelated to any file either phase touched, confirmed by starting the dev server directly, HTTP 200". That diagnosis was wrong and is corrected rather than deleted, because the way it was wrong is the lesson: the check started the server by hand and queried `localhost`, which resolves to `::1` on macOS, while Playwright probes `127.0.0.1`. Vite bound IPv6-only, so the evidence gathered proved a different address than the one failing.
  - Behind that timeout sat a second, older breakage: the e2e mock backend's Guard-tier response had not matched the classifier's schema since build phase 3.0, so the suite would have failed even had it started. Both are fixed
- Premise gate, cypher_query: 9 of 9
- Premise gate, write-step grounding: 11 passed, 1 xfailed by design
- Premise gate, guardrail: 20 of 20
- Premise gate, ncbi_efetch: 19 passed, 1 skipped (tunnel)
- Premise gate, ncbi_dbsnp: 8 of 8, live, no tunnel-gated skip
- Premise gate, pubtator_annotate + litvar2_lookup: 12 of 12, live, no tunnel-gated skip
- Premise gate, pathogen_detection: 5 of 5, live, no tunnel-gated skip
- Premise gate, clinicaltrials_search: 3 of 3, live, no tunnel-gated skip
- Premise gate, citation trust full (Layer 2/3 provenance, the two-tier risk gate, freshness, conflict detection): 10 of 10, live, no tunnel-gated skip, graded pass@8 on its one Synth-sampling-sensitive case (F-3.4-T05-05)
- Premise gate, build phase 4.0's own gate (a normal test file, not one of the seven live tool gates above): 26 of 26
- Premise gate, build phase 4.1's own gate (the MCP server, a normal test file, not one of the seven live tool gates above): 48 of 48
- Premise gate, build phase 4.10's own gate (the guest allowance, a normal test file, not one of the seven live tool gates above): 36 of 36, every clause mutation-proven, two-armed throughout since a control that refuses every guest passes every attack test and destroys the product
- Decisions logged: 464
- Learnings entries: 152, plus a retrospective. Restructured 2026-08-10 (PR #38): every entry from build phase 1.0 onward is now a short table row ending "Full account below," pointing to a verbatim detail section, since the table cells had grown into 100 to 500-plus word paragraphs. Nothing was reworded; only relocated. See LEARNINGS.md's own table of contents

- Build phase 3.4, citation trust extended to Layers 2 and 3, closed 2026-08-10 on `phase/3.4-citation-trust-full`, merged as PR #28 (see "Build phase 3.4, done" below).
- This was the last of the six Step 6.3 tool-and-trust phases (3.0 through 3.5) named in Section 25's dependency graph; all six are now merged, and nothing in that group is left to open.

- The build phase 3.1 tool surface is complete and its findings are settled: 40 of 42 numbered findings closed, F-3.1-04's answer-path half (Act-step wiring, Layer 2 citation, trust gate) closed by T-3.1-28, folded into build phase 3.4 as T-3.4-05, and exactly two left open on genuine product decisions, F-3.1-41 and F-3.1-42, detailed in `tracker/phase_3.1.md`.

- Step 6.2 moved on 2026-08-03 to run AFTER the 3.x tool phases rather than between 2.2 and 3.0, because its own written reasoning names 3.x as the code its security scan most exists for, and because reconciling the frozen documents after the tool phases is better input than reconciling before them.
- With build phase 3.4's merge, that condition was met, and Step 6.2 ran and closed the same day, 2026-08-10 (see "Step 6.2, done" below).
- Its security scan stays separately PAUSED INDEFINITELY on cost, with one condition that turns it back on: exposure.
- First contact with a real user, a deploy, or a public URL triggers it, whichever comes first.
- Step 6.3 continues at build phase 4.0.

Per-phase detail lives in `tracker/phase_N.M.md`. Phase narrative lives in `requirements/Plan.md`'s Revision history. Phase status and the flags that gate a phase live in `tracker/BOARD.md`.

- READ THE BOARD'S FLAG COUNT AS TWO NUMBERS, not one.
- Its flags table is a LEDGER, not a queue: a closed finding keeps its row so the trail survives, so the total only ever grows and is not a backlog.
- `render_board.py` reports the split, currently `flags: 57 open, 29 closed` (86 total), after the single number was read as 83 outstanding problems on 2026-08-23 when 26 of them were already closed.
- Of the open ones, most are CONDITIONAL, worded "whenever X is next touched": those are notes attached to code, not scheduled work, and they become work only if someone touches that code.
- The rows that are genuinely queued name a phase or a branch.

One exception to the one-owner convention, stated rather than left to be discovered.

- The Open items table below is NOT a copy of `tracker/BOARD.md`.
- Measured 2026-08-04: of its 28 tracked identifiers, 14 also appear on the board and 14 appear nowhere else in the repository.
- So the table is the full forward backlog by owner and is the sole record for half its rows, while the board carries the subset that blocks a specific phase from closing.
- Where an item appears in both, the board's "Resolve before" column is authoritative.

That split is a known wart rather than a design: the board is the incomplete one. Folding the 14 orphans into it would break the renderer's invariant that every phase's flag count matches the Open flags table, so it is a deliberate task and not a tidy-up. Until then, do not delete a row here on the assumption the board already has it.
