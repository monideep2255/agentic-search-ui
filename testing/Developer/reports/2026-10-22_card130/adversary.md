# Card 130 adversary round

One round against pull request 294, branch fix/card130-writer-sees-table-columns. Findings are appended as found and are never closed here.

## Findings

### A-130-01: a dbSNP gene is attributed to the other rs id, and the wrong sentence ships cited to the wrong record
- Severity: critical (a confident wrong record, the owner's rule)
- What: the writer's prompt names neither row's rs id. For "What are rs334 and rs6025?" it reads only `[1] Variant record clinical_significance: pathogenic`, `[2] Variant record genes: HBB`, `[3] Variant record clinical_significance: pathogenic`, `[4] Variant record genes: F5`. The grounding pass checks the column sentence against the cited finding's value (`HBB`) plus the question, and the question licenses both rs ids, so a sentence pairing the gene with the wrong rs id grounds. Nothing checks that the rs id in the sentence is the cited record's own rs id. New with this change: on develop the writer never saw a gene, so there was no gene to misattribute.
- Reproduction: my probe (scratchpad `adv/run.py` with `adv/sc_dbsnp.py`), `write_node` with a stubbed writer, real `NcbiDbsnpOutput` rows through `_layer_tool_output_to_structured_fields`, Researcher. Writer reply `rs6025 is in HBB [2].` gives answer text `rs6025 is in HBB [3].` with citation 3 to `https://www.ncbi.nlm.nih.gov/snp/rs334`, claim_text `rs6025 is in HBB`. Writer reply `rs334 is in F5 [4].` ships `rs334 is in F5 [3].` cited to `.../snp/rs6025`. rs334 is in HBB and rs6025 (factor V Leiden) is in F5, so both shipped sentences are false.
- Why it matters: a clinician reads "rs6025 is in HBB", cited, above a table that says F5. The writer cannot get this right except by numbering order, because the prompt never ties [2] to rs334. Source: `synthesis/findings.py:766-787` (the column finding carries no record name) and `synthesis/grounding.py:1595-1600` (`supporting_text` includes the licensed question, which names every rs id).
- NOT FIXED

### A-130-02: an ortholog's organism is stated as the query gene's own organism, with trust "answer"
- Severity: critical
- What: the column finding's value is the bare organism, and the grounding pass accepts any sentence that contains it and otherwise uses only the question's words, the field name, the CURIE and scaffold words. So the question's gene symbol can be made the subject of the organism. The human TP53 record's own citation can sit in the same sentence. On develop each sentence below is stripped and trust is "ask"; on the branch each ships and trust becomes "answer".
- Reproduction: scratchpad `adv/sc_orth.py`, 3 real-shaped ortholog rows through `cypher_query` (template `gene_orthologs_one`) plus a Layer 2 `gene` record `name: TP53` for NCBIGene:7157, question "What are the known orthologs of TP53 in other species?", Researcher. Writer `TP53 is a Mus musculus gene [2].` ships `TP53 is a Mus musculus gene [5].` cited to `.../gene/100000`, trust `answer`. Writer `TP53 [7] is a Mus musculus gene [2].` ships `TP53 [4] is a Mus musculus gene [5].` with [4] the human record `.../gene/7157`, trust `answer`. Writer `TP53 is in Mus musculus [2].` ships, trust `answer`.
- Why it matters: "TP53 is a Mus musculus gene", with the human TP53 record cited beside it, is false (human TP53 is a Homo sapiens gene, the mouse ortholog is Trp53) and reads as authoritative. The trust badge rises to "answer" on exactly this wrong sentence. `synthesis/grounding.py:1595-1625`.
- NOT FIXED

### A-130-03: "only" passes, so one ortholog becomes the gene's only species
- Severity: major
- What: the scaffold vocabulary exempts "only", so an exclusive claim built on one row's organism grounds. The table beside it shows three orthologs in three species.
- Reproduction: same probe, writer `TP53 is found only in Mus musculus [2].` ships `TP53 is found only in Mus musculus [5].`, trust `answer`, above a table of three rows (Mus musculus, Rattus norvegicus, Danio rerio). On develop the same reply is stripped (no organism finding exists), trust `ask`.
- Why it matters: a quantifier that contradicts the table ships as a cited fact. It is the same family as the R-03 "no"/"none" lesson in `synthesis/grounding.py`, now reachable on every ortholog list, because a column value is a short phrase that a writer can wrap in any frame.
- NOT FIXED

### A-130-04: a resistance gene is attributed to the wrong isolate, the two halves cited to two different records
- Severity: critical
- What: a sentence may name one isolate through that isolate's name finding and give it another isolate's resistance genes through the other isolate's column finding. Each clause grounds on its own marker. No check asks whether the two markers in one sentence are the same record. The column finding carries no isolate name, so the writer has only the numbering to pair them.
- Reproduction: scratchpad `adv/sc_iso.py`, three real `PathogenIsolate` rows through `_layer_tool_output_to_structured_fields("pathogen_detection", ...)`: EC000 `mcr-1.1, blaCTX-M-55`, EC001 `mcr-1.1`, EC002 `mcr-3.1`. Prompt: `[3] ... name: EC001`, `[4] ... amr_genotypes: mcr-1.1`, `[5] ... name: EC002`, `[6] ... amr_genotypes: mcr-3.1`. Writer `EC002 [5] has mcr-1.1 [4].` ships `EC002 [3] has mcr-1.1 [4].`, trust `answer`. EC002 carries mcr-3.1, and its own table row says so.
- Why it matters: a surveillance reader is told an isolate carries a colistin gene it does not carry. Each number opens a real record, so each citation looks right. The same mechanism applies to dbSNP rows. `synthesis/grounding.py:1563-1625` grounds each clause against its own marker only.
- NOT FIXED

### A-130-05: a variant's clinical significance and its gene combine into "HBB is pathogenic", a gene-level claim no record makes
- Severity: major (clinical risk; trust stayed "ask" in every run)
- What: the dbSNP picked finding (`clinical_significance: pathogenic`) and the new column finding (`genes: HBB`) sit side by side, and a sentence citing both grounds clause by clause. The record says the variant is pathogenic. It does not say the gene is. The cross-record form also ships: rs6025's significance with rs334's gene.
- Reproduction: `adv/sc_dbsnp.py`, "What are rs334 and rs6025?", Researcher. Writer `HBB [2] is pathogenic [1].` ships `HBB [3] is pathogenic [1].`. Writer `rs6025 is a pathogenic variant [3] in HBB [2].` ships `rs6025 is a pathogenic variant [2] in HBB [3].`, with [3] opening `.../snp/rs334`. Writer `rs334 in HBB [2] is pathogenic [1].` ships, which is correct. Trust `ask` for all three, so the risk verdict still fires on this shape.
- Why it matters: "HBB is pathogenic" is a gene-level pathogenicity statement a clinician could act on. Before this change the writer had no gene, so it could only say the variant was pathogenic. `synthesis/findings.py:766-787`, `synthesis/grounding.py:1563-1625`.
- NOT FIXED

### A-130-06: punctuation-only and placeholder column values reach the writer as findings
- Severity: minor
- What: `column_value_for_row` refuses only blank text, `none`, `null`, `-`, a slashed n/a and a URL. A value of `,`, `.`, `?`, `[]`, `nan`, `unknown`, `not provided` or `missing` ships as a column finding. A real isolate shape produces one: `amr_genotypes=["",""]` joins at `core/graph.py:5181-5182` to `, ` and strips to `,`.
- Reproduction: direct call, `column_value_for_row({'node_or_edge_type':'Gene','fields':{'organism':v,'name':'x'}}, 'name')` returns `('organism', ',')` for `,`, `('organism', '?')` for `?`, `('organism', 'not provided')` for `not provided`, `('organism', 'nan')` for `nan`. End to end (`adv/sc_iso.py`, genotypes `["",""]`, `["not provided"]`, `[",",";"]`), the prompt carries `[2] Pathogen Detection isolate amr_genotypes: ,`, `[6] ... amr_genotypes: not provided` and `[8] ... amr_genotypes: ,, ;`.
- Why it matters: each one takes a prompt slot from a real finding (J-130-02's mechanism). `not provided` and `unknown` are words a writer can state as a fact ("EC002 carries not provided"). The table already shows `,` from the same field, so that part predates this card. `synthesis/findings.py:537-569`.
- NOT FIXED

### A-130-07: column sentences count as citations toward the display cap, so a complete list is reported as truncated
- Severity: major (a false statement to the reader about their own answer)
- What: `citations_capped = findings_capped or len(citations) >= _MAX_FINDINGS_FOR_DISPLAY` (`core/graph.py:15186`, cap 100). A column sentence gets its own citation for a record the table already cites (J-130-04), so 85 records plus 15 column sentences reach 100 citations. The truncation note then fires though every record was retrieved and shown.
- Reproduction: scratchpad `adv/sc_orth_echo.py`, N ortholog rows, all returned (`total_count` equals N), a writer that writes `One record is <organism> [i].` for each organism finding it sees, Researcher. N=84: 99 citations, 84 table rows, no note. N=85: 100 citations, 85 rows, text carries `Note: this answer was truncated to 85 records, though every record that matched this question was retrieved`. N=90: 105 citations, 90 rows, `truncated to 90 records`. Develop at N=90: 90 citations, no truncation note.
- Why it matters: a reader of an 85 to 100 record list is told the answer was cut when it was not. The trigger is the very column sentences this card exists to produce. No test covers a list of this size.
- NOT FIXED

### A-130-08: the reopened saved answer loses the citations behind the last column sentences, so their markers open nothing
- Severity: major (the saved answer and the live answer differ; a cited sentence becomes uncited)
- What: the capture keeps the first 100 citations by citation id (`feedback/capture.py:477-480`), and `GET /v1/history/{trace_id}/answer` slices to 100 again (`adapters/web_sse/app.py:1162`). Column sentences are numbered after every listing row (J-130-04), so on a list of 86 to 100 records they are the citations cut. The saved markdown keeps their markers. The live stream and the command line keep all of them.
- Reproduction: `adv/sc_orth_echo.py`, N=90, events pickled from `write_node`, then `answer_markdown_from(events)` and `one_per_citation_id(...)[:_MAX_CITATIONS]` (scratchpad `adv/render_cmp.py`). Saved: `citations 100 of 105 | markers in markdown 105 | markers with no saved citation [101, 102, 103, 104, 105]`. The command line `Renderer` over the same events prints `[11][101] NCBIGene - .../gene/100010` up to `[15][105] ... /gene/100014`, so it resolves all of them. Develop at N=90: 90 citations, none cut.
- Why it matters: a person who reopens the search sees "One record is ... [101]" with no source behind it, a citation the live answer had. That breaks "every fact links to its source" on the saved surface only, so the live answer, the saved answer and the command line no longer match.
- NOT FIXED

### A-130-01 addendum: in Plain language there is no table to contradict the wrong gene
- Severity: critical (raises the reader-side risk of A-130-01, A-130-02 and A-130-05)
- Reproduction: the same probes at depth `plain_language`. Writer `rs6025 is in HBB [2].` ships `rs6025 is in HBB [3].`, trust `ask`. The only other text on the page is `I found 2 genetic variants on this topic [1][2].` and the source list `Variant record clinical_significance: pathogenic [1]. Variant record clinical_significance: pathogenic [2].` The page has no rs id beside a gene and no gene column. Writer `HBB [2] is pathogenic [1].` ships `HBB [3] is pathogenic [1].`. Ortholog writer `TP53 is a Mus musculus gene [2].` ships `TP53 is a Mus musculus gene [5].`, trust `answer`.
- Why it matters: the Researcher reader can at least see a table that says F5. The Plain language reader, the least able to catch it, sees only the wrong sentence and a medical-advice footer.
- NOT FIXED

### A-130-09: in Plain language the column sentence's citation number is missing from "Where this answer comes from"
- Severity: unsure (presentation; whether the marker still opens the record on the web screen was not probed)
- What: the Plain language source list prints one line per record ([1] to [4] in the ortholog probe). The column sentence's own citation ([5], or [3] for dbSNP) never appears in that list.
- Reproduction: ortholog probe at `plain_language`: prose `TP53 is a Mus musculus gene [5].`, source list `Gene NCBIGene:100000, name: tumor protein p53 [1]. ... Gene name: TP53 [4].` with no [5]. dbSNP probe: prose `HBB [3] is pathogenic [1].`, source list carries [1] and [2] only.
- Why it matters: a reader who looks up "[5]" in the source list finds nothing. It is J-130-04's double numbering, made worse on the depth with no table.
- NOT FIXED

### A-130-10: the right ortholog sentence is stripped while the wrong one ships, because the relation is never in what a column sentence may draw on
- Severity: major
- What: a column finding's supporting text is its value, field name, CURIE, record type and the licensed question (`synthesis/grounding.py:1595-1600`). The row's `traversed_edge_type` (`orthologous_to`) is not in it. So "ortholog" grounds only when the question happens to contain that exact word form. "is a ... gene" and "is found in" always ground, and they state the wrong relation (A-130-02).
- Reproduction: `adv/sc_orth.py`, 3 ortholog rows, Researcher. Question "What are the known orthologs of TP53 in other species?": `TP53 has an ortholog in Mus musculus [2].` is stripped (trust `ask`, no prose), and `One TP53 ortholog is in Mus musculus [2].` is stripped, while `TP53 has orthologs in Mus musculus [2].` ships. Question "Which species have a version of TP53?": `TP53 has orthologs in Mus musculus [2].` is stripped (trust `ask`), while `TP53 is a Mus musculus gene [2].` ships as `TP53 is a Mus musculus gene [4].` and `TP53 is found in Mus musculus [2].` ships, both with trust `answer`.
- Why it matters: the gate's filter on column sentences selects for the false framing. A writer that follows the records and says "ortholog" is cut, and one that drops the relation is shown. The card's own example sentence ("TP53 has an ortholog in Oryctolagus cuniculus") does not ground for the singular form even on the measured question.
- NOT FIXED

### A-130-08 addendum: the MCP and GraphQL surfaces keep the first 100 citations too
- Severity: minor (read, not run)
- What: `adapters/mcp/server.py:1186` appends a citation only while fewer than 100 are kept, and `adapters/graphql/fold.py:666` omits past `MAX_CITATIONS` (100, `adapters/graphql/types.py:188`) with an omission note. So on the 90 record list both surfaces drop the same five column citations ([101] to [105]). GraphQL adds a "citations omitted" disclosure that develop did not show for this answer. I read this code but did not run either surface.
- NOT FIXED

### A-130-11: on a multi-valued column only a word-for-word copy of the whole list grounds, so a true sentence naming one gene is stripped
- Severity: major (the card's benefit does not reach most isolates or multi-gene variants; the wrong-record path of A-130-04 is the single-gene one)
- What: the column value is one comma-joined string (`core/graph.py:5117` for dbSNP genes, `core/graph.py:5181-5182` for genotypes). `ground_claim` needs the whole value inside the clause or the clause inside the value (`synthesis/grounding.py:128-142`). So "EC000 has mcr-1.1" against `mcr-1.1, blaCTX-M-55` fails, and so does "rs334 is in HBB" against `HBB, HBB-AS1`. Live isolates carry many genes (G-035's `acrF, aph(3'')-Ib, blaCTX-M-15, ...`), so a colistin sentence must copy every gene to ground.
- Reproduction: `adv/sc_iso.py`: writer `EC000 [1] has mcr-1.1 [2].` grounds only `EC000 [1].`, which the restatement drop removes, so no prose is shown. `adv/sc_dbsnp_multi.py` (rs334 with genes HBB and HBB-AS1, question "What gene is rs334 in?"): `rs334 is in HBB [2].` is stripped (trust `ask`, "no written summary" note), while `rs334 is in HBB, HBB-AS1 [2].` ships.
- Why it matters: the colistin question is the one the card names for isolates, and the true one-gene sentence a writer would naturally write ("EC000 carries mcr-1.1") never shows. What does show for a single-gene column is the cross-isolate form in A-130-04. The builder's after.md fallback rate (17 of 24 runs, per J-130-01) is consistent with this. That link is a guess and I did not measure it.
- NOT FIXED

### A-130-12: a column claim on a variant record gets claim trust "answer" at risk tier "low", including the wrong-record sentence
- Severity: major (unsure how prominently the web screen shows claim-level trust; the answer-level verdict stays "ask")
- What: per-claim trust is decided from the cited finding's field, and `genes` is not a high-risk field. So the claim behind "rs6025 is in HBB" is marked grounded, `answer`, `low`, while the variant's own `clinical_significance` claims are `ask`, `high`. The answer-level signal is still `ask`, `high`, so card 30's floor and the risk verdict still fire for this shape. That part held.
- Reproduction: `adv/sc_dbsnp.py`, `DUMP_DONE=1`, writer `rs6025 is in HBB [2].`. Trust events: `{"outcome": "ask", "risk_tier": "high", "citation_id": "call-a-1", "scope": "claim"}`, `{"outcome": "ask", "risk_tier": "high", "citation_id": "call-b-3", "scope": "claim"}`, `{"outcome": "answer", "risk_tier": "low", "grounded": true, "citation_id": "call-a-2", "scope": "claim"}` (the wrong sentence), `{"outcome": "ask", "risk_tier": "high", "scope": "answer"}`. Writer `HBB [2] is pathogenic [1].` gives the same split: the gene clause `answer`/`low` and the pathogenic clause `ask`/`high`.
- Why it matters: any surface or client that reads claim-level trust (MCP, GraphQL, a per-sentence badge) is told the false sentence is a low-risk, confident answer. `synthesis/trust.py` (`trust_for_claims`, called at `core/graph.py:15003`).
- NOT FIXED

### A-130-13: the restatement drop does not cover a column sentence, so prose that only repeats the table's column ships
- Severity: minor (presentation; the 2026-09-14 rule says prose is for what the list cannot say)
- What: `drop_record_restatements` compares a sentence with the record's shown row from `one_finding_per_record`, which now skips every `row_detail` finding (`synthesis/findings.py:1444-1457`). A sentence that only states a row's organism or genes, which the table prints in its own column, is therefore never a restatement.
- Reproduction: `adv/sc_orth_echo.py`, N=90, Researcher. The shown prose is `One record is Mus musculus [91]. One record is Rattus norvegicus [92]. One record is Danio rerio [93]. ...` for 15 sentences, above a table whose third column already prints each organism. The develop equivalent ("The clinical trial named X [3].") is dropped by the same function.
- Why it matters: this is the "One trial is named X. Another is named Y" paragraph item 12.12 removed, rebuilt from the column instead of the name, and it is what a writer most easily produces from the new findings.
- NOT FIXED

### A-130-04 addendum: a question that names an isolate gets a wrong one-clause answer about it, trust "answer"
- Severity: critical
- Reproduction: `adv/sc_iso.py`, question "Which isolates near SAMN1000002 carry colistin resistance, and does SAMN1000002 carry mcr-1.1?", the same three isolates (SAMN1000002 is EC002, which carries `mcr-3.1`). Writer `SAMN1000002 has mcr-1.1 [4].` ships `SAMN1000002 has mcr-1.1 [4].`, with citation 4 to `.../biosample_acc:SAMN1000001` and claim_text `SAMN1000002 has mcr-1.1`. Answer trust is `answer`. The accession comes from the question and the gene from the other isolate's column, so one marker on a different record carries the whole false sentence. No second marker is needed.
- Why it matters: the reader asked a yes or no question about one isolate and is told yes, with a citation and trust "answer", when that isolate's record says no.
- NOT FIXED

### A-130-14: the second draft is ordered to report every gene with no rs id beside it, and told the reader cannot see them otherwise
- Severity: major (it pushes the writer toward A-130-01; the judge's J-130-01 covers the directive swap, not this content)
- What: for the dbSNP pair the second writer call carries `COMPLETENESS REQUIREMENT. The system lists the records found below your answer, but it cannot show the findings in the block below that way, so your answer is the only place a reader will see them. Report and cite EVERY finding listed in the block by its marker` followed by the block `[2] genes=HBB` and `[4] genes=F5`. The block names no rs id. The claim that the reader sees these only in the prose is false: the table's gene column shows both.
- Reproduction: `adv/sc_dbsnp.py`, writer `Nothing.`, `DUMP_PROMPT=1`, second prompt, text from `COMPLETENESS` onward, quoted above.
- Why it matters: the writer is required to state each gene, and its only way to name the variant is the question's rs ids, which it must pair by guessing. That is the exact sentence A-130-01 shows grounds when the guess is wrong. `synthesis/findings.py:1945` (`build_listing_gap_directive`) and `core/graph.py:10473-10489` (`_listing_uncitable`, no `row_detail` exclusion).
- NOT FIXED

## Checks that held

- Card 30 and the risk verdict: on the dbSNP pair the answer-level trust signal stays `ask` at risk tier `high` on both branch and develop. Card 30's note keys on graph `SequenceVariant` rows, which this card's table does not touch (`synthesis/answer_layout.py:384-410`, read).
- Duplicate rows: a record returned twice, once by a second call with a different organism value, carries one name finding and one column finding. The second call's record is skipped whole (probe `adv/sc_dup.py`).
- The command line resolves every column marker: `[1][91] NCBIGene - .../gene/100000` groups both numbers under one source.
- Huge lists: the schema caps genotypes at 30 entries of 40 characters and dbSNP genes at 10, so a 50-name list cannot reach the column. The joined value stays under `MAX_FIELD_VALUE_CHARS` (2000) (read).

## Verdict

FAIL. The card's own owner rule is "A confident wrong record is worse than a missing one", and this change makes three confident wrong records reachable that develop strips: a gene given to the other rs id (A-130-01), an ortholog's organism given to the query gene with trust "answer" (A-130-02), and an isolate given another isolate's resistance gene with trust "answer" (A-130-04). Each is a single stubbed writer reply on real row shapes. The grounding pass checks a column sentence only against the cited finding's own value plus the question's words. It never checks that the record the sentence names is the record the value came from, and for dbSNP and isolate rows the prompt does not even tie the value to its record (no rs id, no isolate name on the column line). No test in `test_row_column_findings.py` grounds a column sentence.

These sit inside this phase's fix (card 130's `ROW_COLUMN_FIELDS` and `column_value_for_row`), so the review loop's stop condition applies.

Verified with my own probes (scratchpad `adv/`, stubbed writer, `write_node` end to end, branch against a develop `src` export): A-130-01 to 08, 10 to 14, both addenda that rest on runs, and every "held" item except the two marked read. Read only: A-130-08's MCP and GraphQL addendum, card 30's keying, the schema caps, and whether the web screen shows claim-level trust (A-130-12) or makes the Plain language column marker clickable (A-130-09).
