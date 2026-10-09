# UI fixes done

- Every closed item from the UI fix loop lives here, with its detail and its history: built and live on develop, whether the product owner has approved it or it still awaits their retest or decision, or answered, superseded, run or accepted.
- What is being built and what is next live in `testing/UI_fix_plan.md`, which is the product owner's source of truth for work.
- Since the plan became a board on 2026-09-24, with only To do, Build in progress and Retest, this file also holds the cutoff, "Where we stopped", and the detail behind every item still on the board except the architecture cards, whose detail sits under the board's To do.

Closed history moved to [`testing/UI_fixes_archive.md`](UI_fixes_archive.md) on 2026-10-06; [Moved to the archive](#moved-to-the-archive) names each section that moved.

## Table of contents

- [Waiting for your retest](#waiting-for-your-retest)
- [Done features at a glance](#done-features-at-a-glance)
- [What is done, in summary](#what-is-done-in-summary)
- [How to read this](#how-to-read-this)
- [Where we stopped](#where-we-stopped)
- [Detail for items on the board](#detail-for-items-on-the-board)
- [Session history](#session-history)
- [Moved to the archive](#moved-to-the-archive)

## Waiting for your retest

Built and live on develop, waiting for the product owner's verdict, newest first.

- Moved here from the board on 2026-10-06 at the owner's request, so the board counts only work still to do.
- The queries to type and what you should see are in `testing/Test_queries_and_workflows.md`, by the number in the Queries column.
- Your verdict sets the Retest column to Approved, or sends the card back to To do with your words.

| # | What to check, in plain words | Item | Queries | Retest |
|---|---|---|---|---|
| 1 | A reopened answer shows the same trust words and "High-risk claim" tag the live answer showed: a BRCA1 answer's red tag comes back in the same red, an answer with no tag reopens with none, and an answer stopped by the cost limit reopens reading "Not verified", never with a tick. Answers saved before card 71 went live, late on 2026-10-08, show no tag | card 71 (#212) | 67 | Waiting for your verdict |
| 2 | A question about rs334 lists only rs334, never rs334348, rs334353 or rs334773; "What does the RS1 gene do?" is still about the gene. Still open: the rs334 row is named by its clinical significance labels and names no condition | card 37, part (#213) | 23 | Waiting for your verdict |
| 3 | Typing "Recent papers on BRCA1 from the last 10 years?", or picking a "How far back" choice the system no longer remembers, the plan line says the date range could not be applied and papers from any year were searched; a choice picked at once applies and says nothing | card 36, part (#215) | 108 | Waiting for your verdict |
| 4 | The About page no longer mentions a coloured track beside the answer, and its "Cite or refuse" section says a copied cut is judged by the same model check | card 51, part (#219) | 102 | Waiting for your verdict |
| 5 | Nothing to see: a graph column a model happens to name like MedGen's clinical features is never shown as MedGen's list (card 32, #214); a crash or failed step logs which search and why, never the error's text (card 85, part, #220) | card 32 (#214) and card 85, part (#220) | 87 | Waiting for your verdict |
| 6 | An answer that finished before you pressed Stop stays on screen with its sources and trust line, and history and the conversation keep it; Stop pressed while the search is still working shows "Stopping…" then "Search stopped" and records nothing | card 59 (#208) | 56 | Waiting for your verdict |
| 7 | A reopened answer written during an NCBI outage says the database was not answering when it was written, never "right now"; only on an answer saved during an outage, so it cannot be tried on demand | card 67 (#207) | 100 | Waiting for your verdict |
| 8 | No disease cell under the variant-to-disease table is blank without a reason ("None named: the ClinVar record says not provided", "Name could not be looked up"), and an answer lists one record once in its tables, for example "BRCA1 NCBIGene:672 [6, 7]" | cards 103 and 104 (#205) | 79, 107 | Waiting for your verdict |
| 9 | A sentence whose copied piece the sentence check holds back is dropped whole: no bare name like "Ribavirin [1]." and no sentence with its limit cut off | card 101, part (#204) | 106 | Waiting for your verdict |
| 10 | A reopened long answer keeps every source it cited, up to 100, so its "Based on N sources cited" line, its Sources rows and the history count agree; answers saved before 2026-10-08 still keep at most 50 | card 54 (#202) | 67, 107 | Waiting for your verdict |
| 11 | A reopened answer's table shows ten rows at a time with the live answer's "Showing 1–10 of N" bar, and on a phone each row stacks with its column names and fits the screen | card 71, part (#203) | 67 | Waiting for your verdict |
| 12 | A reopened saved answer lists its sources again, one row per page under its "Based on N sources cited" line, and long links wrap inside their row on a phone | card 102 (#199) | 107 | Waiting for your verdict |
| 13 | Under the variant-to-disease table the note reads "Each row lists the conditions the variant's ClinVar record names; the record's classification (for example pathogenic, benign or uncertain) is not shown here. Disease names are MedGen titles looked up from NCBI.", directly under its table at 1280 and 390, also when the table ends the answer | card 23 (#198) | 79 | Waiting for your verdict |
| 14 | One sources count everywhere: the line under the question, the trust line, the Sources heading, the history list after a reload and a reopened saved answer show the same number of pages; a page cited from the graph and from live NCBI is one card naming both layers, "from 2 layers"; "Confirmed by N independent databases" counts only cited databases that state the fact | card 22 (#197) | 107 | Waiting for your verdict |
| 15 | Before a reworded sentence is shown, the sentence check reads it against its paper: a bronchiolitis answer no longer says "babies" where its record says children | card 101, part (#193) | 106 | Waiting for your verdict |
| 16 | The command line and its MCP bridge: a queued agent request gets its full time once it starts and a plain "busy" message if it waits too long; Ctrl-C says you stopped the search; invisible-only feedback no longer erases a rating; credential errors name the right fix without printing the file's path | card 61 (#190, built by Factory) | none; `s3` and `s3 mcp` from the Integrations page | Waiting for your verdict |
| 17 | On a phone, a long variant name wraps inside the answer and the page never scrolls sideways; its citation number stays on the same line as the end of the name, in the record list and in the sentence | cards 43 and 43b (#181, #187, built by Factory; checked on develop by the lead) | 105 | Waiting for your verdict |
| 18 | The design prototype's home page is light, like the app's, so screen checks stop flagging the live home page; closes by itself seven days after it reached Retest on 2026-10-06, unless you object (a design-file card the lead's reviewer passed at both widths) | card 47 (#188, built by Factory) | none, a design file | Closes by itself seven days after 2026-10-06 unless you object |
| 19 | A plain-language GERD answer never says "children" where its paper says young children, or drops "potentially"; Researcher answers are unchanged. It also shows about one sentence fewer, mostly the risk-factor sentence, which card 101 works on | card 99 (#184) | 75, 68 | Waiting for your verdict |
| 20 | The "Take the tour" button on the home page stays readable when the pointer rests on it: dark blue text and border, contrast 6.5 where it was 4.4 | card 44 (#183, built by Factory) | 63 | Waiting for your verdict |
| 21 | The Mediterranean question names Familial Mediterranean fever and has a written answer | card 89 (#175) | 73 | Waiting for your verdict |
| 22 | GERD shows a written answer above its tables at both depths | card 88 (#161, #163) | 75, 68 | Waiting for your verdict |
| 23 | A sentence that cites a record shows the record words it was checked against, even when another sentence cites the same record; seen today in the command line's `s3 --json` and the API's citation events, not yet on the web screen | card 57 (#161) | none | Waiting for your verdict |
| 24 | A question about one paper's linked data lists the records NCBI links to it, or says plainly there are none | card 74 (#172) | 104 | Waiting for your verdict |
| 25 | E. coli isolates show their resistance genes in Plain language, the colistin search finds mcr carriers, and the answer says which gene families were searched | card 94, part (#158, #165, #169, #174) | 33 to 37 | Waiting for your verdict |
| 26 | A chromosome window lists its dbVar records, and its first sentence shows no raw bracketed numbers | cards 92 and 95 (#158, #164) | 27, 29 | Waiting for your verdict |
| 27 | The TP53 dataset question no longer says a search did not finish, and when a search does fail the note says which and why | card 91 and 77 (#160, #169) | 25, and "Any trials for GERD?" in 76 | Waiting for your verdict |
| 28 | "recent-onset diabetes treatment" is answered directly; GERD, BRCA1 and Marfan alone are still asked back | card 87 (#162) | 84, 76 | Waiting for your verdict |
| 29 | Muir-Torré syndrome is spelled correctly, and no OMIM row appears twice | cards 96 and 97 (#170, #166) | 24 | Waiting for your verdict |
| 30 | When the guard model sends back an empty reply, the search is retried and, if it still has no reply, the person is asked to try again, where before the search ended "failed unexpectedly"; it is rare and cannot be typed on purpose | card 98 (#166) | none, nothing to type | Waiting for your verdict |
| 31 | When no written summary survives, one plain line says why and the records found are listed | card 46 and decision D1 (#168) | none yet | Waiting for your verdict |
| 32 | The Integrations page shows the command line tools' commands, the About page shows its layer cards first, and two page sentences are corrected | cards 79, 80 and 85, part (#167) | 102, 59, 60 | Waiting for your verdict |
| 33 | Every library's license text ships with the web app | card 86 (#157) | 99 | Waiting for your verdict |
| 34 | The MODY genes question passes its citation check; superseded by 11.20, and the board proposes closing it | card 13 | 78 | Waiting for your verdict |
| 35 | The architecture deep dive is merged (`visualizations/System_3_deep_dive.md`); the board proposes closing it | card 39 | none | Waiting for your verdict |
| 36 | The server address is gone from every tracked file (pull request #109); only git history holds it, and rewriting history is your call (recommendation: no). The board proposes closing it | card 41 | none | Waiting for your verdict |
| 37 | The command line and an AI agent do what the web does, installed and run as the Integrations page prints them; what the product review found is cards 61, 62 and 63 | cards 49 and 21, phase 8.10 | 90 to 97, and 60 | Waiting for your verdict |
| 38 | A graph search that cannot finish gives up after 30 seconds, not 90 | card 45, R-09 | 59 | Waiting for your verdict |
| 39 | A one-to-three-word question is asked back, with choices written for its subject | 12.3 | 76 | Waiting for your verdict |

## Done features at a glance

Done here means closed: built and live on develop, or answered, superseded, run or accepted, as the Status column says.

- For an item that is built and live, the Status column also says whether the product owner has approved it or it still awaits their retest or decision.
- Those actions are tracked on the board in `testing/UI_fix_plan.md` (decisions in its To do column) and, for retests, in "Waiting for your retest" above.

| Item | What you see | Status | Test query, `Test_queries_and_workflows.md` |
|---|---|---|---|
| 1.1 | Remove the five-search guest limit | Approved | 1, 53 |
| 1.2 | Remove the free-search and moved-into-an-account walls | Approved | 1 |
| 1.3 | Remove the ten-attempt guest limit | Approved | 45, 55 |
| 1.4 | Keep the cost caps, raise the anonymous daily cap to 1,000 | Approved | 52 |
| 1.5 | One Log in button | Approved | 49, 50 |
| 1.6 | Log out returns to the home page | Approved | 49 |
| 1.7 | The daily cap message reaches the screen | Approved |  |
| 1.8 | Update the test checklist for the new sign-in flow | Approved |  |
| 2.1 | Centre the sign-in box | Approved | 49 |
| 2.2 | One box width from progress to answer | Approved | 1 |
| 2.3 | Fix the header and footer in place | Approved | 59 |
| 2.4 | Smooth transitions between screens | Approved | 59 |
| 2.5 | Header and footer in the same blue | Approved | 59 |
| 2.6 | New search as a distinct blue button | Approved | 56 |
| 2.7 | Add the three missing logo colours to the theme | Approved |  |
| 2.8 | A light home page | Approved | 59 |
| 2.9 | Screens centred between header and footer | Approved | 59 |
| 2.10 | No idle wait after pressing Search | Approved | 1 |
| 2.11 | Searches that fail at the Think step | Approved |  |
| 2.12 | A bigger search box on the home page | Approved | 59 |
| 2.13 | NCBI design system: the changes possible today | Approved |  |
| 2.14 | A favicon | Approved | 59 |
| 3.1 | Remove the red refusal pills | Approved | 45, 46 |
| 3.2 | Make the NCBI search address a clickable link | Approved | 46 |
| 3.3 | A grey label matched to the refusal reason | Approved | 45, 46 |
| 3.4 | "Search stopped" with Run again and New search | Approved | 56 |
| 4.1 | Stay signed in on reload, and history on phones | Approved | 49, 51, 59 |
| 5.1 | Rebuild the Integrations page from the reference layout | Approved | 59 |
| 5.2 | Correct the GraphQL example | Approved | 59 |
| 5.3 | Fix the MCP server rejecting every request | Approved | 60 |
| 5.4 | Fold Docs into Integrations | Approved | 59 |
| 5.5 | Rebuild the disclaimer at the reference size | Approved | 61 |
| 5.6 | Four Integrations cards with real summary chips | Approved | 59 |
| 5.7 | Disclaimer wording from the reference structure | Approved | 61 |
| 6.1 | Let the automated test harness see a real knowledge-graph answer | Live |  |
| 7.1 | Follow-ups keep the earlier context | Approved | 20 |
| 7.2 | "Yes, go deeper" continues the same search | Approved | 7, 20 |
| 7.3 | A follow-up stays on the same screen | Approved | 20 |
| 7.4 | A folded turn keeps the whole earlier answer, with room between turns | Approved | 20 |
| 7.5 | A follow-up that refers to nothing asks for the missing detail | Approved | 20 |
| 8.1 | Search all three layers at the same time | Approved | 5 |
| 8.2 | A lead scientist hands off to three named scientists | Approved | 1, 8 |
| 8.3 | Progress steps named for the scientist | Approved | 1, 8 |
| 8.4 | Scientists stay random on every visit | Approved 2026-09-29, batch retest | 9 |
| 9.1 | Two answer modes, Plain language and Researcher | Approved | 2 |
| 9.2 | An info button explaining the two modes | Approved | 3 |
| 9.3 | Plain language: about 250 words in three paragraphs | Superseded |  |
| 9.4 | Researcher: a full page organised by topic | Superseded |  |
| 9.5 | Short paragraphs of prose with citations inline | Approved | 1, 5 |
| 9.6 | The answer streams in sentence by sentence | Approved | 1 |
| 9.7 | Fix answers that open broken or garbled | Approved | 1 |
| 9.8 | Fix the uncited note and awkward disease names | Approved for the disease names; superseded for the further-records note | 1 |
| 9.9 | Trust signals become one plain line | Approved for the one-line shape; wording is your decision | 5 |
| 9.10 | Researcher headings, Plain language without them | Superseded |  |
| 9.11 | A small medical-advice line on Plain language answers | Your decision, not an approval | 2 |
| 9.12 | The depth cannot change mid-search | Approved 2026-09-29, batch retest | 4 |
| 10.1 | Stop the flagship questions from refusing | Live | 1, 7 |
| 10.2 | History shows the saved answer instantly | Approved 2026-09-29, batch retest | 67 |
| 10.3 | The consistency run, three tries per golden question | Run 2026-09-22 |  |
| 11.1 | Researcher answers should follow your reference screenshot | Superseded by 11.12 |  |
| 11.2 | Delete the reference screenshot and the sets 8 and 9 session prompt when done | Done |  |
| 11.3 | Stop after sets 8 and 9, do not touch set 10 | Done |  |
| 11.4 | Does the research layer make people wait 45 seconds? | Answered |  |
| 11.5 | Citations are too big and overwhelm the answer | Live, approved | 1, 5 |
| 11.6 | The answers lack the level of detail of your reference prototype | Live, approved | 79 |
| 11.7 | Switch the answer-writing model's reasoning setting to none | Live, approved |  |
| 11.8 | Make the process quicker | Live, approved | 1 |
| 11.9 | Show "[scientist] is writing the answer…" while it loads | Live, approved | 5 |
| 11.10 | Use parallel sub-agents, each on a model matched to the task | Done |  |
| 11.12 | The answer reads as one block; break it into readable paragraphs, headings and tables | Live, approved | 2, 5 |
| 11.13 | The same readable format in both Plain language and Researcher | Superseded by 11.31 |  |
| 11.14 | Copying the answer picks up "Source 1, layer 2" text | Approved 2026-09-29, batch retest | 6 |
| 11.15 | The answer does not stream | Superseded by 11.16 |  |
| 11.16 | Signal the write step as it starts, reveal sentences at reading pace | Live, approved | 1, 5 |
| 11.17 | Why only gene records, and not PubMed, PMC or NCBI Datasets? | Live, approved | 5, 19 |
| 11.18 | Search everything in all three layers, sources exact | Answered |  |
| 11.19 | "Variants in GCK causing MODY" should answer every time | Live, approved | 7 |
| 11.20 | "What genes are associated with MODY?" should answer | Live, approved | 78 |
| 11.21 | Search the right resource for each question, not only PubMed | Live, approved, both decisions done | 19 |
| 11.22 | PubMed and PMC should provide context for the answers | Live, verified | 13 |
| 11.23 | Check whether the NCBI API key allows 100 requests per second | Answered |  |
| 11.24 | How do I test what is built so far? | Answered |  |
| 11.25 | What from Set 11 is on develop? | Answered |  |
| 11.26 | The answers do not look like the approved mockup | Live, approved | 17 |
| 11.27 | Too much bold: only the title or main point should be bold | Live, approved | 77 |
| 11.28 | The move from searching to the streamed answer is too quick | Live, approved | 18 |
| 11.30 | Make sure every integration on the Integrations page actually works, end to end | Approved 2026-09-29, batch retest | 60 |
| 11.31 | The two answer modes look the same, and they should not | Live, approved as is | 14, 2 |
| 11.33 | PubMed abstracts reach the answer page cut off mid-word | Approved | 11 |
| 11.34 | A multi-sentence abstract loses its citation entirely in the code-built tail | Fixed and live | 13 |
| 11.35 | "The Notes section is super confusing. remove it" | Live, approved | 7 |
| 11.36 | The answer-modes info button still promised "about 250 words in three paragraphs" | Approved 2026-09-29, batch retest | 3 |
| 11.37 | Layer 1 knowledge-graph sources are invisible in the source list | Accepted, not a defect to fix |  |
| 12.1 | A disease question searches one place and refuses | Failed the 2026-09-29 batch retest, back in To do as card 90 | 68 |
| 12.2 | A literature question is refused as "Outside biomedical research" | Approved 2026-09-29, batch retest | 70 |
| 12.3 | Do we ask a clarifying question when a query is one to three words? | Live, awaiting your retest | 76 |
| 12.4 | "If it didn't have an answer, why would I 'continue the conversation'?" | Approved 2026-09-29, batch retest | 71 |
| 12.5 | Can these questions be answered at all, and how? | Answered | 68, 69, 73 |
| 12.6 | The product already writes a good clarifying question and throws it away | Already built, closed by measurement | 48 |
| 12.7 | A question naming no gene and no disease finds nothing at all | Approved 2026-09-29, batch retest | 69 |
| 12.8 | The trust line under an answer undercounts its sources | Approved 2026-09-29, batch retest | 74, shared with 12.11 |
| 12.9 | Plain language and researcher return the SAME text | Approved 2026-09-29, batch retest | 72 |
| 12.10 | The answers list what was found instead of answering | Failed the 2026-09-29 batch retest, back in To do as card 89 | 73 |
| 12.11 | The sources chip and the trust line disagree | Approved 2026-09-29, batch retest | 74 |
| 12.12 | Broken sentences and repeated records | Failed the 2026-09-29 batch retest, back in To do as card 88 | 75 |
| 12.13 | Clicking a search in the history rail re-runs it instead of showing the saved answer | Approved 2026-09-29, batch retest | 67 |
| 12.15 | A question asking for RECENT papers should ask what recent means: "recent paper on statin, should have asked a clarification of year range" | RAISED 2026-09-23 in `testing/User-feedback/fix-2/`. LIVE on develop 2026-10-05 as card 87 (#162), in Retest, queries 84 and 76; it was NOT STARTED | The product owner's comment is the screenshot's filename. `recent papers on statins` is four words and names what it wants, so 12.3's rule rightly does not ask it back; this is a different clarification, about a time window rather than a subject. Recorded so it is not lost; not being built. Evidence: `testing/Developer/reports/2026-09-23_fix2/findings.md` |
| card 58 | Stop works until the first sentence of the answer is on screen, and a stop in that window shows "Search stopped" and nothing of the answer | Approved 2026-09-29, batch retest | 98 |
| card 60 | The web app carries its libraries' license notices: React, React DOM and MUI, each with its version and license text | Failed the 2026-09-29 batch retest, back in To do as card 86 | 99 |
| card 63 | A "not yet confirmed" answer reopens from your searches with its trust line and notes, and during an NCBI outage the note says the database is down and may be missing things, never that the answer has none | Approved 2026-09-29, batch retest | 100, 67 |
| card 62 | The Integrations page's install works on the first try, and `s3` shows the web's trust line for each answer | Approved 2026-09-29, batch retest | 101 |
| card 53 | The Architecture and About pages, the KGX manifest and the project documents state what the code does | Approved 2026-09-29, batch retest | 102 |
| card 73 | A search that crashes writes its reason and trace id to the log | Approved 2026-09-29, batch retest | none, nothing to try by hand |
| cards 49 and 21, phase 8.10 | The command line and an AI agent do what the web does, installed and run as the Integrations page prints them; what the product review found is cards 61, 62 and 63 | Live, awaiting your retest | 90 to 97, and 60 |
| card 1, T-8.6-06 | An answer about something else never says "MedGen lists no clinical features for ..." | Approved 2026-09-29, batch retest | 87 |
| card 31, T-8.6-06 | At Researcher depth, a question about a disease's features names them in the written answer too | Approved 2026-09-29, batch retest | 81 |
| T-8.6-04, T-8.6-05, R-02 | A question carrying hidden instructions, or asking to change the graph, is refused, and Jev makes that call | Approved 2026-09-29, batch retest | 88, 89 |
| card 45, R-09 | A graph search that cannot finish gives up after 30 seconds, not 90 | Live, awaiting your retest | 59 |
| card 3, T-8.6-07 | The second writing call runs only when it can change the answer | Approved 2026-09-29, batch retest | Nothing to try by hand: `tracker/phase_8.6.md`, T-8.6-07 |
| card 34, T-8.6-03 | Jev's and DeepSeek's picks are compared offline instead of racing the answer | Approved 2026-09-29, batch retest | Nothing to try by hand: `tracker/phase_8.6.md`, T-8.6-03 |
| 13.2 | The Answer modes card gives each mode its own block and says what the mode gives, never who the reader is; on a phone it now fits on screen | Approved 2026-09-29, batch retest | 86 |
| Jev as the classifier, golden row G-038 | A question the biomedical word list does not know is judged by the classifier, not refused: the tree of life is answered, pizza is refused, and off-topic follow-ups are refused | Approved 2026-09-29, batch retest | 83 |
| 12.15 | "Recent papers" asks how far back to search, and the choice narrows the papers | Failed the 2026-09-29 batch retest, back in To do as card 87 | 84 |
| 12.16 part 3 | Whether a question wants papers is a classifier's choice, not a word list | Approved 2026-09-29, batch retest | 85 |
| Jev, the probability model trial | Jev makes the small choices on develop and DeepSeek's pick is recorded beside it: read the comparison table | Approved 2026-09-29, batch retest | Nothing to try by hand: `testing/Developer/reports/2026-09-25_phase_8.2_golden/decisions_comparison.md` |
| 11.32, the function catalogue | The NCBI and enrichment calls are listed once as typed functions the classifier can choose from | Approved 2026-09-29, batch retest | Nothing to try by hand: `src/system_03_search_agent/tools/catalogue.py` |
| the golden rows | Golden row G-035 accepts the Taxonomy link the product cites | Approved 2026-09-29, batch retest | Nothing to try by hand |
| disease names, the hand-over | The graph's data gaps are handed to the repository that writes the graph | Approved 2026-09-29, batch retest | Nothing to try by hand: read `docs/data-engineering/Graph_data_hand_over_2026-09-25.md` |
| 2.13, the four type values | The design card's four type values match the shipped code | Approved 2026-09-29, batch retest | Nothing to try by hand |
| the checkpoint line | `/phase-checkpoint` names the counts line by what it holds | Approved 2026-09-29, batch retest | Nothing to try by hand |
| 12.14 | A question about a disease's features names them, each cited to MedGen: in the written answer at Plain language, in the list at Researcher | Approved 2026-09-29, batch retest | 81 |
| 12.17 | A good question is never refused because the think step's reply was malformed | Approved 2026-09-29, batch retest | 80 |
| the ceiling, the byte ceiling | An answer can cite up to 30 sources, and a question about papers reaches them | Approved 2026-09-29, batch retest | 82 |
| the live NCBI unit test | An NCBI outage no longer turns the build red | Approved 2026-09-29, batch retest | Nothing to try by hand: CI's unit gate deselects the live test |
| G-019 | MeSH terms show as real terms, each linked to its MeSH record | Approved 2026-09-29, batch retest | 64 |
| the opening count | The opening sentence's count agrees with the list beneath it | Approved 2026-09-29, batch retest | 65 |
| the phenotype template | The Marfan phenotype question no longer says "I could not find evidence"; what it answers instead is 12.14 in To do | Approved 2026-09-29, batch retest | 66 |
| G-033, G-037 | Two questions keep their own graph search: MLH1 and MSH2, and GEO datasets for TP53 | Failed the 2026-09-29 batch retest, back in To do as card 91 | 24, 25 |
| the coordinate range | A chromosome range is answered with its genes and records, and a range with no assembly asks which | Failed the 2026-09-29 batch retest, back in To do as card 92 | 27, 28, 29 |
| the question's own words | An answer never lists the question's own words as diseases it did not address | Failed the 2026-09-29 batch retest, back in To do as card 93 | 23, 25 |
| the accessions | A BioProject or BioSample accession is answered, and an unknown one is named as not found | Approved 2026-09-29, batch retest | 30, 31, 32 |
| G-035 | Pathogen Detection isolate questions answer with a table of isolates and their resistance genes | Failed the 2026-09-29 batch retest, back in To do as card 94 | 33, 35, 36, 38, 39, 40, 44, and `testing/Product/queries/Isolate_search_queries_and_workflow.md` |
| card 89 | The Mediterranean question names Familial Mediterranean fever and has a written answer | Live, awaiting your retest | 73 |
| card 88 | GERD shows a written answer above its tables at both depths | Live, awaiting your retest | 75, 68 |
| card 74 | A question about one paper's linked data lists the records NCBI links to it, or says plainly there are none | Live, awaiting your retest | 104 |
| card 94, part | E. coli isolates show their resistance genes in Plain language, the colistin search finds mcr carriers, and the answer says which gene families were searched | Live, awaiting your retest | 33 to 37 |
| cards 92 and 95 | A chromosome window lists its dbVar records, and its first sentence shows no raw bracketed numbers | Live, awaiting your retest | 27, 29 |
| cards 91 and 77 | The TP53 dataset question no longer says a search did not finish, and when a search does fail the note says which and why | Live, awaiting your retest | 25, and "Any trials for GERD?" in 76 |
| card 87 | "recent-onset diabetes treatment" is answered directly; GERD, BRCA1 and Marfan alone are still asked back | Live, awaiting your retest | 84, 76 |
| cards 96 and 97 | Muir-Torré syndrome is spelled correctly, and no OMIM row appears twice | Live, awaiting your retest | 24 |
| card 46 and decision D1 | When no written summary survives, one plain line says why and the records found are listed | Live, awaiting your retest | none yet |
| cards 79, 80 and 85, part | The Integrations page shows the command line tools' commands, the About page shows its layer cards first, and two page sentences are corrected | Live, awaiting your retest | 102, 59, 60 |
| card 86 | Every library's license text ships with the web app | Live, awaiting your retest | 99 |
| card 13 | The MODY genes question passes its citation check; superseded by 11.20, and the board proposes closing it | Live, awaiting your retest | 78 |
| card 98 | An empty reply from the guard model asks the person to try again | Live, awaiting your retest | none, nothing to type |
| card 22 | One sources count everywhere, each total naming what it counts; a page cited from two layers is one card naming both | Live, awaiting your retest | 107 |
| card 23 | The note under the variant-to-disease table says what its rows are and that the classification is not shown, directly under its table | Live, awaiting your retest | 79 |
| card 102 | A reopened saved answer lists its sources, one row per page | Live, awaiting your retest | 107 |
| card 71, part | A reopened answer's tables page ten rows at a time and stack on a phone with their column names | Live, awaiting your retest | 67 |
| card 54 | A reopened long answer keeps every source it cited, up to 100 | Live, awaiting your retest | 67, 107 |
| card 101, part | A sentence whose copied piece the sentence check holds back is dropped whole, never shown cut | Live, awaiting your retest | 106 |
| cards 103 and 104 | No disease cell is blank without a reason, and an answer lists one record once in its tables | Live, awaiting your retest | 79, 107 |
| card 59 | An answer that finished before Stop was pressed stands on screen, in history and in memory | Live, awaiting your retest | 56 |
| card 67 | A reopened outage answer says the database was not answering when it was written, never "right now" | Live, awaiting your retest | 100 |
| card 71 | A reopened answer shows the live answer's trust words and High-risk claim tag | Live, awaiting your retest | 67 |
| card 37, part | A question about rs334 lists only rs334, never its near misses | Live, awaiting your retest | 23 |
| card 36, part | A date range that could not be applied is named in the plan line | Live, awaiting your retest | 108 |
| card 32 | A graph column named like MedGen's clinical features is never shown as them | Live, awaiting your retest | 87 |
| card 51, part | The About page no longer describes the retired track beside each answer | Live, awaiting your retest | 102 |
| card 85, part | A crash or failed step logs which search and why, never the error's text | Live, awaiting your retest | none, nothing a person sees |

## What is done, in summary

Moved to [`testing/UI_fixes_archive.md`](UI_fixes_archive.md#what-is-done-in-summary).

## How to read this

Start with [Where we stopped](#where-we-stopped). That section is the cutoff:

- What is live
- What is waiting on the product owner
- And what the next session does first

Everything above it in the old plan was the record of how each item got to
its current state. Since the 2026-09-24 split, that record is this file, and
"What is live on develop" is under "History and what is live" in [`testing/UI_fixes_archive.md`](UI_fixes_archive.md#history-and-what-is-live).

The marks used in the set tables and the shape of a set moved to [`testing/UI_fixes_archive.md`](UI_fixes_archive.md#how-to-read-the-set-tables).

### The board's waiting on column

What the Waiting on column means:

- Your decision: waiting on you: decisions.
  - Each is written so the answer is: yes, no, or pick one.
  - None blocks work in flight
- Nobody on it: still to build, nobody on it
- Your retest: waiting on you: retests.
  - Each of these is built, live on develop, and needs your eyes before it counts as done.
  - Nothing is blocked on them
- Parked: parked, and never work the product owner will build.
  - A discussion that precedes a build waits on Nobody on it, not Parked.
  - Corrected 2026-09-24 on the product owner's instruction, after discussions that precede a build had been marked Parked

"How the board came to be" moved to [`testing/UI_fixes_archive.md`](UI_fixes_archive.md#how-the-board-came-to-be).

## Where we stopped

The cutoff. It is updated at the end of every working session, so the next
session starts here rather than reconstructing state.

LAST UPDATED 2026-10-08, AT THE END OF THE NIGHT. THE ONE THING TO KNOW:

- Six cards merged overnight, each behind CI, a judge, an adversary, one fix round and a fresh verifier, then checked on develop at 1280 and 390, and wait for your retest: 71 (#212), 37 part (#213), 32 (#214), 36 (#215), 51 part (#219) and 85 part (#220)
- Phase 8.7 is built, reviewed, fixed once and checked live on its branch, and waits for your call on pull request #218: its fresh verifier found two things worse than develop
- Parked with their reasons: the guardrail (84 and 72), card 15's next step and card 101's last slices

`HANDOFF.md` says what to do next.

What is live on develop:

- Every card in "Waiting for your retest" above, newest first: tonight's cards 71, 37 part, 36, 51 part, and 32 with 85 part on top. Each is one row in "Done features at a glance", with its query number.
- Card 98 (an empty guard reply asks the person to try again) is live with no query to type.
- Develop's API carries `CLASSIFIER_PROVIDER=jev`, `SYSTEM_DAILY_CAP_USD=25` and its own `SYNTH_MODEL`, so a code default does not change develop's writer. Migration 0011 (the risk tier column) ran on develop late on 2026-10-08. Both Railway services redeploy on every push to `develop`.
- What each numbered phase delivered and what stays open: its ledger, `tracker/phase_N.M.md`. Phase 8.7's ledger is on its branch until it merges.
- Production is unchanged on `v0.2.0`. The release job tags `production` and never pushes to it, and only the owner changes `develop` and `production`.

What awaits the product owner is under "What is waiting on the product owner" below.

This section is also the shared plan.

- What we agreed, what is done and what is next all live here rather than in a session that disappears, so the product owner and whoever picks this up read the same record.
- Since the 2026-09-24 split, what is done lives in `testing/UI_fixes_done.md`.

"The result that should shape what happens next" moved to [`testing/UI_fixes_archive.md`](UI_fixes_archive.md#the-result-that-should-shape-what-happens-next).

### What is parked, and why

- Waiting for the owner, not parked: phase 8.7 (cards 2, 50 and 5), pull request #218. Its fresh verifier found that on the web a citation chip under a summary sentence no longer shows the words it was checked against (A04, card 57) and that every summary waits up to about 3.5 s for the classifier's lead-sentence pick (A07). Its record: `tracker/phase_8.7.md` on the branch; its live check: `testing/Developer/reports/2026-10-08_phase_8.7/live_check.md`.
- Parked on 2026-10-08 overnight, each with its reason and its `DECISIONS.md` row:
  - The guardrail, cards 84 and 72: its fix round admitted a follow-up after a long server pause that develop refuses, refused pause cases develop admits, and over-charged Jev replies (the lead's brief misstated the rule). Re-split proposed. Code: local tag `parked/card84-72-guardrail-2026-10-08`; reports: `testing/Developer/reports/2026-10-08_guardrail_design/`. Step 2 (host routing) parked separately for want of a week of logs that name a cut call's host.
  - Card 15's next step: showing one record for every non-count question gave wrong or thinner answers than develop. Needs one checked template per question shape. Code: `parked/card15-checked-searches-2026-10-08`; reports: `testing/Developer/reports/2026-10-08_card15/`.
  - Card 101's last slices: a new sentence splitter chained records into units that let a writer's quote through without its negation. Needs a design for where a record sentence ends. Code: `parked/card101-last-slices-2026-10-08`; reports: `testing/Developer/reports/2026-10-08_card101/`.
- Waiting on a merge: cards 18, 19, 30, 38 and 94's last slices wait for phase 8.7, and card 35 for the guardrail's re-split, since each rewrites code those change. Their diagnoses: `testing/Developer/reports/2026-10-08_overnight/`.
- Older work parked at tags: `parked/phase-8.4-2026-09-25`, `parked/phase-8.8-snippets-2026-09-25` and `parked/verify-facts-118-2026-09-27`.
- THE ARCHITECTURE WORK IS NOT PARKED.
  - The product owner will build it, so its six cards, 8 to 13 in the board's To do, wait on nobody.
  - Corrected 2026-09-24 on their instruction: the board had marked three of those items Parked and moved every word of their detail into this file.
  - That detail, with their direction on the model architecture, now sits under the board's To do.
- THE OMIM DISPATCH IS NO LONGER PARKED.
  - It was enabled and reverted on 2026-09-21 because `breadth_plan.filter_omim_titles` existed and nothing called it.
  - On 2026-09-22 the filter was wired into the act result path and the dispatch went live.
  - What stays true, and is why the line is kept rather than deleted: the dispatch and the filter ship together, and re-enabling one without the other cites a different gene than the question asked about.
- THE EXPLANATION HALF OF 11.31, in [`testing/UI_fixes_archive.md`](UI_fixes_archive.md).

### What is waiting on the product owner

- "Waiting for your retest" above, newest first, tonight's cards on top; each row names its queries in `testing/Test_queries_and_workflows.md`.
- Phase 8.7, pull request #218: merge with A04 and A07 filed as cards, or fix them first; with any merge, set `PER_QUERY_COST_CAP_USD=0.25` on develop's API (the lead's attempt was refused by the permission layer). Separately, whether develop's writer becomes Opus 5.5, knowing that at a true 25-cent bound its repairs are refused on 3 to 19 of 24 bench questions.
- The guardrail's re-split, proposed in its `DECISIONS.md` row.
- Card 40: 27 itemized hook and rule changes, each a yes or no, `testing/Developer/reports/2026-10-08_card40/itemized_list.md`; nothing in the security layer changed.
- Closing cards 11 and 12, proposed: neither reproduced since 2026-09-25, and both fixes were reverted.
- Design or decision questions from tonight's diagnoses: cards 16 (fold into 56), 17, 20, 29, 33 (D19), 48, and the `.claude/` and A07 parts of 51 and 85. New cards found tonight: `testing/Developer/reports/2026-10-08_overnight/new_cards.md`.
- The decisions taken on the owner's behalf overnight, each a `DECISIONS.md` row dated 2026-10-08.
- Decisions D5 to D21 in `testing/Board_plan.md`: each carries the lead's recommended default, taken unless the owner objects.
- After phase 8.7 merges, delete `feat/8.7-s1` to `s3` on GitHub (the lead's tag-and-delete was refused).
- The privacy pre-commit hooks on the second laptop, and `railway link` there so deploys can be confirmed.

Carried from 2026-09-29 and not re-checked today:

- Four checks of under a minute each, the only rows still not approved:
  - Copy an answer and paste it somewhere (11.14)
  - Open the answer-modes info button (11.36)
  - Change the mode while a search is running (9.12)
  - Open the app twice to see different scientists with the same answer (8.4)
- Still undecided from the older standing list: the three `theme.ts` logo tokens, the 720px nav, and the four golden test rows.

### Loose ends, named rather than left

- FROM THE NIGHT OF 2026-10-07 TO 08, found by the reviews and product checks and not filed as cards (each report under `testing/Developer/reports/2026-10-08_*`):
  - Card 54: an answer saved before 2026-10-08 still reopens with at most 50 sources and no word that some are missing; the warning line was reverted because it fired on bracketed numbers in record data such as "CAG[40]" (VF-54-01). The locked technical specification still says 50 in Section 13.2.
  - Cards 103 and 104: a merged BRCA1 row's text reads "BRCA1, identified by the gene symbol BRCA1 and gene name BRCA1." (product check PR-01); the Notes line counts 39 placeholder links against 33 cells and says "listed below" for records above; three edge cases on hand-built inputs (VF-103-01 to 03); a gene listed under two different names stays as two rows.
  - Card 67: no live check is possible without an NCBI outage; two test gaps (VF-67-01, 02).
  - Card 59: the user database sets no statement or connect timeout and its writes run on the event loop, so a hung write freezes a worker, as on develop (VF-59-01); three comments, one in `frontend/src/lib/api.ts`, still describe the old stop contract.
  - Answers: Plain language GERD and bronchiolitis answers often name no symptom, cause or risk factor; on a phone the searches panel stays open over a reopened answer; click to answer has a median of 23 seconds (`2026-10-08_product_check/product_review.md`).
  - Process: `/ship` Step 3 still says `-D` and `--force` where the git-workflow rule says `-d`, and `bossman-mode` still calls the golden run blocking; both are under `.claude/`, for the owner.
  - Nine old local worktrees on merged branches could not be checked for untracked work: iCloud evicted their files (`LEARNINGS.md`, 2026-10-08), and the permission layer refused comparing card 22's untracked reports with develop.
- FROM THE NIGHT OF 2026-10-06 TO 07, found by the product checks and fresh verifiers on develop, none filed as a card yet (`testing/Developer/reports/2026-10-06_card22/product_review.md`, `testing/Developer/reports/2026-10-07_card102/product_review.md`):
  - Card 23's line sits above five rows with an empty disease cell on HNF1A's first page. Closed 2026-10-08 by card 103 (#205): every cell now says why it is empty.
  - A reopened answer's tables run past a phone's screen edge. Closed 2026-10-08 by card 71 (#203): reopened tables stack on a phone.
  - The Sources group badges can add to one more than the Sources heading in the two-layer case; the group's line explains it.
  - A gene page can appear twice in the gene record tables while Sources lists it once. Closed 2026-10-08 by card 104 (#205), for rows that match in every cell.
  - Answers take 31 to 36 seconds on screen from click to trust line, against 15 to 25 on the app's own timer.
  - The golden run owed for cards 22 and 23 was not run: on 2026-10-08 the owner chose the test queries as the only check (DECISIONS.md).
  - Card 22's per-claim check still compares tools, not databases, and agreement does not check that two records are about the same variant; both are candidates for a card.
- L-01 is MEASURED, its two causes are READ, and the reader is now TOLD: a lost search is disclosed under the answer and a question the product could not read is answered with a request for a name (`10f6a46`).
  - What is NOT fixed is the cause itself: the deterministic half is a Think gap and the variance half is the act budget, both below.
- THE DETERMINISTIC HALF OF L-01 was a Think gap. For these questions Think
  resolved no entity and the plan still dispatched `cypher_query`, which
  refuses to run with nothing to bind:
  - a GRCh38 coordinate range (G-001)
  - a Pathogen Detection isolate (G-035)
  - a BioProject accession (G-007)
  - and on some passes Lynch syndrome (G-003)

  THE COORDINATE RANGE IS FIXED (`66b3811`, the same night); the isolate and the accession are card 94 and the accession answers in To do.

  G-005 and G-022 resolve an entity and find nothing; G-036 never calls Layer 1.
- THE VARIANCE HALF OF L-01 was NOT the act budget and NOT a follow-up: the graph server's own log shows the question's OWN search, taking the model path on an exploratory no-shape question, killed by the graph's 30-second statement timeout after 85 seconds because the planner mis-estimates an id match by four orders of magnitude.
  - Fixed for the exploratory class (`2bc8ec0`).
  - G-037 and G-033 were a different fault: generation or validation failing before the transport ("Generated Cypher references vertex label", "appears to bind a literal value"). FIXED the same evening as fix-plan item 1:
    - No template matched, so both took the model path
    - Both take a template now (`27d68ae`)
    - And G-037 also searches GEO (`b6cd025`)
    - See the 2026-09-22 session table in [`testing/UI_fixes_archive.md`](UI_fixes_archive.md#session-history-2026-09-21-to-2026-09-27)
- THE TRUST TIER `ask` AND THE PARKED GRADER'S `ask` ARE TWO MEANINGS OF ONE WORD.
  - Widening the golden rows to accept the trust tiers was built, found to erase the parked grader's answer-versus-clarification distinction (two of its tests go red for a real reason), and discarded.
  - The 77 percent answer-or-refuse figure is the one to read; the 14 percent is vocabulary.
  - Recorded in `DECISIONS.md` for whoever un-parks the grader.
- DEVELOP TRACES NOTHING TO LANGSMITH, BY DESIGN: tracing runs on production only, product-owner confirmation of 2026-09-22.
  - So a cause behind a develop measurement is read by local reproduction, as L-01's was, never from a trace.
  - Any future "read the trace" step written against develop is wrong on its face.
- `testing/Shipped_2026-09-20.md` was found deleted from the working tree
  mid-session by something outside this session's tool calls, and restored
  from HEAD unchanged. Cause unknown.
- The 2026-09-20 L-01 instrument filtered on `layer_1` while the API emits
  `layer_1_graph`, so its own anomaly field read zero on every run. Any
  instrument that reports "no anomalies" deserves a populate-check.
- A multi-sentence record can now render as several list rows under one record
  heading, a consequence of 11.34's fix. Not a grounding or citation defect,
  and no test covers it.

- ADDED 2026-09-24, from the session's live runs:
  - The rule for a reworded sentence that switches papers is satisfied by any
    shared title word, and a generic one ("patients") is a weak anchor.
    Recorded in 12.16's row; not fixed.
  - The ask-back classifier is a judgement: `MeSH` was asked back 2 times in 3
    after tuning.
  - Some dense paragraphs in older sections, carried over by the plan's split,
    were left as written: cosmetic, and three cannot pass the no-loss check.
  - The leftover agent worktree was removed at the evening close, its branch
    already merged into develop.
- ADDED 2026-09-24 evening, from the harness session:
  - Seven test files the deletion inventory set aside await the product
    owner's ruling: `docs/build/Bossman_redesign_deletion_inventory.md`.
  - A test inside the unit gate makes a live NCBI call, so an NCBI outage can turn CI red with nothing wrong in the code.
    - It belongs behind the integration marker.
    - Not started.
  - `/phase-checkpoint` still says the tracked counts sit on CLAUDE.md line
    32; since the trim they sit on line 31. The drift check finds them by
    content, so nothing fails, but the sentence is stale and changing it
    needs a pull request, since it is under `.claude/`.
- A lock file for the Python build.
  - `requirements.txt` gives ranges rather than versions, so every Railway build resolves afresh
  - D5 showed a release can reach develop thirteen minutes after it is published.
  - Not started, and it is the product owner's call.

- ADDED 2026-10-05:
  - Card 57 shows "Building, wave 0" on the board while the day's facts record #161 as touching it; the board's word stands until the owner retests it.
  - The untracked board-plan report folder holds copies whose names end in " 2" (`brief 2.md` and the like), the same copying seen on 2026-09-25. They are not committed.
  - Factory, a second development agent, was given the screen and wording lane (cards 43, 44, 18, 23, 24, 25, 47 and the rest of 61) and paused the same night after a trial.
    - The split is provisional and those cards are pending until the owner's renewed instructions.
    - The lead keeps the answer path, the board, the plan and the one merge queue.

### Notes carried over from the old tracker

Carried over from the plan's own "Additional notes" when it became a
board on 2026-09-24.

- THE GRAPH HOLDS NO DISEASE NAMES AND NO MESH TERMS, measured graph-wide on 2026-09-23.
  - Every `Disease` vertex carries its source vocabulary in `name` and zero contain the word "syndrome".
  - Known since build phase 2.1 as F-2.1-B07.
  - Writing the graph is Systems 1 and 2 work in the other repository, so this is a hand-over rather than a task, and it BOUNDS what any answer-path work here can achieve.
- ITEM 11.21's PROMISE IS NOT BEING KEPT, measured for the first time on 2026-09-23 and on wiring nobody changed.
  - Six identical PubMed searches returned two distinct result sets, and the GERD questions moved 20 citations to 19 with one paper swapped.
  - Separately, which path a question takes is a model call, so it is a sample: `reflux disease` resolved nothing on one run in six.
  - Nobody had looked.
  - Not yet its own item. Since the audit of 2026-09-24 it is card 19 on the board.
- OMIM is live WITH `filter_omim_titles`; the two ship together and neither is
  enabled or removed without the other
- The cutoff and the ordered next actions are in "Where we stopped"

### Next, in order

- Rewritten 2026-10-08, after the overnight run, in the order of the board's To do column, top to bottom, one line per card.
- The board is the order; this list gives each card's reason or a pointer to its detail.
- `testing/Board_plan.md` holds the dependencies and the waves, and the order work is built in.

1. Card 56: Smallest fix live (#186): the plain SARS-CoV-2 question no longer binds the disease SARS. Still open, for a design with the owner first: "SARS CoV-2" with a space, a remembered gene after a missed question, and the leukaemia and "Illumina" cases on the board.
2. Card 101: Part live (#193, #204). Its last three slices were built overnight on 2026-10-08 and parked after both reviews found a new sentence splitter worse than develop: it needs a design for where a record sentence ends (`testing/Developer/reports/2026-10-08_card101/`).
3. Card 94: Part live. Still open: the place column (the accession already shows as Identifier), a single-isolate lookup and a follow-up such as "from 2023"; diagnosed 2026-10-08, built after phase 8.7 merges since it touches the same answer layout.
4. Card 84: Built overnight with card 72 and parked: its fix round admitted a follow-up after a long server pause that develop refuses and over-charged Jev replies. Re-split proposed in its `DECISIONS.md` row of 2026-10-08.
5. Card 72: Logging live (#159); its fix is the guardrail re-split with card 84; step 2, host routing, waits for a week of logs that name a cut call's host.
6. Card 75: Factory's next card (`docs/build/Factory_onboarding.md`): the command line's MCP bridge latches after a refused or unreadable sign-in renewal, so it never resends a spent token.
7. Card 85: Part live (#167, #220): the page sentences and the logging slice. Still open, each the owner's: the facts checker's gaps, under `.claude/`, and the five `exc_info` warnings (A07).
8. Card 2: Phase 8.7, pull request #218, waiting for the owner's call; the first sentence answers when a checked sentence does.
9. Card 4: Tell the reader when the search was drafted rather than checked; keyed on the query being drafted, never on empty or failed. Nobody on it.
10. Card 5: The per-model effort setting and the Opus writer are built in phase 8.7 (#218); develop's writer stays as it is until the owner chooses, since at a true 25-cent bound Opus's repairs are refused on 3 to 19 of 24 bench questions.
11. Card 6: The agentic loop, the owner's second quote under their model architecture direction. Nobody on it.
12. Card 7: Hard and soft edges over a fuller graph; read `testing/Developer/reports/2026-09-23_overnight/soft_edges_scoping.md` first (11.29). Nobody on it.
13. Card 8: Trust-line wording (9.9): the owner chose "say what was checked"; planned in phase 8.9 from the parked 8.4 commit.
14. Card 9: Judge answer quality once answering is reliable (10.4). Nobody on it.
15. Card 11: Proposed for closing: not reproduced since 2026-09-25 and its fix reverted (`tracker/phase_8.1.md` F-8.1-03).
16. Card 12: Proposed for closing: not reproduced since 2026-09-25 and its fix reverted (F-8.1-A13).
17. Card 14: One 127-second search against a median of 14 (F-8.1-05). No run passed 60 s in phase 8.7's 32 live runs on 2026-10-08 (slowest 58.6 s); per the 2026-10-05 decision it closes when phase 8.7 merges.
18. Card 15: Step 1 live (#171). The next step was built overnight on 2026-10-08 and parked: one record for every non-count question gave wrong or thinner answers. Needs one checked template per question shape (`testing/Developer/reports/2026-10-08_card15/`).
19. Card 16: G-022 is fixed; G-005 fails on the "Illumina" refusal card 56 holds for a design; proposed to fold into card 56 (diagnosis `testing/Developer/reports/2026-10-08_overnight/card16_diagnosis.md`).
20. Card 17: A reworded sentence can switch papers on a generic title word; five design options with their costs in `testing/Developer/reports/2026-10-08_overnight/card17_diagnosis.md`, for the owner.
21. Card 18: Mostly fixed; two rows remain when a record's sentences pass 1000 characters. Small, built after phase 8.7 merges (diagnosis in the overnight folder).
22. Card 19: No false writing step found; one real gap (a call skipped at the 20-call limit keeps the steps on Act through the writing wait). Small, built after phase 8.7 merges.
23. Card 20: An isolate search filters only by gene prefix; the parked filters merge cleanly, but where the year and place come from is a design choice for the owner (diagnosis in the overnight folder).
24. Card 24: Factory's card after 75: the Plain language and Researcher switch beside the answer's header, with the confirmation the owner approved on 2026-10-06.
25. Card 25: Install the public USWDS package: decided 2026-09-25, not built; a new package needs the owner's approval and a supply-chain review first.
26. Card 29: The answering sentence under each cited paper; parked on `parked/phase-8.8-snippets-2026-09-25`. Lifts mostly cleanly; how many papers get a sentence is a cost and speed choice for the owner.
27. Card 30: The BRCA1 pathogenic-variants question lists unclassified variants and drops the caveat; the honest note is small and built after phase 8.7 merges; fetching classifications is a cost choice for the owner.
28. Card 33: G-006 is fixed (#172); G-004 waits on decision D19, since nothing is findable until the isolate is named.
29. Card 35: An off-topic follow-up containing a word such as "cell" still gets through; small, built after the guardrail re-split since both change `guardrail_node`.
30. Card 36: Live (#215): the plan line now says when a picked or typed date range could not be applied. Still open, the owner's design choice: making a picked window survive a restart.
31. Card 37: Part live (#213): rs334 lists only rs334. Still open: the rs334 row named by its clinical significance labels and naming no condition; planned in phase 8.9.
32. Card 38: Orthologs' species and papers' titles still missing (the isolate genes are fixed); phase 8.9 tickets, built after phase 8.7 merges.
33. Card 40: The itemized list is written, 27 items each a yes or no (`testing/Developer/reports/2026-10-08_card40/itemized_list.md`); nothing in the security layer changes before the owner answers.
34. Card 42: The build team checks the product the way a person uses it; proposal `docs/build/Verify_loop_proposal.md` waits for the owner's yes.
35. Card 48: A fuzzy question should ask which aspect is meant first; whether "How do birds fly?" asks back, and the extra writer call's cost, are the owner's (diagnosis in the overnight folder).
36. Card 50: Phase 8.7 (#218): records at a median 9.3 s against 27.3 s for the whole answer on its live check; waiting for the owner's call.
37. Card 51: Part live (#156, #219): the About page no longer describes the retired track. Still open, the owner's: a registry of every page claim.
38. Card 52: Every answer ends by offering the next useful step; designed in `testing/Developer/reports/2026-09-26_conversation_next_steps/design.md`, a numbered phase after 8.7 and 8.9.
39. Card 55: The test queries document is the gate; the golden run is an alarm only (decision D4).
40. Card 100: Factory's card after 24, low priority: a very long signed-in email pushes the top bar off screen between 721 and 900 pixels.
41. Card 105: A picked date range limits only the live PubMed search, while the graph's own article records ignore it; found by card 36's product check. Nobody on it.
42. Card 106: The "High-risk claim" tag breaks across two lines on a phone; found by card 71's product check. Nobody on it.
43. Card 107: A rejected reworded clause can leave the start of its sentence on screen; card 101's territory, found by card 51's verifier. Nobody on it.

Not on this list, deliberately: the explanation half of item 11.31.

- The owner approved the current state as is on 2026-09-21.
- The remaining lever is recorded in "The result that should shape what happens next" in [`testing/UI_fixes_archive.md`](UI_fixes_archive.md#the-result-that-should-shape-what-happens-next) as a standing option, not as queued work.

### How to start the next session

1. Read `HANDOFF.md`, "The one next action" (the lead rewrites it at each checkpoint, so read the current one), then "Where we stopped" above, then the session tables under "Session history" below, newest first.
2. Run `git status` and `git worktree list`. Local carries `develop` plus the old worktrees `HANDOFF.md` names; GitHub carries `develop`, `production`, phase 8.7's branch with its open pull request #218 and its three builder branches, listed by `git branch -r`.
3. Read "What is parked, and why" before picking anything up. OMIM is live WITH its title filter; the two ship together and neither is re-enabled or removed without the other.
4. Retests: "Waiting for your retest" at the top of this file.
   - Its newest cards are tonight's 71, 37 part, 36, 51 part, 32 and 85 part, then 59, 67, 103 and 104, 101 part, 54 and 71 part, and the older rows below them.
   - Each names its queries in `testing/Test_queries_and_workflows.md`.
5. Then decide pull request #218, and build the cards that wait on it from their diagnoses in `testing/Developer/reports/2026-10-08_overnight/`, as `HANDOFF.md` says.
   - Test queries sign in with throwaway accounts made on develop only with the owner's yes, their details kept in the scratchpad and never committed; the golden run is an alarm, run only when the owner asks (2026-10-08).
   - The call ceiling is measured and stays at twenty.

## Detail for items on the board

Items raised in Sets 10 to 12 that are still open, each a card in the To do column of `testing/UI_fix_plan.md`. The rest of those sets is closed, recorded in the set sections of [`testing/UI_fixes_archive.md`](UI_fixes_archive.md).

### 105 A picked date range limits only the live PubMed search

- Found 2026-10-08 overnight by the product check of card 36, PR-36-01, `testing/Developer/reports/2026-10-09_product_check_37_36/product_review.md`.
- Asked "recent papers on BRCA1" and picking "from the last 5 years" at once, the plan line names the window, but the answer's first 41 papers are knowledge graph records with ids from about 1999 and 2000, shown as bare ids; only the four live PubMed papers fall inside the window, and the heading repeats "from the last 5 years".
- True on develop before card 36, which only adds the note when a window could not be applied. Cause not yet diagnosed: the window is passed to the live PubMed search only.

### 106 The High-risk claim tag breaks across two lines on a phone

- Found 2026-10-08 overnight by the product check of card 71, `testing/Developer/reports/2026-10-09_product_check_71/product_review.md`.
- At 390 pixels the tag under a reopened BRCA1 answer reads "High-" on one line and "risk claim" on the next. Overflow stays 0. Whether the live answer's tag wraps the same way was not captured.

### 107 A rejected reworded clause can leave the start of its sentence on screen

- Found 2026-10-08 overnight by card 51's fresh verifier, V-51-01, in its report on card 51's merged branch, `testing/Developer/reports/2026-10-09_card51/verifier.md`.
- A probe showed that when the model check rejects a clause the writer reworded, the beginning of that sentence still shows, so a person reads half a sentence the check did not pass. Card 101's territory.

### 10.4 Judge answer quality once answering is reliable (R39)

Built: · Live: · Approved:

- Feature being tested: answer quality is judged only once the product answers consistently.
- What you noted: "Only once questions answer reliably, judge answer quality: the grader, or a domain expert reading the answers."
- What's expected: a quality pass with the grader or a domain expert, once R38's consistency run shows reliable answering. This is a developer check, not a hand test.

### 99 The sentence check approves rewordings that drop a qualifier

- What a person sees: an answer can show a broader claim than its source. "Young children" is shown as "children", or a dropped "potentially" makes a hedged finding read as certain. Develop has done this since the check began.
- Found by: the card 89 measurement, 2026-10-05, `testing/Developer/reports/2026-10-05_wave3/sentence_check.md`.
- Design: `testing/Developer/reports/2026-10-05_qualifier_check/design.md`.
- Decision, the owner, 2026-10-05: measure the pair check on all 144 faithful rewordings first, then decide whether to ship.
- Where it stands: nobody on it until that measurement runs; the card is second in the board's To do.

### Set 11, still open

Moved word for word to the To do section of `testing/UI_fix_plan.md` on 2026-09-24. That covers Set 11's open rows with the detail behind them, and the product owner's direction on the model architecture of 2026-09-23.

### Set 12, still open

| # | The feedback | Status | Where it stands |
|---|---|---|---|
| 12.14 | `What phenotypic features are associated with Marfan syndrome?` names no phenotypic feature at either depth | RAISED 2026-09-23 in `testing/User-feedback/fix-2/`. NOT STARTED | Plain language answered "Found 1 disease record, 37 sequence variant records and 3 gene records for Marfan syndrome" and researcher "Found 1 disease record for Marfan syndrome: Marfan syndrome." The question asks for features and the answer substitutes an adjacent record type. This is the honest gap the 2026-09-23 shipped list's retest item 5 named, now query 66: removing the dead template stopped a search that could never work, and nothing that CAN answer it runs instead. Evidence: `testing/Developer/reports/2026-09-23_fix2/findings.md` |
| 12.16 | No hardcoded decisions: "Please do not hardcode! Hopefully not that dumb" | RAISED 2026-09-24 by the product owner. Parts 1, 2 and 4 LIVE on develop 2026-09-24; part 3 NOT STARTED | AUDITED THE SAME NIGHT. No product code special-cases a test question by its text: every mention of the feedback questions in `src/` is a comment recording a measurement. WHAT IS HARDCODED, and what happens to each: (1) three model prompts use examples LIFTED FROM THE TEST QUESTIONS, the answer writer's "Caffeine improves endurance performance", the guardrail's "does coffee help exercise performance", and the sentence checker's "kidney" for "renal" and "mouth" for "oral cavity" from the GERD answer; that is teaching to the test, and they are replaced with neutral examples outside the test set, IN PROGRESS; (2) 12.3's clarify-or-proceed decided by word lists, REDESIGNED as a classifier decision, IN PROGRESS; (3) item 12.7's literature-request routing, decided by a word list (paper, publication, article and kin), to become a classifier decision, NOT STARTED; (4) the grounding gate's phrase lists added on 2026-09-23 for broken sentences and references ("however", "Another", "This ...", a "Yes," opener), which sit beside the exact checks the product owner asked to stay deterministic (quote in the record, numbers, negation), DECIDED 2026-09-24 BY THE PRODUCT OWNER: "Structure, not words", chosen over keeping them as exact backstops and over handing them to the model check. THE REPLACEMENTS, IN PROGRESS: a sentence copied from the middle of a record's sentence and starting in lowercase is that sentence's back half and is dropped, decided from where the words sit in the record, not from a list of connectives; any other lowercase start is capitalised; a reworded sentence that switches to a record the sentence before it did not cite must name something from its own record's title, decided from the records' own titles, not from a list of pointing words; the "Another ..." list is removed, since the restatement rule already drops a sentence that only repeats a row the list shows; the "Yes," or "No," opener stays, stated as the one exception because yes and no are the whole class of English answer words rather than a sample of phrasings. Measured before shipping. The distinction that governs all four: code VERIFIES exactly; a DECISION goes to a classifier. WHAT SHIPPED 2026-09-24: part 1, the three prompt examples replaced with neutral ones, and the guardrail re-measured live, 68 checks and 0 wrong, the coffee question admitted 10 of 10 without its own example; part 2, 12.3 as a classifier decision; part 4, the phrase lists replaced by `_starts_inside_record_sentence` and `_names_its_record`, replayed over three live replies with nothing a reader needed dropped. A RESIDUAL OF PART 4, found in the live run and stated rather than hidden: the switch rule is satisfied by any shared title word, and a generic one is a weak anchor. After a Tay-Sachs sentence, "No patient carried more than one of these mutations" cited a BRCA paper whose title says "patients", so "these mutations" reads as Tay-Sachs while the paper means BRCA founder mutations. The phrase list it replaced would have missed it too, since "these" is not the first word. Not fixed |
| 12.17 | A good question sometimes fails at the think step and shows a refusal | RAISED 2026-09-24 from the live runs. NOT STARTED, nobody on it | Seen twice in about forty live runs over 2026-09-23 and 2026-09-24: `Does coffee help make exercise more effective?` and `is there a trial recruiting for melanoma`, both at researcher depth, each failing with "the plan tier's response did not match the think classification schema". Neither question reaches 12.3's ask-back, which only reads one to three words, so tonight's work did not cause it. The reader sees a refusal for a question the product answers on every other run. Evidence: `testing/Developer/reports/2026-09-24_no_hardcoding/live_runs/` |

## Session history

### The night of 2026-10-08 to 09, in one table

- The lead ran the owner's six-item list overnight under their approval; every pull request went through CI, a judge, an adversary, one fix round and a fresh verifier, and merged only when that verifier found nothing worse than develop
- Six cards merged and were checked on develop at 1280 and 390; phase 8.7 waits for the owner; three pieces of work were parked after their reviews; two fix-round changes were reverted before merge
- OpenRouter: $4.33 spent of $36.11, $31.77 left

| Item | What happened | Where it stands |
|---|---|---|
| Card 71 (#212) | The "High-risk claim" tag stored with the answer, migration 0011 approved by the owner; the fix round made the saved trust words mirror the live ones, a capped answer no longer reopening with a tick | Live; in Retest; query 67 passed on develop at 1280 and 390, the tag wrapping at 390 filed as a new card |
| Card 37 (#213) | Only rs334's own records listed; the citation label taken from the cited record; the fix round's case-insensitive rs ids reverted after the verifier found "RS1 gene" read as the variant rs1 | Live, part; in Retest; query 23 passed |
| Card 32 (#214) | A graph column named like MedGen's clinical features is renamed where it is born, collision-proof | Live; in Retest; no live trigger, query 87 as the regression |
| Card 36 (#215) | The plan line says when a picked or typed date range could not be applied, only when a paper search ran | Live; in Retest; query 108 passed; its product check found the window limits only the live PubMed search, filed as a new card |
| Card 51 (#219) | The About page's retired track sentence removed; the fix round's stop 5 rewording reverted to the true sentence | Live, part; in Retest; the About page checked at 1280 and 390 |
| Card 85 (#220) | A crash or failed step logs which search and why, never the error's text | Live, part; in Retest; nothing a person sees |
| Phase 8.7 (#218) | Built in full from its four parked branches, reviewed, fixed once, checked live on its branch for $3.67 | Waiting for the owner: its verifier found A04 and A07 worse than develop |
| Guardrail, cards 84 and 72 | Steps 1 and 3 built, reviewed and fixed once; step 2 parked for want of a week of logs | Parked: the fix round admitted a follow-up after a long pause and over-charged Jev replies |
| Card 15 | The next step built and reviewed | Parked: one record for every non-count question gave worse answers |
| Card 101 | The last three slices built and reviewed | Parked: the new sentence splitter let a quote through without its negation |
| Card 40 | The itemized list of 27 hook and rule changes written | Waiting for the owner's yes or no per item |
| The To do cards nobody was on | Each diagnosed in `testing/Developer/reports/2026-10-08_overnight/` | Built after phase 8.7 or the guardrail re-split, or waiting on the owner's design |

### The night of 2026-10-07 to 08, in one table

- The lead ran the board overnight under the owner's approval; every merge waited for CI and a fresh verifier, and the owner answered each new decision in the chat
- Seven cards merged; card 54's warning line was reverted before merge, and every card got a product check on develop where one was possible
- Branches and tags were cleaned on both repositories, and the data engineering repository was released

| Item | What happened | Where it stands |
|---|---|---|
| Card 101 (#204) | Last round on the owner's yes: a held copied piece drops the whole sentence; a fresh judge and adversary both found nothing worse than develop | Live, part; in Retest; query 106 passed on develop |
| Card 54 (#202) | A saved answer keeps up to 100 citations, code only; the fix round's warning line for older answers was reverted after its verifier found false alarms | Live; in Retest; query 107 passed on develop |
| Card 71 (#203) | Reopened tables page ten rows and stack on a phone; the first column leads each row, merged on the owner's choice | Live, part; in Retest; query 67 passed on develop; the tag waits for a migration |
| Cards 103 and 104 (#205) | Empty disease cells say why; a record is listed once; merged with three named edge cases on the owner's choice | Live; in Retest; queries 79 and 107 passed on develop |
| Card 67 (#207) | A reopened outage note is in the past tense with no date; round 1's dated version failed both reviews and was redone | Live; in Retest; no live check possible |
| Card 59 (#208) | An answer that finished before Stop stays on screen, in history and in memory; a stop failure never touches the next question | Live; in Retest; query 56 passed on develop at both widths |
| Overnight skill (#206) | `.claude/skills/overnight-development/SKILL.md`, ending with the branch and tag end-state check | Merged on the owner's word |
| Guardrail design | Written from the two parked branches, their reviews kept, both branches deleted | Waiting for the owner's seven answers |
| Golden run | Started, then stopped when card 101 deployed mid-run; the owner then chose the test queries only | Not run; partial results set aside |
| Branches and tags | Merged worktrees and branches removed; four finished tags deleted; the data engineering repository's two merged branches deleted | GitHub: develop, production and phase 8.7's four branches |
| Data engineering release | v1.1.0 released by its workflow; the changelog carried to production (#19, #20, #21) | Done |

### 2026-10-06 and the night to 2026-10-07, in one table

- Factory returned with a written brief and built five cards, each verified by the lead before merge
- The Retest list moved here, and a sync check now proves the key documents agree
- Overnight the lead merged cards 22, 23 and 102 and the readability pass under the owner's delegation, and parked card 101.

| Item | What happened | Where it stands |
|---|---|---|
| Factory's brief (#179) | `docs/build/Factory_onboarding.md`, one self-contained brief; Factory's own trailer allowed (#182) | Done; its next cards are 75, 24 and 100 |
| npm advisories (#180) | compression, source-map-js and vitest patched | Done |
| Cards 43 and 43b (#181, #187, Factory) | Long variant names wrap on a phone and keep their citation number | Retest, query 105 |
| Card 44 (#183, Factory) | The tour button stays readable on hover | Retest, query 63 |
| Card 47 (#188, Factory) | The design prototype's home page is light | Retest |
| Card 99 (#184, #189) | The pair check holds back a sentence that drops a limit its record sets; measured live | Retest |
| Card 56 (#186) | The smallest fix: the SARS-CoV-2 question no longer binds the disease SARS | Live, part; card stays in To do |
| Card 61 (#190, Factory) | Ten command line and MCP bridge edge cases; one gap moved to card 75 | Retest |
| Card 101 (#192, #193, then rounds 3 and 4) | Every reworded sentence goes to the sentence check; the copied-cut fix failed its last adversary on a fail-mode limit cut | Part in Retest; copied cuts parked on `fix/card101-copied-cuts` |
| Retest list and sync check (#194, #195) | Retest moved to this file; `tracker/check_doc_sync.py` runs at every checkpoint and push | Done |
| Readability (#196) | This file, the board, `PROGRESS.md` and the board plan restructured with no fact lost; closed history to `testing/UI_fixes_archive.md` | Done; remaining walls listed in `testing/Developer/reports/2026-10-06_readability/report.md` |
| Card 22 (#197) | One sources count everywhere; a page from two layers is one card naming both; the confirmed count counts only cited databases | Retest, query 107 |
| Card 23 (#198) | The note under the variant-to-disease table tells the truth and sits under its table | Retest, query 79 |
| Card 102 (#199) | Found by card 22's product review: a reopened saved answer listed no sources; fixed, with long links wrapping on a phone | Retest, query 107 |
| An older lead still running after the IDE closed | Two writers on the readability pass; the old process was stopped | `LEARNINGS.md`, 2026-10-06 |

### 2026-10-05, in one table

- Twenty-one pull requests merged (#155 to #175)
- Thirteen cards moved to Retest
- The board went from 78 to 52 cards
- The test queries ran three times on develop.

The day's facts: `testing/Developer/reports/2026-10-05_board_plan/day_facts.md`.

| Item | What happened | Where it stands |
|---|---|---|
| The whole-board plan and the board clean-up (#155) | Nine diagnoses, the plan with decisions D1 to D4 and the filing rule; four dead cards removed (53, 62, 90, 93), ten moved to `testing/Future.md` rows 48 to 57 | Done; D5 to D21 wait on the owner's objection |
| Card 51, part (#156) | The facts checker passes again after the 2026-10-04 rewording | Retest, part |
| Card 86 (#157) | Every library's license text ships with the web app | Retest, query 99 |
| Cards 92 and 94, part (#158) | Chromosome windows list their dbVar records; the colistin search finds mcr carriers instead of a false zero | Retest |
| Card 72, part (#159) | One log line per guard-model and Jev call | Part live; the guardrail design waits on logs |
| Card 91 (#160) | The TP53 dataset question uses the checked graph search | Retest, query 25 |
| Cards 88 and 57 (#161, #163) | GERD keeps its reworded answer sentences, a record cited twice shows each sentence's own quote, and a repair draft with more grounded sentences wins | Card 88 in Retest, queries 75 and 68; card 57 still Building on the board |
| Card 87 (#162) | "recent-onset diabetes treatment" is answered; a bare subject is still asked back | Retest, queries 84 and 76 |
| Card 95 (#164) | No raw bracketed markers in a long first sentence | Retest, queries 27 and 29 |
| Card 94, part (#165, #174) | Plain language shows the isolates and genes table; the table also shows an organism record beside the isolates | Retest, queries 33 to 37 |
| Cards 97 and 98 (#166) | One row per record, no duplicated OMIM row; an empty guard reply asks to try again | Card 97 in Retest, query 24; card 98 live with no query |
| Cards 79, 80 and 85, part (#167) | The Integrations card shows its commands, About shows its layer cards first, two page sentences corrected | Retest, queries 102, 59 and 60 |
| Card 46 and decision D1 (#168) | When no written summary survives, one plain line says why; a capped question lists what it gathered | Retest, no query yet |
| Cards 91, 77 and 94, part (#169) | The answer names which search failed and why, which gene families an isolate search used, and when trials were not searched | Retest |
| Card 96 (#170) | "Muir-Torré syndrome" spelled right; NCBI's record carries broken encoding, repaired on arrival | Retest, query 24 |
| Card 15, step 1 (#171) | A question about one paper uses a checked graph search | Part live; the remaining anchors per D5 |
| Card 74 (#172) | A paper's linked data from NCBI's live links | Retest, query 104 |
| Card 56 (#173) | Organisms resolve through NCBI Taxonomy, with SRA and assembly routes | Failed live; back at the top of To do |
| Card 89 (#175) | The sentence check reads the whole record sentence a quote sits in; the writer quotes whole sentences | Retest, query 73 |
| Card 13 | Proposed for closing, superseded by 11.20 | Retest, query 78 |
| Card 99, new | The sentence check approves rewordings that drop a qualifier | To do; measure first |
| The test queries on develop | Morning: 84, 76, 99, 1, 75, 68, 27, 29, 25 and 24 passed, 33, 34 and 37 failed; afternoon: 27, GERD, Integrations and About at 1280 and 390 passed, 33 and 37 failed, fixed by #174; final: 9 of 10 passed, the SARS-CoV-2 question failed | Reports under `testing/Developer/reports/2026-10-05_*_test_queries/` |
| Phase 8.7 | Resume plan written and its decisions taken | Parked, waiting on an OpenRouter top-up |
| Process | Factory takes the screen and wording lane, then the trial is paused the same night and its cards are pending; lessons logged in `LEARNINGS.md` (the shared git stash, CI starvation, untracked evidence and the leak guard, Jev's literal criteria, fixtures from real answers, paths with a space, parallel builders on one file) | Standing |

### 2026-09-30, overnight, in one table

No product change. `/ship` gained a leak scan, and the branches were cleaned while the owner slept.

| Item | What happened | Where it stands |
|---|---|---|
| The `/ship` leak scan, both repositories | Builder, judge, adversary, one fix round, fresh verifier; merged with the verifier's items named, git-sync's added step reverted (#145, data engineering #11) | Done |
| Email findings as warnings | Asked by the owner; refused by the permission layer as a security weakening | Waiting on the owner's approval |
| `brace-expansion` audit | A new high advisory turned gate 7 red; lockfile moved to 1.1.21 first (#146) | Done |
| Branches | Develop only locally in both repositories; on GitHub develop, production and System 3's six parked branches | Done |

### 2026-09-29, second session, in one table

Back on the first laptop. Card 63's two checks ran, and cards 62 and 53 were resumed from their parked branches and taken through their review rounds.

| Item | What happened | Where it stands |
|---|---|---|
| Card 63, every "not yet confirmed" answer saved and an NCBI outage said plainly | Test queries 100 and 67 passed on develop; the golden run answered 98 of 150 against a floor of 101, the lost runs guard-model timeouts, one unlogged crash and G-006's graph timeouts; the owner kept it and accepted the run | Retest |
| Card 62, install and connect on the first try | Builder's report, judge, adversary, one fix round, fresh verifier; the round's MCP fix broke silent renewal against production and the owner had it reverted | Live on develop (#133), Retest |
| Card 53, the pages and documents state what the code does | The same rounds; every rewritten page sentence true on every path the verifier ran; checker gaps and two sentences named open | Live on develop (#134), Retest |
| Two rules naming LitSense | The owner approved correcting the two API lists, one line each | Merged (#135) |
| Cards 71 to 78 | Filed: a reopened answer that differs from the one read (71), guard timeouts (72), a crash with no logged reason (73), G-006 (74), card 62's dropped MCP fix (75), two page sentences (76), the silent layer 3 skip (77), the facts checker's gaps (78) | To do |
| The AirDrop steps in `HANDOFF.md` | Removed at the owner's word | Done |
| Cards 62 and 53, and the two rule lists | Merged by the lead with `--admin` on the owner's grant (#133, #134, #135); card 53's branch first updated so the facts checker follows card 62's page; README's KGX line fixed after the product review (#138) | Retest |
| Card 73, a crashed search logs its reason | Builder, judge, adversary, one fix round, fresh verifier; merged with V01 named at the owner's choice (#139) | Retest |
| R-10 and card 72, the guard fix | Diagnosis, builder, judge, adversary (stalled after five findings), one fix round, fresh verifier: DO NOT MERGE on F-72-V08; parked on its branch at the owner's choice | Re-split as cards 84 and 72 |
| Cards 79 to 84 | Filed from the product review, card 73's reviews and the parked guard fix | To do |
| Card 84, R-10's guardrail fixes alone | Built; its adversary found an off-topic question and a disguised injection admitted under a rate limit; stopped and parked at the owner's choice | Parked |
| The Retest column | Three runners ran every Retest card's test queries on develop: 39 passed and were approved by the owner, 9 failed and went back to To do as cards 86 to 94, 3 wait on the owner's eye | Done |

### 2026-09-29, in one table

The first session on a second laptop, an Intel Mac, set up from nothing. Card 63 was the one piece of parked work resumed.

| Item | What happened | Where it stands |
|---|---|---|
| Card 63, every "not yet confirmed" answer saved and an NCBI outage said plainly | Both rounds rerun, since no adversary row survived the restart; judge PASS, adversary FAIL on an outage note contradicting the papers above it; one fix round, a fresh verifier's MERGE, the full suite green; merged by the owner (#128) | Retest, queries 100 and 67; its golden run still to come |
| The frontend dependency audit | A high advisory against the dev-only `fast-uri` turned gate 7 red; lockfile moved to `fast-uri` 3.1.8 and `undici` 7.30.0 after the supply-chain checks; merged by the owner (#129) before card 63 | Done |
| Cards 67 to 70 | Filed: three open items from card 63's review and two moderate `vitest` advisories | To do |
| Local links under `reference/` | `.gitignore` ignores anything added there except the two committed links, so a private repository's link never needs naming; merged by the owner (#131) | Done |
| The second laptop | Python 3.11, PostgreSQL, Redis and Node from Miniforge, since Homebrew no longer installs on Intel Macs; the develop suite passed on it | Done, less the privacy hooks and the Railway link |

Session tables dated 2026-09-27 and earlier moved to [`testing/UI_fixes_archive.md`](UI_fixes_archive.md#session-history-2026-09-21-to-2026-09-27).

## Moved to the archive

Each section listed here moved to [`testing/UI_fixes_archive.md`](UI_fixes_archive.md) on 2026-10-06.

- [What is done, in summary](UI_fixes_archive.md#what-is-done-in-summary)
- [Progress at a glance](UI_fixes_archive.md#progress-at-a-glance)
- [How to read the set tables](UI_fixes_archive.md#how-to-read-the-set-tables)
- [How the board came to be](UI_fixes_archive.md#how-the-board-came-to-be)
- [The result that should shape what happens next](UI_fixes_archive.md#the-result-that-should-shape-what-happens-next)
- [Set 1: let people in](UI_fixes_archive.md#set-1-let-people-in)
- [Set 2: a steady frame](UI_fixes_archive.md#set-2-a-steady-frame)
- [Set 3: refusals and Stop](UI_fixes_archive.md#set-3-refusals-and-stop)
- [Set 4: stay signed in, history on phones](UI_fixes_archive.md#set-4-stay-signed-in-history-on-phones)
- [Set 5: Integrations and the disclaimer](UI_fixes_archive.md#set-5-integrations-and-the-disclaimer)
- [Set 6: let automated checks see a real answer](UI_fixes_archive.md#set-6-let-automated-checks-see-a-real-answer)
- [Set 7: a conversation that remembers](UI_fixes_archive.md#set-7-a-conversation-that-remembers)
- [Set 8: search every layer, with the scientists](UI_fixes_archive.md#set-8-search-every-layer-with-the-scientists)
- [Set 9: answers worth reading](UI_fixes_archive.md#set-9-answers-worth-reading)
- [Set 10: reliable flagship answers, and saved history](UI_fixes_archive.md#set-10-reliable-flagship-answers-and-saved-history)
- [Set 11: live feedback of 2026-09-13 and 2026-09-14](UI_fixes_archive.md#set-11-live-feedback-of-2026-09-13-and-2026-09-14)
- [Set 12: the second tester's questions](UI_fixes_archive.md#set-12-the-second-testers-questions)
- [Session history, 2026-09-21 to 2026-09-27](UI_fixes_archive.md#session-history-2026-09-21-to-2026-09-27)
- [Shipped days, 2026-09-20 to 2026-09-23](UI_fixes_archive.md#shipped-days-2026-09-20-to-2026-09-23)
- [History and what is live](UI_fixes_archive.md#history-and-what-is-live)
- [Developer detail](UI_fixes_archive.md#developer-detail)
