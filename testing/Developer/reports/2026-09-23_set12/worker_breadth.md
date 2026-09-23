# Item 12.1: a disease question searches every layer

VERDICT: DONE for the disease-anchored defect. `Any trials for GERD?` now returns cited ClinicalTrials.gov trials, `GERD` answers instead of refusing, and three of the seven tester questions move from no citation to a cited answer. The other four fail upstream of this fix, in entity resolution, and are recorded below rather than closed.

## Table of contents

- [What a person sees now](#what-a-person-sees-now)
- [What I changed, and why](#what-i-changed-and-why)
- [The constraint, and the way through it](#the-constraint-and-the-way-through-it)
- [The determinism proof](#the-determinism-proof)
- [What a disease question spends](#what-a-disease-question-spends)
- [The seven questions, before and after](#the-seven-questions-before-and-after)
- [Tests](#tests)
- [One test changed, and which of the three cases it was](#one-test-changed-and-which-of-the-three-cases-it-was)
- [What I could not close](#what-i-could-not-close)

## What a person sees now

Typed before this change, `Any trials for GERD?` returned "I could not find grounded evidence for this", with a link to NCBI's cross-database search for `MedGen%3AC5563728`. The registry holds thousands of GERD trials and nobody asked it.

Typed now, the same question returns five ClinicalTrials.gov studies, the MedGen record for the condition, and five papers, every one cited to its own page. The wait line names the disease in words, "searching 3 layers for gastroesophageal reflux", not as a concept id.

Typed on its own, `GERD` returns an answer rather than a refusal: MedGen's own record, papers, trials.

## What I changed, and why

Two gates, both in `core/graph.py`, opened for a disease the same way they were already open for a gene.

`src/system_03_search_agent/core/breadth_plan.py`:

- `disease_search_text(title)`: the one normalised string a disease question searches on, so its three calls (PubMed term, trials condition, PubTator3 lookup) can never disagree about which disease they are about.
- `_normalise_title` now drops a balanced parenthesised segment WHOLE rather than deleting its brackets. Measured: MedGen's name for C5563728 is `Gastroesophageal reflux (GERD)`, and unbracketing leaves `gastroesophageal reflux gerd`, a phrase no paper or trial record contains. The search would have looked fixed and found nothing.
- `build_medgen_term`, `plan_disease_search`, `plan_medgen_follow_up`: the disease's own MedGen record, the live-record leg of a disease question's breadth, the counterpart of `plan_gene_summary`. A search then a summary, not one call, because a MedGen CONCEPT id is not an E-utilities uid: `synthesis/disease_names` measured NCBI rejecting an ESummary keyed on one outright, and the uid the record page is addressed by only exists in the search result.
- `plan_first_stage`'s title-only path had no caller until today. It now has one.

`src/system_03_search_agent/core/graph.py`:

- `_first_disease_curie`, the disease counterpart of `_first_gene_curie`.
- `_disease_search_text`, which awaits `synthesis.disease_names.resolve_concept_ids` on the resolved CURIE and normalises what comes back. That function already existed, is cached for a week in-process, goes through the shared `eutils` pool and the per-query ceiling, and never raises or invents a name.
- `_build_layer_tool_calls` takes a `disease_text` and plans the PubTator3 lookup and the trials search on it when no gene resolved. The symbol still wins outright.
- `_build_breadth_calls` takes `disease_title` and `disease_curie` and plans the MedGen record pair plus the PubMed search and its follow-ups. ClinVar, OMIM and GEO stay gene-only: each of those terms is a gene field or a bare symbol.
- `_BREADTH_FOLLOW_UPS` gains `medgen_search -> medgen_summary`; `_follow_up_planned_call` gains its branch; `_BREADTH_FIELDS_BY_PURPOSE` gains `medgen_summary: (title, definition, semantictype)`.
- `_unwrap_medgen_fields`, and its call site. NCBI returns MedGen's `definition` and `semantictype` as one-key wrapper objects, `{"value": "..."}`, and `{}` when the concept has none. Left wrapped, the definition could never be cited, because `grounding.ground_claim` matches a clause against source TEXT by containment, and an empty one would have read as `definition: {}` to the person asking. Named field by field rather than a generic unwrap, because ClinVar's `germline_classification` has the same shape and `ncbi_eutils_actions` deliberately passes that one through untouched.
- The plan narrative names the disease in words for a disease question, as it already named the gene CURIE for a gene question.

## The constraint, and the way through it

`_build_breadth_calls` refused a disease title on a real ground: the only disease text Plan held was the model-extracted mention, whose boundaries move between runs of one question, and item 11.21 promised the same question shows the same number and set of sources.

No mention is passed. What is passed is the MedGen record's own preferred name, read live from the CURIE Think already confirmed. Both halves were measured on 2026-09-23 before any code was written:

| Probe | Runs | Result |
|---|---|---|
| `resolve_disease_mention_to_curies("GERD")` | 3, cache cleared each time | `['MedGen:C5563728']`, matched=1, identical |
| `resolve_disease_mention_to_curies("reflux disease")` | 3, cache cleared each time | the same 8 CURIEs in the same order, matched=20 |
| `resolve_concept_ids(["MedGen:C5563728"])` | 3, cache cleared each time | `Gastroesophageal reflux (GERD)`, identical |

The blocked-stop the brief named did not fire: a live MedGen summary does give a stable preferred name for a CURIE, so nothing was substituted from the model's span.

A gene question is untouched. `_build_breadth_calls("BRCA1", disease_title=..., disease_curie=...)` plans byte-identical calls to `_build_breadth_calls("BRCA1")`, which an arm pins directly. Narrowing a gene question's literature search by a disease as well would change every gene question's source set, which is a separate decision with its own evidence to gather.

## The determinism proof

Run, not asserted. Three runs of the planning path with both caches cleared each time, so each run re-read MedGen live rather than replaying the first run's answer:

```
run 0: disease_text='gastroesophageal reflux' calls=7
run 1: disease_text='gastroesophageal reflux' calls=7
run 2: disease_text='gastroesophageal reflux' calls=7
IDENTICAL ACROSS 3 RUNS: True
CONTROL, a different disease differs: True 'gastroesophageal reflux disease'
```

Compared on tool, layer, purpose, source_purpose and the full serialised input, excluding `call_id`, which is a fresh uuid per run by design. The control line is the arm's populate check: a different concept plans a different set, so the equality above is a property of the resolution rather than of the comparison being empty.

Offline, `test_three_runs_of_one_disease_question_plan_and_cite_the_same_set` runs the whole loop three times with the fakes returning PMIDs in a different order each run, and compares the plan's tool list and the citation source set.

## What a disease question spends

The Section 21.3 ceiling of 20 Layer 2 and Layer 3 calls per query is respected and was not raised.

| Question | Layer 2/3 calls used, live | Of 20 |
|---|---|---|
| `GERD` | 11 | 55 percent |
| `Any trials for GERD?` | 11 | 55 percent |
| `reflux disease` | 13 | 65 percent |
| a gene question, for comparison | 14 to 16 | unchanged |

The 11 breaks down as: 2 that Think already spent resolving the mention against MedGen, 2 that `_disease_search_text` spends reading the preferred name, and 7 planned (PubTator3 lookup, trials search, MedGen search, PubMed search, PubMed abstracts, PubTator3 publications, MedGen summary). Nothing is displaced, so the ordering question the brief raised does not arise; the disease's own record is nonetheless planned first, so under a ceiling it would be the last call admission skipped.

## The seven questions, before and after

Run once, live, sequentially, one question at a time so the shared rate pools are never contended. Transcripts and `runs.jsonl` are in `testing/Developer/reports/2026-09-23_set12/breadth_runs/`. I wrote into set 12's own folder rather than over `2026-09-23_user_feedback/`, which another worker owns.

| # | Question | Before | After |
|---|---|---|---|
| 1 | reflux disease | answered, graph only | answer, 28 citations, 8 tools, 25.9 s |
| 2 | GERD | refuse, 0 citations | answer, 20 citations, 8 tools, 18.9 s |
| 3 | Any trials for GERD? | refuse, 0 citations | ask, 20 citations including 5 trials, 8 tools, 26.6 s |
| 4 | papers on the effects of caffeine on exercise performance | refuse, 0 citations | refuse, unchanged |
| 5 | Does coffee help make exercise more effective? | refuse, 0 citations | refuse, unchanged |
| 6 | Are there any beneficial variants typically found in people of mediterranean descent? | refuse, 0 citations | refuse, unchanged |
| 7 | What positive and negative genes do ashkenazi jewish people have? | refuse, 0 citations | refuse, unchanged |

I read the per-tool status rather than the row count. The four refusals are NOT a transport error dressed as an empty result: each carries `resolved_entities: []` and the deterministic message "no entity could be identified in this query", which is the unresolved-entity refusal firing by design, not a `ConnectTimeout`. Question 5 planned no tool at all.

## Tests

`tests/system_03_search_agent/core/test_disease_breadth.py`, new, 33 cases. `tests/system_03_search_agent/core/test_breadth_plan.py`, one case updated (see below).

Every arm that asserts something is absent carries a populate check beside it, so an arm cannot pass because nothing ran. Each new arm was proven able to fail, by mutation rather than by reading:

| Mutation | Arms that went red |
|---|---|
| `search_text = gene_symbol` (the pre-fix routing) plus `title = None` | 9, including all four end-to-end arms |
| the MedGen unwrap call site deleted, and the parenthetical unbracketed rather than dropped | 6 |

Under the first mutation the gene-path-unchanged arm stays green, which is correct: that mutation IS the pre-fix behaviour and the gene path was never supposed to move.

Results, reported honestly:

- `python -m pytest tests/system_03_search_agent/core/ -x -q`: 1020 passed, 59 skipped, 0 failed.
- The whole Python suite: 5595 passed, 178 skipped, 1 xfailed, 0 failed, in 4 m 35 s. This tree also carries two other workers' in-flight changes to `guardrail/prefilter.py` and `guardrail/classifier.py`, so that figure is the combined state rather than mine alone.
- `ruff check` on my four files: clean. `ruff check .` over the repository reports 4 errors, all of them in two report scripts I do not own, `testing/Developer/reports/2026-09-23_set12/probe_guard_verdicts.py` and `testing/Developer/reports/2026-09-23_user_feedback/run_feedback_questions.py`. CI gate 3 is `ruff check` with no path, so these will fail the gate for whoever ships next.
- CI gate 2, `.github/gates/gate02-isort.sh`, exits 0 both with and without my change.

## One test changed, and which of the three cases it was

`test_pubmed_term_strips_operator_characters_from_a_title` expected `(x)` to lose its brackets and keep its `x`. It now expects the parenthesised segment to be dropped whole.

Of the three cases `goal-contracts` names, this is the first: the SUBJECT changed, deliberately, and the check was pinning the old subject. The old behaviour was correct while nothing passed a disease title, which was true until today. It is not a weakened check: the arm still asserts an exact string, and an arm was ADDED beside it pinning that an unbalanced bracket is still removed as a character while its text survives, so nothing that carries meaning in a PubMed term escapes either path. The docstring records the change and the reason in the file.

## What I could not close

- QUESTIONS 4 TO 7 STILL REFUSE, and not for a routing reason. Think resolves no entity of any kind, so there is no anchor for any search: question 4 and 5 name a chemical (caffeine, coffee), question 6 and 7 name a population (Mediterranean descent, Ashkenazi Jewish). The product has a gene resolver and a disease resolver and nothing else, so a chemical or a population span is dropped and the run refuses with "I could not tell which gene, variant, disease or organism you mean". This is upstream of Plan and is a different item from 12.1. From the user's chair the refusal is at least honest and says what to type next, but four of seven ordinary questions is the bigger remaining hole.
- TWO SYNONYMS STILL SEARCH SLIGHTLY DIFFERENT TEXT. `GERD` resolves to C5563728 and searches `gastroesophageal reflux`; `reflux disease` resolves to C0017168 first and searches `gastroesophageal reflux disease`. Each question searches the record it actually resolved, which is honest, and both now answer, which is the defect closed. But a reader typing two names for one condition still gets two source sets. Closing that means changing which concept a mention binds to, which is Think's resolution rule, not this routing.
- LATENCY. A disease question now takes 19 to 27 seconds where a refusal took 13. That is the existing no-ticket-owns-it item from build phase 6.2, not new, but this change moves these questions into its range.
- THE TRIALS SHOWN ARE THE FIVE LOWEST NCT IDS out of a page of 50, which for GERD means studies registered around 2005. That is `_CLINICALTRIALS_PAGE_SIZE`'s deliberate consistency-over-relevance rule from item 10.1 and applies identically to gene questions; I did not change it, but a person asking "any trials for GERD?" would probably rather see recruiting ones.
- I TOUCHED NOTHING under `guardrail/` or `frontend/`. No change is needed there for this item.
