# Card 37 diagnosis: rs334 is listed beside variants that only share its first digits

Read on develop at `c916cfa3`, 2026-10-08. Code reading and saved run files only; no live run, no model call.

## Table of contents

- [Status today](#status-today)
- [What a person sees](#what-a-person-sees)
- [The cause](#the-cause)
- [The smallest fix](#the-smallest-fix)
- [Overlap with phase 8.7 and the guardrail](#overlap-with-phase-87-and-the-guardrail)
- [Needs the owner](#needs-the-owner)
- [Test query](#test-query)

## Status today

Still happens. Last seen live on develop on 2026-10-05: "outcome ask, 38.7 s. Lists rs334348, rs334353, rs334773 as literature variant records beside rs334; the rs334 record is named by its clinical significance list" (`testing/Developer/reports/2026-10-05_board_plan/w2_think_and_search.md:20`). No commit since touches the LitVar2 shaping or the dbSNP row: the code below is unchanged on develop. The fix is fully specified as phase 8.9's T-8.9-04 and half of T-8.9-03 (`tracker/phase_8.9.md`); phase 8.9 is "planned, not opened".

## What a person sees

Asked "What is rs334 and what condition is it associated with?":

- Literature variant records for rs334348, rs334353, rs334558 and rs334773 sit beside rs334 as if they were the same variant. They are different variants in other places; they only start with the same digits.
- rs334's own dbSNP record is labelled by a list of clinical significance values ("not-provided, protective, likely-benign, pathogenic, other"), not by its name, its gene (HBB) or its condition (sickle cell).
- The writing model was never given the gene, so it cannot say rs334 is in HBB.

A confident wrong record: a person could read rs334348's literature as rs334's.

## The cause

| Part | Cause | Evidence |
|---|---|---|
| Near misses listed | LitVar2's autocomplete returns prefix matches for "rs334", all marked "Matched on rsid". The tool keeps them by design (F-3.3-A-01 made it a disclosure fix, not a filter). The shaping step keeps every match that has a link, with no check that its rs id is the one asked about | Tool: `src/system_03_search_agent/tools/litvar2_lookup.py:209` to `:227` ("It deliberately does not build a match-quality heuristic or auto-refuse a weak match"). Shaping: `src/system_03_search_agent/core/graph.py:4890` to `:4912`, the `litvar2_lookup` branch of `_layer_tool_output_to_structured_fields` (`:4775`). The call is planned with the exact rs id as its query: `core/graph.py:5057`, from `_rsids_in_text` (`:5315`). Phase 8.9's probe 3: five matches, rs334 plus four near misses |
| rs334 named by its significance list | The dbSNP pseudo-row puts `clinical_significance` first and has no `name`. `_pick_representative_field` prefers `name`, else the first usable field, so the record's one finding is its significance list. The `genes` field ("HBB") is in the row and never reaches the writer, which gets one field per row | Row: `core/graph.py:4864` to `:4887`. Picker: `core/graph.py:9110`. One field per row: `synthesis/findings.py:587` to `:615`. Product harness review, G-024 row (`testing/Developer/reports/2026-09-25_harness_review/product_harness.md`) |
| No condition | The dbSNP row carries no condition field, and no ClinVar call is planned for an rs id | Harness review, C2 "Variants": the condition "would come from the ClinVar side of the fan-out, which `_rsids_in_text` already routes to LitVar2 and dbSNP only" |

## The smallest fix

Step 1 alone removes the wrong records. It is the fix the owner's order of work names first (D10, "the rs334 filter first", `testing/Board_plan.md`).

| Step | What changes, in the person's words | Fence | Answer path | Dial | Size |
|---|---|---|---|---|---|
| 1, T-8.9-04 | A question about rs334 shows only rs334's own records, never a variant that only shares its first digits | `core/graph.py`: the `litvar2_lookup` branch of `_layer_tool_output_to_structured_fields` only (`:4890` to `:4912`). When `tool_input` is a `variant_search` whose query is an rs id, keep a match only when its `rsid` equals the query, case-insensitively. No exact match gives status `empty`, not `error`. New test `tests/system_03_search_agent/core/test_litvar2_exact_rsid.py` | Yes | 2, runnable behaviour | S |
| 2, part of T-8.9-03 | rs334's record says it is in the gene HBB, and the writer can say so | `synthesis/findings.py` `build_synth_findings` (a companion finding for row type `Variant record`, field `genes`, named `gene`), `core/graph.py` `_layer3_base_citation` only | Yes | 2, runnable behaviour | S |
| 3, optional | rs334's record is labelled by its rs id, not its significance list | `core/graph.py:4864` to `:4887`: put `rsid` first in the dbSNP pseudo-row, so the picker's first usable field is the identifier | Yes | 2, runnable behaviour | S |

Step 1 is an exact identifier match, which is verification, not a decision read from the question's wording, so it keeps the "no hardcoded decisions" rule (phase 8.9's constraints say the same). The condition (sickle cell) needs a ClinVar lookup by rs id and is out of this card's smallest fix.

Step 3 changes what every dbSNP record is called in the list and the prompt. Run query 23 and the golden G-024 row before and after; phase 8.9's acceptance item 5 already checks G-024.

## Overlap with phase 8.7 and the guardrail

| Step | Phase 8.7 overlap | Guardrail overlap |
|---|---|---|
| 1 | None. `_layer_tool_output_to_structured_fields` is called from `_execute_planned_call` (`core/graph.py:8110`, call at `:8283`), not from the functions 8.7 rewrites, and 8.7's parked branches do not touch it: `git diff develop...` hunk headers name only imports, Write's functions and `findings.py` helpers on `origin/feat/8.7-s1`, and `act_node`, `_gather_planned_calls` and `_PlannedFollowUpCall` on `phase/8.7-answers-sooner` | None |
| 2 | Yes: `synthesis/findings.py`, which phase 8.7 rewrites | None |
| 3 | None | None |

Step 1 can ship alone now, ahead of both phases.

## Needs the owner

No. D10 ("Open phase 8.9 ... the rs334 filter first") was taken as recommended unless the owner objects (`testing/Board_plan.md`). Step 1 has no design choice, package, migration, cost or security change. Shipping step 1 outside phase 8.9 is a sequencing call the lead can make; the board row already says "Do not wait if 8.9 stays closed; a small exact-match filter ships alone" (`w2_think_and_search.md`, card 37 row).

## Test query

Query 23 ("rs334 without invented conditions") asks the right question but checks only that no invented condition appears. Proposed addition to query 23's "What you should see", same shape:

```markdown
- Only rs334's own records are listed. Never rs334348, rs334353, rs334558 or rs334773, which are different variants that only start with the same digits.
- rs334's record is named by its identifier or its gene, HBB, not by a list such as "not-provided, protective, likely-benign, pathogenic, other".
- Plain language and Researcher list the same records.
```
