# Card 35 diagnosis: an off-topic follow-up with a biomedical word gets through

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

Still happens. Nothing on develop changed the path since F-8.2-V01 was filed. The code in `src/system_03_search_agent/core/graph.py` (`guardrail_node` line 1829, the set-aside at line 2119) and `guardrail/prefilter.py` (`clears_biomedical_allowlist`, line 628) is as the finding describes.

## What a person sees

- They ask one gene question, such as BRCA1.
- They then type "Which cell phone is it best to buy this year?"
- The product runs a full paid search and grounds it on the remembered gene, instead of saying the question is outside biomedical research.

## The cause

| Step | Evidence |
|---|---|
| The word list admits the question | `prefilter.clears_biomedical_allowlist` returns True on "cell", "study", "research", "effective" (`prefilter.py:628`). |
| So no relevancy judge is started | `graph.py:1829`: `if not prefilter.clears_biomedical_allowlist(...)` creates the relevancy task. A hit leaves `relevancy_task` as None. |
| The guard classifier says off topic | Its verdict is set aside by `_is_memory_bound_follow_up` alone (`graph.py:2119`), because the sentence holds "it" and memory holds an entity. |
| Nothing else checks | The relevancy check at `graph.py:2213` needs a task. With none, the question continues. The check at `graph.py:2237` also needs one. |

Without memory the same sentence is refused by the classifier, so the leak is only the set-aside path.

## The smallest fix

Start the relevancy judge whenever the set-aside could apply, whatever the word list says. In `guardrail_node` change the condition at `graph.py:1829` to start the task when the word list misses OR `_is_memory_bound_follow_up(query.text, state)` is true. The existing code at lines 2213 to 2240 then judges the follow-up with the previous question in view (`_relevancy_state`) and refuses on "off_topic". A genuine follow-up ("and what about it in children?") is still admitted, as F-8.2-A01 already proved.

| Item | Value |
|---|---|
| File fence | `core/graph.py`, function `guardrail_node` (one condition). Test in `tests/system_03_search_agent/guardrail/test_guardrail_node_integration.py`. |
| Answer path | No. It is the guardrail, before Think. |
| Dial position | 2, runnable behaviour. |
| Size | S |
| Cost | One cheap classifier call (about $0.00008, 1.7 to 1.9 s measured in F-8.2-A01) on follow-ups only, run alongside the injection check, so the person waits for the slower of two. |
| Migration | No. |

This respects the standing rule: a model decides, code only verifies. The word list stays as an admission shortcut for first questions, which the owner may want to retire later (see below).

## Overlap

- Touches `guardrail_node`, in the guardrail overlap zone. Not `_guardrail_after_prefilter`, `_jev_injection_pick`, `_await_jev_own_pick`, `jev_client.py` or `call_log.py` themselves, but it feeds the task they read.
- No overlap with phase 8.7 (`_answer_tokens`, `_write_answer`, `write_node`, `act_node`, `answer_layout.py`, `findings.py`, `decide.py`).
- Both edit `core/graph.py`, so a rebase conflict is possible but small.

## Needs the owner

No for the fix. Optional design choice for later: retiring the word list for first questions too, which would put every question through a model call (cost and speed). Not needed to close this card.

## Proposed test query

Add to section 6 of `testing/Test_queries_and_workflows.md`, after query 45:

### An off-topic follow-up with a biomedical word in it (card 35)

Queries to try:

- Ask query 1, then `Which cell phone is it best to buy this year?`
- Then `Is it effective to invest in bitcoin right now?`
- Control: after query 1, ask `and what about it in children?`

What you should see:

- The two off-topic follow-ups are refused with the "Outside biomedical research" label and no search runs.
- The control follow-up is answered about the same gene.
- Why it matters: a person should not pay for, or trust, a biomedical answer to a question that is not biomedical because one word matched.
