# Card 48 diagnosis: a fuzzy question should ask which aspect first

Base: develop at c916cfa3. Read-only diagnosis, no model calls made.

## Table of contents

- [Status today](#status-today)
- [What a person sees](#what-a-person-sees)
- [The cause](#the-cause)
- [The smallest fix](#the-smallest-fix)
- [Overlap](#overlap)
- [Needs the owner](#needs-the-owner)
- [Proposed test query](#proposed-test-query)

## Status today

Still happens. The ask-back is live only for an opening message of one to three words. Ticket T-8.10-06 in `testing/Developer/reports/2026-09-26_conversation_next_steps/design.md` (the widening) is not built, and no commit since touches the gate: `_MAX_CLARIFY_TRIGGER_WORDS = 3` at `core/graph.py:3677`.

## What a person sees

Measured in F-8.6-RA04 (`tracker/phase_8.6.md`, line 478), live, researcher depth:

| Question typed | Words | What came back |
|---|---|---|
| `Tell me about apple trees.` | 5 | "Found 5 pubmed records: Proteomic differences in apple spur buds ..." 9 citations, 29.9 s, $0.0222 |
| `How do birds fly?` | 4 | "What it takes to fly: the structural and functional respiratory refinements in birds and bats ..." 6 citations, 18.6 s |
| `Tell me about the tree of life.` | 7 | A list that includes a gradient boosted tree paper on quality of life questionnaires, 7 citations, 27.9 s |

The answer looks authoritative and cited, but sits beside the question. The owner wants: "When there are fuzzy questions like this, clarify."

## The cause

| Part | Evidence |
|---|---|
| The word count is a hard gate | `core/graph.py:4055`: the `think.ask_back` decision is asked only when the opening text is at most 3 words. A 4 to 7 word fuzzy question never reaches it. |
| The decision's own wording shuts the door | `_ASK_BACK` (`core/graph.py:966`): "proceed" covers any question or "a subject followed by a word that names the wanted kind of information". "Tell me about X" and "How do birds fly?" read as requests, so even if asked, the classifier would say proceed. |
| Fuzzy here has two kinds | A subject with a vague request ("Tell me about the tree of life"), and a real question outside what biomedical records can answer ("How do birds fly?"). Both got in through the R-03 door (guard said off topic, Jev said on topic). |

## The smallest fix

Widen the same classifier decision, not a word list.

1. Gate: in `core/graph.py` `_think` (line 4055 area), ask `think.ask_back` for any opening turn (no memory), not only when the text is 3 words or fewer. Keep the 3-word case exactly as today.
2. Criterion: in `_ASK_BACK` (`core/graph.py:966`), add to "ask_back": a message that asks to be told about a subject in general, or asks something so broad that the answer depends on which aspect is meant, with no word naming the wanted kind of information. Keep "proceed" for a specific request.
3. Writer: for messages over 3 words, call `_write_clarify_choices` only after the decision picks `ask_back` (one extra 2 to 3 s on asked-back questions only), instead of beside the decision on every opening question.
4. Fail-open stays: any failure searches. Never ask back on a follow-up (memory present).
5. Held-out measure from the ticket: ten opening texts, five subjects and five real questions, live; every real question must still search.

| Item | Value |
|---|---|
| File fence | `core/graph.py`: `_ASK_BACK` spec, `_think` ask-back gate, nothing else. Tests: `tests/system_03_search_agent/core/test_bare_topic_clarification.py`, `test_clarify.py`. |
| Answer path | Yes: it decides whether a search happens. |
| Dial position | 2, runnable behaviour. |
| Size | M (small code, but the live held-out measure needs about ten runs, about 20 cents). |
| Migration | No. |

The criterion text is in `core/graph.py`, not in `harness/decide.py` as the ticket says; `decide.py` itself need not change.

## Overlap

- None with phase 8.7's named functions (`_answer_tokens`, `_write_answer`, `write_node`, `act_node`, `answer_layout.py`, `findings.py`) or the guardrail functions. It edits `_think`, which is neither.
- Same file as 8.7 (`core/graph.py`), so rebase after 8.7 lands, or build first and expect a clean merge.
- `harness/decide.py` is on 8.7's list. The fix does not edit it.

## Needs the owner

Yes, a design choice. "How do birds fly?" is a complete question with a clear aim. Asking which aspect means the product treats non-biomedical-but-biology-adjacent questions as too broad. Two readings serve different users:

| Option | Person sees | Cost |
|---|---|---|
| A: ask back on a subject with no kind of information, and on "tell me about X" (recommended) | "Tell me about the tree of life" asks which aspect. "How do birds fly?" still searches. | Smallest. Fixes two of three RA04 cases. |
| B: also ask back on a real question outside biomedical evidence | "How do birds fly?" asks which aspect, offering biomedical angles. | A classifier criterion about scope, which is the guardrail's job; risk of asking back real questions. |

Also a cost choice: the writer call beside the decision (zero added wait, one extra model call on every opening question) or after it (about 2 to 3 s extra on asked-back questions only, zero extra on real ones). Recommended: after.

## Proposed test query

Add to section 1 or 2 of `testing/Test_queries_and_workflows.md`, near the bare-subject ask-back (find with the word "GERD"):

### A broad question asks which aspect first (card 48)

Queries to try:

- `Tell me about the tree of life.`
- `Tell me about apple trees.`
- Control: `What genes are associated with cystic fibrosis?`
- Control: after the ask-back, click one of the offered choices.

What you should see:

- The first two show a grey "What would you like to know" style question with three or four clickable choices written for that subject, and no search has run yet.
- The control question is searched at once, with no question back.
- Clicking a choice runs an ordinary search on it.
- Why it matters: a confident list of papers that sit beside the question is worse than one short question that finds out what the person wants.
