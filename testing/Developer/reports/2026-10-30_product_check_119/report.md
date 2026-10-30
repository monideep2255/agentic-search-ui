# Product check of card 119 on develop, 2026-10-30

A pre-screen before the owner retests card 119 (merged #312). It closes nothing; the owner's verdict closes.

- Target: develop web `https://search-agent-web-develop-2aeb.up.railway.app`, API `https://search-agent-api-develop-43b3.up.railway.app`. `/health` read `{"status":"ok","app_env":"develop"}` before the first capture, and every run logged it again (field `health` in each `*_log.json`).
- Deployed commit: 4eda8ca5, the merge of #312, as stated in the brief.
- Asked as a guest, no sign-in. No golden run, by the brief.
- Capture: a short Playwright script kept outside the repository, run from `frontend/`, one fresh browser per question and width. It picks the answer mode, asks, saves the "How far back" ask-back, clicks the window, times from that click to the finished answer (the `answer-meta` line), and saves the answer text, links, a full-page screenshot and `scrollWidth - clientWidth`.
- Paper years come from PubMed's own esummary record for each PMID the answer listed, looked up after capture.

## Table of contents

- [Findings](#findings)
- [Summary](#summary)

## Findings

### PR-119-01: The 5-year BRCA1 answer lists 9 papers, all inside the window, each with a title, and the count line counts them
- Kind: answer
- Verdict: pass
- Card: 119
- What: at 1280, Researcher, after picking "Recent papers on BRCA1 from the last 5 years?", the "PubMed records found" table has 9 rows, each with a title and a PMID. The count line reads "Found 9 papers for BRCA1." with markers 1 to 9. PubMed dates: 35432218 (2022), 36270245 (2022), 36914836 (2023), 37774066 (2023), 38266640 (2024), 39052257 (2024), 39261729 (2024), 39643918 (2024), 39510841 (2025). All inside 2021 to 2026. Before the card the same answer listed at most 5.
- Evidence: `testing/Developer/reports/2026-10-30_product_check_119/brca1_5y_1280_full.png`, `brca1_5y_1280_answer.txt`, `brca1_5y_1280_log.json`.
- Why a person would care: they asked for recent papers and get nine titled ones from the window, and the count matches what they see.
- NOT CLOSED

### PR-119-02: The GeneReviews chapter from 1993 is still listed in the 5-year BRCA1 answer, under its own "Publication records found" table
- Kind: answer
- Verdict: needs your eye
- Card: earlier, known (card 124 for the GeneReviews chapter; first seen as PR-card105-01). Not re-filed as new; recorded so the owner sees it is still there after card 119.
- What: below the 9 windowed papers, "Publication records found" lists "BRCA1- and BRCA2-Associated Hereditary Breast and Ovarian Cancer", PMID:20301425, marker 15. PubMed's esummary dates it 1993. The count line says 9 papers, so this chapter is not counted.
- Evidence: `testing/Developer/reports/2026-10-30_product_check_119/brca1_5y_1280_full.png`, `brca1_5y_1280_answer.txt`.
- Why a person would care: "I asked for the last five years and a 1993 record is listed."
- NOT CLOSED

### PR-119-03: The BRCA1 summary cites markers 24, 25 and 26 while the answer says 22 sources were cited
- Kind: answer
- Verdict: needs your eye
- Card: likely this card, since the summary sentences that carry these markers are the abstract-based summary card 119 changed; the same pattern of markers beyond the count was seen before card 119 (PR-121-123-03), so it may be earlier
- What: the summary sentences end with markers 24, 25 and 26. The meta line reads "22 sources cited from 2 layers", the Sources disclosure shows 22, and the line under the answer reads "Based on 22 sources cited". I did not open markers 24 to 26 or the Sources list, so I do not know whether they resolve.
- Evidence: `testing/Developer/reports/2026-10-30_product_check_119/brca1_5y_1280_full.png`, `brca1_5y_1280_answer.txt`: "contribute to BRCA1-driven tumorigenesis in vivo.24", "cancers in males.25", "inherited breast and ovarian cancers.26".
- Why a person would care: a reader checking the sentence they most want to trust finds source 24 when the answer says there are 22.
- NOT CLOSED

### PR-119-04: The BRCA1 summary opens on one study's detail instead of saying what the recent papers cover
- Kind: answer
- Verdict: needs your eye
- Card: 119 (the summary now draws on the best-matching abstracts)
- What: after "Found 9 papers for BRCA1." the next sentence is "Pre-cancer-associated fibroblasts producing protumorigenic factors such as MMP3 contribute to BRCA1-driven tumorigenesis in vivo." It is one finding from one paper, given no lead-in. A section "Male carriers and clinical management" follows with one sentence from a review and one from the gene record. Three of the nine papers are touched; the window ("last 5 years") is not named in any sentence. Rubric line 1: the count line answers "what recent papers are there" only by number. Rubric line 2: the male-carrier sentence is useful and specific.
- Evidence: `testing/Developer/reports/2026-10-30_product_check_119/brca1_5y_1280_answer.txt`.
- Why a person would care: they want to know what recent BRCA1 research is about; they get a fibroblast detail first, with no sense of the themes across the nine papers.
- NOT CLOSED

### PR-119-05: At 390 the same BRCA1 question listed 9 papers inside the window, and the page fits the phone width
- Kind: screen
- Verdict: pass
- Card: 119
- What: a second, separate run at 390, Researcher, picking the last 5 years: "Found 9 papers for BRCA1." over 9 titled rows stacked title over PMID. One paper differs from the 1280 run: 35671604, "Discovery of BRCA1/BRCA2 founder variants by haplotype analysis." (PubMed 2022 Aug) replaces 37774066. All 9 inside the window. Horizontal overflow 0 px. The GeneReviews 1993 chapter is again listed under "Publication records found" (known, card 124).
- Evidence: `testing/Developer/reports/2026-10-30_product_check_119/brca1_5y_390_full.png`, `brca1_5y_390_answer.txt`, `brca1_5y_390_log.json` (overflow `sw_minus_cw: 0`).
- Why a person would care: on a phone the list reads cleanly, one paper per block, no sideways scrolling.
- NOT CLOSED

### PR-119-06: In the second BRCA1 run the written summary draws on no paper at all, only the gene record
- Kind: answer
- Verdict: needs your eye
- Card: 119 (the card says the summary draws on the best-matching papers that have an abstract)
- What: the 390 run's whole summary is one sentence: "The BRCA1 gene encodes a 190 kD nuclear phosphoprotein that maintains genomic stability as a tumour suppressor, and mutations in this gene are responsible for approximately 40% of inherited breast cancers and more than 80% of inherited breast and ovarian cancers.24" That is the gene record's description, not any of the nine papers. Marker 24 again exceeds the 22 sources cited (see PR-119-03). The 1280 run of the same question did quote two papers. Two runs, two different kinds of summary.
- Evidence: `testing/Developer/reports/2026-10-30_product_check_119/brca1_5y_390_answer.txt`, `brca1_5y_390_full.png`; compare `brca1_5y_1280_answer.txt`.
- Why a person would care: they asked what recent papers say and are told what BRCA1 is, which any textbook or chatbot says; the nine papers go unsummarised.
- NOT CLOSED

### PR-119-07: The 5-year cystic fibrosis answer now has a written summary about the disease
- Kind: answer
- Verdict: pass
- Card: 119
- What: at 1280, Researcher, after picking the last 5 years: "Found 10 papers for cystic fibrosis." then "CFTR modulators have shifted the treatment paradigm by improving production of defective CFTR protein and increasing its cell-surface expression, thereby improving ion exchange, fluidizing respiratory secretions, and reducing airflow obstruction.11 Ongoing research is also directed at correcting the underlying genetic defect.11" Ten titled rows; PubMed dates 2022 to 2025, all inside the window. Rubric line 2 passes on the CFTR modulator sentence; rubric line 1 is the count line only.
- Evidence: `testing/Developer/reports/2026-10-30_product_check_119/cf_5y_1280_full.png`, `cf_5y_1280_answer.txt`.
- Why a person would care: the first build gave them a list and no words; now they get a sentence about where treatment stands.
- NOT CLOSED

### PR-119-08: Four of the ten "cystic fibrosis" papers are not about cystic fibrosis
- Kind: answer
- Verdict: fail
- Card: shown by this card (the list grew from 5 to 10, so the weaker matches now appear); the search that matches "cystic" and "fibrosis" separately is likely earlier
- What: rows 2, 3, 4 and 8 are "Targeting fibrosis, mechanisms and cilinical trials." (35773269), "Diagnosis and management of choledochal cysts." (36257874), "Epidemiology of small intestinal bacterial overgrowth." (37389240) and "Autosomal Recessive Polycystic Kidney Disease: Diagnosis, Prognosis, and Management." (38097335). The count line counts them as cystic fibrosis papers: "Found 10 papers for cystic fibrosis." Seen in one run at 1280; see the 390 run below.
- Evidence: `testing/Developer/reports/2026-10-30_product_check_119/cf_5y_1280_answer.txt`, `cf_5y_1280_full.png`.
- Why a person would care: "I asked about cystic fibrosis and got papers on choledochal cysts and kidney disease, labelled as cystic fibrosis papers." A confident wrong record is worse than a missing one.
- NOT CLOSED

### PR-119-09: The cystic fibrosis summary cites marker 11 while the answer says 10 sources were cited
- Kind: answer
- Verdict: needs your eye
- Card: same pattern as PR-119-03
- What: both summary sentences end in marker 11; the meta line reads "10 sources cited from 1 layer", Sources shows 10, and the line under the answer reads "Based on 10 sources cited, all from PubMed". I did not open marker 11, so I cannot say which paper it is.
- Evidence: `testing/Developer/reports/2026-10-30_product_check_119/cf_5y_1280_answer.txt`.
- Why a person would care: the one sentence they would check cites a source the count says does not exist, and they cannot tell which of the ten papers it came from.
- NOT CLOSED

### PR-119-10: The 390 cystic fibrosis answer prints a bare line of five "Publication PMID" numbers in the summary
- Kind: answer
- Verdict: fail
- Card: likely earlier (graph publication records written as text), shown in this card's windowed summary; needs the owner's eye on which
- What: a second, separate run at 390, Researcher, last 5 years. After two good summary sentences the answer prints: "Publication PMID 35015036, Publication PMID 35551858, Publication PMID 35773269, Publication PMID 36257874, and Publication PMID 37389240.12-16" Markers 12 to 16 render in the other layer's colour and exceed the "10 sources cited" in the meta line. The same five papers already appear, with titles, as rows 1 to 5 of the table. The 1280 run of the same question did not print this line.
- Evidence: `testing/Developer/reports/2026-10-30_product_check_119/cf_5y_390_full.png`, `cf_5y_390_answer.txt`.
- Why a person would care: a sentence of raw ID numbers in the middle of the answer looks broken, and two of those five numbers are the off-topic papers (fibrosis in general, choledochal cysts).
- NOT CLOSED

### PR-119-11: The 390 cystic fibrosis run lists the same off-topic papers, and its summary is good
- Kind: answer
- Verdict: needs your eye
- Card: 119 (summary) and as PR-119-08 (off-topic rows)
- What: the summary reads "Cystic fibrosis is described as a genetic and multisystemic disease whose main adult comorbidity is respiratory involvement with bronchiectasis, chronic bronchial infection, and airflow obstruction.11" then the CFTR modulator sentence, under "Disease overview and CFTR modulators". Ten titled rows, PubMed dates 2022 to 2025, all inside the window. Rows 3, 4 and 5 are again "Targeting fibrosis...", "choledochal cysts" and "small intestinal bacterial overgrowth"; row 2 is about non-cystic fibrosis bronchiectasis and COPD. The meta line says "10 sources cited from 2 layers" while the line under the answer says "Based on 10 sources cited, all from PubMed". Overflow 0 px.
- Evidence: `testing/Developer/reports/2026-10-30_product_check_119/cf_5y_390_full.png`, `cf_5y_390_answer.txt`, `cf_5y_390_log.json`.
- Why a person would care: the written part now explains the disease well; the list under it still mixes in papers about other conditions.
- NOT CLOSED

### PR-119-12: The 5-year statins answer in Plain language lists 10 titled papers inside the window, with a plain summary from one review
- Kind: answer
- Verdict: pass
- Card: 119
- What: at 1280, Plain language (pressed, per the log), after picking the last 5 years: "I found 10 published papers on this topic.1-10" then "A review of statin intolerance found that muscle pain is the most common adverse effect and the most common reason people stop taking statins, ...11". "Where this answer comes from" lists 10 titles. PubMed dates run from 2021 Nov 1 (34279010) to 2024 Jun 25 (38934304), all inside the last five years counted from 2026-10-30. The papers are about statins, apart from "Sterols in asthma." (36041950), which is a stretch. Rubric line 2 passes on the muscle pain sentence. The summary draws on one of the ten papers, and marker 11 again exceeds the "10 sources cited" (as PR-119-03). The count line does not say "for statins" or name the window.
- Evidence: `testing/Developer/reports/2026-10-30_product_check_119/statins_5y_plain_1280_full.png`, `statins_5y_plain_1280_answer.txt`, `statins_5y_plain_1280_log.json`.
- Why a person would care: a student gets ten recent statin papers by title and one practical sentence about why people stop taking statins.
- NOT CLOSED

### PR-119-13: The statins answer suggests "What variants cause it?" as a follow-up
- Kind: answer
- Verdict: needs your eye
- Card: earlier (the same three suggestions appear on every answer in this check)
- What: under "Continue this conversation" the chips read "What variants cause it?", "Which trials are recruiting?", "What does the literature add?". Statins are a drug class; variants do not cause them. The same three chips appear on the BRCA1 and cystic fibrosis answers.
- Evidence: `testing/Developer/reports/2026-10-30_product_check_119/statins_5y_plain_1280_full.png`, `statins_5y_plain_1280_answer.txt`.
- Why a person would care: a suggestion that makes no sense for their question makes the tool look like it did not understand them.
- NOT CLOSED

### PR-119-14: The 390 statins run took 20.2 s by the app's own figure, and its two summary sentences each name a different review
- Kind: answer
- Verdict: needs your eye
- Card: 119 (the summary now reads abstracts; the 1280 run of the same question took 7.8 s)
- What: same ten papers, same dates, all inside the window, overflow 0 px. The meta line reads "Answered 20.2s · 3 tool calls · 10 sources cited from 1 layer", just over the owner's 20 s target; the script measured 20.7 s from the click. The summary reads "A review notes that statins raise the risk of type 2 diabetes while still being effective at preventing heart disease events.11" and "A review reports that muscle pain is the most common reason people stop taking statins, ...12". Markers 11 and 12 exceed the 10 sources cited (as PR-119-03). The opening line "I found 10 published papers on this topic." wraps after "on" at 390, leaving the right part of the column empty.
- Evidence: `testing/Developer/reports/2026-10-30_product_check_119/statins_5y_plain_390_full.png`, `statins_5y_plain_390_answer.txt`, `statins_5y_plain_390_log.json`.
- Why a person would care: on a phone they waited twenty seconds for the same list that came back in eight on a laptop; the content itself reads well.
- NOT CLOSED

### PR-119-15: The honest "No PubMed papers from the last 12 months" line still shows for C9orf43
- Kind: answer
- Verdict: pass
- Card: 119 (unchanged behaviour kept) and card 105
- What: at 1280, Researcher, after picking "Recent papers on C9orf43 from the last 12 months?", the Notes section reads "No PubMed papers from the last 12 months were found for C9orf43. Papers in the knowledge graph carry no publication date, so they are not listed here." That matches the card 105 retest row word for word. PubMed's own search for C9orf43 with a 365-day publication window returns 0, and 1 paper in all, so the line is true. No paper is listed.
- Evidence: `testing/Developer/reports/2026-10-30_product_check_119/c9orf43_12m_1280_full.png`, `c9orf43_12m_1280_answer.txt`.
- Why a person would care: they are told plainly that nothing recent exists, rather than shown an old paper as if it were new.
- NOT CLOSED

### PR-119-16: The C9orf43 answer leads with a list of variant names, and the "no papers" line sits at the bottom under Notes
- Kind: answer
- Verdict: needs your eye
- Card: earlier (the answer shape is the same as card 105's check described); not changed by card 119
- What: the first sentence is "Found 1 gene record and 5 clinvar records for C9orf43: C9orf43, NM_001278629.2(C9orf43):c.293C>T (p.Pro98Leu), ..." followed by an "Answer" section that reads in full "The gene symbol is C9orf43, and the gene name is C9orf43.1, 3". The one line that answers the question, that no recent papers exist, is the last item on the page, under "Notes". Rubric line 1 fails: the answer lists what was found instead of answering. Rubric line 2 fails on "The gene symbol is C9orf43, and the gene name is C9orf43." Markers run to 7 while the meta line says 6 sources.
- Evidence: `testing/Developer/reports/2026-10-30_product_check_119/c9orf43_12m_1280_full.png`, `c9orf43_12m_1280_answer.txt`.
- Why a person would care: "I asked for recent papers and the first thing I read is five variant codes; I have to scroll to the bottom to learn there are none."
- NOT CLOSED

### PR-119-17: At 390 the C9orf43 line still shows, the page fits, and the answer is marked "? Answered" with no summary
- Kind: answer
- Verdict: pass for the card 119 check; the rest needs your eye
- Card: 119 (the line) and earlier (the rest)
- What: a separate run at 390. Notes read "No PubMed papers from the last 12 months were found for C9orf43. Papers in the knowledge graph carry no publication date, so they are not listed here." and "Note: no written summary could be checked against the records, so this answer lists the records found with their sources". The meta line shows "? Answered 12.3s" where the 1280 run showed "✓ Answered 19.9s" and an "Answer" section. The same opening variant list as PR-119-16. Overflow 0 px.
- Evidence: `testing/Developer/reports/2026-10-30_product_check_119/c9orf43_12m_390_full.png`, `c9orf43_12m_390_answer.txt`, `c9orf43_12m_390_log.json`.
- Why a person would care: the honest line is there on a phone; two asks of the same question give two different answer states.
- NOT CLOSED

### PR-119-18: The no-window control keeps its shape: four diseases first, five papers, same tables
- Kind: answer
- Verdict: pass
- Card: 119 (a question with no window must be unchanged)
- What: `Which diseases are associated with BRCA1?`, Researcher, 1280. The first sentence is the same as on 2026-10-29: "BRCA1 is associated with four diseases: familial cancer of breast, familial breast-ovarian cancer susceptibility 1, pancreatic cancer susceptibility 4, and Fanconi anemia complementation group S." The tables are in the same order (disease, gene, PubMed, ClinVar, OMIM, clinical trials) with the same rows, apart from one paper: PubMed still lists 5 papers, with 16998500 in place of 33789098. Meta "? Answered 9.9s · 13 tool calls · 21 sources cited from 2 layers" against "? Answered 14.4s · 13 tool calls · 21 sources cited from 2 layers" before. Overflow 0 px.
- Evidence: `testing/Developer/reports/2026-10-30_product_check_119/control_brca1_1280_full.png`, `control_brca1_1280_answer.txt`; compare `testing/Developer/reports/2026-10-29_product_check_121_123/q5_researcher_answer.txt`, `q5_researcher_1280_full.png`.
- Why a person would care: someone asking about diseases, not recent papers, sees the answer they saw yesterday.
- NOT CLOSED

### PR-119-19: The control's written summary shrank from four paragraphs to one sentence that opens on "The protein"
- Kind: answer
- Verdict: needs your eye
- Card: unclear. One run each side, so this may be run-to-run variation; card 119 changed how the summary picks papers, and the no-window path should not have moved. Summaries that open mid-thought are card 147.
- What: on 2026-10-29 the summary had a "Gene function and DNA repair" section with four paragraphs, including "BRCA1 encodes a 190 kD nuclear phosphoprotein that acts as a tumor suppressor..." and the 40% and 80% figures. Today the whole summary is "The protein plays a role in transcription, DNA repair of double-stranded breaks, and recombination.23" No section heading, no inheritance figures.
- Evidence: `testing/Developer/reports/2026-10-30_product_check_119/control_brca1_1280_answer.txt`; compare `testing/Developer/reports/2026-10-29_product_check_121_123/q5_researcher_answer.txt`.
- Why a person would care: a clinician who got the 80% inherited-cancer figure yesterday gets one sentence about "the protein" today, with no word of which protein.
- NOT CLOSED

### PR-119-20: At 390 the control's summary carries the inheritance figures again, so PR-119-19 looks like run-to-run variation
- Kind: answer
- Verdict: needs your eye
- Card: earlier (summary variation between runs; "This protein thus" opening mid-thought is card 147)
- What: the separate 390 run of the control reads "Mutations in this gene are responsible for approximately 40% of inherited breast cancers and more than 80% of inherited breast and ovarian cancers.23" and "This protein thus plays a role in transcription, DNA repair of double-stranded breaks, and recombination.23", then the ClinVar sentence, as on 2026-10-29. Four diseases first, 5 PubMed papers. Meta "? Answered 10.3s". Overflow 0 px. I read the text only for this run, not its screenshot.
- Evidence: `testing/Developer/reports/2026-10-30_product_check_119/control_brca1_390_answer.txt`, `control_brca1_390_log.json`.
- Why a person would care: the same question gives a fuller or a thinner summary depending on the run.
- NOT CLOSED

## Summary

Verdict on card 119's own promise: met in every run. Each windowed answer listed up to 10 papers (9, 9, 10, 10, 10, 10), each with a title, every one dated inside the window by PubMed's own record, and the count line matched the rows. Cystic fibrosis now has a written summary about the disease. The C9orf43 "No PubMed papers from the last 12 months" line still shows. The no-window control keeps its shape and its 5 papers.

Overall: fail, on two answer findings the longer lists bring into view: four off-topic papers counted as cystic fibrosis papers (PR-119-08), and a bare line of "Publication PMID" numbers in one cystic fibrosis summary (PR-119-10). The card still waits for the owner's verdict, as every answer-path card does.

### Answer times

From the click on the window (or on Search, for the control) to the finished answer, measured by the script; the app's own figure in brackets.

| Run | 1280 | 390 |
|---|---|---|
| BRCA1, last 5 years, Researcher | 16.7 s (16.4) | 17.7 s (17.2) |
| Cystic fibrosis, last 5 years, Researcher | 13.1 s (12.5) | 13.2 s (13.0) |
| Statins, last 5 years, Plain language | 8.1 s (7.8) | 20.7 s (20.2) |
| C9orf43, last 12 months, Researcher | 20.2 s (19.9) | 12.7 s (12.3) |
| Control, BRCA1 diseases, Researcher | 10.6 s (9.9) | 11.1 s (10.3) |

- Median 13.2 s, p90 20.2 s, worst 20.7 s (statins at 390). None over 25 s. Two over the owner's 20 s target by the script's clock: statins at 390 and C9orf43 at 1280.
- The "How far back" ask-back appeared in 1.5 to 3.6 s every time.

### What to look at first

1. PR-119-08, fail: four of ten "cystic fibrosis" papers are about other conditions.
2. PR-119-10, fail: "Publication PMID 35015036, Publication PMID ..." printed as a sentence in the 390 cystic fibrosis summary.
3. PR-119-03, with PR-119-09, PR-119-12 and PR-119-14: summary markers run past the stated source count in every windowed summary (24 to 26 of 22; 11 of 10; 11 and 12 of 10).
4. PR-119-06 and PR-119-04: the BRCA1 summary drew on no paper in one run and on one study's detail in the other.
5. PR-119-16 and PR-119-17: C9orf43 leads with variant codes; the honest line is last, and the two runs differ in answer state.
6. PR-119-14: statins at 390 took 20.2 s by the app's own figure.
7. PR-119-19 and PR-119-20: the control's summary varies between runs.
8. PR-119-13: "What variants cause it?" offered under a statins answer.
9. PR-119-02, known (card 124): the 1993 GeneReviews chapter still listed in the 5-year BRCA1 answer.

### Overflow at 390 and missing design

- Horizontal overflow at 390: 0 px on all five 390 runs (`*_390_log.json`, `sw_minus_cw`).
- No surface without a design was touched: the answer screen is "Home, answer, streaming", designed (`docs/build/design/README.md`, coverage table). The "How far back" ask-back has no design card of its own; it was not changed by this card.
- Every full-page screenshot shows the fixed app bar or footer band once in the middle of the page. That is how a full-page capture draws a fixed bar, seen in the 2026-10-29 captures too, not a layout defect.

### What I read myself, and what I did not capture

- Read myself, screenshot and text: BRCA1 at 1280 and 390, cystic fibrosis at 1280 and 390, statins at 1280 and 390, C9orf43 at 1280 and 390, the control at 1280, and the 2026-10-29 control screenshot. Read as text only: the control at 390 (`control_brca1_390_answer.txt`). Paper years rest on PubMed esummary lookups I ran, not on the app.
- Not opened: citation markers beyond the source count (24 to 26, 11, 12 to 16) and the Sources disclosure, so whether those markers resolve is unknown. My script's click meant for the Sources disclosure opened the first citation popover instead; the `*_sources_open*` files show that popover, not the Sources list.
- Not compared against `docs/build/design/design-system/prototype/app.html`: the card changes answer content, not a screen, and the prototype has no windowed paper list.
- Each question was asked once per width, so two runs per question; nothing here is a repeated-run measure. No golden run, by the brief. No follow-ups, so cards 150 and 151 were not exercised.
