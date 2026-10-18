# Card 54 build: a reopened long answer keeps every citation

## Table of contents

- [The change in the reader's words](#the-change-in-the-readers-words)
- [Choices](#choices)
- [Tests](#tests)

## The change in the reader's words

Reopening a long past answer used to lose every source after the fiftieth, so a marker such as [77] pointed at nothing and the rows sat under a line naming more sources than were listed. Now the reopened answer lists every source the live answer showed, up to 100, and the citations export returns the same. No schema change: the stored column was already unbounded.

## Choices

- Ceiling 100, matching what one live answer can cite (the display cap) and what MCP and GraphQL already return. Rejected: 200 or no cap, because the run can never reach it and a bound must stay a bound.
- One named constant, `MAX_CITATIONS_PER_ANSWER` in `feedback/contracts.py`, used by capture, the stored row model, the saved-answer model and slice, and the export. Rejected: five separate literals, which is how the five drifted before.
- Code only, no migration. Rejected: a column constraint, because the column has none and a migration would run on every develop deploy.
- Frontend untouched: the screen and the history count already follow whatever the stored list holds.

## Tests

- Capture of 61 citations stores 61 (red at 50, green at 100); above the ceiling it truncates to 100.
- Saved-answer endpoint returns 61 (red at 50, green at 100); 130 stored returns 100; the response model bound reads 100.
- REST export returns 77 with no truncation header (red at 50, green at 100); 120 events return 100 with the truncation header.
- Stored row model accepts 100 and refuses 101; the constant equals the run's display bound.
