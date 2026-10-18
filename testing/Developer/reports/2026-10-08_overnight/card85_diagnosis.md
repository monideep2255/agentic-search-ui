# Card 85 diagnosis: the facts checker's gaps and three logging gaps

Diagnosis only, 2026-10-08 overnight, read against `develop` at `c916cfa3`. Paths are relative to `<repo-root>`. No code was changed and no model was called. The checker probes ran on a scratch copy made with `git archive`, each edit restored after its run.

## Table of contents

- [Status today](#status-today)
- [What a person sees](#what-a-person-sees)
- [The causes](#the-causes)
- [The smallest fixes](#the-smallest-fixes)
- [Overlap with phase 8.7 and the guardrail](#overlap-with-phase-87-and-the-guardrail)
- [Needs the owner](#needs-the-owner)
- [Proposed test query](#proposed-test-query)

## Status today

Every slice still happens on develop. The checker is unchanged since `e0b4fbb2` (2026-09-29) apart from two pattern updates (`fe178506`, and `9e791e45` in #156).

Checker baseline on develop: `facts: 80 | stale 0 | not fully checked 0 | places: PASS 225, FAIL 0, GAP 0, ERROR 0 | PASS`, exit 0. Three of the verifier's edits, re-run today on a scratch copy:

| Edit to `ArchitectureScreen.tsx` | Verifier's id | Checker result today |
|---|---|---|
| The cite-or-refuse sentence reversed: "cited to the model's own knowledge ... written from the model's memory" | V-M10d (F-53-V05) | PASS 225, exit 0: not caught |
| "a time limit the model chooses for it on each question" | V-M10 (F-53-V05) | PASS 225, exit 0: not caught |
| "This happens only in Researcher mode." added after the guarded LitVar2 sentence | V-M09 (F-53-V02) | PASS 225, exit 0: not caught |

The logging gaps, read on develop:

| Gap | Report id | Develop today |
|---|---|---|
| A crash's reason sits on the lines after its trace id | F-73-V01 | Still: `_crash_record` (`src/system_03_search_agent/core/run.py:262` to `292`) puts only "search crashed, trace <id>" on line 1; class, chain and frames follow on lines without the id. It writes `trace <id>`, where every other line writes `trace_id=<id>`. |
| Step-level failures that log no reason | F-73-J06 | Part fixed by card 72: the guardrail's own call now logs one line with its outcome (`core/graph.py:1977`, `call_log.log_model_call`, outcome `error`, `timeout` or `rate_limited`), but not the error's class. Think (`core/graph.py:3885`, `_run_think_classification`) and Write (`core/graph.py:13120`, `_write_answer`) still turn the failure into "A step in this query failed unexpectedly." with no log line. |
| An older database warning logs a full error message | F-73-A07 | Still: five warnings carry `exc_info=True` (`core/run.py:458`, `507`, `575`, `776`, `954`), so a database failure prints host, port and driver message, and a statement error could print its parameters, under the same trace id. |

Whether F-73-V01 hurts depends on how the deployed log viewer groups lines. Cheapest check: find any past crash's trace id in the deployed develop logs and see whether the class line comes back with it.

## What a person sees

Nothing directly; these are behind the scenes.

- The checker: `/verify` can certify the About and Architecture pages while they say the opposite of the product's trust promise. A reader of the Architecture page could then be told that an uncited claim is written from the model's memory, with the check green.
- The logs: when a search fails, the person sees "A step in this query failed unexpectedly." and the developer finds no reason in the log, so the failure cannot be fixed from its report.

## The causes

| Slice | Where | Cause |
|---|---|---|
| F-53-V05, sentences with no place | `.claude/skills/verify/scripts/facts_registry.py` | No fact names the cite-or-refuse sentence (`ArchitectureScreen.tsx:521` to `522`), the time-limit sentence (line 513) or About's "says which limit it hit" (`InfoScreens.tsx:1391`). The registry has a time-limit fact only for the About wording (`facts_registry.py:1439`). |
| F-53-V02, a false sentence beside a guarded one | `.claude/skills/verify/scripts/check_facts.py:736`, `sentence_problem` | Checks only the sentences a place's match touches; a new sentence after the full stop is read by nothing. |
| F-53-V03, true wording in a place a reader never sees | `check_facts.py:532`, `_unused_constants`, and `:677`, `visible` | Only comments and unused top-level constants are blanked. An unused component, a `{false && ...}` branch, a `data-` attribute, a type alias or an unused local still vouch. |
| F-53-V04, a guarded sentence moved elsewhere on the page | `facts_registry.py` places | A place names a file, not where in it. |
| F-73-V01 | `core/run.py:262`, `_crash_record` | Multi-line record, id on line 1 only (the fix for F-73-J05's wrapping). |
| F-73-J06 | `core/graph.py:3885`, `13120`; `_step_error_kwargs` at `862` | The step error is built for the person with no log call beside it. |
| F-73-A07 | `core/run.py` five `exc_info=True` warnings | The crash record's no-message rule is not applied to its neighbours. |

## The smallest fixes

| Field | Checker: V05 | Checker: V02, V03, V04 | Logs: V01 and J06 | Logs: A07 |
|---|---|---|---|---|
| Change | Add facts for the three unplaced sentences, each with a break-it edit in `MUTATIONS` | Read the whole paragraph a place sits in (V02); blank every non-rendered carrier, or read rendered text from the built page (V03); anchor a place to its stop or heading (V04) | Line 1 of the crash record carries `trace_id=<id>` and the class; Think and Write log one warning with the trace id, step, `error_class` and the cause's class, never its message | Replace `exc_info=True` on the five warnings with the class and chain the crash record already builds |
| Files and functions | `.claude/skills/verify/scripts/facts_registry.py` | `.claude/skills/verify/scripts/check_facts.py`: `sentence_problem`, `visible`, `_unused_constants`; place matching | `core/run.py` `_crash_record`; `core/graph.py` `_run_think_classification`, `_write_answer` (or once, in `_step_error_kwargs`); tests in `tests/system_03_search_agent/core/test_run.py` | `core/run.py`, the five warning sites |
| Answer path | No | No | No | No |
| Dial position | 3, `.claude/` | 3, `.claude/` | 2 | 2, but see the owner below |
| Size | S | M for V02 and V04; L for V03 by rendered text | S | S |
| Migration, package, event schema | None | None; reading rendered text uses the existing `capture.mjs` and no new package | None | None |

Logging `_step_error_kwargs` once covers all three steps at one site, and the guardrail's call-log line stays as it is.

## Overlap with phase 8.7 and the guardrail

| Fence | Phase 8.7 | Guardrail |
|---|---|---|
| `.claude/skills/verify/scripts/` | None | None |
| `core/graph.py` `_write_answer` (J06, Write) | Yes: rewritten tonight | None |
| `core/graph.py` `_run_think_classification` (J06, Think) | No | No |
| `core/graph.py` `_step_error_kwargs` (J06, one site) | No, but its callers in `_guardrail_after_prefilter` and `_write_answer` are | Yes, it is called from `_guardrail_after_prefilter` |
| `harness/call_log.py` | None from these fixes | The guardrail work owns it; leave it alone |
| `core/run.py` (V01, A07) | None | None |

The checker fixes and the `core/run.py` fixes can be built tonight. The J06 log lines wait for 8.7 and the guardrail to merge.

## Needs the owner

- The checker fixes: yes, a `.claude/` change, so the owner approves it itemized before it is built (dial 3).
- F-73-A07: yes, a design choice the adversary left to the owner and no `DECISIONS.md` row has recorded. Either no log line carries an exception's message (recommended: a developer still gets class, chain and frames, and no connection detail or SQL parameter reaches the log), or the crash record also carries the message.
- F-73-V01 and F-73-J06: no.

## Proposed test query

No user-facing query covers log lines. The page half is existing query 102 ("The pages say what the system actually does", card 53). Proposed line to add to it:

```markdown
- The Architecture page's citation stop still says a claim with no link is not cited and an answer with nothing to cite is refused; the time limits are set in code, not by the model.
```
