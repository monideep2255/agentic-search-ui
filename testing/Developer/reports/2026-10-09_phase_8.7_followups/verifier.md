# Phase 8.7 follow-ups, fresh verifier

Fresh-context verifier after the one fix round. Branch `fix/8.7-followups-a04-a07` at `077c553b`, compared with develop `b01dee92`. Read and run only; probes live outside the checkout. Findings are appended as established.

## Findings

### V-87F-01: an old client's stream is no longer byte-identical to develop; each summary-cited citation's claim_text is reordered
- Severity: minor (unsure whether it is a defect: the change is deliberate and restores the order from before 8.7)
- Inside a fix made this phase: yes, the fix round's J-87F-03 change (`row_claims` in `_citations_from_grounded_claims`, `core/graph.py`), which applies to every request, not only one that reads `placement`.
- What: for a request without `?reads=placement`, every token frame and every citation's number, record and link are byte-identical to develop, but each citation a summary sentence cites carries its `claim_text` in the other order: the sentence's words first, the record row's after. Develop sends the row first.
- Reproduction: my probe drove offline `write_node` (Researcher five-disease state, three writer replies, Jev picking "neither" and "first", `_request_reads_placement` false) on this branch and on an export of `b01dee92`, then compared each serialized event with `ts` and timing fields removed. 12 of 12 plain runs differ only in `claim_text` (plus `call_elapsed_s` and `elapsed_ms`). Example, citation `cq-completeness-1`: branch `NCBIGene:672 is associated with disease name number 1 Disease MedGen:C1, name: disease name number 1`; develop `Disease MedGen:C1, name: disease name number 1 NCBIGene:672 is associated with disease name number 1`. No token frame carries `placement` on either tree, and the citation event count is 5 on both.
- Why it matters: the brief's claim "old clients get byte-identical streams to develop" is false as stated. For a person it is not worse: the same words, in the order from before 8.7, the order card 57 asks for, and no client schema reads the order. A byte-level golden or a cached comparison against develop would see a change.
- NOT FIXED

### V-87F-02: a command line installed from develop since #218 prints a false "redefined" warning for every summary-cited record once it reaches a server with this branch
- Severity: minor (narrow reach; a false alarm, not a wrong record)
- Inside a fix made this phase: yes, the A04 re-send (`916b5c37`), gated on `reads=placement`, which develop's command line already sends.
- What: the fix round's quiet arm (`names_same_record` in `adapters/cli/render.py`) only helps a command line built from this branch. A command line built from develop `b01dee92` treats each re-send as a conflict, prints one warning per summary-cited record, and its `--json` keeps the row words only (as develop's server gives today).
- Reproduction: this branch's offline `write_node` stream (placement on) fed to develop's `Renderer`: answer "answering" printed `warning: citation 'cq-completeness-1' was redefined mid-run; the redefinition was ignored and the first source for this id is kept.` and the same for -2 and -3; "reverse" printed two (-1, -4), "single" one (-2). The same stream through this branch's `Renderer` printed nothing. A plain stream (no `reads=placement`) printed nothing on either.
- Who meets it: README's published install is `pip install "git+https://github.com/<owner>/agentic-search-ui.git#subdirectory=clients/system3-cli"`, which resolves to the default branch, `develop` (`gh repo view`). Develop's client has sent `reads=placement` since `95680687` (2026-10-08 evening), so anyone who installed in that window and points at the develop deployment (`S3_BASE_URL`) meets it at merge, and at the next production release with the default server. Production today (`cde4f592`) has neither the client flag nor the re-send, so the production command line never meets it.
- Worse than develop for a person: yes, for that narrow group only, in noise: on develop's server today the same command line prints no warning and the same records; on this server it prints a warning that says sources were redefined when nothing changed. The answer, the numbers and the records are the same. A reinstall clears it. Worth a line in the release note; a server-side alternative is gating the re-send on a new `reads` value only the fixed client sends.
- NOT FIXED

### V-87F-03: the pydantic floor is stated in requirements.txt but not in pyproject.toml
- Severity: unsure (no install changes either way today)
- What: `requirements.txt` now carries `pydantic>=2.12.0` for `exclude_if`; the root `pyproject.toml` dependency list, which a wheel install reads, still names no pydantic and relies on `mcp>=2.0` the same way requirements.txt did before.
- Reproduction: `grep -n -i pydantic pyproject.toml` prints nothing; `grep -n pydantic requirements.txt` prints line 13.
- Why it matters: only for the stated reason of the fix (say the need where it is installed); the wheel path keeps the transitive guarantee only.
- NOT FIXED

## What I ran

All offline: models, Jev and the guard faked, no live model call. My own probes in a scratch directory outside the checkout, against this branch and an export of develop `b01dee92`. One note on method: the session's shared scratch directory held another agent's `conftest.py` that swaps `TokenPayload` for a subclass defaulting `placement` to "summary"; my first runs picked it up and showed `placement` on every token of a plain stream on both trees. I moved every probe to a fresh subdirectory and reran everything; all numbers below come from the clean runs.

| Check | Method | Result |
|---|---|---|
| 1. One entry per citation id, same as develop | 12 offline `write_node` runs per tree (three writer replies, Jev "neither" and "first", placement on and off), each stream fed to MCP `_fold_run_to_response`, GraphQL `fold_run` and `fold_citations`, REST `GET /v1/query/{run_id}/citations`, CLI `Renderer` and `JsonRenderer`, `assemble_interaction`, `_remember_turn` (capture), `record_from_runs`, and the web `useRunView` (vitest, branch hook, then develop's hook checked out and restored) | Branch sends 8, 7 and 6 citation events where develop sends 5; every surface on the branch shows 5 rows, one per id, with the same (id, number, record) list as develop's surface on develop's stream, in all 12 runs. Web: 5 sources and identical claims on both trees, and develop's hook on the branch's stream also gives 5 |
| 1. Sentence's words first | `claim_text` of each summary-cited record on every surface | Sentence words first on every surface (records 1 to 3; 4 and 1; 2). Record 5 in one shape was stripped by grounding, so it is not summary-cited and correctly keeps row words. Develop with placement carries row words only. With `_CLAIM_TEXT_MAX` at 80, the sentence's words are kept and the row is what drops |
| 1. Session memory and eval | captured findings, `record_from_runs` counts | 5 findings and 5 shown records on both trees in all 12 runs; eval 5 citations and 5 claims on both. Develop's own `_remember_turn` fed the branch stream stores 8, which is what the fix closes |
| 1. Old clients | serialized events, placement off, `ts` and timing removed | No token carries `placement` on either tree; tokens identical; citation `claim_text` order differs (V-87F-01) |
| 2. A07 | real event-loop clock from the pick being asked to the first summary claim token, placement on and off | Jev at 0.95 s: 0.95 s, Jev's sentence leads (develop the same). Jev at 1.05 s: 1.003 s, count line leads, no lead decision recorded (develop 1.053 s, Jev leads). Jev never: 1.003 s, count line (develop 3.50 s, guard's pick). Jev fails at 0.9 s, guard slow: 1.003 s, count line (develop 3.92 s). A writer reply opening on an ungrounded sentence with Jev picking "first": the grounded sentence leads on both trees |
| 3. CLI | branch and develop `Renderer` on the branch's placement stream; a same-record re-send and a different-record re-send | Branch: no warning on any of 12 streams; the builder's different-record arm still warns. Develop's CLI: one warning per summary-cited record (V-87F-02) |
| 4. pydantic | installed 2.13.4 METADATA changelog; `pip index versions`; `pip install --dry-run --ignore-installed --report` of develop's and this branch's requirements.txt | Changelog lists "Add support for exclude_if at the field level (#12141)" under v2.12.0b1, so 2.12.0 has it. mcp 2.0.0 requires `pydantic>=2.12.0`. Both dry runs resolve the same 113 packages at the same versions (pydantic 2.14.0, mcp 2.3.0 today), so the floor changes nothing a fresh install gets |
| 5. Tests | contracts, adapters (MCP, REST, GraphQL, CLI), eval trace_source and phase 5.2 eval files, core run, run capture, session memory, plan memory, run registry, the four write test files, feedback | 1686 passed, 2 warnings. Every core and synthesis test file naming `claim_text` or `_citations_from_grounded_claims`: 578 passed, 30 skipped. `npx vitest run src/hooks/useRunView`: 7 files, 41 passed |
| 5. Lint | `ruff check`; `isort --check-only --diff src tests services tracker alembic .claude .github` | All checks passed; exit 0 |

Verified by my own probes: every claim in items 1 to 4. Read only: the MCP and REST warning log text for a different-record repeat (the builder's tests cover it, I did not probe it), the GraphQL cap path for a re-sent capped citation, and the web screen's rendering beyond `useRunView`'s sources and claims.

## Verdict

MERGE.

A04, A07 and V01 hold under my probes, and every surface shows a person one entry per citation id, the same count as develop, with the summary sentence's words first. Session memory stores 5 entries, as develop does.

Both V-87F-01 and V-87F-02 sit inside fixes made this phase (the fix round's word order, and the A04 re-send). Neither changes a record, a number or a link. V-87F-01 is the order from before 8.7, not worse for a person. V-87F-02 is the one place a person sees something worse than develop: a command line installed from develop since 2026-10-08 evening prints a false "redefined" warning per summary-cited record against a server carrying this branch, until reinstalled. The published production command line never meets it. It needs a release-note line, "reinstall the command line", or the owner's call to gate the re-send on a new `reads` value.
