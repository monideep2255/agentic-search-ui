# Four defects in one live TP53 answer

Established 2026-09-20 from the product owner's own paste of a live develop run,
after the day's seven fixes had deployed. The question was "Show the dbSNP record
for rs28934578 in TP53", answered in 18.9s, 12 tools, 78 sources.

These are new findings, not regressions of the day's work. Most were invisible
before, because the display cap was 20 and the volume that makes them obvious did
not exist.

## D-1: every GO biological process row is labelled with the GENE, not the process

What the reader saw, ten rows, all identical:

    Biological process records found
    TP53   8
    TP53   12
    TP53   16
    TP53   20
    TP53   24 ... 29

Ten rows carrying ten distinct citations and one repeated, useless word. A reader
learns nothing from them and reasonably concludes the product is repeating itself.

Where it comes from. `cypher_templates.gene_go_processes_one` matches
`(a:Gene {id: $e})-[:participates_in]->(x:BiologicalProcess)` and returns `x`, so
each row IS a distinct process. But the row is deliberately CITED to the gene,
through `go_attribution_param` and `to_output_rows(go_attribution_curie=...)`,
because a GO vertex carries no NCBI record URL of its own. `record_label`
(`synthesis/answer_layout.py:334`) then picks the first non-blank field of
`("name", "title", "symbol", "preferred_name")` from the row, falling back to the
finding's CURIE and value. The label being the gene symbol on every row means the
process's own name is not reaching that lookup, so the fallback wins every time.

THIS IS THE MOST DAMAGING OF THE FOUR, because it is the one a reader reads as
incompetence rather than as a caveat. Priority over the other three.

Unverified and the first thing to check: whether `BiologicalProcess` vertices in
the live graph carry a `name` at all, or only a GO id. If they carry only an id,
the fix is a label lookup rather than a field choice, and that is a different and
larger job.

## D-2: three different totals, none of them explained

The same answer showed all of these:

| Where | Number |
|---|---|
| Status strip | 78 sources from 3 layers |
| Lead sentence | of 124 available |
| Table pagination | Showing 1 to 10 of 59 |
| Note | Showing 78 of 124 matching rows |

124, 78 and 59 are all true of different things, and the answer never says which.
A reader cannot tell whether 46 records were lost, or reorganised, or never
existed. The numbers are individually honest and collectively confusing, which is
the same class of defect as the contradicting notes fixed earlier today in
`e581a05`, one layer up.

## D-3: the truncation note still claims rows are "not shown above"

    Note: this result was truncated. Showing 78 of 124 matching rows; the rest
    are not shown above.

`9cc5d63` raised the display bound to 100 precisely so rows would stop being
discarded. 124 exceeds 100, so SOMETHING is still cutting, and the note is
probably literally true. But it now sits directly above a paginated table, and a
reader who has just been given pagination reads "not shown above" as "the pager
is hiding them", which is not what it means.

Two separate questions, and they should not be answered together: whether 100 is
the right bound for a 124-row result, and whether this wording still makes sense
next to a pager.

## D-4: the answer says it did not address the entity it just addressed

    Note: this answer does not address the following entities named in the
    question: rs28934578. Ask about them individually for a complete answer.

The question was "Show the dbSNP record for rs28934578 in TP53". The answer's own
lead sentence reads "for rs28934578 and TP53", and the answer contains a variant
record and three ClinVar records. So the note contradicts the answer it is
attached to.

This is the worst of the four for TRUST, as opposed to for appearance. An answer
that tells a reader it ignored their question, while visibly not having ignored
it, teaches the reader to distrust every other note on the page, including the
ones that are true and important.

## What connects all four

Every one is a REPORTING defect rather than a retrieval defect. The agent found
the records, cited them, and rendered them. What it says ABOUT what it found is
wrong or unreadable in four different ways at once.

That matters for what to fix next. The day's work was aimed at retrieval breadth
and at showing more of it, and it succeeded: 124 rows were available where 44 used
to be. The constraint has moved. It is now the answer's account of itself.
