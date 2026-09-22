# Item 11.33: every hypothesis and its verdict

Each row carries one line of evidence. Every verdict was reached offline, with
no call to develop, production, NCBI or any enrichment endpoint.

## Verdicts

| # | Hypothesis | Verdict | Evidence |
|---|---|---|---|
| a | A Pydantic `max_length=500` or a `[:500]` on a field the value travels through | CONFIRMED, in a form the hypothesis did not name | It is neither Pydantic nor a display slice: `_cap_scalar_string` at `harness/coordinator_worker.py:426-434` slices at `_MAX_STRUCTURED_NESTED_STRING_CHARS = 500` (line 173), and running `_cap_structured_fields` over the real `ncbi_efetch` row shape returns the summary at length 500 ending "through the C-terminal d" |
| b | The Redis Layer 2 and 3 response cache, live-only because develop sets `REDIS_URL` | RULED OUT | `grep -rn -i redis src/` returns only the substring "rediscover" in three prose comments. No Redis client, no cache read or write, no serialiser. The response cache is not implemented, so it cannot differ between live and local |
| c | The citation `claim_text` or `field` bounds in `contracts/events.py` | RULED OUT | `CitationPayload.claim_text` is `max_length=1000`, `field` is 128, and the value itself is not on the citation payload at all: the capture's citation events carry only `source_id`, `source_url`, `layer`, `source`, `field`, `entity_name` and `evidence_kind` |
| d | The `interactions` capture and the `GET /v1/history` read path | RULED OUT | The fragment is already present in `answer_text`, the reassembled SSE token stream, so the cut precedes anything saved or re-read |
| e | The frontend: a `slice(0, 500)`, `substring`, `maxLength` or CSS clamp | RULED OUT | Same evidence as (d), plus every `500` in `frontend/src` is an HTTP status, a font weight, a test fixture timing or prose about the 500-row graph limit |
| f | The LangSmith or PostHog wrappers replacing a value with a bounded copy | RULED OUT | Neither wrapper appears anywhere between the tool result and the finding: `act_node`'s only transform of `structured_fields` is the `coordinator_worker_execute` call at `core/graph.py:5170`, and the cut reproduces fully inside that call with no observability code loaded |
| g | The MCP or GraphQL projection allowlists shared with the web path | RULED OUT | Their 500-char bounds (`adapters/mcp/server.py:791`, `adapters/graphql/types.py:190`) are on disclosure notes, and the web SSE path imports neither. The web path's own projection, `_ncbi_efetch_output_to_structured_fields`, applies no character cap |

## Two hypotheses that were not on the list and mattered

| Hypothesis | Verdict | Evidence |
|---|---|---|
| The word-boundary clip shipped on 2026-09-21 was on the wrong path | CONFIRMED | `answer_layout.clip_to_word` is called from `record_label` and `summary_label`, which build the `cells` of a list row. The visible prose comes from `tail_sentences`, built by `build_structured_fallback_narrative`, which `clip_to_word` never touches. Hence a live run showing every fragment and zero ellipses |
| The tail render truncates a long multi-sentence value | RULED OUT | Driving the real `build_structured_fallback_narrative` and `run_grounding_pass` over a 1247-character summary returns all ten sentences, 1288 characters joined, claims 10 and stripped 0 |

## The one thing the smoke capture could not settle

Nothing. The capture placed the cut server side, and the remaining half was
settled by executing the shipped code offline rather than by instrumenting a
live run. That is why no `instrument.patch` accompanies this report.
