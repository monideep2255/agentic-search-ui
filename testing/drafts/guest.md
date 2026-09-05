# Guest lifecycle workflows

What the guest experience is for: a stranger must be able to judge whether this product is worth an account before creating one. The product lets an anonymous visitor ask real questions against the real agent, cited the same way a signed-in answer is cited, for a bounded number of free answers, so the decision to sign in is made on evidence rather than on a marketing claim. Every control in this lifecycle exists to keep that trial honest: the allowance is server-counted rather than guessed, a clumsy question does not cost the trial, and the trial cannot be multiplied by opening a second tab or minting a new identity for free.

## Table of contents

- [W-GUEST-1: A first visit](#w-guest-1-a-first-visit)
- [W-GUEST-2: Asking the first question, from a chip and from typing](#w-guest-2-asking-the-first-question-from-a-chip-and-from-typing)
- [W-GUEST-3: The allowance counting down across five answers](#w-guest-3-the-allowance-counting-down-across-five-answers)
- [W-GUEST-4: A returning guest cannot see their own allowance](#w-guest-4-a-returning-guest-cannot-see-their-own-allowance)
- [W-GUEST-5: The attempt ceiling is not the answer allowance](#w-guest-5-the-attempt-ceiling-is-not-the-answer-allowance)
- [W-GUEST-6: The wall on an exhausted allowance](#w-guest-6-the-wall-on-an-exhausted-allowance)
- [W-GUEST-7: The wall on the attempt ceiling](#w-guest-7-the-wall-on-the-attempt-ceiling)
- [W-GUEST-8: The wall on a migrated identity](#w-guest-8-the-wall-on-a-migrated-identity)
- [W-GUEST-9: What a guest can and cannot do](#w-guest-9-what-a-guest-can-and-cannot-do)
- [W-GUEST-10: Guest to account migration, and the five-minute window that empties it](#w-guest-10-guest-to-account-migration-and-the-five-minute-window-that-empties-it)
- [W-GUEST-11: The shared daily ceilings, which are not the guest's own allowance](#w-guest-11-the-shared-daily-ceilings-which-are-not-the-guests-own-allowance)
- [Notes on the two things I was asked to check](#notes-on-the-two-things-i-was-asked-to-check)

### W-GUEST-1: A first visit

The product must: show a stranger the medical disclaimer before anything else is usable, and show them a landing screen that explains what the tool does and invites a question, without claiming an allowance the server has not yet counted.

Status: BUILT, `frontend/src/components/shell/DisclaimerModal.tsx:47-215`, `frontend/src/App.tsx:1079` (`<div inert={!accepted}>`), `frontend/src/components/screens/HomeScreen.tsx:129-153` (`home-hero`)
Layer: A
Cost: 0

| # | Step | What must happen | Evidence hook |
|---|---|---|---|
| 1 | Load the app with no session storage and no guest token in local storage | The disclaimer modal is present and the rest of the page is `inert` | `data-testid="disclaimer-modal"`; the app root has the `inert` attribute while it is open |
| 2 | Read the modal without checking the box | The Continue button is disabled | role `button`, name `Continue`, `aria-disabled` or `disabled` true. Settle 300ms before reading the computed style or a screenshot: D11 measured this exact disabled-to-enabled transition read wrong twice this session |
| 3 | Check "I understand this is a research tool and does not provide medical advice." and click Continue | The modal closes and the home hero renders | `data-testid="home-hero"` visible, `disclaimer-modal` gone |
| 4 | Look at the hero's footer area | No guest allowance indicator is present | `guest-allowance` testid absent |

Fails if: the app is usable (any control outside the modal receives focus or a click) before the disclaimer is accepted, or the home hero shows a search-count claim before any run has happened.

Note: step 4 is not a defect. `allowance` starts `null` (`App.tsx:302`) and the footer only renders once `allowance?.kind === "guest"` (`App.tsx:1039`), so a visitor who has never minted a guest identity has nothing to show yet. This is the true first-visit case; a returning guest with a real, already-known allowance is a different case and is not handled the same way. See W-GUEST-4.

### W-GUEST-2: Asking the first question, from a chip and from typing

The product must: let an anonymous visitor ask a real question two ways, a seed chip or the free-text field, and mint a guest identity only at the moment a question is actually sent, never on page load.

Status: BUILT, `frontend/src/components/screens/HomeScreen.tsx:33-37` (`SEEDS`), `:183-184` (`aria-label="Your question"`), `:244-273` (chip buttons), `frontend/src/App.tsx:719-753` (lazy `mintGuest`)
Layer: A
Cost: 0

| # | Step | What must happen | Evidence hook |
|---|---|---|---|
| 1 | Click a seed chip, e.g. "Diseases linked to BRCA1" | The run starts immediately at the chip's own text, no typing needed | role `button`, accessible name is the chip's visible text (no testid exists on the chip; none was invented) |
| 2 | Reload to a clean guest, type a question into the field and submit | The same run screen appears | input role `textbox`, name `Your question`; submit role `button`, name `Search the knowledge graph` |
| 3 | In both cases, watch the network/state at the moment of submission | `POST /auth/guest` fires once, only now, never before this click | `App.tsx:722-731`'s comment: "minted lazily, on the FIRST question... never eagerly on page load" |
| 4 | Let the run land | The answer screen shows a real cited answer from the mock backend's event stream, not canned content | `answer-meta`, `sources-disclosure` |

Fails if: a guest identity is minted before any question is sent (an unauthenticated write on a visit that never asks anything), or the chip and the typed path produce different downstream behaviour for the same question text.

### W-GUEST-3: The allowance counting down across five answers

The product must: show the guest how many of their five answers remain, counted by the server after every run, never guessed on the client.

Status: BUILT, `src/system_03_search_agent/data/guest_sessions.py:60` (`FREE_RUN_ALLOWANCE: Final[int] = 5`), `frontend/src/components/guest/GuestAllowance.tsx:74-134`, `frontend/src/App.tsx:790-792` (`getAllowance` after `createRun`)
Layer: A
Cost: 0

| # | Step | What must happen | Evidence hook |
|---|---|---|---|
| 1 | Ask a first question as a guest and let it land | The footer shows five dots, one spent, caption "4 searches left" | `guest-allowance`; each dot carries `data-dot-state="spent"` or `"available"` (`GuestAllowance.tsx:115`) |
| 2 | Ask a second through fifth question, letting each land | The spent-dot count rises by exactly one per landed answer, caption counts down to "1 search left" then to none | same hook, read after each landing, settled |
| 3 | After the fifth answer lands | The caption no longer offers a count; the sixth ask meets the wall (W-GUEST-6) | `guest-allowance` still shows five spent dots on the answer screen that produced them, before the sixth ask is sent |

Fails if: the dot count ever runs ahead of or behind the server's own `used` value, or a dot reads as available after the server has already reported the run that spent it (`GuestAllowance.tsx:76-81`'s point: the dots are an affordance for "a search is available," not a mirror of a client counter).

### W-GUEST-4: A returning guest cannot see their own allowance

The product must: tell a returning guest, one whose browser already holds a guest token and a real, server-known allowance, how many searches they have left before they spend one, the same information a brand-new visitor cannot yet have but this visitor already does.

Status: NOT BUILT. `frontend/src/App.tsx:302` seeds `allowance` at `null` on every mount, and nothing re-populates it for a persisted token: the only two writers are `getAllowance` after a run lands (`App.tsx:790-792`) and after sign-in (`App.tsx:895-897`). `guestToken` itself IS restored from storage at mount (`App.tsx:278`, `loadPersistedGuestToken`), but no effect is keyed on it to fetch `GET /v1/allowance` for that restored identity.
Layer: A
Cost: 0

| # | Step | What must happen today | Evidence hook |
|---|---|---|---|
| 1 | As a guest, ask two questions and let both land, then reload the page in the same browser | The guest token survives the reload (`App.tsx:278`) and the allowance is real (three of five left) | localStorage key `agentic-search-ui.guest-token.v1` still present after reload |
| 2 | Look at the home hero footer immediately after reload, before asking anything | Today: no `guest-allowance` renders at all, even though the server already knows this identity has three answers left. This is the confirmed gap | `guest-allowance` testid absent on reload |
| 3 | Ask a third question | Only now does `getAllowance` run and the dots appear, already reading two spent of the pre-reload count plus this one | `guest-allowance` appears only after this run lands |

Fails if (once fixed): a returning guest with a live token asks their next question with no idea, until after they have spent it, whether they have one search left or four.

This is a distinct case from W-GUEST-1's step 4. `tracker/phase_4.10.md`'s F-4.10-A-13 is the brand-new-visitor question ("should the dots show before the first ask at all") and is recorded there as an open product-owner design question, not a bug. This finding is narrower and does not share that open status: it is not about whether a stranger who has never asked anything should see a promise of five, it is that a visitor whose real, already-spent allowance the server already knows is shown nothing at all, when the server has the number ready via `GET /v1/allowance`. Confirmed by reading `App.tsx` end to end for any effect that calls `getAllowance` keyed on `guestToken`: none exists.

### W-GUEST-5: The attempt ceiling is not the answer allowance

The product must: let a guest attempt up to ten questions even though only five ever produce an answer, so a clumsy or off-topic question never costs one of the five, while still stopping a caller who only ever triggers refusals before they can attempt an eleventh.

Status: BUILT, `src/system_03_search_agent/data/guest_sessions.py:60,90` (`FREE_RUN_ALLOWANCE = 5`, `ATTEMPT_ALLOWANCE = 10`), `:314-319` ("THE TWO COUNTERS ARE ASYMMETRIC"), `:400-417` (`_UNSPEND_STATEMENT` refunds `runs_used`, never `attempts_used`), `:447-499` (`refund_one_run`)
Layer: A
Cost: 0

| # | Step | What must happen | Evidence hook |
|---|---|---|---|
| 1 | As a fresh guest, ask an off-topic question the mock backend is scripted to classify `off_topic` | The run is refused, the guardrail banner shows, and the answer allowance is refunded: the dots still show zero spent | `guardrail-notice`, then `guest-allowance` reading `used: 0` |
| 2 | Repeat the same refused question nine more times (ten attempts total) | Every one refunds the answer count, so the dots never move, but the ATTEMPT count is climbing where nothing on screen shows it | `guest-allowance` stays at zero spent across all ten |
| 3 | Attempt an eleventh question of any kind | The server returns 403 `guest_attempt_limit_reached` and the wall appears, reason `attempt_limit`, even though the answer dots still read "5 searches left" the moment before this ask | `sign-in-wall` testid; `App.tsx:808-816` |

Fails if: a refused question ever decrements the visible allowance (contradicts the refund), or a caller can attempt more than ten times before meeting a wall, or the eleventh attempt is met with the wrong wall sentence (see W-GUEST-7).

Note: nothing in the interface shows the attempt count separately from the answer count. A guest who has been refused nine times sees "5 searches left" right up until the tenth refusal walls them with no warning. That silence is accurately described by the code (`GuestAllowance.tsx` only ever renders the answer allowance), not a testing gap; whether the product should surface the attempt count too is a product decision, not something this spec can settle.

### W-GUEST-6: The wall on an exhausted allowance

The product must: after a guest's fifth answer lands, refuse a sixth run with a sentence that is true for exactly this caller, someone who has been given five real answers.

Status: BUILT, `src/system_03_search_agent/adapters/web_sse/app.py:1157-1172` (403 `guest_allowance_exhausted`), `frontend/src/App.tsx:796-806`, `frontend/src/components/guest/GuestAllowance.tsx:171-173` (`WALL_COPY.allowance_exhausted`)
Layer: A
Cost: 0

| # | Step | What must happen | Evidence hook |
|---|---|---|---|
| 1 | As a guest, exhaust all five answers | The fifth answer lands normally | `answer-meta` on the fifth run |
| 2 | Ask a sixth question | The server returns 403 `guest_allowance_exhausted`; the wall renders with `reason="allowance_exhausted"` | `sign-in-wall` testid |
| 3 | Read the wall's sentence | "You have used your free searches. Sign in or create an account to keep going." | text content under `sign-in-wall`; `GuestAllowance.tsx:172-173` |

Fails if: this wall's sentence appears for a caller who has not actually received five answers (see W-GUEST-7 for why that distinction is load-bearing), or the sixth ask is silently retried instead of walled.

### W-GUEST-7: The wall on the attempt ceiling

The product must: refuse a guest who has attempted ten questions, whatever their outcome, with a sentence that does not claim they received five answers when they may have received none.

Status: BUILT, `src/system_03_search_agent/adapters/web_sse/app.py:1173-1191` (403 `guest_attempt_limit_reached`), `frontend/src/App.tsx:808-816`, `frontend/src/components/guest/GuestAllowance.tsx:174-175` (`WALL_COPY.attempt_limit`)
Layer: A
Cost: 0

| # | Step | What must happen | Evidence hook |
|---|---|---|---|
| 1 | As a fresh guest, trigger ten refused attempts (see W-GUEST-5) | Every one refunds the answer count, none refunds the attempt count | `guest-allowance` reads zero spent throughout |
| 2 | Attempt an eleventh question | 403 `guest_attempt_limit_reached`; wall renders with `reason="attempt_limit"` | `sign-in-wall` testid |
| 3 | Read the wall's sentence | "You have asked as many questions as a guest can. Sign in or create an account to keep going." It must NOT say "used your free searches" | text content under `sign-in-wall`; must differ from W-GUEST-6's sentence |

Fails if: this caller sees W-GUEST-6's sentence instead (false: they may have zero answers), or the attempt ceiling never fires and a caller can attempt indefinitely as long as every attempt is refused.

### W-GUEST-8: The wall on a migrated identity

The product must: once this browser's guest session has been converted into an account, never mint it a second free allowance, and tell it plainly that it needs to sign in rather than claiming a number of searches it cannot compute.

Status: BUILT, `frontend/src/App.tsx:605-626` (pre-flight check), `:817-838` (401 `guest_session_revoked` path), `frontend/src/lib/guestSession.ts:71-116` (`markGuestSessionMigrated`, `guestSessionWasMigrated`), `frontend/src/components/guest/GuestAllowance.tsx:176-177` (`WALL_COPY.migrated`)
Layer: A
Cost: 0

| # | Step | What must happen | Evidence hook |
|---|---|---|---|
| 1 | As a guest, ask one question, then sign up for an account in the same tab | The guest session is migrated and revoked server-side in the same request; this tab's guest token is dropped and `agentic-search-ui.guest-migrated.v1` is set | `App.tsx:875-897`; localStorage key present after signup |
| 2 | Sign out | Signing out does not clear the migrated marker | `App.tsx:1126` area comment: "the migrated marker are deliberately NOT cleared here" |
| 3 | As a signed-out visitor in this same browser, ask a question | The pre-flight check fires before any state is touched: no fresh guest is minted, the wall shows immediately with `reason="migrated"` | `sign-in-wall` testid; no `POST /auth/guest` call in this attempt |
| 4 | Read the wall's sentence | "This browser's guest session was moved into an account. Sign in to keep searching." It must not state a count of searches used, because none is known for this path | text content under `sign-in-wall` |
| 5 | Alternatively, reach the same wall from a stale token instead of the local marker: hold a guest token whose session was migrated from another tab, then ask | The server returns 401 `guest_session_revoked`; the client drops the token, sets the same marker, and shows the same wall | `App.tsx:825-838` |

Fails if: signing out and back in as a guest ever produces a fresh five-search allowance for a browser that already migrated one (this was a real, since-fixed hole, F-4.10-A-05), or the wall's sentence claims anything about how many searches this identity used.

### W-GUEST-9: What a guest can and cannot do

The product must: let a guest submit feedback on an answer and stop a run in progress, the same as a signed-in user, while never showing a guest their own search history rail, which exists only for an authenticated account.

Status: BUILT, `frontend/src/components/screens/AnswerScreen.tsx:109-123` (`FeedbackSurface` takes `authToken`, comment: "so a guest can submit feedback the same"), `frontend/src/App.tsx:918-927` (`onStop` uses `authToken`, which is `token ?? guestToken`, `App.tsx:501`), `frontend/src/App.tsx:525` (`railAvailable = signedIn && ...`)
Layer: A
Cost: 0

| # | Step | What must happen | Evidence hook |
|---|---|---|---|
| 1 | As a guest, let an answer land and submit thumbs up or down | The feedback posts using the guest bearer token and confirms | `feedback` testid, `feedback-status` testid, accessible names `Helpful` / `Not helpful` |
| 2 | As a guest, start a run and click Stop before it lands | The run aborts using the guest bearer token, same as a signed-in Stop | `run-elapsed` stops advancing; `stopRun` called with `authToken` (`App.tsx:927`) |
| 3 | As a guest, at any point in the search screen, look for the searches rail or its toggle | Neither exists. `railAvailable` is `false` whenever `signedIn` is `false` | `history-rail`, `collapsed-rail`, and the toggle named `Show or hide your searches` are all absent for a guest |
| 4 | Sign in mid-session from a guest state | The rail becomes available only now, seeded from `GET /v1/history`, which build phase 4.13 scoped to the signed-in principal | `history-rail` appears only after `signedIn` becomes true |

Fails if: a guest's feedback or stop silently no-ops instead of using their token, or any rail element is reachable (even empty) while `signedIn` is false.

### W-GUEST-10: Guest to account migration, and the five-minute window that empties it

The product must: when a guest signs up or logs in, move whatever of their guest activity the server still holds into the new account, and say nothing the interface cannot make true, since most of that activity is already gone by the time migration runs.

Status: BUILT for the transaction itself, and DELIBERATELY LIMITED by design: `src/system_03_search_agent/core/run_registry.py:183` (`DEFAULT_RETENTION_SECONDS = 300.0`), `:703-724` (`_evict_expired` drops any run finished more than 300 seconds ago). The wall's copy in `GuestAllowance.tsx:214-247` documents, at length, why no sentence here promises history moving with the account: the promise was tried twice and withdrawn both times as false for the one situation the wall is shown in.
Layer: A
Cost: 0 (see note on the five-minute case below)

| # | Step | What must happen | Evidence hook |
|---|---|---|---|
| 1 | As a guest, ask a question, let it land, and sign up for an account within the same few seconds | The run the `RunRegistry` still holds is reassigned to the new account's owner id | server-side: `reassign_owner` moves the run; no client-visible testid, since nothing in the UI renders a migrated run at all (`GuestAllowance.tsx:231-236`: "Nothing in the UI shows a migrated run") |
| 2 | Same as step 1, but wait more than five minutes (300 seconds) after the run lands before signing up | `_evict_expired` has already dropped the run from the in-memory registry; migration moves nothing, and reading that run under the new account returns 404 | none, needs one. A Playwright test would need either to wait 300+ seconds in real time or the running server to accept an injected shorter retention window, and neither exists today: `default_registry = RunRegistry()` (`app.py:57`, module import) is constructed with the hardcoded default and has no environment override. The comment at `GuestAllowance.tsx:224-229` cites this exact behaviour "measured with retention forced to zero," which was done by constructing a `RunRegistry` directly in a unit test, not by driving the live server |
| 3 | In either case, look at the sign-in wall or any other screen for a claim about history moving | No sentence anywhere claims this. The wall's only claim is that the identity was moved and the visitor should sign in | text content under `sign-in-wall`, reason `migrated` (W-GUEST-8) |
| 4 | Sign in as the new account and look at the history rail | The rail is now available (W-GUEST-9), but it reads from `GET /v1/history`, which is a durable table separate from the in-memory `RunRegistry`; whether the pre-signup question appears there depends on build phase 4.6's `interactions` capture, not on this migration path | `history-rail` |

Fails if: any UI text promises that history or past searches "move with you" on sign-in, since that promise was tested and found false for the one moment it would be shown (`GuestAllowance.tsx:216-247`'s full account), or if the five-minute figure ever changes in `run_registry.py` without this workflow's numbers being revisited.

### W-GUEST-11: The shared daily ceilings, which are not the guest's own allowance

The product must: distinguish, in both the machine-readable reason and the sentence a person reads, a refusal caused by this guest's own five-search allowance from a refusal caused by every anonymous caller, or one network's share of them, having used up a shared daily budget that resets at UTC midnight and that signing in bypasses entirely.

Status: BUILT, `src/system_03_search_agent/adapters/web_sse/app.py:1112-1156` (429 `anon_source_daily_cap_reached` and 429 `anon_daily_cap_reached`, both carrying `Retry-After`), `frontend/src/components/guest/GuestAllowance.tsx:31-52` (`AllowanceBlockedReason`, `BLOCKED_COPY`)
Layer: A
Cost: 0

| # | Step | What must happen | Evidence hook |
|---|---|---|---|
| 1 | With `ANON_DAILY_RUN_CAP` set low for the test environment, exhaust the system-wide anonymous budget for the day with any mix of guest identities | The next anonymous ask anywhere returns 429 `anon_daily_cap_reached` with a `Retry-After` header equal to seconds until UTC midnight | none, needs one at the UI layer. The reason is asserted in `phase410Premise.test.tsx:256` against `GuestAllowance`'s copy directly; no E2E test drives the real 429 through `createRun` today |
| 2 | Read the error surfaced to the guest who was refused | Today this does NOT reach the wall (only 403 reasons do, `App.tsx:796-816`) and does not populate `GuestAllowance`'s `blockedReason` from this path either, since that field is only ever set from `GET /v1/allowance`'s own `blocked_reason`, not from a `createRun` failure. The visible result is the generic dispatch error path: `answer-failure` with the raw `ApiError` message ("createRun failed with 429: anonymous searches are at their daily limit...") | `answer-failure` testid; `dispatchError` set at `App.tsx:847-852` |
| 3 | Separately, call `GET /v1/allowance` for an identity whose network share is capped | The response's `blocked_reason` is `anon_source_daily_cap_reached`, and the home footer's dots all render spent with the caption "This network has used its guest searches for today" | `guest-allowance`, caption text matching `BLOCKED_COPY.anon_source_daily_cap_reached` |
| 4 | Compare the two daily reasons | `anon_daily_cap_reached` says "Guest searches are paused for today" (everyone), `anon_source_daily_cap_reached` says "This network has used its guest searches for today" (this address's share). Neither may say "no guest searches left", which is `guest_attempt_limit_reached`'s sentence and a different, permanent condition | `BLOCKED_COPY` (`GuestAllowance.tsx:48-52`) |

Fails if: a shared daily refusal is ever shown as if it were this guest's own allowance being spent (the two are keyed on entirely different tables, `guest_sessions` versus `guest_daily_usage` and `guest_source_daily_usage`), or the two daily reasons are collapsed into one sentence.

## Notes on the two things I was asked to check

D3, the invisible allowance after reload, is TRUE, and it is narrower and more concrete than the open product question already on record. `tracker/phase_4.10.md`'s F-4.10-A-13 is about whether a first-time visitor should see the dots before ever asking anything, an unresolved design question. What I confirmed by reading `App.tsx` end to end is a distinct case: a RETURNING guest whose token survives reload (`App.tsx:278`) and whose allowance the server already knows precisely, has no effect anywhere that fetches it. The only two call sites for `getAllowance` are after a run lands (`:790-792`) and after sign-in (`:895-897`); nothing is keyed on `guestToken` at mount. That guest asks their next question with the same lack of information as someone who has never asked anything at all, despite the server already holding the real number. I wrote this as its own workflow, W-GUEST-4, separate from W-GUEST-1's step 4, so the two are not conflated: one is "nothing exists yet" and the other is "something exists and is not shown."

The wall copy's dropped promise: I read the full comment in `GuestAllowance.tsx:214-247` before writing W-GUEST-8 and W-GUEST-10. It documents that the promise "your history moves with you" was tried once, narrowed once, and then removed rather than narrowed a third time, for two independent reasons: the five-minute `RunRegistry` retention makes it false in the one situation the wall is shown in (the sixth search, meaning every retained run is already close to that window or past it by the time a visitor bothers to sign up), and nothing in the UI renders a migrated run even when the server-side move succeeds. My migration workflow (W-GUEST-10) states only what the wall actually says, and step 3 explicitly checks that no screen claims history moves with the account.

## What I found that the shared brief did not mention

The attempt ceiling (W-GUEST-5) has no visible counter anywhere in the UI. A guest can be refused nine times with the answer dots reading "5 searches left" the entire time, then be walled on the tenth with no warning shot. This is consistent with the code as read (`GuestAllowance.tsx` renders only the answer allowance) rather than a defect I am asserting, but it is a real gap in what the interface tells a guest, and it was not named in the shared brief's feature facts.

The shared daily ceilings (W-GUEST-11) do not reach the sign-in wall at all, only the guest's own two per-identity states do (`App.tsx:796-816` checks exactly `guest_allowance_exhausted` and `guest_attempt_limit_reached`). A guest refused by the system-wide or per-network daily cap sees the generic `answer-failure` path with a raw, unstyled error string rather than `GuestAllowance`'s own honest, purpose-written sentences for those exact reasons. The copy exists and is tested against the component directly (`phase410Premise.test.tsx:256-258`), but nothing wires it into the live refusal path from `createRun`, only into `GET /v1/allowance`'s independent read. That is a real product gap: the words were written for this moment and are not shown at this moment.

## Checklist items covered

D3 (guest's own item, verified true and given its own workflow, W-GUEST-4). No other checklist row names the guest area as its owner in `coverage_checklist.md`; every other row I could find (D2 thread-not-cleared, D4 rail-versus-toggle, D7 sign-in styling) is owned by identity or controls, and I have not written workflows for those to avoid double-covering another worker's file.
