# Diagnosis of PR-87-04, PR-87-05 and PR-87-11

Diagnosis only, no fix. The product check in this folder ran on deployed develop at merge b01dee92 (phase 8.7, pull request #218). Code was read in a checkout whose `src/` and `frontend/` are identical to b01dee92; "before 8.7" means b01dee92^1 (451104d6), read with `git show`. Line numbers are at b01dee92.

## Table of contents

- [How the evidence was gathered](#how-the-evidence-was-gathered)
- [PR-87-05: "Marfan syndrome and Marfan syndrome."](#pr-87-05-marfan-syndrome-and-marfan-syndrome)
- [PR-87-04: the Marfan answer opens on the count line](#pr-87-04-the-marfan-answer-opens-on-the-count-line)
- [PR-87-11: a stopped search reads "21 sources cited"](#pr-87-11-a-stopped-search-reads-21-sources-cited)
- [Summary](#summary)

## How the evidence was gathered

- Code reading at b01dee92 and b01dee92^1, and `git diff b01dee92^1 b01dee92`.
- Two local runs of query 66 in Plain language through `core/run.py`'s `run_streaming`, with the web client's settings (`reads_placement=True`), develop's writer setting (kept by `DECISIONS.md`, 2026-10-09), `CLASSIFIER_PROVIDER=jev` and `PER_QUERY_COST_CAP_USD=0.25`. A wrapper logged every writer reply, every grounding result and the lead-sentence decision. Cost: $0.0065 and $0.0057, about $0.012 in all.
- Offline calls to the grounding pass (`synthesis/grounding.py`, `run_grounding_pass`) with the 30 real prompt findings logged by run 1 and hand-written writer sentences.

What the two runs showed, in short:

| Run | Drafts started | Draft kept | Lead candidates | Jev's pick | How it opened |
|---|---|---|---|---|---|
| 1 | first draft and the 8.7 "COMPLETENESS REQUIREMENT" draft, both at 9.89 s | the second (3 sentences against 1) | two feature sentences | "first", 0.97, 273 ms | a features sentence |
| 2 | both at 14.99 s | the first (1 sentence each) | the features sentence | "first", 0.98, 251 ms | the features sentence |

Neither run reproduced the deployed answer word for word, so the exact writer reply behind the deployed sentences was not seen; the mechanism below is shown from code and offline calls instead.

## PR-87-05: "Marfan syndrome and Marfan syndrome."

### Cause

The sentence is the writer's prose, accepted unchanged by the exact grounding check. No code builds it. It is not the count line, the 8.7 gap clause, a listing row or a code-built list joiner:

- The summary part of a token stream is only the lead sentence (if any), the count line and the model's grounded sentences (`core/graph.py:13316-13362`, `_answer_parts`). The count line's own joiner (`synthesis/answer_layout.py:1322-1323`) and `_summary_subject`'s (`core/graph.py:12499`) never repeat a name; the subject joiner drops case-insensitive duplicates (`core/graph.py:12493`).
- PubMed returns three Marfan papers whose titles are all "Marfan syndrome." (PMIDs 2402263, 38517496 and 40466129, in run 1's prompt findings 2, 15 and 19). The deployed listing shows one at 79 and another on page 2, at 81.
- Offline, the grounding pass turns the writer sentence `Marfan syndrome [2] and Marfan syndrome [15].` into `Marfan syndrome [1] and Marfan syndrome [2].` with nothing stripped. Each segment is a title copied exactly, so each grounds against its own paper. `_clean_claim` (`synthesis/grounding.py:1405-1421`) drops the joining "and" before matching, so the glue is never checked.
- A longer writer sentence gives the same result: `Marfan syndrome [15] and Marfan syndrome [19] are recent reviews of the condition.` loses its unsupported ending (the end strip of T-6.2-15) and leaves the same two names.

The likeliest author is the second draft. Phase 8.7's `build_listing_gap_directive` (`synthesis/findings.py:1727`) tells the writer to "Report and cite EVERY finding listed", and for query 66 that list holds the five `pmid` rows the listing cannot cite. In both runs, only that draft named the papers: run 1 wrote "Research publications on Marfan syndrome include PMID 2402263 [6], ...", run 2 wrote "... identified by the following PubMed records: 2402263 [5], ...". Both were stripped. Writing the titles instead of the numbers gives the deployed sentence.

The features sentence, "Aortic regurgitation, Arachnodactyly and Astigmatism, ... Exotropia and Pes planus, ...", is also the writer's own glue:

- `build_clinical_features_directive` (`synthesis/findings.py:1889-1941`) gives the writer a three-name example shape, `first name [a], second name [b] and third name [c]` (`findings.py:1930`). A writer copying that shape in chunks puts "and" inside the list.
- Offline, `Aortic regurgitation [8], Arachnodactyly [12] and Astigmatism [16].` grounds whole, with "and" kept where the writer put it. The grounding pass rebuilds a sentence from the writer's own text between markers, and it checks the names, never the glue.

### Did 8.7 introduce it

Unsure, leaning no.

- The code that accepts both sentences is unchanged by #218: `git diff --stat b01dee92^1 b01dee92` lists no change to `synthesis/grounding.py` or `synthesis/sentence_check.py`. The same writer reply grounds to the same sentence before and after 8.7.
- The features directive dates from F-8.1-A11, and 8.7 did not change it.
- What 8.7 changed is the prompt of the draft that is most likely to write the sentence. Before 8.7, a repair draft ("COMPLETENESS CORRECTION", `build_completeness_directive`) ran after the first and listed the findings that draft had left out. Since 8.7, under develop's writer, the "COMPLETENESS REQUIREMENT" draft starts beside the first whenever the listing has an uncitable finding (`core/graph.py:13909-13942`). Both versions are kept by the same rule (`core/graph.py:14232-14235`). Both ask the writer to cite every listed `pmid` row, so it cannot be shown that before 8.7 the writer would never have written the titles. Whether 8.7 makes this happen more often is not measured.

### Smallest fix

- Code: after grounding, drop a prose sentence when every claim in it is a record label (a title or a name) that the listing already shows. Such a sentence repeats the listing and adds nothing. One check in the prose loop of `_answer_parts` (`core/graph.py:13338-13362`), with a test in `tests/system_03_search_agent/core/`. It is a check on the sentence's structure, not a decision about meaning, and reads no word of the question.
- Prompt, for the features sentence: give the shape as one comma-separated list with "and" only before the last name, in `build_clinical_features_directive` (`synthesis/findings.py:1924-1931`), plus its test. This touches the dynamic suffix only, so the stable prefix is unchanged.

### What a person sees today

The answer ends with "Marfan syndrome and Marfan syndrome.", which says nothing, and the features sentence has "and" in odd places.

## PR-87-04: the Marfan answer opens on the count line

### Cause

The opening comes from a code limit on which sentences the lead pick may choose. It is not a fallback, and the pick did not fail:

- `_lead_candidates` (`core/graph.py:12618-12632`) offers the lead decision only the first two grounded sentences that carry a citation (`MAX_LEAD_CANDIDATES`, `harness/decide.py:589-592`, two picks: "first" and "second").
- In the deployed answer, the model's grounded sentences ran in this order: "There is currently no radical treatment ..." [83], "Neonatal Marfan syndrome is especially rare ..." [83], then the features sentence, then "Marfan syndrome and Marfan syndrome." So the two candidates were the two abstract sentences, and the features sentence, third, could not be picked.
- Neither candidate answers "what features". "Neither" is therefore the right pick, and with "neither", a late pick or a failed call, `_lead_sentence_choice` (`core/graph.py:12635-12686`) returns None. Then `_answer_parts` opens on the count line (`core/graph.py:13318-13334`). Which of those happened on develop is not recorded, and it makes no difference: no pick could reach sentence 3.
- Why the abstract sentences came first: they are Plain language rewordings of a paper's abstract. In both local runs, only the second draft wrote such sentences, and in both it put them ahead of the features sentence, although its directive says "Keep the answer to the question in the first sentence". When that draft is kept (the card 88 rule, `core/graph.py:14232-14235`: same records, more sentences), its order becomes the answer's order.
- The phase's own live check, where the features sentence led in both modes, ran with a writer at whose price two drafts never fit the cap. That check notes the second draft never started there. Develop's writer is cheap enough that both drafts always start (runs 1 and 2: both at the same second), so the live check never covered the order seen here.
- When the features sentence is first or second, the pick works: Jev chose it in about 0.25 s, at 0.97 and 0.98, in both local runs.

### Did 8.7 introduce it

No. Before 8.7 the count line always opened every answer: the only opening branch is `if summary_sentence:` (`core/graph.py:12734-12737` at b01dee92^1), with no lead pick. So develop before 8.7 opened this question on the count line too. Phase 8.7 added a way out, and here it did not reach the sentence that answers.

### Smallest fix

Offer the lead decision every grounded, cited sentence up to a small bound, three or four instead of two:

- Raise `LEAD_SENTENCE_PICKS` and `MAX_LEAD_CANDIDATES` in `harness/decide.py:589-592`, add the criteria for each new option, and lower `_LEAD_CANDIDATE_MAX_CHARS` (`decide.py:596`, now 1200) so that the question and every candidate fit `_STATE_MAX_CHARS` (4000).
- `core/graph.py` needs no change beyond what `_lead_candidates` already reads.
- Tests: `tests/system_03_search_agent/harness/test_decide.py` and `tests/system_03_search_agent/core/test_write_answers_sooner.py`.

The rule that only grounded sentences may lead still holds.

### What a person sees today

They ask what the features of Marfan syndrome are, and the answer opens by counting papers and trials. The list of features comes fourth.

## PR-87-11: a stopped search reads "21 sources cited"

### Cause

The count comes from citation events that phase 8.7 now sends before the summary, and the history rail shows that count whatever the outcome was:

- Since 8.7, for a client that reads `placement` (the web app), the Write step sends the listing and its citations before any writer call (`core/graph.py:13884-13898`). For query 1 that is 21 citations.
- Stop then ends the run. `run_streaming`'s `finally` captures every event seen so far (`core/run.py:973`). It adds a stand-in `done` with `trust_outcome="refuse"` (`core/run.py:408-419`), which is why the row says `refuse`.
- `assemble_interaction` stores every `citation` event in the row (`feedback/capture.py:474`). It does not save the answer for `refuse` (`_SAVEABLE_OUTCOMES`, `capture.py:93`), which is why `has_saved_answer` is false.
- `list_history` counts the stored citations' pages (`feedback/history.py:317`), and `GET /v1/history` returns them (`adapters/web_sse/app.py:1080`).
- The rail renders `${count} sources cited` for any row with a count, and never reads `trust_signal` (`frontend/src/App.tsx:268-276`, `formatHistoryMeta`). So a stopped search and an answered one look the same.

### Did 8.7 introduce it

Yes, the count is new with 8.7. Before 8.7 the Write step sent citations once, after the writer and after the answer's tokens (`core/graph.py:14079` at b01dee92^1, the only `emit_live("citation", ...)`). Card 58's Stop rule only stops a run before the first sentence is on screen. So a stopped run had no citation events, and its row was stored with `citation_count` 0. The rail then read "0 sources cited", the same words but a different number.

The rail itself never told a stopped row from an answered one, before or after 8.7.

The re-run when such a row is opened is older and is left alone here. With `has_saved_answer` false, `onOpen` asks the question again (`frontend/src/App.tsx:2152-2174`), which is card 59's PR-04.

### Smallest fix

- In the rail, the frontend alone: in `formatHistoryMeta` (`frontend/src/App.tsx:268-286`), when `trust_signal` is `refuse` and there is no saved answer, show a plain status in place of the count, for example "Stopped, no summary". Test: the history-rail test beside `App.tsx`.
- The words are the owner's to pick. A guardrail refusal and a clarifying question are also stored as `refuse`, so the words must fit all three, or the server must tell them apart.
- The server's stored citations can stay as they are: the daily caps and the weekly review read them.

### What a person sees today

In "Your searches", a search they stopped shows "21 sources cited", the same as an answered one, and they cannot tell which row holds an answer.

## Summary

| Finding | Cause | Introduced by 8.7 | Smallest fix | Files |
|---|---|---|---|---|
| PR-87-05 | The writer cites two papers that share the title "Marfan syndrome."; the exact grounding check accepts each copied title and never checks the "and" between them; the features "and" comes from the writer copying the directive's three-name shape | Unsure, leaning no: the accepting code is unchanged; 8.7 changed only the second draft's prompt and timing | Drop a prose sentence made only of labels the listing already shows; give the features shape as one list | `core/graph.py`, `synthesis/findings.py`, tests |
| PR-87-04 | The lead pick sees only the first two cited sentences; the kept second draft put two abstract sentences first, so the features sentence, third, could not lead | No: before 8.7 the count line always opened | Offer three or four candidates, with a smaller cap on each | `harness/decide.py`, tests |
| PR-87-11 | Citations now leave before the summary, a Stop captures them in a `refuse` row, and the rail prints the count without reading the outcome | Yes for the count (0 before 8.7); the rail's blindness to the outcome and the re-run on open are older | Show a status in place of the count for a `refuse` row with no saved answer | `frontend/src/App.tsx`, its test |
