# Phase 3.1: ncbi_efetch, the general Layer 2 client

Build phase 3.1 delivers the first Layer 2 tool: one tool, seven actions, across three API families with two incompatible error conventions.

Depends on: build phase 2.0 (done, PR #9) and build phase 3.0 (done, PR #19)
Branch: `phase/3.1-ncbi-efetch`
Spec: `requirements/Technical_specification.md` Section 6.2, with Section 21.1 for rate limits
Reference: `docs/ncbi/Tool_implementation_mechanics.md`, `.claude/rules/tool-call-budgets.md`, `LEARNINGS.md`'s build phase 2.1 retrospective

## Phase premise (the done-when)

A question the graph cannot answer reaches a live NCBI API, comes back as real records, and is either cited from what the API actually returned or refused, and a question about a gene the system has never been told about resolves to the right gene.

The second half is the one a reader will underestimate. `_KNOWN_GENE_SYMBOL_CURIES` (`core/graph.py:839`) holds exactly one entry, `BRCA1`, so today "What diseases are linked to TP53?" resolves nothing and answers nothing. That is finding F-2.1-07, this phase owns it, and it is what stands between this repo and a prototype that can be shown to anyone.

The verify surface is `tests/system_03_search_agent/tools/test_ncbi_efetch_premise.py`, not a suite total.

## Phase status: OPEN, stage 3

Opened 2026-08-04, immediately after build phase 3.0 merged.

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
| T-3.1-11 | F-2.1-07: real gene-symbol resolution, replacing the one-entry table | `core/graph.py` |
| T-3.1-12 | Tool registration, and the schema's place in the stable prompt prefix | `core/graph.py`, `harness/cache.py` |

## Recommended build order, and why it is not the ticket order

T-3.1-01, then T-3.1-02 and T-3.1-03, then T-3.1-04, T-3.1-05 and T-3.1-11, then the rest.

The reason is the demo. F-2.1-07 needs exactly one path to work: a gene symbol resolved to an NCBIGene id, which `dataset_report`'s `gene/symbol/{symbol}/taxon/{taxon}` endpoint does directly and which `search` plus `summary` on the `gene` database does as a fallback. Everything else on this tool (`fetch`, `link`, `coordinate_overlap`, `pubchem_property`) is real v1 scope and none of it is on the path between here and a system a person can be shown.

This is a sequencing choice inside the phase, not a scope reduction. Every ticket above is built before this phase closes. Nothing on the Section 6.2 list is being dropped, deferred, or quietly renamed, which `.claude/rules/v1-scope-boundary.md` would forbid.

## Premise gate design

Not yet written. Stage 5 is BLOCKING and applies here: `docs/build/Build_workflow_cadence.md` names every tool phase from 3.1 to 3.5 as requiring it, and this tool's output feeds the same synthesis path 2.2 built.

What it must do differently from 3.0's gate, since the failure modes are different:

- It calls the LIVE NCBI APIs, so its ground truth is a real record read at a real moment. Records change, so every pinned value carries the date it was read and a note on what to do when it moves (re-verify, never weaken).
- It must exercise both error conventions on purpose. A gate that only tests the happy path cannot see the HTTP-200-with-an-error-body trap, which is the single most load-bearing finding for this tool.
- It must include the F-2.1-07 case directly: a question about a gene that is NOT `BRCA1`, resolving correctly end to end. That is the phase's own reason for existing and the assertion a green suite will not make for us.
- It must state its own coverage, per `.claude/rules/goal-contracts.md`: which of the seven actions and which of the fourteen databases it exercises, and which it does not.

## Findings

None yet.

## History

- 2026-08-04 lead: phase opened immediately after 3.0 merged as PR #19. Dependencies 2.0 and 3.0 both verified `done` on the board. Section 6.2 and the tool-mechanics trap list read. Twelve tickets decomposed. Branch cut. Stage 5 not yet started, and no tool code exists.
