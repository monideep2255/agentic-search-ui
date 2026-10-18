# Card 63 test queries 100 and 67, develop web app

- Develop commit: not exposed. `/health` returned `{"status":"ok","app_env":"develop"}` and the page carries no build id.
- Time run: 2026-09-29, about 12:00 to 12:10 (the app shows "asked Sep 29, 2026, 12:00 PM" and "12:02 PM")
- Account: s3-queries-c-20260929@example.com
- Browser: Chrome via Playwright, 1280 wide, full-page screenshots, signed in through the web UI
- Questions spent: 4 of 12 (BRCA1 once as the query 100 ask, the E. coli question, BRCA1 again for query 67 in the same tab, one guest CFTR question)

## Query 100: a "not yet confirmed" answer reopens too

Ask 1 (BRCA1) read "Based on 22 sources, not yet confirmed", so no further gene questions were needed.

- PASS: reopens at once, marked "Saved answer, asked <date>", no progress screen, no second charge. Evidence: `q100_reopened_300ms.png`, `q100_reopened.png`, `q100_reopened.txt`. About 350 ms after the click the saved screen was up, marker read "Saved answer · asked Sep 29, 2026, 12:00 PM", no loading text, no progress stepper. "No second charge" was judged from the absence of any run, not from a usage counter (the footer says "No search limit in effect yet"). `q100_newsearch_rail.png` is the rail before the click.
- PASS: trust line still "Based on 22 sources, not yet confirmed" with no check mark (`q100_reopened.png`, `q100_reopened.txt`, and the trust-line element text). The live answer was `q100_ask1_answer.png` and `.txt`.
- PASS with an observation: the BRCA1 answer had no note under it live (`q100_ask1_answer.txt`), so there was no note to keep. The live trust line ended "· High-risk claim"; the reopened screen shows only "Based on 22 sources, not yet confirmed". The live screen also has a collapsed "Sources 22" panel and the reopened screen shows no Sources section. Whether either is intended is for the owner to say.
- PASS: a guest's search is not saved. A signed-out fresh browser context asked `Which diseases are associated with CFTR?` and it answered; after "New search" and after a reload, no history rail exists and CFTR appears nowhere on the page. Evidence: `q100_guest_answer.png`, `q100_guest_after_newsearch.png`, `q100_guest_after_reload.png`, and the matching `.txt` files. The signed-in account's rail never showed CFTR (never asked there).
- NOT TESTABLE: the NCBI outage note wording. It cannot be triggered on demand.

## Query 67: a past search reopens with the answer it gave

- PASS: clicking a search in the rail shows the answer already given instead of a second search. Evidence: `q67_ecoli_newsearch_rail.png`, `q67_ecoli_reopened.png`, `q67_brca_reopened.png`.
- PASS: at once, no progress screen, no wait. About 300 ms after the click both the E. coli and the BRCA1 items showed the saved screen with no loading text and no progress stepper (`q67_brca_reopened_300ms.png`).
- PASS: marked "Saved answer · asked Sep 29, 2026, 12:02 PM", carries its own trust line ("Based on 21 sources, not yet confirmed" for E. coli, "Based on 22 sources, not yet confirmed" for BRCA1), and a Run again button is present on both. Evidence: `q67_ecoli_reopened.png`, `q67_brca_reopened.png`.
- PASS: the isolate answer renders as real tables (2 table elements on the saved screen, 0 lines of pipe characters). Evidence: `q67_ecoli_reopened.png`, `q67_ecoli_reopened.txt`.
- NOT TESTED: "Run again does a fresh search, charged as a normal search". The brief said not to press it. Only the button's presence was confirmed.
- PASS: the search asked in the same tab does not search again. The live BRCA1 answer read "13 tools · 23 sources from 2 layers" and "Based on 22 sources, not yet confirmed". Clicking it in the rail straight away showed the same "13 tools · 23 sources from 2 layers", the same trust line and the same text. After stripping citation markers (live uses superscripts, saved uses [n]) and the live-only follow-up block, the answer body diff was empty. Evidence: `q67_brca_live.txt`, `q67_brca_reopened.txt`, `q67_brca_live.png`, `q67_brca_reopened.png`.
- PASS: guests do not get this (same evidence as query 100's guest bullet). The clause "deleting the account deletes it" was not tested.

## Differences between a live answer and its saved copy (for the owner, not judged as failures)

- The E. coli live answer paged its isolate table ("Showing 1–10 of 20", "Page 1 of 2"). The saved copy shows all 20 rows on one page. Evidence: `q67_ecoli_live.txt`, `q67_ecoli_reopened.png`.
- The E. coli saved copy has a note the live answer did not show: "Note: the written summary of these records could not be verified against them, so this answer lists the records found instead". The live answer showed only the Pathogen Detection count note under a "NOTES" heading. Evidence: `q67_ecoli_live.txt`, `q67_ecoli_reopened.txt`.
- The saved screen shows no Sources section and no "High-risk claim" tag; the live screen has both. Evidence: `q67_brca_live.txt`, `q67_brca_reopened.txt`.
- After a fresh sign-in the rail listed one BRCA1 item and one E. coli item, though BRCA1 had been asked twice on this account. It appears deduplicated by question or the earlier one was replaced. Not investigated.

## Files

Scripts live in the scratchpad, not here. Screenshots and texts in this folder are named `q100_*` and `q67_*`. `q100_search_log.json` records the one gene question asked for query 100.
