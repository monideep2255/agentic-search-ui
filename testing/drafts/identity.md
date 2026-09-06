# Identity workflows

An account exists to give a searcher two things a guest identity cannot: a search allowance that is not on a five-minute clock, and a thread of past questions that follows them rather than dying with the browser tab. Nothing about the account is a second product. It re-seeds the one preference the product remembers (audience depth), it replaces the guest allowance with the server's own daily cap, and it is the only identity the history rail will render for. Everything below is the mechanism that makes that true, and one place where the code does not yet keep the promise its own comment makes.

## W-identity-1: Signing up through the sign-in screen

The product must: a visitor with no account can create one from the same screen a returning user logs in on, and land on the home screen able to ask a question immediately.

Status: BUILT, `frontend/src/components/auth/AuthGate.tsx:60-301` (the whole component), wired at `frontend/src/App.tsx:868-898`.
Layer: A
Cost: 0

| # | Step | What must happen | Evidence hook |
|---|---|---|---|
| 1 | Open the app, click "Log in" in the nav | The sign-in screen renders | `data-testid="auth-gate"` (`AuthGate.tsx:185`) |
| 2 | Fill the email field | Value updates, button stays disabled until password is also filled | Accessible name `Email` |
| 3 | Fill the password field | Value updates | Accessible name `Password` |
| 4 | Click "Sign up" | A signup request fires, then a login request against the same credentials, then the screen leaves the sign-in view | Role `button`, name `Sign up`; `AuthGate.tsx:81-89` |
| 5 | Land back in the app | The home screen shows the question input, ready to ask | Accessible name `Your question` (per shared brief); pattern proven working at `frontend/e2e/second-turn.spec.ts:35-47` |

Fails if: the sign-up button is disabled with both fields filled, or the app does not reach a screen with a visible question input within a few seconds of a successful sign-up.

Caution for anyone extending this workflow: do not assert that a guest's prior searches or thread carry into the new account. Migration only moves runs the in-memory registry still holds, `DEFAULT_RETENTION_SECONDS` is 300 seconds, so a guest session more than five minutes old has nothing left to migrate. A workflow that signs up immediately after a guest ask and expects continuity is testing a promise the product does not make past five minutes, and one that waits past five minutes and expects continuity is testing a promise the product never made at all.

## W-identity-2: Signing in with an existing account

The product must: a returning user with a correct email and password reaches the app; a wrong password or an unknown email produces the same visible failure, so the screen never discloses which case occurred.

Status: BUILT, `AuthGate.tsx:68-117`.
Layer: A
Cost: 0

| # | Step | What must happen | Evidence hook |
|---|---|---|---|
| 1 | Fill Email and Password with a real account's credentials, click "Log in" | The app leaves the sign-in screen | Role `button`, name `Log in`; `AuthGate.tsx:260-267` |
| 2 | Fill Email and Password with a wrong password (or an email that was never registered), click "Log in" | A single fixed sentence appears: "Could not log in with that email and password." Nothing distinguishes the two cases | `role="alert"` (`AuthGate.tsx:243-247`) |
| 3 | Press Enter with both fields filled instead of clicking | The form submits the same way clicking "Log in" does | `AuthGate.tsx:121-129`, a real `<form onSubmit>` |

Fails if: a wrong-password attempt and an unknown-email attempt produce visibly different messages, statuses, or timing that would let a visitor enumerate registered emails. `AuthGate.tsx:42-58`'s own docstring names this as the reason two explicit buttons exist rather than a try-login-then-fallback flow; a workflow here is what keeps that reasoning honest.

## W-identity-3: What changes the moment you are signed in

The product must: signing in swaps the nav's "Log in" button for a named account control, reveals the rail toggle, drops the guest allowance display, and re-seeds audience depth from the account rather than leaving it at the session default.

Status: BUILT. Account menu replaces Log in: `frontend/src/components/shell/AppShell.tsx:225-253`. Rail toggle: `railAvailable = signedIn && screen === "search" && searchView.name !== "signin"` (`App.tsx:525`), passed to `showRailToggle` (`App.tsx:1093`). Guest allowance disappears: the footer is only rendered `!signedIn && allowance?.kind === "guest"` (`App.tsx:1039`). Depth re-seed: the `fetchMe` effect keyed on `token` (`App.tsx:437-452`).
Layer: A
Cost: 0

| # | Step | What must happen | Evidence hook |
|---|---|---|---|
| 1 | Before signing in, note the nav shows "Log in" and (if any guest runs happened) a guest allowance readout under the question box | Baseline captured | Role `button`, name `Log in`; `data-testid="guest-allowance"` |
| 2 | Sign in | "Log in" is replaced by a pill naming the account | `AccountMenu.tsx:54-152`, the pill shows the account's email |
| 3 | Look at the guest allowance readout | It is gone, not zeroed, gone | Absence of `guest-allowance` testid |
| 4 | Look at the app bar's far left | A rail toggle icon button is now present | Accessible name `Show or hide your searches` |
| 5 | If the account previously chose a non-default depth and this is a fresh page load signing into it, the depth control | Reflects the account's stored `audience_depth`, not the session default of "researcher" | Accessible name `Audience-level depth` group; `App.tsx:437-452` |

Fails if: "Log in" and the account pill are both visible at once, or the guest allowance readout still renders after sign-in, or the depth control still reads the session default after `GET /auth/me` has resolved for an account with a stored non-default depth.

## W-identity-4: Opening the history rail

The product must: a signed-in user can open a rail listing their past questions, each one a button; an account with no history yet sees an honest empty message rather than a blank panel.

Status: BUILT, `frontend/src/components/answer/FollowUp.tsx:373-609` (`HistoryRail`), rendered at `App.tsx:1172-1204`. History is fetched at sign-in and merged with this tab's own live activity: `App.tsx:481-490`.
Layer: A
Cost: 0

| # | Step | What must happen | Evidence hook |
|---|---|---|---|
| 1 | Sign in, click the rail toggle | The rail opens at the left of the search screen | `data-testid="history-rail"` |
| 2 | With no history yet | The rail shows "Your searches appear here, with their sources attached." rather than an empty panel | `FollowUp.tsx:479-499` |
| 3 | Ask a question and let it land | A row for that question appears at the top of the rail | `FollowUp.tsx:501-577`, row text is `item.question` |
| 4 | Look at each row | It shows the question (clamped to two lines) and, once the run has landed, a short meta line (source count and date, or this session's own counts) | `FollowUp.tsx:530-575` |

Fails if: the rail renders nothing at all (not even the empty-state sentence) for a signed-in user with zero history, or a landed run never produces a row.

## W-identity-5: Clicking a history row re-runs the query, it does not replay a stored answer

The product must: history stores questions only. Opening a past row asks the agent that question again, live, rather than showing a cached answer. This is the single fact a user is most likely to get wrong about the rail, so it is stated as its own workflow rather than folded into "opening the rail."

Status: BUILT (as a re-ask, not as a replay), confirmed by reading the data shape and the click handler, not assumed. `HistoryEntry`'s type is `{ id: string; question: string; meta?: string; traceId?: string }` (`App.tsx:135`), no field on it ever holds an answer, a claim, or a source. Clicking a row calls `onOpen`, which finds the row by id and calls `ask(item.question, depth)` (`App.tsx:1188-1191`), the exact same function a fresh question from the home screen calls.
Layer: A
Cost: 0

| # | Step | What must happen | Evidence hook |
|---|---|---|---|
| 1 | Ask a question, let it land on the answer screen | A row appears in the rail | `history-rail` testid, row text matches the question |
| 2 | Note the elapsed time or step announcements the first run showed | Baseline: this run took some real (mocked) latency to land | `data-testid="run-elapsed"`, `data-testid="run-step-announcement"` |
| 3 | Navigate away (ask a different question, or open a different row), then click the original row again | The screen moves to the run view, not straight to the answer view, and the guardrail-through-write step sequence runs again in full | `data-testid="step-{Guard\|Think\|Plan\|Act\|Write}"` with `data-state`, observable transitioning again |
| 4 | Compare the two landings | The second landing is a fresh run: it gets its own `runId`, its own tool calls, its own timing, not a frozen copy of the first answer's DOM | `data-testid="tool-{name}"`, `data-layer`, present again on the second run |

Fails if: clicking a row jumps directly to a fully rendered answer with no run screen in between, or the answer content is byte-identical to a cached value the client never re-requested. Either would mean the row read from stored answer content, which the data model does not carry and this workflow exists to keep true.

## W-identity-6: Collapsing and restoring the rail

The product must: the rail can be collapsed to a narrow strip that still shows how many searches it is holding, and restored to the full rail from that strip, without reflowing the rest of the page.

Status: BUILT, `frontend/src/components/answer/FollowUp.tsx:295-358` (`CollapsedRail`), wired at `App.tsx:1172-1174`.
Layer: A
Cost: 0

| # | Step | What must happen | Evidence hook |
|---|---|---|---|
| 1 | With the rail open and at least one history row, click the collapse control | The rail becomes a narrow strip; the vertical label "Your searches" and a count badge are visible | Accessible name `Hide your searches`; `data-testid="collapsed-rail"` |
| 2 | Check the count badge | It matches the number of rows the open rail had | `CollapsedRail`'s `count` prop is `history.length` (`App.tsx:1173`) |
| 3 | Click the collapsed strip | The full rail reopens with the same rows | Accessible name `Show your searches`; `data-testid="history-rail"` reappears |

Fails if: the count badge is absent or wrong, or collapsing and restoring loses a row that was present before.

## W-identity-7: The rail footer names the account

The product must: the bottom of the open rail states which account these searches belong to, so a shared workstation makes ownership visible rather than implicit.

Status: BUILT, `FollowUp.tsx:585-608`.
Layer: A
Cost: 0

| # | Step | What must happen | Evidence hook |
|---|---|---|---|
| 1 | Sign in and open the rail | The footer shows the signed-in account's email | `history-rail` testid, footer text matches the email used to sign in |
| 2 | Check the line beneath the email | It states the account's real search standing (never a hardcoded number, per `AccountMenu.tsx:188-197`'s sibling logic; the rail's footer is built by the same `dailyLimitPhrase` function so the two surfaces cannot disagree) | Second line of `.rfoot`, `FollowUp.tsx:601-606` |

Fails if: the footer is absent while signed in with a known email, or it shows a placeholder instead of the real account.

## W-identity-8: The account menu's own items

The product must: the account control is a menu, not a single sign-out button, and it links to the two other identity-adjacent screens before it offers to sign out.

Status: BUILT, `frontend/src/components/shell/AccountMenu.tsx:97-255`.
Layer: A
Cost: 0

| # | Step | What must happen | Evidence hook |
|---|---|---|---|
| 1 | Sign in, click the account pill | A menu opens naming the account and its search standing | `role="menu"`; `AccountMenu.tsx:154-199` |
| 2 | Click "API key and integrations" | The menu closes and the app navigates to the Integrations screen | `role="menuitem"`, name `API key and integrations`; `AccountMenu.tsx:215-226` |
| 3 | Reopen the menu, click "Documentation" | The menu closes and the app navigates to the Docs screen | `role="menuitem"`, name `Documentation`; `AccountMenu.tsx:227-238` |
| 4 | Reopen the menu, click "Log out" | The account is signed out immediately, with no confirmation step | `role="menuitem"`, name `Log out`; `AccountMenu.tsx:239-250` |
| 5 | With the menu open, click outside it or press Escape | The menu closes without navigating anywhere | `AccountMenu.tsx:66-80` |

Fails if: "Log out" is reachable but "API key and integrations" or "Documentation" do not navigate, or the menu fails to close on an outside click or Escape.

## W-identity-9: Signing out, what is cleared and what deliberately survives

The product must: signing out returns the app to a clean, anonymous-feeling state for the next person, while leaving in place the one thing that is scoped to the browser rather than the account, the guest identity and its migrated-marker.

Status: PARTLY BUILT, and this is D2, a real defect confirmed by reading the handler rather than assumed. The sign-out handler at `App.tsx:1100-1151` clears the token, account email, run id, stop flag, history, flagged sources, dispatch error, allowance, session id, disclaimer acceptance, depth (reset to "researcher"), and rail-open state. It deliberately does NOT clear `guestToken` or the migrated marker, and says so in its own comment (`App.tsx:1125-1138`). It also does not call `setThread([])`, and this is the gap: `thread`'s own declaration at `App.tsx:262-264` states "Cleared by 'New search' and by signing out, never trimmed," but `setThread([])` only appears in the three New-search handlers (`App.tsx:934`, `:1001`, `:1198`). The sign-out handler's own comment two lines above claims "everything session-scoped is cleared here, in one place," which is false for `thread`.
Layer: A
Cost: 0

| # | Step | What must happen | Evidence hook |
|---|---|---|---|
| 1 | Sign in as account A, ask a question, then ask a follow-up so a turn is archived into `thread` | The answer screen shows a previous-turn card for the first question | `data-testid="previous-turn-{i}"` |
| 2 | Sign out (Log out from the account menu) | The app returns to the home screen, "Log in" visible in the nav | Role `button`, name `Log in` |
| 3 | Sign in as a different account B in the same tab, ask a new question, let it land on the answer screen | Account B's answer screen shows ONLY this new turn, no card from account A's earlier question | `previous-turn-{i}` testids present should number only B's own follow-ups |
| 4 | If step 3 shows a `previous-turn` card from account A's question | This is the reproduction of D2 | Confirms `thread` survived sign-out |

Fails if: step 3 shows any previous-turn content that belongs to account A. That is the observable form of D2: one person's collapsed conversation reappearing for the next person at the same browser, without a reload even being involved.

What this workflow deliberately does not check: that the guest token or its migrated marker gets cleared. They should NOT clear on sign-out, per `App.tsx:1125-1138`'s documented decision, so a workflow asserting they are wiped would be asserting the wrong behaviour.

## W-identity-10: A reload signs you out

The product must: the access token exists only in memory, so refreshing the page always returns to the signed-out state, with no silent partial recovery of the account's identity.

Status: BUILT (as a known, accepted limitation, not a bug). `token` is `useState<string | null>(null)` with no persistence (`App.tsx:303`), unlike `guestToken`, which is explicitly seeded from `localStorage` on mount (`App.tsx:278`, `:270-277`).
Layer: A
Cost: 0

| # | Step | What must happen | Evidence hook |
|---|---|---|---|
| 1 | Sign in, confirm the account pill is visible | Signed-in state established | `AccountMenu` pill visible |
| 2 | Reload the page | The app returns to the signed-out state: "Log in" in the nav, no rail toggle, no account pill | Role `button`, name `Log in`; absence of `showRailToggle` effect |
| 3 | If a guest token had been minted in this tab before signing in | It survives the reload (a separate, deliberate persistence path, not this workflow's subject) | `lib/guestSession.ts`'s persisted-token read |

Fails if: the account pill, the rail toggle, or any account-scoped content survives a reload without a fresh sign-in. This is documented as accepted, not silently broken, so a workflow finding the opposite (identity surviving a reload) would itself be the surprise worth flagging.

## Coverage notes

Checklist items covered: D2 (workflow W-identity-9, confirmed as a real defect), D4 (workflow W-identity-11 below, confirmed as a real defect), D7 (folded into W-identity-1's status line: `AuthGate.tsx` now imports `Box, Button, Stack, TextField, Typography` from `@mui/material`, so the "only screen component importing no MUI" premise is gone and D7 is FIXED).

## W-identity-11: The rail toggle does nothing below the `md` breakpoint

The product must: a control that is visible must do something observable when pressed, on every screen size it is visible at.

Status: PARTLY BUILT, and this is D4, confirmed by reading both sides of the gap. The toggle button in the app bar (`AppShell.tsx:152-167`) carries no breakpoint guard at all, so `showRailToggle && signedIn` renders it identically at every viewport width, including below `sm`. `frontend/src/components/shell/AppShell.tsx` was rebuilt hours before this brief was written to fix the app bar's own two-row wrap at 390px (see its `flexWrap: { xs: "wrap", sm: "nowrap" }` at lines 137-144), so the toggle's visibility at narrow widths is current behaviour, not stale. What it toggles is hidden: both the open rail (`display: { xs: "none", md: "flex" }`, `FollowUp.tsx:397`) and the collapsed strip (`display: { xs: "none", md: "flex" }`, `FollowUp.tsx:315`) disappear below `md`. A signed-in user on a phone-width viewport (below `md`, roughly 900px in MUI's default breakpoints, a wider cutoff than the `sm` breakpoint the app bar itself reflows at) can press a visible, enabled button and see nothing change.
Layer: A
Cost: 0

| # | Step | What must happen | Evidence hook |
|---|---|---|---|
| 1 | Sign in, resize the viewport below `md` (under roughly 900px wide, which includes ordinary phone widths) | The rail toggle icon button is still visible in the app bar | Accessible name `Show or hide your searches` |
| 2 | Click it | Nothing observable happens: no rail, no collapsed strip, no visible state change anywhere on screen | Absence of both `history-rail` and `collapsed-rail` testids at this width, before and after the click |
| 3 | Click it again (to rule out a toggle that only fails to render, versus one that is not receiving the click at all) | `aria-expanded` on the button does flip (the state itself does change), confirming the defect is the rail's own responsive hiding, not a broken handler | `aria-expanded` attribute on the toggle button |

Fails if: step 2 does not reproduce, meaning either breakpoint has since been reconciled. As currently built, this workflow's expected outcome is the defect itself: a click with a state change and zero visible effect. Anyone re-running this after a fix should expect step 2 to instead show a rail or strip, and should update the Status line to FIXED with the new citation.
