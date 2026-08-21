# Feedback review ritual

The runbook for Section 16's stage 3 and stage 4: the weekly human-gated review of captured interactions, and the stage 5 promotion path that follows an approval. Build phase 4.6, tickets T-4.6-10, T-4.6-11 and T-4.6-12. The commands below are real scripts, not a description of one: `system_03_search_agent/feedback/review.py` and `system_03_search_agent/feedback/promotion.py`.

Last updated: 2026-08-21.

## Table of contents

- [Cadence](#cadence)
- [Before you start](#before-you-start)
- [Step 1: surface the week's candidates](#step-1-surface-the-weeks-candidates)
- [Step 2: read the flagged interactions](#step-2-read-the-flagged-interactions)
- [What most of what turns up will be](#what-most-of-what-turns-up-will-be)
- [Step 3: check novelty and recurrence](#step-3-check-novelty-and-recurrence)
- [Step 4: record the decision](#step-4-record-the-decision)
- [Step 5: promote an approved candidate](#step-5-promote-an-approved-candidate)
- [The privacy step is enforced, not trusted](#the-privacy-step-is-enforced-not-trusted)
- [Where things land](#where-things-land)
- [The human-terminal gate](#the-human-terminal-gate)
- [Troubleshooting](#troubleshooting)

## Cadence

Weekly, per Section 16. This is a starter value, tunable the same way the cost caps are tunable: a real number chosen to get the loop running, not a fixed constant nobody may revisit. Changing it is a `--window-days` flag on `review.py list`, not a code change.

## Before you start

Run every command from the repository root with the virtual environment active:

```bash
source venv/bin/activate
```

`review.py` and `promotion.py` both read `USER_DB_URL` the same way the rest of the application does. Set it before running anything below if it is not already set in your shell.

`query_text` and `user_feedback` are sensitive by default (Section 16, Section 11.3). Everything these scripts print goes to your terminal only. Do not paste raw output from `review.py list` into a chat channel, a ticket, or any other durable log; summarize the pattern you found instead.

`query_text` and `representative_query` are also untrusted content, not just sensitive content: they were typed by a caller `review.py` does not control, and the script escapes any control character or bidi-override character in them before printing so one cannot forge or erase what is on your screen. If a sample query shows a literal `\x1b`, `\n`, or similar backslash-escape sequence, that is the escaping working correctly, not a corrupted row: the original text contained a control character, and you are seeing its visible spelling instead of its live effect.

## Step 1: surface the week's candidates

```bash
python -m system_03_search_agent.feedback.review list
```

This is stage 3 step 1's exact filter: rows where `rubric_outcome != 'pass'`, `trust_signal IN ('flag','ask','refuse')`, or `user_feedback->>'rating' = 'down'`, grouped by normalized query text and ordered by count. A clean, passing, no-feedback row never appears here.

Use `--window-days` to widen or narrow the review window for one run:

```bash
python -m system_03_search_agent.feedback.review list --window-days 14
```

## Step 2: read the flagged interactions

The command above prints, per group: the count, the distinct trust signals in that group, how many carried a thumbs-down, a sample query, and the `interaction_ids` behind it. Read the actual query text and any feedback comment. This is the one step no script can do for you: Section 16 puts the judgment squarely on the reviewer, not on the query that surfaced the candidate.

The sample query is display-escaped, per "Before you start" above, so a hostile `query_text` cannot displace the `interaction_ids` line printed beneath it. Copy `interaction_ids` only from a group that printed as one coherent block; if a group's output looks visually broken up or interleaved with an unrelated group, re-run `list` and read that group's raw escaped text closely before copying anything from it.

## What most of what turns up will be

Noise, most of the time. A single ambiguous phrasing. A transient API timeout that tripped a hard-fail check once. A user who down-voted a correct but slow answer. None of these are a gap in the product; they are the normal cost of running a general agent against real queries.

Your job is not to promote everything that surfaces. It is to find the recurring pattern underneath the noise: the same kind of question failing the same way more than once, not a single bad interaction. A group with `count: 1` is very rarely worth a `cq_candidates` row on its own. A group with `count: 5`, all citing the same missing tool or the same wrong route, usually is.

## Step 3: check novelty and recurrence

Stage 4's trigger rule has three parts, and this ritual applies all three in the same pass rather than as a separate job. Two named constants carry the starter values (`system_03_search_agent/feedback/review.py`): `TRIGGER_FREQUENCY_THRESHOLD = 3` and `TRIGGER_ROLLING_WINDOW_DAYS = 30`, meaning a pattern recurs at least 3 times in a rolling 30-day window. Tunable, the same as the review cadence above.

Check whether a similar candidate already exists:

```bash
python -m system_03_search_agent.feedback.review similar "What is known about the BRCA1 gene?"
```

This runs a `pg_trgm` similarity check against `cq_candidates.representative_query` and lists near matches. A match means reinforce an existing row (step 4 below) rather than create a new one.

Evaluate the full trigger rule for one pattern, once you have run the moat test's no-general-tool-equivalent check by hand against the same panel of general tools the original seven must-pass questions were checked against:

```bash
python -m system_03_search_agent.feedback.review trigger "What is known about the BRCA1 gene?" \
  --moat-gate-provenance \
  --moat-gate-deterministic \
  --moat-partial-or-better
```

This prints the frequency count, whether it met the threshold, whether the moat bar is met, and whether the pattern is novel. It decides nothing on its own; you read the output and decide.

## Step 4: record the decision

A brand new candidate:

```bash
python -m system_03_search_agent.feedback.review record \
  --representative-query "What is known about the {gene} gene?" \
  --source-interaction-id <uuid> --source-interaction-id <uuid> \
  --wedge-type gene-variant-literature \
  --moat-gate-provenance --moat-gate-deterministic \
  --moat-rank tier_1 \
  --reviewed-by <your identity> \
  --review-decision approve \
  --review-notes "recurring: three users this week asked variants of this, agent returned only non-human orthologs each time"
```

Reinforce an existing candidate instead of creating a new one, using the id `similar` printed above:

```bash
python -m system_03_search_agent.feedback.review record \
  --representative-query "irrelevant on the reinforcement path" \
  --source-interaction-id <uuid> \
  --reviewed-by <your identity> \
  --review-decision approve \
  --existing-candidate-id <cq_candidates.id>
```

On the reinforcement path, `source_interaction_ids` grows (deduplicated) and `frequency_count` increments; `moat_rank` is left exactly as it was, per Section 16 stage 4.

`--reviewed-by` and `--review-decision` are always required and always yours to set. Neither is ever inferred or defaulted; see "The human-terminal gate" below.

## Step 5: promote an approved candidate

Only for a row you just recorded with `--review-decision approve`. Prepare a payload file with the two Section 17 shapes, wording generalized:

```json
{
  "few_shot_example": {
    "query_pattern": "What is known about the {gene} gene?",
    "query_class": "exploratory",
    "resolved_entities": [
      {"surface_form": "BRCA1", "curie": "NCBIGene:672", "entity_type": "gene"}
    ],
    "route": {"layers": ["layer1", "layer2"], "tools": ["cypher_query", "ncbi_efetch"]},
    "narrative_pattern": "gene record, recent reviews, pathogenic variants, clinical tests, linked conditions",
    "citation_pattern": ["Gene", "PubMed", "ClinVar", "GTR", "MedGen"]
  },
  "eval_case": {
    "question": "What is known about the BRCA1 gene?",
    "expected_entities": ["NCBIGene:672"],
    "expected_layers": ["layer1", "layer2"],
    "expected_tools": ["cypher_query", "ncbi_efetch"],
    "expected_citation_sources": ["Gene", "PubMed", "ClinVar", "GTR", "MedGen"],
    "fixture_ref": "golden/gene_672_brca1_2026-07",
    "rubric_hint": {"must_not_render_verdict": true}
  }
}
```

Then run:

```bash
python -m system_03_search_agent.feedback.promotion promote \
  --candidate-id <cq_candidates.id> \
  --payload-file payload.json
```

This moves `status` to `promoted`, sets `promoted_at`, and appends both payloads to their destination files (below), each tagged with the candidate's id. Running it twice on the same candidate appends nothing a second time; it is safe to re-run if you are not sure the first run finished.

## The privacy step is enforced, not trusted

Section 16: nothing promoted is a verbatim copy of one user's exact sentence. `promotion.py` refuses (`PrivacyViolationError`) if `few_shot_example.query_pattern` is byte-identical to any of the candidate's source interactions' `query_text`. Generalize the wording yourself before promoting: `{gene}` in place of the literal `BRCA1`, `{disease}` in place of a specific condition name. The script cannot generalize a sentence for you; it can only refuse an ungeneralized one.

## Where things land

- `few_shot_example` appends to `src/system_03_search_agent/orchestrator/few_shot_examples.json`, the versioned pool file Section 17 places in the orchestrator. Build phase 4.6 owns writing to it; build phase 4.7 owns wiring Think and Plan to read it once at process start, per `.claude/rules/prompt-cache-discipline.md`. A promoted example sitting unread until then is expected, not a defect.
- `eval_case` appends to `eval/golden_dataset.json`. Build phase 5.1 owns building the full Phase 4 golden dataset (the 50-query expansion set); this file seeds it with real promoted cases in the meantime.

Neither destination is hot-reloaded. Both take effect on the next deploy or eval run, which is adequate at a weekly promotion cadence (Section 16 stage 5).

## The human-terminal gate

`reviewed_by` and `review_decision` are the only two things that can ever move a `cq_candidates` row toward `promoted`, and both are human-set columns. Neither `review.py` nor `promotion.py` computes, defaults, or infers either value: `upsert_candidate` raises if `--reviewed-by` is blank, and `promote_candidate` raises if the row's `review_decision` is not `approve`. This mirrors Section 16's own framing of the LLM-judge, which is not live in v1 at all: "The LLM-judge writes `llm_judge_rationale`; it has no column that can move a row to `promoted`." These two scripts are the human half of that same guarantee.

## Troubleshooting

`review.py list` prints nothing: either the window genuinely had no flagged interactions, or `USER_DB_URL` points at the wrong database. Widen `--window-days` before assuming the second.

`promotion.py promote` raises `PrivacyViolationError`: the `query_pattern` you wrote still matches a source interaction's exact wording. Generalize it further and re-run; the previous run made no partial writes to either destination file.

`promotion.py promote` raises a `review_decision` error: the candidate has not been approved yet, or was rejected or marked `needs_more_data`. Go back to step 4.
