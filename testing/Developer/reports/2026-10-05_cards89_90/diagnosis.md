# Cards 89 and 90: the Mediterranean question sometimes never names Familial Mediterranean fever

Diagnosis only, no code changed. Question run: `Are there any beneficial variants typically found in people of mediterranean descent?` (plain language), nine times on the develop API as a guest, each in a fresh guest session. Raw event streams: `raw/run1.json` to `raw/run9.json`. Scripts: `run_med.py`, `analyze.py`.

## Table of contents

- [What the person sees](#what-the-person-sees)
- [Reproduction table](#reproduction-table)
- [Divergence point](#divergence-point)
- [Root cause](#root-cause)
- [Fix options](#fix-options)
- [Recommendation](#recommendation)
- [Confidence](#confidence)
- [Not covered](#not-covered)

## What the person sees

- Same question, same five papers, three different kinds of answer.
- Sometimes: "Familial Mediterranean fever, caused by mutations in the MEFV gene, primarily affects Turkish, Armenian, Arab, and Jewish populations" (the right answer).
- Sometimes: "This disease is caused by mutations in a gene called MEFV", with no name for the disease, or a sentence about R202Q and M694V with no disease named.
- Sometimes: "I found 5 published papers on this topic" and nothing else, with the line "Based on 5 sources, not yet confirmed".
- Once the wrong paper leads: a sentence about G6PD deficiency only, never mentioning the MEFV papers in prose.

## Reproduction table

| Run | Named FMF in the answer text | Entity resolved by Think | Tools | Seconds | Trust outcome | What the prose said |
|---|---|---|---|---|---|---|
| 1 | no | none | ncbi_efetch x2, pubtator_annotate | 17.1 | answer | "This autosomal recessive disease is caused by mutations in the MEFV gene" |
| 2 | yes | none | same | 10.6 | answer | "Another condition, Familial Mediterranean fever, is caused by mutations in the MEFV gene" |
| 3 | no | none | same | 13.1 | answer | G6PD deficiency sentence only |
| 4 | yes | none | same | 12.2 | answer | "Familial Mediterranean fever, caused by mutations in the MEFV gene" |
| 5 | no | none | same | 14.0 | answer | "This disease is caused by mutations in a gene called MEFV" |
| 6 | no | none | same | 15.3 | ask | no prose, count line only, "not yet confirmed" |
| 7 | no | none | same | 12.0 | answer | G6PD enzyme sentences plus R202Q with M694V |
| 8 | no | none | same | 11.1 | ask | no prose, "not yet confirmed" |
| 9 | no | none | same | 11.2 | ask | no prose, "not yet confirmed" |

- Pass rate: 2 of 9 named Familial Mediterranean fever (22 percent). The 2026-09-29 retest saw 1 of 2, so the failure is the common case, not a rare one.
- 3 of 9 gave no prose at all (outcome `ask`).
- Every run: Think resolved no entity, the plan narrative was identical ("no gene, variant or disease was named, so searching the published literature"), the three tool calls were identical, and the same five PubMed records came back (16225031, 34582790, 35098403, 37782073, 39042260) in all nine runs.
- Questions spent: 9 live questions (one earlier call was rejected with HTTP 422 for a wrong depth value and ran no question).

## Divergence point

- Not Think: no entity, nine of nine times. `core/graph.py` line 6426 builds the same topic plan every time.
- Not retrieval: identical five records in nine runs. The PubMed set variation of board card 11 did not occur here.
- Not the tools or timing: identical tools, 10 to 17 seconds.
- It is the Write step, in two places:
  - The Synth model call (`core/graph.py` around line 12030, prompt built by `build_synth_messages` in `synthesis/findings.py`, topic line `TOPIC_ANSWER_DIRECTIVE` at about line 1909) chooses which abstract sentences to report. It picks different ones each run.
  - The grounding pass (`synthesis/grounding.py`, kept-sentence rules around lines 1425 to 1460) then strips whatever does not ground. In runs 6, 8 and 9 every model sentence was stripped, which is the fallback to "not yet confirmed".

Evidence that the disease name lives in one sentence only:

- The title of PMID 39042260 is "Molecular analyses of MEFV gene mutation variants in Turkish population". It has no disease name.
- The name "Familial Mediterranean fever (FMF)" appears only in the first sentence of that abstract (BACKGROUND). The next sentences say "MEFV variants", "FMF variant" and "R202Q".
- Runs 2 and 4 used the first sentence and passed. Runs 1 and 5 used a later or rewritten sentence, "This ... disease", with the name left out. Runs 3 and 7 led with a different paper (G6PD). Runs 6, 8, 9 grounded nothing.
- Run 1 wrote "This autosomal recessive disease..." right after a sentence about MEFV analysis, which survived. The bare-pronoun rule (`_opens_on_bare_pronoun`, `synthesis/grounding.py` line 1642) only catches "It", "They", or "This/These" followed by a linking verb. "This disease is" and "This autosomal recessive disease is" pass it, so a sentence with no antecedent on the page is shown.

## Root cause

- The answer is built from free choice among abstract sentences, and nothing in the product checks that the answer covers the entity the retrieved papers are mostly about. The disease name sits in a single sentence the model may skip, and the checks after it only remove ungrounded text; they never ask "does the answer name the subject of the evidence?".
- The topic directive tells the model to answer the question from what the papers report, but gives it no instruction to name the condition or gene the papers study. Model output varies run to run, so the answer varies.
- A second, smaller gap: the pronoun rule misses "This <noun> is", so a disease-less sentence can survive.
- A third: when all model sentences are stripped (3 of 9), the topic path falls to a bare count with `ask`, rather than the code-built sentence listing that other paths use. Whether that listing is reachable on the topic path was not traced.

## Fix options

All three are answer-path changes. None hardcodes the question, a disease name or a word list. The golden run must hold at least 101 of 150 before and after, and each needs five or more repeated live runs of this question to prove it.

| Option | What changes | Risk |
|---|---|---|
| A. Directive line | Add to `TOPIC_ANSWER_DIRECTIVE` (`synthesis/findings.py` about line 1909): when the papers study a named condition or gene, the first sentence names it, each name taken from the findings. | Low code risk. A prompt line is a nudge, not a guarantee; the earlier note in the same file says directives that constrain form failed before. Measure, do not assume. |
| B. Classifier decision plus code check | Add a Write-side decision (a classifier model call, in the style of `think.asks_features`) that asks "do the retrieved papers center on a named condition or gene, and which?", then code verifies the answer names it and the name occurs in the findings; if not, re-ask once with the missing name, as the existing completeness repair does. | Medium. One more cheap call, around a second, against the 20 second ceiling. Matches the rule that decisions belong to a classifier and code only verifies. |
| C. Pronoun rule | Extend the bare-pronoun check so "This/These <noun> ..." counts when its antecedent did not survive. | Low. Fixes the nameless-disease sentence but not the omission itself. It would turn some run 1 and 5 style answers into dropped sentences, so alone it makes more empty answers. Use only with A or B. |

## Recommendation

- Do B, with A as its cheap first half. The classifier names what the papers centre on, and code only confirms that name is in the findings and in the answer. This follows the project rule (decisions to a classifier, code verifies) and uses the existing completeness-repair pattern, so one retry is already budgeted in the Write step.
- Add C only after B, so tightening the pronoun rule does not raise the 3 of 9 empty answers.
- Separately, look at why runs 6, 8 and 9 grounded nothing and fell to a bare count. That is the worst outcome the person sees, and it was a third of these runs.
- Acceptance: at least five live runs of this question with FMF named in every one, query 73 coffee and Ashkenazi still passing, golden at 101 of 150 or more.

## Confidence

- High: retrieval and Think are not the cause (nine of nine identical, every record set the same).
- High: the disease name occurs in one abstract sentence only (checked against the PubMed abstract text).
- Medium: the exact reason each run dropped the name. The stream shows only text after grounding, not the model's draft, so I could not see which draft sentences the grounding pass stripped in runs 5, 6, 8 and 9. Option B's retry would hide this; a one-off look at the pre-grounding draft would settle it.
- Medium: the three-way split of failure types is based on nine runs; rates will move with more.

## Not covered

- The model draft before grounding (no event carries it), so "model skipped the sentence" versus "grounding stripped it" is inferred, not seen.
- Why the topic path falls to a bare count with `ask` when everything is stripped.
- The Researcher depth and the other two plain-language topic questions (coffee, Ashkenazi) for the same variation.
- Whether the golden run holds under any of the fixes (nothing was built or run).
- Card 90's other six skip-manager questions; only the Mediterranean one was run.
- No source code was read beyond the Write step excerpts cited above.
