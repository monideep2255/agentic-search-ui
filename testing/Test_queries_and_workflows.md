# Test queries and workflows

This is the one document that lists every query worth typing into the product, what a person should see when they type it, and why it matters to the person asking. This document is the status of record for testing, saying which queries are approved, awaiting retest or removed, while the five sources below remain the owners of build detail: the commits, the live-run measurements, and the open engineering questions behind each fix.

- `testing/Product/Product_workflows.md`
- `testing/Shipped_2026-09-20.md`
- `testing/Shipped_2026-09-22.md`
- `testing/Shipped_2026-09-23.md`
- `testing/Product/queries/Isolate_search_queries_and_workflow.md`
- `testing/UI_fix_plan.md`

## Table of contents

- [From the user's chair](#from-the-users-chair)
- [Status words](#status-words)
- [What to retest first](#what-to-retest-first)
- [Known already, no need to report](#known-already-no-need-to-report)
- [What this document does not cover](#what-this-document-does-not-cover)
- [1. Basic search and answers](#1-basic-search-and-answers)
- [2. Follow-up questions and conversation](#2-follow-up-questions-and-conversation)
- [3. Genes, variants and diseases](#3-genes-variants-and-diseases)
- [4. Chromosome windows and accessions](#4-chromosome-windows-and-accessions)
- [5. Pathogen isolates](#5-pathogen-isolates)
- [6. Refusals, off-topic and compute requests](#6-refusals-off-topic-and-compute-requests)
- [7. Sign in, sessions and history](#7-sign-in-sessions-and-history)
- [8. Stop, feedback and the connection](#8-stop-feedback-and-the-connection)
- [9. Screens, phone width, the tour and the disclaimer](#9-screens-phone-width-the-tour-and-the-disclaimer)
- [Workflow for the product owner](#workflow-for-the-product-owner)
- [Workflow for the developer](#workflow-for-the-developer)
- [Where each query came from](#where-each-query-came-from)

## From the user's chair

The person typing a query is a researcher, clinician or student who asked a real question and is waiting for an answer.

- What they see: an answer, a refusal, a spinner, or nothing at all. They never see the code, the tickets, or the trace behind it.
- Honesty beats polish: a tool that says one of its searches did not finish is trusted more than one that quietly returns less.
- A refusal must say what to type next, not just that it failed.
- A confident wrong record is worse than a missing one: never trade correctness for coverage just to make an answer look fuller.

## Status words

- Approved: the product owner retested this query and approved what it does.
- Awaiting retest: the feature behind this query is live on develop, but the product owner has not retested it yet.
- Removed: this test no longer applies, and the entry says why.
- Not yet recorded as approved: the test exists and the feature is live, but no document records the product owner's verdict on it.

When an answer does not match what is expected, screenshot it into `testing/Product/feedback/inbox/` and say "check the inbox". The full workflow is below, under Workflow for the product owner.

## What to retest first

As of 23 September 2026. Everything named here is live on develop and none of it has been retested yet, so this is the queue rather than a summary.

Start with these two, because they are where a mistake is most likely and most costly:

- Query 67, a past search reopening with the answer it gave. Pick a question whose answer had a table, such as an isolate question. The backend, the screen and the seam between them were built separately, so the table is where a seam would show.
- Query 66, the phenotypic features of Marfan syndrome. One live run settles the single gap the 23 September work left open, and that entry says plainly what is not yet known about it.

Then the rest of the 23 September work: query 64 (subject terms in words), query 65 (the opening count agreeing with the list beneath it), and query 60 (the MCP configuration, whose address no longer drops the s from https).

Then the four one-look checks, each a single glance rather than a search: query 3 (the answer-modes info button), query 4 (the mode locking once a search starts), query 7 (copying an answer carries no citation-card text) and query 9 (two visits, different scientists, the same answer).

Then the batch from the night of 22 September, still untested: queries 23 to 44 across sections 3, 4 and 5. That is the two lost searches, the coordinate range, the generic-word guard, the BioProject and BioSample accessions, and the whole isolate set.

Query numbers are permanent. A new query takes the next free number and sits in the section it belongs to, so the numbers do not run in strict order inside a section. Nothing is ever renumbered, because other documents point at these numbers.

## Known already, no need to report

Found by the browser run on 2026-09-12. Full report with screenshots: `testing/Developer/reports/2026-09-12_walkthrough/index.html`. Each line below is checked against the later fixes in `testing/UI_fix_plan.md`'s "What is live on develop" and the two shipped-day summaries, so it says whether it is still true.

- Follow-up questions used to get refused, including the suggested "What variants cause it?", 3 times out of 3. Closed: fixed in set 7 on 2026-09-13, and query 20 covers the retest.
- "Which diseases are associated with BRCA1?" was refused with "I could not find grounded evidence" about one time in three, and "Variants in GCK causing MODY" was refused too. Closed for these two questions specifically: set 10.1 shipped "BRCA1 and GCK answer every time," built and live.
- An answer can open with "These include…" without saying what "these" are, and a "one further gene record" note can show as a grey sentence with no source. Not confirmed closed by any named fix; still worth reporting if seen.
- After sign-up, your guest searches do appear in your history, but no message says so. Not confirmed closed.
- Answers sometimes take more than 25 seconds. Only partly addressed: the specific hundred-second BRCA1 question is fixed, query 10, but a 127.1-second run against a 13.6-second median is recorded as still open and unowned in `testing/Shipped_2026-09-20.md`.
- A citation chip can read as a code such as `MedGen:C0346153` even though the sentence beside it names the disease in words. Closed: query 1's own expected behaviour now requires disease names in words, never a bare code, and UI_fix_plan item 11.5 ("Citations are too big and overwhelm the answer," Live, approved 2026-09-22) moved citations to small raised numbers with a hover or tap card, so the code itself no longer sits in the chip.
- An answer's first sentence can come out garbled, for example "BRCA1 (gene symbol BRCA1 [1]. These are…". Not confirmed closed by any named fix; still worth reporting if seen.
- A returning guest cannot see how many searches are left until they run one. No longer applicable: the guest search limit itself was removed on 2026-09-12, query 53, so there is no limit left to show in advance.
- `testing/Shipped_2026-09-20.md`'s "What is still open" recorded an unowned MODY-genes grounding failure: "What genes are associated with MODY?" failed grounding on 5 of 6 runs. Included here because entry 7 sends the reader to a MODY question. Later addressed: UI_fix_plan items 11.19 and 11.20, both "Live, approved 2026-09-22," fixed MODY's gene and organism resolution specifically, though neither row names this exact grounding-failure measurement as its closure.

## What this document does not cover

These are tested on the developer side instead of by hand; see Workflow for the developer below.

- A citation that points outside NCBI, which should be refused rather than linked.
- The shared daily limit for all guests on one network.
- How the answer text arrives on screen, sentence by sentence or all at once.
- The GraphQL and MCP integrations, which need a developer's tools to call. They are checked on the developer side after every change to the Integrations page.

## 1. Basic search and answers

### 1. A first search with citations

Testing: a first-time visitor can ask a question and get a cited answer.

Query: `Which diseases are associated with BRCA1?`

Steps: open the site as a guest, tick "I understand this is a research tool...", Continue, then type the query in the search box, or click the "Diseases linked to BRCA1" chip, then Search.

Expected:

- A progress screen with five steps and a seconds counter that keeps ticking.
- During the search step, the scientist at the top says who they are handing off to, and three lines appear naming the graph, the live NCBI records and the literature and trials, each filling in a layer badge as its results arrive.
- The answer builds on screen sentence by sentence, then settles into short paragraphs, each sentence with its numbered citation chip, plus source cards. Typically 20 to 40 seconds, never more than 90.
- The answer never opens on a broken sentence.
- Any note reads as a grey note after the answer, never first and never styled like a cited sentence.
- Diseases are named in words that read naturally, such as "Familial breast-ovarian cancer susceptibility 1", never a bare code like `MedGen:C0346153` and never a garbled form like "susceptibility to, 1".
- Clicking a citation or source link opens an ncbi.nlm.nih.gov page for that record.

Why it matters: this is the first thing anyone sees, so a broken sentence, a bare code, or a dead link here reads as the whole product being unreliable.

Status: Approved (Product test 1)

### 2. Plain language versus researcher depth

Testing: the two answer modes change how the answer is written, not what it finds.

Query: `Which diseases are associated with BRCA1?`, asked twice.

Steps: on the home page check that "Plain language" is selected, Search, then New search, choose "Researcher", Search.

Expected:

- Plain language is the default, and it has no headings, lists or tables.
- Researcher mode has short topic headings, then the records found as a bulleted list under a heading, each row with its citation chip, and key names in the opening paragraph in bold.
- Both modes open with one sentence counting what was found and naming it, such as "Found 4 disease records for BRCA1: Familial cancer of breast [1], …".
- The same sources appear in both modes; compare the source count and the source list.
- A mode change applies only to the next question you ask.
- The handoff lines from a first search reappear under a follow-up question, though the three helper scientists may differ.
- Researcher never repeats a record in the prose that the list below already shows.
- No sentence reads "has a source URL of".
- No specific word count or paragraph count is promised.

Why it matters: a student and a clinician reading the same question want different depth, and neither should get a different set of facts because they picked a different reading level. The mode's earlier promise of a specific word count, about 120 words for Plain language and about 200 for Researcher, was recorded as stale on 21 September and dropped: the same question measured 66, 101 and 113 words across three runs.

Status: Approved (Product test 7); the info button's wording is query 3 and the mid-search lock is query 4. Whether Plain language keeps its small grey medical-advice reminder line ("Research information, not medical advice.") is still the product owner's decision, 9.11.

### 3. The answer-modes info button explains who each mode is for

Testing: the small "i" beside the answer mode selector describes who each mode suits, not a word-count promise it cannot keep.

Steps: click the small "i" beside the answer mode selector and read it.

Expected:

- The card describes who Plain language and Researcher mode are each for.
- It no longer promises a specific word count or paragraph count.

Why it matters: a promise about word count that is not kept reads as the product not knowing itself; describing who each mode suits is a promise it can actually keep.

Status: Awaiting retest (UI_fix_plan item 11.36)

### 4. The mode locks once a search starts

Testing: choosing a different answer mode while a search is running does not corrupt the answer.

Steps: start a search, then try to change the answer mode while it is running.

Expected:

- The mode selector is locked once a search starts.
- A change only applies to the next question.

Why it matters: a person who changes their mind mid-search should not get an answer that is a confused mix of both depths.

Status: Awaiting retest (UI_fix_plan item 9.12)

### 5. Trust signals and sources across layers

Testing: an answer says in one line how much to trust it, and its sources come from more than one layer.

Query: `Which diseases are associated with BRCA1?`, then `What is known about EGFR mutations in non-small cell lung cancer, and what trials are recruiting?`

Steps: watch the answer being written, get the answer, hover, tap or Tab to a citation number, read the card, press Escape, read the line under the answer, click its "i", look through the sources, open "Show work".

Expected:

- While the answer is being written, the scientist's line reads "{name} is writing the answer…" with moving dots, and no raw bracket numbers such as `[1][2]` show while it writes.
- Each cited sentence ends in small raised numbers, not boxes. A sentence with many sources shows one range, such as "1 to 13".
- Hovering, tapping or tabbing to a number opens a card naming the source, its id, its layer in words, and a link to the record on ncbi.nlm.nih.gov or clinicaltrials.gov. Escape, or a click elsewhere, closes the card.
- Under the answer, one plain line such as "Based on 4 sources, not yet confirmed" or "Confirmed by 2 independent sources", with an "i" explaining how sources are counted. No row of pills, and no two trust signals that contradict each other: the status word says "Answered" when the line carries the caution.
- A high-risk claim adds "High-risk claim" in red on the same line.
- Sources come from more than one layer: live NCBI gene records, the literature record from PubTator3, and up to five recruiting clinical trials for the EGFR question.
- A trial source names clinicaltrials.gov and its NCT number, and opens that trial's page.
- Any sentence with no source is shown in grey with no citation chip.
- On a phone, in Researcher mode, the tables become stacked rows: the name first with its citation number, the identifier underneath. The page never scrolls sideways.
- "Show work" shows the steps and tools the search used, including the literature and trials tools.

Why it matters: a person deciding whether to trust an answer needs one honest line telling them how confirmed it is, and a citation that actually opens the record it claims to cite.

Status: Approved (Product test 12); the copy-and-paste check is query 6.

### 6. Copying an answer carries no citation-card text

Testing: selecting and pasting an answer picks up only what is meant to be read, not the citation card's hidden text.

Query: `Which diseases are associated with BRCA1?`

Steps: get the answer, select it all, and paste it into a text editor.

Expected:

- The pasted text reads as prose and table text with citation digits only, never "Source 1, layer 2" or "Sources 1 to 4".
- With a screen reader, each citation number still announces its source and layer.

Why it matters: a researcher copying an answer into their own notes should get what they read on screen, not hidden accessibility text mixed into the middle of their notes.

Status: Awaiting retest (UI_fix_plan item 11.14; a real selection of 1,703 characters checked live held none of that text)

### 7. Suggested next step and missing-information notes

Testing: the answer is honest about what it left out.

Query: `Which diseases are associated with BRCA1?`, then `Variants in GCK causing MODY`

Steps: get each answer, read the end of the answer.

Expected:

- Sometimes one suggested next step that makes sense for the question, sometimes none.
- If there is one, "Yes, go deeper" runs a real follow-up on the same screen about the same gene, and the new answer lists records the earlier answer did not show.
- If the answer left something out, a plain note says so in everyday words, with no internal jargon.
- No Notes block appears under the answer.
- If the answer is a refusal instead, it shows a grey label such as "No answer found in NCBI records", with a clickable NCBI search link.
- No note ever appears as a normal cited sentence.

Why it matters: a researcher who does not know an answer was incomplete may treat it as the whole picture, so the honesty about what was left out is part of the answer, not an optional extra.

Status: Approved (Product test 13); the old Notes block (the unverified-summary note and the further-records note) was removed from the screen and approved 2026-09-22 (UI_fix_plan item 11.35).

### 8. The scientist name at the top

Testing: the "Working as" name is decoration only, and a reader can learn who the scientist was.

Steps: look at "Working as..." at the top right, click the small "i" next to the name, click "Learn more on Wikipedia", close the card with Escape or a click elsewhere.

Expected:

- A scientist's name, which may differ between visits.
- The "i" opens a card with one or two lines on what the scientist did, and a Wikipedia link that opens in a new tab.
- During each search, three helper scientists appear, one per layer, never the lead scientist, with the same "i" cards.

Why it matters: the scientist personas make the wait feel less like a black box, but they must never change what the person actually gets back.

Status: Approved (Product test 14); whether two visits show different scientists but the same answer is query 9.

### 9. Two visits show different scientists but the same answer

Testing: the scientist persona is random per visit and never changes what is found.

Query: `Which diseases are associated with BRCA1?`

Steps: open the site in two separate private windows and run the query in each.

Expected:

- The two visits can show different scientists.
- Both visits get the same answer content and the same sources.

Why it matters: the persona is decoration, and a person comparing notes with a colleague who got a different scientist name should still be looking at the same evidence.

Status: Awaiting retest (UI_fix_plan item 8.4)

### 10. The hundred-second question, fixed

Testing: an exploratory question with no recognisable shape answers quickly instead of waiting on a search that cannot finish.

Query: `I am a student. Explain in plain terms what the BRCA1 gene does and why it matters, with sources.`

Steps: type the query, Search.

Expected:

- The answer arrives well under a minute, not around 100 seconds.
- The gene record is among the sources.
- No line saying a background search did not finish.

Why it matters: a student asking a plain question should not wait far longer than someone asking a sharply worded one; a slow honest answer is still a bad experience if it is needlessly slow.

Status: Approved (Shipped_2026-09-22 item 1)

### 11. Researcher depth runs to the end of the record

Testing: a record's text is no longer cut off mid-word.

Query: `Which diseases are associated with BRCA1?` at researcher depth.

Steps: choose Researcher mode, Search.

Expected:

- The gene summary in the record tail runs past "and through the C-terminal d" to its actual end, with no cut mid-word and no ellipsis where the text was previously trimmed.

Why it matters: a sentence that stops mid-word reads as broken, and a researcher relying on the full description should get the full description, not a silently shortened one.

Status: Approved (Shipped_2026-09-22 item 6)

### 12. A lost background search says so

Testing: an answer that lost a background search tells the reader, instead of quietly showing less.

Query: no single query reliably triggers this; it rides along with any broad gene question, for example `Give me everything NCBI knows about BRCA1: the gene record, associated conditions, variants, tests and literature`.

Steps: ask a broad question that fans out into several background searches, and watch what the answer says if one of them does not finish.

Expected:

- An answer that lost a background search ends with "One of the background searches did not finish, so this answer may be missing sources. Ask again to retry."
- Its trust line reads "not yet confirmed".
- A search that failed with nothing found says so and invites a retry.

Why it matters: a person who does not know a search silently failed will treat a partial answer as the whole picture; telling them lets them decide whether to ask again.

Status: Approved (UI_fix_plan, "What is live on develop")

### 13. A quote spanning more than one sentence keeps its source link

Testing: a multi-sentence quote from a paper or a gene summary is cited on every sentence, not silently stripped, and a paper's own words reach the answer as citeable evidence at all.

Query: `Which diseases are associated with BRCA1?` at researcher depth.

Steps: choose Researcher mode, Search, and check every sentence of the gene summary in the record tail carries its citation.

Expected:

- A quote running to more than one sentence keeps its citation on every sentence, not just the last one.
- No sentence from a retrieved record is dropped for being part of a longer quote.

Why it matters: a retrieved record that gets shown and then quietly loses the link proving where it came from is a citation the reader cannot check, which defeats the point of citing it at all.

Status: Awaiting retest (UI_fix_plan item 11.34, fixed and live 2026-09-21; item 11.22, verified live 2026-09-22 and still awaiting the product owner's look, is the same check: a paper's own words reaching the answer, cited)

### 14. NCBI's own gene summary is retrieved and shown as a source

Testing: NCBI's plain-English gene description is fetched and cited as a source, though the answer does not yet use it to explain the gene in its own words.

Query: `Which diseases are associated with BRCA1?`

Steps: get the answer and look through its sources for the gene's own summary.

Expected:

- NCBI's plain-English gene summary appears among the sources, cited.
- The answer's own prose does not yet use it to explain the gene in its own words; that half is not built.

Why it matters: a person wants the gene's official description somewhere they can check it, even while the fuller explanation built from it is still to come.

Status: Approved for the retrieval half (UI_fix_plan item 11.31, "What is live on develop"); the explanation half is parked, not built.

### 15. A gene-to-disease question's notes agree with each other

Testing: the notes beneath an answer no longer contradict each other or the table beneath them.

Query: `Which diseases are associated with BRCA1?`

Steps: ask the query and read the answer's notes.

Expected:

- The notes and the table tell the same story about what was found.

Why it matters: an answer that contradicts itself in the same breath undermines trust in every other line of it.

Status: Awaiting retest (Shipped_2026-09-20 retest item 1; a retest instruction, not a recorded approval)

### 16. A literature question stays on topic

Testing: PubMed searches are relevance sorted rather than returning whatever came back first.

Query: any literature question, for example `What is known about EGFR mutations in non-small cell lung cancer, and what trials are recruiting?`

Steps: ask the query and check the papers returned are on topic.

Expected:

- The papers shown are actually about the subject asked, not an unrelated topic that happened to share a word.

Why it matters: a paper that shares a word with the question but is about something else wastes the reader's time and looks like a careless search.

Status: Awaiting retest (Shipped_2026-09-20 retest item 2; a retest instruction, not a recorded approval)

### 17. A question with many records pages cleanly

Testing: answer tables page at ten rows instead of showing a cut list, and the source list groups into three collapsed layer rows.

Query: any question that returns many records, for example `Which clinically significant variants have been reported in CFTR?`

Steps: ask the query and open the answer.

Expected:

- The table pages at ten rows, with every retrieved row still reachable.
- The source list shows three collapsed layer rows rather than a long unsorted list, with each record listed once.

Why it matters: a wall of sources is unreadable, and a person should be able to see how much was found without scrolling past dozens of near-duplicate rows.

Status: Approved (Shipped_2026-09-20 retest item 3; UI_fix_plan item 11.26, "Live, approved 2026-09-22")

### 18. The wait stays readable

Testing: the scientist names during the wait are readable, and the reveal timing scales with how many scientists a run actually shows.

Query: a slow, broadly worded question, for example `I am a student. Explain in plain terms what the BRCA1 gene does and why it matters, with sources.`

Steps: ask the query and watch the progress screen while it runs.

Expected:

- The names on the progress screen are readable, not cut off or flickering past too fast.
- The reveal timing scales with how many scientists a run actually shows, rather than a single fixed pace for every run.

Why it matters: a person staring at the progress screen for tens of seconds should be able to read what it is telling them, not just see it flash by.

Status: Approved (Shipped_2026-09-20 retest item 5; UI_fix_plan item 11.28, "Live, approved 2026-09-22")

### 19. The same question returns the same set of sources

Testing: asking the same question twice returns the same evidence.

Query: `Which diseases are associated with BRCA1?`

Steps: ask the query twice.

Expected:

- The same question returns the same set of sources, and the same count, on a second run.

Why it matters: an answer that changes its evidence base every time it is asked the same question is not trustworthy, even if each individual answer looks fine.

Status: Approved (Shipped_2026-09-20 retest item 6; UI_fix_plan item 11.21, "Live, approved 2026-09-22, both decisions done")

### 64. Subject terms are named, not coded

Testing: a question about what a paper is about answers with real subject terms rather than with the identifiers behind them.

Query: `What MeSH terms are assigned to PMID 11237011?`

Steps: type the query, Search.

Expected:

- Real terms in words, such as Genome Human, Chromosome Mapping and CpG Islands. This paper has 26 of them.
- Each term links to its own MeSH record on ncbi.nlm.nih.gov.
- No `[MeSH] D000818` style code anywhere in the answer, and no identifier presented as though it were a term.
- No slower than any other question of this size. Resolving the terms costs two lookups however many terms there are, so a paper with fifty terms is no slower than one with five.

Why it matters: a reader asking what a paper is about should get the subject terms in words. Twenty-six reference numbers answer the question in form only, and an identifier shown at full confidence as though it were a name is worse than showing nothing at all.

Status: Awaiting retest (Shipped_2026-09-23 items 3 and 5)

### 65. The opening count matches the list beneath it

Testing: the number an answer opens with agrees with the number of records it then shows.

Query: any question returning more than twenty records. `Which diseases are associated with BRCA1?` and the GEO question at query 25 both do on most runs.

Steps: ask the query, read the opening sentence, then count the records in the list or table beneath it.

Expected:

- The opening count and the list agree exactly.
- Before 23 September the sentence said twenty whatever the list held, because it counted a slice handed to the model rather than what the reader can actually see.

Why it matters: a reader who counts twenty-six rows under a sentence promising twenty stops trusting both numbers, and has no way to tell which of the two is wrong.

Status: Awaiting retest (Shipped_2026-09-23 item 4)

## 2. Follow-up questions and conversation

### 20. A follow-up carries the gene forward

Testing: the chat keeps context, so "it" means the gene from the last answer.

Query: after query 1, ask `What variants cause it?`

Steps: finish query 1, type in "Ask a follow-up question", or click the "What variants cause it?" chip, submit, watch the search run, then click "New search".

Expected:

- You stay on the same screen. The first question and its answer fold into a collapsed row at the top, and the new search's progress appears below it. The page scrolls so the new question's heading is in view.
- There is clear space between the folded rows and the new question.
- A second answer about BRCA1 grows where the progress was, without you typing BRCA1 again, naming ClinVar variants with sources. Sometimes it reads as a plain list of records with a note saying so, and that is still an honest answer, not a refusal.
- The folded row says "Show answer" and, once open, "Hide answer", reopening the earlier answer exactly as it looked when it was live.
- From a fresh page with no earlier answer, "What variants cause it?" does not refuse: a grey "One more detail needed" label asks which gene, variant or condition you mean, and the follow-up field is ready for the answer.
- Stop during the follow-up shows "Search stopped" with "Run again".
- "New search" clears the conversation and returns to the home page.

Why it matters: a person having a conversation should never have to repeat the subject they already named, and an unclear follow-up should ask rather than guess or refuse outright.

Status: Approved (Product test 2)

## 3. Genes, variants and diseases

### 21. GCK and its correct OMIM record

Testing: a gene question shows the right gene's OMIM entry, and never another gene's.

Query: `Which diseases are associated with GCK?`

Steps: type the query, Search.

Expected:

- OMIM 138079, glucokinase, is among the sources.
- No other gene's OMIM record, such as MAP4K2, appears.

Why it matters: a clinician looking up one gene and getting a citation for a different gene is a wrong record dressed up as a right one, which is the worst kind of mistake this product can make.

Status: Approved (Shipped_2026-09-22 item 3)

### 22. CFTR variants still answer

Testing: a previously working gene-variant question keeps answering the same way.

Query: `Which clinically significant variants have been reported in CFTR?`

Steps: type the query, Search.

Expected:

- The answer still answers, with the same sources as before.

Why it matters: someone checking CFTR before an appointment needs this answer to keep working exactly as it did last time, not to quietly go missing because some unrelated part of the product changed.

Status: Approved (Shipped_2026-09-22 item 5)

### 23. rs334 without invented conditions

Testing: the question's own words are never mistaken for a disease name.

Query: `What is rs334 and what condition is it associated with?`

Steps: type the query, Search.

Expected:

- The answer ends without a note listing conditions never mentioned, such as "Patient condition unchanged" or "Condition of fetal membrane".

Why it matters: the person asked about sickle cell trait's variant, not about unrelated MedGen entries that happened to share the word "condition" with their own question; a made-up list of conditions reads as evidence when it is noise.

Status: Awaiting retest (Shipped_2026-09-22 item 12)

### 24. Comparing two genes in a disease context

Testing: a question naming two genes gets both genes' records, not a note that a background search did not finish.

Query: `Compare what is known about MLH1 and MSH2 in colorectal cancer risk.`

Steps: type the query, Search.

Expected:

- Both genes' condition records are among the sources.
- No line saying a background search did not finish.

Why it matters: a comparison question is only useful if both halves of the comparison actually show up; half an answer that does not say it is half an answer is misleading.

Status: Awaiting retest (Shipped_2026-09-22 item 7)

### 25. GEO expression datasets for TP53

Testing: a dataset question searches GEO and cites real series, and the question's own wording is never mistaken for a disease.

Query: `Find GEO expression datasets studying TP53 in human tumour samples.`

Steps: type the query, Search. Run it twice, since this one does not go wrong on every try.

Expected:

- GEO series are among the sources, each linking to an NCBI GEO DataSets page.
- No line saying a background search did not finish.
- The answer ends without a closing note listing mouse tumour records as entities named in the question.

Why it matters: a dataset search that silently drops results, or that tells the person they asked about something they did not, both erode trust in the same way a wrong citation does.

Status: Awaiting retest (Shipped_2026-09-22 items 8 and 13)

### 66. Phenotypic features of a disease

Testing: a question about the physical features of a disease no longer runs a search that could never return a row.

Query: `What phenotypic features are associated with Marfan syndrome?`

Steps: type the query, Search. One run settles it.

Expected, and this entry is deliberately open where the others are not:

- Before 23 September this always answered "I could not find evidence", which reads as "nothing is known about this" and is false.
- The graph search behind it could never return a row, and it has been removed. What the question reaches INSTEAD was not verified end to end, so what a correct answer looks like here is the thing this test establishes rather than something it checks against.
- A refusal is worth reporting rather than passing. The open question is whether the question should reach MedGen through the live NCBI records instead, which is a routing decision rather than a defect.

Why it matters: "I could not find evidence" about a disease whose features are thoroughly documented is the worst shape of wrong answer, because it reads as an authoritative statement that nothing is known.

Status: Awaiting retest (Shipped_2026-09-23 item 6; `UI_fix_plan.md` "Next, in order" item 1, the one honest gap the overnight session left)

## 4. Chromosome windows and accessions

### 26. A copy number variant window, before the coordinate range feature

Testing: a coordinate-only question about ACMG evidence, tested and approved on the morning of 22 September, before the coordinate range feature shipped that night.

Query: `What ACMG-relevant evidence is available for a copy number variant spanning chr17:43,044,295-43,125,364 on GRCh38?`

Steps: type the query, Search.

Expected:

- The answer asks the person to name a gene, variant, disease or organism.
- If instead it answers with the genes and records under the window, that is query 27 working as intended, not a defect: the coordinate feature shipped later the same day and changed this.

Why it matters: this was the honest fallback for a coordinate question the product could not yet resolve; keeping the record straight about when each behaviour was true stops a fixed feature being reported as broken.

Status: Approved on 22 September before the coordinate feature shipped; current behaviour is query 27's (Shipped_2026-09-22 item 2)

### 27. The same window, with genes and overlapping records asked for by name

Testing: after the coordinate range feature, the same window resolves to real genes and records instead of asking for a gene.

Query: `What ACMG-relevant evidence is available for a copy number variant spanning chr17:43,044,295-43,125,364 on GRCh38? List the overlapping genes, dbVar records and ClinVar entries.`

Steps: type the query, Search.

Expected:

- BRCA1 is named without the person having to name it themselves.
- dbVar and ClinVar records are among the sources, with working links.
- No request to name a gene, and no classification of the variant.

Why it matters: a researcher pasting in coordinates from a lab report should get back what is actually under that window, not a request to already know the answer.

Status: Awaiting retest (Shipped_2026-09-22 item 9)

### 28. A window with no assembly named

Testing: a coordinate window with no genome assembly stated is asked which one, rather than guessed.

Query: `What is under chr17:43,044,295-43,125,364?`

Steps: type the query, Search.

Expected:

- One question back: which assembly, GRCh38 or GRCh37, and why it matters.

Why it matters: the two assemblies put different genes under the same numbers, so guessing which one the person meant risks a confidently wrong answer.

Status: Awaiting retest (Shipped_2026-09-22 item 10)

### 29. A CFTR-locus window

Testing: a different chromosome window resolves to the right gene and its surrounding records.

Query: `What genes and ClinVar records are under chr7:117,480,025-117,668,665 on GRCh38?`

Steps: type the query, Search.

Expected:

- CFTR is named first, with CFTR-AS1 and CFTR-AS2 beside it.
- The literature and OMIM content is about CFTR, not an unrelated regulatory fragment.
- ClinVar and dbVar records for that stretch are among the sources.

Why it matters: someone working on cystic fibrosis pastes in their own coordinates and must get CFTR, not whatever the product was first built against.

Status: Awaiting retest (Shipped_2026-09-22 item 11)

### 30. A BioProject accession with everything it links to

Testing: an accession-only question is answered with the actual project record and what it links to, rather than a request for a gene.

Query: `For BioProject PRJNA31257, list the BioSamples, the SRA runs and any genome assemblies, and tell me how to retrieve each.`

Steps: type the query, Search.

Expected:

- The project record (the Human Genome Project) is among the sources.
- Its BioSample, its SRA run SRR9496657, and its GRCh38.p14 assembly are each cited to the NCBI page it can be fetched from.
- No request to name a gene.

Why it matters: a person who already has an accession number from a paper or a database wants what that accession points to, not to be redirected into a gene search they did not ask for.

Status: Awaiting retest (Shipped_2026-09-22 item 14)

### 31. An accession NCBI does not have

Testing: an accession that does not exist is told so honestly, not answered as if it were a missing gene name.

Query: `What is in BioProject PRJNA999999999?`

Steps: type the query, Search.

Expected:

- One line back: the accession was not found in NCBI, check it and ask again.
- Not a request to name a gene.

Why it matters: a typo in an accession number is a different problem from an unrecognised question, and the response should tell the person which one they hit.

Status: Awaiting retest (Shipped_2026-09-22 item 15)

### 32. A BioSample accession and its runs

Testing: a BioSample accession resolves to its record and its SRA runs, the same way a BioProject accession does.

Query: `What is BioSample SAMN12121739 and which SRA runs and assemblies come from it?`

Steps: type the query, Search.

Expected:

- The BioSample record and up to ten of its SRA runs are among the sources.
- No "which gene, variant or condition do you mean?" request.

Why it matters: a person who already found a BioSample id in a paper or a database wants to know what came from that exact sample, not to be redirected into naming a gene they never asked about.

Status: Awaiting retest (Shipped_2026-09-22 item 16)

## 5. Pathogen isolates

This is the pathogen isolate search. It lets a person ask for the actual isolates behind a resistance question and get back a short list they can open, each linked to its NCBI Pathogen Detection page, each showing its resistance genes, plus an honest count of how many isolates matched and how many are shown. From the isolate document's own framing: the person asking is an outbreak or AMR researcher who wants isolates they can open, each with its resistance genes and a link, and an honest statement of how many there are and how many were shown.

### 33. The flagship question: E. coli and ESBL genes

Testing: the flagship isolate search question, the one the product is measured on.

Query: `What Escherichia coli isolates in Pathogen Detection carry extended-spectrum beta-lactamase genes?`

Steps: type the query, Search.

Expected:

- A table headed "Isolates and their AMR genes" with 20 rows. Each row shows the isolate's BioSample accession, strain, and where and when it was collected, beside its gene list; every row carries a blaCTX-M gene, and each gene list is linked to that isolate's own Pathogen Detection page.
- The line "Pathogen Detection lists 140,476 Escherichia coli isolates with these genes; the first 20 in the snapshot are shown."
- A note saying only the blaCTX-M family of genes was searched for "extended-spectrum beta-lactamase", and why: a plain blaTEM or blaSHV gene name cannot be told apart from a genuine ESBL by its name alone, so those families were left out rather than risk a wrong label.
- E. coli named and linked to its NCBI Taxonomy record among the sources cited.
- The answer arrives well under a minute.

Why it matters: an outbreak researcher needs isolates they can actually open and check, not a summary that hides how the gene family was interpreted.

Status: Awaiting retest (Product/queries/Isolate_search_queries_and_workflow.md query 1, Shipped_2026-09-22 item 17)

### 34. The same question on Salmonella

Testing: the isolate search works for an organism other than E. coli, with the same shape of answer.

Query: `Which Salmonella isolates in Pathogen Detection carry ESBL genes?`

Steps: type the query, Search.

Expected:

- The same shape as query 33: a list of isolates with accession, strain, collection details, resistance genes and links, an exact count, "showing the first 20", and the same disclosure that only the blaCTX-M family was searched.
- Salmonella named and linked to its own NCBI Taxonomy record, not E. coli's.

Why it matters: a search that only works for one organism is not a general capability, it is a demo, and a researcher working on Salmonella needs the same trustworthy answer as one working on E. coli.

Status: Awaiting retest (Product/queries/Isolate_search_queries_and_workflow.md query 2)

### 35. An exact gene, one allele only

Testing: naming a specific gene, rather than a family word, searches for that gene and nothing broader.

Query: `Which Salmonella isolates carry blaCTX-M-15?`

Steps: type the query, Search.

Expected:

- Every isolate shown carries a gene starting with blaCTX-M-15, not a different CTX-M number and not a different gene family.
- The count and the "first 20 shown" note, same as the other queries. The count reads 2,678.
- No mention of other ESBL families, since none were asked for.

Why it matters: naming an exact gene is a precise request, and returning isolates carrying a different allele would be a quiet substitution the person did not ask for.

Status: Awaiting retest (Product/queries/Isolate_search_queries_and_workflow.md query 3, Shipped_2026-09-22 item 18)

### 36. Carbapenemase genes in Klebsiella

Testing: a different resistance family, on a different organism, still returns real isolates.

Query: `Which Klebsiella isolates in Pathogen Detection carry carbapenemase genes?`

Steps: type the query, Search.

Expected:

- Isolates carry at least one of the carbapenemase families (blaKPC, blaNDM, blaOXA-48, blaVIM, blaIMP), each with its full gene list and a link to its Pathogen Detection page, and the answer names which gene prefixes it searched.
- An exact count, reading 88,025, and the first-20 note.

Why it matters: carbapenemase resistance is one of the most clinically serious findings in this domain, so this answer's accuracy matters more than most.

Status: Awaiting retest (Product/queries/Isolate_search_queries_and_workflow.md query 4, Shipped_2026-09-22 item 19)

### 37. Colistin resistance in E. coli

Testing: a differently named resistance mechanism, a plasmid-mediated gene rather than a beta-lactamase, still resolves correctly.

Query: `Which E. coli isolates in Pathogen Detection carry colistin resistance genes?`

Steps: type the query, Search.

Expected:

- Isolates carrying an mcr gene, listed with their full gene set and a link to each isolate's page.
- The answer names the mcr gene prefixes it searched.
- An exact count and the first-20 note.

Why it matters: colistin is a drug of last resort, so someone checking for resistance to it needs the same careful answer they would get for a better-known gene family, not a special case that only works for ESBL.

Status: Awaiting retest (Product/queries/Isolate_search_queries_and_workflow.md query 5)

### 38. A gene nothing in this organism carries

Testing: a real, well-formed gene question that has zero matches gets an honest zero, not a refusal.

Query: `Which Listeria isolates in Pathogen Detection carry blaKPC?`

Steps: type the query, Search.

Expected:

- The plain statement "Pathogen Detection lists 0 Listeria isolates with these genes," not "I could not find information on this."
- No isolate rows, since there are none to show.
- No suggestion that the search failed or was refused, and no request for a gene name. It ran, and the true answer is zero.
- Listeria cited to NCBI Taxonomy.

Why it matters: a true zero and a failed search look identical if the product does not say which one happened, and telling them apart is the difference between "there is nothing here" and "the tool broke".

Status: Awaiting retest (Product/queries/Isolate_search_queries_and_workflow.md query 6, Shipped_2026-09-22 item 20)

### 39. An organism Pathogen Detection does not cover

Testing: asking about an organism outside Pathogen Detection's scope gets an honest explanation, not an empty or invented result.

Query: `Which tomato isolates in Pathogen Detection carry resistance genes?`

Steps: type the query, Search.

Expected:

- One question back: Pathogen Detection is searched one organism at a time, which organism do you mean, with a few it covers named in words (Escherichia coli, Salmonella, Listeria monocytogenes, Klebsiella pneumoniae, Campylobacter).
- The answer does not claim to know whether "tomato" is or is not in Pathogen Detection. It only recognises the organisms it can search, so it asks rather than asserts.
- No isolate rows and no invented data.

Why it matters: a product that confidently states an organism is not covered, when it actually has no idea, is guessing dressed up as knowledge.

Status: Awaiting retest (Product/queries/Isolate_search_queries_and_workflow.md query 7, Shipped_2026-09-22 item 21)

### 40. An organism named with no gene

Testing: naming an organism but no resistance gene or family asks a clarifying question rather than dumping every isolate.

Query: `Which E. coli isolates are in Pathogen Detection?`

Steps: type the query, Search.

Expected:

- The answer asks which resistance gene or gene family to search for, with ESBL, carbapenemase, colistin and a gene name offered as examples, rather than listing anything.
- No attempt to return all E. coli isolates. The exact number in the snapshot, in the hundreds of thousands, is never shown as a result list.

Why it matters: dumping hundreds of thousands of rows because a question was underspecified would bury the person in noise instead of helping them narrow their question.

Status: Awaiting retest (Product/queries/Isolate_search_queries_and_workflow.md query 8, Shipped_2026-09-22 item 21)

### 41. A follow-up asking to filter by year

Testing: a follow-up after an isolate search carries the organism and gene forward, and is honest about what it can and cannot do yet.

Query: after query 33, ask `Show me the ones from 2023`

Steps: finish query 33, type the follow-up, Search.

Expected, honestly stated for the first version: a year filter is not built, and a follow-up does not yet carry an isolate search forward the way it carries a gene forward.

- The answer asks which organism to search, or which gene, rather than pretending to filter.
- It never repeats the same full list as if it had been filtered to 2023, and never invents a filtered list.
- If the answer instead lists 2023 isolates that were genuinely filtered, that is a later version working, not this one; note it as a pleasant surprise rather than a pass.

Why it matters: a follow-up that silently ignores part of the question, while looking like it answered it, is more dangerous than one that admits it cannot filter yet.

Status: Awaiting retest (Product/queries/Isolate_search_queries_and_workflow.md query 9)

### 42. The existing single-isolate lookup still works

Testing: the older, single-isolate mode of this tool is not broken by adding isolate search.

Query: `What is known about Salmonella isolate SAMN02147118 in Pathogen Detection?`

Steps: type the query, Search.

Expected:

- A single isolate's details: its strain, where and when it was collected, its resistance genes, and a link to its Pathogen Detection page.
- No mention of "showing the first 20" or a count of isolates, since this is a single-record lookup, not a search.

Why it matters: adding a new search mode should never break the lookup someone was already relying on.

Status: Awaiting retest (Product/queries/Isolate_search_queries_and_workflow.md query 10)

### 43. The wait feels alive

Testing: the person is not staring at a frozen screen while the search runs.

Query: `Which E. coli isolates in Pathogen Detection carry ESBL genes?`

Steps: type the query, Search, watch the progress screen while it runs.

Expected:

- The progress steps show the pathogen search running, with continuous motion, not a blank pause.
- The answer arrives and builds on screen; nothing about the wait looks stuck or broken.

Why it matters: the search reads a very large file, which takes real time, and a frozen-looking screen during that time reads as a crash even when the search is working fine.

Status: Awaiting retest (Product/queries/Isolate_search_queries_and_workflow.md query 11)

### 44. The shortest version a person would type

Testing: a terse, minimally worded question with only "ESBL" as the clue still works.

Query: `ESBL E. coli isolates?`

Steps: type the query, Search.

Expected:

- The same shape of answer as query 33: isolates listed with genes and links, an exact count, the first-20 note, the disclosure that only blaCTX-M was searched, and E. coli's Taxonomy record cited.
- The short, informal phrasing is understood the same way as the fully worded question in query 33.

Why it matters: most people type the short version of a question, not the fully worded one, so the product has to understand both.

Status: Awaiting retest (Product/queries/Isolate_search_queries_and_workflow.md query 12, Shipped_2026-09-22 item 22)

What the answer must never do, from the isolate document, applies to every query in this section:

- Never list a blaTEM-1 carrier as an ESBL isolate. blaTEM-1 is a plain, broad-spectrum gene, not an extended-spectrum one, and stating otherwise would be a confident wrong record.
- Never claim a total number of isolates it did not actually count. If the scan was cut off before finishing, the answer says "at least" that many, never a bare exact number it cannot back up.
- Never link an isolate to any page outside NCBI.
- Never answer from memory when the search returned nothing. A true zero is stated as a true zero, and an organism or gene Pathogen Detection genuinely lacks data for is named as such, never papered over with a guess.
- Never show a bare `SAMN` accession as an isolate's only name when it has a strain name. The strain name comes first, with the accession alongside it.

## 6. Refusals, off-topic and compute requests

### 45. An off-topic question

Testing: the product refuses rather than making something up.

Query: `What is the capital of France?`

Steps: type the query, Search.

Expected:

- A refusal box with a calm grey label reading "Outside biomedical research".
- A short sentence explaining the refusal.
- No red "Not verified" or "Not fully grounded" pill.
- No error styling.
- Never an invented answer.

Why it matters: a product that stays quiet about what it cannot do, rather than guessing, is one a person can trust when it does answer.

Status: Approved (Product test 8)

### 46. A question with no data

Testing: when NCBI has nothing, the product says so instead of inventing an answer.

Query: `Which diseases are associated with the gene FAKEGENE99?`

Steps: type the query, Search.

Expected:

- A refusal box with the grey label "No answer found in NCBI records".
- A plain sentence saying nothing was found.
- A clickable NCBI search link.
- No diseases listed.
- No citation chips.
- No red "Not verified" or "Not fully grounded" pill.

Why it matters: a made-up gene name is exactly the kind of input a careless system would hallucinate an answer for, so this is the test that proves it will not.

Status: Approved (Product test 19)

### 47. Compute requests are turned away

Testing: a request for a capability the product does not have, sequence matching or file analysis, is refused with a clear reason rather than answered from whatever disease-sounding words appear in the wording.

Query: `BLAST this sequence against nr and tell me the top hit: ATGGATTTATCTGCTCTTCGCGTTGAAGAAGTAC` and `Here is my VCF file, tell me which variants are concerning.`

Steps: type each query in turn, Search.

Expected:

- Both are turned away with a message saying the capability does not exist and where to run a sequence search.
- Neither is answered from disease terms found inside the wording, which is what used to happen.

Why it matters: a person pasting in a sequence or a VCF file wants to know the product cannot do that, immediately, rather than getting a confident-sounding answer built on the wrong reading of their question.

Status: Approved (Shipped_2026-09-22 item 4)

### 48. A question the product could not read

Testing: a question the guardrail cannot parse into a gene, variant, disease or organism is answered with a request for one, instead of a dead end.

Query: any text naming no recognisable gene, variant, disease or organism, for example `qwerty asdf zxcv`.

Steps: type the query, Search.

Expected:

- The answer reads "I could not tell which gene, variant, disease or organism you mean. Name one and I will search."

Why it matters: telling someone exactly what to type next turns a dead end into a next step, which is the difference between a refusal that helps and one that just stops.

Status: Approved (UI fix plan, what is live on develop)

## 7. Sign in, sessions and history

### 49. Log in and log out

Testing: one Log in button creates an account for a new email, and logging out goes to the home page.

Steps: click "Log in" at the top right, enter a new email and a password, Log in, reload the page, run query 1, click "Integrations" in the top bar, click your email at the top right, Log out, click "Log in", enter the same email and password, Log in.

Expected:

- A sign-in screen titled "Log in" that says a new email creates your account, with one button and no Sign up button.
- After the first Log in, the top right shows your initials and email instead of "Log in".
- Clicking your email opens a menu with your email, "Signed in", "API key and integrations", "Documentation" and a red "Log out".
- Search and follow-ups work the same as queries 1 and 20.
- Log out, even from the Integrations page, lands on the search home page, with the previous conversation gone.
- Logging back in with the same email and password shows your email at the top right again.
- After a reload you stay signed in.

Why it matters: a person's account should feel like theirs, the same every time they come back, and logging out should leave nothing of the previous conversation behind.

Status: Approved (Product test 3)

### 50. A wrong password gives a clear message

Testing: a wrong password shows a clear message, and the form still works afterwards.

Steps: click "Log in", enter your account's email with a wrong password, Log in, fix the password, Log in.

Expected:

- "That password does not match this email. Check it and try again."
- Your email stays filled in, and the corrected password logs you in.
- No raw error codes or technical messages.

Why it matters: a raw error code tells a person nothing about what to fix; a plain sentence does.

Status: Approved (Product test 5)

### 51. Search history

Testing: a signed-in user can see and re-run earlier searches.

Steps: log in, run 2 different searches, look at "Your searches" on the left, click an older one, click "Hide your searches", then "Show your searches".

Expected:

- Both searches are listed.
- Clicking one shows the answer that search already gave, at once, with a Run again button beside it. Query 67 covers that in full.
- The panel hides and comes back.
- Guests see no history panel.
- Reload the page: you stay signed in and both searches are still listed.

Why it matters: a researcher tracking down the same gene across several sessions needs to find their earlier questions without re-typing them from memory.

Status: Approved (Product test 6); what clicking an older search does changed on 23 September and is query 67.

### 52. Search limit shown to a signed-in user

Testing: a signed-in user sees their own search limit, and it is true.

Steps: log in, click your email at the top right, look at the bottom of "Your searches".

Expected:

- The menu reads "Signed in", followed by your search limit.
- The bottom of the history panel names your account and your search limit.
- No "unlimited" claim anywhere.

Why it matters: a person should be told their real limit rather than an inflated or absent one, so they are not surprised when they hit it.

Status: Approved (Product test 18)

### 53. Guest limit of 5 searches

Removed on 2026-09-12. Set 1 took away the guest limit, so there is nothing left to test here. Query 1 now covers searching as a guest, with no count and no sign-in card however many searches are run.

Status: Removed (Product test 4)

### 54. Guest searches moving into a new account

Removed on 2026-09-12. With no guest limit, there is no guest allowance to move into an account.

Status: Removed (Product test 16)

### 55. Too many guest attempts

Removed on 2026-09-12. Set 1 took away the ten-attempt guest limit. Query 45, the off-topic question, still covers a question being refused.

Status: Removed (Product test 20)

### 67. A past search reopens with the answer it gave

Testing: clicking a search in the history rail shows the answer already given, at once, instead of paying for a second one.

Steps: sign in, ask a question whose answer has a TABLE, such as an isolate question from section 5, wait for the answer, start a new search, then click that first question in "Your searches".

Expected:

- The answer you already got appears AT ONCE, with no progress screen and no wait.
- It is marked "Saved answer, asked <date>", carries its own trust line, and has a Run again button beside it.
- A table renders as a table, not as rows of pipe characters. This is where a mistake would show, since the backend, the screen and the seam between them were built separately.
- Run again does a fresh search, charged to you as a normal search.
- Guests do not get this. The account is what stores the answer, and deleting the account deletes it with them.

Why it matters: clicking your own earlier question, being charged a second search for it, and waiting thirty seconds to read something you already read is the kind of small dishonesty that makes a history rail feel like decoration rather than a record.

Status: Awaiting retest (Shipped_2026-09-23 item 2; UI_fix_plan item 10.2). Query 51 covers the rail itself.

## 8. Stop, feedback and the connection

### 56. Stop a search

Testing: a search can be cancelled mid-way.

Query: `Which diseases are associated with BRCA1?`

Steps: Search, press Stop while the progress screen is running.

Expected:

- The progress steps disappear.
- A "Search stopped" message appears.
- Two buttons appear: "Run again" and "New search".
- Clicking "Run again" asks the same question again from the start.
- Clicking "New search" returns to the home page.
- No answer appears from the stopped search.

Why it matters: a person who changes their mind mid-search should not have to wait out a search they no longer want.

Status: Approved (Product test 9)

### 57. Feedback on an answer

Testing: a reader can rate an answer and flag a bad source.

Steps: get any answer, click "Not helpful", pick a reason such as "Wrong answer", type a comment, Send feedback, on a source click "Flag: does not support".

Expected:

- Reasons appear only after "Not helpful", never after "Helpful".
- Sending confirms that it went through.
- The source changes to "Flagged".

Why it matters: flagging a bad source is how a real reader tells the product it got something wrong, and that channel only works if it visibly confirms it was heard.

Status: Not yet recorded as approved (Product test 10)

### 58. Feedback when the connection drops

Testing: feedback written is not lost if sending fails.

Steps: get any answer, click "Not helpful", pick a reason and type a comment, turn off Wi-Fi, Send feedback, turn Wi-Fi back on, Retry.

Expected:

- Your reason and comment stay on screen with a Retry button.
- Retry sends it once you are back online.

Why it matters: losing a thoughtful piece of feedback to a dropped connection would discourage anyone from bothering to give it again.

Status: Not yet recorded as approved (Product test 21)

## 9. Screens, phone width, the tour and the disclaimer

### 59. Other pages and phone width

Testing: navigation works, including on a phone.

Steps: click Integrations, About, press the browser back button, on Integrations click a copy button, back on About scroll to the bottom and click "Explore the architecture", make the window phone-narrow or open the site on your phone, open "More pages", log in, tap the searches button at the top right.

Expected:

- Each page opens, and back returns to the previous page. The top bar shows Search, Integrations and About.
- Integrations shows one title, four chips (115M nodes, 693M edges, 3 data layers, 7 tools), then four cards of the same height, each with a round icon and its buttons lined up along the bottom: REST and SSE, GraphQL, MCP server, and Command line tools.
- Below the cards, a short access notice, then an API documentation section.
- About opens with "What happens to your question": seven numbered stops following one BRCA1 question through the system, and its closing line has an "open Search" link that returns to the home page.
- About ends with "Where the data comes from": the knowledge graph is a snapshot finished on 22 April 2026, built from Gene, PubMed, ClinVar, Taxonomy and MedGen, holding 115,406,761 nodes and 693,295,991 edges, with layers 2 and 3 called live. "Explore the architecture" goes to the Architecture page without reloading, so you stay logged in.
- Architecture opens with the title "Architecture" and four numbered stops: Layer 1 the data pipelines and the knowledge graph, Layer 2 live NCBI APIs, Layer 3 enrichment, then how all three feed the search agent. The word "system" appears nowhere on the page, and it also opens directly at /architecture.
- Stop 1 shows the pipeline steps, the snapshot figures, one card per source database with its node count, the graph facts and an example query, and it ends with the blue L1 card for cypher_query naming its 90-second, 500-row limit. Stops 2 and 3 each show their own coloured card: green L2 with ncbi_efetch, ncbi_dbsnp and pathogen_detection, purple L3 with pubtator_annotate, litvar2_lookup and clinicaltrials_search, each tool naming what it calls and its time limit.
- Stop 4 says the agent reads layer 1 first and reaches layers 2 and 3 live while you wait, and that every fact arrives with a link to the record behind it.
- The closing line on Architecture, "open About", goes back to About.
- The copy button copies the snippet.
- At phone width nothing scrolls sideways, and the other pages are reachable from "More pages".
- At phone width, while logged in, the searches button opens your searches as a sliding panel, closable by tapping outside, Escape, or its close button.

Why it matters: a person on a phone in a lab or a clinic should get the same working product as one at a desk, not a broken layout.

Status: Approved (Product test 11)

### 60. Open the Integrations page and paste the MCP configuration

Testing: the MCP configuration printed on the Integrations page is complete and copies cleanly. This is only what the product owner can judge by eye; whether it actually connects end to end is a developer check, see Workflow for the developer below.

Steps: open the Integrations page, read the printed MCP configuration, and click its copy button.

Expected:

- The configuration is printed on the page.
- The copy button copies it.
- The address it prints no longer drops the s from https. Before 23 September a request to it was answered with a redirect to an `http://` address, which a client would follow with its token in the clear.

Why it matters: a developer following printed setup instructions should not have to debug the instructions themselves before they can use the integration.

Status: Awaiting retest (UI_fix_plan item 11.30; Shipped_2026-09-23 item 1). The end-to-end half is already proven live on develop by the developer check below, which is why this is the one item of the 23 September set that did not need a signed-in session to verify.

### 61. The disclaimer

Testing: nobody can use the product without accepting the disclaimer.

Steps: open the site as a guest, try to click past the disclaimer or press Escape without ticking the box, tick the box, Continue, log in, Log out.

Expected:

- The disclaimer is a wide box titled "Important medical disclaimer" with a bold opening sentence, a paragraph advising you to seek your physician's advice, and a notice box titled "Prototype".
- The continue button runs the full width of the box, reads "I understand, continue to the research tool", and stays greyed out until the box is ticked.
- Escape does not close it.
- After ticking and Continue, the product opens.
- It does not come back while you use the site, and it appears again after Log out.

Why it matters: this is the one screen standing between a person and a research prototype that must never be mistaken for medical advice, so it cannot be skippable.

Status: Approved (Product test 15)

### 62. A page address that does not exist

Testing: a mistyped address does not break the site.

Steps: open the site's address with `/nonsense` added to the end.

Expected: you land on the Search page, not a blank or error page.

Why it matters: a broken link or a typo should never leave a person staring at a dead page with no way forward.

Status: Not yet recorded as approved (Product test 17)

### 63. The guided tour

Testing: a first-time visitor can take a tour of every feature that ends with a real answer.

Steps: open the site in a private window, tick the disclaimer, Continue, on the home page under the suggested questions click "Start the tour", read each card and press Next, on step 7 click "Run it for me", wait for the answer, press Next to the end, Done, click the "Take the tour" button under the suggested questions on the home page.

Expected:

- A card reads "New here? Take the two-minute tour" with "Start the tour" and "Not now". "Not now" removes it for good on this browser.
- The tour has nine steps with a "Step n of 9" counter, highlighting the question box, the answer depth, the suggested questions, the scientist name, the top bar, and Log in.
- Step 7 fills the question box with the BRCA1 question and runs it; Stop stays reachable.
- Steps 8 and 9 point at the citation chips, the sources, and the follow-up field. Done closes the tour.
- If the system refuses the question, the tour says so and ends with Done.
- Escape closes the tour at any point. "Take the tour" starts it again any time.
- At phone width the card sits at the bottom of the screen and nothing scrolls sideways.

Why it matters: a first-time visitor who does not know what to ask should be able to see the whole product work end to end without having to guess a good question first.

Status: Not yet recorded as approved (Product test 22)

## Workflow for the product owner

1. Open the develop app: <https://search-agent-web-develop-2aeb.up.railway.app>
2. Sign in with your usual account, or test as a guest for the queries that call for it, in a private or incognito window.
3. Run the queries in this document in whatever order you like. They are grouped by feature area, and each section stands on its own.
4. For the pathogen isolate section, queries 33 to 44, run them in order: each builds a little on the last, which makes it easier to spot where something breaks.
5. Screenshot the answer for anything that looks wrong, and especially the honest-zero, unsupported-organism, and clarifying-question cases, since these are the ones most likely to go wrong quietly.
6. Drop screenshots and notes in `testing/Product/feedback/inbox/`. Put the query number in the filename if that is convenient.
7. Say "check the inbox" when you are done, and the findings will be picked up from there.

## Workflow for the developer

The automated checks behind these queries, and the live proof that backs the isolate search in particular:

- `tests/system_03_search_agent/tools/test_pathogen_detection.py`: unit tests for the isolate search mode of the tool itself.
- `tests/system_03_search_agent/tools/test_pathogen_detection_premise.py`, run with `RUN_PREMISE_GATE=1`: the live premise gate against the real Pathogen Detection FTP snapshot.
- `tests/system_03_search_agent/core/test_isolate_search.py` and `test_isolate_search_wiring.py`: the agent-loop side, how Think, Plan, Act and Write handle an isolate search question.

For a live proof against develop itself, use the consistency runner at `testing/Developer/reports/2026-09-22_10.3_consistency/run_consistency.py` with `--ids G-035`, run three passes, and keep the laptop awake with `caffeinate -i` for the duration. Do not run any other live measurement against NCBI at the same time, since the E-utilities and Pathogen Detection rate pools are shared and a second live check running in parallel can trip both.

The evidence folder for that run must contain `runs.jsonl` (the raw pass-by-pass record), a `raw/` folder (the full response bodies), and a `findings.md` that states its verdict in the first line, before any detail.

Two developer-side facts from 23 September. Query 60's end-to-end check has been run against develop and passes: a `POST` to `/mcp` answers `307` with an `https://` location, and a `POST` to `/mcp/` returns a valid MCP initialize response, which proves the mount still works rather than that the redirect merely changed. Separately, the frontend unit suite, which is the quick check run before a push, was both repaired and made faster: 527 of 527 passing in about 85 seconds against 128 to 163 before. Its filmstrip evidence is in `frontend/e2e/evidence/2026-09-23_journey7_viewports/`.

For the wider suite, `testing/Developer/Developer_workflows.md` has the full specification and run commands, including how to run the automated tests behind every other section of this document. Whether the MCP configuration printed on the Integrations page (query 60) actually connects end to end, not just reads correctly, is checked there too, after every change to that page.

## Where each query came from

| Section | Source documents |
|---|---|
| 1. Basic search and answers | `Product/Product_workflows.md` tests 1, 7, 12, 13, 14; `Shipped_2026-09-22.md` items 1, 6; `Shipped_2026-09-20.md` retest items 1, 2, 3, 5, 6; `UI_fix_plan.md` "What is live on develop" and items 8.4, 9.12, 11.14, 11.31, 11.34, 11.35, 11.36; `Shipped_2026-09-23.md` items 3, 4, 5 |
| 2. Follow-up questions and conversation | `Product/Product_workflows.md` test 2 |
| 3. Genes, variants and diseases | `Shipped_2026-09-22.md` items 3, 5, 7, 8, 12, 13; `Shipped_2026-09-23.md` item 6 |
| 4. Chromosome windows and accessions | `Shipped_2026-09-22.md` items 2, 9, 10, 11, 14, 15, 16 |
| 5. Pathogen isolates | `Product/queries/Isolate_search_queries_and_workflow.md` queries 1 to 12; `Shipped_2026-09-22.md` items 17 to 22 |
| 6. Refusals, off-topic and compute requests | `Product/Product_workflows.md` tests 8, 19; `Shipped_2026-09-22.md` item 4; `UI_fix_plan.md` "What is live on develop" |
| 7. Sign in, sessions and history | `Product/Product_workflows.md` tests 3, 4, 5, 6, 16, 18, 20; `Shipped_2026-09-23.md` item 2; `UI_fix_plan.md` item 10.2 |
| 8. Stop, feedback and the connection | `Product/Product_workflows.md` tests 9, 10, 21 |
| 9. Screens, phone width, the tour and the disclaimer | `Product/Product_workflows.md` tests 11, 15, 17, 22; `Shipped_2026-09-20.md` retest item 4; `UI_fix_plan.md` item 11.30; `Shipped_2026-09-23.md` item 1 |
