# The second tester's questions, re-run against today's code

VERDICT IN THE FIRST LINE: one of the seven questions answers today. Six do
not. All seven were asked on the 2026-09-14 build and all seven refused then,
so one has improved since and the other six fail for the same reasons they
failed then.

The questions came from a second tester, a skip-level manager who had never
seen the product and asked what a person actually asks. Their four screenshots
are in `testing/User-feedback/`, with the comment written into each filename.

Re-run with `run_feedback_questions.py` in this folder, against the real model
and the real graph, one question at a time so the shared NCBI rate pools are
never contended. Full transcript per question in `qN_*.txt`, machine-readable
summary in `runs.jsonl`.

A CORRECTION IS RECORDED HERE RATHER THAN TIDIED AWAY. The first pass read
`reflux disease` as a refusal and this document said "zero of seven". That was
wrong. Its graph call had failed with a `ConnectTimeout` to the graph query
service, which is an outage on the measuring run and not a property of the
product. Re-run, the same question answers with eight cited records. Two other
refusals were re-run to check for the same mistake and both reproduced exactly.

## What happened, question by question

| # | Question | Tools that ran | Graph result | Sources | Outcome |
|---|---|---|---|---|---|
| 1 | `reflux disease` | cypher_query | ok, 8 rows | 8 | ANSWERS, grounded, trust `ask`, 23.2s |
| 2 | `GERD` | cypher_query | empty, 0 rows | 0 | refuse |
| 3 | `Any trials for GERD?` | cypher_query | empty, 0 rows | 0 | refuse, reproduced twice |
| 4 | `papers on the effects of caffeine on exercise performance` | NONE | not reached | 0 | refused before any search |
| 5 | `Does coffee help make exercise more effective?` | NONE | not reached | 0 | refused before any search |
| 6 | `Are there any beneficial variants typically found in people of mediterranean descent?` | cypher_query | error, no entity | 0 | refuse |
| 7 | `What positive and negative genes do ashkenazi jewish people have?` | cypher_query | error, no entity | 0 | refuse, reproduced twice |

## Cause A: the plan is gene-shaped, so a disease question searches one place

This accounts for questions 2, 3, 6 and 7, and it explains why question 1
survives only by luck. It is not a mistake in the code; it is what the code
says it does. `_build_layer_tool_calls` in `core/graph.py` opens its work with
`if gene_symbol:` and its own docstring closes:

> "A question that resolves no gene and names no rs id plans nothing here, so
> a disease named only as a typed `MedGen:` CURIE keeps its single graph
> call."

So the breadth wiring that item 11.21 shipped, live NCBI records plus the
literature plus the trials registry, fires on a GENE. A question anchored on a
disease, a population, or nothing at all gets one Cypher query and nothing
else. When that one query comes back empty, the whole question is lost.

THE SHARPEST EVIDENCE IS THE PAIR OF SYNONYMS, and neither half of it was
designed:

- `reflux disease` resolves to eight MedGen concepts, all eight of which exist
  as `Disease` vertices, so the single graph call returns 8 rows and the
  question answers.
- `GERD` resolves to one concept, `MedGen:C5563728`, which the graph does not
  hold. The same single call returns zero rows and the question refuses.

The same condition under two names gives an answer or a refusal depending on
which concept id the name happens to land on, because nothing else is
searched. That is not a ranking problem; it is a single point of failure.

Question 3 is the sharpest case of the cost, because every step before the
last one worked. Think resolved GERD correctly at confidence 1.0 and its own
narrative reads:

> "Broad request for clinical trials on a disease ... open-ended exploration
> across trial registries and literature."

Plan then chose one tool, `cypher_query`, and ran:

    MATCH (a:Disease {id: $e_MedGen_C5563728}) RETURN a LIMIT 100
    0 rows

`clinicaltrials_search` is built, tested and wired. It was never called. The
registry holds thousands of GERD trials.

This compounds with the graph finding of the same day: `Disease` vertices
carry their source vocabulary in `name`, so question 1's eight rows are
answered from the MedGen records fetched live, not from names the graph holds.

## Cause B: the allowlist contains no literature vocabulary

Questions 4 and 5 never reached a search at all. They were refused by
`guardrail/prefilter.py`'s biomedical allowlist, deterministically, in 0.0
seconds, with "This looks outside biomedical research."

Measured against the shipped allowlist, every one of these is absent as a
single term: `paper`, `papers`, `publication`, `article`, `literature`,
`study`, `studies`, `trial`, `trials`, `research`. Only the two-word phrase
`clinical trials` is present.

The refusal text is the part worth quoting back:

> "This looks outside biomedical research. I can help with a gene, variant,
> pathogen, or **paper** question."

The word `paper` is not in the allowlist. The refusal invites a question the
same check then refuses.

Measured consequences beyond the tester's own two questions:

| Question | Cleared? |
|---|---|
| `Any trials for GERD?` | yes |
| `any trials for gerd?` | NO |
| `recent papers on statins` | NO |
| `recent papers on BRCA1` | yes |
| `find me studies about vitamin d` | NO |
| `what does the literature say about metformin` | NO |
| `show me publications about aspirin` | NO |
| `latest research on long covid` | NO |
| `is there a trial recruiting for melanoma` | NO |

The first two rows are the same question. `Any trials for GERD?` passes only
because `GERD` is uppercase and matches the deliberately over-broad
symbol-shaped identifier regex, `\b[A-Z]{2,}[A-Z0-9-]*\b`. Lowercase the same
sentence and the product tells the person their question is outside biomedical
research. Capitalisation decides whether a question is medical.

`recent papers on BRCA1` clears for the same accidental reason, which is why
this has never shown up in our own testing: every question we type names a
gene in capitals.

## Cause C: the product already writes the clarification and never shows it

Questions 6 and 7 resolved no entity at all, and the graph tool was dispatched
anyway with nothing to bind. It reported, in its own words:

> "no entity could be identified in this query, so no graph lookup was
> attempted. Name the gene, variant, disease or organism, or supply a CURIE
> such as NCBIGene:672. Retrying this query unchanged will not help."

That is a good clarifying question. The reader never sees it. What reaches the
screen is "No answer found in NCBI records. I could not find grounded evidence
for this", plus a link to an NCBI search.

So this is not only a missing feature. The actionable text exists inside the
tool result and is discarded on the way to the person who needed it.

## Cause D: nothing asks which question a short one meant

Separately from the above, `reflux disease` is two words and could mean the
concept, its genetics, its treatments, its trials, or the literature. The
product picks one reading silently. Today it happens to return a list of eight
related concepts, which is a defensible answer to an ambiguous question, but it
is an accident of the graph rather than a decision.

Today there are exactly four clarifying paths and none is keyed on ambiguity:

- `_needs_clarification` in `core/graph.py`: fires only when a question
  contains a referring word ("it", "those") AND resolves no entity AND has no
  remembered antecedent. A bare topic contains no referring word, so it never
  fires.
- `coordinate_window.ASSEMBLY_QUESTION`: a chromosome window with no assembly.
- `isolate_search`: an isolate question missing its organism or its gene.
- An accession the product cannot place.

Nothing is keyed on the question being short, broad, or having many readings.

## Cause E: the follow-up invitation ignores that there was no answer

`FollowUp.tsx` renders unconditionally under every result, including a
refusal. So a person who has just been told "No answer found in NCBI records"
is offered the heading "Continue this conversation" and three chips: "What
variants cause it?", "Which trials are recruiting?", "What does the literature
add?".

There is no "it". Pressing that first chip sends a question whose only
referring word has no antecedent, which is the one case `_needs_clarification`
does catch, so the product would then ask which gene they meant.

The tester's own words: "If it didn't have an answer, why would I 'continue
the conversation'? Maybe 'ask another question?'"

## Can these questions be answered at all

Yes, and that is the important half. No new capability is needed for six of
the seven; the tools are built and the data exists.

| Question | What would answer it | Already built? |
|---|---|---|
| Any trials for GERD? | `clinicaltrials_search` with `query_cond` from a disease anchor rather than only a gene symbol | the tool, yes; the routing, no |
| GERD | a live MedGen lookup for the concept, plus PubMed, plus the trials registry, rather than one graph call that misses | the tools, yes; the routing, no |
| papers on caffeine and exercise | a PubMed search on the topic, no gene anchor needed | the tool, yes; the allowlist refuses first |
| beneficial variants in mediterranean descent | PubMed; this is a literature question, not a graph question | the tool, yes; the routing, no |
| genes in ashkenazi jewish people | PubMed, plus a named-gene path once the literature names them | the tool, yes; the routing, no |
| Does coffee help make exercise more effective? | PubMed papers. Note the honest limit: the product can return what has been published, never a verdict on whether coffee works | the tool, yes; the allowlist refuses first |

So the constraint is routing and vocabulary, not capability. That is worth
stating plainly because it is the opposite of the graph disease-name finding
from the same day, which cannot be fixed from this repository at all.

## What this changes about priority

The Marfan phenotype check that the overnight session left as its one open
item is the same family as questions 2 and 3: a disease-anchored question
reaching a single graph call that returns nothing. It should be verified as
part of this work rather than separately.

## What the measurement taught

The instrument was wrong before the product was. A single run of `reflux
disease` produced a refusal that fitted the story being told, and it was a
graph service timeout. It was caught only because the per-tool STATUS was
recorded alongside the row count, and `error` does not mean `empty`. A report
that had logged "0 sources" and stopped would have read as confirmation.
