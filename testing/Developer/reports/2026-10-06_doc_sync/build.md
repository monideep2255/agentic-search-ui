# Cross-document sync check: build report

Built on 2026-10-06 on the branch `chore/doc-sync-check`, from develop `5cf63d6c`. The product owner, that day: "Documentation is the foundation for success." Cards 44 and 47 had stayed in To do after they merged, because every existing check reads one file at a time. This report covers the new check, `tracker/check_doc_sync.py`, which compares the key documents with each other.

## Table of contents

- [What the check proves](#what-the-check-proves)
- [Findings on today's develop](#findings-on-todays-develop)
- [Where it runs](#where-it-runs)
- [Choices and the alternatives](#choices-and-the-alternatives)
- [Tests and mutations](#tests-and-mutations)
- [Run time](#run-time)
- [What it does not cover](#what-it-does-not-cover)
- [Files changed](#files-changed)

## What the check proves

Six rules, each a named function with its own failing arm in `--mutation-test`:

| Rule | In plain words |
|---|---|
| `card-in-one-place` | A card on the board's To do or Build in progress is not also in "Waiting for your retest", and the reverse. A retest row that marks the card ", part" is the exception: its first part is live and the rest is still to do |
| `retest-names-query` | Every retest row names a query that exists as a `### N.` heading in the test queries document, or says plainly there is none |
| `card-exists` | Every card the board plan's Waves section names, and every card in the Factory brief's card sections and "Not yours now", is on the board, waiting for retest, or in a done table |
| `factory-lane` | A card the Factory brief gives Factory (a `## Card N` section) is not already waiting for retest or done; and a To do card whose Waiting on cell gives it to Factory has its own section in the brief |
| `handoff-agrees` | Every card `HANDOFF.md` names is on a list, and the develop commit it states is an ancestor of HEAD |
| `registry-paths` | Every path in the registry's Document column exists |

Each finding prints as `file:line: rule: what disagrees, and the fix`. Exit 0 is clean, 1 is any finding, 2 is that the check could not run (a document, section or table it reads is missing, or git cannot be asked). Exit 2 is never a pass.

## Findings on today's develop

Nine findings, all real disagreements. None was fixed here, as the brief asked: the lead fixes them.

| Where | Rule | What disagrees | The fix |
|---|---|---|---|
| `testing/UI_fixes_done.md:47` | `retest-names-query` | Cards 43 and 43b: the Queries cell says "the answer to "What does BRCA1 do?" at phone width", which names no query number and does not say none | Name the query that asks "What does BRCA1 do?", or add one for the phone width check, or write "none" and keep the description |
| `testing/UI_fixes_done.md:50` | `retest-names-query` | Card 44: the Queries cell says "the home page, hover the button" | The same: a query number, a new query, or "none" |
| `docs/build/Factory_onboarding.md:239` | `factory-lane` | Card 43 still has a section in Factory's card list, but it is waiting for retest | Take its section out of the card list |
| `docs/build/Factory_onboarding.md:278` | `factory-lane` | Card 44, the same | Take its section out |
| `docs/build/Factory_onboarding.md:310` | `factory-lane` | Card 43b, the same | Take its section out and update the order line ("43b, then 47, then 61") |
| `docs/build/Factory_onboarding.md:323` | `factory-lane` | Card 47, the same | Take its section out |
| `docs/build/Factory_onboarding.md:343` | `factory-lane` | Card 61, the same (#190 merged) | Take its section out |
| `testing/UI_fix_plan.md:30` | `factory-lane` | Card 75's Waiting on cell says "Factory's next item here", but the brief has no section for card 75, and its card 61 section says "card 75 owns it", meaning leave it alone | Add a card 75 section to the brief, or say on the board that it is not Factory's |
| `testing/UI_fix_plan.md:50` | `factory-lane` | Card 24's Waiting on cell says "Factory's next screen card after 61", but the brief lists card 24 under "Not yours now" | Move card 24 from "Not yours now" into its own section, or correct the board |

What came back clean:

- No card sits both on the board and in the retest list. Cards 85, 94 and 101 are in both as ", part", which the board's own Waiting on cells confirm.
- Every card the board plan's waves name exists.
- Every card `HANDOFF.md` names exists.
- The handoff's develop commit `042985a3` is an ancestor of HEAD. It is stale (develop is at `5cf63d6c`, #194), but rule 5 asks only that it is in history, so that is not a finding.

## Where it runs

- `/phase-checkpoint`: a new Step 6b, just before Step 7, runs it in every mode. A finding is fixed in the same checkpoint, and the exit checklist has a line for it.
- `/ship`: Step 0's list of checks runs it right after `check_doc_drift.py --check`. Exit 1 blocks the push; exit 2 is never a pass.
- CI is not changed, by the owner's choice.
- `.claude/README.md` lists it with the other portable tracker scripts.

## Choices and the alternatives

| Choice | Alternatives considered | Why |
|---|---|---|
| A ", part" marker on the retest row lets a card sit in both places | Flag every card in both places; or read "Part live" from the board's cell | Three cards (85, 94, 101) are legitimately half live today. Flagging them would be a false alarm every session. The retest row's marker is exact and already used in both tables |
| A Factory card is one with its own `## Card N` section | Read the order line ("in this order: 43b, then 47, then 61"); or count any mention of the card in the brief | Section headings are stable structure. The order line is prose that changes wording. Counting any mention would pass card 75, which the brief mentions only to say "leave it alone", the opposite of what the board says |
| A board cell gives a card to Factory when it names Factory and does not say "out of Factory's lane", "not Factory's" or "not yours" | Require an exact phrase such as "Factory's next" | Cards 18 and 25 say "Out of Factory's lane" today and must not fire. A list of exclusions copes with new wordings of "Factory's next"; an exact phrase would miss them silently |
| The done set is the Item column of the tables under "Done features at a glance" and "What is done, in summary" | Every card reference anywhere in the done file | The session history tables name cards being worked on, not done, and the card numbers were renumbered once (an old "card 44" is LitSense passages). Reading them would hide a stale Factory card |
| A Queries cell drops quoted text and code spans before reading numbers | Read every number | "What does BRCA1 do?" and `s3` carry digits that are not query numbers |
| A missing section exits 2 | Report it as a finding | The other checks already own document shape (`check_living_docs.py --shape`). A missing section means this check cannot know the answer, which is not the same as a disagreement |
| `--mutation-test` runs on a small built-in set of documents, not on today's real ones | Mutate the real documents | The real documents carry findings today, so a mutation on them would prove nothing. The built-in set passes clean, so each mutation's finding is the mutation's alone, and the arm also proves no other rule fires |
| The Factory brief's registry shape lists its fixed sections, not its card sections | List every `##` heading, card sections included | The card sections change every session by design. Pinning them would turn `--shape` red at every checkpoint |

## Tests and mutations

- `--self-test`: 19 reader cases (card lists, ", part", ranges, possessives, phase numbers and pull request numbers not read as cards, query numbers, quoted digits, dates). All pass.
- `--mutation-test`: the golden set passes with zero findings, then 15 single-break mutations, each caught by its named rule with no other rule firing, and 3 missing-section cases that must exit 2. All 19 pass.
- Proof the arms are live: replacing each rule function with one that returns nothing turns `--mutation-test` red, 3 failures for `card-in-one-place`, 2 for `retest-names-query`, 4 for `card-exists` (3 arms and the Waves cannot-run case), 3 for `factory-lane`, 3 for `handoff-agrees`, 1 for `registry-paths`.
- `tests/tracker/test_check_doc_sync.py`: 12 tests, beside the drift and living-documents tests. The tracker folder runs 60 tests, all passing.
- Gates: `gate02_import_order.sh` and `gate03_lint.sh` pass. `check_doc_drift.py --check` and `check_living_docs.py --shape` pass with the three new registry rows (18 rows).

## Run time

About 0.05 seconds on the real repository, one git call included. The test asserts under 5 seconds.

## What it does not cover

- Whether a card's status words agree with its detail section or its query's text. Only where the card sits is compared.
- Card references in any document other than the seven it reads.
- A card the Factory brief mentions outside its card sections, and the brief's order line.
- Whether a retest row's query tests what the row describes.
- A card list written in a way the reader does not know, such as "the rest of 61": the reader stops there and reads nothing, by design.
- The handoff's other claims, such as the production tag. Only the develop commit is asked of git.
- `card 98` appears in "Done features at a glance" as live and awaiting retest but not in "Waiting for your retest". No rule asks for that today; it would be a seventh rule if the owner wants the two tables to match.

## Files changed

- `tracker/check_doc_sync.py`, new.
- `tests/tracker/test_check_doc_sync.py`, new.
- `tracker/Living_documents.md`: a line in the intro naming the check; new rows for `README.md`, `docs/build/Factory_onboarding.md` and `docs/architecture/Model_architecture.md`; the board and done-file rows updated for the moved retest list, each Set by cell citing "2026-10-06, the Retest list moves to UI_fixes_done.md".
- `.claude/skills/phase-checkpoint/SKILL.md`: Step 6b and an exit checklist line.
- `.claude/skills/ship/SKILL.md`: one check in Step 0.
- `.claude/README.md`: one line in the portable tracker scripts list.
