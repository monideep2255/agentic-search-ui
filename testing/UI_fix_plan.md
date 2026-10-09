# UI fix plan

The board for the UI fix loop. An item starts in To do and moves to Build in
progress when someone starts it. Once it is live on develop it moves to
"Waiting for your retest" in `testing/UI_fixes_done.md`, and your verdict
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

Last updated: 2026-10-08.

## To do

In priority order.

| # | Feature, in plain words | Item | Waiting on |
|---|---|---|---|
| 56 | A question about SARS-CoV-2 is answered about the disease SARS, so a person gets a confident wrong record and no sequencing runs | Card 56 diagnosis (`testing/Developer/reports/2026-10-05_card56/diagnosis.md`); the fix (#173) passed 3 of 3 local Think and Plan runs but failed on develop on 2026-10-05 (`testing/Developer/reports/2026-10-05_final_test_queries/results.md`) | Part live once merged (#186 or the next number): the plain SARS-CoV-2 question no longer binds the SARS disease (0 of 20 live runs, 5 of 26 before). Still open, for a design with you first: "SARS CoV-2" typed with a space still binds SARS; after a gene in the same conversation a missed SARS-CoV-2 question uses the remembered gene; "SRA runs from AML-derived cell lines" can lose its leukaemia match; the "Illumina" refusal (7 of 20 runs). Evidence: `testing/Developer/reports/2026-10-06_card56/` |
| 101 | A reworded sentence can reach the screen without passing the sentence check: a bronchiolitis answer said "For babies with severe bronchiolitis" where its record says children, and that sentence was never among the check's candidates. Re-aimed 2026-10-06 from card 99's sentence cost, whose writer line measured no gain | `testing/Developer/reports/2026-10-06_card101/fix_round.md`, "For the owner" | Part live (#193, #204, in Retest). Its last three slices were built on 2026-10-08 overnight and parked after both reviews found a new sentence splitter worse than develop; it needs a design for where a record sentence ends. Evidence: `testing/Developer/reports/2026-10-08_card101/` |
| 94 | Isolate questions answer with a table of isolates and their resistance genes: the default mode often shows names without genes, the blaCTX-M note is missing, a colistin question returns a suspicious zero, and a single-isolate answer lacks its details (queries 33, 35, 36, 44 and the isolate workflow); some counts differ only because the snapshot is newer | G-035; failed the batch retest of 2026-09-29 (`testing/Developer/reports/2026-09-29_retest/`) | Part live (#158, #165, #169, #174, in Retest). Still open: the place column, a single-isolate lookup and a follow-up such as "from 2023"; diagnosed 2026-10-08 (`testing/Developer/reports/2026-10-08_overnight/card94_diagnosis.md`), built after phase 8.7 merges |
| 84 | R-10's guardrail fixes on their own | Built, then stopped at the owner's choice on 2026-09-29 after its adversary found an off-topic question and a disguised injection admitted when the provider rate-limits (F-84-A05, A07); its branch (tip 5a0adc02) deleted on 2026-10-08 after the design described every commit; records in `testing/Developer/reports/2026-09-29_card84/` | Built overnight on 2026-10-08 with card 72 and parked (pull request #217 closed): its fix round admitted a follow-up after a long server pause that develop refuses and over-charged Jev replies. Your call on the re-split proposed in its `DECISIONS.md` row; code under the local tag `parked/card84-72-guardrail-2026-10-08`; reports in `testing/Developer/reports/2026-10-08_guardrail_design/` |
| 72 | A search fails with "a temporary error" because the guard model did not answer in time, twice: 4 of 150 golden runs on 2026-09-29. The first hedged design lost searches in a slow spell and let an off-topic question through on the relevancy check (F-72-V08), and was not merged | Diagnosis: `testing/Developer/reports/2026-09-29_card72/diagnosis.md`; the deleted branch's verifier (`testing/Developer/reports/2026-09-29_card72/verifier.md`): F-72-V06 and V08 | Part live (#159): one log line per guard and Jev call. Its fix is the guardrail re-split with card 84 (your call); step 2, host routing, waits for a week of logs that name a cut call's host (`testing/Developer/reports/2026-10-08_guardrail_design/step2_data.md`) |
| 75 | An AI agent that sends an unknown argument whose name contains "bearer token" makes `s3 mcp` tell the person to log in again, and two Authorization headers or an empty "Bearer " get the wrong fixed message | Card 62's adversary F-62-A06 and judge F-62-J06; the fix `3842019f` was dropped because production does not send the field it keyed on (F-62-V03, `DECISIONS.md` 2026-09-29) | Factory's next card (`docs/build/Factory_onboarding.md`, card 75), from card 61's review (#190): after a sign-in renewal reply that cannot be read, a second request through the same bridge resends the spent token and production signs the person out of the command line and the web app (on develop today too). The fix latches the bridge after an unreadable or refused renewal, so it never calls /auth/refresh again in that process, tested with two calls. The older items in this row stay out of that section: they wait for the server's `data.reason` refusal field to land and reach production first, then the client change |
| 85 | Small accuracy fixes, one card: two page sentences still false on some paths (the layer 3 stop names three kinds of question searched another way where there are five, and the About walk says BRCA1's live searches run at the same time as the graph, where four of thirteen run in a second round); and behind the scenes, the facts checker's remaining gaps and three logging gaps (a crash's reason on the lines after its trace id, step-level failures that log no reason, and an older database warning that logs a full error message) | Folded from cards 76, 78, 81, 82 and 83 at the owner's choice, 2026-09-29; detail in `testing/Developer/reports/2026-09-29_card53/verifier.md` and `testing/Developer/reports/2026-09-29_card73/` | Part live (#167, #220, in Retest): the page sentences and the logging slice. Still open, each yours: the facts checker's gaps, under `.claude/`, and the five `exc_info` warnings (A07) |
| 2 | Every answer opens with the code-built "Found N ... records for X" line, whatever the writing model, so its first sentence never answers the question | `testing/Developer/reports/2026-09-25_writer_bench/results.md` and the 8.1 product review; the design: `testing/Developer/reports/2026-09-26_phase_8.7/design.md`; phase 8.10's product review, PR-8.10-02 (`tracker/phase_8.10.md`): the Plain language BRCA1 answer opens "I found 4 conditions related to BRCA1" and names no disease | Phase 8.7, pull request #218, waiting for your call: built, reviewed, fixed once and checked live on its branch; its fresh verifier found two things worse than develop (A04, A07). Two options on the pull request |
| 4 | Tell the reader when the system wrote its own search rather than using a checked one | the drafted search | Nobody on it |
| 5 | Models chosen per task by tier: open source where an equivalent is available, frontier models where they are needed | [direction, point d](#the-product-owners-direction-on-the-model-architecture-2026-09-23) | Built in phase 8.7 (#218). Your choice when it merges: develop sets its own `SYNTH_MODEL`, so its writer stays as it is until you switch it; at a true 25-cent bound Opus's repairs are refused on 3 to 19 of 24 bench questions |
| 6 | The agentic loop: interpret the objective, make a plan, use tools, check intermediate results, adjust when something fails, produce or apply the final result | [the agentic loop](#the-product-owners-direction-on-the-model-architecture-2026-09-23) | Nobody on it |
| 7 | Hard and soft edges over a fuller graph, "connecting the dots" | [11.29](#detail-1129) | Nobody on it |
| 8 | The trust-line wording | 9.9; built on the unmerged branch `phase/8.4-answers-worth-reading`, not on develop | You chose, 2026-09-25: say what was checked. Planned: phase 8.9, from the parked 8.4 commit with "which differ" corrected |
| 9 | Judge answer quality once answering is reliable | 10.4 | Nobody on it |
| 11 | The same question does not always return the same papers: six identical PubMed searches returned two different sets, and `reflux disease` found nothing on one run in six | Where we stopped, notes carried over from the old tracker; tried 2026-09-25, not reproducible, fix reverted: `tracker/phase_8.1.md` F-8.1-03 | Proposed for closing, 2026-10-08: not reproduced since 2026-09-25 and its fix reverted; reopen on a failing test query |
| 12 | The trust verdict under an answer changes with nothing else changed: five runs on identical evidence gave `flag` four times and `ask` once | Where we stopped, Next, in order; tried 2026-09-25, the fix labelled correct answers as disagreeing and was reverted: F-8.1-A13 | Proposed for closing, 2026-10-08: not reproduced since 2026-09-25 and its fix reverted; reopen on a failing test query |
| 14 | One search took 127 seconds against a median of 14, and nobody owns it | Shipped days, 2026-09-20; diagnosed 2026-09-25, a timeout that stops the wait but not the work: F-8.1-05 | No run passed 60 s in phase 8.7's 32 live runs on 2026-10-08 (slowest 58.6 s); closes when phase 8.7 merges, per your decision of 2026-10-05 |
| 15 | Close the remaining path where the system writes its own graph search, or ask the reader instead; card 7 only tells them | L-01 | Step 1 live (#171). The next step was built on 2026-10-08 overnight and parked (pull request #216 closed): one record for every non-count question gave wrong or thinner answers. Needs one checked template per question shape (`testing/Developer/reports/2026-10-08_card15/`) |
| 16 | Three golden questions get nothing from the graph: G-005 and G-022 find nothing, and G-036 never searches it | Where we stopped, loose ends | Diagnosed 2026-10-08: G-022 fixed; G-005 fails on the "Illumina" refusal card 56 holds for a design. Proposed: fold into card 56 (`testing/Developer/reports/2026-10-08_overnight/card16_diagnosis.md`) |
| 17 | A reworded sentence that switches papers can point at the wrong paper when the only title word it shares is a generic one, such as "patients" | 12.16 part 4; built on the unmerged branch `phase/8.4-answers-worth-reading`, not on develop | Your design choice: five options with their costs in `testing/Developer/reports/2026-10-08_overnight/card17_diagnosis.md` |
| 18 | A record with several sentences shows as several list rows under one heading, and no test covers it | Where we stopped, loose ends; a helper is on the 8.4 branch, its wiring in `core/graph.py` is not built | Diagnosed 2026-10-08: mostly fixed; two rows remain when a record's sentences pass 1000 characters. Built after phase 8.7 merges |
| 19 | The paced handoff may show a false writing step on some other path, and nobody has checked | 11.28 | Diagnosed 2026-10-08: no false writing step found; one real gap (a call skipped at the 20-call limit). Built after phase 8.7 merges |
| 20 | An isolate search can filter only by gene prefix | Shipped days, 2026-09-22; year from the question built on the 8.4 branch, location needs the plan step | Your design choice: where the year and place come from (`testing/Developer/reports/2026-10-08_overnight/card20_diagnosis.md`) |
| 24 | Where the Plain language and Researcher toggle goes | Where we stopped, waiting on the product owner; built on the unmerged branch `phase/8.4-answers-worth-reading`, not on develop | Your decision of 2026-10-06: the switch sits beside the answer's header, its cost shown on click (D21). Factory's card after 75 (`docs/build/Factory_onboarding.md`, card 24): it ports the switch built in commit `df7d7a2c`, kept under the local tag `parked/phase-8.4-2026-09-25` since the branch left the remote, and adds the cost shown on click |
| 25 | Install the public USWDS package, the base of the NCBI design system: yes or no | 2.13; decided 2026-09-25, not built | Out of Factory's lane on 2026-10-06: a new package needs your approval and a supply-chain review first. Before: Nobody on it |
| 29 | Under each cited paper, show the one sentence of its own abstract that answers the question, quoted and cited (replaces the LitSense route, closed 2026-09-25: LitSense cannot be pointed at a paper) | [13.1](#detail-131), DECISIONS.md 2026-09-25 | Your choice: how many papers get a sentence, a cost and speed question (`testing/Developer/reports/2026-10-08_overnight/card29_diagnosis.md`) |
| 30 | `Which BRCA1 variants are pathogenic?` lists 40 unclassified variants and the model's honest caveat is stripped | `tracker/phase_8.1.md` F-8.1-A16, found 2026-09-25, older than that night | Diagnosed 2026-10-08: the honest note is built after phase 8.7 merges; fetching classifications is a cost choice for you |
| 33 | Two golden questions that answered on 2026-09-22 no longer do: G-004, a Salmonella isolate question that runs no search, and G-006, sequence data for PMID 11237011 | the golden run of 2026-09-25, `testing/Developer/reports/2026-09-25_phase_8.1_golden/` | Diagnosed 2026-10-08: G-006 fixed (#172); G-004 waits on your decision D19 |
| 35 | An off-topic follow-up that happens to contain a biomedical word such as "cell" or "study" still gets through, as it did before tonight | `tracker/phase_8.2.md` F-8.2-V01 | Diagnosed 2026-10-08: small; built after the guardrail re-split, since both change `guardrail_node` |
| 36 | A picked "How far back" window is lost after a restart or deploy, and nothing tells the person | F-8.2-V02 | Live (#215, in Retest): the plan line says when a picked or typed date range could not be applied. Still open, your design choice: making a picked window survive a restart |
| 37 | `What is rs334 and what condition is it associated with?` lists rs334348, rs334353 and rs334773 as if they were rs334: they are different variants that only share its first digits. The rs334 record itself is named by its list of clinical significance values, with no gene or condition | the phase 8.7 design, row G-024; `tools/litvar2_lookup.py` keeps LitVar2's near misses by design (F-3.3-A-01) and nothing downstream drops them | Part live (#213, in Retest): rs334 lists only rs334. Still open: the rs334 row named by its clinical significance labels; planned in phase 8.9 |
| 38 | Some answers list records that cannot answer what was asked: TP53's orthologs carry no species, CFTR's papers carry no title, and the ESBL isolates do not say which gene each carries. Not yet known whether the graph lacks the field or the search does not ask for it | the phase 8.7 design, rows G-016, G-021 and G-035 | Diagnosed 2026-10-08: orthologs' species and papers' titles; phase 8.9 tickets, built after phase 8.7 merges |
| 40 | Make the harness work well: carry out what the two harness reviews recommend, for the product's question-to-answer harness and for the build harness | the product owner, 2026-09-25: "you take charge and implement the improvement"; the reviews: `testing/Developer/reports/2026-09-25_harness_review/` | The itemized list is written: 27 items, each your yes or no (`testing/Developer/reports/2026-10-08_card40/itemized_list.md`); nothing in the security layer changes before you answer |
| 42 | The build team checks the product the way a person uses it, so the owner's retest confirms rather than discovers: it writes the code, verifies it, runs the judge and the adversary, checks the result against a `/design` of what the owner wants, and ends with a `/verify` of the QA and UI work. Two months of building left more than 100 UI fix items for the owner to find | the product owner, 2026-09-26: "for the QA and UI checks you depend on me, I do not like that, ideally I would want you to be confident on the UI check and me not have to give you the instructions everytime" and "the bossman mode team should be able to write the code, verify the code, judge, averserial, then have a /design for what I want and in the end /verify the QA work. This whole end to end is what we need to build." Inspired by the talk "Building verification loops in Claude Code" (https://www.youtube.com/watch?v=mQZB0l-rhxE) | Queued by the owner behind the running work: phase 8.6's golden run, the build-harness and hook-gap pull requests, card 39 and phase 8.9's opening. Proposal: `docs/build/Verify_loop_proposal.md`, waiting for the owner's yes before anything is built |
| 48 | A fuzzy question such as "Tell me about the tree of life." or "How do birds fly?" gets a list of loosely matched papers; the owner wants it to ask which aspect the person means first | The product owner, 2026-09-26: "When there are fuzzy questions like this, clarify." Measured by the re-land's adversary, F-8.6-RA04 in `tracker/phase_8.6.md` | Your design choice: whether "How do birds fly?" asks back, and the extra writer call's cost (`testing/Developer/reports/2026-10-08_overnight/card48_diagnosis.md`) |
| 50 | Nobody waits in silence: an answer shows its records within seconds, then its sentences one by one as each passes its check, and most answers finish near 20 seconds without giving up a correct one. Twenty seconds is a guide, not a hard limit (`DECISIONS.md`) | The product owner, 2026-09-26: "at most, it should take in my opinion 20 seconds" (`DECISIONS.md`). The re-land's golden run: median 17.1 s, p90 24.9 s, worst 31.3 s, and the answer text appears all at once at the end (F-8.6-P11). Follows card 3; phase 8.10's product review, PR-8.10-14: the web showed each answer at about 30 seconds while its own meta line said about 11, and `s3` and MCP took 14 to 15 | Phase 8.7, pull request #218, waiting for your call: records at a median 9.3 s against 27.3 s for the whole answer on its live check |
| 51 | Nothing the app tells people about itself goes stale as the backend changes: the About, Architecture, Integrations and home pages, the tour and the access notes, and the reference documents that repeat the same facts | The product owner, 2026-09-26: "the information that we are providing on the UI is not stale and it reflects the current uh, updates ... this could just be part of the verify skill" (`DECISIONS.md`). Extends card 42 | Part live (#156, #219, in Retest): the About page no longer describes the retired track. Still open, yours: a registry of every page claim |
| 52 | Every answer, whatever the question, ends by offering the next useful step, decided from that answer's own context and never from a template or a topic list. For example "Would you like the clinical trials recruiting for GERD, or the genes linked to it?", and a click continues the same conversation with its context. Today an answer ends on its table, and the only offer is "go deeper" into records it left out | The product owner, 2026-09-26, after asking "GERD" beside a general AI search answer that ended "Would you like me to put together a sample 1-day meal plan ... or would you prefer a list of safe ingredient swaps": "It is beautiful orchestration of continuing the discussion and searching for the next thing or guiding the user in the conversation. Ideally my ai agent system needs to be able to do this. This will help with the follow up too." Then: "GERD was an example of the follow up, do not hard code." Builds on the next-step offer of 2026-09-01 and 2026-09-13 (`DECISIONS.md`) and sits beside card 48 | Designed, 2026-09-26: `testing/Developer/reports/2026-09-26_conversation_next_steps/design.md`. The writing model proposes at most three follow-up questions from the answer's own findings, code checks each is answerable and names a record the answer found, and Jev decides it asks what records hold, not advice. No fixed menu. A numbered phase after 8.6's follow-up, 8.7 and 8.9, at dial position 3 (event schema). Five decisions for you when it opens, the lead recommending yes to each |
| 55 | Work counts as done when the test queries document passes, run automatically by the team, not when the golden count holds: every feature's "what you should see" is checked, and an expert checks the facts in a few key answers | The product owner, 2026-09-26: "what we should be actually trusting ... is running the test queries and workflow document that should be the barrier that needs to pass" (`DECISIONS.md`) | Being designed, 2026-09-26: how each entry becomes checks, the runner, the cost and the first baseline run. Then built on a branch, since it changes `.claude/`. The golden run stays the blocking gate until this one has run once. The expert review is the owner's to arrange; the lead prepares the answers to check |
| 100 | Between 721 and 900 pixels wide, the top bar runs off the screen when the signed-in email is very long | Found by the lead's check of cards 43 and 44 on 2026-10-06 with a 50-character test email; a real long email was not tried | Your decision of 2026-10-06: low priority, a Factory screen card after card 24 |
| 105 | A picked "How far back" window limits only the live PubMed search: after picking "from the last 5 years", the answer's first 41 papers are knowledge graph records from about 1999, shown as bare ids, under a heading that repeats the window | Card 36's product check, PR-36-01 (`testing/Developer/reports/2026-10-09_product_check_37_36/product_review.md`) | Nobody on it; found 2026-10-08 overnight, true on develop before card 36 |
| 106 | On a phone, the "High-risk claim" tag under a reopened answer breaks across two lines as "High-" and "risk claim" | Card 71's product check (`testing/Developer/reports/2026-10-09_product_check_71/product_review.md`) | Nobody on it; found 2026-10-08 overnight |
| 107 | When the model check rejects a clause the writer reworded, the start of that sentence can still show, so a person reads half a sentence the check did not pass | Card 51's fresh verifier, V-51-01 (`testing/Developer/reports/2026-10-09_card51/verifier.md` on card 51's merged branch) | Nobody on it; card 101's territory, found 2026-10-08 overnight |
| 108 | When every search a question planned is skipped, because the per-question cost cap was reached or the 20-lookup limit was already used, the progress steps stay on Plan for the whole time the answer is being written, then jump to Write with Act never lit | Card 19's judge and adversary, J-19-03 and A-19-03 (`testing/Developer/reports/2026-10-09_card19/`): the backend sends no frame when it skips every call, so the screen cannot know the searching is over | Nobody on it; true on develop before card 19; needs a new progress event, so it is an event-schema change at dial position 3 |

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
| 11.11 | Use your reference prototype for answer depth, formatting and structure; it writes with a different model family | Queued | Tenth in "Next, in order". It was listed as in progress until 2026-09-24 with nobody on it, so it moved out of section 1. 12.9 and 12.10 answered part of its ask. The answer-writing model is unchanged: switching models is a separate decision |
| 11.29 | Think big about connecting the dots: if everything were in the knowledge graph, from PubMed literature to sequence, clinical and PubChem data, how do we find hard edges (direct relationships) and soft edges (indirect, through multi-hop)? Do we need RAG pipelines, vector embeddings, a hybrid knowledge-graph model? | Discussion, precursor to a build | Reclassified 2026-09-22 by the product owner: a discussion that precedes a build under `/bossman-mode`, not a question waiting on them. Raised 2026-09-20. Full detail: [11.29](#detail-1129) |
| 11.32 | Wrap the Layer 2 and Layer 3 API calls in internal MCP servers. "Why dont we wrap our layer 2 and layer 3, the api calls in internal mcps ... can understand from the API keys on how to setup things for each database. Maybe just add to the list for now" | Discussion, precursor to a build | Reclassified 2026-09-22 by the product owner: scoped in a discussion first, then built under `/bossman-mode`, still against the locked Section 6 tool list. Raised 2026-09-20. BACKLOG ONLY, nothing designed and nothing promised. Full detail: [11.32](#detail-1132) |
| 11.38 | Try the new model on OpenRouter that returns probabilities with its output, and decide where calibrated confidence belongs in the architecture: the guardrail, the choice of which resource to pull, and the cite-or-refuse gate | Discussion, precursor to a build | Raised 2026-09-22 by the product owner, who named the guardrail and the resource choice. BACKLOG ONLY, nothing designed and nothing promised. IDENTIFIED 2026-09-23 from the two links the product owner gave: it is `typesafe/jev-1.13` from TypeSafe, and it fits two of the three places they named and not the third. CORRECTION, because the assistant said the opposite hours earlier: it is NOT a harness config change, because it answers on its own `POST /api/alpha/decisions` endpoint rather than chat completions, so a trial needs a new client path. Full detail: [11.38](#detail-1138) |

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
| Phase 8.7: the first sentence answers the question, the records show at about 8 seconds, and Opus writes | 2, 50, 5 | `tracker/phase_8.7.md`, branch `phase/8.7-answers-sooner`; parked 2026-09-27 with its three builders part-way, each listed in `HANDOFF.md` |
| Two reviews of the harness, since "I do not think our harness works well right now": the product's, which turns a question into an answer, and the build's, which is how the product gets built; each ends in ranked changes and questions for you | the product owner, 2026-09-25 | `testing/Developer/reports/2026-09-25_harness_review/product_harness.md` and `build_harness.md` |

## Retest

Moved on 2026-10-06, at the product owner's request, to `testing/UI_fixes_done.md`, section "Waiting for your retest". A card that is built and live waits there for your verdict; it is not work to do and is not counted here.
