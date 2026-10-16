# Phase 8.7 follow-ups product check: the summary sooner, one entry per citation

The product reviewer's pre-screen of pull request #229 (merge b2514161, F-8.7-A07 and F-8.7-A04) on deployed develop. It files findings and closes nothing; the owner's retest decides. No golden run was in this brief; at most three questions were allowed.

## Table of contents

- [Which app answered](#which-app-answered)
- [Findings](#findings)
- [Timing](#timing)
- [Result](#result)
- [What was not captured](#what-was-not-captured)

## Which app answered

- API `/health` at 11:19:20 UTC: `{"status":"ok","app_env":"develop"}`.
- Web bundle served at 11:19:20 UTC: `index-Dp5DL01h.js`, and the same bundle in the signed-in page of each run (`brca1_log.json` and `marfan_log.json`, step "bundle").
- One throwaway develop account, its name masked as "account hidden" on every screenshot (log step "signed in, email visible unmasked": false).
- Full-page screenshots show the fixed top bar and history rail painted part way down the page; that is how a full-page capture draws fixed elements, not something a person sees.

## Findings

### PR-87F-01: BRCA1 at 1280, Researcher: each source listed once, the card numbers cover every chip
- Kind: screen
- Verdict: pass
- What: the answer showed 21 source cards (16 under Live NCBI APIs, 5 under Enrichment) with 21 distinct names and no repeated row. The chips in the answer use numbers 1 to 23; every one of the 23 appears on exactly one card. Gene 672 is one card carrying "[5][9][23]", the deduplicated page the Sources list was designed to show. The Sources count, the meta line ("21 sources cited from 2 layers") and the trust line ("Based on 21 sources cited") all read 21. No "also cited" lines. Overflow at 1280: 0.
- Evidence: `brca1_log.json`, step "sources" (fields `rows`, `chipNums`, `count`, `groupCounts`, `trust`); `brca1_1280_3_sources_open.png`, `brca1_1280_4_top_viewport.png`.
- Why a person would care: "Each source is listed once, and every number I see in the text has its card."
- NOT CLOSED

### PR-87F-02: BRCA1's OMIM source card carries no link
- Kind: answer
- Verdict: needs your eye
- What: source [8], "omim 113705" (row "BRCA1 DNA REPAIR-ASSOCIATED PROTEIN; BRCA1"), is the one card of 21 with no link inside it; every other card links to ncbi.nlm.nih.gov, pubmed.ncbi.nlm.nih.gov or clinicaltrials.gov. OMIM is not on the web's list of linkable hosts, so this is likely older than #229, and the card was not opened to read what it says instead. Query 1 says "Clicking a citation or source link opens an ncbi.nlm.nih.gov page for that record".
- Evidence: `brca1_log.json`, step "sources", row `source-8` with `"href": null`; `brca1_1280_3_sources_open.png`.
- Why a person would care: "One of the sources has nothing to click, so I cannot check it."
- NOT CLOSED

### PR-87F-03: Marfan at 390, Plain language: each source listed once, no overflow
- Kind: screen
- Verdict: pass
- What: 12 source cards (6 Live NCBI APIs, 6 Enrichment), 12 distinct names, no repeated row; the Sources count, the meta line ("12 sources cited from 2 layers") and the trust line ("Based on 12 sources cited") all read 12. Every chip number in the answer (1 to 13 and 73 to 83) appears on exactly one card. Horizontal overflow at 390: 0 for the page and 0 for the body, at the first record, at the first summary sentence, and with every Sources group open.
- Evidence: `marfan_log.json`, steps "first record row on screen", "first summary sentence on screen" and "sources" (`overflow` 0, `bodyOverflow` 0); `marfan_390_3_sources_open.png`, `marfan_390_4_top_viewport.png`.
- Why a person would care: "On my phone the sources fit the screen and none is listed twice."
- NOT CLOSED

### PR-87F-04: At 390 the MedGen source card opens with 71 bracketed numbers over seven lines
- Kind: screen
- Verdict: needs your eye
- What: the one MedGen card ("medgen 44287") carries the markers "[2][3][4]...[72]", 71 numbers, one per clinical-feature row across the seven pages of "Clinical features MedGen lists". At 390 they fill about seven lines above the card's name. The page does not overflow, and each number does belong to that one record, so this is the deduplication working as designed; it is a readability question, and it is likely older than #229.
- Evidence: `marfan_log.json`, step "sources", row `source-2` (71 markers); `marfan_390_3_sources_open.png`, the Live NCBI APIs group.
- Why a person would care: "One source card is a wall of numbers before I can see what it is."
- NOT CLOSED

### PR-87F-05: Through the API, a citation re-sent for a summary sentence leads with that sentence's words and changes nothing else
- Kind: answer
- Verdict: pass
- What: the BRCA1 question in Researcher, streamed with `?reads=placement` as the web asks, sent 32 citation events. 22 went out with the records at 4.18 s. At 8.70 s nine of them were sent again with the same id and number: records 1 to 4 (the four MedGen diseases) and the five ClinVar records 7, 12, 15, 18 and 21. In all nine, `claim_text` is the only field that differs, and the summary sentence's words come first, the row's words after. Record 1 went from "Disease name: Familial cancer of breast" to "BRCA1 is associated with Familial cancer of breast Disease name: Familial cancer of breast"; record 7 from "clinvar title: NM_007294.4(BRCA1):c.5243_5277+2788del" to "ClinVar records for BRCA1 include NM_007294.4(BRCA1):c.5243_5277+2788del clinvar title: ...". One citation was new, number 23, gene 672, carrying the gene summary's words. Nothing was re-sent with another number or another record. The web kept one card per record from the same kind of stream (PR-87F-01).
- Evidence: `api_brca1_events.jsonl` (run e82c9770), the `citation` events at t 4.18 to 4.19 and 8.70 to 8.71.
- Why a person would care: "The words under a sentence's citation are the words that sentence was checked against, and a citation never turns into a different record."
- NOT CLOSED

### PR-87F-06: Counting citation ids gives 23; the "sources cited" line says 21
- Kind: answer
- Verdict: needs your eye
- What: the API run has 23 distinct citation ids (numbers 1 to 23); its `done` event reads "Based on 21 sources cited, not yet confirmed". The difference is gene 672, cited under three ids (5, 9 and 23); the line counts pages, not ids, the rule the web's Sources list follows (one card "[5][9][23] gene 672", 21 cards). So the check as the brief states it does not hold, while the line, the Sources count and the meta line agree with each other on both web runs (21 and 12). The owner should say whether "sources cited" is meant to count pages, as it does today.
- Evidence: `api_brca1_events.jsonl`, the `citation` events and the `done` event's `trust_line`; `brca1_log.json`, step "sources".
- Why a person would care: "The answer says 21 sources, the citation numbers go up to 23; the Sources list explains it, since one gene page carries three numbers."
- NOT CLOSED

### PR-87F-07: A re-sent citation's words run straight into the row's words, with no break between them
- Kind: answer
- Verdict: needs your eye
- What: the grown `claim_text` joins the sentence's words and the row's words with a single space and no punctuation, for example "BRCA1 is associated with Familial cancer of breast Disease name: Familial cancer of breast" and "NM_007294.4(BRCA1):c.5277+2916_5277+2946delinsGG clinvar title: NM_007294.4(BRCA1):c.5277+2916_5277+2946delinsGG". The web shows no chip words (the build report says so), so a person meets this in `s3 ask --json`, the MCP, GraphQL and the citations export, not on the web screen.
- Evidence: `api_brca1_events.jsonl`, the nine re-sent `citation` events at t 8.70 to 8.71.
- Why a person would care: "The text under a citation reads as one garbled sentence; I cannot tell where the claim ends and the record begins."
- NOT CLOSED

### PR-87F-08: Query 91's expected text on develop says the opposite order from what develop sends
- Kind: answer
- Verdict: needs your eye
- What: `testing/Test_queries_and_workflows.md` on develop, query 91: "A citation that a summary sentence cites carries, in its `claim_text`, the record's own row words followed by the record words that sentence was checked against." Develop sends the sentence's words first and the row's after (PR-87F-05), which is what the fix round (J-87F-03 in the build report) intended. The owner retesting query 91 against that line would mark a correct answer as wrong.
- Evidence: `testing/Test_queries_and_workflows.md` at b2514161, query 91; `api_brca1_events.jsonl`.
- Why a person would care: "The test I am told to run says the wrong thing should happen."
- NOT CLOSED

### PR-87F-09: The summary was held 0.37 s for its first-sentence pick, and the pick led
- Kind: answer
- Verdict: pass
- What: in the API run the first-sentence decision `write.lead_sentence` was answered by the classifier in 371 ms (chosen "first"); the first summary token arrived at 8.70 s and the run finished at 8.72 s. On the web the first sentence answers the question and the "Found 4 disease records" line follows: "BRCA1 is associated with familial cancer of breast, familial breast-ovarian cancer susceptibility 1, pancreatic cancer susceptibility 4, and Fanconi anemia complementation group S." In Marfan, Plain language, the opening is "MedGen lists these clinical features: Aortic regurgitation, Arachnodactyly, ..." with "I found 5 published papers, ..." after it. The time the writer's draft returned is not on the wire, so this shows the hold was at most 0.37 s on this run; it cannot show the 1 s cut-off firing, which needs a slow pick.
- Evidence: `api_brca1_events.jsonl`, the `done` event's `decisions` (`write.lead_sentence`, `jev_latency_ms` 371); `brca1_log.json` and `marfan_log.json`, step "first summary sentence on screen".
- Why a person would care: "The answer's first sentence answers my question, and I did not wait for it."
- NOT CLOSED

### PR-87F-10: The BRCA1 answer reads "? Answered" in amber with "not yet confirmed" and "High-risk claim"
- Kind: answer
- Verdict: needs your eye
- What: the 1280 BRCA1 answer's meta line reads "? Answered 9.5s · 13 tool calls · 21 sources cited from 2 layers" in amber, and the trust line "Based on 21 sources cited, not yet confirmed · High-risk claim"; the API run's outcome was `ask`. The Marfan answer read "✓ Answered". Not part of #229 as far as the diff shows, but it is the first line a person reads on query 1.
- Evidence: `brca1_1280_4_top_viewport.png`; `brca1_log.json`, step "sources", field `trust`; `api_brca1_events.jsonl`, `done`, `trust_outcome` "ask".
- Why a person would care: "The flagship question says answered, with a question mark and a warning; I am not sure whether to trust it."
- NOT CLOSED

## Timing

Seconds from pressing Search (web, polled every 100 ms) or from the start request (API).

| Run | First record row | First summary sentence | Answer landed |
|---|---|---|---|
| BRCA1, Researcher, web at 1280 | 5.68 | 9.75 | 10.03 (meta "9.5s") |
| Marfan, Plain language, web at 390 | 12.26 | 17.57 | 17.57 (meta "17.2s") |
| BRCA1, Researcher, API with `?reads=placement` | 4.17 | 8.70 | 8.72 (`elapsed_ms` 8530) |

All three answered within 20 s; none over 25 s. On the web the summary appeared 0.28 s and 0 s before the answer's meta line; on the API 0.02 s before `done`.

## Result

- Golden run: not in this brief, so no answered count against the floor and no answered-well sample.
- Questions spent: three, two on the web and one through the API.
- Fails: none.
- Needs your eye, in order: PR-87F-08 (query 91's expected order is stale), PR-87F-06 (23 ids against "21 sources cited"), PR-87F-07 (run-together chip words), PR-87F-10 (amber "? Answered" on query 1), PR-87F-02 (OMIM card with no link), PR-87F-04 (71-number MedGen card at 390).
- Passes: PR-87F-01, PR-87F-03, PR-87F-05, PR-87F-09.
- Overflow at 390: 0 on every capture of the Marfan answer. No surface without a design was touched.
- Read myself: every verdict rests on a screenshot or log I read in this folder (`brca1_*`, `marfan_*`, `api_brca1_events.jsonl`); PR-87F-08 also on the test queries document at b2514161. None rests only on a summary; the build report was read only to know what the change meant to do.

## What was not captured

- Query 91 from the command line: `s3` is not installed on this machine (not on the path, not in the project's virtual environment), so per the brief nothing was installed and the "redefined" warning was not checked.
- The 1 s cut-off itself: it fires only when the first-sentence pick is slow, and this run's pick took 0.37 s.
- The chip words on the web: the web shows none, by the build report's own account, so A04 on the web was checked only as one card per record.
- The prototype side-by-side at both widths: not asked for in this brief, and no screen layout changed in #229.
- Opening the OMIM card to read what it shows in place of a link.
