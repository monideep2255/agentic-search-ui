# Card 17 diagnosis: a reworded sentence that switches papers on a generic title word

Diagnosis only, 2026-10-08 overnight, read against `develop` at `c916cfa3`. Paths are relative to `<repo-root>`. No code was changed and no model was called.

## Table of contents

- [Status today](#status-today)
- [What a person sees](#what-a-person-sees)
- [The cause](#the-cause)
- [Design options and their costs](#design-options-and-their-costs)
- [The smallest fix](#the-smallest-fix)
- [Overlap with phase 8.7 and the guardrail](#overlap-with-phase-87-and-the-guardrail)
- [Needs the owner](#needs-the-owner)
- [Proposed test query](#proposed-test-query)

## Status today

Still happens on develop. The rule is unchanged since `044f834b` (2026-10-05) took the card 17 guard back out. Seven later commits touched `synthesis/grounding.py` (`14ef02be` to `804db362`, card 101's work); none of them touches the switch rule or `_names_its_record`.

## What a person sees

An answer reads as one story, but two sentences in a row cite two different papers. The second sentence uses a pointing phrase such as "these mutations". The reader takes it to mean the first paper's subject. It means the second paper's.

The case measured live on 2026-09-24 (done file, item 12.16 part 4): after a Tay-Sachs sentence, "No patient carried more than one of these mutations" cited a BRCA paper whose title says "patients". A reader takes "these mutations" as the Tay-Sachs ones. The paper means BRCA founder mutations. Each sentence is true to its own quote; the link between them is false.

## The cause

| Where | What it does |
|---|---|
| `src/system_03_search_agent/synthesis/grounding.py:1863` to `1872` | A reworded sentence (`reworded`) that cites no record the sentence before it cited (`not (this_refs & previous_refs)`) is dropped unless `names_a_record` is true. |
| `synthesis/grounding.py:2090` to `2126`, `_names_its_record` | `names_a_record` is true when the sentence shares any one stemmed content word with its record's title (`if said & title: return True`, line 2117). |

One shared word is enough. "Patients", "disease", "children", "study" and "risk" sit in many titles. Sharing one of them says nothing about which record a sentence is about. The rule cannot tell a real anchor ("BRCA1") from a generic one ("patients").

The guard tried in `d9a8eabb` and removed in `044f834b` counted a title word only when no other retrieved record's title carried it. In the card 88 build that dropped good sentences whose only anchor was "disease" or "children" (`testing/Developer/reports/2026-10-05_wave0/card88.md`). Researcher depth with the guard: 6 of 10 runs reached two or more written sentences. Without it: 8 of 10.

## Design options and their costs

This is a trade between two harms the owner ranks. A dropped good sentence costs the reader a written answer. A kept wrong-paper sentence costs the reader a false link. The house rule "a confident wrong record is worse than a missing one" leans one way. The owner's "Structure, not words" ruling (12.16 part 4) and "no hardcoded decisions" rule out a stop-word list.

| Option | How it works | What it costs | Fence |
|---|---|---|---|
| A. Distinct from every other record (the removed guard) | A title word counts only when no record the sentence does not cite has it in its title. | Measured: drops good sentences on shared words like "disease" and "children". Researcher 6 of 10 runs with two or more sentences, against 8 of 10 without. | `grounding.py`, `_names_its_record`, `run_grounding_pass` |
| B. Distinct from the record just left | A title word counts only when the title of a record the previous sentence cited does not carry it. Only the switch is judged, so a word every title shares still counts unless the paper the reader just read has it. | Smaller loss than A, since only one or two titles are compared. Does not fix the Tay-Sachs case unless the Tay-Sachs title also said "patients"; that title is not in the record and needs a replay to know. | Same as A |
| C. Two anchors | A switch needs two distinct shared title words, or one defined short form (the card 88 rule). | Short titles and terse sentences lose their sentence. Needs a replay over saved replies to measure. "No patient ... these mutations" shares only "patient" with its title, so it is dropped. | Same as A |
| D. Ask the sentence check | Pass the previous kept sentence to the sentence check model as context, and add one question: read after that sentence, does this one still say what its quote says? A decision, so it goes to a classifier, as the owner's rule asks. | One more input per checked sentence; more tokens on every Researcher answer (343 to 611 ms per check call, card 88 diagnosis). Changes the one bounded model exception in production standards. Fails closed, so a failed call drops the sentence. | `synthesis/sentence_check.py`, `core/graph.py` `_ground_with_sentence_check`, `harness/decide.py` and possibly `harness/jev_client.py` |
| E. Say the switch instead of deleting | Keep the sentence, and when it switches records on a single shared word, put a code-built lead-in naming its record's short title ("In a study of BRCA1 carriers, ..."). Nothing is lost and the link is made true. | A layout change on the answer path; code writes words beside the model's sentence. Needs a design for how the title is shortened. Reads heavier in Plain language. | `grounding.py` render step (lines 1879 to 1900), `synthesis/answer_layout.py` |

A pointing-word check ("these", "this", "such" after a switch) is left out of the table. It is a word list, which the owner ruled out on 2026-09-24, and the "Yes," or "No," exception was granted only for the whole class of answer words.

## The smallest fix

The smallest in code is option B or C. Each is a few lines in one function.

| Field | Value |
|---|---|
| Files and functions | `src/system_03_search_agent/synthesis/grounding.py`: `_names_its_record` (new argument), `run_grounding_pass` (pass the previous sentence's record titles, lines 1853 to 1861); tests in `tests/system_03_search_agent/synthesis/test_sentence_check.py` |
| Answer path | Yes |
| Dial position | 2, runnable behaviour |
| Size | S for B or C; M for D or E |
| Migration, package, event schema | None for any option |

Before building any option, replay it over saved live replies and count the sentences it drops. The card 88 build's trace runs, `raw/local_write_trace.py` in `testing/Developer/reports/2026-10-05_card88/`, are the cheapest bench. The bar from card 88: two or more written sentences on 5 of 5 GERD runs at each depth.

## Overlap with phase 8.7 and the guardrail

| Fence | Phase 8.7 | Guardrail |
|---|---|---|
| Options A, B, C: `synthesis/grounding.py` | Not in 8.7's list. Its callers sit in `core/graph.py` (`_ground_with_sentence_check`, line 9683; `write_node`, lines 13408 and 13513), which 8.7 rewrites, but the call signature does not change. | None |
| Option D: `sentence_check.py`, `harness/decide.py`, `_ground_with_sentence_check` | Yes: `harness/decide.py` is rewritten tonight | Yes if it touches `harness/jev_client.py` |
| Option E: `synthesis/answer_layout.py` | Yes | None |

Build B or C after 8.7 merges, or on top of it, so the replay runs against 8.7's writer.

## Needs the owner

Yes, a design choice. The options trade dropped good sentences against wrong-paper links, and D changes the bounded model exception. Recommendation to put to the owner: E if they want nothing lost and the link made true; B as the cheapest code-only step, measured by replay first.

## Proposed test query

Proposed entry 108, for section 1 of `testing/Test_queries_and_workflows.md`:

```markdown
### 108. A sentence that moves to a different paper says which paper (card 17, 12.16 part 4)

Queries to try:

- `What genetic variants are common in people of Ashkenazi Jewish descent?` in Researcher, three times
- The same question in Plain language

What you should see:

- When one sentence cites a Tay-Sachs paper and the next cites a BRCA paper, the second sentence names BRCA or its paper's subject; it never says "these mutations" as if they were the first paper's.
- Each answer still has two or more written sentences above its records.
- Why it matters: a reader who links two facts the papers never linked takes away a false finding about their own ancestry.
```
