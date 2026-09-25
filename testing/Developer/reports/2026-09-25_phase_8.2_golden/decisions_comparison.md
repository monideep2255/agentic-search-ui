# Jev against the guard tier, golden run of 2026-09-25

The product owner's comparison table for card 8: every decision the 150 golden runs made on develop at `566e1ab` with `CLASSIFIER_PROVIDER=jev`, read from each run's done event by `decisions_table.py` in this folder.

| Decision | Decisions | Made by Jev | Both models picked | Agreed | Guard pick not ready in time |
|---|---|---|---|---|---|
| guardrail.relevancy, is the question on topic | 11 | 11 | 6 | 6 of 6 | 5 |
| plan.literature, does the question want papers | 117 | 116 (1 Jev timeout, the guard decided) | 36 | 32 of 36 | 80 |
| think.recent_years, does it ask for recent work with no range | 118 | 118 | 44 | 44 of 44 | 74 |

- Relevancy runs only for questions the biomedical word list does not recognise, which is why it made 11 decisions, not 150.
- The one-to-three-word ask-back made none: no golden question is that short.
- The four disagreements were all on papers: G-002 (BRCA1 overview, Jev not_literature at 0.72 and 0.75, the guard wants_literature), G-025 and G-028 (Jev wants_literature at 0.74 and 0.91, the guard not_literature).
- "Guard pick not ready" is the one-second grace of `GUARD_COMPARISON_GRACE_S`: the answer does not wait for the comparison. Most rows therefore compare nothing; letting the comparison land before the done event is a To do card.
