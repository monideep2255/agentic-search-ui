# Search and conversation behaviour

What the search agent does with a question, stated as the five situations a person actually puts it in. Written for the product owner and for anyone testing on develop, on 2026-09-13, at the product owner's request after UI fix set 7, and extended on 2026-09-23 with the fifth, a question that names nothing the product can resolve. Each situation names the code that decides it, so a claim here can be checked rather than trusted.

## Table of contents

- [The five situations](#the-five-situations)
- [Known item search](#known-item-search)
- [Continuing the discussion](#continuing-the-discussion)
- [Changing the subject](#changing-the-subject)
- [A reference with nothing behind it](#a-reference-with-nothing-behind-it)
- [A subject with no identifier behind it](#a-subject-with-no-identifier-behind-it)
- [The firewall: memory guides retrieval, never assertion](#the-firewall-memory-guides-retrieval-never-assertion)
- [How to check each one on develop](#how-to-check-each-one-on-develop)

## The five situations

| Situation | Example | What happens | Decided in |
|---|---|---|---|
| Known item | "Which diseases are associated with BRCA1?" | The named entity is resolved live and used. Memory never overrides it. | `think_node`, `_select_planned_tool_call` in `core/graph.py` |
| Continue the discussion | "What variants cause it?" after a BRCA1 answer | "it" binds to the entity most recently mentioned in this session, and the retrieval runs against that entity. | `_antecedent_curie`, `_is_memory_bound_follow_up` in `core/graph.py`; `merge_turn` in `core/session_memory.py` |
| Change the subject | "Which diseases are associated with TP53?" after a BRCA1 answer | The new entity is used. Memory is not consulted for the subject. | `_select_planned_tool_call`, rule 3 |
| A reference with nothing behind it | "What variants cause it?" as the first question | The answer asks which gene, variant or condition is meant, with no tool call. | `_needs_clarification` in `core/graph.py` |
| A subject with no identifier behind it | "papers on the effects of caffeine on exercise performance" | The question names no gene, variant or disease, so the published literature is searched for the question's own words and the answer is the papers. No graph call is made. | `breadth_plan.build_topic_term`, `plan_node`'s topic branch in `core/graph.py` |

A fifth case sits under all four: a symbol that does not exist ("BRCA9") refuses by name, and memory can neither prevent that refusal nor supply an entity in its place. That is the safety control from build phase 3.1, unchanged.

## Known item search

Every question is read for entity mentions: an exact identifier (a CURIE such as `NCBIGene:672`), or a symbol that a live NCBI lookup confirms. A confirmed entity is the question's subject, and nothing remembered from earlier turns can replace it. A mistyped or obsolete symbol that the lookup rejects produces a refusal naming the symbol and offering the NCBI search page, never a guess and never a substitution from memory.

## Continuing the discussion

The session remembers every entity it has resolved, in order of most recent mention (a re-mentioned entity moves to the front of recency, so BRCA1, then TP53, then BRCA1 again leaves BRCA1 as the antecedent). A follow-up that names no entity of its own but carries a referring word ("it", "its", "this", "that", "these", "those", "they", "them", "their", "one", "ones") binds to that antecedent, exactly one entity, and the search runs against it.

Two controls make this work in practice:

- The guardrail judges the bare words of the follow-up and, on its own, would call "What variants cause it?" off topic about one time in three. When the session has resolved an entity and the question carries a referring word, that off-topic verdict is set aside in code. An injection verdict is never set aside.
- The go-deeper offer is a real follow-up question built in code ("Which other sequence variant records are linked to BRCA1?"), and the session remembers which records each answer already showed, so that turn puts records not yet shown first.

The earlier turns also reach the Think and Plan steps as a labelled data block (entities, established findings, open questions), which guides what is looked up. They never reach the guardrail's prompt or the answer-writing step.

## Changing the subject

A follow-up that names a new entity is a known-item search on that entity. Nothing pulls it back to the earlier subject. The earlier entities stay in memory, so a later "it" can still refer to whichever was mentioned most recently.

## A reference with nothing behind it

When a question carries a referring word, names no entity, has no unresolved symbol to refuse on, and the session has nothing remembered, the Think step publishes a clarifying question, the Plan step selects no tool, and the answer is the question: "One more detail is needed: which gene, variant or condition do you mean? Ask again naming it, for example "Which variants cause disease in BRCA1?", and the follow-up will use it." The web app labels it "One more detail needed" and puts the cursor in the follow-up field. The run costs no tool call.

## A subject with no identifier behind it

Fix-plan item 12.7, 2026-09-23. Some questions name nothing this product can resolve: a chemical ("caffeine", "coffee"), a population ("people of Mediterranean descent", "Ashkenazi Jewish people"), a diet, a sport, a country. There is a gene resolver and a disease resolver and nothing else, so before this these questions reached the graph with nothing to bind, got "no entity could be identified in this query", and the answer asked the reader to name a gene, variant, disease or organism. That asks for a vocabulary they do not have.

A literature question needs no identifier. The question's own content words become a PubMed search, the top five papers are fetched with their abstracts and annotated, and the answer is those papers, each cited to its own PubMed record. No graph call is made, because with no identifier there is nothing for the graph to answer.

The search term is built by a fixed rule from the words the person typed, with no model call and no network call in it, so the same question searches for the same thing every time. Four kinds of word are dropped: grammar words, words describing the search rather than the subject ("papers", "studies", "find"), light verbs and hedging adverbs ("help", "make", "found", "typically"), and the asker's own value judgements ("beneficial", "good", "harmful"). Each category was measured against live PubMed: keeping "help" and "make" took a coffee question from 532 matching papers to zero, and keeping "beneficial" took a Mediterranean-variants question from 17 to zero.

The answer reports what has been published and never gives a verdict. A question like "Does coffee help make exercise more effective?" gets the papers about caffeine and exercise performance; it never gets a yes or a no.

When the literature search genuinely matches nothing, the answer still refuses, and the refusal says what it searched: "I searched the published literature for coffee, exercise, effective and found nothing."

Session memory does not take this question over. A remembered entity keeps the turn only when the question carries a referring word ("it", "those") or leaves fewer than two content words behind, which is the continuation rule above. A full new question about caffeine, asked right after a question about a gene, is about caffeine.

## The firewall: memory guides retrieval, never assertion

Technical specification Section 14.1. Memory decides which entity a question is about and what the earlier turns established, so the right thing is looked up. It never becomes a source: every claim in a follow-up's answer is retrieved fresh on that turn and grounded and cited by the same code as any first question. The answer-writing step reads no memory at all, which the premise gate asserts by walking the loop's call sites.

## How to check each one on develop

1. Known item: ask "Which diseases are associated with BRCA1?". Expect named diseases, each with a source. Then ask "Which diseases are associated with BRCA9?". Expect a refusal naming BRCA9.
2. Continue: after the BRCA1 answer, ask "What variants cause it?". Expect ClinVar variants of BRCA1, on the same screen, with the earlier answer folded above.
3. Change the subject: then ask "Which diseases are associated with TP53?". Expect TP53's diseases. Then ask "What variants cause it?". Expect TP53 variants.
4. Back again: ask "Which diseases are associated with BRCA1?" once more, then "What variants cause it?". Expect BRCA1 variants, not TP53's.
5. Nothing behind it: in a fresh private window, ask "What variants cause it?" first. Expect the "One more detail needed" question, no sources, no tool calls.
6. No identifier behind the subject: ask "papers on the effects of caffeine on exercise performance". Expect five PubMed papers about caffeine and exercise, each with a source, and no knowledge-graph step in the pipeline. Then, in the same session, ask "Does coffee help make exercise more effective?". Expect papers again, and no yes or no.

Last updated: 2026-09-23
