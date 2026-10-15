# Card 109 verifier 2 (fix round 85b3f1c0)

Verdict: MERGE

Probed myself
- Mutation: validator reverted to `=== true`. Two tests went red (App.historyNoAnswer.test.tsx rail text through the real fetchHistory; api.fetchHistory.test.ts boolean keep). Restored with git checkout.
- The rail test stubs only fetch; false row reads "No answer saved" with no "sources cited"; true and missing keep "21 sources cited".
- Whole vitest suite: 67 files, 610 tests pass. tsc --noEmit clean. npm run build succeeds (chunk size warning only, pre-existing kind). ruff check (no path): all checks passed.

Readers of has_saved_answer in frontend/src (false changes nothing else)
- App.tsx formatHistoryMeta: false gives "No answer saved" plus the date (the intended change).
- App.tsx restored-row builder: `item.has_saved_answer === true`, false gives hasSavedAnswer false, same as before the fix (previously dropped to absent, same result).
- App.tsx onOpen: `hasSavedAnswer === true`, false re-asks as before.
- App.tsx line 1290 live-row marking: `!== true`, unaffected.
- No tour or aria-label code reads the flag.

API (read)
- feedback/history.py: has_saved_answer = answer_markdown IS NOT NULL, so a stopped row sends false. web_sse/app.py passes it through. history_api_rows.json shows real rows with false (refuse) and true.

Read only: backend route code and the tour/accessibility search (grep, not run).
