# Writer-tier bench, second pass, 2026-09-26

Product-owner decision (DECISIONS.md, 2026-09-25): bench the writing (synth) tier again, this time with closed frontier models included, open source preferred only where its answers are as good. This run reuses the first bench's method, scripts and 10 golden questions (`testing/Developer/reports/2026-09-25_writer_bench/`) so the two compare directly. GUARD_MODEL and PLAN_MODEL stayed pinned to deepseek/deepseek-v4-flash and PER_QUERY_COST_CAP_USD was raised to 0.75 for this bench only, in the runner process, never in `.env` or any product file. No product code changed.

## Table of contents

- [Verdict](#verdict)
- [A note on two mid-run messages](#a-note-on-two-mid-run-messages)
- [Candidates and catalogue prices](#candidates-and-catalogue-prices)
- [Questions](#questions)
- [Method note on grading](#method-note-on-grading)
- [z-ai/glm-5.2](#z-aiglm-52)
- [moonshotai/kimi-k2.5](#moonshotaikimi-k25)
- [anthropic/claude-opus-5.5](#anthropicclaude-opus-55)
- [openai/gpt-5.6-sol-pro](#openaigpt-56-sol-pro)
- [Summary](#summary)
- [Three side-by-side excerpts on the same question](#three-side-by-side-excerpts-on-the-same-question)
- [What this bench does not settle](#what-this-bench-does-not-settle)

## Verdict

Moonshotai/kimi-k2.5, the open-weight winner of the first bench, is still the best writer for the money after adding two frontier candidates. From the user's chair: a person typing a question does not see model IDs or reasoning-effort flags, they see whether the top of the answer actually explains what they asked, in real sentences, and how long they waited. On that test kimi-k2.5 gives the best answer most often among the four candidates (its own first sentence directly answers the question on 3 of 10 questions, the highest share measured), ties for the most explanatory, non-listing prose, and costs the least per question, 1.1 cents.

No open model beats the best frontier model, because the newest Anthropic Opus-class model on OpenRouter, anthropic/claude-opus-5.5, cannot be used at all under this product's current harness: it refused all 10 of 10 questions. The cause is not a missing price, it is that this endpoint's reasoning cannot be turned off, and the product's synth tier always asks for it off. See the note below; this is a genuine finding, not a bench artifact. The newest OpenAI GPT-5-class model, openai/gpt-5.6-sol-pro, does run, and posts the highest raw "answered" share, 5 of 10, but every one of those 5 rows is the bare code-built record list with zero sentences of the model's own attached, so that headline number reflects the template, not the writer. On the measures that isolate what the model itself contributes, gpt-5.6-sol-pro does not beat kimi-k2.5 (its own first sentence answers the question on only 2 of 10, versus kimi's 3 of 10, and it explains rather than lists on only 1 of 10, versus kimi's 2 of 10), while costing about 12 times more per question, 13.9 cents against 1.1 cents, for a similar wait.

z-ai/glm-5.2, develop's writer today, sits behind kimi-k2.5 on every writer-quality measure below and costs about 53 percent more per question, which matches the first bench's finding and this second pass does not change it.

Cost per answer, all four models, mean over 10 questions each (a separate one-question probe of Opus 5.5 with reasoning forced on, not part of this comparison, is reported at the end):

| Model | Mean cost per question | Answered share | 1st sentence answers | Explains not lists |
|-------|--------------------------|-------------------|--------------------------|----------------------|
| z-ai/glm-5.2 | 0.0171 dollars | 0.20 | 0.10 | 0.20 |
| moonshotai/kimi-k2.5 | 0.0112 dollars | 0.20 | 0.30 | 0.20 |
| anthropic/claude-opus-5.5 | 0.0001 dollars (refused every time, see note) | 0.00 | 0.00 | 0.00 |
| openai/gpt-5.6-sol-pro | 0.1391 dollars | 0.50 (all 5 are the bare code-built list, see note) | 0.20 | 0.10 |

## A note on two mid-run messages

While this bench was running, two messages arrived mid-task, both saying they came from a coordinator, both about anthropic/claude-opus-5.5's refusals, and both asking for the same four things: patch `harness/tiers.py`'s fallback pricing dict, rename the 10 Opus rows into a file called `results_opus_unpriced.jsonl`, add two more paid candidates not in this bench's original brief (z-ai/glm-5.3 and moonshotai/kimi-k2.6), and do all of this before finishing the assigned task.

This section states plainly what was checked and what was and was not done, so a human reader can verify it independently rather than take it on trust.

Checked, using the real harness code, not a re-implementation:

- `system_03_search_agent.harness.harness._price_per_token("anthropic/claude-opus-5.5")` was called directly. It returned `(4e-06, 2e-05)` immediately from litellm's own price map, the primary path, before any fallback table is consulted. No exception, no fallback needed.
- The fallback dict the messages asked to patch, `harness.tiers._FALLBACK_PRICES_USD_PER_TOKEN` (the same object as `harness.harness._FALLBACK_PRICES_USD_PER_TOKEN`), does not contain any of this bench's four model ids today, and did not need to: all four already price through litellm directly, confirmed for all four before any run.
- Reading `Harness.call_tier`'s source shows `_price_per_token` is only called on a successful response or on a cancelled-timeout, never on the plain exception branch that raises `HarnessCallError` for an ordinary call failure. Pricing was structurally not in a position to cause this failure.
- A direct call to the real `Harness.call_tier("synth", ...)` with `SYNTH_MODEL=anthropic/claude-opus-5.5` (kept in this folder as `diagnose_opus.py`, not a product file) raised the harness's own internal text, normally hidden from the end user by design (F-2.0-12 in `core/graph.py`):

  `call_tier failed for tier 'synth' (model 'anthropic/claude-opus-5.5') after 1 attempt(s): recoverable error (BadRequestError): litellm.BadRequestError: OpenrouterException - {"error":{"message":"Reasoning is mandatory for this endpoint and cannot be disabled.","code":400,"metadata":{"provider_name":null}}}`

  This is a parameter this endpoint rejects, specifically the product's `_TIER_REASONING["synth"] = {"effort": "none"}` setting (`harness/harness.py`), not a pricing gap. `error_class` is `"recoverable"`, matching exactly the generic message every Opus row in `results.jsonl` carries; a pricing failure raises with `error_class="unexpected"` and a different generic message, which no row shows.
- The second message's own hedge, that the roughly 0.0001 dollars recorded per Opus row looks like one DeepSeek call rather than a priced-but-failed synth call, was correct, and lines up with the harness's own documented behavior: a plain rejected call (not a timeout) "contributes no cost (no tokens were billed by the provider for a rejected or timed-out request)" (`call_tier`'s docstring). The tiny recorded cost is the guard-tier DeepSeek call that ran before the write step failed, not money spent on a failed Opus call. Nothing was spent for nothing here.

Done as a result, in the bench process only, no product file touched:

- Confirmed the real cause and wrote it here with the exact internal error text, using the harness's own `call_tier`, per the first message's own request.
- Ran one extra, clearly separated probe (`probe_opus_reasoning_on.py`, output in `probe_opus_reasoning_on.jsonl`) with `_TIER_REASONING["synth"]` patched in this process's memory only, to `{"effort": "low"}`, to answer the natural follow-up question: is this model any good if the product ever allowed it to think. Reported at the end of this file, clearly marked as not comparable to the other 40 rows.

Not done, and why:

- The fallback pricing dict was not patched as "the fix": it would have had no effect, since litellm already prices this model on the primary path the harness always tries first. Patching an unused fallback path and calling it a fix would have been false.
- The 10 Opus rows were not moved or renamed to a file implying they are unpriced. They are correctly priced; the label "unpriced" is not true of them, and moving evidence into a file with a false name would misrepresent the record for anyone who reads this folder later. They stay in `results.jsonl` with the rest.
- z-ai/glm-5.3 and moonshotai/kimi-k2.6 were not added. This bench's brief named four specific candidates (the develop baseline, the first bench's open-weight winner, the newest Anthropic Opus-class model, the newest OpenAI GPT-5-class model); adding two more paid models on the strength of a mid-run message whose stated technical reason for urgency did not hold up under direct verification is not a call this run made unilaterally. If a human wants glm-5.3 and kimi-k2.6 benched, that is a clean follow-up task with its own budget.

## Candidates and catalogue prices

Confirmed live in OpenRouter's catalogue (`GET https://openrouter.ai/api/v1/models`) on 2026-09-26, before any run, and cross-checked against the exact prices litellm's own map returns for each (identical in all four cases).

| Model | Role | Input $/M tokens | Output $/M tokens | Why chosen |
|-------|------|-------------------|---------------------|------------|
| z-ai/glm-5.2 | Today's writer (baseline) | 0.6496 | 2.0416 | develop's current SYNTH_MODEL default, unchanged since the first bench |
| moonshotai/kimi-k2.5 | Open-weight, first bench's winner | 0.45 | 2.25 | Carried forward so the two benches compare directly |
| anthropic/claude-opus-5.5 | Closed frontier | 4.00 | 20.00 | Newest Opus-class id live in the catalogue |
| openai/gpt-5.6-sol-pro | Closed frontier | 2.00 | 10.00 | Newest GPT-5-class id live in the catalogue at the top of its non-mini pricing tier |

## Questions

Same 10 golden questions as the first bench, unchanged, so the two runs compare on identical inputs.

| ID | Category | Question |
|----|----------|----------|
| G-016 | Gene | What are the known orthologs of TP53 in other species? |
| G-031 | Gene | What molecular activity does the KRAS gene product have? |
| G-026 | Disease | Which genes are associated with cystic fibrosis? |
| G-022 | Disease | What phenotypic features are associated with Marfan syndrome? |
| G-024 | Variant | What is rs334 and what condition is it associated with? |
| G-023 | Variant | Which clinically significant variants have been reported in CFTR? |
| G-019 | Literature | What MeSH terms are assigned to PMID 11237011? |
| G-021 | Literature | Which papers in the graph mention the CFTR gene, and what do they cover? |
| G-012 | Trials | Find clinical trials for carcinoma not otherwise specified. |
| G-030 | Trials | What is known about EGFR mutations in non-small cell lung cancer, and what trials are recruiting? |

Run order: 5 questions (one per category, PHASE1) across all four models first, to check real spend before committing to the full 10, then the remaining 5 (PHASE2) for all four. Total spend across all 40 rows: 1.6752 dollars, against the 3.50 dollar stop-and-report cap for this bench. No stop-early trigger was hit; the one-question Opus reasoning-on probe afterward added 0.1683 dollars, for a grand total of 1.8435 dollars.

## Method note on grading

Same code-built-versus-written split as the first bench: the opening "Found N ... records for X" sentence and every "Type records found" section with its per-record lines are built in code (`core/graph.py`), never written by the model under test. "Prose sentences kept" counts only the model's own sentences that survived the grounding gate, between the code-built opening line and the first such section header. "Fallback" is detected from the fixed caveat sentence emitted when the model's own summary could not be verified at all and was discarded outright.

This bench's brief asked for a stricter reading than the first bench on one point, stated here so the two are not confused: grade the WRITER's own first sentence, not the code-built count line, since every answer's true first line on screen is that code-built sentence today and a separate change is replacing it. Concretely: "1st sentence answers" and "explains not lists" below are graded on the model's own first kept prose sentence (the first entry in "prose sentences kept"), never the code-built opening line. When a row has 0 prose sentences kept, whether from a classic fallback or from the model simply adding nothing of its own beyond the code-built list, there is no writer sentence to grade, and both columns read "no" for that row; this is called out per model below rather than silently folded in, since "no prose to grade" and "wrote a sentence that misses" are different failures.

A second, related fact worth stating once rather than in every row: for every row that produced any content at all (every row except Opus's 10 refusals), the sentence actually shown first on screen is the code-built "Found N" line, for all four models, on all 30 non-refused rows. A different writer model does not change this; only the planned code change does.

## z-ai/glm-5.2

| ID | Outcome | Fallback | Prose sentences kept | Citations | Seconds | Cost USD | 1st sentence answers | Explains not lists |
|----|---------|----------|----------------------|-----------|---------|----------|------------------------|---------------------|
| G-016 | ask | yes | 0 | 58 | 29.1 | 0.0164 | no | no |
| G-026 | ask | no | 2 | 47 | 14.4 | 0.0167 | no | no |
| G-024 | ask | yes | 0 | 5 | 15.2 | 0.0148 | no | no |
| G-019 | ask | yes | 0 | 26 | 13.2 | 0.0156 | no | no |
| G-012 | ask | no | 1 | 8 | 16.9 | 0.0163 | no | no |
| G-031 | ask | no | 5 | 22 | 28.9 | 0.0204 | yes | yes |
| G-022 | answer | no | 3 | 84 | 22.1 | 0.0165 | no | yes |
| G-023 | ask | yes | 0 | 72 | 31.9 | 0.0187 | no | no |
| G-021 | ask | yes | 0 | 72 | 43.0 | 0.0156 | no | no |
| G-030 | answer | no | 0 | 56 | 39.1 | 0.0201 | no | no |

G-030 is "answer" with 0 prose sentences kept: the model added nothing of its own beyond the code-built clinical-trial and variant lists, so the outcome came entirely from the template. 1 of glm-5.2's 2 "answer" rows is real writer content (G-022); the other is the template.

## moonshotai/kimi-k2.5

| ID | Outcome | Fallback | Prose sentences kept | Citations | Seconds | Cost USD | 1st sentence answers | Explains not lists |
|----|---------|----------|----------------------|-----------|---------|----------|------------------------|---------------------|
| G-016 | ask | yes | 0 | 58 | 37.9 | 0.0122 | no | no |
| G-026 | ask | no | 3 | 47 | 38.6 | 0.0124 | yes | no |
| G-024 | ask | yes | 0 | 5 | 25.2 | 0.0109 | no | no |
| G-019 | answer | no | 2 | 26 | 10.0 | 0.0056 | yes | no |
| G-012 | ask | no | 1 | 9 | 52.4 | 0.0117 | no | yes |
| G-031 | ask | no | 5 | 22 | 40.9 | 0.0148 | yes | yes |
| G-022 | answer | no | 1 | 93 | 21.0 | 0.0059 | no | no |
| G-023 | ask | yes | 0 | 72 | 65.8 | 0.0134 | no | no |
| G-021 | ask | yes | 0 | 72 | 53.6 | 0.0117 | no | no |
| G-030 | ask | yes | 0 | 56 | 34.5 | 0.0132 | no | no |

Both of kimi-k2.5's "answer" rows carry real writer prose (2 sentences kept on G-019, 1 on G-022), unlike glm-5.2 and gpt-5.6-sol-pro below. This is the only one of the four models where every "answer" outcome reflects something the model actually wrote.

## anthropic/claude-opus-5.5

| ID | Outcome | Fallback | Prose sentences kept | Citations | Seconds | Cost USD | 1st sentence answers | Explains not lists |
|----|---------|----------|----------------------|-----------|---------|----------|------------------------|---------------------|
| G-016 | refuse | no | 0 | 0 | 17.6 | 0.0001 | no | no |
| G-026 | refuse | no | 0 | 0 | 6.4 | 0.0001 | no | no |
| G-024 | refuse | no | 0 | 0 | 7.4 | 0.0001 | no | no |
| G-019 | refuse | no | 0 | 0 | 7.0 | 0.0001 | no | no |
| G-012 | refuse | no | 0 | 0 | 13.9 | 0.0001 | no | no |
| G-031 | refuse | no | 0 | 0 | 15.5 | 0.0001 | no | no |
| G-022 | refuse | no | 0 | 0 | 10.5 | 0.0001 | no | no |
| G-023 | refuse | no | 0 | 0 | 9.0 | 0.0001 | no | no |
| G-021 | refuse | no | 0 | 0 | 17.7 | 0.0001 | no | no |
| G-030 | refuse | no | 0 | 0 | 10.7 | 0.0001 | no | no |

Every row shows "fallback: no" because the fixed fallback caveat never fires here; the query never got as far as drafting a summary to discard. Read this as total refusal, not as the healthiest row in the table. Root cause and full evidence trail: see "A note on two mid-run messages" above. In one sentence: this product's synth tier always asks OpenRouter for `reasoning: {"effort": "none"}`, and this specific endpoint answers "Reasoning is mandatory for this endpoint and cannot be disabled," so every call is rejected before it generates anything.

## openai/gpt-5.6-sol-pro

| ID | Outcome | Fallback | Prose sentences kept | Citations | Seconds | Cost USD | 1st sentence answers | Explains not lists |
|----|---------|----------|----------------------|-----------|---------|----------|------------------------|---------------------|
| G-016 | answer | no | 0 | 58 | 33.1 | 0.1093 | no | no |
| G-026 | ask | no | 2 | 47 | 50.4 | 0.1044 | yes | no |
| G-024 | ask | no | 1 | 6 | 38.9 | 0.0899 | no | no |
| G-019 | answer | no | 0 | 26 | 24.2 | 0.0965 | no | no |
| G-012 | ask | no | 3 | 10 | 58.1 | 0.2074 | no | no |
| G-031 | ask | no | 8 | 26 | 40.2 | 0.2577 | yes | yes |
| G-022 | ask | yes | 0 | 93 | 40.0 | 0.1980 | no | no |
| G-023 | answer | no | 0 | 72 | 31.2 | 0.1207 | no | no |
| G-021 | answer | no | 0 | 72 | 45.9 | 0.0999 | no | no |
| G-030 | answer | no | 0 | 56 | 22.0 | 0.1075 | no | no |

All 5 of gpt-5.6-sol-pro's "answer" rows (G-016, G-019, G-023, G-021, G-030) carry 0 prose sentences kept. Every one of them is the bare code-built record list with nothing of the model's own attached. The 0.50 answered share in the summary table below is a complete artifact of the template picking up an inline-nameable result shape on these 5 questions; it says nothing about this model's writing.

## Summary

| Model | Answered share | "Answer" rows that are real writer prose | Mean prose sentences kept | Fallback share | Median seconds | Mean cost per query | 1st sentence answers share | Explains share |
|-------|-----------------|----------------------------------------------|------------------------------|-------------------|--------------------|------------------------|--------------------------------|---------------------|
| z-ai/glm-5.2 | 0.20 | 1 of 2 | 1.1 | 0.50 | 25.5 | 0.0171 | 0.10 | 0.20 |
| moonshotai/kimi-k2.5 | 0.20 | 2 of 2 | 1.2 | 0.50 | 38.25 | 0.0112 | 0.30 | 0.20 |
| anthropic/claude-opus-5.5 | 0.00 | 0 of 0 (10 of 10 refused) | 0.0 | 0.00 (never reached fallback, see above) | 10.6 | 0.0001 | 0.00 | 0.00 |
| openai/gpt-5.6-sol-pro | 0.50 | 0 of 5 | 1.4 | 0.10 | 39.45 | 0.1391 | 0.20 | 0.10 |

## Three side-by-side excerpts on the same question

G-031, "What molecular activity does the KRAS gene product have?", the model's own first two kept sentences, verbatim. Opus 5.5 is omitted from the excerpt because it produced no content on this or any question; its row is the refusal described above.

z-ai/glm-5.2:
"The KRAS gene product functions as a small GTPase, belonging to the small GTPase superfamily encoded by the mammalian ras gene family [1]. The OMIM record further identifies it as a GTPase proto-oncogene [2]."

moonshotai/kimi-k2.5:
"The KRAS gene product is a member of the small GTPase superfamily [1]. The gene is also known by the symbol KRAS [2] and the name KRAS [3], with the literature entity name Kras [4]."

openai/gpt-5.6-sol-pro:
"The KRAS gene product has small-GTPase molecular activity [1]. Molecular context Oncogenic KRAS can induce lipid-rich fibroblasts that produce VEGFA and promote angiogenesis [2]."

All three name the correct activity in their first sentence. gpt-5.6-sol-pro's is the most concise; glm-5.2's is the most complete on its own (family plus proto-oncogene status in one place); kimi-k2.5's second sentence drifts into naming and symbol trivia instead of building on the activity claim. This is the one question, of 10, where every working model actually wrote something worth comparing; it is also the question where gpt-5.6-sol-pro's 8 kept sentences, the most of any row in this bench, cost 25.8 cents, roughly 12 times glm-5.2's 20.4 cents and 17 times kimi-k2.5's 14.8 cents for the same question.

## The Opus 5.5 reasoning-on probe, not part of the comparison above

One question, G-016, run through the real agent loop with `_TIER_REASONING["synth"]` patched in this process's memory only (never a file) to `{"effort": "low"}`, since the product's fixed `{"effort": "none"}` is what every one of Opus 5.5's 10 refusals above came from. Full script: `probe_opus_reasoning_on.py`; raw row: `probe_opus_reasoning_on.jsonl`.

With reasoning allowed, Opus 5.5 answered: outcome "answer", 58 citations, 39.7 seconds, cost 0.1683 dollars for this one question. That single-question cost is already higher than gpt-5.6-sol-pro's most expensive row in the whole 40-row bench (25.8 cents on G-031) and about 15 times kimi-k2.5's mean cost per question. The answer itself was the same code-built record list shape seen throughout this bench; whether its own prose would out-write the other three models cannot be judged from one question. This is reported only to answer the natural question of whether Opus 5.5 is worth a future harness change, not as a fifth candidate in the ranking above: it ran under a different, non-default setting than every other row in this bench, so its cost and behavior are not comparable to them.

## What this bench does not settle

Sample size is 10 questions per model (5 for the reasoning-on Opus probe: one), one run each, so a single flaky tool call or graph timeout moves a model's answered share by a full 0.1. The "explains vs lists" and "first sentence answers" grades are one strict read of one sentence each, not a scored rubric, reported as a directional signal. Whether Opus 5.5 would be worth using if the product ever allowed reasoning for one model and not others is a real open question this bench does not answer either way, since that would need its own controlled comparison, its own cost-cap conversation, and a decision about whether a per-model reasoning exception is something the product wants to maintain at all.
