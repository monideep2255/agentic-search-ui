# Judge report, cards 110 and 111

Judge, bossman mode dial position 2, one round. Base: change 409a0610 (branch fix/cards110-111-summary-opening) against origin/develop cffdb8fd. Probes and mutations ran in a detached worktree at <scratchpad>/j110. This file is the only file written in the branch worktree.

## Findings

### J-110-01: The state arithmetic comment counts three separators where there are four
- Severity: minor
- What: `harness/decide.py:595-597` says the worst case is "1000 + 10 + 4 * (700 + 12) + 3 * 2 separators = 3864". `lead_sentence_state` joins five parts (question plus four sentences) with "\n\n", which is four separators, so the worst case is 3866. Still under `_STATE_MAX_CHARS` 4000, so nothing is cut; the comment is wrong by 2.
- Reproduction: `lead_sentence_state("Q"*5000, ["x"*5000+" [1]"]*10)` printed `worst len 3866 max 4000 count Sentence 4 endswith x True` and `separators 4`.
- Why a person would care: they would not today. The next person to raise the cap or add a fifth candidate trusts a sum that is already off.
- NOT FIXED
### J-111-01: The drop never checks that the listing shows the record, so with no listing a Plain language answer loses the names entirely
- Severity: major (rare path; inside this change's own fix)
- What: card 111's sentence is "titles the answer already lists". The code (`core/graph.py`, `_is_label_only_sentence` and the `label_by_display` / `echo_positions` block in `_answer_parts`) only checks that each piece equals the cited finding's own name, title, symbol or preferred_name. It never checks that a listing row exists for that record. When the code-built listing grounds nothing (`listing_grounding.claims` empty, so `tail_sentences` is empty and no listing is sent), the dropped sentence was the only place in the visible answer that named those records. The `len(echo_positions) >= len(sentences)` guard does not help, because another, non-label sentence survives.
- Reproduction: a probe in `<scratchpad>/j110` (and the same file at cffdb8fd in `<scratchpad>/j110dev`) drives `write_node` with three Disease rows ("disease name number 1..3"), the writer reply `NCBIGene:672 is associated with disease name number 3 [c]. Disease name number 1 [a] and Disease name number 2 [b].`, and `build_structured_fallback_narrative` patched to `"nothing here."` (the stand-in `test_write_completeness._tail_cannot_ground` already uses for a listing the pass strips), depth `plain_language`.
  - Branch 409a0610:
    ```
    claim: 'I found 3 conditions on this topic [1][2][3]. '
    claim: 'NCBIGene:672 is associated with disease name number 3 [1]. '
    note: 'This is a research summary, not medical advice.'
    MENTIONS number 1: False number 2: False
    ```
  - Develop cffdb8fd, same probe:
    ```
    claim: 'I found 3 conditions on this topic [1][2][3]. '
    claim: 'NCBIGene:672 is associated with disease name number 3 [1]. '
    claim: 'Disease name number 1 [2] and Disease name number 2 [3]. '
    MENTIONS number 1: True number 2: True
    ```
  - In Researcher and Clinical brief the code-built count line happens to name all three ("Found 3 disease records: disease name number 3 [1], disease name number 1 [2] ..."), so only Plain language loses them.
- Why a person would care: on this path a Plain language reader is told "I found 3 conditions" and is shown the name of one. Two conditions the writer named, and that are cited, disappear from the page. Develop shows them. How often the listing grounds nothing while the prose grounds is not measured; I am unsure of the live rate, and it may be rare.
- NOT FIXED
### J-111-02: Three single-property mutations survive the branch's tests
- Severity: minor
- What: six single-line mutations were applied one at a time in `<scratchpad>/j110` and restored with `git checkout -- src` after each. Three went red, three stayed green:
  - M1, card 110, `_lead_candidates` slices to `[:2]`: red, `test_write_answers_sooner.py::test_the_third_cited_sentence_can_lead_the_answer`, `1 failed, 123 passed`.
  - M3, card 111, keep-all guard `>=` to `>`: red, `test_summary_label_only_sentence.py::test_a_summary_made_only_of_record_names_is_kept_not_emptied`, `1 failed, 41 passed`.
  - M4, card 111, text after the last marker ignored (`if not numbers:`): red, `test_label_only_is_decided_from_structure[... are recent reviews.-False]`, `1 failed, 41 passed`.
  - M2, card 110, the "third" criterion says "sentence 4" instead of "sentence 3": green, `124 passed`. The criteria texts the classifier reads for the two new options are not pinned by any test.
  - M5, card 111, the empty-piece branch `elif seen is None or seen != label...` replaced by `elif False:`: green, `42 passed`. That branch decides "[2] Marfan syndrome [3]." and "Marfan syndrome [1][2]."; with M5 a sentence that opens on a bare marker counts as label-only. No test covers back-to-back or leading markers.
  - M6, card 111, the keep-all guard applied even when a lead is set (`lead_text is None and` removed): green, `42 passed`. No test covers a lead sentence together with label-only sentences. Its effect is small (the lead shows either way), so this one is a coverage note only.
- Reproduction: the commands and output above, run from `<scratchpad>/j110` with the two test files of each card (`test_write_answers_sooner.py` plus `test_decide.py` for 110; `test_summary_label_only_sentence.py` plus `test_listing_one_row_per_record.py` for 111).
- Why a person would care: a later edit can swap the wording of the criteria for sentences 3 and 4, or change how a marker with no words before it is read, and no test says so. Either can change which sentence opens an answer, or whether a sentence is dropped.
- NOT FIXED
### J-110-02: Two docstrings still describe two candidates, and the cap drop from 1200 to 700 is not tested against a long features sentence
- Severity: minor
- What:
  - `core/graph.py` `_lead_candidates` docstring still says "the first one or two sentences that carry a citation marker" (the slice is now four).
  - `harness/decide.py` `lead_sentence_state` docstring still says each candidate is capped "so neither can crowd the other out", wording for two.
  - `_LEAD_CANDIDATE_MAX_CHARS` fell from 1200 to 700. A candidate between 700 and 1200 characters (after markers are removed) was read whole on develop and is now cut. A features sentence listing about 30 features passes 700. The answering words of such a sentence are at its start ("MedGen lists these clinical features: ..."), so the pick should not change, but no test or probe in the build report shows a long features sentence still picked.
- Reproduction: `grep -n "first one or two" src/system_03_search_agent/core/graph.py` in `<scratchpad>/j110` returns the `_lead_candidates` docstring line; `lead_sentence_state` docstring read at `harness/decide.py:663-670`.
- Why a person would care: not directly. The stale text misleads the next reader of the code; the cap is a small, unmeasured risk to which sentence opens a long features answer.
- NOT FIXED
- Addendum to J-110-02: the grep returned two lines, `core/graph.py:12628` (a block comment, "the first one or two grounded, cited sentences") and `core/graph.py:12653` (the `_lead_candidates` docstring).
### J-110-03: The lead pick takes a sentence that opens on "It", and four candidates widen where that can happen
- Severity: minor (the classifier behaviour predates this change; the change widens its reach)
- What: the "neither" criterion says a sentence that "needs an earlier sentence to make sense" must not lead. Live, Jev ignores that for a sentence that opens on a pronoun. Card 110 now offers sentences 3 and 4, where a sentence that refers back is more likely than at sentence 2.
- Reproduction: live Jev through `decide()` with the branch's own options, criteria and `lead_sentence_state`, question "What organs does Marfan syndrome affect?":
  - Four candidates ("Marfan syndrome is a heritable disorder of connective tissue [1].", "Neonatal Marfan syndrome is especially rare [2].", "It mainly affects the heart, the eyes and the skeleton [3].", "Marfan syndrome [4] and Marfan syndrome [5]."): `pronoun3 run0..run4 chosen=third by=jev`, 5 of 5.
  - Develop's shape, two candidates (sentence 1 and the "It ..." sentence): `pronoun2 run0..run4 chosen=second by=jev`, 5 of 5. So the weakness exists on develop; this change does not create it.
  - Controls, same branch: a first sentence that answers stays first (`first_ok` 5 of 5 `first`), and four non-answering sentences, two of them title-only, give `neither` 5 of 5 (`titles4`).
- Why a person would care: the answer can open on "It mainly affects ...", with "It" pointing at a sentence that is now below it. Here "It" is the question's own subject, so it still reads; with "They" or "This study" it would not. Worth an eye in the owner's test-queries pass; not a merge blocker on its own.
- NOT FIXED
### J-111-03: A second copy of the label field list, a private import across modules, and label-only sentences still use up lead candidate slots
- Severity: minor
- What:
  - `core/graph.py` adds `_LABEL_FIELDS_FOR_ECHO = frozenset({"name", "title", "symbol", "preferred_name"})`. `synthesis/answer_layout.py:780` already has `_LABEL_FIELDS = ("name", "title", "symbol", "preferred_name")`, which `record_label` uses to choose what a listing row shows. Two lists that must stay equal for "a title the listing already shows" to stay true; a field added to one and not the other breaks the card's premise silently.
  - `core/graph.py` now imports `_clean_claim`, a private name, from `synthesis/grounding.py`. The builder says the check "reads ... no word list of its own"; it borrows one. `_clean_claim` strips a leading "and", "or", "but", "also" or "then", so "Marfan syndrome [2] but Marfan syndrome [3]." and "Marfan syndrome [2] then Marfan syndrome [3]." are also matched (probe output: `True | Marfan syndrome [2] but Marfan syndrome [3].`, `True | Marfan syndrome [2] then Marfan syndrome [3].`). Those sentences say nothing either, so the effect is harmless today, but a change to the grounding pass's glue list now changes which summary sentences are dropped.
  - The lead decision (`_lead_candidates`) is computed before `_answer_parts` and is offered label-only sentences as candidates. Order "abstract, abstract, label-only, label-only, features" leaves the features sentence fifth and out of reach, while two of the four slots go to sentences the summary will drop anyway. Jev declines them (`titles4` 5 of 5 `neither` in J-110-03), so the slot is wasted, not misused.
- Reproduction: `grep -n "_LABEL_FIELDS" src/system_03_search_agent/synthesis/answer_layout.py src/system_03_search_agent/core/graph.py` in `<scratchpad>/j110`; the direct `_is_label_only_sentence` probe quoted above; `core/graph.py` `_lead_candidates` reads `model_grounding.sentences` with no label check.
- Why a person would care: today, barely. The duplicated list and borrowed glue rule are how this check drifts from the listing it relies on.
- NOT FIXED
### J-111-04: When the question asks "which", a bare list of names is the answer, and the summary now leaves it to the listing
- Severity: minor (unsure; the owner's card asks for this drop, and the names stay in the listing)
- What: checklist item 2 asked whether "label" can be the answer itself. It can. `symbol` and `name` are label fields, so for "Which diseases ..." or "Which genes ..." a writer sentence of bare names ("Disease name number 1 [1] and Disease name number 2 [2].", or "FBN1 [1] and TGFBR2 [2].") is matched and dropped whenever any other model sentence survives. A single bare name was already dropped on develop by `drop_record_restatements`; a join of two or more names is newly dropped.
- Reproduction: the probe of J-111-01 with the listing left on (`no_listing=False`), question "Which diseases are associated with NCBIGene:672?", depth `plain_language`.
  - Branch: `claim: 'I found 3 conditions on this topic [1][2][3]. '`, `claim: 'NCBIGene:672 is associated with disease name number 3 [3]. '`, then the listing under "Where this answer comes from" with all three names.
  - Develop: the same, plus `claim: 'Disease name number 1 [1] and Disease name number 2 [2]. '` in the summary.
  - Direct: `_is_label_only_sentence("FBN1 [4].", {4: "FBN1"})` is `True`.
- Why a person would care: a Plain language reader who asked "which diseases" sees one disease named as associated in the summary and the other two only in the source list below. The dropped sentence did not say they were associated either, so nothing true is lost, but the summary can read as if only one answered. This is the owner's call on how far "titles the answer already lists" reaches, not a defect I can prove.
- NOT FIXED

## Checklist, with evidence

1. Correctness of card 110. Verified by probe.
   - `LEAD_SENTENCE_PICKS` gains "third" and "fourth" (`harness/decide.py:589`); `MAX_LEAD_CANDIDATES` follows (`:592`). Every consumer found by `git grep -l "lead_sentence\|LEAD_SENTENCE"` is `core/graph.py`, `harness/decide.py` and three test files. `_lead_candidates` slices by the constant; `lead_sentence_options`, `lead_sentence_criteria`, `lead_sentence_index` all read the tuple. Probe: `lead_sentence_options(4)` gave `('first', 'second', 'third', 'fourth', 'neither')`; `lead_sentence_index` over first..fifth, neither, None with 3 candidates gave `[0, 1, 2, None, None, None, None]`.
   - Option limits elsewhere: `DecisionRecord.options` and Jev's `_MAX_PROBABILITIES` allow 12 (`harness/jev_client.py:176-178`); five options fit. Each criterion is under `_DESCRIPTION_MAX_CHARS` 1000 (measured 327, 171, 179, 182). The guard parse matches whole option tokens and needs exactly one; the criteria texts name "Sentence 1..4", not option words.
   - State bound: worst case measured 3866 characters against `_STATE_MAX_CHARS` 4000, all four candidates whole (J-110-01: the comment says 3864).
2. Card 111 never drops a sentence that says more than labels. Verified by probe for the structural check; the "only answer" guard holds only when every model sentence is label-only, and the "already lists" premise fails when no listing is built (J-111-01). `zip(strict=False)` of texts and numbers is correct: `split` with one capture group always yields one more text than numbers, and the trailing text is checked separately (probe: "... [3]. Treatment is losartan." gives False). A label can be the answer itself (J-111-04).
3. No hardcoded decisions. Read and probed. No question words in code or prompt; the lead criteria name sentence positions only. The features directive adds list shape only ("commas between the names, and the word "and" only before the last name"), says nothing about which names, and sits in `build_clinical_features_directive`, which reaches only the user message (`synthesis/findings.py:2043-2066`), the dynamic suffix. The one borrowed word list is the grounding pass's glue rule (J-111-03).
4. Production standards. Read. Bounded context: candidates capped at 700 and the state at 4000 before injection. Deterministic accept or reject: the drop is exact equality after normalising case and end punctuation. Cite-or-refuse: the change only removes sentences, never adds text. isort: `core/graph.py` fails identically on develop (below). No new dependency, endpoint, schema or secret.
5. Break it. Six single-line mutations, three red and three survivors (J-111-02).
6. Gates, run by me in `<scratchpad>/j110`:
   - `ruff check` (no path): `All checks passed!`
   - `isort --check-only` on the three source files and four test files: only `core/graph.py` fails, with the diff `+from system_03_search_agent.contracts.events import ResolvedEntity as EventResolvedEntity` moved within the `contracts.events` import block. Develop cffdb8fd, same command on `core/graph.py`: the same ERROR and the same diff lines. Not this change's.
   - `pytest tests/system_03_search_agent/harness tests/system_03_search_agent/core tests/system_03_search_agent/synthesis -m "not integration" -q`: `2 failed, 2836 passed, 66 skipped, 1 deselected, 1 xfailed, 2 warnings in 88.03s`. The two failures are `test_opus_writer.py::test_the_rollback_writer_glm_5_2_is_still_priced_by_the_installed_map` and `::test_the_old_writer_is_never_priced_below_the_static_estimate`; at cffdb8fd the same two fail with `no OpenRouter price found for model 'z-ai/glm-5.2'`.
7. Latency. The bound is `asyncio.wait_for(..., timeout=min(_LEAD_DECISION_MAX_WAIT_S, budget_s - 0.5))` in `_lead_sentence_choice`, with `_LEAD_DECISION_MAX_WAIT_S = 1.0`; a late pick returns None and the count line leads. Live Jev, `decide()` wall time, five runs each: two candidates (state 311 characters) 217, 207, 248, 267, 185 ms; four candidates (508) 162, 190, 210, 161, 180 ms; worst-case state (3866) 184, 210, 236, 202, 172 ms. Far inside 1 s. About 35 live Jev calls in all, well under $0.10.
8. Worse than develop for a person? On one path, yes: J-111-01. Everywhere else I probed, no. Card 110 did what it says live: with abstract, abstract, features, title-only sentences, the pick was `third` 5 of 5; develop's two-candidate shape gave `neither` 5 of 5.

## Verified by my own probes versus only read

- Verified by probe: the state arithmetic; option, criterion and index handling; Jev latency at two, four and worst-case size; the four-candidate pick reaching the features sentence; the pronoun pick (J-110-03); the structural check on 16 hand-built sentences; the end-to-end drop in three depths with and without a listing, against develop; the gates; six mutations.
- Only read: the guard tier's parse of "third" and "fourth" (no guard-tier live call); that the features directive changes what the writer produces (no live writer run; the builder's five Marfan runs are claimed, not reproduced); the builder's live costs and the EGFR runs; how often a listing grounds nothing in live traffic.

## Learnings

None over five minutes. One note: in this shell (zsh) an unquoted `$1` holding several test paths is not split, so pytest saw one missing path and printed nothing. Pass paths as an array.

## Verdict

J-111-01 sits inside the fix this change makes (card 111's drop) and is the newest code.

FIX FIRST: J-111-01 (drop a label-only sentence only when the records it cites are in the listing the answer shows; with no listing, keep it). J-110-01, J-110-02, J-110-03, J-111-02, J-111-03 and J-111-04 are minor and do not hold the merge.
