# Build phase 8.5, fix and verify round, 2026-09-25

The one fix-and-verify round against the judge's round 1 findings
(`tracker/phase_8.5.md`, "Lead triage of round 1"). Four items, one commit
each on `phase/8.5-housekeeping`, no push, no branch switch.

## Table of contents

- [Item 1: F-8.5-J07, the two non-timing controls](#item-1-f-85-j07-the-two-non-timing-controls)
- [Item 2: F-8.5-J01, J02, J03, J08, J09, the hand-over document](#item-2-f-85-j01-j02-j03-j08-j09-the-hand-over-document)
- [Item 3: F-8.5-J04, the Python test count](#item-3-f-85-j04-the-python-test-count)
- [Item 4: F-8.5-J05, J10, J06, the three small corrections](#item-4-f-85-j05-j10-j06-the-three-small-corrections)
- [Commits](#commits)

## Item 1: F-8.5-J07, the two non-timing controls

Two new unit tests added to `tests/system_03_search_agent/core/test_graph.py`
(appended at end of file, no existing test changed):

- `test_unresolved_gene_symbol_refusal_spends_no_synth_tier_call`
- `test_unresolved_gene_symbol_refusal_never_announces_write_started`

Each pins one of the two properties the deleted W4
(`test_write_streaming_premise.py`, removed with card 37) used to pin: the
unresolved-entity refusal spends no synth-tier call, and it never emits the
`step` / write-started marker.

Proof each control is real, using an in-memory mutant of `core/graph.py` in
a scratch copy of the repository under `/private/tmp` (never in this
worktree's `src/`):

- Mutant A: inserted `await _dispatch_tier_call(harness, trace_id, "synth",
  "write", build_synth_messages("mutant probe", []), 5.0)` immediately
  before the refusal's `sink.emit("token", ...)` call. Result:
  `test_unresolved_gene_symbol_refusal_spends_no_synth_tier_call` FAILED
  ("the unresolved-entity refusal path spent a synth-tier call");
  `test_unresolved_gene_symbol_refusal_never_announces_write_started`
  PASSED (the mutant does not touch the step marker).
- Mutant B: inserted `sink.emit_live("step", StepPayload(step="write",
  status="started"))` unconditionally, immediately after `sink =
  _EventSink(...)` at the top of `write_node`. Result:
  `test_unresolved_gene_symbol_refusal_never_announces_write_started` FAILED
  ("a refusal that never began the answer path announced that Write had
  started"); `test_unresolved_gene_symbol_refusal_spends_no_synth_tier_call`
  PASSED (the mutant does not touch the synth call).
- Both mutants reverted, both tests PASSED against the unmutated source.

Full required suite in this worktree after the change:
`python3 -m pytest -m "not integration" -q -p no:cacheprovider
tests/system_03_search_agent/core/test_graph.py` gives `216 passed`. The
full non-integration suite gives `5221 passed, 143 skipped, 24 deselected,
1 xfailed`, two more passes than the judge's round 1 baseline of `5219
passed`, matching the two new tests added.

## Item 2: F-8.5-J01, J02, J03, J08, J09, the hand-over document

`docs/data-engineering/Graph_data_hand_over_2026-09-25.md` rewritten so
every gap cites the probe script, pattern and date that actually produced
it:

- Item one (Disease names): now cites
  `testing/Developer/reports/2026-09-23_overnight/probe_disease_names.py`,
  the "syndrome" pattern probe, dated 2026-09-23, rather than the
  2026-07-31 F-2.1-B07 census, which never ran that pattern or that count.
  F-2.1-B07 is kept as background for the per-vertex pattern, with its own
  three-way status conflict named rather than resolved by picking one.
- Item three (OntologyClass/MeSH): now cites
  `probe_ontology_names.py`, the two zero-row graph-wide patterns, dated
  2026-09-23, instead of "the same census as item one, extended", which
  names a query that does not exist.
- Item two (has_phenotype): the citation now points at
  `Knowledge_graph_on_server_reference.md` section E (edge counts), not
  section D (vertex counts), and states both endpoint pairs that row
  actually records instead of asserting all 6,076,735 rows run one way.
  Also softened the phenotype-question claim to name what actually answers
  it today (MedGen clinical features, phase 8.1) rather than crediting a
  template removal with making it answerable.
- Added a new item four, the Gene vertex gap (seven properties, none a
  fact; 17 of 20 calls in the worst cold pass; 2,957 of 4,748 citations
  from a wordless layer), sourced to `soft_edges_scoping.md`, which card
  29's board title and DECISIONS.md row had both been silent on.
- Dropped the unsourced claim that the citation rule is what keeps an
  answer from being withheld; replaced with the actual mechanism
  (degradation to a live Layer 2/3 call per the cite-or-refuse gate).

`python3 .claude/skills/doc-readability/scripts/check_style.py
docs/data-engineering/Graph_data_hand_over_2026-09-25.md` reports `0 hard,
5 advisory` (the five advisories are heading-case notices on named types
Disease/MeSH/Gene and a missing-mermaid suggestion, both pre-existing
choices carried from the original doc's heading style).

## Item 3: F-8.5-J04, the Python test count

The drift check's `VENV_PYTHON` is hard-coded to `venv/bin/python` relative
to the script's own location, and this worktree has no `venv/`, so it
silently skips the two test-count facts. Per the brief, ran it with
`VENV_PYTHON` monkeypatched to `sys.executable` in memory (no file on disk
edited):

```
python3 -c "
import sys, pathlib
sys.path.insert(0, 'tracker')
import check_doc_drift
check_doc_drift.VENV_PYTHON = pathlib.Path(sys.executable)
print(check_doc_drift.main(['--check']))
"
```

Before the fix: `AGENTS.md:31`, `CLAUDE.md:31`, `tracker/phase_8.5.md:103`
and `:111` all flagged, computed count `5531` (5529 the judge measured, plus
the two tests added in item 1) against a stated `5550`.

Fixed: `CLAUDE.md` and `AGENTS.md`'s Current focus table build row now read
`5531 Python tests`. `tracker/phase_8.5.md`'s own F-8.5-J04 heading and
second bullet reworded with a hedge word ("previously said") next to the
quoted `5550` so the ledger's own wording no longer keeps the drift check
red, per the judge's own addendum asking for exactly that.

After the fix, same command: `ok: 8 facts computed (2 skipped) | 0 stale |
0 structural`, exit 0.

## Item 4: F-8.5-J05, J10, J06, the three small corrections

- F-8.5-J05: `.claude/agents/docs-sync.md`'s routing table named
  `CLAUDE.md`'s counts by line number ("line 32"), the same drift
  `.claude/skills/phase-checkpoint/SKILL.md` already fixed. Reworded to
  "CLAUDE.md's Current focus table's build row", naming the row by content.
- F-8.5-J10: `frontend/e2e/tool-chip.spec.ts`'s header comment named
  `test_phase_4_16_premise.py` as the backend half of its proof; that file
  was deleted with the rest of the streaming-timing test set (card 37).
  Reworded to name the backend suites that incidentally still guard
  `act_node` emitting `tool_start`/`tool_result`
  (`test_bare_topic_clarification.py`, `test_breadth_wiring.py`,
  `test_clarification.py`, `test_layer_handoff.py`, per the judge's own
  mutation probe), and to state that the live-versus-buffered timing
  question is covered only by the product reviewer's time-to-answer
  measure per the card 37 ruling, not by any test.
- F-8.5-J06: `type.html`'s body1 sample carried no `line-height` and
  rendered at the page's global `1.6` while its own spec label read
  `1.65`. Added `line-height:1.65` to the sample span so render matches
  label.
  `docs/build/design/NCBI_design_system_migration_assessment.md`'s
  four-value disagreement table (h1 letter-spacing, h1 size, h2 size,
  body1 line-height) is recorded as settled on 2026-09-25 by the product
  owner's ruling that the shipped `theme.ts` values win; `theme.ts` itself
  was not touched.

## Commits

One commit per item, on `phase/8.5-housekeeping`, no push:

1. `test(write): pin the two non-timing controls W4 pinned before deletion`
2. `docs(data-engineering): cite the real measurement, date and probe per gap`
3. `docs(tracker): correct the Python test count to what a real interpreter computes`
4. `fix(docs): three small corrections from phase 8.5 round 1 triage`
