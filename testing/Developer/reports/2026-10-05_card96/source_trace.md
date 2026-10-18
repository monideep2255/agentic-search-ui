# Source trace: "Muir-TorrÃ© syndrome" (MedGen C1321489)

Date: 2026-10-05. Read-only. Scripts beside this file: `source_trace.py` (graph) and `source_trace_ncbi.py` (NCBI).

## Verdict

The bytes are already garbled at NCBI. The app decodes them correctly. It is NCBI's problem, not ours and not the data repository's.

## Which layer made finding [3]

- The citation event (seq 84) has `source: ncbi_efetch`, `layer: layer_2_api`, `source_id: MedGen:C1321489`, `field: name`. That is a live NCBI MedGen call, not the graph. Its `citation_id` carries the `cq-` call prefix only because the graph call listed the MedGen id.
- The graph node itself holds `name: "MONDO"` (so the first check was right about the property, wrong about the layer). That is a separate, smaller defect: the graph's Disease name for this id is an ontology name.

## Reproduction

- Graph: `source_trace.py` posts the app's own query through `graph_http_transport.execute_cypher_over_http`. Raw row: `"name": "MONDO"`, ASCII only.
- NCBI: `source_trace_ncbi.py` calls `ncbi_transport.execute_get` for `esummary.fcgi?db=medgen&id=231157&retmode=json` (231157 is the UID that ESearch returns for C1321489). Response header: `application/json; charset=UTF-8`.
- Raw bytes of the name field, hex: `4d7569722d546f7272 c383 c2a9 20 73796e64726f6d65` which is "Muir-Torr" then `c3 83 c2 a9` then " syndrome".
- Correct UTF-8 for "é" is `c3 a9`. NCBI sends `c3 83 c2 a9`, which is "Ã©" already encoded as UTF-8 (double encoding at NCBI).
- `response.text` and `bytes.decode("utf-8")` both give "Muir-TorrÃ© syndrome". The XML esummary (`retmode=xml`) and the JSON esummary show the same four bytes, so it is the MedGen record, not one serialiser.

## Where the bytes go wrong

No line in this repository. httpx reads the charset from the header (UTF-8), `response.text` at `tools/ncbi_eutils_actions.py` line 680 and `json.loads(text)` at `tools/ncbi_transport.py` line 885 decode faithfully, and the summary extractor (`_cap_value`, `summary()` near line 1150) passes the string through unchanged.

## Fix proposal

Add a repair step where esummary string values enter the record, in `_cap_value` in `tools/ncbi_eutils_actions.py`: for each string containing a character in U+00C2 to U+00C3, try `value.encode("latin-1").decode("utf-8")`, and keep the result only when it succeeds and is shorter. Correct text such as "Torré" fails the latin-1 encode or stays unchanged, so it is safe; log a counter so NCBI can be told. Also report the record to NCBI MedGen support. Anything else that passes through `_cap_value` gets the same repair: every esummary database (gene, clinvar, medgen, omim, gtr, pubmed titles), so the repair must apply only to strings that match the mojibake pattern. ESearch, EFetch XML and PubTator or ClinicalTrials text take other paths and are untouched; a check of those is worth one run.
