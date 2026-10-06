# Card 56 follow-up: why develop still answered about SARS

Lead diagnosis, 2026-10-06. Card 56's fix (#173) passed 3 of 3 local Think and Plan runs on 2026-10-05, then failed the one develop run that evening: the SARS-CoV-2 SRA question was answered about the disease SARS (`testing/Developer/reports/2026-10-05_final_test_queries/results.md`, item 4).

## Table of contents

- [What the person sees](#what-the-person-sees)
- [The cause](#the-cause)
- [Evidence](#evidence)
- [The fix](#the-fix)
- [What was not covered](#what-was-not-covered)

## What the person sees

On develop's plan model, about one run in three of a question about SARS-CoV-2 sequencing runs goes wrong. About one in five is answered with three MedGen records about the disease SARS, a different virus, and no sequencing runs. About one in six plans nothing, because "Illumina" was taken for a gene. The rest get SARS-CoV-2's SRA runs.

## The cause

Two model habits, each defeating #173 in its own way:

- No entities at all. The fix in #173 protects a span only when Think's model tags it as an organism. With nothing tagged, the token fallback splits "SARS-CoV-2" on its hyphens, "SARS" passes the all-capitals shape, and MedGen binds three SARS disease records, exactly as before #173.
- A search condition tagged as a gene. "Illumina" tagged as a gene fails the live gene lookup and is filed as an unresolved symbol, and an unresolved symbol blocks the organism route, so nothing is planned.

The local and develop runs used different plan-tier models, which is why three local passes did not show it:

| Setting | Local `.env` | Develop API service (Railway, read 2026-10-06) |
|---|---|---|
| `PLAN_MODEL` | moonshotai/kimi-k2.6 | deepseek/deepseek-v4-flash |
| `CLASSIFIER_PROVIDER` | unset (guard) | jev |

The deployed code was not stale: #173 merged at 19:03 and the develop run was at about 19:45 on 2026-10-05.

## Evidence

Guardrail, Think and Plan only, run locally with `CLASSIFIER_PROVIDER=jev` and each plan model, on the exact question develop was asked. No Act, no Write, nothing written. Cost about $0.0003 a run on deepseek, $0.0016 on kimi.

| Plan model | Valid runs | Tagged SARS-CoV-2 as an organism, SRA route planned | Returned no entities, three MedGen SARS records bound |
|---|---|---|---|
| deepseek-v4-flash | 26 | 17 | 5 |
| kimi-k2.6 | 2 | 2 | 0 |

The fourth outcome, not in the table's columns: on deepseek 4 of 26 runs tagged "Illumina" as a gene and planned nothing; kimi did not show it in 2 runs.

- Raw: `raw/think_probe.py` is the probe; `raw/deepseek_runs.jsonl` and `raw/kimi_runs.jsonl` hold the second batch of each model (12 deepseek runs, 5 valid with one miss; 6 kimi runs, all step-failed). `raw/deepseek_runs_batch3.jsonl` holds the last 12 deepseek runs (3 SARS bindings, 3 "Illumina" genes). The other deepseek batches (3, 1 and 4 runs: one SARS binding, one "Illumina" gene) and the first kimi batch (2 runs) were read from the terminal and not saved.
- In every miss the model still set `record_type` to `sra`. In the five with no entities the reply contradicts itself: it says the question asks for SRA runs and names no organism.
- 13 further runs ended "a step failed" in one burst and did not recur when re-run; they are not counted. The burst looks like an upstream outage and is card 72's territory, not this card's.
- Whole-name lookups: MedGen `[All Fields]` maps "SARS-CoV-2" and "COVID-19" to COVID-19 records, and "SARS" to SARS records. A hyphen-joined name looked up whole does not land on SARS.

## The fix

Four parts, decided by the lead from the user's chair (`DECISIONS.md`, 2026-10-06):

1. When Think's reply asks for SRA runs or assemblies and names no organism, Think is asked once more through its existing retry exchange. A reply without that contradiction pays nothing.
2. If the second reply still names no organism for an SRA or assembly question, the gene and disease token fallbacks are skipped and the person is asked which organism's records they want.
3. The token fallback never cuts a name into pieces: in a hyphen-joined word the whole word may be a candidate, and a piece only when it carries a digit. "TP53-mutant" still offers TP53, "COVID-19" still reaches COVID-19, "SARS-CoV-2" never offers SARS.
4. When an SRA or assembly question's organism is confirmed and the only thing in the way is a "gene" that failed lookup, the classifier model decides whether that word is a gene the person asks about or a condition on the search. Only a condition is set aside, and the answer says it was not applied. If the classifier cannot answer, the refusal stays.

## What was not covered

- Kimi's miss rate: 2 runs only. Switching develop's plan model was not considered a fix: the miss is a model habit both may share, and the guard must hold whichever model answers.
- The rate of empty-entity replies on other question shapes was not measured.
- Act and Write were not run.
