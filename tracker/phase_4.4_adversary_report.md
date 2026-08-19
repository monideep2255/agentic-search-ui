# Build phase 4.4 adversary report, round 1

Agent: adversary
Date: 2026-08-19
Branch: `phase/4.4-kgx-export`
Round: 1 of a maximum of 2

No finding in this report sits inside code written to fix an earlier finding in this
phase. There is no `Regression of:` line anywhere below, so this report does not trip
the mid-round phase stop condition.

## Transport state

`python3 tracker/preflight.py --transport graph` returned `graph ok, TCP 15432 open in
2ms` before live work, between every live probe, and after the last one. Every live
result below was read from a healthy transport. No finding here is a dead-transport
misread.

## Where I attacked

The premise gate states its own coverage and names four omissions: multi-hop traversal,
every edge label but `gene_associated_with_condition`, non-Gene seeds, and concurrent
exports. All four turned out to contain defects, and three of the four blocking findings
below live inside that stated blind spot. The fourth (the cap-attribution defect) is
visible from the gate's own truncation case but is not asserted on.

## Merge bar summary

| Finding | Severity | Reachable | Reproduced | Blocks merge |
|---------|----------|-----------|------------|--------------|
| F-4.4-50 | critical | yes | yes, live | yes |
| F-4.4-51 | major | yes | yes, live | yes |
| F-4.4-52 | major | yes | yes, live | yes |
| F-4.4-53 | major | yes | yes, injected delay | yes |
| F-4.4-54 | major | yes | yes | yes |
| F-4.4-55 | minor | latent | yes, synthetic | no, track |
| F-4.4-56 | minor | yes | yes, live | no, track |
| F-4.4-57 | minor | yes | yes, live | no, track |
| F-4.4-58 | minor | yes | yes | no, track |
| F-4.4-59 | minor | yes | yes | no, track |
| F-4.4-60 | minor | yes | yes | no, track |
| F-4.4-61 | minor | latent | yes | no, track |

## Findings

### F-4.4-50: a default export traverses only the first edge label that matches the seed, while the manifest asserts all fourteen were traversed

Status: filed
Raised by: adversary
Severity: critical
Round: 1
Reachable: yes. This is the plainest possible invocation of the shipped command, `s3-kgx-export NCBIGene:7157 --output-dir DIR`, with no flags.
Reproduced: yes, live against the graph.
Location: `src/system_03_search_agent/export/traversal.py:522-534` (the edge-label loop consumes the whole shared node budget on whichever label comes first), `src/system_03_search_agent/export/kgx.py:335`, `src/system_03_search_agent/export/manifest.py:138-158` (`edge_labels` is recorded from the request, not from what ran)

What happened: `traverse_subgraph` walks `EDGE_LABELS` in its fixed row-count-descending
order and draws every query's `LIMIT` from one shared `max_nodes` / `max_edges` budget.
No budget is reserved per label. `mentioned_in` is second in that order and is a hub
label, so for any Gene seed it exhausts the entire node cap before the loop reaches the
twelfth, thirteenth or fourteenth label. `gene_associated_with_condition` is thirteenth.

The export of TP53 that this phase pinned its ground truth from therefore contains none
of that ground truth:

```
$ PYTHONPATH=src venv/bin/python -m system_03_search_agent.export.cli \
    NCBIGene:7157 --output-dir .../live_A
wrote 500 nodes and 499 edges to .../live_A
This export covers Layer 1, the pre-ingested knowledge graph, only. ...
truncated: hit the max_nodes cap at 500; the export is incomplete
truncated: hit the max_edges cap at 1000; the export is incomplete

edge_labels claimed : ['has_mesh_annotation', 'mentioned_in', 'in_taxon',
  'actively_involved_in', 'participates_in', 'located_in', 'orthologous_to',
  'has_phenotype', 'is_sequence_variant_of', 'cited_in', 'subclass_of',
  'close_match', 'gene_associated_with_condition', 'exact_match']
predicates present  : Counter({'biolink:mentioned_in': 499})
node categories     : Counter({'biolink:Article': 499, 'biolink:Gene': 1})
```

Fourteen labels are named in `manifest.json` under a key whose own docstring
(`manifest.py:108`) defines it as "the edge labels actually traversed". One was
traversed. Twelve of the fourteen were never queried at all: they are skipped without a
query when `EDGE_ENDPOINTS` rules them out for the seed's label, and the rest are cut off
by the exhausted budget, and neither case leaves any trace anywhere in the output.

Why this is critical rather than major: the phase's own premise gate opens by naming the
failure it exists to prevent as "a file that is well-formed and wrong: correct TSV,
correct headers, correct row count, and a subgraph that is not the one the seed names".
This is that file, produced by the default invocation, and the manifest actively
certifies fourteen-label coverage that did not happen. `truncated: max_nodes` is present
but does not carry the information a consumer needs: it says the subgraph is a bounded
sample, not that it is a sample of one relation type out of fourteen. A downstream
consumer asking "which diseases is TP53 associated with" against these files gets zero
rows and no signal that the question was never asked of the graph.

The gate cannot see this. Five of its six cases pass an explicit
`edge_labels=("gene_associated_with_condition",)`, and the sixth asserts only that
`max_nodes` appears in the truncation list. "Every edge label but
`gene_associated_with_condition`" is the second item on the gate's own stated omission
list.

History:
- 2026-08-19 adversary: filed

### F-4.4-51: the truncation report names caps that were never reached, and the real limiter is never disclosed

Status: filed
Raised by: adversary
Severity: major
Round: 1
Reachable: yes. It fires on any export that hits the ambiguity branch, which includes every truncated export I produced, live and synthetic.
Reproduced: yes, live, twice, with two different shapes.
Location: `src/system_03_search_agent/export/traversal.py:553-572` (the `got_more` fallback marks both caps unconditionally) and `traversal.py:534` (`requested = min(limit_n + 1, MAX_ROW_LIMIT)`, with no re-query for the remainder)

What happened: two distinct wrong statements come out of the same block.

First, a cap that was not reached is reported as hit. `requested` is clamped to
`MAX_ROW_LIMIT` (500), so a single query can never return more than 500 rows, and the
traversal never issues a follow-up query to collect the rest. Any `max_nodes` or
`max_edges` above 500 is therefore silently a no-op for a single-label, single-direction
hop, and the stop is attributed to the cap anyway:

```
$ PYTHONPATH=src venv/bin/python -m system_03_search_agent.export.cli \
    NCBIGene:7157 --output-dir .../live_E --edge-label mentioned_in \
    --max-nodes 1200 --max-edges 1200
wrote 501 nodes and 500 edges to .../live_E
truncated: hit the max_nodes cap at 1200; the export is incomplete
truncated: hit the max_edges cap at 1200; the export is incomplete

  caps: {'max_edges': 1200, 'max_nodes': 1200, 'time_budget_s': 60.0}
  counts: {'edges': 500, 'nodes': 501}
  truncation: [{'cap': 'max_nodes', 'value': 1200}, {'cap': 'max_edges', 'value': 1200}]
```

501 nodes did not hit a cap of 1200. 500 edges did not hit a cap of 1200. Both printed
lines and both manifest entries are false, and the mechanism that actually stopped the
traversal, an internal constant of 500 rows per query, appears nowhere in `caps`, nowhere
in `truncation`, and nowhere on stdout. The user's only lever, raising the caps, cannot
change the outcome, and nothing tells them that.

Second, the edge cap is reported as hit on runs nowhere near it, because the fallback at
`traversal.py:571-572` marks `max_nodes` and `max_edges` together whenever `got_more` is
true and neither cap reads as exhausted by remaining room. That is the normal case, not
the rare one, since the caps are consumed by the rows of the very query being judged:

```
$ ... MedGen:C0205770 --output-dir .../live_D --max-nodes 40
wrote 15 nodes and 40 edges to .../live_D
truncated: hit the max_nodes cap at 40; the export is incomplete
truncated: hit the max_edges cap at 1000; the export is incomplete
  counts {'edges': 40, 'nodes': 15} trunc True
         [{'cap': 'max_nodes', 'value': 40}, {'cap': 'max_edges', 'value': 1000}]
```

Fifteen nodes are reported as having hit a node cap of 40. Forty edges are reported as
having hit an edge cap of 1000.

The intent, per the comment at `traversal.py:560-570`, is honest conservative
disclosure, and disclosing "there may be more" is right. Naming a specific cap and a
specific value that were provably not reached is not conservative, it is wrong, and it is
the kind of wrong that survives inspection: the manifest is internally contradictory
(`caps.max_nodes: 1200` beside `counts.nodes: 501` beside `truncation: max_nodes=1200`)
and nothing in the phase's tests compares those three fields against each other. The
honest form is a distinct reason, for example `per_query_row_limit=500`, or a truncation
entry with no cap name at all.

History:
- 2026-08-19 adversary: filed

### F-4.4-52: a seed that exists in the graph is reported as not existing in the graph

Status: filed
Raised by: adversary
Severity: major
Round: 1
Reachable: yes. `NamedThing` is a real label the live graph carries, its vertices carry `OMIM:` CURIEs, and no `OMIM:` CURIE and no `NamedThing` vertex can ever resolve as a seed.
Reproduced: yes, live, in two steps: the vertex read directly off the graph, then the export denying it exists.
Location: `src/system_03_search_agent/export/traversal.py:129-147` (`_invert_label_curie_prefixes`), `traversal.py:388-389` (an unmapped prefix yields zero candidate labels and zero queries), `traversal.py:651-655` (the `empty_reason` wording), against `src/system_03_search_agent/tools/graph_schema_constants.py:122` (`"NamedThing": ()`)

What happened: `_lookup_seed` resolves a seed only through `LABEL_CURIE_PREFIXES`.
`NamedThing` maps to the empty tuple there, so no CURIE can ever select it, and `OMIM` is
not a key in that table under any label. A `NamedThing` seed therefore issues zero graph
queries and returns "not in the graph".

The vertices are real. Read live off the graph:

```
== NamedThing sample (2.0s, 3 rows)
   label=NamedThing props={"id": "OMIM:100070", "name": "[stub] OMIM:100070",
     "xrefs": "", "source": "stub", "agent_type": "", "source_url": "",
     "knowledge_level": ""}
   label=NamedThing props={"id": "OMIM:100100", ...}
   label=NamedThing props={"id": "OMIM:100200", ...}
```

The export, on the first of those three:

```
$ ... OMIM:100070 --output-dir .../live_C
wrote 0 nodes and 0 edges to .../live_C
empty export: 0 of 1 requested seed CURIE(s) resolved to a vertex in the graph: OMIM:100070
```

Exit code 0. The statement "resolved to a vertex in the graph" is false about a vertex
the graph demonstrably holds, and it is the only explanation the user is given. This is
worse than a crash: it is an authoritative-sounding negative answer about Layer 1
contents from a tool whose whole purpose is to be a faithful window onto Layer 1.

Two things follow that the fix should cover, not just the wording. `NamedThing` is the
dangling-endpoint stub label the five-database merge produces, and the same
`graph_schema_constants` file argues at line 17 that "a generator that cannot name it
cannot query it"; the seed resolver is exactly such a generator and cannot query it. And
`close_match` and `exact_match`, the two labels with no declared endpoint pair, are
precisely the labels that attach to these stubs, so a whole region of the graph is
reachable at hop two but never as a seed.

History:
- 2026-08-19 adversary: filed

### F-4.4-53: two exports into one output directory produce a torn, self-certifying bundle, with no lock and no detection

Status: filed
Raised by: adversary
Severity: major
Round: 1
Reachable: yes. Two scheduled batch runs pointed at one directory is an ordinary operational mistake, and nothing in the command, the manifest, or the documentation warns against it.
Reproduced: yes, with an injected delay to widen a real race window. There is no lock, no temp-file-then-rename, and no directory-contents check anywhere in the write path, so the window is genuine; the sleep only makes it deterministic.
Location: `src/system_03_search_agent/export/kgx.py:317-352` (three independent writes into a shared directory, no atomicity across them)

What happened: `export_subgraph` writes `nodes.tsv`, then `edges.tsv`, then
`manifest.json`, each as its own unsynchronized overwrite. Two concurrent calls interleave
freely. Both return successfully.

Probe: export A seeded from a gene with four disease neighbours, export B seeded from a
gene with none, both into the same directory, A stalled 0.6s after writing its
`nodes.tsv`.

```
nodes.tsv rows on disk : 1 ['NCBIGene:2']
edges.tsv rows on disk : 4
manifest seeds         : ['NCBIGene:1']
manifest counts        : {'edges': 4, 'nodes': 5}
manifest truncated     : False
TORN? True
```

The bundle on disk is `nodes.tsv` from B, `edges.tsv` from A, `manifest.json` from A.
Every one of the four edges references a subject absent from `nodes.tsv`, so this is a
KGX file with 100 percent dangling edges, and the manifest beside it certifies five nodes,
four edges, `truncated: false`, seeds `['NCBIGene:1']`. Nothing failed. Both processes
exited 0.

Concurrency is the fourth item on the premise gate's own stated omission list. The
minimum fix is a directory lock or a write to a temporary sibling directory followed by
an atomic rename, so a reader never sees a half-replaced bundle; a manifest that records
a checksum or row count the reader can verify against the TSV files would also make the
torn state detectable rather than silent.

History:
- 2026-08-19 adversary: filed

### F-4.4-54: a usage error is reported to the user as a graph-transport failure, and the actionable message is discarded

Status: filed
Raised by: adversary
Severity: major
Round: 1
Reachable: yes. A typo in `--edge-label` is the most likely mistake a first-time user of this command makes, and there are fourteen valid values that are not listed in `--help`.
Reproduced: yes, offline, no graph needed.
Location: `src/system_03_search_agent/export/cli.py:312-330` (the catch-all prints only `type(exc).__name__`)

What happened: `_validate_edge_labels` (`traversal.py:266-273`) raises a `ValueError`
carrying exactly the message the user needs, naming the offending label and listing all
fourteen valid ones. The CLI's catch-all swallows `str(exc)` and substitutes a fixed
message about the SSH tunnel:

```
=== bogus edge label -> exit 1
  STDERR: s3-kgx-export: the export failed (ValueError); check that the output
  directory is writable and that the graph transport (the SSH tunnel to the
  Hetzner graph host) is reachable, then retry

=== negative hops -> exit 1
  STDERR: s3-kgx-export: the export failed (ValueError); check that the output
  directory is writable and that the graph transport (the SSH tunnel to the
  Hetzner graph host) is reachable, then retry
```

Both are pure usage errors. Neither has anything to do with the tunnel, the output
directory, or the transport, and the message sends the user to diagnose infrastructure
that is working. `production-standards`' retry-safety gate requires an error to say what
to do next; this one says what to do next and it is the wrong thing. It also returns
`EXIT_RUNTIME_ERROR` (1) where `EXIT_USAGE_ERROR` (2) is correct, so a wrapping script
cannot tell the two apart either.

The catch-all's reasoning (redact an exception from a module this file cannot inspect) is
sound as a default. The fix is to let `ValueError` through as a usage error with its own
message before the catch-all runs, since `ValueError` is the one shape `export_subgraph`
documents itself as raising for bad arguments, and it is raised before any credential is
touched.

History:
- 2026-08-19 adversary: filed

### F-4.4-55: a literal pipe in a value is indistinguishable from the list separator after serialization

Status: filed
Raised by: adversary
Severity: minor
Round: 1
Reachable: latent. Every sampled `xrefs` field on the live graph is the empty string across seven vertex labels, so I found no live instance. The exposure is real because this module pipe-joins arbitrary graph property values, where the upstream System 1 exporter it copies the contract from controls the values it joins.
Reproduced: yes, with a synthetic property value.
Location: `src/system_03_search_agent/export/kgx.py:101-113` (`serialize_value`)

What happened: `serialize_value` joins list items with `|` and passes scalars through
unchanged, and neither path escapes an embedded `|`. A two-item list whose first item
contains a pipe is written identically to a three-item list:

```
input   listy = ["x|y", "z"]      output column: x|y|z
input   piped = "alpha|beta"      output column: alpha|beta
```

A downstream KGX reader splitting multi-valued columns on `|` reconstructs
`["x", "y", "z"]` from the first and `["alpha", "beta"]` from the second. `csv`'s
`QUOTE_MINIMAL` does not help, since `|` is not the delimiter, not the quote character,
and not a line terminator. Nothing counts or discloses the ambiguity.

Note the tightly related thing that does work: tab, newline, carriage return and double
quote all round-trip correctly, verified at byte level. Pipe is the one separator with no
escape.

History:
- 2026-08-19 adversary: filed

### F-4.4-56: every edge cites its subject's record page rather than the record that evidences the edge

Status: filed
Raised by: adversary
Severity: minor
Round: 1
Reachable: yes, it is every edge in every export.
Reproduced: yes, live.
Location: `src/system_03_search_agent/export/kgx.py:233` (`_resolve_source_url(subject_curie, ...)`)

What happened: `_edge_row` derives `source_url` from `subject_curie` only, and keeps a
stored edge `source_url` when it matches the host pattern, which per finding F-2.1-B06 is
also the subject's page. Across the 499-edge TP53 export:

```
=== distinct edge source_url count ===
1 distinct urls over 499 edges
[('https://www.ncbi.nlm.nih.gov/gene/7157', 499)]
sample edge: {'subject': 'NCBIGene:7157', 'predicate': 'biolink:mentioned_in',
  'object': 'PMID:1088347', 'source': 'NCBI Gene',
  'source_url': 'https://www.ncbi.nlm.nih.gov/gene/7157', ...}
```

For a `mentioned_in` edge, the record that actually evidences the mention is the article
(`PMID:1088347`), and the citation resolves to the gene page. The citation is host-pinned
and points at a real record, just not the one the assertion is about, which is the exact
class F-2.1-B06 and F-2.1-C04/C05 were filed for on the `cypher_query` path. Filed as
minor rather than major because it faithfully reproduces what the graph itself stores and
what the mature `cypher_provenance` module already treats as the accepted attribution, so
it is an inherited convention rather than a defect this phase introduced. It is worth an
explicit decision, not a silent inheritance.

Related and clean, so recorded here rather than as its own finding: node provenance
checks out. Every sampled label's stored `source_url` agrees with its own CURIE
(`MedGen:C0205770` to `/medgen/C0205770`, `PMID:1` to `/pubmed/1/`, `ClinVar:2` to
`/clinvar/variation/2`, `NCBITaxon:1` to the taxonomy browser id 1), and the MeSH nodes'
stored `meshb.nlm.nih.gov` URL correctly fails the host pin and falls back to the derived
NCBI page rather than shipping an off-host URL.

History:
- 2026-08-19 adversary: filed

### F-4.4-57: `summary_lines` is dead code, and the count of rows with no provenance never reaches the user

Status: filed
Raised by: adversary
Severity: minor
Round: 1
Reachable: yes, on any export containing stub nodes.
Reproduced: yes, live.
Location: `src/system_03_search_agent/export/manifest.py:174-201` (never called from production code), `src/system_03_search_agent/export/cli.py:229-253` (re-derives its own summary)

What happened: `manifest.summary_lines` exists, per its own docstring, so that the
command's output cannot drift from the manifest. `grep -rn summary_lines src tests`
returns six hits, all six in `test_kgx_manifest.py`, and none in `src/`. The CLI's
`_print_disclosures` re-derives the text the function was written to prevent re-deriving,
and omits the one line `summary_lines` carries that it does not: the count of rows written
with an empty `source_url`.

Live consequence, from the Disease-seed export:

```
  empty source_url rows: 13        (of 55 rows written)
```

Thirteen of fifty-five rows shipped with no citation at all, and the command printed
nothing about it. The count is in `manifest.json`, which satisfies T-4.4-04's written
criterion, but the same ticket's next criterion asks for the truncation and limitation
statements on the command's own output, and a quarter of the rows being uncitable is the
same class of fact. Six tests currently grade a function no shipped path calls.

History:
- 2026-08-19 adversary: filed

### F-4.4-58: an export into a non-empty directory silently overwrites and leaves stale siblings

Status: filed
Raised by: adversary
Severity: minor
Round: 1
Reachable: yes, re-running an export into the same directory is the normal workflow.
Reproduced: yes.
Location: `src/system_03_search_agent/export/kgx.py:317-318`, `src/system_03_search_agent/export/cli.py:276-285`

What happened: an output directory pre-loaded with a previous run's files is overwritten
without a word, and any file the new run does not itself write survives beside the new
bundle:

```
### existing NON-EMPTY output dir (stale files from a previous export)
  cli exit: 0 dir now: ['edges.tsv', 'extra_from_last_run.tsv', 'manifest.json',
                        'nodes.tsv']
```

`extra_from_last_run.tsv` is now a stale file sitting inside a bundle whose manifest does
not mention it, and a consumer reading the directory as one export sees it as part of the
export. A `--force` flag, or simply refusing a non-empty directory unless told otherwise,
closes this.

History:
- 2026-08-19 adversary: filed

### F-4.4-59: the output directory is neither resolved nor constrained, and a failed write is only discovered after the traversal is paid for

Status: filed
Raised by: adversary
Severity: minor
Round: 1
Reachable: yes.
Reproduced: yes.
Location: `src/system_03_search_agent/export/cli.py:276-278`, `src/system_03_search_agent/export/kgx.py:317-318`

What happened: two related things.

A symlinked output directory, and a path containing `..`, both write outside the location
the user typed, with no resolution and no message:

```
### output_dir is a SYMLINK pointing outside
  cli exit: 0 files landed in outside/: ['edges.tsv', 'manifest.json', 'nodes.tsv']
### output_dir with .. traversal
  cli exit: 0 escaped exists: True
```

T-4.4-05's criterion "writes no file outside the output directory it was given" is
arguably still met, since the files are inside the directory as named. It is worth
recording that the guarantee is nominal rather than enforced: nothing calls `resolve()`
and nothing reports where the files actually landed.

Second, writability is never checked before the graph work. A read-only output directory
survives `mkdir(exist_ok=True)`, so the entire traversal runs, and only then does the
first `_write_tsv` fail:

```
### read-only output dir
  cli exit: 1 stderr: s3-kgx-export: the export failed (PermissionError); check that
  the output directory is writable and that the graph transport ... is reachable
```

The message is right here, but the whole graph cost was spent to get to it. A pre-flight
write probe before the traversal starts costs one file operation.

By contrast, the output-directory-is-a-file case is handled cleanly and reports well:
`could not create the output directory ... (FileExistsError); check the path and its
permissions and retry`.

History:
- 2026-08-19 adversary: filed

### F-4.4-60: duplicate seeds are not deduplicated, and cost a full extra round of graph queries each

Status: filed
Raised by: adversary
Severity: minor
Round: 1
Reachable: yes, a seed list assembled from a script or a file will contain duplicates.
Reproduced: yes.
Location: `src/system_03_search_agent/export/traversal.py:482-504` (the seed loop appends to `frontier` per requested seed, not per distinct resolved vertex)

What happened: the same CURIE passed twice resolves twice and is expanded twice. Every
hop query for that vertex is issued a second time and every returned edge is discarded by
`seen_edge_ids`:

```
### 6. duplicate seeds
  resolved ['NCBIGene:1', 'NCBIGene:1'] calls 4 nodes 2 edges 1
```

Four graph calls where two would do, on a transport this phase has already recorded as
fragile under load, and `seeds_resolved` in the manifest double-counts. `nodes` is keyed
by CURIE so the output itself is correct; only the cost and the count are wrong. Note the
manifest's `seeds` field is deliberately never deduplicated (`manifest.py:105-107`), which
is right; `frontier` and `seeds_resolved` are a different question.

History:
- 2026-08-19 adversary: filed

### F-4.4-61: no length cap on a seed CURIE

Status: filed
Raised by: adversary
Severity: minor
Round: 1
Reachable: latent. It is safely bound, so the exposure is resource use, not injection.
Reproduced: yes.
Location: `src/system_03_search_agent/export/cli.py:70` (`_CURIE_PATTERN` has no length bound), `src/system_03_search_agent/export/traversal.py:392-399`

What happened: a 5000-character seed passes the CURIE shape check and is sent to the graph
as a bound parameter. It is not an injection (the PREPARE and EXECUTE path holds, see
below), but `production-standards`' multi-agent pipeline gate requires `maxLength` on
every string field precisely so one oversized input cannot be used as a lever. A bound of
a couple of hundred characters costs nothing; the longest real CURIE in the graph's prefix
set is well under fifty.

History:
- 2026-08-19 adversary: filed

## What I tried that failed to break it

This is evidence too, and several of these are the places I expected to find defects.

- TSV escaping. A property value containing a tab, a newline, a carriage return and a
  double quote all round-trip exactly through `csv.DictReader`, verified at byte level:
  `b'...\t"TP\t53"\t...\t"a\rb"\t"line1\nline2"\t...\t"he said ""hi"""\r\n'`, parsed back
  to `'TP\t53'`, `'a\rb'`, `'line1\nline2'`, `'he said "hi"'`. No column shifted and no
  row split. `QUOTE_MINIMAL` is doing exactly what the docstring at `kgx.py:140-145`
  claims. Only the pipe (F-4.4-55) escapes this.
- Cycles. A three-Gene `orthologous_to` cycle at `hops=3` terminates cleanly at three
  nodes, three edges, seven graph calls, no double counting, no re-walk, `truncated:
  false`. `visited` and `seen_edge_ids` hold.
- Multi-hop correctness, live. TP53 at `hops=2` over
  `gene_associated_with_condition` and `has_phenotype` returned 67 nodes (55 Gene, 12
  Disease) and 74 edges, zero dangling edges, `truncated: false`, in 47.9 seconds inside
  its 60-second budget. Direction handling at the second hop is right: a Disease frontier
  node correctly expands `gene_associated_with_condition` inbound and pulls the other
  genes associated with that disease. This is the gate's first stated omission and the
  traversal is correct on it.
- Non-Gene seeds that have a mapped prefix. A `MedGen:` Disease seed and a `MeSH:`
  OntologyClass seed both resolve and traverse correctly, including the ambiguous MedGen
  prefix that maps to both Disease and PhenotypicFeature. Only the unmapped-prefix case
  fails, which is F-4.4-52.
- Query injection. Every seed value reaches AGE through the existing PREPARE and EXECUTE
  binding; no query text in `traversal.py` is built with an f-string or `.format()`. My
  fake graph raises on any query shape outside the three documented ones and never fired
  across every probe in this report, including multi-hop, mixed-endpoint and NamedThing
  paths. Hostile seeds (a colon in the local id, a Unicode look-alike colon `U+A789`, the
  empty string, 5000 characters) are either rejected at the CLI with the expected-shape
  message or bound safely.
- Variable-length patterns. None emitted, on any path I could reach.
- Credential leakage. No password, DSN or environment value appeared in any stdout or
  stderr I produced, on the success or the failure path, including the catch-all in
  F-4.4-54 (which is over-redacted, not under-redacted).
- Wall-clock runaway. Bounded. A two-hop traversal issues one query per frontier node per
  label per direction, which is O(n) queries, and the time budget stops it and records the
  cap rather than hanging. The per-call timeout clamps to a floor of one second rather
  than going negative.
- The empty and absent-seed path. An unresolvable seed writes both TSV files with their
  headers and zero rows, plus a manifest reason, no crash. (The reason's wording is wrong
  in the specific NamedThing case, F-4.4-52; the mechanism is right.)
- Output directory as an existing file. Clean, actionable, correctly attributed error.
- Baseline. `venv/bin/python -m pytest` over the four offline export test files:
  `90 passed in 0.28s`. Nothing in this report is a pre-existing red test.

## Coverage this report does not claim

Stating it so the gap is arguable rather than discovered later, the same standard the
premise gate holds itself to.

- I did not exercise `pathogen_detection`-scale volumes or a seed with more than roughly
  500 neighbours of more than one label at once.
- I did not test a graph vertex carrying a label outside the eleven in `VERTEX_LABELS`. If
  one exists, `_hop_cypher` would raise `ValueError` mid-traversal at hop two for
  `close_match` or `exact_match`, which `traverse_subgraph` does not catch. I could not
  enumerate the live label set cheaply enough to rule it in or out, so this is reasoned,
  not reproduced, and is deliberately not filed as a finding.
- I did not test the console script on `$PATH`, since it does not exist in this
  environment (the already-filed F-4.4-01). Every invocation above used `python -m`.
- I did not attack the manifest's `graph_snapshot_version` fallback beyond noting it is a
  hardcoded default (`ncbi_kg_v1_2026-04-22`) that will silently persist as the recorded
  provenance if `GRAPH_SNAPSHOT_VERSION` is never set, which it is not in this
  environment.
