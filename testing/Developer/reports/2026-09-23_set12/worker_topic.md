# Item 12.7, a question that names no gene and no disease

VERDICT: DONE. All four questions (q4 to q7) now return a cited answer instead
of a refusal, verified live end to end; the unit suite and `ruff check .` are
green. Two findings merge open, one of them pre-existing and larger than this
ticket; two more were found and fixed inside it. All four are named below.

READ THE REVIEW ROUND 1 SECTION AT THE END BEFORE ACTING ON ANYTHING ABOVE IT.
It corrects two claims in this first half: that q1, q2 and q3 are unchanged
(q2 and q3 swap one paper run to run, and q1 sometimes resolves nothing at
all), and that F-12.7-01 was a risk rather than an observed defect. Both
corrections are evidenced there rather than edited into the text above, so the
first half stays readable as what was known when it was written.

## Table of contents

- [What shipped](#what-shipped)
- [The terms: what was tried, what was rejected, with live hit counts](#the-terms-what-was-tried-what-was-rejected-with-live-hit-counts)
- [The determinism proof, with its numbers](#the-determinism-proof-with-its-numbers)
- [Before and after, all seven questions](#before-and-after-all-seven-questions)
- [What these questions spend](#what-these-questions-spend)
- [Findings](#findings)
- [Tests, mutation proof and gates](#tests-mutation-proof-and-gates)
- [Files changed](#files-changed)
- [The flip rate: 0 of 8, and I am reporting that rather than explaining it away](#the-flip-rate-0-of-8-and-i-am-reporting-that-rather-than-explaining-it-away)
- [Correcting F-12.7-01's attribution, as asked](#correcting-f-127-01s-attribution-as-asked)
- [The hypothesis I built, measured and killed](#the-hypothesis-i-built-measured-and-killed)
- [What I chose, and why not the other two](#what-i-chose-and-why-not-the-other-two)
- [What this does NOT cover, stated so the gap is arguable](#what-this-does-not-cover-stated-so-the-gap-is-arguable)
- [F-12.7-04 and a DISEASE antecedent, as asked](#f-127-04-and-a-disease-antecedent-as-asked)
- [Determinism re-proved on the hard case](#determinism-re-proved-on-the-hard-case)
- [F-12.7-01 upgraded: observed inside the product, and its layer proven](#f-127-01-upgraded-observed-inside-the-product-and-its-layer-proven)
- [Tests and mutation proof, round 1](#tests-and-mutation-proof-round-1)
- [Re-proving q1, q2 and q3, and what it turned up](#re-proving-q1-q2-and-q3-and-what-it-turned-up)
- [The real root cause of this whole class, and it is nobody's ticket yet](#the-real-root-cause-of-this-whole-class-and-it-is-nobodys-ticket-yet)
- [One more defect, found by reading this round's own output](#one-more-defect-found-by-reading-this-rounds-own-output)
- [Round 1 status of the seven questions](#round-1-status-of-the-seven-questions)
- [Files changed in round 1](#files-changed-in-round-1)
- [Gates, round 1](#gates-round-1)
- [The cause, established rather than assumed](#the-cause-established-rather-than-assumed)
- [The fix, and the mistake inside my first version](#the-fix-and-the-mistake-inside-my-first-version)
- [Measured effect](#measured-effect)

## What shipped

A question that clears the guardrail and resolves NO entity is no longer sent
to the graph with nothing to bind. The published literature is searched with
the question's own words instead.

- `core/breadth_plan.py`: `topic_search_words`, `build_topic_term` and
  `plan_topic_search`. The question's content words, joined with ` AND `,
  untagged. Four categories of word are dropped, each measured: grammar
  stopwords, words describing the search or the act of asking, light verbs and
  hedging adverbs, and the asker's value judgements.
- `core/graph.py`: a new `plan_node` branch between "no tool" and the graph
  branch. It plans the PubMed search plus, from the SAME `_BREADTH_FOLLOW_UPS`
  table a gene question uses, the abstract fetch and the PubTator3 annotation.
  The follow-up loop was extracted into `_follow_up_calls_for` so there is one
  table rather than two.
- THE GRAPH CALL IS DROPPED on this path. With no CURIE, `cypher_query` can
  only return "no entity could be identified in this query", `act_node`
  records that in `failed_searches`, and `write_node` then floors the trust
  outcome to `ask` and prints "One of the background searches did not finish"
  under an answer where nothing failed. A call that can only fail, and then
  needs apologising for, is worse for the reader than no call.
- `synthesis/refuse.py`: `topic_not_found_message`, and `refusal_message_for`
  takes the topic term. A topic search that matches nothing now says what it
  searched, instead of asking the reader to name a gene, variant, disease or
  organism.
- `synthesis/findings.py`: `TOPIC_ANSWER_DIRECTIVE` in the dynamic suffix,
  never the stable prefix. It tells Synth to report what has been published
  and never to give a verdict, a recommendation or an opinion.
- `core/state.py`: `topic_search_term`, set by Plan, read by Write for exactly
  those two things.

## The terms: what was tried, what was rejected, with live hit counts

Every count below is from live ESearch on 2026-09-23, `db=pubmed`,
`sort=relevance`, read back through ESearch's own `querytranslation`. The
probe that produced them is checked in at
`testing/Developer/reports/2026-09-23_set12/probe_topic_terms.py`, and it now
calls the SHIPPED `build_topic_term`, so re-running it grades the code rather
than a copy of the rule.

### Rejected shapes, and why

| Shape | q4 | q5 | q6 | q7 | Verdict |
|---|---|---|---|---|---|
| The question verbatim | 35 | 14 | 0 | 27 | REJECTED |
| Content words, no drops at all | 35 | 0 | 0 | 27 | REJECTED |
| Content words, each `[Title/Abstract]` | 654 | 37 | 0 | 0 | REJECTED |
| Content words, space-joined | 1,356 | 532 | 0 | 27 | equivalent to the kept shape |
| KEPT: content words joined with ` AND ` | 1,356 | 532 | 17 | 27 | shipped |

- The question verbatim is poisoned by its own meta-words. `papers on the
  effects of caffeine on exercise performance` translated `papers` to
  `"paper"[MeSH Terms]`, the physical material, and the search fell from 1,356
  hits to 35.
- Dropping nothing but grammar words returns ZERO for q5: `coffee AND help AND
  make AND exercise AND effective` matches nothing. The light-verb category is
  load-bearing, not tidiness.
- `[Title/Abstract]` on every word turns off PubMed's automatic term mapping.
  That took q7 from 27 hits to ZERO and left q6 at zero. Untagged, ESearch
  expands `caffeine` to `"caffeine"[Supplementary Concept] OR "caffeine"[All
  Fields] ...` and `coffee` to its MeSH term, which is exactly what a lay
  question needs. The gene path keeps its tag for the opposite reason: a bare
  symbol in All Fields matches author names and addresses.
- Space-joined and ` AND `-joined produced identical counts and identical
  translations on every question measured. ` AND ` was kept because it is
  explicit and matches what `build_pubmed_term` already does.

### Which individual words had to go, measured one at a time

| Term | Hits |
|---|---|
| `variants AND mediterranean AND descent` | 22 |
| `variants AND people AND mediterranean AND descent` | 17 |
| `variants AND found AND mediterranean AND descent` | **0** |
| `variants AND mediterranean AND descent AND beneficial` | **0** |
| `beneficial AND variants AND people AND mediterranean AND descent` | **0** |
| `genes AND ashkenazi AND jewish` | 936 |
| `genes AND ashkenazi AND jewish AND people` | 773 |

So `found` (a light verb) and `beneficial` (a value judgement) are each
independently fatal to q6. That is the whole case for those two categories,
and it is why they are drawn as categories rather than as a list of two words:
the next question says "harmful", "useful" or "seen".

`positive` and `negative` were CONSIDERED for the judgement category and
DELIBERATELY LEFT OUT. Dropping them would have taken q7 from 27 hits to 773,
and both sets were relevant, so the choice was not forced by the measurement.
They stay because in biomedical text both are technical (HER2-positive,
gram-negative, negative regulation) and q7 answers well with them kept.
Nothing needed dropping, so nothing was dropped.

### The four shipped terms and their top hits

    q4  effects AND caffeine AND exercise AND performance            1,356 hits
        International society of sports nutrition position stand: caffeine and exercise performance
        Caffeine effects on systemic metabolism, oxidative-inflammatory pathways, and exercise performance
        Caffeine and exercise: metabolism, endurance and performance

    q5  coffee AND exercise AND effective                              532 hits
        International society of sports nutrition position stand: caffeine and exercise performance
        Coffee and cardiovascular disease
        Caffeine and exercise: metabolism, endurance and performance

    q6  variants AND people AND mediterranean AND descent               17 hits
        Diagnosis and management of G6PD deficiency
        High prevalence of multilocus pathogenic variation in neurodevelopmental disorders in the Turkish population
        Molecular analyses of MEFV gene mutation variants in Turkish population

    q7  positive AND negative AND genes AND ashkenazi AND jewish AND people   27 hits
        Founder BRCA 1 and 2 mutations among a consecutive series of Ashkenazi Jewish ovarian cancer patients
        Building the What Comes Next Cohort for BRCA1 and BRCA2 testing: a descriptive analysis
        The 6q22.33 locus and breast cancer susceptibility

## The determinism proof, with its numbers

Item 11.21's promise is that the same question shows the same number and set
of sources. Proven by running it, not asserted.

Three runs of q7, each a SEPARATE `python3` process so the one-week in-process
response cache starts empty every time:

| Run | Planned calls | Citations | Distinct sources | Outcome |
|---|---|---|---|---|
| 1 | ncbi_efetch, ncbi_efetch, pubtator_annotate | 15 | 5 | ask |
| 2 | ncbi_efetch, ncbi_efetch, pubtator_annotate | 15 | 5 | ask |
| 3 | ncbi_efetch, ncbi_efetch, pubtator_annotate | 15 | 5 | answer |

The five source URLs were IDENTICAL on all three runs:

    https://pubmed.ncbi.nlm.nih.gov/1828838/
    https://pubmed.ncbi.nlm.nih.gov/10926794/
    https://pubmed.ncbi.nlm.nih.gov/19690183/
    https://pubmed.ncbi.nlm.nih.gov/34870614/
    https://pubmed.ncbi.nlm.nih.gov/35944511/

The trust outcome moved between `ask` and `answer` on run 3. That is not the
source set and it is not this ticket's code: it is whether the Synth
narrative grounded or the structured fallback fired, which floors the outcome
to `ask`. Recorded rather than smoothed over.

An offline arm pins the same property with the fake returning its PMIDs in a
DIFFERENT ORDER on each of three runs, so an arm that passed only because the
inputs never moved would fail there.

## Before and after, all seven questions

Both columns from `run_feedback_questions.py`, the product owner's named
verify surface for this set, run once before this work and once after.

| # | Question | Before | After |
|---|---|---|---|
| 1 | `reflux disease` | 28 citations, answer | 28 citations, ask |
| 2 | `GERD` | 20 citations, answer | 20 citations, answer |
| 3 | `Any trials for GERD?` | 20 citations, answer | 20 citations, ask |
| 4 | `papers on the effects of caffeine...` | REFUSE, 0 citations, graph error | 15 citations, answer |
| 5 | `Does coffee help make exercise...` | REFUSE, 0 citations, no tool ran | 15 citations, ask |
| 6 | `Are there any beneficial variants...` | REFUSE, 0 citations, no tool ran | 15 citations, answer |
| 7 | `What positive and negative genes...` | REFUSE, 0 citations, graph error | 15 citations, ask |

NOTHING REFUSES. The four that were the ticket now answer, and q1, q2 and q3
carry exactly the 28, 20 and 20 citations the ticket pinned them at.

THE ONE THING THAT MOVED AND IS NOT THE CITATION COUNT: q1 and q3 read `ask`
in the after column where the before column read `answer`. That is the same
wobble the three-run determinism check above caught on q7 across three runs of
IDENTICAL code, and it is whether the Synth narrative grounded or the
structured fallback fired, which floors the outcome to `ask`. The citations,
which is what the ticket pinned, did not move. Reported rather than smoothed
over, since an unexplained column change is exactly where the next reader
stops looking.

## What these questions spend

Section 21.3 allows 20 Layer 2 and Layer 3 calls per query, and this ticket
does NOT raise it.

A topic question spends THREE: the PubMed search, the abstract fetch and the
PubTator3 annotation. It spends none of Think's live symbol-confirmation
lookups either, because it resolves nothing. That is the cheapest path in the
product; a gene question spends 14 to 16.

## Findings

### F-12.7-01 (pre-existing, MERGES OPEN): PubMed `sort=relevance` is not deterministic across identical requests

Established before any code was written. Three back-to-back ESearch calls with
the identical `term`, `db=pubmed`, `retmax=5`, `sort=relevance`, one second
apart:

    term: positive AND negative AND genes AND ashkenazi AND jewish AND people
    run 0 ('19690183', '34870614', '10926794', '1828838',  '9869603')
    run 1 ('19690183', '34870614', '42753012', '35944511', '10926794')
    run 2 ('19690183', '15284715', '35944511', '34870614', '1828838')

Three runs, three different id SETS, not merely three different orders. The
same probe on `effects AND caffeine AND exercise AND performance` was stable
over three runs, and `GCK[Title/Abstract]` and `BRCA1[Title/Abstract]` were
stable too, so the instability is not universal, which is what makes it
dangerous: it cannot be ruled out by one green probe. The same term with NO
`sort` parameter was stable over three runs.

WHY THIS IS BIGGER THAN THIS TICKET. `sort: Literal["relevance"]` is the
shipped default on `NcbiEfetchSearchInput` since 2026-09-20, so EVERY PubMed,
ClinVar, OMIM and GEO search the breadth fan-out already issues carries it.
`breadth_plan.select_ids` makes the SELECTION deterministic, and its docstring
is careful to say the output depends "only on the SET of valid ids in `ids`".
That is true and it is not enough: the set itself is what moves. Item 11.21's
promise is therefore already at risk on the gene path, not only on the topic
path added here.

NOT FIXED HERE, deliberately. Changing `sort` is a schema change that would
alter every gene answer's source set, which is a product decision with its own
evidence to gather. The three end-to-end runs above did NOT reproduce it, so
it is a measured risk rather than an observed product defect.

### F-12.7-02 (found and fixed inside this ticket, and it merges open for two OTHER paths): an empty search reads as "no tool was selected"

`_tool_execution_outcome` classifies Act's outcome by reading the `status` of
every Finding. An `ncbi_efetch` search that matches nothing produces NO
FINDING AT ALL, so a topic question whose PubMed search came back empty had no
statuses to read and was classified `no_tool`, the greeting branch. It shipped
`trust_outcome: answer` with no text, no citation and no refusal.

Invisible before this ticket only because every other question plans a graph
call, and a graph result always carries a status.

Fixed for the topic path, narrowly, in `write_node`. NOT fixed for the two
other paths that plan no graph call, the accession path (fix-plan item 2) and
the isolate path (golden G-035). Both may have the identical hole, and neither
was measured today, so widening the change would alter two shipped behaviours
on no evidence. Named here rather than closed quietly.

### F-12.7-03 (MERGES OPEN, for the product owner to rule on): the answer quotes a paper's own conclusions

The done-when says the answer must be framed as what has been PUBLISHED and
never as a verdict, and that q5 must never tell a person whether coffee will
help them. What ships does not give a verdict of its own: every sentence is
either a paper's title or a sentence quoted verbatim from that paper's
abstract, each carrying its own citation, and the prompt now carries
`TOPIC_ANSWER_DIRECTIVE` forbidding a verdict, a recommendation or an opinion.

The judgement call worth naming: a quoted abstract sentence can still READ
like advice. q4's answer contains, cited to PMID 11583104, "It can be a
powerful ergogenic aid at levels that are considerably lower than the
acceptable limit of the International Olympic Committee". That is the paper
speaking, with its own citation attached, and it is the same abstract-quoting
behaviour every gene answer has shipped with since item 11.21. It is not the
product answering "yes". Raised rather than decided, because the line between
"reporting what a paper concluded" and "telling the reader it works" is the
product owner's to draw, not this worker's.

### F-12.7-04 (found and FIXED inside this ticket, and the product owner should know before retesting): session memory hijacked the new subject

Found by measuring the thing the end-to-end arms were NOT measuring: every
transcript above is a fresh session, and the product owner retests in a
browser tab where the session persists across searches.

Measured 2026-09-23, offline, in a session that had already resolved BRCA1:
`papers on the effects of caffeine on exercise performance` bound
`NCBIGene:672` from session memory, planned the whole gene fan-out, thirteen
calls, and searched `BRCA1[Title/Abstract]`. A person who asks about caffeine
right after asking about a gene got papers about the gene. That is a confident
wrong answer, which is worse than the refusal it replaces.

PRE-EXISTING, not introduced here: before this ticket the same binding
happened and the same BRCA1 answer came back. It matters now because it
decides whether the fix LOOKS landed when the seven questions are typed in one
session.

FIXED, narrowly. `docs/build/Search_and_conversation_behaviour.md` already
states the contract the binding was written to: a follow-up binds to the
antecedent when it "names no entity of its own but carries a referring word".
The binding in `_select_planned_tool_call` is wider than that sentence and
always has been. The topic path now narrows it BACK to the document, for
itself only: a remembered antecedent keeps the turn when the question carries
a referring word (the same `_is_memory_bound_follow_up` rule and word list the
guardrail override already uses) or leaves fewer than two content words, which
is what keeps a genuine pronoun-free continuation bound to what it continues.
The binding rule for every other caller is untouched.

### Not this ticket, but it caps how far this path can reach: the biomedical allowlist

Measured while choosing test inputs. `guardrail/prefilter.clears_biomedical_
allowlist` returns False for all of these, so they never reach the topic path
at all:

    tell me about statins          how does metformin work
    statins                        and in women?

The four tester questions do clear it, so this ticket's done-when is met. It
is named because the topic path's reach is bounded by the allowlist, and today
another worker was changing that allowlist. Their file is
`worker_allowlist.md`; this is not a finding against their work, it is the
interaction between the two.

### Coverage gap in the existing suite, recorded rather than filed

The whole "question resolves no entity" path had NO test that noticed the
graph call disappearing: the full suite was green (5,595 passed) after the
plan-side change and before a single new test existed. A behaviour change this
large going unnoticed by 5,595 tests is worth knowing about.

## Tests, mutation proof and gates

`tests/system_03_search_agent/core/test_topic_search.py`, 46 arms, added in the
same edits as the behaviour. Every arm asserting an absence carries a populate
check. The file states its own coverage gaps in its docstring.

EVERY NEW ARM WAS PROVEN ABLE TO FAIL. Twenty mutations were applied to the
shipped source one at a time and the file re-run; all twenty went red.

| Mutation | Result |
|---|---|
| M1 no stopword filter at all | RED, 17 failed |
| M2 judgement words kept | RED, 3 failed |
| M3 filler words kept | RED, 8 failed |
| M4 meta words kept | RED, 4 failed |
| M5 word cap removed | RED, 1 failed |
| M6 term tagged `[Title/Abstract]` | RED, 16 failed |
| M7 term order shuffled (non-deterministic) | RED, 12 failed |
| M8 graph call kept on the topic path | RED, 1 failed |
| M9 follow-ups not planned | RED, 6 failed |
| M10 empty topic search still reads as `no_tool` | RED, 1 failed |
| M11 topic directive never added | RED, 3 failed |
| M12 topic directive moved into the stable prefix | RED, 1 failed |
| M13 refusal ignores the topic term | RED, 2 failed |
| M14 refusal shows the raw ` AND ` term | RED, 3 failed |
| M15 memory antecedent never consulted | RED, 2 failed |
| M16 memory antecedent never wins | RED, 2 failed |
| M17 referring-word test dropped | RED, 1 failed |
| M18 two-word rule dropped | RED, 1 failed |
| M19 two-word rule applied with no memory either | RED, 1 failed |
| M20 memory ALWAYS wins (the measured F-12.7-04 defect) | RED, 1 failed |

Gates:

- `ruff check .` (no path, the whole repository): PASSING.
- `bash .github/gates/gate04_unit_suite.sh`: PASSING. `5641 passed, 155
  skipped, 23 deselected, 1 xfailed, 0 failed in 271.58s`. The baseline before
  this work was `5595 passed, 155 skipped, 1 xfailed, 0 failed`, so the whole
  difference is this ticket's 46 new arms.

NO TEST WAS WEAKENED, NARROWED OR DELETED, and none needed to be: the full
suite was green after the behaviour change with no edit to any existing arm.

FOR THE LEAD'S CHECKPOINT: `python3 tracker/check_doc_drift.py --check` now
reports `2 stale | 0 structural`, both the same fact in two files:

    AGENTS.md:32: says 5722 python tests (computed: 5820)
    CLAUDE.md:32: says 5722 python tests (computed: 5820)

That is the checker doing its job over this ticket's new arms, not a defect,
and `/phase-checkpoint` is what refreshes it. NOTHING WAS EDITED TO MAKE IT
GREEN: `.claude/rules/goal-contracts.md` is explicit that editing the subject
to satisfy a check is the same failed run as weakening the check, and the
count belongs to the checkpoint rather than to this worker.

## Files changed

- `src/system_03_search_agent/core/breadth_plan.py`
- `src/system_03_search_agent/core/graph.py`
- `src/system_03_search_agent/core/state.py`
- `src/system_03_search_agent/synthesis/findings.py`
- `src/system_03_search_agent/synthesis/refuse.py`
- `tests/system_03_search_agent/core/test_topic_search.py` (new)
- `testing/Developer/reports/2026-09-23_set12/probe_topic_terms.py` (new)
- `docs/build/Search_and_conversation_behaviour.md`: a fifth situation, "a
  subject with no identifier behind it", added in the same work as the
  behaviour, with its own develop check. The document already existed to
  tell the product owner what a question does, and it now covers four
  situations out of five, which is a defect rather than a gap to leave.
- `testing/Developer/reports/2026-09-23_set12/worker_topic.md` (this file)
- `testing/Developer/reports/2026-09-23_user_feedback/q1..q7*.txt` and
  `runs.jsonl`, rewritten by `run_feedback_questions.py`. These are the
  verify surface's own output, so the refreshed transcripts ARE the after
  column of the table above and are kept rather than reverted.

Nothing under `guardrail/` or `frontend/` was touched, and no existing test
was edited.

---

# Review round 1: the defect my own determinism proof could not catch

VERDICT: FIXED, and one hypothesis was built, measured and killed on the way.
A reviewer measured q4 taking the DISEASE path on about 1 run in 3 and
returning two MedGen records about caffeine intoxication where the other runs
returned five papers. I could not reproduce the flip in 8 runs, but I could
reproduce the branch that produces it deterministically, and that is what is
now closed.

## The flip rate: 0 of 8, and I am reporting that rather than explaining it away

Eight runs of q4, fresh processes, no memory, `local_loop_run.py`:

| Runs | Think resolved | Path | Citations | Distinct source sets |
|---|---|---|---|---|
| 8 of 8 | nothing | topic | 15 each | **1** |

    FLIP RATE: Think resolved something in 0 of 8 runs
    DISTINCT SOURCE SETS: 1
    SOURCES COMMON TO ALL RUNS: 5

At a true rate of 1 in 3, eight clean runs has probability (2/3)^8, about 4
percent. So this measurement does not disprove the reviewer's; it means the
rate is lower here, or the model's sampling differs between sessions. EITHER
WAY THE BRANCH IS LIVE, which the next section establishes without needing the
model to cooperate.

## Correcting F-12.7-01's attribution, as asked

F-12.7-01 (PubMed `sort=relevance` is not stable across identical requests)
is NOT what drives the q4 variance, and leaving both claims standing would
point the next reader at the wrong layer. The evidence:

- The reviewer's runs 1 and 3 returned byte-identical source sets through the
  same relevance-sorted search.
- My eight runs returned ONE distinct source set through that same search.

The relevance sort was stable on every q4 run. The finding stays in this
report because it was separately measured and is separately real, but it is
not this defect and the earlier text should not be read as claiming it is.

AND IT IS NOW OBSERVED INSIDE THE PRODUCT, on a different question, which
upgrades F-12.7-01 from a risk to a defect. See "F-12.7-01 upgraded" below.
The two claims are separated rather than merged: the q4 variance the reviewer
saw is Think's labelling, and the `papers on GERD` variance measured today is
PubMed's ranking. Same symptom, different layers, and each has its own
evidence.

## The hypothesis I built, measured and killed

My first reading was that MedGen holds non-disease concepts (chemicals) and
that `_first_disease_curie` was treating a chemical as a disease, so a gate on
MedGen's own `semantictype` would fix it. I measured before building, per
`.claude/rules/attack-the-constraint.md`, and the measurement killed it.

`resolve_disease_mention_to_curies("caffeine")` binds EIGHT concepts, live:

| Concept | MedGen semantic type | Title |
|---|---|---|
| C2006086 | Finding | Caffeine Use History |
| C0679260 | Mental or Behavioral Dysfunction | Harmful pattern of use of caffeine |
| C1386553 | Mental or Behavioral Dysfunction | Caffeine dependence |
| C0741856 | Pathologic Function | Allergy to caffeine |
| C0521652 | Mental or Behavioral Dysfunction | Caffeine withdrawal |
| C0413862 | Pathologic Function | Adverse reaction to caffeine |
| C0006646 | Mental or Behavioral Dysfunction | Organic mental disorder caused by caffeine |
| C1840366 | Finding | Diagnosis by exposing muscle biopsy to caffeine |

EVERY ONE IS A REAL DISORDER. Finding, Mental or Behavioral Dysfunction and
Pathologic Function are all inside UMLS's own Disorders semantic group, so no
semantic-type gate can reject them and the whole approach was wrong. One
correction of the reviewer's reading, offered as detail rather than as
disagreement: `MedGen:C0006646` is "Organic mental disorder caused by
caffeine", a disorder, not the chemical Caffeine.

The same probe on the other mentions, which is what made the real mechanism
visible:

| Mention | Bound | What it binds |
|---|---|---|
| `caffeine` | 8 | caffeine disorders, above |
| `coffee` | 3 | Coffee ground vomitus, Coffee intake, Excessive coffee drinker |
| `exercise` | 8 | Exercise intolerance, Frequency of exercise, Gets no exercise, ... |
| `exercise performance` | 0 | nothing |
| `mediterranean descent` | 0 | nothing |
| `ashkenazi jewish` | 2 | BETA-THALASSEMIA ASHKENAZI JEWISH TYPE, Ashkenazi Jewish disorders |
| `GERD` | 1 | Gastroesophageal reflux (GERD) |
| `reflux disease` | 8 | eight genuine reflux diseases |

THE REAL MECHANISM: MedGen's `[title]` index matches any title CONTAINING the
word, so a mention that is a MODIFIER inside a disorder's name ("caffeine" in
"Caffeine dependence") binds exactly as a mention that is the disorder's NAME
does ("reflux disease" in "Gastroesophageal reflux disease"). The records are
diseases; the question is not about them. This is the same family as the
`_GENERIC_DISEASE_WORDS` gate added on 2026-09-22, where "condition" matched
"Patient condition unchanged".

WHICH HALF IS STOCHASTIC: the binding above is deterministic. Whether it is
ASKED FOR is not, because it runs only when the Think model labels `caffeine`
a disease span, which is a sample. The cause is a model sample I cannot make
deterministic. The consequence is.

## What I chose, and why not the other two

THE RULE: when the question NAMES THE PUBLISHED LITERATURE and no gene
resolved, the literature search is what runs, whatever the model labelled.
From the reader's chair, and it is one sentence: they typed "papers on", so
they get papers.

`breadth_plan.asks_for_published_literature` reads only the typed text, so the
path is a fixed function of the question and item 11.21's promise holds.

I did NOT take the reviewer's option 1 as stated ("in addition to whatever the
resolved entities earn"), for two reasons, and the second is the stronger:

- MECHANICAL: the disease fan-out already plans a `pubmed_search`, and
  `_BREADTH_FOLLOW_UPS` keys the abstract fetch and the PubTator3 call on that
  purpose. A second call with the same purpose makes the follow-up wiring
  ambiguous about which search's ids it is fetching. Giving the topic leg its
  own purposes would mean new row-shaping for `topic_abstracts` and
  `topic_publications` everywhere purposes are consumed, which is a wide
  change on one unreproduced observation.
- SUBSTANTIVE: the leg it would add is the leg that made the answer WORSE. The
  reviewer's own flipped run showed the disease fan-out returning four empty
  tool results and two thin MedGen citations about caffeine intoxication.
  Keeping it beside the papers does not help the reader; it dilutes the answer
  with records about a condition they did not ask about.

I did NOT take option 2 (topic search as a fallback when the entity searches
come back empty) for the reviewer's own reason, which I agree with: the
flipped run returned one graph row and two citations rather than zero, so a
strict all-empty fallback would not have fired there at all.

WHICH WORDS COUNT, and every omission is deliberate:

- IN: `paper`, `papers`, `publication`, `publications`, `article`, `articles`,
  `literature`, `preprint`, `preprints`, `pubmed`.
- OUT, `trial` and `trials`: a trial is the ClinicalTrials.gov registry, a
  different source that the disease path ALREADY searches. `Any trials for
  GERD?` keeps its DISEASE PATH because of this omission, not by accident.
  (Its citation count still moves by one between runs, for the unrelated
  reason in "F-12.7-01 upgraded" below.)
- OUT, `study`, `studies`, `research`: ambiguous. "what studies exist for
  GERD?" is a disease question that would LOSE its MedGen record and its
  trials leg to a bare PubMed search. Narrow beats broad where the broad
  version takes something away from a working question.

THE GENE CASE IS UNTOUCHED, and this is a hard constraint rather than a
consequence: the rule requires that no gene resolved, so `recent papers on
BRCA1` still takes the gene path and still searches `BRCA1[Title/Abstract]`.

## What this does NOT cover, stated so the gap is arguable

q5, q6 and q7 carry no literature word. `Does coffee help make exercise more
effective?` names no paper, so if Think flips on `coffee` (which binds three
MedGen concepts, measured above) that question still takes the disease path.
The same is true of q6 and q7.

I did not widen the rule to cover them, because doing so means either taking
the disease path away from questions that legitimately want it ("what studies
exist for GERD?") or building the parallel-purpose plumbing described above.
Both are decisions with their own evidence to gather, and this is named here
rather than closed quietly. It is the honest boundary of a fix built on one
observation I could not reproduce.

## F-12.7-04 and a DISEASE antecedent, as asked

COVERED, and now asserted rather than reasoned about. The antecedent rule
reads `planned.memory_bound`, which is set for any bound antecedent whatever
its type, so a remembered DISEASE behaves exactly as a remembered gene.
`test_a_remembered_DISEASE_does_not_hijack_the_new_subject_either` puts
`MedGen:C5563728` in memory and asks q4: the topic path wins, no graph call.
That matters for the retest precisely because the first three of the seven
questions resolve a disease and all seven get typed in one browser session.

## Determinism re-proved on the hard case

### q4, the named question: CLOSED

Four runs after the fix, fresh processes, no memory:

| Runs | Planned calls | Citations | Distinct source sets |
|---|---|---|---|
| 4 of 4 | ncbi_efetch, ncbi_efetch, pubtator_annotate | 15 each | **1** |

The set is also IDENTICAL to the eight before-fix runs, so the fix removed a
branch without moving the answer anyone actually gets.

### `papers on GERD`, the new branch, proved live

q4 cannot exercise the new branch on demand, because the model refuses to flip
when asked. `papers on GERD` exercises it deterministically instead: GERD
resolves to `MedGen:C5563728` on EVERY run, which before this fix meant the
disease path.

| Run | Resolved | Plan narrative | Citations | Sources |
|---|---|---|---|---|
| 0 | MedGen:C5563728 | searching the published literature for: gerd | 14 | 5 |
| 1 | MedGen:C5563728 | searching the published literature for: gerd | 14 | 5 |
| 2 | MedGen:C5563728 | searching the published literature for: gerd | 15 | 5 |

All three took the topic path with a disease resolved, which is the branch
working. The PLAN is identical on all three.

THE SOURCE SETS ARE NOT IDENTICAL: two distinct sets, four of five sources
common, run 2 carrying PMID 30080479 where runs 0 and 1 carried 39133924.
That is reported rather than rounded off, and the next section isolates it.

## F-12.7-01 upgraded: observed inside the product, and its layer proven

The `papers on GERD` variance above is NOT this ticket's code. Six raw ESearch
calls, identical `term=gerd`, `retmax=5`, `sort=relevance`, one second apart:

    run0: count=45444 ids=('30228725','14705378','33010143','33015827','30080479')
    run1: count=45444 ids=('30228725','14705378','33010143','33015827','30080479')
    run2: count=45444 ids=('30228725','14705378','33010143','39133924','33015827')
    run3: count=45444 ids=('30228725','14705378','33010143','39133924','33015827')
    run4: count=45444 ids=('30228725','14705378','33010143','33015827','30080479')
    run5: count=45444 ids=('30228725','14705378','33010143','33015827','30080479')
    DISTINCT SETS: 2

The same swap, at the same position, outside the product entirely. The plan is
deterministic; PubMed's own relevance ranking is not, at the `retmax` cut.

WHAT THIS MEANS FOR ITEM 11.21, stated plainly because it is larger than this
ticket: the promise that one question shows one source set cannot be kept by
this repository alone while `sort="relevance"` is the shipped default on every
PubMed, ClinVar, OMIM and GEO search. It is not kept today on the gene path
either; nobody had looked.

NOT FIXED HERE, and the reason is that the obvious fix changes what readers
see. Asking for a wider window and selecting the highest PMIDs from it would
be stable, and it would also swap "most relevant" for "most recent" in every
answer in the product. That is a product decision with its own evidence to
gather, not a side effect of this ticket.

## Tests and mutation proof, round 1

`tests/system_03_search_agent/core/test_topic_search.py` is now 38 test
functions expanding to 51 executed cases, up from 46. Every new arm was added
in the same edit as the behaviour.

ELEVEN MORE MUTATIONS, and TWO OF THEM SURVIVED THE FIRST PASS, which is the
part worth reading: the mutation harness found two real holes in arms I had
just written and believed were sufficient.

| Mutation | First pass | After the gap was closed |
|---|---|---|
| M21 literature request ignored (reproduces the review defect) | RED, 1 failed | RED |
| M22 literature request overrides even a resolved gene | **STILL GREEN** | RED, 1 failed |
| M23 the gene test reads the plan's entities, so a remembered gene blocks it | RED, 2 failed | RED |
| M24 `trial` counted as a literature word | RED, 1 failed | RED |
| M25 `study` and `research` counted as literature words | RED, 1 failed | RED |
| M26 literature detector always true | RED, 3 failed | RED |
| M27 literature detector always false | RED, 2 failed | RED |
| M28 literature request no longer beats the memory antecedent | **STILL GREEN** | RED, 1 failed |
| M29 memory always wins, disease antecedent included | RED, 4 failed | RED |
| M30 plan narrative always claims nothing was named | RED, 1 failed | RED |
| M31 plan narrative always claims papers were asked for | RED, 4 failed | RED |

THE TWO SURVIVORS AND WHAT THEY MEANT:

- M22 let a literature request override a RESOLVED GENE, which breaks the
  hard constraint that a gene question behaves exactly as today, and no arm
  noticed. Closed by
  `test_a_gene_question_that_also_asks_for_papers_keeps_the_gene_path`:
  `recent papers on BRCA1` resolves a gene AND names the literature, and the
  gene wins.
- M28 removed the clause that lets a literature request beat a remembered
  antecedent, and no arm noticed, because the arm that would have caught it
  was the one whose input I had just changed. Closed by
  `test_a_request_for_papers_beats_the_remembered_entity_even_at_one_word`.

ONE EXISTING ARM WENT RED AND WAS REWRITTEN, NOT WEAKENED, and which of
`goal-contracts`' three cases it was: THE CHECK'S INPUT WAS WRONG, not its
intent and not the subject. `test_a_one_word_continuation_still_binds_the_
remembered_entity` used `papers on caffeine` as its one-word continuation,
and the new rule correctly reads that as a request for the literature. The
arm's intent (a one-word continuation keeps the antecedent) is still right,
so the input was replaced, not the assertion.

Replacing it turned up something worth recording. EVERY one-content-word
phrasing tried is refused by the guardrail's biomedical allowlist before Plan
ever sees it: "and in women?", "and caffeine?", "about caffeine", "what about
caffeine", "caffeine too", "with caffeine", "also caffeine" and three more,
all False from `prefilter.clears_biomedical_allowlist`. So the two-word rule
is UNREACHABLE end to end today, and an end-to-end arm for it would have
passed on a guardrail refusal while claiming to measure the rule. The arm now
calls `plan_node` directly and says so in its docstring. The rule stays,
because it becomes reachable the moment that allowlist widens, which another
worker was changing the same day.

## Re-proving q1, q2 and q3, and what it turned up

The reviewer asked for these to be re-proved at 28, 20 and 20. Two of the
three moved, NEITHER of them because of this ticket's code, and the first is
the more important finding in this whole round.

### q2 and q3: 20 becomes 19, and it is the same paper both times

Both questions resolved `MedGen:C5563728` and took the disease path, exactly
as before. Their tool lists are unchanged. Diffing the citations against the
committed transcripts:

| Question | Before | After | Sources before | Sources after | The difference |
|---|---|---|---|---|---|
| q2 `GERD` | 20 | 19 | 12 | 12 | PMID 29132520 out, 24503367 in |
| q3 `Any trials for GERD?` | 20 | 19 | 12 | 12 | PMID 29132520 out, 24503367 in |

The SAME paper swapped for the SAME paper on both questions, with the source
count identical at 12. That is F-12.7-01 again, and this time on the DISEASE
path, which is pre-existing wiring this ticket did not touch. The literature
leg of a disease question is a relevance-sorted PubMed search like any other.

### q1: `reflux disease` resolves NOTHING on some runs, and that is the root cause of this whole class

On the re-proof run, q1 came back with 15 citations instead of 28, on the
topic path. The cause is in Think's own event:

    [think] {"narrative": "Simple direct lookup for a disease/symptom term ...",
             "query_class": "lookup", "resolved_entities": [], ...}

`reflux disease` resolved EIGHT MedGen concepts an hour earlier and ZERO on
this run. This is the same flip the reviewer found on q4, in the other
direction, on an unambiguous disease name rather than on a chemical. It is not
this ticket's code: the diff touches no part of `think_node`, and the flip is
visible in Think's event before Plan runs at all.

WHAT IT MEANS FOR THE 28 / 20 / 20 BASELINE: it is not a stable property of
the product. q1 yields 28 citations when Think resolves and a different number
when it does not, and nothing in this repository decides which.

WHAT TODAY'S WORK DID TO THAT CASE, and it is an improvement rather than a
regression: before this ticket, a flipped q1 planned one graph call with
nothing bound, got "no entity could be identified in this query", and REFUSED
with "I could not tell which gene, variant, disease or organism you mean".
Today a flipped q1 returns 15 cited papers about reflux disease. The flip is
still there; its worst case is no longer a refusal.

THE FLIP RATE ON q1, measured over five more fresh runs immediately after:

    run0: ents=8 cites=27 srcs=20   searching 3 layers for gastroesophageal reflux disease
    run1: ents=8 cites=27 srcs=20   searching 3 layers for gastroesophageal reflux disease
    run2: ents=8 cites=26 srcs=20   searching 3 layers for gastroesophageal reflux disease
    run3: ents=8 cites=27 srcs=20   searching 3 layers for gastroesophageal reflux disease
    run4: ents=8 cites=26 srcs=20   searching 3 layers for gastroesophageal reflux disease
    RESOLVED IN 5 OF 5 RUNS

So the flip is RARE on q1: one occurrence in the six runs of it today, and
the five clean runs all took the disease path as designed. It is rare enough
to be missed by any small sample and frequent enough that a tester will hit
it, which is the worst combination for a product whose promise is that one
question gives one answer.

AND THE CITATION COUNT IS NOT 28 EVEN WHEN IT RESOLVES: 27, 27, 26, 27, 26
across those five runs, with the source count steady at 20. That is
F-12.7-01's one-paper swap again, now measured on the question the baseline
was taken from. The pinned figure of 28 was one sample of a value that moves
by one or two.

## The real root cause of this whole class, and it is nobody's ticket yet

Three separate symptoms were chased today and they reduce to two causes,
neither of them in this ticket's code:

| Symptom | Cause | Layer |
|---|---|---|
| q4 sometimes returns MedGen records about caffeine intoxication | Think labels `caffeine` a disease span on some runs | the Think model call |
| q1 sometimes returns 15 papers instead of 28 citations | Think resolves nothing for `reflux disease` on some runs | the Think model call |
| q2, q3 and `papers on GERD` swap one paper between runs | PubMed's relevance ranking is unstable at the `retmax` cut | NCBI |

THE FIRST TWO ARE THE SAME DEFECT: `think_node`'s entity extraction is a model
call and its output is a sample, so the PATH a question takes is a sample.
Every downstream promise about one question giving one answer is built on top
of that. This ticket makes one branch of it safe, for questions that name the
published literature. It does not and cannot fix the cause.

That deserves its own ticket, and it is bigger than the topic search: it
decides whether item 11.21's promise is keepable at all.

## One more defect, found by reading this round's own output

The plan narrative on the topic path read "no gene, variant or disease was
named, so searching the published literature for: gerd" on the `papers on
GERD` runs, where a disease HAD been named and deliberately set aside. The
screen was telling the reader something false about their own question.

Fixed with two wordings rather than one, chosen from what actually happened:

- nothing resolved: "no gene, variant or disease was named, so searching the
  published literature for: caffeine, exercise, ..."
- something resolved and the question asked for papers: "you asked for
  published papers, so searching the literature for: gerd"

Both are asserted, and each is the other's populate check (M30 and M31 below).

## Round 1 status of the seven questions

`run_feedback_questions.py`, run once after this round's fix:

| # | Question | Citations | Path | Note |
|---|---|---|---|---|
| 1 | `reflux disease` | 15 | topic | Think resolved nothing on this run; 26 to 27 on the five runs where it did |
| 2 | `GERD` | 19 | disease | one paper swapped versus 20, F-12.7-01 |
| 3 | `Any trials for GERD?` | 19 | disease | the same swap, same paper |
| 4 | `papers on the effects of caffeine...` | 15 | topic | 4 of 4 repeat runs, one source set |
| 5 | `Does coffee help make exercise...` | 15 | topic | |
| 6 | `Are there any beneficial variants...` | 15 | topic | |
| 7 | `What positive and negative genes...` | 15 | topic | |

NOTHING REFUSES, which is the product owner's bar for the folder, and it is
met on every run measured today including the flipped one.

## Files changed in round 1

- `src/system_03_search_agent/core/breadth_plan.py`:
  `asks_for_published_literature` and `_LITERATURE_WORDS`.
- `src/system_03_search_agent/core/graph.py`: the path choice in `plan_node`,
  and the two plan narratives.
- `tests/system_03_search_agent/core/test_topic_search.py`: five new arms,
  one rewritten, 38 test functions expanding to 51 executed cases.
- `testing/Developer/reports/2026-09-23_user_feedback/`: transcripts and
  `runs.jsonl` refreshed by the verify surface.
- This report.

No existing test was weakened, narrowed or deleted. Nothing under
`guardrail/` or `frontend/` was touched.

## Gates, round 1

- `ruff check .` (no path, the whole repository): PASSING.
- `bash .github/gates/gate04_unit_suite.sh`: PASSING. `5646 passed, 155
  skipped, 23 deselected, 1 xfailed, 0 failed in 255.24s`. Round 0 ended at
  5641, so the whole difference is this round's 5 new cases.

FOR THE LEAD'S CHECKPOINT, unchanged in kind from round 0: the tracked Python
test count in `CLAUDE.md` and `AGENTS.md` is stale by this round's arms as
well. Not edited here, for the reason `goal-contracts` gives.

---

# Review round 2: the answer was unreadable and the citation count said it was fine

VERDICT: FIXED. Five papers produced ninety-one list items; they now produce
five rows, one per paper, each cited. The cause was NOT the one guessed, and
establishing it took reading the shaped findings rather than the code. The
depth question is answered with a named layer and NOT papered over. One more
defect was found in my own first fix by an existing test, and that is recorded
rather than quietly corrected.

## The cause, established rather than assumed

The reviewer's guess was one row per FIELD of a PubMed record. That is close
and wrong in the load-bearing way, and a per-field rule would have produced
fifteen rows rather than the ninety-one measured.

IT IS ONE ROW PER SENTENCE OF THE ABSTRACT. `build_structured_fallback_
narrative` marks every SENTENCE of a finding's value separately, which item
11.34 made it do for a real reason: a multi-sentence body with one trailing
marker grounds nothing at all, so the finding contributes no citation.

Dumping the real findings for `Does coffee help make exercise more effective?`:

    [1..5]   field='title'     sentences=1   five papers
    [6]      field='abstract'  sentences=16
    [7]      field='abstract'  sentences=8
    [8]      field='abstract'  sentences=21
    [9]      field='abstract'  sentences=32
    [10]     field='abstract'  sentences=6
    [11..15] field='pmid'      sentences=1
    15 findings over 5 records; 93 listing rows, 83 of them abstract sentences

So each paper contributes THREE findings sharing one `source_url`, and the
abstracts alone account for 83 of the 93 rows.

AND THE TRIGGER, which matters as much as the cause: the model's own narrative
grounded ZERO claims. Its text was good prose about the papers, but
`ground_claim` accepts a claim only when it is contained in the cited
finding's value, and a synthesis across five papers quotes none of them
verbatim. So the code-built listing, designed as a last resort, becomes the
WHOLE answer on this path every time.

THE SAME DUPLICATION IS ON THE DISEASE PATH and is merely smaller. `GERD`
measured 19 findings over 12 records, 26 listing rows, with papers
contributing `title`, `pmid` and sometimes `abstract`. It is worst on the
topic path because there every admitted record is a paper with a long
abstract and there is nothing else in the answer.

IT ALSO BROKE A HELD-BACK PRODUCT-OWNER DECISION. `core/breadth_plan.py`'s
module docstring records that abstract sentences do NOT become findings until
a new design exists, held back on 2026-09-14 because a sentence rule accepted
meaning-reversing fragments and cannot see a refutation in the next sentence.
The listing was emitting one quoted abstract sentence per row. Fixing the
readability restores that decision, and it also resolves my own F-12.7-03,
the "It can be a powerful ergogenic aid" quote I escalated: that sentence was
a listing row, and listing rows are now titles.

## The fix, and the mistake inside my first version

`one_finding_per_record`, in front of the listing loop. Group by
`source_url`; keep one finding per record; prefer a single-sentence value so
the row that ships is the title rather than a whole abstract; never
deduplicate on the rendered string.

MY FIRST VERSION GROUPED ON `source_url` ALONE AND WAS WRONG. An existing
test caught it: `test_graph.py::test_tool_row_limit_truncation_is_surfaced_
even_when_byte_ceiling_never_fires` has three genes, `NCBIGene:672`, `673`
and `674`, every one `field="name"` and every one pointing at
`.../gene/672`. Collapsing them deleted two real findings, and the answer
then announced itself INCOMPLETE, because a deleted finding counts as
unreported and floors the trust outcome to `ask`. A readability fix had
started telling readers their answer was missing sources.

Which of `goal-contracts`' three cases: THE SUBJECT WAS WRONG. The check was
right and my rule was wrong, so the rule changed and the check did not.

The corrected rule adds one clause: within a `source_url` group, if every
finding carries the SAME `field` name they are separate records sharing a
page and ALL are kept; only a group with DIFFERENT field names is several
views of one record and collapses to one. The discriminator is the field
NAME, metadata, never the field value.

## Measured effect

| Shape | Records | Listing rows before | Listing rows after |
|---|---|---|---|
| q5, topic path (measured live) | 5 | 93 | **5** |
| q2, disease path (measured live) | 12 | 26 | **12** |
| three genes sharing one page | 3 | 3 | **3**, unchanged |

WHAT IT COSTS THE CITATION COUNT, stated plainly because it will look like a
regression on the old verify surface: q5 drops from 15 citations to 5. That
is the duplication leaving, not evidence leaving. Five papers were always
five papers. The count was never the right measure, which is the whole point
of this round.

WHAT IT DOES NOT TOUCH: the MODEL still receives every finding, abstracts
included. `build_synth_messages` is unchanged, so a narrative that quotes an
abstract still grounds against it and still earns that citation. Only the
code-built listing is deduplicated.

WHAT I COULD NOT ADD: journal and year. The `pubmed_abstracts` path is an
EFetch, and `_extract_pubmed_fetch_records` parses `title` and `abstract`
only; `fulljournalname` and `pubdate` live on the ESummary path, which this
question does not call. Adding them means a third call per question. Reported
rather than built.
