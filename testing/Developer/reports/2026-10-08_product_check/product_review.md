# Cards 101, 54 and 71 product review (pre-screen, develop)

Reviewer: product reviewer agent, 2026-10-08 (session date 2026-10-07 local). Pre-screen only; nothing here closes an item or moves a card.

## Table of contents

- [Target](#target)
- [Findings](#findings)
- [Per query](#per-query)
- [Report](#report)

## Target

- API `/health` before the first capture: `{"status":"ok","app_env":"develop"}`.
- Brief: web and API on 7309b55f (PR #204), Railway SUCCESS on both. Signed in with one throwaway develop account; its credentials are not written anywhere in this folder.

## Findings

Findings are appended here the moment each is established.

### PR-01: on a phone, tapping a past search leaves the searches panel open over the reopened answer
- Kind: screen
- Verdict: needs your eye
- What: at 390, "Show or hide your searches" opens the panel (left 1, right 249 px). Tapping "What diseases are caused by variants in the HNF1A gene?" loads the saved answer behind it, and 4 seconds later the panel is still open at the same position, with the answer greyed out behind it. The person has to close the panel themselves to read what they asked for.
- Evidence: `product_390_drawer_open.png`, `product_390_after_tap_viewport.png`; script output "open {left:1,right:249}" and "after tap {left:1,right:249}"; the same panel covers the stacked table in `product_390_hnf1a_researcher_saved-answer-table-4.png`.
- Why a person would care: on a phone they tap their old question and still see the list, not the answer, so it looks as if nothing happened. Not one of tonight's three cards; I have no before reading, so not a regression claim. The phone rail has no design (`docs/build/design/README.md` lists it as NO).
- NOT CLOSED

### PR-02: the BRCA1 answer lists the same gene record twice in its tables, so its record list reads 22 against 21 sources
- Kind: answer
- Verdict: needs your eye
- What: "Which diseases are associated with BRCA1?" at Researcher shows under "Gene records found" two rows, "BRCA1 NCBIGene:672 [6]" and "BRCA1 NCBIGene:672 [10]". At Plain language the "Where this answer comes from" list holds "BRCA1 [6]" and "BRCA1 [10]" and its bar reads "Showing 1–10 of 22", while the meta line, the SOURCES heading and the trust line all say 21. The SOURCES cards and the saved rows do merge the page correctly ("5, 6, 10. gene ... /gene/672"), so the three source numbers agree; only the record tables repeat it.
- Evidence: `brca1_researcher_live_1280.txt`, `brca1_plain_live_390.txt`; `product_measurements.json` entries `brca1_researcher` (`sourceCards: 21`) and `brca1_plain` (`tables: answer-records-0-status: Showing 1–10 of 22`); screenshots `product_1280_brca1_researcher_live.png`, `product_390_brca1_plain_live.png`.
- Why a person would care: query 107 says the gene page is one source. A reader sees BRCA1's gene record twice in a row and a list of 22 under a line saying 21 sources. Not from tonight's cards; no before reading for the table, so not a regression claim.
- NOT CLOSED

### PR-03: one plain-language GERD answer of three names no symptom and no risk factor
- Kind: answer
- Verdict: needs your eye
- What: "What are the typical symptoms and risk factors of GERD?" in Plain language, third run (390). Its prose is three sentences: what GERD is, that reflux in children is common, and that proton-pump inhibitors work but carry long-term risks. No sentence names a symptom or a risk factor, though its own source 1 (PMID 29132520) says "The typical symptoms of GERD are heartburn and regurgitation of gastric contents into the oropharynx." Runs 1 and 2 at 1280 both open "The typical symptoms of GERD are heartburn and regurgitation ...". All three have the same 12 sources. Rubric line 1 fails on run 3: the first prose sentence is "GERD happens when stomach contents flow back up into the esophagus or mouth, causing symptoms or complications [1]."
- Evidence: `gerd_plain_3_live_390.txt`, `gerd_plain_3_saved.txt`, `product_390_gerd_plain_3_live.png`; compare `gerd_plain_1_live_1280.txt`, `gerd_plain_2_live_1280.txt`. Abstract read from PubMed E-utilities for PMID 29132520.
- Why a person would care: they asked for symptoms and risk factors and got a definition and a drug warning. I cannot tell from the screen whether the sentence check held the symptom sentence back (card 101's whole-sentence rule would make that likelier) or the writer never wrote it; the answer gives no sign either way.
- NOT CLOSED

### PR-04: a plain-language GERD sentence turns the paper's "is associated with" into "carries risks"
- Kind: answer
- Verdict: needs your eye
- What: run 3 says "The most effective treatment is a class of drugs called proton-pump inhibitors, but using them for a long time carries risks including bone fractures, kidney disease, pneumonia, and intestinal infection [1]." Source 1 (PMID 29132520) says "Long-term use of PPIs is associated with bone fractures, chronic renal disease, acute renal disease, community-acquired pneumonia, and Clostridium difficile intestinal infection." An association becomes a stated risk. The sentence also answers a question nobody asked (treatment), in a question about symptoms and risk factors.
- Evidence: `gerd_plain_3_live_390.txt`; abstract of PMID 29132520 from PubMed E-utilities.
- Why a person would care: query 106's promise is that a plain-language answer never claims more than its paper. A reader on a long-term PPI reads that it causes kidney disease, where the paper reports only that the two go together.
- NOT CLOSED

### PR-05: four of five plain-language GERD answers name no risk factor, and one fills the gap with a sentence about the search
- Kind: answer
- Verdict: needs your eye
- What: five runs of "What are the typical symptoms and risk factors of GERD?" in Plain language, same 12 sources each time. Only run 1 names risk factors ("Factors that can contribute to GERD include problems with the esophageal lining's defenses, impaired movement and clearing of the esophagus and stomach, and anatomical defects such as hiatal hernia [2]"). Runs 2, 3, 4 and 5 name none. Run 5 ends its prose with "The search also returned a MedGen record titled Gastroesophageal reflux (GERD) and a literature entity named Gastroesophageal Reflux [2, 3]." The same question at Researcher has a "Risk factors and pathogenesis" heading and keeps the paper's limiting word: "Factors contributing to GERD pathogenesis include abnormal transient relaxations of the lower esophageal sphincter, ...".
- Evidence: `gerd_plain_1_live_1280.txt` to `gerd_plain_5_live_390.txt`, `gerd_researcher_live_1280.txt`; source 2 is PMID 37034973 (abstract read from PubMed E-utilities), which states the factors.
- Why a person would care: half the question goes unanswered most of the time, and which half you get changes from run to run. Rubric line 2 fails on run 5: a sentence about what the search returned teaches nothing. Query 106's bar (about two to three sentences, nothing wider than the paper) is met on runs 1, 2, 4 and 5; the hold-back that keeps claims narrow may also be what removes the risk-factor sentence, which I cannot see from the screen.
- NOT CLOSED

### PR-06: the bronchiolitis answer never says what causes bronchiolitis
- Kind: answer
- Verdict: needs your eye
- What: "What causes bronchiolitis in babies, and how is it usually treated?" in Plain language answers treatment faithfully and says nothing on cause. Prose: "Bronchiolitis is the most common lower respiratory tract infection to affect infants and toddlers [1]." "In healthy infants and children, bronchiolitis goes away on its own [1]. Treatment is usually aimed at relieving symptoms, and the main goal is to keep the child properly oxygenated and hydrated [1]." Each sentence matches PMID 24093893 ("self-limited disease in healthy infants and children", "Treatment is usually symptomatic, and the goal of therapy is to maintain adequate oxygenation and hydration"), and it never says babies where the paper says children, so query 106 passes. But "Respiratory syncytial virus bronchiolitis" and "Adenoviral bronchiolitis" sit in its own record list and the prose never says a virus causes it.
- Evidence: `bronch_plain_live_1280.txt`, `bronch_plain_saved.txt`, `product_1280_bronch_plain_live.png`; abstract of PMID 24093893 from PubMed E-utilities.
- Why a person would care: a parent asked what causes it first. Rubric line 1: the first prose sentence answers neither part of the question.
- NOT CLOSED

### PR-07: the E. coli answer's prose is a list of isolate names and never says which ESBL gene they carry
- Kind: answer
- Verdict: needs your eye
- What: the prose is "I found 20 pathogen samples and 1 organism related to Escherichia coli." then "The isolates are C236-11, 11-3677, ... and NA114." The gene (blaCTX-M-15, in every row shown) appears only in the table, and the scope ("141,088 Escherichia coli isolates with these genes; the first 20 in the snapshot are shown") only in Notes.
- Evidence: `ecoli_plain_live_1280.txt`, `product_1280_ecoli_plain_live.png`.
- Why a person would care: rubric line 1 fails: the first sentence lists what was found instead of answering. Not tonight's change.
- NOT CLOSED

### PR-08: the reopened answer, its stacked phone tables and the phone searches panel have no design
- Kind: missing design
- Verdict: needs your eye
- What: `docs/build/design/README.md` has no row for a saved answer and lists "History rail and its collapsed strip" as NO. Card 71's paging and phone stacking were judged against the live answer and query 67, not a design.
- Evidence: `product_1280_ecoli_plain_saved_saved-answer-table-3.png`, `product_390_ecoli_plain_saved_saved-answer-table-3.png`, `product_390_after_tap_viewport.png`.
- Why a person would care: no one has said what the reopened answer should look like on a phone.
- NOT CLOSED

### PR-09: from the click, eight of eleven answers took over 20 seconds on screen, three over 30
- Kind: answer
- Verdict: needs your eye
- What: eleven questions. On the meta line: median 15.6 s, worst 23.9 s (HNF1A Researcher), none over 25 s. From the click to the trust line: median 23.1 s, worst 35.8 s (BRCA1 Researcher). Over 25 s from the click: HNF1A Researcher 32.5, BRCA1 Researcher 35.8, BRCA1 Plain 31.5, GERD Plain run 1 25.3, GERD Plain run 5 26.2.
- Evidence: `product_measurements.json`, `meta` and `clickToTrustSecs` of each `live_1280` and `live_390` entry; table under "Per query".
- Why a person would care: the owner's bar is 20 seconds per answer. Yesterday's card 102 review read 31.5 to 36.0 s from the click on the same HNF1A and BRCA1 questions, so this is no worse than before tonight, not better.
- NOT CLOSED

## Per query

| Query | 1280 | 390 | Rests on |
|---|---|---|---|
| 106 GERD Plain, 5 runs (cards 99, 101) | Pass on its stated bar, with PR-03 to PR-05 | Pass on its stated bar, with PR-03 to PR-05 | No fragment, no bare name, no cut sentence in any run (scan of every `*_live_*.txt`); every run has two to four prose sentences; run 4 keeps "is associated with", run 3 does not (PR-04) |
| 106 bronchiolitis Plain | Pass | Not asked at 390; overflow measured 0 after resize | "In healthy infants and children, bronchiolitis goes away on its own [1]." matches PMID 24093893; never "babies" |
| 106 GERD Researcher (other depth) | Pass | Not asked | "Factors contributing to GERD pathogenesis include abnormal transient relaxations ..." keeps "transient" |
| 107 BRCA1 Researcher and Plain (card 22) | Pass, with PR-02 | Pass, with PR-02 | Meta "21 sources cited from 2 layers", SOURCES 21, 21 cards, "Based on 21 sources cited, not yet confirmed", rail "21 sources cited", saved 21 rows with "5, 6, 10. gene ... /gene/672" |
| 107 add-on: HNF1A Researcher reopened (card 54) | Pass | Pass | Live "61 sources cited from 3 layers", SOURCES 61; rail "61 sources cited · Oct 7"; saved trust "Based on 61 sources cited, not yet confirmed" over 61 rows numbered 1 to 62 ("45, 49." one row); every marker in the saved text is a listed row |
| 67 E. coli isolates reopened (card 71) | Pass | Pass, with PR-01 | Saved table "Showing 1–10 of 20", Next gives "Showing 11–20 of 20" with 10 rows; at 390 the table is a list, each row led by the isolate with "Identifier:", "AMR genes:", "Collected:" labels, table right edge 355 on a 390 screen, page overflow 0 |

Time to answer:

| Question | Width asked | Meta line (s) | Click to trust line (s) |
|---|---|---|---|
| HNF1A Researcher | 1280 | 23.9 | 32.5 |
| BRCA1 Researcher | 1280 | 17.7 | 35.8 |
| BRCA1 Plain | 390 | 14.7 | 31.5 |
| E. coli isolates Plain | 1280 | 17.2 | 19.2 |
| GERD Plain run 1 | 1280 | 16.5 | 25.3 |
| GERD Plain run 2 | 1280 | 13.0 | 22.3 |
| GERD Plain run 3 | 390 | 12.2 | 22.1 |
| GERD Plain run 4 | 390 | 10.5 | 20.2 |
| GERD Plain run 5 | 390 | 15.6 | 26.2 |
| Bronchiolitis Plain | 1280 | 16.0 | 23.1 |
| GERD Researcher | 1280 | 12.5 | 20.2 |

## Report

1. Golden result: not run. The brief named no accounts file and no floor, and asked for the owner's test queries instead. Card 101 changes which sentences show, an answer-path change, so the golden run is owed and was not measured here: answered against the floor, answered well of the fixed ten, questions that got worse, all unmeasured. Time to answer for my eleven questions: meta line median 15.6 s, worst 23.9 s, none over 25 s; click to trust line median 23.1 s, p90 31.5 s, worst 35.8 s (PR-09).
2. Look at first. No fail. Needs your eye, ranked by what a person feels: PR-03 (a GERD answer with no symptom), PR-04 ("associated with" became "carries risks"), PR-05 (risk factors missing in four of five GERD runs), PR-06 (bronchiolitis cause never stated), PR-01 (phone searches panel stays open over the reopened answer), PR-02 (BRCA1 gene record listed twice, 22 rows against 21 sources), PR-09 (time), PR-07 (E. coli prose lists names), PR-08 (no design).
3. Overflow at 390: 0 on every screen measured (every live answer after resize or asked at 390, every saved answer at 390); no element wider than the screen. No design: saved answer screen, its phone tables, the history rail and its phone panel (PR-08). Prototype screenshots were not taken because none of these surfaces exists in it.
4. Not captured: the golden run (above); bronchiolitis and GERD Researcher at 390 as live asks (resized to 390 instead, overflow 0); a saved answer from before tonight with more than 50 sources, to see the stated 50 cap still applies; whether PR-03's missing sentence was held back by the sentence check or never written (the screen does not say); the live answer's own table stacking beyond the overflow number. Full-page and element screenshots draw the sticky header and footer over the page part way down; that is the capture method, not a defect. Eleven questions asked on the one throwaway develop account.

What I read myself: the answer text files for all eleven questions and the four saved answers; the PubMed abstracts of PMIDs 29132520, 37034973 and 24093893; the screenshots `product_390_hnf1a_researcher_saved-answer-table-4.png`, `product_390_after_tap_viewport.png`, `product_1280_hnf1a_researcher_saved_saved-answer-table-4.png`, `product_390_hnf1a_researcher_saved_saved-answer-table-4_bar.png`, `product_390_ecoli_plain_saved_saved-answer-table-3.png`, `product_1280_ecoli_plain_saved_saved-answer-table-3.png`. Counts, overflow, paging status and timings rest on `product_measurements.json`, which the scripts wrote from the DOM; the full-page screenshots of the long answers I did not read at full size.

Note from the lead, 2026-10-08: the screenshots this report names as evidence are not committed. The leak scan cannot read an image, and signed-in screens show the throwaway account in the top bar, so they stay off the public repository. The golden run was left out at the owner's choice ("Test queries only").
