# Testing

Everything needed to test the product by hand or by machine, and the record of what each round of testing found and what shipped from it. Start with the one document that holds every query, then use the folders for detail.

## Table of contents

- [Start here](#start-here)
- [The folders](#the-folders)
- [Testing by hand](#testing-by-hand)
- [What lives where, and why the top level stays as it is](#what-lives-where-and-why-the-top-level-stays-as-it-is)

## Start here

| If you want to | Open |
|---|---|
| Test the product by hand: every feature, the queries to try, and what you should see from the chair of the person asking | `Test_queries_and_workflows.md`, the one document, organised by feature area. Its closing table, "Every feature and where to try it", gives the query for every item, board card and retest step |
| See what awaits your retest, in order | The Retest column of `UI_fix_plan.md`. Each card's steps are its query in `Test_queries_and_workflows.md` |
| See what shipped on a given day | `UI_fixes_done.md`: its "Session history" tables, and its "Shipped days, 2026-09-20 to 2026-09-23" section, which keeps what the daily shipped lists of those days recorded |
| See what is to do, what is being built and what awaits your retest | `UI_fix_plan.md`, the board: To do, Build in progress, Retest, in that order |
| See every item that is built and live, the detail behind every card on the board, and where the last session stopped | `UI_fixes_done.md`, split out of the plan on 2026-09-24 |
| See the remaining work outside the UI fix loop | `Future.md`: every open item from `requirements/Plan.md`'s Phase 7 and the archived continuation prompt's open items, each checked against the code first, with the closed ones and their evidence listed below it |

## The folders

| Folder | Who | What is in it |
|---|---|---|
| `Product/` | The product owner, testing by hand | `Product_workflows.md`, the original 22 hand tests in the same Testing / Query / Steps / Expected shape; `queries/`, one document per feature whose queries were written from the user's chair before the feature shipped (the isolate search is the first); `feedback/inbox/` for screenshots and notes; `reports/` for the write-ups of a testing round |
| `Developer/` | The assistant, testing with automated tests and a real browser | `Developer_workflows.md`, the 50 things the product must do in three tiers with the run commands; `scripts/`, the local measurement scripts; `reports/`, one dated folder per measurement or live proof, each with its evidence and a findings file whose verdict comes first |

## Testing by hand

1. Open the develop app in a browser: <https://search-agent-web-develop-2aeb.up.railway.app>
2. Work through `Test_queries_and_workflows.md`, any order, skip anything. Each query says what you should see.
3. When something looks wrong, drop a screenshot or a `.md` note into `Product/feedback/inbox/`.
4. Say "check the inbox".

## What lives where, and why the top level stays as it is

Three files sit at the top level on purpose:

- `UI_fix_plan.md`
- `UI_fixes_done.md`
- `Test_queries_and_workflows.md`

The two skills that close a session, `/phase-checkpoint` and `/ship`, write them by these paths. Code comments and tests point at them by these paths too. So moving them buys nothing a line in this file does not.

Where new material goes:

- A new per-feature query document goes under `Product/queries/`.
- A new measurement is a new dated folder under `Developer/reports/`.
- The daily `Shipped_<date>.md` lists of 2026-09-20, 2026-09-22 and 2026-09-23 were folded in on 2026-09-24: their retest steps into `Test_queries_and_workflows.md`, and everything else into `UI_fixes_done.md`.
