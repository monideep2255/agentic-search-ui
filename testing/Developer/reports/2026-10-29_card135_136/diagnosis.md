# Cards 135 and 136: diagnosis

Read-only diagnosis of the six defects on cards 135 (a reopened saved answer) and 136 ("Your searches"), written 2026-10-29 for the overnight run. No source was edited, no live model was called, and the deployed develop app was read with plain GETs only. Evidence: `testing/Developer/reports/2026-10-18_browser_retest/report.md`, rows 18, 21, 24, 34 and 35 and the "Defects seen that no row covers" table; the board rows are `testing/UI_fix_plan.md` lines 79 and 80. Source read at commit `46f23485`, identical to develop for source.

## Table of contents

- [Summary](#summary)
- [The owner's decisions that bound these fixes](#the-owners-decisions-that-bound-these-fixes)
- [Card 135: a reopened saved answer](#card-135-a-reopened-saved-answer)
- [Card 136: your searches](#card-136-your-searches)
- [Build slices](#build-slices)
- [What was run](#what-was-run)

## Summary

| Defect | Cause in one line | Fix in one line | Migration, stored data or owner decision | Build tonight |
|---|---|---|---|---|
| 135.1 OMIM "Not linked" | The web's citation host list never gained `omim.org`, which the server has admitted since 2026-09-20 | Add `omim.org` and `www.omim.org` to the one host list, with a test that holds it to the server's pattern | None | Yes |
| 135.2 Raw tool names | The saved screen labels a source `entity_name ?? source` and drops the record id; `source` is a tool name for many Layer 2 findings | One shared label helper that names the database from the record page and keeps the id, used by the live and saved screens | None; changes labels on the live screen too, so product review at 1280 and 390 | Yes |
| 135.3 Plain "[1]" and `[1][2]...[20]` | The saved renderer prints the stored markdown's `[n]` markers as text; the live screen strips them and renders superscript markers | Render each run of known `[n]` markers through the live `CitationMarkers` component | None | Yes |
| 136.1 Only 20 searches | The rail fetches `GET /v1/history` once with the default `limit` of 20, and the endpoint has no paging | Add an optional `before=<trace_id>` cursor and `has_more`, and a "Show older searches" control at the foot of the list | None; additive API field, judge and adversary for the cursor | Yes, after 136.3 |
| 136.2 Guest searches read "No answer saved" | A guest's answer is never stored (owner, 2026-09-22), and sign-in moves the row to the account with its answer column still empty | Owner question below; recommended: at sign-in, save the answers the server still holds for that guest's just-finished searches | Owner decision; touches the sign-in path | No |
| 136.3 Drawer stays open at phone width | Picking a row calls `onOpen` only; nothing closes the temporary drawer | At phone width the rail closes itself after a row or "+ New search" is picked | None | Yes |

## The owner's decisions that bound these fixes

| Date | Decision, quoted or summarised from `DECISIONS.md` | What it constrains |
|---|---|---|
| 2026-09-20 | "REVERSES the row above: widen the citation host rule so OMIM can be cited, and dispatch OMIM in the broad search" (product owner). The server pattern admits `omim.org` and `www.omim.org` as exact hosts only, never a subdomain | 135.1: the web list must add exactly those two hosts, nothing wider |
| 2026-09-22, recorded 2026-09-23 | "A saved answer is stored for SIGNED-IN ACCOUNTS ONLY, excluded at the WRITE in three independent layers"; the owner's decision "was accounts only, deleted with the account". A database CHECK constraint enforces it (`alembic/versions/0010_interactions_saved_answer.py:142` to `146`) | 136.2: storing a guest's answer while they are a guest reverses this and needs a migration |
| 2026-09-27 | "A 'not yet confirmed' answer is saved like a confirmed one, so every answered search can be reopened" | 136.2: the intent is that every answered search reopens |
| 2026-10-07 | Card 102: a reopened answer reads stored citations "through the live answer's own mapping ... so the live and saved screens cannot drift apart again" | 135.2 and 135.3: reuse the live helpers, never a second copy |
| 2026-10-09 | Card 109: a row with no saved answer reads "No answer saved" so "a person scanning their history wants to know which row opens an answer" | 136.2: the words stay true; the fix is to have the answer, not to change the words |
| 2026-08-27 | `GET /v1/history` refuses a `limit` above 50 with a 422, never a silent clamp | 136.1: paging adds a cursor; it does not raise or clamp the limit |
| 2026-09-13 | Below `md` the rail is "a LEFT-ANCHORED TEMPORARY DRAWER ... with a close control, backdrop and Escape all routed through the existing collapse path" (product-owner decision U9) | 136.3: closing after a pick goes through the same `onCollapse` path |

## Card 135: a reopened saved answer

### 135.1 The OMIM source reads "Not linked"

What the person sees: on a reopened answer the OMIM row shows red text, "Not linked: this URL is not on a recognised NCBI host.", and no link.

Cause:

- `frontend/src/components/answer/CitationMarkers.tsx:101` to `108` lists six hosts: NCBI, its `www`, `pubmed` and `pmc` subdomains, and `clinicaltrials.gov` with its `www`. No `omim.org`.
- `isLinkableCitationUrl` (`CitationMarkers.tsx:111` to `118`) links a URL only on those hosts. `SavedAnswerScreen.tsx:140` and `:196` to `202` print the "Not linked" line for anything else.
- The server's citation contract has admitted OMIM since the owner's 2026-09-20 decision: `src/system_03_search_agent/contracts/events.py:186` to `192`, `(?:www\.)?omim\.org/`. OMIM records are built as `https://omim.org/entry/{id}` (`src/system_03_search_agent/tools/ncbi_eutils_actions.py:499`). The web list was never updated, and no test ties the two together.
- The live screen has the same defect, hidden: its source card is a closed `<details>` and its "Record" row (`AnswerScreen.tsx:2529` to `2553`) and the marker card (`CitationMarkers.tsx:396` and `:447`) both use the same check. The saved screen prints the link line openly, which is why the retest saw it only there.

Fix, from the person's chair: the OMIM row opens the OMIM entry, on the reopened answer, in the live source card and in the marker card.

- Add `"omim.org"` and `"www.omim.org"` to `ALLOWED_CITATION_HOSTS`. Exact hosts, matching the 2026-09-20 decision; no subdomain wildcard.
- Files: `frontend/src/components/answer/CitationMarkers.tsx`.
- Tests:
  - `frontend/src/components/answer/CitationMarkers.test.tsx`: `https://omim.org/entry/113705` and `https://www.omim.org/entry/113705` are linkable; `https://sub.omim.org/...`, `http://omim.org/...` and `https://omim.org.evil.example/...` are not.
  - A backend test in `tests/system_03_search_agent/contracts/` that reads the host list out of `CitationMarkers.tsx` and checks it against `NCBI_SOURCE_URL_PATTERN` both ways, the precedent being card 23's test that holds `VARIANT_TABLE_SOURCE_NOTE_PREFIX` to the shipped constant (`DECISIONS.md`, 2026-10-07). This is the test that would have caught the drift.
  - Mutation: removing either new host turns the first test red.

Stops: none. No migration, no stored data, no auth, no event schema, no owner decision; the owner already decided OMIM is citeable.

Size: extra small, about ten lines plus two tests. Build tonight: yes.

### 135.2 Sources carry raw tool names

What the person sees: the reopened Sources list reads "ncbi_efetch LIVE", "clinicaltrials.gov LITERATURE", and on query 33 twenty rows each reading only "pathogen_detection LIVE" (`screens/R_390_reopened_source_links_wrap.jpg`), so the rows cannot be told apart without reading the link.

Cause:

| Where | What it does |
|---|---|
| `frontend/src/components/screens/SavedAnswerScreen.tsx:141` | `const label = citation.entity_name ?? citation.source;` drops `source_id` |
| `SavedAnswerScreen.tsx:169` and `:175` | Prints the label, then the layer word upper-cased: "ncbi_efetch LIVE" |
| `frontend/src/hooks/useRunView.ts:613` | The live screen names the same citation `sourceDisplayName(source, source_id)` (`useRunView.ts:173`), so live reads "pathogen_detection SAMN00715300" |
| `src/system_03_search_agent/core/graph.py:12578` and `:12746` | A Layer 2 finding's citation sets `source=synth_finding.tool`, a tool name such as `ncbi_efetch` |
| `src/system_03_search_agent/tools/pathogen_detection.py:1501`, `tools/clinicaltrials_search.py:664` | These tools set `source` to `"pathogen_detection"` and `"clinicaltrials.gov"` |

So there are two layers to the defect:

- The saved screen differs from the live one: it drops the record id, so identical labels repeat.
- Both screens show tool names for these sources; the live one adds the id. `useRunView.ts:158` to `164` left the display casing "for the design card to settle", and it never was.

The server already has a reader-facing database name for every record page: card 8's table in `src/system_03_search_agent/synthesis/trust.py:615` to `650` (`_NCBI_DATABASE_NAMES` and `_DATABASE_NAMES`), keyed by `record_database` (`trust.py:537`), which reads the database off the record page. That is how the trust line says "from ClinVar and OMIM".

Fix, from the person's chair: every source names its database and record in words they know, "Pathogen Detection SAMN00715300", "OMIM 113705", "ClinicalTrials.gov NCT01234567", and the reopened list reads exactly like the live one.

- One helper in `frontend/src/hooks/useRunView.ts`, beside `sourceDisplayName`: the database name read off the record page with the same keys and names as `trust.py`'s table, then the bare record id (the existing CURIE-prefix strip kept). When the page names no known database, it falls back to today's `sourceDisplayName` output, never a guess.
- The live source list (`useRunView.ts:613`), the marker card (it reads the same `name`) and the saved list (`SavedAnswerScreen.tsx:141`) all call it. `entity_name`, when present, can follow the id as it does today on the saved screen; the builder keeps whichever of the two the live screen shows, so the two screens agree.
- Files: `frontend/src/hooks/useRunView.ts`, `frontend/src/components/screens/SavedAnswerScreen.tsx`.
- Tests:
  - `useRunView.sourceName.test.ts` gains one case per table key, plus an unknown host falling back.
  - `SavedAnswerScreen.card102.test.tsx` gains a stored Layer 2 `pathogen_detection` citation and a `clinicaltrials.gov` one, run through the real `fetchHistoryAnswer` parser into the real screen (card 102's lesson), asserting the label equals the live screen's for the same payload.
  - A backend test holds the web table to `trust.py`'s `_DATABASE_NAMES`, both ways.

Stops:

- No migration, no stored data, no auth, no event schema.
- It changes labels on the live answer screen as well. That is within the lead's remit under the user's-chair rule (one kind of reader, no split between users), but it is a visible change to the main screen, so it needs the product reviewer at 1280 and 390, and the owner's retest row should say the live labels changed too.

Size: small to medium, about 60 lines plus tests. Build tonight: yes.

### 135.3 Citations show as plain "[1]" or a run `[1][2]...[20]`

What the person sees: the reopened summary ends "... Escherichia coli [1][2][3][4]...[20]." as literal text, and tables and bullets show "C236-11 [1]" and "TP53[3]". The live answer shows one small superscript range marker, 1 to 20, that opens a card listing every source.

Cause:

- The stored answer is markdown with the markers written in as text. `src/system_03_search_agent/feedback/capture.py:105` to `115` (`_markers_for`) appends `[n]` runs to table first cells (`:229` to `:232`) and list items (`:226`, `:238`), and claim text keeps its own inline `[n]` (`:240` to `:244`).
- `frontend/src/components/screens/savedAnswerMarkdown.tsx` never reads markers: paragraphs render `{block.text}` (`:338`, `:360`), list items `{item}` (`:352`), table cells `{cell}` and `{row[0]}` (`:267`, `:310`).
- The live screen strips exactly the `[n]` numbers the token cites (`frontend/src/hooks/useRunView.ts:855` to `864`, the R-05 rule: never strip a bracketed number by pattern alone) and renders `CitationMarkers` (`frontend/src/components/answer/CitationMarkers.tsx:481`), which collapses four or more into one marker (`collapseCitations`, `:126`).
- `SavedAnswerScreen.tsx:316` passes only the markdown to the renderer, not the citations, so it could not render a marker card even if it tried.

Fix, from the person's chair: the reopened answer's citations look and work like the live ones: small superscript numbers, a run of twenty becomes one range marker, 1 to 20, and pressing one opens the same card with the source and its link.

- `SavedAnswerScreen` passes `answer.citations` to `SavedAnswerMarkdown`, converted to `CitationSource` (`n`, `layer`, `name` from 135.2's helper, `tool`, `url`).
- In paragraphs, list items and a table's first cell, a run of `\s*[n]` markers is replaced by one `CitationMarkers` element only when every `n` in the run is a stored citation's `display_index`, the saved-answer form of R-05. Any other bracketed number stays as text.
- A marker followed by sentence punctuation moves after it, so "cavity [13]." reads "cavity." then the marker, as live.
- Files: `frontend/src/components/screens/savedAnswerMarkdown.tsx`, `frontend/src/components/screens/SavedAnswerScreen.tsx`.
- Tests:
  - `savedAnswerMarkdown.test.tsx`: the existing twenty-marker fixture (`:32`) renders one range marker, `markerLabel([1..20])`, and no "[" in the text; "study [12]" with no citation 12 stays as text.
  - `savedAnswerMarkdown.card71.test.tsx:60`, `:91` and `:92` pin "Iso-1 [1]" as text today; they change to assert a marker in the first cell.
  - `App.savedAnswer.test.tsx`: the stored shape through the real parser into the real screen, pressing a marker opens its card with a link.
  - Mutation: rendering raw text again turns them red.

Stops: none. No migration and no change to stored data: old and new rows already hold markers in this form, so every saved answer gains the fix at once. Not auth, not the event schema.

Size: medium, about 120 lines plus tests. Build tonight: yes.

## Card 136: your searches

### 136.1 Only the latest 20 show, with no way to reach older ones

What the person sees: "Your searches" lists 20 rows. Older searches are stored but cannot be reached from the screen.

Cause:

| Where | What it does |
|---|---|
| `frontend/src/App.tsx:716` | `fetchHistory(token, { signal })` once per token, no `limit`, so the server default |
| `src/system_03_search_agent/feedback/history.py:84`, `:89`, `:308` | `DEFAULT_LIMIT = 20`, `MAX_LIMIT = 50`, a real SQL `LIMIT`, newest first by `created_at DESC, id DESC` |
| `src/system_03_search_agent/adapters/web_sse/app.py:1041` to `1045` | `limit` is the only parameter; the response is `{items, count, omitted_count}`; its docstring (`:948` to `:955`) records "There is no cursor" as a known gap from F-4.13-A-09 |
| `frontend/src/App.tsx:275` and `:1447` | `HISTORY_LIST_LIMIT = 20`; every new ask trims the in-tab list back to 20 |
| Deployed develop | `GET /openapi.json` on the develop API shows `limit` (1 to 50, default 20) as the only parameter and `items`, `count`, `omitted_count` as the only fields |

Fix, from the person's chair: at the foot of the list a "Show older searches" control loads the next 20, as many times as they have searches; it disappears when there are no more.

- Backend: `list_history(owner_id, limit, before=None)`. `before` is a `trace_id` (unique, `src/system_03_search_agent/data/models.py:176`). The server looks up that row's `(created_at, id)` for this same owner and returns rows strictly older, using the existing `(owner_id, created_at DESC, id DESC)` index from migration 0009. A `before` that is not this caller's row returns an empty page, the same posture as the saved-answer endpoint's single 404 for three causes.
- Fetch `limit + 1` rows to set `has_more`. `GET /v1/history` gains an optional `before` query parameter and a `has_more: bool = False` field. Both are additive within v1, and the MCP caller (`adapters/mcp/server.py:1535`) is unchanged.
- Frontend: `fetchHistory` takes `before`. `App.tsx` appends the older page through `mergeServerHistory`, which already dedupes by `trace_id`. The trim at `App.tsx:1447` keeps every loaded row, trimming only the first page. `HistoryRail` shows the control when `has_more`, styled as the rail's existing "+ New search" text button so no new design is invented.
- Files: `src/system_03_search_agent/feedback/history.py`, `src/system_03_search_agent/adapters/web_sse/app.py`, `frontend/src/lib/api.ts`, `frontend/src/App.tsx`, `frontend/src/components/answer/FollowUp.tsx`.
- Tests:
  - `tests/system_03_search_agent/feedback/test_history.py`: 45 rows page into 20, 20 and 5 with no row twice and none lost, including six rows on one timestamp (the existing total-order fixture); `has_more` is false on the last page; another owner's `trace_id` as `before` returns nothing.
  - The endpoint tests: a duplicate `before` is refused like a duplicate `limit`.
  - A new `App.historyPaging.test.tsx`: the control loads and appends, then disappears.

Stops:

- No migration and no stored data.
- Not auth, but it changes a REST response and adds a parameter that reads by an id the caller supplies. That is an owner-scoping surface, so a judge and an adversary review it.
- No owner decision: one kind of reader, and the 2026-08-27 limit decision is untouched.

Size: medium, about 150 lines plus tests across the server and the web. Build tonight: yes, after 136.3, since both edit `FollowUp.tsx`.

### 136.2 Guest searches carried in at sign-in read "No answer saved"

What the person sees: they ask a question as a guest, get a full answer, then sign in to keep it. Before a reload the row reads "13 tool calls · 21 sources cited". After a reload the same row reads "No answer saved". Opening it runs the search again, as a new search.

Cause:

- Capture writes an answer only for an account: `src/system_03_search_agent/feedback/capture.py:520`, `if owner_id.startswith("user:") and trust_signal in _SAVEABLE_OUTCOMES`.
- The database forbids a stored answer on a guest row: `alembic/versions/0010_interactions_saved_answer.py:142` to `146`, `answer_markdown IS NULL OR left(owner_id, 5) = 'user:'`. This is the owner's decision of 2026-09-22.
- At sign-in, `src/system_03_search_agent/auth/router.py:415` (`_migrate_guest_session`) re-points the guest's in-memory runs (`:496` to `:500`) and their stored rows (`:528` to `:532`, through `src/system_03_search_agent/feedback/writer.py:579` to `585`). It moves `owner_id` and `user_id` only, so `answer_markdown` stays NULL.
- `GET /v1/history` then reports `has_saved_answer: false` (`feedback/history.py:318`), and the rail prints "No answer saved" (`frontend/src/App.tsx:285`).
- The server does still hold a just-finished run's events: the run registry keeps a finished run for five minutes (`src/system_03_search_agent/core/run_registry.py:182`, `DEFAULT_RETENTION_SECONDS = 300.0`), and `answer_markdown_from` (`capture.py:118`) builds the saved answer from exactly those events.

Owner question. Recommendation first:

| Option | What the person sees | Cost |
|---|---|---|
| A, recommended: save at sign-in what the server still holds | A search asked as a guest within five minutes before signing in reopens like any other. The retest's case, ask then sign in to keep it, is this one. Older guest searches still read "No answer saved" and open as a new search | No migration: once the row is the account's, the CHECK constraint allows the answer. It changes the sign-in path (`auth/router.py`) and writes answers onto rows at sign-in, so it takes the highest review position: judge, adversary, and a check that a guest token can only fill its own rows. About 120 lines. It stores, under the account, an answer produced while a guest, which the 2026-09-22 decision did not foresee; within its spirit (accounts only, deleted with the account) but the owner's to confirm |
| B: store every guest answer, keep it only if claimed | Every guest search reopens after sign-in, however old | A migration dropping or changing `ck_interactions_answer_account_only`, and a reversal of the 2026-09-22 decision: guest answers sit on disk for people who never sign up, which needs a retention period and a clean-up job. A hard stop tonight |
| C: change only the words | Carried-in rows read differently, for example "Asked before you signed in · opens a new search" | No server change of substance, but no column marks a row as carried in from a guest, so telling those rows apart needs a marker; and the person still loses the answer. Lowest value |

Files for option A: `src/system_03_search_agent/auth/router.py`, `src/system_03_search_agent/core/run_registry.py` (a read of the reassigned finished entries), `src/system_03_search_agent/feedback/writer.py` (an UPDATE that fills only rows whose answer is NULL, matched by `trace_id` and the new owner), and `capture.py`'s existing builders reused.

Tests:

- `tests/system_03_search_agent/auth/test_router.py`: a guest run finished, then sign-in; the row has an answer equal to what capture would have stored for an account.
- A run evicted before sign-in leaves NULL.
- A second guest's token cannot fill the first guest's rows.
- Sign-in still returns 201 or 200 when the fill raises.

Stops:

- Option B needs a database migration and reverses an owner decision: a hard stop tonight.
- Option A touches auth and needs the owner's yes.

Size: option A medium, option B large. Build tonight: no, because it needs an owner decision and option A sits on the sign-in path.

### 136.3 At phone width, picking a search leaves the drawer open over the answer

What the person sees: on a phone they open "Your searches", tap a past search, and the panel stays over the answer they asked for; they must tap the backdrop or the close control to read it.

Cause:

- `frontend/src/components/answer/FollowUp.tsx:691`: a row's `onClick` calls `onOpen?.(item.id)` and nothing else.
- Below `md` the rail renders inside a temporary `Drawer` that is `open` while mounted and closes only through `onClose={onCollapse}` (`FollowUp.tsx:808` to `813`), a backdrop tap or Escape.
- `App.tsx:2248` to `2275` (`onOpen`) and the rail's `onNewSearch` (`App.tsx:2277` to `2284`) change the screen but never call `setRailOpen(false)`. "+ New search" in the drawer has the same defect.
- `HistoryRail.phone.test.tsx:58` to `77` tests opening and the close button, never a pick.

Fix, from the person's chair: on a phone, tapping a past search or "+ New search" closes the panel and shows the answer. On desktop nothing changes; the rail stays open beside the answer.

- In `HistoryRail`, when `isNarrow` (`FollowUp.tsx:533`), a row click calls `onOpen(id)` then `onCollapse()`, and "+ New search" calls `onNewSearch()` then `onCollapse()`. This is the same collapse path decision U9 routes every close through, so focus returns as MUI's drawer already handles.
- Files: `frontend/src/components/answer/FollowUp.tsx`.
- Tests:
  - `HistoryRail.phone.test.tsx`: at phone width a row click calls `onOpen` once and `onCollapse` once, and "+ New search" likewise.
  - At desktop width a row click calls `onOpen` and never `onCollapse`.
  - Mutation: dropping the collapse turns the phone case red.

Stops: none. No migration, no stored data, no auth, no owner decision.

Size: extra small, about ten lines plus tests. Build tonight: yes.

## Build slices

Slices are fenced by the files each one edits. Two slices may run in parallel only when their file sets do not meet.

| Slice | Defects | Files it edits | Review position | Tonight |
|---|---|---|---|---|
| S1 OMIM link | 135.1 | `frontend/src/components/answer/CitationMarkers.tsx`, its test, one new backend contracts test | Builder and fresh verifier | Yes |
| S2 Saved answer reads like live | 135.2, 135.3 | `frontend/src/hooks/useRunView.ts`, `frontend/src/components/screens/SavedAnswerScreen.tsx`, `frontend/src/components/screens/savedAnswerMarkdown.tsx`, their tests, `frontend/src/App.savedAnswer.test.tsx`, one new backend parity test | Builder, judge, product review at 1280 and 390 (live labels change too) | Yes |
| S3 Phone drawer closes | 136.3 | `frontend/src/components/answer/FollowUp.tsx`, `HistoryRail.phone.test.tsx` | Builder and fresh verifier | Yes |
| S4 Older searches | 136.1 | `src/system_03_search_agent/feedback/history.py`, `src/system_03_search_agent/adapters/web_sse/app.py`, `frontend/src/lib/api.ts`, `frontend/src/App.tsx`, `frontend/src/components/answer/FollowUp.tsx`, their tests | Builder, judge and adversary (an id the caller supplies) | Yes, after S3 merges |
| S5 Guest answers at sign-in | 136.2 | `src/system_03_search_agent/auth/router.py`, `src/system_03_search_agent/core/run_registry.py`, `src/system_03_search_agent/feedback/writer.py`, their tests | Owner decision first, then the highest position, the sign-in path | No |

What can run at once:

- S1, S2 and S3 share no file and can be built in parallel. S2 imports `CitationMarkers` and `isLinkableCitationUrl` from S1's file but does not edit it, so S2's OMIM row links once S1 lands, and neither waits on the other.
- S4 edits `FollowUp.tsx` with S3 and is the largest slice, so it starts once S3 merges, or takes S3's ten lines into itself if one builder holds both.
- S5 waits for the owner's answer on option A, B or C, and if B, for a migration window that is not tonight.

## What was run

| Check | Result |
|---|---|
| `npx vitest run` on `SavedAnswerScreen.test.tsx`, `savedAnswerMarkdown.test.tsx`, `HistoryRail.phone.test.tsx`, `App.historyNoAnswer.test.tsx` | 4 files, 36 tests passed: the defects are untested, not failing tests |
| `venv/bin/python -m pytest tests/system_03_search_agent/feedback/test_capture_saved_answer.py` | 36 passed |
| `GET /openapi.json` on the develop API | `/v1/history` takes only `limit` (1 to 50, default 20); the response is `items`, `count`, `omitted_count` |
| `GET /v1/history` on the develop API with no credential | 401, as designed |
| Retest screenshot `screens/R_390_reopened_source_links_wrap.jpg` | Reopened rows read "2. pathogen_detection LIVE" with no record id, confirming 135.2 |
