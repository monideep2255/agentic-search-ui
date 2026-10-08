# Cards 103 and 104 product review (pre-screen, develop)

Reviewer: product reviewer agent, 2026-10-08 (session date 2026-10-07 local). Pre-screen only; nothing here closes an item or moves a card.

## Table of contents

- [Target](#target)
- [Findings](#findings)
- [Per query](#per-query)
- [Report](#report)

## Target

- API `/health` before the first capture: `{"status":"ok","app_env":"develop"}`.
- origin/develop head: 17b2a721 (PR #206, docs only), parent adad3dd5 (PR #205, cards 103 and 104). Whether the API runs the change is read from its behaviour below.
- Signed in with one throwaway develop account; its credentials are not written anywhere in this folder. Screenshots stay outside the repository.
- Before reading: the product check of the same night, `../2026-10-08_product_check/` (`brca1_researcher_live_1280.txt`, `brca1_plain_live_390.txt`, `hnf1a_researcher_live_1280.txt`), captured on 7309b55f before PR #205.

## Findings

Findings are appended here the moment each is established.

### PR-01: the BRCA1 Researcher answer gains a sentence that says nothing, cited to the merged gene row's two numbers
- Kind: answer
- Verdict: needs your eye
- What: "Which diseases are associated with BRCA1?" at Researcher, 1280, now carries the prose sentence "BRCA1, identified by the gene symbol BRCA1 and gene name BRCA1.[6, 7]" between the summary and the tables. Its citation numbers [6, 7] are exactly the merged gene row's ("BRCA1 NCBIGene:672 [6, 7]"). The before capture of the same question (7309b55f) has no such sentence; its gene table held two rows, [6] and [10]. One run, so I cannot say whether the merge put the gene row's own sentence into the prose or the writer produced it by chance.
- Evidence: `brca1_researcher_1280.txt`; before: `../2026-10-08_product_check/brca1_researcher_live_1280.txt`; screenshot `brca1_researcher_1280.png` (kept outside the repository).
- Why a person would care: a researcher reads a sentence that tells them BRCA1 is called BRCA1. It teaches nothing and looks like a machine talking to itself (rubric line 2). fix.md says a merged row's text now carries both grounded sentences; if that text reaches the prose, every merged record may add one of these.
- NOT CLOSED

### PR-02: one Plain language BRCA1 answer never names a disease in its prose
- Kind: answer
- Verdict: needs your eye
- What: at 390 the Plain language answer opens "I found 4 conditions related to BRCA1.[2–5]" and its only other sentences are about what the gene does ("The gene encodes a protein that helps keep genetic material stable and acts as a tumor suppressor ..."). No prose sentence names one of the four diseases; they appear only in the "Where this answer comes from" list. The 1280 run of the same question a minute earlier names all four: "The diseases associated with BRCA1 are familial cancer of breast, familial breast-ovarian cancer susceptibility 1, pancreatic cancer susceptibility 4, and Fanconi anemia complementation group S.[1–4]"
- Evidence: `brca1_plain_390.txt` against `brca1_plain_1280.txt`.
- Why a person would care: they asked which diseases, and the words they read count the diseases without saying them (rubric line 1, "lists what was found instead of answering"). Run-to-run variation in the writer, not visibly from cards 103 or 104; no before reading at this width, so not a regression claim.
- NOT CLOSED

### PR-03: the Notes count of 39 placeholder links cannot be matched to the 30 rows that say so
- Kind: answer
- Verdict: needs your eye
- What: the HNF1A Researcher answer's variant table has 38 rows over 4 pages; 30 say "None named: ..." and every cell has text. Counting the placeholders those 30 cells quote gives 33 ("not provided and not specified" counted as two). The Notes line says "39 variant links to ClinVar placeholder conditions ('not provided', 'not specified' or 'see cases') are not listed as diseases." The other 6 are presumably placeholders linked beside a real name on the 8 named rows, which those cells do not mention. No cell says "see cases" or "gives only a placeholder", though the Notes names "see cases". Nothing contradicts; the reader just cannot reconcile 39 with what they see.
- Evidence: `hnf1a_researcher_1280.txt` (Notes, page 1), `hnf1a_researcher_1280_later_pages.txt` (pages 2 to 4). Before (7309b55f): the same 39, ending "are not listed." (`../2026-10-08_product_check/hnf1a_researcher_live_1280.txt`).
- Why a person would care: someone checking the table against the note counts 30 placeholder rows and finds 39 claimed. Minor; the wording change itself reads correctly.
- NOT CLOSED

### PR-04: the HNF1A Notes say the records are "listed below" while they sit above, and say no summary could be checked
- Kind: answer
- Verdict: needs your eye
- What: the Notes, at the end of the answer under every table, read "Note: no written summary could be checked against the records, so the records found are listed below with their sources". The records are above that line. The answer has no prose beyond the opening "Found 38 ..." line. Same text before the change, so not a regression.
- Evidence: `hnf1a_researcher_1280.txt`, `hnf1a_researcher_390.txt`; before: `../2026-10-08_product_check/hnf1a_researcher_live_1280.txt`.
- Why a person would care: a researcher asking which diseases HNF1A variants cause gets a table and no sentence of explanation, and a note pointing the wrong way.
- NOT CLOSED

### PR-05: a BRCA1 Researcher answer prints two verbless fragments as sentences
- Kind: answer
- Verdict: needs your eye
- What: at 390 the Researcher answer's third paragraph reads "The familial cancer of breast and familial breast-ovarian cancer susceptibility 1.[1, 2] Pancreatic cancer susceptibility 4 and Fanconi anemia complementation group S.[3, 4]" Neither has a verb, and both repeat the line above. These cite disease rows that were not merged, so this one is not the merge; it makes PR-01 look more like the writer than the merge, which I still cannot separate from the screen.
- Evidence: `brca1_researcher_390.txt`.
- Why a person would care: a researcher reads broken sentences in a cited answer and trusts the rest less.
- NOT CLOSED

### PR-06: every answer took 32 to 35 seconds from the click to the trust line, while the answer says 13 to 25
- Kind: answer
- Verdict: needs your eye
- What: measured from the click on Search to the trust line with "Answered" in the meta line: 33.3, 32.2, 34.2, 35.3, 33.4, 35.2 and 32.4 seconds over seven runs. The meta lines read 15.8, 25.1, 21.3, 17.7, 13.6, 15.2 and 12.7 seconds. The before capture showed the same gap (32.5 against 23.9), so not a regression. One run's own figure, Plain language BRCA1 at 1280, is over 25 seconds (25.1).
- Evidence: `measurements.jsonl` (`clickToTrustSecs`, `meta`).
- Why a person would care: the owner's bar is every answer within 20 seconds. A person waits over half a minute while the answer reports less, and none of tonight's seven met 20 by the clock.
- NOT CLOSED

## Per query

All seven questions asked once each on develop, answer text in this folder, overflow measured at the page (`scrollWidth` minus `clientWidth`).

| Run | Width | Meta line time | Click to trust line | Sources heading, trust line, cards | Record list | Overflow |
|---|---|---|---|---|---|---|
| Query 107, BRCA1, Researcher | 1280 | 15.8 s | 33.3 s | 21, 21, 21 | gene table one row, "BRCA1 NCBIGene:672 [6, 7]" | 0 |
| Query 107, BRCA1, Researcher | 390 | 15.2 s | 35.2 s | 21, 21, 21 | "BRCA1 [5, 9] NCBIGene:672", one row | 0 |
| Query 107, BRCA1, Plain language | 1280 | 25.1 s | 32.2 s | 21, 21, 21 | "Showing 1–10 of 21", "BRCA1 [6, 10]" once | 0 |
| Query 107, BRCA1, Plain language | 390 | 21.3 s | 34.2 s | 21, 21, 21 | "Showing 1–10 of 21", "BRCA1 [6, 10]" once | 0 |
| Query 107, BRCA1, Plain language, second run | 1280 | 12.7 s | 32.4 s | 21, 21, 21 | all 3 pages read, 21 rows, BRCA1 once | 0 |
| Query 79, HNF1A, Researcher | 1280 | 17.7 s | 35.3 s | 61, 61, 61 | all 4 pages read: 38 rows, 30 "None named: ...", 8 named, no blank cell; gene row "HNF1A NCBIGene:6927 [45, 49]" | 0 |
| Query 79, HNF1A, Researcher | 390 | 13.6 s | 33.4 s | 61, 61, 61 | page 1 identical to 1280 | 0 |

Query 107: pass. Before (7309b55f) the gene table had "BRCA1 NCBIGene:672 [6]" and "BRCA1 NCBIGene:672 [10]" and the Plain language list read 22 against 21 sources. Now: "BRCA1 NCBIGene:672 [6, 7]" and "Showing 1–10 of 21" under "21" sources.

Query 79: pass. Page 1 reads "None named: the ClinVar record says not provided" (four rows) and "None named: the ClinVar record says not specified" (one); page 2 and 3 add "None named: the ClinVar record says not provided and not specified". No row says "Name could not be looked up" or "gives only a placeholder", so those two wordings were not seen live. The line under the table, "Each row lists the conditions the variant's ClinVar record names; ...", sits directly under the pagination at both widths (screenshots read). The Notes line now ends "are not listed as diseases." and does not contradict any cell (count caveat in PR-03).

## Report

- Golden run: not run, not asked for in this brief. The change is on the answer path, so the golden floor still applies before the owner retests.
- Look at first: no fails. Needs your eye: PR-01 (filler sentence beside the merged gene row), PR-05, PR-02, PR-06, PR-03, PR-04.
- Overflow at 390: none (0 on all three 390 runs). Design: the answer screen is in the prototype; I did not capture the prototype beside it.
- Not captured: prototype comparison screenshots; the "Name could not be looked up" and "gives only a placeholder" cells (no live row produced them).
- Read myself: every verdict rests on answer text in this folder; the table position at 1280 and 390 on the HNF1A screenshots I read. Nothing rests only on a summary.
