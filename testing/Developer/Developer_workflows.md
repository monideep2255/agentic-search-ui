# Developer workflows

What this product must be able to do, derived from what is actually built, ranked so you can stop reading anywhere and still have covered the things that matter most.

This is a product specification first and a test plan second. Each workflow states an obligation you can disagree with on product grounds, and carries a status verified against code rather than assumed. Where the product does not meet its own obligation, that is written down here rather than discovered later.

## Table of contents

- [How to read this](#how-to-read-this)
- [Tier 1, must never break](#tier-1-must-never-break)
- [Tier 2, visibly wrong if broken](#tier-2-visibly-wrong-if-broken)
- [Tier 3, quiet failures](#tier-3-quiet-failures)
- [The three audience depths](#the-three-audience-depths)
- [What is not built](#what-is-not-built)
- [Defects this exercise found](#defects-this-exercise-found)
- [Decisions waiting on the product owner](#decisions-waiting-on-the-product-owner)
- [Coverage against UI feedback](#coverage-against-ui-feedback)
- [How to run the automated tests](#how-to-run-the-automated-tests)

## How to read this

Fifty workflows, in three tiers, written by four workers each owning one area. The four per-area drafts were merged here by id, then deleted on 2026-09-12; they remain in git history under `testing/drafts/`.

Every workflow carries three fields.

- Status: BUILT, PARTLY BUILT or NOT BUILT, each citing a file and line. A status without a citation was not accepted.
- Layer: which of the three testing layers verifies it, defined under [How to run the automated tests](#how-to-run-the-automated-tests).
- Cost: real model answers consumed. Layer A is always zero.

The distribution is the useful number: 46 of 50 workflows are Layer A and cost NOTHING. Only the three depth workflows and one live resolution check need a real answer. Proven rather than claimed: `frontend/e2e/second-turn.spec.ts` already drives sign-up, an answer, a follow-up producing a second answer, the thread collapsing and New search resetting, in 16.5 seconds against a real FastAPI, real Postgres, real auth, real SSE and the real five-node loop, with only the outbound model call faked.

## Tier 1, must never break

The product has no reason to exist if one of these is wrong.

| Id | The product must | Status | Layer | Cost |
|---|---|---|---|---|
| W-thread-3 | Tie every claim to a source, or refuse and say so. No answering from model priors | BUILT, enforced at two independent points: the backend grounding pass, and a frontend contract where an uncited claim renders grey with screen-reader text "This sentence has no source." (`AnswerScreen.tsx:519-527`) | A | 0 |
| W-thread-2 | Show the answer as claims on a provenance spine, each with citation chips, source cards and trust pills | BUILT, `AnswerScreen.tsx:500-566`, `:583-624`, `:846` | A | 0 |
| W-thread-4 | Name diseases in words, not as `MedGen:C2676676` | BUILT, resolved through Layer 2 at query time, `synthesis/disease_names.py` | A, B to prove the live API | 0, 1 |
| W-thread-5 | Never link a citation to a host outside the allowed NCBI set, and say so when it cannot | BUILT, `isLinkableCitationUrl`, `AnswerScreen.tsx:198-215` | A | 0 |
| W-thread-6 | Carry a follow-up forward so "it" resolves, without the reader repeating themselves | BUILT, a follow-up runs a FULL search rather than reusing the previous answer | A | 0 |
| W-thread-1 | Show continuous motion while the reader waits: five steps, a ticking counter, tool chips | BUILT, `RunScreen.tsx:52`, `:196`, `:340` | A | 0 |
| W-GUEST-2 | Let a stranger ask a question with no account, from a suggested chip or by typing | BUILT, `HomeScreen.tsx:33-37`, `App.tsx:719-753` | A | 0 |
| W-GUEST-6 | Stop a guest at five answers with an honest wall, not a broken page | BUILT, `app.py:1157-1172`, `GuestAllowance.tsx:171-173` | A | 0 |
| W-identity-1 | Let someone create an account and sign in | BUILT, `AuthGate.tsx:60-301`, rebuilt 2026-09-05 | A | 0 |
| W-identity-2 | Never echo a backend error into the sign-in screen, and never say which emails exist | BUILT, fixed copy per mode, `AuthGate.tsx:68-117` | A | 0 |

## Tier 2, visibly wrong if broken

A reader would notice, and would lose trust, but the product still functions.

| Id | The product must | Status | Layer | Cost |
|---|---|---|---|---|
| W-thread-7 | Offer one honest next step derived from what retrieval left out, or stay quiet | BUILT, never model-generated, returns `None` in four named cases | A | 0 |
| W-thread-8 | Refuse clearly, whether the refusal comes from the guardrail or from having no data | PARTLY BUILT. The two paths render DIFFERENTLY: a guardrail refusal gets a dedicated notice, a no-data refusal renders as an ordinary uncited grey spine claim | A | 0 |
| W-thread-9 | Say so when it left something out, in the reader's terms | PARTLY BUILT. Three notes render; a fourth, `_build_repair_cap_note`, matches no prefix and still lands as an uncited claim | A | 0 |
| W-thread-10 | Stop a run when the reader asks, and abort it server side too | BUILT for the mechanics, `App.tsx:918-928` | A | 0 |
| W-thread-11 | Hedge an answer that is grounded but confirmed by only one source, without blaming the reader | BUILT, `synthesis/trust.py` DECISION_TABLE row `(high, grounded, insufficient)` | A | 0 |
| W-identity-3 | Change the product visibly on sign-in: account menu, rail, no allowance, saved depth | BUILT, `AppShell.tsx:225-253`, `App.tsx:525`, `:1039`, `:437-452` | A | 0 |
| W-identity-4 | List your earlier searches in a rail, once signed in | BUILT, `FollowUp.tsx:373-609` | A | 0 |
| W-identity-5 | Be honest that a history row RE-RUNS the question rather than replaying a stored answer | BUILT as a re-ask. `HistoryEntry` holds no answer, claim or source field | A | 0 |
| W-identity-6 | Let the rail collapse and come back, and remember which | BUILT, `FollowUp.tsx:295-358` | A | 0 |
| W-identity-9 | Clear one person's conversation when they sign out | PARTLY BUILT, and this is the privacy defect. Sign-out never calls `setThread([])` | A | 0 |
| W-identity-10 | Be honest that a reload signs you out, since the token lives in React state only | BUILT as an accepted limitation, `App.tsx:303` | A | 0 |
| W-GUEST-3 | Count the allowance down visibly across five answers | BUILT, `guest_sessions.py:60`, `GuestAllowance.tsx:74-134` | A | 0 |
| W-GUEST-7 | Wall a guest who burns ten attempts, distinctly from spending five answers | BUILT, `app.py:1173-1191` | A | 0 |
| W-GUEST-8 | Tell a guest whose session was migrated into an account what happened | BUILT, `App.tsx:605-626`, `:817-838` | A | 0 |
| W-GUEST-9 | Let a guest give feedback and stop a run, while never showing them a rail | BUILT, `App.tsx:501`, `:525` | A | 0 |
| W-GUEST-11 | Say something true when a shared daily ceiling is hit, not a generic failure | PARTLY BUILT. The copy exists and reaches the dots caption, but the ask-failure path never routes these reasons | A | 0 |
| W-CTRL-04 | Offer three answer depths, default to researcher, and remember an account's choice | BUILT, `DepthControl.tsx:23-29` | A | 0 |
| W-CTRL-06 | Enable Stop only while a run is genuinely in flight | BUILT, `RunScreen.tsx:213-225` | A | 0 |
| W-CTRL-08 | Take feedback: thumbs, reasons only on a thumbs down, a comment, and send | BUILT, `FeedbackSurface.tsx:161-445` | A | 0 |
| W-CTRL-09 | Keep a failed feedback send visible with a retry rather than losing it | BUILT, `FeedbackSurface.tsx:204-234` | A | 0 |
| W-CTRL-10 | Let a reader flag a source as not supporting its claim | BUILT, `AnswerScreen.tsx:710-745` | A | 0 |
| W-CTRL-13 | Route between the four screens, support the back button, and fall back on an unknown path | BUILT, `lib/routing.ts` | A | 0 |
| W-CTRL-15 | Never scroll sideways at any supported width | BUILT, fixed twice in this branch. Verified 0px at 320, 390, 719, 721, 1440 | A | 0 |

## Tier 3, quiet failures

Wrong here is survivable and would go unnoticed for a long time.

| Id | The product must | Status | Layer | Cost |
|---|---|---|---|---|
| W-GUEST-1 | Show a stranger what this is before they have done anything | BUILT, `DisclaimerModal.tsx:47-215`, `HomeScreen.tsx:129-153` | A | 0 |
| W-GUEST-4 | Let a returning guest see how many searches they have left | NOT BUILT. `allowance` seeds `null` every mount and nothing refetches it for a restored token | A | 0 |
| W-GUEST-5 | Treat the ten-attempt ceiling as distinct from the five-answer allowance, with refunds | BUILT, `guest_sessions.py:60,90`, `:400-417` | A | 0 |
| W-GUEST-10 | Move a guest's runs into a new account, within the five-minute retention window | BUILT and deliberately limited. Promises nothing beyond it | A | 0 |
| W-identity-7 | Name the account and its remaining searches in the rail footer | BUILT, `FollowUp.tsx:585-608` | A | 0 |
| W-identity-8 | Offer integrations, documentation and sign-out from the account menu | BUILT, `AccountMenu.tsx:97-255` | A | 0 |
| W-identity-11, W-CTRL-16 | Not show a control that does nothing | PARTLY BUILT. The rail toggle is visible and enabled below `md` while what it toggles is hidden | A | 0 |
| W-CTRL-05 | Lock the depth control once a run starts | NOT BUILT. The `locked` prop exists and no caller passes it | A | 0 |
| W-CTRL-07 | Tell a reader their stop worked | BUILT as described, not as desired. No confirmation renders; the run screen freezes | A | 0 |
| W-CTRL-11 | Show the persona as presentation only, never letting it touch retrieval | BUILT, `PersonaChip.tsx:1-13` | A | 0 |
| W-CTRL-12 | Gate the product behind a disclaimer that cannot be escaped, and re-show it after sign-out | BUILT, `DisclaimerModal.tsx` | A | 0 |
| W-CTRL-14 | Explain its integrations honestly, without offering controls that do nothing | BUILT as static prose. The "placeholder" complaint does not match the code | A | 0 |
| W-thread-12 | Be honest about how the answer arrives, rather than implying streaming it does not do | BUILT as described. `write_node` chunks by sentence but emits with plain `emit`, so all chunks land in one flush | A | 0 |

## The three audience depths

The centrepiece, and the only place the spec judges an answer's content rather than the interface's behaviour. Depth reaches synthesis at exactly one line, `core/graph.py:5634`, and changes register and length only, never retrieval.

| Id | Depth | The product must | Layer | Cost |
|---|---|---|---|---|
| W-CTRL-01 | `clinical_brief` | Write plain, short, complete sentences for a clinician, and NEVER diagnose, classify a variant, or recommend treatment | C | 1 answer |
| W-CTRL-02 | `researcher` | Write standard biomedical vocabulary with full mechanistic detail. The default | B with C | 1 answer |
| W-CTRL-03 | `deep_technical` | Give maximal depth with raw CURIEs inline in the prose, and never invent an identifier absent from the findings | B with C | 1 answer |

Two interactions a naive test gets wrong, stated here so nobody re-derives them.

Seeing `MedGen:C0346153` at `deep_technical` is CORRECT. The directive requires identifiers inline. The old W1 check treated any visible CURIE as the defect, so it would fail the product for obeying its instructions.

`clinical_brief` is the dangerous one. `synthesis/findings.py:788-796` records finding F-4.5-06 breach 2: told to be brief, it reported three of four pinned disease associations, every claim correctly grounded and correctly cited, and nothing said a fourth existed. That is a confident wrong answer, and it is invisible to every check that reasons about the claims that ARE present. Two successive strengthenings of the directive failed to hold, which is why the completeness repair is structural rather than promptable. So W-CTRL-01 checks that the FINDING COUNT does not drop between depths, never merely that the prose got shorter.

## What is not built

Four things, stated so the spec is not read as more complete than it is.

| Item | Where | Consequence |
|---|---|---|
| A returning guest's allowance | W-GUEST-4 | They cannot see how many searches they have left until they spend one |
| The depth lock during a run | W-CTRL-05 | Unobservable today, since the home screen unmounts during a run |
| Clarifying questions for an ambiguous query | `graph.py:1498`, hardcoded `None` | The contract carries the field and the frontend parses it. Nothing ever populates it |
| Five of the seven tools | `graph.py:3157`, `:3259` | Built, schema-registered, unreachable. The model is told about all seven |

## Defects this exercise found

Found by deriving workflows from features, before a single test was run.

| # | Defect | Status |
|---|---|---|
| 1 | The sign-in screen had no design and rendered as raw browser defaults | FIXED 2026-09-05 |
| 2 | The app bar collided with itself below 720px on every screen | FIXED 2026-09-05, twice: the first fix was invented, the second follows `prototype/app.html:403` |
| 3 | The truncation and unaddressed-entities disclosures rendered nowhere | FIXED 2026-09-05 |
| 4 | A fourth disclosure, `_build_repair_cap_note`, still renders as an uncited spine claim | OPEN, W-thread-9 |
| 5 | A no-data refusal renders as prose rather than a refusal notice | OPEN, W-thread-8 |
| 6 | `thread` survives sign-out, so one person's conversation reaches the next person at that browser | OPEN, W-identity-9 |
| 7 | The rail toggle is a dead control below `md`, in the design as well as the code | OPEN, W-CTRL-16 |
| 8 | The attempt ceiling has no counter. Nine refusals while the dots read "5 searches left" | OPEN, W-GUEST-5 |
| 9 | Daily-cap refusals never reach their own purpose-written copy on the ask path | OPEN, W-GUEST-11 |
| 10 | Journey 7 selects nav items by `getByRole("link")` when they are buttons, inside a `.catch()`, so it has probably never navigated anywhere while reporting success | OPEN, test defect |
| 11 | Five surfaces have no design at all: the sign-in screen, the follow-up field, the history rail and its strip, the account menu, and all three informational screens | OPEN, product decision |
| 12 | The frontend suite fails by machine load. Identical code gave 5 failed on a 139-second run and 245 passed on a 50-second run | OPEN, gate quality |

## Decisions waiting on the product owner

Four, none of which an assistant should settle.

- Below 720px the design hides every nav item except the current page, so Integrations, About and Docs become unreachable with no menu to reach them from. Shipped as designed. Is that right?
- The rail toggle below `md` is dead in the DESIGN, not only in the code. Hide the toggle, or make the rail reachable?
- Five surfaces have no design. Design them, or accept that they are built from foundations case by case?
- Should a no-data refusal look like a guardrail refusal? They are different code paths today and nothing states an intent.

## Coverage against UI feedback

Every item in `docs/build/UI_feedback.md` is carried, per the product owner's instruction of 2026-09-05 that nothing in it be dropped. The three headline findings, the five complaints, the four known-not-fixed items and the four never-checked items map to workflows above. Three resolve differently than that document states, and each is worth knowing.

- Complaint 4, the integrations page as a placeholder: the premise does not match the code. There are no controls on any of the three informational screens, and the stale claim about a dead KGX button lives in `frontend/src/stubs/registry.ts`, not in the page.
- Complaint 1, the 8px horizontal bleed at 390px: that was the measurement, not the defect. The app bar overlapped itself.
- `total_cost_usd` reporting `0.0` is a deliberate redaction for non-operators (`harness/cost_control.py:696-731`), not an unverified value. The control is working.

## How to run the automated tests

For developers. Moved here from `testing/README.md` on 2026-09-12, when that README became a short note for the product owner.

| Layer | What it checks | Cost |
|-------|-----------------|------|
| A, mechanism | Deterministic assertions against the real stack: real FastAPI, real SSE, real cost caps, the real five-node loop. Only the outbound model call is faked, by `tests/e2e_support/mock_llm_backend.py` | Free, about a minute |
| B, live product | Capture, not assertion, against the deployed develop app | Real money and real guest allowance |
| C, answer quality | Whether an answer is complete, well cited and readable | A person's time. No script |

Layer A:

```bash
cd frontend && npx playwright test e2e/
```

Layer B, gated so it never runs by accident:

```bash
cd frontend && RUN_LIVE_JOURNEYS=1 npx playwright test e2e/journeys/
```

Without `RUN_LIVE_JOURNEYS=1`, `frontend/e2e/journeys/_capture.ts` disables the live journeys. With it, they target the develop app unless `S3_LIVE_WEB_URL` or `S3_LIVE_API_URL` overrides it, and an override must be `https://` or loopback. Screenshots land in `frontend/e2e/evidence/`.

### Run a real-answer check

Added 2026-09-13, fix set 6 item 6.1. Layer A fakes the model, so until this existed no automated run had ever asserted on an answer a model wrote, and every answer fix could only be checked by hand.

```bash
cd frontend && npm run test:real-answer
```

What it needs: the credentials in the repository root `.env`. The mode refuses to start and names the missing variable names when any of GUARD_MODEL, PLAN_MODEL, SYNTH_MODEL, OPENROUTER_API_KEY, GRAPH_QUERY_URL, GRAPH_QUERY_TOKEN or PER_QUERY_COST_CAP_USD is unset. It also needs the local `search_agent_users` database, the same as every other Layer A run.

What it costs: real model budget on one question, two at the most, since a refusal is retried once. The backend reaches the configured provider, the graph query service and live NCBI endpoints, so this is not free and not offline.

What it asserts: shape and grounding only. At least one claim, at least one citation chip, a source card linking to an NCBI record, a disease named in words with no raw `MedGen:` code, and a source count on the meta strip. It never checks whether a stated fact is true.

One trap worth knowing: `S3_E2E_REAL_MODEL=1` alone does not guarantee a real backend, because `reuseExistingServer` reuses a mock backend already listening on port 8931. The spec asks the backend `/__e2e__/mode` before it asks a question and fails loudly rather than passing against the fake, so stop any stray backend on that port first.

The Playwright specs stay under `frontend/e2e/` because `frontend/playwright.config.ts` sets `testDir: "./e2e"`, `.github/gates/gate10_accessibility.sh` names `e2e/accessibility.spec.ts`, and `frontend/e2e/live-target.spec.ts` walks `e2e/` to forbid hardcoded deployed URLs.
