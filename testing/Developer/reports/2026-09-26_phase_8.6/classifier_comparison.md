# Jev and the guard tier on the loop's own decisions

Written by `testing/Developer/scripts/compare_classifiers.py` on 2026-09-26 03:23 UTC. For each golden question:

- The script ran the loop's own Guardrail, Think and Plan steps, never Act or Write.
- Each time the loop asked for a decision, Jev and the guard tier were both asked the same question over the same bounded state.
- The loop went on with the pick Jev-mode `decide()` uses, so it took the path it takes on develop.

## Table of contents

- [The run](#the-run)
- [Agreement by decision point](#agreement-by-decision-point)
- [Disagreements](#disagreements)
- [Every question](#every-question)
- [What this does not compare](#what-this-does-not-compare)

## The run

- Questions: 10, G-003, G-008, G-009, G-013, G-021, G-022, G-030, G-038, G-042, G-050.
- Jev: `typesafe/jev-1.13`. Guard tier: `deepseek/deepseek-v4-flash`. Plan tier, which ran Think's own classification and is not compared: `moonshotai/kimi-k2.6`.
- Decisions asked: 18; compared, both models asked and returned: 18.
- Spend measured by the harness: $0.0097, under a budget of $0.50 enforced as a $0.0500 per-question cap.
- Wall time: 46 s.
- Modules whose `decide` was recorded: `system_03_search_agent.core.graph`.

## Agreement by decision point

Agreement counts only decisions where both models made a pick. A failed model is counted in its own column, never as a disagreement.

| Decision point | Asked | Both picked | Agreed | Disagreed | Agreement | Jev failed | Guard made no pick | Jev median ms | Guard median ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `guardrail.relevancy` | 4 | 4 | 4 | 0 | 100% | 0 | 0 | 314 | 1234 |
| `plan.literature` | 7 | 7 | 7 | 0 | 100% | 0 | 0 | 266 | 1334 |
| `think.recent_years` | 7 | 7 | 7 | 0 | 100% | 0 | 0 | 270 | 947 |

## Disagreements

None: wherever both models made a pick, they made the same one.

## Every question

| Question | Text | Where the loop stopped | Decisions: Jev pick / guard pick | Spend | Seconds |
| --- | --- | --- | --- | --- | --- |
| G-003 | What is known about Lynch syndrome across NCBI: the causal genes, the condition record,... | planned 8 tool calls | `think.recent_years` not_applicable / not_applicable; `plan.literature` not_literature / not_literature | $0.0014 | 5.7 |
| G-008 | 334 | refused at the guardrail | `guardrail.relevancy` off_topic / off_topic, the loop had moved on | $0.0001 | 3.9 |
| G-009 | the | refused at the guardrail | `guardrail.relevancy` off_topic / off_topic | $0.0001 | 1.7 |
| G-013 | what diseases are linked to brca1? | planned 13 tool calls | `think.recent_years` not_applicable / not_applicable; `plan.literature` not_literature / not_literature | $0.0013 | 4.4 |
| G-021 | Which papers in the graph mention the CFTR gene, and what do they cover? | planned 13 tool calls | `think.recent_years` not_applicable / not_applicable; `plan.literature` wants_literature / wants_literature | $0.0013 | 3.4 |
| G-022 | What phenotypic features are associated with Marfan syndrome? | planned 8 tool calls | `think.recent_years` not_applicable / not_applicable; `plan.literature` not_literature / not_literature | $0.0015 | 9.2 |
| G-030 | What is known about EGFR mutations in non-small cell lung cancer, and what trials are r... | planned 13 tool calls | `think.recent_years` not_applicable / not_applicable; `plan.literature` not_literature / not_literature | $0.0015 | 3.3 |
| G-038 | Tell me about the tree of life. | planned 3 tool calls | `guardrail.relevancy` on_topic / on_topic; `think.recent_years` not_applicable / not_applicable; `plan.literature` not_literature / not_literature | $0.0013 | 4.1 |
| G-042 | What is the weather in San Francisco tomorrow? | refused at the guardrail | `guardrail.relevancy` off_topic / off_topic | $0.0001 | 1.8 |
| G-050 | Welche Krankheiten sind mit dem Gen BRCA1 assoziiert? | planned 13 tool calls | `think.recent_years` not_applicable / not_applicable; `plan.literature` not_literature / not_literature | $0.0013 | 4.2 |

## What this does not compare

- The Write step's reworded-sentence check: it needs the full answer, which this script never builds.
- Follow-up questions: every run here is a first turn, so the relevancy state never carries a previous question.
- Decisions the loop did not ask for a question: the tables count only decisions actually asked.
- Model calls outside `decide()`, such as the injection classifier and Think's classification: they ran, but are not compared.
- Whether either pick was right: agreement is not correctness, and a disagreement is a row to read, not a verdict.
