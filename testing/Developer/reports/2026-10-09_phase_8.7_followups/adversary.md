# Phase 8.7 follow-ups: adversary report

Fresh-context adversary, checkout detached at 9fe8f166, base develop b01dee92. Findings are appended as established.

## Findings

### A-87F-01: a follow-up turn's memory stores each re-sent citation twice
- Severity: major
- Inside a fix made this phase: yes, A04's re-send is what creates the second event; the builder named it and left it.
- What: `core/run.py::_remember_turn` builds one `CompressedFinding` per raw `citation` event. With the A04 re-send, every listing record the summary also cites becomes two findings with the same citation id, one with the listing row's words and one with the grown words.
- Reproduction: a temporary probe ran `graph_module.write_node(_write_state(audience_depth="researcher"))` with `_models` faked (as `test_write_answers_sooner.py` does) and `_request_reads_placement` true, then `run._remember_turn(query, events)` with `session_memory.remember_turn_for_caller` replaced by a capture. Printed: `MEMORY FINDINGS 8 ['cq-completeness-1', 'cq-completeness-2', 'cq-completeness-3', 'cq-completeness-4', 'cq-completeness-5', 'cq-completeness-1', 'cq-completeness-2', 'cq-completeness-3']`. The same run with `_request_reads_placement` false printed `MEMORY FINDINGS plain 5`. Before the fix (develop) the placement run sent each id once, so memory held 5.
- What a person sees: every web question (the web bundle always reads `placement`) files the summary's records twice into session memory. Memory holds at most 20 findings (`MAX_COMPRESSED_FINDINGS`) inside a 1500-token budget, so the duplicates push older turns' facts out sooner, and a follow-up question's prompt repeats the same record twice. A follow-up such as "tell me more about the second one" is answered from a thinner and repeated memory.
- NOT FIXED

### A-87F-02: the evaluation's trace reader counts each re-sent citation as a second citation and a second claim
- Severity: minor
- Inside a fix made this phase: yes (A04's re-send); named by the builder and left.
- What: `eval/trace_source.py::record_from_runs` takes every `citation` payload, and one claim per payload. A trace of a run that read `placement` (every web, MCP and GraphQL run) yields duplicate citations and claims.
- Reproduction: the same faked `write_node` stream with `_request_reads_placement` true, serialized into `runs=[{"outputs": {"events": [...]}}]`, then `record_from_runs(runs, query_id="q")`. Printed `TRACE CITATIONS 8 CLAIMS 8` with ids 1 to 5 then 1, 2, 3 again. The answer has 5 distinct citations.
- What a person sees: nobody in the product; the owner reading an evaluation scored from live web traces sees grounding ratios and citation-based scores weighted toward the summary's records (each counted twice), so the number moves for a reason that is not answer quality.
- NOT FIXED

### A-87F-03: MCP and the REST citations export now drop a conflicting repeat of a citation id silently, where GraphQL discloses it
- Severity: minor (unsure whether the server can ever send one; its own guard says it does not)
- Inside a fix made this phase: yes, the A04 fold in `adapters/mcp/server.py` and `adapters/web_sse/app.py`.
- What: a second `citation` event with the same id but another record (`source_id` and `source_url` changed) is dropped by `one_per_citation_id` with no disclosure on MCP and on `GET /v1/query/{run_id}/citations`. GraphQL counts the same event as `citations_omitted` and the CLI stream prints a "redefined" warning. On develop, MCP and REST listed both rows.
- Reproduction: a temporary probe fed the stream guard, two listing tokens, citations c1 and c2, a summary token citing c2, then c2 again with `source_id="MedGen:C99"`, then done, through the builder's `_registry_run` and `_event` helpers. Printed: `MCP CONFLICT [('c1', 'MedGen:C1'), ('c2', 'MedGen:C2')] MSG None`, `REST CONFLICT [('c1', 'MedGen:C1'), ('c2', 'MedGen:C2')]` with no disclosure header, `GQL CONFLICT [...] omitted 1`.
- What a person sees: an agent on MCP, or a script on the REST export, is never told that the run named two different records under one number; the same run read through GraphQL says one citation was omitted. Three surfaces, three answers about one run.
- NOT FIXED

### A-87F-04: a command line built from develop before this fix prints a "redefined" warning for every record the summary cites
- Severity: minor (unsure of reach: production's command line does not send `?reads=placement`, so it never meets a re-send; only a command line built from develop since #218 does)
- Inside a fix made this phase: yes, the A04 re-send is gated on `reads_placement`, which the develop command line at b01dee92 already sends (`adapters/cli/client.py`, `params={"reads": "placement"}`), but that command line's `Renderer` treats any changed payload as a conflict.
- What: the re-send is not hidden from every client that predates it. The gate is "reads placement", not "understands re-sends".
- Reproduction: `adapters/cli/render.py` checked out at b01dee92 (restored after), `Renderer` fed guard, a listing token citing c1, citation c1 ("Disease 1"), a summary token citing c1, citation c1 again with claim_text "Disease 1 S", done. stderr: `warning: citation 'c1' was redefined mid-run; the redefinition was ignored and the first source for this id is kept.` At 9fe8f166 stderr is empty.
- What a person sees: someone running `s3 ask` from a develop install against a server with this fix sees one alarming warning per summary-cited record on every answer, telling them the sources were redefined when nothing changed. Web bundles built at b01dee92 are not affected (their `useRunView` skips a repeat with the same number).
- NOT FIXED

### A-87F-05: V01's `exclude_if` depends on a pydantic version nothing in this repository pins
- Severity: unsure
- Inside a fix made this phase: yes, V01 (`contracts/events.py`, `placement: ... = Field(None, exclude_if=_placement_is_absent)`).
- What: `Field(exclude_if=...)` exists only in recent pydantic 2.x (installed here: 2.13.4). Neither `requirements.txt` nor `pyproject.toml` names pydantic; the floor comes only transitively (`mcp 2.0.0 -> pydantic>=2.12.0`, `fastapi -> pydantic>=2.9.0`). On a pydantic 2.x that predates the parameter, `Field` takes an unknown keyword as deprecated `json_schema_extra` with only a warning, so `placement` would serialize as `"placement": null` and every old client whose model forbids extra keys would reject every token: the exact F-8.7-A01 break, with no import error to catch it. The wrap serializer it replaced worked on every pydantic 2.x. I could not establish the release that added `exclude_if` offline, so I do not know whether the transitive 2.12 floor covers it.
- Reproduction: at 9fe8f166 with pydantic 2.13.4, `TokenPayload(text="a", marker_ids=[]).model_dump_json()` gives `{"text":"a","marker_ids":[],"kind":null,"cells":null,"emphasis":null}` (correct), and the serialization schema's properties equal the validation schema's (V01 verified). The installed requirement scan printed `mcp 2.0.0 -> pydantic>=2.12.0`, `fastapi 0.140.4 -> pydantic>=2.9.0`, `litellm 1.93.0 -> pydantic>=2.10.0,<3.0.0`, and no direct pin.
- What a person sees: nothing today. If a later resolve lands a pydantic without the parameter (another package capping it, or mcp dropped), an older command line or saved web bundle stops showing any answer text, with no test failing unless the pinned-bytes test runs on that build.
- NOT FIXED

## Probed and held

Each line below is my own probe at 9fe8f166, offline, with the models and Jev faked as the existing tests do.

| Claim | Probe | Result |
|---|---|---|
| An old client sees what it saw on develop | `write_node` stream with `_request_reads_placement` false, serialized, at b01dee92 and at 9fe8f166 (`src/` checked out at the base, then restored) | Byte-identical after dropping timing fields |
| Placement and plain end with the same citations | Two other summary shapes (records 4, 5 and 1; records 3 then 1), folded one per id | Equal, field for field |
| No re-send on writer failure or cost cap after the listing | Writer raising, and `check_per_query_cap` raising for synth | Five citation events, no repeats |
| A07 bound | Jev delayed 0.9, 0.99, 1.01, 1.2 and 100000 s, placement on and off | Held 0.90 to 1.007 s; at 0.99 s the pick leads, at 1.01 s and later the count line leads with no lead decision recorded |
| A07, Jev fails and guard picks | Jev http_error, guard answers at once | Guard's pick leads, held 0.002 s |
| Caps with re-sends | 105 citations then re-sends of c1 (kept) and c103 (capped), MCP and GraphQL and the GraphQL export | 100 kept, c1 grown, 5 omitted disclosed, the capped re-send not counted twice |
| V01 | `model_dump_json()` of a token without placement, and both schemas | No `placement` key; serialization properties equal validation properties |
| History count, saved answer, MCP reopen | Read only: all three read `assemble_interaction`'s stored citations, now `one_per_citation_id` | Not probed separately |
| Web live view | Read only: `useRunView` keeps one per id and builds sources from the kept map; the builder's vitest arms not rerun by me | Not probed |

## Verdict

FAIL.

A-87F-01 sits inside this phase's own A04 fix: the re-send it added makes a follow-up turn's session memory hold each summary-cited record twice, on every web question, where develop held it once. The brief names "a follow-up turn's memory" as a surface that must keep one row per citation id. This fires the review loop's stop condition. A-87F-02 to A-87F-05 are minor or unsure.

Verified by my own probes: A-87F-01 to A-87F-04, the old-client byte parity, the A07 timing boundaries, the cap arithmetic, V01's bytes and schema. Read only: the history count, saved answer and MCP reopen paths, the web view, and A-87F-05's version question.

Housekeeping: three temporary probe files remain untracked in this checkout because the project's hook blocks deletion from the shell: `tests/system_03_search_agent/core/test_zz_adv_probe.py`, `tests/system_03_search_agent/core/test_zz_adv_dump.py`, `tests/system_03_search_agent/adapters/test_zz_adv_surfaces.py`. No tracked file was changed.
