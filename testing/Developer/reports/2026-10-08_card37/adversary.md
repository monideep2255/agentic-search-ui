# Card 37 adversary, round 1

- Checkout: card37-adv, HEAD bcdfee5ea3ca97c418fd6c4f1e34ed44b94b7e6d, merge base with origin/develop c916cfa30f59802dfd85c81ef7ba39bdcfc2b263
- Method: own probes (small scripts and single test files), no live model calls

## Findings

### A-37-01: rs334's citation still takes its confidence from a dropped near-miss variant
- Severity: major (unsure whether it is in this card's scope; it is the same "near miss shown as rs334" defect at the citation layer)
- What: the filter removes rs334348 from the shaped rows, but the raw `Litvar2LookupOutput` handed to the citation builder is unfiltered. `litvar2_build_citation` reads `variant_matches[0]`, so when the autocomplete lists a near miss first, the rs334 citation's `assertion_confidence` is computed from rs334348's clinical significance and matched_on text.
- Reproduction: script p37a.py (scratchpad) at HEAD bcdfee5e. Output `variant_matches=[rs334348 cs=["likely-benign"], rs334 cs=["pathogenic"]]`, input query "rs334". Printed: `rows: ['rs334'] ok`, then `rs334 https://www.ncbi.nlm.nih.gov/snp/rs334 hedged`, then `base direct: rs334348 hedged`. Control with only rs334 in the output: `rs334 ... asserted`.
- What a person sees: a citation chip for rs334 (pathogenic) labelled hedged, because a different variant, rs334348, carries "likely". The reverse order makes a hedged claim read as asserted. The trust signal on the cited record belongs to another variant.
- NOT FIXED
### A-37-02: "RS334" typed in capitals plans no LitVar2 lookup at all; the case-insensitive test covers a path the planner never takes
- Severity: minor
- What: `_rsids_in_text` uses the case-sensitive `\brs\d+\b`, so a question with "RS334" or "Rs334" plans neither dbSNP nor LitVar2. The new `test_match_is_case_insensitive` passes `query="RS334"` straight into the shaper, a value the only planner (`_layer_tool_calls`, `rsid[:100]` from `_rsids_in_text`, already lowercased) never produces.
- Reproduction: p37b.py at HEAD bcdfee5e printed `'What is RS334?' []` and `'What is Rs334?' []`, against `'What is rs334?' ['rs334']`.
- What a person sees: "What is RS334?" gets no rs334 literature records and no variant record, with no word that the id was not recognised. Not a regression from this card; the card's test suggests capitals are handled when they are not.
- NOT FIXED

### A-37-03: the exact match compares strings, so a leading-zero or merged rs id the user typed drops its own record
- Severity: unsure
- What: the comparison is `match.rsid.casefold() != asked_rsid` on the strings, not on the parsed number, although the code comment says "An exact comparison of the parsed rs number". "rs0334" is extracted as `rs0334` (p37b.py: `'rs0334 sickle' ['rs0334']`); if LitVar2 answers with `rsid="rs334"` the row is dropped. The same holds for an rs id dbSNP merged into another, if LitVar2 reports the current id.
- Reproduction: comparison read at graph.py lines 4898 to 4907; extraction probed as above. LitVar2's own behaviour for "rs0334" and merged ids NOT probed (no live calls), hence unsure.
- What a person sees: possibly no LitVar2 record for the variant they asked about, where it exists.
- NOT FIXED

### A-37-04: the filter runs after the tool's 10-match cap, so an asked rs id outside the autocomplete's first 10 now reads as LitVar2 holding nothing
- Severity: unsure
- What: `_parse_variant_matches` keeps only the first 10 autocomplete rows; the exact filter runs afterwards in the shaper. For an rs id whose prefix matches many better-cited variants, the exact record can sit beyond row 10, and the shaped result becomes `status: empty`, `0 record(s)`.
- Reproduction: structural, from litvar2_lookup.py `_parse_variant_matches` (`raw_list[:_MAX_VARIANT_MATCHES]`) and the shaper order. Whether LitVar2's autocomplete ever ranks the exact id below 10 prefix matches was NOT probed live.
- What a person sees: the LitVar2 line reports no records for a variant LitVar2 has, which is an absence stated without evidence. Before this card they saw wrong variants instead; now they may see a false "none".
- NOT FIXED
## Verdict

- PASS against "a question about rs334 never lists rs334348, rs334353 or rs334773 as if they were rs334" for the listed rows, with A-37-01 (major) open: the rs334 citation's confidence label can still come from a dropped near miss, because the citation builder reads the unfiltered raw output. A-37-01 is in code next to the fix, not inside it.
- Verified by my own probes: A-37-01 (citation confidence, with a control run), rs id extraction for capitals, spaces, leading zero, possessive, parentheses, slash and three ids. Read only: A-37-03 and A-37-04 depend on LitVar2's live behaviour, not probed.
