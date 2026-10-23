# Card 145 before: how often Think reads no subject

Ten readings of `What causes bronchiolitis in babies, and how is it usually treated?` through Think's classification and live confirmation, on develop's code at `25235e98` before card 145's change. Run on 2026-10-22 with `think_probe.py` (the Think step alone: `graph._think` with no session memory, so exactly the resolution `_needs_clarification` reads), develop's pinned models (plan tier deepseek-v4-flash) and live NCBI. Raw rows: `raw/before_think.jsonl`.

## Result

| Run | Entities the model returned | Resolved | Asked back | Think seconds |
|---|---|---|---|---|
| 1 | none | nothing | yes | 2.7 |
| 2 | none | nothing | yes | 1.5 |
| 3 | bronchiolitis (disease) | 8 MedGen records | no | 3.4 |
| 4 | bronchiolitis (disease) | 8 MedGen records | no | 2.6 |
| 5 | bronchiolitis (disease) | 8 MedGen records | no | 2.3 |
| 6 | bronchiolitis (disease), babies (organism) | 8 MedGen records | no | 1.4 |
| 7 | bronchiolitis (disease) | 8 MedGen records | no | 1.5 |
| 8 | none | nothing | yes | 2.3 |
| 9 | bronchiolitis (disease) | 8 MedGen records | no | 1.1 |
| 10 | bronchiolitis (disease) | 8 MedGen records | no | 1.0 |

Asked back on 3 of 10. Every ask-back was the same reading: the model returned no entity at all. The two other readings the diagnosis named, the span tagged "other" and the compound span "bronchiolitis in babies", did not occur, and no MedGen failure occurred. When the model named the condition, MedGen bound the same 8 records every time.

## Spend

0.0055 dollars for the ten readings, plus 0.0054 for one trial reading before them (`raw/before_trial.jsonl`, answered, not counted above), read from the key's usage before and after.
