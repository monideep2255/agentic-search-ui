# Testing

The single entry point for UI testing in this repository. It names the three layers of testing this product has, gives the exact command for each, and says where every related file lives, including the ones that deliberately did not move here.

## Table of contents

- [The three layers](#the-three-layers)
- [Run commands](#run-commands)
- [Where things live](#where-things-live)
- [What moved, and what stayed put](#what-moved-and-what-stayed-put)
- [What is next](#what-is-next)

## The three layers

| Layer | What it checks | Determinism | Cost | Runtime |
|-------|-----------------|-------------|------|---------|
| A, mechanism | Deterministic assertions against the real stack: real FastAPI, real SSE streaming, real cost-cap enforcement, the real five-node LangGraph loop. Only the outbound LLM call is faked, by `tests/e2e_support/mock_llm_backend.py` | Deterministic, real red or green | Free, no model provider is called | About a minute |
| B, live product | Capture, not assertion, against a deployed app | Non-deterministic, the model and the network both vary run to run | Real money and real guest allowance are spent | Minutes, and it reaches the public internet |
| C, answer quality | Whether an answer is actually good: complete, well cited, readable | Not automatable today | A person's time | However long the reviewer takes |

Layer C has no script and no command. A human reads the answer and judges it. Nothing here replaces that.

## Run commands

Layer A, the mechanism suite:

```bash
cd frontend && npx playwright test e2e/
```

This runs everything under `frontend/e2e/`, `journeys/` included, against the local stack that `frontend/playwright.config.ts` boots for the run: Vite on a fixed port and FastAPI on a fixed port, with `tests/e2e_support/mock_llm_backend.py` swapped in as the backend process so the only faked piece is the outbound model call. Nothing here reaches the internet and nothing here spends money.

Layer B, the live journeys:

```bash
cd frontend && RUN_LIVE_JOURNEYS=1 npx playwright test e2e/journeys/
```

`RUN_LIVE_JOURNEYS=1` is the gate. Without it, `frontend/e2e/journeys/_capture.ts` sets `JOURNEYS_ENABLED` to false and the live journeys do not run. With it, they default to the DEPLOYED DEVELOP app, not production, with no environment variable needed: `frontend/e2e/live-target.ts` resolves `LIVE_WEB_URL` and `LIVE_API_URL` to the develop deployment unless `S3_LIVE_WEB_URL` or `S3_LIVE_API_URL` overrides them, and either override must be `https://` or a loopback address, never a plaintext remote host.

Run Layer B deliberately, not by habit. It spends a real guest allowance and real model budget every time.

## Where things live

| Item | Location | Why |
|------|----------|-----|
| This entry point | `testing/README.md` | Start here |
| Manual test workflows and the product owner's verdict | `testing/UI_feedback.md` | Moved from the repository root, see below |
| Screenshots and filmstrips the live journeys produce | `testing/evidence/` | Moved from `docs/build/design/evidence/`, see below |
| Feedback capture (inbox, processed) | `testing/feedback/` | Already in place, untouched by this reorganization |
| The Playwright specs themselves | `frontend/e2e/` and `frontend/e2e/journeys/` | Deliberately did NOT move, see below |
| The ranked workflow spec | `testing/Product_workflows.md` | Does not exist yet, see "What is next" |

The Playwright specs stay in `frontend/e2e/` rather than moving under `testing/`, for three verified reasons:

- `frontend/playwright.config.ts` sets `testDir: "./e2e"`, resolved relative to the config file's own directory. Moving the specs would mean moving or rewriting that config too.
- `.github/gates/gate10_accessibility.sh` runs `npx playwright test e2e/accessibility.spec.ts`, a working CI gate that names this exact path.
- `frontend/e2e/live-target.spec.ts` is a structural guard: it walks every `.ts` file under `e2e/` recursively and fails if any spec outside `live-target.ts` itself hardcodes a deployed URL. Moving the specs out from under `e2e/` would either break that walk or require rewriting the guard along with everything it guards.

Moving the specs for the sake of tidiness would trade a working CI gate and a working structural guard for a cleaner-looking folder. Not worth it.

## What moved, and what stayed put

Two moves, both with `git mv` so history follows the files:

- `UI_feedback.md` moved from the repository root to `testing/UI_feedback.md`.
- `docs/build/design/evidence/` moved to `testing/evidence/`. The rest of `docs/build/design/` (the design system, the prototype HTML, the build workflow doc) stayed exactly where it was: only the evidence subfolder was testing output living in the wrong place.

Every live reference to either path was updated so it resolves, including the code path that matters most: `frontend/e2e/journeys/_capture.ts` computes `EVIDENCE_ROOT` with `path.resolve` from its own directory, and that computation changed from `../../../docs/build/design/evidence` to `../../../testing/evidence`.

Three files deliberately did NOT get updated, and this is load-bearing rather than an oversight: `DECISIONS.md`, `LEARNINGS.md`, and everything under `tracker/`. These are append-only historical records. An entry written in August that names the path the file had in August is a true statement about the past. Rewriting it to name today's path would make the record say something that was never the case. `.claude/rules/goal-contracts.md` states the general version of this: never corrupt the subject to satisfy the check. The subject here is history, and it does not get corrected to match a later reorganization.

## What is next

The ranked workflow spec will land at `testing/Product_workflows.md`. It does not exist yet, and this README does not guess at what it will say.
