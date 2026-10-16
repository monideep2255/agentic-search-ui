# Overnight state, 2026-10-15 to 16

The live ledger of the night: where each card stands, which agent holds it, and the next step. The lead rewrites a row the moment a card moves, so a session that stops at a usage limit resumes from this file, not from memory. The plan and the owner's rules: `plan.md` beside this file.

Last updated: 2026-10-16 00:15.

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
| 29 | card29, fix/card29-abstract-sentence | Fix round running | fix-29 | Fresh verifier (Fable), then CI, merge, product check |
| 75 | card75, fix/card75-renewal-latch, #239 | Judge SHIP, adversary FAIL; fix round running | fix-75 | Fresh verifier (Opus), merge |
| 115 | card115, fix/card115-readonly-reply-first, #240 | Judge and adversary running | judge-115, adversary-115 | One fix round if needed, fresh verifier, merge |
| 94 | card94, fix/card94-isolate-lookup | Builder running | builder-94 | Commit, pull request, judge and adversary |
| 17 | card17, fix/card17-name-the-paper | Builder running (design committed) | builder-17 | Commit, pull request, judge and adversary (Fable adversary) |
| 110 | card110, fix/card110-first-sentence-redesign | Builder running (design committed) | builder-110 | Commit, pull request, judge and adversary |
| 101 | card101, fix/card101-record-sentence-end | Design committed | none yet | Builder (Sonnet) when the running count drops |
| 15 | card15, fix/card15-checked-templates | Design committed (four shapes) | none yet | Builder (Sonnet) when the running count drops |
| 84 and 72 | none (removed) | Design on develop; not built: needs the owner's yes on the guardrail rule | none | The owner's answer in the morning |
| 24 | none yet | Waits for 29 to merge | none | Worktree from develop after 29 merges, builder (port df7d7a2c from the tag, add the cost on click) |
| 20 | none yet | Waits for 94 to merge | none | Worktree from develop after 94 merges, builder (separate extraction call) |
| Parked branch | fix/cards110-111-summary-opening | Kept until card 110 merges or closes | none | Delete with card 110 |
| Local tags | parked/phase-8.4, phase-8.8-snippets, card101, card15 (card84-72 deleted) | Each deleted when its card merges or closes | none | Delete with its card |

## Merged tonight

| Pull request | Card | Checked on develop |
|---|---|---|
| #236 | Retest file | Documentation |
| #237 | Overnight skill lessons | Documentation |
| #238 | `/ship` retest rule | Tooling |

## Spend

OpenRouter at 23:30: $30.69 left of $125. Night cap $8, up to $12 if needed. Read the balance with `python3 -I testing/Developer/reports/2026-10-15_overnight/or_balance.py`: it reads the API key from `.env` and prints only the totals.
