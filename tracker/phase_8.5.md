# Build phase 8.5: housekeeping nobody sees

Branch: `phase/8.5-housekeeping`. Opened 2026-09-25, built alongside phases 8.1 and 8.2 on files neither touched.

The fifth phase of the overnight plan, `testing/Overnight_build_plan_2026-09-25.md`. Nothing here changes what a person using the product sees. It needs a pull request because it touches `.claude/` (the `git-workflow` rule), and a judge round; no adversary round, since no runnable product code changes, and no golden run, since nothing here is on the answer path.

## Table of contents

- [Tickets](#tickets)
- [Not built tonight](#not-built-tonight)
- [History](#history)
- [Findings](#findings)

## Tickets

### T-8.5-01: The graph's data gaps are handed to the repository that owns the graph (card 29)

Status: in-review, builder E, `02556f6`
Acceptance: `docs/data-engineering/Graph_data_hand_over_2026-09-25.md` states each gap with its measurement, date and query, and what a person loses because of it. Nothing under `reference/` is modified.

### T-8.5-02: The design card's four type values match the shipped code (card 34)

Status: in-review, builder E, `908980a`
Acceptance: `docs/build/design/design-system/foundations/type.html` carries theme.ts's h1, h2 and body1 values; `frontend/src/theme.ts` is untouched (the product owner's ruling, 2026-09-25).

### T-8.5-03: `/phase-checkpoint` names the counts line by what it holds, not a line number (card 40)

Status: in-review, builder E, `98b2d81`
Acceptance: `.claude/skills/phase-checkpoint/SKILL.md` no longer says "line 32" anywhere; each reference names the Current focus table's build row.

### T-8.5-04: The four streaming-timing test files are deleted together (card 37)

Status: in-review, builder E, `dab2757`
Acceptance: the four files are gone, collection still works, and the deletion inventory records the product owner's ruling.

### T-8.5-05: The deleted-file mystery is investigated (card 41)

Status: investigated, nothing changed: the repository's hooks are ruled out by their own matching rules (builder E); the lead found a process creating " 2" copies inside the repository mid-session, a ref file and `.git/index 2`, likely iCloud Desktop sync. Card 41 stays in To do with this lead.

### T-8.5-06: The Integrations page's two command examples, run as printed (card 30)

Status: measured by builder E: `s3 login` fails as printed (it needs the email) and `s3-kgx-export` needs graph credentials no public user has; `s3 ask` works. The page fix is in phase 8.4's branch (builder G, `22e0e2b`).

## Not built tonight

- Card 18, the Python lock file, and card 35, the USWDS package: each changes what develop builds or installs, and each deserves a morning with the product owner awake rather than an unattended deploy. Decided and ready to build.
- Card 39, merging bossman mode's two modes: due after a build phase closes, now true; a `.claude/` change of its own, left for a session with the owner.

## History

- 2026-09-25: builder E built tickets 01 to 06 in its own worktree; the lead merged develop into the branch and opened the pull request.

## Findings

Written the moment a finding is established.

Judge, round 1, 2026-09-25: started. Findings follow as established.

### F-8.5-J01: Hand-over item one dates the "zero syndrome" measurement to 2026-07-31 and to F-2.1-B07; it was taken on 2026-09-23 by a different query

Status: raised
Raised by: judge, round 1
Severity: medium
Round: 1

Card 29's acceptance is "each gap with its measurement, date and query". Item one of `docs/data-engineering/Graph_data_hand_over_2026-09-25.md` (lines 20 to 29) says a graph-wide census found zero of 200,845 `Disease` rows containing "syndrome", "When: censused on 2026-07-31, during build phase 2.1", "Filed as finding F-2.1-B07", query "a graph-wide scan ... counting vocabulary-artifact strings".

What the cited sources actually say:
- `tracker/phase_2.1.md:889` (F-2.1-B07) contains no census, no 200,845 and no "syndrome": it says names are "frequently parse artifacts", with BRCA1's four diseases as the example (`:1158`).
- The 200,845-row census of 2026-07-31 is F-2.1-J5-04 (`src/system_03_search_agent/core/graph.py:6735`), and it counted leaked vocabulary tokens (15,466 missed by the shape rule), not "syndrome".
- The "zero syndrome" result is from 2026-09-23: `testing/Developer/reports/2026-09-23_overnight/findings.md:475` and `soft_edges_scoping.md:49` and `:360`, query in `probe_disease_names.py:71`, pattern `(?i).*syndrome.*`. `findings.md:598` says explicitly that this graph-wide form is what was NEW on 2026-09-23 and not in the 2026-07-31 census.

So the date, the finding id and the query given for item one's headline measurement are wrong, and the real query (the one the data-engineering repository could re-run) is not given. A reader in the other repository re-running "the F-2.1-B07 census" finds nothing matching the number.

Also item one opens "every `Disease` vertex's `name` property holds the name of the vocabulary". The sources support "zero contain syndrome" plus samples of 8 and 3 vertices; F-2.1-B07 itself says "frequently". Unsure whether "every" overstates; the 2026-09-23 report does conclude "the field holds the wrong value everywhere", so it is a sourced inference, but it is not stated as one.

### F-8.5-J02: Hand-over item three gives no real query or measurement date, and points at a census that never covered OntologyClass

Status: raised
Raised by: judge, round 1
Severity: medium
Round: 1

`docs/data-engineering/Graph_data_hand_over_2026-09-25.md` lines 76 to 86: "every `OntologyClass` vertex [named] after its own identifier ... measured graph-wide"; "When: known since build phase 2.1 as finding F-2.1-B07, and restated ... on 2026-09-24"; "By what query: the same graph-wide vocabulary-artifact census described in item one, extended to the `OntologyClass` label."

The graph-wide OntologyClass measurement is `testing/Developer/reports/2026-09-23_overnight/probe_ontology_names.py`, 2026-09-23, `MATCH (o:OntologyClass) WHERE o.name =~ $pattern` with `.*[a-z]{4,}.*` and `(?i).*neoplasm.*`, both ZERO graph-wide (`findings.md:771` and `:772`). The hand-over never names that probe, that date or that query. "The same census as item one, extended" describes no query that exists: the 2026-07-31 census (F-2.1-J5-04) was over `Disease` rows only, and item one's own query is misattributed (F-8.5-J01). F-2.1-B07 has no measurement at all, only "frequently parse artifacts".

Card 29's acceptance, "measurement, date and query", therefore fails for item three as written: the data repository cannot re-run it from this document.

### F-8.5-J03: Hand-over item two cites the wrong section of the graph reference, and that source contradicts "all 6,076,735 run from SequenceVariant to Disease"

Status: raised
Raised by: judge, round 1
Severity: low
Round: 1

`docs/data-engineering/Graph_data_hand_over_2026-09-25.md` lines 51 to 53: the count "(6,076,735 rows, all `SequenceVariant` to `Disease`) was recorded earlier, on 2026-09-14, in `docs/data-engineering/Knowledge_graph_on_server_reference.md` section D."

- Section D of that file is "Vertex labels and counts" (line 79). The `has_phenotype` row is in section E, "Edge labels and counts", line 108.
- Line 108 reads "Disease to PhenotypicFeature, and SequenceVariant to Disease (... measured live 2026-09-14, HNF1A alone has 2075 such rows ...)". It does not record that all rows are SequenceVariant to Disease; it names both pairs. A data-engineering reader who follows the pointer finds the opposite of what the hand-over says it holds.
- The "all" claim is carried from `soft_edges_scoping.md:176`, which rests on a zero-row existence check for `Disease` as the source plus `LIMIT 5` samples of each side (`probe_disease_names.py:75` and `:80`). No per-label count of the 6,076,735 rows appears in any cited source. Unsure whether other source labels exist; the hand-over states it as measured.

### F-8.5-J04: Deleting 21 tests left CLAUDE.md and AGENTS.md with a stale count, previously 5550 Python tests; the drift check's green in this worktree skipped that count

Status: raised
Raised by: judge, round 1
Severity: medium
Round: 1

- `python3 -m pytest --collect-only -q -p no:cacheprovider` at the worktree root: `5529 tests collected`.
- `CLAUDE.md` line 31 and `AGENTS.md` line 31 on this branch previously said "5550 Python tests". 5550 minus 5529 is 21, exactly the four deleted files' tests (5 + 7 + 4 + 5).
- `python3 tracker/check_doc_drift.py --check` in this worktree prints `ok: 6 facts computed (4 skipped) | 0 stale`, and its detail lists "Python tests: SKIPPED (venv/bin/python not found)" and "Premise gate tests: SKIPPED". The green is the same green a branch that changed nothing would get: the fact this phase moved is the one it did not compute. `VENV_PYTHON` is hard-coded to `venv/bin/python` (`tracker/check_doc_drift.py:185`) and a worktree has none. CI does not run the drift check (`.github/workflows/ci.yml` and `release.yml` do not name it).
- Consequence: after merge, the first `/ship` or `/phase-checkpoint` run from the main checkout (which has `venv/`) goes red on "Python tests says 5550 (computed: 5529)", in whichever unrelated session runs next.

Separately, and unsure whether it is a defect or intended: a worktree drift run that skips the two test-count facts still exits 0 and prints "ok". A gate that reports ok while skipping the fact under test is the vacuous-green shape.

Addendum to F-8.5-J04, measured by the judge: the drift check run with a real interpreter (in memory, `check_doc_drift.main(["--check"])` with `VENV_PYTHON` pointed at `sys.executable`, no file changed) exits 1, "8 facts computed (2 skipped) | 4 stale", naming `AGENTS.md:31` and `CLAUDE.md:31`, plus two lines of THIS ledger: the J04 heading and its second bullet, because they quote the stale count without a hedge word the checker recognises. Those two ledger hits are the judge's own quotation, introduced by this append; the closer should reword them (or the lead should) when the count is fixed, or the gate stays red on the ledger alone.

### F-8.5-J05: The same stale "CLAUDE.md line 32" survives in the docs-sync agent

Status: raised
Raised by: judge, round 1
Severity: low
Round: 1

`git grep -n "line 32" -- '*.md' '*.py' '*.sh'` on this branch: `.claude/agents/docs-sync.md:75` still reads "`CLAUDE.md` line 32 counts (tests, decisions, learnings) | Owned by /phase-checkpoint Step 5d ...". The counts sit on line 31 (`grep -n "Current counts" CLAUDE.md` gives 31), which is card 40's whole defect, one file over. Card 40 was scoped to `/phase-checkpoint` and T-8.5-03's acceptance names only that skill, so this may be deliberate; filed because this pull request is the one `.claude/` pull request of the night and the next chance needs another. `tracker/Living_documents.md:45` also names "line 31" by number, which is correct today and will go stale the same way.

Card 40 itself verified: `.claude/skills/phase-checkpoint/SKILL.md` has no "line 32" and no other line number for the counts; the diff is exactly three lines (the ownership table row, Step 5d's second bullet, one exit-checklist item), each a like-for-like substitution with the meaning unchanged.

### F-8.5-J06: Card 34 leaves two loose ends: the body1 sample still renders at 1.6 under a 1.65 label, and the migration assessment still lists the four values as open

Status: raised
Raised by: judge, round 1
Severity: low
Round: 1

Verified first: `type.html` lines 39 to 41 now carry `clamp(32px, 4.8vw, 52px)`, weight 800, `-.034em` (h1), `clamp(24px, 3.1vw, 33px)`, `-.022em` (h2), and the body1 label `1.65`; these equal `frontend/src/theme.ts` lines 160, 161 and 164. `git diff origin/develop..HEAD --stat -- frontend/` is empty. The card's diff is exactly those three lines.

Loose end one: the body1 row's sample span carries only `font-size:16px`, so it renders at the page's `body{line-height:1.6}` (line 23 of the card) while its spec label now says `1.65`. Before this change label and render agreed at 1.6; now the card's own sample contradicts its label. The h1 and h2 samples likewise carry no line height, where theme.ts has 1.1 and 1.15; that part predates this phase.

Loose end two: `docs/build/design/NCBI_design_system_migration_assessment.md` lines 105 to 114 still say "Still open, reported rather than fixed ... Neither card nor code was edited for these four", with the old card values and line pointers, and line 64 still gives the type scale as "38px/800, 26px/800". CLAUDE.md's reference table sends readers to that assessment "before scoping or deciding on a migration", so it now reports a resolved disagreement as open.

### F-8.5-J07: One deleted arm was not timing: W4 was the only test that a refusal decided before Write spends no synth-tier call, and the remaining suite now passes with that broken

Status: raised
Raised by: judge, round 1
Severity: high
Round: 1

The deletion inventory and the card 37 decision describe all four files as "when progress reaches the screen". `test_write_streaming_premise.py`'s W4 (`test_w4_a_refusal_decided_before_the_synth_call_never_announces_write_and_never_calls_synth`, origin/develop lines 407 to 446) pinned two non-timing properties of the unresolved-entity refusal: it spends no synth call (`delay.synth_calls == 0`) and it never emits the `step` "write started" marker. W3 also pinned non-timing parity (see the note at the end).

Probe, in memory only (a meta-path loader compiles `core/graph.py` with one inserted block; no file edited):
- Mutant A: inside `write_node`'s `if unresolved_entity_symbols:` branch, before the refusal is emitted, call `_dispatch_tier_call(harness, trace_id, "synth", "write", ...)`. Full remaining suite on this branch, `-m "not integration" tests/system_03_search_agent`: `5219 passed, 143 skipped, 24 deselected, 1 xfailed`, exit 0; the branch ran 7 times and the synth-tier call succeeded 7 times. Nothing went red.
- Mutant B: emit `step` / `write started` live when `unresolved_entity_symbols` is set. Same full suite: `5219 passed ...`, exit 0, branch hit 7 times. Nothing went red.
- Control, run in the main checkout at `6bbe7f5` (develop, which still has the file): W4 unmutated `1 passed`. W4 under Mutant A2 (the same call built with `build_synth_messages`, so W4's counter sees it): `AssertionError: the refusal path spent a synth call. assert 1 == 0`. W4 under Mutant B: `AssertionError: a refusal that never began the answer path announced that Write had started.`

So W4 detected both and nothing that remains detects either. `tests/system_03_search_agent/core/test_graph.py:3481` (`test_unresolved_gene_symbol_refuses_before_reaching_the_graph`) says in its docstring "no synth call is spent" but asserts only that `cypher_query` is not called, the refusal wording, zero tool calls and `risk_tier`; it never counts synth calls. That docstring is a claim with no test behind it (the self-eval-loop rule's comment-as-claim case).

Why it matters: the synth tier is the most expensive model; a regression that sends every unresolved-name question through a synth call before refusing costs money on every such question and adds seconds to a refusal, and a stray `step` marker tells the reader "writing your answer" before a refusal. It is a cost behaviour and a refusal-path behaviour, not timing, so it falls outside what the product owner was told the deletion removed. Fix shape, not mine to choose: move W4's two assertions into an ordinary test (for example beside `test_graph.py:3481`), which the inventory's own recommendation for the other files already describes.

W3 note, lower confidence: W3 also pinned live-versus-buffered parity of grounded write events on a tool-using answer and Section 8 order (tokens, then citations, then trust signals, the answer-scope verdict last). `core/test_run.py:528` still pins type-sequence parity and `:513` seq uniqueness, but on a no-tool query. Not mutation-tested by the judge; unsure whether a tool-path-only divergence would now go unseen.

Addendum to F-8.5-J07: Mutant A2 (the synth call built with `build_synth_messages`, the exact shape W4 counts) against the full remaining suite on this branch: `5219 passed, 143 skipped, 24 deselected, 1 xfailed`, exit 0, branch hit 7 times, synth-tier call succeeded 7 times. Established for both the realistic and the generic form of the mutant.

Addendum to F-8.5-J01: the conflation is inherited. `testing/Developer/reports/2026-09-23_overnight/soft_edges_scoping.md:799` to `:802` already joins the two in one bullet ("Zero vertices graph-wide contain 'syndrome'. Filed here since build phase 2.1 as F-2.1-B07, still open, censused over all 200,845 rows on 2026-07-31"), while the same document's own table (`:49`, `:360`) and `findings.md:598` date the syndrome result to 2026-09-23. The hand-over copied the ambiguous sentence rather than the measurement. The sources also disagree on F-2.1-B07's state: `tracker/phase_2.1.md:891` says `Status: closed`, `:1158` says `in progress`, and the scoping document says "still open"; the hand-over does not say which.

### F-8.5-J08: The hand-over drops the scoping document's third measurement, the Gene vertex that carries no facts

Status: raised
Raised by: judge, round 1
Severity: low
Round: 1

Unsure whether this is a defect or a scoping choice. `soft_edges_scoping.md:796` to `:809` says "The right artifact is a request with three measurements attached, in this order", and its third is "The Gene vertex has seven properties and none of them is a fact, the worst cold pass spends 17 of 20 calls, and 2,957 of 4,748 citations come from a layer that supplies no words." DECISIONS.md row 680 (card 12) names card 29 as handing over "the data gaps" in "the scoping document's order". `docs/data-engineering/Graph_data_hand_over_2026-09-25.md` carries the first two and replaces the third with MeSH term names, and does not mention the Gene-vertex measurement anywhere (`grep -n "seven properties\|4,748\|17 of 20"` returns nothing). Card 29's board title ("no disease names and no MeSH terms", `testing/UI_fix_plan.md:45`) supports the MeSH item; the scoping document's own request list supports the Gene item. The data repository gets a request missing the measurement the scoping document called the motivation for "graph plus values" (`:414` to `:422`).

### F-8.5-J09: Two claims in the hand-over rest on reasoning its sources do not give

Status: raised
Raised by: judge, round 1
Severity: low
Round: 1

- Lines 67 to 72: the phenotype template "was removed on 2026-09-23 ... so today the product falls back to live sources for this class of question instead of returning the false refusal". The cited record (`testing/UI_fixes_done.md:2209`) says only that the template was removed. `requirements/Plan.md` for 2026-09-23 says the opposite of verified: "whether a phenotype question now reaches a path that CAN answer it was not verified end to end". What answers the Marfan question today is phase 8.1's MedGen clinical features (card 1, `testing/Developer/reports/2026-09-25_phase_8.1/fix_round.md:84`), which the hand-over does not name. Removing a template does not by itself make anything answer.
- Lines 107 to 110: "since the citation rule in `CLAUDE.md` means an answer is never withheld while the graph gap stands". The citation rule (and cite-or-refuse in `production-standards`) says the reverse in general: an answer with no source IS withheld. What keeps these questions answered is that Layers 2 and 3 supply sources, not the citation rule. A reader in the data repository is told a guarantee that does not exist.

### F-8.5-J10: `frontend/e2e/tool-chip.spec.ts` still names the deleted file as "the backend half" of its proof, and the builder's list of remaining references missed it

Status: raised
Raised by: judge, round 1
Severity: low
Round: 1

`frontend/e2e/tool-chip.spec.ts:16` to `:23`: "It does NOT prove the backend emits those frames. That half is `tests/system_03_search_agent/core/test_phase_4_16_premise.py`, which drives the real loop, plus its mutation harness. ... NEITHER alone would have caught the shipped defect". That file is deleted by this branch. `testing/Developer/reports/2026-09-25_phase_8.5/builder_E.md` lists the remaining references "for the lead to edit" and omits this one; `git grep -n test_phase_4_16_premise` finds it.

Whether the backend half still exists, measured with in-memory mutants of `core/graph.py` against the full remaining suite (`-m "not integration" tests/system_03_search_agent`):
- act_node never emits `tool_start` (the 4.16 defect itself): `12 failed, 5207 passed` (`test_bare_topic_clarification.py`, `test_breadth_wiring.py`, `test_clarification.py`, `test_layer_handoff.py`). Still guarded.
- act_node never emits `tool_result`: `8 failed, 5211 passed`. Still guarded.
- act_node emits both frames with buffered `emit` instead of `emit_live` (frames reach the screen only when Act finishes, the 4.16 timing regression): `5219 passed`, exit 0. Nothing guards it now. This is the timing loss the product owner ruled acceptable (DECISIONS.md row of 2026-09-25, card 37: "the product reviewer's time-to-answer measure now covers" it), recorded so the closer knows the ruling was exercised and is not an accident; not itself a defect. The spec's comment should say which backend tests now carry the presence half, and that the timing half is covered only by the product reviewer.

Addendum to F-8.5-J07's W3 note, now measured: an in-memory mutant of `core/run.py` that drops `run_streaming`'s seq de-duplication on the updates channel (so every live-written event is yielded twice) fails the remaining suite, `8 failed, 5211 passed` (`core/test_run.py::...test_seq_is_monotonic_starting_at_zero_with_no_repeats`, `...test_yields_the_same_event_type_sequence_as_the_buffered_run`, five in `test_breadth_wiring.py`, one in `test_disease_breadth.py`). W3's duplicate-event half is still guarded; the W3 note's uncertainty is withdrawn for that half. W4's two properties remain the only non-timing loss found.

Judge, round 1, complete. Ten findings, J01 to J10: none blocking, one high (J07), four medium (J01, J02, J04; J03 is low), five low (J03, J05, J06, J08, J09, J10 counted with it: J03, J05, J06, J08, J09, J10 are the six low). Verdict FAIL against card 29's acceptance (items one and three lack a real query and correct date) and against brief check 1 for card 37 (W4 was not timing and nothing else covers it). Cards 34 and 40 pass. Run by the judge: the unit suite (`5219 passed, 143 skipped, 24 deselected, 1 xfailed`, exit 0), collection (5529), `ruff check .` (all checks passed), the drift check both as shipped (ok, 4 skipped) and with an interpreter (exit 1, stale test count), `check_style.py` (0 hard, 4 advisory), seven in-memory mutants. Read only: the hand-over's source citations, the inventory's reasoning, the skill diff.

Correction to the line above, which garbled the tally: blocking 0; high 1 (J07); medium 3 (J01, J02, J04); low 6 (J03, J05, J06, J08, J09, J10).

### Lead triage of round 1

Written by the lead, 2026-09-25. One fix-and-verify round.

- F-8.5-J07 (high): before the four streaming files' deletion stands, their two non-timing controls get ordinary unit tests, each shown red when broken and green when restored: the "could not identify that name" refusal makes no writing-model call, and it never announces that the writing step started. This is the condition the 2026-09-24 deletion decision set for any file that pinned a control.
- F-8.5-J01, J02, J03, J08, J09: the hand-over document cites the measurement, date and probe each gap actually rests on, adds the Gene vertex gap, and drops or sources the two unsourced claims.
- F-8.5-J04: the Python test count is corrected where it is tracked, and the ledger's own wording no longer states a stale count.
- F-8.5-J05, J10: the remaining stale "line 32" reference and the comment naming a deleted file are corrected.
- F-8.5-J06: the type card's sample renders at the value its label states, and the migration assessment records the four values as settled on 2026-09-25.
