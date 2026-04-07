---
name: qa-gate
description: Post-task quality gate that runs before any commit on a pipeline change. Six phases: tests, code standards, BioLink validation, KGX shape, dependency tracking, verdict.
---

# QA gate

Run before committing any change to `data-pipelines/`, `knowledge-graph/`, `schema/`, or shared utilities. Six phases. Stop at the first failure, fix the root cause, restart from phase 1.

This is the rigid kind of skill. Do not skip phases. Do not reorder them.

## Phase 1: tests pass

```bash
pytest -q
```

If anything fails, fix it. Do not delete or `xfail` failing tests to make the gate pass. If a test is genuinely obsolete, delete it deliberately and note why in the commit.

For new code: there should be a test next to it. If you wrote a parser, there is a `test_parser.py` that exercises it on a small fixture under `tests/fixtures/`.

## Phase 2: code standards

Apply `.claude/skills/python-code-standards/SKILL.md`:

- Type hints on every public function signature.
- Google-style docstring on every module and every public function.
- No bare `except:`. Catch `Exception` at most, log, re-raise or convert to a named pipeline error.
- No `print()` in library code. Use `logging`.
- Constants in `UPPER_SNAKE_CASE` at module top, not magic literals inside functions.

Apply `.claude/skills/testing-standards/SKILL.md`:

- One assertion per test concept.
- Fixtures for shared setup, never copy-paste.
- Tests do not hit the network unless marked `@pytest.mark.integration`.

## Phase 3: BioLink + KGX validation

For any change that produces or consumes nodes/edges:

1. Every node has `id`, `category`, `name`, `source`, `source_url`. Categories are valid BioLink classes.
2. Every edge has `subject`, `predicate`, `object`, `source`, `source_url`. Predicates are valid BioLink slots.
3. CURIE prefixes are canonical (`NCBIGene:`, `MONDO:`, `MedGen:`, `PMID:`, `NCBITaxon:`, `GO:`, `HP:`, `MeSH:`, `ClinVar:`, `dbSNP:`).
4. Run the eval-harness gates (see `.claude/skills/eval-harness/SKILL.md`):
   - `assert_no_dangling_edges`
   - `assert_load_parity` (KGX row count round-trips through Postgres+AGE)
   - Provenance coverage = 100% on a sample.

If the pipeline output is a KGX file, sanity-check the column order and tab-separation by `head -1` on the resulting `nodes.tsv` and `edges.tsv`. Wrong column order is the most common silent breakage.

## Phase 4: schema and dependency tracking

If you touched a schema file or any cross-module import:

1. Re-run schema validation: `linkml-validate -s schema/biolink_ncbi.yaml <some_kgx>.yaml` (or the equivalent).
2. Update the `Depends on` / `Reads` / `Writes` block in the module docstring per `.claude/rules/dependency-tracking.md`.
3. If a `.claude/` component (skill, agent, rule) was added or renamed, update both its `depended_by` field and the file that depends on it.
4. Grep the repo for the old name if you renamed anything. Do not trust your memory.

## Phase 5: documentation sync

If your change affects how a pipeline is run, what it consumes, or what it emits:

1. Update the relevant section of `docs/System_1_data_engineering_plan.md`.
2. Update `CLAUDE.md` if it shifts current focus or build order.
3. If a non-trivial choice was made (library, file structure, predicate selection), append a row to `DECISIONS.md`.

Do not create new top-level docs. Edit the ones that already exist.

## Phase 6: verdict

Walk through this checklist out loud (in your head, in the chat, in your commit body — pick one):

- [ ] All tests pass
- [ ] Code standards clean
- [ ] BioLink + KGX validation clean on the affected pipeline
- [ ] Dangling edges = 0
- [ ] Provenance coverage = 100% on sample
- [ ] Schema and dependency tracking updated
- [ ] Docs in sync
- [ ] DECISIONS.md updated if applicable

If every box is checked, you may commit. If any box is not checked, you may not commit. There is no "I'll fix it next time."

## What this skill does NOT cover

- Deployment. There is no deploy step in this repo. KGX files land on disk, Postgres + AGE loads them locally.
- Frontend. There is no frontend.
- Railway, Render, Netlify, Neon. None of these apply.
- Phase tracking against an external task list. We use `DECISIONS.md` and the build order in `CLAUDE.md`.
