# Phase 3.1: ncbi_efetch, the general Layer 2 client

Build phase 3.1 delivers the first Layer 2 tool: one tool, seven actions, across three API families with two incompatible error conventions.

Depends on: build phase 2.0 (done, PR #9) and build phase 3.0 (done, PR #19)
Branch: `phase/3.1-ncbi-efetch`
Spec: `requirements/Technical_specification.md` Section 6.2, with Section 21.1 for rate limits
Reference: `docs/ncbi/Tool_implementation_mechanics.md`, `.claude/rules/tool-call-budgets.md`, `LEARNINGS.md`'s build phase 2.1 retrospective

## Phase premise (the done-when)

A question about a gene the system has never been told about resolves to the right gene, and the `ncbi_efetch` tool classifies what a live NCBI API actually returned as `ok`, `empty`, or `error` correctly across all three API families and both error conventions.

The answer-path half of the original premise ("reaches a live NCBI API, comes back as real records, and is either cited from what the API actually returned or refused") is CARRIED to T-3.1-28 (the Act-step wiring ticket), by the product owner's decision of 2026-08-05. This is a deliberate narrowing, not a silent edit. Section 25 groups provenance and the two-tier trust gate across 3.0 to 3.5 rather than inside 3.1, and wiring the answer-path inside this phase would have been real additional work: tool selection, a Layer 2 `CitationPayload`, provenance, and the trust gate. The premise is restated here rather than quietly rewritten to match the current state, which is the verify-surface weakening `goal-contracts` forbids.

The second half is the one a reader will underestimate. `_KNOWN_GENE_SYMBOL_CURIES` (`core/graph.py:839`) held exactly one entry, `BRCA1`, so a query about any other gene resolved nothing and answered nothing. That was finding F-2.1-07, this phase owns it, and it is the single thing that stood between this repo and a prototype that can be shown to anyone. It is now resolved: gene symbols are looked up live via NCBI Datasets v2 and ESearch, and the one-entry hardcoded table is gone.

The verify surface is `tests/system_03_search_agent/tools/test_ncbi_efetch_premise.py`, not a suite total.

## Phase status: two independent re-review rounds complete 2026-08-07, all findings closed or explicitly open on product decisions, PR pending

Opened 2026-08-04, immediately after build phase 3.0 merged. Stage 5, the blocking premise gate, was written and watched failing on 2026-08-05 at 15 of 16, with the failure direction verified. Merged as PR #22 on 2026-08-05 at 1571 passed, 82 skipped, 1 xfailed, doc drift clean, WITHOUT an adversarial pass over its own fix round, which was the stated pre-merge condition. That was a product-owner decision of 2026-08-05, recorded rather than hidden: twenty-two findings were fixed on the fixer's word and no independent role had confirmed any of them.

Round 1 re-review (2026-08-07, primary provider): six independent fresh-context reviewers found that commit FAIL. 11 of 26 findings closed clean, 15 reopened, and 9 new defects of the fix round's own making, two CRITICAL (gene-symbol resolution completely broken; a field-tag fix that was not valid Entrez syntax).

Fix round 2 (same day): six parallel builders in isolated worktrees fixed the round-1 findings. Integrating their branches surfaced two cross-file seams no single builder could see (documented in the Findings table).

Round 2 re-review (same day): three more independent fresh-context reviewers, live against NCBI, found a genuine soundness gap in gene resolution (alias matching could silently return a confidently WRONG gene, not just fail to resolve), a pre-existing bug that made one of round 1's critical fixes dead code in production, a second URL-encoding gap, and a regression in round 2's own wait-budget fix. All fixed the same day; the two highest-stakes fixes were mutation-tested (revert, confirm the new test fails, restore) rather than trusted on a single pass.

Net: 40 of 42 numbered findings are `closed`, F-3.1-04 is correctly `carried`, and exactly two are `open` on genuine product decisions rather than left unfixed by oversight (F-3.1-41, F-3.1-42, both detailed in the Findings table, both downgraded from "could fabricate a wrong answer" to "could over-block a legitimate one" by the F-3.1-39 fix). Seven more minor findings from round 2 are carried to Step 6.2 rather than fixed same-day, listed in "Minor findings from round 2" below.

Gates as of the last commit on `fix/3.1-rereview-round1-critical-regressions`: `pytest -q` 1715 passed, 82 skipped, 1 xfailed. `ruff check src/ tests/` finds the same 4 errors present before this round started and confirmed unrelated (pre-existing `PYI034`/`SIM117` in one test file's log-capture helper, untouched by any commit here). `python tracker/check_doc_drift.py --check` still flags stale test counts in `AGENTS.md`, `CLAUDE.md`, and `requirements/phase_6/Continuation_prompt.md`, addressed separately.

Not yet done: a third independent re-review of fix round 2 itself, and opening the pull request. Per this same day's own lesson, closing this phase on the strength of two same-day self-verifications, however thorough, repeats exactly the pattern that produced round 1's two critical regressions. The PR should carry this table as its description and get a genuinely independent look before merge, even though every fix already shipped with a live reproduction.

## Scale, stated at the top because it changes how this phase should run

This is a larger phase than 3.0, and the numbers are worth seeing before any ticket is picked up:

| Dimension | Count |
|-----------|-------|
| Actions on one tool | 7 |
| Databases accepted by `search` | 14 |
| Databases with a verified, per-database ESummary field set to extract | 8 |
| Independent API families | 3 (E-utilities, Datasets v2, PubChem) |
| Error conventions among those families | 2, and they are opposites |
| Rate-limit pools | 3, one of which has an unresolved conflict (Section 21.1) |

Build phase 2.1 was a single tool with a single action against a single host, and it took four calendar days and five review rounds. This phase is wider than that on every axis. Sequencing it as one undifferentiated block is how it becomes 2.1 again.

## The load-bearing trap, named once here

E-utilities returns HTTP 200 for a genuinely empty result AND for several distinct error classes. An invalid database name arrives as a 200 whose body carries `esearchresult.ERROR`. EFetch on a nonexistent id arrives as a 200 with an empty record set and no error node at all.

So every E-utilities-backed action decides `ok` versus `empty` versus `error` by inspecting the response BODY, never the HTTP status. Datasets v2 and PubChem are the exact opposite: they return proper status codes and branch on status directly.

Both conventions live on the same tool, behind one output shape. Error handling written once and assumed to cover every action will get one family right and the other silently wrong. That is the cross-tool trap `docs/ncbi/Tool_implementation_mechanics.md` records at lines 119 to 122, and it is why T-3.1-02 exists as its own ticket ahead of every action ticket.

## Ticket map

| Ticket | Slice | Files |
|--------|-------|-------|
| T-3.1-01 | The premise gate, blocking | `tests/system_03_search_agent/tools/test_ncbi_efetch_premise.py` |
| T-3.1-02 | Transport: the two error conventions, timeout, retry, throttle | `tools/ncbi_transport.py` |
| T-3.1-03 | Schemas: the 7-way discriminated input, the single output shape | `tools/ncbi_efetch_schemas.py` |
| T-3.1-04 | `search` (ESearch), with EInfo-validated field tags | `tools/ncbi_efetch.py` |
| T-3.1-05 | `summary` (ESummary) and the per-database field extraction | `tools/ncbi_efetch.py` |
| T-3.1-06 | `fetch` (EFetch), XML with external entities disabled | `tools/ncbi_efetch.py` |
| T-3.1-07 | `link` (ELink) with an explicit target db, never the default | `tools/ncbi_efetch.py` |
| T-3.1-08 | `dataset_report` (Datasets v2), status-code branching | `tools/ncbi_efetch.py` |
| T-3.1-09 | `pubchem_property` (PUG REST), status-code branching | `tools/ncbi_efetch.py` |
| T-3.1-10 | `coordinate_overlap`, the five-step placement procedure | `tools/ncbi_efetch.py` |
| T-3.1-11 | F-2.1-07: real gene-symbol resolution, replacing the one-entry table. Carries the candidate filter (F-3.1-01) and the async ripple, both named below | `core/graph.py` |
| T-3.1-12 | Tool registration, and the schema's place in the stable prompt prefix | `core/graph.py`, `harness/cache.py` |
| T-3.1-13 | F-2.1-B10: an unresolvable entity refuses, rather than reaching the graph as an unbound parameter | `core/graph.py` |
| T-3.1-28 | Wire the Act step to dispatch ncbi_efetch as an answer-bearing tool, with Layer 2 citation payload and trust gate. Carried from 3.1's original premise (product owner decision 2026-08-05) | `core/graph.py`, `harness/` |

Three tickets changed on 2026-08-05, after the stage 5 research pass. Recording what moved and why, since a silently edited decomposition is the thing build phase 2.1's retrospective warns about:

- T-3.1-13 is NEW. F-2.1-B10 had no owner. The twelve-ticket map assumed it closed when F-2.1-07 closed, and it does not: perfect resolution still leaves typos, non-human genes, and disease names typed where a symbol was expected. Those reach the graph with an unbound parameter and surface as `graph query failed: UndefinedParameter` after burning two model calls and 21.7 seconds. The adversary's own line is the acceptance criterion: "I could not identify that gene" and "the graph query failed" are different messages, and only one of them is true.
- T-3.1-11 gained the candidate filter explicitly, rather than leaving it to be discovered. See F-3.1-01 below. It must land in this ticket and not a follow-up, because this ticket is what arms the defect.
- T-3.1-11 also gained the async ripple explicitly. Making resolution network-bound turns `_extract_target_entities` (`core/graph.py:849`, currently `def`) async, which touches two production call sites (`graph.py:915` in `_select_planned_tool_call`, `graph.py:2139` in `write_node`'s refusal branch) and six test call sites across four files, including build phase 2.1's own premise gate at `test_cypher_query_premise.py:170`. The `write_node` site needs a decision rather than a mechanical await: re-resolving on the refusal path spends a live API call and latency to tell a user no, twice over.

## Recommended build order, and why it is not the ticket order

T-3.1-01, then T-3.1-02 and T-3.1-03, then T-3.1-04, T-3.1-05 and T-3.1-11, then the rest.

The reason is the demo. F-2.1-07 needs exactly one path to work: a gene symbol resolved to an NCBIGene id, which `dataset_report`'s `gene/symbol/{symbol}/taxon/{taxon}` endpoint does directly and which `search` plus `summary` on the `gene` database does as a fallback. Everything else on this tool (`fetch`, `link`, `coordinate_overlap`, `pubchem_property`) is real v1 scope and none of it is on the path between here and a system a person can be shown.

This is a sequencing choice inside the phase, not a scope reduction. Every ticket above is built before this phase closes. Nothing on the Section 6.2 list is being dropped, deferred, or quietly renamed, which `.claude/rules/v1-scope-boundary.md` would forbid.

## Premise gate design

WRITTEN and watched failing on 2026-08-05, before any tool code existed. Stage 5 is satisfied.

File: `tests/system_03_search_agent/tools/test_ncbi_efetch_premise.py`, 16 cases.

Baseline, the number this phase is measured against: 15 failed, 1 skipped. Every failure was in the correct direction, which was checked rather than assumed, per LEARNINGS.md row 43: a failure whose direction does not match the change is a broken experiment, not a finding. All 15 failed because the artifact under construction is absent (`ModuleNotFoundError: No module named 'system_03_search_agent.tools.ncbi_efetch'`, and for the three resolution cases `ImportError: cannot import name 'resolve_entity_curies'`). None failed for an unrelated reason such as a network fault or a syntax error.

The one skip is case 16 and it is deliberate. See "the arm that is deliberately not blocking" below.

### The arms, which are not 3.0's arms

3.0's guardrail had no safe direction of failure, so its arms were admit and refuse. This tool's arms are the three status values, because `ncbi_efetch` makes one decision repeatedly: given a response, is this `ok`, `empty`, or `error`.

Getting `ok` wrong is the dangerous case, since an `ok` carrying nothing real is a fabricated citation. But `error` is not a safe default either: a tool that returns `error` on every zero-hit search tells a user the API broke when the honest answer is that nothing matched. Those are different answers to a user and only one is true in each case.

| Arm | Cases | What it pins |
|-----|-------|--------------|
| ok | 1 to 6 | Real records come back, and they are the RIGHT records. Case 1 asserts the id is `7157`, not that an id exists, since "an id came back" is the assertion that let build phase 2.1 ship twenty-five orthologs |
| empty | 7, 8 | Nothing matched, and the tool neither errors nor fabricates a blank record carrying a `source_url` |
| error | 9, 10, 11 | Something genuinely broke, in all three response envelopes |
| the phase's own reason | 12 to 15 | F-2.1-07, F-2.1-B10, F-3.1-01, and the silent field-tag fallback |
| end to end | 16 | The full premise, gated on the tunnel |

### The near-miss pair, which is why the gate exists

Cases 7 and 9 are adjacent on purpose. A genuine zero-hit search returns HTTP 200 with `count` `0`, an empty `idlist`, and no `ERROR` key. An invalid db name returns HTTP 200 with `esearchresult.ERROR` set. The two responses differ by the presence of a single JSON key and must land in different status buckets. A tool that branches on HTTP status classifies them identically and is wrong about one of them.

This is build phase 3.0's near-miss trap ("what legitimate input is one token away from the rejection rule") applied to error classification instead of to admission.

Cases 10 and 11 are the deliberate counterweight: Datasets v2 and PubChem use proper HTTP status codes, so one shared error-handling path cannot satisfy both case 9 and case 10. That is the constraint T-3.1-02 exists to carry, and it is now testable rather than only described.

### The arm that is deliberately not blocking

Case 16 asserts the phase premise in full: a TP53 question is ANSWERED, not merely resolved. It skips on graph reachability and blocks nothing today, because the SSH tunnel cannot be opened from this environment (T-3.0-07, `tracker/BOARD.md:79`) and gating the blocking gate on an unreachable tunnel makes it unrunnable, which is worse than a narrower assertion.

Stated plainly rather than buried: a green run of the blocking half proves TP53 RESOLVES. It does not prove a TP53 question is answered well. That is a known, dated hole in this gate, not a covered case, and it closes the moment the tunnel is reachable with no edit to the file.

### Coverage

The gate states its own coverage in its module docstring, per `.claude/rules/goal-contracts.md`. Summarized: 6 of 7 actions, 4 of 14 databases, all 3 API families, both error conventions.

The highest-risk omission, named in the gate itself rather than left to be discovered: `coordinate_overlap` is NOT exercised, and it carries the one trap in this tool with a proven live bug. No coordinate ground truth is pinned anywhere in this repository, and constructing an expected overlap set from documentation would assert a result nobody has verified. T-3.1-10 must pin its own live-verified fixture and add it to the gate. Until it does, the gate does not cover this tool's worst trap.

## Findings

State vocabulary, added 2026-08-05, extended 2026-08-07 across two re-review rounds:

- `fix-landed`: a commit claiming to fix this finding has merged, and no independent role has confirmed it. No finding is in this state; every one below has been through at least one independent re-review.
- `carried`: deliberately not fixed in this phase, with a named owner elsewhere.
- `open`: an unresolved decision, not a bug with a single correct fix. Building the wrong resolution unilaterally is worse than leaving it open; the disposition line says what is blocking a decision.
- `closed`: an independent re-review reproduced the fix and found it complete.

Round 1 (2026-08-07, primary provider): six independent fresh-context reviewers (five by file cluster, one adversary) found the prior fix-landed commit FAIL: 11 of 26 closed clean, 15 reopened, F-3.1-04 correctly carried, and 9 new defects of the fix round's own making, two critical (F-3.1-28, F-3.1-29 below).

Fix round 2 (2026-08-07, same day): six parallel builders in isolated worktrees fixed the round-1 findings; the lead integrating their branches caught and fixed two cross-file seams neither builder could see alone (a `retry_after` value nobody wired up, `coordinate_overlap.py` missing the HTTP-status guard `ncbi_eutils_actions.py` got).

Round 2 (2026-08-07, same day): three more independent fresh-context reviewers re-verified the fix-round-2 diff, live against NCBI. Found a genuine soundness gap neither round 1 nor the builders caught (NCBI's `[sym]` tag and the Datasets symbol endpoint both match on gene ALIASES, so an "unambiguous" single-id match could be a confidently WRONG gene), a pre-existing bug that made one of round 1's two critical fixes dead code in production (EInfo's real response shape was never handled), a second URL-encoding gap in a sibling file, and a regression in round 2's own wait-budget fix. All four fixed the same day, each live-verified and, where practical, mutation-tested (reverted, confirmed the new test fails, restored).

Net result as of this table: every finding below is `closed` or `carried` except two, both `open` on a genuine product decision rather than a bug, and both downgraded from "could return a confidently wrong gene" to "could over-block a legitimate one" by the alias-verification fix. Full evidence for every row is in the commit history on `fix/3.1-rereview-round1-critical-regressions`, not restated here; each commit message carries its own live reproduction.

| ID | State | Summary |
|----|-------|---------|
| F-3.1-01 | closed | Gene-symbol candidate extraction fired on every word in the query. Fixed at the root: candidates are matched against the ORIGINAL query text (case preserved), not an uppercased copy, so only tokens already written the way a gene symbol is written qualify. Live-verified on the original failing vocabulary |
| F-3.1-02 | closed | The coordinate overlap filter compared assembly and the overlap predicate but never the chromosome. Fix verified live against real dbVar |
| F-3.1-03 | closed | Resolution caching stored every `None`, including a transient-failure `None`, as a permanent non-resolution. `(curie, cacheable)` now genuinely distinguishes the two |
| F-3.1-04 | carried | `ncbi_efetch` is never dispatched as an answer-bearing tool, only from inside entity resolution. Re-confirmed accurate after every fix round: exactly two call sites, both in entity resolution |
| F-3.1-05 | closed | The Datasets resolution path took `records[0]` with no ambiguity guard. Now requires exactly one record and falls through otherwise |
| F-3.1-06 | closed | The unit suite made live NCBI calls. `tests/conftest.py` carries a session-scoped autouse guard, verified to actually fire |
| F-3.1-07 | closed | Any 2xx Datasets body lacking a `reports` list collapsed to "empty" rather than "error". Now allowlists the live-verified empty shape and fails closed otherwise |
| F-3.1-08 | closed | Every PubChem record shipped `source_url=None`. Host pattern widened to admit `pubchem.ncbi.nlm.nih.gov`, holds against every spoof tried. (The URL-encoding gap this fix's own new code introduced is tracked separately as F-3.1-36) |
| F-3.1-09 | closed | A docstring falsely claimed the Act step wraps every tool call in `harness.enforce_timeout`. Corrected |
| F-3.1-10 | closed | `_generic_summary_fields` copied every response key with no field-level filter. Real per-database allowlists added for all 12 `SummaryDb` values; the character cap now recurses through nested dicts/lists, not just top-level strings |
| F-3.1-11 | closed | The tool registry gained `ncbi_efetch` with no contract-version bump. Replaced the decorative constant with a fingerprint-based gate that fails the process at import time if the registered tool set changes without a version bump; proof-tested by temporarily adding a fake tool and watching it fail, twice, independently, by two different roles |
| F-3.1-12 | closed | Four minor gaps, all closed: 429 now surfaces a real `retry_after` via the shared `Retry-After` parser; the coordinate-range validator moved to the Pydantic schema layer, visible in the generated JSON schema; property-claiming comments got enforcing tests; the per-value character cap now applies in all four field-extraction modules |
| F-3.1-13 | closed | `summary` fabricated a citation for a nonexistent uid. Fixed and live-verified across gene, pubmed, clinvar and the generic path |
| F-3.1-14 | closed | The live-lookup budget was consumed by ordinary English words. Fixed at the root alongside F-3.1-01 (case-preserving candidate shape); the digit-priority sort that caused F-3.1-30's regression was removed rather than patched further; duplicate-token budget waste (found by round 2's adversary) fixed in the same pass |
| F-3.1-15 | closed | `chr1` reported no variants for a window that has 17. `_normalize_chromosome` now strips leading zeros too, closing the `'01'` spelling the original fix missed; all spellings tested return the identical live result set |
| F-3.1-16 | closed | ELink's real error shape was classified as a confirmed empty result. Fixed and re-confirmed live by two independent reviewers |
| F-3.1-17 | closed | Non-human taxon resolution discarded the correct cross-species record. Reachable now that F-3.1-28 is fixed; live-verified TRP53/mouse resolves to 22059, not human TP53 |
| F-3.1-18 | closed | Unencoded `&` and `=` let caller values inject arbitrary parameters. `safe=""` applied to every query-string value |
| F-3.1-19 | closed | HTTP status codes were never read. Now read on every E-utilities call site: `search`/`summary`/`fetch`/`link`, the EInfo hop, and (found by round 2's adversary, missed by round 1) both `coordinate_overlap` hops, which shared the same gap through a different file. A real `retry_after` surfaces via `ncbi_transport`'s shared parser everywhere a 429/503 can occur |
| F-3.1-20 | closed | `fetch` on schema defaults returned one uncited blob. Guard generalized from `db == "pubmed"` to all 8 `FetchDb` values |
| F-3.1-21 | closed | PubChem confused total failure with a clean empty result and silently dropped CIDs. Both halves fixed: error/empty distinction corrected, and truncation now honestly disclosed when the name-resolution cap drops CIDs |
| F-3.1-22 | closed | A retry issued a second HTTP request without a second rate-limiter acquisition. Fixed; the latency-budget regression this fix itself caused is F-3.1-37, also closed |
| F-3.1-23 | closed | `_apply_field_tags` scoped a field tag to only the last token. Root cause was invalid Entrez syntax in the first fix attempt (F-3.1-29); corrected to tag a single atomic term directly and fail closed with an actionable error on a multi-token term rather than guess. Live-verified equivalent to the pre-defect control on the single-token case; the multi-token case no longer emits silently-wrong syntax |
| F-3.1-24 | closed | `total_available` reported the coarse ESearch prefilter count. Restored to the honest ESearch total; added `candidates_checked` as a distinct, additive field so `total_available == record_count` while `truncated == True` can no longer both be true for the same output |
| F-3.1-25 | closed | `record_count` meant a different thing per action. Now `len(records)` consistently across all seven actions |
| F-3.1-26 | closed | A zero-id search poisoned the symbol cache. Both legs (E-utilities side and the "both APIs answered" cacheability check) now correctly require BOTH Datasets and ESearch to have answered without erroring before caching a negative |
| F-3.1-27 | closed | `coordinate_overlap` accepted inverted, negative and zero-length windows. Fixed; the named 0bp dbVar residual could not be reproduced against live data and is filed as latent, not exploitable |
| F-3.1-28 | closed | CRITICAL. `resolve_symbol_to_curie` passed its own cache key, not the caller's symbol, into the lookup function, so every live gene-symbol resolution returned `None`. One-line root cause (a taxon-aware refactor left the wrong variable at the call site), fixed and live-verified: BRCA1, TP53, EGFR, and cross-species TRP53/mouse all resolve correctly; the phase's own premise gate passes 19 of 20 live (the 1 skip is the pre-existing tunnel-gated case) |
| F-3.1-29 | closed | CRITICAL. `(term)[tag]` was not valid Entrez syntax; it unscoped the query and injected "sym" as a literal search term. Fixed alongside F-3.1-23. Separately, found unreachable in production by round 2's adversary because of a pre-existing EInfo parsing bug (see F-3.1-38) that predates this phase; both are now fixed and `[sym]` is live-verified working end to end |
| F-3.1-30 | closed | The digit-priority candidate sort (added to fix F-3.1-14) made build/coordinate tokens outrank real gene symbols. Removed outright once the case-preserving root fix (F-3.1-01/14) made it unnecessary; live-verified the KRAS regression case now resolves correctly |
| F-3.1-31 | closed | The stopword-list additions permanently blacklisted `LARGE`, a real human gene (NCBIGene:9215). Removed from the list; a live full audit of the remaining list (below, F-3.1-39) found more of the same class, left open as a product decision rather than mechanically removed |
| F-3.1-32 | closed | A passing test assertion was deleted with no replacement during the first fix round. Restored |
| F-3.1-33 | closed | The fix commit introduced 12 new `ruff` errors. Clean since the fix-round-2 integration; reverified at every commit in this round, 4 pre-existing errors remain (confirmed present before AND after every change in this round, unrelated to this phase) |
| F-3.1-34 | closed | `pubchem_property` raised an uncaught `ValidationError`; `_cids_from_body` silently dropped non-scalar CID entries. Both fail closed now, matching every sibling module |
| F-3.1-35 | closed | `_chromosome_matches` matched an empty-string chromosome against a placement with a missing `chr` key. Now fails closed on either side being blank |
| F-3.1-36 | closed | PubChem's new `source_url` (from the F-3.1-08 fix) interpolated the untrusted CID unencoded. Now goes through the same path-segment quoting helper every other caller-supplied URL segment in this codebase uses |
| F-3.1-37 | closed | Acquiring the rate limiter per retry attempt let one call wait up to 2x its declared ceiling. First fix (per-attempt deadline) shared a WALL-CLOCK deadline that also charged request and backoff time against the pool-wait budget, silently zeroing the retry's budget in the exact case (a timeout) a retry exists for; found by round 2's adversary, fixed by tracking only actual time spent inside the rate limiter's own wait, and mutation-tested: reverted to the wall-clock version, confirmed the new test fails with the reproduced symptom, restored |
| F-3.1-38 | closed | NEW, found by round 2. Live EInfo wraps `einforesult.dbinfo` in a one-element LIST; the code required a dict and failed closed unconditionally, meaning `field_tags` validation, and therefore F-3.1-29's fix, was dead code in production since before this phase. Fixing the shape alone would have made things worse: EInfo's own fieldlist has no entry for `sym`, the module's own canonical example, which IS a real working Entrez tag EInfo simply does not advertise. Both fixed together: the list shape is now parsed, and a small explicitly-labeled supplement admits `sym` alongside whatever EInfo actually lists |
| F-3.1-39 | closed | CRITICAL, found by round 2's adversary, the most serious finding of the day. NCBI's `[sym]`-tagged ESearch AND the Datasets `gene/symbol/{symbol}/taxon/{taxon}` endpoint both match on gene ALIASES, not only the exact approved symbol, so an "unambiguous" single-id match could be a confidently WRONG gene (live-verified: `HG38[sym]` resolves to LGR5, `MRI` to CYREN, `CAN` to NUP214, `ALL` to BCR). The existing ambiguity guard only catches multiple candidates, never one confidently wrong one. This is the fabricated-citation shape the whole cite-or-refuse gate exists to prevent, one layer upstream of where F-2.1-B10 looked. Both resolution paths now verify the returned record's own symbol field matches what was searched before trusting it |
| F-3.1-40 | closed | NEW, found by round 2's adversary. `ncbi_coordinate_overlap.py`'s dbVar accession and ClinVar uid, both from the untrusted ESummary body, were interpolated into `source_url` unencoded, the same defect class as F-3.1-36 in a sibling file. Now quoted through the same path-segment helper pattern |
| F-3.1-41 | open | Product decision, not a bug. The stopword list's "clinical acronym" entries (`ADHD`, `COPD`, `MRSA`, and others per a live audit) are themselves resolvable, approved NCBI gene symbols. Blocking them avoids the flagship "In ADHD, PTSD and OCD cohorts, is TP53 mutated?" case starving the lookup budget before reaching TP53; NOT blocking them would sometimes correctly resolve a real gene mention. F-3.1-39's fix makes the wrong choice here safe (no more false-gene fabrication either way) but does not resolve which choice is right. Left for the product owner rather than decided unilaterally |
| F-3.1-42 | open | Product decision, not a bug. A gene mentioned in lowercase (e.g. "what does brca1 do?") produces no candidate under the case-preserving fix, and because `unresolved_symbols` is also empty (nothing was attempted), the query falls through to `cypher_query` with no target entities instead of a clean refusal, reopening T-3.1-13/F-2.1-B10's opaque-failure shape one layer up. A case-insensitive fallback would fix this but reopens F-3.1-14 (ordinary lowercase English words would then burn live-lookup budget too). Left for the product owner |

### Minor findings from round 2, carried rather than fixed today

Round 2's adversary filed several more findings, all minor severity, none live-exploitable today, and none blocking. Fixing all of them in the same session that already closed two critical regressions, a soundness gap, and a dead-code bug risked exactly the kind of rushed, unverified change this whole day exists to catch. Recorded here rather than dropped, per `goal-contracts`' "no silent caps."

| ID | Summary | Target |
|----|---------|--------|
| F-3.1-43 | `ncbi_pubchem_actions.py` and `ncbi_datasets_actions.py` catch no `TransportError` at all, contradicting both the module docstring (added this round) and the dispatcher's own docstring. A routine timeout surfaces as "this action module has a defect that needs fixing" instead of an actionable retry message | Step 6.2 |
| F-3.1-44 | `search` and `coordinate_overlap` return opposite verdicts (`error` vs `empty`) for the identical inconsistent ESearch body (`count` nonzero, `idlist` empty). One of the two readings is wrong; nothing in the repo says which | Step 6.2 |
| F-3.1-45 | `resolve_symbol_to_curie`'s docstring claims it never raises, but `NcbiEfetchInput.model_validate` runs before `ncbi_efetch` is called and can raise `ValidationError` on an over-length symbol or taxon. Unreachable from `_resolve_query_entities` today (tokens cap at 10 chars) but reachable from any other caller of this public entry point | Step 6.2 |
| F-3.1-46 | `ncbi_coordinate_overlap.py`'s per-value character cap does not recurse into dicts, the same hole `ncbi_eutils_actions.py`'s cap was rewritten to close days earlier. Latent: no live dbVar/ClinVar field observed to actually nest a dict this deeply | Step 6.2 |
| F-3.1-47 | `_normalize_chromosome("chr")` (the bare prefix, no chromosome after it) returns `"CHR"` rather than failing closed, silently bypassing the F-3.1-35 blank-chromosome guard and putting a nonsense `CHR[CH]` term on the wire | Step 6.2 |
| F-3.1-48 | Hyphenated approved gene symbols (`HLA-DRB1`, `MT-CO1`) split into two bogus tokens at the hyphen and burn two live-lookup slots for nothing, since neither half alone is a real symbol. Same class of gene-recognition trade-off as F-3.1-41/F-3.1-42, pre-existing rather than introduced this round | Step 6.2, alongside F-3.1-41/42 |
| F-3.1-49 | `ncbi_datasets_actions.py` builds `NcbiEfetchRecord` with no `try/except ValidationError` around `gene_id`/`accession`, the same gap F-3.1-34 closed on the PubChem side. An over-length `gene_id` or an `accession` producing a `source_url` over 300 chars would raise out of `dataset_report` | Step 6.2 |

## Judge round 1, 2026-08-05: FAIL

A judge round returned FAIL. Findings below are all now FIXED but NOT closed: the fixer is never the closer, and a re-review closes them. Two findings stay open by design, one on a product-owner scope decision and one on a recommended fix not yet applied; the rest stay open pending the same independent close.

### F-3.1-02: the coordinate overlap filter never compared chromosome

Severity: critical. Status: fixed, needs an independent closer.

`ncbi_coordinate_overlap.py:511-520`, the candidate filter compared assembly and the overlap predicate but never the chromosome. Reproduced by the judge: a caller asking chr1:1,000,000-1,100,000 GRCh38 got back a record whose only placement is chr2:1,000,500-1,000,600 GRCh38, returned as status `ok` with a real host-pinned citation. The module's own docstring documents the ESearch prefilter as unreliable and re-verifies it in code, which is exactly why relying on it for chromosome was wrong: `_Placement` already carried the chromosome and simply never compared it. Fixed with normalized chromosome matching plus 5 unit tests and premise gate case 19.

### F-3.1-03: a transient NCBI failure was cached as a permanent non-resolution

Severity: critical. Status: fixed, needs an independent closer.

`core/graph.py:1043-1048` and `:1079-1086`, resolution cached every `None`, including a `None` caused by a transient NCBI timeout, connection failure, 5xx, or rate limit. A comment claimed `None` meant "an already-confirmed non-resolution", a property the code did not implement. Judge reproduced: one transient outage made TP53 permanently unresolvable for the life of the process, with only 2 calls made. This is the F-2.1-J5-01 pattern, a comment asserting what the code lacks. Fixed by returning a `(curie, cacheable)` pair so only a confirmed negative is cached.

### F-3.1-04: `ncbi_efetch` is never dispatched as an answer-bearing tool

Severity: critical. Status: open, awaiting a product owner scope decision. NOT fixed.

`ncbi_efetch` has exactly two call sites in the whole source tree, both inside entity resolution. `act_node` dispatches only `cypher_query`. No NCBI record becomes a citation, reaches the Write step, or is subject to cite-or-refuse. The tool schema sits in the stable prefix but is inert. The premise gate passes because it calls the tool directly through its `_run` helper, bypassing the agent loop. This is the same shape LEARNINGS.md records for build phase 3.1: a gate whose only production-path case is also its only skippable case tests the component and not the system.

### F-3.1-05: the Datasets resolution path omitted the ambiguity guard its own fallback enforces

Severity: major. Status: fixed, needs an independent closer.

`core/graph.py:1062-1067`, the Datasets resolution path took `records[0]` with no ambiguity guard, while the ESearch fallback twenty lines below explicitly refuses on more than one candidate with the comment "never fabricate a CURIE by guessing among candidates". The path tried first omitted the guard the fallback applied. Fixed by mirroring the guard.

### F-3.1-06: the unit suite made live NCBI calls

Severity: major. Status: fixed, needs an independent closer.

`tests/.../adapters/web_sse/test_streaming_endpoints.py:146`, the unit suite made live NCBI calls, proven by the judge with an `httpx` spy. The suite's green depended on NCBI being up and caused one spurious failure. Fixed with the missing stub plus a new session-scoped autouse guard in `tests/conftest.py` that hard-fails any outbound HTTP outside the premise gate.

### F-3.1-07: an unrecognized 2xx Datasets body silently read as empty rather than error

Severity: major. Status: fixed, needs an independent closer.

`ncbi_datasets_actions.py:316-320`, any 2xx body lacking a `reports` list collapsed to "empty", so a contract change or a 2xx proxy page was reported to the user as "no results". Fixed by allowlisting the live-verified empty body and failing closed to "error" otherwise.

### F-3.1-08: every PubChem record ships with `source_url=None`

Severity: major. Status: open. Not fixed.

`ncbi_pubchem_actions.py:204`, every PubChem record ships `source_url=None`, because the schema's host pattern does not admit `pubchem.ncbi.nlm.nih.gov`. The judge's adjudication: not a violation today since no PubChem record reaches synthesis, but it becomes one the moment it is wired, and the shipped pattern is narrower than `production-standards.md`'s own canonical example `^https://([A-Za-z0-9-]+\.)*ncbi\.nlm\.nih\.gov/`. Recommended fix is to adopt the rule's canonical pin. Not applied.

### F-3.1-09: a docstring claims a timeout enforcement path that does not exist

Severity: major. Status: open.

`ncbi_efetch.py:19`, a docstring claims "the Act step already wraps every tool invocation in `harness.enforce_timeout`", which is false as shipped, since `act_node` never dispatches this tool (F-3.1-04). A justification naming another layer is a claim about that layer, and it was not verified there.

### F-3.1-10: `_generic_summary_fields` copies untrusted content with no field-level filter

Severity: major. Status: open.

`ncbi_eutils_actions.py:541-549`, `_generic_summary_fields` copies every response key for five databases, bounded only by a 40-key cap, so untrusted external content flows toward the model unfiltered. The LEARNINGS.md row 56 blocklist shape: an unbounded field set is the wrong shape regardless of the count cap.

### F-3.1-11: the tool registry changed the stable prefix with no contract-version bump

Severity: major. Status: open.

`harness/cache.py:151-178`, the tool registry gained `ncbi_efetch`, changing the stable prefix, with no contract-version bump, which `system-design-patterns` pattern 10 requires.

### F-3.1-12: four minor gaps

Severity: minor. Status: open.

- A 429 from E-utilities lands in the unparseable-body branch with no `retry_after`.
- Four property-claiming comments with no enforcing test.
- No `start <= end` validator on the coordinate input.
- No per-value character cap in four of five field-extraction paths.

### F-3.1-01: the over-broad symbol pattern is a scheduled defect

Found 2026-08-05 during the stage 5 research pass, before any tool code was written. Filed here rather than left for the adversary because the ticket that arms it is in this phase.

`core/graph.py:885` runs `_GENE_SYMBOL_TOKEN_PATTERN` (`graph.py:846`, `\b[A-Z][A-Z0-9]{1,9}\b`) against `query_text.upper()`. Because the input is uppercased first, the pattern matches every 2-to-10-character word in the query rather than only symbols. Verified by running it:

```text
"What diseases are linked to TP53?" -> ['WHAT', 'DISEASES', 'ARE', 'LINKED', 'TO', 'TP53']
```

Today this costs nothing: six `dict.get` calls against a one-entry table. The moment T-3.1-11 replaces that table with a live NCBI lookup it becomes six live calls per query, five of them guaranteed misses, against a pool whose sustained ceiling is unresolved (`.claude/rules/tool-call-budgets.md` records the 3-versus-10-versus-100 conflict).

This is LEARNINGS.md row 38 verbatim: a known limitation that is currently dormant is not a limitation, it is a scheduled defect, and the thing that makes it dormant is usually another bug, so fixing that bug arms it silently.

The fix is NOT a wider table. It is a real candidate filter before any network call: drop English stopwords, require a shape heuristic, cap candidates per query, and short-circuit when an exact CURIE was already matched (`Tool_implementation_mechanics.md:272-277`, do not fuzzy-match an identifier that was already exact). Pinned by case 14 of the premise gate, which bounds resolution at 3 live lookups for a question containing ten ordinary words.

## Adversary round 1, 2026-08-05

An adversary round ran against the build phase 3.1 tool surface and filed 15 findings, all reproduced live. Every finding below is state OPEN. The adversary files, it never closes; a separate closer verifies and resolves each one.

### F-3.1-13: `summary` fabricates a citation for a nonexistent record

Severity: critical. Status: open, unfixed.

`tools/ncbi_eutils_actions.py:569-584`. `summary` emits a real, host-pinned, schema-valid citation for a record that does not exist. ESummary answers a nonexistent uid with HTTP 200 and a PER-UID error object: `{"result":{"uids":["999999999"],"999999999":{"uid":"999999999","error":"cannot get document summary"}}}`. The classifier sees envelope `result` and no top-level `ERROR`, so it returns ok. The extractor finds none of the allowlisted fields, discards the `error` string because it is not in the allowlist, and builds a record anyway. Observed: `summary db=gene ids=['999999999']` returns status ok, record_count 1, source_url `https://www.ncbi.nlm.nih.gov/gene/999999999`, fields `{}`. Same for pubmed and clinvar. A mixed batch `ids=['672','999999999']` returns real BRCA1 beside a fabricated citation, both ok, indistinguishable downstream. This is the wrong-record-right-citation shape the whole system exists to prevent, on the tool's most-used action. Not caught because the suite fixtures only the BATCH-level `{"result":{"ERROR":...}}` shape, never the per-uid shape NCBI actually returns.

### F-3.1-14: the live-lookup budget is consumed by ordinary English words

Severity: critical. Status: open, unfixed.

`core/graph.py:930` pattern, `:986` cap, `:1209-1225` loop. The live-lookup budget is consumed by ordinary English words, so the gene in the question is never looked up, and nothing tells the user. `_GENE_SYMBOL_TOKEN_PATTERN` runs against `query_text.upper()` and matches every 2-to-10-character word; `_MAX_LIVE_SYMBOL_LOOKUPS = 3` then breaks. Reproduced with resolution stubbed to resolve every real symbol, so the cap is the only possible cause: "Which small molecule inhibitors block ALK fusion?" looks up SMALL, MOLECULE, INHIBITORS and never tries ALK. "In ADHD, PTSD and OCD cohorts, is TP53 mutated?" never tries TP53. "Does chronic smoking increase EGFR mutation frequency?" never tries EGFR. Two compounding harms: `unresolved_symbols` reports SMALL, MOLECULE, INHIBITORS as gene symbols NCBI could not find, and that list is what the unresolved-entity refusal refuses on, so the user is told ordinary words are unknown genes while the real gene was never queried. A dropped gene appears in neither `curies` nor `unresolved_symbols`, so it is invisible in both directions with no truncation disclosure on this path.

Recorded explicitly because it changes how F-3.1-01 should be read: the earlier stopword fix was aimed at the wrong layer. The constraint is the pattern matching every word, not the completeness of the stopword list, since MUTANT, LUNG, CHRONIC, SMOKING, SMALL, MOLECULE and INHIBITORS are all ordinary English. Premise gate case 14 pins "3 lookups for a 10-word question" and passes while the behavior is wrong, which makes it a gate that measures the wrong property. Amplifier: non-ASCII input synthesizes candidates, since `ß` uppercases to `SS`, which matches the pattern and burns a lookup.

### F-3.1-15: `chr1` reports no variants for a window that has 17

Severity: critical. Status: open, unfixed.

`tools/ncbi_coordinate_overlap.py:214` and `:221` versus `:239-263`. Reports "no variants" for a real window when the chromosome is spelled `chr1`, the spelling its own normalizer claims to accept. `_normalize_chromosome` strips a `chr` prefix and is applied ONLY in the post-filter; `_build_search_term` interpolates the raw caller value, so `chr1[CH]` goes on the wire and dbVar matches nothing. Live, same window three spellings: chromosome `'1'` gives status ok, record_count 17, total_available 1892; chromosome `'chr1'` gives status empty, record_count 0; chromosome `'01'` gives status empty. Telling a clinician no structural variants overlap an interval when 17 do. `chromosome` has no format constraint and `chr1` is the more common spelling in genomics tooling. Related: `_chromosome_matches('MT','M')` and `('M','MT')` are both False, so mitochondrial queries silently return empty either way, and `_normalize_chromosome('chr')` returns empty string. Not caught because the unit tests mock the ESearch response, so the term actually sent is never exercised against a live index.

### F-3.1-16: ELink's real error shape is classified as no results found

Severity: critical. Status: open, unfixed.

`tools/ncbi_transport.py:372-374`, surfacing at `ncbi_eutils_actions.py:754-755`. ELink's real error shape is classified as "no results found". ELink puts `ERROR` at the TOP level and makes `linksets` a LIST: `{"linksets":[],"ERROR":"Invalid db name specified: notadatabase"}`. The matched envelope is a list, so `isinstance(envelope, dict)` is False and the ERROR check is skipped, giving status ok, and `link()` then returns empty. Observed: status empty, record_count 0, error None. A hard API error reported to the agent loop as a confirmed zero-result answer, and `dbfrom`/`db` are unvalidated free strings so a plan-tier typo yields "there are no linked publications". Not caught because the test fixtures `{"linksets": {"ERROR": ...}}` with `linksets` as a DICT, a shape NCBI does not emit. Recorded explicitly: the test invented the shape that would have passed.

### F-3.1-17: taxon is accepted and discarded, returning the wrong species' gene

Severity: critical. Status: open, unfixed.

`core/graph.py:1064-1071` cache key, `:1109-1117` hardcoded `human[orgn]`. `resolve_symbol_to_curie` accepts a taxon, discards the correct cross-species answer, and returns the human gene. The Datasets branch honours taxon but requires `taxname == "Homo sapiens"`; anything else falls through to an ESearch hardcoded to `human[orgn]`. Traced live: `dataset_report symbol=TRP53 taxon=mouse` returns the correct id 22059, symbol Trp53, Mus musculus, and that record is thrown away. `resolve_symbol_to_curie('TRP53', taxon='mouse')` returns NCBIGene:7157, human TP53. This is build phase 2.1's ortholog failure re-created one layer up, in resolution instead of generation. Separately the cache key omits taxon, so `BRCA1` resolved for human returns from cache for mouse with zero network calls. Not caught because no test calls the function with a non-default taxon.

### F-3.1-18: unencoded query-string separators let caller values inject parameters

Severity: major, a security finding. Status: open, unfixed.

`tools/ncbi_transport.py:698`. Caller-supplied values inject arbitrary parameters into every E-utilities URL, confirmed honoured live. `quote(str(value), safe=":/=?&|+")` leaves `&` and `=` unencoded, so any value can append parameters. Live proof one: term `'BRCA1[sym] AND human[orgn]&retstart=500'` returns record_count 0 against a control of 1. Live proof two: `ids=['672&linkname=gene_pubmed_rif']` on a gene-to-pubmed link changes total_available from 7503 to 3006, and the module's own `dbto == params.db` guard still passes because the injected linkname still targets pubmed, so direct cross-references are silently swapped for the GeneRIF set with output that is indistinguishable. That reopens the module's own documented trap 3 through a different door. Path-segment values in the Datasets and PubChem modules correctly use `safe=""`; only the query-string builder is loose.

### F-3.1-19: HTTP status codes are never read

Severity: major. Status: open, unfixed.

`tools/ncbi_eutils_actions.py:436-444`. The E-utilities path never reads `response.status_code`, so a 429 or 503 becomes a misleading non-actionable message and a 4xx with a good-looking body becomes status ok. Stubbed: HTTP 429 twice yields error "E-utilities response body is neither recognizable JSON nor XML ... refusing to guess its meaning". HTTP 503 identical. HTTP 400 carrying a valid-looking esearchresult yields status ok with record_count 3. Two defects: a server-side 429 or 5xx is reported as "your body was unparseable", pointing the next step at rewriting the request when the correct action is back off and retry, and `TransportRateLimitedError` with its family and retry_after is raised only by the CLIENT-side limiter, so a real NCBI 429 can never produce it, which `tool-call-budgets.md` explicitly forbids. The adversary hit this for real when a genuine HTTP 500 surfaced as that same string. No non-2xx fixture exists in the tests.

### F-3.1-20: `fetch` on its own default schema returns one uncited multi-record blob

Severity: major. Status: open, unfixed.

`tools/ncbi_eutils_actions.py:653-663` and `:686-689`, defaults at `ncbi_efetch_schemas.py:212-213`. `fetch` on its own schema defaults returns one uncited multi-record blob and misreports record_count. Defaults are `rettype=docsum, retmode=json`, which for pubmed returns ESummary-shaped JSON, so the XML branch fails and the generic extractor builds ONE record holding the entire payload with id None and source_url None. Observed: 20 PMIDs give status ok, record_count 1, truncated False, source_url None, a 23,696 character blob containing all 20 records. Three problems: zero citations for 20 real articles passing the cite-or-refuse gate as ok, record_count 1 for 20 records, and `_cap_text` is never applied here, confirmed by a 200,000 character value surviving uncapped, violating the bounded-context-items gate. Every fetch test passes `retmode=xml` explicitly, so the default combination is untested.

### F-3.1-21: PubChem confuses total failure with a clean empty result, and silently drops CIDs

Severity: major. Status: open, unfixed.

`tools/ncbi_pubchem_actions.py:334-348` and `:325`, `:350-357`. PubChem returns empty for the exact failure the cid path returns error for, and silently drops resolved CIDs. `lookup_type=name value=aspirin properties=['NotARealProperty']` gives status empty with error None, while `lookup_type=cid value=2244` with the same bad property gives status error "Invalid property". The name path resolves the CID, every fan-out property fetch 400s, each is swallowed by a `continue`, and all-fail collapses to empty. The graceful-degradation comment is right when some fetches succeed and wrong when all fail, and the code does not distinguish. Separately `cids[:5]` discards the remainder while `truncated` is computed as `len(records) > 100` and `total_available` is None, so 40 resolved CIDs report truncated False.

### F-3.1-22: a retry issues a second request without a second rate-limiter acquisition

Severity: major. Status: open, unfixed.

`tools/ncbi_transport.py:787-789` versus `:824-861`. One rate-limiter acquisition, two HTTP requests: the retry escapes the pool. Counted with a stub: one `execute_get` issues 2 requests against a 0.333 s pacing interval. Usually survives by accident because the backoff is 1.0 s, but the retry is triggered BY a 429, so the moment NCBI rate-limits us the code issues a second unpaced request into the pool it is being throttled out of, and raising `NCBI_EUTILS_RPS`, which the module invites, makes the burst real. Nothing asserts requests-per-acquisition.

### F-3.1-23: field tags scope only the last token of a multi-word term

Severity: major. Status: open, unfixed.

`tools/ncbi_eutils_actions.py:296-313`. `_apply_field_tags` scopes only the last token of a multi-word term, contradicting its own docstring. `_apply_field_tags("BRCA1 AND cancer", ["sym"])` gives `'BRCA1 AND cancer[sym]'`, so Entrez binds `[sym]` to the adjacent token only and BRCA1 runs unscoped across every indexed field. The two-tag form gives `'(BRCA1 AND cancer[sym] OR BRCA1 AND cancer[titl])'`, which Entrez reads with different precedence than intended. Same class as trap 1 in `docs/ncbi/Tool_implementation_mechanics.md`: a search the tool believes is scoped silently returning broad hits, arriving through a VALID tag. The term also escapes its own bracket: `_apply_field_tags("BRCA1] OR cancer[titl", ["sym"])`. No test exists; grep returns nothing and the only field_tags tests use single-token terms.

### F-3.1-24: `total_available` reports the coarse prefilter count the module itself discredits

Severity: major. Status: open, unfixed.

`tools/ncbi_coordinate_overlap.py:480-487` and `:576-583`. `total_available` is the count from the prefilter the module exists to discredit. Observed record_count 17, total_available 1892, truncated True, where only 20 candidates were ever place-checked and 1892 is the coarse ESearch count the module's own docstring proves returns wrong-assembly matches. A reader takes it to mean 1892 variants overlap. The honest disclosure, 20 of 1892 candidates checked and 17 confirmed, is not expressible in the current output shape.

### F-3.1-25: `record_count` means different things per action, and `search` bypasses the maxItems cap

Severity: minor. Status: open, unfixed.

`tools/ncbi_eutils_actions.py:493-503`. `record_count` means different things per action and `search` bypasses the records maxItems cap: for search `record_count = len(idlist)` while `len(records) == 1`, and a 500-id search puts 500 ids past a `max_length=100` the schema believes it enforces, since `_cap_fields` caps key count not list length.

### F-3.1-26: a zero-id search reports ok and permanently poisons the symbol cache

Severity: minor. Status: open, unfixed.

`ncbi_eutils_actions.py:496-503` consumed at `core/graph.py:1125-1136`. A zero-id search is status ok, and that answer permanently poisons the symbol cache. Body `{"count":"7","idlist":[]}` gives status ok because empty is reserved for count 0, then resolution reads the empty idlist, takes the not-exactly-one branch, and caches a real gene as a confirmed non-resolution for the process lifetime. F-3.1-18's injection reaches this state deliberately. Related: a comment claims a cached None means both APIs answered, but only `search_output.status` is checked, so a Datasets error still yields cacheable True.

### F-3.1-27: `coordinate_overlap` accepts inverted, negative and zero-length windows

Severity: minor. Status: open, unfixed.

`ncbi_efetch_schemas.py:265-270`, predicate at `ncbi_coordinate_overlap.py:266-268`. `coordinate_overlap` accepts inverted, negative and zero-length windows with no validation. `start=2000, end=1000` is accepted and produces `'1[CH] AND 2000:1000[BASE]'`. An inverted window makes the predicate False for everything, so it degrades to a confident status empty. A dbVar 0 bp insertion where `chr_end = chr_start - 1` is dropped by a single-base window.

### Attacked and found solid

Negative evidence is evidence. The following held under attack:

- Path-segment quoting in the Datasets and PubChem modules, using `safe=""`.
- The Datasets `reports` allowlist failing closed, confirming that earlier fix (F-3.1-07) genuinely landed.
- EInfo-backed field_tags validation rejecting before any request.
- `fetch` with explicit `retmode=xml` on a nonexistent PMID returning empty with no fabricated citation.
- The XML classifier failing closed on truncated bodies, HTML error pages and unrecognized roots, and the bare-DOCTYPE correction behaving as intended.
- The record URL pattern rejecting the eutils and api hosts.
- The coordinate assembly prefix match and the chr2-answering-chr1 guard behaving as documented when the chromosome reaches the index.
- No secret leakage anywhere across every probe.

### Next target

The adversary's stated next target: `_generic_summary_fields` as an untrusted-content channel, since it copies arbitrary upstream keys with no per-value length cap and no escaping into `NcbiEfetchRecord.fields`, is the default path for five databases and every non-XML fetch, and becomes live the moment the tool is wired into `act_node`.

## History

- 2026-08-04 lead: phase opened immediately after 3.0 merged as PR #19. Dependencies 2.0 and 3.0 both verified `done` on the board. Section 6.2 and the tool-mechanics trap list read. Twelve tickets decomposed. Branch cut. Stage 5 not yet started, and no tool code exists.
- 2026-08-05 lead: branch synced with `main`, which had moved two merged pull requests ahead (#20, #21) since the branch was cut. Left unsynced, the phase pull request would have read as reverting both. Doc drift clean afterwards at 0 stale, 0 structural.
- 2026-08-05 lead: stage 5 complete. Premise gate written at 16 cases and watched failing at 15 failed, 1 skipped, with every failure confirmed to be in the correct direction rather than assumed to be. Three decomposition gaps found by the research pass and closed before any builder was dispatched: F-2.1-B10 had no owner (now T-3.1-13), and T-3.1-11 was carrying two unnamed obligations, the candidate filter and the async ripple. One new finding filed, F-3.1-01, a dormant defect this phase's own T-3.1-11 arms.
