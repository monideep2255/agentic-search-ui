# Card 139 fresh verifier, after the fix round

Pull request #297, branch fix/card139-notes-say-what-is-true, fix round 60aaad16 after develop merge 0d780193. Fresh context, read and run only. Findings are appended as they are established.

## Findings

### V-139-01: A kind NCBI links whose summarised records all fail to become rows now gets no line at all, where develop gave a false "shows 10"
- Severity: unsure (inside the fix round, 60aaad16, `core/paper_links.py:172` `if shown == 0 or total <= shown`; I do not file it as "Regression of:" because develop's line in the same case is false, so the person is not worse off than on develop)
- What: when a kind's summary call returns records but none of them becomes a row (or the call fails), the branch says nothing about that kind. In the no-failure case there is no other note either, so a person who asked for sequence data sees SRA and assembly rows and no word that NCBI lists 1533 linked sequence records. Develop said "NCBI lists 1533 sequence records linked to PMID 11237011; this answer shows 10." over zero rows. The pre-fix branch (59965172) said the true "this answer shows 0".
- Reproduction: my probe (scratchpad `v139/test_v139.py`, real `plan_node`, `act_node`, `write_node`, classifier, NCBI and the LLM stubbed, realistic ESummary fields per kind), PICK=sequences, nuccore 20 linked of 1533, sra 3, assembly 8, nuccore ESummary records with empty `fields`. Branch: cites `{sra: 3, assembly: 5}`, notes "NCBI lists 8 genome assemblies linked to PMID 11237011; this answer shows 5." / "Note: no written summary could be checked against the records, so this answer lists the records found with their sources". Develop (`git archive origin/develop` bae47b6e into scratch, same probe): "NCBI lists 1533 sequence records linked to PMID 11237011; this answer shows 10." / "...listed below with their sources". With the nuccore summary call failing instead: branch keeps only "The background search of NCBI records did not finish, so this answer may be missing sources from it. Ask again to retry." (names no database); develop adds the false "shows 10" line above it.
- Why it matters: "A confident wrong record is worse than a missing one" favours the branch over develop. But the person loses a true fact (how many linked records NCBI holds of the kind they asked for), and the failure note does not name sequences. A line such as "NCBI lists 1533 ...; this answer shows none of them" would be true and say what exists. Owner wording call, not a merge blocker under "nothing worse than develop".
- NOT FIXED

### V-139-02: The no-zero rule is pinned by one unit arm, and that arm's last list check passes on an empty list
- Severity: minor (test gap inside the fix round, 60aaad16; the product behaves as intended in my probes)
- What: `tests/system_03_search_agent/core/test_paper_links_wiring.py` `test_a_kind_the_answer_shows_none_of_gets_no_count` is the only test that goes red when the `shown == 0` arm is removed. Its line `assert all("shows 0" not in note for note in graph_module._paper_link_notes(state, []))` checks an empty list (every kind shows none, so no note is returned) and would pass on a subject that returned nothing. The whole-path test `test_the_written_answer_counts_the_records_it_shows` never has a zero kind, so the Plan, Act and Write path does not pin the rule.
- Reproduction: scratch edit of `core/paper_links.py:172` to `if total <= shown:`, then the paper-link, completeness and eval-gate files: `1 failed, 52 passed, 1 skipped`, the failure at `test_paper_links_wiring.py:389` (the first list assertion, not the `all(...)` line). Restored by copy; `git diff HEAD --stat` empty.
- Why it matters: one arm guards the rule; if it is edited, "this answer shows 0" returns with the suite green.
- NOT FIXED

## Re-derived verdicts on the earlier findings

| Finding | Verdict | Evidence |
|---|---|---|
| J-139-01, cost-limit clause | Closed | `core/graph.py:10679` now ends "so it could not add the records it found the answer left out": no direction word, no pointer at the hidden "one further" note. The web UI hides only `/^Note: (?:one\|\d+) further /` (`frontend/src/components/screens/AnswerScreen.tsx:648`), so this note shows on screen and is true there: the completeness check found the omission before the repair hit the cap (graph.py:14696 to 14751). House style: one sentence, opens "Note:", no dash, no interior period. Mutation adding "as described above" to it: red (`test_a_cost_cap_hit_during_the_repair_is_disclosed`). |
| J-139-02, A-139-01, "shows 0" | Closed | Probe: nuccore summary failing or yielding no rows gives no nuccore count line on the branch. Break-it below goes red. V-139-01 records what the person loses. |
| J-139-03, A-139-02, two kinds and distinct pages | Closed | New arms `test_two_kinds_cited_together_are_counted_apart` and `test_two_citations_of_one_page_count_as_one_record_shown`. Probe: `all_data` six kinds, each "shows 5" over 5 cited pages each; baseline nuccore 5 and assembly 5 counted apart. |
| A-139-03, fallback overclaims over a stripped row | Open, not worse than develop | Probe, nuccore 5 linked of 1533, record 1002 titled "[3]": both trees ship 4 nuccore citations and "one further nuccore record ... not included in the list above". Branch: "this answer lists the records found with their sources" and "shows 4". Develop: "the records found are listed below with their sources" and "shows 10". Same overclaim, branch's count right. |
| A-139-04, saved copy present tense | Open, not worse than develop | `feedback/outage_note.py` and `feedback/history.py` are not in `git diff origin/develop...HEAD`; read only. |
| A-139-05, submitter title as a row | Open, not worse than develop | The row builder is not in the diff (diff touches only the note builders and `_paper_link_shown`); read only. |

## Card 128's note with this card's ordering

Card 128 (merged as bae47b6e, in this branch through 0d780193) says "Note: no written summary is shown, because the sentences written only repeated the records listed above". My probe (scratchpad `v139/test_v139_order.py`, card 128's own `_restating_reply` through the real `write_node`), all four depths: the note fires and lands after the last listing row in the token stream (note token 17, last row token 15; plain language 10 and 8), in the saved answer (`answer_markdown_from`: note offset 578, last row 530; plain 239 and 208) and on the command line (`Renderer`: 504 and 470; plain 374 and 340). So "listed above" reads true on those three. The web screen I read only (notes render after `listingBlocks`), and the three frontend note files pass.

## Break it

`core/paper_links.py:172` `if shown == 0 or total <= shown:` edited to `if total <= shown:` (puts "this answer shows 0" back): `1 failed, 52 passed, 1 skipped`, `FAILED test_paper_links_wiring.py::test_a_kind_the_answer_shows_none_of_gets_no_count` at line 389. Restored by copy. Two more wording mutations, each restored: the fallback note back to "listed below with their sources" goes red (`test_the_fallback_note_is_one_plain_line_with_no_blame`); "as described above" appended to the cost-limit clause goes red (`test_a_cost_cap_hit_during_the_repair_is_disclosed`). After all three: `git diff HEAD --stat` empty, `git status --short` shows only `?? frontend/node_modules`. No stash used.

## Runs

- `pytest test_paper_links_wiring.py test_write_completeness.py eval/test_write_step_eval_gate.py test_write_answer_structure.py test_write_answer_quality.py`: `134 passed, 1 skipped in 4.27s`
- `npx vitest run` on `useRunView.refusal.test.ts`, `answerNotesHidden.test.tsx`, `AnswerScreen.listingFirst.test.tsx`: `Test Files 3 passed (3)`, `Tests 21 passed (21)`
- `venv/bin/isort --check-only --diff src tests services tracker alembic .claude .github`: "Skipped 2 files", exit 0
- `venv/bin/ruff check .`: "All checks passed!", exit 0

## Branch against develop, same probe

Develop copied with `git archive origin/develop` (bae47b6e) into the scratchpad, never into the worktree. Same six scenarios on both trees:

| Scenario | Develop | Branch |
|---|---|---|
| nuccore 20 of 1533, sra 3, assembly 8 | "shows 10" over 5 nuccore rows; no assembly count | nuccore "shows 5", assembly "8 ... shows 5" |
| nuccore summary fails | false "1533 ... shows 10" plus the failure note | failure note only (V-139-01) |
| nuccore records give no rows | false "1533 ... shows 10" | nothing about nuccore (V-139-01) |
| only nuccore, its summary fails | refusal, "Ask again to retry" | identical refusal |
| all_data, six kinds of 500 | six "shows 10" over 5 rows each | six "shows 5" |
| all_data, gds summary fails | six "shows 10", gds among them over 0 rows | five "shows 5", no gds line, gds failure note names GEO DataSets |

## Verdict

PASS: nothing worse than develop. Every count the branch prints equals the rows and cited pages of that kind; develop's are false in every multi-record scenario. No note says "below" or "above" where it is untrue, on the three surfaces I drove. Two findings, both inside the fix round, neither a regression against develop: V-139-01 (unsure, a wording call for the owner: a kind shown as none is now silent where a true "shows none" line was possible) and V-139-02 (minor test gap).

Verified by my own probes: counts per kind against citations on both trees (six scenarios plus the stripped row); card 128's note placement in tokens, saved answer and command line at four depths; the cost-limit note's visibility pattern; three mutations each red; the gate commands. Read only: the web screen's render order, A-139-04 and A-139-05 (outside the diff), and the truth of "it found the answer left out" (from `write_node`'s repair flow, not driven).
