# Build phase 8.1: fix-and-verify round

The phase's one fix-and-verify round, run by the fix agent on 2026-09-25 against `phase/8.1-good-questions-answer` at `310f607`. The work list is the lead's triage of round 1 in `tracker/phase_8.1.md`. Each result is written here the moment it is established.

## Table of contents

- [Scope](#scope)
- [Item 1: the Think retry](#item-1-the-think-retry)
- [Item 2: thirty sources on a paper question](#item-2-thirty-sources-on-a-paper-question)
- [Item 3: the MedGen clinical features path](#item-3-the-medgen-clinical-features-path)
- [Tests and lint](#tests-and-lint)
- [Live runs](#live-runs)

## Scope

- File fence: `core/graph.py`, `synthesis/findings.py`, `tools/ncbi_eutils_actions.py`, `tools/ncbi_efetch_schemas.py`, `harness/coordinator_worker.py`, their tests, and this report.
- Untouched on purpose: `synthesis/grounding.py` and `synthesis/trust.py`. The cite-or-refuse gate stays exactly as develop has it.
- Not reintroduced: the two reverted changes, `c9b3441` (full-retrieval conflict floor) and `76a0578` (stacked citation markers).

## Item 1: the Think retry

Findings: F-8.1-J04, J05, A05.

What the person typing a question gets: nothing changes on a good run. On a run where the planning model sends a malformed reply, the second attempt still tells it exactly what was wrong, and now a reply engineered with an enormous or multi-line key name can no longer blow up the second model call or forge a line in the operator's log.

What changed, in `core/graph.py`:

- `_THINK_ERROR_TEXT_MAX_CHARS = 300`, a named constant. 300 holds every real field-level complaint (the live shape "narrative: Field required; bogus_field: Extra inputs are not permitted" is 60 characters), so only a reply whose key names are themselves oversized gets elided.
- `_bounded_one_line(text, max_chars)`: every non-printable character (newline, carriage return, control characters, U+202E, U+200B) becomes a space, whitespace collapses, and anything past the cap is cut with a note "... [N more characters elided]".
- `_think_validation_detail` now returns its summary through that bound. Its docstring no longer claims a 256-character cap it never had.
- `_think_error_text(exc)` is the one form of the error both readers take. In `think_node` it is computed once as `error_text`; the warning log and the retry prompt both use `error_text`, never `exc` raw.

Tests, in `tests/system_03_search_agent/core/test_graph.py`:

- `test_think_retry_feeds_back_the_validation_error` rewritten so it can fail. The fake model now repeats its bad reply unless the messages carry attempt 1's reply echoed as the assistant turn AND a user turn naming "bogus_field" and "narrative: Field required". The word "bogus_field" appears nowhere except in the bad reply and the feedback built from it, unlike "narrative", which the system instruction also contains (the vacuous check J05 found). It also asserts attempt 1 carries no feedback and attempt 2 carries exactly two more messages.
- `test_think_validation_detail_is_bounded_for_an_oversized_key`: the 5,000-character key and five 20,000-character keys from round 1.
- `test_think_error_text_cannot_forge_a_second_line`: newline, carriage return, escape sequence, U+202E, U+200B in a key name.
- `test_bounded_one_line_keeps_a_short_error_whole`.
- `test_think_retry_prompt_and_log_carry_only_the_bounded_error`: end to end through `think_node` with a 20,000-character key holding a newline; the retry prompt and both warning log lines are one line and bounded.

Proof the feedback test can fail (run 2026-09-25 in this worktree, then restored from a byte copy):

- Mutation 1: the line `call_messages = think_messages + [` changed to `_unused_feedback = think_messages + [`, which restores the blind resend. Result: `2 failed, 12 passed` (`test_think_retry_feeds_back_the_validation_error` at `assert _carries_feedback(think_calls[1])`, and the end-to-end bounding test). Restored: `14 passed`.
- Mutation 2: `_bounded_one_line` made to return its input unchanged. Result: `3 failed, 11 passed` (the three bounding tests). Restored: `14 passed`.

## Item 2: thirty sources on a paper question

Finding: F-8.1-A08.

What the person typing a question gets: on a question whose prompt carries long paper abstracts, the writing model now reads all 30 findings it is handed instead of stopping part-way down the list, so the owner's 30-source decision takes effect for the model's own prose too, not only for the code-built listing.

What changed:

- `synthesis/findings.py`: `MAX_FINDINGS_BLOCK_CHARS` 12,000 to 18,000, with the reason and the decision it serves in its comment.
- `MAX_FINDINGS_PER_PROMPT = 25` in the same file was checked and left alone: it is only a default argument of `build_synth_findings`, and the live caller in `write_node` passes `_MAX_FINDINGS_FOR_DISPLAY` (100) instead, so it binds nothing on the live path.
- Test comment in `test_pubmed_abstract_grounding.py` that named "12,000" now names the constant.

Tests, `tests/system_03_search_agent/synthesis/test_pubmed_abstract_grounding.py`:

- `test_a_thirty_finding_prompt_with_long_abstracts_reaches_the_model_whole`: the longest prompt the live path can build (the breadth plan fetches at most 5 papers per question, so 5 abstracts and one gene summary, each at the 2,000-character field cap, beside 24 short rows). A populate-check asserts 12,000 characters cuts this shape; the test then asserts all 30 markers appear in `build_synth_messages`'s user message.
- `test_block_cap_is_the_fix_round_value`.
- Mutation: the constant set back to 12,000 gives `2 failed, 7 passed`; restored, `9 passed`.

Offline reconstruction, the adversary's own synthetic shape (15 paper titles and 15 abstracts, rendered by the branch's `render_findings_block`; script `<scratchpad>/probe_block_caps.py`):

| Abstract length | Findings rendered at 12,000 | At 18,000 |
|-----------------|-----------------------------|-----------|
| 1,000 | 21 | 30 |
| 1,200 | 18 | 27 |
| 1,300 | 17 | 25 |
| 1,400 | 15 | 23 |
| 1,500 | 15 | 22 |
| 1,800 | 13 | 19 |
| 2,000 | 11 | 17 |

Stated plainly, since this is where the acceptance is tight: at 18,000 a prompt of 15 abstracts of 1,500 characters renders 22, not more than 22; it passes 22 at 1,400 characters or shorter. That shape cannot occur on the live path today, since no question fetches more than 5 PubMed abstracts. The shape that can occur, 6 values at the 2,000-character cap among 30, renders all 30 at 18,000 and 25 at 12,000 (the unit test above).

Live run 1 of 12, `What research papers discuss BRCA1?`, researcher depth, $0.0172, 31.1 s, outcome `ask`, 58 citations (log: `<scratchpad>/live1_papers.log`, script `fix_round_live_run.py` in this folder). Both Synth calls were handed 30 findings and rendered all 30, in a 1,010-character block, at 12,000 and at 18,000 alike. Every one of the 30 was a short graph `curie` row, so this question, the one builder A used as T-8.1-02's evidence, never puts an abstract in front of the model at all; its "58 sources" are the code-built listing. This confirms F-8.1-A08's point that the earlier evidence could not show the block cap either way, and it is why the proof for this item is the offline shape above rather than this run.

## Item 3: the MedGen clinical features path

Findings: F-8.1-A11, A12, J09, J10, J11, J13, J14, A03, A04, A10.

## Tests and lint

## Live runs
