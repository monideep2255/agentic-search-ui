# Builder C report, phase 8.1

Branch: `worktree-agent-a8663f2264dc9e8c8` (fast-forwarded onto `0e273fa`, the phase-open commit).

Status: in progress. This file is updated the moment a finding is established.

## T-8.1-06: a phenotype question names phenotypes

Status: PARTIALLY DONE, blocked-stop on the remainder. The extraction,
parsing, capping and security work is complete and tested, entirely inside
my fence. Wiring it into the answer the reader sees needs one line in
`core/graph.py`, which is not my file, and possibly a second change beyond
that line. Both are named exactly below.

What is done, in my fence:

- `tools/ncbi_eutils_actions.py`: `_parse_medgen_clinical_features` parses
  MedGen's `conceptmeta` field (a 35KB blob of several sibling top-level
  XML elements, not one document, measured live 2026-09-25 for Marfan
  syndrome, UID 44287, CUI C0024796: `<Names>`, `<OMIM>`,
  `<ClinicalFeatures>` with 70 `<ClinicalFeature>` entries) into a bounded
  list of `{"name": ..., "hpo_id": ...}` items, capped at 30
  (`_MAX_CLINICAL_FEATURES`) with each name capped at 120 characters
  (`_MAX_CLINICAL_FEATURE_NAME_CHARS`). The HPO id comes from the
  `ClinicalFeature` element's own `SDUI` attribute, kept only when it is
  genuinely `HP:`-prefixed (MedGen's `SDUI` column also carries MeSH ids on
  other element types, confirmed live on the same record's `Names` block).
  `summary()` now sets `extracted["clinical_features"]` for `db="medgen"`,
  always (an empty list when MedGen carries no clinical features for the
  concept, never an omitted key), and `conceptmeta` itself is never added to
  `_SUMMARY_FIELDS_BY_DB["medgen"]`, so the raw blob never reaches a record's
  `fields` dict at all, only this parsed, bounded derivative.
- Security: a malformed `conceptmeta` fails closed to `[]`
  (`ElementTree.ParseError` caught, never raised out of `summary()`). A
  DOCTYPE or ENTITY declaration anywhere in the fragment is rejected before
  `ElementTree.fromstring` ever sees it, the same reject shape
  `tools/ncbi_transport.py`'s own "XML parsing and external entities"
  section uses for the same reason (this project has no `lxml` or
  `defusedxml` dependency, so `etree.XMLParser(resolve_entities=False)`
  from `.claude/rules/production-standards.md` is not directly available;
  stdlib `ElementTree` does not resolve external entities by default
  regardless, so the reject targets the one gap it does not close, an
  internal `<!ENTITY` inside a DOCTYPE). Tested with a hostile payload
  carrying a classic XXE `<!ENTITY>` declaration: rejected to `[]`, not
  parsed, not passed through.
- Reconciliation item, as the ticket asked, matching the precedent already
  set for `gene`'s `summary` field: `clinical_features` on `db=medgen` is an
  ADDITION beyond `requirements/Technical_specification.md` Section 6.2's
  ESummary field table, which names `conceptid`, `title`, `definition`,
  `semantictype` for MedGen and no more. Not a locked-document edit (the
  spec is read-only), a note for the Step 6.2-style reconciliation the
  `gene.summary` addition already went through.

Tests (all in my fence, all passing):
`tests/system_03_search_agent/tools/test_ncbi_eutils_actions.py`,
`TestSummary.test_medgen_clinical_features_are_parsed_out_of_conceptmeta`,
`test_medgen_with_no_clinical_features_states_an_empty_list`,
`test_medgen_clinical_features_are_capped_in_count`,
`test_medgen_conceptmeta_with_a_doctype_or_entity_is_rejected`, and a new
`TestParseMedgenClinicalFeatures` class with five direct unit tests
(non-string input, blank string, malformed XML, a feature with no `Name`
skipped, a non-HPO `SDUI` dropped, a long name capped). 78 of 78 tests in
this file pass. `ruff check` and `isort --check-only` pass.

Live proof the parser itself works: `summary()` called live against real
MedGen for UID 44287 returned `clinical_features` with 30 entries (the cap),
starting with `{"name": "Aortic regurgitation", "hpo_id": "HP:0001659"}`,
matching the ticket's own measured example exactly.

BLOCKED-STOP: the field does not yet reach the writing model, and the file
that must change is not mine. Traced the path as the ticket asked:
`core/graph.py`'s `_ncbi_efetch_output_to_structured_fields` (around line
5489) builds every `medgen_summary` row's `fields` dict by filtering
`record.fields` against `_BREADTH_FIELDS_BY_PURPOSE["medgen_summary"]`
(line 5330), which today reads `("title", "definition", "semantictype")`.
`clinical_features` is not in that tuple, so it is silently dropped at line
5539 (`{key: record.fields[key] for key in allowed if key in
record.fields}`) before any row, finding or citation is ever built from it.
Confirmed empirically, not just by reading the code: one live run of
`What phenotypic features are associated with Marfan syndrome?` at
`plain_language` depth, AFTER my parser change, still answered from
PubMed abstracts, a ClinVar/gene record and clinical trials, with a MedGen
citation present only for the disease's title, never for any clinical
feature. Full narrative and 14 citations captured in the probe script kept
in scratchpad (not committed, per file fence).

Exact change needed, for whichever builder owns `core/graph.py` next:

1. Add `"clinical_features"` to the `_BREADTH_FIELDS_BY_PURPOSE["medgen_summary"]`
   tuple at line 5330, so the field survives the filter into `row["fields"]`.
2. Likely also needed, not just the one line: `clinical_features`'s value is
   a list of dicts, not a scalar. Every other list-shaped field this
   pipeline already handles specially gets reduced to a plain, quotable
   string before synthesis (`_sra_run_accessions` for SRA's `runs`, wired at
   line 5563 for `purpose == _SRA_SUMMARY_PURPOSE`). Without an equivalent
   step for `medgen_summary`, `synthesis/grounding.py`'s exact-containment
   check (`ground_claim`, `.claude/rules/production-standards.md`'s
   deterministic accept-or-reject rule) has a Python list to match a
   sentence against instead of a string, and a written phenotype name would
   need to appear as an exact substring of that list's `repr()` to ground,
   which will not happen for readable prose. The natural fix, matching the
   `_sra_run_accessions` shape: a small helper turning the list into
   something like `"Aortic regurgitation (HP:0001659), Arachnodactyly
   (HP:0001166), ..."`, wired the same way at line ~5551 alongside the
   existing `_MEDGEN_SUMMARY_PURPOSE` unwrap step.
3. The acceptance criterion "when MedGen lists no clinical features, the
   answer must say so rather than substituting another record type" is a
   Write-step synthesis decision (what the narrative says when a finding's
   `clinical_features` is `[]`), which also lives in `core/graph.py`
   (or `synthesis/`, builder B's fence for T-8.1-04/05), not mine.

Not fixed and not claimed fixed: the acceptance criterion "5 local live
runs at each depth name at least five phenotypic features, each cited to
MedGen" cannot pass until the above lands, since the feature list never
reaches the answer today. Did not spend the run budget chasing a criterion
this fence cannot close; the one live run above is what established the
blocked-stop, not a repeated attempt at the full acceptance test.

## T-8.1-07: the same question returns the same papers each time

Status: done.

Investigation: `core/breadth_plan.py`'s `build_pubmed_term`/`disease_search_text`
are pure functions of an already-resolved disease title, and PubMed's ESearch
already defaults to `sort=relevance` (fixed 2026-09-20, `70a6c4e`), so the
term itself is stable given a stable resolved entity. Three live probes
against real NCBI E-utilities (immediate repeat, ~72s apart, and
unauthenticated) all showed the exact term
`"gastroesophageal reflux"[Title/Abstract]` returning the identical top-5
idlist every time today, so the ESearch backend is not currently
nondeterministic for this term. The real gap is architectural rather than
a live NCBI flake: the search call's own `retmax` WAS `PUBMED_RESULT_CAP`
(5), so `plan_literature_follow_up`'s deterministic reselection
(`select_ids`, highest PMID first, already order-independent) had nothing
to re-sort. It received at most five raw ids, exactly whichever five
NCBI's relevance ranking happened to place in that window on a given call,
and could only reorder that same five. The module's own docstring already
states the design intent ("the planner never re-sorts by relevance"), but
the code never gave that reselection a wider pool to work from, so a
narrow, transient shift in NCBI's own top-5-by-relevance boundary (the kind
the 2026-09-23 measurement caught, and the kind this module's own comments
already name as a known ESearch property) passed straight through to the
final citation set with nothing to absorb it.

Cause named: no hardcoded decision or model call is involved (ruled out:
entity resolution is not what varies for the bare `GERD` question, since it
resolves to the fixed CURIE `MedGen:C5563728` and the same normalised
title every time); the instability is in the zero-buffer gap between the
ESearch call's `retmax` and the follow-up's own final cap.

Fix: added `PUBMED_SEARCH_OVERFETCH` (30) in `core/breadth_plan.py`, used
as the ESearch `retmax` for the `pubmed_search` purpose in
`plan_first_stage` and `plan_topic_search`, while `PUBMED_RESULT_CAP` (5)
stays the final cap `plan_literature_follow_up`'s `select_ids` applies. A
wider candidate pool, deterministically narrowed by a fixed rule (highest
PMID), is far less sensitive to a narrow ranking shift at the old
five-result cutoff. `core/graph.py`'s own displayed summary for the search
step reads ESearch's `total_available` (the true hit count), never
`retmax`, so this is invisible to the reader except in which five papers
are consistently cited (verified by reading `_search()` in
`tools/ncbi_eutils_actions.py` and the summary line in `core/graph.py`,
both out of my fence, read-only).

Evidence:
- Live direct-probe scripts (kept in scratchpad, not committed):
  6 identical ESearch calls to real NCBI, sub-second apart, keyed:
  1 distinct set. 6 more, ~72s apart, keyed, retmax=5 and retmax=50 both:
  1 distinct set each. 6 more, unauthenticated, 1.1s apart: 1 distinct set.
  All confirm today's live ESearch is deterministic for this term; the
  architectural gap is the defect this fix closes regardless.
- Full local pipeline, BEFORE the fix, question "What causes GERD?" at
  `plain_language` depth, 6 runs: 1 distinct PubMed citation set already
  (the acceptance criterion technically already held on this exact
  question at this exact moment; the gap is real but not currently
  manifesting on this term).
- Full local pipeline, AFTER the fix, same question, 6 runs: 1 distinct
  PubMed citation set, all 6 outcome=answer. The selected set changed
  (from the old top-5-by-relevance derived set to the highest-PMID-of-30
  set), which is expected: the final five are now chosen by the module's
  own documented rule from a real pool instead of degenerating to "the
  only five ids the search call ever saw."
- `python -m pytest tests/system_03_search_agent/core/test_breadth_plan.py
  tests/system_03_search_agent/core/test_topic_search.py -q`: 109 passed
  (two existing assertions updated to reflect the new retmax split, plus
  one new test, `test_pubmed_search_overfetches_a_candidate_pool_wider_than_the_final_cap`,
  that pins the T-8.1-07 finding).
- `tests/system_03_search_agent/core/test_disease_breadth.py` (core/graph.py's
  test surface, out of my fence, read-only check): 33 passed, unaffected.
- `ruff check` and `isort --check-only` pass on all changed files.

No hardcoded decision: the overfetch buffer is a numeric robustness
constant, not a routing or classification choice: it changes how wide a
pool a fixed, already-existing rule (highest PMID) chooses from, never
which path a question takes.

Out of scope, not fixed here, and not required by this ticket's acceptance:
`reflux disease` resolving to zero results on one run in six
("Notes carried over from the old tracker", `testing/UI_fixes_done.md`)
is a routing/classifier sampling question (which entity-resolution or
clarify path a run takes), not a PubMed-search-determinism question, and
it lives upstream in `core/graph.py`/`core/clarify.py`, out of this
builder's fence.

## T-8.1-08: an NCBI outage no longer turns the build red

Status: done.

Cause: `test_a6_pinned_ground_truth_still_matches_live_medgen` in
`tests/system_03_search_agent/core/test_answer_readability_premise.py`
calls `_live_medgen_title`, which calls `_get_json`, which calls
`urllib.request.urlopen` directly against live NCBI E-utilities. The test
carried no `@premise_gate` (unlike A1, A2, A3, A6bis in this file) and no
`integration` marker, so it ran unconditionally under the unit gate's
`pytest -m "not integration"` selection (`.github/gates/gate04_unit_suite.sh`),
bypassing the hermetic guard in `tests/conftest.py`. A bare NCBI HTTP
error, unrelated to the product, would turn CI red (LEARNINGS.md,
2026-09-24, named exactly this failure mode).

Fix: added `@pytest.mark.integration` to the test. The check it performs
is unchanged, only where it runs moved, to gate 5
(`.github/gates/gate05_integration.sh`, which already runs
`pytest -m integration`).

Evidence:
- `python -m pytest -m "not integration" -q --collect-only tests/system_03_search_agent/core/test_answer_readability_premise.py`
  -> 5/6 collected, 1 deselected (test_a6 deselected).
- `python -m pytest -m "integration" -q --collect-only tests/system_03_search_agent/core/test_answer_readability_premise.py`
  -> 1/6 collected (test_a6 only), 5 deselected.
- `ruff check` and `isort --check-only` pass on the changed file.

Reconciliation: none needed, no field beyond spec touched.
