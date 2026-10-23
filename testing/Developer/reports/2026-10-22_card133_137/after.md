# Cards 133 and 137 part 1, after the fix, 2026-10-22

Live runs after Fix A of `diagnosis.md` (same folder). The rule built, from DECISIONS.md (2026-10-22): two rows whose page key and the record's own identifier both match are one record and merge even when their names differ, showing both names and keeping every citation number; a borrowed or blank identifier, or two different kinds of record, never merge.

In short: the gene listed twice is gone in both depths, and on query 24 and `What does BRCA1 do?` the list, Sources and the Based on line now give one number. Query 116 had no repeated record before or after; its "Found 40" over 41 gene rows has a different cause, named below, and is not fixed here.

## Table of contents

- [What changed for the reader](#what-changed-for-the-reader)
- [How the runs were made](#how-the-runs-were-made)
- [Results](#results)
- [Query 116 is a different count](#query-116-is-a-different-count)
- [Speed](#speed)
- [Spend](#spend)

## What changed for the reader

- A question about one gene lists that gene's record once. The row reads both names the two layers give it, "mutL homolog 1 (MLH1)", "BRCA1 DNA repair associated (BRCA1)", and carries both citation numbers.
- Rows that only borrow a gene's identifier (ortholog edges, GO terms cited through their gene), rows with no identifier, and two kinds of record on one page stay separate rows, as before.

## How the runs were made

| Setting | Value |
|---|---|
| Entry point | `core.run.run_streaming()`, the web app's path |
| Context | `surface="web_ui"`, `reads_placement=True` |
| Cost cap | `PER_QUERY_COST_CAP_USD` 0.25 |
| Code | branch `fix/card133-one-record-one-row`; baseline is `origin/develop` at `bae47b6e`, run the same way |
| Measured | list rows (`table_row` and `list_item` tokens), distinct source pages over citation events (the key Sources counts on), the opening line, the trust line, any page shown on more than one row, seconds to `done` |

## Results

| Question | Depth | Code | Run | List rows | Sources | Based on | Gene shown twice | Seconds |
|---|---|---|---|---|---|---|---|---|
| Query 24 (MLH1 and MSH2) | Plain language | develop | 1 | 24 | 23 | 23 | Yes: "mutL homolog 1" and "MLH1" | 10.1 |
| Query 24 | Plain language | fix | 1 | 23 | 23 | 23 | No, one row "mutL homolog 1 (MLH1)" | 13.6 |
| Query 24 | Plain language | fix | 2 | 23 | 23 | 23 | No, one row "mutL homolog 1 (MLH1)" | 7.7 |
| `What does BRCA1 do?` | Researcher | develop | 1 | 18 | 17 | 17 | Yes: "BRCA1 DNA repair associated" and "BRCA1" | 10.2 |
| `What does BRCA1 do?` | Researcher | fix | 1 | 17 | 17 | 17 | No, one row "BRCA1 DNA repair associated (BRCA1)" | 15.7 |
| `What does BRCA1 do?` | Researcher | fix | 2 | 17 | 17 | 17 | No | 9.0 |
| `What does BRCA1 do?` | Plain language | fix | 1 | 17 | 17 | 17 | No, one row "BRCA1 DNA repair associated (BRCA1)" | 9.7 |
| `What does BRCA1 do?` | Plain language | fix | 2 | 17 | 17 | 17 | No | 8.6 |
| Query 116 (TP53 orthologs) | Researcher | develop | 1 | 57 | 57 | 57 | No | 18.3 |
| Query 116 | Researcher | fix | 1 to 4 | 57 | 57 | 57 | No | 21.4, 18.0, 21.1, 16.9 |

The opening lines, the same on every run of a question:

| Question | Depth | Found line |
|---|---|---|
| Query 24 | Plain language | "I found 2 genes and 5 conditions related to MLH1, MSH2 and colorectal cancer" |
| `What does BRCA1 do?` | Researcher | "Found 1 gene record for BRCA1: BRCA1 DNA repair associated [1]." (one gene row now; two on develop) |
| `What does BRCA1 do?` | Plain language | "I found 1 gene related to BRCA1 [1]." (one gene row) |
| Query 116 | Researcher | "Found 40 gene records for TP53, of 715 available" over 41 gene rows, on develop and on the fix |

## Query 116 is a different count

- The diagnosis expected query 116 to carry the same graph and live pair. The live runs show it does not: the ortholog answer has no graph row for human TP53, so there is nothing to merge, and rows, Sources and Based on already agree at 57 on develop.
- The 41st gene row is the live NCBI Gene record of TP53 itself (`NCBIGene:7157`, "TP53"), a distinct page. The Found line counts the 40 ortholog records the graph call returned and leaves out that context record, so the reader sees "Found 40 gene records" over a table of 41.
- Fixing that is a choice about the opening count line in `synthesis/answer_layout.py`, outside this card's file fence, so it is left open for the lead.

## Speed

- The change is an in-memory comparison of rows already built; it makes no call.
- Query 116 in Researcher ran 18.3 s on develop and 16.9 to 21.4 s on the fix across four runs. Two of the four runs passed 20 s; the spread is network and model time, and this question sat near 20 s before the change.
- Every other run finished in under 16 s.

## Spend

| Reading | Dollars |
|---|---|
| Account usage before the first run | 0.8513 |
| Account usage after the last run | 0.9752 |
| Spent, all runs including the develop baseline and one aborted script run | 0.124 |
| Cap | 0.60 |

The usage figure is the whole account's, so it would include any other run on the same account at the same time.
