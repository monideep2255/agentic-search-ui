# Card 51 and card 85 product check: The About page tells the truth

The product reviewer's pre-screen of card 51's slice (pull request #219, merge 599c6e67) and card 85 (pull request #220, merge c319dd42) on deployed develop, at 1280 and 390. It files findings and closes nothing; the owner's retest decides. No golden run (the owner's choice) and no questions asked of the search.

## Table of contents

- [Which app answered](#which-app-answered)
- [Findings](#findings)
- [Result per step](#result-per-step)
- [What was not captured](#what-was-not-captured)

## Which app answered

- API `/health` at 02:53:08 and 02:53:44 UTC: `{"status":"ok","app_env":"develop"}`.
- Web bundle on develop changed from `index-DB6gWcmy.js` (02:53:13 UTC) to `index-Bvd0kBlI.js` (02:53:44 UTC). The capture pages loaded `assets/index-Bvd0kBlI.js` at both widths (`capture_log.json`).
- Railway deployment list (CLI, read only, 02:54 UTC): search-agent-web SUCCESS at 599c6e67, created 2026-10-09 02:50 UTC; search-agent-api BUILDING at 599c6e67 (02:50 UTC), with SUCCESS at c319dd42 (card 85's merge, 02:35 UTC) still serving.

## Findings

### PR-51-01: The only About design still describes the coloured track the page just removed
- Kind: missing design
- Verdict: needs your eye
- What: `docs/build/design/README.md`'s coverage table lists "Integrations, docs and about" as NO design card, "Only ever inside `prototype/app.html`". That prototype's "Cite or refuse" section still reads "The track beside each answer shows one segment per claim, coloured by its layer, so an uncited claim is visible before you read a word." The deployed page no longer says this, which is card 51's point, so the page is now right and its only reference is wrong. The page was not judged against an invented look.
- Evidence: `about_prototype_1280.png`, `about_prototype_390.png` ("Cite or refuse" paragraph); `about_develop_1280.txt` has no "track" or "segment" anywhere.
- Why a person would care: "Whoever next rebuilds the About page from the design will put the track sentence straight back."
- NOT CLOSED

### PR-51-02: The deployed About page no longer follows the prototype's layout
- Kind: screen
- Verdict: needs your eye
- What: at both widths the deployed page runs "How an answer is built" (three layer cards, same position as the prototype), then a seven-stop walk "What happens to your question", "Cite or refuse" as one paragraph, and "Where the data comes from". The prototype runs the layer cards, "The run loop" (five rows), "The tool set" table, "Cite or refuse" with a second paragraph on listing and flagging sources, and "What it will not do" as a list. The sources-and-flag paragraph was gone before card 51 (card 51's diff, 68e9d7d5, touches only the two sentences). Not caused by this card; recorded because the prototype is the only design.
- Evidence: `about_develop_1280.png` beside `about_prototype_1280.png`; `about_develop_390.png` beside `about_prototype_390.png`.
- Why a person would care: "The design and the page tell me different things about how an answer is built, so I cannot tell which is meant."
- NOT CLOSED

### PR-51-03: Test query 102 lists as known a fault the page no longer has
- Kind: screen
- Verdict: needs your eye
- What: query 102's "Known, card 76" line says "the About walk says BRCA1's live searches run at the same time as the graph, where four of its thirteen run in a second round". The deployed walk, stop 3, now reads "One query returns the stored links from BRCA1 to its diseases, while most of the live searches run at the same time and four of the thirteen calls follow in a second round." So that half of the known fault looks fixed on the page, and the test document is stale. The other half (the Architecture page's layer 3 stop) was not captured.
- Evidence: `about_develop_1280.txt`, stop 3 "Knowledge graph" card; `testing/Test_queries_and_workflows.md`, query 102.
- Why a person would care: "The test sheet tells me to expect a mistake that is not there, so I start doubting the sheet."
- NOT CLOSED

## Result per step

| Check | 1280 | 390 | Rests on |
|---|---|---|---|
| Card 51: no coloured track beside the answer | Pass: no "track" or "segment" on the page | Pass: same text | `about_develop_1280.txt`, `about_develop_390.txt` (identical), screenshots read |
| Card 51: stop 5 reads "A copied cut is judged the same way, and a sentence with any copied piece held back is dropped whole" | Pass: in stop 5, "The answer is written, then streamed to you", which ends "That rule is called cite or refuse." | Pass | Text files, one match each; screenshot stop 5 read |
| Card 51: "Cite or refuse" reads "a line of framing with no source shows in muted ink" | Pass: "Each claim's marker carries its layer's colour, and a line of framing with no source shows in muted ink with no marker after it." | Pass | Text files, one match each; screenshots read |
| Card 51: matches test query 102's About line | Pass: query 102 puts the copied-cut sentence in Stop 5 and the marker and muted-ink sentence in "Cite or refuse", as the page does. Its "judged by the same model check" reads "judged the same way" on the page, same meaning. Its known card 76 line is stale (PR-51-03) | Pass | `testing/Test_queries_and_workflows.md` query 102, text files |
| Card 51: horizontal overflow at 390 | n/a | Pass: 0 (prototype also 0) | `capture_log.json`, `"overflow": 0`, no element past the viewport edge |
| Card 51: beside the prototype | Needs your eye (PR-51-01, PR-51-02); layer cards sit in the same place, the rest differs | Same | Screenshot pairs read |
| Card 85: `/health` answers develop | Pass: `{"status":"ok","app_env":"develop"}` at 02:53 and 02:55 UTC | | curl |
| Card 85: API deploy SUCCESS at 599c6e67 or later | Pass: search-agent-api SUCCESS at 599c6e67, created 2026-10-09 02:50 UTC, read at 02:55:37 UTC | | Railway CLI deployment list, read only |

Wording card, both widths: card 51 passed at 1280 and at 390.

Horizontal overflow at 390: 0. Surfaces with no design card: the About page (prototype only, and the prototype is stale, PR-51-01).

## What was not captured

- No golden run (the owner's choice) and no question asked of the search, so no answer was read and no time to answer measured. Card 85 changes logging only and was checked by deploy status and `/health` alone.
- The Railway MCP tool was not available in this session (its loader is disabled for sub-agents); the deployment list came from the Railway CLI, read only, with the same project id.
- The Architecture page, which query 102 also covers, was not in this brief.
- The blue "NCBI Agentic Search" bar that appears partway down both develop screenshots is the sticky footer (`AppShell.tsx`, `position: "sticky"`, an owner decision of 2026-09-12) drawn at its viewport position by the full-page capture. Not a page defect, and the text under it at stop 2 was read from the text files.
- The disclaimer modal showed on first load at both widths and was accepted by the capture script before the shots.
- Every verdict above rests on screenshots and text files captured and read by the reviewer in this folder; none rests only on a summary.
