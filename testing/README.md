# Testing

Everything needed to test the product by hand or by machine, and the record of what each round of testing found and what shipped from it. Start with the one document that holds every query, then use the folders for detail.

## Start here

| If you want to | Open |
|---|---|
| Test the product by hand: every query worth typing, what you should see, why it matters to the person asking, and whether it is approved or awaiting your retest | `Test_queries_and_workflows.md`, the one document, organised by feature area |
| See what shipped on a given day and exactly what to retest from it | `Shipped_2026-09-22.md`, `Shipped_2026-09-20.md`, one file per day |
| See where every feature stands, what is next, and where the last session stopped | `UI_fix_plan.md`, the ordered work list and the single owner of what is being built and what is next |
| See every item that is built and live, with its test query and retest item | `UI_fixes_done.md`, split out of the plan on 2026-09-24 |

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

`UI_fix_plan.md`, `UI_fixes_done.md` and the `Shipped_<date>.md` files sit at the top level on purpose. The skills that close a session, `/phase-checkpoint` and `/ship`, write them by these paths, and code comments and tests point at them by these paths, so moving them buys nothing a line in this file does not. New per-feature query documents go under `Product/queries/`; a new day's shipped list is a new `Shipped_<date>.md` beside the others; a new measurement is a new dated folder under `Developer/reports/`.
