# Live check: gene summary field allowlist addition

What this covers: whether NCBI's Gene ESummary `summary` field reaches the
caller through `ncbi_eutils_actions.summary()` after adding `"summary"` to
`_SUMMARY_FIELDS_BY_DB["gene"]`.

## What was run

One live call through the tool's own `summary` action, `db=gene`,
`id=672` (BRCA1), on 2026-09-21. Script: a one-off check, not committed to
the repository (it imported the tool module directly and printed the
result as JSON). Output saved verbatim in
`live_gene_summary_check_output.json`.

## Result

`status: ok`, `record_count: 1`. The returned `fields` dict carries all ten
allowlisted gene keys including `summary`, and `summary_present` is `true`.
The value begins with the same sentence confirmed live before this task was
written: "This gene encodes a 190 kD nuclear phosphoprotein that plays a
role in maintaining genomic stability, and it also acts as a tumor
suppressor." `source_url` is `https://www.ncbi.nlm.nih.gov/gene/672`.

The field flows through end to end: NCBI's ESummary response, through
`_SUMMARY_FIELDS_BY_DB`'s allowlist filter, into the `fields` dict the
caller receives. Nothing downstream of the tool re-filters it.

## Test evidence

`tests/system_03_search_agent/tools/test_ncbi_eutils_actions.py`,
`TestSummary::test_gene_summary_field_passes_through_the_allowlist`:

- Populate-check: asserts `"summary"` is present in the returned fields, its
  value matches the live-probed text, and an unlisted field is still
  filtered out.
- Mutation arm: `"summary"` was removed by hand from
  `_SUMMARY_FIELDS_BY_DB["gene"]` in the source file, the test was re-run,
  and it went red (`AssertionError: 'summary' must reach the caller for
  'db=gene', but it was filtered out; fields returned: ['name']`). The
  allowlist entry was then restored and the full module test suite
  (68 tests) passed again.
