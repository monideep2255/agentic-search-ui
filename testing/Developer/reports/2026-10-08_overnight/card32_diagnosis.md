# Card 32 diagnosis: a graph column named clinical_features is read as MedGen's

Base: develop at c916cfa3. Read-only diagnosis, no model calls made.

## Table of contents

- [Status today](#status-today)
- [What a person sees](#what-a-person-sees)
- [The cause](#the-cause)
- [The smallest fix](#the-smallest-fix)
- [Overlap](#overlap)
- [Needs the owner](#needs-the-owner)
- [Proposed test query](#proposed-test-query)

## Status today

Still present in code, and not reachable in a live run so far. F-8.1-V02 was filed "unsure" because the alias was never observed live. No commit since (`git log` on `synthesis/findings.py` shows 6b09d468, d9a8eabb, b1f2cd7f, none about this) narrows the key. Nothing in the tool schemas names a `clinical_features` column or property (a search of `tools/cypher*.py` for the word finds nothing), so the model would have to choose that alias itself.

## What a person sees

Nothing today. If the plan tier ever writes `RETURN p.name AS clinical_features` for a phenotype question, graph rows are shown to the writing model and to the reader as MedGen's list, under the heading "Clinical features MedGen lists", cited to a gene or other record. It is a wrong source label on a page whose trust rests on source labels.

## The cause

Every consumer keys on the field name alone:

| Place | Evidence |
|---|---|
| Name of the field | `synthesis/findings.py:167`: `CLINICAL_FEATURES_FIELD = "clinical_features"` |
| Directive to the writer | `findings.py:1845` `build_clinical_features_directive`, filter at line 1875 |
| Record views | `findings.py:1235`, `1247`, `1268` |
| Anchor reservation | `core/graph.py:8871` |
| Heading routing | `core/graph.py:12362` |
| Where a Layer 1 field name comes from | `tools/cypher_provenance.py:885`: `fields = {labels.get(column, column): value ...}`, labels from `cypher_query.column_labels_for` (`cypher_query.py:484`), which limits an alias by length only. |
| Where the real feature rows come from | `core/graph.py` near line 7846, built from the MedGen `ncbi_efetch` record (Layer 2). |

## The smallest fix

Close it where the name is born, so no consumer changes: in `tools/cypher_provenance.py` `_shape_derived_value`, when a Layer 1 alias equals one of the reserved feature field names (`clinical_features`, `clinical_features_total`, `hpo_id`, `disease_title`), keep the positional or a prefixed label such as `graph_clinical_features`. This is a name check on our own reserved strings, not a classification of text.

Alternative: carry the tool in the test, so a feature finding needs `tool == "ncbi_efetch"`. That touches about eight places in two files and is larger.

| Item | Value |
|---|---|
| File fence | `tools/cypher_provenance.py` `_shape_derived_value` (one line plus a constant). One test in `tests/system_03_search_agent/tools/`. |
| Answer path | Yes, narrowly: it only changes a field name that no live run produces. |
| Dial position | 2, runnable behaviour. |
| Size | S |
| Migration | No. |

## Overlap

- None with phase 8.7's list: `cypher_provenance.py` is not on it. `synthesis/findings.py` is on it, and the smallest fix does not touch that file.
- None with the guardrail.

## Needs the owner

No. A suggestion for the board: this is latent, so the owner may prefer to leave it until a live run shows the alias. It is cheap enough to close with the next tool change.

## Proposed test query

No live query can trigger it on purpose. Cover it with a unit test (a Layer 1 row aliased `clinical_features` must not appear under "Clinical features MedGen lists"). For the live regression, the existing query 87 (`testing/Test_queries_and_workflows.md`, "No stray sentence about a record's clinical features") and the Marfan phenotype query at line 531 still stand.
