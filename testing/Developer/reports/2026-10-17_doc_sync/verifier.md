# Verifier report: documentation sync, 2026-10-17

Fresh verifier for branch `chore/doc-sync-2026-10-17` at 0192e9d0, seven commits on develop 4eab6dd6. Findings are written as each is established, ids V-DS-01 and up. The verifier fixes nothing.

## Findings

### V-DS-01: checklist item 1, no loss in LEARNINGS.md: PASS with two minor findings (V-DS-02, V-DS-03)
- Method: own script, not the author's. Rows matched by `^\|\s*\d{4}-\d{2}-\d{2}` (a stricter `...\d{2}\s*\|` misses the `2026-08-10/11` row, so the looser form is used). Each row normalised by removing `\|`, `<summary>...</summary>`, `<details>`, `</details>` and the cell pipes, then compared as a multiset, old (`git show 4eab6dd6:LEARNINGS.md`) against the branch.
- Output: `old rows 253 new rows 253`, `missing 0 added 0`.
- Non-row lines of the old file absent from the new one: one blank line; the "Index by theme" intro and its seven bullets (the intended index rewrite, item 2); the Entry detail intro sentence that said "every entry above". Nothing else. A per-theme date check shows no date dropped from any of the seven old bullets (`lost dates: []` for each).
- Structure of the branch file: first dated row line 756, last line 1008, 253 rows, no non-table line inside the block, `## Lessons` (line 747) is the last `##` heading, no line after the last row, rows in non-decreasing date order (old file had three inversions at old lines 84, 93, 869, now gone). `<details>` 506, `</details>` 506; every row has five cells, and cells 4 and 5 each start with `<details><summary>what was tried</summary>` / `<details><summary>what fixed it</summary>` and end with exactly one `</details>` (0 bad rows).
- Note: the learnings report says 253 rows in its comparison against 468e8898; that matches.

### V-DS-02: Entry detail intro still says "matching the table above", and the table is now below
- Severity: minor
- What: commit a157c02f rewrote the one "above" sentence's first half ("every entry above" became "every entry in the Lessons table") but kept its last clause. LEARNINGS.md line 38 on the branch ends "In date order, oldest first, matching the table above." The Lessons table now starts at line 747, below Entry detail.
- Reproduction: `git show 0192e9d0:LEARNINGS.md | sed -n 38p` prints the sentence ending "matching the table above."; `grep -n '^## Lessons' ` prints 747.
- Also not strictly true: Entry detail keeps the old order (a 2026-08-05 entry at line 352 before 2026-08-04 entries at 360 to 376), while the table is now strictly date-ordered, so "matching the table" no longer holds for those entries either.
- Why it matters: a reader following the sentence scrolls up for a table that is at the end. Small, but it is the exact sentence the brief named as the one allowed change, and the change left it half stale.
- NOT FIXED

### V-DS-03: 83 rows and the file intro point "below" to Entry detail, which is now above the table
- Severity: minor (unsure whether the owner treats row text as untouchable here; the rows themselves cannot be reworded, but the intro can say so)
- What: 83 rows end "Full account below." and line 7 says every later entry ends with "Full account below," a pointer into Entry detail. Moving the table to the end of the file put Entry detail above every one of those rows. The intro was not updated to say the pointer now reads upward.
- Reproduction: `grep -c 'Full account below' LEARNINGS.md` gives 83; Entry detail heading is line 36, first dated row line 756.
- Why it matters: every one of those 83 pointers now sends the reader the wrong way. A one-clause note in the intro or the Lessons intro would make it true without touching a row.
- NOT FIXED

### V-DS-04: checklist item 2, the theme index: PASS with one minor finding (V-DS-05)
- Coverage, own script: every row date appears under at least one theme (`row dates not in any theme: []`), and no theme lists a date with no row (`index dates with no row: []`).
- Sample of 30 rows dated after 2026-08-21, read against the theme(s) that list their date (LEARNINGS.md line numbers on the branch): 869 ESummary "already inside" claim, written claim; 870 NCBI `status` in three shapes, live sources; 871 refusal on two channels, check vs user gap; 873 four mutations that did not mutate, assertions; 875 and 876 `railway up`, environment; 878 "passed" vs "did not run", assertions; 882 overstated headline finding carried into a commit and a decision row, written claim; 884 "verified locally" with a `.env` CI lacks, environment; 885 TEXT gate, assertions; 909 checks that name something, silent tooling; 910 wall-clock `no_done` called a product defect, measurement misread; 916 wrong code comment, written claim; 917 minus-strand placement, live sources; 919 pipe exit code of `tail`, silent tooling; 922 `[ACCN]` not resolving, live sources; 932 row inserted mid-row, scripted edits; 937 workers spawning children, agents outside role; 938 and 939 cut at a full stop and verbatim moves, scripted edits; 940 agent report says the lessons were placed, written claim; 941 MedGen 500 vs "zero failures", measurement misread; 959 new machine suite, environment; 961 review output in a cleared temp folder, lost work; 963 verifier quoted a home-folder prefix, private data; 982 iCloud eviction, environment; 985 brief restating a rule from memory, written claim; 996 to 1000 session limits, worktree `--force`, two pairs in one file, deleted parked tag, lost work and two writers; 1003 diff against a moved base, scripted edits; 1007 HEV acronym, live sources. All fit except 1006, below.
- Rows that fit only loosely but whose date is covered: 942 (kanban restructure) under check vs user gap; 995 (lead finishing a rejected branch) under written claim; 1001 (safety check blocking an approved permission) under environment.
- The seven new themes: each lists between 4 and 17 dates and names one shared failure (lost work on stop or clean-up; live sources unlike their documentation; a measurement misread; a written claim trusted; scripted edits capturing the wrong text; agents outside their role; private data in evidence). None restates an older theme.
- Counts: no row count is stated. Numerals left in the index are "up to an eleventh" (a dated fact kept from the old text), "three shapes" (an NCBI field), and "more than one theme". The "about 79 dated rows" and the two ranking claims are gone.

### V-DS-05: the 2026-10-17 fix-round row is not listed under "A fix round introducing the defect the next round finds"
- Severity: minor
- What: row 1006 (2026-10-17, "A fix brief that dictates prompt wording, card 125's fix round") records a defect planted by a fix round's own brief and found by the next reviewer, and says "Inside the fix commit, so the attempt closed with no third round". That is the fix-round theme by its own definition. The theme's dates end at 2026-10-15; 2026-10-17 is listed under five other themes, none of which describes this row (closest is "A written claim trusted over what it describes", which it fits only loosely).
- Reproduction: `grep -n '^- A fix round' LEARNINGS.md` shows the date list ending "2026-09-29, 2026-10-15."; `sed -n 1006p LEARNINGS.md` shows the row.
- Why it matters: the theme the repository names as its most repeated failure misses its newest instance, so a reader filtering on it before a fix round will not see the card 125 lesson.
- NOT FIXED

### V-DS-06: the drift check passes a LEARNINGS.md or DECISIONS.md with every `</details>` removed
- Severity: minor (unsure how it renders: a browser usually closes the element at the cell's end, but the learnings writer treated an unclosed dropdown as a fault and repaired 28 rows of them by hand, found by a separate scan, not by the check)
- What: `check_append_only_table` tests only `"<details>" in cells[idx]` (tracker/check_doc_drift.py, the wrapper loop after the column count test). It never looks for `</details>`. The repair in a157c02f is therefore not protected: the next row appended without its closing tag passes.
- Reproduction, in my own detached worktree at 0192e9d0:
  - Last row's final `</details>` removed (line 1008): `ok: 2 facts computed | 0 could not be computed | 0 stale | 0 structural`, rc 0.
  - `sed 's#</details>##g'` over the whole of LEARNINGS.md (`grep -c '</details>'` then 0): same `ok` line, rc 0.
  - The same over DECISIONS.md: same `ok` line, rc 0.
- Why it matters: the brief asked whether an unclosed `<details>` can still pass; it can, in any number. This is the same class the commit message itself names ("an instruction is not enforcement").
- NOT FIXED

### V-DS-07: checklist item 3, the drift check rule (111c8066): PASS on its stated property, with V-DS-06 and V-DS-08 as gaps
- Against develop's file (develop's LEARNINGS.md written into my own worktree at 0192e9d0, branch script): rc 1, `error: 2 facts computed | 0 could not be computed | 0 stale | 141 structural`; 140 lines of the form `LEARNINGS.md:N: dated row after the table`, plus `LEARNINGS.md:152: text follows the table's last row`. So all 140 stray rows are reported.
- Against the branch: `ok: 2 facts computed | 0 could not be computed | 0 stale | 0 structural`, rc 0.
- Baseline `tests/tracker/test_check_doc_drift.py`: `36 passed`.
- Mutations of the rule, each restored with `git checkout` and `git status` clean after:
  - M2, the whole-file scan stops at the first heading after the table: 3 failed (`test_a_dated_row_after_the_table_in_another_section_fails[DECISIONS.md]`, `[LEARNINGS.md]`, `test_a_row_glued_to_a_paragraph_in_a_later_section_fails`).
  - M3, the "text follows" loop disabled: 2 failed (`test_text_after_the_table_fails[DECISIONS.md]`, `[LEARNINGS.md]`).
  - M4, no upper bound on the in-table range: the same 3 failed as M2.
  - M5, no lower bound (rows before the header accepted): 1 failed (`test_a_dated_row_before_the_header_fails`).
- The unclosed `<details>` question: yes, it passes, filed as V-DS-06.

### V-DS-08: a stray row written `|2026-...` or `|  2026-...` in another section passes the new rule
- Severity: minor
- What: `DATED_ROW_RE = re.compile(r"^\| \d{4}-\d{2}-\d{2}")` demands exactly one space after the pipe. The new whole-file scan therefore never sees a dated row written with no space or two spaces, and markdown renders both as table rows or loose text exactly as it does the one-space form.
- Reproduction, my worktree at 0192e9d0, one line inserted after `## Recurring patterns` (no header copy):
  - `|2026-10-18 | area | broke | <details>...</details> | <details>...</details> |` gives `ok: ... 0 structural`.
  - `|  2026-10-18 | ...` gives `ok: ... 0 structural`.
  - Control, `| 2026-10-18 | ...` gives `LEARNINGS.md:717: dated row before the header`, `1 structural`.
  - The same no-space row appended at the end of the file is caught, but only by the "text follows" rule, with a message that does not say it is a row.
- Why it matters: the rule exists because an instruction to writers failed; it depends on the writer using the exact spacing. No existing row uses another spacing today (0 in both files), so this is a gap, not a present defect.
- NOT FIXED

### V-DS-09: the learnings skill still says to add a detail section "below the table", which the new rule now fails
- Severity: major (inside this branch's own change: commit a66b39d1 edited the same "Entry format" section, eight lines above, and left this instruction contradicting it)
- What: `.claude/skills/learnings/SKILL.md` line 63 on the branch: "When the table cell is too small for the fix: add a detailed section below the table, under a heading matching the date and topic." The table is now the last section of the file, and 111c8066 fails any text after its last row. Entry detail, where such sections live, is now above the table.
- Reproduction, my worktree at 0192e9d0: appended `### 2026-10-18 - Example detail section` and one line after the last row of LEARNINGS.md, then `tracker/check_doc_drift.py --check` printed `LEARNINGS.md:1010: text follows the table's last row: the table must be the last thing in the file, so that an append lands inside it` and `error: ... 1 structural`.
- Why it matters: a writer following the skill to the letter gets a red check, and the likeliest "fix" for a writer under time pressure is to move the table or the text in a way that breaks the new structure. The branch's claim that the skill and the check "say one consistent, true thing" does not hold for this line.
- NOT FIXED

### V-DS-10: checklist item 4, skill and registry wording (a66b39d1): FAIL, on V-DS-09
- The four edited statements are each true against my probes of the check: the learnings skill's new fourth failure (a dated row outside the table) fires (V-DS-07); `/phase-checkpoint` Step 1b and Step 7, `/ship` Step 0 and `/precommit` say the same thing.
- Not consistent: the learnings skill's own "add a detailed section below the table" (line 63) now fails the check (V-DS-09).
- Incomplete, minor: the learnings skill says the check "fails on four things"; it fails on a fifth, text after the table's last row, which is exactly what the line-63 instruction produces. No other skill names that fifth failure except through `/phase-checkpoint`'s "confirm the new row is the last line".
- `python3 tracker/check_living_docs.py --shape` on the branch: `living documents: 20 rows, shape as registered`, rc 0. Mutation: renaming `## Lessons` to `## Lessons table` gives `LEARNINGS.md: anchor '## Lessons' is in the registry but not in the file`, rc 1, so the new pin is live. It pins presence only, not order: the "last section" property is enforced by the drift check, not by `--shape`.

### V-DS-11: docs/README.md still says the security guide is a symlink into the owner's private repository, after the last commit made it a regular file
- Severity: major (inside this branch's newest change: 0192e9d0 replaced the symlink but did not update the one document that describes it, and 3ec6c46e edited that very sentence's first half on the same branch)
- What: `docs/README.md` line 106 on the branch: "It is also a symlink into the owner's private reference repository rather than a real file here, so it resolves only on a machine with that repository checked out alongside this one, and will dangle in a fresh clone or in CI." `git ls-files -s docs/Claude_security_plugin_usage.md` gives `100644 6dc31ac7...`, an ordinary file.
- Reproduction: `git show 0192e9d0:docs/README.md | sed -n 106p`; `git ls-files -s docs/Claude_security_plugin_usage.md` at 0192e9d0.
- Why it matters: the public folder index tells every reader the guide is missing from a fresh clone and that the owner has a private repository behind it, both now untrue; and it is the exact fact the privacy commit changed. The reason the file "cannot move" still holds (the locked specification names the path), so only the second sentence is stale.
- NOT FIXED

### V-DS-12: checklist item 5, canonical and reference edits (3ec6c46e, 4bcc5efc): FAIL, on V-DS-11
Changed statements checked against the code or repository, each with what I ran (all at 0192e9d0 in my own worktree):

| File | Statement | Evidence | Result |
|---|---|---|---|
| CLAUDE.md | Tools live in `src/system_03_search_agent/tools/` | `ls` lists the seven named modules there; `system_03_search_agent/` at the root does not exist | true |
| CLAUDE.md | The seven tools are BUILT, phases 2.1 and 3.1 to 3.5 merged | `git log --merges develop --grep` finds a merge for each of 2.1, 3.1, 3.2, 3.3, 3.4, 3.5 | true |
| CLAUDE.md, README.md | Layer 1 via a read-only HTTPS graph query service (4.11) or psycopg2 | `tools/graph_connection.py` dispatches on `GRAPH_QUERY_URL`, else `psycopg2.connect` (line 347); `services/graph_query_service/__init__.py` says build phase 4.11; 4.11 merged as PR #55 | true |
| README.md | `orchestrator/` is the few-shot routing pool, loaded once per process | `orchestrator/__init__.py` docstring and `few_shot_pool.py` | true |
| README.md | New tree entries `eval/` (src), `tour/`, `services/`, `clients/`, `eval/`, `visualizations/`, `HANDOFF.md`, `CHANGELOG.md` | each exists; `src/.../eval/` holds `dataset.py`, `rubric_grader.py`, `hard_fails.py`, `cost_report.py` | true |
| README.md | A push that changes only Markdown runs no workflow | `ci.yml` line 62, `paths-ignore: "**.md"` under `push`; the comment says a pull request is never filtered | true |
| README.md | The reference docs table is in `.claude/README.md` | `--shape` pins `## Reference docs (in docs/)` there and passes | true |
| .claude/README.md | Section 25 has 4.8 to 4.10, added after they were built | Technical specification lines 3227 to 3229 | true |
| .claude/README.md | Search and conversation behaviour has five situations | that file, line 3 and `## The five situations` | true |
| .claude/README.md | PreToolUse hooks include a source-write secret scan and a sensitive-file read block | `.claude/settings.json`: `scan-write-secrets.sh` on Edit or Write (its header: config and source files), `block-sensitive-read.sh` on Read and Bash | true |
| docs/README.md | Runbook and hand-over listed under `data-engineering/`; `build/README.md` exists; the fallback note is gitignored, not in the repository | `ls docs/data-engineering/`; `git check-ignore -v` gives `.gitignore:74`; `git ls-files` has no such file | true |
| docs/README.md | The security guide "is also a symlink into the owner's private reference repository" | `git ls-files -s` gives mode 100644 | FALSE, V-DS-11 |
| Model_architecture.md | Eleven new line references (`tiers.py:72,73,74,192,241`, `harness.py:403,534,667,952`, `graph.py:820`, `cost_control.py:536`) | `sed -n` on each line shows the named symbol | true, all eleven |
| Model_architecture.md | `ClarifyChoices`, `Harness.call_cost_bound_usd`, glm-5.2 priced at $0.037 and $7 per million | `clarify.py:98`, `harness.py:872`, `tiers.py:172` `(0.000000037, 0.000007)` | true |
| Debugging_guide.md | `env.example` declares 43; `CLASSIFIER_PROVIDER` read in `decide.py`; `JEV_MODEL`, `LOOP_STALL_WATCH`, `MCP_ALLOWED_*`, `GRAPH_BOX_HOST` readers; `OPENROUTER_API_KEY` read directly for Jev | `grep -cE` gives 43; `decide.py:342` is the only environment read of `CLASSIFIER_PROVIDER`; `git grep` matches each named reader | true |
| Agent_mods.md | `omim.org` is not reported because it is acknowledged | `mod-citation-drift/hooks/config.ts:61` | true |
| Plan.md, UI_fixes_done.md | Repaired anchors | `#### Detail 11.29`, `11.32`, `11.38` in `UI_fix_plan.md`; Plan.md line 866 heading slugs to the new anchor | true |

- CLAUDE.md changes facts only: the stack line, the tool status cell, the Layer 1 access wording (twice), the tools path and the date. No rule, working agreement or instruction changed (diff read in full).
- AGENTS.md: `sync-agents-md.sh --force` in my worktree left `git status` clean, and `diff <(tail -n +4 CLAUDE.md) <(tail -n +4 AGENTS.md)` is empty. Control: appending a line to AGENTS.md and rerunning the hook printed `Synced AGENTS.md from CLAUDE.md` and restored it, so the clean result is not a hook that did nothing.
- Unsure, not filed as a finding: Project_overview_A_to_Z.md's repaired link now points at this repository's `README.md#cost-model`, whose table says about $35 a month for the graph host including tax, while the sentence linking to it says roughly $30. The sentence came from the data engineering repository and was not changed.

### V-DS-13: the cleaned security guide still names a plan product, which its decision row says was removed
- Severity: minor (unsure: whether a plan tier name counts under the vendor rule is the owner's reading)
- What: the 2026-10-17 DECISIONS.md row says the guide's text was kept "with its employer-internal references ... and model and plan product names removed". `docs/Claude_security_plugin_usage.md` line 24, the tools table, still says `| Code Review | At pull request time | Team or Enterprise plans only |`, which names the vendor's paid plan tiers and a vendor product ("Code Review"). The title and the plugin names (`claude-security`, `claude-plugins-official`) are real names and the canonical report lists them for the owner, so they are not part of this finding.
- Reproduction: `grep -n -i 'enterprise' docs/Claude_security_plugin_usage.md` at 0192e9d0 prints line 24.
- Why it matters: a decision row that states a removal the file does not bear out is the "written claim trusted over what it describes" pattern; and the writing-style rule says never mention a specific vendor product.
- NOT FIXED

### V-DS-14: checklist item 6, privacy: PASS, with V-DS-11 and V-DS-13 as wording issues, not leaks
- Mode: `git ls-tree 0192e9d0 docs/Claude_security_plugin_usage.md` gives `100644 blob 6dc31ac7...`; on develop 4eab6dd6 it was `120000`. `test -L` on the checkout: regular file.
- Content: the 82-line file read in full. No local path, no private repository name, no internal project or internal tool name, no employer name. My own check, which never prints the values: each path part of the old link target compared against the new file and against every added line of the branch diff. The private repository name and the folder after it appear in neither (they appear only on the removed side of the diff); the remaining parts are generic words ("security", the file's own name) and match only ordinary text. `git grep -i -F` for the private repository name over every tracked file at 0192e9d0 finds 0 files.
- Leak scan, run from the docsync worktree as the brief asks, rc 0, last lines:
  `private-name check: PASS (it read every line, file name and message this scan read, in 7 commit(s) and the working tree, and every tracked file)`
  `scanned 738 lines, 6 file names and 7 commit(s) against origin/develop (merge base 4eab6dd6); 0 finding(s), 0 file(s) too large to scan, 0 binary file(s) for a person to look at`
  `PASS: nothing to publish looks like a secret or a private value.`
- Control, so the PASS is not a scan that sees nothing: in my own worktree I committed a symlink whose target is the old private target and ran the scan with `--no-fetch --base 0192e9d0`: rc 1, `FAIL private-name check: commit 8f9a8096 probe_link.md:1 [owner-term]`. The probe commit was reset away at once.
- Diff search over all 793 added lines of `git diff 4eab6dd6..0192e9d0`: no home directory path (the macOS and Linux home-folder prefixes, a tilde path, and the system temporary folders: 0 hits); no email address (the only `@` matches are `@pytest.mark.parametrize`); IP addresses only `127.0.0.1`; no ssh or login command; one GitHub URL, the public data engineering repository, already linked on develop.
- Note for the owner, not new: git history still holds the old link target (the decision row says so); rewriting history is the owner's call.

### V-DS-15: checklist item 7, all doc checks: PASS
Run in my own clean detached worktree at 0192e9d0, venv tools (`ruff` and `isort` 9.0.0 resolved from the project venv):

| Command | Output | Exit |
|---|---|---|
| `python3 tracker/check_doc_drift.py --check` | `ok: 2 facts computed \| 0 could not be computed \| 0 stale \| 0 structural` | 0 |
| `python3 tracker/check_doc_sync.py` | `ok: the board, the done file, the retest file, the test queries, the board plan, the Factory brief, the handoff and the registry agree` | 0 |
| `python3 tracker/check_living_docs.py --shape` | `living documents: 20 rows, shape as registered` | 0 |
| `ruff check` (no path) | `All checks passed!` | 0 |
| `bash .github/gates/gate02_import_order.sh` (`isort --check-only --diff src tests services tracker alembic .claude .github`) | `Skipped 2 files` | 0 |
| `pytest tests/tracker tests/system_03_search_agent/test_debugging_guide_coverage.py` | `79 passed` | 0 |

These pass, but the drift check passing is weaker evidence than it looks: it cannot see an unclosed `<details>` (V-DS-06) or a stray row with other spacing (V-DS-08), and it fails the learnings skill's own detail-section instruction (V-DS-09).

### V-DS-16: `--counts` reports 252 lessons when the table holds 253 (present on develop too, not worse)
- Severity: minor, pre-existing
- What: `_dated_row_count` in `tracker/check_doc_drift.py` uses `^\|\s*\d{4}-\d{2}-\d{2}\s*\|`, which skips the `| 2026-08-10/11 |` row. The structural rule's `DATED_ROW_RE` (`^\| \d{4}-\d{2}-\d{2}`) does match it, so the two parts of the same script disagree about what a lesson row is.
- Reproduction: `compute_learnings_entry_count()` gives `value=252` on both develop's and the branch's LEARNINGS.md; `grep -c '^| *20[0-9][0-9]-' LEARNINGS.md` gives 253 on both.
- Why it matters: the counts command CLAUDE.md points to understates the log by one. Same on develop, so nothing here is worse.
- NOT FIXED

## Where the findings sit

Three findings sit inside this branch's own changes, which is the review loop's stop condition:
- V-DS-09: the learnings skill section that a66b39d1 edited still tells writers to add text below the table, which 111c8066 now fails.
- V-DS-11: 0192e9d0 made the security guide a regular file, but `docs/README.md` still calls it a symlink into the owner's private repository, in the sentence 3ec6c46e edited.
- V-DS-02: 468e8898 rewrote the "above" sentence but left "matching the table above".

None of the three makes anything worse than develop for a person using the product. On develop, the docs/README sentence was true and the skill line was harmless. V-DS-11 replaces a true sentence with a false one, but a false one that leaks nothing.

## Verdict

FAIL against the checklist, items 4 and 5. Items 1, 2, 3, 6 and 7 pass, with minor findings.

| Item | Result | Basis |
|---|---|---|
| 1 No loss in LEARNINGS.md | PASS, minor V-DS-02, V-DS-03 | own probe |
| 2 Theme index | PASS, minor V-DS-05 | own probe and reading of 30 sampled rows |
| 3 Drift check rule | PASS on its property; gaps V-DS-06 (unclosed `<details>` passes), V-DS-08 | own probes and mutations |
| 4 Skill and registry wording | FAIL, V-DS-09 | own probe of the check, reading of the skills |
| 5 Canonical and reference edits | FAIL, V-DS-11 | own commands against code and repository; AGENTS.md regenerated with a control |
| 6 Privacy | PASS, wording issue V-DS-13 | own probes, leak scan with a positive control |
| 7 All doc checks | PASS | own runs |

Verified with my own probes: the row-by-row word comparison and the structure of the file; the coverage of the index by date; the drift rule against develop's file and the branch, plus four mutations and three evasion probes; the shape pin with a mutation; every line reference and environment-variable claim in item 5's table; AGENTS.md regeneration with a drift control; the file mode, the old target's path parts, the leak scan with a positive control, and the diff searches; every item 7 command.

Only read, not probed: whether each of the 30 sampled rows fits its theme, which is a judgement; whether "Jev, live on develop" and the develop overrides in Model_architecture.md hold on the deployed service, since I read no deployed variables; the cost figures.

Nothing found is worse than develop for a person using the product, or for privacy. The leak itself is fixed in the tree, and only git history still holds it.
