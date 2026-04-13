## Phase [N.M] - [title]

Branch: `phase/N.M-description`

### Deliverables

- [ ] Deliverable 1
- [ ] Deliverable 2
- [ ] Deliverable 3

### QA gate results

- [ ] Phase 1: tests pass (`pytest -q`)
- [ ] Phase 2: code standards (type hints, docstrings, logging, no bare except)
- [ ] Phase 3: BioLink + KGX validation (categories, predicates, CURIEs, dangling edges = 0, provenance = 100%)
- [ ] Phase 4: schema and dependency tracking updated
- [ ] Phase 5: documentation sync (CLAUDE.md, DECISIONS.md, plan doc)
- [ ] Phase 6: verdict checklist all green

### Decisions made

| Decision | Alternatives | Why |
|----------|-------------|-----|
| | | |

### How to test

```bash
# activate venv
source venv/bin/activate

# run tests
pytest tests/

# run pipeline (small slice)
python -m system_01_data_pipelines.<pipeline> --help
```
