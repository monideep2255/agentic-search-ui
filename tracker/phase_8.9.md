# Build phase 8.9: the writer is given the field the question asked for

Branch: `phase/8.9-asked-for-field`. Cut it from `develop` only after phase 8.6 has merged and its golden run has held its floor. Status: planned, not opened.

The phase comes from two product-owner decisions of 2026-09-25 (`DECISIONS.md`):

- The order of work: "then phase 8.9, the writer is given the field the question asked for (a paper's title, an ortholog's species, a variant's gene, and rs334 matched exactly rather than by its first digits)".
- Row 733: "The trust line says what was checked: which sources back the answer and whether their values could be compared, for example 'Based on 4 sources, all from MedGen' or 'Based on 6 sources from MedGen and OMIM; their values could not be compared'. The verdict behind the line does not change." The line is built from the parked commit `90b018e`, and its "which differ" wording is replaced.

The merge and this phase's golden run are delegated to the lead under automatic checks (`DECISIONS.md`, 2026-09-26; `testing/Overnight_build_plan_2026-09-25.md`, "Automatic checks for each merge").

The design sources are:

- The product harness review: "What the writer model is actually given", W11, C2 and C3.
- Cards 8, 37 and 38 of `testing/UI_fix_plan.md`.
- Rows G-016, G-021, G-024 and G-035 of the phase 8.7 design.

Where those sources disagree with the code, the code wins; see [Where the code overrides the sources](#where-the-code-overrides-the-sources).

## Table of contents

- [Goal contract](#goal-contract)
- [Budget](#budget)
- [Tickets](#tickets)
- [Builder split and contracts](#builder-split-and-contracts)
- [Dispatch plan](#dispatch-plan)
- [Review focus](#review-focus)
- [Out of scope, and why](#out-of-scope-and-why)
- [Premises and probes](#premises-and-probes)
- [Where the code overrides the sources](#where-the-code-overrides-the-sources)
- [Decisions this plan takes](#decisions-this-plan-takes)
- [History](#history)
- [Findings](#findings)

## Goal contract

### Done when

1. Every ticket below meets its acceptance. Each builder's report pastes its test command's result line.
2. CI is green on the pull request.
3. One judge round and one adversary round, then one fix-and-verify round, leave nothing blocking.
4. The golden consistency run on develop after the merge answers no fewer than phase 8.6's golden run did, with zero rate-limit signals.
   - The run is 50 questions, three passes each, 150 runs, two workers, using `testing/Developer/reports/2026-09-22_10.3_consistency/run_consistency.py` and `summarize.py`.
   - The floor is the latest run the product owner accepted. Today that is phase 8.2's run, 102 of 150 (commit `566e1ab`). Phase 8.6's run answered 99 of 150 and was not accepted (`testing/Developer/reports/2026-09-26_phase_8.6_golden/summary.md`). If the owner accepts it, or a re-landed 8.6 runs higher, paste that figure here before 8.9's run starts.
   - A drop undoes the merge. Only the product owner may accept one.
5. The three rows this phase exists for now show what they lack today. Each is read from the saved `raw/G-0NN_runN.json` of every pass. The baselines are phase 8.2's run, pasted under [Premises and probes](#premises-and-probes).
   - G-016 (TP53 orthologs):
     - Answered in 3 of 3 passes.
     - The ortholog call's `tool_result` still reads "100 row(s) of 591".
     - In at least 2 of 3 passes, at least one `citation` has field `organism` on a `https://www.ncbi.nlm.nih.gov/gene/` page. Today that count is 0.
   - G-021 (CFTR papers):
     - Answered in 3 of 3 passes.
     - In every pass, no citation on a `https://pubmed.ncbi.nlm.nih.gov/` page has field `curie`. Today there are 54 per pass.
     - The one exception is a record PubMed returns no title for; the builder's report names each one.
   - G-024 (rs334):
     - Answered in 3 of 3 passes.
     - In every pass, every `litvar2` citation's `source_id` is `rs334`.
     - None of rs334348, rs334353, rs334558 or rs334773 appears in the citations or the answer text. Today all four appear in every pass.
     - In at least 2 of 3 passes, a citation has field `gene` on `https://www.ncbi.nlm.nih.gov/snp/rs334`. Today that count is 0.
6. No `trust_line` in the golden run contains "not yet confirmed" or "which differ", and none is longer than 200 characters.
   - Report the counts of `answer`, `ask` and `flag` beside phase 8.6's.
   - Name for the owner any question whose verdict changed in all three passes.

### Verify

- Per ticket: its test command. The judge also runs the "break it, does a test go red" line on every control the ticket adds.
- Whole suite:
  - `venv/bin/python -m pytest tests/system_03_search_agent -q`
  - `venv/bin/ruff check .`
  - `venv/bin/isort --check-only src tests`
  - In `frontend/`: `npm test` and `npm run build`
- Stable prefix: `tests/system_03_search_agent/synthesis/test_prompt_cache_prefix.py` and `tests/system_03_search_agent/harness/test_cache.py` pass unchanged.
- Gate and verdict untouched:
  - `git diff develop...HEAD -- src/system_03_search_agent/synthesis/grounding.py src/system_03_search_agent/synthesis/sentence_check.py` is empty.
  - The `trust.py` diff touches only `answer_trust_line` and one new naming helper.
- Event contract: the diffs of `src/system_03_search_agent/contracts/` and `frontend/src/lib/events.ts` are comment lines only.
- Live runs: local, before and after, researcher depth, one run each of G-016, G-021 and G-024.
  - Builder N runs all three. Builder M runs G-016 through `cypher_query` only.
  - Each run pastes:
    - the citation fields;
    - the first five finding lines of the synth prompt;
    - the number of writing calls;
    - whether the first reply grounded anything. Phase 8.6's History (2026-09-26) says the repair clause is measured again after this phase.
- The golden run and its summary, then the row checks in item 5. The lead runs them read-only over the saved raw files.
- The product reviewer on develop, per `reference/Product_review.md`.

### Output

- The pull request from `phase/8.9-asked-for-field` to `develop`.
- `testing/Developer/reports/2026-09-26_phase_8.9/builder_M.md` and `builder_N.md`.
- `testing/Developer/reports/<date>_phase_8.9_golden/`, holding `runs.jsonl`, `raw/` and `summary.md`.
- `testing/Developer/reports/<date>_product_review_8.9/`.
- This file's Findings and the lead's triage.
- `DECISIONS.md` rows for [Decisions this plan takes](#decisions-this-plan-takes).

### Constraints

- Every rule under `.claude/rules/` applies.
- The cite-or-refuse gate stays exactly as strict:
  - No change to `synthesis/grounding.py` or `synthesis/sentence_check.py`.
  - A new word may be licensed only through a finding's own code-built field name, and that name must truthfully describe its value.
- The trust verdict does not change. These are byte-identical:
  - `decide`, `DECISION_TABLE`, `triangulate`, `_origin_of`, `_origin_database`, `aggregate`, `risk_tier_for`
  - the risk token tables and `_BUCKET_BY_VALUE`
- New prompt content goes only in the dynamic suffix, which is the user message of `build_synth_messages`. `SYNTH_SYSTEM_INSTRUCTION` and the prefix in `harness/cache.py` stay byte-identical.
- The event contract is additive only, and this phase adds nothing to it:
  - no new event;
  - no new field;
  - no widened bound (`DonePayload.trust_line` stays at 200 characters).
- The Article quarantine stays:
  - `_sanitized_citeable_row`, `_split_rows_by_trust` and `_untrusted_rows_free_text` are unchanged.
  - The graph's copy of a title is never carried.
  - Titles come from PubMed through the `ncbi_efetch` reading tool.
- No decision is read from a question's wording:
  - no new keyword rule;
  - the companion rule keys on a record's type and field;
  - the rs id filter is an exact identifier match, which is verification.
- No golden question, answer or identifier goes in a prompt or in product code. Tests may use them.
- Every new network request is charged against the 20-call ceiling at the transport (`call_budget.charge_one_call` in `ncbi_transport.execute_get`). It also waits in the E-utilities pool and carries a declared timeout.
- No database migration. `requirements/PRD.md` and `requirements/Technical_specification.md` stay untouched. The v1 scope boundary holds.
- Nothing committed carries a local path, a server address or a key (`public-repository-privacy.md`).

### Blocked-stop

- Phase 8.6 has not merged, or its golden run did not hold its floor: 8.9 does not open.
- A ticket needs something it may not touch. The builder stops and the lead writes it here. This covers:
  - a file outside the ticket's fence;
  - a change to the gate, the sentence check, the trust verdict, the stable prefix or the event schema;
  - a migration;
  - an edit to a locked document.
- A regression sits inside a fix made in this phase. File it with `Regression of`, then stop the round (Review_rounds Rule 4).
- The golden run drops below the floor.
  - Undo the merge with the bin script and send the per-question table to the owner.
  - A run with rate-limit signals is rerun once, after the pool clears, and is never argued away.
- Any of these also stops the phase:
  - the night's spend would pass $11;
  - a ninth dispatch would be needed;
  - the harness refuses a permission;
  - 8 hours have passed.

## Budget

- Wall clock: 8 hours from opening.
- Dispatches: 8 of 8, as planned in [Dispatch plan](#dispatch-plan).
- Golden floor: phase 8.6's accepted run, at least 102 of 150.
- Answer path: yes, for all six tickets.
- Spend:
  - The golden run costs about $3 and is approved: `DECISIONS.md` (2026-09-26) reads "Finish the job" as a yes to it, with the night stopping at $11.
  - Live runs by builders and reviewers cost about 2 cents each. The harness review measured 1.7 to 2.0 cents per traced question.
  - Read the credits endpoint before the golden run.

## Tickets

Which tickets serve which shape:

| Shape | Tickets |
|---|---|
| Papers | T-8.9-01 |
| Orthologs | T-8.9-02 (the graph returns the organism), T-8.9-03 (the writer is given it), T-8.9-06 (the list shows it) |
| Variants | T-8.9-03 and T-8.9-06 (the gene), T-8.9-04 (card 37, the exact match) |
| Trust line | T-8.9-05 |
| Phase 8.6's open flags | T-8.9-07 (a Jev charge stays inside its ceiling; two fixes get tests) |

### T-8.9-01: A paper found in the graph is named by its title

- Builder: N.
- Answer path: yes.
- Size: M, about 120 lines plus tests.

What the person notices:

Asking which papers in the graph mention CFTR, each listed paper now reads as its title, not a bare "Article record PMID:10075921". The writing model is also given the titles.

Acceptance:

1. Rewrite each graph Article finding before the writing call.
   - In scope: every graph Article finding in the admitted display list, meaning a `curie_fallback` finding whose curie is `PMID:<n>`.
   - It becomes the title PubMed returns for that PMID:
     - `field` "title"
     - `field_value` the cleaned title
     - `name_resolved` true
     - `curie_fallback` and `value_is_suspect` false
     - `layer` "layer_2_api"
     - `tool` "ncbi_efetch"
   - These stay unchanged: `curie`, `source_url`, `ref_index`, `citation_id` and `entity_type` ("Article").
   - The prompt then reads "Article title: ...", and the list shows the title at both depths. That comes from `record_label`'s existing `name_resolved` branch, which is unchanged.
   - Put the resolver in a new `synthesis/article_titles.py`. Mirror `synthesis/disease_names.py` and `synthesis/mesh_terms.py`, keeping `apply_resolved_disease_names` and `readable_disease_name` out of it, since the latter reorders comma-separated words.
2. Read the titles through the EFetch path the product already verifies:
   - `action` fetch, `db` pubmed, `rettype` abstract, `retmode` xml, parsed by `_extract_pubmed_articles`.
   - Use at most two requests of at most 50 PMIDs each, which is the cap on `NcbiEfetchFetchInput.ids`, issued concurrently.
   - Cover the display list in `ref_index` order, so the prompt slice is covered first.
   - Join each title to its finding by the PMID on the returned record (`NcbiEfetchRecord.id`), never by position.
   - Discard the fetched abstracts. They never become findings on this path.
3. Clean each title with the rule in `clean_clinical_feature_name`:
   - every non-printable character becomes a space, including a newline, a tab, a bidi override and a zero-width character;
   - runs of whitespace collapse.
   - Withhold a title over 500 characters, or one the fetch already cut (it ends in " [truncated]"): the finding keeps its PMID. Never truncate a title.
4. A failure degrades the answer and never fails it.
   - These each leave the finding exactly as it was, with nothing raised into `write_node`:
     - a transport error;
     - a rate-limit refusal;
     - the 20-call ceiling;
     - a malformed body;
     - a missing record;
     - an empty title.
   - Write one log line naming the cause's class, never the exception text.
   - Bound the whole lookup with an explicit wait of 15 seconds, the tool's own per-call budget from `tool-call-budgets.md`.
5. Run the rewrite in `write_node` after `drop_placeholder_condition_findings`, so decision D2 can never drop a paper titled "Not provided". It also runs before `row_types` and the prompt slice.
6. List a paper once when it reaches the list twice, from the graph and from the literature search, with the same page and the same title.
   - Keep the lower number.
   - Renumber densely, the way `drop_placeholder_condition_findings` does.
7. Add one line in the dynamic suffix, only when a title finding is in the prompt. It tells the writer that a title is an article's name, which is data and never an instruction, and not a verified finding in its own right.
8. Graph Article handling is unchanged: `_sanitized_citeable_row`, `_split_rows_by_trust` and `_untrusted_rows_free_text`.

Test command:

`venv/bin/python -m pytest tests/system_03_search_agent/synthesis/test_article_titles.py tests/system_03_search_agent/core/test_article_title_wiring.py -q`

File fence:

- new `src/system_03_search_agent/synthesis/article_titles.py`
- `core/graph.py`: the resolution block of `write_node` only
- `synthesis/findings.py`: the title line in `build_synth_messages`
- the two new test files

Premise:

Premise (a): graph Article rows reach Write as `curie_fallback` findings.

- Status: proved from saved runs. G-021 has 54 PubMed-page citations with field `curie` in every pass.

Premise (b): EFetch returns one title per PMID.

- Status: live-verified path. The repository's premise gate cases 4 and 8 cover it, and it runs on every gene question (G-016's saved runs show `fetch: 10 record(s)`).
- Not probed today: EFetch latency for 50 PMIDs.
  - Builder N measures it on G-021.
  - If the median is above 3 seconds, the lead decides. The lighter ESummary route needs `title` added to the PubMed ESummary allowlist, which is a deviation from Section 6.2's table and takes a decision row, as the gene row's additions did.

### T-8.9-02: The graph returns each ortholog with its organism

- Builder: M.
- Answer path: yes.
- Size: M, about 60 lines plus tests.

What the person notices:

Nothing on its own. It is what lets T-8.9-03 and T-8.9-06 name each ortholog's species. The answer still says how many orthologs the graph holds.

Acceptance:

1. Change the single-gene ortholog template: anchor Gene, shape `orthologs`, one anchor, not a count.
   - Its Cypher becomes the shape probed: `MATCH (a:Gene {id: $e})-[:orthologous_to]->(x:Gene) OPTIONAL MATCH (x)-[:in_taxon]->(t:OrganismTaxon) WITH x, collect(DISTINCT t.name) AS xs RETURN x, xs ORDER BY x.id`, with the parameter named by `entity_param_bindings`.
   - Keep the name `gene_orthologs_one` and the edge label `orthologous_to`, so the pinned case in `test_cypher_templates.py` stays green as it is.
   - The count form and the several-gene form are unchanged.
2. Add a new optional `CypherTemplate` attribute, a value fold, so `cypher_query` writes the list column's strings onto the anchor row as `fields["organism"]`.
   - Clean each name to one printable line.
   - Drop blanks, deduplicate, sort, keep at most `MAX_FOLD_ITEMS`, and join with ", ".
   - Write nothing when the list is empty.
   - Ignore a non-string item. Never render it with `str()`.
   - The existing CURIE fold (`_fold_curies`, `_apply_fold` for the variant-to-disease templates) and the model path are unchanged.
3. No taxon vertex becomes a row. The list column holds strings, so `_iter_entities` emits nothing for it. TP53's call returns exactly today's rows: 100.
4. Keep the total. The ortholog call's `total_available` for TP53 stays 591.
   - Today a two-column RETURN that hits its cap reports the total as unknown (`_run_pipeline`, `column_count == 1`).
   - A value-fold template adds no rows, so its count query must still run. `_build_count_cypher` takes the text before RETURN and counts one row per `x`.
5. The template must pass these checks:
   - it passes `validate_cypher`;
   - it is in `all_template_examples()`;
   - its `in_taxon` hop is asserted documented at import;
   - it runs well under the graph's 30-second statement timeout.
   - Builder M pastes the live time through `cypher_query`. The probe measured 5.1 seconds over the configured HTTPS transport, against 5.01 for today's template.
6. The contract is the constant `FOLD_FIELD_ORGANISM = "organism"` in `tools/cypher_templates.py`. A test pins the literal.

Test command:

`venv/bin/python -m pytest tests/system_03_search_agent/tools/test_cypher_templates.py tests/system_03_search_agent/tools/test_cypher_fold_templates.py tests/system_03_search_agent/tools/test_cypher_query_templates.py -q`

File fence:

- `tools/cypher_templates.py`
- `tools/cypher_query.py`
- the three test files above

Premise:

The graph carries a readable organism for these rows, and the hop is cheap.

- Status: proved by probe 1.
  - 591 of 591 TP53 orthologs have an `in_taxon` edge.
  - Taxon names read like "Oryctolagus cuniculus".
  - The candidate template took 5.1 seconds for 100 rows, with 0 of 100 empty taxon lists.
  - The validator accepted it.

### T-8.9-03: An ortholog's organism and a variant's gene reach the writer

- Builder: N.
- Answer path: yes.
- Size: S, about 50 lines plus tests.

What the person notices:

- Asking about TP53's orthologs, the written answer can name the species each ortholog belongs to.
- Asking about rs334, it can say the variant is in HBB, cited to the dbSNP record.

Acceptance:

1. `build_synth_findings` emits one companion finding per row, from a closed table keyed by (row type, row field):

   | Row type | Row field | Companion field |
   |---|---|---|
   | `Gene` | `organism` | `organism` |
   | `Variant record` | `genes` | `gene` |

   - Place it right after its row's own finding, and after its explanatory finding if there is one.
   - Pass it through the same `seen` dedup and the same cap, as item 11.31's explanatory finding does.
   - Emit nothing when:
     - the value is not a non-blank string;
     - the field is the one the row's own finding already uses.
2. Only the listed rows gain a finding. A test shows no companion for:
   - a Layer 2 gene record, a biosample or an assembly record carrying `organism`;
   - a `Literature variant` row carrying `gene`.
3. The companion keeps its row's `source_url`, `curie`, `entity_type`, `layer`, `tool` and `call_id`.
   - Its citation comes from the row's own tool builder.
   - For dbSNP, `_layer3_base_citation` maps the finding field `gene` to the output field `genes`, the same shape as the isolate builder's `name` to `strain`.
4. The findings are the same at every depth (Section 14.1's firewall).
5. Add one line in the dynamic suffix, only when companion findings are in the prompt. It gives each companion one sentence shape in which the unchanged gate licenses every content word:
   - the record's identifier, then "is in the organism" and the value;
   - the question's subject or the record's identifier, then "is in the gene" and the value.
   - It never names a golden question.
6. A replay through the unchanged `run_grounding_pass` shows sentences of both shapes survive at both depths.
   - `drop_record_restatements` keeps them, because the list shows the row's own finding, not the companion.
7. Live: builder N runs G-016 and G-024 at researcher depth, before and after. The report pastes:
   - the number of citations with field `organism` and field `gene`;
   - the prose sentences kept.

Test command:

`venv/bin/python -m pytest tests/system_03_search_agent/synthesis/test_companion_findings.py tests/system_03_search_agent/synthesis/test_explanatory_findings.py -q`

File fence:

- `synthesis/findings.py`
- `core/graph.py`: `_layer3_base_citation` only
- new `tests/system_03_search_agent/synthesis/test_companion_findings.py`

Premise:

Premise (a): the dbSNP row already carries the gene.

- Status: proved by probe 3. The pseudo-row holds `'genes': 'HBB'`.

Premise (b): the ortholog rows carry `organism`.

- Status: proved for the data by probe 1. The rows themselves exist once T-8.9-02 lands.

Premise (c): the strict gate licenses a claim's words only from:

- its finding's value;
- the field name in both spellings;
- the CURIE;
- the type;
- the open question.

It strips no word endings.

- Status: code-read, in `run_grounding_pass`'s `supporting_text`.
- This is why the gene companion is named `gene`, not `genes`: "rs334 is in the gene HBB" must survive.

### T-8.9-04: rs334 is matched exactly, not by its first digits (card 37)

- Builder: N.
- Answer path: yes.
- Size: S, about 15 lines plus tests.

What the person notices:

Asking about rs334 no longer lists rs334348, rs334353, rs334558 (c.-50T>C) and rs334773 as if they were rs334. The one literature record kept is rs334's own: c.20A>T in HBB.

Acceptance:

1. Filter LitVar2 matches before any row exists, in the `litvar2_lookup` branch of `_layer_tool_output_to_structured_fields`.
   - This applies when the call's query is an rs id, which is the only kind `_rsids_in_text` plans.
   - Keep only matches whose `rsid` equals that rs id, compared case-insensitively.
   - Drop a match with another rsid or with no rsid.
   - The tool itself still keeps its near misses by design (F-3.3-A-01). This is the downstream check: an exact identifier match.
2. When no match is exact, the LitVar2 result is `empty`, not `error`. That produces no failed-search note and no refusal.
3. An offline replay of the probe's five matches keeps rs334 alone.
   - Two rs ids in one question each keep their own match.
   - A query of `rs33` does not keep `rs334`.
4. Live: builder N runs G-024 at researcher depth. The report pastes the LitVar2 `tool_result` summary and every citation's `source_id`.

Test command:

`venv/bin/python -m pytest tests/system_03_search_agent/core/test_litvar2_exact_rsid.py -q`

File fence:

- `core/graph.py`: the `litvar2_lookup` branch of `_layer_tool_output_to_structured_fields` only
- new `tests/system_03_search_agent/core/test_litvar2_exact_rsid.py`

Premise:

LitVar2 returns rs334's own match alongside prefix near misses whose rsid differs.

- Status: proved by probe 3.
  - 5 matches came back: rs334 (c.20A>T, HBB), rs334558, rs334348, rs334353 and rs334773.
  - All five read "Matched on rsid", so `matched_on` cannot tell them apart.

### T-8.9-05: The trust line says what was checked (card 8)

- Builder: M.
- Answer path: yes. It changes the line under every answer; no verdict changes.
- Size: M, about 70 lines plus tests and fixtures.

What the person notices:

Under an answer the line reads "Based on 4 sources, all from MedGen" or "Based on 6 sources from MedGen and OMIM; their values could not be compared". It never reads "not yet confirmed".

Acceptance:

1. Wording in `answer_trust_line`:
   - Refuse, or nothing grounded: None, unchanged.
   - `flag`: "Sources disagree on at least one claim", unchanged.
   - "Confirmed by N independent sources": exactly as today, with `database_count` from `_origin_database` unchanged.
   - Every other line names the databases behind the grounded claims.
     - Order them by how many cited pages each backs, ties alphabetical.
     - One database: "Based on 4 sources, all from MedGen". With one source: "Based on 1 source, from MedGen".
     - Two or three: "Based on 6 sources from MedGen and OMIM", or "... from MedGen, OMIM and PubMed".
     - Four or more: the three most cited, then "and N other databases".
   - Append "; their values could not be compared" only when all three hold:
     - the verdict is `ask`;
     - two or more databases are named;
     - at least one high-risk claim's triangulation came back `insufficient`.
   - An `ask` that comes only from an answer-level floor gets no comparison clause. The floors are the fallback, omitted findings, a failed search and an unaddressed entity, and each has its own note.
   - "not yet confirmed" and "which differ" appear nowhere under `src/`.
2. Names come from one closed display table. Look up the CURIE prefix first, then the E-utilities database of an `ncbi_efetch` finding (its `entity_type`), then the tool.

   | Key | Name shown |
   |---|---|
   | `NCBIGene` | NCBI Gene |
   | `ClinVar` | ClinVar |
   | `MedGen` | MedGen |
   | `PMID` | PubMed |
   | `NCBITaxon` | NCBI Taxonomy |
   | `GO` | Gene Ontology |
   | `MeSH` | MeSH |
   | `HP` | HPO |
   | `MONDO` | MONDO |
   | `pubmed` | PubMed |
   | `gene` | NCBI Gene |
   | `clinvar` | ClinVar |
   | `omim` | OMIM |
   | `medgen` | MedGen |
   | `gds` | GEO |
   | `taxonomy` | NCBI Taxonomy |
   | `bioproject` | BioProject |
   | `biosample` | BioSample |
   | `sra` | SRA |
   | `assembly` | NCBI Assembly |
   | `dbvar` | dbVar |
   | `gtr` | GTR |
   | `mesh` | MeSH |
   | `ncbi_dbsnp` | dbSNP |
   | `pubtator_annotate` | PubTator3 |
   | `litvar2_lookup` | LitVar2 |
   | `clinicaltrials_search` | ClinicalTrials.gov |
   | `pathogen_detection` | Pathogen Detection |
   | `cypher_query` | the knowledge graph |

   - A key the table does not hold is never printed; it is counted among the other databases.
   - A test sweeps every prefix in `CURIE_PREFIXES`, every `SummaryDb` and `FetchDb` value and every catalogue tool (Rule 2's exhaustive sweep).
3. The line is at most 200 characters for every combination. That is the `max_length` of `DonePayload.trust_line`.
   - A property test over the whole table proves it.
   - The schema is not widened.
4. Take only these hunks of `90b018e`:
   - `trust.py`;
   - the `contracts/events.py` comment;
   - `test_answer_layout.py`.
   Replace the "which differ" branch. The parked `builder_F.md` report stays on phase 8.4's branch.
5. `decide`, `DECISION_TABLE`, `triangulate`, `_origin_of`, `_origin_database`, `aggregate`, `risk_tier_for`, the token tables and `_BUCKET_BY_VALUE` are byte-identical.
6. Frontend: these files carry the new wording and none of the old.
   - `answerPagination.test.tsx`
   - `answerLayout.test.tsx`
   - `set9AnswerStructure.test.tsx`, at lines 116, 224 and 229
   - `e2e/bold-and-stagger.spec.ts`
   - `e2e/answer-layout.spec.ts`, at lines 183 and 237
   - the example in the comment of `frontend/src/lib/events.ts`
   - Runtime is unchanged: `useRunView.ts` still marks only a line starting "Confirmed" as good.

Test command:

`venv/bin/python -m pytest tests/system_03_search_agent/synthesis/test_trust_line.py tests/system_03_search_agent/synthesis/test_answer_layout.py -q`, then `npm test` and `npm run build` in `frontend/`.

File fence:

- `synthesis/trust.py`
- `contracts/events.py`: the comment on `DonePayload.trust_line` only
- `frontend/src/lib/events.ts`: comment only
- the five frontend test files above
- `tests/system_03_search_agent/synthesis/test_answer_layout.py`
- new `tests/system_03_search_agent/synthesis/test_trust_line.py`

Premise:

`answer_trust_line` holds the grounded claims and their per-claim triangulation, which is enough to name databases and to tell a failed comparison from a floor.

- Status: code-read. No probe was needed.
- `_origin_database` names every E-utilities record "ncbi_efetch", so it cannot supply display names.

### T-8.9-06: The record list shows each ortholog's organism and the variant's gene

- Builder: M.
- Answer path: yes, for what the list shows.
- Size: S, about 30 lines plus tests.

What the person notices:

- At Researcher depth, the ortholog table gains an Organism column and the variant table a Gene column.
- At Plain language, each ortholog reads "tumor protein p53 (Oryctolagus cuniculus)" instead of the same name forty times.

Acceptance:

1. The Researcher table's extra column reads from a closed table keyed by (row type, row field):

   | Row type | Row field | Column heading |
   |---|---|---|
   | `Gene` | `organism` | Organism |
   | `Variant record` | `genes` | Gene |

   - Show the value verbatim, as one printable line, capped like the status column.
   - The column rides the existing return shape of `record_status_or_year`. A status or year keeps precedence, though none of these rows carries one today.
2. At Plain language, a list row whose record carries `organism` reads "<title> (<organism>)". Every other plain label is unchanged.
3. No change to the `listing()` closure in `core/graph.py`, which is the only caller of both helpers.

Test command:

`venv/bin/python -m pytest tests/system_03_search_agent/synthesis/test_answer_layout.py -q`

File fence:

- `synthesis/answer_layout.py`
- `tests/system_03_search_agent/synthesis/test_answer_layout.py`, shared with T-8.9-05 under the same builder

Premise:

The list reads each row's own fields for its label, its identifier and one extra column.

- Status: code-read, in `record_label`, `plain_record_label`, `record_status_or_year` and `listing()`.
- Without this ticket, the species reach the person only when the writer's sentences survive. In 43 of 102 answered golden runs, none did.

### T-8.9-07: A Jev charge stays inside its ceiling, and two 8.6 fixes get the tests they lack

- Builder: M.
- Answer path: no. Cost accounting, two docstrings and tests only.
- Size: S, about 20 lines plus tests.
- Source: phase 8.6's fresh verifier, F-8.6-V01, V03, V05, V06 and V07 in `tracker/phase_8.6.md`. Phase 8.6 merged with them named as open flags, and this ticket is their trigger.
- DROPPED on 2026-09-26: phase 8.6's re-land carries the whole of this ticket as its R-04 (`tracker/phase_8.6.md`, "Re-land"). Builder M does not take it.

What the person notices:

- Nothing on an ordinary day.
- On a day Jev's alpha endpoint misreports its cost, say 12.5 for 0.0000125, one question no longer pauses every person's questions on develop for the rest of the day. Today the whole reported figure is charged, and the system's daily cap sums it (V01).

Acceptance:

1. Every Jev charge lands between $0 and `MAX_JEV_COST_USD`, inclusive.
   - `jev_client.py` sets `JevCallError.billed_cost_usd` in three places: the one-decision call, the batch call, and the check for a cost above the ceiling. Fix it there, at its source.
   - A finite reported cost above the ceiling is charged at the ceiling, never in full (V01).
   - A reported cost that is not a finite, non-negative number is charged at the ceiling (V03). That covers NaN, Infinity, a negative number, a missing field, a string, `true`, and an integer too large for a float. This follows `harness.py`'s rule that a cost cap which guesses must guess toward stopping (F-2.1-B02).
   - A well-formed cost at or under the ceiling is charged exactly as today.
   - The three charge sites are not edited, since they read `billed_cost_usd`: `decide()`, the guardrail's `_jev_injection_pick` and `synthesis/sentence_check.py`. `git diff develop -- src/system_03_search_agent/synthesis/sentence_check.py` stays empty.
2. Two docstrings say what the code has done for `guardrail.injection` since 8.6's bca9261 (V05). Docstrings only; no field, type or bound moves.
   - `contracts/events.py`, `DecisionRecord`: the injection record is built by `core/graph.py`'s `_injection_record`, not by `decide()`. In Jev mode the guard classifier is asked beside Jev on every question, so `agreed` is set on that row, and `decided_by` "guard" there does not mean Jev failed.
   - `harness/decide.py`'s module docstring no longer lists `guardrail.injection` among the points `decide()` answers.
3. A test goes red if the late-read grace grows (V07).
   - It must not patch `_LATE_DECISION_GRACE_S`, and must not compare the constant with itself.
   - With a decision that never finishes, measure Plan's wait and assert it is under 2 seconds. The measured failure was 14.00 s.
4. A test goes red if the completeness repair's call site stops passing the Researcher-only listing mode (V06).
   - Drive `write_node` at Plain language on inputs where the two modes disagree. The verifier's example: a gene record with a summary and a disease, where the plain-language tail skips the repair and the Researcher listing runs it.
   - Assert that no second writing call is made.
   - Forcing `lists_every_finding=True` at every depth must turn it red.
5. Any existing assertion that pins the full charge above the ceiling changes on purpose. Name each changed assertion in the report. The lead's `test_with_jev_an_unusable_reply_is_charged_at_its_billed_cost` bills 0.0125, which is above the $0.01 ceiling, so expect it among them.

Test command:

`venv/bin/python -m pytest tests/system_03_search_agent/harness/test_jev_cost_bounds.py tests/system_03_search_agent/core/test_late_decision_grace.py tests/system_03_search_agent/core/test_repair_listing_mode.py tests/system_03_search_agent/harness/test_jev_client.py tests/system_03_search_agent/harness/test_decide.py tests/system_03_search_agent/guardrail/test_guardrail_node_integration.py -q`

File fence:

- `harness/jev_client.py`
- `harness/decide.py`, the module docstring only
- `contracts/events.py`, the `DecisionRecord` docstring, beside T-8.9-05's comment in the same file
- new `tests/system_03_search_agent/harness/test_jev_cost_bounds.py`
- new `tests/system_03_search_agent/core/test_late_decision_grace.py`
- new `tests/system_03_search_agent/core/test_repair_listing_mode.py`
- `tests/system_03_search_agent/harness/test_jev_client.py`, `test_decide.py` and `tests/system_03_search_agent/guardrail/test_guardrail_node_integration.py`, only where an assertion pins the full charge above the ceiling

Premise:

`jev_client.py` sets `billed_cost_usd` from the reported cost with no upper bound.

- Status: code-read at lines 259, 441 and 614 on 8.6's head, and measured by the verifier (`decide(): reported cost 12.5 -> query charged 12.5` at d75fa09; 0.0 on develop before 8.6).
- Left open by name, not this ticket: a Jev timeout after the request was sent is charged $0, as it has been since phase 8.2.

## Builder split and contracts

| Builder | Tickets | File fence | Isolation |
|---|---|---|---|
| M: the graph rows, the trust line and 8.6's open flags | T-8.9-02, T-8.9-05, T-8.9-06, T-8.9-07 | `harness/jev_client.py`, `harness/decide.py` (module docstring), `tools/cypher_templates.py`, `tools/cypher_query.py`, `synthesis/answer_layout.py`, `synthesis/trust.py`, `contracts/events.py` (comment), `frontend/src/lib/events.ts` (comment), the five frontend test files, `tests/.../tools/test_cypher_templates.py`, `test_cypher_fold_templates.py`, `test_cypher_query_templates.py`, `tests/.../synthesis/test_answer_layout.py`, new `test_trust_line.py`, T-8.9-07's three new test files and its named assertions, `builder_M.md` | worktree |
| N: the writer's input | T-8.9-01, T-8.9-03, T-8.9-04 | `core/graph.py` (`write_node`'s resolution block, `_layer_tool_output_to_structured_fields`'s `litvar2_lookup` branch, `_layer3_base_citation`), `synthesis/findings.py`, new `synthesis/article_titles.py`, new test files `test_article_titles.py`, `test_companion_findings.py`, `core/test_article_title_wiring.py`, `core/test_litvar2_exact_rsid.py`, `builder_N.md` | worktree |

T-8.9-01, 03 and 04 all touch `core/graph.py`, in different functions. One builder holds them and works them one after another (Review_rounds Rule 1). No file is in both fences.

### Contracts

Both briefs carry these word for word.

1. M to N, the ortholog rows.
   - Rows from the `gene_orthologs_one` template carry `node_or_edge_type` "Gene" and `fields["organism"]`.
   - The value is a string: the in_taxon names, cleaned, deduplicated, sorted and joined with ", ". The field is absent when there are none.
   - M defines `FOLD_FIELD_ORGANISM = "organism"`.
   - N keys its companion table on the literal `organism` and does not import M's constant, because the two build in separate worktrees. Each pins the literal in a test.
   - After both merge, the judge checks that the two agree.
2. N to M, how new findings are named on the trust line.
   - A resolved paper finding keeps `curie` "PMID:<n>" and `entity_type` "Article", with `tool` "ncbi_efetch" and `layer` "layer_2_api". The trust line names it "PubMed".
   - A companion keeps its row's `curie`, `tool` and `entity_type`:
     - the organism companion is named "NCBI Gene";
     - the gene companion is named "dbSNP".
3. Frozen for both: the dbSNP pseudo-row in `_layer_tool_output_to_structured_fields` keeps `node_or_edge_type` "Variant record" and its field `genes`.
   - N owns that code and must not rename either.
   - M's T-8.9-06 and N's T-8.9-03 both read them.
4. Neither builder edits the other's files. `test_answer_layout.py` belongs to M; N's tests go in new files.

### What each builder is handed

Builder M reads:

- `tools/cypher_templates.py`: the module docstring, `_HOPS`, `_hop_template`, `select_template`, `all_template_examples`.
- `tools/cypher_query.py`: `_fold_curies`, `_apply_fold`, `_run_pipeline`'s count logic, `_build_count_cypher`.
- `tools/cypher_provenance.py`: `_iter_entities`.
- `synthesis/trust.py`.
- `synthesis/answer_layout.py`.
- `git show 90b018e`.
- `contracts/events.py`: `DonePayload`.
- `frontend/src/hooks/useRunView.ts`: the trust-line tone.

Builder M's LEARNINGS row: 2026-09-23, on `tools/cypher_templates.py`. Tests passed for months by agreeing with a wrong constant, so verify against the live graph.

Builder N reads:

- The resolution block of `write_node`.
- `_layer_tool_output_to_structured_fields`, `_layer3_base_citation`, `_citations_from_grounded_claims` and `_rsids_in_text`.
- `synthesis/disease_names.py` and `synthesis/mesh_terms.py`, the pattern to mirror.
- `synthesis/findings.py`: `build_synth_findings`, `explanatory_value_for_row`, `one_finding_per_record`, `render_finding_body`, `build_synth_messages`, `build_clinical_features_directive`, `apply_resolved_disease_names`.
- Read-only:
  - `synthesis/grounding.py` (`run_grounding_pass`);
  - `synthesis/answer_layout.py` (`drop_record_restatements`, `record_label`);
  - `tools/ncbi_eutils_actions.py` (`_extract_pubmed_articles`, `clean_clinical_feature_name`);
  - `tools/litvar2_lookup.py`'s docstring (F-3.3-A-01).

Builder N's LEARNINGS rows:

- 2026-08-08: LitVar2 discarded its own relevance signal.
- 2026-09-24: a change to an answer instruction alone made GERD fall back to a list.

Both builders read this file's Findings before starting and again before reporting. The lead commits this ledger on the phase branch before dispatch (LEARNINGS 2026-08-08: worktree builders were once dispatched before their prerequisites were committed).

## Dispatch plan

The lead's plan, set at open. The planner that drafted this file counts as dispatch 1, so the draft's second fix builder is dropped and one fix builder takes findings from both fences, one fence after the other.

| # | Role | Agent | Model | Isolation | Starts |
|---|---|---|---|---|---|
| 1 | Planner (done) | Plan | Opus 5.5 | read-only | before open |
| 2 | Builder M | general-purpose | Sonnet 5 | worktree | at open |
| 3 | Builder N | general-purpose | Opus 5.5, since untrusted titles enter the writer's prompt | worktree | at open, beside M |
| 4 | Judge | phase-reviewer | Opus 5.5 | shared checkout, break-it in its own worktree | both merged into the phase branch, full suite green |
| 5 | Adversary | phase-reviewer | Fable 5.1, for the prompt-injection hunt | shared checkout, break-it in its own worktree | after the judge |
| 6 | Fix builder X1 | general-purpose | by the findings | worktree | after triage |
| 7 | Fresh verifier | phase-reviewer | Opus 5.5 | shared checkout | after the fixes; names the fix commits as the most dangerous code |
| 8 | Product reviewer | product-reviewer | Opus 5.5 | shared checkout | after merge and deploy |

Workers never dispatch.

### Dispatch table

| # | Role | Model | Start (UTC) | End (UTC) | Tokens |
|---|---|---|---|---|---|
| 1 | Planner | Opus 5.5 | 2026-09-26 05:11 | 05:52 | 601,275 |

## Review focus

### The judge

- The gate is exactly as strict:
  - The diffs of `grounding.py` and `sentence_check.py` are empty, and `SYNTH_SYSTEM_INSTRUCTION` is byte-identical. Paste the prefix test lines.
  - Each new field name licenses only words true of its value: `organism`, `gene`, `title`.
  - `supporting_text` is per finding, so check that no companion licenses a word for another finding's claim.
- Break it; does a test go red?: Run each of these, observe the red, then restore the file.
  - Join titles by position instead of by PMID.
  - Remove the one-line cleaning of titles and of organism names.
  - Make the rs filter a prefix match.
  - Let the value fold `str()` a dict item.
  - Drop the 200-character bound.
  - Let the companion table match `gene` on `Literature variant` rows.
  - Make the title resolver raise.
  - Let the "could not be compared" clause fire on a floor-only `ask`.
- The 20-call ceiling and timeouts:
  - With a query-scoped budget already at 20, the title lookup sends no request and raises nothing, and every finding keeps its PMID.
  - The 15-second bound fires on a stubbed slow fetch.
  - The ortholog template's live time is pasted.
- The event contract: `DonePayload` is byte-identical apart from the comment, and the frontend's runtime is unchanged.
- The split:
  - The tickets together meet done-when item 5.
  - Run G-016, G-021 and G-024 once each on the merged phase branch and paste their citation fields.
  - Check contract 1's literal on both sides.
- Provenance:
  - A title is a Layer 2 citation to the PubMed page it was read from.
  - An organism is cited to the ortholog's own gene page.
  - The gene is cited to `snp/rs334`.

### The adversary

- Untrusted titles as a prompt-injection path into the writer: Test through a stubbed EFetch, then once live.
  - Titles that try to forge a finding line: a newline, U+2028, a bidi override, a zero-width character.
  - Titles shaped as instructions: add an uncited claim, drop a record, or state the title as fact.
  - Marker-shaped text in a title: "[3]" or `[2: "..."]`.
  - A 4,000-character title ending " [truncated]".
  - A title that equals a placeholder ("Not provided"), or equals another record's value.
  - The quote path is the live risk. A writer sentence carrying `[N: "title words"]` skips the restatement drop and reaches the reworded-sentence check. Measure whether a hostile title's claim ships as a fact through the Jev and guard judges.
- Wrong paper: Shuffled EFetch order; a merged PMID answered under another id; duplicate ids; a partial response.
- Near-miss variants:
  - `rs33` against `rs334`.
  - Two rs ids in one question.
  - A LitVar2 match with no rsid.
  - An rs id inside HGVS text.
  - The answer never lists another rs id as if it were the one asked, and never implies no literature exists when the only rows were near misses.
- The lying trust signal:
  - "Their values could not be compared" when only a floor made the answer `ask`.
  - "All from X" when a grounded claim's page belongs to another database.
  - A raw key printed as a name, or a line over 200 characters.
  - "Confirmed" appearing where it did not appear before.
  - Databases named for claims that were stripped.
- Orthologs:
  - A gene with two taxon edges, or none.
  - Odd characters in a taxon name.
  - The several-gene question.
  - The total stays 591 and the row count is unchanged.
  - The graph's 30-second timeout with three concurrent runs.
- Budget and rate limits:
  - A paper-heavy question near the 20-call ceiling.
  - A burst of paper questions against the E-utilities pool, 10 per second with a key.
  - A stubbed 20-second PubMed.
  - Each case either degrades with one log line, or is itself a finding.
- Depth: The same findings reach the writer at both depths.
- Provenance display:
  - A paper's citation moves from Layer 1 to Layer 2 in the source list, as MedGen-named diseases did in phase 6.2.
  - Check that nothing on screen then implies the papers were not found in the graph.

### The product reviewer

- The answer screen at 1280 and 390 for three questions:
  - G-016 at both depths: the Organism column and the plain labels.
  - G-021: the titles in the list.
  - G-024: the Gene column, with no near misses.
- The longer trust line under each answer: horizontal overflow at 390 must be 0.
- Rubric line 3: three answered golden questions, each asked at both depths.

## Out of scope, and why

- Card 38's ESBL isolate gene (G-035):
  - Each isolate row already carries every AMR gene (`amr_genotypes`). The Researcher table already shows them (`TABLE_COLUMNS`, "Isolates and their AMR genes"). Only the writer lacks them.
  - It waits for three reasons:
    - It is not in the owner's approved words for 8.9.
    - `amr_genotype` is a high-risk field token in `synthesis/trust.py`. A companion finding would move every isolate answer's verdict, and this phase changes no verdict.
    - "Which ESBL genes" means picking the ESBL genes out of a full AMR list. That is a judgement for a classifier, not an exact match code can verify.
- The condition for an rs id, from ClinVar (G-024's second half):
  - Probe 2 shows ClinVar holds it: record 15333 lists "Hb SS disease".
  - It also shows that 9 of the 10 records a ClinVar search for rs334 returns are not the plain variant. Eight are compound records, such as "c.[20A>T;428C>T]", "HEMOGLOBIN S (TRAVIS)". One is another allele: c.20A>C, "Likely benign", trait "not specified".
  - A correct version needs three things:
    - a new first-stage call for each rs id;
    - an exact single-variation filter over `variation_set`, a nested shape `ncbi_eutils_actions` passes through unread by design;
    - the placeholder-trait rule.
  - That is a medium ticket with its own review, outside the approved words. The lead brings it to the owner as the next candidate, with this evidence.
  - Until then, G-024 names the gene and cannot name the condition.
- Citing the HBB gene record (G-024's must-cite `gene/3043`): dbSNP carries the id 3043, but citing that page needs a Gene record fetch. The gene reaches the writer through dbSNP, which is what the owner asked for.
- The count line and the first sentence (phase 8.7, card 22's family):
  - G-016's "of 715 available" adds the GO call's 124 to the orthologs' 591.
  - G-024 reads "1 variant record record".
- Other harness-review items:
  - The repair gate (C1, reverted in phase 8.6's fix round): measured again by builder N's runs, not changed here.
  - The writer's prefix (C8), the check-and-adjust step (C7) and the writing-model pick (card 5, after 8.9).
- Phase 8.4's other parked work:
- Unchanged templates and patterns:
  - The several-gene ortholog template and the ortholog count template.
  - "Which organisms have TP53 orthologs?" still selects the taxon template by keyword order. This is pre-existing.
  - An rs id typed in capitals is still not recognised by `_RSID_PATTERN`. This is pre-existing.
- Titles beyond the display cap of 100 findings, and papers PubMed returns no title for.

## Premises and probes

All probes were read-only, about ten calls in all, paced.

- `.env` was loaded inside each script and no value was printed.
- The audit sink was switched off in-process (`TOOL_AUDIT_LOG_ENABLED=false`), so no file was written.
- The graph went through `tools/graph_connection.execute_cypher`, over the configured transport (`https`), and each query passed `validate_cypher` first.

Probe 1: TP53 orthologs and the `in_taxon` hop. Premise proved.

```
Q1 one-hop count rows 1 total 1 seconds 5.35
   orthologs: {'n': '591'}
Q2 two-hop count rows 1 total 1 seconds 5.44
   orthologs with a taxon edge: {'n': '591'}
Q3 sample names rows 8 total 8 seconds 5.1
    {'xid': 'NCBIGene:100009292', 'xname': 'tumor protein p53', 'tid': 'NCBITaxon:9986', 'tname': 'Oryctolagus cuniculus'}
    {'xid': 'NCBIGene:100049321', 'xname': 'tumor protein p53', 'tid': 'NCBITaxon:8090', 'tname': 'Oryzias latipes'}
Q4 current template rows 100 total 100 seconds 5.01
   Gene vertex property keys: ['agent_type', 'id', 'knowledge_level', 'name', 'source', 'source_url', 'xrefs']
Q5 candidate fold template rows 100 total 100 seconds 5.1
    NCBIGene:100009292 ['Oryctolagus cuniculus']
   rows whose taxon list is empty: 0 of 100
```

Probe 2: ClinVar by rs334, through `ncbi_eutils_actions.search` and `summary`. The condition is present; the premise is proved with a caveat, since 9 of 10 records are not the plain variant.

```
clinvar esearch rs334: status ok ids ['15175', '446738', '446748', '446737', '446735', '446731', '446747', '446736', '446730', '15333'] total 10
  15175 | NM_000518.4(HBB):c.20A>C (p.Glu7Ala) | genes ['HBB', 'LOC106099062', 'LOC107133510'] | class Likely benign | traits ['not specified']
  446738 | NM_000518.4(HBB):c.[20A>T;428C>T] | ... | class Pathogenic | traits ['HEMOGLOBIN S (TRAVIS)']
  15333 | NM_000518.5(HBB):c.20A>T (p.Glu7Val) | genes ['HBB', 'LOC106099062', 'LOC107133510'] | class Pathogenic | traits ['Beta-thalassemia HBB/LCRB', 'Hereditary persistence of fetal hemoglobin', 'Hb SS disease', 'Hereditary persistence of fetal hemoglobin', 'Malaria, susceptibility to', 'Hb SS disease']
  germline_classification keys: ['description', 'fda_recognized_database', 'last_evaluated', 'review_status', 'trait_set']
```

Probe 3: the dbSNP row and LitVar2 for rs334, through the product's `ncbi_dbsnp`, `litvar2_lookup` and `_layer_tool_output_to_structured_fields`. Premise proved.

```
dbsnp status ok rsid rs334 genes [('HBB', '3043')]
  pseudo-row fields as handed on: {'clinical_significance': 'not-provided, protective, likely-benign, pathogenic, other', 'functional_consequence': 'coding_sequence_variant, missense_variant', 'rsid': 'rs334', 'genes': 'HBB', 'chrpos': '11:5227002'}
litvar2 status ok matches 5 total 5
   rs334 | c.20A>T | ['HBB'] | Matched on rsid <m>rs334</m> | https://www.ncbi.nlm.nih.gov/snp/rs334
   rs334558 | c.-50T>C | ['GSK3B', 'LOC107986119'] | Matched on rsid <m>rs334558</m> | https://www.ncbi.nlm.nih.gov/snp/rs334558
   rs334348 | rs334348 | ['TGFBR1'] | Matched on rsid <m>rs334348</m> | https://www.ncbi.nlm.nih.gov/snp/rs334348
   rs334353 | rs334353 | ['TGFBR1'] | Matched on rsid <m>rs334353</m> | https://www.ncbi.nlm.nih.gov/snp/rs334353
   rs334773 | rs334773 | ['TRNT1'] | Matched on rsid <m>rs334773</m> | https://www.ncbi.nlm.nih.gov/snp/rs334773
```

Baseline for done-when item 5, from phase 8.2's saved golden run:

```
G-016 1 answered cits 58 | pubmed fields {'title': 5} | gene-page fields {'name': 41, 'symbol': 1} | litvar2 [] | fallback note True
G-016 2 answered cits 58 | pubmed fields {'title': 5} | gene-page fields {'name': 41, 'symbol': 1} | litvar2 [] | fallback note False
G-016 3 answered cits 58 | pubmed fields {'title': 5} | gene-page fields {'name': 41, 'symbol': 1} | litvar2 [] | fallback note True
G-021 1 answered cits 72 | pubmed fields {'curie': 54, 'title': 5} | gene-page fields {'symbol': 1, 'name': 1} | litvar2 [] | fallback note True
G-021 2 answered cits 72 | pubmed fields {'curie': 54, 'title': 5} | gene-page fields {'symbol': 1, 'name': 1} | litvar2 [] | fallback note True
G-021 3 answered cits 72 | pubmed fields {'curie': 54, 'title': 5} | gene-page fields {'symbol': 1, 'name': 1} | litvar2 [] | fallback note False
G-024 1 answered cits 5 | pubmed fields {} | gene-page fields {} | litvar2 ['rs334348', 'rs334353', 'rs334558', 'rs334773'] | fallback note True
G-024 2 answered cits 5 | pubmed fields {} | gene-page fields {} | litvar2 ['rs334348', 'rs334353', 'rs334558', 'rs334773'] | fallback note True
G-024 3 answered cits 6 | pubmed fields {} | gene-page fields {} | litvar2 ['rs334', 'rs334348', 'rs334353', 'rs334558', 'rs334773'] | fallback note False
```

## Where the code overrides the sources

1. Titles today come from EFetch, not ESummary:
   - `plan_literature_follow_up` fetches with EFetch (`action` fetch, `rettype` abstract, `retmode` xml), not ESummary.
   - The PubMed ESummary allowlist (`_SUMMARY_FIELDS_BY_DB["pubmed"]`) has no title field.
   - What keeps those titles safe today is the tool's schema, the 4,000-character `_cap_text` and the exact gate. They are not cleaned of line breaks, and they do not pass the guard-tier reader.
2. C2 proposes a Plan-declared follow-up; the code's precedent is Write-time resolution:
   - The precedent for making a CURIE-only record readable is Write-time resolution: MedGen names (T-6.2-02) and MeSH headings (2026-09-23).
   - A follow-up's title findings would compete for the 30 prompt slots. The list would stay on bare PMIDs, because it shows one entry per page, the lowest number wins, and graph rows are numbered first.
   - T-8.9-01 follows the resolver precedent.
3. TP53 has 591 orthologs in the graph, not 715: The count line adds the GO call's 124: "100 row(s) of 591" plus "59 row(s) of 124".
4. c.20A>T is rs334 itself: The harness review lists c.20A>T among LitVar2's near misses, but it carries rsid rs334 and shares rs334's dbSNP page.
5. For papers, the proof is the list, not the prose:
   - C2's proof is "model sentences kept" on G-021.
   - `drop_record_restatements` drops a prose sentence that only restates a listed record, so a sentence naming a paper's title is dropped once the list shows the title.
6. A two-column template reports its total as unknown, which is why T-8.9-02 must keep 591 explicitly.
7. `DonePayload.trust_line` is capped at 200 characters: Naming every database can exceed that, which is why the line names at most three.
8. Line pointers have moved:
   - The dbSNP pseudo-row with `genes` is in `_layer_tool_output_to_structured_fields`, about line 3962.
   - `_sanitized_citeable_row` is about line 6304.
   - `_pick_representative_field` is about line 7821.

## Decisions this plan takes

Log each of these in `DECISIONS.md` when the phase opens.

1. Paper titles are resolved in Write, like MedGen names and MeSH headings, not planned as a follow-up at Act.
2. Titles come from EFetch, which is live-verified. ESummary is not used, because the PubMed allowlist has no title field. There are at most two requests of 50, and the wait is bounded at 15 seconds.
3. The companion rule is a closed table keyed on record type and field. The variant's gene is emitted under the field name `gene`.
4. The trust line names databases on every "Based on" line, not only under the ask-tier examples. It adds the comparison clause only when a high-risk claim could not be compared, and names at most three databases. The owner sees it at retest.
   - Confirmed by the lead at open, from the user's chair: row 733 asks the line to say what was checked, and a person reading any "Based on" line is better served by the names of the databases than by a bare count.
   - "Confirmed by N independent sources" stays exactly as it is.
5. The ClinVar condition for an rs id, and the isolate genes, wait for the reasons above.

## History

- 2026-09-26: planned.
  - Drafted from the product harness review (C2, C3, W11), cards 8, 37 and 38, the phase 8.7 design's rows G-016, G-021, G-024 and G-035, and the `DECISIONS.md` rows of 2026-09-25 and 2026-09-26.
  - Three read-only probes were run through the product's own code; see [Premises and probes](#premises-and-probes).
  - Not opened yet: it waits on phase 8.6's merge and golden run.
- 2026-09-26: phase 8.6 merged (#108), but its golden run answered 99 of 150 against the floor of 102, so its product code came off develop (#111). This phase does not open until the owner decides whether to accept that drop or fix it first (`tracker/phase_8.6.md`, History). T-8.9-07 applies only once phase 8.6's code is back on develop, since the five flags it closes live in that code.
- 2026-09-26: T-8.9-07 added by the lead for builder M. Phase 8.6's verifier left five open flags, V01, V03, V05, V06 and V07. Phase 8.6 merged with them named rather than run a third round, and this ticket closes them inside 8.9's own review rounds with no extra dispatch.

## Findings

Written the moment a finding is established. Reviewers append here, and this section stays last in the file.
