# Runner C: the command line, MCP, and the no-hand-test cards

- Run: 2026-09-29, about 22:00 to 22:25 local (2026-09-30 02:00 to 02:25 UTC).
- Develop API `/health` at 02:09 UTC: `{"status":"ok","app_env":"develop"}`.
- Develop web `/integrations` serves bundle `assets/index-CBcyVX6d.js`; its printed commands were read from that bundle and from `frontend/src/components/screens/InfoScreens.tsx` (identical text).
- Account: `s3-queries-c-20260929@example.com` (the one test account; password never printed).
- Code state read for Part 2: `origin/develop` (this checkout differs from it only in two docs files).
- Method: `s3` installed with the Integrations page's own install text into a throwaway venv under `<scratch>/retestC/`. Every `s3` call used `S3_BASE_URL` for develop and its own credentials file inside that folder. `s3 mcp` was driven over stdio by a small JSON-RPC script (initialize, tools/list, tools/call), which stands in for a desktop AI agent app. No agent app was available.
- Questions asked of the product: about 22, under the 40 limit.
- All evidence files are in this folder. Files named below are relative to it.

## Part 1

### Query 90: every command printed runs as printed

- PASS: install command as printed (`python3.11 -m venv s3-env`, `. s3-env/bin/activate`, `pip install "git+https://github.com/monideep2255/agentic-search-ui.git#subdirectory=clients/system3-cli"`) installed `system3-cli 0.1.0`, and `s3 --help` printed usage. The Mac's own `python3` is 3.9.6, so this is the case card 62 fixed. Evidence: `<scratch>/retestC/install.log`, also the bundle text.
- PASS: the page never tells you to `pip install s3` (grep of the deployed bundle: the only `pip install` lines are the `git+` one and the sentence about virtual environments).
- PASS: login line names develop. The page's line is `s3 login --base-url <API_ORIGIN> you@example.org`, and the deployed bundle's only API host is `search-agent-api-develop-43b3.up.railway.app`. After the password, `s3` printed "logged in to https://search-agent-api-develop-43b3.up.railway.app".
- PASS: second line `s3 ask "diseases linked to BRCA1"` printed a cited answer, `[answer]`, a trust line, and 23 reference lines. Evidence: `q90_second_line_ask.txt`.
- FAIL (doc is stale, page is newer): the bullet says the agent configuration names the command `s3`. Develop's page now prints `"command": "/path/to/s3-env/bin/s3"` (card 62's change, and query 101 says so). Evidence: bundle text, `InfoScreens.tsx` MCP_STDIO_CONFIG. The config carries `"args": ["mcp"]` and no token, which matches. Query 90's wording needs updating to query 101's.
- PASS: through `s3 mcp` over stdio, `tools/list` returned exactly four tools: ask_biomedical_question, list_past_searches, reopen_past_answer, send_answer_feedback. Evidence: `q90_mcp_initialize_toolslist.json`. Not done: asking a real agent app "What tools does system3 give you?" (NOT TESTABLE, no agent app).
- PASS: the MCP server card names the same four tools, says an account is required and that a bearer token lasts 15 minutes, and its own config carries `"Authorization": "Bearer <your token>"`. Evidence: deployed bundle strings.
- PASS: the Access notice says "GraphQL and the MCP server: an account is required, so a guest cannot reach either", and REST and SSE take a guest. Evidence: bundle string.
- NOT TESTED: the KGX copy button (marked Known in the doc; the page no longer prints a KGX install at all).

### Query 91: a question from the command line

- PASS: `s3 ask "Which diseases are associated with BRCA1?"` printed status lines (`[Koch | think]`, `[Koch | plan]`, one `[tool]` line per call), then the answer with [n] markers. Evidence: `q91_a_brca1.txt`. Took 13 s.
- PASS: `[answer]` on its own line, then the trust line "Based on 22 sources, not yet confirmed · High-risk claim". Never `[refuse]`.
- PASS: "References:" has one line per marker (22 markers, 22 lines), each with number, source and link.
- PASS with a note: every reference line has a link, but 6 of 22 are not on ncbi.nlm.nih.gov: one omim.org and five clinicaltrials.gov. The other 16 are on `ncbi.nlm.nih.gov` or `pubmed.ncbi.nlm.nih.gov`. The doc's words say "a link on ncbi.nlm.nih.gov"; the web cites the same non-NCBI links (see query 94).
- PASS: no line starts `[unresolved: marker`, and no `$` anywhere in the output.
- PASS: `--json` printed a single JSON object (whole file parses as one object) with answer, 23 citations each with `source_url`, `trust_outcome: "ask"`, `trust_line`, `session_id`, `"complete": true`, `unresolved_markers: []`. Evidence: `q91_b_json.out`, `q91_b_json.err` empty.
- PASS with a note: `s3 ask "What is the capital of France?"` printed exactly "guard: this looks outside biomedical research. Try a gene, variant, pathogen, or paper question." with no answer and no references. It also printed a second line on stderr, "s3: the run finished with no answer text and no citations; nothing was actually delivered even though the run did not fail.", and exited 1. Evidence: `q91_c_france.txt`. The doc does not mention the second line.

### Query 92: a one-word question

- PASS: `s3 ask "GERD"` printed the question back "What would you like to know about GERD?" and four numbered full questions. Evidence: `q92_a_gerd.txt`.
- PASS: then `[ask]` on its own line, never `[refuse]`.
- PASS: then "s3: to ask one of these, run: s3 ask --session-id 1df4244f... "<the question you pick>"".
- PASS: running it with choice 4 word for word ("Are there genes associated with GERD?") and that session id ran in the same conversation (the plan line resolved "GERD: 1 MedGen record matched by name") and returned a cited answer with 12 references. Evidence: `q92_b_choice.txt`.
- Note: `list_past_searches` (query 95) records the GERD question-back with trust "refuse", while `s3` prints `[ask]` for it.

### Query 93: another AI agent, and its follow-up (driven over `s3 mcp` stdio, not a real agent app)

Evidence: `q93_mcp_session.jsonl` (first attempt, then the retry, then the 15-minute question).

- FAIL as worded (the harness passed the whole sentence): when the doc's full first prompt ("Which diseases are associated with BRCA1? Show every citation with its link, the trust line and the session id.") was sent verbatim as the tool's `query`, the guard refused it: "it did not pass this system's content guardrail (the query contains an instruction directed at the system rather than a question about biomedical evidence)". A real agent normally passes only the question, and the retry below with the bare question worked. Worth knowing because a chatty agent may pass the whole sentence.
- PASS: with the bare question, `ask_biomedical_question` returned a cited answer with 23 citations, every marker (23 of 23) has a citation, `trust_line` "Based on 22 sources, not yet confirmed", and a `session_id`. No token or password was asked for; `s3 mcp` used the stored sign-in.
- PASS with a note: 6 of the 23 citations point off `ncbi.nlm.nih.gov` (omim.org, clinicaltrials.gov), the same as query 91.
- PASS: the follow-up "What variants cause it?" with the returned `session_id` answered about BRCA1's variants ("Found 40 sequence variant records for BRCA1, of 15350 available", 58 citations) without naming BRCA1.
- PASS: the same follow-up with the session id left out asked "which gene, variant or condition do you mean?".
- PASS: default depth is Researcher. The tool schema says "'researcher' is the default here; 'plain_language' is the everyday wording the web app uses by default".
- Note on speed: the follow-up took about 53 s (22:03:24 to 22:04:17), the first answer about 23 s.
- PASS: the question asked 16 minutes after sign-in (22:17, sign-in at 22:00:51, same `s3 mcp` process) with `audience_depth: plain_language` still worked: a cited answer, 23 citations, trust line "Based on 22 sources, not yet confirmed". `s3 mcp` reported on stderr "renewed the sign-in". Evidence: `q93_mcp_session.jsonl`, tags `after_15min_plain` and `stderr`.
- PASS with a note: the plain language answer opens in everyday words ("I found 4 conditions related to BRCA1", "Mutations in this gene are responsible for approximately 40% of inherited breast cancers"), but the "Where this answer comes from" list below it still carries the technical record titles (ClinVar variant names such as NM_007294.4(BRCA1):c.5243_5277+2788del, OMIM titles). Whether that reads as "everyday words" is the owner's call.
- NOT TESTABLE: the agent app's own behaviour (never asks you for a token, uses the tool by name), since no agent app was available. The known items (card 52, F-8.6-V10) were not tried.

### Query 94: the same records and trust line as the web

Question `Which diseases are associated with BRCA1?` at Researcher, three ways. Evidence: `q94_web_endpoints_events.json` and `q94_web_summary.txt` (the web's own endpoints, POST `/v1/query` then its SSE events), `q94_cli.json`, and `q93_mcp_session.jsonl` (tag `first_retry_question_only`).

- NOT TESTABLE as worded: the web app itself (no browser here). The stand-in is the same two endpoints the web's `frontend/src/lib/api.ts` calls, with `audience_depth: researcher`.
- FAIL (strict wording, small difference): the same records were not cited all three ways. The web endpoints and the agent cited the identical 21 unique records. The CLI cited 21 too, of which 19 are identical and 2 differ: web and agent cite pubmed 19168207 and 35432218, the CLI cites pubmed 28976962 and 34421362. All four differences are PubMed papers, one of the five literature rows. Disease, gene, ClinVar, MedGen, OMIM and clinical trial records are identical in all three. The count is the same, 21 unique, and 22 sources in the trust line.
- PASS: `trust_line` "Based on 22 sources, not yet confirmed" in the JSON, the agent result and the web's done event. The web's high-risk verdict sits in its answer-scope trust signal (`risk_tier: high`), and the CLI printed it as "High-risk claim" (query 91).
- PASS: `unresolved_markers` is `[]` in the JSON.

### Query 95: past searches through an agent (driven over `s3 mcp` stdio)

Evidence: `q95_mcp_session.jsonl`, `q95_reopen_q97_missing.jsonl`.

- PASS: asked the BRCA1 question, then `send_answer_feedback` with rating `down` and a comment: `{"recorded": true}`.
- PASS: `send_answer_feedback` with only `run_id`: refused with the message "nothing to record: send at least one of rating ('up' or 'down'), comment, flagged_reason or citation_flags. Any feedback already sent for this answer is unchanged". Starts with "nothing to record". (This was sent through the raw tool call; a real agent may decline it.)
- PASS: `list_past_searches` returned items newest first, each with `trace_id`, `question`, `asked_at`, `trust_signal`, `citation_count`, `has_saved_answer`. It included searches from `s3 ask`, the MCP session and one older search not made in this run. Default returned 16 (fewer than 20 exist). `limit: 2` returned 2. `limit: 51` was refused with "Input should be less than or equal to 50".
- PASS: `reopen_past_answer` on a saved search returned the answer with 22 citations, `trust_line`, `audience_depth: researcher`, `citations_omitted: 0`; no new search (instant).
- PASS: reopening a search with no saved answer (a GERD question back) returned "no saved answer for this search; ask it again to get a fresh one".
- NOT TESTED: the feedback retry note (Known), the 50-citation cap (Known), and whether the list held a search made in the web app in this run (none was made; the older entry could be from the web).
- Note: the list shows the question-back GERD search with `trust_signal: refuse`.

### Query 96: a guest gets no more than the web gives a guest

Evidence: `q96_guest.txt`. Each command used `S3_CREDENTIALS_PATH=no-sign-in.json` (a file that does not exist).

- PASS: `s3 ask "..."` printed "s3: not logged in; run 's3 login' first", exit 1, no answer.
- PASS: `s3 ask --json "..."` printed one JSON object with `"complete": false`, `"answer": ""`, and an error whose message is "s3: not logged in; run 's3 login' first".
- PASS: `s3 mcp` stopped at once with "s3: not logged in; run 's3 login' first", exit 1, printed nothing on stdout.
- PASS: the Integrations page's Access notice says the same (bundle string, see query 90).
- NOT TESTED: the web letting a guest search (query 1's job), and the guest-token MCP refusal (Known, developer side).

### Query 97: one account never sees another's searches

- NOT TESTABLE: it needs two accounts, A and B, and only one test account was given. The B-side bullets (B's list has no A search, B reopening A's trace id, then A again) were not run.
- PASS (the part one account can show): reopening a trace id that does not exist (`00000000-0000-0000-0000-000000000000`) returns "no saved answer for this search; ask it again to get a fresh one", the same words as a search with no saved answer. So the refusal reveals nothing beyond "not yours or not there". Evidence: `q95_reopen_q97_missing.jsonl`, tag `reopen_nonexistent`.

### Query 101: install and connect on the first try

- PASS: the card says it needs git and Python 3.11 and works on macOS and Linux (deployed bundle: "The install works on macOS and Linux and needs git and Python 3.11").
- PASS: the install command uses `python3.11`, and it succeeded here where the system `python3` is 3.9.6.
- PASS: in a second, fresh shell with a minimal PATH (`/usr/bin:/bin`), following the card's line `. s3-env/bin/activate` found `s3`, and `s3 --help` worked. Evidence: `q101_second_terminal.txt`. `s3 login` itself was done in the first shell; not repeated in the second.
- PASS: under a finished answer `s3` prints the web's trust line with "· High-risk claim" (query 91). A question the system asks back reads `[ask]` with no trust line (query 92).
- NOT TESTABLE by hand-timed interrupt: "A search you stop prints 'Not verified · the run did not finish'". Five Ctrl-C attempts at 4, 9, 11, 12.6 and 13.2 s each printed "s3: interrupted, stopping the run..." and "error: the run ended before a final answer was received", and no verdict. The notice is only printed when some answer text or citations already reached stdout. In each attempt the last output was still tool status lines (stdout empty in the saved last attempt), so the answer had not started. So the "never a confirmed verdict" half held; the exact words were not reached. Evidence: `q101_stop_sigint.txt`. Source of the condition: `render.py` `_write_unfinished_notice` in the installed package.
- PASS (with a limit): `s3 mcp --help` says "Point the agent at s3 by the full path that command -v s3 prints". "The agent app finds it": NOT TESTABLE (no agent app). The stdio driver started `s3 mcp` by full path successfully.
- PASS: the page prints no KGX install command; the card says "today a KGX file comes from the operator".
- PASS: a guest over MCP with no token was told "no bearer token on this request. The MCP server needs a System 3 account: sign in with POST /auth/login ... A token lasts 15 minutes.", never "malformed". Evidence: `q101_guest_mcp_call.txt`. (`initialize` itself answered 200; the tool call gave the message.)
- NOT TESTED: card 75 (Known).

## Part 2: Retest cards marked "Nothing to try by hand" (10)

Code read from `origin/develop`.

- Row 1, card 73 (a crashed search writes "search crashed, trace <id>" to the log): PASS. `src/system_03_search_agent/core/run.py:295` defines `_log_crash`; it is called first in both last-resort handlers, at `:747` (in `run`) and `:935` (in the streaming path), ahead of `_crash_fallback_events`, so what the screen shows is unchanged. The record's first line is `f"search crashed, trace {trace_id}"` at `:274`; the fallback if the record cannot be built logs "search crashed, trace %s: crash record could not be built" at `:325`. Not checked: a real crash in develop's log (the card says the reason sits on the lines below, per card 81).
- Row 12, card 3, T-8.6-07 (the second writing call runs only when it can change the answer): PASS with a caveat the owner should weigh. The gate exists: `core/graph.py:12208-12218` skips the repair call when `_code_built_lines_will_cite` (`:9063`) says the code-built lines will cite every omitted finding, and runs it when the model grounded nothing, a tool failed, or a sentence gets stripped. But the ledger records that T-8.6-07's own gate change was reverted (`tracker/phase_8.6.md:89`), its live acceptance "one writing call each on G-012, G-013, G-021, G-024" was not met (`:73`) and was called moot (`:109`); the gate that stands is the 2026-09-14 one, with a note at `graph.py:9096-9109` on why the folding was reverted. So "only when it can change the answer" holds by design, but the ticket's stronger claim does not.
- Row 13, card 34, T-8.6-03 (Jev's and DeepSeek's picks compared offline): PASS. `testing/Developer/scripts/compare_classifiers.py:1-9` says no live path calls it or `compare_models`; `git grep compare_models origin/develop -- src` names it only in `harness/decide.py` (`:50`, `:539`, `:600`); `decide.py` header says the guard tier is asked only after a Jev failure. A run exists: `testing/Developer/reports/2026-09-26_phase_8.6/classifier_comparison.md` ("Decisions asked: 18; compared, both models asked and returned: 18").
- Row 18, Jev and the comparison table: PASS. `testing/Developer/reports/2026-09-25_phase_8.2_golden/decisions_comparison.md` lines 1-13: a table over the 150 golden runs with "Made by Jev" and "Both models picked / Agreed" columns (e.g. plan.literature 116 of 117 made by Jev, 32 of 36 agreed). Not checked live: that develop's `CLASSIFIER_PROVIDER` is `jev` right now (the file says it was for that run).
- Row 19, card 9, the function catalogue: PASS. `src/system_03_search_agent/tools/catalogue.py`: `get_catalogue()` returns 17 typed actions across all 7 tools, sorted by name, each built from the tool's own input model; `tests/system_03_search_agent/tools/test_catalogue.py` ran 6 passed. `resource_options()` lists the 7 tool names.
- Row 20, golden row G-035 accepts the Taxonomy link: PASS. `eval/golden/golden_dataset.json:1357` has `"https://www.ncbi.nlm.nih.gov/taxonomy/562"` in G-035's `must_cite` (commit `364e2b92` replaced the old `Taxonomy/Browser/wwwtax.cgi?id=562` link). `ncbi_efetch_schemas.py:186` says the product cites `/taxonomy/562`.
- Row 21, the graph data gaps handed over: PASS on the document. `docs/data-engineering/Graph_data_hand_over_2026-09-25.md` (170 lines) names four gaps with measurements, dates and what is being asked. Not verifiable here: that the other repository received it (a search of `reference/agentic-search-data-engineering` found no copy or mention).
- Row 22, the four type values: PASS. `docs/build/design/design-system/foundations/type.html:39-41` and `frontend/src/theme.ts:160,161,164` agree: h1 `clamp(32px, 4.8vw, 52px)` with `-0.034em`, h2 `clamp(24px, 3.1vw, 33px)`, body1 line-height 1.65.
- Row 23, `/phase-checkpoint` names the counts line by what it holds: PASS. No `line 31/32` reference remains in `.claude/` or `CLAUDE.md` (grep empty); the counts line itself has since been retired: `.claude/skills/phase-checkpoint/SKILL.md:85` and `:251` say counts are computed on demand and stated in no document.
- Row 27, an NCBI outage no longer turns the build red: PASS. The live MedGen test `test_a6_pinned_ground_truth_still_matches_live_medgen` in `tests/system_03_search_agent/core/test_answer_readability_premise.py:368` carries `@pytest.mark.integration`; the unit gate runs `pytest -m "not integration"` (`.github/gates/gate04_unit_suite.sh:6`). Ran it: `-m "not integration" --collect-only` gives "5/6 tests collected (1 deselected)" and the deselected one is a6; `-m integration` selects it.

## Summary

| Item | Passed of total | Verdict |
|---|---|---|
| Query 90, printed commands | 7 of 8 | FAIL on one bullet: the doc says the agent config's command is `s3`; the page now prints a full path (doc stale). Agent-app half NOT TESTABLE |
| Query 91, one question from the command line | 7 of 7 | PASS (two notes: 6 of 22 links are not on ncbi.nlm.nih.gov; France prints an extra stderr line) |
| Query 92, one-word question | 4 of 4 | PASS |
| Query 93, another agent and its follow-up (over `s3 mcp` stdio) | 6 of 7 | FAIL on one bullet: the doc's verbatim first prompt, sent whole as the tool query, is refused by the guard; the bare question passes. Agent app behaviour NOT TESTABLE |
| Query 94, same records as the web | 2 of 3 | FAIL (small): web and agent cite identical records; the CLI run differed on 2 of 21 PubMed papers. Real web app NOT TESTABLE, endpoints used |
| Query 95, past searches through an agent | 5 of 5 | PASS |
| Query 96, a guest gets no more than the web | 4 of 4 | PASS |
| Query 97, one account never sees another's | 1 of 1 run, 4 not run | NOT TESTABLE: needs two accounts |
| Query 101, install and connect first try | 7 of 8 | NOT TESTABLE on the stop notice ("Not verified · the run did not finish": 5 interrupts never reached it) and on the agent app finding `s3`; the rest PASS |
| Part 2, ten no-hand-test cards | 10 of 10 | PASS, row 12 (card 3) with a caveat: T-8.6-07's own gate was reverted, the older gate stands |

