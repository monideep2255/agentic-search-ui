# Product check on develop: cards 139 (notes) and 134 (paper titles)

Pre-screen before the owner's retest, on 2026-10-22. It files findings and closes nothing. The owner's verdict closes.

## Table of contents

- [Target](#target)
- [Findings](#findings)
- [Per query results](#per-query-results)
- [Summary](#summary)

## Target

- Web: https://search-agent-web-develop-2aeb.up.railway.app
- API /health, read before the first capture: `{"status":"ok","app_env":"develop"}`
- Deployed commit named in the brief: dfd5e4ff
- Guest sessions only, no sign-in, no accounts. Every run is a fresh browser context loaded at the width in its file name; a file ending `_390resized` is the same page resized to 390 after the answer landed.
- Times are on my clock from the Search click: first records is the first moment a records list or table is on screen, done is when the answer meta line appears. One run per row, so each time is one observation.

## Findings

### PR-notes-01: The same query 104 answer carries the "no written summary" note in one run and not in two others
- Kind: answer
- Verdict: needs your eye
- What: all three query 104 runs show the same count line and no written summary beyond it. Plain language at 1280 ends its notes with "Note: no written summary could be checked against the records, so this answer lists the records found with their sources". Plain language at 390 (fresh load) and Researcher at 1280 show no such note. Where the note shows, its wording is the one card 139 asks for, with no "listed below". From card 139 or earlier: the wording is card 139's and is right; whether the note shows at all looks like run-to-run variation in whether a summary was written and dropped, which card 139 did not change. I cannot tell from the screen which it is.
- Evidence: `c139_q104_plain_1280.txt` and `.png` (note present), `c139_q104_plain_390.txt`, `c139_q104_researcher_1280.txt` (note absent).
- Why a person would care: "Twice it said nothing about a missing summary, once it told me one could not be checked. Same question, same records."
- NOT CLOSED

### PR-notes-02: Query 104 in Researcher names the records by database code: "Found 5 nuccore records, 1 sra record and 5 assembly records"
- Kind: answer
- Verdict: needs your eye
- What: the Researcher count line reads "Found 5 nuccore records, 1 sra record and 5 assembly records for PMID 11237011." and the table headings read "NUCCORE RECORDS FOUND", "SRA RECORDS FOUND", "ASSEMBLY RECORDS FOUND". The notes under the same answer say "sequence records" and "genome assemblies". Plain language says "I found 5 records, 1 sequencing dataset and 5 genome assemblies", where "5 records" does not say records of what. Already there before these cards: neither card changes the count line or headings.
- Evidence: `c139_q104_researcher_1280.txt` and `.png`; `c139_q104_plain_1280.txt`.
- Why a person would care: "What is a nuccore record? The note below calls them sequence records. And in plain language, five records of what?"
- NOT CLOSED

### PR-notes-03: A paper data question offers follow-ups about variants and recruiting trials
- Kind: answer
- Verdict: needs your eye
- What: under query 104, a question about the data linked to one paper, the follow-up chips are "What variants cause it?", "Which trials are recruiting?" and "What does the literature add?". "It" has no referent here. Already there before these cards.
- Evidence: `c139_q104_plain_1280.txt`, `c139_q104_researcher_1280.txt`.
- Why a person would care: "What variants cause what? I asked about a paper."
- NOT CLOSED

### PR-notes-04: The CFTR Plain language answer opens its summary with "Another finds", after a first finding that is not there
- Kind: answer
- Verdict: fail
- What: query 117 in Plain language at 1280 reads "I found 54 published papers related to CFTR, out of 1962 available." then, as the next sentence, "Another finds that a cellular energy-sensing protein can turn CFTR off." Nothing before it names a first finding. Query 1's entry says the answer never opens on a broken sentence. From these cards or earlier: neither card's diff is in the summary writer as far as the cards describe, so most likely already there (a summary sentence dropped by a check); not proven either way from the screen.
- Evidence: `c134_q117_plain_1280.txt` and `c134_q117_plain_1280.png`.
- Why a person would care: "Another what? It feels like a paragraph is missing."
- NOT CLOSED

### PR-notes-05: The CFTR Researcher answer at 1280 has no written summary and no note saying so; the 390 run of the same question has one
- Kind: answer
- Verdict: needs your eye
- What: query 117 in Researcher at 1280 shows only "Found 54 papers for CFTR, of 1962 available." then the tables; its only note is the truncation note. The fresh 390 run of the same question writes four summary paragraphs ("Sodium 4-phenylbutyrate downregulation of Hsc70 ... are also covered."). The brief asks that an answer whose summary is missing says so in the card 139 wording; this one says nothing. Whether this is card 139's case (a summary written then dropped) or a reply that never wrote one, the screen cannot tell.
- Evidence: `c134_q117_researcher_1280.txt` against `c134_q117_researcher_390.txt`.
- Why a person would care: "On my laptop I got a list with no explanation, on my phone a write-up. Which is the real answer?"
- NOT CLOSED

### PR-notes-06: The CFTR count says 54 papers while the answer lists 59 papers in two tables, "Article records" and "PubMed records"
- Kind: answer
- Verdict: fail
- What: Researcher opens "Found 54 papers for CFTR, of 1962 available." The "ARTICLE RECORDS FOUND" table pages through 54, and "PUBMED RECORDS FOUND" lists 5 more papers. "1962 available" counts graph records (the note says "only 117 of the 1962 records ... were retrieved"), not papers. Plain language's list reads "Showing 1–10 of 71". Already there before these cards (filed as PR-answers-06 and 07 in the 2026-10-22 answers check); card 134 now gives the five PubMed rows titles, so the second table is easier to read, not new.
- Evidence: `c134_q117_researcher_1280.txt`, `c134_q117_researcher_390.txt`, `c134_q117_plain_1280.txt`.
- Why a person would care: "It says 54 papers, then shows me a second list of papers, and 1962 of what?"
- NOT CLOSED

### PR-notes-07: In Plain language, four CFTR papers read "Published paper" with no title and no number
- Kind: answer
- Verdict: fail
- What: across all 8 pages of the Plain language CFTR list (71 rows, fresh load at 390), four rows read only "Published paper", citations 18, 33, 44 and 45. Researcher shows the same four as "PMID:11109941 | PMID:11109941", "PMID:11397675", "PMID:11680956" and "PMID:11683083". PubMed gives each of the four a title only in square brackets (a translated title, for example "[Genetic testing for cystic fibrosis: evaluation of the Elucigene CF20 kit in blood and buccal cells]."), which query 117's entry allows to keep its number. Plain drops the number too, so the entry's "never a ... 'Published paper' row" and the brief's "a paper with no usable title shows PMID:n" both fail in Plain. These are graph papers, not enrichment-layer papers. Already there before card 134: its fresh verifier recorded "Plain on all three trees: Published paper" (`testing/Developer/reports/2026-10-22_card134/verify.md`, V-134-03).
- Evidence: `c134_q117_plain_pages_390.txt` lines 84, 191, 248, 249; `c134_q117_researcher_pages_1280.txt` lines 106, 259, 339, 340; screenshots `c134_q117_plain_pages_390_p1.png`, `_last.png`.
- Why a person would care: "Published paper. Which one? There is nothing to click on or search for."
- NOT CLOSED

### PR-notes-08: Researcher shows untitled papers as the same number twice, "PMID:11109941 | PMID:11109941"
- Kind: answer
- Verdict: needs your eye
- What: the four bracket-titled papers in the Researcher table read "PMID:n" in both the Paper and the Identifier column. This is the form the brief asks for ("a paper with no usable title shows PMID:n"), so it passes the brief, but the reader still sees the number twice and nothing else. PubMed does hold a readable (bracketed, translated) title for each. Card 134's verifier filed the same shape as V-134-03.
- Evidence: `c134_q117_researcher_pages_1280.txt` line 106: "PMID:11109941	PMID:11109941".
- Why a person would care: "Why does it print the number twice? PubMed shows me a title for this paper."
- NOT CLOSED

### PR-notes-09: Two CFTR runs took just over 20 seconds
- Kind: answer
- Verdict: needs your eye
- What: the second pair of CFTR runs landed in 20.4 s (Plain language, 390, meta "Answered19.7s") and 21.4 s (Researcher, 1280, meta "Answered20.9s") on my clock from the Search click. The first three CFTR runs landed in 14.1 to 17.6 s. The owner's bar is every answer within 20 s. One run each, so these are two observations, not a rate; the paging runs ran straight after the first batch, so a busier service is one other cause that gives the same numbers.
- Evidence: `c134_q117_researcher_pages_1280.txt` line 4 "Answered20.9s"; `c134_q117_plain_pages_390.txt` "Answered19.7s"; capture log times 20.43 and 21.43.
- Why a person would care: "It is a list of papers; why is it taking longer than everything else?"
- NOT CLOSED

### PR-notes-10: The query 1 control in Plain language at 1280 now opens on a statistic, not on the diseases asked about
- Kind: answer
- Verdict: needs your eye
- What: query 1 in Plain language at 1280 opens "Changes in this gene account for roughly 40% of inherited breast cancers and over 80% of inherited breast and ovarian cancers combined." then "I found 4 conditions related to BRCA1." The prose never names the four conditions; only the list does. The earlier check today opened "I found 4 conditions related to BRCA1." (`testing/Developer/reports/2026-10-22_product_check_answers/control_q1_brca1_plain_1280.txt`). The fresh 390 run in this check opens with the answer: "BRCA1 is associated with four diseases: Familial cancer of breast, ...". So the control does not read exactly as before: it gained a cited background sentence ([23], the gene summary) in both runs, and at 1280 that sentence leads. "This gene" comes before BRCA1 is named. From these cards or earlier: card 134 changes which view of a page is kept, which could change what the writer is given, but run-to-run variation in the writer gives the same picture; one run each cannot separate them.
- Evidence: `control_q1_plain_1280.txt` and `.png` against `control_q1_plain_390.txt` and `.png`.
- Why a person would care: "I asked which diseases. It told me a percentage about an unnamed gene first."
- NOT CLOSED

### PR-notes-11: Query 1 in Researcher names the four diseases twice in a row
- Kind: answer
- Verdict: needs your eye
- What: Researcher opens "BRCA1 is associated with four diseases: familial cancer of breast, familial breast-ovarian cancer susceptibility 1, pancreatic cancer susceptibility 4, and Fanconi anemia complementation group S." and the very next sentence is "Found 4 disease records for BRCA1: Familial cancer of breast, Familial breast-ovarian cancer susceptibility 1, Pancreatic cancer susceptibility 4 and Fanconi anemia complementation group S." The same four names, twice, back to back, at both widths. Query 1's entry describes this order (answer sentence, then the "Found N" line), so it is by design and already there; it still reads as a repeat.
- Evidence: `c134_q1_researcher_1280.txt`, `c134_q1_researcher_390.txt`.
- Why a person would care: "It just said that."
- NOT CLOSED

### PR-notes-12: Researcher answers still head a paper table "PubMed records found" and cite chip 23 under "21 sources"
- Kind: answer
- Verdict: needs your eye
- What: query 1 Researcher shows "PUBMED RECORDS FOUND" above its five papers, and its summary sentence carries chip 23 ("...maintaining genomic stability.23") while the Sources header says 21. Both were already there (PR-answers-03 and PR-answers-05 in the 2026-10-22 answers check); neither card changes them. Card 134's papers now carry titles in that table.
- Evidence: `c134_q1_researcher_1280.txt`, `c134_q1_researcher_1280.png`.
- Why a person would care: "21 sources, so where is 23?"
- NOT CLOSED

### PR-notes-13: The CFTR Researcher summary at 390 also starts mid-thought, "... are also covered"
- Kind: answer
- Verdict: fail
- What: the fresh 390 Researcher run of query 117 reads "Found 54 papers for CFTR, of 1962 available." then "Sodium 4-phenylbutyrate downregulation of Hsc70 and its implications for ΔF508-CFTR intracellular trafficking are also covered." "Also" points back at a sentence that is not there; the next paragraph says "are additionally reported". Same pattern as PR-notes-04 in Plain language: two of the three CFTR runs that wrote a summary open it as if an earlier sentence was removed. The summary also carries an em dash from the writer ("specific CFTR variants—D579G"). From these cards or earlier: not provable from the screen; neither card describes a change to the summary writer.
- Evidence: `c134_q117_researcher_390_fold.png` (read myself), `c134_q117_researcher_390.txt`.
- Why a person would care: "Also covered, as well as what? It starts in the middle."
- NOT CLOSED

## Per query results

Times: first records / done, seconds from the Search click on my clock. Overflow is scrollWidth minus clientWidth at 390; 0 in every run, including the 1280 pages resized to 390.

| Query | Card | Depth | Width | First records / done | Entry and brief | Screenshot |
|---|---|---|---|---|---|---|
| 104 PMID data | 139 | Plain | 1280 | 6.7 / 9.2 | Pass: "this answer shows 5" for 5 sequence records and 5 assemblies shown; fallback note in card wording, no "listed below"; notes after the list | `c139_q104_plain_1280.png` |
| 104 PMID data | 139 | Plain | 390 fresh | 6.3 / 8.8 | Pass on the counts; no summary note (PR-notes-01) | `c139_q104_plain_390.png` |
| 104 PMID data | 139 | Researcher | 1280 | 5.0 / 7.0 | Pass on the counts; database codes in headings (PR-notes-02) | `c139_q104_researcher_1280.png`, `_390resized.png` |
| 117 CFTR papers | 134 | Researcher | 1280 | 11.3 / 17.6 | Pass on card 134: five enrichment papers carry PubMed titles ("Molecular Structure of the Human CFTR Ion Channel." for PMID:28340353), no "Title not retrieved", no "28340353 \| PMID:28340353". Entry fails on two paper tables and a count of 54 for 59 papers (PR-notes-06, earlier) | `c134_q117_researcher_1280.png` |
| 117 CFTR papers | 134 | Researcher | 390 fresh | 9.8 / 14.1 | Same as 1280; summary opens mid-thought (PR-notes-13) | `c134_q117_researcher_390.png`, `_fold.png` |
| 117 CFTR papers | 134 | Researcher | 1280, all 6 pages | done 21.4 | Every row titled except 4 bracket-titled graph papers shown as "PMID:n" twice (PR-notes-08); over 20 s (PR-notes-09) | `c134_q117_researcher_pages_1280_p1.png`, `_last.png` |
| 117 CFTR papers | 134 | Plain | 1280 | 11.4 / 16.4 | Titles shown; summary opens with "Another finds" (PR-notes-04) | `c134_q117_plain_1280.png`, `_390resized.png` |
| 117 CFTR papers | 134 | Plain | 390 fresh, all 8 pages | done 20.4 | Fail on the entry: 4 rows read "Published paper" (PR-notes-07, earlier); over 20 s (PR-notes-09) | `c134_q117_plain_pages_390_p1.png`, `_last.png` |
| 1 BRCA1 diseases | 134 | Researcher | 1280 | 6.2 / 8.8 | Pass: all 5 papers titled; diseases in words; diseases named twice (PR-notes-11) | `c134_q1_researcher_1280.png` |
| 1 BRCA1 diseases | 134 | Researcher | 390 fresh | 4.7 / 9.3 | Pass, same | `c134_q1_researcher_390.png` |
| 1 control | none | Plain | 1280 | 6.0 / 8.5 | Needs your eye: opens on a statistic about "this gene", not the diseases (PR-notes-10) | `c134_q1_researcher_1280.png` is Researcher; control is `control_q1_plain_1280.png`, `_390resized.png` |
| 1 control | none | Plain | 390 fresh | 8.5 / 11.5 | Pass: opens "BRCA1 is associated with four diseases: ..." | `control_q1_plain_390.png` |

Card 139's third complaint ("does not address the following entities named in the question" naming CFTR-AS1 or LOC numbers) did not appear in any of the five CFTR runs.

## Summary

- Golden run: not run. The brief is guest only with no accounts, and the golden instrument signs in with two accounts. Both cards change answers, so the owner's verdict is still needed and the golden floor has not been checked for this deploy.
- Answered well of the fixed ten: not read, for the same reason.
- Card 139: pass at 1280 and 390 on query 104. Every "this answer shows M" equals the rows of that kind shown, and no note in any of the 12 answers says "listed below" or "listed above" (searched across every saved text).
- Card 134: pass at 1280 and 390 on its own change. Enrichment papers carry their PubMed titles in Researcher and Plain language, in query 117 and query 1. Query 117's entry still fails on "Published paper" rows in Plain language, which were there before this card.
- Worse than before: only the control's opening at 1280 (PR-notes-10), cause not separable from writer variation in one run. Two CFTR runs went just past 20 s.
- Screens: the answer screen's layout did not change in either card, so it was compared against the prototype captures already in `testing/Developer/reports/2026-10-22_product_check_answers/` (`prototype_answer_1280.png`, `prototype_answer_390.png`), not recaptured. No overflow at 390. No new surface, so no missing design.
- Full-page screenshots show the fixed header and footer bars painted mid-page; that is how a full-page capture draws fixed bars, not a page defect. Where a bar covers a row, the `.txt` file beside the screenshot has the full text.
- Read myself: the screenshots `c139_q104_plain_1280.png`, `c139_q104_plain_390.png`, `c134_q1_researcher_390.png`, `c134_q117_researcher_390_fold.png`, and every `.txt` answer file named above. Not opened as images: the other screenshots; their verdicts rest on the saved page text from the same run.
- Not captured: the golden run and the answered-well ten (no accounts by brief); a second run of any query, so every time and every wording difference is one observation.
- Correction to the table: the screenshots for the control at 1280 are `control_q1_plain_1280.png` and `control_q1_plain_390resized.png`; the mention of `c134_q1_researcher_1280.png` in that row is not part of the control. The one em dash in this report sits inside a quote of the app's own text (PR-notes-13).
