# Writer bench 3, 2026-09-26

The product owner approved a third writer bench on 2026-09-26, with a spend of up to 30 dollars (`DECISIONS.md`, that date). The question: which writer model, the synth tier, gives the best answers, fastest, and at what cost per question?

Only the writer varies. Every run goes through develop's own code at 00f45e8 in a detached worktree, with develop's other settings pinned in the bench process only:

- guard and plan: deepseek/deepseek-v4-flash
- `CLASSIFIER_PROVIDER=jev`
- a per-query cost cap of 0.50 dollars
- tracing and the audit log off, and no caller identity

No product file changed. The only departure from the product's request is the lead's labelled `+effort-minimal` variants for models that refuse `effort: none`, set in the bench process's memory and never committed.

The benching agent returned this report as text, because its harness has sub-agents return findings rather than write report files. The lead saved it and filled in the stage 2 section from `analyze.py 1,2,3` after the finalist round ended.

## Table of contents

- [Verdict](#verdict)
- [Candidates and prices](#candidates-and-prices)
- [Probes](#probes)
- [Stage 1 results](#stage-1-results)
- [Stage 2 results](#stage-2-results)
- [Quality reading](#quality-reading)
- [What it means for speed](#what-it-means-for-speed)
- [Recommendation](#recommendation)
- [Method and corrections](#method-and-corrections)
- [Spend](#spend)
- [What cost time](#what-cost-time)

## Verdict

Speed first, against the 20 second target:

- Four writers keep every call under 20 seconds at the 90th percentile:
  - glm-5.2: 3.3 s median, 6.2 s p90
  - gemini-3.8-flash at minimal effort: 4.5 s median, 7.6 s p90
  - sonnet-5: 9.4 s median, 11.6 s p90
  - opus-5.5 at minimal effort: 10.7 s median, 13.3 s p90
- Four do not:
  - opus-5.5 at its default: 22.0 s p90
  - kimi-k2.5: 22.5 s p90
  - gemini-3.1-pro at minimal: 25.8 s p90
  - gpt-6-astra at minimal: 30.6 s p90
- Grok 4.7 cannot answer at all under the harness: its first writer call ran past the 45 second write budget on the probe.

Quality second, among the four fast writers:

- opus-5.5 at minimal effort withdrew no summary on 18 answered questions and kept 8.3 prose sentences per answer.
- Against it:
  - gemini-3.8-flash at minimal: 4 withdrawn, 3.8 kept
  - sonnet-5: 7 withdrawn, 3.3 kept
  - glm-5.2, today's writer: 9 withdrawn, 0.7 kept
- Opus at minimal also needed the completeness repair on only 8 of 18 questions, against glm-5.2's 18 of 18. That is why its write step (12.0 s median) is close to glm's (7.6 s), although each Opus call is three times slower.

Cost third, as billed by OpenRouter per question:

- opus-5.5 at minimal: $0.126
- gemini-3.8-flash at minimal: $0.022
- glm-5.2: $0.021

Stage 2 confirmed the winner over three runs of each finalist: opus-5.5 at minimal withdrew 0 of 54 summaries, and gemini-3.8-flash at minimal withdrew 14 of 54.

## Candidates and prices

Every id was confirmed live in OpenRouter's catalogue on 2026-09-26. Every one prices through litellm's own map at exactly the catalogue price.

| Model | Role | Input $ per million tokens | Output $ per million tokens | Accepts `effort: none` | Lowest effort accepted |
|---|---|---|---|---|---|
| z-ai/glm-5.2 | Develop's writer today | 0.6496 | 2.042 | Yes | none |
| moonshotai/kimi-k2.5 | Earlier benches' pick for the money | 0.45 | 2.25 | Yes | none |
| anthropic/claude-opus-5.5 | Newest Opus class | 4 | 20 | No | minimal |
| anthropic/claude-sonnet-5 | Newest Sonnet class | 2 | 10 | Yes | none |
| openai/gpt-6-astra | OpenAI's flagship, in the catalogue's words | 10 | 50 | No | minimal |
| x-ai/grok-4.7 | Newest Grok | 1.6 | 4.8 | No | not probed, dropped |
| google/gemini-3.1-pro-preview | Newest Gemini Pro | 2 | 12 | No | minimal |
| google/gemini-3.8-flash | Newest Gemini Flash | 0.75 | 3.75 | No | minimal |

Not benched:

- anthropic/claude-fable-5.1 ($10 and $50): above the Opus class the brief named.
- openai/gpt-6-sol ($2 and $10): the catalogue places it below the flagship.

## Probes

One question, G-031, per model, at the product's own request:

- Five of the six new frontier models refused `effort: none` ("Reasoning is mandatory for this endpoint and cannot be disabled").
- Phase 8.6's retry (T-8.6-08, `harness.py`) then resent the request without the reasoning block, as the code says, and the model reasoned at its own default:
  - Opus 5.5: 21.4 s per call and 1,307 reasoning tokens.
  - The two Gemini models: 3,720 and 3,838 of their 4,000 output tokens went on reasoning, and the reply was cut at the ceiling.
  - Astra and Kimi: their second call was cut at the 45 s write budget.
  - Grok: no call returned inside the budget, and the question ended in the generic step error.
- A one-line effort probe then found that Opus, Astra and both Gemini models all accept `minimal`. Opus, Astra and Gemini Flash used 0 reasoning tokens at minimal; Gemini Pro still used 319.
- Following the lead's decisions, these labels were dropped:
  - Grok
  - the Gemini defaults and Astra's default, which cannot finish inside the ceiling or the budget
- Opus's default was kept as the quality reference.

## Stage 1 results

Eight labels, 18 questions, one run each, question by question, one run at a time at the full NCBI rate. The window was 22:29 to 00:47 UTC, with a pause from 23:40 to 00:08 for a golden run on develop. All 144 runs answered. Output of `analyze.py 1`:

| Model | Withdrawn of 18 answered | Prose sentences kept, total | Mean kept per answer | Answers keeping any prose | First sentence answers | Jev sent / approved | Repair fired | Must-cite hits |
|---|---|---|---|---|---|---|---|---|
| anthropic/claude-opus-5.5 | 0 | 164 | 9.11 | 18 | 4 of 18 | 47 / 24 | 8 of 18 | 34 of 42 |
| anthropic/claude-opus-5.5+effort-minimal | 0 | 150 | 8.33 | 18 | 5 of 18 | 56 / 24 | 8 of 18 | 33 of 42 |
| anthropic/claude-sonnet-5 | 7 | 60 | 3.33 | 9 | 7 of 9 | 31 / 9 | 15 of 18 | 30 of 42 |
| google/gemini-3.1-pro-preview+effort-minimal | 1 | 87 | 4.83 | 17 | 7 of 17 | 27 / 8 | 10 of 18 | 34 of 42 |
| google/gemini-3.8-flash+effort-minimal | 4 | 68 | 3.78 | 14 | 5 of 14 | 41 / 12 | 17 of 18 | 33 of 42 |
| moonshotai/kimi-k2.5 | 8 | 20 | 1.11 | 10 | 5 of 10 | 18 / 3 | 17 of 18 | 33 of 42 |
| openai/gpt-6-astra+effort-minimal | 1 | 173 | 9.61 | 16 | 8 of 16 | 23 / 16 | 9 of 18 | 33 of 42 |
| z-ai/glm-5.2 | 9 | 13 | 0.72 | 9 | 6 of 9 | 28 / 7 | 18 of 18 | 33 of 42 |

| Model | Writer calls | Writer s per call, median | p90 | Output tokens, median | Tokens per s | Reasoning tokens, median | Write step s, median | Whole question s, median | p90 | OpenRouter $ per question | Metered $ per question |
|---|---|---|---|---|---|---|---|---|---|---|---|
| anthropic/claude-opus-5.5 | 26 | 15.8 | 22.0 | 1359 | 85 | 585 | 20.3 | 31.5 | 47.4 | 0.1412 | 0.1413 |
| anthropic/claude-opus-5.5+effort-minimal | 26 | 10.7 | 13.3 | 830 | 76 | 170 | 12.0 | 24.9 | 33.3 | 0.1255 | 0.1256 |
| anthropic/claude-sonnet-5 | 33 | 9.4 | 11.6 | 791 | 89 | 0 | 17.3 | 25.8 | 34.9 | 0.0785 | 0.0786 |
| google/gemini-3.1-pro-preview+effort-minimal | 27 | 19.4 | 25.8 | 2642 | 134 | 2274 | 32.9 | 41.3 | 52.3 | 0.0833 | 0.0860 |
| google/gemini-3.8-flash+effort-minimal | 35 | 4.5 | 7.6 | 386 | 93 | 0 | 9.8 | 18.3 | 26.6 | 0.0219 | 0.0220 |
| moonshotai/kimi-k2.5 | 33 | 14.4 | 22.5 | 460 | 29 | 0 | 32.3 | 41.2 | 51.4 | 0.0075 | 0.0125 |
| openai/gpt-6-astra+effort-minimal | 25 | 19.5 | 30.6 | 448 | 27 | 103 | 30.9 | 38.7 | 51.1 | 0.0839 | 0.2152 |
| z-ai/glm-5.2 | 36 | 3.3 | 6.2 | 524 | 151 | 0 | 7.6 | 16.7 | 24.1 | 0.0212 | 0.0175 |

How to read these tables:

- Prose kept counts whole sentences only, of four words or more once citation markers are removed. The count includes listing sentences a writer composes itself ("Another is NM_... [6]."), which inflates Opus and Astra. The quality reading below separates the two.
- "First sentence answers" is a hand grade of each answer's first shipped prose sentence, in `grades.json`, over answers that kept any prose.
  - "Yes" means the sentence, read alone, answers at least one part of the question.
  - "No" means an identity line, a count only, a record title with no verb, or a sentence whose subject hangs on a stripped earlier sentence.
- Whole-question seconds are measured on this machine with Act calling live NCBI. Compare them with each other, never with develop's golden timings.
- The two cost columns differ for two reasons:
  - The metered cost charges a writer call cut at the budget at its full 4,000-token ceiling, which is why Astra's metered cost is high.
  - OpenRouter bills glm-5.2 above the catalogue price.

## Stage 2 results

The two finalists ran runs 2 and 3 of the 18 questions side by side, from 00:49 to 01:07 UTC, each process at half the NCBI rate (approved by the lead). Compare them on writer seconds per call, which the NCBI rate does not touch. Stage 2's whole-question seconds ran at half rate and are never set beside stage 1's.

Output of `analyze.py 1,2,3` for the two finalists, over all three runs:

| Model | Runs | Answered | Withdrawn of answered | Prose sentences kept, total | Mean kept per answered run | Runs keeping any prose | First sentence answers | Jev sent / approved | Repair fired | Repair returned | Must-cite hits |
|---|---|---|---|---|---|---|---|---|---|---|---|
| anthropic/claude-opus-5.5+effort-minimal | 54 | 54 | 0 | 373 | 6.91 | 54 | 5 of 18 read | 147 / 68 | 24 of 54 | 24 of 24 | 99 of 126 |
| google/gemini-3.8-flash+effort-minimal | 54 | 54 | 14 | 182 | 3.37 | 39 | 5 of 14 read | 120 / 37 | 50 of 54 | 50 of 50 | 99 of 126 |

| Model | Writer calls returned | Writer s per call, median | p90 | First reply s, median | Output tokens, median | Tokens per s, median | Reasoning tokens, median | Write step s, median | Replies cut at the ceiling | Reasoning-block refusals | OpenRouter $ per question |
|---|---|---|---|---|---|---|---|---|---|---|---|
| anthropic/claude-opus-5.5+effort-minimal | 78 | 10.8 | 14.8 | 10.3 | 812 | 75 | 168 | 14.2 | 0 | 0 | 0.1257 |
| google/gemini-3.8-flash+effort-minimal | 104 | 4.6 | 7.6 | 4.1 | 438 | 93 | 0 | 9.8 | 0 | 0 | 0.0214 |

- Opus at minimal held across three runs: 0 of 54 summaries withdrawn, every run keeping prose, the repair on 24 of 54. Its writer p90 of 14.8 s stays under 20.
- Flash at minimal withdrew 14 of 54, and needed the repair on 50 of 54.
- The first sentences of stage 2 were not hand graded; the "read" counts are stage 1's.
- The glm-5.2 baseline's runs 2 and 3 were proposed and not started.

## Quality reading

Five questions, stage 1: G-031 (KRAS activity), G-026 (cystic fibrosis genes), G-024 (rs334), G-030 (EGFR in NSCLC and recruiting trials) and G-033 (MLH1 against MSH2). For each, the writer's first reply was read against the records that run retrieved (`read_answers.py <id> 1 --records`).

### Opus 5.5, default and minimal: answers, and says what the records do not cover

- G-031: "The KRAS gene product is a small GTPase", quoting the RefSeq summary word for word.
- It states gaps plainly, and every such statement checked out against the records:
  - G-024: "None of the findings names an associated condition", and the other rsIDs "should not be read as evidence about rs334".
  - G-030: the records "name the trials but give no recruitment status".
  - G-026: "The findings do not describe what role any of the three plays".
  - G-033: the records "do not say which condition belongs to which gene".
- G-033 is the one place where it may be over-cautious. The records list each gene's conditions after it, and the four other models that wrote the comparison read that order as the pairing.
- It invented nothing in the five.
- The cost of its honesty: its gap statements cite nothing, so the grounding pass strips them. The first sentence that ships is often a fragment ("Another is Colorectal cancer, hereditary nonpolyposis, type 2 [1]."), which is why it scores only 4 and 5 of 18 on first sentences.

### GPT-6 Astra at minimal: as careful as Opus, too slow

- G-030: the variant records "do not establish their pathogenicity", and the trial findings "do not establish which trials are recruiting".
- It invented nothing in the five.
- 19.5 s per call median, 30.6 s p90.

### Sonnet 5: answers first and fluently, but adds what the records do not say

- G-026: it calls CFTR "the core disease-causing gene" and the other two "modifier genes". The records state only an association.
- G-031: it cites the gene-symbol record for a claim about function.
- G-033: it attaches all five conditions to MLH1 and says MSH2 has none, which the records' order contradicts.
- That is why its summary was withdrawn on 7 of 18.

### Gemini 3.8 Flash at minimal: fast, writes in its own words, and fills gaps from memory

- G-033: "Biallelic disruption of NCBIGene:4436 causes Mismatch repair cancer syndrome 2", where "biallelic" is not in any record.
- G-030: "An extracellular domain substitution", also not in the records.
- G-024: "the records link this variation to rs334353", treating an unrelated rsID as linked.
- The gate strips most of these, but it hedges less than Opus.

### Gemini 3.1 Pro at minimal: mechanical

- It writes phrases such as "medgen clinical_features: Asthma".
- G-026: it calls trials with no status "ongoing".
- G-024: its first reply was only "I could not find information on this."

### Kimi-k2.5: the most confident inventions of the eight

- G-030: "classical activating mutations such as p.Asn280Lys". Neither record says so, and the classic activating EGFR mutations are L858R and exon 19 deletions.
- G-024: "suggests either tight linkage disequilibrium".
- G-033: it read the conditions for each gene correctly.

### glm-5.2, today's writer: accurate, but its prose rarely survives

- G-024: an honest "I could not find information on what rs334 is". Its G-033 split of conditions between the genes follows the records' order.
- Its sentences seldom pass the exact checks: 9 of 18 summaries withdrawn, 0.7 sentences kept, and the repair fired on every question.

In short:

- Opus answers, and says honestly what is missing.
- Astra is just as careful, but too slow.
- Sonnet and Kimi add claims the records do not make, and Kimi invents the most confidently.
- Gemini Flash is fast but fills gaps from memory.
- glm-5.2 is accurate but loses most of its prose to the exact checks.

## What it means for speed

The owner's target is every answer within 20 seconds, and the write step is half of every answer.

- The fastest write steps: glm-5.2 at 7.6 s, Gemini Flash at minimal at 9.8 s, and Opus at minimal at 12.0 s.
- Opus at minimal costs about 4.4 s more write time than glm-5.2 at the median. It pays for most of its slower calls by needing the repair less than half as often.
- The mandatory-reasoning models at their default cannot meet the target, because the reasoning alone takes 15 to 28 s.
- Sonnet's write step is 17.3 s, because the repair fired on 15 of 18.
- Gemini Pro at minimal still reasoned a median 2,274 tokens.

## Recommendation

By measured quality and speed, the pick is anthropic/claude-opus-5.5 with reasoning set to minimal:

- It is the only fast writer that never withdrew a summary, over 18 questions and then over 54 runs.
- It keeps the most prose among the fast writers.
- Its write step stays near glm-5.2's.

Cost, beside that: about $0.126 per question against glm-5.2's $0.021, or about $104 more for every thousand questions.

Two conditions before it ships:

- The product asks every tier for `effort: none`. Opus refuses that, and the retry then drops the reasoning block, so Opus reasons at its default, 22 s p90 per call here. Shipping Opus at minimal needs a per-model effort setting in the product.
- The golden consistency run must confirm the answered count before any change to the answer path.

The product owner decided on 2026-09-27 (`DECISIONS.md`): if the finals agree, phase 8.7 builds the per-model effort setting and switches develop's writer to Opus 5.5 at minimal, with the per-question cost cap raised to 25 cents. The finals agree.

## Method and corrections

- Questions:
  - The brief's 22 are 18 distinct questions. The first bench's 10 and the 12 where withdrawn summaries rose share G-016, G-019, G-021 and G-026.
  - The 18: G-016, G-031, G-026, G-022, G-024, G-023, G-019, G-021, G-012, G-030, G-001, G-002, G-003, G-011, G-029, G-033, G-034, G-040.
- Answered and must-cite hits use the golden consistency run's own rules. Withdrawn means the answer carries "could not be verified against them".
- Writer seconds come from `LLMResponse.elapsed_s`.
- Code checked against the brief:
  - T-8.6-08's fix drops the reasoning block on a refusal and does not lower the effort.
  - A call cut by the step timeout is metered at the tier's full ceiling.
  - `Query.trace_id` is capped at 64 characters.

## Spend

The meter is the account's own usage, at the lead's decision.

- Stage 1: usage grew from $64.06 at the start to $76.65 at 00:47 UTC, that is $12.59, including the develop golden run's $1.69 during the pause.
- Stage 2: the driver ended at 01:07 UTC with the bench's own spend at $18.96. Usage had grown $17.73 since the start, and $43.21 remained in the account.
- The probes: $0.90 metered and $0.65 as OpenRouter reported it.

## What cost time

- The account started at $10.94 against a $30 approval, on the account develop also bills. The bench waited for a top-up after the probes.
- Five of six frontier models refusing `effort: none` turned a model comparison into a test of whether any of them can write inside the budget, which led to the minimal-effort variants.
- A golden run on develop paused stage 1 for 28 minutes.
- The first cost figure came from the last `cost` event, which predates a cut call's charge. It was switched to the done event's total.
