# Card 8 diagnosis: the trust-line wording

Diagnosed against develop `78c68c1c`, 2026-10-16. Read-only; nothing was built. Board row: item 9.9, "You chose, 2026-09-25: say what was checked", planned as phase 8.9 ticket T-8.9-05 from parked commit `90b018eb` with "which differ" corrected.

## Table of contents

- [Status today](#status-today)
- [What a person sees](#what-a-person-sees)
- [The cause](#the-cause)
- [What "which differ" corrected means](#what-which-differ-corrected-means)
- [Wording before and after](#wording-before-and-after)
- [Does the saved diff still apply](#does-the-saved-diff-still-apply)
- [The smallest fix](#the-smallest-fix)
- [Tests](#tests)
- [Overlap with tonight's other cards](#overlap-with-tonights-other-cards)
- [Needs the owner](#needs-the-owner)
- [Test query](#test-query)

## Status today

- The problem still happens. About 57 of 102 answered golden runs read "not yet confirmed" and none read "Confirmed" (`testing/Developer/reports/2026-09-25_harness_review/product_harness.md`, W4), measured before card 22. Card 22's merge changed only the count and added the word "cited".
- No part of the owner's choice (`DECISIONS.md` row of 2026-09-25, "The trust line says what was checked", and row 697) is built on develop. Phase 8.9 is "planned, not opened" (`tracker/phase_8.9.md`).
- The trust line is still built in one place: `src/system_03_search_agent/synthesis/trust.py` `answer_trust_line`, called once at `src/system_03_search_agent/core/graph.py:15353`.

## What a person sees

- Under a gene question such as `Which diseases are associated with BRCA1?` the line reads "Based on 16 sources cited, not yet confirmed". It sounds like a warning, and it reads the same whether the answer rests on one database, on six that were never compared, or on an answer that may be incomplete.
- The status word above it already says "Answered" when a line is present (`frontend/src/hooks/useRunView.ts:1191` to `1200`), so the two disagree in tone.
- A saved answer that is reopened shows the stored line, so old rows keep the old wording (`frontend/src/components/screens/SavedAnswerScreen.tsx:333`). That stays honest and needs no change.

## The cause

| Link | Evidence |
|---|---|
| Every high-risk claim needs two independent origins whose values fall in the same bucket | `synthesis/trust.py:372` to `402` (`triangulate`) |
| The bucket table holds seven clinical-significance words and no disease names | `synthesis/trust.py:343` (`bucket_for`), harness review W4 |
| So a disease row is `insufficient`, and `insufficient` decides `ask` | `synthesis/trust.py:408` to `415` (`DECISION_TABLE`) |
| The line words every `ask` the same way | `synthesis/trust.py:723` to `726`, `Based on {n} {noun} cited, not yet confirmed` |
| Floors also produce `ask` with no comparison failure at all (fallback list, failed search, omitted records, unaddressed entity) | `core/graph.py:14372`, `14393`, `14553`, `7151` |
| A low-risk claim is also marked `insufficient` by design | `synthesis/trust.py:451` to `458`, so "insufficient" alone cannot mean "a comparison failed" |

## What "which differ" corrected means

- The parked commit worded an `ask` over two or more databases as "from M databases, which differ".
- "Differ" is false. The trust code names a real disagreement `discordant`, and that maps to `flag`, which already has its own line "Sources disagree on at least one claim" (`DECISION_TABLE`, `trust.py:413`). An `ask` is never a found disagreement.
- In an `ask` from several databases, the values were not compared at all, because they sit outside the bucket table (`trust.py:397` to `400`, "Insufficient, never a guess in either direction"). The owner's row 733 therefore replaces "which differ" with "their values could not be compared".
- It also overreaches for answers whose `ask` comes from a floor, where nothing failed to compare. The comparison clause must be conditional (below).

## Wording before and after

Today is `78c68c1c`. After is the recommended re-cut. N is distinct cited pages (card 22's `source_page_key`), unchanged.

| State | Today | After |
|---|---|---|
| Refuse, or nothing grounded | no line | unchanged |
| `flag` | "Sources disagree on at least one claim" | unchanged |
| `answer`, high-risk facts concordant, every one backed by 2 or more databases | "Confirmed by N independent databases" | unchanged. The phase 8.9 plan writes "sources" here; card 22 made it "databases" and that stays |
| `answer` with all claims low risk | "Based on N sources cited" | "Based on N sources cited, all from MedGen" or "Based on N sources cited from MedGen and OMIM" |
| `answer`, high-risk concordant but under 2 databases | "Based on N sources cited, not yet confirmed" | the same database naming, no clause |
| `ask`, one database | "Based on N sources cited, not yet confirmed" | "Based on N sources cited, all from MedGen". With one source: "Based on 1 source cited, from MedGen" |
| `ask`, two or more databases, a high-risk claim `insufficient` | "Based on N sources cited, not yet confirmed" | "Based on N sources cited from MedGen and OMIM; their values could not be compared" |
| `ask`, two or more databases, from a floor only | "Based on N sources cited, not yet confirmed" | "Based on N sources cited from MedGen and OMIM", no clause |
| Four or more databases | not applicable | the three most cited, then "and N other databases" |

Phase 8.9's example text "Based on 4 sources, all from MedGen" lacks the word "cited". After card 22 the "Based on" lines say "sources cited" on purpose (row 880), so keep it, or the line goes back to the 17 against 16 disagreement card 22 closed.

## Does the saved diff still apply

- `git apply --check` against develop (it modifies nothing): the `contracts/events.py` hunk applies; the `trust.py` hunk fails at line 561; the `test_answer_layout.py` hunk fails at line 315. The new `builder_F.md` file does not need to come back.
- The trust hunk fails because card 22 rewrote the branch to add "cited" and rewrote the docstring. The diff's other branch ("from M databases") also counts databases with `_origin_database`, which the card 22 fix round replaced with `record_database`, a page-based key (`trust.py:536` to `580`). Resurrecting the old count would show a graph ClinVar row and a live ClinVar fetch as two databases again.
- So: re-cut by hand. Only the events.py comment hunk is worth keeping, and its example needs "Based on 1 source cited, all from MedGen".
- Stale items in the plan's T-8.9-05 to correct when it is opened:
  - It keys database names by CURIE prefix, then tool. Use `record_database` instead.
  - It says "Confirmed by N independent sources". Today it is "databases".
  - It says to add the clause when "a high-risk claim's triangulation came back insufficient". Filter on `risk_tier == "high"`, because low-risk claims are also marked `insufficient`.
  - It lists frontend fixtures at old line numbers. Re-find by text.

## The smallest fix

| Item | Value |
|---|---|
| What changes in the person's words | Every "Based on" line names the databases behind it; "not yet confirmed" is gone; the comparison clause shows only when a high-risk fact could not be compared across two or more databases |
| File fence | `synthesis/trust.py` (`answer_trust_line` plus one new naming helper and a closed display table keyed by `record_database` output, such as `ncbi.nlm.nih.gov/medgen` to MedGen, `omim.org` to OMIM, `ncbi.nlm.nih.gov/pubmed` to PubMed; an unknown key counts under "other databases", never printed); `contracts/events.py` comment line 615 only; `frontend/src/lib/events.ts:291` comment; frontend `TRUST_LINE_EXPLAINER` in `AnswerScreen.tsx:134` (its "Not yet confirmed means" sentence now describes a phrase that no longer shows); frontend and Python test fixtures that pin the old text |
| Answer path | Yes, the line under every answer. No verdict changes |
| Dial | 1, wording only. `decide`, `DECISION_TABLE`, `triangulate`, `aggregate` and `core/graph.py` stay byte-identical. The status word, the tone and the "Confirmed" check mark (`useRunView.ts:1015`, `SavedAnswerScreen.tsx:335`) key on the first word "Confirmed" and are unaffected |
| Size | M: about 70 lines in `trust.py`, plus about 20 test and fixture files because the old text is pinned widely |
| Migration, package, event schema, setting | None. `DonePayload.trust_line` stays capped at 200 characters; the three-database limit keeps it under that. Stored lines in old saved rows stay as written |

Ways it could make an answer worse than today, and the catch:

- A line over 200 characters would fail event validation and could lose the done event. A property test over the whole table and every database combination catches it.
- A wrong database name (a key mapped to the wrong name, or an unmapped host printed raw). A sweep test over every key `record_database` can return catches it.
- The comparison clause shown on a floor `ask` would say something false. A test per floor, with all-low-risk and mixed claims, catches it.
- A line starting "Confirmed" must stay the only one that does. A test asserts no other branch starts with that word.
- The CLI, MCP and GraphQL pass the text through (`adapters/cli/render.py`, `adapters/mcp/server.py:455`); nothing there parses it, but their tests pin the old text and would fail until updated.

## Tests

- New `tests/system_03_search_agent/synthesis/test_trust_line.py`, one test per row of the table above, plus the 200-character property test, the sweep over `record_database` keys, and "no branch contains 'not yet confirmed' or 'which differ'". These fail on develop.
- Update the tests that pin the old text under `tests/system_03_search_agent/synthesis/test_answer_layout.py:329` and `:347`, `test_trust_line_names_its_count.py` (lines 110, 111, 259 to 321, 591), and the pass-through fixtures in `tests/system_03_search_agent/adapters/` (cli, graphql, mcp) and `feedback/`.
- Frontend: `AnswerScreen.card22.test.tsx:234`, `:375` to `:377`, `SavedAnswerScreen.test.tsx`, `riskTag.parity.test.tsx:89`, `set9AnswerStructure.test.tsx`, `answerLayout.test.tsx`, `answerPagination.test.tsx`, and the e2e fixtures.

## Overlap with tonight's other cards

| Card | Fence | Overlap with card 8 |
|---|---|---|
| 30 | `synthesis/answer_layout.py` a note; `core/graph.py` Think, `_write_answer`, trust floor to `ask` | The floor makes a BRCA1 variants answer `ask` with nothing failed to compare. With the new wording that answer reads "Based on N sources cited, all from ClinVar", no clause, and card 30's own note carries the caveat. Without card 8 it reads "not yet confirmed", which is a blunt stand-in for that caveat. The two are independent in code, since card 8 only reads `trust_outcome` and `claim_trusts`. But card 30 must set the floor through `trust_outcome` and not by marking a claim `insufficient`, or card 8 would add the false clause. Merge order is free |
| 105 | date window and graph papers | None in code. A graph paper's page host decides its database name; PubMed pages must key to PubMed |
| 37, 38 | records carry the field asked for | None in code. New fields change findings, not the line, unless they change risk tiers, which must not happen in the line's file |
| 18 | `core/graph.py` `_answer_tokens` | None. Card 8 does not touch `core/graph.py` |

Card 8 shares only `trust.py` with no other card tonight, and `answer_layout.py` only through a test file.

## Needs the owner

| Choice | Options | Recommendation |
|---|---|---|
| Name the databases or only count them | Names (the owner's own examples): clearer, needs a display table. Counts only ("from 2 databases"): smaller, no table | Names, as the owner wrote in row 733 |
| The comparison clause's wording when a fact has one database among several | "their values could not be compared" (owner's words); or "no second database stated the same fact", more exact when one claim has no counterpart | Keep the owner's words; reconsider only if the retest finds it misleading |
| The "Not yet confirmed" paragraph of the explainer card | Rewrite to describe the new lines; or remove | Rewrite; it is copy under the same item |

None of these changes which answers appear or the verdict; the first is the only one a reader would weigh visibly.

## Test query

No query covers the new wording. Query 100 (`testing/Test_queries_and_workflows.md:1203`) says a saved answer's line reads "not yet confirmed" and query 74 (`:1534`) covers the count agreeing with the Sources list. Both need their text updated when this lands. Proposed new entry in the file's shape:

### The trust line says what was checked (card 8, item 9.9)

Queries to try:

- `Which diseases are associated with BRCA1?`
- `GERD`

What you should see:

- The line under the answer names the databases behind it, for example "Based on 16 sources cited from MedGen and OMIM; their values could not be compared". The count equals the Sources heading.
- It never says "not yet confirmed" or "which differ".
- A line starting "Confirmed by N independent databases" still shows its check mark, and nothing else does.
