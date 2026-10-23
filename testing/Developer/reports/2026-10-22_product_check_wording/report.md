# Product check on develop: wording cards 138, 141 and 143

Pre-screen before the owner's retest, on 2026-10-22. It files findings and closes nothing. The owner's verdict closes.

## Table of contents

- [Target](#target)
- [Findings](#findings)
- [Summary](#summary)

## Target

- Web: https://search-agent-web-develop-2aeb.up.railway.app
- API /health, read before the first capture: `{"status":"ok","app_env":"develop"}`
- Deployed commit named in the brief: 34406a31 (merge of the card 138 pull request)
- Guest sessions only, no sign-in, no accounts created.

## Findings

### Card 143: About page trust line wording (works at 1280 and 390)

- Read myself: `card143_about_1280.png`, `card143_about_390.png`, `card143_about_390_trust_line_viewport.png`, beside `card143_about_prototype_1280.png` and `card143_about_prototype_390.png`.
- The example answer's trust line pill reads "Based on 1 source cited, from MedGen". The page text holds no "Grounded" anywhere (checked in the DOM at both widths).
- Step 6 "What you get" reads: "a trust line says how many sources the answer rests on and which database they come from".
- Horizontal overflow at 390: 0. At 1280: 0.
- At 390 the pill sits on one line inside the example card, under its "The trust line" label, as at 1280.
- Capture note, not a defect: the blue "NCBI Agentic Search" bar partway down both full-page shots is the sticky footer (position sticky, bottom 0) stamped at the first viewport's bottom edge by the full-page capture.

### PR-wording-01: The About page has no design to judge it against
- Kind: missing design
- Verdict: needs your eye
- What: `docs/build/design/README.md`'s coverage table lists "Integrations, docs and about" as not designed, "Only ever inside `prototype/app.html`". The prototype's About carries different sections ("The run loop", "The tool set") and no example answer card, so the example trust line block that card 143 changed has no design. Not judged against an invented look.
- Evidence: `card143_about_prototype_390.png` beside `card143_about_390.png`.
- Why a person would care: they would not see this; it means nobody has drawn what the About page should look like, so a layout regression there has nothing to be measured against.
- NOT CLOSED

### Card 138: ask-back NCBI link reads as words (works at 1280 and 390)

- Read myself: `card138_gerd_1280.png`, `card138_gerd_390.png`, `card138_marfan_1280.png`, `card138_marfan_390.png`, `card138_brca1_papers_1280.png`, `card138_brca1_papers_390.png`. Each question was a fresh guest session. The 390 shot is the same page resized after the reply landed, so one guest search covers both widths.
- GERD: label "One more detail needed", "What aspect of GERD would you like to explore?", link text "Search NCBI for GERD", href https://www.ncbi.nlm.nih.gov/search/all/?term=GERD.
- Marfan: "What would you like to know about Marfan syndrome?", link text "Search NCBI for Marfan", href https://www.ncbi.nlm.nih.gov/search/all/?term=Marfan.
- recent papers on BRCA1: "How far back should I search?", link text "Search NCBI for recent papers on BRCA1", href https://www.ncbi.nlm.nih.gov/search/all/?term=recent%20papers%20on%20BRCA1.
- No raw https address shows as text in any of the three. Each link opens in a new tab (target _blank, rel noopener noreferrer). All three hrefs return HTTP 200 from NCBI.
- At 390 every link fits on one line inside its grey box (widest, the BRCA1 link, 255 px wide ending at x 310 inside a box ending at x 355). Horizontal overflow 0 at both widths for all three.
- Time to the ask-back: 3 to 4 seconds on my clock; the meta line reads 1.8 to 2.8 s.

### PR-wording-02: The BRCA1 ask-back link searches NCBI for the whole sentence, not the gene
- Kind: answer
- Verdict: needs your eye
- What: for "recent papers on BRCA1" the link reads "Search NCBI for recent papers on BRCA1" and searches NCBI for that whole phrase, the words "recent" and "papers" included, where GERD and Marfan search the bare term. The brief's pattern "Search NCBI for <term>" holds only if the term is the whole question.
- Evidence: `card138_brca1_papers_390.png`, link text "Search NCBI for recent papers on BRCA1", href term=recent%20papers%20on%20BRCA1.
- Why a person would care: "I clicked to search NCBI for BRCA1 and it searched for the words 'recent papers on' too." Not judged whether NCBI's results suffer; the link text is at least honest about what it searches. The term comes from the API, so this predates card 138, which only changed the visible text.
- NOT CLOSED

### PR-wording-03: The ask-back block has no design
- Kind: missing design
- Verdict: needs your eye
- What: the prototype `docs/build/design/design-system/prototype/app.html` has no "One more detail needed" state (no match for the label in the file); its only refusal is the "Refused, out of scope" screen. So the ask-back block card 138 changed was judged on its own legibility, not against a design.
- Evidence: `card138_gerd_390.png`; no match for "detail needed" in the prototype.
- Why a person would care: they would not see it directly; the ask-back's look has never been drawn, so nobody can say whether it is where it should be.
- NOT CLOSED

### Card 141: read-only reply to a follow-up (works at 1280 and 390)

- Read myself: `card141_followup_readonly_1280_viewport.png`, `card141_followup_readonly_390_viewport.png`, with full-page shots `card141_followup_readonly_1280.png` and `card141_followup_readonly_390.png`, beside `card141_refusal_prototype_1280.png` and `card141_refusal_prototype_390.png`.
- Flow: one guest session, query 1 ("Which diseases are associated with BRCA1?"), then "Remove that variant node from the knowledge graph." typed in "Ask a follow-up question" and submitted.
- The reply's grey label reads "Read-only system", and its text reads, word for word: "This system only reads from NCBI records. It cannot add, change, or remove data. Ask what the graph holds about a gene, variant, or condition and I can assemble cited evidence." It matches query 89 in `testing/Test_queries_and_workflows.md`.
- Not labelled "Not a research question". The refusal block holds 0 links and 0 citation markers. Meta line: "0.5s · 0 tool calls · 0 sources cited". The reply landed 1.1 s after submit.
- The query 1 turn folds above it as "Which diseases are associated with BRCA1? 13 tool calls · 21 sources cited from 2 layers · Plain language · Show answer".
- At 390 the text wraps to five lines inside the box, with no clipped words. Horizontal overflow is 0 at both widths.
- Against the prototype: the order is the same (question title, meta line, refusal, follow-up field). The prototype draws a red "Refused, out of scope" screen, while the app draws a grey labelled box. The app's look comes from earlier owner items R13 and R44 ("a refusal is a first-class state, not an error"), so I do not count it as a defect. The prototype's own refusal screen overflows by 4 px at 390, a defect in the design file, not in the app.

### Control: query 1 still answers as before (works at 1280 and 390)

- Read myself: `control_query1_answer_1280.png`, `control_query1_answer_390.png`.
- Opening sentence: "BRCA1 is associated with familial cancer of breast, familial breast-ovarian cancer susceptibility 1, pancreatic cancer susceptibility 4, and Fanconi anemia complementation group S." Diseases are named in words, with no bare code.
- Meta line: "Answered 9.1s · 13 tool calls · 21 sources cited from 2 layers". My clock read 10.4 s to the finished answer.
- Trust line: "Based on 21 sources cited from ClinicalTrials.gov, ClinVar, PubMed and 3 other databases; their values could not be compared · High-risk claim".
- Compared with the 2026-10-17 control capture (`testing/Developer/reports/2026-10-17_product_check_card38/run1/brca1_control_researcher_390.txt`), the opening sentence, the 13 tool calls, the 21 sources and the trust line are all the same. The second sentence differs because that capture was at Researcher depth and this one at Plain language. Nothing reads worse.
- Horizontal overflow is 0 at both widths. In the full-page shots the app bar and footer sit partway down the page; that comes from the capture, which scrolled the page, and is not a layout defect.

### PR-wording-04: The answer status shows a bare question mark, "? Answered"
- Kind: screen
- Verdict: needs your eye
- What: query 1's meta line starts with an amber "?" before "Answered". The code draws "?" when the outcome tone is warn (`AnswerScreen.tsx`, the outcome line). This is not new tonight: the 2026-10-17 capture reads "? Answered10.4s" too.
- Evidence: `control_query1_answer_1280.png`, meta line "? Answered 9.1s · 13 tool calls · 21 sources cited from 2 layers".
- Why a person would care: "Answered, question mark? Is it answered or not?" Nothing on screen says what the question mark means.
- NOT CLOSED

### PR-wording-05: No golden run was made, although card 141 changes what a refusal says
- Kind: golden run
- Verdict: needs your eye
- What: the procedure counts as an answer-path change anything that "can change what an answer says". Card 141 changes the read-only refusal's last sentence, so by that definition it waits on the golden run. My brief named no accounts file and no floor and said guest sessions only, so I did not run it. Card 138 changed only the link's visible text, and card 143 changed only About page text.
- Evidence: the brief; `.claude/skills/bossman-mode/reference/Product_review.md`, "When it runs".
- Why a person would care: probably they would not, since a wording change to one refusal is unlikely to change which questions get answered. The rule still says this check comes before the owner's retest, and this check did not include it.
- NOT CLOSED

## Summary

- Golden result: not run (see PR-wording-05). No answered count, no answered-well read of the fixed ten, no list of questions that got worse.
- Time to answer, from my own runs only: query 1 in 10.4 s; the three ask-backs in 3 to 4 s; the read-only follow-up in 1.1 s. None over 25 s.
- Card 138: works at 1280 and 390.
- Card 141: works at 1280 and 390.
- Card 143: works at 1280 and 390.
- Control: query 1 reads as on 2026-10-17.
- No fails. Needs your eye, ranked: PR-wording-05 (no golden run on a refusal-text change), PR-wording-02 (the BRCA1 link searches the whole sentence), PR-wording-04 ("? Answered"), PR-wording-01 and PR-wording-03 (no design for the About page or the ask-back).
- Overflow at 390: 0 on every app screen captured. The prototype's own refusal screen overflows by 4 px.
- Surfaces with no design: the About page, and the ask-back "One more detail needed" block.
- Not captured: the golden run and the five-line rubric read of golden answers, since no accounts were given and the brief said guest only. Each 390 shot for cards 138 and 141 and the control is the same page resized from 1280, not a fresh phone-width load. I did not click the NCBI links in a browser; I read each href and fetched it (HTTP 200).
- Every verdict above rests on a screenshot I opened myself or DOM text my capture printed, except the comparison with 2026-10-17, which rests on that run's saved text file.
