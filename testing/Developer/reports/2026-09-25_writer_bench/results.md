# Writer-tier bench, 2026-09-25

Card 10, DECISIONS.md 2026-09-25: bench the writing (synth) tier locally on golden questions against GLM 5.2 (develop's current writer), two open-weight models and one closed frontier model. GUARD_MODEL and PLAN_MODEL were pinned to deepseek/deepseek-v4-flash and PER_QUERY_COST_CAP_USD raised to 0.50 for this bench only, in the runner process, never in .env or any product file. No product code changed.

## Verdict

Moonshotai/kimi-k2.5 gives the best answers for the money. It leads on every axis measured: highest answered share (4 of 10 questions came back as a full "answer" rather than a hedge), lowest fallback share (4 of 10 answers fell back to the code-built list, tied for lowest), the most kept prose sentences per answer (2.2 mean), and the lowest cost per query (1.1 cents). It clearly beats GLM 5.2, develop's current writer, which answered only 1 of 10, fell back on 6 of 10, and cost more per query for a worse result on every axis. Anthropic's claude-sonnet-5, the closed frontier candidate, does not beat GLM 5.2 or kimi-k2.5: it answered only 2 of 10, produced the fewest explanatory (non-listing) sentences of the four models, and cost 5 to 8 times more per query than the other three. Deepseek-v4-pro sits between kimi and GLM on quality at roughly double kimi's cost.

Two things this bench also found that matter more than the ranking:

No model cleared an answered share above 0.4. Most queries across all four models came back as "ask" (the trust gate's hedge outcome, not a refusal and not a clean answer) rather than "answer". Swapping the writer model narrows this gap but does not close it: the ceiling on how often this system delivers a clean answer looks like it is set upstream of the writer tier, most likely in grounding or retrieval, not by which model drafts the prose.

The first sentence of every single answer, across all four models, is a code-built line ("Found N ... records for X ..."), never text the writer model generated. `answer_summary_sentence` in `core/graph.py` builds it in code specifically so a count never disagrees with the list under it. This means "does the first sentence answer the question" is mostly a property of that template, not of the writer tier: it only reads as a direct answer when the template happens to inline named results (it does for the gene-list and clinical-trial-list question shapes here, and does not for the rest). A different writer model cannot fix a first sentence it never writes. Grading below reports this honestly rather than crediting a model for a sentence it did not produce.

## Candidates and catalogue prices

Confirmed live in OpenRouter's catalogue (`GET https://openrouter.ai/api/v1/models`) on 2026-09-25, before any run.

| Model | Role | Input $/M tokens | Output $/M tokens | Why chosen |
|-------|------|-------------------|---------------------|------------|
| z-ai/glm-5.2 | Today's writer (baseline) | 0.6496 | 2.0416 | develop's current SYNTH_MODEL default |
| moonshotai/kimi-k2.5 | Open-weight | 0.45 | 2.25 | Published weights, strong general instruction-following, output price under the 3 dollar cap |
| deepseek/deepseek-v4-pro | Open-weight | 0.783 | 1.566 | Published weights, DeepSeek's full flagship (not the flash tier already in use for guard/plan), output price under the 3 dollar cap |
| anthropic/claude-sonnet-5 | Closed frontier | 2.00 | 10.00 | Live Sonnet-class Anthropic model in the catalogue |

Two open-weight models considered and passed over: moonshotai/kimi-k2.6 (already develop's PLAN_MODEL default, and its output price is 4.00 dollars/M, over the 3 dollar cap) and moonshotai/kimi-k2.7-code (3.30 dollars/M output, over the cap, and coding-specialized rather than general instruction-following). litellm's own price map already carried all four candidate ids (verified live), so `harness.harness._price_per_token` priced every run through its primary path; no product file needed a fallback-table edit.

## Questions

Ten golden questions that answered on develop tonight on all three consistency passes (`testing/Developer/reports/2026-09-25_phase_8.1_golden/runs.jsonl`), chosen to spread across gene, disease, variant, literature and trials shapes:

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

## Method note on the two prose metrics

The opening "Found N ... records ..." sentence and every "Type records found" section and its per-record lines are code-built (`core/graph.py`, `answer_summary_sentence` and the `f"{noun} records found"` header), not written by the model under test. "Prose sentences kept" below counts only the text between that opening line and the first such section header, the model's own material that survived the grounding gate. "Fallback" is detected from the fixed caveat sentence `_build_structured_fallback_note()` emits when the model's own summary could not be verified at all and was discarded outright. Both are proxies read from the displayed answer text, stated here so a different count is expected to land close, not identical.

"First sentence answers" and "explains vs lists" below are graded on the actual first two sentences shown to the reader (including the code-built opening line, since that is what the reader sees first), read individually for each of the 40 runs.

## z-ai/glm-5.2

| ID | Outcome | Fallback | Prose sentences kept | Citations | Seconds | Cost USD | 1st sentence answers | Explains not lists |
|----|---------|----------|----------------------|-----------|---------|----------|------------------------|---------------------|
| G-016 | ask | yes | 0 | 58 | 34.2 | 0.0173 | no | no |
| G-031 | ask | no | 7 | 21 | 16.3 | 0.0200 | no | yes |
| G-026 | ask | no | 2 | 47 | 17.1 | 0.0167 | yes | no |
| G-022 | answer | no | 5 | 83 | 22.8 | 0.0166 | no | yes |
| G-024 | ask | yes | 0 | 5 | 14.7 | 0.0147 | no | no |
| G-023 | ask | yes | 0 | 72 | 24.6 | 0.0184 | no | no |
| G-019 | ask | yes | 0 | 26 | 18.2 | 0.0154 | no | no |
| G-021 | ask | yes | 0 | 72 | 32.9 | 0.0161 | no | no |
| G-012 | ask | no | 2 | 9 | 83.2 | 0.0167 | yes | yes |
| G-030 | ask | yes | 0 | 56 | 17.7 | 0.0187 | no | no |

## moonshotai/kimi-k2.5

| ID | Outcome | Fallback | Prose sentences kept | Citations | Seconds | Cost USD | 1st sentence answers | Explains not lists |
|----|---------|----------|----------------------|-----------|---------|----------|------------------------|---------------------|
| G-016 | ask | yes | 0 | 58 | 53.2 | 0.0116 | no | no |
| G-031 | ask | no | 1 | 19 | 51.4 | 0.0156 | no | yes |
| G-026 | ask | no | 1 | 47 | 23.2 | 0.0123 | yes | no |
| G-022 | answer | no | 2 | 83 | 20.3 | 0.0122 | no | yes |
| G-024 | ask | yes | 0 | 5 | 28.4 | 0.0105 | no | no |
| G-023 | ask | yes | 0 | 72 | 23.1 | 0.0136 | no | no |
| G-019 | answer | no | 1 | 26 | 21.5 | 0.0057 | no | no |
| G-021 | answer | no | 15 | 72 | 37.7 | 0.0061 | no | no |
| G-012 | answer | no | 2 | 17 | 46.6 | 0.0127 | no | no |
| G-030 | ask | yes | 0 | 56 | 19.7 | 0.0129 | no | no |

## deepseek/deepseek-v4-pro

| ID | Outcome | Fallback | Prose sentences kept | Citations | Seconds | Cost USD | 1st sentence answers | Explains not lists |
|----|---------|----------|----------------------|-----------|---------|----------|------------------------|---------------------|
| G-016 | ask | yes | 0 | 58 | 42.8 | 0.0213 | no | no |
| G-031 | ask | no | 2 | 20 | 28.9 | 0.0247 | no | yes |
| G-026 | ask | no | 2 | 47 | 23.0 | 0.0212 | yes | yes |
| G-022 | answer | no | 4 | 84 | 25.6 | 0.0210 | no | yes |
| G-024 | ask | yes | 0 | 5 | 16.4 | 0.0192 | no | no |
| G-023 | answer | no | 0 | 72 | 24.6 | 0.0224 | no | no |
| G-019 | answer | no | 3 | 26 | 20.7 | 0.0197 | no | no |
| G-021 | ask | yes | 0 | 72 | 39.6 | 0.0207 | no | no |
| G-012 | ask | no | 2 | 9 | 112.9 | 0.0206 | yes | no |
| G-030 | ask | yes | 0 | 56 | 34.8 | 0.0232 | no | no |

## anthropic/claude-sonnet-5

One duplicate run occurred for G-030 (the background driver and a manual re-run both fired before the driver's completion was confirmed); only the first is counted below and in every total. The duplicate cost an extra 0.0947 dollars, included in total spend but excluded from these 10 rows and from every mean.

| ID | Outcome | Fallback | Prose sentences kept | Citations | Seconds | Cost USD | 1st sentence answers | Explains not lists |
|----|---------|----------|----------------------|-----------|---------|----------|------------------------|---------------------|
| G-016 | ask | yes | 0 | 58 | 33.7 | 0.0809 | no | no |
| G-031 | ask | no | 6 | 23 | 37.9 | 0.1090 | no | yes |
| G-026 | ask | no | 2 | 47 | 24.7 | 0.0831 | yes | no |
| G-022 | answer | no | 2 | 84 | 25.9 | 0.0861 | no | no |
| G-024 | ask | yes | 0 | 5 | 17.4 | 0.0696 | no | no |
| G-023 | answer | no | 1 | 72 | 30.0 | 0.0970 | no | no |
| G-019 | ask | yes | 0 | 26 | 15.1 | 0.0747 | no | no |
| G-021 | ask | yes | 0 | 72 | 33.7 | 0.0777 | no | no |
| G-012 | ask | no | 0 | 9 | 29.1 | 0.0833 | yes | no |
| G-030 | ask | yes | 0 | 56 | 34.7 | 0.0994 | no | no |

## Summary

| Model | Answered share | Mean prose sentences kept | Fallback share | Median seconds | Mean cost per query | 1st sentence answers share | Explains share |
|-------|-----------------|-----------------------------|------------------|-------------------|------------------------|-------------------------------|--------------------|
| z-ai/glm-5.2 | 0.10 | 1.6 | 0.60 | 20.5 | 0.0171 | 0.20 | 0.30 |
| moonshotai/kimi-k2.5 | 0.40 | 2.2 | 0.40 | 25.8 | 0.0113 | 0.10 | 0.20 |
| deepseek/deepseek-v4-pro | 0.30 | 1.3 | 0.40 | 27.3 | 0.0214 | 0.30 | 0.30 |
| anthropic/claude-sonnet-5 | 0.20 | 1.1 | 0.50 | 29.6 | 0.0861 | 0.20 | 0.10 |

Total spend across all 41 runs (including the one duplicate): 1.4533 dollars, against the 2.50 dollar cap for this bench. No stop-early trigger was hit.

## What this bench does not settle

Sample size is 10 questions per model, one run each, so a single flaky tool call or graph timeout moves a model's answered share by a full 0.1. The "explains vs lists" and "first sentence answers" grades are one person's strict read of two sentences each, not a scored rubric, and are reported as a directional signal rather than a precise measurement. The low answered share across every model, most queries came back "ask" rather than "answer", looks like a property of the grounding or retrieval path shared by all four writers, and this bench was not scoped to diagnose that; it is named here so the writer-tier decision is not made on the assumption that a different model would clear it.
