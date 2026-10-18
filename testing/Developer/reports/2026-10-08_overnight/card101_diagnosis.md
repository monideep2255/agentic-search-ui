# Card 101 diagnosis: the three slices still open

Diagnosis only, 2026-10-08 overnight, read against `develop` at `c916cfa3`, which carries #204. Paths are relative to `<repo-root>`. No code was changed and no model was called. One local probe ran the real `run_grounding_pass` offline on the adversary's and the judge's own reproductions; its script is not committed.

## Table of contents

- [Status today](#status-today)
- [What a person sees](#what-a-person-sees)
- [The causes](#the-causes)
- [The smallest fixes](#the-smallest-fixes)
- [Overlap with phase 8.7 and the guardrail](#overlap-with-phase-87-and-the-guardrail)
- [Needs the owner](#needs-the-owner)
- [Proposed test query](#proposed-test-query)

## Status today

All three still happen on develop. The probe, through `run_grounding_pass` with the first pass's check items collected:

| Slice | Record | Writer wrote | Shown on the first pass | Items sent to the check |
|---|---|---|---|---|
| A4-101-01 | "No isolates of S. Typhimurium carried the blaCTX-M gene." | the same words, cited | "Typhimurium carried the blaCTX-M gene [1]." | 0 |
| A4-101-01 | "It is unproven that the U.S. FDA-approved vaccine prevents bronchiolitis in infants." | the same words, cited | "FDA-approved vaccine prevents bronchiolitis in infants [1]." | 0 |
| A4-101-02 | 'Advertisers claimed that "this drug is a miracle. Drug X cures cancer. It is safe." Regulators found every claim false.' | "Drug X cures cancer [1]." | "Drug X cures cancer [1]." | 0 |
| A4-101-02 | "An early uncontrolled report (since retracted. Ribavirin cured every infant. No controls were used.) prompted this trial ..." | "Ribavirin cured every infant [1]." | "Ribavirin cured every infant [1]." | 0 |
| J5-101-01 | A 740-character abstract opening "There was no evidence that azithromycin shortened the illness in infants with bronchiolitis." with no capital-led break after it | the cut, with its own words as the quote | nothing yet | 1, whose only quote is the cut itself: "azithromycin shortened the illness in infants with bronchiolitis" |

The J5-101-01 item is then shown if the check approves it; the judge measured the same shape approved 3 of 3 live in round 4 (A4-101-07). `DECISIONS.md`, 2026-10-08, records J5-101-01 as open at merge.

## What a person sees

- A4-101-01: a paper says "No isolates of S. Typhimurium carried the gene". The answer says "Typhimurium carried the gene", cited to that paper. The writer copied the paper faithfully; the system cut the "No" off.
- A4-101-02: a paper quotes a claim in order to reject it. The answer prints the rejected claim as the paper's finding.
- J5-101-01: a paper says "There was no evidence that azithromycin shortened the illness". The answer can say "Azithromycin shortened the illness", when the paper's sentences run long and the writer quoted its own copied words.

Each shows a paper saying the opposite of what it says, with a citation that makes it look checked.

## The causes

| Slice | Where | What goes wrong |
|---|---|---|
| A4-101-01 | `src/system_03_search_agent/synthesis/grounding.py:57`, `_SENTENCE_BOUNDARY` | The writer's reply is split at every full stop and space, so "No isolates of S." becomes its own unmarked piece and is stripped. |
| A4-101-01 | `grounding.py:806`, `_RECORD_SENTENCE_BOUNDARY` | The record is split at a full stop, space and capital, so "Typhimurium carried the blaCTX-M gene." counts as a whole record sentence. `is_whole_record_sentence` (line 994) then lets the tail through with no check. The round 4 comment (lines 949 to 953) names the "Dr. Smith" case and accepts it; it is wider than stated, since it needs no writer cut. |
| A4-101-02 | `grounding.py:806` and `_record_sentences` (line 959) | A sentence in the middle of a quotation or bracket starts after a full stop and a capital and ends at the next one, so it reads as whole. Nothing asks whether a quotation mark or bracket is still open around it. |
| J5-101-01 | `grounding.py:1131` to `1132`, `_copied_clause_candidate` | With a valid writer quote, the clause's record text is `widen_to_record_sentences(quote, ...)`, which falls back to the quote itself when the run of record sentences is over 600 characters (`widen_to_record_sentences`, line 836). Round 5 switched only the unquoted branch (line 1133 onward, `_copied_record_span`) to hold instead. |

## The smallest fixes

| Field | J5-101-01 | A4-101-02 | A4-101-01 |
|---|---|---|---|
| Change | In `_copied_clause_candidate`'s quoted branch, use `record_sentence_run` and return None when it is None, as the unquoted branch already does. The clause is held, and with it the sentence. | A record sentence that starts while a quotation mark or bracket opened before it in the value is still open is not whole, so a copy of it is a cut and goes to the check. Counted from the value's own characters, no word list. | Do not end a record sentence after a token shaped like an abbreviation: one capital letter, or letters with an inner full stop ("U.S."). Applied in the one boundary that `record_sentence_run`, `_record_sentences` and `_starts_inside_record_sentence` share, so the copy becomes a cut and the check reads the whole sentence. A shape rule, not an abbreviation list. |
| Files and functions | `grounding.py`, `_copied_clause_candidate`; a test in `tests/system_03_search_agent/synthesis/test_copied_cuts.py` with a quoted cut past 600 characters | `grounding.py`, `is_whole_record_sentence` or `_record_sentences`; tests in `test_copied_cuts.py` | `grounding.py`, `_RECORD_SENTENCE_BOUNDARY` and its three users; tests in `test_copied_cuts.py` and the widening tests |
| Answer path | Yes | Yes | Yes |
| Dial position | 2 | 2 | 2 |
| Size | S | S | M: it moves the boundary that the widener and the code-built listing also read, so it needs the 168-draft replay and the listing fuzz the judge used in round 5 |
| Migration, package, event schema | None | None | None |

Direction of every change: each one only turns a sentence that shows unchecked today into one the check reads, or one that is held. None can add text. The cost is sentences held when the check says no or cannot run, which the owner accepted on 2026-10-07 ("a missing sentence is better than a wider one"). A4-101-01 will also hold some faithful copies, since a period after one capital letter does sometimes end a sentence ("vitamin C. Then ..."); the replay measures how many.

The J5-101-01 fix is the one the judge's stop condition named, and it is the smallest. Build it first.

## Overlap with phase 8.7 and the guardrail

| Fence | Phase 8.7 | Guardrail |
|---|---|---|
| `synthesis/grounding.py` | Not on 8.7's list. Its callers in `core/graph.py` (`_ground_with_sentence_check`, `write_node`) are rewritten, but the call does not change. | None |
| The sentence check itself (`synthesis/sentence_check.py`, `harness/jev_client.py`) | Untouched by these fixes | Untouched |

These fixes can be built tonight beside 8.7, provided the replay runs again on 8.7's writer after it merges.

## Needs the owner

No for J5-101-01 and A4-101-02: both apply the owner's 2026-10-07 rule to a path it missed. A4-101-01 needs the owner only if the replay shows it holds many faithful sentences; then the trade between lost sentences and reversed ones is theirs.

## Proposed test query

Existing query 106 ("A plain-language answer never claims more than its paper") covers the class. Proposed lines to add to it:

```markdown
Queries to try (added):

- `What do studies say about Salmonella Typhimurium and extended-spectrum beta-lactamase genes?` in Researcher, three times

What you should see (added):

- No sentence begins with a species or product name cut from the middle of the paper's sentence ("Typhimurium carried ...", "FDA-approved vaccine ..."), and no sentence drops the paper's "no", "not" or "no evidence that".
```
