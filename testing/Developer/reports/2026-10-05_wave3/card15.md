# Card 15, step 1: Article anchors

## The change

- Before: one PubMed paper with no hop word in the question ("sequence data for PMID 11237011", golden G-006) on a single-hop, multi-hop or aggregate class got no template, so the model wrote the graph search and it failed.
- After: `select_template` returns a checked template, `article_links_one`, built by `_article_links_template` in `src/system_03_search_agent/tools/cypher_templates.py`. It is three single-edge inline id matches joined by UNION ALL: MeSH terms (`has_mesh_annotation`), papers the article cites and papers that cite it (`cited_in`). Each branch has its own ORDER BY.
- Applies to exactly one Article anchor, no count request. Count questions (how many, or count and number of on an aggregate class), several Articles, Gene and Disease anchors, and questions with a shape word (for example MeSH) are unchanged.
- The graph has no edges to sequence data, BioProjects, GEO series or assemblies. The template returns what the graph holds for the paper; the answer for the rest has to come from Layer 2 (card 74, the elink call).

## Finding the lead must know

The obvious second edge, genes that mention the paper (`mentioned_in`, matched from the Article end), times out at the 30-second statement limit on the live graph for PMID 11237011. That is very likely the timeout the model-written draft hit on 2026-09-29. It is left out of the template. A fast way to list a paper's genes needs an index or a different query shape, and is not part of this step.

## Tests (`tests/system_03_search_agent/tools/test_cypher_templates.py`)

- One Article, no hop word, three classes: selects `article_links_one`, three ORDER BY, no `mentioned_in`. Failed on the old code (3 failures).
- The template's Cypher passes `validate_cypher` and normalizes to three LIMITs. Failed on the old code.
- Count questions on an Article, and two Articles, still return None. These pass on old and new code: they guard the paths that must not move. The old row "Tell me about PMID" on a hop class was removed from the fall-back list because that behavior changed on purpose.
- The MeSH question still takes `article_mesh_one`. Passes on both.
- `all_template_examples` now includes the new template, so the existing every-template validator test covers it.
- Old-code proof: the old file was restored from `HEAD` into place, the tests run (4 red, 63 green), and the new file copied back. No stash.

## Gates

- Gate 2 (import order): green. Gate 3 (lint, whole repository): green.
- Gate 4 (unit suite): 6539 passed, 6 failed, 229 skipped. All 6 failures are connection refused to a local PostgreSQL (port 5432) in tests that need the user database, none touch templates. Not re-run against develop.

## Live run (read-only, through the repository's own `execute_cypher`)

- Graph access works from this shell (the main checkout's `.env` sets the HTTPS graph service).
- Template for PMID 11237011, validated then run: 26 rows in 1.26 s, all MeSH terms, none from the two citation branches (cited and citing counts are zero for this paper; each branch measured 0.5 s and 2.1 s alone).
- The `mentioned_in` branch alone: timeout at 30.4 s.

## Not covered

- No end-to-end answer run: how Write phrases 26 MeSH rows against a question that asked for sequence data is the lead's test-query check on develop, and card 74 owns the Layer 2 call.
- Rows from the UNION share one variable across two edge labels, so the per-row traversed edge type is left empty for them (the code already treats that as unknown). Not tested against the full agent loop.
