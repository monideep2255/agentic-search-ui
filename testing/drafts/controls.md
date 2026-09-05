# Controls, chrome and the three depths

These are the parts of the product that shape HOW an answer is delivered rather than what it
retrieves: the audience-depth switch a reader sets before asking, the stop and feedback controls
around a run, the chrome that holds every screen together (the app bar, the disclaimer, client-side
routing), and the informational surfaces (integrations, docs, about) that describe the product
rather than answering a question. None of these change what gets retrieved or what gets cited. Two
of them, depth and the stop button, can change what a reader sees of an answer that already exists,
and one depth in particular has a documented history of quietly dropping findings while looking
complete. The rest exist so the product is usable, honest about its limits, and does not silently
break on a phone.

Any step below that asserts on a computed style or a screenshot settles first (waits past MUI's
roughly 250ms transition) and says so in its own text, per D11: a screenshot and a DOM probe both
misread an enabled primary button as disabled grey this session, mid-transition, and a false defect
was one step from being filed against correct work.

## The three depth workflows

Depth reaches synthesis at exactly one line, `core/graph.py:5634`, inside `build_synth_messages`,
and it changes register and length only, never which tool ran or what was retrieved. The three
directives are `synthesis/findings.py:751-770`. A structural completeness repair sits behind all
three (`core/graph.py:5723-5789`): if the first Write call's grounded claims omit any finding Act
retrieved, a second bounded Write call runs with the omitted findings named explicitly
(`build_completeness_directive`), and the repair is kept only if it is a strict superset of what the
first call reported. This exists because two successive prompt-only fixes to the `clinical_brief`
directive did not hold (`synthesis/findings.py:715-747`), so completeness is now a code-level check
on the output, not a wording request.

### W-CTRL-01: a reader selects clinical_brief and reads a short, complete answer

The product must: at `clinical_brief` depth, the answer covers every finding Act retrieved, in
plain clinical language and short complete sentences, and never diagnoses, classifies a variant, or
recommends treatment.

Status: BUILT, `synthesis/findings.py:751-758` (the directive), `core/graph.py:5726-5789` (the
completeness repair that makes coverage a checked property rather than a prompt request).
Layer: C (a person must judge register, completion of sentences, and absence of diagnostic language)
composed with B (a real model call is needed to produce the answer at all).
Cost: 1 real answer per run of this workflow.

| # | Step | What must happen | Evidence hook |
|---|---|---|---|
| 1 | Sign in or continue as guest, select "Clinical brief" on the home screen | The depth control's `Clinical brief` button becomes pressed | role group "Audience-level depth", role button "Clinical brief" with `aria-pressed="true"` |
| 2 | Ask a question with a known multi-finding answer (for example, a gene-disease question the golden dataset already pins to more than one disease) | The run completes to the answer screen | `data-testid="answer-meta"` present, `searchView.name === "answer"` |
| 3 | Read the answer text | Every sentence is short, uses plain clinical wording, and answers the question directly. No sentence classifies a variant, names a diagnosis for the reader, or recommends a treatment | answer body text (no dedicated testid; read the rendered claim text nodes, `claim-text-{i}`) |
| 4 | Count the findings named in the answer against the run's own source list | The number of distinct findings reported equals the number of findings the sources list shows for the run at `researcher` depth on the same question, not fewer | `data-testid="sources-count"`, compared against a `researcher`-depth run of the identical question (W-CTRL-02) |
| 5 | Check for a completeness note | If the repair still could not report everything (a cap hit during the repair, `core/graph.py:5748-5752`), the answer discloses the gap rather than silently presenting as complete | `data-testid="answer-note-{i}"` |

Fails if: the answer at this depth reports fewer distinct findings than the same question reports
at `researcher` depth, with nothing in the answer or its notes saying a finding was left out. This
is the F-4.5-06 breach 2 shape: every claim present is correctly grounded and cited, and the
omission is invisible to any check that only reasons about the claims that ARE there. A test that
only checks tone and sentence length passes this exact defect.

### W-CTRL-02: a reader selects researcher (the default) and reads full mechanistic detail

The product must: at `researcher` depth, the default a reader gets with no action, the answer uses
standard biomedical vocabulary and gives full mechanistic detail on every finding retrieved.

Status: BUILT, `synthesis/findings.py:759-762`; default confirmed in code at
`frontend/src/App.tsx:318` (`useState<AudienceDepth>("researcher")`) and
`synthesis/findings.py:776` (`DEFAULT_AUDIENCE_DEPTH = "researcher"`).
Layer: C composed with B.
Cost: 1 real answer.

| # | Step | What must happen | Evidence hook |
|---|---|---|---|
| 1 | Land on the home screen with no account and ask a question without touching the depth control | The run dispatches at `researcher` depth with no user action needed | depth group shows "Researcher" pressed by default: role button "Researcher" `aria-pressed="true"` |
| 2 | Read the answer | Standard biomedical vocabulary is used throughout, and each finding gets a full mechanistic explanation, not a one-line label | claim text nodes, `claim-text-{i}` |
| 3 | Compare against the same question at `clinical_brief` depth | The set of findings reported is the same; only the depth and length of explanation per finding differs | `sources-count` at both depths |

Fails if: the default run (no depth chosen) does not match what a reader gets from explicitly
pressing "Researcher", which would mean the two paths through `App.tsx`'s depth state have drifted.

### W-CTRL-03: a reader selects deep_technical and reads raw identifiers inline

The product must: at `deep_technical` depth, the answer states raw CURIEs inline in the prose
(for example `NCBIGene:672` or `MedGen:C0346153`), along with assembly or version context and full
parameter and coordinate detail the findings actually contain, and never invents an identifier the
findings do not contain.

Status: BUILT, `synthesis/findings.py:763-770`.
Layer: C composed with B.
Cost: 1 real answer.

| # | Step | What must happen | Evidence hook |
|---|---|---|---|
| 1 | Select "Deep technical" and ask a disease-anchored question | The depth control shows "Deep technical" pressed | role button "Deep technical" `aria-pressed="true"` |
| 2 | Read the answer | Raw identifiers (CURIEs) appear directly in the sentences, not only in the citation list | claim text nodes, `claim-text-{i}`; cross-check each inline identifier against `citation-{n}` / `source-{n}` |
| 3 | Cross-check every identifier that appears in the prose | Every identifier named in the prose also appears as a finding's own identifier in the run's sources. None is invented | `source-{n}` entries |
| 4 | Compare against the same question at `researcher` depth | Seeing `MedGen:C0346153` or a similar CURIE in the prose HERE is correct, not a regression. Build phase 6.2 made `researcher` and `clinical_brief` name diseases in words; `deep_technical` is the one depth whose directive requires the raw identifier | n/a, a judgement step |

Fails if: a raw identifier appears in the prose that does not match any finding's own identifier
(an invented CURIE), or if a reviewer flags a visible CURIE at THIS depth as a defect. The latter is
not a failure of the product; it is a failure of the test, and this workflow exists specifically to
stop that miscall from recurring. Build phase 6.2 shipped precisely because `researcher` and
`clinical_brief` answers used to read `MedGen:C0346153` where a disease name belonged; `deep_technical`
was never part of that complaint and its directive still requires the identifier.

## The audience-depth control itself

### W-CTRL-04: the depth control is home-screen-only and seeded from the account

The product must: offer exactly three depth options, default to researcher, appear only on the home
screen, and for a signed-in reader, start from the depth stored on their account rather than always
resetting to the default.

Status: BUILT. Three options and default: `frontend/src/components/controls/DepthControl.tsx:23-29`.
Home-screen-only: the only render call site is `frontend/src/components/screens/HomeScreen.tsx:231`;
grep confirms `<DepthControl` appears nowhere else under `frontend/src/components/`.
Account seeding: `frontend/src/App.tsx:437-452`, a `fetchMe` effect keyed on the auth token that
calls `setDepth(me.audience_depth)` once the account's stored preference resolves, best-effort (a
failed fetch leaves the control at whatever it already shows).
Layer: A.
Cost: 0.

| # | Step | What must happen | Evidence hook |
|---|---|---|---|
| 1 | Load the app signed out | The depth group shows exactly three options, Researcher pressed | role group "Audience-level depth"; role buttons "Clinical brief", "Researcher", "Deep technical" |
| 2 | Navigate to the run or answer screen | No depth control is present on either screen | absence of role group "Audience-level depth" outside the home screen |
| 3 | Sign in to an account whose stored `audience_depth` is `deep_technical` | The home screen's depth control switches to "Deep technical" pressed shortly after sign-in, with no action from the reader | role button "Deep technical" `aria-pressed="true"`, polled after the `GET /auth/me` response |
| 4 | Sign out | The depth control resets to "Researcher" (`frontend/src/App.tsx`, the sign-out handler's `setDepth("researcher")`) | role button "Researcher" `aria-pressed="true"` |

Fails if: the depth control renders on any screen besides home, or a signed-in reader with a
non-default stored preference sees "Researcher" pressed on load instead of their own setting.

### W-CTRL-05: depth is not locked once a run starts

The product must: per the component's own stated intent, lock the depth control while a run is in
flight, since the depth a run dispatched with should not change mid-stream. Today it does not.

Status: NOT BUILT. `DepthControl.tsx:34` documents the `locked` prop and its rationale ("The
disabled state is the part that matters and is easy to skip... A user who changes depth mid-answer
would otherwise get a paragraph in one register followed by a paragraph in another"), but the prop
is never set true by any caller; the control is not even rendered on the run screen (W-CTRL-04,
step 2), so there is currently nothing to lock. This is moot rather than broken today because the
control that would need locking is absent from the screen where locking would matter, but it means
the documented safeguard has no caller anywhere in the codebase.
Layer: A.
Cost: 0.

| # | Step | What must happen | Evidence hook |
|---|---|---|---|
| 1 | Grep every call site of `<DepthControl` for a `locked` prop | No caller passes `locked` | `grep -rn "DepthControl" frontend/src --include="*.tsx"` |

Fails if: this is ever wrong in the other direction, that is, a future caller renders the depth
control mid-run without ever passing `locked`, which would let a reader change depth while a run is
streaming with nothing to stop them.

## Stop, and what stopping actually does

### W-CTRL-06: Stop is enabled only while a run is genuinely in flight

The product must: offer a Stop control that is enabled from the moment a question passes the
guardrail until the run reaches a terminal state, and disabled at every other time.

Status: BUILT. Rendered at `frontend/src/components/screens/RunScreen.tsx:213-225` as a plain button
with the accessible name "Stop", `disabled={!stopEnabled}`. The enabled window is derived by
`deriveStopEnabled`, exported from `frontend/src/components/chat/StopButton.tsx` for direct unit
testing; the component that surrounds it is never itself rendered (its docstring is consumed as a
pure function only), so `.stop-button` is not a valid selector.
Layer: A.
Cost: 0.

| # | Step | What must happen | Evidence hook |
|---|---|---|---|
| 1 | Ask a question | Once the guard step reports a pass, the Stop button becomes enabled | role button "Stop", not disabled |
| 2 | Wait for the run to land on an answer | Stop becomes disabled once a terminal event (`trust_signal`, `done`, or a fatal `error`) arrives | role button "Stop", disabled |
| 3 | Ask a question the guardrail refuses | Stop never becomes enabled, since no passing guard event ever arrives | role button "Stop", disabled throughout |

Fails if: Stop stays enabled after the run has landed (a stale-enabled bug this exact mechanism was
built to fix, per `StopButton.tsx`'s own docstring), or is enabled before a guard pass.

### W-CTRL-07: a user-initiated stop shows no confirmation and leaves a frozen run screen

The product must, TODAY, as built: stop the run immediately on click with no confirmation dialog,
and leave the run screen showing its last state with Stop now disabled. Whether "no confirmation"
and "a frozen screen with no message" are the right product behaviour is exactly what this workflow
should force a reader to weigh; nothing here asserts that freezing is correct, only that it is what
ships.

Status: BUILT (as described, not necessarily as desired). `frontend/src/App.tsx:918-928`: clicking
Stop synchronously sets `stopped=true`, calls the local `stop()` (which aborts the client-side event
source, so no terminal event ever arrives to naturally disable the button), and separately posts
`POST /v1/query/{run_id}/stop`. No confirmation step exists anywhere in this path. D5.
Layer: A.
Cost: 0.

| # | Step | What must happen | Evidence hook |
|---|---|---|---|
| 1 | Start a run and click Stop while it is mid-flight | The click has no confirmation step: no dialog, no "are you sure" | absence of any `role="dialog"` opening on Stop click |
| 2 | Observe the run screen immediately after | The stepper freezes on whatever step was live, Stop becomes disabled, and no message explains that the reader caused this rather than the system | role button "Stop", disabled; absence of any testid'd notice explaining the stop (there is none: `guardrail-notice`, `cap-notice` and `run-failure` all render only for their own specific payloads, none of which fires on a user-initiated stop) |
| 3 | Check the server side | `POST /v1/query/{run_id}/stop` was actually sent, so the backend run is genuinely cancelled and not merely abandoned client-side | network assertion on the stop request, or the `/__e2e__/run_status` route the local mock backend exposes for exactly this proof |

Fails if: step 3 never fires (a client-only stop that leaves server-side work running is a cost and
correctness gap on top of the UX one), or if a later change adds a message to this path without
updating this workflow's expectation of silence.

## The feedback surface

### W-CTRL-08: thumbs, reason chips gated on thumbs down, comment, send

The product must: let a reader rate an answer helpful or not, and only when they rate it not
helpful, offer a fixed set of specific reasons plus a free-text comment before sending.

Status: BUILT, `frontend/src/components/feedback/FeedbackSurface.tsx:161-445`. Five reason chips
(`REASONS`, lines 51-57) render only when `rating === "down"` (line 327). The reasons are not
generic: each maps to a failure mode this system has actually produced (an unsupported citation, a
wrong answer, a missing source, a refusal that should have answered, or "too slow").
Layer: A.
Cost: 0.

| # | Step | What must happen | Evidence hook |
|---|---|---|---|
| 1 | Land on an answer screen | The feedback panel shows "Was this answer helpful?" with two thumb buttons and no reason chips | `data-testid="feedback"`; role buttons "Helpful" and "Not helpful" |
| 2 | Click "Helpful" | The up thumb is pressed; still no reason chips appear | role button "Helpful" `aria-pressed="true"`; absence of any of the five reason-chip texts |
| 3 | Click "Not helpful" instead | The down thumb is pressed and exactly five reason chips appear: "Citation does not support the claim", "Wrong answer", "Missing a source I expected", "Should have refused", "Too slow" | role button "Not helpful" `aria-pressed="true"`; role buttons for each of the five reason strings |
| 4 | Toggle one or more reasons, type a comment, click "Send feedback" | The panel shows "Thanks. This goes to the review queue." and the controls disappear | role status text "Thanks. This goes to the review queue." |
| 5 | Instead of sending, click "Skip" | The panel disappears with nothing sent | absence of `data-testid="feedback"` after click |

Fails if: reason chips appear before a thumbs-down, or a rating can be sent with no rating and no
flagged source at all (the send action is gated on `rating !== null || flaggedSources.length > 0`,
`FeedbackSurface.tsx:305`; a workflow probing this should confirm no Send control renders otherwise).

### W-CTRL-09: a send failure or a not-yet-captured race stays visible with a retry

The product must: if feedback cannot be saved because the run's own capture write has not landed
yet, retry automatically and say so; if it genuinely fails, show a plain error with a manual retry
rather than silently discarding the rating.

Status: BUILT, `FeedbackSurface.tsx:204-234`. A 409 (`FeedbackNotYetCapturedError`) is not treated
as a failure and retries up to `MAX_NOT_YET_CAPTURED_RETRIES` (3) times honoring the server's
`Retry-After`; any other failure shows a fixed error string and a "Retry" button in place of "Send
feedback".
Layer: A. The mock backend can simulate the 409 race deterministically since it is a local FastAPI
process this suite already controls; it needs no real model call.
Cost: 0.

| # | Step | What must happen | Evidence hook |
|---|---|---|---|
| 1 | Send feedback for a run whose capture write is deliberately delayed past the send | The panel shows "Still finishing up your answer. Retrying in a moment." rather than an error | `data-testid="feedback-status"`, role status |
| 2 | Let the retries exhaust | The panel shows "Still saving your answer. Try again in a moment." as an alert, with the button reading "Retry" | `data-testid="feedback-status"`, role alert |
| 3 | Force a non-409 failure (network error) | The panel shows "Could not send your feedback. Check your connection and try again." | `data-testid="feedback-status"`, role alert |

Fails if: a failed send silently clears the rating with no visible trace, which the component's own
docstring names as the worse alternative it was built to avoid.

### W-CTRL-10: flagging a source as not supporting its claim

The product must: let a reader flag an individual source as not supporting the claim it is attached
to, and include that flag in the SAME feedback submission as any rating and comment, rather than
posting it the instant it is clicked.

Status: BUILT. The control is `frontend/src/components/screens/AnswerScreen.tsx:710-745`, inside
each source card's body (never inside its `<summary>`, deliberately, to avoid a nested-interactive
accessibility violation, F-4.9-D-13). Bundling: `AnswerScreen.tsx` threads `flaggedSources` into
`FeedbackSurface`'s `citation_flags` payload (`FeedbackSurface.tsx:198-201`) rather than firing a
separate request, because `record_feedback` replaces the whole feedback row on every write and a
lone flag-only POST would silently erase an already-sent rating or comment.
Layer: A.
Cost: 0.

| # | Step | What must happen | Evidence hook |
|---|---|---|---|
| 1 | Open a source card and click "Flag: does not support" | The button now reads "Flagged" and stays pressed | inside `data-testid="source-{n}"`, role button text changes from "Flag: does not support" to "Flagged", `aria-pressed="true"` |
| 2 | Click Send feedback without touching the thumbs | The submission still sends, since a flagged source alone is enough to have something worth sending | `canSend` is true with `rating === null` and `flaggedSources.length > 0` |
| 3 | Inspect the submitted payload | `citation_flags` contains the flagged source's number with the fixed reason "Citation does not support the claim" | request body assertion against `postFeedback`'s call |

Fails if: clicking the flag button also opens or closes the source card underneath it (it lives
inside the `<summary>` region and must call `stopPropagation`), or if flagging fires its own request
immediately rather than waiting for Send.

## Presentation-only chrome

### W-CTRL-11: the persona chip is presentation only and hidden below md

The product must: show a small, static, named-scientist chip that never changes what the agent
retrieves or how it is trusted, visible in the app bar only at `md` and above.

Status: BUILT. Presentation-only by design, stated in `frontend/src/components/shell/PersonaChip.tsx:1-13`
("never changes which tools run, which records are retrieved, or what the trust signal says").
Hidden below `md`: `frontend/src/components/shell/AppShell.tsx:221`,
`sx={{ ml: 1, display: { xs: "none", md: "block" } }}` wraps the chip in the app bar. This applies
to the app-bar CHIP only; the run screen's `PersonaCaption` (same file, lines 118-158) carries no
such breakpoint and is visible at every width.
Layer: A.
Cost: 0.

| # | Step | What must happen | Evidence hook |
|---|---|---|---|
| 1 | Load the app at 1440px wide after a run has returned a persona name | The app bar shows the persona chip, "Working as [name]" | `data-testid="persona-chip"` visible |
| 2 | Resize to 390px wide with the same state | The app-bar persona chip is no longer visible | `data-testid="persona-chip"` present in the DOM but with `display: none` computed, or absent depending on MUI's `sx` breakpoint implementation; check computed style after settling, per D11 |
| 3 | Start a run at 390px | The run screen's persona caption (a different element) is still visible, since it carries no breakpoint | `data-testid="persona-caption"` visible at 390px |

Fails if: the persona chip or caption is ever found to change which tool ran, what was retrieved, or
the trust outcome, which would be a personalization-firewall breach (Section 14.1), not a chrome
defect, and should be escalated rather than filed here.

### W-CTRL-12: the disclaimer modal cannot be escaped and reappears after sign-out

The product must: block the entire app, mouse and keyboard alike, behind a medical disclaimer until
a reader checks the acknowledgement box and clicks Continue, and show it again for the next person
at the same workstation after a sign-out, since the previous person's acceptance should not read as
this one's.

Status: BUILT. `frontend/src/components/shell/DisclaimerModal.tsx`: `inert={!accepted}` on the
entire app shell (`frontend/src/App.tsx`, `<div inert={!accepted}>` wrapping `<AppShell>`), not only
a Tab-key trap, because a Tab trap alone was defeated by programmatic focus and a browser-chrome
round trip (F-4.8-A-08). Escape is explicitly swallowed (`DisclaimerModal.tsx:81-85`). Reappears
after sign-out: `frontend/src/App.tsx`'s sign-out handler calls `setAccepted(false)` (comment "R-11:
the next person at this workstation has not read the disclaimer"), independent of the
`sessionStorage` flag `rememberDisclaimer` sets, which is never cleared.
Layer: A.
Cost: 0.

| # | Step | What must happen | Evidence hook |
|---|---|---|---|
| 1 | Load the app fresh | The disclaimer modal is present, Continue is disabled | `data-testid="disclaimer-modal"`; Continue button disabled |
| 2 | Try Tab, Shift+Tab and Escape without checking the box | Focus never leaves the dialog, Escape does nothing, and nothing behind the modal is reachable by keyboard | focus stays within `data-testid="disclaimer-modal"`; rest of the page has `inert` |
| 3 | Check the box and click Continue | The modal closes and the app becomes reachable | absence of `data-testid="disclaimer-modal"` |
| 4 | Sign in, then sign out | The disclaimer modal reappears | `data-testid="disclaimer-modal"` visible again after sign-out |

Fails if: the modal can be dismissed by Escape, by a click outside it, or by any keyboard path that
does not go through the checkbox and Continue button, or if it does NOT reappear after sign-out.

### W-CTRL-13: client-side routing across the four top-level screens

The product must: keep the address bar and the visible screen in step in both directions, forward
navigation and the browser's own back and forward buttons, across exactly four paths, and treat any
other path as the search screen rather than a blank page.

Status: BUILT, `frontend/src/lib/routing.ts`. The four nav items in the app bar
(`frontend/src/components/shell/AppShell.tsx:201-219`) are `<Button>` elements, not anchors, so they
carry ACCESSIBLE ROLE "button", never role "link". `useScreenRoute` (`routing.ts:98-118`) pushes
history on forward navigation and listens for `popstate` on back/forward, proven by mutation:
removing the `popstate` listener leaves the URL-change and deep-link checks green and fails only the
back-button case (`routing.ts:91-96`). An unknown path falls back to `search`
(`screenForPath`, `routing.ts:64-71`).
Layer: A.
Cost: 0.

| # | Step | What must happen | Evidence hook |
|---|---|---|---|
| 1 | Click each of the four nav items in turn | The URL updates to `/`, `/integrations`, `/about`, `/docs` respectively, and the visible screen changes to match | role button (NOT role link) with each nav label; `window.location.pathname` |
| 2 | Click a nav item that is already current | No duplicate history entry is pushed | `window.history.length` unchanged across a repeat click |
| 3 | Navigate forward twice, then press the browser Back button | The URL changes back AND the visible screen changes back to match, not just the URL | `window.location.pathname` and the rendered screen agree after `popstate` |
| 4 | Load the app directly at an unrecognised path, for example `/nonsense` | The search screen renders rather than a blank page | `screen === "search"` on load |

Fails if: any workflow or test selects these nav items by role "link" rather than role "button". At
least one existing capture journey (`frontend/e2e/journeys/narrow-viewports.spec.ts:60-63`) does
exactly this, wrapped in `.catch(() => undefined)`, so the nav click silently never fires and the
journey still reports success. That is a defect in the TEST, not the product, and it is flagged here
because a workflow reader might otherwise copy the same wrong selector.

## Integrations, docs and about

### W-CTRL-14: three static informational screens with no interactive controls

The product must: describe the product's five access surfaces (web, REST/SSE, GraphQL, MCP, CLI,
plus a KGX export batch command), the event contract, and the three data layers, accurately against
what is actually shipped, as read-only reference material. It must not claim a capability that does
not exist in the shape described.

Status: BUILT as static prose, and the complaint that it is "a placeholder" (C4) does not match what
is on `develop` today. `frontend/src/components/screens/InfoScreens.tsx` renders three screens, each
a `Page` of `Card`s. NONE of the three screens contains a single `<button>` element in the ordinary
sense: every interactive element is a `<pre>` code block made focusable and given a role (line 61-63,
`tabIndex={0}` `role="region"`) so a keyboard user can scroll a code sample, which is an
accessibility fix for a static block, not a control that does anything.

C4 and the PREMISE: the stub registry (`frontend/src/stubs/registry.ts`, `kgx-export` entry) still
says "A request button that acknowledges and does nothing", but no such button exists anywhere in
`InfoScreens.tsx`. The KGX card (`InfoScreens.tsx:151-155`) is a code sample showing the real CLI
command (`s3-kgx-export ...`), with no button at all. This registry entry is STALE. It should be
corrected or removed the next time `stubs/registry.ts` is touched, since a stub entry describing a
control that does not exist is exactly the failure mode the registry's own docstring warns against
("A registry entry that understates or overstates what a surface does is read as an inventory and is
worse than none").
Layer: A.
Cost: 0.

| # | Step | What must happen | Evidence hook |
|---|---|---|---|
| 1 | Navigate to Integrations | Five cards render: REST and SSE, GraphQL, MCP server, KGX export, Command line. No button anywhere on the page | `role="heading"` for each card title; absence of any `role="button"` on the page besides the app bar's own nav and account controls |
| 2 | Navigate to Docs | Four cards render: Access, The event stream, Citations, Limits | `role="heading"` for each card title |
| 3 | Navigate to About | Three layer cards plus a "Cite or refuse" section render | `role="heading"` for each |
| 4 | Tab to a code sample | It receives focus and is announced by its label (for example "REST and SSE example") | `role="region"` with the card's own `aria-label` |
| 5 | Compare every command and endpoint printed against the code it claims to describe | `POST /v1/query`, the GraphQL mutation shape, the MCP tool name `ask_biomedical_question`, the `s3-kgx-export` command, and `s3 ask` all match what actually exists (build phases 4.2, 4.3, 4.4, T-4.16-04's own account of the four errors this page previously had) | source review, not a UI hook: compare against `pyproject.toml`'s console scripts and the mounted `/graphql` route |

Fails if: any card describes a route, command, or capability that does not exist in the shape shown,
which is the exact defect class T-4.16-04 already found and fixed once (a command line card printing
a nonexistent `ncbi-search` binary, a KGX card printing a nonexistent live POST route). This page is
prose about other modules, and nothing links the two automatically, so this check has to be redone
by hand whenever a described surface changes.

## Viewports and the app bar

### W-CTRL-15: no horizontal overflow at any supported width, and the app bar specifically

The product must: never let the page scroll sideways at any width the product claims to support, and
the app bar in particular must not collide with itself (the brand wrapping across the nav, or the
sign-in button clipping off the edge).

Status: BUILT (fixed in this branch). `frontend/src/components/shell/AppShell.tsx:118-144` documents
the defect measured at 390px, brand wrapping to three lines, "Log in" clipped off the right edge, and
the fix: the `Toolbar` wraps (`flexWrap: { xs: "wrap", sm: "nowrap" }`), the brand gets `whiteSpace:
"nowrap"` and `flexShrink: 0`, and the nav wraps inside its own `Box`. The comment states it was
verified at 0px overflow at 320, 390, 480, 768 and 1440.
Layer: A.
Cost: 0.

| # | Step | What must happen | Evidence hook |
|---|---|---|---|
| 1 | Set the viewport to 320, 390, 480, 768 and 1440px in turn, on every one of the four top-level screens | `document.documentElement.scrollWidth` does not exceed `document.documentElement.clientWidth` by more than 1px at any width, on any screen | `page.evaluate(() => ({scroll: document.documentElement.scrollWidth, client: document.documentElement.clientWidth}))`, exactly the measurement `frontend/e2e/journeys/narrow-viewports.spec.ts:45-56` already takes, but asserted rather than only noted |
| 2 | At 390px specifically, read the app bar | The brand text stays on one line, does not overlap the nav, and "Log in" (or the account menu) is fully visible, not clipped | visual bounding-box check: the brand's bounding box does not intersect the first nav item's bounding box; "Log in" button's bounding box is fully inside the viewport |
| 3 | Settle before measuring | Wait past MUI's transition window (roughly 250ms) before taking either measurement, and state that the step did so, per D11 | explicit wait or a stable-frame check before the `page.evaluate` call |

Fails if: `scrollWidth` exceeds `clientWidth` by more than a hairline at any of the five widths, or
if the brand and the first nav item's bounding boxes overlap. The existing capture journey
(`narrow-viewports.spec.ts`) takes this exact measurement today but only WRITES it as a note in a
filmstrip; it never asserts on it, which is why the collision shipped and nobody was watching. This
workflow is what that journey would need to become to actually catch a regression rather than
narrate one after the fact. N2 and D8 are the same underlying defect and are covered by this one
workflow, not two.

### W-CTRL-16: the rail toggle button, and the rail it operates, disagree below md

The product must, if it intends to match the approved design at all widths: either hide the rail
toggle at the same breakpoint the rail itself disappears, or make the rail reachable at every width
the toggle is offered. Today it does neither, and the approved prototype already answers this
question, which the shipped code did not consult when it fixed the narrow-width app bar (see the
design-system finding under D9 below).

Status: PARTLY BUILT, and the two halves disagree. The rail (`frontend/src/components/answer/FollowUp.tsx:397`,
`HistoryRail`) and the collapsed rail strip (same file, line 315, `CollapsedRail`) both carry
`display: { xs: "none", md: "flex" }`, so neither renders below `md`. The toggle button that opens
and closes the rail (`frontend/src/components/shell/AppShell.tsx:152-167`, gated only on
`showRailToggle={railAvailable}` at `App.tsx`, which checks sign-in state and screen, never
viewport) carries no breakpoint at all and stays visible at every width. So a signed-in reader on a
phone sees a working-looking toggle button that does nothing observable, because the thing it
toggles is not on screen at that width. This is D4.

THE DESIGN ALREADY ANSWERS THIS, and the shipped fix diverged from it without citing it: the
approved prototype's own stylesheet (`docs/build/design/design-system/prototype/app.html:65`) reads
`@media (max-width:860px){#rail,#railStub{display:none}}`, hiding the rail AND its own toggle
stub together at the same breakpoint. `AppShell.tsx`'s comment on the neighbouring app-bar fix
states "there is no designed mobile bar to copy" while citing only the standalone
`components/app-bar.html` card, which is true of that one file but not of the full prototype, which
does have a matching rule for exactly this control pair. Whoever next touches this should hide the
rail toggle at the same `md` breakpoint the rail itself uses, which is what the approved design
already specifies.
Layer: A.
Cost: 0.

| # | Step | What must happen | Evidence hook |
|---|---|---|---|
| 1 | Sign in on a 390px viewport, on the search screen | The rail toggle icon button is visible in the app bar | `aria-label="Show or hide your searches"`, visible |
| 2 | Click it | Nothing observable happens, because `HistoryRail`/`CollapsedRail` are `display: none` below `md` regardless of the toggle's own state | no change in the DOM's visible rail region at this width |
| 3 | Widen to 900px or above with the same signed-in state | The rail (or its collapsed strip) becomes visible and the same toggle now does something | `data-testid="history-rail"` or `data-testid="collapsed-rail"` visible |

Fails if: this stays as is with nobody having chosen it on purpose. It is not currently ticketed as a
defect anywhere read for this pass; it is recorded here because the checklist's D4 already flagged
the mismatch and the design system turns out to already have the answer.

## Design system coverage (D9)

Neither the sign-in screen nor the app bar had any design in
`docs/build/design/design-system/` before this branch, and both were found by accident rather than
by checking. The instruction was to check every surface the product has against that directory
rather than assume those two were the only holes. Full listing of
`docs/build/design/design-system/` (20 files) checked against every screen and major component
`frontend/src/components/` renders:

| Surface | Has a dedicated design file | Note |
|---|---|---|
| Home screen | Yes, `screens/home.html` | |
| Run/streaming screen | Yes, `screens/streaming.html` | |
| Pipeline stepper | Yes, `components/pipeline-stepper.html` | |
| Answer screen | Yes, `screens/answer.html` | |
| Source card | Yes, `components/source-card.html` | |
| Trust pills | Yes, `components/trust-pills.html` | |
| Citation chip | Yes, `identity/citation-chip.html` | |
| Layer badges | Yes, `identity/layer-badges.html` | |
| Provenance spine | Yes, `identity/provenance-spine.html` | |
| Feedback surface | Yes, `components/feedback.html` | |
| Depth control | Yes, `components/depth-control.html` | |
| Persona chip/caption | Yes, `components/persona.html` | |
| Disclaimer modal | Yes, `flows/disclaimer-modal.html` | |
| Guest allowance / wall states | Yes, `flows/guest-states.html` | |
| App bar (as a standalone component) | Yes, `components/app-bar.html`, but WITH NO RESPONSIVE RULE of its own | The full `prototype/app.html` DOES carry a responsive rule for the app bar (`@media (max-width:720px)`, line 402-410) that the standalone card lacks. See W-CTRL-16 |
| Logo/brand | Yes, `brand/logo.html` | |
| Foundations (colour, spacing, type) | Yes | |
| Sign-in screen | NO | Confirmed a hole in the code itself: `AuthGate.tsx`'s own comment states "This screen has no designed precedent of its own". Known, D7 |
| Follow-up field | NO dedicated component page | Present only inside the monolithic `prototype/app.html`, not as its own card the way search-bar or feedback are |
| History rail / collapsed rail | NO dedicated component page | Same: present only inside `prototype/app.html` (`#rail`, `#railStub`), with no standalone card |
| Account menu | NO | Not mentioned anywhere under `design-system/`, including the monolithic prototype's account dropdown markup at a glance; not deeply audited in this pass, flagged for a follow-up look |
| Integrations, Docs, About screens | NO dedicated screen design | Referenced only by name inside `prototype/app.html`'s nav; no standalone screen mock for any of the three exists |
| Reasoning log ("Show work" disclosure) | NO dedicated component page | The label "Show work" appears once, inside `screens/answer.html:82`, as one line of that screen's mock; there is no separate component card for it the way `pipeline-stepper.html` or `source-card.html` exist |

The general pattern: every element that got its OWN component card (source card, trust pills,
feedback, persona, depth control) is designed. Everything that only ever appeared as a piece of the
single monolithic `prototype/app.html` mock, and never got promoted to its own card, has no
addressable design a component-level fix can consult. That is a bigger set than the two holes found
by accident: the sign-in screen, the follow-up field, the history rail, the account menu, and all
three informational screens share the same gap.

## Other findings from this pass

Why `total_cost_usd` reports `0.0` (U2, N4): this is DELIBERATE, not an unverified or untrusted
value. `src/system_03_search_agent/harness/cost_control.py:696-731`,
`filter_events_for_end_user`'s docstring states plainly: "redacts `total_cost_usd` out of any `done`
event to 0.0 (F-2.0-05), so no dollar figure of any kind reaches an end-user surface." Every
end-user-facing adapter (the React UI included) applies this; only an operator-scoped adapter sees
the real figure. There is no workflow to write here beyond confirming the redaction holds: a normal
user should NEVER see a nonzero cost figure, and `0.0` appearing in `answer-meta` or anywhere else in
the UI is the redaction working, not a defect to chase.

The narrow-viewports capture journey's own nav selector (`frontend/e2e/journeys/narrow-viewports.spec.ts:60-63`)
uses `getByRole("link", ...)` for the four nav items, which the shared brief and W-CTRL-13 both
confirm are `<Button>` elements with role "button", never role "link". The click is wrapped in
`.catch(() => undefined)`, so this has been silently failing (never actually navigating) every time
that journey has run, and the journey still reports frames captured and passes. This is a test
defect worth a ticket, separate from anything in this file: the journey believes it is capturing
Integrations, About and Docs at each width and it is very likely still on the home screen for all
three.
