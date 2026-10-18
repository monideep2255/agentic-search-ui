# Overnight state, 2026-10-16 to 17

The live ledger of the night: where each card stands, which agent holds it, and the next step. The lead rewrites a row the moment a card moves, so a session that stops at a usage limit resumes from this file, not from memory. The plan and the owner's rules: `plan.md` beside this file.

Last updated: 2026-10-17 11:50. The night is closed: every card merged or closed, the close under way.

## Table of contents

- [How to resume after a stop](#how-to-resume-after-a-stop)
- [Cards](#cards)
- [Merged tonight](#merged-tonight)
- [Spend](#spend)

## How to resume after a stop

1. `git worktree list` and `gh pr list --state open`: what exists.
2. For each row below whose agent is named and not marked done, send that agent a message to continue (it keeps its transcript); dispatch a fresh one only if it cannot be resumed, giving it the row's next step.
3. Keep about six agents running at once.
4. At 07:00 start the close in `plan.md`.

## Cards

| Card | Worktree, branch | Stage | Agent | Next step |
|---|---|---|---|---|
| 30, step 1 | removed | Merged #261 (ec30edb4); product check PASS; retest row | none | The owner's retest |
| 37, slice A1 | removed | Merged #262 (655e9dfe); product check PASS; retest row | none | The owner's retest |
| 8 | removed | First attempt #259 closed (V-8-05); second attempt merged #266 (ec547c2a); product check PASS at 1280, the info card's phone overflow is card 123; retest row | none | The owner's retest |
| 38, slice B | removed | Merged #265 (0bb341c7); product check PASS on the change; retest row | none | The owner's retest |
| 105 | removed | First attempt #260 closed (V-105-01); second attempt merged #268 (dc566429); product check PASS on the change, one enrichment-layer paper is card 124; retest row | none | The owner's retest |
| 38, slice C | removed | First attempt #263 closed (V-38C-01); second attempt merged #267 (cf9be15d); product check PASS on the change; retest row | none | The owner's retest |
| 18 | removed | Closed #258 (judge FAIL: MCP and GraphQL lose sentences) | none | A design with the owner |
| 37, slice A2 | removed | Closed #264 (adversary: a gene can attach to the wrong rs id) | none | A design with the owner |
| 30, step 2b | removed | Closed #269 after the session stopped 01:40 to 11:32 and the owner chose to resume its verifier (V-30b-04: MCP and GraphQL cut the longer answer) | none | A rebuild that keeps the text-only answer inside the cut |

## Merged tonight

| Pull request | Card | Checked on develop |
|---|---|---|
| #261 (ec30edb4) | 30 step 1 | PASS, `2026-10-16_product_check_card30` |
| #262 (655e9dfe) | 37 slice A1 | PASS, `2026-10-17_product_check_card37` |
| #266 (ec547c2a) | 8 | PASS at 1280; phone overflow pre-existing (card 123), `2026-10-17_product_check_card8` |
| #265 (0bb341c7) | 38 slice B | PASS on the change, `2026-10-17_product_check_card38` |
| #268 (dc566429) | 105 | PASS on the change, `2026-10-17_product_check_card105` |
| #267 (cf9be15d) | 38 slice C | PASS on the change, `2026-10-17_product_check_card38c` |

## Spend

OpenRouter at 21:50: $23.86 left of $125; at 11:40 on 2026-10-17: $22.55, so the night spent $1.31, develop's questions from the product checks included. Night cap $8, up to $12 if needed. Read the balance with `python3 -I testing/Developer/reports/2026-10-15_overnight/or_balance.py` from the main checkout: it reads the API key from `.env` and prints only the totals.
