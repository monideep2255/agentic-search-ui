# Card 109 verifier report

## Finding F-109-V-01 (major): the fix does nothing in the running app

- `frontend/src/lib/api.ts`, `withValidatedOptionalFields` (the last line, `if (source.has_saved_answer === true) validated.has_saved_answer = true;`) drops `has_saved_answer: false`. `fetchHistory` maps every row through it.
- So `formatHistoryMeta` in `App.tsx` never sees `false`, only `true` or missing, and always keeps "N sources cited".
- Probe (own, deleted after): stub `fetch` to return one row `{trace_id:"a", question:"q", citation_count:21, has_saved_answer:false}`, call `fetchHistory`. Observed: `has_saved_answer` is `undefined` (`expected undefined to be false`).
- The new unit test passes only because it mocks `fetchHistory` and so skips the validator. It would pass against a subject that never fixed the real path.
- Result for a person: a stopped search still reads "21 sources cited", as on develop. Not worse than develop, but the card is not fixed.
- Needed: keep `false` in the validator (`typeof === "boolean"`), update its comment, and add a test through the real `fetchHistory`.

## Checks

- Row kinds: server `HistoryItem` has `has_saved_answer: bool = False`, set from `answer_markdown IS NOT NULL`. Signed-in answered, stopped, refusal and clarifying rows would read correctly once F-109-V-01 is fixed. Rows from before the flag existed have it missing and keep their count. Read only.
- Guests: `api.ts` says the history list is fetched for a signed-in account only, so a guest sees no server list. Read only.
- Other readers of the meta string: grep found none in tests, the tour or aria labels beyond the new test. The e2e "sources cited" hits are trust lines, not the rail meta. Read only.
- 390 px: the meta is a wrapping text span and the new text is shorter. Read only, not rendered.
- Mutation: build report's red run was not repeated. Moot, since the test does not reach the real path.
- Query 56 line: describes pressing Stop then opening "Your searches", which an owner can do and see. It would still show the old text until F-109-V-01 is fixed.
- Ran: `npx vitest run` 66 files, 608 passed; `npx tsc --noEmit -p .` clean; `npm run build` succeeds; `ruff check` passed.

## Verdict

HOLD: F-109-V-01.
