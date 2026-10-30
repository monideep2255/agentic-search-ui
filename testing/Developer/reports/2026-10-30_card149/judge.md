# Card 149 judge, round 1

Judge for draft pull request #320, branch fix/card149-human-gene-record-only, tip 3997dede. Findings appended as established.

## Findings

### Evidence E-1: the compiled graph, branch against develop, live PubTator3 replies

Probe (judge's own, not the author's tests): the real compiled graph via `run_streaming`, model stubbed, `cypher_query`, `ncbi_efetch` and `clinicaltrials_search` stubbed at module level, and `pubtator_annotate` run for real with only its transport stubbed to return the live PubTator3 `entity/autocomplete/?query=<SYM>&limit=5` bytes fetched 2026-10-30. The same probe run against `git archive origin/develop` (15363460). Question "Which diseases are associated with <SYM>?", gene resolved to the human NCBI Gene id. NCBI ESummary confirmed the species: 24385 rat, 24525 rat, 24616 rat, 483665 dog, 20423 mouse, 449571 chimpanzee, 14466 mouse.

| Symbol | Gene records cited, develop | Gene records cited, branch | PubTator call status, develop / branch |
|---|---|---|---|
| GCK | 24385, 2645 | 2645 | ok / empty |
| KRAS | 24525, 3845 | 3845 | ok / empty |
| PAH | 24616, 5053 | 5053 | ok / empty |
| INS | 483665, 3630 | 3630 | ok / empty |
| SHH | 20423, 6469 | 6469 | ok / empty |
| GBA1 | 449571, 2629 | 2629 | ok / empty |
| TP53 | 7157 | 7157 | ok / ok |
| BRCA1 | 672 | 672 | ok / ok |

TP53, BRCA1 and the disease question ("Any trials for GERD?", live PubTator3 reply for "gastroesophageal reflux disease") produce byte-identical normalised event summaries on develop and on the branch (only uuids and timings normalised). For the six wrong-species genes the only differences are: the "Literature entity name: Gck" listing section and its citation are gone, the trust line drops from "Based on 4 sources" to "Based on 3 sources" (NCBI Gene stays, from the human record), and the PubTator call reads `empty: 0 record(s)`. The human record stays cited in every case.

### J-149-01: Two of the four hops that carry the fix have no test; cutting either brings the rat record back with every test green
- Severity: major
- What: the new tests call `_layer_tool_output_to_structured_fields` and `_build_layer_tool_calls` directly. Nothing drives the compiled graph with a wrong-species PubTator3 entity, so the plan_node hop (`core/graph.py:7408` to `7413`, the numeric id read from `gene_curie`) and the Act hop (`core/graph.py:8746` to `8748`, `planned.expected_gene_id` passed to the shaper) are unguarded.
- Evidence (temporary edits, restored, `git diff --stat` empty after each):
  - M1, plan_node: `gene_id = tail if tail.isdigit() else ""` replaced by `gene_id = ""`. `test_layer_handoff.py` + `test_pubtator_act_cap.py`: `36 passed`. `test_graph.py` plus every `tests/system_03_search_agent/core/*.py` naming pubtator: `755 passed in 20.70s`. The judge's end-to-end probe under M1, GCK: citations `['https://clinicaltrials.gov/study/NCT00000001', 'https://www.ncbi.nlm.nih.gov/gene/24385', 'https://www.ncbi.nlm.nih.gov/gene/2645', ...medgen/C0342276]`, the rat record back.
  - M2, Act: `planned.expected_gene_id` removed from the shaper call. Same suites: `36 passed`, `755 passed in 21.62s`. Probe: the same four citations, 24385 back.
  - For contrast, the hops the author did test go red: M3 (`_layer_call` drops the field) 1 failed; M4 (id comparison removed) 2 failed; M5 (`db == "ncbi_gene"` removed) 1 failed; M6 (symbol guard removed) 1 failed.
- What a person sees: nothing today. The risk is a later refactor of plan_node or Act that silently drops the id, and the GCK answer cites the rat gene again while CI is green. The build report's "Mutation (id comparison replaced by True) 2 new tests red" mutated only the hop that was tested.
- NOT FIXED

### J-149-02: The isdigit guard on the resolved id is untested
- Severity: minor
- What: replacing `gene_id = tail if tail.isdigit() else ""` with `gene_id = tail` (M7) leaves `test_layer_handoff.py` + `test_pubtator_act_cap.py` at `36 passed`. Checklist item 3 (a non-numeric id behaves as develop) has no test guarding it. See E-2 for the behaviour itself.
- NOT FIXED

### Evidence E-2: a non-numeric or missing resolved id behaves as develop

Same probe, `resolve_symbol_to_curie` returning `NCBIGene:abc` for GCK and for TP53, then returning None. Normalised event summaries, branch against develop: `[NCBIGene:abc] SAME gene_GCK.json`, `[NCBIGene:abc] SAME gene_TP53.json` (both still cite 24385 for GCK, as develop does, since no numeric id exists to compare), `[none] SAME gene_GCK.json`, `[none] SAME gene_TP53.json` (both refuse, no citations, as develop). Verified by probe, not by reading.

### J-149-03: Show work now says PubTator3 returned "0 results" for GCK, when it returned five entities and one was set aside as another species
- Severity: minor (unsure whether the owner counts it as a defect)
- What: when every entity is dropped by the id rule the shaper downgrades `ok` to `empty` (`_shaped`, `core/graph.py:5019`), so the tool_result is `status: empty`, `summary: "empty: 0 record(s)"`, `result_count: 0`. The Show work trace renders tool results as `${tool} — ${result_count} results` (`frontend/src/hooks/useRunView.ts:1171`), so the person reads "pubtator_annotate — 0 results". Nothing in the answer or its notes says that PubTator3 indexes GCK only under a rat record, which is why no literature entity is cited.
- Evidence: judge probe, GCK on the branch: `{'tool': 'pubtator_annotate', 'status': 'empty', 'summary': 'empty: 0 record(s)', 'result_count': 0}`; on develop `status: ok`, `summary: ok: 1 record(s)`. The live PubTator3 reply for `GCK` held 5 entries (`@GENE_GCK` 24385, `@GENE_GCKR` 2646, two LitVar2 variants, `@GENE_MAP4K2` 5871).
- Frequency: the judge's live sample of 30 more common symbols (PubTator3 autocomplete plus NCBI ESearch `SYM[sym] AND 9606[taxid]`) found 5 more where develop cites a non-human record and the branch now keeps nothing: SNCA (20617), VHL (22346), TTN (22138), TNF (24835), VEGFA (83785). With the diagnosis's 6 of 18, about 11 of 48 common genes now show PubTator3 as "0 results".
- What a person sees: the wrong record is gone, which is right. A researcher who opens Show work may conclude PubTator3 knows nothing about TNF or VEGFA, which is false. The diagnosis chose this state deliberately ("the same state as a symbol PubTator3 does not know"); filed so the owner sees the trade.
- NOT FIXED

### Evidence E-3: what else read the PubTator3 entity row

- Citations: `_layer3_row_for_synth_finding` (`core/graph.py:12759`) only cites a row present in `structured_fields`, so the retained typed output in `layer3_raw_outputs` cannot bring 24385 back; confirmed by the probe, no 24385 citation on the branch in any of the six cases.
- PubTator3 publication annotations: planned as a breadth follow-up of `pubmed_search` (`core/graph.py:8965`), built without `expected_gene_id`, so they keep the default. Probe: the shaper's publication rows with `expected_gene_id` "" and "2645" are equal (`True 1`).
- Trust line: "Based on 4 sources cited from NCBI Gene, ClinicalTrials.gov and MedGen" becomes "Based on 3 sources cited from ClinicalTrials.gov, MedGen and NCBI Gene" for the six genes; the count drop is the rat record, and NCBI Gene stays because the human record is still cited. TP53 and BRCA1 unchanged.
- Answer listing: the "Literature entity records found / Literature entity name: Gck" section is removed; no note was added or removed (card 139's notes and the "no written summary" note are byte-identical).
- About page: the Layer 3 line ("PubTator3, LitVar2 and ClinicalTrials.gov. Literature and trial evidence about the gene, disease or variant a question names, when Plan adds them", `InfoScreens.tsx:1280`) stays true; its walk-through question is BRCA1, whose record is human and unchanged.
- Disease and isolate questions: disease probe byte-identical; `test_isolate_search.py`, `test_isolate_search_wiring.py`, `test_disease_breadth.py`, `test_say_what_was_searched.py`: `128 passed in 7.59s`.

### Evidence E-4: gates and related suites
- `ruff check .`: `All checks passed!`, exit 0.
- `isort --check-only --diff src tests services tracker alembic .claude .github` (gate02): exit 0.
- `test_graph.py` plus every core test naming pubtator: `755 passed in 26.72s`. `test_layer_handoff.py` + `test_pubtator_act_cap.py`: `36 passed in 7.25s`.
- Live sample, 30 symbols: no case where develop kept the human record and the branch dropped it (CFTR, EGFR, APOE, MTHFR, LDLR, HBB, PTEN, BRCA2, MYC, HLA-A, HLA-B, CYP2D6, APP, FMR1, DMD, SMN1, ALK, BRAF, NRAS, PIK3CA, ESR1, IL6, ACE2, CD4 all keep the same human id). HTT: the branch keeps whichever id the resolver gives (PubTator3 returns both 3064 HTT and 6532 SLC6A4), so a correct resolution of HTT to 3064 keeps the HTT row.

## Verdict

PASS, no blocking finding. J-149-01 (major) and J-149-03 (minor) both sit inside this card's own fix.

| Checklist item | Method | Result |
|---|---|---|
| 1. Correctness through the compiled graph, against develop | Judge's own probe (E-1), live PubTator3 bytes | Verified: six wrong-species records gone, human record kept, TP53, BRCA1 and disease byte-identical |
| 2. What else depended on the entity | Probe (E-1, E-3) plus reading the citation and follow-up paths | Verified by probe for citations, trust line, listing and notes; publication rows by a shaper probe; About page and card 139 notes by reading and an identical answer text. J-149-03 filed |
| 3. Non-numeric or missing id equals develop | Probe (E-2) | Verified |
| 4. Break it | Seven mutations | M3 to M6 red; M1 (plan_node), M2 (Act) and M7 (isdigit) stay green: J-149-01, J-149-02 |
| 5. Gates | ruff, gate02 isort | Verified, both exit 0 |

Not verified: a deployed run on develop, and whether any other path in a gene answer (outside `pubtator_annotate` entity lookup) cites another species' record; this diff does not touch those paths.
