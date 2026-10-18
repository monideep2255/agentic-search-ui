# The qualifier check: catching a dropped "young" or "potentially" without losing faithful rewordings

Design only, no product code changed, 2026-10-05. The sentence check (Jev, one yes or no choice per reworded sentence: does it say more than its quote) approves rewordings that drop a qualifier from the record. Measured today on develop and on the card 89 branch alike: "young children" shown as "children" at 0.71 to 0.81, "symptoms potentially attributable to GERD" shown as "GERD symptoms" at 0.57 to 0.61. This report builds a labelled evaluation set from the two existing labelled sources (205 sentences), tries five ways of rejecting dropped or loosened qualifiers offline, and recommends one. Scripts and raw verdicts are in `raw/`; 59 Jev calls were spent against a budget of 60, including two attempts lost to transport errors, about $0.03 in all.

## Table of contents

- [What the person sees](#what-the-person-sees)
- [The evaluation set](#the-evaluation-set)
- [The options and their scores](#the-options-and-their-scores)
- [Why sentence-level questions fail and per-pair questions work](#why-sentence-level-questions-fail-and-per-pair-questions-work)
- [Recommendation](#recommendation)
- [What was not covered](#what-was-not-covered)

## What the person sees

| Today | With the recommended check |
|---|---|
| A plain-language GERD answer says "In children, GERD symptoms can be varied and nonspecific" where the paper says young children. The reader of a question about an older child takes it as about their child | That sentence is not shown. The researcher-depth sentence "In young children, clinical manifestations are varied and nonspecific" still is, in every run measured |
| "Reflux symptoms are among the most common reasons people visit their primary care doctor" where the paper says symptoms potentially attributable to GERD | Not shown. "Symptoms that may be related to GERD are among the most common complaints reported to primary care providers" still is, in 3 of the 7 hedged plain-language rewordings measured; the other 4 are also dropped, because they leave out "in the outpatient setting" (below) |
| A faithful plain-language sentence that drops a setting word, such as "outpatient" from "reported to primary care providers in the outpatient setting", is shown | It is dropped in about half of such cases, at a coin flip (0.30 to 0.48). The reader sees one sentence fewer, never a wider claim |

In the person's words: a sentence about young children is never shown as a sentence about all children, and a symptom the paper only suspects is never shown as a symptom the paper confirms. The price is that some plain-language sentences that leave out a setting word such as "outpatient" disappear too.

## The evaluation set

`raw/eval_set.jsonl`, built by `raw/build_eval_set.py` from two labelled sources, 205 items, each with the sentence, the quotes the judge reads (whole record sentences, as card 89 ships), the writer's own quotes, the cited record text, the label, a sub-label, the note and the live verdict.

| Source | Items | How labelled |
|---|---|---|
| The design's 65 pairs (`2026-10-05_sentence_check/raw/`) | 65 | The design's F, R, A classes. Each quote was widened to its whole record sentence(s) with the design's own `widen_to_sentences`; an R pair whose extra words sit inside the widened sentence was relabelled faithful (14), the rest stay R (20) |
| Card 89 branch traces, every approved sentence | 86 | The wave 3 report's six additions and nine borderline items by id; every other approval faithful |
| Develop control traces, every approved sentence | 54 | The wave 3 report's four additions and eleven borderline items by id; the rest faithful |

Labels after this reader read every item against its widened quote:

| Label | Count | Sub-labels |
|---|---|---|
| A, addition the check must reject | 18 | dropped_qualifier 9 ("children" for "young children"), dropped_hedge 3 ("potentially attributable" dropped), dropped_condition 1, loosened_frequency 1, added_population 1 ("in adults"), added_explanation 1, other_record 1, reframed 1 |
| F, faithful rewording, a rejection is a wrong rejection | 144 | 130 faithful, 14 record-faithful within the widened sentence |
| B, borderline, scored separately with this reader's call | 23 | stronger_degree 10 ("hallmark" for "typical", "carries risks" for "associated with"), relabelled 5 ("risk factors" for "play a role in the pathogenesis"), added_gloss 3, weaker_degree 2, narrowed 2, reframed 1 |
| R, beyond the widened quote, should stay rejected | 20 | the extra words are in the record but outside the sentence quoted |

Where this reader's labels differ from the two earlier readers:

- `cm5-c1-i8` ("spread across 10 different forms" drops "seen in greater than 1% of patients") and `cm5-c2-i3` ("occasionally" for "in rare instances") were borderline in the wave 3 report. By this brief's definition (a restricting word or hedge the sentence leaves out: frequency, condition) both are dropped qualifiers, so they are A here.
- `med1-c2-i5` was R in the design and stays R after widening: "the most common single-gene disorders" is the record's first sentence, the quote its second.
- `med1-c2-i4` ("consortium study") is borderline added_gloss, `gerd1-c2-i4` ("In children" from the record, not the quote) borderline narrowed, `md4-c1-i2` ("commonly" for "most commonly") borderline weaker_degree.
- This reader's call on each borderline class: relabelled keep; added_gloss, weaker_degree and reframed reject (an explanation or a degree the quote does not give, the same class as the design's hemoglobin addition); stronger_degree and narrowed either way.

The B items are reported, never counted in the A or F scores, so a reader who disagrees with a call can re-score from `raw/`.

## The options and their scores

All model options ran through the product's own `call_jev_batch` with `typesafe/jev-1.13`, the same `_jev_approves` rule (a "no" pick with a strictly higher probability than "yes"), and question text under the client's 1000-character cap, so each could ship as written. Every example word in a question is a general category ("elderly patients", "may reduce", "rarely"); none is from a test sentence. "A" is additions approved (must be 0 of 18 to recommend), "F" faithful rewordings approved (of 144, a rejection is wrong), "R" beyond-quote sentences approved (of 20). Scripts: `raw/offline_qualifier_judge.py`, output `raw/offline_<variant>.jsonl`.

| Option | What changes | A approved | F approved | R approved | Extra calls and latency per check call | Verdict |
|---|---|---|---|---|---|---|
| Today's question, re-run on this set (`second`, the `says_more` answers) | Nothing | 10 of 18 | 125 of 144 | 2 of 20 | none | The baseline. Lets all 9 "young children" through at 0.50 to 0.84 |
| 1. Reframed single question (`reframed`) | The live question names dropped or loosened restrictions as part of "says more", with category examples; the "yes" criterion widened to match | 7 of 18 | 115 of 144 | 2 of 20 | none; 315 to 425 ms for 30 items, as today | Fails. 6 of 9 "young children" through at 0.48 to 0.79, and 29 faithful rewordings lost |
| 2. Second question in the same call (`second`): does the sentence drop or loosen a restriction, five categories with examples; approved only when both say no | Two questions per item, one call | 7 of 18 | 113 of 144 | 2 of 20 | none; 297 to 477 ms for 15 items (30 questions) | Fails. Catches all 3 dropped hedges (0.05 to 0.23) but 6 of 9 "young children" (0.49 to 0.94), and rejects faithful hedged rewordings ("symptoms that may be related to GERD") |
| 2b. Population-only question (`population`), with today's | One question aimed at the people a claim is about, "a limiting word before a group" spelled out | 7 of 18 | 124 of 144 | 2 of 20 | none | Fails. 6 of 9 "young children" through at 0.51 to 0.93, same items |
| 2c. Code lists the two-word quote phrases the sentence shortens in a CHECK line; one question per item asks whether any is a dropped limit (`pairs`), with today's | Code proposes, one question per item decides | 5 of 18 | 115 of 144 | 1 of 20 | none; 376 to 560 ms, one call at 1844 ms | Fails. 4 of 9 "young children" through at 0.52 to 0.74; near-identical sentences got 0.23 and 0.74 |
| All four questions together | | 4 of 18 | 110 of 144 | 1 of 20 | none | Fails. The same three "young children" items pass every sentence-level question |
| 3. Code check, every shortened quote phrase must keep its neighbour (`neighbour`) | No model; parser-free adjacency on words of four letters or more | 1 of 18 | 6 of 144 | 1 of 20 | none | Out. No parser is in the dependencies (checked `pyproject.toml`; no spacy, nltk or stanza), and without one the check cannot tell "young children" from "gastric contents": it rejects 138 of 144 faithful rewordings |
| 4. Code proposes the pairs, Jev decides each pair (`perpair`), with today's question | For each two-word quote phrase in which a word the sentence uses sits next to one it does not, one yes or no question: does the sentence make that phrase's claim without the missing word's limit. A sentence is approved only when today's question says no and every pair says no | 0 of 18 (two runs) | 9 of 16 sampled | not measured | 1 to 2 more Jev calls per check call, run concurrently; 347 to 574 ms per call of 30 pairs, $0.0006 per call | Recommended, with the cost below |
| 5. Ask the writer to keep qualifiers | Rule 3a of `synthesis/findings.py` says to keep every limiting word of the quote | not measured | not measured | | none at check time; a few more synth tokens | A nudge, not a gate; five directive prompt versions failed before (design.md of the sentence check). Worth adding beside option 4, since the Researcher-depth writer already kept "young children" in 5 of 5 runs and only the plain-language rewording drops it |

Option 4 in detail, from `raw/offline_perpair.jsonl` (run 1, 34 items, 242 pairs, 9 calls) and `raw/offline_perpair_run2.jsonl` (the 18 additions again, 108 pairs, 4 calls):

| Class | Pairs alone, run 1 | Pairs alone, run 2 | With today's question |
|---|---|---|---|
| dropped_qualifier, 9 | all 9 rejected; the "young children" pair at 0.15 to 0.39 | all 9 rejected; 0.10 to 0.22 | 0 of 9 approved |
| dropped_hedge, 3 | all 3 rejected; "symptoms potentially" at 0.24 to 0.27 | all 3 rejected; 0.09 to 0.21 | 0 of 3 approved |
| dropped_condition, 1 | rejected ("seen in" at 0.50) | approved | 0 of 1: today's question rejects it offline (0.22) but approved it live (0.64), so this one rests on a coin flip |
| loosened_frequency, 1 | approved: "in rare instances" shares no word with "occasionally", so no pair is proposed | approved | 0 of 1: today's question rejects it (0.46 offline; live approved at 0.55), another coin flip |
| added_population, added_explanation | rejected on incidental pairs at 0.31 to 0.49 | rejected | 0 of 2 |
| reframed, other_record | approved (no pair carries the problem; other_record has no shortened pair at all) | approved | 0 of 2: today's question rejects both at 0.0 and 0.36 |
| F sample, 16 | 10 approved | | 9 approved (one more lost to today's question) |

The six faithful rejections in the sample, by the pair that caused them: "the outpatient" dropped, four times, at 0.30 to 0.48; "a higher" dropped ("higher incidence" shortened to "including"), 0.48; "abnormal transient" dropped ("abnormal relaxation" for "abnormal transient relaxations"), 0.27. The last is a dropped modifier by the owner's bar, so the check is right and the label is generous; the first four are a setting word that "primary care" already implies, and they sit at the line.

Cost of option 4 in numbers: the set has 5.8 proposed pairs per sentence (median 4, maximum 25, 7 sentences with none). A live check call carries 4 to 8 sentences, so 25 to 50 pair questions, one or two calls of at most 30 questions (`MAX_BATCH_QUESTIONS`), each 347 to 574 ms and about $0.0006, run concurrently with the item call under the same 3-second bound and the same cost-cap check. Wall time per check call rises from 300 to 480 ms to about 400 to 600 ms; an answer has at most two check calls (first draft, repair), so under half a second per answer, within the 20-second line. Two of about 45 calls in this session failed at the transport layer (`SSLV3_ALERT_BAD_RECORD_MAC`, before any reply); with two or three calls per check instead of one, a check that approves nothing for that reason becomes two to three times as likely, and it already fails closed today.

## Why sentence-level questions fail and per-pair questions work

- Every sentence-level framing, however the category was spelled out, left the same three or more "young children" sentences through, and gave near-identical sentences verdicts of 0.23 and 0.74. At the sentence level this class sits at Jev's noise floor: it reads "In children" as a population kept, not a limit dropped.
- Shown one phrase, its quote and the sentence, Jev's verdict on "young children" is 0.10 to 0.39 across 18 readings in two runs, never above the line. The decision is the same, only the unit changed: a concrete pair instead of an abstract definition. This is the measured behaviour the brief names (Jev follows literal words), turned to use: code puts the literal words in front of it as data.
- The proposal is code, but no word list: every two-word quote phrase in which one word is in the sentence and the other is not, the missing word of four letters or more (the one knob, a stand-in for function words), a possessive "'s" stripped. Code never decides; it only names what the classifier must look at, and it verifies the reply the way `approved_keys_from_jev` does today.
- The per-pair question states its own escape hatches (a function word, a synonym, the same scope in other words, a claim the sentence does not make), which is why 10 of 16 faithful sentences with up to 14 proposed pairs each passed every pair.

## Recommendation

Build option 4 and add option 5 beside it, behind the usual judge, adversary and five or more live runs per question. In code terms, all inside `synthesis/sentence_check.py` and only in Jev mode:

- `check_phrases(sentence, quotes)` as in `raw/offline_qualifier_judge.py`: pure, bounded by `MAX_SENTENCE_CHARS` and `MAX_QUOTE_CHARS`, tested on the labelled set (every "young children" and "symptoms potentially" pair proposed, 0 pairs for a sentence that shares no word).
- `_ask_jev` builds the item call as today and, in the same `asyncio.gather`, one or more pair calls: state of PAIR blocks (phrase, quote, sentence), questions `pair_<item>_<k>` with the fixed `PERPAIR_INSTRUCTIONS` and `PERPAIR_CRITERIA` from the script, at most `MAX_BATCH_QUESTIONS` per call, each cap-checked and charged like the item call.
- A sentence is approved only when its item answer approves (unchanged) and every one of its pair answers is a "no" that `_jev_approves`. Any failed, late, malformed or cost-capped call, item or pair, approves nothing in that check (today's rule, unchanged). A sentence with no proposed pair needs only the item answer, as today.
- The owner's exception of 2026-09-23 keeps its scope: this adds a second model veto, never a model approval. A sentence approved today can only lose approval; the cite-or-refuse gate never loosens, the three exact checks still run first on the writer's own quote, and the guard path is untouched.
- Option 5: rule 3a of `synthesis/findings.py` gains one line, keep every word of the quote that limits who, how surely, how often or where a claim holds. Fixed text in the cached prefix, one cache miss after deploy, measured not assumed.
- How to measure after building: re-run `raw/offline_qualifier_judge.py perpair` on the full 205 items (about 40 calls; A must be 0 of 18 twice) and report the faithful rejections by pair word, since this report measured F on 16 sampled sentences only; then five or more live runs of each question at plain language, counting sentences shown, "young children" shown as "children" (must be 0) and the hedged primary-care sentence shown.
- Ask the owner one question before building: the check will also drop faithful plain-language sentences that leave out a setting word such as "outpatient", at a coin flip, about half of such sentences in the sample. Recommended answer yes, because a sentence that is not shown costs the reader less than a claim about the wrong people; the alternative is today's check, which shows "children" for "young children" in 3 to 5 of 15 runs.

## What was not covered

- Option 4's faithful-rejection rate on the full set is unmeasured: 16 faithful sentences were sampled, 10 of them the hedged rewordings the sentence-level questions had wrongly rejected, so the sample is hard-biased and the 9 of 16 figure is a floor, not an estimate. The 40-call full run is the first step after the owner's yes.
- Two additions never produce a pair ("in rare instances" replaced by "occasionally"; a fact from another paper) and one sits at the line ("seen in greater than 1% of patients" dropped, 0.50 then approved). All three are rejected by today's question offline, two of them at a coin flip that approved them live. Option 4 does not fix the coin flip on those classes; it fixes the two classes the owner saw.
- Verdicts were measured in batches of 30 items or 30 pairs, not the live 4 to 8 items; the sentence check design measured that batch size moves Jev's verdicts.
- Option 5 was not simulated; it needs the writer to produce new drafts.
- The labels are one reader's, with the two earlier readers' labels kept in the file where they differ.
- No local database, no graph and no write path ran; every model call was an offline Jev call over captured sentences.
