---
paths: ["src/**/*", "frontend/src/**/*", "services/**/*", "tracker/phase_*.md", "testing/Future.md"]
---
## V1 scope boundary

`requirements/PRD.md` and `requirements/Technical_specification.md` are locked and name what v1 excludes. Never edit either. Never build an excluded capability because it looks easy, fits naturally or would improve a demo.

- Anchor cases: no BLAST, no sequence-similarity search, no VCF ingestion.
- Also excluded: UCSC segmental duplication, non-NCBI knowledge-graph federation, model distillation, fusion panels, automated feedback mining, persistent cross-session memory, sub-query decomposition, the full Section 508 and WCAG audit, enterprise IAM, and the federal authorization path.
- Each has a named trigger, and only a human confirms a trigger is met.
- Crossing the boundary means stop and report: name the capability and its line, say what would have been built, never substitute silently, and wait.
- Bossman mode does not suspend this rule.

Full lists, with each trigger: `.claude/rules-reference/v1-scope-boundary.md`.
