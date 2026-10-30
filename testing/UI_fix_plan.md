# UI fix plan

The board for the UI fix loop. An item starts in To do and moves to Build in
progress when someone starts it. Once it is live on develop it moves to
`testing/Retest_product_owner.md`, and your verdict
closes it.

This board is the source of truth for what gets worked on: an item is written
here before it is built.

- A review finding goes on this board only if a person using the product would
  notice it; anything else is fixed in that review round or recorded in the
  phase ledger (`DECISIONS.md`, 2026-10-05).
- Engineering work no user would notice lives in `testing/Future.md`.
- The order every card is built in, and what blocks what, is
  `testing/Board_plan.md`.
- The detail behind the architecture cards sits under To do, below its table.
- Every other item's detail, every closed item and every note behind the board
  are in `testing/UI_fixes_done.md`.

Last updated: 2026-10-29.

## To do

In priority order. The Next move column says who moves each card next: the team or Factory builds it now, a design is agreed with the product owner first, or it is the product owner's own decision, architecture work or reading of data.

Order note, 2026-10-25: card 147 leads the cards the team can build (you said to diagnose it next), then card 84's reading of the guard lag lines. The rest keep their order.

| # | Next move | Feature, in plain words | Item | Waiting on |
|---|---|---|---|---|
| 56 | Design with you first | A question about SARS-CoV-2 is answered about the disease SARS, so a person gets a confident wrong record and no sequencing runs | Card 56 diagnosis (`testing/Developer/reports/2026-10-05_card56/diagnosis.md`); the fix (#173) passed 3 of 3 local Think and Plan runs but failed on develop on 2026-10-05 (`testing/Developer/reports/2026-10-05_final_test_queries/results.md`) | Part live once merged (#186 or the next number): the plain SARS-CoV-2 question no longer binds the SARS disease (0 of 20 live runs, 5 of 26 before). Still open, for a design with you first: "SARS CoV-2" typed with a space still binds SARS; after a gene in the same conversation a missed SARS-CoV-2 question uses the remembered gene; "SRA runs from AML-derived cell lines" can lose its leukaemia match; the "Illumina" refusal (7 of 20 runs). Evidence: `testing/Developer/reports/2026-10-06_card56/`; card 16 folded in on 2026-10-09: golden question G-005 fails on this card's "Illumina" refusal. Designed with you on 2026-10-17 (`testing/Developer/reports/2026-10-17_card56/design.md`, seven calls in `DECISIONS.md`): built in three slices, each merged before the next: (1) a phrase that does not confirm is looked up whole in NCBI and used when exactly one record fits, otherwise asked, with a whole-word fallback when the model names nothing; (2) conditions such as Illumina are applied or said not applied, never read as genes; (3) a remembered subject fills in only when the question names none. Slice 1 built and closed on 2026-10-17 under your rule, never pushed: its judge and adversary found it worse than develop in ways one fix round could not close: a single NCBI fit is not proof for an acronym ("HEV" read as a pig virus, Taxonomy 42005; "CMV" as cucumber mosaic virus), "COVID-19 patients" on a sequencing question became the virus, "HIV-1" bound HIV disease records, an ask said "could not find CML" falsely, and the extra model call fired on ordinary questions (one topic question took 46 s). What held: no word was cut, and "SARS CoV-2", "SARS COV2" and "SARS CoV-2 variants" read as the virus. The next design decides when a single fit can be trusted, narrows the retry to the replies that contradict themselves, and puts the lookup before the disease fallback on sequencing questions. Reports and the closed diff: `testing/Developer/reports/2026-10-17_card56/` |
| 101 | Design with you first | A reworded sentence can reach the screen without passing the sentence check: a bronchiolitis answer said "For babies with severe bronchiolitis" where its record says children, and that sentence was never among the check's candidates. Re-aimed 2026-10-06 from card 99's sentence cost, whose writer line measured no gain | `testing/Developer/reports/2026-10-06_card101/fix_round.md`, "For the owner" | Part live (#193, #204, in Retest). Its last slices were rebuilt overnight on 2026-10-15 from a design for where a record sentence ends (#248), and closed under the owner's rule when the judge and the adversary both found sentences develop shows that the branch drops: a curly apostrophe or a later closing mark pairs with a stray opening quote and marks the rest of an abstract as quoted, and a negation one sentence further back is lost. The next attempt reads quote marks by their pairing in the record, not by their shape. Evidence: `testing/Developer/reports/2026-10-15_card101/` (design, build, both reviews, final diff) and `testing/Developer/reports/2026-10-08_card101/` |
| 94 | Design with you first | Isolate questions answer with a table of isolates and their resistance genes: the default mode often shows names without genes, the blaCTX-M note is missing, a colistin question returns a suspicious zero, and a single-isolate answer lacks its details (queries 33, 35, 36, 44 and the isolate workflow); some counts differ only because the snapshot is newer | G-035; failed the batch retest of 2026-09-29 (`testing/Developer/reports/2026-09-29_retest/`) | Part live (#158, #165, #169, #174, and the place in the "Collected" cell, #226, in Retest). Still open: a single-isolate lookup, built overnight 2026-10-15 to your calls and closed by your rule (#244): Pathogen Detection's isolate file is read in submission order, so within an answer's time only the oldest 11 to 18 percent of Salmonella isolates can be reached, and reading the organism by genus sent two species to the wrong data; it needs an index of the files before it returns (`testing/Developer/reports/2026-10-15_card94/`). The timeout-crash fix from that build is re-split onto its own pull request, and a follow-up such as "from 2023" (card 20) |
| 147 | Team: buildable now | Some answers' written summary opens mid-thought ("Another finds ...", "... are also covered"), seen in 2 of 3 CFTR papers runs that wrote a summary on 2026-10-22 | The product check of notes and papers, PR-notes-04 and PR-notes-13 (`testing/Developer/reports/2026-10-22_product_check_notes_papers/`) | Diagnose next, by your call of 2026-10-25 |
| 84 | Team: buildable now | R-10's guardrail fixes on their own | Built, then stopped at the owner's choice on 2026-09-29 after its adversary found an off-topic question and a disguised injection admitted when the provider rate-limits (F-84-A05, A07); its branch (tip 5a0adc02) deleted on 2026-10-08 after the design described every commit; records in `testing/Developer/reports/2026-09-29_card84/` | Safe part live (#227, in Retest). Step 3b, the server-pause fix: your call 2026-10-16, count first. Since #251 (43bcfcf7) develop logs `event loop lag: <s> s (timers ran late)` each time the server's timers run 0.25 s or more late, from a freeze, a busy server or a host pause. Read a week of these lines on 23 October, then decide whether the fix (`testing/Developer/reports/2026-10-15_card84_72/design.md`) is worth building. By your call of 2026-10-25 the lead reads the last week's guard lag lines from develop and production logs, read only, and brings the numbers and one recommendation |
| 72 | Team: buildable now | A search fails with "a temporary error" because the guard model did not answer in time, twice: 4 of 150 golden runs on 2026-09-29. The first hedged design lost searches in a slow spell and let an off-topic question through on the relevancy check (F-72-V08), and was not merged | Diagnosis: `testing/Developer/reports/2026-09-29_card72/diagnosis.md`; the deleted branch's verifier (`testing/Developer/reports/2026-09-29_card72/verifier.md`): F-72-V06 and V08 | Part live (#159, one log line per guard and Jev call; #227, the safe part with card 84, in Retest). Still open: step 2, host routing, waits for a week of logs that name a cut call's host, which the log now keeps for names written in words (`testing/Developer/reports/2026-10-08_guardrail_design/step2_data.md`); a slow guard was seen again on 2026-10-09, 8.3 s on card 19's check. By your call of 2026-10-25 the lead reads the guard lag lines with card 84's and brings the numbers and one recommendation |
| 85 | Yours: a decision | Small accuracy fixes, one card: two page sentences still false on some paths (the layer 3 stop names three kinds of question searched another way where there are five, and the About walk says BRCA1's live searches run at the same time as the graph, where four of thirteen run in a second round); and behind the scenes, the facts checker's remaining gaps and three logging gaps (a crash's reason on the lines after its trace id, step-level failures that log no reason, and an older database warning that logs a full error message) | Folded from cards 76, 78, 81, 82 and 83 at the owner's choice, 2026-09-29; detail in `testing/Developer/reports/2026-09-29_card53/verifier.md` and `testing/Developer/reports/2026-09-29_card73/` | Part live (#167, #220, in Retest): the page sentences and the logging slice. Still open, each yours: the facts checker's gaps, under `.claude/`, and the five `exc_info` warnings (A07) |
| 4 | Yours: your architecture work | Tell the reader when the system wrote its own search rather than using a checked one | the drafted search | Nobody on it |
| 6 | Yours: your architecture work | The agentic loop: interpret the objective, make a plan, use tools, check intermediate results, adjust when something fails, produce or apply the final result | [the agentic loop](#the-product-owners-direction-on-the-model-architecture-2026-09-23) | Nobody on it |
| 7 | Yours: your architecture work | Hard and soft edges over a fuller graph, "connecting the dots" | [11.29](#detail-1129) | Nobody on it |
| 9 | Yours: your architecture work | Judge answer quality once answering is reliable | 10.4 | Nobody on it |
| 15 | Design with you first | Close the remaining path where the system writes its own graph search, or ask the reader instead; card 7 only tells them | L-01 | Step 1 live (#171). The next step was built on 2026-10-08 overnight and parked (pull request #216 closed): one record for every non-count question gave wrong or thinner answers. One checked template per question shape was designed and built overnight on 2026-10-16 (#249), four shapes, and closed under your rule: after a session's last subject was a condition, a new question whose own condition does not resolve could get up to 100 cited variants of the remembered condition, and a "which has more" question got two lists marked complete. The next build skips the shape decision when the subject comes from memory and keeps count and comparison questions off the list shapes. Evidence: `testing/Developer/reports/2026-10-15_card15/` (design, build, both reviews, final diff) and `testing/Developer/reports/2026-10-08_card15/` |
| 18 | Design with you first | A record with several sentences shows as several list rows under one heading, and no test covers it | Where we stopped, loose ends; a helper was built on the 8.4 branch, saved as `testing/Developer/reports/2026-09-25_phase_8.4/parked_commits/04_9c46d708_*.diff`, its wiring in `core/graph.py` is not built | Built overnight on 2026-10-16 to your call (#258, one row, the later sentence dropped from the command line) and closed under your rule: the judge found that MCP and GraphQL also build the answer from row text, so an agent calling the product lost about half of a long abstract's sentences (16 of 32 in its probe, against 32 of 32 on develop), a cost you were not asked about. The next build needs a design with you that keeps every sentence for the text-only surfaces, such as a continuation event (an event-schema change). Evidence: `testing/Developer/reports/2026-10-16_card18/` (diagnosis, build, judge, adversary, final diff) |
| 20 | Design with you first | An isolate search can filter only by gene prefix | Shipped days, 2026-09-22; year from the question built on the 8.4 branch (saved as `testing/Developer/reports/2026-09-25_phase_8.4/parked_commits/03_94b0ba41_*.diff`), location needs the plan step | Your call 2026-10-15: a small extraction call that runs only on isolate questions, so Think and every other question stay as on develop. Built overnight on 2026-10-16 (#247) and closed under your rule: a "Georgia" question counted every USA isolate, a state written as a postal code (USA:GA) never matched while the count read as exact, two countries read as one place, and a paper's year became the collection year. The next build needs a design for how a place in the question is matched to how Pathogen Detection writes it. Evidence: `testing/Developer/reports/2026-10-16_card20/` (build, both reviews, final diff) and `testing/Developer/reports/2026-10-09_card20/` |
| 25 | Yours: a decision | Install the public USWDS package, the base of the NCBI design system: yes or no | 2.13; decided 2026-09-25, not built | Out of Factory's lane on 2026-10-06: a new package needs your approval and a supply-chain review first. Before: Nobody on it |
| 29 | Design with you first | Under each cited paper, show the one sentence of its own abstract that answers the question, quoted and cited (replaces the LitSense route, closed 2026-09-25: LitSense cannot be pointed at a paper) | [13.1](#detail-131), DECISIONS.md 2026-09-25 | Built and reviewed overnight 2026-10-15, pull request #243 closed by your rule: retracted papers and cut sentences are fixed, but 3 of 24 distinct sentences shown would mislead (a pronoun pointing elsewhere, a weak claim picked at low confidence, background citing a retracted paper), worse than develop's title-only cards. Needs a stricter pick (a confidence floor or a second check) before it returns. Reports and the final diff: `testing/Developer/reports/2026-10-15_card29/` |
| 30 | Team: buildable now | `Which BRCA1 variants are pathogenic?` lists 40 unclassified variants and the model's honest caveat is stripped | `tracker/phase_8.1.md` F-8.1-A16, found 2026-09-25, older than that night | Part live (#261, in Retest, overnight 2026-10-16): the plain line under a graph variant list and the "ask" verdict on a classification question. Still open: step 2b, each listed variant shows its ClinVar classification, built overnight (#269) and closed under your rule: every classification shown was right (134 of 134), but the classification text added to each row pushed long variant answers past the 8000-character cut of MCP and GraphQL, so an agent asking query 22 lost five trial records and step 1's line. The next attempt keeps the text-only answer inside that cut. Evidence: `testing/Developer/reports/2026-10-16_card30/` |
| 33 | Yours: a decision | Two golden questions that answered on 2026-09-22 no longer do: G-004, a Salmonella isolate question that runs no search, and G-006, sequence data for PMID 11237011 | the golden run of 2026-09-25, `testing/Developer/reports/2026-09-25_phase_8.1_golden/` | Diagnosed 2026-10-08: G-006 fixed (#172); G-004 waits on your decision D19 |
| 36 | Design with you first | A picked "How far back" window is lost after a restart or deploy, and nothing tells the person | F-8.2-V02 | Live (#215, in Retest): the plan line says when a picked or typed date range could not be applied. Still open, your design choice: making a picked window survive a restart |
| 37 | Design with you first | `What is rs334 and what condition is it associated with?` lists rs334348, rs334353 and rs334773 as if they were rs334: they are different variants that only share its first digits. The rs334 record itself is named by its list of clinical significance values, with no gene or condition | the phase 8.7 design, row G-024; `tools/litvar2_lookup.py` keeps LitVar2's near misses by design (F-3.3-A-01) and nothing downstream drops them | Part live (#213, and #262 overnight 2026-10-16, both in Retest): rs334 lists only rs334, and its record is named rs334 with its gene and its significance in their own columns. Still open: the condition, now card 120. The writer given the gene (slice A2, #264) was built and closed under your rule: on a two-variant question the gene could attach to the wrong rs id and still pass the citation check; it needs a design that carries the variant into the check. Evidence: `testing/Developer/reports/2026-10-16_card37_38/` |
| 40 | Yours: a decision | Make the harness work well: carry out what the two harness reviews recommend, for the product's question-to-answer harness and for the build harness | the product owner, 2026-09-25: "you take charge and implement the improvement"; the reviews: `testing/Developer/reports/2026-09-25_harness_review/` | The itemized list is written: 27 items, each your yes or no (`testing/Developer/reports/2026-10-08_card40/itemized_list.md`); nothing in the security layer changes before you answer |
| 42 | Yours: a decision | The build team checks the product the way a person uses it, so the owner's retest confirms rather than discovers: it writes the code, verifies it, runs the judge and the adversary, checks the result against a `/design` of what the owner wants, and ends with a `/verify` of the QA and UI work. Two months of building left more than 100 UI fix items for the owner to find | the product owner, 2026-09-26: "for the QA and UI checks you depend on me, I do not like that, ideally I would want you to be confident on the UI check and me not have to give you the instructions everytime" and "the bossman mode team should be able to write the code, verify the code, judge, averserial, then have a /design for what I want and in the end /verify the QA work. This whole end to end is what we need to build." Inspired by the talk "Building verification loops in Claude Code" (https://www.youtube.com/watch?v=mQZB0l-rhxE) | Queued by the owner behind the running work: phase 8.6's golden run, the build-harness and hook-gap pull requests, card 39 and phase 8.9's opening. Proposal: `docs/build/Verify_loop_proposal.md`, waiting for the owner's yes before anything is built |
| 48 | Design with you first | A fuzzy question such as "Tell me about the tree of life." or "How do birds fly?" gets a list of loosely matched papers; the owner wants it to ask which aspect the person means first | The product owner, 2026-09-26: "When there are fuzzy questions like this, clarify." Measured by the re-land's adversary, F-8.6-RA04 in `tracker/phase_8.6.md` | Taken back 2026-10-15 by your call, pull request #230 closed: the redesign searched every message naming a record, but the card's rewrite of the ask-back decision asked back real questions develop searches, such as "ESBL E. coli isolates?" and "recent-onset diabetes treatment" (queries 44 and 84). Needs a new design that never asks a real question; reviews in `testing/Developer/reports/2026-10-09_card48/` and `2026-10-15_card48/` |
| 51 | Yours: a decision | Nothing the app tells people about itself goes stale as the backend changes: the About, Architecture, Integrations and home pages, the tour and the access notes, and the reference documents that repeat the same facts | The product owner, 2026-09-26: "the information that we are providing on the UI is not stale and it reflects the current uh, updates ... this could just be part of the verify skill" (`DECISIONS.md`). Extends card 42 | Part live (#156, #219, in Retest): the About page no longer describes the retired track. Still open, yours: a registry of every page claim |
| 52 | Team: buildable now | Every answer, whatever the question, ends by offering the next useful step, decided from that answer's own context and never from a template or a topic list. For example "Would you like the clinical trials recruiting for GERD, or the genes linked to it?", and a click continues the same conversation with its context. Today an answer ends on its table, and the only offer is "go deeper" into records it left out | The product owner, 2026-09-26, after asking "GERD" beside a general AI search answer that ended "Would you like me to put together a sample 1-day meal plan ... or would you prefer a list of safe ingredient swaps": "It is beautiful orchestration of continuing the discussion and searching for the next thing or guiding the user in the conversation. Ideally my ai agent system needs to be able to do this. This will help with the follow up too." Then: "GERD was an example of the follow up, do not hard code." Builds on the next-step offer of 2026-09-01 and 2026-09-13 (`DECISIONS.md`) and sits beside card 48 | Designed, 2026-09-26: `testing/Developer/reports/2026-09-26_conversation_next_steps/design.md`. The writing model proposes at most three follow-up questions from the answer's own findings, code checks each is answerable and names a record the answer found, and Jev decides it asks what records hold, not advice. No fixed menu. A numbered phase after 8.6's follow-up, 8.7 and 8.9, at dial position 3 (event schema). Five decisions for you when it opens, the lead recommending yes to each |
| 55 | Design with you first | Work counts as done when the test queries document passes, run automatically by the team, not when the golden count holds: every feature's "what you should see" is checked, and an expert checks the facts in a few key answers | The product owner, 2026-09-26: "what we should be actually trusting ... is running the test queries and workflow document that should be the barrier that needs to pass" (`DECISIONS.md`) | Being designed, 2026-09-26: how each entry becomes checks, the runner, the cost and the first baseline run. Then built on a branch, since it changes `.claude/`. The golden run stays the blocking gate until this one has run once. The expert review is the owner's to arrange; the lead prepares the answers to check |
| 100 | Factory: buildable now | Between 721 and 900 pixels wide, the top bar runs off the screen when the signed-in email is very long | Found by the lead's check of cards 43 and 44 on 2026-10-06 with a 50-character test email; a real long email was not tried | Factory's card (`docs/build/Factory_onboarding.md`, card 100), your decision of 2026-10-06: low priority, a Factory screen card |
| 106 | Factory: buildable now | On a phone, the "High-risk claim" tag under a reopened answer breaks across two lines as "High-" and "risk claim" | Card 71's product check (`testing/Developer/reports/2026-10-09_product_check_71/product_review.md`) | Factory's card from 2026-10-16 (`docs/build/Factory_onboarding.md`, card 106). Before: Nobody on it; found 2026-10-08 overnight |
| 107 | Design with you first | When the model check rejects a clause the writer reworded, the start of that sentence can still show, so a person reads half a sentence the check did not pass; seen again on develop: a Plain language BRCA1 answer read "One is double-strand break repair ..." with nothing saying what "one" is (card 19's product check, PR-19-06) | Card 51's fresh verifier, V-51-01 (`testing/Developer/reports/2026-10-09_card51/verifier.md` on card 51's merged branch) | Nobody on it; card 101's territory, found 2026-10-08 overnight |
| 108 | Team: buildable now | When every search a question planned is skipped, because the per-question cost cap was reached or the 20-lookup limit was already used, the progress steps stay on Plan for the whole time the answer is being written, then jump to Write with Act never lit | Card 19's judge and adversary, J-19-03 and A-19-03 (`testing/Developer/reports/2026-10-09_card19/`): the backend sends no frame when it skips every call, so the screen cannot know the searching is over | Nobody on it; true on develop before card 19; needs a new progress event, so it is an event-schema change at dial position 3 |
| 110 | Design with you first | An answer can open on its count line though a sentence that answers the question exists, because the first-sentence pick sees only the first two sentences; the Plain language Marfan features answer opened "I found 5 published papers ...", and the Researcher EGFR question opened by counting records (card 19's product check, PR-19-07) | Phase 8.7's product check on develop, PR-87-04 (`testing/Developer/reports/2026-10-09_product_check_8.7/`, cause in its `diagnosis.md`) | Redesigned and built overnight 2026-10-15, pull request #242 closed by your rule: develop's own pick never lost an opening and later answering sentences now opened (25 in replay), but two titles or features joined by "as well as", "&" or "plus" still opened the answer (38 of 40 replays). The next attempt needs a label filter that reads any joining words, not a list of them. Reports and the final diff: `testing/Developer/reports/2026-10-15_card110/` |
| 113 | Factory: buildable now | Records kept after Stop look very pale a few seconds later, though they were full ink when Stop took effect; seen in two checks, cause not found (a fade after Stop, or the full-page capture) | Card 109's product check on develop, PR-109-03 (`testing/Developer/reports/2026-10-09_product_check_109/product_review.md`) and phase 8.7's check, PR-87-10 | Factory's card from 2026-10-16 (`docs/build/Factory_onboarding.md`, card 113). Before: Nobody on it; needs one look by hand after a Stop |
| 116 | Design with you first | A short real question such as "TP53 mutations", "Lynch syndrome genes" or "Salmonella isolates" is asked "which aspect?" instead of searched, every time | Card 48's adversary, 2026-10-15, A2-48-02 (`testing/Developer/reports/2026-10-15_card48/adversary.md`): true on develop today, on the one-to-three-word path | Nobody on it yet |
| 117 | Factory: buildable now | Two small marks on the new Plain language and Researcher switch: an answer asked last through the command line or MCP folds under the raw label "clinical_brief", and with no mode picked the status strip carries about 19 px of blank space, so the answer starts lower than before | Card 24's fresh verifier, 2026-10-16, V-24-02 and V-24-03 (`testing/Developer/reports/2026-10-16_card24/verifier.md`) | Factory's card from 2026-10-16 (`docs/build/Factory_onboarding.md`, card 117). Before: Not started; card 24 merged with both named open under your overnight rule |
| 119 | Team: buildable now | After picking a "How far back" window, an answer lists at most 5 papers from that window | Card 105's diagnosis (`testing/Developer/reports/2026-10-16_card105/diagnosis.md`); your call of 2026-10-16: keep the cap at 5 inside card 105, raise it on a card of its own | Nobody on it; filed 2026-10-16 overnight |
| 120 | Team: buildable now | `What is rs334 and what condition is it associated with?` names no condition: sickle cell (Hb SS disease) is in ClinVar, but 9 of the 10 records a ClinVar search for rs334 returns are compound records or another allele, so it needs an exact single-variant filter | Cards 37 and 38's diagnosis (`testing/Developer/reports/2026-10-16_card37_38/diagnosis.md`), "Needs the owner"; your call of 2026-10-16: a later card | Nobody on it; filed 2026-10-16 overnight |
| 122 | Team: buildable now | `What does the RS1 gene do?` lists papers that are not about the RS1 gene: a "radial spoke 1" paper and a viral enzyme paper among its sources | Card 37 slice A1's product check on develop, 2026-10-17 (`testing/Developer/reports/2026-10-17_product_check_card37/report.md`); A1 did not change gene answers (its verifier found them byte-identical to develop) | Nobody on it; filed 2026-10-17 overnight, cause not diagnosed |
| 124 | Team: buildable now | After picking a "How far back" window, a paper from the enrichment layer can still be listed from outside the window: `recent papers on BRCA1` with "the last 5 years" lists PubMed 20301425, from 1993, as "Published paper" | Card 105's product check on develop, 2026-10-17 (`testing/Developer/reports/2026-10-17_product_check_card105/report.md`); card 105 left out the knowledge graph's papers by your decision, and develop lists this paper too | Nobody on it; filed 2026-10-17 overnight |
| 126 | Design with you first | When two cited databases disagree on a high-stakes fact (ClinVar "Pathogenic", dbSNP "Benign"), the line under the answer should say the sources disagree, also when another check lifts the answer to "ask"; today it names both databases with no warning. Some real disagreements show no warning at all: graph ClinVar against live ClinVar on one record, and a live ClinVar classification is not treated as high-stakes | Card 8's fresh verifier, V-8-06; your call of 2026-10-17 (`DECISIONS.md`); this card's judge and adversary (`testing/Developer/reports/2026-10-17_card126/`) | Built 2026-10-17 and closed by your call the same day, never pushed: the line fired on answers where nothing disagrees, because the check that compares records matches any record with the same field, not the same variant and not only cited records (A-126-01, A-126-02, J-126-02). The next build fixes that comparison first (same variant, cited records only; A-126-03, 04, 14), then the line (A-126-06, 07, 12, J-126-01). Diff kept: `closed_branch.patch` |
| 127 | Team: buildable now | A follow-up about a remembered organism never reaches its own records: after a tuberculosis question, "And its SRA runs?" searches the knowledge graph, not SRA, and a remembered organism never reaches its assembly records either | Card 56's code map, P8 (`testing/Developer/reports/2026-10-17_card56/code_map.md`, `tests/system_03_search_agent/core/test_think_sra_disease_fallback.py:266`); your call of 2026-10-17 (`DECISIONS.md`) | Nobody on it; filed 2026-10-17, built after card 56 merges |
| 128 | Team: buildable now | A CFTR papers answer in Researcher can show no written summary and no note saying why: the note "no written summary could be checked against the records" was missing at both widths on 2026-10-17, where card 38 slice C's check saw it | Card 125's product check, PR-card125-02 (`testing/Developer/reports/2026-10-17_product_check_card125/report.md`); not traced to card 125, whose change never touched the note's code (`core/graph.py`) | Part live (#291). Still open: an answer where some sentences were stripped shows no summary and no reason. Your call of 2026-10-25: its note stays beside the failed-search note and cards 74 and 77's notes |
| 129 | Design with you first | `How many genes are associated with breast cancer?` answers "I found 1 record related to breast cancer", the record named "Seen by breast cancer nurse", with a note listing upper-case entity names. Large: how the question is read and searched | Browser retest, row 28 and the defects table (`testing/Developer/reports/2026-10-18_browser_retest/report.md`) | Folded into card 56's redesign by your call of 2026-10-25 (#295 closed): card 56's call 1 is the binding rule it needs; the "both" count is designed there |
| 130 | Design with you first | Many common questions show no written summary, only a count line and a list: TP53 orthologs, CFTR variants, MODY genes, `What are rs334 and rs6025?`, colistin isolates, query 104. The note says why, but a person reads a list. Large; card 128 is one case | Browser retest, rows 4, 7, 48, 54, 57 (`testing/Developer/reports/2026-10-18_browser_retest/report.md`) | Root fix closed by your call of 2026-10-25 (#294): revisit only with a new design; cards 128 and 131 carry the no-summary lists meanwhile |
| 131 | Team: buildable now | Where a summary exists, its first sentence often counts records or lists codes instead of answering: "I found 8 conditions related to bronchiolitis", 20 isolate codes, 13 HGVS names in a sentence, paper titles strung with their own full stops ("Regulator., Preneoplastic ... lethality.."). Large | Browser retest, rows 3, 7, 23, 38, 48 and the defects table (`testing/Developer/reports/2026-10-18_browser_retest/report.md`) | Part 1 live (#292, in Retest). Part 2 closed by your call of 2026-10-25 (#296): the count line stays. A sentence of record codes opening the answer waits for card 110 |
| 132 | Team: buildable now | An answer misses part of what was asked: "Compare MLH1 and MSH2" describes one gene; the Mediterranean question never names Familial Mediterranean fever; bronchiolitis never says what causes it; "and what about it in children?" says nothing about children. Large | Browser retest, rows 15, 38, 44, 52 (`testing/Developer/reports/2026-10-18_browser_retest/report.md`) | Nobody on it; filed 2026-10-18 from the browser retest, after the poster |
| 133 | Team: buildable now | The list total and the sources count differ by one: MLH1 and MSH2 24 against 23, the CFTR window 71 against 70, TP53 GEO 23 against 22, TP53 orthologs 41 against 40. Medium; card 22's "one count everywhere" | Browser retest, row 37 (`testing/Developer/reports/2026-10-18_browser_retest/report.md`) | Live (#300) except query 116's "Found 40" over 41 gene rows, a separate cause in the opening line |
| 136 | Team: buildable now | "Your searches": only the latest 20 show, with no way to reach older ones; searches made as a guest before signing in are carried in but read "No answer saved" though they were answered; at phone width picking a search leaves the drawer open over the answer. Medium | Browser retest, rows 18, 21, 35 (`testing/Developer/reports/2026-10-18_browser_retest/report.md`) | Nobody on it; filed 2026-10-18 from the browser retest, after the poster. Part 3 live 2026-10-29 (#313, in Retest): the phone drawer closes after a pick. Part 1, older searches, built overnight 2026-10-29 and under review. Part 2, guest searches, waits for your call (`testing/Developer/reports/2026-10-29_card135_136/diagnosis.md`, 136.2) |
| 137 | Team: buildable now | The BRCA1 gene record is listed twice, "BRCA1 DNA repair associated" and "BRCA1", on `What does BRCA1 do?` and a BRCA1 follow-up; query 1 in Researcher shows a heading "DNA REPAIR PATHWAY DISEASE" over one broken fragment. Medium | Browser retest, rows 15, 31, 40 and the defects table (`testing/Developer/reports/2026-10-18_browser_retest/report.md`) | Part 1 live (#300, in Retest). Part 2 by your call of 2026-10-25: when a sentence's uncited ending is stripped, the whole sentence is dropped, not kept as a fragment |
| 139 | Team: buildable now | Notes that say the wrong thing: "listed below" under the list; query 104's "this answer shows 10" where it shows 5; "does not address the following entities named in the question" naming entities the question never named (CFTR-AS1, LOC numbers). Small | Browser retest, rows 47, 49, 54 (`testing/Developer/reports/2026-10-18_browser_retest/report.md`) | Notes 1 and 2 live (#297, in Retest). Note 3 (#301, draft) to be reworked by your call of 2026-10-25: names only what the question named, keeps develop's "ask" when coverage is weak. Also by your call: a kind showing none gets one true line ("NCBI lists N ... linked to this paper; none are shown in this answer") |
| 140 | Design with you first | The follow-up chips are always "What variants cause it?", "Which trials are recruiting?", "What does the literature add?", also after isolates, papers or MODY questions where they do not fit | Browser retest, defects table (`testing/Developer/reports/2026-10-18_browser_retest/report.md`) | Nobody on it; filed 2026-10-18 from the browser retest, after the poster |
| 142 | Team: buildable now | The command line's Ctrl-C prints "s3: interrupted, stopping the run..." and then "error: the run ended before a final answer was received", calling the person's own stop an error. Small | Browser retest, row 39 (`testing/Developer/reports/2026-10-18_browser_retest/report.md`) | Redesign by your call of 2026-10-25 (#298 closed): the stop line at once, the stop confirmed in the background under a short bound, a second Ctrl-C as the hard exit |
| 144 | Team: buildable now | Four of about 35 timed answers ran over 20 s: query 117 in Researcher 32.5 s (Think alone 13.6 s), TP53 orthologs 21.3 s and 23.6 s, a BRCA1 follow-up 20.7 s | Browser retest, Timings (`testing/Developer/reports/2026-10-18_browser_retest/report.md`) | Nobody on it; filed 2026-10-18 from the browser retest, after the poster |
| 145 | Design with you first | `What causes bronchiolitis in babies, and how is it usually treated?` is asked back "which gene, variant or condition do you mean?" about half the time (2 of 4 on production, also on develop): the question step does not always recognise bronchiolitis as a condition, though it is one. Medium | Production check after release v0.3.0 (`testing/Developer/reports/2026-10-18_browser_retest/report.md`, "Production check") | Folded into card 56's redesign by your call of 2026-10-25 (#293 closed): the second reading is built there with the "does this question name its own subject?" check |
| 146 | Team: buildable now | A retracted paper is listed by its full title with no mark that it was retracted (the Wakefield paper, PMID 9500320) | Card 134's adversary, A-134-02 (`testing/Developer/reports/2026-10-22_card134/adversary.md`) | Designed by your call of 2026-10-25: a "Retracted" tag beside the title from PubMed's own publication type, and the writer told not to state its findings as fact |
| 149 | Team: buildable now | A question about the human GCK gene cites "Gck", linked to NCBI Gene 24385, which is the rat gene, not human GCK (2645): a confident wrong record | The product check of cards 135 and 136 on deployed develop, PR-135-136-06 (`testing/Developer/reports/2026-10-30_product_check_135_136/report.md`); species confirmed by the lead from NCBI Gene on 2026-10-30 | Nobody on it; filed 2026-10-30 overnight, cause not diagnosed |
| 150 | Team: buildable now | After a windowed papers answer, "What did the first paper in that list find?" is answered about a different paper: after BRCA2 with the last 5 years, the reply described kidney transplant mortality under "Found 5 papers for BRCA2"; develop named a graph paper that was not in the list. A confident wrong answer to a natural follow-up | Card 119's adversary, A-119-03 (`testing/Developer/reports/2026-10-29_card119/adversary.md` on #312's branch) | Nobody on it; filed 2026-10-30 overnight, cause not diagnosed |
| 151 | Team: buildable now | "Show me more papers" after a windowed answer drops the picked window without saying so: after PALB2 with a window it listed 70 knowledge graph papers from 2002 to 2011, and the 10,113-character answer is cut on MCP and GraphQL | Card 119's adversary, A-119-07 (same report); not yet run against develop | Nobody on it; filed 2026-10-30 overnight |

Below sits the detail behind architecture cards 8 to 13 and card 14, 11.11.
It moved here from `testing/UI_fixes_done.md` on 2026-09-24 without a word
changed:

- The product owner will build this work, so no architecture card is parked.
- A status or position written inside the detail records the day it was
  written, and the cards above are current. Among them:
  - 11.32 and 11.38, "backlog only"
  - 11.32, "parked as a discussion that precedes a build"
  - 12.3, "the product owner's open decision", now live and in Retest
  - 11.11, "Tenth" in "Next, in order", now fourteenth
- Set 11's intro, which the table below points to, stays in
  `testing/UI_fixes_done.md`.
- The product owner's direction on the model architecture, in their own
  words, follows the detail for 11.38.

### Set 11, still open

Set 11's intro below defines most of the status words these rows use.

| # | Your feedback | Status | Where it stands |
|---|---|---|---|
| 11.11 | Yours: your architecture work | Use your reference prototype for answer depth, formatting and structure; it writes with a different model family | Queued | Tenth in "Next, in order". It was listed as in progress until 2026-09-24 with nobody on it, so it moved out of section 1. 12.9 and 12.10 answered part of its ask. The answer-writing model is unchanged: switching models is a separate decision |
| 11.29 | Yours: your architecture work | Think big about connecting the dots: if everything were in the knowledge graph, from PubMed literature to sequence, clinical and PubChem data, how do we find hard edges (direct relationships) and soft edges (indirect, through multi-hop)? Do we need RAG pipelines, vector embeddings, a hybrid knowledge-graph model? | Discussion, precursor to a build | Reclassified 2026-09-22 by the product owner: a discussion that precedes a build under `/bossman-mode`, not a question waiting on them. Raised 2026-09-20. Full detail: [11.29](#detail-1129) |
| 11.32 | Yours: your architecture work | Wrap the Layer 2 and Layer 3 API calls in internal MCP servers. "Why dont we wrap our layer 2 and layer 3, the api calls in internal mcps ... can understand from the API keys on how to setup things for each database. Maybe just add to the list for now" | Discussion, precursor to a build | Reclassified 2026-09-22 by the product owner: scoped in a discussion first, then built under `/bossman-mode`, still against the locked Section 6 tool list. Raised 2026-09-20. BACKLOG ONLY, nothing designed and nothing promised. Full detail: [11.32](#detail-1132) |
| 11.38 | Yours: your architecture work | Try the new model on OpenRouter that returns probabilities with its output, and decide where calibrated confidence belongs in the architecture: the guardrail, the choice of which resource to pull, and the cite-or-refuse gate | Discussion, precursor to a build | Raised 2026-09-22 by the product owner, who named the guardrail and the resource choice. BACKLOG ONLY, nothing designed and nothing promised. IDENTIFIED 2026-09-23 from the two links the product owner gave: it is `typesafe/jev-1.13` from TypeSafe, and it fits two of the three places they named and not the third. CORRECTION, because the assistant said the opposite hours earlier: it is NOT a harness config change, because it answers on its own `POST /api/alpha/decisions` endpoint rather than chat completions, so a trial needs a new client path. Full detail: [11.38](#detail-1138) |

#### Detail 11.29

The ask: Think big about connecting the dots: if everything were in the
knowledge graph, from PubMed literature to sequence, clinical and PubChem data,
how do we find hard edges (direct relationships) and soft edges (indirect,
through multi-hop)? Do we need RAG pipelines, vector embeddings, a hybrid
knowledge-graph model?

Status: Discussion, not started

Raised 2026-09-20. A DISCUSSION ITEM, deliberately not a build item, and it
needs its own session rather than a slot in the fix loop.

Three things are worth settling before it opens.

- FIRST, most of the premise is not this repository's to decide: "everything
  is in the graph" is Systems 1 and 2, which live in a separate repository, and
  `.claude/rules/file-protection.md` forbids this repository writing into the
  graph at all, by direction of data flow. System 3 can only read.
- SECOND, vector embeddings, RAG pipelines and knowledge-graph federation sit
  on the v1 out-of-scope and fast-follow lists in
  `.claude/rules/v1-scope-boundary.md`; external non-NCBI federation has NO
  named trigger at all, so it stops and asks by rule. Discussing is free,
  building is not.
- THIRD, the multi-hop half is already real and measured rather than
  hypothetical: the live graph rejects edge alternation, `[:a|b|c]` fails with
  SyntaxError, so the broad search traverses `participates_in` alone and GO
  molecular activities and cellular components are not reached
  (`2026-09-19_breadth_wiring/build.md`). That is a soft-edge limitation
  sitting in the product today, and it costs one graph call per edge to
  widen .

THE PRODUCT OWNER'S OWN FRAMING, given 2026-09-20
when asked whether the product fails because the data is absent or because we
cannot find the path between things that are present: BOTH, and the headline
verdict is blunter than either: "the answers all look surface level and most
chatbots like ChatGPT, Claude, Gemini can answer better".

That is a judgement on the ANSWER PATH, not on presentation, and it is the bar
11.29 has to clear: not "does it cite" but "is it worth reading instead of a
general chatbot". Every presentation-side fix in Set 11 leaves that bar
untouched

#### Detail 11.32

The ask, in the product owner's own words: "Why dont we wrap our layer 2 and
layer 3, the api calls in internal mcps ... can understand from the API keys on
how to setup things for each database. Maybe just add to the list for now."

Status: Not started. Raised 2026-09-20, backlog only.

THE SOURCE MATERIAL THEY NAMED, both verified to exist on 2026-09-20: <!-- local-refs: allow -->

| What | Where |
|---|---|
| The connection maps and per-database deep dives | the owner's private notes (not published) |
| The databases paper | the `NCBI-databases-paper-09-2025` folder inside it |
| Open this first | `NCBI_database_connection_map.md`, then `NCBI_databases_deep_dive.md` and `NCBI_enterprise_infrastructure_deep_dive.md` |

NOTHING IS DESIGNED AND NOTHING IS PROMISED. This crosses the tool-integration
boundary the locked technical specification's Section 6 defines, which names
seven tools and their transports, so under `.claude/rules/v1-scope-boundary.md`
it is scoped against that section and signed off before any work starts, never
the other way round.

Two questions to settle when it is scoped, neither decided here.

- Whether an internal MCP server is a TRANSPORT SWAP underneath the existing
  seven tools, which would leave every tool schema and call site unchanged the
  way build phase 4.11's HTTPS graph service did, or a RE-CUT of what the tools
  are, which is a contract-version event under `system-design-patterns`
  pattern 10.
- And what it buys over the direct calls the tools make today, since
  `.claude/rules/supply-chain-security.md` treats every MCP server as an
  execution surface running with the app's own credentials, so the answer has
  to be worth that.

ANSWERED 2026-09-22, when the product owner asked directly whether wrapping
Layer 2 and Layer 3 in MCP would be faster and more reliable. The honest answer
splits their question in two, because the valuable half is not the MCP half.

On speed, no, and this is measured rather than argued.

- MCP is a protocol for one process to offer tools to another.
- It does not change what NCBI returns or how fast NCBI returns it, so
  wrapping our own calls in it adds a hop rather than removing one.
- Item 11.4 measured where the wait actually is: the searches take about a
  second, and the wait was the writing step.
- Item 11.8 then cut the median answer from 26.5 to 19.7 seconds by working on
  that step, not on the transport.
- Under `.claude/rules/attack-the-constraint.md`, the transport is not the
  constraint, so optimising it buys nothing a person would feel.

On reliability, yes, and the product owner's instinct is right, but the thing
that buys it is the half of their sentence that does not mention MCP:

- "reverse engineer the NCBI API, see what data exists, and build functions around them".

- That is a measured, typed function surface
- and it removes a real class of wrong answer, namely the agent choosing an
  endpoint or a parameter that does not mean what it assumed.

It is also the exact method that closed G-035 on the night of 2026-09-22:

- the FTP tree was measured live first (521 MB, 584,433 rows, a 17.7 second full scan)
- a wire contract was pinned from those numbers
- and the shape went from never answering to 5 of 5.

That method is available today, one tool at a time, with no protocol change and
no new execution surface.

So the two halves separate cleanly, and only one of them is blocked:

- The typed, measured function surface per database: valuable, in scope as
  ordinary work on the existing seven tools, and provably effective here.
- The MCP envelope around it: a transport change that earns its keep only if
  these tools must be callable by agents outside this product. That is a
  distribution argument, not a speed or reliability one, and it stays a
  scoping discussion against Section 6 as this detail already says.

Worth stating plainly, because the naming invites the confusion:

- This product already HAS an MCP surface, at `/mcp`, and it points the other way.
- It exists so other agents can call this product.
- Item 11.32 would point MCP inward, at our own calls, which is the direction
  that adds the hop.

#### Detail 11.38

The ask, raised 2026-09-22: try the new model on OpenRouter that returns
probabilities with its output, because it could help the guardrail and the step
where the agent chooses which resource to pull.

Status: Not started. Backlog only, nothing designed and nothing promised.

WHAT IT IS, established 2026-09-23 from the two sources the product owner
supplied, `https://typesafe.ai/` and
`https://openrouter.ai/docs/guides/community/jev`. Read as vendor claims, which
is what they are; nothing below has been measured against this product's own
questions yet.

| Fact | Value |
|---|---|
| Model id | `typesafe/jev-1.13`, alias `~typesafe/jev-latest` |
| Maker | TypeSafe, who call it a "System One Model" |
| Endpoint | `POST https://openrouter.ai/api/alpha/decisions`, NOT chat completions |
| Question types | Choice: the selected option, a probability for every option, and a confidence. Bool: the probability of yes. Score: a probability-weighted position, a probability per level, and a confidence |
| Context | 32,000 tokens, state plus questions |
| Price | Input tokens billable, OUTPUT TOKENS FREE. Vendor claims $42 per billion input tokens |
| Vendor speed and cost claim | 193.6x faster and 244.6x cheaper on their own "System One" tasks: 0.114s and $0.000081 against 8.566s and $0.013880 |

THE LIMITATION THAT DECIDES WHERE IT CAN GO, in the vendor's own words:

- "Jev does not produce reasoning traces, explanations, or free-form text"
- and "It is not a drop-in replacement for a chat model."

That single sentence sorts the whole question. The product owner named three
places. Two of them are decisions, and Jev is built for exactly that shape. The
third is writing, and Jev cannot do it at all.

| Where | Shape today | Does Jev fit |
|---|---|---|
| Guardrail | A Guard-tier chat model classifies the input, and the answer is taken as certain | YES. This is a Choice with a confidence, which is what the step actually needs. A borderline question could be asked about rather than guessed at |
| Which resource to pull | Think and Plan pick from a fixed plan per question shape | YES, and it is the better of the two. The option set is closed and known, which is the condition a typed decision needs |
| Writing the answer | The Synth tier writes prose with inline citations | NO. It emits no free-form text. Not a candidate, at any price |

ON "ZERO HALLUCINATIONS", which is on the vendor's front page and should be read
carefully rather than quoted.

- The honest version of that claim is structural: a decision constrained to a
  fixed option set cannot return an option outside the set.
- That is real and it is worth something here, since this product's failures
  include the model reading MODY as an organism (item 11.19).
- It is NOT a claim that the chosen option is correct, and it must never be
  repeated to a user as though it were.

WHY THE INSTINCT IS SOUND, independently of which model it turns out to be. The
loop currently makes three decisions that are taken as if certain and are not:

| Decision | Where | What is lost today |
|---|---|---|
| Is this input safe and on topic | Guardrail | A borderline question is admitted or refused outright, with no middle path such as asking the person what they meant |
| Which resource answers this | Think and Plan | A wrong pick is invisible: the answer comes back confidently sourced from the wrong place |
| Is this claim supported | Write, the cite-or-refuse gate | The gate is deterministic by design, which is correct; a calibrated confidence would inform what the answer SAYS about its own certainty, never whether the gate passes |

A calibrated confidence turns each of those from a silent guess into a number
that can be acted on, and the third one is the trust moat: a product that can
say "I am not sure" honestly is worth more than one that is fluent and wrong.

WHAT IS CHEAP AND WHAT IS NOT, since these are usually conflated.

A CORRECTION FIRST, recorded rather than quietly fixed:

- on the night of 2026-09-22 the assistant said trying this model would be a
  config change under `system-design-patterns` pattern 11, reversible in one
  edit.
- That was said before the model was identified and it is WRONG for this
  model.
- Jev answers on its own `/api/alpha/decisions` endpoint, not on chat
  completions, so `resolve_model()` pointing a tier at it does nothing.
- A trial needs a new client path in the harness, which is a small build
  rather than a config edit.
- The cost estimate moves with it.

What remains cheap:

- the trial is still bounded and reversible, because the two candidate call
  sites are decisions with closed option sets, and either can fall back to
  today's path on any error.
- Output tokens being free makes a side-by-side shadow run, where Jev decides
  in parallel and its answer is only recorded rather than acted on, unusually
  affordable.
- That shadow run is the right first step, because it produces this product's
  own calibration data instead of a vendor benchmark.

What is NOT cheap: ACTING on a confidence number. A threshold anywhere in the
loop is a new control with its own failure modes, it must be calibrated against
this product's own questions, and under `.claude/rules/goal-contracts.md` a
threshold is a verify surface that must not be quietly lowered later to make
results look better.

TWO CONSTRAINTS THAT BIND ANY TRIAL, both from rules already in force:

- The cite-or-refuse gate stays DETERMINISTIC. `.claude/rules/production-standards.md`
  requires accept or reject by exact or substring match and says outright that
  fuzzy scoring may rank repair suggestions but never gates acceptance. So a
  confidence number may inform what an answer SAYS about its own certainty, and
  may never decide whether a citation passes. This is the place a probability
  model is most tempting and most dangerous.
- `/api/alpha/decisions` is an ALPHA endpoint, and the guardrail is on the path
  of every single query. A dependency that can change under us does not belong
  in front of everything until it has a fallback that is proven by execution
  rather than asserted.

#### Detail 13.1

The ask, raised by the product owner on 2026-09-25 after a codeathon: RAG-style retrieval of the specific sections of a source that answer the question, since today the product hands people sources and they still have to browse them.

Status: Not started. Decided 2026-09-25 (`DECISIONS.md`): add the card, probe first.

- The source: NCBI's LitSense, sentence-level search over PubMed abstracts and PMC full text, with the index hosted by NCBI. The locked technical specification already names it as a Layer 3 source in Section 5; nothing in the code calls it yet.
- The probe, first: about ten golden literature questions sent to LitSense live, measuring whether the returned sentences answer the question and how long each call takes.
- The build, if the probe holds: the answering sentences shown quoted under each paper, each cited. Verbatim sentences pass the cite-or-refuse gate by construction.
- Not built: chunking or embedding full texts ourselves, which is a data-pipeline project for the data repository.
- Budgets: one of the twenty per-query calls, a 15-second timeout, and the provisional 5 requests per second throttle, since LitSense publishes no rate limit.

### The product owner's direction on the model architecture, 2026-09-23

Added on the product owner's instruction, IN THEIR OWN WORDS, unedited. Quoted
rather than paraphrased because they asked that the wording not be changed.

> 1. Do we need to rethink the model use architecture, this ties into use of Jev from TypeSafe that we need to discuss.
>
> a) Jev becomes our classfier -> 1-3 words -> clarification question or move forward -> guardrails on the terms of relevancy or any place where a choice needs to be made.
> b) Here is where I do think converting our NCBI APIs and enrichment calls into functions MCP style do make sense. This way easy for Jev to help with the classifer
> c) We use Jev as a classifier where ever we are making those decisions
> d) Ideally we need opensource model but if frontier are needed then so be it.
>
> For instance, example, how models should be chosen, using frontier models as example, if equivalent opensource is available then amazing
>
> OpenAI/Claude example:
>
> Luna/Haiku/Sonnet for query classification, metadata cleanup, simple extraction, routing, or highvolume answer drafts.
> Sol/Opus 5.5 for multi-step retrieval planning, evidence synthesis, code generation, complex user
> questions, and tool-using workflows.
> Astra/Fable 5.1 for difficult scientific reasoning, ambiguous tasks, high-risk decisions, or final
> escalation when lower-cost models cannot reach a quality threshold.
>
> Then another thing you added was the model check.

Added later the same evening, again in the product owner's own words, unedited:

> What we need to be able to do in here. We are a agentic search:
> A conventional chatbot produces text in response to a question.
> An agent works through a sequence: 1.
> It interprets an objective.
> 2.
> It makes a plan.
> 3.
> It uses tools, such as a terminal, browser, spreadsheet, or internal system.
> 4.
> It checks intermediate results.
> 5.
> It adjusts when something fails.
> 6.
> It produces or applies a final result.
> For example, “modernize this legacy service” is not one answer.
> It may require locating dependencies, changing thousands of lines, running tests, investigating failures, revising code, documenting changes, and opening a review.
> The modelʼs value depends on completing the entire loop, not simply generating a plausible code snippet.

Where this connects to items already in this plan, stated by the assistant and
kept separate from the quote above:

- Point a), the 1-3 word clarification question: item 12.3, the product
  owner's open decision, with the fix-2 evidence (`BRCA1`, `MeSH`, `Marfan`
  and `recent papers on statins` all answered without asking).
- Point b), NCBI APIs and enrichment calls as MCP-style functions: item 11.32,
  parked as a discussion that precedes a build.
- THE MODEL CHECK: a decision point added on 2026-09-23 under items 12.9 and
  12.10, approved by the product owner the same evening.
  - A guard-tier model decides whether a sentence the answer model REWORDED
    says anything more than the exact record words it quotes, after code has
    verified the quote is in the record character for character, the numbers
    are in the quote and the negation matches.
  - It fails closed.
  - It is exactly the kind of yes-or-no decision point point c) names, and a
    candidate for Jev's Bool question type once a shadow run has calibrated
    it.
  - It amends the first constraint above (the cite-or-refuse gate stays
    deterministic) for that one bounded case: the rule text changes in pull
    request #101, and the reasoning is in DECISIONS.md on 2026-09-23.

ONE STANDING RULE TO HOLD AGAINST IT, `system-design-patterns` pattern 11 again:
on a recurring failure, iterate the harness first and swap the model second. So
a probability-emitting model is worth a bounded trial on its own merits, never
as the answer to a failure the harness has not been worked on yet.

## Build in progress

| What | Cards | Where |
|---|---|---|
| Two reviews of the harness, since "I do not think our harness works well right now": the product's, which turns a question into an answer, and the build's, which is how the product gets built; each ends in ranked changes and questions for you | the product owner, 2026-09-25 | `testing/Developer/reports/2026-09-25_harness_review/product_harness.md` and `build_harness.md` |

## Retest

Moved on 2026-10-15, at the product owner's request, to `testing/Retest_product_owner.md` (before that, from 2026-10-06, a section of `testing/UI_fixes_done.md`). A card that is built and live waits there for your verdict; it is not work to do and is not counted here.
