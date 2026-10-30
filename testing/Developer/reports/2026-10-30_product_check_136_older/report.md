# Product check, card 136 part 1: show older searches

Pre-screen on deployed develop at merge commit fa37d18c, before the owner retests. The API's `/health` read `{"status":"ok","app_env":"develop"}`. Signed in as a throwaway develop account. Nothing here closes anything; the owner's verdict does.

## Table of contents

- [Findings](#findings)
- [What was done](#what-was-done)
- [What was not captured](#what-was-not-captured)

## Findings

### PR-136A-01: At 1280 the list shows 20, the button loads the 3 older ones and then goes away
- Kind: screen
- Verdict: pass
- From: this change
- What a person sees: 20 searches with "Show older searches" at the foot of the list, below "Which diseases are associated with GCK?". One press brings the list to 23, the last three being the account's oldest searches, and the button disappears.
- Evidence: `w1280_01_first_page.png`, `w1280_01b_foot_viewport.png` (button at the foot), `w1280_02_after_press_1.png`; `w1280_log.json` steps 01 (count 20, button shown) and 02 (count 23, button gone, the press took 1.1 seconds). The API agrees: two pages, 20 then 3.
- NOT CLOSED

### PR-136A-02: At 1280 a new search goes on top and the loaded older ones stay
- Kind: screen
- Verdict: pass
- From: this change
- What a person sees: after loading the older three, asking "What does SOX2 do?" puts it first in the list; the list holds 24 and still ends with the three oldest searches.
- Evidence: `w1280_03_after_new_question.png`; `w1280_log.json`: `newOnTop` true, `droppedAfterAsk` empty, count 24. The only repeated question is "Which diseases are associated with GCK?" three times, which is three real searches in the account, not a duplicate row.
- NOT CLOSED

### PR-136A-03: At 1280 a reload shows the latest 20 with the button, and an older search reopens
- Kind: screen
- Verdict: pass
- From: this change
- What a person sees: after reload the list is 20, newest "What does SOX2 do?", with "Show older searches" at the foot. Loading everything again and opening "What does GCK do?", 23rd of 24, opens its saved answer: "SAVED ANSWER · ASKED OCT 30, 2026, 12:01 AM / What does GCK do?".
- Evidence: `w1280_04_after_reload.png`, `w1280_05_reload_all_loaded.png`, `w1280_06_older_opened.png`; `w1280_log.json` `openedText`.
- NOT CLOSED

### PR-136A-04: The button's look beside "+ New search" at 1280
- Kind: screen
- Verdict: pass
- From: this change
- What a person sees: a full-width outlined button with blue 13px semibold text, the same type and corner radius as "+ New search" but outlined rather than filled, so the rail keeps one filled blue action. It is 41px tall to the other's 39px, and 223px wide, the full list width, while "+ New search" is 181px because it shares its row with the hide control.
- Evidence: `w1280_01b_foot_viewport.png`; `w1280_log.json` step 01 `geom`.
- NOT CLOSED

### PR-136A-05: There is no design for "Show older searches"
- Kind: missing design
- Verdict: needs your eye
- From: this change
- What a person sees: a new control with no design behind it. `docs/build/design/README.md` lists the history rail as having no design screen ("the prototype is the only reference"), and the prototype's rail in `docs/build/design/design-system/prototype/app.html` has no older-searches control. The prototype also hides the rail below 860px, so nothing designs the phone drawer either. The look was judged for consistency with "+ New search" only, not against a design.
- Evidence: `docs/build/design/README.md` coverage table row "History rail and its collapsed strip | NO"; the prototype's `renderRail`.
- NOT CLOSED

### PR-136A-06: A guest sees no searches list at either width
- Kind: screen
- Verdict: pass
- From: earlier, rechecked
- What a person sees: a fresh browser shows the landing with "Log in", no rail, no collapsed strip, no drawer toggle, no "Your searches" and no "Show older searches"; the page sent no request to `/v1/history`. Nothing scrolls sideways at 390.
- Evidence: `guest_w1280.png`, `guest_w390.png`, `guest_log.json`.
- NOT CLOSED

### PR-136A-07: At 390 the drawer shows 20, the button loads the rest, the drawer stays open, and nothing scrolls sideways
- Kind: screen
- Verdict: pass
- From: this change
- What a person sees: in the phone drawer, 20 searches and "Show older searches" at the foot, above the account line. One press brings the list to 24 (by then the account held 24), ending with the oldest three, and the button disappears; the drawer stays open after the press. Horizontal overflow measured 0 at every step, including the reopened answer.
- Evidence: `w390_01_first_page.png`, `w390_01b_foot_viewport.png`, `w390_01c_drawer_element.png`, `w390_02_after_press_1.png`; `w390_log.json` steps 01 and 02 (`overflow` 0, `drawerStillOpen` true, the press took 1.1 seconds).
- NOT CLOSED

### PR-136A-08: At 390 a new search goes on top, a reload shows 20 with the button, and an older search reopens
- Kind: screen
- Verdict: pass
- From: this change
- What a person sees: after loading the older ones, asking "What does PAX6 do?" puts it first in the drawer, with the loaded older ones still there (25 in all). After reload the drawer shows 20 with the button. Loading everything and opening "What does GCK do?", 24th of 25, opens its saved answer and closes the drawer.
- Evidence: `w390_03_after_new_question.png`, `w390_04_after_reload.png`, `w390_05_reload_all_loaded.png`, `w390_06_older_opened.png`; `w390_log.json`: `newOnTop` true, `droppedAfterAsk` empty, `drawerClosedAfterOpen` true, `openedOverflow` 0.
- NOT CLOSED

### PR-136A-09: At 390 the button sits the same as at 1280
- Kind: screen
- Verdict: pass
- From: this change
- What a person sees: the same outlined button, 223 by 41px, 13px semibold blue text, full list width, between the last search and the account line, with clear space above it. It reads as secondary to "+ New search".
- Evidence: `w390_01b_foot_viewport.png`; `w390_log.json` step 01 `geom`.
- NOT CLOSED

### PR-136A-10: A search that failed shows in the list as "No answer saved"
- Kind: answer
- Verdict: needs your eye
- From: earlier, not this change
- What a person sees: one of the 17 setup questions, "What does PTEN do?", ended with "A step in this query hit a temporary error. Retrying the query may succeed." (error from the guardrail step, marked transient). It still takes a row in "Your searches", reading "No answer saved · Oct 30". That is honest, but one in 17 short gene questions failing on a temporary error is worth a glance.
- Evidence: `w1280_01b_foot_viewport.png` and `w390_01b_foot_viewport.png` (the PTEN row); the run's trace id `e6027d89-0342-42ec-a0cd-74cb47045ba4`, from the setup log kept outside the repository.
- NOT CLOSED

### PR-136A-11: At 390 "+ New search" shows in its darker hover colour when the drawer opens
- Kind: screen
- Verdict: needs your eye
- From: earlier, not this change
- What a person sees: when the drawer opens, "+ New search" is dark navy instead of the blue it is at 1280. The computed background was rgb(17, 47, 78) at 390 and rgb(32, 84, 147) at 1280, which looks like the hover or focus state on the first control the drawer focuses. Minor; recorded so it is not mistaken for part of this change.
- Evidence: `w390_01_first_page.png` against `w1280_01_first_page.png`; `geom.newSearch.bg` in both logs.
- NOT CLOSED

## What was done

| Step | Result |
|------|--------|
| Health check | `app_env` develop |
| Setup | The account had 6 searches. 17 questions of the form "What does GENE do?" were asked through the API's own endpoints as the same account, one at a time; 16 answered in 7.7 to 13.4 seconds and 1 failed (PR-136A-10). The API then paged 20 and 3 with `Cache-Control: no-store`. |
| 1280 flow | Script-driven, a fresh browser: count, press until gone, ask one new question, reload, load all, open an older one |
| 390 flow | The same in the phone drawer, with a touch viewport |
| Guest | Fresh browser at both widths, no sign-in |
| Questions asked through the app | 2, "What does SOX2 do?" at 1280 (12.9 s) and "What does PAX6 do?" at 390 (10.4 s) |

Screenshots show the account's address in the header and at the foot of the rail. It is a throwaway develop address on a reserved example domain, not a person's.

## What was not captured

- The prototype beside the live rail: the prototype keeps its state inside a closure, so a script could not open its rail with a list, and it hides the rail below 860px. `prototype_rail_w1280.png` and `prototype_rail_w390.png` show only the prototype's landing and were not used for any verdict. The look was judged against "+ New search" and the prototype's rail styles in code.
- Several presses: the account had at most 25 searches, so every older load was one press of up to 5 rows. A list needing two or more presses (over 40 searches) was not exercised in the browser.
- The failure path, "Older searches did not load. Try again.", was not forced.
- Another account's searches: only one account was used, so "you only ever see your own searches" rests on every row being a question this account asked, and on the guest view sending no history request.
- A guest after asking a question was not checked; the guest check is before any question.
- Spend: the API returns `total_cost_usd` as 0.0 to a signed-in user, so the cost of the 19 questions could not be measured from this side.
- The full-page shots at 390 with the drawer open show a grey strip under the drawer and, on the long saved answer, a footer band mid-page; both come from full-page capture of fixed elements, not from the app.
