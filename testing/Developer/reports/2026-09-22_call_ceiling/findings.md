# The call ceiling, measured: how close each question shape comes to twenty outside lookups

Fix-plan item 1 as rewritten on the night of 2026-09-22: a gene question charges 14 to 16 of its 20 allowed Layer 2 and 3 calls, a dataset question two more, a window question two more, and the variable part is the model's own spans, each confirmed live in Think where no event showed it. The night's coordinate-range work had just measured the failure this item warned about: a window question crossed the ceiling on one pass in five and the person got a citation-less refusal on a question that had answered the pass before. This folder measures every question shape the plan named, on develop, with the count made visible.

## Table of contents

- [Verdict](#verdict)
- [What the person feels](#what-the-person-feels)
- [The instrument](#the-instrument)
- [Method](#method)
- [The counts](#the-counts)
- [What the counts say, and the decision](#what-the-counts-say-and-the-decision)
- [Method and evidence](#method-and-evidence)

## Verdict

The ceiling holds, and it stays at twenty. Twenty-four of twenty-four runs answered, none was refused by the ceiling, and the worst pass spent 17 of the 20 allowed calls (the GRCh38 window on every pass, and the GEO question on one). The three-rs-number question the plan named as the shape most likely to reach twenty spends 6. No shape came within two calls of the limit, so neither the ceiling nor the fan-out moves, and the fix that made a window question's count fixed (`c72b8a7`, the night's coordinate-range work) closed the only refusal ever observed.

What the count is made of turned out differently from what the plan assumed, and the difference matters for what a person hits:

- The variable part is not the model's spans on every pass. It is the model's spans the FIRST time a process sees them. Think remembers each confirmed gene symbol, disease mention and organism for the life of the process (three in-process caches in `core/graph.py`), so the first question after a deploy pays for every span and the same question a minute later pays nothing for them. Five of eight shapes spent more on pass 1 than on passes 2 and 3.
- The cold count is the one that matters, since every person's first question after a deploy is cold, and every never-seen span is cold. The cold worst case observed is 17.
- Two things outside the plan are paid on every pass, cold or warm: a window question's two gene lookups (never cached, by design, since the window changes) and Write's name resolution of MedGen ids the rows carry without a name (two calls, ESearch then ESummary, for any number of ids). That is why the window question reads 17 on all three passes.
- The theoretical cold worst case is above twenty. Think may look up at most three gene symbols and three disease mentions live (`_MAX_LIVE_SYMBOL_LOOKUPS` and `_MAX_LIVE_DISEASE_LOOKUPS`, both 3), each costing up to two calls, plus one organism check and Write's two: up to 15 outside the plan on top of a 13-call fan-out. It was not observed; the most any pass spent outside the plan was 7.

The measurement also found a defect the count alone would never show, and from the user's chair it outranks the count. Two of the eight shapes ended their answer with a list of records the person never named. See the decision section.

## What the person feels

A ceiling refusal is the worst kind of failure from the user's chair: the same question answered a minute ago and now says "reached its resource limit" with no sources, and nothing about the question changed. Whether the ceiling moves or the fan-out moves is decided by what the counts show, and the property to want is the one the window fix bought: the same count on every pass, so a question that fits once fits always.

## The instrument

The stream showed the planned calls (the `tool_start` events) and never Think's own lookups: the live confirmation of each gene-shaped span the model extracts, the MedGen lookup for a disease mention, the taxonomy check for an organism, and now the window's gene lookup. Those are counted at the transports, where `harness/call_budget.py` charges them, and were invisible to every measurement until tonight. Commit `df657ad` puts the query's count on the done event as `layer_calls_used`, additive and optional, read here and ignored by every surface. The difference between that count and the planned Layer 2 and 3 calls on the stream is Think's own spending.

## Method

Twenty-four signed-in runs on develop at `df657ad`, one at a time, the laptop held awake, three passes each of:

| id | Shape | Why it is in the set |
|---|---|---|
| G-002 | A gene question naming diseases, variants and articles | The everyday gene question with the fullest fan-out |
| G-011 | Two genes and their diseases | Two gene symbols to confirm |
| G-037 | A gene question asking for GEO datasets | The GEO pair adds two calls |
| G-001 | A GRCh38 window | The window's own two lookups plus the two overlap calls |
| G-003 | A disease question (Lynch syndrome) | The MedGen lookup path |
| G-024 | A question naming one rs number | dbSNP and LitVar2 add two calls per rs number |
| G-039 | The plain-terms BRCA1 explanation | A gene question with no shape word |
| R-THREE-RS | Three rs numbers in one question (not a golden row) | The shape the plan named as the one that could still reach twenty |

## The counts

All 24 runs on develop at `df657ad`, one worker, no laptop sleep, with the count read from the done event. "Planned on the stream" is the Layer 2 and 3 calls the plan event listed; the difference is what Think and Write spent outside the plan.

| id | pass | outcome | seconds | Layer 2 and 3 calls spent | planned on the stream | outside the plan: Think's lookups and Write's name resolution (difference) | refused by the ceiling |
|---|---|---|---|---|---|---|---|
| G-001 | 1 | answered | 27.1 | 17 | 13 | 4 | 0 |
| G-001 | 2 | answered | 18.9 | 17 | 13 | 4 | 0 |
| G-001 | 3 | answered | 21.0 | 17 | 13 | 4 | 0 |
| G-002 | 1 | answered | 34.4 | 16 | 11 | 5 | 0 |
| G-002 | 2 | answered | 25.4 | 11 | 11 | 0 | 0 |
| G-002 | 3 | answered | 24.1 | 11 | 11 | 0 | 0 |
| G-003 | 1 | answered | 17.1 | 4 | 0 | 4 | 0 |
| G-003 | 2 | answered | 10.9 | 0 | 0 | 0 | 0 |
| G-003 | 3 | answered | 33.4 | 0 | 0 | 0 | 0 |
| G-011 | 1 | answered | 20.0 | 14 | 11 | 3 | 0 |
| G-011 | 2 | answered | 13.1 | 11 | 11 | 0 | 0 |
| G-011 | 3 | answered | 11.2 | 11 | 11 | 0 | 0 |
| G-024 | 1 | answered | 17.5 | 9 | 2 | 7 | 0 |
| G-024 | 2 | answered | 16.8 | 3 | 2 | 1 | 0 |
| G-024 | 3 | answered | 15.1 | 3 | 2 | 1 | 0 |
| G-037 | 1 | answered | 11.3 | 15 | 13 | 2 | 0 |
| G-037 | 2 | answered | 12.7 | 17 | 13 | 4 | 0 |
| G-037 | 3 | answered | 12.1 | 13 | 13 | 0 | 0 |
| G-039 | 1 | answered | 9.9 | 11 | 11 | 0 | 0 |
| G-039 | 2 | answered | 12.0 | 11 | 11 | 0 | 0 |
| G-039 | 3 | answered | 13.3 | 11 | 11 | 0 | 0 |
| R-THREE-RS | 1 | answered | 25.5 | 6 | 4 | 2 | 0 |
| R-THREE-RS | 2 | answered | 11.9 | 6 | 4 | 2 | 0 |
| R-THREE-RS | 3 | answered | 14.1 | 6 | 4 | 2 | 0 |

| id | question | passes | spent, min to max | headroom under 20 at the worst pass |
|---|---|---|---|---|
| G-001 | What ACMG-relevant evidence is available for a copy number variant spanning chr17:43,000,000-43,200,000 on GRCh38? | 3 | 17 to 17 | 3 |
| G-002 | Give me everything NCBI knows about BRCA1: the gene record, associated conditions, variants, tests and literature | 3 | 11 to 16 | 4 |
| G-003 | What is known about Lynch syndrome across NCBI: the causal genes, the variants, the tests and the trials? | 3 | 0 to 4 | 16 |
| G-011 | Which diseases are associated with BRCA1 and BRCA2? | 3 | 11 to 14 | 6 |
| G-024 | What is rs334 and what condition is it associated with? | 3 | 3 to 9 | 11 |
| G-037 | Find GEO expression datasets studying TP53 in human tumour samples. | 3 | 13 to 17 | 3 |
| G-039 | I am a student. Explain in plain terms what the BRCA1 gene does and why it matters | 3 | 11 to 11 | 9 |
| R-THREE-RS | What conditions are rs334, rs1801133 and rs429358 associated with? | 3 | 6 to 6 | 14 |

Two readings of the first table, checked against the raw captures rather than inferred:

- The three-rs question plans four calls, not six: a dbSNP and a LitVar2 call for two of the three rs numbers. Its plan event lists `cypher_query`, then `ncbi_dbsnp` and `litvar2_lookup` twice. The third rs number rides on the graph call. Its two outside calls are Write's name resolution.
- The disease question (G-003) plans no Layer 2 or 3 call at all: the graph answers it. Its four cold calls are Think confirming "Lynch syndrome" against MedGen (two calls) and Write resolving the names of MedGen ids in the rows (two calls). Warm, it spends nothing.

## What the counts say, and the decision

Decided from the user's chair, and stated in the person's words.

- The ceiling stays at twenty and the fan-out stays as it is. Nobody in 24 runs was refused, and the shape that was refused last night now spends the same 17 every time. A change to the ceiling is the product owner's call in any case, and the counts give no reason to ask for one.
- The count on the done event stays, ignored by every surface. The next time a person sees "reached its resource limit", the capture says exactly what was spent, which no measurement before tonight could.
- A question's own words for a disease are never searched as a disease name (fixed tonight, `d8619bc`). This is the result that matters most to the person. The rs334 answer on pass 1 ended: "this answer does not address the following entities named in the question: Patient condition unchanged, Condition of fetal membrane, Body condition unknown, Poor skin condition, Condition of arterial wall, Condition of jugular veins, Condition of perforator veins, Condition and involution of uterus after childbirth." The GEO answers on passes 2 and 3 ended with eight mouse tumour records the same way. The person had typed "condition" and "tumour samples". The model tagged each word as a disease span, Think sent it to MedGen's name index, the index matched eight arbitrary records, and Write listed them as entities the question had named. A mention made only of generic disease vocabulary now binds nothing and costs no call; "breast cancer" and "Lynch syndrome" are searched exactly as before, and a test pins that.
- The residual, named rather than hidden: a question with a full fan-out and several never-seen spans on a freshly deployed process can still reach twenty in theory (up to 15 outside the plan on top of 13), and if it does the last planned calls are refused and the answer thins or refuses. It was not observed in 24 runs, the most spent outside the plan was 7, and the generic-word guard takes the commonest source of that 7 away. If it is ever seen, the done event's count is the evidence, and the choice then is the product owner's: raise the ceiling, or charge Think's confirmations to their own small budget so they can never eat the plan's.

What the person notices after tonight: the rs334 answer and the GEO answer end without a list of conditions they never mentioned, and every question in the set answers on every pass.

## Method and evidence

| File | What it is |
|---|---|
| `runs.jsonl`, `raw/` | The live runs, written first as they end, with every event but tokens |
| `summarize_ceiling.py` | The tables above, computed from the two files |
| `run_rs.py` | The three-rs-number question, which is not a golden row, through the consistency run's own client |
| The other seven shapes | Run through `testing/Developer/reports/2026-09-22_10.3_consistency/run_consistency.py` with `--ids` naming them, into this folder |
