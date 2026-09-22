# Coordinate-range probes: BRCA1 window (chr17, GRCh38)

Three facts measured live against NCBI on 2026-09-22 for the window
chromosome 17, 43044295 to 43125364, assembly GRCh38, the window the
planning task named as the BRCA1 locus (Entrez Gene uid 672). Every number
below came from running `probe_gene_window.py` or `probe_overlap_window.py`
from the repository root; nothing here was typed from memory or from the
API documentation. No NCBI error occurred and no environment variable was
missing, so there is no blocked-stop to report.

## Table of contents

- [Scope and method](#scope-and-method)
- [Fact 1: the Gene search term for a window](#fact-1-the-gene-search-term-for-a-window)
- [Fact 2: the coordinate-overlap action live](#fact-2-the-coordinate-overlap-action-live)
- [Fact 3: the shape of the numbers](#fact-3-the-shape-of-the-numbers)
- [Requests spent and constraints followed](#requests-spent-and-constraints-followed)
- [How to re-run these probes](#how-to-re-run-these-probes)

## Scope and method

`probe_gene_window.py` calls E-utilities `esearch.fcgi` and `esummary.fcgi`
on db=gene directly over `urllib.request`, the same pattern
`probe_gds_search.py` uses in the sibling report folder
`2026-09-22_item1_lost_search`. `probe_overlap_window.py` calls
`system_03_search_agent.tools.ncbi_coordinate_overlap.coordinate_overlap`
directly. Reading `src/system_03_search_agent/tools/ncbi_efetch.py` first
confirmed that function needs no harness or transport object: `ncbi_efetch.py`
itself dispatches the `coordinate_overlap` action with `return await
coordinate_overlap(resolved)`, no client override and no wrapping harness,
so calling it directly with just the validated Pydantic input is the same
call production and the live premise test
(`test_ncbi_efetch_premise.py` cases 17 to 19, through `ncbi_efetch`) both
make. `NCBI_API_KEY` was present in the repository's `.env` and both calls
returned `status: ok`, so nothing was missing and nothing is recorded as
blocked.

Both scripts print their real output; nothing in the tables below was
computed except by reading a number straight off that output or, where
stated explicitly, by a plain arithmetic comparison against the window
(min and max of a record's own reported coordinates against the window's
start and end).

## Fact 1: the Gene search term for a window

### The three ESearch terms

All three terms returned the identical count (8) and the identical eight
gene ids, in the same order, including 672. They are not byte-identical in
how NCBI echoes them back: the position portion of every term always
resolved to the real underlying index tag `CHRPOS` with zero-padded
numbers, but the chromosome and organism portions were echoed closer to
whatever was typed.

| Term | Raw term sent | Querytranslation | Count | Elapsed |
|------|----------------|-------------------|-------|---------|
| a | `17[CHR] AND 43044295:43125364[CPOS] AND human[ORGN]` | `17[CHR] AND 000043044295[CHRPOS] : 000043125364[CHRPOS] AND "Homo sapiens"[Organism]` | 8 | 0.232s |
| b | `17[Chromosome] AND 43044295:43125364[Base Position] AND "Homo sapiens"[Organism]` | `17[Chromosome] AND 000043044295[CHRPOS] : 000043125364[CHRPOS] AND "Homo sapiens"[Organism]` | 8 | 0.213s |
| c | `17[chr] AND 43044295:43125364[chrpos] AND 9606[taxid]` | `17[chr] AND 000043044295[CHRPOS] : 000043125364[CHRPOS] AND 9606[taxid]` | 8 | 0.150s |

The idlist for all three: `672, 111589215, 110485084, 140660, 111589216,
129664047, 126862571, 127886930`.

Which term to use: any of the three works, since all three return the same
count and the same ids. Term c is the most literal reflection of what NCBI
actually indexes, since its `9606[taxid]` and `[chrpos]` both survive the
translation unchanged rather than being rewritten. Term a is the shortest.
Recommendation: use term a for brevity, since equivalence was measured
directly rather than assumed. This result was reproduced on two separate
runs of the script (once before timing was added, once after), with an
identical count and idlist both times.

### Is uid 672 in the results

Yes. 672 is the first id in the idlist for all three terms.

### ESummary on the winning term's idlist

One batched ESummary call (0.184s) on all 8 ids from term a.

| Uid | Symbol | Description | Chr | Chrstart | Chrstop | Chraccver |
|-----|--------|--------------|-----|----------|---------|-----------|
| 672 | BRCA1 | BRCA1 DNA repair associated | 17 | 43170326 | 43044294 | NC_000017.11 |
| 111589215 | LOC111589215 | BRCA1 promoter region | 17 | 43124494 | 43127555 | NC_000017.11 |
| 110485084 | LOC110485084 | BRCA1 intronic recombination region | 17 | 43119628 | 43120299 | NC_000017.11 |
| 140660 | RPL21P4 | ribosomal protein L21 pseudogene 4 | 17 | 43079260 | 43079815 | NC_000017.11 |
| 111589216 | LOC111589216 | BRCA1 intron 2 regulatory region | 17 | 43119736 | 43120060 | NC_000017.11 |
| 129664047 | LOC129664047 | ReSE screen-validated silencer GRCh37_chr17:41224055-41224260 | 17 | 43072037 | 43072242 | NC_000017.11 |
| 126862571 | LOC126862571 | BRD4-independent group 4 enhancer GRCh37_chr17:41243136-41244335 | 17 | 43091118 | 43092317 | NC_000017.11 |
| 127886930 | LOC127886930 | OCT4-NANOG hESC enhancer GRCh37_chr17:41214996-41215531 | 17 | 43062978 | 43063513 | NC_000017.11 |

### A trap this measurement found: chrstart can be greater than chrstop

Gene 672's own record reads `chrstart=43170326, chrstop=43044294`, chrstart
greater than chrstop, because BRCA1 is on the minus strand and Gene
ESummary reports these two fields in transcription order, not in ascending
genomic order. `dbvar` and `clinvar` placements, by contrast, are already
genome-ascending (confirmed by reading `ncbi_coordinate_overlap.py`, whose
`_overlaps` predicate assumes `chr_start <= chr_end`). Any code that reads
Gene's `genomicinfo.chrstart`/`chrstop` and applies the same ascending-order
overlap predicate without first taking the min and max would silently
reject every minus-strand gene, since `chr_start <= end` would read
`43170326 <= 43125364`, which is false. This is worth flagging directly to
whoever wires the coordinate-range feature to the Gene db: normalize with
min and max before comparing, the same way `ncbi_coordinate_overlap.py`
already normalizes assembly and chromosome before comparing.

### Do the results include genes that do not overlap the window

No, not in this sample. Comparing each record's chrstart/chrstop
(order-normalized to min and max) against the window (43044295 to
43125364) by the same predicate `ncbi_coordinate_overlap.py` uses
(`placement_min <= window_end AND placement_max >= window_start`), all 8
records genuinely overlap. Six of the eight (everything except 672 and
111589215) sit entirely inside the window. 111589215 (the BRCA1 promoter
region, 43124494 to 43127555) straddles the window's end. 672 (BRCA1
itself) straddles the window on both sides, for a reason worth flagging on
its own below.

### A second discrepancy: the window does not reach BRCA1's own reported end

Reading 672's own record order-normalized (43044294 to 43170326) against
the window this task specified (43044295 to 43125364): the window's start
matches the gene's own start to within 1 base pair, consistent with an
ordinary 0-based versus 1-based fencepost difference between sources. The
window's end (43125364) is about 45,000 base pairs short of what NCBI's own
live Gene record reports as the gene's end (43170326). The window still
overlaps the gene under any overlap predicate, since overlap needs only a
partial intersection, so this does not change the answer to the question
directly above. It does mean the window covers only about 64 percent
(81,069 of 126,032 base pairs) of what NCBI's Gene record for uid 672
currently reports as BRCA1's full genomic span. The nearby promoter-region
record (111589215, 43124494 to 43127555) sits right at the window's stated
end rather than near 43170326, which is circumstantial evidence that
43125364 is closer to where the transcript-proximal features actually
cluster. This probe did not investigate why the two figures differ (an
annotation-release change, a different boundary convention, or something
else); it only measured that they do differ today, live, and that is worth
the planner's attention before treating either figure as fixed ground
truth for "the BRCA1 window".

## Fact 2: the coordinate-overlap action live

Both calls went through `coordinate_overlap()` directly, no client
override, default `max_candidates` (20).

| Db | Elapsed | Status | Record count | Total available | Truncated | Candidates checked |
|----|---------|--------|---------------|-------------------|-----------|----------------------|
| clinvar | 0.393s | ok | 20 | 15506 | True | 20 |
| dbvar | 1.360s | ok | 20 | 2884 | True | 20 |

`record_count` equals `candidates_checked` for both calls: every one of the
20 candidates the five-step procedure actually placement-checked survived
the overlap predicate in this window. `total_available` is the coarse
ESearch prefilter count before placement-checking, so it is not directly
comparable to `record_count`; it is the number the tool reports as
"matches that exist but were never checked" once truncated is true.

### ClinVar, first three records

| Id | Chr_start | Chr_end | Classification | Gene | Title |
|----|-----------|---------|------------------|------|-------|
| VCV004886868 | 43057598 | 43068066 | Likely pathogenic | BRCA1 | GRCh38/hg38 17q21.31(chr17:43057598-43068066)x1 |
| VCV004884209 | 43104913 | 43104928 | Pathogenic | BRCA1 | NM_007294.4(BRCA1):c.241_256del (p.Gln81fs) |
| VCV004883931 | 43063868 | 43063868 | Uncertain significance | BRCA1 | NM_007294.4(BRCA1):c.5152+6del |

Source URLs (all under `www.ncbi.nlm.nih.gov/clinvar/variation/`, the
record host, not the eutils fetch host):
`.../4886868/`, `.../4884209/`, `.../4883931/`. No field value on any of
these three records reached the script's 80-character cut.

### dbVar, first three records

| Id | Chr_start | Chr_end | Variant type | Gene(s) |
|----|-----------|---------|----------------|---------|
| nsv7909385 | 43094142 | 43094142 | insertion | BRCA1 |
| nsv7909384 | 43093358 | 43093358 | insertion | BRCA1 |
| nsv7909321 | 43124366 | 43127401 | delins | BRCA1, NBR2 |

Source URLs (all under `www.ncbi.nlm.nih.gov/dbvar/variants/`):
`.../nsv7909385/`, `.../nsv7909384/`, `.../nsv7909321/`. No field value on
any of these three records reached the script's 80-character cut.

## Fact 3: the shape of the numbers

| Source | Query | API-reported matches | Checked in this call | Genuine overlaps among them | Wall time |
|--------|-------|------------------------|-------------------------|--------------------------------|-----------|
| Gene ESearch (db=gene, term a) | chr17:43044295-43125364, GRCh38 | count 8 | 8 (retmax 20, only 8 exist) | 8 of 8 (hand-verified, order-normalized) | 0.232s esearch, 0.184s esummary |
| ClinVar coordinate_overlap | chr17:43044295-43125364, GRCh38 | total_available 15506 | 20 (default max_candidates) | 20 of 20 (record_count, tool-verified) | 0.393s |
| dbVar coordinate_overlap | chr17:43044295-43125364, GRCh38 | total_available 2884 | 20 (default max_candidates) | 20 of 20 (record_count, tool-verified) | 1.360s |

What a person asking "what is under this window" would get, in plain
words, if the answer listed the top records: from Gene, BRCA1 itself plus
the seven small regulatory and pseudogene features already tabulated above,
all nested inside or right at the edge of it, and no unrelated gene turned
up in this window. From ClinVar, the
top three of the 20 checked (15,506 catalogued in this span overall) are
all BRCA1 variants, a large deletion classed likely pathogenic, a
frameshift deletion classed pathogenic, and a splice-region deletion of
uncertain significance, so yes, the ClinVar rows are dominated by BRCA1
variants here, which fits a window that is essentially the gene's own
coordinates. From dbVar, the top three of the 20 checked (2,884 catalogued
overall) are two single-base-pair insertions and one roughly 3,000-base-pair
deletion-insertion reaching into the neighboring NBR2 gene, none of the
three is a huge structural variant spanning the whole region, though three
records out of 2,884 is too small a sample to say what the other 2,881
look like. Given the total-available counts run into the thousands while
only 20 were ever placement-checked and only 3 were printed here, showing
somewhere around 3 to 10 rows per source looks reasonable, with the
total-available number stated in the answer text itself (for example
"15,506 ClinVar records catalogued in this region") so a reader is not
left thinking a handful of rows is the whole picture.

## Requests spent and constraints followed

`probe_gene_window.py` ran twice: once before per-call timing was added
(4 requests, 3 esearch plus 1 esummary), and once after (4 more requests),
because Fact 3 asked for the wall time of each call and the first run had
not measured it. Both runs returned the identical count and idlist, so the
second run is the one quoted above and nothing from the first run is lost.
`probe_overlap_window.py` ran once (4 requests, 2 per db call). Total live
NCBI requests made across both scripts: 12, at the stated cap and not over
it. Both scripts sleep at least 1 second between their own top-level NCBI
calls (`time.sleep(1.0)` in `probe_gene_window.py`, `asyncio.sleep(1.0)`
between the two `coordinate_overlap()` calls in `probe_overlap_window.py`,
the async form of the same wait, needed because ruff's ASYNC251 rule
rejects a blocking `time.sleep` inside an `async def`). The two requests
inside a single `coordinate_overlap()` call (its own ESearch then its own
batched ESummary) are not separately throttled by this probe, since that
pacing lives inside `ncbi_coordinate_overlap.py` itself, under `src/`,
which this task does not edit.

No credential or email address is printed or written anywhere in this
folder. Both scripts read `.env` the same way the existing
`probe_gds_search.py` and `probe_record_forms.py` do, setting environment
variables without ever printing them. Both scripts use only relative paths
(`pathlib.Path(".")`), never an absolute local path.

## How to re-run these probes

From the repository root, with `.env` populated:

```
python3 testing/Developer/reports/2026-09-22_coordinate_range/probe_gene_window.py
python3 testing/Developer/reports/2026-09-22_coordinate_range/probe_overlap_window.py
```

`ruff check testing/Developer/reports/2026-09-22_coordinate_range` and
`isort --check-only testing/Developer/reports/2026-09-22_coordinate_range`
both pass clean as of this measurement.
