# Card 112 verifier report

Fresh verifier, 2026-10-09, branch fix/card112-history-after-stop at 5d7c38bb, base develop d0319502. Own vitest probes through the real App and the real fetchHistory with fetch stubbed; the probe file was kept out of the checkout afterwards.

## Findings

None new. The known minor items (failed re-ask leaving bare rows, guest stop before sign-in, failed run reading as answered, stop then re-ask before the reply) are the adversary's A-112-01, 03, 05, 06, 07; they are before this card or choices the build named, and none is worse than develop for a person.

## Checks, each run by me

- Stop: ask a listed question, press Stop, server sends cancelled. Every earlier row stays; the top row reads "<question>No answer saved · <date>". After a remount fed the server's list (stopped run on top, then the four earlier rows) the rows, text and order are identical (5 and 5). Passed.
- Limit: a 20 row account, re-ask and stop. Before reload 20 rows, after reload 20 rows, identical text and order. Passed (the judge's J-112-02 overflow is fixed).
- 4.13 modes: stop, two failed re-asks, one answered re-ask, then opening restored rows. No "same key" console error. Opening the oldest restored row called fetchHistoryAnswer with its own trace id (t-answered-1), another with t-answered-2. The highlight sat on the opened row each time (J-112-03 fixed). No row showed another run's numbers.
- Card 59: Stop pressed with the stop request pending, the answer then done, then a stray cancelled. The row reads the answered counts, never "No answer saved", and the answer stays on screen. Passed.
- Mutation 1, text filter put back: 8 tests red (5 shipped, 3 of mine). Restored with git checkout.
- Mutation 2, stopped-row update disabled: 4 tests red (2 shipped, 2 of mine). Restored with git checkout.
- App.tsx hash after restores equals the hash before mutating.
- Whole suite: 68 files, 618 passed. npx tsc --noEmit -p . exit 0. npm run build succeeds (chunk size warning only). ruff check from the root: all checks passed.

## Read only, not probed

Midnight date difference between the confirmed-stop date and the server's created_at (named in the code comment as possible), guest sign-in migration, StrictMode, the deployed app.

## Verdict

MERGE. Nothing is worse than develop for a person; the fix round closed the judge's J-112-01, 02, 03 and 04, and the four failure modes stay closed.
