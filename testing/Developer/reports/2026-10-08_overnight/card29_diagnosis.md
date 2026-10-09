# Card 29 diagnosis: the one answering sentence under each cited paper

Diagnosis only, 2026-10-08 overnight, read against `develop` at `c916cfa3` and the local tag `parked/phase-8.8-snippets-2026-09-25`. Paths are relative to `<repo-root>`. No code was changed and no model was called. The trial merge used `git merge-tree`, which touches no working tree.

## Table of contents

- [Status today](#status-today)
- [What a person sees](#what-a-person-sees)
- [What is parked and what lifts cleanly](#what-is-parked-and-what-lifts-cleanly)
- [What is not built at all](#what-is-not-built-at-all)
- [The smallest fix](#the-smallest-fix)
- [Overlap with phase 8.7 and the guardrail](#overlap-with-phase-87-and-the-guardrail)
- [Needs the owner](#needs-the-owner)
- [Proposed test query](#proposed-test-query)

## Status today

Not on develop. Nothing in `src/` or `frontend/src/` on develop carries a snippet. The parked work is five commits on a base 742 commits behind develop (base `2c6374f3`, 2026-09-25):

| Commit | What |
|---|---|
| `4baec209` | `synthesis/snippets.py`: the sentence splitter and the model pick |
| `5cfa7f28` | `CitationPayload.snippet`, optional, 500 characters at most |
| `053a9287` | The source card shows the sentence; the source merge keeps it |
| `a076c298` | Tests: `test_snippets.py`, `test_citation_snippet.py`, `AnswerScreen.sourceSnippet.test.tsx` |
| `39f71b2b` | Builder M's report |

The feature is approved: `DECISIONS.md` rows of 2026-09-25 ("Answer on top, evidence below", and the row that moved card 44's goal to the paper's own abstract).

## What a person sees

Today: under each cited paper in the sources list, only its title, number and layer. To learn why a paper was cited, the person opens it and reads the abstract.

With this card: one quoted sentence from that paper's own abstract under its title, the one that answers the question, visible without opening the card.

## What is parked and what lifts cleanly

Trial merge of the tag into develop (`git merge-tree --write-tree develop parked/phase-8.8-snippets-2026-09-25`):

| File | Result | Why |
|---|---|---|
| `src/system_03_search_agent/synthesis/snippets.py` (new) | Lifts cleanly | New file. Its one dependency, `harness.decide.decide(harness, trace_id, point, state, options, *, instructions, criteria, default)`, has the same signature on develop (`harness/decide.py:420`). |
| `src/system_03_search_agent/contracts/events.py` | Auto-merges | Adds `snippet: str or None, max_length=500` to `CitationPayload` (develop's class at line 421). |
| `frontend/src/lib/events.ts`, `frontend/src/hooks/useRunView.ts` | Auto-merge | Wire-field plumbing: 10 changed lines in `events.ts`, 4 in `useRunView.ts`. |
| The three test files (new) | Lift cleanly | New files. |
| `tests/system_03_search_agent/fixtures/debugging_guide_manifest.json` | Auto-merges | One row. |
| `docs/build/Debugging_guide.md` | Conflict | One table row; trivial to redo. |
| `frontend/src/components/screens/AnswerScreen.tsx` | Conflict, three hunks | Card 22 rewrote `groupSourcesByLayer` on develop: sources now merge by page key (`sourcePageKey`), across layers, with a primary citation per layer. The parked backfill was written against the older merge by URL and has to be rewritten: the merged card takes the first non-empty snippet among its citations. The source card's header was also restructured (markers, name and a layers label), so the parked `<Typography>` for the sentence must be placed again under the name. |

Two cautions on the parked splitter:

- It protects a fixed list of abbreviations (`_ABBREVIATIONS`, line 89 of the tagged file). "S. Typhimurium" and "U.S. FDA" are the same gap card 101 found (A4-101-01). A split there leaves a short piece, which the 8-word minimum drops, so the harm is a lost candidate, not a wrong sentence.
- Its tests were last run against the 2026-09-25 tree. They have not been run against develop.

## What is not built at all

The hookup in `core/graph.py`, which builder M's report names as still needed:

| Piece | Where on develop |
|---|---|
| Split each cited paper's abstract | The abstract text is `record.fields["abstract"]`, read in `_pubmed_abstract_rows` (`core/graph.py:7591`, called at 7991). |
| Ask which sentence answers the question, once per paper with an abstract | `snippets.pick_snippet`, one `decide()` per paper. `harness/jev_client.py:589`, `call_jev_batch`, can send several questions in one call, which the parked code does not use. |
| Put the chosen sentence on the paper's citation | Citation assembly, `_citations_from_grounded_claims` (`core/graph.py:10667`), inside the write step. |
| Run it beside the writer, not after it | `write_node`, so the pick adds no wait. Jev measured 343 to 611 ms per call. |

## The smallest fix

| Field | Value |
|---|---|
| Files and functions | Lift `synthesis/snippets.py`, the `CitationPayload.snippet` field, `lib/events.ts` and `useRunView.ts` plumbing, and the three tests. Redo by hand `AnswerScreen.tsx` `groupSourcesByLayer` and the source card header. Build new: in `core/graph.py`, `write_node` starts one batched pick for the cited papers alongside the writer, and `_citations_from_grounded_claims` attaches each result to that paper's abstract citation. |
| Answer path | Yes: what a reader sees under each source, and one more decision in the write step |
| Dial position | 3: an additive event-schema field (`CitationPayload.snippet`) |
| Size | M for the lift and the redone source card; L with the `core/graph.py` hookup and its 1280 and 390 pixel checks |
| Migration, package, event schema | No migration, no package. One additive optional field on the citation event. A saved answer reopened later has no snippet unless saved answers store it; check `core/session_memory.py` before building. |

## Overlap with phase 8.7 and the guardrail

| Fence | Phase 8.7 | Guardrail |
|---|---|---|
| `core/graph.py` `write_node` and citation assembly | Yes: `write_node` is rewritten tonight | None |
| `harness/decide.py` (the pick's seam) | Yes: rewritten tonight; the `decide()` signature may change | None |
| `harness/jev_client.py` (for a batched pick) | No | Yes |
| `frontend/src/hooks/useRunView.ts` | Yes | Yes, `FATAL_COPY` in the same file |
| `components/screens/AnswerScreen.tsx` | Yes | None |

Heavy overlap. Build after 8.7 and the guardrail merge, against their code.

## Needs the owner

The feature and its look are decided. One cost and speed choice is open and is the owner's: how many papers get a sentence per answer (builder M proposed the first 5 papers with an abstract), and whether a batched pick may add a Jev call to every literature answer. Each call is about $0.00002, and it runs beside the writer so it should add no wait; that has to be measured against the 20-second ceiling.

## Proposed test query

Proposed entry 109, for section 1 of `testing/Test_queries_and_workflows.md`:

```markdown
### 109. Each cited paper shows the sentence that answers the question (card 29, 13.1)

Queries to try:

- `What are the typical symptoms and risk factors of GERD?` in Researcher
- `papers on the effects of caffeine on exercise performance` in Plain language
- Both at 1280 and 390 pixels wide

What you should see:

- Under a cited paper's title, one quoted sentence from that paper's own abstract that bears on the question, readable without opening the card.
- A paper with no abstract, or none that answers, shows no sentence and no empty line.
- The sentence is word for word what the abstract says; the answer above it is unchanged.
- Why it matters: a reader can see why each paper is cited without opening thirty abstracts.
```
