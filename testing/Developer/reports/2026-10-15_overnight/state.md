# Overnight state, 2026-10-15 to 16

The live ledger of the night: where each card stands, which agent holds it, and the next step. The lead rewrites a row the moment a card moves, so a session that stops at a usage limit resumes from this file, not from memory. The plan and the owner's rules: `plan.md` beside this file.

Last updated: 2026-10-16 06:45. The night's work is done: every card merged or closed; the close (checkpoint, ship, clean-up) is under way. A usage limit stopped six agents at about 01:08; all six were resumed at 05:10 with a deadline before the 07:00 close.

## Table of contents

- [How to resume after a stop](#how-to-resume-after-a-stop)
- [Cards](#cards)
- [Merged tonight](#merged-tonight)
- [Spend](#spend)

## How to resume after a stop

1. `git worktree list` and `gh pr list --state open`: what exists.
2. For each row below whose agent is named and not marked done, send that agent a message to continue (it keeps its transcript); dispatch a fresh one only if the agent cannot be resumed, giving it the row's next step.
3. Keep about six agents running at once; hold Fable and Opus work back first.
4. At 07:00 start the close in `plan.md`, whatever is still open: a card not merged is closed, back in To do with its reports on develop, its branch deleted.

## Cards

| Card | Worktree, branch | Stage | Agent | Next step |
|---|---|---|---|---|
| 29 | none (removed) | Closed: verifier HOLD (3 of 24 sentences mislead); #243 closed, card back in To do; tag phase-8.8 deleted | none | A stricter pick, later |
| 75 | none (removed) | Closed: verifier HOLD (worse after a one-off 502 or lost connection); #239 closed, card back in To do | none | The owner's call in the morning |
| 115 | none (merged) | Merged #240 (0fadfdf9) after verifier PASS; in the retest file | none | Product check PASS; the owner's retest |
| 94 | none (timeout fix merged #246; lookup #244 closed) | Merged; in the retest file | none | Product check PASS; the owner's retest |
| 17 | none (merged #241, 2903ce43) | Merged; in the retest file | none | Product check PASS; the owner's retest |
| 110 | none (removed) | Closed: verifier HOLD (titles joined by other words still open); #242 closed; parked 110/111 branch deleted | none | A filter that reads any joining words, later |
| 101 | none (removed) | Closed: judge FIX FIRST and adversary FAIL (sentences develop shows are dropped); #248 closed, branch and tag deleted, reports on the docs branch | none | Pair quote marks by the record, later |
| 15 | none (removed) | Closed: judge FIX FIRST and adversary FAIL (a remembered condition's variants shown for a new subject); #249 closed, branch and tag deleted, reports on the docs branch | none | Skip the shape decision for a remembered subject, later |
| 84 and 72 | none (removed) | Design on develop; not built: needs the owner's yes on the guardrail rule | none | The owner's answer in the morning |
| 24 | none (merged #245, de53c6aa) | Merged on the verifier's PASS; in the retest file; tag phase-8.4 deleted; V-24-02 and V-24-03 are card 117 | none | Product check PASS; the owner's retest |
| 20 | none (removed) | Closed: adversary FAIL (a Georgia question counted every USA isolate; postal-code states dropped under an exact-looking count); #247 closed, branch deleted, reports on the docs branch | none | A design for matching a place to how the file writes it, later |
| Parked branch | none | Deleted with card 110 | none | Done |
| Local tags | parked/phase-8.4, phase-8.8-snippets, card101, card15 (card84-72 deleted) | Each deleted when its card merges or closes | none | Delete with its card |

## Merged tonight

| Pull request | Card | Checked on develop |
|---|---|---|
| #236 | Retest file | Documentation |
| #237 | Overnight skill lessons | Documentation |
| #238 | `/ship` retest rule | Tooling |
| #240 | 115, the read-only reply for a graph-change follow-up | PASS, `2026-10-16_product_check` |
| #241 | 17, the paper named when a sentence moves to another | PASS, `2026-10-16_product_check` |
| #246 | 94 part, a timed-out isolate search keeps the answer | PASS, `2026-10-16_product_check` |
| #245 | 24, the Plain language and Researcher switch | PASS, `2026-10-16_product_check_card24` |

## Spend

OpenRouter at 23:30: $30.69 left of $125. Night cap $8, up to $12 if needed. Read the balance with `python3 -I testing/Developer/reports/2026-10-15_overnight/or_balance.py`: it reads the API key from `.env` and prints only the totals.
