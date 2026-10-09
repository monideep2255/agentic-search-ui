# Card 112 diagnosis: earlier searches vanish from "Your searches" after a re-ask

Finding PR-109-02 (product check of card 109): straight after a Stop, "Your searches" fell from 11 rows to 5. Every earlier "Which diseases are associated with BRCA1?" row was gone, and the new row had no second line. After a reload all 12 rows were back, the new one reading "No answer saved · Oct 9".

## Table of contents

- [What the evidence shows](#what-the-evidence-shows)
- [Cause 1: the rows vanish when the question is asked, not when it is stopped](#cause-1-the-rows-vanish-when-the-question-is-asked-not-when-it-is-stopped)
- [Cause 2: a stopped row never gets a second line](#cause-2-a-stopped-row-never-gets-a-second-line)
- [Where it began](#where-it-began)
- [Does it also happen after an answered re-ask](#does-it-also-happen-after-an-answered-re-ask)
- [Is the fix frontend only](#is-the-fix-frontend-only)

## What the evidence shows

`run_1280_log.json` beside the product review, read row by row:

| Moment | BRCA1 rows | Other rows | Total |
|--------|-----------|-----------|-------|
| Rail before asking | 7 (answered and stopped, Oct 8 and Oct 9) | 4 (two EGFR, GERD, Marfan) | 11 |
| Rail after Stop, before reload | 1 (the new one, `"meta": null`) | 4 | 5 |
| Rail after reload | 8 (the new one reads "No answer saved · Oct 9") | 4 | 12 |

Exactly the rows sharing the asked question's text left; every other row stayed. That points at a filter on question text, not at the Stop.

## Cause 1: the rows vanish when the question is asked, not when it is stopped

`frontend/src/App.tsx`, `ask`, the rail update made the moment a question is sent:

```ts
setHistory((current) => [
  { id: entryId, question },
  ...current.filter((item) => item.question !== question),
]);
```

- The filter drops every row whose question text equals the one just asked, restored rows from `GET /v1/history` included, and puts one fresh row on top.
- Nothing puts them back in the tab. The only other writer that adds rows is the seeding effect (`fetchHistory` then `mergeServerHistory`), and it runs once per token, at sign-in or on a reload. There is no `fetchHistory` refresh after Stop or after `done`.
- On reload `mergeServerHistory` keys on `trace_id`, never on text, so every server row comes back. That is why a reload restores them.
- The Stop is a bystander: the reviewer only looked at the rail after pressing it.

The filter was transcribed from the prototype's `start()` (`st.history.filter(...); st.history.unshift(...)`), which has no server history. Once phase 4.13 made history durable, with one server row per search, the filter started hiding real, separate searches.

## Cause 2: a stopped row never gets a second line

- A row asked in this tab starts with no `meta`. Its only writer is the meta effect keyed on `view.landed && view.meta`, which runs when a run lands.
- A confirmed stop (`deriveStopVerdict` returns "stopped" on the server's `cancelled` error) never lands, so nothing writes the row's meta, and `HistoryRail` renders no second line for an absent `meta`.
- After a reload the row comes from the server with `has_saved_answer: false`, and `formatHistoryMeta` (card 109) renders "No answer saved · <date>".

## Where it began

| Change | Touched this code? |
|--------|-------------------|
| Phase 4.13, commit `10da7faa` (2026-08-27, "render a restored row's date and move a re-ask to the top", merged with phase 4.13 in #69) | Yes. `git blame` and `git log -S` put the text filter here. |
| Card 59 (#208) | No. Its `App.tsx` diff touches only a comment that mentions history. |
| Phase 8.7 (#218) | No change to history code. |
| Card 109 (#225) | No change to `App.tsx` history code; it made restored rows read "No answer saved", which made the gap on the live row visible beside them. |

Cause 2 is as old as the meta effect: a live row has only ever had a second line once its run landed. Card 109 did not cause either part.

## Does it also happen after an answered re-ask

Yes. The filter runs when the question is sent, whatever the outcome. Asking a question already in the list, and letting it answer, also drops every earlier row of it until a reload. The new test's second arm (`frontend/src/App.historyAfterStop.test.tsx`, "after an answered re-ask, every earlier row stays too") is red on develop's code with 1 BRCA1 row where 4 belong.

## Is the fix frontend only

Yes. The server already returns every search as its own row, with the right flag and date. Both causes are in how `App.tsx` keeps its local list, so no backend or API change is needed.
