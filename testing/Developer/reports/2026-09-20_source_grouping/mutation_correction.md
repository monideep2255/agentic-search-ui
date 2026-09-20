# Correcting the mutation claim in commit 9d20438

Written 2026-09-20 by the reviewer, correcting the reviewer.

## What the commit message says

`9d20438`'s message states:

> Keying the merge map per citation instead of per URL, so the merge silently
> never happens while every symbol still exists, turns ALL EIGHT arms red. That
> is the property under test actually being tested.

That claim is WRONG in a way worth recording rather than quietly leaving, because
it is the exact overstatement this reviewer spent the day catching in other
agents' reports.

## What was actually done, and why it proved less than claimed

The mutation changed two things at once. It stopped the merge AND it changed the
map's keys, from `source.url` to `source.url + String(source.n)`. The second
change is structural: it breaks the grouping's own lookup rather than isolating
the deduplication behaviour. Everything downstream collapsed, so every arm went
red, including arms that have nothing to do with deduplication.

A mutation that breaks everything proves less than a targeted one. All it
establishes is that the code is load-bearing in general, not that each arm tests
the property it claims to.

## What the cleaner experiment shows

The agent that wrote the feature ran a plain revert of `AnswerScreen.tsx` with
the test file kept, and got `6 failed | 2 passed (8)`:

| Arm | Discriminates? |
|---|---|
| Groups by layer, fixed order and labels | yes |
| Omits an empty layer group | yes |
| Two citations of the same URL merge, both markers carried | yes |
| Two different records in the same layer NOT merged | yes |
| Group heading and per-group count render | yes |
| A duplicate record renders once, markers `[1][2]` | yes |
| A table row is NOT collapsed when it shares a record | NO, correctly |
| A prose citation marker still resolves to the right record | NO, correctly |

The last two are INVARIANTS, not tests of this feature. Marker resolution runs
through `sourceByIndex`, which neither the old nor the new code touches, and the
result table is built from `claims`, which grouping never reads. They must hold
in both states by construction. They exist as regression guards against a FUTURE
change that reaches into the table or the marker map, which is a real and
valuable job, and it is not the job of discriminating today's change.

## Why this is worth a file rather than a shrug

Six discriminating arms plus two deliberate invariants is a good verify surface.
The feature is not in doubt. What was wrong was the REPORTING, and this reviewer
had spent the day writing commit messages criticising exactly this: an arm that
fails for an uninteresting reason being counted as proof.

The rule that follows, for whoever mutates next: change ONE property and leave
every other symbol and key intact. If a mutation makes unrelated arms fail, it is
too broad to be evidence, and the honest response is to narrow it rather than to
report the wider blast radius as a stronger result.

## One process note, also the reviewer's

`9d20438` was committed while the authoring agent was still verifying, after this
reviewer had said in the same session that it would not push work whose author
had not confirmed it finished. The code was complete and its gates were green, so
nothing shipped broken, but the stated rule was departed from without saying so
at the time. The agent noticed and said so in its report.
