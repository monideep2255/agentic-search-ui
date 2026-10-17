# Card 18 adversary: one row per record

Adversary round, 2026-10-16, pull request #258, branch `fix/card18-one-row-per-record`, commit `4469c901` on develop `78c68c1c`. Paths are relative to `<repo-root>`; probes sit in `<scratchpad>/card18_adv/` and are not committed. The question: does this branch show any person, for any question, something worse than develop shows today?

## Table of contents

- [Scope and method](#scope-and-method)
- [Findings](#findings)
- [Probes](#probes)
- [Live runs](#live-runs)
- [Verdict](#verdict)

## Scope and method

- Read: `diagnosis.md`, `build.md`, `git diff origin/develop...HEAD` (one hunk in `core/graph.py` inner `merge_into`, three tests).
- Compared every probe on two trees: the branch worktree and a develop worktree at `78c68c1c`, through `_answer_parts` and `_answer_tokens` with made-up findings.
- Surfaces checked by reading their code: web rows (`AnswerScreen.tsx`), saved answer (`feedback/capture.py` `answer_markdown_from`), command line (`adapters/cli/render.py`), MCP (`adapters/mcp/server.py`), GraphQL (`adapters/graphql/fold.py`), citation `claim_text` (`core/graph.py` `_citations_from_grounded_claims`).

## Findings

Filed as found.

### A-18-01: MCP and GraphQL answers lose the folded sentence too, and the owner's decision names only the command line

- Severity: minor (a scope gap in the decision, not a defect in the code).
- Worse than develop: yes in the strict sense, on two surfaces the decision does not name; the same loss class the owner accepted for the command line.
- Evidence: MCP builds `answer` as the plain join of every token's text, `raw_answer_text = joined_text(answer_parts).strip()` (`adapters/mcp/server.py:1270`); GraphQL does the same, `answer_text = joined_text(acc.answer_parts).strip()` (`adapters/graphql/fold.py:1103`); the evaluation trace too (`eval/trace_source.py:219`). Probe S1 at both depths: develop's joined text carries sentences a, b and c; the branch's carries a and b. The diagnosis's surface table (`diagnosis.md`, "What each surface prints after the fix") lists web, saved answer and command line only, and the decision reads "the command line prints the record's first sentences and not the later one ... the web and saved answers lose nothing".
- In the person's words: an agent asking through MCP gets the paper once with its first sentences, not the later repeat sentence. Citation numbers are unchanged (probe S1: joined markers `['1']` on both trees).
- Mitigating: MCP cuts its answer at 8000 characters (`adapters/mcp/server.py:202`, `1295`), so on a long papers list develop's repeats can push later records past the cut; the branch frees that room.
- Ask: the lead confirms with the owner that "the command line" in the decision covers every text surface (command line, MCP, GraphQL). No code change asked.

### A-18-02: a record whose first sentence passes 1000 characters loses its only printed citation number on the command line and MCP

- Severity: minor (rare reach: one grounded sentence of 1000 characters or more).
- Worse than develop: yes, on the command line, MCP and GraphQL; not on web or saved answer.
- Evidence: `sentence_token` cuts every row's text at 1000 (`core/graph.py:13107`, `[:1000]`), which cuts off the sentence's own trailing `[1]`. On develop the next sentence of the same record cannot join (the joined text passes 1000) and becomes a second row whose text prints `[1]`. On the branch it folds into the first row and its text is dropped, so no text of that record carries a number. Probe S8 (a 1200 character sentence, then a 50 character one, both `[1]`), researcher row texts:

```text
develop [(1000, 'aa...aaaaaaaaaaaaaaaaaaaaaaaaa'), (56, '. ...bbbbbbbbbbbbbbbbbbb [1]. ')] markers printed in joined text: ['1']
branch  [(1000, 'aa...aaaaaaaaaaaaaaaaaaaaaaaaa')] markers printed in joined text: []
```

- The row's `marker_ids` stay `['pm-1']` on both trees, so the web chip and the saved answer's `[1]` are unchanged, and the citation still prints in the command line's sources list. What is lost is the inline number beside a sentence cut mid word.
- Pre-existing part: the cut itself, and the first row printing no number, are on develop too. The branch removes the second row that carried the number.
- No sentence-length cap upstream: the fallback narrative splits a field value on sentence boundaries (`synthesis/findings.py:1057`) and `grounding.py` has no length cap, so a run-on abstract sentence can reach this.
- Fix inside the fence, one line: fold without the sentence only when the first row's text still prints every marker the repeat carries; otherwise keep develop's behaviour (`continue`).

### A-18-03: query 75 never reaches the long case live, so the owner's retest of it cannot see this fix

- Severity: minor (evidence for the retest, not worse than develop).
- Worse than develop: no.
- Evidence: four live runs below; in every one the listing's sentences are the papers' titles (lengths 79, 76, 117, 110, 140), and develop's code path gives the same five rows as the branch. `one_finding_per_record` keeps "the lowest `ref_index` among single-sentence values, so the row that ships is the title rather than a whole abstract" (`synthesis/findings.py:1193` to `1196`). The long case needs a record whose every value is several sentences, such as a record that reached synthesis with its abstract and no title, or a gene summary.
- Ask: the retest line the diagnosis proposes for query 75 ("no paper appears on two rows of its table, even when its abstract is long") will pass on develop too. The lead names a question that reaches the long case, or says the retest can only confirm nothing got worse.

## Probes

Script `<scratchpad>/card18_adv/probe.py`, the same made-up findings through `_answer_tokens` on both trees, at Researcher and Plain language. "Printed" means the sentence appears whole in the joined token text, which is what the command line, MCP and GraphQL show. Saved answer is `answer_markdown_from` over the emitted events.

| Probe | What it attacks | Develop rows | Branch rows | Citation numbers on rows | Verdict |
|---|---|---|---|---|---|
| S1 three sentences of 436 characters, one paper | the card's case | 2 (872, 436) | 1 (872) | `pm-1` on both | as decided; joined text loses sentence c |
| S2 200, 900, 100 characters, one paper | which sentence the text keeps | 2 | 1 | `pm-1` on both | joined text keeps a and c, drops b; develop's order was a, c then b |
| S3 long repeat citing a second record on the same page, same cells | a new citation folded away | 2 | 2 | `pm-1`, `pm-2` on both | same |
| S4 `[1][2]` then long `[1][2]` then `[2]` | a repeat whose markers are all on the row | 3 | 2 | `pm-1`, `pm-2` on both | as decided |
| S5 `[1][2]` then long `[1][3]` (same count, different marker) | the guard counting markers | 2 | 2 | `pm-1`, `pm-2`, `pm-3` on both | same; the guard counts the union, so a swapped marker cannot pass |
| S6 two papers, same title, different pages | two records folded | 2 | 2 | one each | same |
| S7 two records, same page, same title, same identifier | two records folded | 2 | 2 | one each | same, held by the new marker |
| S8 first sentence of 1200 characters, then 50 | a cut first sentence | 2 | 1 | `pm-1` on both | A-18-02 |
| S9a joined exactly 1000 | the boundary | 1 | 1 | same | same |
| S9b joined 1001 | the boundary | 2 | 1 | same | as decided |
| S10 a, b, a, b interleaved, long | repeats that are not adjacent | 4 | 2 | same | as decided |
| S11 variant-to-disease row, long repeats, one citing a disease too | linked disease chips and cell | Researcher 3 variant rows; Plain 3 | Researcher 1; Plain 2 | Researcher `v-1`, `d-1`, `d-2` on both; Plain same set | cell "Disease one; Disease two" and chips unchanged; the `[3][1]` repeat stays its own row in Plain, as on develop |

Saved answer: every probe's markdown rows carry the same cells and the same `[n]` set on both trees; the branch only has fewer duplicate rows (S1: develop two `| A paper about caffeine number 1 [1] | PMID:12345671 |` lines, branch one).

Evidence only, not a finding: in S11 Researcher the folded variant row's chips read `[1][2][3]` (ascending) where develop's first row read `[3][1][2]`. Develop already sorts this way whenever a short repeat merges (`in_citation_order`, card 104), so the branch extends develop's own short-case order to the long case. The record name is not a link (`AnswerScreen.tsx:1541` to `1549`), so no chip opens a wrong record.

Citation `claim_text` is built from the grounding pass's claims (`core/graph.py:11319` to `11327`), never from row text, so no checked words change on any probe. The touched test file on the branch: `54 passed in 10.16s`.

## Live runs

Script `<scratchpad>/card18_adv/live.py`, branch tree, `run_streaming()`, Researcher, `reads_placement=True`, settings as card 17's live check (`CLASSIFIER_PROVIDER=jev`, guard and plan `deepseek/deepseek-v4-flash`, synth from the local settings file, `PER_QUERY_COST_CAP_USD=0.25`), session ids `card18-adv-r1` to `r4`. Each run's `_answer_parts` inputs were saved and replayed through develop's tree (`replay.py`), so the long case is read on develop's code path from the same inputs.

| Run | Question | Outcome | Seconds | Cost (USD) | Listing rows branch / develop path | Long case reached |
|---|---|---|---|---|---|---|
| r1 | papers on the effects of caffeine on exercise performance | answer, "Based on 5 sources cited" | 9.7 | 0.0179 | 5 / 5, identical | no |
| r2 | recent papers on statins | asked back, "How far back should I search?" | 2.5 | 0.0013 | none | no |
| r3 | caffeine, again | answer, "Based on 5 sources cited" | 10.0 | 0.0209 | 5 / 5, identical | no |
| r4 | caffeine, again | answer, "Based on 5 sources cited" | 11.1 | 0.0218 | 5 / 5, identical | no |

- Spend: about 0.062 USD of the 0.75 allowed; four of the five runs allowed. A fifth caffeine run would repeat the same five title rows, and query 75's third question (`GERD`) is asked back when it opens a conversation (query 76).
- Every run logged `CallerIdentityRequired` from session memory at the end, because the script passes no owner id; it is after `done` and not related to this change.

## Verdict

- A-18-01: a decision-scope question for the owner, no code change.
- A-18-02: worse than develop on the command line, MCP and GraphQL, in a rare case (a grounded sentence of 1000 characters or more): the record keeps its chip and source, but no printed text of it carries its number. Fixable inside `merge_into` in one round.
- A-18-03: evidence for the retest.
- No probe found two different records folded into one, a citation lost from any row, a changed disease cell or chip set, or a row cut by the change itself. Web and saved answer only lose duplicate rows.

VERDICT: FIX FIRST
