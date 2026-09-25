# Builder E report, build phase 8.5, "housekeeping nobody sees"

All six tasks complete. Nothing here changes what an answer says.

## Task 1: Card 29, graph data hand-over

Wrote `docs/data-engineering/Graph_data_hand_over_2026-09-25.md`: a request
to the data-engineering repository covering three measured gaps, each with
what was measured, when, by what query, and what a person using the product
loses.

- Disease vertices named after their source vocabulary (F-2.1-B07, censused
  2026-07-31 over 200,845 rows, zero contain "syndrome").
- No Disease vertex has an outgoing `has_phenotype` edge, and every
  PhenotypicFeature is an unpopulated stub (measured 2026-09-23,
  `probe_disease_names.py` and `probe_g022.py`).
- The graph holds no MeSH term names (same F-2.1-B07 root cause, restated in
  `testing/UI_fixes_done.md` on 2026-09-24).

`check_style.py` reports 0 hard findings (4 advisory: technical vertex-label
capitalization and a missing Mermaid diagram, both acceptable for this doc).
Commit: `02556f6`.

## Task 2: Card 34, four type values

Confirmed the disagreement against `theme.ts` lines 160 to 164 and the
migration assessment doc's table (lines 105 to 114), then updated
`docs/build/design/design-system/foundations/type.html` so its h1 (font-size
and letter-spacing), h2 font-size, and body1 line-height match `theme.ts`
exactly. `theme.ts` itself was not touched. Only the four named values and
their displayed spec labels changed; h2 letter-spacing already matched and
was left alone. Commit: `908980a`.

## Task 3: Card 40, phase-checkpoint line references

Verified CLAUDE.md's tracked-counts line now sits at line 31 (grep for
"decisions (DECISIONS.md)"), confirming the card. Reworded all three stale
"CLAUDE.md line 32" / "AGENTS.md line 32" references in
`.claude/skills/phase-checkpoint/SKILL.md` (the reference table row, the
Step 5d instruction, and the Step 6 checklist item) to name the line by
content, "the Current focus table's build row", instead of a line number, so
a future trim cannot make the same reference stale again. Meaning otherwise
unchanged. Commit: `98b2d81`.

## Task 4: Card 37, delete four test files

Ran `git rm` on exactly the four named paths (`test_phase_4_16_premise.py`,
`test_phase_4_16_mutation.py`, `test_write_streaming_premise.py`,
`test_write_streaming_mutation.py`). `python3 -m pytest
tests/system_03_search_agent/core -q --co` collects cleanly: 1120 tests, no
collection errors. Commit: `dab2757`.

Remaining references to the four deleted filenames, for the lead to edit
(none of these are in my file fence, so none were touched):

- `docs/build/Bossman_redesign_deletion_inventory.md` lines 101 to 104 and
  109 (the deletion-decision table itself and the explanatory sentence
  below it).
- `tracker/phase_4.16.md` line 119 (ticket T-4.16-06's status note naming
  `test_phase_4_16_premise.py`).
- `testing/Developer/reports/2026-09-19_ci_green/python_gates.md` lines 33
  and 57 (historical CI-collection-order notes naming
  `test_phase_4_16_premise.py`).
- `docs/build/Debugging_guide.md`: no reference found, so no update needed
  there despite the debugging-guide-coverage test's usual requirement.

## Task 5: Card 41, missing-file investigation (read-only, nothing changed)

Read `.claude/hooks/scan-duplicate-copies.sh` and every other hook under
`.claude/hooks/`, plus `testing/UI_fixes_done.md`'s "Loose ends, named
rather than left" section (where the incident is recorded as "cause
unknown").

`scan-duplicate-copies.sh` is the only hook anywhere in `.claude/hooks/`
that moves or deletes a file (grep for `rm |mv |unlink|Trash` across every
hook confirms this: the only hits are in this one file, plus comments in
`block-bash-delete.sh` describing what it blocks, not what it does). Its
match pattern is `grep -E ' [0-9]+\.[A-Za-z0-9]+$'`, meaning a literal space
followed by digits and an extension at the end of the filename, the macOS
Finder "Keep Both" duplicate-copy shape ("env 2.py"). Tested directly:
`echo "testing/Shipped_2026-09-20.md" | grep -E ' [0-9]+\.[A-Za-z0-9]+$'`
does not match, because the filename has no space before a digit. This
rules the hook out as the cause: it structurally cannot have matched, let
alone moved, that file.

No other hook (`block-bash-delete.sh`, `block-sensitive-read.sh`,
`scan-context-injection.sh`, `scan-secrets.sh`, `scan-write-secrets.sh`,
`session-start.sh`, `sync-agents-md.sh`, `sync-board.sh`) writes, moves, or
deletes any file outside `.claude/`; `sync-agents-md.sh` and
`sync-board.sh` only ever write `AGENTS.md` and the board's generated HTML.

`~/.Trash` could not be listed: `ls -la ~/.Trash` returns "Operation not
permitted", an OS-level (Terminal Full Disk Access) restriction, not a
sandbox setting this session can change. So I cannot confirm or rule out a
Trash copy either way; that check is unresolved, not negative.

Conclusion: every hook in this repository is ruled out as the mechanism,
by direct evidence (the pattern test above) for the one hook capable of
moving a file at all, and by absence of any file-mutating code for the
rest. The cause remains unestablished, consistent with the existing "cause
unknown" note; nothing found here points at a suspect script inside this
repository. Likeliest remaining explanations are outside this repository's
`.claude/` tooling entirely (a manual Finder action, a different local
tool, or an editor's own file-management behavior), and none of those left
evidence a grep of this repository can recover.

## Task 6: Card 30, Integrations page commands

Created a fresh virtual environment at
`testing/Developer/reports/2026-09-25_phase_8.5/venv` (gitignored, `pip
install -e .` succeeded cleanly, both `s3` and `s3-kgx-export` console
scripts installed). Signed up one fresh test account on develop via `POST
/auth/signup` (status 201) using a script written with the Write tool and
run by path, with a randomly generated password never printed to any
command's stdout or command text.

`s3 login` then `s3 ask "diseases linked to BRCA1"`:

- `s3 login` (exactly as printed, no arguments): FAILS immediately, exit
  code 2. `email` is a required positional argument
  (`_parse_login_args`, `src/system_03_search_agent/adapters/cli/main.py`
  line 650). Output:
  ```
  usage: s3 login [-h] [--base-url BASE_URL] email
  s3 login: error: the following arguments are required: email
  ```
  What a person would have to type instead: `s3 login you@example.com`,
  with `S3_BASE_URL` set to the target server (or `--base-url` passed), and
  the password piped or typed at the resulting prompt. Confirmed working
  with the signed-up test account and `S3_BASE_URL` set to
  `https://search-agent-api-develop-43b3.up.railway.app`: exit code 0,
  output `logged in`.
- `s3 ask "diseases linked to BRCA1"` (exactly as printed): WORKS, once
  logged in. Exit code 0. First 20 lines of output:
  ```
  [Chargaff | think] One direct API call to a gene-disease association database will answer it.
  [Chargaff | plan] searching 3 layers for NCBIGene:672. Layer 1, the knowledge graph: cypher_query; Layer 2, live NCBI records: ncbi_efetch; Layer 3, literature and trials: pubtator_annotate, clinicaltrials_search
  [tool] cypher_query (layer_1_graph): running
  [tool] ncbi_efetch (layer_2_api): running
  [tool] pubtator_annotate (layer_3_enrichment): running
  [tool] clinicaltrials_search (layer_3_enrichment): running
  [tool] ncbi_efetch (layer_2_api): running
  [tool] ncbi_efetch (layer_2_api): running
  [tool] ncbi_efetch (layer_2_api): running
  [tool] ncbi_efetch (layer_2_api): running
  [tool] pubtator_annotate (layer_3_enrichment): running
  [tool] ncbi_efetch (layer_2_api): running
  [tool] ncbi_efetch (layer_2_api): running
  [tool] ncbi_efetch (layer_2_api): running
  [tool] cypher_query (layer_1_graph): running
  [tool] pubtator_annotate (layer_3_enrichment): ok - ok: 1 record(s) (1 result(s))
  [tool] ncbi_efetch (layer_2_api): ok - search: 10 id(s) (10 result(s), truncated)
  [tool] ncbi_efetch (layer_2_api): ok - search: 5 id(s) (5 result(s), truncated)
  [tool] ncbi_efetch (layer_2_api): ok - dataset_report: 1 record(s) (1 result(s))
  [tool] clinicaltrials_search (layer_3_enrichment): ok - ok: 5 record(s) (5 result(s))
  ```

`s3-kgx-export NCBIGene:672 --hops 1 --output-dir ./kgx-out` (exactly as
printed): FAILS, exit code 1. Output:
```
s3-kgx-export: graph connection environment variables are not fully set: GRAPH_PG_HOST, GRAPH_PG_USER, GRAPH_PG_PASSWORD, GRAPH_PG_DBNAME must all be set, then retry
```
This is by design, not a bug in the command itself:
`src/system_03_search_agent/export/cli.py`'s own module docstring states
this export "reads the graph directly" and deliberately never touches the
REST API, unlike `s3`. So there is no `s3-kgx-export login` or `--base-url`
that would make the printed command work against develop; it needs direct
Hetzner AGE graph credentials (`GRAPH_PG_HOST`, `GRAPH_PG_USER`,
`GRAPH_PG_PASSWORD`, `GRAPH_PG_DBNAME`), which nowhere on the Integrations
page (`frontend/src/components/screens/InfoScreens.tsx`) is mentioned as a
prerequisite. From the user's chair: a person reading the Integrations page
sees a copy-paste command that looks parallel to `s3 ask`, but it silently
needs a different, undocumented, and more sensitive kind of credential than
account login, one an ordinary product user has no way to obtain. I did not
attempt to obtain graph credentials myself, since Layer 1 access is a
scoped, read-only credential this task gave me no reason to acquire.
What a person would have to type instead: nothing they can self-serve from
the page as written; they would need `GRAPH_PG_HOST`,
`GRAPH_PG_USER`, `GRAPH_PG_PASSWORD` and `GRAPH_PG_DBNAME` set to real
Hetzner graph credentials first, which is an operator-level prerequisite the
page does not name.

No code was changed for this task (`InfoScreens.tsx` was read only, per
instructions).

## Files touched

- `docs/data-engineering/Graph_data_hand_over_2026-09-25.md` (new)
- `docs/build/design/design-system/foundations/type.html`
- `.claude/skills/phase-checkpoint/SKILL.md`
- Deleted: the four test files named in task 4
- `testing/Developer/reports/2026-09-25_phase_8.5/builder_E.md` (this file)
- `testing/Developer/reports/2026-09-25_phase_8.5/venv/` (gitignored, not committed)
