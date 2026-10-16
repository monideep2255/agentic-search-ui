# Card 17 design: a sentence that switches papers names its paper (option E)

Design only, 2026-10-15, branch `fix/card17-name-the-paper` cut from `develop` at `7626fe85`. Paths are relative to `<repo-root>`. No source file changed and no model was called. The numbers below come from a read-only replay of the 35 saved runs in the card 17 bench (`raw/probe_switches.py` beside this file, the same trace reader as `testing/Developer/reports/2026-10-09_card17/raw/replay_option_b.py`).

The card, in the user's words: "A reworded sentence that switches papers never points at the wrong paper because the only word it shares with that paper's title is a generic one such as 'patients'."

The owner's decision (`DECISIONS.md`, 2026-10-15): "Card 17 takes option E: a reworded sentence that switches to a paper on one shared title word is kept, and a code-built lead-in names its paper."

In the reader's words: when a sentence moves to a different paper and the only thing tying it to that paper is one word of its title, the answer says which paper the sentence comes from. Nothing is deleted.

## Table of contents

- [When the lead-in fires](#when-the-lead-in-fires)
- [Where it runs](#where-it-runs)
- [How the title is shortened: options compared](#how-the-title-is-shortened-options-compared)
- [The lead-in's words](#the-lead-ins-words)
- [What the person sees](#what-the-person-sees)
- [The replay plan](#the-replay-plan)
- [Build steps](#build-steps)
- [Risks](#risks)
- [Owner decisions](#owner-decisions)
- [Files](#files)

## When the lead-in fires

The switch rule on develop (`synthesis/grounding.py`, `run_grounding_pass`, lines 1863 to 1873) drops a reworded sentence that cites no record the last shown sentence cited unless `_names_its_record` is true, and `_names_its_record` (lines 2090 to 2126) is true on one shared stemmed content word between the sentence and the record's title, or on a short form the record's own text defines (card 88). That rule is not changed. The lead-in is added after it, to the sentences it already shows, and only when all five of these hold:

| Condition | In code terms | Why |
|---|---|---|
| 1. There is a sentence shown before it | The sentence is not the first in the prose the reader sees, after `drop_record_restatements` has run | A first sentence switches from nothing, so there is no earlier sentence for a pointing word to be misread against. The 111 reworded first sentences in the bench get no lead-in |
| 2. The sentence is reworded | Any of its `GroundedClaim`s carries an `evidence_quote` | A copied record sentence is the record's own words; the switch rule has never applied to it and the lead-in does not either |
| 3. It switches pages, not only refs | The `source_page_key` set of the records its claims cite is disjoint from the previous shown sentence's set | Develop's rule compares `ref_index`, and a paper's title and abstract are two refs on one page. A move from a paper's title to its abstract is no switch, so the lead-in never names the paper the reader is already in. Measured: 0 of the 173 switches in the bench were same-page, so this costs nothing today and guards the case when it comes |
| 4. Every cited page is anchored by one shared word at most | For each cited page, `title_words_shared(sentence without markers, page labels)` has at most one stem and the short form test is false; at least one page has exactly one | A sentence that shares two title words, or writes the record's own defined short form ("GERD"), names its paper already. The threshold "one" is the owner's, from the decision; it is the only number in the design |
| 5. The record has a label | The page has a `title`, `name`, `symbol` or `preferred_name` finding (`LABEL_FIELDS`), which the switch rule already requires | A lead-in can only quote what the record says about itself |

Every other sentence renders exactly as on develop: the pass that adds the lead-in returns the sentence tuple unchanged except for a prefix on the sentences above, and its claims, markers, origins and `stripped_count` untouched. The replay in [The replay plan](#the-replay-plan) proves that by comparing every sentence before and after.

What the condition fires on in the bench, over 67 writer drafts (`raw/probe_switches.txt`):

| Approval mode | Full-page switches | Switches on one shared word and no short form (lead-in fires) | Switches anchored by two or more words or a short form (no lead-in) |
|---|---|---|---|
| Live (the check's own approvals) | 41 | 20 | 21 |
| All (every reworded candidate approved) | 132 | 45 | 87 |

Across both modes the probe walked 465 shown sentences, 444 of them reworded and 111 of them first sentences; the 173 switches in the table are the rest of the reworded ones that moved to another page.

The single words the 20 live switches rested on: "children" (12), "disease" (4), "reflux" (1), "deficiency" (2), "hemoglobin" (1), "variant" (1). None of these is a word list anywhere in the design; the list is a measurement of what the rule let through.

## Where it runs

In `synthesis/answer_layout.py`, as a pass right after `drop_record_restatements` (called from `core/graph.py` at line 14594), not inside `run_grounding_pass`'s render step. Three reasons:

- The previous sentence must be the one the reader actually sees above. `run_grounding_pass`'s `previous_refs` is the last sentence the pass kept, but `drop_record_restatements` can remove a sentence after that, and then the reader's previous sentence is a different one. Reading order is only final after that drop.
- The depth and the record nouns live there. `plain_noun` and `clip_to_word` are already in `answer_layout.py`; `grounding.py` cannot import it (`answer_layout` imports `grounding`).
- It keeps the guarantee in condition 1's row above by construction: a pass that only prepends text to a sentence it selects cannot change any sentence it does not select. `drop_record_restatements` already walks sentences against claims with the same cursor (lines 1083 to 1105) and is the pattern to copy.

The anchor test itself stays in `grounding.py`, factored out of `_names_its_record` so the switch rule and the lead-in can never disagree on what counts as a shared word.

## How the title is shortened: options compared

Each option is judged against the four bars in the brief. "Readable" is judged on the bench's own titles, which run from 32 characters ("Gastroesophageal Reflux Disease.") to about 125 ("Clinical and molecular evaluation of MEFV gene variants in the Turkish population: a study by the National Genetics Consortium").

| Option | Always true to the record | Readable in Plain language and Researcher | No word list | No meaning judged by code |
|---|---|---|---|---|
| 1. The whole title, verbatim, trimmed mechanically only: trailing full stop off, square brackets off, whitespace collapsed, cut at a word boundary past a length cap with the ellipsis mark `clip_to_word` already uses | Yes by construction: the record's own words in the record's own order, and a cut is visible as a cut | Heavier than the bare sentence; in the bench 20 of 41 live switches get one, so a GERD answer carries about one lead-in in three to five sentences. Long titles are long | Yes | Yes: a length is not a meaning |
| 2. The record's own short fields: first author and year ("Smith and colleagues, 2019") | Would be, but the write step's findings do not carry them: a PubMed finding is a `title`, an `abstract` and a `pmid` (`FINDINGS` rows in every bench trace), a trial is a `name` and a status, a MedGen record a `title`. Plumbing an author and a year onto `SynthFinding` is a new field on Section 8.1's shape | Short, but it does not do the card's job: "Smith and colleagues report that no patient carried more than one of these mutations" still leaves "these mutations" pointing at the sentence before. The title says what the paper is about; an author name does not. A MedGen record and most trials have no author at all | Yes | Yes |
| 3. A classifier picks a span of the title | Code can verify the span is contiguous in the title, not that it keeps what the title means. A span that drops "in children", "in Hispanic patients" or the "RETRACTED:" label card 101 round 4 measured names the paper wrongly, which is the card's own failure moved one step | Lightest read | Yes | Yes, but a model call per switched sentence on the answer path, 0.3 to 0.6 s each (card 88 diagnosis), failing closed, which means falling back to option 1 anyway |
| 4. Cut the title at its own colon, keeping the part before the subtitle | No: "RETRACTED: Drug X cures cancer" becomes "RETRACTED", and "Gastroesophageal reflux disease in children: What's new right now?" loses nothing but a structured title loses its half. Card 101 round 4: a colon is not a sentence start | Lighter | Yes | No: which half of a title carries its meaning is a judgment |

Recommendation: option 1. It is the only one that is true by construction, needs no new field and no model call, and does exactly what the card asks: the reader sees the paper's name, so a pointing word resolves to that paper. Its cost is the one the owner accepted when choosing E, a heavier read, and it is bounded: the cap is `LEAD_IN_MAX_TITLE_CHARS = 160`, which leaves every title in the bench whole and cuts a longer one visibly.

Option 3 is the one to come back to if the owner finds Plain language too heavy on the live check. It would be a second step on top of option 1, never instead of it, because a failed or held call must fall back to a lead-in that is still true.

## The lead-in's words

Shape: the lead-in ends in a colon and the approved sentence follows it unchanged, down to its first letter.

```
From the paper "<title>": <the sentence exactly as the check approved it>
```

Why a colon and not "In the paper X, the sentence": folding the sentence into a clause means lowering its first letter, and `_capitalise_opening`'s inverse is not safe ("GERD", "BRCA1", "Clostridium" must not be lowered). A colon keeps the sentence the check read byte for byte, so the sentence check's approval still covers every word that is a claim.

The noun names the kind of record, read from the record's type through `plain_noun`, never from the model:

| `plain_noun(entity_type)` | Lead-in noun |
|---|---|
| "published paper" | "the paper" |
| "clinical trial" | "the trial" |
| anything else ("condition", "gene", "record") | "the <noun> record", so "the condition record" |

Same words at both depths. Rule 5 of `answer_layout.py` (Section 14.1's firewall) allows depth to change wording, but there is no lighter form that is both true and code-built, so one wording keeps the design small; the owner may ask for a different one.

What the title goes through, in order, all mechanical:

1. Whitespace collapsed to single spaces.
2. Square brackets removed. PubMed writes a translated title as "[Title in English].", and `_renumber_markers_by_citation_id` (`core/graph.py`, line 12537) and `sentence_token`'s `marker_ids` parse `[N]` in the sentence text, so a title must never carry one.
3. A trailing full stop removed; a trailing question mark kept, because "What's new right now?" is the title.
4. Straight and curly double quotes inside the title replaced by single quotes, so the quoted title closes where it should.
5. `clip_to_word(title, LEAD_IN_MAX_TITLE_CHARS)`, which cuts at a word boundary and appends the ellipsis mark only when it cut.

A sentence that cites two or more switched-to pages names each of them, joined with "and", in display order: `From the papers "A" and "B": ...`. The bench has no such case; the test suite covers it.

Emphasis: `key_terms` lists every record title, so when a lead-in sentence is the lead the answer emphasises (`sentence_token(..., emphasize=True)`), the title inside the quotes is bolded. That is correct behaviour, not a defect: it is the one term in the sentence the run looked up. The token text cap of 1000 characters (`sentence_token`) is not reached: 160 for the title, under 40 for the frame, and the longest bench sentence is under 400.

## What the person sees

Three real cases from the bench, each a shown sentence in live approval mode, quoted from `raw/probe_switches.txt`. "Before" is develop today; "after" is the design. The sentence before each is the one the reader sees above it.

### 1. Mediterranean variants, Plain language (`develop_control/cm5`): the card's own failure shape

The sentence above, cited to "Diagnosis and management of G6PD deficiency.": "Approximately 400 million people are affected worldwide."

| | The switched sentence |
|---|---|
| Before | "Other frequent variants include M694V at about 25% and E148Q at about 11.5%." |
| After | "From the paper "Molecular analyses of MEFV gene mutation variants in Turkish population": Other frequent variants include M694V at about 25% and E148Q at about 11.5%." |

Before, "Other frequent variants" reads as G6PD variants; they are MEFV variants from a different paper, and the only word the sentence shares with that paper's title is "variants". This is the Tay-Sachs and BRCA shape of 2026-09-24, found in the bench. After, the reader sees which paper, and the pointer resolves.

### 2. GERD, Plain language (`sentence_check_raw/gp5`): a harmless switch, the heavier read

The sentence above, cited to "Gastroesophageal reflux disease in children: What's new right now?": "Factors that contribute to GERD include abnormal relaxations of the lower esophageal sphincter, defects in the esophageal lining's defense, impaired movement and clearance of the esophagus and stomach, and anatomical defects of the lower esophageal sphincter."

| | The switched sentence |
|---|---|
| Before | "While the most effective treatment is proton-pump inhibitors, long-term use carries risks including bone fractures, kidney disease, pneumonia, and intestinal infection." |
| After | "From the paper "Gastroesophageal Reflux Disease": While the most effective treatment is proton-pump inhibitors, long-term use carries risks including bone fractures, kidney disease, pneumonia, and intestinal infection." |

This is the proton-pump inhibitor sentence option B dropped in `gr1` and `gr4`. It shares only "disease" with its title. It stays, and the reader learns it comes from the adult review, not the children's one above it. This is what Plain language pays: ten extra words on one sentence in five.

### 3. Mediterranean variants, Researcher (`sentence_check_raw/md4`): a long title, cited honestly

The sentence above, cited to "Diagnosis and management of G6PD deficiency.": "This deficiency can cause red blood cell breakdown triggered by infections, certain drugs, or fava beans."

| | The switched sentence |
|---|---|
| Before | "Hemoglobin disorders are also described as common single-gene disorders, with ancestry and geography playing a significant role and African, Asian, and Mediterranean populations among the most affected." |
| After | "From the paper "Hemoglobin β-Globin Variants In Hispanic Patients: An Institutional Experience From Dallas, Texas": Hemoglobin disorders are also described as common single-gene disorders, with ancestry and geography playing a significant role and African, Asian, and Mediterranean populations among the most affected." |

The sentence shares only "hemoglobin" with its title. After, a researcher sees that a claim about Mediterranean populations rests on a paper about Hispanic patients in Dallas, which is exactly the thing a citation chip hides until clicked. The title is 97 characters and is shown whole.

For the record, the most common live case (12 of 20) is "In young children, however, clinical manifestations are varied and nonspecific, necessitating careful diagnostic evaluation." switching to the children paper on the word "children". It gets the lead-in too, because the rule cannot tell "children" from "patients" without a word list, and the owner ruled word lists out. It reads as a correct attribution rather than a repair.

## The replay plan

The bench is the same 35 saved runs and 67 writer drafts option B was replayed over, in the three folders `replay_option_b.py` reads:

| Folder | Runs |
|---|---|
| `testing/Developer/reports/2026-10-05_wave3/sentence_check_raw` | gp1 to gp5, gr1 to gr5, md1 to md5 |
| `testing/Developer/reports/2026-10-05_wave3/sentence_check_raw/develop_control` | cp1 to cp5, cr1, cr3 to cr5, cm1 to cm5 |
| `testing/Developer/reports/2026-10-05_sentence_check/raw` | gerd1 to gerd3, med1 to med3 |

`raw/replay_option_e.py`, written by the builder from `replay_option_b.py`'s trace reader (the `rows_of`, `findings_of`, `quotes_for`, `drafts_of` and `shown` functions, reused as they are), runs each draft in both approval modes, live and all, through:

- Before: `run_grounding_pass` as on develop, then `drop_record_restatements`.
- After: the same, then the new pass.

The bar, every line of it checked by the script and printed as a count:

| Check | Pass condition |
|---|---|
| No good sentence dropped | The after sentence tuple has the same length as before, and every after sentence, with its lead-in removed, equals its before sentence character for character. Expected 0 dropped and 0 changed |
| Every switched sentence names its paper | Every sentence meeting the five conditions in [When the lead-in fires](#when-the-lead-in-fires) begins with the lead-in. Expected 20 in live mode and 45 in all mode, the probe's counts; a different count is a finding to explain, not to accept |
| No lead-in on any other sentence | A sentence not meeting the conditions is unchanged. Expected 0 |
| The lead-in is true to the record | Each quoted title is, after the five mechanical steps, the label of a page the sentence cites. Expected 0 mismatches |
| The card 88 bar holds | Two or more written sentences on 5 of 5 GERD runs per depth, unchanged from option B's before column by construction, printed anyway |

The script writes every lead-in it added, with its run and the title, to `raw/replay_option_e.txt`, so a reviewer can read all 65 and say whether any one names a paper the sentence is not about.

How a builder runs it, from the repository root with no network:

```
"<repo-root>/venv/bin/python" -I testing/Developer/reports/2026-10-15_card17/raw/replay_option_e.py \
  src testing/Developer/reports/2026-10-15_card17/raw/replay_option_e.txt \
  testing/Developer/reports/2026-10-05_wave3/sentence_check_raw \
  testing/Developer/reports/2026-10-05_wave3/sentence_check_raw/develop_control \
  testing/Developer/reports/2026-10-05_sentence_check/raw
```

The traces were recorded on 2026-10-05 code and the pass is today's, so, as in the option B build, only the before and after difference is the measure.

## Build steps

Dial position 2, runnable behaviour on the answer path, as the diagnosis set it. Branch `fix/card17-name-the-paper`, one pull request into `develop`.

| Step | File fence | What |
|---|---|---|
| 1. Factor the anchor test | `src/system_03_search_agent/synthesis/grounding.py`: `_names_its_record` (lines 2090 to 2126) and the label and short form maps in `run_grounding_pass` (lines 1474 to 1490) | Add `title_words_shared(sentence, labels) -> set[str]` (the `said & title` set) and `names_by_short_form(sentence, labels, short_forms) -> bool` (the loop). `_names_its_record` becomes `bool(title_words_shared(...)) or names_by_short_form(...)`. Add `record_labels_by_page(synth_findings)` and `short_forms_by_page(synth_findings)` returning the two dicts the pass builds inline, and have the pass call them. No behaviour change; the switch tests in `tests/system_03_search_agent/synthesis/test_sentence_check.py` (lines 351 to 470) must pass untouched |
| 2. The pass | `src/system_03_search_agent/synthesis/answer_layout.py`, after `drop_record_restatements` | `name_switched_records(grounding, synth_findings) -> tuple[GroundingResult, int]`: the cursor walk of `drop_record_restatements`, the five conditions, `lead_in_for(findings)` building the words from the table in [The lead-in's words](#the-lead-ins-words), constants `LEAD_IN_MAX_TITLE_CHARS = 160` and `LEAD_IN_FRAME = 'From {noun} "{title}": '`. Pages are compared with `source_page_key`. Markers are stripped with `_MARKER.sub(" ", sentence)` before `title_words_shared`, so a marker's digit is never a shared word with a title that carries a number ("Older Than 18 Years"). Returns the input unchanged, and 0, when the result has no `sentences` or the claim cursor does not close, exactly as `drop_record_restatements` does |
| 3. The call | `src/system_03_search_agent/core/graph.py`, `write_node`, the block at lines 14577 to 14594 | `grounding, switches_named = name_switched_records(grounding, synth_findings)` directly after the `drop_record_restatements` call, inside the same `if`. Record `switches_named` beside `restatements_dropped` wherever that count is logged or traced, so the audit trail says a lead-in was written |
| 4. Unit tests | `tests/system_03_search_agent/synthesis/test_answer_layout.py` (new tests), `test_sentence_check.py` (one mutation proof) | Listed below |
| 5. Replay | `testing/Developer/reports/2026-10-15_card17/raw/replay_option_e.py` and `.txt` | As in [The replay plan](#the-replay-plan). The build report `build.md` in this folder carries the counts table and every lead-in added |
| 6. Live check | None (a report) | Below |
| 7. The queries document | `testing/Test_queries_and_workflows.md`, section 1 | Add the diagnosis's proposed entry 108, with "What you should see" reworded to the lead-in: the second sentence opens "From the paper "...":" naming the BRCA paper |

Unit tests, each a sentence pair built by hand from neutral records, never the test questions:

- Fires: reworded, previous sentence on another page, one shared title word, no short form: the sentence gains the lead-in and nothing else changes (claims, origins, `stripped_count`, the other sentences).
- Does not fire on the first sentence of the prose.
- Does not fire when the previous sentence cites the same page through a different ref (title then abstract).
- Does not fire on two shared title words, nor on a defined short form ("GERD" style, built from a neutral record).
- Does not fire on a copied sentence (no `evidence_quote`).
- A title "[Translated title]." is quoted as "Translated title", and `marker_ids` on the rendered sentence lists only the sentence's own markers.
- A title longer than the cap is cut at a word boundary and ends with the ellipsis mark; one at the cap is whole.
- A marker digit does not count as a shared word against a title carrying that number.
- A trial record reads "From the trial", a MedGen record "From the condition record".
- Two switched-to pages are both named, in display order.
- Mutation proof: with `name_switched_records` replaced by the identity, the sentence of the first test ships bare after a sentence on another record.
- `core/graph.py`: `_label_only_positions` leaves a lead-in sentence in (it has words beyond a label), and the lead sentence picked by `_lead_candidates` keeps its lead-in when it is at index 1.

Live check, after the replay passes and before the pull request: five runs each of the two bench questions, which the owner's example rule says are illustrations and not the case to build for:

- "What are the typical symptoms and risk factors of GERD?" in Plain language and in Researcher.
- "Are there any beneficial variants typically found in people of mediterranean descent?" in Plain language and in Researcher.

Pass: every answer within 20 s; two or more written sentences on 5 of 5 GERD runs per depth; every lead-in names a paper the sentence's chip opens; no sentence lost against a develop control run of the same question; and the full text of every lead-in copied into `build.md` so the owner can read how Plain language feels before deciding on [Owner decisions](#owner-decisions) item 2. Then the Ashkenazi question of the diagnosis's entry 108 three times in Researcher, as a held-out check the design was not shaped on.

## Risks

| Risk | How the design prevents it |
|---|---|
| A lead-in names the wrong paper | The title is read from a `LABEL_FIELDS` finding on a page the sentence's own claims cite, through the same `source_page_key` the citation chip uses; the replay's fourth check asserts it for all 65 lead-ins in the bench and a unit test for a two-page sentence. Code never chooses among titles by meaning: every switched-to page is named |
| A lead-in changes a sentence's meaning | The sentence follows a colon unchanged, so every claim word the sentence check approved is shown as approved. The lead-in itself asserts one thing, that the sentence comes from that record, which the citation already asserts. "From" reports provenance; it is not a verdict word, and `_VERDICT_OPENER` does not match it. A title cut is visible (the ellipsis mark) and never at a colon, so a label such as "RETRACTED:" cannot be dropped |
| A heavier Plain language read | Bounded and measured: 20 lead-ins in 35 live runs, about one sentence in five in a GERD answer, each at most 160 title characters plus a four-word frame. The owner reads the live check's lead-ins before merge and holds the option to ask for a lighter form, which is [Owner decisions](#owner-decisions) item 2 |
| A title that carries marker-shaped text or a quote mark | Square brackets removed and inner double quotes turned to single quotes before the title is framed; a unit test on "[Translated title]." and one on `marker_ids` |
| The lead-in trips a later filter | `drop_record_restatements` runs before it and never sees it; a reworded sentence is never a restatement in any case (line 1097). `_label_only_positions` requires every piece between markers to equal a label, and a lead-in sentence has a frame and a claim, so it cannot match. The sentence pair check reads the sentences the check approved, before this pass |
| The switch condition disagrees with the grounding rule | One function, `title_words_shared`, serves both, and the labels and short forms come from the same two helpers the pass uses |
| A sentence that is the picked lead | `_lead_candidates` may pick index 1 (`core/graph.py`, line 12704). A lead-in there is still true and still cites its page; a graph-level test covers it |

## Owner decisions

1. The lead-in's exact words. The design proposes `From the paper "<title>": ` with "the trial" and "the <noun> record" for other types; wording of code-built text has been the owner's in cards 23 and 32. Recommended: take the proposal and read it on the live check.
2. Whether Plain language keeps the whole title or later gets a classifier-shortened span (option 3) on top of it. Recommended: whole title at both depths now; decide on the live check's text, since no lighter code-built form is true by construction.
3. Whether the threshold stays at one shared word (the decision as written) or the lead-in fires on every full-page switch regardless of shared words. Recommended: one word, as decided; the second doubles the lead-ins (41 against 20 live) for switches that already name their paper.

## Files

| File | What it is |
|---|---|
| `design.md` | This document |
| `raw/probe_switches.py` | The read-only probe that measured the counts and examples above; run like `replay_option_b.py` without the output path |
| `raw/probe_switches.txt` | Its output: every full-page switch in the bench, the sentence before it, the titles, the shared stems and short forms |
