# Card 17 fix round: the lead-in on the order the reader sees

Fix agent, dial position 2, 2026-10-16. Branch `fix/card17-name-the-paper`, base `85b2fa42` (pull request #241), clean at the start. Paths are relative to `<repo-root>`. Nothing was committed.

The lead's design for this round (`DECISIONS.md`, 2026-10-16): the lead-in pass runs on the final order the reader sees, after card 111's removals and the first-sentence pick, and never puts a lead-in on the sentence that opens the answer. A title another listed paper shares gets the year when the record carries one, otherwise "another paper titled". A blank title becomes "another record". A short form counts as naming a paper only when one paper alone defines it. Record-type nouns read naturally and never cut a sentence's end. The call gets its missing test, and the surviving mutants get tests.

## Table of contents

- [What changed](#what-changed)
- [Findings, each with its test](#findings-each-with-its-test)
- [Open, not in this round](#open-not-in-this-round)
- [The record nouns](#the-record-nouns)
- [Replay over the 35 saved runs](#replay-over-the-35-saved-runs)
- [Live check](#live-check)
- [Mutations](#mutations)
- [Gates](#gates)

## What changed

- `core/graph.py`: the call moved from right after `drop_record_restatements` to right before `_answer_parts`, after the lead pick. Two small helpers, `_prose_echo_positions` (card 111's set, with its keep-all fallback, now used by `_answer_parts` too) and `_prose_reading_order` (the lead sentence first, then the others without card 111's removals), give the pass the order.
- `synthesis/answer_layout.py`: `name_switched_records(grounding, findings, reading_order=None)` judges "the sentence above" on that order and never leads in the first sentence in it. New `LeadInPage`, year lookup, shared-title test, fit to the 1000 character token, natural nouns.
- `synthesis/grounding.py`: `short_form_definers` and an optional `definers` argument on `names_by_short_form`. `_names_its_record`, the switch rule's own call, is unchanged.
- The lead pick: choice made, the simplest one. The pick runs first on the bare sentences, exactly as on develop, so its input and its decision are develop's. The pass then runs on the order that includes the pick. A sentence the pick lifted to the top opens the answer bare. A lead-in is therefore never offered to the pick at all.

## Findings, each with its test

| Finding | Status | Test |
|---|---|---|
| A-17-01, J-17-02 | Closed | `tests/system_03_search_agent/core/test_card_17_lead_in_order.py::test_a_sentence_card_111_leaves_out_is_not_the_sentence_above` (the judge's exact reproduction: `_label_only_positions` gives `{1}`, the pass in its own order names 0, in the reading order names 1); `test_the_lead_sentence_is_first_in_the_reading_order_and_is_never_led_in`; `test_every_sentence_stays_when_card_111_would_leave_none_and_no_lead_was_picked`; `test_answer_layout.py::test_the_sentence_above_is_the_one_the_reader_sees_above` |
| J-17-08a | Closed | `test_answer_layout.py::test_the_sentence_that_opens_the_answer_never_gets_a_lead_in`; `test_card_17_lead_in_order.py::test_the_lead_pick_sees_the_bare_sentences_and_a_picked_lead_is_not_led_in` (the write step: the pick sees no "From", the picked sentence opens bare) |
| A-17-02, A-17-08 | Closed | `test_answer_layout.py::test_a_title_another_listed_paper_shares_carries_the_year_or_says_another`: a shared title with no year reads `From another paper titled "T": `, with a `pubdate` finding `From the paper "T" (2021): `, a title no other paper shares is quoted alone even when a year exists. The shipped PubMed efetch record carries no year field, so live this reads "another paper titled" (see the live check). |
| J-17-01 | Closed | `test_a_blank_or_punctuation_only_title_reads_another_record` (seven blank shapes, `From another record: `, never `""`) |
| J-17-12 | Closed | `test_a_short_form_several_papers_define_does_not_name_one_of_them` (the count is over all pages in the answer, not only the cited ones: the reader must be told which of five papers that all define the name) |
| J-17-05 | Closed | `test_a_sentence_citing_a_titled_page_and_an_unlabelled_page_names_both` (`From the paper "T" and another record: `) |
| J-17-06 | Closed | `test_the_record_noun_reads_naturally_and_ignores_case` (25 spellings); mapping below |
| J-17-08b | Closed | `test_a_lead_in_never_cuts_the_end_of_a_sentence_at_the_token_limit` (lengths 700 to 975 end whole under 1000, 995 is left bare and whole). The title is cut shorter first, then the lead-in loses its title, then no lead-in. |
| J-17-03 | Closed | `test_the_write_step_names_the_paper_a_switched_sentence_comes_from` (drives `write_node`; red when the call is removed, mutant M1) |
| J-17-04 | Closed | M3, M4 and M5 below, each red; the vacuous lambda assertion in `test_sentence_check.py` replaced by a before and after comparison on the real pass |
| J-17-07 | Closed | `raw/replay_option_e.py` rewritten, see the replay section; `build.md` line corrected |

## Open, not in this round

- A-17-03: pronoun openers ("This condition") after a lead-in still point at nothing named.
- A-17-05, HTML entities in a title, a trailing "..." losing one dot, a title ending in a semicolon: open. A previous sentence with no marker still counts as a sentence shown before.
- A-17-06: a retracted paper's title carries no flag; card 29 adds the retraction flag separately.
- A-17-09: a prose sentence that is a bare list of PubMed ids. Pre-existing.
- Also seen, not this card: the chip number a lead-in sentence carries ([13] live) is not a listing row number (the prose cites the abstract reference, the listing the title reference). Develop numbers it the same way. Four of the Ashkenazi Plain language runs below ended `ask` with the code-built papers or condition summary and no model prose, so the pass did not run on them (develop behaviour, J-17-10 and J-17-11).

## The record nouns

The key is the entity type with case, spaces and punctuation removed, so "PubMed", "pubmed" and "Pub Med" are one key. Singular and plural; a lead-in over mixed types reads "the records"; a missing type reads "the record".

| Entity types | Noun |
|---|---|
| PubMed, PMC, Publication, Article | paper |
| ClinicalTrial, ClinicalTrials | trial |
| Disease, MedGen | condition record |
| Gene | gene record |
| SequenceVariant, VariantRecord, LiteratureVariant, Variant, ClinVar, dbVar | variant record |
| Literature entity | literature record |
| Pathogen detection isolate | pathogen sample record |
| Organism taxon, Taxonomy | organism record |
| Biological process | biological process record |
| Molecular activity | molecular activity record |
| Cellular component | cell component record |
| Ontology class, MeSH | medical topic record |
| OMIM | OMIM record |
| GTR | genetic test record |
| GDS | dataset record |
| BioProject | project record |
| BioSample | sample record |
| SRA | sequencing dataset record |
| Assembly | genome assembly record |
| Protein | protein record |
| Chemical entity | chemical record |
| anything else, including an empty type | record |

## Replay over the 35 saved runs

Command from the repository root, no network: `python -I testing/Developer/reports/2026-10-15_card17/raw/replay_option_e.py src <out> <the three trace folders>` as in `design.md`.

| Measure | Design | Round 1 | Now |
|---|---|---|---|
| Runs, writer drafts | 35, 67 | 35, 67 | 35, 67 |
| Lead-ins, live approvals | 20 | 20 | 26 |
| Lead-ins, all candidates approved | 45 | 45 | 71 |
| Sentences dropped | 0 | 0 | 0 |
| Bodies, claims, origins or counts changed | 0 | 0 | 0 |
| Meeting the conditions with no lead-in | 0 | 0 | 0 |
| Lead-ins on sentences not meeting them | 0 | 0 | 0 |
| Quoted titles not the label of a cited page | 0 | 0 | 0 |
| Pass count disagreeing with sentences changed | 0 | 0 | 0 |
| Lead pick order (sentence 1 first), cases, lead-ins | not run | not run | 106 cases, 96 lead-ins |
| Opener led in, that order | not run | not run | 0 |
| Disagreeing with the separate walk, that order | not run | not run | 0 |

Why the counts rose, 20 to 26 and 45 to 71: only J-17-12. The change is purely additive, no round 1 lead-in disappeared (65 of 65 still present; 32 new, all GERD style sentences that write a short form five papers define). Proof: the same replay with `short_form_definers` replaced by an empty map gives exactly 20 live and 45 all, the design's numbers. In the new output every lead-in is the "the paper" frame (63) or "another paper titled" (34); the records now carry a type per tool (PubMed, ClinicalTrial, Literature entity), so the replay finally reads in the words a user sees (A-17-04).

What the replay still does not model: the saved traces carry no lead pick and no card 111 listing, so the writer's own order is run, plus the lifted order above. The orders the write step builds are tested in `test_card_17_lead_in_order.py`.

Replay independence (J-17-07): the expected walk now calls none of the helpers the change added (`record_labels_by_page`, `short_forms_by_page`, `title_words_shared`, `names_by_short_form`, `short_form_definers`). It still shares `content_tokens`, `_stemmed` and `defined_short_forms`, which the change did not touch and the judge compared against develop over 39,888 calls (J-17-09). It is independent of the change, not of those three. The walk disagreed with the pass in 0 of 106 lifted cases and 0 of the writer order cases, and with the short form map emptied it disagreed in exactly the 6 and 26 cases it should, which shows the walk really is separate.

## Live check

Ten sequential runs, develop's settings (`CLASSIFIER_PROVIDER=jev`, guard and plan `deepseek/deepseek-v4-flash`, synth `z-ai/glm-5.2`, per-query cap 0.25 USD), no Opus, 0.0995 USD in all against 0.40. Traces: `raw/live_fix/*.jsonl`. Elapsed 7.4 to 12.1 s, nothing near 20 s.

| Run | Question, depth | Elapsed s | Outcome | Lead-ins |
|---|---|---|---|---|
| gerd-fix-1 | GERD, Researcher | 12.1 | answer | 1 |
| gerd-fix-2 | GERD, Researcher | 8.2 | answer | 1 |
| gerd-fix-3 | GERD, Researcher | 10.1 | answer | 1 |
| gerd-fix-4 | GERD, Researcher | 7.6 | answer | 0 |
| gerd-fix-5 | GERD, Researcher | 9.5 | answer | 1 |
| ashk-fix-1 | Ashkenazi, Plain language | 9.0 | ask | none, no model prose |
| ashk-fix-2 | Ashkenazi, Plain language | 7.4 | ask | none, no model prose |
| ashk-fix-3 | Ashkenazi, Plain language | 9.3 | ask | none, no model prose |
| ashk-fix-4 | Ashkenazi, Plain language | 7.4 | ask | none, no model prose |
| ashk-fix-5 | Ashkenazi, Plain language | 8.2 | answer | 0 |

Every lead-in shown, with the page its marker opens:

- gerd-fix-1 (the lead pick lifted sentence 1; reading order `[1, 0]`): `From another paper titled "Gastroesophageal Reflux Disease": GERD is a gastrointestinal motility disorder caused by reflux of stomach contents into the esophagus or oral cavity, producing symptoms or complications [13].` Marker [13] opens PubMed 29132520, titled "Gastroesophageal Reflux Disease.", one of the several papers with that title, so the words say "another paper titled" instead of passing it off as the paper above. No year is in the record.
- gerd-fix-2: `From the paper "Gastroesophageal reflux disease in children: What's new right now?": Pathogenic factors include abnormal transient relaxations of the lower esophageal sphincter, ...` Marker [14] opens PubMed 37034973, that title.
- gerd-fix-3 (lead pick lifted sentence 1, order `[1, 0, 2, ...]`): the same sentence and title. Marker [14] opens 37034973. The lead sentence opened the answer bare: "The typical symptoms are heartburn and regurgitation of gastric contents into the oropharynx [13]."
- gerd-fix-5: `From the paper "Gastroesophageal reflux disease in children: What's new right now?": Clinical manifestations in young children are varied and nonspecific, prompting the necessity for careful diagnostic evaluation [14].` Marker [14] opens 37034973.
- gerd-fix-4: no lead-in (the pass found no switch in the order `[1, 0, 2, 3]`).
- Ashkenazi Plain language: no lead-in in five runs. In gerd-fix-1 and gerd-fix-3 the lifted lead sentence opened bare. In no run did a lead-in sit on an answer's first claim.

## Mutations

Each applied once, tested against the four test files, restored. All red:

| Mutant | Red test |
|---|---|
| M1 the call removed from `_write_answer` | `test_the_write_step_names_the_paper_a_switched_sentence_comes_from` |
| M2 the pass given no reading order | `test_the_lead_pick_sees_the_bare_sentences_and_a_picked_lead_is_not_led_in` |
| M3 `any` reworded claim changed to `all` (J-17-04) | `test_a_sentence_with_one_copied_and_one_reworded_claim_is_reworded` |
| M4 title from the last label finding (J-17-04) | `test_the_title_quoted_is_the_first_usable_label_of_the_page` |
| M5 mixed types "the records" changed to "the paper" (J-17-04) | `test_a_lead_in_over_mixed_record_types_says_records` |
| M6 first sentence in the order may be led in | `test_the_lead_sentence_is_first_in_the_reading_order_and_is_never_led_in` |
| M7 short form definers ignored | `test_a_short_form_several_papers_define_does_not_name_one_of_them` |
| M8 year printed on any title | `test_a_title_another_listed_paper_shares_carries_the_year_or_says_another` |
| M9 no fit to the token limit | `test_a_lead_in_never_cuts_the_end_of_a_sentence_at_the_token_limit` |
| M10 "and another record" removed | `test_a_sentence_citing_a_titled_page_and_an_unlabelled_page_names_both` |
| M11 blank title check removed | `test_a_blank_or_punctuation_only_title_reads_another_record` (this one survived on the first test version, with only the judge's four blank shapes; "--", "[;]" and "( )" were added) |
| M12 noun lookup case sensitive | `test_a_sentence_card_111_leaves_out_is_not_the_sentence_above` and the noun test |
| M13 no title counted as shared | `test_a_sentence_card_111_leaves_out_is_not_the_sentence_above` |
| M14 year lookup off | `test_a_title_another_listed_paper_shares_carries_the_year_or_says_another` |
| M15 prefix not added | `test_a_sentence_card_111_leaves_out_is_not_the_sentence_above` |

## Gates

- `ruff check` (no path): All checks passed!
- isort gate 2 (`isort --check-only --diff src tests services tracker alembic .claude .github`): exit 0.
- `pytest tests/system_03_search_agent/synthesis tests/system_03_search_agent/core -m "not integration" -q`: 2336 passed, 66 skipped, 1 deselected, 1 xfailed (round 1: 2296 passed).
