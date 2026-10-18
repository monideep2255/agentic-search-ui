# Diagnosis: cards 91 and 93 (query 25 background-search line)

Read-only diagnosis, 2026-10-05, against the develop API as a guest. No code changed.

## Table of contents

- [What the person sees](#what-the-person-sees)
- [Which question was asked](#which-question-was-asked)
- [Reproduction table](#reproduction-table)
- [Root cause, card 91](#root-cause-card-91)
- [Root cause, card 93](#root-cause-card-93)
- [Do the cards share a cause](#do-the-cards-share-a-cause)
- [Fix options](#fix-options)
- [Recommendation](#recommendation)
- [Confidence](#confidence)
- [What was not covered](#what-was-not-covered)

## What the person sees

- A TP53 dataset question returns a full answer (GEO series, ClinVar, trials, 23 sources), then under the Notes it says: "One of the background searches did not finish, so this answer may be missing sources. Ask again to retry."
- The trust line drops to "Based on 23 sources, not yet confirmed" (outcome `ask`), because any failed call floors the outcome.
- The sentence is true only part of the time. In two of the three failing runs below, the missing piece was not a database the person asked about.
- Card 91 names MLH1 and MSH2 (query 24). That question did not show the line in the retest or in 5 of 5 live runs here. The line was seen on query 25 only.

## Which question was asked

- Runner A typed "Find GEO expression datasets studying TP53 in human tumour samples." as query 25 (`runner_A/results.md`, `q25_run1.txt`, `q25_run2.txt`). Same text as the test document.
- Runner A marked "the answer never says the question's wording is a disease" as PASS on both runs and "no closing note listing mouse tumour records" as PASS. The only FAIL on query 25 was the background-search line. Neither saved text contains "named in the question".

## Reproduction table

Question: query 25 text, researcher depth, fresh guest each run, `raw/*.json` holds every event. Seconds are wall clock to the last event. Runs 1 to 3 ran together, runs 4 to 6 ran together with five query 24 runs (8 at once), run 7 ran alone.

| Run | Think class | Outcome | Seconds | Background line | What failed |
|---|---|---|---|---|---|
| q25_r1 | aggregate | ask | 31.8 | yes | cypher_query (the question's own graph search), error after about 6.7 s, "Generated Cypher appears to bind a literal value directly instead of a parameter" |
| q25_r2 | exploratory | flag | 16.2 | no | nothing |
| q25_r3 | single_hop | ask | 17.1 | no | nothing (ask came from "summary could not be verified") |
| q25_r4 | single_hop | ask | 16.2 | yes | 5 ncbi_efetch calls, "rate limited by NCBI" (pubmed, clinvar, omim, gds searches) |
| q25_r5 | multi_hop | flag | 17.8 | no | nothing |
| q25_r6 | exploratory | ask | 34.9 | yes | 3 ncbi_efetch calls, "rate limited by NCBI" |
| q25_r7_alone | exploratory | flag | 16.5 | no | nothing |

Query 24 (MLH1 and MSH2), five runs, `raw/q24_r*.json`:

| Run | Think class | Seconds | Background line | Both genes searched |
|---|---|---|---|---|
| q24_r1 | exploratory | 20.2 | no | yes (7 rows and 6 rows) |
| q24_r2 | exploratory | 23.3 | no | yes |
| q24_r3 | aggregate | 23.7 | no | yes |
| q24_r4 | exploratory | 25.6 | no | yes |
| q24_r5 | aggregate | 37.0 | no | yes |

- No graph search timed out in any run (the 30 s limit, `graph_schema_constants.py:208`, was never reached; the slowest graph call seen was the 6.7 s rejected one in run 1).
- Runner A's own two runs showed the line while all five gds, five pubmed, five clinvar and one omim records arrived, so the failed call there was not one of those five searches. The saved text has no step events, so which call failed in runner A's runs is not pinned.

## Root cause, card 91

The line has one source and several causes. Source: any tool call that ends with status `error` is copied to `failed_searches` (`core/graph.py:8091-8105`), and `write_node` turns a non-empty list into the fixed sentence (`core/graph.py:12584-12590`, text at `synthesis/refuse.py:111`). The sentence does not say which call or why, and it appears for a rate limit and a code-side rejection alike.

Cause A, seen live in run 1 (Think classed the question `aggregate`):

- Think's class is a model guess and varies run to run for the same text (aggregate, exploratory, single_hop and multi_hop all appeared in 7 runs).
- Template choice depends on the class. `select_template` (`tools/cypher_templates.py:711`) finds no shape for a dataset question; with no shape, `lookup` and `exploratory` get the record template, and a Gene anchor on `single_hop` and `multi_hop` gets it too (`cypher_templates.py:782-787`). An `aggregate` question returns None (`cypher_templates.py:788`), which sends the call down the model-written Cypher path.
- The model-written query was rejected twice by the validator (`cypher_validator.py:1317-1330`, literal value in the Cypher text), one repair retry allowed (`tools/cypher_query.py:1971`), then `_error_output`. No graph call was ever made, so this is a code-side rejection, not a timeout.
- The comment at `cypher_templates.py:755-770` records the same failure for G-037 before on "every pass" and fixed it for the `single_hop` and `multi_hop` classes only. The `aggregate` class was left on the model path on purpose for count questions (G-034), and a TP53 dataset question is not a count.
- The plan's second graph call (the GO terms call, `core/graph.py:6536`) is a fixed template and never failed.

Cause B, seen live in runs 4 and 6 (NCBI rate limit):

- `ncbi_efetch` calls returned "rate limited by NCBI" (status 429 mapped at `tools/ncbi_transport.py:559`). The dependent fetch and annotate calls then returned `empty` ("no ids to fetch"), and those did not add to the note, but the failed searches did.
- Confound: runs 4 and 6 ran alongside seven other questions from the same address (about 13 NCBI calls each), so this is very likely load I created. Runs 1 to 3 and 7 saw none. Runner A may have met the same effect when several runners shared a window. This is a hypothesis for runner A, not proven.

Query 24: no failure in 5 runs. If the retest had shown it, the likely cause is the same (class aggregate with no template, or rate limit), but nothing here reproduces it. Card 91's title should say query 25.

## Root cause, card 93

- The guard that stops the question's own words from becoming disease rows exists: `_GENERIC_DISEASE_WORDS` and `_is_generic_disease_mention` (`core/graph.py:2794-2816`), applied at the top of `resolve_disease_mention_to_curies` (`core/graph.py:2874`). A mention made only of those words ("human tumour samples") is never sent to MedGen.
- Entity extraction is a model step in Think, so whether the model emits "tumour" as a disease span varies per pass. The test document says the same (query 25 note).
- Live evidence: in 7 of 7 runs Think resolved only TP53 (`resolved_entities`), no disease span, and no answer carried a "named in the question" note or mouse tumour rows. Runner A recorded the same PASS on both of its runs.
- Card 93 was not reproduced and runner A's own results contradict its wording ("query 25 failed on both runs"): the failure on both runs was the background line, which is card 91. I could not find a card 93 failure of its own.
- Residual weakness, from reading the code only: the guard is an exact all-words-in-a-list test. A span with one word outside the list ("tumour xenograft samples") passes it and is searched. A list of words is also the kind of rule the project says belongs to a classifier. Not observed live.
- Separate and unrelated to card 93: query 24 says "does not address the following entities named in the question: Colorectal cancer" in 5 of 5 runs. Colorectal cancer is a real disease the person named, so this is not the question's own wording becoming a disease. Whether the note is right is for the owner.

## Do the cards share a cause

No. Card 91 is a real failed call surfaced by one fixed sentence (a code-side Cypher rejection on one Think class, or an NCBI rate limit). Card 93 had no failing evidence on its own and was filed from the same screens. Closing 91 will not change 93's status, and 93 should probably be closed as not reproduced, or reworded to the list-based guard weakness above.

## Fix options

1. Make the graph search for a Gene anchor use the record template for `aggregate` when no shape and no count word match (`cypher_templates.py:788`).
   - Changes: one branch in `select_template`. The model path stays only for true count questions.
   - Risk: low, same path the other three classes already take for this question.
   - Changes the answer path: yes, for questions Think classes as aggregate. The golden run must hold at least 101 of 150 (G-034 count question is the one to watch).
2. Name the failure in the note and stop treating a context-only or recoverable failure as a lost search: say "NCBI is busy, ask again in a minute" for a rate limit, and say nothing for a model-path rejection where the template path still answered.
   - Changes: `_build_failed_search_note` (`core/graph.py:9175`) and the `failed_searches` rule. The first needs the typed `kind` it already has; the second needs a rule for when the graph search was redundant.
   - Risk: medium, touches the trust floor (outcome `ask`).
   - Changes the answer path: it changes the trust outcome shown, not the sources. Run the golden anyway.
3. Retry a rate-limited `ncbi_efetch` search once after the `Retry-After` wait before giving up, and cap concurrent NCBI calls per run.
   - Changes: transport or act step.
   - Risk: medium, adds latency against the 20 s answer limit.
   - Changes the answer path: yes, answers get more complete under load. Golden run applies.

For card 93, if kept: replace the word list with a classifier decision that says whether a disease span names a disease or is the question's own wording, and have code only verify the MedGen match. No question text or word list added.

## Recommendation

- Do option 1 first. It removes the one failure I could pin to code (run 1) with a small, reversible change that follows an existing, measured decision for this exact golden question.
- Do option 2's wording part next, so the person learns what actually happened. The honest, user-facing fix for rate limits is a clearer sentence, not a hidden one.
- Leave option 3 until the rate-limit effect is shown without my concurrency.
- Close card 93 as not reproduced, or reopen it with a failing run.

## Confidence

- Cause A (aggregate class, no template, validator rejects model Cypher): high. The raw event shows the exact error, and the code path and class correlation line up in 7 runs. One failing run only, so the frequency is not measured.
- Cause B (rate limit): high that it exists, medium that runner A saw it, because I created load.
- Card 93: medium that it is not a live defect (7 clean runs plus runner A's PASS), low on the intermittent rate.
- The shared-cause answer: high.

## What was not covered

- The live-question budget of 12 was used (7 for query 25, 5 for query 24). The intermittent rate of cause A is unmeasured: 1 in 7.
- Which call failed in runner A's two runs is not known from its saved text.
- Query 24 under load or on an aggregate class with a rate limit was not forced.
- Railway logs for the retest window were not read.
- The disease word-list weakness was read from code, not triggered.
- No fix was built, so no golden run was made.
