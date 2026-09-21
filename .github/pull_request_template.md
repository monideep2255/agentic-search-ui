## Phase [N.M] - [title]

Branch: `phase/N.M-description`

### Deliverables

- [ ] Deliverable 1
- [ ] Deliverable 2
- [ ] Deliverable 3

### Merge-blocking gates (Section 24)

CI runs all ten on this pull request and is the authority. Do not tick a box here that the run did not earn: this list exists so a reader knows what was checked, not so an author can assert it.

- [ ] 1. Python compiles and imports cleanly
- [ ] 2. Import order (`isort --check-only`)
- [ ] 3. Lint (`ruff check`)
- [ ] 4. Unit test suite (`pytest -m "not integration"`), with no test skipped for a missing database
- [ ] 5. Integration test suite (`pytest -m integration`), or recorded as NOT RUN with the reason
- [ ] 6. Python dependency audit (`pip-audit -r requirements.txt`), no Critical or High CVE
- [ ] 7. Frontend dependency audit (`npm audit --audit-level=high`)
- [ ] 8. Frontend build and test (`npm run build`, `npm test`)
- [ ] 9. Required-path tests, never skippable (cite-or-refuse, zero-retrieval refusal)
- [ ] 10. Accessibility, WCAG 2.1 AA (UI-touching pull requests only)

### The human gates CI does not run

Section 24 is explicit that the security scan is not an automated block: `claude-security` produces human-reviewed patch files, not a pass or fail signal, so a CI gate would misrepresent a step that needs a person to approve each patch.

- [ ] Security scan: ran `/claude-security` on this branch, reviewed the findings, applied or accepted each one (see `docs/Claude_security_plugin_usage.md`). Required before a release; judgement call otherwise, scaled to the attack surface this change actually adds
- [ ] Citation provenance: every claim carries `source`, `source_id`, `source_url` and `layer`; every tool and subagent output is schema-validated
- [ ] Documentation sync: `CLAUDE.md`, `DECISIONS.md`, `LEARNINGS.md`, `tracker/BOARD.md`, the phase file, and `docs/build/Debugging_guide.md` if any file under `src/` was added, deleted, renamed or repurposed
- [ ] Review rounds used, and whether any finding sat inside an earlier fix from this same phase

### Decisions made

| Decision | Alternatives | Why |
|----------|-------------|-----|
| | | |

### How to test

```bash
source venv/bin/activate

# The API
uvicorn system_03_search_agent.adapters.web_sse.app:app --reload

# The gates, as CI runs them
python -m compileall -q src services tests alembic
isort --check-only --diff src tests services tracker alembic .claude
ruff check
pytest -m "not integration" -q
pip-audit -r requirements.txt

# Frontend
npm --prefix frontend ci
npm --prefix frontend audit --audit-level=high
npm --prefix frontend run build
npm --prefix frontend test
```
