# Factory review loop

How Factory's pull requests get reviewed, fixed and merged without the product owner carrying messages between Factory and the lead. Proposed on 2026-10-16 at the owner's request; nothing in it runs until the owner says yes to each permission in [What needs your yes](#what-needs-your-yes).

Last updated: 2026-10-16.

## Table of contents

- [The problem](#the-problem)
- [The loop](#the-loop)
- [What each part may and may never do](#what-each-part-may-and-may-never-do)
- [When it stops and tells the owner](#when-it-stops-and-tells-the-owner)
- [What needs your yes](#what-needs-your-yes)
- [How we test it first](#how-we-test-it-first)

## The problem

Today one card takes this path, and the owner carries every arrow marked "owner":

1. Factory opens a pull request and tells the owner.
2. The owner tells the lead.
3. The lead's reviewers comment on the pull request.
4. The owner tells Factory to read the comments.
5. Factory pushes fixes and tells the owner, and steps 2 to 4 repeat.

Factory cannot see review comments by itself (owner, 2026-10-16), and the lead and Factory cannot message each other. So the owner is the messenger, both ways, for every round.

## The loop

A scheduled job on the owner's Mac runs once an hour while the Mac is awake. It does one thing per run, in this order, then exits:

```mermaid
flowchart TD
  A[Hourly job starts] --> B{Factory PR open?}
  B -- no --> C{Next lane card?}
  C -- yes --> D[Start Factory on it]
  C -- no --> Z[Exit]
  D --> P[Job pushes the branch]
  P --> Z
  B -- yes --> E{New commits since review?}
  E -- no --> Z
  E -- yes --> F[Lead reviews it]
  F --> G{Nothing worse, CI green?}
  G -- yes --> H[Merge and retest row]
  G -- fixable --> I[Comments, then start Factory]
  I --> P
  G -- held --> N[Phone notice to owner]
  H --> Z
  N --> Z
```

In words:

- Start: when no Factory pull request is open, the job starts Factory on the next card in its lane (`docs/build/Factory_onboarding.md`, "How you work here"), in its own worktree. Factory builds, tests and commits; the job pushes the branch and opens the pull request from the body Factory wrote.
- Review: when a Factory pull request has commits the lead has not reviewed, the job runs the lead's review exactly as today: Factory's tests run, each part of the fix is removed in turn to check a test turns red, and for a behaviour change a judge, an adversary and, after the one fix round, a fresh verifier.
- Fix: findings go on the pull request as review comments, and the job starts Factory on them with a prompt that points at those comments. Factory commits; the job pushes.
- Merge: when CI is green and the fresh verifier finds nothing worse than develop, the job merges, removes the worktree and branch, and adds the card's row to `testing/Retest_product_owner.md` through a small docs pull request.

## What each part may and may never do

| Part | May | May never |
|---|---|---|
| The job's script | List and read pull requests; push branches named `factory/...`; open a Factory pull request from Factory's own body file; start the lead's review and Factory; send one phone notice | Push any other branch; force-push; touch `develop` or `production` directly; store a key anywhere in the repository |
| The lead's review run | Read the code; run tests, probes and gates in its own worktrees; post review comments; merge a `factory/...` pull request into `develop` when the conditions above hold; open and merge the docs pull request for the retest row | Merge anything that adds a migration, a dependency, or a change under `.claude/`, hooks, settings, auth or the graph credential; deploy to production; write to the knowledge graph; merge without the fresh verifier's PASS |
| Factory | Edit files inside its lane's fence, run its tests and builds, commit, in its own worktree (`droid exec --auto medium`) | Push, reach GitHub, deploy, run a migration (Factory's `--auto medium` level blocks remote writes; the job does the push) |

Limits, so a stuck loop cannot run up cost:

- One Factory pull request at a time.
- At most six runs a day and $3 of review spend a day; the job stops for the day at either.
- One fix round per card, as the review rules say. A second failure is a hold, never a third round.

## When it stops and tells the owner

One phone notice, under 200 characters, only for something the owner must act on:

- Factory's pull request body lists a question for the product owner.
- The fresh verifier holds a card: the notice names the two options the review rules allow, merge with the item named open, or close and re-split.
- The pull request touches anything the job may never merge.
- The day's run or spend limit is reached with work still waiting.

Everything else, start, review, fix, merge and the retest row, happens without a message.

## What needs your yes

The job is part of the security layer, so each item is a separate yes or no. Nothing is installed before every item has an answer.

1. A scheduled job in the Mac's user launch agents folder, outside the repository, running the script hourly while the Mac is awake.
2. The script, committed under `.claude/skills/factory-loop/` through its own pull request, since it sits under `.claude/`.
3. The lead's review run in print mode with an allowed-tools list instead of permission prompts: reading files; `git` without push to `develop` or `production` and without force; `gh pr` list, view, diff, checks, review and merge, the merge limited by the script to `factory/...` heads; the test, lint and build commands of `/ship` Step 0; its own reviewer agents. No permission bypass flag.
4. Factory run headless at `droid exec --auto medium`, which can edit, test and commit but cannot push or reach GitHub.
5. Factory's key, `FACTORY_API_KEY`, kept in the Mac's keychain and read by the script at run time, never written to the repository, a log or a prompt.
6. The job pushes `factory/...` branches itself, and only those.
7. The limits above: one pull request at a time, six runs and $3 of review spend a day, one fix round per card.

## How we test it first

1. Run the script by hand once on card 100 with the schedule off, and watch each step.
2. Leave one deliberate gap in a test, to check the review comments, Factory picks them up, and the fix round closes it.
3. Turn the schedule on for card 106 only.
4. Widen to the whole lane after one card merges with no owner message.
