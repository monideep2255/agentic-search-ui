# Builder F: token placement field and reading order

Base commit: 586d715183733f94c2a2059c18222732caccbb57 on feat/8.7-field.

## What landed

- Cherry-pick of 1e030148 applied cleanly: `TokenPayload.placement` ("listing" or "summary", default "summary"), the browser copy, the schema document row.
- New helper `contracts/token_order.py`: `placement_of`, `in_reading_order`, `joined_text`. A missing or unknown placement counts as summary, so a stream with no placement joins in arrival order.
- Used in: MCP answer collector, GraphQL fold, CLI `JsonRenderer`, saved answer (`answer_markdown_from`), `eval/trace_source.py`, `local_loop_run_depth.py`.
- CLI streaming `Renderer`: listing tokens are held and written at `done` or `finish()`, after the summary.

## Plan deviations

- `adapters/cli/main.py` has no token join. Its token loop only sets a flag, and the text is written by `Renderer`. No change there.
- `flagship_measure.py` and `local_loop_run.py` do not join token text, so they are unchanged.
- The streaming CLI cannot reorder text already written, so a listing that arrives first waits until `done`. A listing with no summary is still written at `finish()`.

## Learnings

- My scripted insert above `offered_options` removed its `@property` line. One test in `test_s3_as_printed.py` caught it. Re-add decorators when inserting a method above a property.
