# Card 18 judge: one row per record

Judge round, 2026-10-16, pull request #258, branch `fix/card18-one-row-per-record`, commit `4469c901` on develop `78c68c1c`. Code, tests and local probes only; no live run, no model call. Paths are relative to `<repo-root>`; probes sit in `<scratchpad>/card18_judge/`.

## Table of contents

- [What the change does](#what-the-change-does)
- [Findings](#findings)
- [Checks](#checks)
- [Break it](#break-it)
- [Tests run](#tests-run)
- [Verdict](#verdict)

## What the change does

In the inner `merge_into` of `_answer_parts` (`src/system_03_search_agent/core/graph.py:13200` to `13208`), when the joined text would pass 1000 characters, a repeat that adds no marker now folds into the first row with the first row's text kept as is; a repeat that adds a marker still stays its own row. The `len(ids) > 20` skip is unchanged.

## Findings

| Id | Severity | Worse than develop | Finding |
|---|---|---|---|
| J-18-01 | major | Yes, on MCP and GraphQL | The folded sentences also vanish from the MCP and GraphQL answer text, two surfaces the owner's decision does not name |
| J-18-02 | major | No (inside the decision's words), but the owner decided on an understated cost | For a real abstract the loss is every sentence past about 1000 characters, not "one repeated sentence" |
| J-18-03 | minor | No | The new marker guard has no test that goes red; a same page test can be built, contrary to the build report |
| J-18-04 | minor | No | The comment above `merge_into` still claims both sentences stay in the row's text |

### J-18-01: MCP and GraphQL lose the folded sentences

- MCP builds its answer from token text only: `raw_answer_text = joined_text(answer_parts).strip()` (`src/system_03_search_agent/adapters/mcp/server.py:1270`); `grep -n "cells\|table_row" adapters/mcp/server.py` returns nothing, so a row's text is the only thing MCP shows of it.
- GraphQL does the same: `answer_text = joined_text(acc.answer_parts).strip()` (`src/system_03_search_agent/adapters/graphql/fold.py:1103`), and also never reads `cells`.
- The owner's decision names only three surfaces: "the command line prints the record's first sentences and not the later one. No citation is lost, and the web and saved answers lose nothing." The diagnosis's surface table ("What each surface prints after the fix") lists web, saved answer and command line only; MCP and GraphQL are absent, so the owner was not asked about them.
- Probe `<scratchpad>/card18_judge/probe_surfaces.py`: two PubMed papers, each with a 16 sentence abstract (about 122 characters a sentence), through `_answer_tokens` and `contracts.token_order.joined_text` (what MCP and GraphQL return before their 8000 character cap):

| Code | Depth | Rows | Joined text characters | Abstract sentences in the text |
|---|---|---|---|---|
| Develop `78c68c1c` | Researcher | 4 | 3926 | 32 of 32 |
| Branch `4469c901` | Researcher | 2 | 1974 | 16 of 32 |
| Develop | Plain language | 4 | 3934 | 32 of 32 |
| Branch | Plain language | 2 | 1982 | 16 of 32 |

- Why it cannot be fixed inside the card's fence: the token text cap is 1000 (`contracts/events.py:396`) and these surfaces read nothing but text, so any fold that keeps one row drops the rest of the text for them. Keeping it needs the diagnosis's option B (an event contract change, dial 3) or an owner decision that extends option A to MCP and GraphQL.
- Mitigation worth stating to the owner: both caps are 8000 characters (`adapters/mcp/server.py:202`, `adapters/graphql/types.py:173`), so on develop a five paper answer with long abstracts is often already truncated on these surfaces; the branch may let more papers fit. No citation is lost on either surface; the citation list is unchanged.

### J-18-02: the cost the owner accepted was stated as one sentence

- The diagnosis says "The cost is one repeated sentence about a paper already listed in the command line", and the decision reads "not the later one".
- The listing renders one finding per record, and that finding is usually the abstract, every sentence carrying the record's one marker (`synthesis/findings.py:1057` docstring and loop; `one_finding_per_record` docstring measured abstracts of "16, 8, 21, 32 and 6 sentences").
- So on the branch the command line, MCP and GraphQL print a paper's abstract only up to the first about 1000 characters; the probe above drops 8 of 16 sentences per paper. On develop all of them print, across repeated rows.
- This is inside the decision's words ("prints the record's first sentences"), so I do not count it as worse than develop for the command line. It is filed so the lead can tell the owner the measured size when asking J-18-01.

### J-18-03: the marker guard is not under test

- Mutation `no_guard` (delete `if len(ids) > len(first.token.marker_ids): continue` at `core/graph.py:13206` to `13207`, keep `text = first.token.text`): the three new tests stay green. Output: `3 passed, 51 deselected in 29.17s`.
- The third test cites `pm-2` on a different URL (`_pubmed_row_tokens` gives each marker its own PMID), so the two rows have different page keys and `merge_into` never reaches the guard. The build report says a same page repeat with a new marker "cannot be built from the fallback sentences alone"; it can.
- Probe `<scratchpad>/card18_judge/probe_same_page.py same_title`: two citations `pm-1` and `pm-2` on one PubMed URL, both field `title` with the same value, sentences `a*430 [1]`, `c*430 [1]`, `b*430 [2]`:

| Code | Researcher rows (text length, markers, count of "[2]" in text) |
|---|---|
| Branch | (872, pm-1, 0), (436, pm-2, 1) |
| Branch with the guard deleted | (872, pm-1 and pm-2, 0) |
| Develop | (872, pm-1, 0), (436, pm-2, 1) |

- With the guard deleted, citation `[2]` stays on the row's chips but its number leaves every printed text. A test of this shape would go red on that mutation. Not worse than develop: the code as committed keeps the guard and behaves as develop.

### J-18-04: the comment above `merge_into` is now false

- `core/graph.py:13174` to `13179` still reads: "both grounded sentences in the row's text, so a surface that prints the text (the command line) still prints every number. When the merge cannot keep all of that, the repeat stays its own row, as before card 104."
- The new branch at `13203` to `13208` folds a repeat without its sentence, so "both grounded sentences in the row's text" no longer holds, and the repeat does not stay its own row. The "every number" half still holds on the fold path, because the fold requires no new marker. Review rounds: a comment that claims a property must be tested or corrected.

## Checks

| Question from the brief | Result | Evidence |
|---|---|---|
| Acceptance: one paper on one row even with a long abstract | Met for repeats with the record's own marker | `test_long_abstract_sentences_of_one_record_are_one_row` red on develop (`assert 2 == 1`), green on branch; probe table above, 4 rows to 2 |
| Is "adds no citation" exact when tested by count | Yes | `ids = list(first.token.marker_ids)` then append only `if marker not in ids` (`core/graph.py:13195` to `13198`), so the length grows if and only if a new marker, sentence or linked, was added. Reordering cannot matter: `in_citation_order` runs after the guard (`13209`). Duplicates in the first row's list (possible, `marker_ids` at `13086` does not dedupe) are copied, so equality still means nothing new |
| Mapping path, linked disease ids | Safe | `mapping_cell(...) != merged[at]` skips first (`13192`); `linked` is computed from the merged fields (`13194`) and joins `ids` before the guard, so a repeat bringing a new disease skips and stays its own row |
| Citation and checked words (`claim_text`, card 57) | Unchanged | Listing citations are built from the grounding claims before `_answer_parts` runs (`core/graph.py:14147` to `14149`); no code path reads row text back into a citation |
| Saved answer | Loses nothing | `answer_markdown_from` prints a row's cells and markers, never its text (`feedback/capture.py:214` to `240`); probe markdown on the branch is develop's minus the duplicate rows |
| Web | Loses nothing | Row shows cells and chips (diagnosis, `AnswerScreen.tsx:532` to `538`) |
| Command line | First sentences only, as decided | `_handle_token` writes `payload.text` (`adapters/cli/render.py:876` to `896`); the References block lists every citation (`render.py:1113`), so no number is lost there |
| Builder's note on the third test | Confirmed and widened | J-18-03 |
| Ruff | Clean | `ruff check` on both files and with no path: `All checks passed!`. `ruff format --diff` hunks in both files are the same as develop's and none touch the new lines |

## Break it

| Mutation (one property, every symbol kept) | Result |
|---|---|
| Restore develop's skip (`len(ids) > 20 or len(text) > 1000`) | Red: `test_long_abstract_sentences_of_one_record_are_one_row`, `assert 2 == 1` |
| Drop `text = first.token.text` | Red: same test, `AssertionError: assert 1308 <= 1000` |
| Drop the marker count guard | Green, 3 passed: J-18-03 |

Each mutation was applied by `<scratchpad>/card18_judge/mutate.py` and the file restored with `git checkout`; `git status --short` is empty.

## Tests run

- `pytest -q tests/system_03_search_agent/core/test_write_answer_structure.py`: `54 passed in 18.40s`.
- Neighbours (answers sooner, breadth wiring, saved answer capture and placement, command line render, paper links, findings tail, readability, repair listing, MeSH answer, completeness, label only sentence, card 17 order, isolate wiring, answer quality, streaming premise and mutation): `350 passed, 4 skipped in 47.97s`.

## Verdict

J-18-01 shows MCP and GraphQL readers less of a paper's abstract than develop shows, a loss the owner's decision does not name, and the card's approach cannot keep that text inside its fence. If the owner extends the decision to every text only surface (command line, MCP, GraphQL), told the measured size in J-18-02, nothing else here is worse than develop, and J-18-03 and J-18-04 are one round fixes (add the same page test, correct the comment).

VERDICT: FAIL
