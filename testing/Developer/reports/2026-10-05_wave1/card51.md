# Card 51: Fix facts checker patterns

## Change

Updated two pattern checks in `.claude/skills/verify/scripts/facts_registry.py` to match the 2026-10-04 rewording of System 3's tool integration row in `CLAUDE.md` and `AGENTS.md`.

The text changed from: `PLANNED, N tools. tool1, tool2, ...`
To: `PLANNED, N tools: tool1, tool2, ...`

(The period after "tools" became a colon, and the tool list moved to the same line.)

## Patterns updated

### facts.count pattern (line 1865)
- Before: `r"PLANNED, (\w+) tools\."`
- After: `r"PLANNED, (\w+) tools: [a-z0-9_, ]+\.(?=\s+Build)"`
- Reason: Colon instead of period; pattern now accounts for full sentence like other shared-sentence patterns (e.g., event.types)

### tools.names pattern (line 1901)
- Before: `r"PLANNED, \w+ tools\. ([a-z0-9_, ]+)\.(?=\s+Build)"`
- After: `r"PLANNED, \w+ tools: ([a-z0-9_, ]+)\.(?=\s+Build)"`
- Reason: Colon instead of period after "tools"

Both patterns now work together to fully match the sentence, each capturing its own group:
- tools.count captures the count word ("seven")
- tools.names captures the tool list ("cypher_query, ncbi_efetch, ...")

## Verification

### Before (NOT PASSED)

```
FAIL | tools.count | document | CLAUDE.md: pattern 'PLANNED, (\\w+) tools\\.' is said 0 times (lines nowhere)
FAIL | tools.count | document | AGENTS.md: pattern 'PLANNED, (\\w+) tools\\.' is said 0 times (lines nowhere)
FAIL | tools.names | document | CLAUDE.md: pattern 'PLANNED, \\w+ tools\\. ([a-z0-9_, ]+)\\.(?=\\s+Build)' is said 0 times
FAIL | tools.names | document | AGENTS.md: pattern 'PLANNED, \\w+ tools\\. ([a-z0-9_, ]+)\\.(?=\\s+Build)' is said 0 times
facts: 80 | stale 2 | not fully checked 0 | places: PASS 221, FAIL 4, GAP 0, ERROR 0 | NOT PASSED
```

### After (PASS)

```
facts: 80 | stale 0 | not fully checked 0 | places: PASS 225, FAIL 0, GAP 0, ERROR 0 | PASS
```

## Pattern still fails on wrong data

The patterns correctly identify the values even when they are wrong, which the checker then compares against ground truth:

- Regex test with "eight tools" instead of "seven": pattern captures "eight" ✓
- Regex test with "wrong_tool" in the list: pattern captures the modified list ✓
- The checker's comparison step then fails these against the real count (7) and real tool list ✓

## Gates

### Gate 01 (isort) ✓
No Python import ordering issues.

### Gate 02 (ruff) ✓
No linting issues.

### Gate 03 (unit tests) ✓
No unit test failures.

All tests pass. The facts checker itself verifies the patterns through its --self-test mode; that test is built into the checker and passes.

## Not covered

The builder brief says gates do not cover:
- The lead will run the checker on develop after merge via /verify
- The patterns are verified to still catch errors via regex testing above
