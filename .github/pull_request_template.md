## Phase [N.M] - [title]

Branch: `phase/N.M-description`

### Deliverables

- [ ] Deliverable 1
- [ ] Deliverable 2
- [ ] Deliverable 3

### QA gate results

- [ ] Phase 1: tests pass (`pytest -q`)
- [ ] Phase 2: code standards (type hints, docstrings, logging, no bare except)
- [ ] Phase 3: citation provenance and schema validation (every claim cites source, source_id, source_url, layer; tool and subagent outputs validated against JSONSchema)
- [ ] Phase 4: documentation sync (CLAUDE.md, DECISIONS.md, plan doc)
- [ ] Security gate: ran `/claude-security` on the branch, reviewed findings, applied or accepted each (see `docs/Claude_security_plugin_usage.md`)

### Decisions made

| Decision | Alternatives | Why |
|----------|-------------|-----|
| | | |

### How to test

No application code exists yet as of Phase 5 (planning). The commands below are this repo's intended entry points, per README.md, once Phase 6 build execution begins.

```bash
# activate venv
source venv/bin/activate

# run the API
uvicorn system_03_search_agent.api.main:app --reload

# run tests
pytest tests/
```
