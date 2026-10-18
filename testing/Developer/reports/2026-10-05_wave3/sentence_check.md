# Card 89: whole record sentences for the sentence check

Builder report, branch `fix/card89-whole-sentence-quotes`, 2026-10-05. Built options 1 and 2 of `testing/Developer/reports/2026-10-05_sentence_check/design.md` as the owner decided (`DECISIONS.md`, 2026-10-05). The owner's ship condition FAILED: the live traces show the check approving six sentences that add something the record does not say. Nothing was loosened. The change is committed locally only and must not merge as it stands.

## Table of contents

- [Verdict](#verdict)
- [What changed](#what-changed)
- [Unit tests and the red proof](#unit-tests-and-the-red-proof)
- [Gates](#gates)
- [Live traces](#live-traces)
- [Approved additions](#approved-additions)
- [Borderline approvals](#borderline-approvals)
- [What the person sees, per run](#what-the-person-sees-per-run)
- [What is not covered](#what-is-not-covered)
- [Develop control, side by side](#develop-control-side-by-side)

## Verdict

| Question | Answer |
|---|---|
| Did any approved sentence add something the record does not say? | Yes, 6 clear additions in 86 approvals across 15 runs, all in GERD plain language runs; 5 of them reached the screen |
| Ship condition met? | No. Stop and report, per the lead's brief |
| Which option caused them? | Neither widening step. In all six the writer's quote was already the whole record sentence, so the judge read exactly what option 1 alone would have shown it. Jev approves these readings of a whole sentence |
| Did it help the person? | Yes, strongly: GERD Researcher shows 5 to 7 prose sentences (design baseline 1 to 3), and the Mediterranean answer names Familial Mediterranean fever in 3 of 5 runs (baseline 1 of 3) |

In the person's words: a plain-language GERD answer now says "In children, the symptoms can be varied and nonspecific" where the paper says young children, and "Reflux symptoms are among the most common reasons people visit their primary care doctor" where the paper says symptoms potentially attributable to GERD. Each is a small widening, and the owner's bar counts both.

## What changed

- Option 1, `src/system_03_search_agent/synthesis/grounding.py`: new `widen_to_record_sentences(quote, record)` returns the shortest run of whole record sentences containing the quote, as exact record text sliced from the finding, found in `_quote_form` the same way `_quote_is_valid` finds a quote. The boundary is the one the design measured offline (`.`, `!` or `?`, space, then a capital, a quotation mark or an opening bracket). Where a candidate is built, each quote is widened against its own finding and duplicates are dropped. Only `SynthesisCandidate.quotes`, what the judge reads, changes. The candidate's key, the second-pass lookup, the claim's stored `evidence_quote`, and all three exact checks (quote in the record, numbers, negation) stay on the writer's own quote.
- A run longer than `MAX_WIDENED_QUOTE_CHARS` (600, equal to `sentence_check.MAX_QUOTE_CHARS`, asserted by a test) keeps the writer's quote, so a widened quote is never cut short in the check item.
- My widening matches the design's offline `widen_to_sentences` on all 73 quotes of the 65 labelled pairs (73 identical, 0 different, checked with no model call), so the design's offline scores for `jev_sentence` describe this code.
- Option 2, `src/system_03_search_agent/synthesis/findings.py`, rule 3a: "a short contiguous span of about five to thirty words, never the whole finding" became "quote the whole sentence of the finding that your sentence rests on, from its first word to its full stop, never the whole finding", with one quote per sentence drawn on (`[4: "First sentence."][4: "Second sentence."]`). The narrower-span escape stays for a sentence whose no or not the written sentence does not state, so the negation check is not set up to fail, and for a sentence over about sixty words, so a quote stays under the 600-character marker limit. The example quote is now a whole sentence.
- Rule 3a sits in `SYNTH_SYSTEM_INSTRUCTION`, the stable cached prefix. The edit is fixed text with no interpolation, so the prefix stays byte-identical across queries (`test_prompt_cache_prefix.py` passes); the one cost is a single cache miss on the first query after deploy, as with the earlier rule 3a edit in commit 1cd59689. I read the brief's line on the cached prefix as forbidding per-query variation, which this edit does not add; if the lead meant any edit to the prefix, option 2 is its own commit and can be dropped alone.
- Not changed: the judge, its question, its decision point, its approve rule, and the guard path. The guard-tier path reads the same `candidate.quotes`, so in guard mode it now also reads widened quotes.

## Unit tests and the red proof

Added to `tests/system_03_search_agent/synthesis/test_sentence_check.py` and `test_answer_quality.py`:

| Test | What it proves |
|---|---|
| `test_a_mid_sentence_quote_is_widened_to_its_whole_record_sentence` | A mid-sentence quote reaches the judge as its whole record sentence, in the Jev state |
| `test_a_quote_crossing_two_record_sentences_is_widened_to_both` | A quote spanning a boundary widens to both sentences |
| `test_a_quote_that_is_already_a_whole_sentence_is_unchanged` | A whole-sentence quote is unchanged |
| `test_the_exact_checks_still_run_on_the_writers_own_quote` | Negation is judged on the writer's quote (the widened sentence says "does not", the candidate still forms); a number only in the widened sentence still blocks the candidate; a quote not in the record still blocks it; the key and the stored evidence stay the writer's words |
| `test_two_quotes_in_one_record_sentence_are_shown_once` | Two quotes from one sentence show it once; the key keeps both |
| `test_a_run_of_record_sentences_too_long_to_show_keeps_the_writers_quote` | Over 600 characters, or not found, returns the writer's quote |
| `test_a_widened_quote_is_never_cut_short_in_the_check` | The cap equals the check item's quote cap |
| `test_rule_3a_asks_for_whole_record_sentences_one_quote_each` | Rule 3a asks for whole sentences, one per quote, and keeps its nothing-more and negation lines |

Red on old code, each proved with `git show origin/develop:<file>` copied over the file, then restored:

- `grounding.py` from origin/develop: the test module fails to import, so every new widening test is red.
- New helper kept, old call site restored (writer quotes sent to the judge): 4 fail by assertion (mid-sentence, two sentences, exact checks on the writer's quote, two quotes shown once). The already-whole test passes there by design, since nothing should change for it; its only red is the import failure above.
- `findings.py` from origin/develop: the rule 3a test fails.

## Gates

| Gate | Result |
|---|---|
| `gate02_import_order.sh` | Pass |
| `gate03_lint.sh` (ruff, whole repository) | Pass |
| `gate04_unit_suite.sh` | 6541 passed, 6 failed, 229 skipped. All 6 failures are `psycopg2.OperationalError: connection to server at "localhost", port 5432 failed: Connection refused` in `adapters/graphql/test_no_cost_channel.py` (3) and `core/test_think_retry.py` (3): no Postgres runs locally on 5432. They touch no code this change touches; CI has its own Postgres |
| `test_sentence_check.py`, `test_answer_quality.py`, `test_prompt_cache_prefix.py` | All pass |

## Live traces

- 15 runs through the real write path (`core.run.run`, real models, tools and graph, `CLASSIFIER_PROVIDER=jev` as develop runs), with the design's trace script adapted to log the writer's own quotes beside the widened ones: `sentence_check_raw/trace_run.py`, summarised by `sentence_check_raw/summarize.py`. Raw output: `sentence_check_raw/<label>.jsonl`.
- Labels: `gr` is GERD at Researcher depth, `gp` GERD at plain language, `md` the Mediterranean question at plain language.
- The user database ran as a throwaway Postgres on port 5433 in the session scratchpad, migrated with the repository's alembic and stopped afterwards; nothing touched the owner's database or any remote one. Keys came from the repository `.env` into the trace process only.
- Spend: about $0.23 for the 15 runs (OpenRouter-reported totals). No reruns. A first batch with a shell word-splitting slip exited before any model call, at no cost.

Every approved sentence (86) was read against the record sentence(s) the judge read and the whole cited record.

## Approved additions

Labelled A by the design's own classes (a widened population; "may" or "potentially" turned into a fact):

| Run, item | Jev "no" | Sentence | Record sentence the judge read | What it adds | Shown |
|---|---|---|---|---|---|
| gp1 c1 i6 | 0.79 | In children, GERD symptoms can be varied and nonspecific, which makes careful diagnostic evaluation important | The clinical manifestations of GERD in young children are varied and nonspecific prompting the necessity for careful diagnostic evaluation. | "young children" widened to "children" | Yes |
| gp2 c2 i5 | 0.81 | In children, the symptoms can be varied and nonspecific, requiring careful evaluation | same | same | Yes |
| gp3 c2 i3 | 0.71 | In children, GERD shows varied and nonspecific signs, making careful diagnosis important | same | same | Yes |
| gp5 c1 i4 | 0.80 | In children, GERD has varied and nonspecific signs that require careful evaluation | same | same | Yes |
| gp1 c2 i6 | 0.59 | GERD symptoms are among the most common reasons people visit their primary care doctor | Symptoms potentially attributable to gastroesophageal reflux disease are among those most commonly reported to primary care providers in the outpatient setting. | "potentially attributable to GERD" stated as GERD symptoms | No |
| gp4 c2 i6 | 0.57 | Reflux symptoms are among the most common reasons people visit their primary care doctor | same | same hedge dropped | Yes |

- The "young children" case is the one the design already named as Jev's boundary, then a coin flip at 0.44 to 0.73. With whole sentences it is approved at 0.71 to 0.81, above the 0.6 line option 3 proposed, so option 3 would not have caught these four.
- The record does also say "GER in children is very common" and "GERD in children" in other sentences, which is why a reader may call these soft. The owner's bar counts them, and so does the design's own classification.
- At Researcher depth every approved sentence on this record kept "young children" (one per run, all five runs); the widening came from plain-language rewording.

## Borderline approvals

Not counted above, listed for the owner's call:

| Runs | Pattern |
|---|---|
| gp2 c2 i4, gp3 c2 i4 | "Risk factors and underlying causes include ..." for factors the record says "play a role in the pathogenesis" (a relabelling toward the question's "risk factors") |
| gp2 c1 i5, gp5 c1 i6 | "long-term use carries risks including ..." for "is associated with" |
| gr3 c1 i3, gr5 c1 i3 | "hallmark symptoms" for "typical symptoms" |
| gp1 c1 i4 | adds "(the valve between the esophagus and stomach)" as a gloss for the lower esophageal sphincter |
| md4 c1 i4 | "common single-gene disorders" for "the most common" (weaker degree) |
| md3 c2 i2 | "Another group of studies focuses on" one cited paper |

Every other approval (71) is a faithful rewording of its record sentence(s). No approved sentence carried a fact from a different paper: the three-sentence FMF item in md4 rests on one abstract.

## What the person sees, per run

| Run | Sent to the check | Approved | Prose sentences shown | Of them model-approved | FMF named | Seconds |
|---|---|---|---|---|---|---|
| gr1 | 11 | 8 | 6 | 5 | n/a | 17.7 |
| gr2 | 11 | 7 | 5 | 4 | n/a | 29.2 |
| gr3 | 9 | 6 | 5 | 5 | n/a | 15.7 |
| gr4 | 11 | 7 | 5 | 3 | n/a | 22.1 |
| gr5 | 12 | 8 | 7 | 5 | n/a | 20.3 |
| gp1 | 12 | 8 | 4 | 4 | n/a | 25.8 |
| gp2 | 10 | 7 | 3 | 3 | n/a | 35.9 |
| gp3 | 12 | 8 | 4 | 4 | n/a | 31.3 |
| gp4 | 12 | 6 | 2 | 2 | n/a | 20.3 |
| gp5 | 6 | 5 | 5 | 5 | n/a | 17.2 |
| md1 | 8 | 2 | 2 | 1 | No | 21.9 |
| md2 | 10 | 4 | 5 | 3 | No | 29.3 |
| md3 | 8 | 3 | 3 | 3 | Yes | 20.2 |
| md4 | 8 | 6 | 4 | 4 | Yes | 23.5 |
| md5 | 5 | 1 | 2 | 0 | Yes | 35.5 |

- "Prose sentences shown" excludes the code-built "Found N records" line. Every run ended as an answer.
- The writer drafted Familial Mediterranean fever in all five Mediterranean runs; md1 and md2's FMF sentences were rejected (md1 at 0.02, "common in people of Mediterranean descent"; md2 twice, one at 0.04 that reads faithful to me). md5's shown FMF sentence passed code alone.
- Approval rate: 86 of 155 sentences sent, against 18 of 65 in the design's six runs.
- Ten of the 15 runs took over 20 seconds. The design's own baseline runs took 19.7 and 32.4 seconds, the judge call is a few hundred milliseconds, and develop was not timed side by side here, so this is not attributed to the change.

## What is not covered

- The labels are one reader's, mine. The six additions follow the design's classes; the borderline list is a judgement the owner should make.
- No develop-side control ran in the same window, so the before figures are the design's six runs, not a paired measurement.
- The guard-tier judge with widened quotes was not measured live; the design measured that model approving all 65 pairs regardless of input.
- The claim's stored evidence quote stays the writer's words. The design suggested storing the widened sentence as the citation's evidence; the lead's brief did not ask for it and it changes what the citation shows, so it is not built.
- Deep technical depth was not traced.
- What the lead must decide: whether to hold card 89, or ask the owner whether the "young children" to "children" class and the dropped "potentially" class are acceptable losses. Neither option here causes them; Jev approves them against the whole sentence, and today's check approves the first one on some runs too.

## Develop control, side by side

Asked by the lead after the hold, 2026-10-05: the same 15 traces, the same harness and the same labelling, against origin/develop's code (`1a071cc2`), with no branch change. The code came out by `git archive origin/develop src` into the session scratchpad, so nothing in the repository changed. `1a071cc2` is four merges ahead of this branch's base (cards 46, 95 and 96 to 98: notes, record lists, the cap path, the guard's empty reply); none touches grounding, the sentence check or rule 3a. Spend about $0.19, no reruns. Raw output: `sentence_check_raw/develop_control/` (labels `cr`, `cp`, `cm` match `gr`, `gp`, `md`).

| Measure | Develop (origin/develop) | Branch (options 1 and 2) |
|---|---|---|
| Sentences sent to the check | 159 | 155 |
| Approved | 54 | 86 |
| Clear additions approved | 4 (3 shown) | 6 (5 shown) |
| "young children" shown as "children" | 3: cp2 c1 i4 (0.73), cp4 c2 i6 (0.72), cp5 c1 i3 (0.81), all shown | 4: gp1, gp2, gp3, gp5 (0.71 to 0.81), all shown |
| "potentially attributable to GERD" dropped | 1: cp1 c2 i4 (0.61), "These symptoms are among the most commonly reported to primary care providers", not shown | 2: gp1 c2 i6 (not shown), gp4 c2 i6 (shown) |
| Borderline approvals | 11 | 9 |
| Prose sentences shown, GERD Researcher | 7, refused, 1, 3, 6 | 6, 5, 5, 5, 7 |
| Prose sentences shown, GERD Plain | 1, 3, 3, 4, 3 | 4, 3, 4, 2, 5 |
| Prose sentences shown, Mediterranean | 1, 0, 0, 6, 3 | 2, 5, 3, 4, 2 |
| Familial Mediterranean fever named | 0 of 5 | 3 of 5 |
| Mediterranean runs with no prose ("not yet confirmed") | 2 (cm2, cm3) | 0 |

Develop's borderline approvals, by the same patterns as the branch's: "hallmark" for "typical" (cr1 c1 i3, cr3 c1 i3); "fundamentally a clinical diagnosis" (cr4 c2 i7); "pediatric GERD pathogenesis" for a general statement in a paediatric review (cr5 c2 i4); "carries risks" for "associated with" (cp1 c2 i5); "Risk factors for GERD include" for pathogenesis factors (cp2 c1 i3, cp3 c2 i5, cp5 c2 i3); "the muscular valve" as a gloss (cp4 c1 i4); "spread across 10 different forms" dropping "seen in greater than 1% of patients" (cm5 c1 i8); "most episodes resolve on their own, though a blood transfusion is occasionally needed" for "self-limited" and "in rare instances" (cm5 c2 i3).

Reading it:

- Develop fails the owner's ship bar too. Today's check approves the same two kinds of addition, at the same probabilities (the "children" class at 0.72 to 0.81 on develop, 0.71 to 0.81 on the branch), and shows three of them to the person in 15 runs against five on the branch. Neither option creates the failure; it is Jev's verdict on these rewordings, with or without whole sentences.
- What the branch changes for the person: Familial Mediterranean fever reaches the screen in 3 of 5 runs against 0 of 5, no Mediterranean run ends with no prose (develop: 2 of 5), and GERD Researcher shows 5 to 7 prose sentences every run. On develop that is 1 to 7, and cr1's 7 were sentences copied word for word that passed code alone.
- Approved additions per approved sentence are close: 4 of 54 on develop, 6 of 86 on the branch. The branch shows more sentences, so in absolute terms it shows two more additions across 15 runs.
- Develop's cr2 hit "A step in this query hit a temporary error" and refused at $0.0004 with nothing sent to the check; it was not rerun, per the budget. cp4's count of 4 includes "Is identified by PMID 36170502", a record line, not prose.
- The labels are still one reader's. cp1 c2 i4 counts as an addition because "These symptoms" states as GERD's what the paper calls potentially attributable to GERD; a reader who takes "these" as hedged by the sentence before would count develop at 3.
