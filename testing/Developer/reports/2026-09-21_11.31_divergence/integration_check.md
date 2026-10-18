# The explanatory finding, checked end to end against live NCBI

Run 2026-09-21 from the repository root, with the real
`_pick_representative_field` and a real live Gene ESummary call, not a stub
and not a fixture. This is the arm the unit tests cannot be: they inject a
picker, so they cannot catch the case where the REAL picker chooses
`summary` first and the dedup then skips it.

## What was run

```
PYTHONPATH=src python3
  tools.ncbi_eutils_actions.summary(db="gene", ids=["672"])
  -> build_synth_findings([finding], core.graph._pick_representative_field)
```

## What came back

The live row's field keys, all ten now that `summary` is allowlisted:

```
chromosome, currentid, description, genomicinfo, maplocation, mim, name,
organism, status, summary
```

Two findings were emitted from that one row:

```
[1] name: BRCA1
[2] summary: This gene encodes a 190 kD nuclear phosphoprotein that plays
             a role in maintaining genomic stability, and it also acts as
             a tumor suppressor.
```

## Why each half matters

- `[1]` proves the picker still prefers `name`, so the identifying finding
  is unchanged and nothing that already worked moved.
- `[2]` proves the explanatory finding is emitted beside it, numbered
  adjacently, carrying the row's own provenance.

The summary's text passes the grounding gate verbatim, checked separately
against `ground_claim` and `claim_introduces_no_new_content`: a sentence
quoting "it also acts as a tumor suppressor" grounds, while the same idea
reworded as "acts as a brake on cell growth" is stripped. That asymmetry is
the whole reason this feature exists rather than a directive rewrite.

## What this does NOT show

No live run has been made through the full agent loop at either depth
against this code, so the DIVERGENCE between the two modes is built and
unproven. The baseline to beat is in `baseline.md`.
