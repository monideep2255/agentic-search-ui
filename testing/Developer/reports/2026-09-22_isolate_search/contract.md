# The isolate search: wire contract, pinned before the build

Fix-plan "Next, in order" item 1 (G-035), 2026-09-22. The product owner approved the shape on 2026-09-22: a bounded sample of isolates, each linked to its Pathogen Detection page with its AMR genes listed, plus a disclosed count and cut. This file is the contract three parallel workers build against. It is pinned before any of them starts and none of them edits it.

## What the person gets

"What Escherichia coli isolates in Pathogen Detection carry extended-spectrum beta-lactamase genes?" is answered with:

- The exact number of E. coli isolates in the current Pathogen Detection snapshot whose AMR genotype list carries a gene in the family asked about, and the number shown (the first 20 in file order).
- One row per shown isolate: its BioSample accession, strain, serovar, where and when it was collected, its full AMR genotype list, each linked to its Pathogen Detection isolate page.
- Which gene prefixes were matched and which were deliberately not, in words: for "ESBL", the blaCTX-M family only, because blaTEM and blaSHV alleles cannot be told apart as ESBL or narrow-spectrum from the name alone (blaTEM-1 is in 279,100 of 584,433 E. coli isolates and is not an ESBL). A confident wrong record is worse than a missing one.
- The organism cited to its NCBI Taxonomy record.

## Measured facts the contract rests on (probes.md, 2026-09-22)

- Taxon folder for E. coli is `Escherichia_coli_Shigella`; the complete snapshot resolved in under 2 seconds.
- The Metadata TSV is 521 MB, 584,433 rows, 67 columns; the AMR column is `AMR_genotypes`, comma-separated, items spelled `blaEC`, `blaTEM-1`, `aph(3'')-Ib`, `tet(A)`.
- A full scan of the file with a per-row predicate finished in 17.7 seconds, so counting every match is affordable inside the tool's 120-second budget.

## The tool side (worker A owns these files and no others)

Files: `src/system_03_search_agent/tools/pathogen_ftp_transport.py`, `tools/pathogen_detection.py`, `tools/pathogen_detection_schemas.py`, and `tests/system_03_search_agent/tools/test_pathogen_ftp_transport.py`, `test_pathogen_detection.py`, `test_pathogen_detection_schemas.py`, `test_pathogen_detection_premise.py`.

Transport, additive:

- `TsvScanResult` gains `match_count: int = 0` (every row the filter accepted, kept or not) and `reached_end: bool = False` (the stream hit EOF, so counts are exact).
- A new `stream_predicate_tsv_rows(url, *, predicate: Callable[[dict[str, str]], bool], deadline: float, client: httpx.AsyncClient, max_rows: int | None = None) -> TsvScanResult`: streams every row, calls `predicate(row_dict)` on each, KEEPS the first `max_rows` accepted rows and keeps COUNTING accepted rows to EOF or the deadline. Same audit hook, same `charge_one_call(tool="pathogen_detection", layer=2)`, same deadline discipline as `stream_filtered_tsv_rows`. The existing function's behaviour is byte-for-byte unchanged; sharing a private loop is fine, changing its results is not.

Schema, additive to the discriminated union:

```
class PathogenIsolateSearchInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["isolate_search"]
    taxon: <same Annotated[str, ...] as the other two modes>
    amr_gene_prefixes: Annotated[list[Annotated[str, Field(min_length=2, max_length=40, pattern=r"^[A-Za-z][A-Za-z0-9_().'\-]*$")]], Field(min_length=1, max_length=10)]
    max_isolates: Annotated[int, Field(ge=1, le=100)] = 20
```

Output, additive on `PathogenDetectionOutput`: `rows_scanned: int | None = None` and `scan_complete: bool | None = None`. Existing fields keep their meaning: `isolates` the kept sample, `isolate_count = len(isolates)`, `total_available` = every matching isolate (exact when `scan_complete` is True, a lower bound when False), `truncated = isolate_count < total_available or not scan_complete`.

Behaviour of `_isolate_search`:

- One `stream_predicate_tsv_rows` over the taxon's Metadata TSV with `max_rows=max_isolates` and the invocation's shared deadline.
- The predicate: parse `AMR_genotypes` with `_parse_pathogen_list_field`; an item matches a prefix when the item, case-folded, starts with the prefix case-folded; the row matches when any item matches any prefix. No regex built from caller input, ever.
- Each kept row becomes a `PathogenIsolate` through `_build_isolate`, `amr_genotypes` verbatim (capped as today, over-length items withheld as today).
- `status`: `ok` with one or more kept isolates; `empty` when the scan reached EOF with zero matches; `timeout` when the deadline cut the scan with zero matches. A deadline cut WITH matches is `ok`, `scan_complete=False`, `truncated=True` (F-3.5-A-01).
- Every error path returns a classified output with an actionable message, never raises, as the other modes do.
- Docstrings: the module docstring's "two modes" becomes three, with this design and the probe's numbers.

Tests: scripted transport arms for ok, empty, timeout, deadline-cut-with-matches, prefix matching (case, a prefix that must NOT match a longer gene name such as `blaTEM` versus `blaTEM-1` only when the caller asks for `blaTEM-1`; and populate checks so an arm cannot pass on an empty result), schema arms (an eleventh prefix rejected, a prefix with a regex metacharacter such as `*` rejected, `max_isolates` bounds), a transport arm proving `match_count` keeps counting past `max_rows` and `reached_end` flips, and a premise-gate arm on `Salmonella` with prefix `blaTEM-1` and `max_isolates=3` asserting `ok`, three isolates, every one carrying an item starting `blaTEM-1`, `total_available > 3`, `scan_complete` True.

## The loop side (the planner owns these files)

Files: `src/system_03_search_agent/core/isolate_search.py` (new, pure), `core/graph.py`, `core/state.py`, `tests/system_03_search_agent/core/test_isolate_search.py`, `test_isolate_search_wiring.py`, `docs/build/Debugging_guide.md`, `DECISIONS.md`, the fix plan and shipped list.

- Think recognises the shape by a fixed rule: an organism from a fixed table (E. coli, Escherichia coli, Salmonella, Listeria, Klebsiella, Campylobacter, and the others the FTP root lists that a person names in words) AND either a gene family word (ESBL, extended-spectrum beta-lactamase, carbapenemase, colistin resistance / mcr) or an explicit `bla...` / `mcr-...` gene, AND an isolate word (isolate, isolates, Pathogen Detection). It resolves the organism to `NCBITaxon:<taxid>` from the table (562 for E. coli, verified live 2026-09-22), skips the model's span confirmation so the call count is fixed, and discloses which prefixes will be searched.
- Plan plans no graph call: one `pathogen_detection` `isolate_search` call and one `ncbi_efetch` summary on `db=taxonomy` for the organism record.
- Act adds `pathogen_detection` to the layer-tool executor table with a 150-second act timeout (the tool's own 120 plus snapshot resolution), and shapes the output into rows led by the BioSample accession, capped at 20 rather than the five-row layer cap, sorted by BioSample accession.
- Write cites an isolate row through the tool's own `build_citation`, and the incompleteness note states the count and the cut in the person's words.

## The document (worker B owns this file and no other)

`testing/Isolate_search_queries_and_workflow.md`: the test queries, written from the user's chair, and the workflow for running them.
