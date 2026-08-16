# Build phase 4.2 judge report, round 1

Verdict: FAIL. Dispatched 2026-08-16 against the merged branch `phase/4.2-cli-adapter`, one fresh-context reviewer at Depth tier, high effort, read-only. Ten findings: one critical, five major, four minor. Three premise clauses are factually unmet.

Baseline the judge established before reviewing:

```
27 passed                          premise gate alone
123 passed                         whole CLI suite
All checks passed!                 ruff
3 failed, 2819 passed, 47 skipped, 1 xfailed   full suite
```

The judge's full-suite figures differ from the lead's own run of the same branch (7 failed, 2749 passed). Both agree the CLI suite and the gate are green and both independently found J-01. The difference is in which live-network-gated cases each environment could reach, and it is recorded rather than reconciled because neither set touches a file in this diff. It is worth remembering that a suite total is environment-dependent, which is the same reason `tracker/phase_3.1.md` forbids citing one as premise evidence.

## Findings

| ID | Severity | Finding | Evidence | Why it matters |
|----|----------|---------|----------|----------------|
| J-4.2-01 | critical, blocking | This branch turns a merge-blocking repo-wide test red. `client.py`'s SSE `Accept` header matches the model-id shape scanner | `model-id-shaped string found outside harness/tiers.py's _DEFAULT_MODELS table: ["adapters/cli/client.py:358: 'text/event-stream'"]` | A gate that blocks merge is red because of this branch's own new file. Already filed as F-4.2-09 with the fix deliberately held during review. A scanner false positive, but the fix is owed by this phase, not deferred |
| J-4.2-02 | major | THE THIRD TICKET SEAM. `main.py:290` catches `httpx.HTTPStatusError`; `credentials.py:260` raises `RefreshError`, which is not an httpx type. The CLI's most routine failure, an expired session, falls through to the catch-all | Live probe: `EXIT 1`, stderr `s3: unexpected error (RefreshError): POST /auth/refresh returned 401; ... Run: s3 login` | Identical shape to F-4.2-08, found because the judge was told to assume a third existed. `main.py:291-294`'s intended message is dead code. The user is told an ANTICIPATED, TYPED failure is "unexpected", through a raw `str(exc)` interpolation at `main.py:743`, the F-4.1-A-09 shape `render.py` deliberately avoids. Arm 11's 401 clause asserts only `err.strip() != ""`, so it passes on this |
| J-4.2-03 | major | The "second, independent" cost-suppression layer is a CLIENT-SUPPLIED FLAG. `--operator` reaches `Renderer(operator=...)` from argv with no credential check anywhere | `main.py:348` to `main.py:521` to `render.py:265`. Server-side truth is `cost_control.py:642 is_operator_user(user_id)`, an allowlist | The premise claims the CLI's suppression "holds independently, so a future server-side regression cannot surface a dollar figure." Anyone typing `s3 ask --operator` defeats it. There is one layer plus a toggle the untrusted party controls. `main.py:351`'s help text describes a credential check the code does not perform. Arm 12 hardcodes `operator=False` and cannot see it |
| J-4.2-04 | major | A run that dies mid-answer leaves an uncited claim on stdout with no references block and no trust outcome | `render.py:303`: `_write_references_block()` is called from `_handle_done` only; `finish()` never calls it. `main.py:533-535` returns the interrupt code without calling `renderer.finish()` at all. Probe: stdout `BRCA1 is associated with hereditary breast cancer [1].` with no reference | `s3 ask > answer.txt` on an interrupted run yields a file containing a biomedical claim, a `[1]` marker, no reference, and no sign of truncation. The honest-unresolved-marker machinery exists at `render.py:337-341` and is simply not wired to the path that needs it. Nonzero exit and stderr are the only mitigations and neither survives a redirect |
| J-4.2-05 | major | F-4.2-05 is still open, and the shipped behaviour fails the premise clause it was meant to arbitrate. The trust tag is a SUFFIX, glued mid-line to the last token | Probe: `BRCA1 is a protein-coding gene [1]. [answer]` then the references. `index of '[answer]': 36`, `PREFIX? False`. `render.py:261` writes `f"[{outcome}]\n"` with no leading newline | The premise says "the answer body carries the trust prefix." It does not. Worse, `render.py`'s own docstring claims the tag prints "as a standalone stdout line" and the code does not do that, which is the `self-eval-loop` liability case: a comment asserting a property the code lacks is where the next reader stops checking |
| J-4.2-06 | major, re-rate | F-4.2-04 was filed as minor and is not | Same evidence as J-4.2-05 | It is a premise clause that is unmet, whose only verify surface cannot detect it, whose documented resolution is not what the code does. Escalating to the product owner is right; carrying it as minor while the gate stays green is not |
| J-4.2-07 | minor | `_run_login`'s `POST /auth/login` declares no timeout | `main.py:408-410`, versus `client.py:333, 367, 392, 410` and `credentials.py:257` which all declare one | `tool-call-budgets`: a call without a declared timeout is not finished. It inherits the injected client's `read=120.0`, an eight-fold drift from the 15s budget this same phase applied to `/auth/refresh`, the identical auth-router call shape |
| J-4.2-08 | minor | The gate's coverage-exclusion section describes arms that DO NOT EXIST, and omits the real blind spots | The section claims "the `Last-Event-ID` resume arms drive the resume code path". `grep -c` for `Last-Event-ID\|last_event_id` in the gate returns 1, that sentence itself | Exactly the failure `tracker/phase_4.10.md` recorded and that this section cites by name: a coverage declaration that excuses a gap while implying coverage. It also omits three genuine blind spots: `main.py` never passes `last_event_id` at all, so resume is UNREACHABLE in production, and `fetch_citations` and `parse_sse_lines` likewise have zero production callers |
| J-4.2-09 | minor | The "a 401 is rejected before any handler body runs" claim is false for `POST /v1/query`, so the create IS reissued on the 401 path | `main.py:275-277` and the gate both assert it. `app.py:735-748` raises 401 from INSIDE the handler, after `count_active_runs_for_owner` and after `spend_one_anonymous_run` | The never-retry-create safety argument rests on a claim about the server that is not true in general. It does not bite today only because the CLI holds user tokens and never guest tokens, an accident of how `s3 login` works rather than a structural guarantee, and nothing pins it |
| J-4.2-10 | minor | `load()` refuses a wide FILE but never checks the containing DIRECTORY, and the check is TOCTOU | `credentials.py:147-154` stats the file only. `credentials.py:178-181` sets `0o700` on the parent only when creating it, so a pre-existing `~/.system3` at `0o777` is neither narrowed nor refused. `os.stat` at :148, `open` at :156 | A world-writable parent lets another local account replace the credential file wholesale, defeating the mode-600 control the module exists to enforce |

## What the judge confirmed as genuinely sound

Recorded because a review that lists only failures gives no signal about what is safe to build on.

- Cite-or-refuse is not weakened. `render.py:239` writes token text verbatim, so client-side renumbering is structurally impossible; the references block is built only from delivered citation events, reports unresolved markers honestly rather than dropping them, and prints nothing rather than an empty block presented as complete. The one exception is the mid-answer death path, J-4.2-04.
- The refresh lock is real, and the judge mutation-proved it independently rather than trusting the ledger: replacing the lock with a no-op turned the arm red 3 times out of 3, deterministically.
- Credential write discipline is correct: mode 600 at the creating syscall with `O_CREAT|O_EXCL`, atomic `os.replace`, refusal rather than a warning on a wide file, temp file cleaned on any failure.
- No secret reaches any output path. The password sentinel arm proves it reaches neither argv, stdout nor stderr on a failed login.
- Create is structurally unretriable on the timeout and transport paths, proven by call-count assertions. The 401 path is the exception, J-4.2-09.
- Scope is clean. Both declared substitutions are genuine substitutions rather than new capabilities, and nothing touches the PRD out-of-scope list or the Section 25 fast-follow table.
- Packaging is exactly correct: 13 packages on disk, the same 13 declared.

## The gate, audited as harshly as the code

Twelve of fourteen arms can fail and name a mutation that would genuinely turn them red. Four cannot carry their stated weight:

- Arm 11's 401 clause asserts `exit_code != 0` and `err.strip() != ""`. It is the arm built for exactly the failure J-4.2-02 describes and it passes on a message reading "unexpected error". It needs to assert the specific copy, the way Arm 9 was repaired to assert "stopped before it finished".
- Arm 1's trust clause is F-4.2-05, still position-blind.
- Arm 12's second test fixes `operator=False` and therefore cannot see J-4.2-03.
- Arm 2's refusal fixture emits no citation events at all, so "no fabricated citation" is asserted against a stream that never had one. The dangerous case, a refusal arriving WITH citations present, is neither tested nor declared.
