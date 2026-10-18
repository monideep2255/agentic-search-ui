# The sentence check: why faithful explanations disappear, and what to change

Diagnosis and design only, no product code changed. Six local runs of the real loop on 2026-10-05 (three of the Mediterranean question at plain language, three of the GERD question at Researcher depth, `CLASSIFIER_PROVIDER=jev` as develop runs), capturing every reworded sentence the check saw, the quote it was judged against, the cited record and Jev's verdict: 65 pairs in `raw/pairs.jsonl`, each classified by hand in `raw/classification.json`. Then 39 offline model calls re-judged the same 65 pairs under six variants. Scripts: `raw/trace_run.py`, `raw/build_pairs.py`, `raw/offline_judge.py`.

## Table of contents

- [What the person sees](#what-the-person-sees)
- [How the check works today](#how-the-check-works-today)
- [The measured classification](#the-measured-classification)
- [The cause](#the-cause)
- [The options and their offline scores](#the-options-and-their-offline-scores)
- [Recommendation](#recommendation)
- [What was not covered](#what-was-not-covered)

## What the person sees

| Run | Question, depth | Sentences sent to the check | Approved | What the screen showed |
|---|---|---|---|---|
| med1 | Mediterranean, plain | 10 (two calls) | 2 | Familial Mediterranean fever named, three sentences of prose |
| med2 | Mediterranean, plain | 11 (two calls) | 2 | No prose: "the written summary of these records could not be verified", "not yet confirmed" |
| med3 | Mediterranean, plain | 6 (one call) | 1 | No prose, "not yet confirmed" |
| gerd1 | GERD, Researcher | 12 (two calls) | 3 | Two sentences of prose |
| gerd2 | GERD, Researcher | 12 (two calls) | 3 | One sentence of prose |
| gerd3 | GERD, Researcher | 14 (two calls) | 7 | Three sentences of prose |

- The writer names Familial Mediterranean fever in every Mediterranean run (med1 twice, med2 twice, med3 once). The check approved one of those five sentences. The name reached the screen in one run of three.
- In med2 the two approved sentences ("It is caused by changes in a gene called MEFV", the rare-variant list) were dropped later for a different reason: both open on a pronoun or rest on a sentence that did not survive, so the answer fell to the record list.
- In GERD the writer drafts eleven to fourteen reworded sentences per answer and the person sees one to three.

## How the check works today

- Where: `src/system_03_search_agent/synthesis/grounding.py` collects a `SynthesisCandidate` for every sentence that passed the three exact checks (quote in the record character for character, every number in a quote, negation matching) but not the word check. `core/graph.py`'s `_ground_with_sentence_check` sends all of one draft's candidates to `synthesis/sentence_check.py`'s `check_reworded_sentences` in one call, then re-runs the grounding pass accepting exactly the approved keys. The repair draft (card 88) goes through the same path, so a run has one or two calls.
- Who judges on develop: Jev (`typesafe/jev-1.13`, resolved as `typesafe/jev-1.13-20260917`), through `call_jev_batch`: one shared state of numbered ITEM blocks (SENTENCE plus QUOTES), one two-option `choice` question per item ("does its SENTENCE say anything its QUOTES do not?", options yes and no). A sentence is approved only when Jev picks "no" with a strictly higher probability for "no" than for "yes". Jev has no `bool` type (HTTP 400 names `noul`, `choice` and `score`), so yes-or-no is a `choice`. The guard-tier chat model (`deepseek/deepseek-v4-flash` on develop) judges only when `CLASSIFIER_PROVIDER` is not `jev`, with `SENTENCE_CHECK_INSTRUCTION` and a `{"supported": [...]}` reply.
- Cost and time measured: 244 to 322 ms and $0.00007 to $0.00013 per call of 4 to 8 items. The check is not the slow part of an answer.
- What the judge is shown: only the span the writer put inside the marker. Rule 3a of the writer prompt (`synthesis/findings.py`) asks for "a short contiguous span of about five to thirty words, never the whole finding" and in the same breath that the sentence "must say NOTHING MORE than the quoted words".

## The measured classification

Each of the 65 pairs was read against its quote and against the whole cited record (`raw/classification.json` carries the one-line reason for every item):

| Class | Meaning | Pairs | Approved by the live check |
|---|---|---|---|
| F, faithful rewording | Everything the sentence says, its quote says | 23 | 18 |
| R, record-faithful, beyond the quote | The extra words are in the same cited record, outside the quoted span | 36 | 0 |
| A, genuine addition | Not in the cited record, a widened population, a stronger degree, or an added explanation | 6 | 0 |

- Of the 47 rejections: 36 (77 percent) are sentences faithful to the cited record whose extra words sit outside the short span the writer quoted; 6 (13 percent) are genuine additions, rightly rejected; 5 (11 percent) are faithful rewordings wrongly rejected.
- The live judge let no genuine addition through (precision 6 of 6 rejected) and approved 18 of 23 faithful rewordings (recall 78 percent). The five wrong rejections had "no" probabilities of 0.48, 0.39, 0.37, 0.28 and 0.16: three of five were coin flips.
- The six genuine additions, in the person's words: a sentence about young children shown as about children (twice, rejected at 0.44 and 0.46, also coin flips); "in adults" where the paper never says adults; "autosomal recessive" taken from a different paper than the one cited; an explanation of what hemoglobin does that no paper gives; a reframing of what a paper studied.
- Examples of the 36 record-faithful rejections: "GERD is a gastrointestinal motility disorder caused by reflux of stomach contents" against the quote "results from the reflux of stomach contents into the esophagus" (the head of the same record sentence was cut); "Long-term use of proton-pump inhibitors, the most effective treatment, is associated with bone fractures" against a quote that starts at "Long-term" (the previous record sentence says "most effectively treated with proton-pump inhibitors"); "Familial Mediterranean fever is an inherited autoinflammatory disorder that mainly affects people of Mediterranean descent" against a quote from the record's second sentence, while "monogenic autoinflammatory disorder" is its first.
- The repair draft shows the mechanism directly: in gerd1 the first draft's GERD definition was rejected against a half-sentence quote (0.06) and the repair's same sentence was approved (0.66) once the writer quoted the whole record sentence.

## The cause

- Primary, 36 of 47 rejections: the quote span. The writer is told to quote five to thirty words and never the whole finding, then writes a sentence that covers the clause before or after the span, or the record's lead sentence. The judge, asked about the span alone, is right to reject. This is not the model, not the prompt wording, and not the yes-or-no framing: a symmetric rewording of the criteria changed nothing (below), the guard-tier model is far worse, and Jev's verdicts track the quote faithfully.
- Secondary, 5 of 47: Jev at the decision line. A faithful rewording with "no" at 0.35 to 0.49 is rejected, and the same sentence flips between calls: the "young children" rewording was approved at 0.64 and 0.73 in two runs and rejected at 0.56 and 0.61 in two others. Verdicts also move with batch size: the same 65 pairs sent as three batches of 19 to 27 items approved 12 to 13 of the 23 faithful rewordings, against 18 of 23 in the live batches of 4 to 8.
- Not a cause: the decision framing. The question is already closed (two options, strict parser, even odds approve nothing), which is what the owner's direction asks for.
- Separately found, outside develop's path: with `CLASSIFIER_PROVIDER` unset (the code default), the guard-tier model `deepseek/deepseek-v4-flash` with reasoning off and 256 tokens approved all 65 pairs, including all six genuine additions, in three of three calls. If production runs the guard provider with this model, its sentence check is a rubber stamp. With reasoning left on, the same model spent all 256 tokens reasoning and returned no JSON, which the live parser reads as approve nothing.

## The options and their offline scores

All variants re-judged the same 65 pairs. "F" is approvals among the 23 faithful rewordings (recall), "R" among the 36 record-faithful sentences beyond the quote, "A" among the 6 genuine additions (any A approval is a fail). Three big batches unless stated. Output files: `raw/offline_<variant>.jsonl`.

| Variant | What changes | F | R | A | Calls | Latency and cost per call |
|---|---|---|---|---|---|---|
| jev_quote (today, big batches, two passes) | Nothing | 12 to 13 | 1 | 0 | 6 | 300 to 400 ms, $0.0003 to $0.0004 for 19 to 27 items |
| Live verdicts (today, batches of 4 to 8) | Nothing | 18 | 0 | 0 | 11 live | 244 to 322 ms, $0.00007 to $0.00013 |
| jev_symmetric | The "yes" criterion loses "or it is unclear whether it does" | 13 | 0 | 0 | 3 | as jev_quote |
| jev_sentence (two passes, identical) | Code widens each quote to the whole record sentence(s) containing it before the judge sees it; question unchanged | 19 | 15 | 0 | 6 | 274 to 472 ms; state 35 percent larger (8.2k to 11.1k characters for 27 items) |
| jev_sentence, live-sized batches | Same, one batch per live call | 20 | 15 | 3 | 11 | 229 to 319 ms |
| jev_context | Widened to the sentence plus one before and one after | 22 | 25 | 2 | 3 | 300 to 442 ms; state 18.9k characters |
| jev_record | The judge reads the cited record in full and is asked whether the sentence says anything the record does not | 23 | 33 | 3 | 3 | 291 to 472 ms; state 16.6k characters |
| guard_quote | The guard-tier chat model, the live instruction, reasoning off | 23 | 36 | 6 | 3 | 1.9 to 6.3 s |

Reading the table:

- Widening the reference past the containing sentence (jev_context, jev_record) lets borderline additions through: "children" for "young children" and the reframed study aim. These fail the bar and would also widen the owner's exception of 2026-09-23 from the quote to the record. Not recommended.
- The guard-tier model fails outright and is also three to twenty times slower.
- Rewording the criteria does nothing. The framing is not the problem.
- Sentence widening (jev_sentence) is the only variant that approved no addition in the big-batch shape, in two identical passes, while recovering 15 of the 36 record-faithful sentences and 7 more faithful rewordings. In the live-sized batches it approved the same three borderline items jev_record did. Two of those three ("children" for "young children") had quotes that were already whole sentences, so widening changed nothing for them: that is the judge's coin flip at 0.44 to 0.46, which today's check is one flip away from as well. The third (the reframed study aim, "studied in the context of screening, diagnosis and genetic counseling") was approved against the whole record sentence, which says understanding prevalence will improve screening, diagnosis and counseling; it is the softest of the six additions, and the bar still counts it.
- What sentence widening does not reach: 21 of the 36 record-faithful sentences draw on two record sentences and quoted one. Fourteen of those are in the Mediterranean runs, where the disease name sits in the abstract's first sentence and the population in its second, so this option alone recovers 2 of the 16 Mediterranean record-faithful sentences and 13 of the 20 GERD ones. Card 89's missing name needs the writer-side change below as well.

The three options, in full:

| Option | What changes | How cite-or-refuse stays strict | Cost and latency | How to measure |
|---|---|---|---|---|
| 1. Code widens the quote to its record sentence(s) | In `grounding.py`, where the candidate is built, each quote is extended to the shortest run of whole record sentences containing it (exact record text, found by the same character-for-character match). The widened span is what the judge reads and what the claim stores as its evidence, so the citation shows the sentence the words came from. The judge, its question and its fail-closed rules are unchanged | The three exact checks still run on the writer's own span before anything is widened; a quote not in the record never reaches this step; numbers and negation are still checked against the writer's span. The judge still sees only exact record words, now the whole sentence they sit in | No extra call. State grows about a third; latency unchanged (274 to 472 ms measured). A code change of one function plus tests | Re-run `raw/offline_judge.py jev_sentence` on the labelled 65 pairs after the change (A must stay 0 of 6 in the big-batch shape, and the three live-batch approvals must be reported); then five or more live runs of each question, counting sentences shown and the disease named, against this report's table |
| 2. The writer quotes whole record sentences, one quote per sentence drawn on | Rule 3a in `synthesis/findings.py` stops asking for "five to thirty words, never the whole finding" and asks for the whole record sentence(s) the written sentence rests on, each as its own quote (`[4: "first sentence"][4: "second sentence"]`, the form the grounding pass already accepts). This is the only option that reaches the 21 cross-sentence cases, including the Mediterranean name | Nothing in the checks changes. More quoted words means the number and negation checks see more, never less | Longer synth output: roughly 20 to 40 more tokens per sentence; the judge's state grows accordingly. No new call. Prompt changes are nudges: five directive versions failed before, so this is measured, not assumed | Five or more live runs per question; the multi-quote path is already proven live (gerd2's three-quote risk-factor sentence and med2's two-quote G6PD sentence were approved) |
| 3. Raise Jev's bar at the line | Approve only when "no" is at least 0.6, to stop the coin flips approving a widened population | Strictly tighter | Free | Costs recall: of the 18 live approvals, 3 sat between 0.52 and 0.58, so this would hide about a sixth of what shows today. Not recommended unless the owner weighs the "young children" case above those sentences |

## Recommendation

- Do option 1 now and option 2 with it. Option 1 is deterministic code that fixes the measured cause for the within-sentence case with no extra call and no addition approved in the big-batch shape across two passes. Option 2 is the only reach into the cross-sentence case that card 89 depends on, and it rides on a quote form the pass already accepts. Together, in the person's words: an explanation written in plain words survives when every fact in it is in the record sentence it quotes, and a sentence about one paper will still never carry a fact from another paper.
- Ask the owner one question before building, because it touches the exception they scoped on 2026-09-23: the judge would compare the sentence with the whole record sentence(s) the quote sits in, rather than the writer's shorter span. Recommended answer yes; the alternative is to keep the span and accept today's loss of three in four record-faithful sentences.
- Report the boundary honestly: Jev flips on "children" versus "young children" at 0.44 to 0.56 today, and no variant here fixes that. Option 3 would, at the price of a sixth of today's approvals.
- Check production's judge. If production runs the guard provider with `deepseek/deepseek-v4-flash`, measure the sentence check there with `raw/offline_judge.py guard_quote` against production's settings; here it approved everything.

## What was not covered

- Six full traces and 39 of the 40 experiment calls were spent. Each option's live effect (the table in "What the person sees") is unmeasured until built; only the offline re-judging is measured.
- The hand classification is one reader's. Six items are marked borderline in `raw/classification.json`; a second reader should check the F and A labels before the 65 pairs serve as a regression set.
- Option 2 was not simulated, since it needs the writer to produce new quotes.
- Whether batch size itself moves Jev's verdicts was observed (18 of 23 at 4 to 8 items, 12 to 13 at 19 to 27) but not isolated from batch composition.
- The local user database was down (a stale Postgres lock from 2026-09-27 whose process id now belongs to another program; the delete hook rightly refused to remove it). The traces ran against a throwaway Postgres in the session scratchpad on port 5433, migrated with the repository's alembic and stopped afterwards; nothing touched the owner's database or any remote one. Every secret came from `<repo-root>/.env` into the trace process only.
- The med2 approved sentences that were then dropped by the pronoun and antecedent rules are card 89's second gap, not this check's.
