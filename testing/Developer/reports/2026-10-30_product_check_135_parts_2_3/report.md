# Product check of card 135, parts 2 and 3, on develop, 2026-10-30

A pre-screen before the owner retests. It closes nothing; the owner's verdict closes.

- Target: develop web `https://search-agent-web-develop-2aeb.up.railway.app`. The API's `/health` read `{"status":"ok","app_env":"develop"}` before the first capture, and `origin/develop` sits at 97356fe1 (merge of #317), as the brief states.
- Signed in with a throwaway develop account. The research-tool disclaimer was ticked in a fresh automated browser. No golden run, by the brief.
- Capture: one Playwright script run from `frontend/`, which asks the question in Researcher at 1280, reads and screenshots the live answer, resizes the same page to 390, then reopens the answer from "Your searches" at 1280 and resizes again to 390. Every judgement below names the file it rests on, all in this folder.
- The decision under test: `DECISIONS.md`, 2026-10-30, last row.
- A range marker the app draws with a dash between two numbers is written here as "1 to 4", the house style allowing no dash.

## Table of contents

- [Findings](#findings)
- [Summary](#summary)

## Findings

### PR-135B-01: Query 21's reopened answer no longer shows "omim LIVE", "ncbi_efetch" or bracketed numbers
- Kind: screen
- Verdict: pass
- From: this change
- What: reopened from "Your searches", the Sources list reads "8. omim 138079", "5, 9, 24. gene 2645", "11. ClinicalTrials.gov NCT01029795", and so on: no "omim LIVE", no "ncbi_efetch", no "ncbi_gene", no lowercase "clinicaltrials.gov" source name. The answer body holds no literal "[n]" text: the script found 0 bracketed numbers and 33 raised markers. The gene row reads "GCK" with markers "5, 9", as on the live answer, where the earlier check saw "GCK [5][9]".
- Evidence: `q21_saved_answer_sources_open.txt`, `q21_log.json` (`saved_literal_brackets: []`, `saved_markers` 33 entries, `saved_sources`), `q21_saved_1280_marker_card.png`. Earlier check: `testing/Developer/reports/2026-10-30_product_check_135_136/report.md`, PR-135-136-05 and 09.
- Why a person would care: the saved copy no longer reads like debugging output, and its numbers can be pressed.
- NOT CLOSED

### PR-135B-02: A citation marker on the reopened answer opens a source card, at 1280 and 390
- Kind: screen
- Verdict: pass
- From: this change
- What: pressing marker 1 in the reopened opening sentence at 1280 opened a card reading "[1] L2 · live", "MedGen C0011860", "Open the record". Pressing marker 1 in the first disease row at 390 opened the same card. The live card for the same source also shows a grey "name" line, the internal field, which the saved card leaves out.
- Evidence: `q21_saved_1280_marker_card.png`, `q21_saved_390_row_marker_card.png`, `q21_live_1280_marker_card.png`, `q21_log.json` (`saved_1280_marker_first`, `saved_1280_marker_table`, `saved_390_marker_row`).
- Why a person would care: they can check a claim's record from a saved answer, as they could from the live one.
- NOT CLOSED

### PR-135B-03: Query 21's reopened opening sentence shows a marker after each disease, where the live answer shows one "1 to 4" range
- Kind: screen
- Verdict: needs your eye
- From: this change (before it, the same places held "[1]", "[2]" text)
- What: the live answer ends the first sentence "Permanent neonatal diabetes mellitus 1." with one marker "1 to 4". The reopened answer puts a marker after each disease instead: "Type 2 diabetes mellitus,1 Maturity-onset diabetes of the young type 2,2 Hyperinsulinemic hypoglycemia, familial, 3,3 and Permanent neonatal diabetes mellitus 1.4". Disease names that end in a number then read "type 2,2", "familial, 3,3" and "mellitus 1.4", where only the colour and size tell name from marker. The same happens in the reopened table's first cells ("familial, 3" followed by marker 3), where the live table puts the marker in its own right-hand column. The stored answer carries a marker per disease, so this is how the saved text was written, not a range the screen failed to collapse.
- Evidence: `q21_saved_1280_marker_card.png`, `q21_saved_390_row_marker_card.png`, `q21_live_1280_marker_card.png`, `q21_saved_answer.txt`, `q21_live_answer.txt`.
- Why a person would care: "familial, 3,3" and "mellitus 1.4" can be misread as part of the disease name, and the saved copy does not look like the answer they first read.
- NOT CLOSED

### PR-135B-04: A literature gene source is named "NCBI Gene @GENE_GCK" and links to gene 24385, on live and reopened
- Kind: screen
- Verdict: needs your eye
- From: this change for the "NCBI Gene" prefix; the "@GENE_GCK" identifier and the record behind it are earlier (card 149 covers a rat gene in a human answer)
- What: source 10 reads "NCBI Gene @GENE_GCK" on the live Sources list and "10. NCBI Gene @GENE_GCK" on the reopened one, linking to `https://www.ncbi.nlm.nih.gov/gene/24385`. The human GCK record in the same answer is gene 2645. "@GENE_GCK" is an annotation tag, not an NCBI Gene record number, so the new database-and-record label pairs a real database name with an id NCBI Gene does not use. The literature table's row still reads "Gck | @GENE_GCK".
- Evidence: `q21_live_answer_sources_open.txt`, `q21_saved_answer_sources_open.txt`.
- Why a person would care: a label reading like an official NCBI Gene record, for a record that is probably not the human gene, makes a confident wrong record look more trustworthy.
- NOT CLOSED

### PR-135B-05: The citation card at 390 runs a few pixels past the bottom of the screen
- Kind: screen
- Verdict: needs your eye
- From: earlier (the live card's placement code, reused here)
- What: marker 1 in the first stacked disease row, near the bottom of a 390x844 screen, opened a card measured at y 760.75 with height 91.6, so its bottom edge sits at about 852, 8 pixels below the 844 screen. In the screenshot "Open the record" is still readable and pressable, and the card covers the footer. Page overflow stays 0.
- Evidence: `q21_saved_390_row_marker_card.png`, `q21_log.json` (`saved_390_marker_row.box`).
- Why a person would care: little today; a card with two or more rows opened at the same place would lose its last link off screen.
- NOT CLOSED

### PR-135B-06: Isolate sources read "Pathogen Detection SAMN..." on the live and reopened answer, never "pathogen_detection"
- Kind: screen
- Verdict: pass
- From: this change
- What: `What Escherichia coli isolates in Pathogen Detection carry extended-spectrum beta-lactamase genes?` in Researcher answered in 15.5 seconds ("Answered15.5s · 2 tool calls · 21 sources cited from 1 layer"). The live source cards read "Pathogen Detection SAMN00715300" and so on, and the reopened Sources list reads "1. Pathogen Detection SAMN00715300" through 20, each linking to `https://www.ncbi.nlm.nih.gov/pathogens/isolates#/search/biosample_acc:SAMN...`. "pathogen_detection" appears 0 times in either page's text, sources opened.
- Evidence: `iso_live_answer_sources_open.txt`, `iso_saved_answer_sources_open.txt`, `iso_log.json` (`saved_sources`, `live_tool_names: []`, `saved_tool_names: []`).
- Why a person would care: a microbiologist sees the database and the BioSample accession they can look up, not a tool name.
- NOT CLOSED

### PR-135B-07: The isolate table's first cell shows raised markers on the reopened answer, at 1280 and in the stacked rows at 390, and the range matches live
- Kind: screen
- Verdict: pass
- From: this change
- What: the reopened opening sentence ends "for Escherichia coli." with one "1 to 20" marker, as on the live answer. Its card lists sources 1 to 20, each "Pathogen Detection SAMN..." with "Open the record". At 1280 the isolate table's first cells read "C236-11" with marker 1, "11-3677" with marker 2, and so on, and marker 1 opens a card for "Pathogen Detection SAMN00715300". At 390 the stacked rows carry the same markers beside the isolate name, and marker 1 opens the same card, inside the screen (x 93, width 280). The taxonomy row "Escherichia coli" carries marker 21. Twelve markers on both screens, no bracketed numbers on the reopened one. Overflow at 390: 0 px, live and reopened.
- Evidence: `iso_saved_1280_table_marker_card.png`, `iso_saved_390_row_marker_card.png`, `iso_saved_1280_range_marker_card.png`, `iso_live_1280_marker_card.png`, `iso_log.json` (`live_markers`, `saved_markers`, `saved_390_marker_ids`, `live_390_overflow`, `saved_390_overflow`).
- Why a person would care: each saved isolate row can be checked against its record, as on the live answer.
- NOT CLOSED

### PR-135B-08: A marker against an isolate name that ends in digits reads as part of the name
- Kind: screen
- Verdict: needs your eye
- From: this change (the live table keeps the marker in its own right-hand column)
- What: on the reopened table the marker sits straight after the isolate name: "C236-11" then a green raised "1", "11-3677" then "2", "11-4404" then "3". Isolate names are codes, so "11-36772" is a plausible misreading. The live table shows the isolate name alone and the marker in the last column.
- Evidence: `iso_saved_1280_table_marker_card.png`, `iso_saved_390_row_marker_card.png`, `iso_live_answer.txt` (rows end with the marker after "Not recorded").
- Why a person would care: a reader copying an isolate name from the saved copy can take a wrong code.
- NOT CLOSED

### PR-135B-09: The isolate answer's first sentence lists what was found instead of answering
- Kind: answer
- Verdict: needs your eye
- From: earlier
- What: the first sentence is "Found 20 pathogen detection isolate records and 1 taxonomy record for Escherichia coli." and the page says "Note: no written summary could be checked against the records, so this answer lists the records found with their sources". Rubric line 1 fails on this run. The scope sentence is useful: "Searching Escherichia coli isolates in Pathogen Detection for AMR genotypes starting blaCTX-M; blaTEM and blaSHV alleles were not searched". One run.
- Evidence: `iso_live_answer.txt`, `iso_saved_answer.txt`.
- Why a person would care: they asked which isolates carry ESBL genes and are first told a record count.
- NOT CLOSED

### PR-135B-10: Query 1's reopened Sources list names every source as the live list does, and no tool name appears on either
- Kind: screen
- Verdict: pass
- From: this change
- What: `Which diseases are associated with BRCA1?` in Researcher answered in 10.1 seconds ("Answered10.1s · 13 tool calls · 21 sources cited from 2 layers"). The live source cards read "MedGen C0346153", "gene 672", "pubmed 16998500", "clinvar 267740", "omim 113705" and "ClinicalTrials.gov NCT00590109"; the reopened Sources list reads the same names ("5, 9, 23. gene 672", "8. omim 113705", "10. ClinicalTrials.gov NCT00590109"). No tool name on either page; the only "clinicaltrials.gov" in lowercase is inside the record links. Marker 1 on the reopened answer at 1280 opened "[1] L2 · live", "MedGen C0346153", "Open the record".
- Evidence: `q1_live_answer_sources_open.txt`, `q1_saved_answer_sources_open.txt`, `q1_log.json` (`saved_sources`, `saved_1280_marker_first`, `saved_1280_marker_table`), `q1_saved_1280_marker_card.png`.
- Why a person would care: the saved copy names its sources the way the answer they first read did.
- NOT CLOSED

### PR-135B-11: The reopened gene source reads "gene 672", not "BRCA1"
- Kind: screen
- Verdict: needs your eye
- From: earlier, as far as the screen shows (not checked against the stored record)
- What: the brief's expectation was that graph sources keep their own names on the reopened answer, for example "BRCA1". On this run the reopened list reads "5, 9, 23. gene 672" and no reopened source is named "BRCA1". The live card reads "gene 672" too. By `frontend/src/components/screens/SavedAnswerScreen.tsx` (the `label` lines in `CitationRow`), a stored name wins when there is one, so this answer's stored citation for gene 672 carries no name; the same holds for query 21's "gene 2645". I did not read the stored citations from the API. The live card is not "NCBI Gene 672" either: the database label applies only to sources that carried a tool name, and "gene" is not one.
- Evidence: `q1_saved_answer_sources_open.txt`, `q1_live_answer_sources_open.txt`, `q21_saved_answer_sources_open.txt`.
- Why a person would care: "gene 672" is readable but lowercase and unnamed; whether "BRCA1" ever shows depends on what was stored, which this check cannot see.
- NOT CLOSED

### PR-135B-12: Query 1's reopened answer shows separate markers where the live answer shows "1 to 4" and "5, 9"
- Kind: screen
- Verdict: fail
- From: this change (before it, the same places held bracketed text)
- What: the brief's "after" for query 1 is that ranges show as on live. They do not on this run. The live answer ends both opening sentences with one "1 to 4" marker and the gene sentence with "5, 9": "The gene symbol for BRCA1 is BRCA1, corresponding to the gene name BRCA1.5, 9". The reopened answer puts one marker per disease, "familial cancer of breast,1 familial breast-ovarian cancer susceptibility 1,2 pancreatic cancer susceptibility 4,3 and Fanconi anemia complementation group S.4", and splits the gene sentence, "BRCA1,5 corresponding to the gene name BRCA1.9". The reopened answer has 35 markers where the live one has 29. The stored text carries a number per item, so the screen renders what was stored; a range is collapsed only inside one run of numbers. Query 21 shows the same pattern (PR-135B-03), and "susceptibility 1,2" and "susceptibility 4,3" can be read as part of the disease names. The isolate answer's single "1 to 20" range does match live (PR-135B-07).
- Evidence: `q1_live_answer.txt`, `q1_saved_answer.txt`, `q1_log.json` (`live_markers` 29, `saved_markers` 35), `q1_saved_390_row_marker_card_first_try.png`, `q1_saved_1280_marker_card.png`.
- Why a person would care: the saved copy reads differently from the answer they read, and numbers after a disease name look like part of it.
- NOT CLOSED

### PR-135B-13: At 390, two reopened markers near the foot of the screen opened no card when pressed
- Kind: screen
- Verdict: needs your eye
- From: unknown; the live answer was not tried the same way
- What: pressing each of the 29 distinct markers on the reopened query 1 answer at 390x844, scrolled into view one at a time, opened a card for 27. The two that did not were the ones scrolled to y 833 (marker 1, first disease row) and y 796 (marker 16, third trial row), inside the bottom band where the fixed footer sits; the page scrolled, the marker showed its pressed underline, and no card opened. The same marker 1 sitting at y 760 on query 21 opened at once. This failed the same way in two separate runs. It may be the automated press landing during a scroll rather than something a person meets, since a person cannot tap a marker under the footer; pressing marker 1 again after scrolling it higher was not tried.
- Evidence: `q1_diag390_log.json`, `q1_diag390_saved-answer-15-2-citation-16.png`, `q1_saved_390_row_marker_card_first_try.png`, `q1_log_first_try.json` and `q1_log.json` (`saved_390_marker_row.opened: false`).
- Why a person would care: if a person meets it, a tap on a number near the bottom of a phone makes the page jump and shows nothing.
- NOT CLOSED

### PR-135B-14: Query 1's second paragraph says the gene symbol is itself
- Kind: answer
- Verdict: needs your eye
- From: earlier
- What: "The gene symbol for BRCA1 is BRCA1, corresponding to the gene name BRCA1." Rubric line 1 passes: "BRCA1 is associated with four diseases retrieved from the knowledge graph: familial cancer of breast, familial breast-ovarian cancer susceptibility 1, pancreatic cancer susceptibility 4, and Fanconi anemia complementation group S." Rubric line 2 is helped by "Mutations in BRCA1 account for approximately 40% of inherited breast cancers and more than 80% of inherited breast and ovarian cancers." One run.
- Evidence: `q1_live_answer.txt`.
- Why a person would care: a sentence that says nothing makes the rest look less careful.
- NOT CLOSED

### PR-135B-15: The saved answer screen has no design
- Kind: missing design
- Verdict: needs your eye
- From: earlier (design gap)
- What: `docs/build/design/README.md`'s coverage table has no row for the saved answer screen, and the prototype has no saved answer. The markers and cards were judged against the live answer screen and the citation chip it shares, not against a design. One placement differs from the live screen by design of the code: a table row's markers sit in its first cell on the reopened answer (`frontend/src/components/screens/savedAnswerMarkdown.tsx`, `firstCell`), where the live table gives them their own last column (PR-135B-08).
- Evidence: `docs/build/design/README.md` lines 78 to 92, `iso_saved_1280_table_marker_card.png`, `iso_live_answer.txt`.
- Why a person would care: no agreed look exists for the saved copy, so "same as live" is the only bar.
- NOT CLOSED

### PR-135B-16: The live answer's layout and source cards are as before; only the tool-named sources changed
- Kind: screen
- Verdict: pass
- From: this change
- What: #317 changes only files under `frontend/` and two report files (`git diff --stat 97356fe1^1 97356fe1`), so it cannot change what the writer says. On query 21 the live meta line, depth toggle, record tables with their own marker column, opening "1 to 4" range and source card fields read as in the earlier check. The second paragraph differs ("From another gene record titled "GCK": Unlike other hexokinases, this enzyme is not inhibited by its product..." where the earlier run said "Recent work describes inhibition of Hmbox1..."), which is the writer varying between runs. The only source name change seen on live is the one the brief names: "ClinicalTrials.gov NCT..." and "NCBI Gene @GENE_GCK" (see PR-135B-04).
- Evidence: `q21_live_answer.txt` beside `testing/Developer/reports/2026-10-30_product_check_135_136/q21_live_answer.txt`, `q21_live_1280_marker_card.png`, `q21_live_answer_sources_open.txt`.
- Why a person would care: nothing on the live answer moved except the names that used to be tool names.
- NOT CLOSED

Note on PR-135B-03: it is the same pattern as PR-135B-12, which the brief's "ranges show as on live" makes a fail. Read PR-135B-03 as a fail for query 21 as well.

## Summary

| Line of the brief | Verdict | Findings |
|---|---|---|
| Query 21: "omim LIVE" and plain "[1]", "[5][9]" gone on the reopened answer | Pass at 1280 and 390 | PR-135B-01, 02 |
| Isolate sources read "Pathogen Detection SAMN...", live and reopened | Pass | PR-135B-06 |
| Table first cells and stacked rows at 390 show markers | Pass, with a misreading risk | PR-135B-07, 08 |
| Graph sources keep their own names on the reopened answer | Not seen: no reopened source carried a name to keep ("gene 672", "gene 2645") | PR-135B-10, 11 |
| Markers open cards on the reopened answer | Pass at 1280; at 390, 27 of 29 opened | PR-135B-02, 07, 13 |
| Ranges show as on live | Fail on queries 1 and 21; pass on the isolate answer | PR-135B-12, 03 |
| Live answer names tool-named sources by database, otherwise unchanged | Pass, but "NCBI Gene @GENE_GCK" | PR-135B-16, 04 |

Answer times, Researcher, one ask each:

| Question | Meta line | Script clock, submit to meta line |
|---|---|---|
| Query 21, `Which diseases are associated with GCK?` | 9.6 s | not kept (the first run stopped before writing its log) |
| `What Escherichia coli isolates in Pathogen Detection carry extended-spectrum beta-lactamase genes?` | 15.5 s | 16.0 s |
| Query 1, `Which diseases are associated with BRCA1?` | 10.1 s | 10.4 s |

None over 20 seconds. Each question was asked once.

What to look at first, ranked:

1. Fail: PR-135B-12, with PR-135B-03: reopened answers show a marker per item where live shows one range, so "susceptibility 1,2" and "familial, 3,3" read as part of a name.
2. Needs your eye: PR-135B-04, "NCBI Gene @GENE_GCK" linking to gene 24385 in a human GCK answer.
3. Needs your eye: PR-135B-08, a marker straight after an isolate code ("11-3677" then "2").
4. Needs your eye: PR-135B-13, two markers near the foot of a phone screen opened nothing.
5. Needs your eye: PR-135B-11, no reopened source was named "BRCA1", so the "keeps its own name" half was not seen working.
6. Needs your eye: PR-135B-05, PR-135B-09, PR-135B-14, PR-135B-15.

Overflow at 390: 0 px on every screen measured (isolate live and reopened, query 1 live and reopened, query 21 reopened, and every opened card). Query 21's live overflow at 390 was not recorded. Surface with no design: the saved answer screen (PR-135B-15).

What was not captured, and why:

- The prototype was not screenshot beside these screens: it has no saved answer screen, and the live answer screen is unchanged by this card.
- The live answers at 390 are the 1280 page resized, not a second ask; the brief allowed two asks and one was enough.
- The stored citations were not read from the API, so PR-135B-11 rests on the screen and the code, not the stored record.
- Query 21's live markers and live 390 overflow were lost when the first run stopped at the rail; its live text and screenshots were kept.
- Resizing to 390 opens the "Your searches" drawer; the scripts closed it before each 390 capture.
- The screenshots taken at 1280 show the throwaway account's address in the app bar and the rail footer. The 390 screenshots show only the initials. The text and log files have the address replaced. Check the images before any commit.

Every verdict above rests on a screenshot or answer file I read myself, except the overflow numbers, marker counts and the 27 of 29 cards, which rest on the scripts' logs (`q21_log.json`, `iso_log.json`, `q1_log.json`, `q1_diag390_log.json`).
