# BioProject accession probes: PRJNA31257 (G-007)

Nine facts measured live against NCBI on 2026-09-22 for BioProject accession
PRJNA31257, the accession golden question G-007 asks about: list its
BioSamples, its SRA runs and any genome assemblies, and say how to retrieve
each. Every number below came from running `probe_bioproject.py` from the
repository root; nothing here was typed from memory or from the API
documentation. No NCBI error occurred and no environment variable was
missing, so there is no blocked-stop to report, though one of the two
ESearch terms returned a genuine empty result for a record that demonstrably
exists, which gets its own section below rather than being folded quietly
into the winning term.

## Table of contents

- [Scope and method](#scope-and-method)
- [Fact 1: the two ESearch terms for BioProject](#fact-1-the-two-esearch-terms-for-bioproject)
- [Fact 2: ESummary on the BioProject record](#fact-2-esummary-on-the-bioproject-record)
- [Fact 3: ELink from BioProject to BioSample, SRA and Assembly](#fact-3-elink-from-bioproject-to-biosample-sra-and-assembly)
- [Fact 4: ESummary on the first linked ids of each target database](#fact-4-esummary-on-the-first-linked-ids-of-each-target-database)
- [Counts, wall time and linknames](#counts-wall-time-and-linknames)
- [Can the product's own ncbi_efetch tool make these exact calls](#can-the-products-own-ncbi_efetch-tool-make-these-exact-calls)
- [What a person asking this would want to see first](#what-a-person-asking-this-would-want-to-see-first)
- [Requests spent and constraints followed](#requests-spent-and-constraints-followed)
- [How to re-run these probes](#how-to-re-run-these-probes)

## Scope and method

`probe_bioproject.py` calls E-utilities `esearch.fcgi`, `esummary.fcgi` and
`elink.fcgi` directly over `urllib.request`, the same raw pattern
`probe_gene_window.py` uses in the sibling report folder
`2026-09-22_coordinate_range`. It never imports or calls anything from
`src/system_03_search_agent`: whether the product's own `ncbi_efetch` tool
could make the same calls is answered in this document by reading
`ncbi_eutils_actions.py` and `ncbi_efetch_schemas.py`, not by executing them.
`NCBI_API_KEY` was present in the repository's `.env` and every one of the
nine calls returned HTTP 200 with a well-formed JSON body, so nothing here
is recorded as blocked.

## Fact 1: the two ESearch terms for BioProject

| Term label | Raw term sent | Querytranslation | Count | Idlist | Elapsed |
|---|---|---|---|---|---|
| accn | `PRJNA31257[ACCN]` | `(PRJNA31257[ACCN])` | 0 | (empty) | 1.387s |
| plain | `PRJNA31257` | `PRJNA31257[All Fields]` | 1 | `31257` | 0.202s |

The uid carried forward into every later step is 31257, ESearch's one hit,
found by the plain unscoped term. The scoped `[ACCN]` term is a genuine trap
worth flagging on its own. NCBI's query parser recognizes `ACCN` as a real
field for db=bioproject: the querytranslation echoes `[ACCN]` back rather
than silently rewriting it to `[All Fields]`, which is how E-utilities
signals a genuinely unrecognized tag (the mechanism `ncbi_eutils_actions.py`
itself relies on for `sym`, its one live-verified hidden-but-real field for
db=gene). Yet `PRJNA31257[ACCN]` matches zero records for a BioProject that
demonstrably exists and that the plain term finds immediately. This is a
count 0, empty idlist result, a valid empty search, not an HTTP error and
not the ESearch index inconsistency the tool's own code checks for (a
nonzero count with an empty idlist); it is simply the wrong search scope for
this value. Which token shape `ACCN` actually indexes for bioproject
(perhaps the bare digits, perhaps a versioned form) was not tested further
here, to stay inside the two terms this measurement was scoped to and the
request budget; it is worth a follow-up probe before anyone builds a
BioProject lookup that reads an `[ACCN]`-scoped empty result as "this
accession does not exist."

## Fact 2: ESummary on the BioProject record

ESummary on db=bioproject, uid 31257, elapsed 0.174s. No value reached the
100-character cut.

| Field | Value |
|---|---|
| project_acc | PRJNA31257 |
| project_title | The Human Genome Project, currently maintained by the Genome Reference Consortium (GRC) |
| project_type | Primary submission |
| project_data_type | Genome sequencing |
| organism_name | Homo sapiens |
| registration_date | 2009/02/27 00:00 |

PRJNA31257 is the umbrella BioProject for the Human Genome Project and the
GRCh38 reference assembly, registered 2009/02/27. That matches what Fact 4
turns up below: the one linked assembly is GCF_000001405.40, GRCh38.p14.

## Fact 3: ELink from BioProject to BioSample, SRA and Assembly

Three ELink calls, `dbfrom=bioproject` against `db=biosample`, `db=sra` and
`db=assembly`, id 31257 in each case. Every linkname printed for every
target db, with its own linked-id count and first five ids.

| Target db | Linkname | Linked id count | First five ids | Elapsed |
|---|---|---|---|---|
| biosample | bioproject_biosample | 1 | 12121739 | 0.358s |
| biosample | bioproject_biosample_all | 1 | 12121739 | |
| biosample | bioproject_biosample_sp | 1 | 12121739 | |
| sra | bioproject_sra | 1 | 8317276 | 0.381s |
| sra | bioproject_sra_all | 1 | 8317276 | |
| assembly | bioproject_assembly | 1 | 11968211 | 0.319s |
| assembly | bioproject_assembly_all | 1 | 11968211 | |

Every linkname returned under a given target db carries the identical
single id, so deduplicating across linknames the way the product's own
`link()` function does leaves exactly one linked id per target: one
BioSample (12121739), one SRA record (8317276), one assembly (11968211).
PRJNA31257 is a single umbrella project rather than a multi-sample study, so
this 1:1:1 fan-out is a property of this specific accession, not evidence
about how a project with hundreds of BioSamples would behave.

## Fact 4: ESummary on the first linked ids of each target database

Each target database had exactly one linked id, so "first three" reduces to
the one id that exists; no target database returned zero links, so nothing
was skipped.

### BioSample, elapsed 0.204s

| Uid | Accession | Title | Organism |
|---|---|---|---|
| 12121739 | SAMN12121739 | Sample from Homo sapiens | Homo sapiens |

### SRA, elapsed 0.213s

| Uid | Runs (cut to 150 characters) | Createdate |
|---|---|---|
| 8317276 | `<Run acc="SRR9496657" total_spots="118" total_bases="95317" load_done="true" is_public="true" cluster_name="public" st [truncated]` | 2020/12/05 |

The raw `runs` field begins with leading whitespace (NCBI's usual
formatting for this field), trimmed above for the table. The 150-character
cut this task specified reaches into the middle of the first `<Run>`
element's own attribute list, so this transcript confirms at least one run,
SRR9496657, 118 spots, 95317 bases, exists inside SRA uid 8317276, but it
cannot confirm whether that uid packages exactly one run or several. The
field was not re-fetched uncut to check, staying inside the cut the task
specified and out of a question this measurement's four numbered steps did
not ask. Whoever answers G-007 for real should treat "one SRA uid" and "one
sequencing run" as two different counts until the full field, or a direct
db=sra search, confirms they are the same number here.

### Assembly, elapsed 0.183s

| Uid | Assemblyaccession | Assemblyname | Assemblystatus | Organism |
|---|---|---|---|---|
| 11968211 | GCF_000001405.40 | GRCh38.p14 | Chromosome | Homo sapiens (human) |

## Counts, wall time and linknames

| Target | Linked (deduplicated) count | Linknames seen | ELink elapsed |
|---|---|---|---|
| BioSample | 1 | bioproject_biosample, bioproject_biosample_all, bioproject_biosample_sp | 0.358s |
| SRA | 1 | bioproject_sra, bioproject_sra_all | 0.381s |
| Assembly | 1 | bioproject_assembly, bioproject_assembly_all | 0.319s |

Wall time of every one of the nine requests, in call order:

| Step | Elapsed |
|---|---|
| ESearch, term accn | 1.387s |
| ESearch, term plain | 0.202s |
| ESummary, bioproject | 0.174s |
| ELink, bioproject to biosample | 0.358s |
| ELink, bioproject to sra | 0.381s |
| ELink, bioproject to assembly | 0.319s |
| ESummary, biosample (first 3) | 0.204s |
| ESummary, sra (first 3) | 0.213s |
| ESummary, assembly (first 3) | 0.183s |

## Can the product's own ncbi_efetch tool make these exact calls

Reading `ncbi_eutils_actions.py`'s `link` function and
`_DIRECT_LINKNAME_PAIRS`, and `ncbi_efetch_schemas.py`'s
`NcbiEfetchLinkInput`: yes, the product's own `ncbi_efetch` tool can make
every one of these nine calls exactly as written. `NcbiEfetchSearchInput.db`
accepts `bioproject` and `term` is free text up to 500 characters with no
pattern restriction, so both `PRJNA31257[ACCN]` and the plain `PRJNA31257`
are legal input without ever touching `field_tags` (that field defaults to
an empty list, and `_apply_field_tags` returns an untouched term when it is
empty, so trap 1's EInfo validation never engages for either of this
probe's two terms; the `[ACCN]` tag arrived pre-embedded in `term` itself,
the same way the module's own `BRCA1[sym]` example is written).
`NcbiEfetchSummaryInput.db` lists `bioproject`, `biosample`, `sra` and
`assembly` as legal `SummaryDb` values, and `_SUMMARY_FIELDS_BY_DB` keeps
every field this probe printed: all six of `project_acc`, `project_title`,
`project_type`, `project_data_type`, `organism_name`, `registration_date`
for bioproject; all three of `accession`, `title`, `organism` for
biosample; all four of `assemblyaccession`, `assemblyname`,
`assemblystatus`, `organism` for assembly; and both `runs` and `createdate`
for sra. Nothing this measurement read would be stripped by the allowlist.
`NcbiEfetchLinkInput` requires `dbfrom` and `db` as plain strings under 20
characters and `ids` as a list under 20 items of 30 characters each, which
`bioproject`, `biosample`, `sra`, `assembly` and a one-element list holding
`31257` satisfy easily. On the linkname question: none of the three pairs
this probe used, bioproject to biosample, bioproject to sra, bioproject to
assembly, appear in `_DIRECT_LINKNAME_PAIRS` (which today holds only
pubmed to pmc), so the function's safe default applies and every
matching-dbto linksetdb contributes its ids to the union. No linkname this
probe saw would be dropped. The one real gap is not in what the tool can
express but in what a caller might type: the idiomatic scoped-search
pattern this codebase already uses for db=gene, value then bracketed tag,
produces a real but silently empty result for `PRJNA31257[ACCN]`, a trap
the schema has no way to catch, since `term` is unrestricted free text and
the tag is a genuine EInfo field rather than an unknown one.

## What a person asking this would want to see first

Someone who typed "list the BioSamples, the SRA runs and any genome
assemblies for PRJNA31257, and tell me how to retrieve each" does not want
a raw id dump first. For a project this size, one BioSample, one SRA
record, one assembly, the whole answer fits on screen, but the shape that
scales to a project with hundreds of BioSamples is: state the counts up
front in plain words, for example "this BioProject links to 1 BioSample, 1
SRA record and 1 genome assembly," then show the first handful of each by
accession and one or two descriptive fields rather than a bare numeric uid,
SAMN12121739 and Homo sapiens for the BioSample, SRR9496657 for the SRA
run, GCF_000001405.40 and GRCh38.p14 for the assembly, each as a link
rather than plain text, and say plainly where the rest can be retrieved
from rather than truncating silently. `_build_record_url` already builds
exactly those links from the same uids this probe used:
`https://www.ncbi.nlm.nih.gov/biosample/12121739`,
`https://www.ncbi.nlm.nih.gov/sra/8317276` and
`https://www.ncbi.nlm.nih.gov/assembly/11968211`, alongside
`https://www.ncbi.nlm.nih.gov/bioproject/31257` for the project itself.
None of these four templates carries the live verification the pubmed and
gene templates carry, a gap the module's own docstring already states
rather than one this probe is newly raising, so a quick live check that
each resolves to the right record page is worth doing before an answer
leans on them. A person would forgive a short wait for that count-first,
few-examples, real-links shape; they would not forgive being shown a wall
of bare integers with no indication of how many more exist or where to
actually download the underlying sequence data from.

## Requests spent and constraints followed

`probe_bioproject.py` ran once, nine requests total, two ESearch, one
bioproject ESummary, three ELink, three target-db ESummary calls, five
under the stated cap of 14. Every step slept at least 1 second before the
next (`time.sleep(1.0)`), so the whole run paced at roughly one request per
second, well inside E-utilities' unauthenticated 3 requests/second ceiling
even before the repository's own API key is counted. No credential or
email address is printed or written anywhere in this folder: the script
reads `.env` the same way `probe_gene_window.py` does, setting environment
variables without ever printing them. The script uses only relative paths
(`pathlib.Path(".")`), never an absolute local path.

## How to re-run these probes

From the repository root, with `.env` populated:

```
python3 testing/Developer/reports/2026-09-22_bioproject_accession/probe_bioproject.py
```

`ruff check testing/Developer/reports/2026-09-22_bioproject_accession` and
`isort --check-only testing/Developer/reports/2026-09-22_bioproject_accession`
both pass clean as of this measurement.
