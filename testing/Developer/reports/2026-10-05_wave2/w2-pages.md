# w2-pages: cards 79, 80, 85 (two sentences), 61 (wording)

Branch `fix/cards79-80-85-page-batch`. Paths relative to `<repo-root>`.

## What changed

- Card 79: the Command line tools card now prints the install command, the sign-in and ask example and the agent configuration in three labelled code boxes, with the prose split into short paragraphs between them (`CLI_CARD_SEGMENTS` replaces the 300-word `CLI_CARD_BODY`). The copy-failure message says "Select the command shown above and copy it by hand." on a card that shows code, and "Allow clipboard access for this page, then try again." on the REST and GraphQL cards, which show none. `s3 mcp --help` ends with a full stop (`adapters/cli/main.py`).
- Card 80: the About page layer cards render before the walk-through (`data-testid="about-layer-cards"`); the stale "further down" comment is fixed.
- Card 85, page sentences: the layer 3 stop (`ArchitectureScreen.tsx`) now names five kinds searched another way. Checked against `core/graph.py` `plan_node`: a gene named by an identifier (no symbol), an isolate question, a no-gene question read as asking for papers, a disease whose `_disease_search_text` lookup returns None, and a disease named by a non-MedGen identifier (`_first_disease_curie` reads only `MedGen:`). The last two get the graph call alone, and the sentence says so. The About walk (`JOURNEY_LAYERS` layer 1) says most live searches run at the same time and four of the thirteen calls follow in a second round (BRCA1 plan: 13 calls, 4 in round two, per F-53-V06 and `act_node`).
- Card 61, wording: already done. The MCP card says follow-up offers "are not part of MCP"; no "coming next" remains, and an existing test pins it. No edit needed.
- Facts registry (`facts_registry.py`): the `L3_OTHER_WAYS` sentence and the `layer3_other_ways` truth carry two more keys (`disease_lookup`, `disease_identifier`); the About sentence pattern for `loop.layer_one_read_first` carries the new wording.

## check_facts.py

- Before: `facts: 80 | stale 0 | not fully checked 0 | places: PASS 225, FAIL 0, GAP 0, ERROR 0 | PASS`
- After: identical line, PASS.

## Tests, each red on old code

Proved by restoring `origin/develop`'s `InfoScreens.tsx` and `main.py` into the worktree (no stash), then restoring mine. Red: About order test, code-boxes test, clipboard message test, no-pointer test, and `test_s3_mcp_help_says_to_name_s3_by_its_full_path` (full stop). Existing tests pinning card text (needs git and Python 3.11, command -v s3 sentence, KGX sentence, no "coming") pass unchanged.

## Gates

- gate02 green, gate03 green.
- Frontend: `tsc --noEmit` clean, full vitest 58 files and 488 tests pass. node_modules was linked from the main checkout for the run and unlinked after; no new dependencies.
- gate04: 6 failed, 6528 passed. All six fail with `psycopg2 connection refused` on localhost:5432 (no local database in this shell); none touch changed files.

## Not covered

- No browser look at 1280 and 390 px; layout is checked in jsdom only. A `/verify` pass should view the Integrations and About pages.
- Accession questions (a record accession) also take their own plan branch with no layer 3 call; the card asked for five and the page still does not name this path. Flag for a later card.
- `vite build` was not run separately (tsc and vitest only).
