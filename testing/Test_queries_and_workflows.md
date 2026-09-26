# Test queries and workflows

This is the one document that lists every feature worth trying in the product. For each one it says what to type and what a person should see when they type it, from the chair of the person asking.

Last updated: 2026-09-25.

Every entry has the same three parts:

- A heading naming the feature in plain words, with its item numbers.
- "Queries to try:", each query in backticks, with any exact steps.
- "What you should see:", what appears on screen, what must not appear, and in one line why it matters to the person asking.

Status does not live here:

- What awaits your retest is the Retest column of the board, `testing/UI_fix_plan.md`.
- Each item's status is in the index at the top of `testing/UI_fixes_done.md`.

The sources below remain the owners of build detail: the commits and the live-run measurements behind each fix, and its open engineering questions.


- `testing/Product/Product_workflows.md`
- `testing/User-feedback/`, a second tester's screenshots, with their comment in each filename
- `testing/Product/queries/Isolate_search_queries_and_workflow.md`
- `testing/UI_fix_plan.md`, the board: to do, build in progress, retest
- `testing/UI_fixes_done.md`, every item that is built and live, with its test query, the detail behind every card, and where the last session stopped
- `testing/UI_fixes_done.md`'s section "Shipped days, 2026-09-20 to 2026-09-23", which keeps what the three daily shipped lists recorded beyond their retest steps

The daily shipped lists of 2026-09-20, 2026-09-22 and 2026-09-23 were folded in on 2026-09-24. Every retest step they carried is a query here, and the closing table, [Every feature and where to try it](#every-feature-and-where-to-try-it), maps each of their retest items to its query.

## Table of contents

- [From the user's chair](#from-the-users-chair)
- [Before you start](#before-you-start)
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
- [10. Questions with no gene and no disease in them](#10-questions-with-no-gene-and-no-disease-in-them)
- [11. Answers that answer the question](#11-answers-that-answer-the-question)
- [12. The overnight build of 2026-09-25](#12-the-overnight-build-of-2026-09-25)
- [Workflow for the product owner](#workflow-for-the-product-owner)
- [Workflow for the developer](#workflow-for-the-developer)
- [Where each query came from](#where-each-query-came-from)
- [Every feature and where to try it](#every-feature-and-where-to-try-it)

## From the user's chair

The person typing a query is a researcher, clinician or student who asked a real question and is waiting for an answer.

- What they see: an answer, a refusal, a spinner, or nothing at all. They never see the code, the tickets, or the trace behind it.
- Honesty beats polish: a tool that says one of its searches did not finish is trusted more than one that quietly returns less.
- A refusal must say what to type next, not just that it failed.
- A confident wrong record is worse than a missing one: never trade correctness for coverage just to make an answer look fuller.

## Before you start

- Open the develop app: <https://search-agent-web-develop-2aeb.up.railway.app>
- Sign in for the queries that say so. Test as a guest, in a private or incognito window, for the ones that call for it.
- ONE THING TO KNOW BEFORE YOU START: type the seven questions in a FRESH session, or at least do not ask them straight after a gene question. The same holds for section 11. A defect found on 2026-09-23 and fixed the same day made the caffeine question bind a gene remembered from an earlier question and answer confidently about the wrong thing. It is fixed, and the retest is more honest if it is not the first thing being tested.
- What to retest, and in what order: the Retest column of `testing/UI_fix_plan.md`. Each card there names its query number here, through the closing table.
- When an answer does not match what is expected, screenshot it into `testing/Product/feedback/inbox/` and say "check the inbox". The full workflow is below, under Workflow for the product owner.
- Query numbers are permanent. A new query takes the next free number and sits in the section it belongs to, so the numbers do not run in strict order inside a section. Nothing is ever renumbered, because other documents point at these numbers.

## Known already, no need to report

Found by the browser run on 2026-09-12. Full report with screenshots: `testing/Developer/reports/2026-09-12_walkthrough/index.html`. Each line below is checked against the later fixes in `testing/UI_fixes_done.md`'s "What is live on develop" and the shipped days recorded there, so it says whether it is still true.

- Follow-up questions used to get refused, including the suggested "What variants cause it?", 3 times out of 3. Closed: fixed in set 7 on 2026-09-13, and query 20 covers the retest.
- "Which diseases are associated with BRCA1?" was refused with "I could not find grounded evidence" about one time in three, and "Variants in GCK causing MODY" was refused too. Closed for these two questions specifically: set 10.1 shipped "BRCA1 and GCK answer every time," built and live.
- An answer can open with "These include…" without saying what "these" are, and a "one further gene record" note can show as a grey sentence with no source. Not confirmed closed by any named fix; still worth reporting if seen.
- After sign-up, your guest searches do appear in your history, but no message says so. Not confirmed closed.
- Answers sometimes take more than 25 seconds. Only partly addressed: the specific hundred-second BRCA1 question is fixed, query 10, but a 127.1-second run against a 13.6-second median is recorded as still open and unowned in the 2026-09-20 shipped day, under "Shipped days" in `testing/UI_fixes_done.md`.
- A citation chip can read as a code such as `MedGen:C0346153` even though the sentence beside it names the disease in words. Closed: query 1's own expected behaviour now requires disease names in words, never a bare code, and UI_fixes_done item 11.5 ("Citations are too big and overwhelm the answer," Live, approved 2026-09-22) moved citations to small raised numbers with a hover or tap card, so the code itself no longer sits in the chip.
- An answer's first sentence can come out garbled, for example "BRCA1 (gene symbol BRCA1 [1]. These are…". Not confirmed closed by any named fix; still worth reporting if seen.
- A returning guest cannot see how many searches are left until they run one. No longer applicable: the guest search limit itself was removed on 2026-09-12, query 53, so there is no limit left to show in advance.
- The 2026-09-20 shipped day's "What is still open", kept in `testing/UI_fixes_done.md`, recorded an unowned MODY-genes grounding failure: "What genes are associated with MODY?" failed grounding on 5 of 6 runs. Included here because entry 7 sends the reader to a MODY question, and query 78 asks this one. Later addressed: UI_fixes_done items 11.19 and 11.20, both "Live, approved 2026-09-22," fixed MODY's gene and organism resolution specifically, though neither row names this exact grounding-failure measurement as its closure.
- The same PubMed search can return a slightly different set of papers. Six identical PubMed searches returned two distinct result sets on 2026-09-23, and the GERD questions moved 20 citations to 19 with one paper swapped. Recorded in `testing/UI_fixes_done.md`'s notes against item 11.21's promise; not yet its own item.

## What this document does not cover

These are tested on the developer side instead of by hand; see Workflow for the developer below.

- A citation that points outside NCBI, which should be refused rather than linked.
- The shared daily limit for all guests on one network.
- How the answer text arrives on screen, sentence by sentence or all at once.
- The GraphQL and MCP integrations, which need a developer's tools to call. They are checked on the developer side after every change to the Integrations page.

## 1. Basic search and answers

### 1. A first search with citations (Product test 1)

Queries to try:

- `Which diseases are associated with BRCA1?`: open the site as a guest, tick "I understand this is a research tool...", Continue, then type the query in the search box, or click the "Diseases linked to BRCA1" chip, then Search.

What you should see:

- A first-time visitor can ask a question and get a cited answer.
- A progress screen with five steps and a seconds counter that keeps ticking.
- During the search step, the scientist at the top says who they are handing off to, and three lines appear naming the graph, the live NCBI records and the literature and trials, each filling in a layer badge as its results arrive.
- The answer builds on screen sentence by sentence, then settles into short paragraphs, each sentence with its numbered citation chip, plus source cards. Typically 20 to 40 seconds, never more than 90.
- The answer never opens on a broken sentence.
- Any note reads as a grey note after the answer, never first and never styled like a cited sentence.
- Diseases are named in words that read naturally, such as "Familial breast-ovarian cancer susceptibility 1", never a bare code like `MedGen:C0346153` and never a garbled form like "susceptibility to, 1".
- Clicking a citation or source link opens an ncbi.nlm.nih.gov page for that record.
- Why it matters: this is the first thing anyone sees, so a broken sentence, a bare code, or a dead link here reads as the whole product being unreliable.

### 2. Plain language versus researcher depth (Product test 7)

Queries to try:

- `Which diseases are associated with BRCA1?`, asked twice: on the home page check that "Plain language" is selected, Search, then New search, choose "Researcher", Search.
- Then query 3 for the info button's wording, and query 4 for the mode locking mid-search.

What you should see:

- The two answer modes change how the answer is written, not what it finds.
- Plain language is the default, and it has no headings, lists or tables.
- Researcher mode has short topic headings, then the records found as a bulleted list under a heading, each row with its citation chip, and key names in the opening paragraph in bold.
- Both modes open with one sentence counting what was found and naming it, such as "Found 4 disease records for BRCA1: Familial cancer of breast [1], …".
- Since 2026-09-24 the two depths also differ in their opening sentence and their list on every question, item 12.9. Query 72 checks that, and it changes the two lines above.
- The same sources appear in both modes; compare the source count and the source list.
- A mode change applies only to the next question you ask.
- The handoff lines from a first search reappear under a follow-up question, though the three helper scientists may differ.
- Researcher never repeats a record in the prose that the list below already shows.
- No sentence reads "has a source URL of".
- No specific word count or paragraph count is promised. The mode's earlier promise of a specific word count, about 120 words for Plain language and about 200 for Researcher, was recorded as stale on 21 September and dropped: the same question measured 66, 101 and 113 words across three runs.
- Plain language may carry its small grey medical-advice reminder line ("Research information, not medical advice."). Whether it keeps it is still the product owner's decision, 9.11.
- Why it matters: a student and a clinician reading the same question want different depth, and neither should get a different set of facts because they picked a different reading level.

### 3. The answer-modes info button explains who each mode is for (11.36)

Queries to try:

- No query needed: click the small "i" beside the answer mode selector and read it.

What you should see:

- The small "i" beside the answer mode selector describes who each mode suits, not a word-count promise it cannot keep.
- The card describes who Plain language and Researcher mode are each for.
- It no longer promises a specific word count or paragraph count.
- Why it matters: a promise about word count that is not kept reads as the product not knowing itself; describing who each mode suits is a promise it can actually keep.

### 4. The mode locks once a search starts (9.12)

Queries to try:

- Any query, for example `Which diseases are associated with BRCA1?`: start a search, then try to change the answer mode while it is running.

What you should see:

- Choosing a different answer mode while a search is running does not corrupt the answer.
- The mode selector is locked once a search starts.
- A change only applies to the next question.
- Why it matters: a person who changes their mind mid-search should not get an answer that is a confused mix of both depths.

### 5. Trust signals and sources across layers (Product test 12)

Queries to try:

- `Which diseases are associated with BRCA1?`
- `What is known about EGFR mutations in non-small cell lung cancer, and what trials are recruiting?`
- For each: watch the answer being written, get the answer, hover, tap or Tab to a citation number, read the card, press Escape, read the line under the answer, click its "i", look through the sources, open "Show work".
- Then query 6 for the copy-and-paste check.

What you should see:

- An answer says in one line how much to trust it, and its sources come from more than one layer.
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
- Why it matters: a person deciding whether to trust an answer needs one honest line telling them how confirmed it is, and a citation that actually opens the record it claims to cite.

### 6. Copying an answer carries no citation-card text (11.14)

Queries to try:

- `Which diseases are associated with BRCA1?`: get the answer, select it all, and paste it into a text editor.

What you should see:

- Selecting and pasting an answer picks up only what is meant to be read, not the citation card's hidden text.
- The pasted text reads as prose and table text with citation digits only, never "Source 1, layer 2" or "Sources 1 to 4".
- With a screen reader, each citation number still announces its source and layer.
- Checked live: a real selection of 1,703 characters held none of that text.
- Why it matters: a researcher copying an answer into their own notes should get what they read on screen, not hidden accessibility text mixed into the middle of their notes.

### 7. Suggested next step and missing-information notes (Product test 13, 11.35)

Queries to try:

- `Which diseases are associated with BRCA1?`
- `Variants in GCK causing MODY`
- For each: get the answer, read the end of the answer.

What you should see:

- The answer is honest about what it left out.
- Sometimes one suggested next step that makes sense for the question, sometimes none.
- If there is one, "Yes, go deeper" runs a real follow-up on the same screen about the same gene, and the new answer lists records the earlier answer did not show.
- If the answer left something out, a plain note says so in everyday words, with no internal jargon.
- No Notes block appears under the answer. The old Notes block, the unverified-summary note and the further-records note, was removed from the screen (UI_fixes_done item 11.35).
- If the answer is a refusal instead, it shows a grey label such as "No answer found in NCBI records", with a clickable NCBI search link.
- No note ever appears as a normal cited sentence.
- Why it matters: a researcher who does not know an answer was incomplete may treat it as the whole picture, so the honesty about what was left out is part of the answer, not an optional extra.

### 8. The scientist name at the top (Product test 14)

Queries to try:

- No query needed: look at "Working as..." at the top right, click the small "i" next to the name, click "Learn more on Wikipedia", close the card with Escape or a click elsewhere.
- Then query 9: whether two visits show different scientists but the same answer.

What you should see:

- The "Working as" name is decoration only, and a reader can learn who the scientist was.
- A scientist's name, which may differ between visits.
- The "i" opens a card with one or two lines on what the scientist did, and a Wikipedia link that opens in a new tab.
- During each search, three helper scientists appear, one per layer, never the lead scientist, with the same "i" cards.
- Why it matters: the scientist personas make the wait feel less like a black box, but they must never change what the person actually gets back.

### 9. Two visits show different scientists but the same answer (8.4)

Queries to try:

- `Which diseases are associated with BRCA1?`: open the site in two separate private windows and run the query in each.

What you should see:

- The scientist persona is random per visit and never changes what is found.
- The two visits can show different scientists.
- Both visits get the same answer content and the same sources.
- Why it matters: the persona is decoration, and a person comparing notes with a colleague who got a different scientist name should still be looking at the same evidence.

### 10. The hundred-second question, fixed (G-039)

Queries to try:

- `I am a student. Explain in plain terms what the BRCA1 gene does and why it matters, with sources.`

What you should see:

- An exploratory question with no recognisable shape answers quickly instead of waiting on a search that cannot finish.
- The answer arrives well under a minute, not around 100 seconds.
- The gene record is among the sources.
- No line saying a background search did not finish.
- Why it matters: a student asking a plain question should not wait far longer than someone asking a sharply worded one; a slow honest answer is still a bad experience if it is needlessly slow.

### 11. Researcher depth runs to the end of the record (11.33)

Queries to try:

- `Which diseases are associated with BRCA1?` at researcher depth: choose Researcher mode, Search.

What you should see:

- A record's text is no longer cut off mid-word.
- The gene summary in the record tail runs past "and through the C-terminal d" to its actual end, with no cut mid-word and no ellipsis where the text was previously trimmed.
- Why it matters: a sentence that stops mid-word reads as broken, and a researcher relying on the full description should get the full description, not a silently shortened one.

### 12. A lost background search says so (L-01)

Queries to try:

- No single query reliably triggers this; it rides along with any broad gene question, for example `Give me everything NCBI knows about BRCA1: the gene record, associated conditions, variants, tests and literature`.
- Ask a broad question that fans out into several background searches, and watch what the answer says if one of them does not finish.

What you should see:

- An answer that lost a background search tells the reader, instead of quietly showing less.
- An answer that lost a background search ends with "One of the background searches did not finish, so this answer may be missing sources. Ask again to retry."
- Its trust line reads "not yet confirmed".
- A search that failed with nothing found says so and invites a retry.
- Why it matters: a person who does not know a search silently failed will treat a partial answer as the whole picture; telling them lets them decide whether to ask again.

### 13. A quote spanning more than one sentence keeps its source link (11.34, 11.22)

Queries to try:

- `Which diseases are associated with BRCA1?` at researcher depth: choose Researcher mode, Search, and check every sentence of the gene summary in the record tail carries its citation.

What you should see:

- A multi-sentence quote from a paper or a gene summary is cited on every sentence, not silently stripped, and a paper's own words reach the answer as citeable evidence at all.
- A quote running to more than one sentence keeps its citation on every sentence, not just the last one.
- No sentence from a retrieved record is dropped for being part of a longer quote.
- Item 11.22 is the same check: a paper's own words reaching the answer, cited.
- Why it matters: a retrieved record that gets shown and then quietly loses the link proving where it came from is a citation the reader cannot check, which defeats the point of citing it at all.

### 14. NCBI's own gene summary is retrieved and shown as a source (11.31)

Queries to try:

- `Which diseases are associated with BRCA1?`: get the answer and look through its sources for the gene's own summary.

What you should see:

- NCBI's plain-English gene description is fetched and cited as a source, though the answer does not yet use it to explain the gene in its own words.
- NCBI's plain-English gene summary appears among the sources, cited.
- The answer's own prose does not yet use it to explain the gene in its own words; that half is not built, and it is parked.
- Why it matters: a person wants the gene's official description somewhere they can check it, even while the fuller explanation built from it is still to come.

### 15. A gene-to-disease question's notes agree with each other

Queries to try:

- `Which diseases are associated with BRCA1?`, or any gene-to-disease question: ask the query and read the answer's notes.

What you should see:

- The notes beneath an answer no longer contradict each other or the table beneath them.
- The notes and the table tell the same story about what was found.
- Why it matters: an answer that contradicts itself in the same breath undermines trust in every other line of it.

### 16. A literature question stays on topic

Queries to try:

- Any literature question, for example `What is known about EGFR mutations in non-small cell lung cancer, and what trials are recruiting?`: ask the query and check the papers returned are on topic.

What you should see:

- PubMed searches are relevance sorted rather than returning whatever came back first.
- The papers shown are actually about the subject asked, not an unrelated topic that happened to share a word.
- Why it matters: a paper that shares a word with the question but is about something else wastes the reader's time and looks like a careless search.

### 17. A question with many records pages cleanly (11.26)

Queries to try:

- Any question that returns many records, for example `Which clinically significant variants have been reported in CFTR?`: ask the query and open the answer.

What you should see:

- Answer tables page at ten rows instead of showing a cut list, and the source list groups into three collapsed layer rows.
- The table pages at ten rows, with every retrieved row still reachable.
- The source list shows three collapsed layer rows rather than a long unsorted list, with each record listed once.
- Why it matters: a wall of sources is unreadable, and a person should be able to see how much was found without scrolling past dozens of near-duplicate rows.

### 18. The wait stays readable (11.28)

Queries to try:

- A slow, broadly worded question, for example `I am a student. Explain in plain terms what the BRCA1 gene does and why it matters, with sources.`: ask the query and watch the progress screen while it runs.

What you should see:

- The scientist names during the wait are readable, and the reveal timing scales with how many scientists a run actually shows.
- The names on the progress screen are readable, not cut off or flickering past too fast.
- The reveal timing scales with how many scientists a run actually shows, rather than a single fixed pace for every run.
- Why it matters: a person staring at the progress screen for tens of seconds should be able to read what it is telling them, not just see it flash by.

### 19. The same question returns the same set of sources (11.17, 11.21)

Queries to try:

- `Which diseases are associated with BRCA1?`: ask the query twice.

What you should see:

- Asking the same question twice returns the same evidence.
- The same question returns the same set of sources, and the same count, on a second run.
- Why it matters: an answer that changes its evidence base every time it is asked the same question is not trustworthy, even if each individual answer looks fine.

### 64. Subject terms are named, not coded (G-019)

Queries to try:

- `What MeSH terms are assigned to PMID 11237011?`

What you should see:

- A question about what a paper is about answers with real subject terms rather than with the identifiers behind them.
- Real terms in words, such as Genome Human, Chromosome Mapping and CpG Islands. This paper has 26 of them.
- Each term links to its own MeSH record on ncbi.nlm.nih.gov.
- No `[MeSH] D000818` style code anywhere in the answer, and no identifier presented as though it were a term.
- No slower than any other question of this size. Resolving the terms costs two lookups however many terms there are, so a paper with fifty terms is no slower than one with five.
- Why it matters: a reader asking what a paper is about should get the subject terms in words. Twenty-six reference numbers answer the question in form only, and an identifier shown at full confidence as though it were a name is worse than showing nothing at all.

### 65. The opening count matches the list beneath it

Queries to try:

- Any question returning more than twenty records. `Which diseases are associated with BRCA1?` and the GEO question at query 25 both do on most runs.
- Ask the query, read the opening sentence, then count the records in the list or table beneath it.

What you should see:

- The number an answer opens with agrees with the number of records it then shows.
- The opening count and the list agree exactly.
- Before 23 September the sentence said twenty whatever the list held, because it counted a slice handed to the model rather than what the reader can actually see.
- Why it matters: a reader who counts twenty-six rows under a sentence promising twenty stops trusting both numbers, and has no way to tell which of the two is wrong.

### 77. Only the main point is bold (11.27)

Queries to try:

- `Which diseases are associated with BRCA1?`, once in Plain language and once in Researcher.

What you should see:

- Only the lead claim's main point is bold.
- Table cells and list items are plain.
- A Plain language answer keeps its bold main point too. The fix over-corrected at first, so plain language had no bold at all, and that was repaired the same day, 2026-09-20.
- Why it matters: in the product owner's words, "Too much bold: only the title or main point should be bold"; bold everywhere stops pointing the reader at anything.

## 2. Follow-up questions and conversation

### 20. A follow-up carries the gene forward (Product test 2, 7.1 to 7.5)

Queries to try:

- After query 1, ask `What variants cause it?`: finish query 1, type in "Ask a follow-up question", or click the "What variants cause it?" chip, submit, watch the search run, then click "New search".
- From a fresh page with no earlier answer, ask `What variants cause it?`.

What you should see:

- The chat keeps context, so "it" means the gene from the last answer.
- You stay on the same screen. The first question and its answer fold into a collapsed row at the top, and the new search's progress appears below it. The page scrolls so the new question's heading is in view.
- There is clear space between the folded rows and the new question.
- A second answer about BRCA1 grows where the progress was, without you typing BRCA1 again, naming ClinVar variants with sources. Sometimes it reads as a plain list of records with a note saying so, and that is still an honest answer, not a refusal.
- The folded row says "Show answer" and, once open, "Hide answer", reopening the earlier answer exactly as it looked when it was live.
- From a fresh page with no earlier answer, "What variants cause it?" does not refuse: a grey "One more detail needed" label asks which gene, variant or condition you mean, and the follow-up field is ready for the answer.
- Stop during the follow-up shows "Search stopped" with "Run again".
- "New search" clears the conversation and returns to the home page.
- Why it matters: a person having a conversation should never have to repeat the subject they already named, and an unclear follow-up should ask rather than guess or refuse outright.

## 3. Genes, variants and diseases

### 21. GCK and its correct OMIM record (2b)

Queries to try:

- `Which diseases are associated with GCK?`

What you should see:

- A gene question shows the right gene's OMIM entry, and never another gene's.
- OMIM 138079, glucokinase, is among the sources.
- No other gene's OMIM record, such as MAP4K2, appears.
- Why it matters: a clinician looking up one gene and getting a citation for a different gene is a wrong record dressed up as a right one, which is the worst kind of mistake this product can make.

### 22. CFTR variants still answer

Queries to try:

- `Which clinically significant variants have been reported in CFTR?`

What you should see:

- A previously working gene-variant question keeps answering the same way.
- The answer still answers, with the same sources as before.
- Why it matters: someone checking CFTR before an appointment needs this answer to keep working exactly as it did last time, not to quietly go missing because some unrelated part of the product changed.

### 23. rs334 without invented conditions

Queries to try:

- `What is rs334 and what condition is it associated with?`

What you should see:

- The question's own words are never mistaken for a disease name.
- The answer ends without a note listing conditions you never mentioned: no "Patient condition unchanged", no "Condition of fetal membrane".
- Why it matters: the person asked about sickle cell trait's variant, not about unrelated MedGen entries that happened to share the word "condition" with their own question; a made-up list of conditions reads as evidence when it is noise.

### 24. Comparing two genes in a disease context (G-033)

Queries to try:

- `Compare what is known about MLH1 and MSH2 in colorectal cancer risk.`

What you should see:

- A question naming two genes gets both genes' records, not a note that a background search did not finish.
- Both genes' condition records are among the sources.
- No line saying a background search did not finish.
- Why it matters: a comparison question is only useful if both halves of the comparison actually show up; half an answer that does not say it is half an answer is misleading.

### 25. GEO expression datasets for TP53 (G-037)

Queries to try:

- `Find GEO expression datasets studying TP53 in human tumour samples.`: run it twice, since this one does not go wrong on every try. The model does not tag "tumour" as a disease on every pass.

What you should see:

- A dataset question searches GEO and cites real series, and the question's own wording is never mistaken for a disease.
- GEO series are among the sources, each linking to an NCBI GEO DataSets page.
- No line saying a background search did not finish.
- The answer ends without a closing note listing mouse tumour records as entities named in the question.
- Why it matters: a dataset search that silently drops results, or that tells the person they asked about something they did not, both erode trust in the same way a wrong citation does.

### 66. Phenotypic features of a disease (12.14)

Queries to try:

- `What phenotypic features are associated with Marfan syndrome?`: one run settles it.

What you should see:

- This entry is deliberately open where the others are not.
- A question about the physical features of a disease no longer runs a search that could never return a row.
- Before 23 September this always answered "I could not find evidence", which reads as "nothing is known about this" and is false.
- The graph search behind it could never return a row, and it has been removed. What the question reaches INSTEAD was not verified end to end, so what a correct answer looks like here is the thing this test establishes rather than something it checks against.
- A refusal is worth reporting rather than passing. The open question is whether the question should reach MedGen through the live NCBI records instead, which is a routing decision rather than a defect.
- What it answers today, from the second tester's fix-2 screenshots: Plain language "Found 1 disease record, 37 sequence variant records and 3 gene records for Marfan syndrome" and researcher "Found 1 disease record for Marfan syndrome: Marfan syndrome." No phenotypic feature is named. That is item 12.14, the one honest gap the overnight session of 2026-09-23 left, in the board's To do column.
- Why it matters: "I could not find evidence" about a disease whose features are thoroughly documented is the worst shape of wrong answer, because it reads as an authoritative statement that nothing is known.

### 78. The genes linked to MODY (11.20)

Queries to try:

- `What genes are associated with MODY?`

What you should see:

- The MODY genes named and cited: 6 MODY genes, the same six the product owner's reference prototype shows.
- The same set of sources when asked again. On develop, 5 of 5 repeated runs returned one source set.
- No grounding refusal. See Known already above for the grounding failure this question once had.
- Why it matters: MODY is a family of conditions a clinician works through gene by gene, so the answer has to name the genes, and the same genes every time.

### 79. Variant-to-disease tables (11.6)

Queries to try:

- `What diseases are caused by variants in the HNF1A gene?`, in either mode.

What you should see:

- Variant-to-disease and gene-to-disease tables over the graph's ClinVar links, in every mode.
- The HNF1A answer shows "Variant-to-disease mapping".
- When checked live on 2026-09-14 the table stopped at 5 rows where the reference prototype shows 13, because an answer cites at most 20 sources. Whether that ceiling is right is the product owner's call, a card in the board's To do column.
- Why it matters: a person asking which diseases a gene's variants cause wants the variant and the disease side by side, not two lists to match up themselves.

## 4. Chromosome windows and accessions

### 26. A copy number variant window, before the coordinate range feature

Queries to try:

- `What ACMG-relevant evidence is available for a copy number variant spanning chr17:43,044,295-43,125,364 on GRCh38?`

What you should see:

- A coordinate-only question about ACMG evidence, tested and approved on the morning of 22 September, before the coordinate range feature shipped that night.
- The answer asks the person to name a gene, variant, disease or organism.
- If instead it answers with the genes and records under the window, that is query 27 working as intended, not a defect: the coordinate feature shipped later the same day and changed this. Its current behaviour is query 27's.
- Why it matters: this was the honest fallback for a coordinate question the product could not yet resolve; keeping the record straight about when each behaviour was true stops a fixed feature being reported as broken.

### 27. The same window, with genes and overlapping records asked for by name

Queries to try:

- `What ACMG-relevant evidence is available for a copy number variant spanning chr17:43,044,295-43,125,364 on GRCh38? List the overlapping genes, dbVar records and ClinVar entries.`

What you should see:

- After the coordinate range feature, the same window resolves to real genes and records instead of asking for a gene.
- BRCA1 is named without the person having to name it themselves.
- dbVar and ClinVar records are among the sources, with working links.
- No request to name a gene, and no classification of the variant.
- Why it matters: a researcher pasting in coordinates from a lab report should get back what is actually under that window, not a request to already know the answer.

### 28. A window with no assembly named

Queries to try:

- `What is under chr17:43,044,295-43,125,364?`

What you should see:

- A coordinate window with no genome assembly stated is asked which one, rather than guessed.
- One question back: which assembly, GRCh38 or GRCh37, and why it matters.
- Why it matters: the two assemblies put different genes under the same numbers, so guessing which one the person meant risks a confidently wrong answer.

### 29. A CFTR-locus window

Queries to try:

- `What genes and ClinVar records are under chr7:117,480,025-117,668,665 on GRCh38?`

What you should see:

- A different chromosome window resolves to the right gene and its surrounding records.
- CFTR is named first, with CFTR-AS1 and CFTR-AS2 beside it.
- The literature and OMIM content is about CFTR, not an unrelated regulatory fragment.
- ClinVar and dbVar records for that stretch are among the sources.
- Why it matters: someone working on cystic fibrosis pastes in their own coordinates and must get CFTR, not whatever the product was first built against.

### 30. A BioProject accession with everything it links to (G-007)

Queries to try:

- `For BioProject PRJNA31257, list the BioSamples, the SRA runs and any genome assemblies, and tell me how to retrieve each.`

What you should see:

- An accession-only question is answered with the actual project record and what it links to, rather than a request for a gene.
- The project record (the Human Genome Project) is among the sources.
- Its BioSample, its SRA run SRR9496657, and its GRCh38.p14 assembly are each cited to the NCBI page it can be fetched from, with a working link.
- No request to name a gene.
- Why it matters: a person who already has an accession number from a paper or a database wants what that accession points to, not to be redirected into a gene search they did not ask for.

### 31. An accession NCBI does not have

Queries to try:

- `What is in BioProject PRJNA999999999?`

What you should see:

- An accession that does not exist is told so honestly, not answered as if it were a missing gene name.
- One line back: the accession was not found in NCBI, check it and ask again.
- Not a request to name a gene.
- Why it matters: a typo in an accession number is a different problem from an unrecognised question, and the response should tell the person which one they hit.

### 32. A BioSample accession and its runs

Queries to try:

- `What is BioSample SAMN12121739 and which SRA runs and assemblies come from it?`

What you should see:

- A BioSample accession resolves to its record and its SRA runs, the same way a BioProject accession does.
- The BioSample record and up to ten of its SRA runs are among the sources.
- No "which gene, variant or condition do you mean?" request.
- Why it matters: a person who already found a BioSample id in a paper or a database wants to know what came from that exact sample, not to be redirected into naming a gene they never asked about.

## 5. Pathogen isolates

This is the pathogen isolate search. It lets a person ask for the actual isolates behind a resistance question and get back a short list they can open:

- each linked to its NCBI Pathogen Detection page
- each showing its resistance genes
- plus an honest count of how many isolates matched and how many are shown

From the isolate document's own framing, the person asking is an outbreak or AMR researcher who wants:

- isolates they can open, each with its resistance genes and a link
- and an honest statement of how many there are and how many were shown

Run queries 33 to 44 in order: each builds a little on the last, which makes it easier to spot where something breaks. The full set of twelve queries and the workflow for running them is `testing/Product/queries/Isolate_search_queries_and_workflow.md`; each heading below names its isolate query number there.

### 33. The flagship question: E. coli and ESBL genes (G-035, isolate query 1)

Queries to try:

- `What Escherichia coli isolates in Pathogen Detection carry extended-spectrum beta-lactamase genes?`

What you should see:

- The flagship isolate search question, the one the product is measured on.
- A table headed "Isolates and their AMR genes" with 20 rows. Each row shows the isolate's BioSample accession, strain, and where and when it was collected, beside its gene list; every row carries a blaCTX-M gene, and each gene list is linked to that isolate's own Pathogen Detection page.
- The line "Pathogen Detection lists 140,476 Escherichia coli isolates with these genes; the first 20 in the snapshot are shown."
- A note saying only the blaCTX-M family of genes was searched for "extended-spectrum beta-lactamase", and why: a plain blaTEM or blaSHV gene name cannot be told apart from a genuine ESBL by its name alone, so those families were left out rather than risk a wrong label.
- E. coli named and linked to its NCBI Taxonomy record among the sources cited.
- The answer arrives well under a minute.
- Why it matters: an outbreak researcher needs isolates they can actually open and check, not a summary that hides how the gene family was interpreted.

### 34. The same question on Salmonella (isolate query 2)

Queries to try:

- `Which Salmonella isolates in Pathogen Detection carry ESBL genes?`

What you should see:

- The isolate search works for an organism other than E. coli, with the same shape of answer.
- The same shape as query 33: a list of isolates with accession, strain, collection details, resistance genes and links, an exact count, "showing the first 20", and the same disclosure that only the blaCTX-M family was searched.
- Salmonella named and linked to its own NCBI Taxonomy record, not E. coli's.
- Why it matters: a search that only works for one organism is not a general capability, it is a demo, and a researcher working on Salmonella needs the same trustworthy answer as one working on E. coli.

### 35. An exact gene, one allele only (isolate query 3)

Queries to try:

- `Which Salmonella isolates carry blaCTX-M-15?`

What you should see:

- Naming a specific gene, rather than a family word, searches for that gene and nothing broader.
- Every isolate shown carries a gene starting with blaCTX-M-15, not a different CTX-M number and not a different gene family: blaCTX-M-15 itself, never blaCTX-M-155.
- The count and the "first 20 shown" note, same as the other queries. The count reads 2,678.
- No mention of other ESBL families, since none were asked for.
- Why it matters: naming an exact gene is a precise request, and returning isolates carrying a different allele would be a quiet substitution the person did not ask for.

### 36. Carbapenemase genes in Klebsiella (isolate query 4)

Queries to try:

- `Which Klebsiella isolates in Pathogen Detection carry carbapenemase genes?`

What you should see:

- A different resistance family, on a different organism, still returns real isolates.
- Isolates carry at least one of the carbapenemase families (blaKPC, blaNDM, blaOXA-48, blaVIM, blaIMP), each with its full gene list and a link to its Pathogen Detection page, and the answer names which gene prefixes it searched.
- An exact count, reading 88,025, and the first-20 note.
- Why it matters: carbapenemase resistance is one of the most clinically serious findings in this domain, so this answer's accuracy matters more than most.

### 37. Colistin resistance in E. coli (isolate query 5)

Queries to try:

- `Which E. coli isolates in Pathogen Detection carry colistin resistance genes?`

What you should see:

- A differently named resistance mechanism, a plasmid-mediated gene rather than a beta-lactamase, still resolves correctly.
- Isolates carrying an mcr gene, listed with their full gene set and a link to each isolate's page.
- The answer names the mcr gene prefixes it searched.
- An exact count and the first-20 note.
- Why it matters: colistin is a drug of last resort, so someone checking for resistance to it needs the same careful answer they would get for a better-known gene family, not a special case that only works for ESBL.

### 38. A gene nothing in this organism carries (isolate query 6)

Queries to try:

- `Which Listeria isolates in Pathogen Detection carry blaKPC?`

What you should see:

- A real, well-formed gene question that has zero matches gets an honest zero, not a refusal.
- The plain statement "Pathogen Detection lists 0 Listeria isolates with these genes," not "I could not find information on this."
- No isolate rows, since there are none to show.
- No suggestion that the search failed or was refused, and no request for a gene name. It ran, and the true answer is zero.
- Listeria cited to NCBI Taxonomy.
- Why it matters: a true zero and a failed search look identical if the product does not say which one happened, and telling them apart is the difference between "there is nothing here" and "the tool broke".

### 39. An organism Pathogen Detection does not cover (isolate query 7)

Queries to try:

- `Which tomato isolates in Pathogen Detection carry resistance genes?`

What you should see:

- Asking about an organism outside Pathogen Detection's scope gets an honest explanation, not an empty or invented result.
- One question back: Pathogen Detection is searched one organism at a time, which organism do you mean, with a few it covers named in words (Escherichia coli, Salmonella, Listeria monocytogenes, Klebsiella pneumoniae, Campylobacter).
- The answer does not claim to know whether "tomato" is or is not in Pathogen Detection. It only recognises the organisms it can search, so it asks rather than asserts.
- No isolate rows and no invented data.
- Why it matters: a product that confidently states an organism is not covered, when it actually has no idea, is guessing dressed up as knowledge.

### 40. An organism named with no gene (isolate query 8)

Queries to try:

- `Which E. coli isolates are in Pathogen Detection?`

What you should see:

- Naming an organism but no resistance gene or family asks a clarifying question rather than dumping every isolate.
- The answer asks which resistance gene or gene family to search for, with ESBL, carbapenemase, colistin and a gene name offered as examples, rather than listing anything.
- No attempt to return all E. coli isolates. The exact number in the snapshot, in the hundreds of thousands, is never shown as a result list.
- Why it matters: dumping hundreds of thousands of rows because a question was underspecified would bury the person in noise instead of helping them narrow their question.

### 41. A follow-up asking to filter by year (isolate query 9)

Queries to try:

- After query 33, ask `Show me the ones from 2023`: finish query 33, type the follow-up, Search.

What you should see:

- A follow-up after an isolate search carries the organism and gene forward, and is honest about what it can and cannot do yet.
- Honestly stated for the first version: a year filter is not built, and a follow-up does not yet carry an isolate search forward the way it carries a gene forward.
- The answer asks which organism to search, or which gene, rather than pretending to filter.
- It never repeats the same full list as if it had been filtered to 2023, and never invents a filtered list.
- If the answer instead lists 2023 isolates that were genuinely filtered, that is a later version working, not this one; note it as a pleasant surprise rather than a pass.
- Why it matters: a follow-up that silently ignores part of the question, while looking like it answered it, is more dangerous than one that admits it cannot filter yet.

### 42. The existing single-isolate lookup still works (isolate query 10)

Queries to try:

- `What is known about Salmonella isolate SAMN02147118 in Pathogen Detection?`

What you should see:

- The older, single-isolate mode of this tool is not broken by adding isolate search.
- A single isolate's details: its strain, where and when it was collected, its resistance genes, and a link to its Pathogen Detection page.
- No mention of "showing the first 20" or a count of isolates, since this is a single-record lookup, not a search.
- Why it matters: adding a new search mode should never break the lookup someone was already relying on.

### 43. The wait feels alive (isolate query 11)

Queries to try:

- `Which E. coli isolates in Pathogen Detection carry ESBL genes?`: watch the progress screen while it runs.

What you should see:

- The person is not staring at a frozen screen while the search runs.
- The progress steps show the pathogen search running, with continuous motion, not a blank pause.
- The answer arrives and builds on screen; nothing about the wait looks stuck or broken.
- Why it matters: the search reads a very large file, which takes real time, and a frozen-looking screen during that time reads as a crash even when the search is working fine.

### 44. The shortest version a person would type (isolate query 12)

Queries to try:

- `ESBL E. coli isolates?`

What you should see:

- A terse, minimally worded question with only "ESBL" as the clue still works.
- The same shape of answer as query 33: isolates listed with genes and links, an exact count, the first-20 note, the disclosure that only blaCTX-M was searched, and E. coli's Taxonomy record cited.
- The short, informal phrasing is understood the same way as the fully worded question in query 33.
- Why it matters: most people type the short version of a question, not the fully worded one, so the product has to understand both.

What the answer must never do, from the isolate document, applies to every query in this section:

- Never list a blaTEM-1 carrier as an ESBL isolate. blaTEM-1 is a plain, broad-spectrum gene, not an extended-spectrum one, and stating otherwise would be a confident wrong record.
- Never claim a total number of isolates it did not actually count. If the scan was cut off before finishing, the answer says "at least" that many, never a bare exact number it cannot back up.
- Never link an isolate to any page outside NCBI.
- Never answer from memory when the search returned nothing. A true zero is stated as a true zero, and an organism or gene Pathogen Detection genuinely lacks data for is named as such, never papered over with a guess.
- Never show a bare `SAMN` accession as an isolate's only name when it has a strain name. The strain name comes first, with the accession alongside it.

## 6. Refusals, off-topic and compute requests

### 45. An off-topic question (Product test 8)

Queries to try:

- `What is the capital of France?`

What you should see:

- The product refuses rather than making something up.
- A refusal box with a calm grey label reading "Outside biomedical research".
- A short sentence explaining the refusal.
- No red "Not verified" or "Not fully grounded" pill.
- No error styling.
- Never an invented answer.
- Why it matters: a product that stays quiet about what it cannot do, rather than guessing, is one a person can trust when it does answer.

### 46. A question with no data (Product test 19)

Queries to try:

- `Which diseases are associated with the gene FAKEGENE99?`

What you should see:

- When NCBI has nothing, the product says so instead of inventing an answer.
- A refusal box with the grey label "No answer found in NCBI records".
- A plain sentence saying nothing was found.
- A clickable NCBI search link.
- No diseases listed.
- No citation chips.
- No red "Not verified" or "Not fully grounded" pill.
- Why it matters: a made-up gene name is exactly the kind of input a careless system would hallucinate an answer for, so this is the test that proves it will not.

### 47. Compute requests are turned away (G-046, G-047)

Queries to try:

- `BLAST this sequence against nr and tell me the top hit: ATGGATTTATCTGCTCTTCGCGTTGAAGAAGTAC`
- `Here is my VCF file, tell me which variants are concerning.`

What you should see:

- A request for a capability the product does not have, sequence matching or file analysis, is refused with a clear reason rather than answered from whatever disease-sounding words appear in the wording.
- Both are turned away with a message saying the capability does not exist and where to run a sequence search: the compute message.
- Neither is answered from disease terms found inside the wording, which is what used to happen.
- Why it matters: a person pasting in a sequence or a VCF file wants to know the product cannot do that, immediately, rather than getting a confident-sounding answer built on the wrong reading of their question.

### 48. A question the product could not read (12.6)

Queries to try:

- Any text naming no recognisable gene, variant, disease or organism, for example `qwerty asdf zxcv`.

What you should see:

- A question the guardrail cannot parse into a gene, variant, disease or organism is answered with a request for one, instead of a dead end.
- The answer reads "I could not tell which gene, variant, disease or organism you mean. Name one and I will search."
- Why it matters: telling someone exactly what to type next turns a dead end into a next step, which is the difference between a refusal that helps and one that just stops.

## 7. Sign in, sessions and history

### 49. Log in and log out (Product test 3)

Queries to try:

- No query of its own: click "Log in" at the top right, enter a new email and a password, Log in, reload the page, run query 1, click "Integrations" in the top bar, click your email at the top right, Log out, click "Log in", enter the same email and password, Log in.

What you should see:

- One Log in button creates an account for a new email, and logging out goes to the home page.
- A sign-in screen titled "Log in" that says a new email creates your account, with one button and no Sign up button.
- After the first Log in, the top right shows your initials and email instead of "Log in".
- Clicking your email opens a menu with your email, "Signed in", "API key and integrations", "Documentation" and a red "Log out".
- Search and follow-ups work the same as queries 1 and 20.
- Log out, even from the Integrations page, lands on the search home page, with the previous conversation gone.
- Logging back in with the same email and password shows your email at the top right again.
- After a reload you stay signed in.
- Why it matters: a person's account should feel like theirs, the same every time they come back, and logging out should leave nothing of the previous conversation behind.

### 50. A wrong password gives a clear message (Product test 5)

Queries to try:

- No query of its own: click "Log in", enter your account's email with a wrong password, Log in, fix the password, Log in.

What you should see:

- A wrong password shows a clear message, and the form still works afterwards.
- "That password does not match this email. Check it and try again."
- Your email stays filled in, and the corrected password logs you in.
- No raw error codes or technical messages.
- Why it matters: a raw error code tells a person nothing about what to fix; a plain sentence does.

### 51. Search history (Product test 6)

Queries to try:

- Any two questions: log in, run 2 different searches, look at "Your searches" on the left, click an older one, click "Hide your searches", then "Show your searches".

What you should see:

- A signed-in user can see and re-run earlier searches.
- Both searches are listed.
- Clicking one shows the answer that search already gave, at once, with a Run again button beside it. Query 67 covers that in full; what clicking an older search does changed on 23 September.
- The panel hides and comes back.
- Guests see no history panel.
- Reload the page: you stay signed in and both searches are still listed.
- Why it matters: a researcher tracking down the same gene across several sessions needs to find their earlier questions without re-typing them from memory.

### 52. Search limit shown to a signed-in user (Product test 18)

Queries to try:

- No query of its own: log in, click your email at the top right, look at the bottom of "Your searches".

What you should see:

- A signed-in user sees their own search limit, and it is true.
- The menu reads "Signed in", followed by your search limit.
- The bottom of the history panel names your account and your search limit.
- No "unlimited" claim anywhere.
- Why it matters: a person should be told their real limit rather than an inflated or absent one, so they are not surprised when they hit it.

### 53. Guest limit of 5 searches, removed (Product test 4, 1.1)

Queries to try:

- None. Removed on 2026-09-12. Set 1 took away the guest limit, so there is nothing left to test here.

What you should see:

- Query 1 now covers searching as a guest, with no count and no sign-in card however many searches are run.

### 54. Guest searches moving into a new account, removed (Product test 16, 1.2)

Queries to try:

- None. Removed on 2026-09-12.

What you should see:

- With no guest limit, there is no guest allowance to move into an account.

### 55. Too many guest attempts, removed (Product test 20, 1.3)

Queries to try:

- None. Removed on 2026-09-12. Set 1 took away the ten-attempt guest limit.

What you should see:

- Query 45, the off-topic question, still covers a question being refused.

### 67. A past search reopens with the answer it gave (10.2, 12.13)

Queries to try:

- `What Escherichia coli isolates in Pathogen Detection carry extended-spectrum beta-lactamase genes?`, as the example whose answer has a table: sign in, ask the query above, wait for the answer, start a new search, then click that first question in "Your searches".
- `Which diseases are associated with BRCA1?`, asked in the same tab: signed in, ask it, wait for the answer, then click it in the history rail straight away.
- Query 51 covers the rail itself.

What you should see:

- Clicking a search in the history rail shows the answer already given, at once, instead of paying for a second one.
- The answer you already got appears AT ONCE, with no progress screen and no wait.
- It is marked "Saved answer, asked <date>", carries its own trust line, and has a Run again button beside it.
- Check a question whose answer had a TABLE, such as an isolate question: the table renders as a table, not as rows of pipes or pipe characters. This is where a mistake would show, since the backend, the screen and the seam between them were built separately.
- Run again does a fresh search, charged to you as a normal search.
- On the search asked in the same tab, it does NOT search again: the source count and the text must match what you just read. The product owner reported on 2026-09-23 that clicking a past search re-ran it instead of showing the saved answer; a search asked in the same tab never got marked as saved, and the second search showed 22 sources against the original 23.
- Guests do not get this. The account is what stores the answer, and deleting the account deletes it with them.
- Why it matters: clicking your own earlier question, being charged a second search for it, and waiting thirty seconds to read something you already read is the kind of small dishonesty that makes a history rail feel like decoration rather than a record.

## 8. Stop, feedback and the connection

### 56. Stop a search (Product test 9)

Queries to try:

- `Which diseases are associated with BRCA1?`: Search, press Stop while the progress screen is running.

What you should see:

- A search can be cancelled mid-way.
- The progress steps disappear.
- A "Search stopped" message appears.
- Two buttons appear: "Run again" and "New search".
- Clicking "Run again" asks the same question again from the start.
- Clicking "New search" returns to the home page.
- No answer appears from the stopped search.
- Why it matters: a person who changes their mind mid-search should not have to wait out a search they no longer want.

### 57. Feedback on an answer (Product test 10)

Queries to try:

- Any question: get any answer, click "Not helpful", pick a reason such as "Wrong answer", type a comment, Send feedback, on a source click "Flag: does not support".

What you should see:

- A reader can rate an answer and flag a bad source.
- Reasons appear only after "Not helpful", never after "Helpful".
- Sending confirms that it went through.
- The source changes to "Flagged".
- Why it matters: flagging a bad source is how a real reader tells the product it got something wrong, and that channel only works if it visibly confirms it was heard.

### 58. Feedback when the connection drops (Product test 21)

Queries to try:

- Any question: get any answer, click "Not helpful", pick a reason and type a comment, turn off Wi-Fi, Send feedback, turn Wi-Fi back on, Retry.

What you should see:

- Feedback written is not lost if sending fails.
- Your reason and comment stay on screen with a Retry button.
- Retry sends it once you are back online.
- Why it matters: losing a thoughtful piece of feedback to a dropped connection would discourage anyone from bothering to give it again.

## 9. Screens, phone width, the tour and the disclaimer

### 59. Other pages and phone width (Product test 11)

Queries to try:

- No query of its own: click Integrations, About, press the browser back button, on Integrations click a copy button, back on About scroll to the bottom and click "Explore the architecture", make the window phone-narrow or open the site on your phone, open "More pages", log in, tap the searches button at the top right.

What you should see:

- Navigation works, including on a phone.
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
- The home page sits on the light grey background between the blue header and footer, with dark text, a bordered white search bar and white chips (item 2.8).
- The home page search box shows about 240 characters without scrolling and grows as you type. A square blue button with a white up arrow sits in its bottom right corner and searches (item 2.12).
- The browser tab shows the helix logo on the header blue, with the tab title "NCBI Agentic Search" (item 2.14).
- Why it matters: a person on a phone in a lab or a clinic should get the same working product as one at a desk, not a broken layout.

### 60. Open the Integrations page and paste the MCP configuration (11.30)

Queries to try:

- No query of its own: open the Integrations page, read the printed MCP configuration, and click its copy button.
- If you have an MCP client, paste the configuration into it exactly as printed and use it.

What you should see:

- The MCP configuration printed on the Integrations page is complete and copies cleanly. This is only what the product owner can judge by eye; whether it actually connects end to end is a developer check, see Workflow for the developer below.
- The configuration is printed on the page.
- The copy button copies it.
- Pasted as printed, it works without editing, and it never sends you to an `http://` address.
- The address it prints no longer drops the s from https. Before 23 September a request to it was answered with a redirect to an `http://` address, which a client would follow with its token in the clear.
- The end-to-end half is already proven live on develop by the developer check below, which is why this is the one item of the 23 September set that did not need a signed-in session to verify.
- Why it matters: a developer following printed setup instructions should not have to debug the instructions themselves before they can use the integration.

### 61. The disclaimer (Product test 15)

Queries to try:

- No query of its own: open the site as a guest, try to click past the disclaimer or press Escape without ticking the box, tick the box, Continue, log in, Log out.

What you should see:

- Nobody can use the product without accepting the disclaimer.
- The disclaimer is a wide box titled "Important medical disclaimer" with a bold opening sentence, a paragraph advising you to seek your physician's advice, and a notice box titled "Prototype".
- The continue button runs the full width of the box, reads "I understand, continue to the research tool", and stays greyed out until the box is ticked.
- Escape does not close it.
- After ticking and Continue, the product opens.
- It does not come back while you use the site, and it appears again after Log out.
- Why it matters: this is the one screen standing between a person and a research prototype that must never be mistaken for medical advice, so it cannot be skippable.

### 62. A page address that does not exist (Product test 17)

Queries to try:

- No query of its own: open the site's address with `/nonsense` added to the end.

What you should see:

- A mistyped address does not break the site.
- You land on the Search page, not a blank or error page.
- Why it matters: a broken link or a typo should never leave a person staring at a dead page with no way forward.

### 63. The guided tour (Product test 22)

Queries to try:

- The tour runs the BRCA1 question for you: open the site in a private window, tick the disclaimer, Continue, on the home page under the suggested questions click "Start the tour", read each card and press Next, on step 7 click "Run it for me", wait for the answer, press Next to the end, Done, click the "Take the tour" button under the suggested questions on the home page.

What you should see:

- A first-time visitor can take a tour of every feature that ends with a real answer.
- A card reads "New here? Take the two-minute tour" with "Start the tour" and "Not now". "Not now" removes it for good on this browser.
- The tour has nine steps with a "Step n of 9" counter, highlighting the question box, the answer depth, the suggested questions, the scientist name, the top bar, and Log in.
- Step 7 fills the question box with the BRCA1 question and runs it; Stop stays reachable.
- Steps 8 and 9 point at the citation chips, the sources, and the follow-up field. Done closes the tour.
- If the system refuses the question, the tour says so and ends with Done.
- Escape closes the tour at any point. "Take the tour" starts it again any time.
- At phone width the card sits at the bottom of the screen and nothing scrolls sideways.
- Why it matters: a first-time visitor who does not know what to ask should be able to see the whole product work end to end without having to guess a good question first.

## 10. Questions with no gene and no disease in them

Added 2026-09-23 from `testing/User-feedback/`, a second tester's session on the 2026-09-14 build. They had never seen the product and asked what a person actually asks. Six of their seven questions returned nothing. All seven answer now, and these queries are how that stays true. That is the largest change in behaviour to check and the one a person feels first.

Ask these in a FRESH session, as "Before you start" says. THE SEVEN QUESTIONS FROM `testing/User-feedback/`, which is where your skip manager's screenshots live. Ask each one and expect a cited answer, not a refusal:

- `reflux disease`, query 68
- `GERD`, query 68
- `Any trials for GERD?`, query 68, expecting real ClinicalTrials.gov studies
- `papers on the effects of caffeine on exercise performance`, query 69
- `Does coffee help make exercise more effective?`, query 73
- `Are there any beneficial variants typically found in people of mediterranean descent?`, queries 69 and 73
- `What positive and negative genes do ashkenazi jewish people have?`, query 73

All seven answered when measured on 2026-09-23. Before that day one answered and six returned nothing.

Since 2026-09-24 a bare `reflux disease` or `GERD` that opens a conversation is first asked what you want to know about it, with choices written for that subject (query 76). That is a question back, not a refusal; picking a choice runs it.

### 68. A condition, asked by its common name and by its abbreviation (12.1)

Queries to try:

- `GERD`, then `reflux disease`, then `Any trials for GERD?`, each as a new search.

What you should see:

- The same condition answers whichever name a person uses.
- All three answer with cited records rather than "I could not find grounded evidence for this". The two bare names are asked back first (query 76); pick a choice.
- The trials question returns real ClinicalTrials.gov studies, each linked to its own study page.
- The abbreviation and the full name both work. Before 2026-09-23 `reflux disease` answered and `GERD` refused, because one name landed on concept ids the graph holds and the other did not, and nothing else was searched.
- Why it matters: a person types whichever name they know. A product that answers one and refuses the other looks broken in a way they cannot diagnose, and they will not think to try a synonym.

### 69. A question about a chemical, a food or a population (12.7)

Queries to try:

- `papers on the effects of caffeine on exercise performance`, then `Are there any beneficial variants typically found in people of mediterranean descent?`: ask each as a new search, in a FRESH session or at least not straight after a gene question.
- On the caffeine question, read the list of papers.

What you should see:

- A question that names no gene and no disease still finds the published literature.
- Cited papers, each linked to its own PubMed page, rather than a request to name a gene.
- Each paper appears ONCE in the list. Before 2026-09-23 five papers rendered as ninety-one rows with the same title repeating, fifteen times, in a 932-word answer. It is 101 words now.
- The answer reports what has been published. It never gives a verdict of its own.
- On the caffeine question the papers should be about caffeine and exercise, for example the sports nutrition position stand, not about something adjacent.
- Why it matters: the product has a gene resolver and a disease resolver, so a question naming a chemical or a population used to reach nothing at all. Most questions a non-specialist asks are this shape.

### 70. The same question in lower case (12.2)

Queries to try:

- `any trials for gerd?` in LOWERCASE, then `recent papers on statins`, then `what does the literature say about metformin`, then `is there a trial recruiting for melanoma`, each as a new search.

What you should see:

- Capitalisation does not decide whether a question is medical.
- Each is accepted and searched.
- None is answered with "This looks outside biomedical research. I can help with a gene, variant, pathogen, or paper question."
- Before 2026-09-23, `Any trials for GERD?` was accepted and `any trials for gerd?` was refused, because the capitals matched a gene-symbol pattern rather than because the question was understood. Capitalisation decided whether a question was medical.
- `is there a trial recruiting for melanoma` was refused the same way before 2026-09-23, and answers with real ClinicalTrials.gov studies now.
- Why it matters: a person who types in lower case, or whose question names no gene in capitals, was being told their subject was outside biomedical research. That reads as a statement about their field, not about the product.

### 71. What sits under an answer that found nothing (12.4)

Queries to try:

- `What variants cause ZZZFAKE1?`: ask it, wait for the refusal, then read everything below the refusal block.

What you should see:

- A refusal does not invite the reader into a conversation that has nothing in it.
- The heading under the refusal reads "Ask another question", not "Continue this conversation".
- The three suggestion chips ("What variants cause it?", "Which trials are recruiting?", "What does the literature add?") are GONE. There is no "it" to refer to.
- The field to type your next question is still there.
- On an answer that DID find something, the heading and all three chips are unchanged.
- Why it matters: the tester's own words were "If it didn't have an answer, why would I 'continue the conversation'? Maybe 'ask another question?'". Pressing the first chip sent a question about an "it" with no antecedent, so the product then asked them which gene they meant: its own suggestion walked them from one dead end into another.

## 11. Answers that answer the question

Items 12.3 and 12.9 to 12.12 were raised on 2026-09-23. They came from the second tester's two rounds of screenshots, and from the two questions the product owner asks of every answer:

- Did it provide the information?
- Did it answer the question?

Their records are in `testing/UI_fixes_done.md`.

### 72. Plain language and researcher mode read differently on every question (12.9)

Queries to try:

- `Any trials for GERD?` in Plain language, then in Researcher.
- Any paper question at both depths, such as `recent papers on statins`.
- `What phenotypic features are associated with Marfan syndrome?`, asked once in Plain language and once in Researcher: ask it in Plain language mode, New search, switch to Researcher, ask it again. Its content is item 12.14's open gap (query 66), so read it for the difference in wording.

What you should see:

- The two answer modes still change how a real answer is written, not just its length, once depth is measured on an answer that previously refused outright.
- Plain language opens "I found 5 clinical trials related to GERD" with a list of titles under "Where this answer comes from".
- Researcher opens "Found 5 clinical trial records for GERD: ..." with a table that has an identifier column.
- Both depths list the same records.
- The two answers read differently. Plain language uses simpler, everyday wording.
- Researcher mode reads more technical, and is not thinner in substance than the plain language version.
- Measured on all 12 full feedback questions, every one differs by depth.
- Why it matters: a student and a clinician asking the same disease question still want different depth, and this question could not be used to check that until the refusal behind it was fixed.

### 73. A question with no gene or disease is answered, not just listed (12.10)

Queries to try:

- In Plain language, each as a new search: `Does coffee help make exercise more effective?`, then `What positive and negative genes do ashkenazi jewish people have?`, then `Are there any beneficial variants typically found in people of mediterranean descent?`, then `GERD`.

What you should see:

- An answer to a question naming no gene and no disease actually answers the question in plain sentences drawn from the cited papers, rather than handing back a bare list of titles.
- The coffee question's opening paragraph states what the published evidence reports about caffeine and exercise performance, in plain sentences, never a yes-or-no verdict or advice, each sentence cited. No sentence opens "Yes," or "No,".
- The ashkenazi question's opening paragraph names the genes the papers actually name, such as BRCA1, BRCA2 and APC I1307K, each cited.
- The Mediterranean question names Familial Mediterranean fever and the MEFV gene.
- Neither answer reads "Found 5 pubmed records:" followed only by a list of titles with no explanatory sentence.
- The opening count matches the list under it.
- How it is checked: code checks each quote is really in its record, and that the numbers and any "not" match. Then a second, cheap model checks each reworded sentence against the exact words it quotes.
- Known: two of six live reruns fell back to a list of papers, once because the checking model's call failed. That is the check refusing to guess, not a crash; report it if you see it often.
- A bare `GERD` opening a conversation is asked back first (query 76).
- Why it matters: a person asking a plain-language question wants the answer, not a bibliography they have to read themselves.

### 74. The sources count agrees with what is shown (12.11, 12.8)

Queries to try:

- Any answer, for example `Which diseases are associated with BRCA1?`, `GERD` or `recent papers on statins`: get an answer, read the "Based on N sources" line under the answer, then count the SOURCES section on the page.

What you should see:

- The "Based on N sources" trust line names the same number as the SOURCES section on the page.
- The two numbers are the same.
- Before, `GERD` read 14 against 12 and `recent papers on statins` read 6 against 5. Earlier still, the trust line undercounted, reading "Based on 1 source" beneath five cited papers; item 12.8 fixed the undercount and item 12.11 the remaining disagreement.
- Why it matters: two numbers on the same screen disagreeing about the same count undermines trust in both of them, not just the wrong one.

### 75. A papers list reads as clean prose, with no record repeated (12.12)

Queries to try:

- `papers on the effects of caffeine on exercise performance`, then `recent papers on statins`: ask each, then read the whole answer closely.
- `GERD` in Researcher, then in Plain language.

What you should see:

- A papers-based answer carries no leftover formatting defects and lists each record once.
- No paragraph starts with a lowercase letter ("so that clinical judgment ...") or a stray quote mark.
- No paragraph reads "Another is titled ..." with no first paper named before it.
- No restatement paragraph ("One is titled X. Another is titled Y"). A paper may appear twice, in the opening sentence and in the list, never three times. Measured 2026-09-23: twice is what ships today.
- `GERD` in Researcher carries prose on symptoms, complications and treatment above the list, and is longer than the Plain language answer. A bare `GERD` opening a conversation is asked back first (query 76).
- Why it matters: a reader who spots the same paper named three different ways in one answer stops trusting the answer was actually checked before it was shown.

### 76. A one-to-three-word question is asked back (12.3)

Queries to try:

- `reflux disease`, then `GERD`, then `BRCA1`, each as a new search in a fresh conversation. Then `Any trials for GERD?` and `What is GERD?`.
- `Marfan` and `papers on caffeine`, each as a new search in a fresh conversation.
- Short follow-ups inside a conversation, for example `and BRCA2?` after a BRCA1 answer.

What you should see:

- A very short question gets a clarifying question with choices, instead of an answer built on one silent guess at what it meant.
- The first three are asked back: "What would you like to know about ...?" with a few questions to pick from, written for that subject by a classifier model rather than a fixed list: symptoms and treatments for a condition, linked diseases and variants for a gene. Picking one runs that question.
- `Marfan` is asked back too.
- `Any trials for GERD?` and `What is GERD?` are answered, not asked back: they say what they want. So is `papers on caffeine`.
- A short follow-up inside a conversation is answered, since the conversation already says what it is about.
- Known: a model makes the call, not a list, so a borderline word such as `MeSH` can go either way (asked back 2 times in 3).
- Why it matters: the product owner's words, approving it on 2026-09-23: "If clarify needed -> yes approved". A two-word question like `reflux disease` could mean its symptoms, its trials or its genes, and answering one silent reading of it hides the other three from the reader.

## 12. The overnight build of 2026-09-25

Built overnight from the board's To do column, by the plan in `testing/Overnight_build_plan_2026-09-25.md`. Everything here is on develop only. If you do not like it, `python3 testing/Developer/scripts/bin_overnight.py --all --yes` puts develop's product code back exactly as it was before the night.

### 80. A good question is not refused at the think step (12.17)

Queries to try:

- `Does coffee help make exercise more effective?` at Researcher depth, three times, each as a new search.
- `is there a trial recruiting for melanoma` at Researcher depth, three times.

What you should see:

- Each is answered every time.
- Never a refusal that says the plan tier's response did not match the think classification.
- Why it matters: both questions failed about twice in forty live runs, and the reader saw a refusal for a question the product answers on every other run. The think step now repairs a mislabelled field and retries with the error when a reply is malformed, and never guesses a classification.

### 81. A question about a disease's features names them (12.14)

Queries to try:

- `What phenotypic features are associated with Marfan syndrome?` at Plain language.
- The same question at Researcher.
- `What is Marfan syndrome?` at Researcher, to check it still opens on what the disease is.

What you should see:

- At Plain language, the answer names several of the features MedGen lists for Marfan syndrome, for example aortic regurgitation, arachnodactyly or ectopia lentis, each cited to MedGen.
- At Researcher, a section "Clinical features MedGen lists for Marfan syndrome" lists them, each cited to MedGen, with its HPO id. It says how many of how many are shown when the list is cut.
- Known: at Researcher the written answer above the list may not name the features. Setting aside room for them in every disease answer pushed other answers' definitions out, so it was withdrawn; the follow-up, doing it only when a question asks about features, is a To do card.
- Known: the written answer names the first features MedGen lists, which are not always the most important. Aortic root aneurysm is in the list, not always in the sentences.
- Why it matters: this question used to answer with variant and gene records, a confident answer of the wrong kind.

### 82. An answer can cite up to 30 sources (cards 6 and 43)

Queries to try:

- `What does the literature say about MTHFR C677T?` at Researcher.
- `Which diseases are associated with BRCA1?` at Researcher.

What you should see:

- The count of sources can go past 20, up to 30, where before every answer stopped at 20.
- The note saying the answer was cut short appears on fewer answers than before.
- Why it matters: 24 of 30 live answers used to hit the 20-source ceiling and tell the reader the answer was incomplete. Your decision of 2026-09-25 raised it to 30, and the two limits behind it were raised so the 30 takes effect on paper questions too.

### 83. A question the word list does not know is judged, not refused (Jev as the classifier)

Queries to try:

- `Tell me about the tree of life`, as a new search.
- `what is the best pizza in Chicago`, as a new search.
- `Which diseases are associated with BRCA1?`, then as a follow-up in the same conversation `is it good with pizza?`, then `and what about it in children?`.
- `make me a weekly workout plan`.

What you should see:

- The tree of life is answered, from NCBI's records, where before it was refused as off topic.
- Pizza is refused, with today's wording. So is the pizza follow-up, and the workout plan.
- `and what about it in children?` after BRCA1 is answered: a follow-up on the same subject is on topic.
- Known: an off-topic follow-up that happens to contain a biomedical word such as "cell" or "study" can still get through, as it did before tonight. A To do card.
- Why it matters: a word list decided what was on topic and refused anything it did not recognise. Jev, the decision model you chose, now makes that call for any question the list does not recognise; the list can still let a clearly biomedical question straight through.

### 84. "Recent papers" asks how far back (12.15)

Queries to try:

- `recent papers on statins`, then pick "the last 5 years".
- `papers on statins since 2022`.
- `recent-onset diabetes treatment`.

What you should see:

- `recent papers on statins` asks "How far back should I search?" with the last 12 months, the last 5 years and the last 10 years. Picking 5 years returns only papers from those years.
- `papers on statins since 2022` is not asked back.
- `recent-onset diabetes treatment` is not asked back: "recent" there describes the disease, not the papers.
- Known: after develop restarts or redeploys, a choice clicked on an earlier question searches without the year limit.

### 85. Whether a question wants papers is a classifier's choice (12.16 part 3)

Queries to try:

- `papers on caffeine`.
- `what does the literature say about MTHFR`.
- `What is GERD?`.

What you should see:

- The first two are treated as questions about papers and answer with papers.
- `What is GERD?` answers about the condition, not only with papers.
- Why it matters: a fixed list of words such as "paper" and "article" decided this before; your rule is that decisions are not hardcoded.

### 86. The Answer modes card says what each mode gives, one block each (13.2)

Where to try it: the search page, the circled "i" beside Plain language and Researcher. No question needed.

What you should see:

- The card titled "Answer modes" shows "Plain language:" set apart, then "the answer in simple terms, easy to understand."
- Below it, "Researcher:" set apart, then "the answer in technical terms, with the specifics and the records listed or in tables."
- Last, on its own line: "Both modes cite every claim. A change applies to your next question."
- Nothing in the card describes who the reader is.
- On a phone, 390 pixels wide, the card opens fully on screen; before this fix it ran off the right edge.
- The onboarding tour's step about the two modes says the same in one sentence.

## Workflow for the product owner

1. Open the develop app: <https://search-agent-web-develop-2aeb.up.railway.app>
2. Sign in with your usual account, or test as a guest for the queries that call for it, in a private or incognito window.
3. Start with the Retest column of `testing/UI_fix_plan.md`, or run the queries in this document in whatever order you like. They are grouped by feature area, and each section stands on its own.
4. For the pathogen isolate section, queries 33 to 44, run them in order: each builds a little on the last, which makes it easier to spot where something breaks.
5. Screenshot the answer for anything that looks wrong, and especially the honest-zero, unsupported-organism, and clarifying-question cases, since these are the ones most likely to go wrong quietly.
6. Drop screenshots and notes in `testing/Product/feedback/inbox/`. Put the query number in the filename if that is convenient.
7. Say "check the inbox" when you are done, and the findings will be picked up from there.

## Workflow for the developer

The automated checks behind these queries, and the live proof that backs the isolate search in particular:

- `tests/system_03_search_agent/tools/test_pathogen_detection.py`: unit tests for the isolate search mode of the tool itself.
- `tests/system_03_search_agent/tools/test_pathogen_detection_premise.py`, run with `RUN_PREMISE_GATE=1`: the live premise gate against the real Pathogen Detection FTP snapshot.
- `tests/system_03_search_agent/core/test_isolate_search.py` and `test_isolate_search_wiring.py`: the agent-loop side, how Think, Plan, Act and Write handle an isolate search question.

For a live proof against develop itself:

- Use the consistency runner at `testing/Developer/reports/2026-09-22_10.3_consistency/run_consistency.py` with `--ids G-035`, and run three passes.
- Keep the laptop awake with `caffeinate -i` for the duration.
- Do not run any other live measurement against NCBI at the same time. The E-utilities and Pathogen Detection rate pools are shared, and a second live check running in parallel can trip both.

The evidence folder for that run must contain:

- `runs.jsonl`, the raw pass-by-pass record
- a `raw/` folder, the full response bodies
- a `findings.md` that states its verdict in the first line, before any detail

Two developer-side facts from 23 September:

- Query 60's end-to-end check has been run against develop and passes. A `POST` to `/mcp` answers `307` with an `https://` location, and a `POST` to `/mcp/` returns a valid MCP initialize response, which proves the mount still works rather than that the redirect merely changed.
- Separately, the frontend unit suite, which is the quick check run before a push, was both repaired and made faster: 527 of 527 passing in about 85 seconds against 128 to 163 before. Its filmstrip evidence is in `frontend/e2e/evidence/2026-09-23_journey7_viewports/`.

For the wider suite, `testing/Developer/Developer_workflows.md` has the full specification and run commands, including how to run the automated tests behind every other section of this document. Whether the MCP configuration printed on the Integrations page (query 60) actually connects end to end, not just reads correctly, is checked there too, after every change to that page.

## Where each query came from

The daily shipped lists named below were folded into this document and `testing/UI_fixes_done.md` on 2026-09-24. Their item numbers are kept here so the provenance stays readable; the closing table maps each retest item to its query.

| Section | Source documents |
|---|---|
| 1. Basic search and answers | `Product/Product_workflows.md` tests 1, 7, 12, 13, 14; the 2026-09-22 shipped list's items 1, 6; the 2026-09-20 shipped list's retest items 1, 2, 3, 5, 6; `UI_fixes_done.md` "What is live on develop" and items 8.4, 9.12, 11.14, 11.27, 11.31, 11.34, 11.35, 11.36; the 2026-09-23 shipped list's items 3, 4, 5 |
| 2. Follow-up questions and conversation | `Product/Product_workflows.md` test 2 |
| 3. Genes, variants and diseases | the 2026-09-22 shipped list's items 3, 5, 7, 8, 12, 13; the 2026-09-23 shipped list's item 6; `UI_fixes_done.md` items 11.6, 11.20 and 12.14 |
| 4. Chromosome windows and accessions | the 2026-09-22 shipped list's items 2, 9, 10, 11, 14, 15, 16 |
| 5. Pathogen isolates | `Product/queries/Isolate_search_queries_and_workflow.md` queries 1 to 12; the 2026-09-22 shipped list's items 17 to 22 |
| 6. Refusals, off-topic and compute requests | `Product/Product_workflows.md` tests 8, 19; the 2026-09-22 shipped list's item 4; `UI_fixes_done.md` "What is live on develop" and item 12.6 |
| 7. Sign in, sessions and history | `Product/Product_workflows.md` tests 3, 4, 5, 6, 16, 18, 20; the 2026-09-23 shipped list's items 2 and 15; `UI_fixes_done.md` items 10.2 and 12.13 |
| 8. Stop, feedback and the connection | `Product/Product_workflows.md` tests 9, 10, 21 |
| 9. Screens, phone width, the tour and the disclaimer | `Product/Product_workflows.md` tests 11, 15, 17, 22; the 2026-09-20 shipped list's retest item 4; `UI_fixes_done.md` items 2.8, 2.12, 2.14 and 11.30; the 2026-09-23 shipped list's item 1 |
| 10. Questions with no gene and no disease in them | `User-feedback/` (a second tester's four screenshots); the 2026-09-23 shipped list's items 8 to 11; `UI_fixes_done.md` items 12.1, 12.2, 12.4, 12.7 |
| 11. Answers that answer the question | `UI_fixes_done.md` items 12.3 and 12.9 to 12.12; the 2026-09-23 shipped list's retest items 12 to 17 |

## Every feature and where to try it

Every feature accounted for, in three tables:

- Every item in the index of `testing/UI_fixes_done.md`, "Done features at a glance".
- Every card on the board, `testing/UI_fix_plan.md`, as it stood on 2026-09-24.
- Every numbered retest item in the three daily shipped lists of 2026-09-20, 2026-09-22 and 2026-09-23.

"Nothing to try by hand" always carries its reason. Status is not repeated here; it lives on the board and in the done file's index.

### Items in the done file's index

| Item | The feature, in plain words | Where to try it |
|---|---|---|
| 1.1 | No five-search guest limit | Query 1, and query 53 for the removed test |
| 1.2 | No free-search or moved-into-an-account wall | Query 1 |
| 1.3 | No ten-attempt guest limit | Query 45, and query 55 for the removed test |
| 1.4 | The cost caps stay, and a signed-in account never claims unlimited searches | Query 52 |
| 1.5 | One Log in button | Queries 49 and 50 |
| 1.6 | Log out returns to the home page | Query 49 |
| 1.7 | The daily cap message reaches the screen | Nothing to try by hand: one tester cannot reach the shared daily cap for all guests, so it is checked on the developer side |
| 1.8 | The test checklist matches the new sign-in flow | Nothing to try by hand: a documentation change to `Product/Product_workflows.md` |
| 2.1 | The sign-in box is centred | Query 49 |
| 2.2 | One box width from progress to answer | Query 1 |
| 2.3 | The header and footer stay in place | Query 59 |
| 2.4 | Smooth transitions between screens | Query 59 |
| 2.5 | Header and footer in the same blue | Query 59 |
| 2.6 | New search is a distinct blue button | Query 56 |
| 2.7 | The three logo colours are in the theme | Nothing to try by hand: a theme change the design token check verifies |
| 2.8 | A light home page | Query 59 |
| 2.9 | Screens centred between header and footer | Query 59 |
| 2.10 | No idle wait after pressing Search | Query 1, the seconds counter |
| 2.11 | Searches no longer fail at the Think step on an unreadable model reply | Nothing to try by hand: nothing changes on screen, searches simply finish |
| 2.12 | A bigger search box with an up-arrow button | Query 59 |
| 2.13 | The NCBI design system changes possible today | Nothing to try by hand: nothing changes on screen, the colours were already the USWDS values |
| 2.14 | A favicon | Query 59 |
| 3.1 | No red refusal pills | Queries 45 and 46 |
| 3.2 | The NCBI search address in a refusal is a link | Query 46 |
| 3.3 | A grey label matched to the refusal reason | Queries 45 and 46 |
| 3.4 | "Search stopped" with Run again and New search | Query 56 |
| 4.1 | Stay signed in on reload, and history on phones | Queries 49, 51 and 59 |
| 5.1 | The Integrations page in the reference layout | Query 59 |
| 5.2 | The GraphQL example is correct | Query 59 shows it printed; calling it is a developer check |
| 5.3 | The MCP server accepts connections | Query 60 |
| 5.4 | Docs folded into Integrations | Query 59 |
| 5.5 | The disclaimer at the reference size | Query 61 |
| 5.6 | Four Integrations cards with real summary chips | Query 59 |
| 5.7 | The disclaimer wording | Query 61 |
| 6.1 | The automated test harness sees a real answer | Nothing to try by hand: a developer test harness |
| 7.1 | Follow-ups keep the earlier context | Query 20 |
| 7.2 | "Yes, go deeper" continues the same search | Queries 7 and 20 |
| 7.3 | A follow-up stays on the same screen | Query 20 |
| 7.4 | A folded turn keeps the whole earlier answer, with room between turns | Query 20 |
| 7.5 | A follow-up that refers to nothing asks for the missing detail | Query 20 |
| 8.1 | Every question searches all three layers | Query 5 |
| 8.2 | A lead scientist hands off to three named scientists | Queries 1 and 8 |
| 8.3 | Progress steps named for the scientist | Queries 1 and 8 |
| 8.4 | Scientists stay random on every visit | Query 9 |
| 9.1 | Two answer modes, Plain language and Researcher | Query 2 |
| 9.2 | An info button explaining the two modes | Query 3 |
| 9.3 | Plain language at about 250 words | Nothing to try by hand: superseded by 11.31; no word count is promised any more (query 2) |
| 9.4 | Researcher as a full page organised by topic | Nothing to try by hand: superseded by 11.31 |
| 9.5 | Short paragraphs with citations inline | Queries 1 and 5 |
| 9.6 | The answer streams in sentence by sentence | Query 1 shows the answer building; how the text arrives is checked on the developer side |
| 9.7 | No answer opens broken or garbled | Query 1 |
| 9.8 | Disease names read naturally | Query 1 |
| 9.9 | The trust signals are one plain line | Query 5 |
| 9.10 | Researcher headings, Plain language without them | Nothing to try by hand: superseded by 11.31 |
| 9.11 | A small medical-advice line on Plain language answers | Query 2 |
| 9.12 | The depth cannot change mid-search | Query 4 |
| 10.1 | BRCA1 and GCK answer every time | Queries 1 and 7 |
| 10.2 | History shows the saved answer instantly | Query 67 |
| 10.3 | The consistency run, three tries per golden question | Nothing to try by hand: a developer measurement of 150 live runs |
| 11.1 | Researcher answers follow the reference screenshot | Nothing to try by hand: superseded by 11.12 |
| 11.2 | Delete the reference screenshot and a session prompt | Nothing to try by hand: housekeeping |
| 11.3 | Stop after sets 8 and 9 | Nothing to try by hand: a working instruction |
| 11.4 | Does the research layer make people wait 45 seconds? | Nothing to try by hand: a question, answered |
| 11.5 | Citations as small raised numbers | Queries 1 and 5 |
| 11.6 | Variant-to-disease tables | Query 79 |
| 11.7 | The answer-writing model's reasoning setting is none | Nothing to try by hand: a model setting; its effect is the speed query 1 checks |
| 11.8 | A quicker answer | Query 1 |
| 11.9 | "[scientist] is writing the answer…" while it loads | Query 5 |
| 11.10 | Parallel sub-agents on matched models | Nothing to try by hand: how the work was done, not what the product does |
| 11.12 | Readable paragraphs, headings and tables | Queries 2 and 5 |
| 11.13 | The same format in both modes | Nothing to try by hand: superseded by 11.31 |
| 11.14 | Copying an answer carries no "Source 1, layer 2" text | Query 6 |
| 11.15 | The answer does not stream | Nothing to try by hand: superseded by 11.16 |
| 11.16 | The write step is signalled and sentences reveal at reading pace | Queries 1 and 5 |
| 11.17 | PubMed, PMC and more are searched, not only gene records | Queries 5 and 19 |
| 11.18 | Search everything in all three layers | Nothing to try by hand: a question, answered by 11.21 |
| 11.19 | "Variants in GCK causing MODY" answers every time | Query 7 |
| 11.20 | "What genes are associated with MODY?" answers | Query 78 |
| 11.21 | The right resource for each question, the same sources every time | Query 19 |
| 11.22 | PubMed and PMC give the answer context | Query 13 |
| 11.23 | Does the NCBI API key allow 100 requests per second? | Nothing to try by hand: a question, answered |
| 11.24 | How do I test what is built so far? | Nothing to try by hand: a question, answered by this document |
| 11.25 | What from Set 11 is on develop? | Nothing to try by hand: a question, answered |
| 11.26 | Answers look like the approved mockup, and tables page | Query 17 |
| 11.27 | Only the title or main point is bold | Query 77 |
| 11.28 | The move from searching to the answer is paced | Query 18 |
| 11.30 | Every integration on the Integrations page works | Query 60 |
| 11.31 | The two answer modes, and NCBI's own gene summary | Queries 14 and 2 |
| 11.33 | Abstracts no longer cut off mid-word | Query 11 |
| 11.34 | A multi-sentence abstract keeps its citation | Query 13 |
| 11.35 | The confusing Notes section is gone | Query 7 |
| 11.36 | The info button no longer promises a word count | Query 3 |
| 11.37 | Knowledge-graph sources in the source list | Nothing to try by hand: accepted, not a defect; the graph's sources merge into the Live NCBI group that query 17 shows |
| 12.1 | A disease question searches every layer | Query 68 |
| 12.2 | A literature question is not refused as "Outside biomedical research" | Query 70 |
| 12.3 | A one-to-three-word question is asked back | Query 76 |
| 12.4 | A refusal says "Ask another question" | Query 71 |
| 12.5 | Can these questions be answered at all, and how? | Queries 68, 69 and 73 try the questions it answered |
| 12.6 | The clarifying request when no gene, variant, disease or organism is named | Query 48 |
| 12.7 | A question naming no gene and no disease finds the papers | Query 69 |
| 12.8 | The trust line stops undercounting | Query 74 |
| 12.9 | Plain language and researcher differ on every question | Query 72 |
| 12.10 | The answer answers the question | Query 73 |
| 12.11 | The sources chip and the trust line agree | Query 74 |
| 12.12 | No broken sentences and no repeated records | Query 75 |
| 12.13 | The history rail opens the saved answer | Query 67 |

### Cards on the board

| Item | The feature, in plain words | Where to try it |
|---|---|---|
| 13.2 | The Answer modes card says what each mode gives, one block per mode | Query 86 |
| 12.14 | A question about a disease's features names them | Query 81 |
| 12.17 | A good question is not refused at the think step | Query 80 |
| 12.16 part 3 | Which questions count as a request for papers becomes a classifier's decision | Nothing to try by hand: not built, and a routing change a person cannot see |
| 12.15 | A question asking for recent papers asks what recent means | Nothing to try by hand: not built. Today `recent papers on statins` is answered without asking (query 70) |
| the golden rows | Four golden test rows disagree with what the product does | Nothing to try by hand: the test set only, and the product owner's decision |
| the ceiling | Is twenty sources the right ceiling? | Nothing to try by hand: the product owner's decision; query 79 shows one table it cuts short |
| the drafted search | Tell the reader when the system wrote its own search | Nothing to try by hand: not built |
| 11.29 | Hard and soft edges over a fuller graph | Nothing to try by hand: parked, a discussion before a build |
| 11.38 | A bounded trial of the probability model | Nothing to try by hand: parked |
| 11.11 | Answers modelled on the reference prototype | Nothing to try by hand: not built |
| 9.11 | Does Plain language keep its medical-advice line? | Query 2 |
| 9.9 | The trust-line wording | Query 5 |
| 10.4 | Judge answer quality once answering is reliable | Nothing to try by hand: not built |
| the lock file | A lock file for the Python build | Nothing to try by hand: a developer build change, and the product owner's decision |
| 11.32 | Internal MCP servers around the Layer 2 and Layer 3 calls | Nothing to try by hand: parked |
| 11.31, explanation half | The answer explains the gene in its own words | Nothing to try by hand: parked; query 14 shows the half that is built |
| the byte ceiling | The byte ceiling at 50,000 | Nothing to try by hand: parked, a developer limit |
| 12.11, 12.8 | "Based on N sources" equals the SOURCES count | Query 74 |
| 12.12 | No broken sentences and no restatement paragraph | Query 75 |
| 12.10 | The answer answers in plain sentences, each cited | Query 73 |
| 12.13 | A search clicked in the history rail, in the same tab, opens its saved answer | Query 67 |
| 12.9 | Plain language and researcher differ on every question | Query 72 |
| 12.3 | A one-to-three-word question is asked back | Query 76 |
| 12.1 | The seven questions from the second tester all answer | Queries 68, 69 and 73 |
| 12.2 | A lowercase literature question is not refused | Query 70 |
| 12.4 | A refusal says "Ask another question" | Query 71 |
| 12.7 | A question naming no gene and no disease finds the papers, each shown once | Query 69 |
| 11.30 | The MCP configuration connects and never sends you to `http://` | Query 60 |
| 10.2 | History shows the saved answer at once, with Run again | Query 67 |
| G-019 | MeSH terms show as real terms | Query 64 |
| the opening count | The opening sentence's count agrees with the list | Query 65 |
| the phenotype template | The Marfan phenotype question no longer says "I could not find evidence" | Query 66 |
| G-033, G-037 | Two questions keep their own graph search | Queries 24 and 25 |
| the coordinate range | A chromosome range is answered, and a range with no assembly asks which | Queries 27, 28 and 29 |
| the question's own words | An answer never lists the question's own words as diseases | Queries 23 and 25 |
| the accessions | A BioProject or BioSample accession is answered, and an unknown one is named as not found | Queries 30, 31 and 32 |
| G-035 | Isolate questions answer with a table of isolates and their resistance genes | Queries 33 to 44 |
| 11.14 | Copy an answer: no "Source 1, layer 2" text | Query 6 |
| 11.36 | The info button: no promise of a word count | Query 3 |
| 9.12 | The mode cannot change mid-search | Query 4 |
| 8.4 | Two visits: different scientists, the same answer | Query 9 |

### Retest items from the daily shipped lists

The 2026-09-23 list has no retest item 7: its item 6 covered the developer test work.

| Shipped list, retest item | The feature, in plain words | Where to try it |
|---|---|---|
| 2026-09-20, 1 | A gene-to-disease answer's notes agree with each other and the table | Query 15 |
| 2026-09-20, 2 | A literature question's papers are on topic | Query 16 |
| 2026-09-20, 3 | Many records: the table pages at ten, the sources collapse to three layer rows | Query 17 |
| 2026-09-20, 4 | The MCP configuration works pasted as printed | Query 60 |
| 2026-09-20, 5 | The scientist names during a slow wait are readable | Query 18 |
| 2026-09-20, 6 | The same question twice keeps its source count | Query 19 |
| 2026-09-22, 1 | The plain-terms BRCA1 explanation answers well under a minute | Query 10 |
| 2026-09-22, 2 | The CNV window as it behaved before the coordinate feature | Query 26, and query 27 for today's behaviour |
| 2026-09-22, 3 | GCK shows OMIM 138079, never MAP4K2 | Query 21 |
| 2026-09-22, 4 | BLAST and VCF requests are turned away | Query 47 |
| 2026-09-22, 5 | CFTR variants still answer | Query 22 |
| 2026-09-22, 6 | The BRCA1 gene summary runs to its end at researcher depth | Query 11 |
| 2026-09-22, 7 | MLH1 and MSH2 both show their condition records | Query 24 |
| 2026-09-22, 8 | GEO datasets for TP53, with no lost-search line | Query 25 |
| 2026-09-22, 9 | The CNV window names BRCA1 and its dbVar and ClinVar records | Query 27 |
| 2026-09-22, 10 | A window with no assembly is asked which | Query 28 |
| 2026-09-22, 11 | The CFTR-locus window | Query 29 |
| 2026-09-22, 12 | rs334 without invented conditions | Query 23 |
| 2026-09-22, 13 | The GEO question without mouse tumour records as named entities | Query 25 |
| 2026-09-22, 14 | BioProject PRJNA31257 and everything it links to | Query 30 |
| 2026-09-22, 15 | An unknown BioProject accession | Query 31 |
| 2026-09-22, 16 | BioSample SAMN12121739 and its runs | Query 32 |
| 2026-09-22, 17 | E. coli isolates with ESBL genes | Query 33 |
| 2026-09-22, 18 | Salmonella isolates with blaCTX-M-15 only | Query 35 |
| 2026-09-22, 19 | Klebsiella isolates with carbapenemase genes | Query 36 |
| 2026-09-22, 20 | Listeria with blaKPC, an honest zero | Query 38 |
| 2026-09-22, 21 | An organism with no gene, and an organism the product cannot search | Queries 40 and 39 |
| 2026-09-22, 22 | "ESBL E. coli isolates?" | Query 44 |
| 2026-09-23, 1 | The MCP configuration connects, never via `http://` | Query 60 |
| 2026-09-23, 2 | History shows the saved answer at once, tables included | Query 67 |
| 2026-09-23, 3 | MeSH terms for PMID 11237011 in words | Query 64 |
| 2026-09-23, 4 | The opening sentence agrees with the list | Query 65 |
| 2026-09-23, 5 | The Marfan phenotype question | Query 66 |
| 2026-09-23, 6 | The developer test work, D4 | Nothing to try by hand: developer tests; the evidence is the filmstrip in `frontend/e2e/evidence/2026-09-23_journey7_viewports/` |
| 2026-09-23, 8 | The seven questions from the second tester | Queries 68, 69 and 73 |
| 2026-09-23, 9 | `any trials for gerd?` in lowercase | Query 70 |
| 2026-09-23, 10 | What sits under a refusal | Query 71 |
| 2026-09-23, 11 | Each paper appears once | Query 69 |
| 2026-09-23, 12 | The trust line counts pages | Query 74 |
| 2026-09-23, 13 | No broken sentences and no restatement paragraph | Query 75 |
| 2026-09-23, 14 | The answer answers the question | Query 73 |
| 2026-09-23, 15 | The history rail opens the saved answer in the same tab | Query 67 |
| 2026-09-23, 16 | Plain language and researcher differ on every question | Query 72 |
| 2026-09-23, 17 | A very short question is asked back | Query 76 |
| 2026-09-23, 18 | 12.16 part 4, the answer checker's structural rules | Nothing to try by hand: its effect is fewer wrong sentences, which queries 73 and 75 already check |
| 2026-09-23, 19 | 12.16 part 1, no tester's question is a prompt's example | Nothing to try by hand: it changed the examples inside the prompts, and the guardrail was re-measured at 68 checks, 0 wrong |
| 2026-09-23, 20 | The fix plan split in two | Nothing to try by hand: a documentation change. `testing/UI_fix_plan.md` holds what is being built and what is next, `testing/UI_fixes_done.md` every closed item |
| 2026-09-23, 21 | Rules and skills, pull requests #101 to #103 | Nothing to try by hand: documents only |
| 2026-09-23, 22 | D5, the API deploys again | Nothing to try by hand: the proof is both develop services reaching SUCCESS on the commit that caps SQLAlchemy |
