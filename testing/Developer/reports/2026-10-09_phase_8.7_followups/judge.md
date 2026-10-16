# Judge report, phase 8.7 follow-ups (A04, A07, V01)

Branch fix/8.7-followups-a04-a07 at 9fe8f166, base develop b01dee92. Fresh-context judge, read and run only.

## Findings

### J-87F-01: Session memory stores a re-sent citation twice, so a follow-up turn reads each summary-cited record twice
- Severity: minor (not visible on screen; a cost and context-budget change on every follow-up of a web, command line, MCP or GraphQL turn)
- What: `core/run.py::_remember_turn` builds one `CompressedFinding` per citation event. On this branch a listing citation the summary also cites arrives twice (row words, then row words plus the sentence's words). The two `claim_summary` strings differ, so `merge_turn`'s exact-match dedupe keeps both, and the follow-up's Think and Plan prompts carry an "Established:" line for the row and a second one that repeats it with the sentence appended. Inside this phase's fix (commit 916b5c37), named by the builder as outside the fence.
- Reproduction: judge probe (offline `write_node`, Researcher five-disease state, writer reply ANSWERING, `_request_reads_placement` patched True, `remember_turn_for_caller` captured, then `merge_turn` and `build_session_context(tier="plan")`), same probe on each tree:
  - branch 9fe8f166: 8 findings for 5 records (cq-completeness-1, -2, -3 each twice); context 694 chars, `count_tokens_worst_case` 232
  - develop b01dee92: 5 findings; 376 chars, 126 tokens
  - before 8.7 (b01dee92^1): 5 findings, sentence words included; 511 chars, 171 tokens
- Why it matters: every follow-up turn pays for the duplicate lines (232 against 171 before 8.7, about a third more on this fixture, scaling with how many listing records the summary cites), and the 20-finding cap and the memory budget fill sooner, so compaction merges and cuts an earlier turn's facts sooner. A person does not see it directly; they may see a follow-up lose an older turn's context earlier. The fix the builder names (fold through `one_per_citation_id` before building findings) is one line. Not worse than develop in what is remembered (develop lacks the sentence words entirely), worse in duplication and size.
- NOT FIXED

### J-87F-02: The eval trace reader counts a re-sent citation as two citations and two claims
- Severity: minor (eval tooling, not a person-facing surface; the evaluation track is closed)
- What: `eval/trace_source.py::record_from_runs` takes every citation event; a re-sent citation yields two entries in `RunRecord.citations` and two in `claims`.
- Reproduction: same probe, events dumped to JSON and passed as `[{"trace_id": "t-j", "outputs": {"events": [...]}}]`: branch `len(rec.citations) == 8`, develop 5, before 8.7 5.
- Why it matters: any eval run over live traces from this branch onward (citation counts, cost per citation, the rubric grader's claim list) reads inflated numbers, and a regression comparison against older traces would show a jump that is a measuring artifact.
- NOT FIXED

### J-87F-03: A04 is restored only when the record row leaves room; a long row drops the summary sentence's words, which before 8.7 came first
- Severity: minor (unsure on reach: depends on how often a row's words plus the sentence exceed 1000 characters, likely for gene rows that carry an NCBI summary)
- What: on this branch the joined `claim_text` puts the listing row's words first and the summary sentence's checked words after; `_joined_checked_words` drops a later entry that would not fit whole in `_CLAIM_TEXT_MAX` (1000). Before 8.7 the sentence's words came first, so a long row was the part dropped. With a long row the re-send never happens and the chip carries no sentence words, as on develop. The order comes from 8.7's merge (listing claims lead), not from this fix, but it means card 57 is not fully back.
- Reproduction: same probe with `_CLAIM_TEXT_MAX` patched to 80 to stand in for a long row:
  - branch: cq-completeness-1 sent once as `Disease MedGen:C1, name: disease name number 1`, never re-sent; cq-completeness-3 the same; only -2 re-sent
  - before 8.7: cq-completeness-1 is `NCBIGene:672 is associated with disease name number 1`, -3 is `Disease name number 3 is also associated with NCBIGene:672`
  - with the real bound (1000) on the short fixture both trees carry both parts, in opposite order: branch `Disease MedGen:C1, name: disease name number 1 NCBIGene:672 is associated with disease name number 1`, before 8.7 `NCBIGene:672 is associated with disease name number 1 Disease MedGen:C1, name: disease name number 1`
- Why it matters: the reader checking a summary sentence against its chip sees only the record's own row when that row is long, which is the A04 complaint. Not worse than develop; short of the pre-8.7 behaviour the follow-up set out to restore. The builder's test pins the row-first order, so it would not catch this.
- NOT FIXED

### J-87F-04: A command line built from develop (phase 8.7) prints three "redefined" warnings against this server
- Severity: minor (only for a command line built between the 8.7 merge and this fix; production's v0.2.0 command line does not send `reads=placement`, so it never receives a re-send)
- What: the re-send reaches any client that sends `reads=placement`. Develop's `Renderer` treats a repeat with a different `claim_text` as a conflicting redefinition and warns; develop's `JsonRenderer` keeps the first payload, so `--json` shows no sentence words.
- Reproduction: the branch's real event stream (judge probe, offline `write_node`, placement on) fed to develop's (b01dee92) `Renderer` and `JsonRenderer`: stderr `warning: citation 'cq-completeness-1' was redefined mid-run; the redefinition was ignored and the first source for this id is kept.` and the same for -2 and -3; `--json` citations carry row words only.
- Why it matters: someone testing the develop deployment with a command line installed from develop before this branch merges sees three alarming warnings on an ordinary answer. Gone once both sides carry this branch; worth a line in the release note that the command line and server must move together.
- NOT FIXED

### J-87F-05: The V01 fix relies on `Field(exclude_if=...)`, and the server's requirements set no pydantic floor
- Severity: unsure (low; the installed and the command line's pinned pydantic are 2.13.4 and work)
- What: `contracts/events.py` now leaves `placement` out through `exclude_if`, the first use of that argument in the repository. `requirements.txt` does not name pydantic; it arrives through `fastapi>=0.111`. I could not confirm offline which pydantic release introduced `exclude_if`; on a release without it the keyword would not drop the field, and `placement: null` would reach every client that did not ask for it, the F-8.7-A01 regression.
- Reproduction: `grep -in pydantic requirements.txt` prints nothing; `git grep exclude_if b01dee92 -- src` prints nothing; `clients/system3-cli/pyproject.toml` pins `pydantic==2.13.4`.
- Why it matters: only if a build resolves an older pydantic; the pinned-bytes test would then fail in CI, which runs the same requirements, so the exposure is a red build rather than a silent one. Filed so the owner can decide whether to state the floor.
- NOT FIXED

## What I ran

All offline, faked tools and models, no live model call. Probes were my own, in a scratch directory outside the repository, run against three trees: this branch, develop b01dee92 and develop before 8.7 (b01dee92^1), the last two unpacked with `git archive`.

| Check | Method | Result |
|---|---|---|
| A04, every surface once per id | one real `write_node` run (Researcher five-disease state, placement on), its events fed to MCP `_fold_run_to_response`, GraphQL `fold_run` and `fold_citations`, REST `GET /v1/query/{run_id}/citations`, CLI `Renderer` and `JsonRenderer`, `assemble_interaction`, and the web `useRunView` | branch: 8 citation events, 5 rows on every surface, records 1 to 3 carry the sentence words, no CLI warning; web sources and claims identical to develop's |
| A04, web chip words | `git grep claim_text b01dee92^1 -- frontend/src`, and the web probe | before 8.7 the web read `claim_text` nowhere outside the event type; the builder's claim holds. A04's original evidence was the API's citation events, not the web chip |
| A04, session memory and eval reader | same events into `_remember_turn`, `merge_turn`, `build_session_context`, `record_from_runs` | J-87F-01, J-87F-02 |
| A07, the wait | real event-loop clock, from the writer's reply to the first summary token | Jev 10 s: 1.002 s, count line leads (develop 3.508 s); Jev 0.95 s: 0.952 s, Jev's sentence leads; Jev fails at 0.5 s and the guard takes 3 s: 1.007 s, count line leads; Jev fails at 0.9 s and the guard answers at once: 0.96 s, the guard's pick leads; placement off, Jev 10 s: 1.003 s |
| A07, what opens | the first summary token in each run above | always the count line or a grounded candidate; before 8.7 the count line opened this answer |
| V01 | `TokenPayload.model_json_schema(mode="serialization")` and `Event.model_dump_json()` for placement None, listing, summary, on branch and develop | branch schema is the full object (six properties, `required: ["text"]`, `additionalProperties: false`), equal to the validation schema; develop `{}`. Event JSON byte-identical on both trees for all three |
| Tests | contracts, the seven touched test files, every adapters test, capture, session memory, eval, core write tests | 343 passed; 1030 passed, 1 skipped; 200 passed, 11 skipped |
| Frontend | `npx vitest run` on the `useRunView` tests; `npx tsc --noEmit -p .` | 7 files, 41 passed; exit 0 |
| Lint | `ruff check`; `isort --check-only --diff src tests services tracker alembic .claude .github` | All checks passed; exit 0 |

Verified by my own probes: A04 on every surface, the web claim, A07's bound and its lead behaviour, V01's schema and bytes, J-87F-01 to J-87F-04. Read only: the GraphQL cap path for a re-sent capped citation, the REST truncation header's change of count, and the builder's mutation table.

## Verdict

MERGE.

A04, A07 and V01 each hold under my own probes, and no surface shows a person anything worse than develop. J-87F-01 sits inside this phase's own fix (the re-send in commit 916b5c37): session memory now stores each summary-cited record twice, 232 against develop's 126 worst-case tokens on the fixture. A person does not see it on screen, and the fix is one line, so I recommend it as the next follow-up rather than a reason to hold the merge. J-87F-03 means card 57 is not fully back when a record row is long. Neither is worse than develop.
