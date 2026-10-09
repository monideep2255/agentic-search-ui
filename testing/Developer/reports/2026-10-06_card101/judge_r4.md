# Card 101, round 4 judge report

Judge: fresh context, branch fix/card101-copied-cuts at a8223b96, base develop d8179c4e. Probes run in a detached worktree, never in asu-card101c.

## Findings

### J4-101-01: a check that approves a gene name but holds the joined gene-disease reading leaves "BRCA1 [1]." on screen, where develop showed the whole sentence
- Severity: blocking (unsure, see below). Regression against develop. INSIDE A FIX MADE DURING THIS PHASE: round 4's joined reads (J3-101-05 fix, `grounding.py:1662-1691`) combined with the end-strip rule left in place at `grounding.py:1764-1779`.
- What: once the first clause of a sentence is a cut, every later copied clause, wrapped gene-disease rows included, becomes a check item read joined. When the check approves the first, short item and holds a later joined item, the end strip shows the approved prefix alone. For a gene name cut that prefix is a bare name.
- Reproduction (`j4out/gene.py` in the session scratchpad, real `run_grounding_pass`, question "What diseases is BRCA1 associated with?"): findings [1] Gene name "BRCA1 DNA repair associated", [2] Disease name "Familial cancer of breast" (name_resolved), [3] Disease name "Breast-ovarian cancer, familial, susceptibility to, 1". Writer: "BRCA1 [1] is associated with familial cancer of breast [2] and breast-ovarian cancer, familial, susceptibility to, 1 [3]."
  - develop d8179c4e: shown whole, no check item.
  - round 3 809c8574: one item "BRCA1"; approved, the whole sentence is shown.
  - round 4 a8223b96: three items, "BRCA1", "BRCA1 is associated with familial cancer of breast", "BRCA1 is associated with familial cancer of breast and breast-ovarian cancer, familial, susceptibility to, 1". Approve all: whole sentence. Approve only the first: shown "BRCA1 [1]."
  - The same shape with a summary cut: "This gene encodes a 190 kD nuclear phosphoprotein [4] and is associated with familial cancer of breast [2]." approve only the first -> "This gene encodes a 190 kD nuclear phosphoprotein [1]." (develop shows the whole sentence).
- Why the partial outcome is the likely one: `build_r3.md` (quoted in the code comment at `grounding.py:1650-1656`) measured the check holding "BRCA1 is associated with familial cancer of breast" back 3 of 3 times, which is why wraps were left on today's path; a bare name read against its own record is the easy approval. Round 4 now asks exactly that held shape whenever a gene sentence opens on a cut name.
- Why it matters: `build_r4.md` "The change in the user's words" says "never a leftover piece such as 'Ribavirin [1].'"; this is that piece, on a gene answer, the app's core question type. The person sees a bare gene name with a citation where develop told them the disease association.
- Unsure: no recorded gene draft exists to show how often the writer cuts a gene's name before its first marker (the recorded bronchiolitis drafts do write "Acute bronchiolitis [1], ..." and "The name Adenoviral bronchiolitis [8] points ..."). I did not measure the check's verdict on the "BRCA1" item live.
- NOT FIXED

Addendum to J4-101-01, measured: `core.graph` runs `drop_record_restatements` next (`answer_layout.py:841`). On the two outcomes above it removes the bare prefix ("BRCA1 [1]." and "This gene encodes a 190 kD nuclear phosphoprotein [1]." both -> '' , 1 dropped), so in the usual path the person sees no fragment; they see the gene-disease sentence develop showed disappear, and the answer falls to the code-built list when that was its only prose. The fragment itself stays on screen only when the list grounds nothing (`graph.py` "put them back"). The finding stands as a loss of a sentence develop shows, on the gene path the logged decision of 2026-10-06 (DECISIONS row "Card 101 round 3: ... A record name wrapped in the question's words keeps today's path for now") meant to leave alone; round 4 sends those wrapped rows to the check whenever an earlier clause in the sentence was a cut.

### J4-101-02: under a partial approval, a held last clause still leaves a verbless fragment that survives the restatement drop: "Ribavirin [1] and palivizumab [2]."
- Severity: major; blocking: unsure (owner's call). Not new in round 4 (round 3 809c8574 gives the identical output), so a residual of this phase's own fix, not of develop; it contradicts round 4's stated property and the owner's round 4 directive "a held cut never leaves a fragment" (DECISIONS row 877).
- Where: the end-strip rule kept by round 4, `grounding.py:1764-1779` ("a held clause itself is still an end strip").
- Reproduction (`j4out/frag3.py`, real `run_grounding_pass` then `drop_record_restatements`, question "How is bronchiolitis in babies treated?"): records [1] title "Ribavirin aerosol therapy", [2] title "Palivizumab prophylaxis", [3] abstract "Several antivirals are used to treat bronchiolitis in infants."; writer "Ribavirin [1] and palivizumab [2] are used to treat bronchiolitis [3]."
  - develop: 'Ribavirin [1] and palivizumab [2] are used to treat bronchiolitis [3].' (no check)
  - round 4 items: 'Ribavirin', 'Ribavirin and palivizumab', 'Ribavirin and palivizumab are used to treat bronchiolitis'.
  - approve the first two, hold the third: shown 'Ribavirin [1] and palivizumab [2].', and after `drop_record_restatements` still 'Ribavirin [1] and palivizumab [2].'
  - approve only the first: 'Ribavirin [1].', removed by the restatement drop.
- Why it matters: `build_r4.md` says "a sentence is either shown as develop showed it or not at all; never a leftover piece such as 'Ribavirin [1].'". That holds when the check holds everything or approves everything, which are the only two outcomes the replay ran; it does not hold for a partial verdict, which is the normal case when the check approves a list of names and holds the claim joined to them.
- Unsure: whether the shipped check approves a bare joined noun phrase such as "Ribavirin and palivizumab"; measured live below if the spend allows.
- NOT FIXED

Live evidence for J4-101-01 and J4-101-02 (`j4out/live_j4.py`, the shipped `check_reworded_sentences` in Jev mode, items built by the branch's `run_grounding_pass`, 3 repetitions, $0.00045 each, $0.00135 in all):

| Item | Run 1 | Run 2 | Run 3 |
|---|---|---|---|
| "BRCA1" | Approved | Approved | Approved |
| "BRCA1 is associated with familial cancer of breast" | Approved | Approved | Approved |
| "BRCA1 is associated with familial cancer of breast and breast-ovarian cancer, familial, susceptibility to, 1" | Approved | Approved | Approved |
| "This gene encodes a 190 kD nuclear phosphoprotein" | Approved | Approved | Approved |
| "This gene encodes a 190 kD nuclear phosphoprotein and is associated with familial cancer of breast" | Approved | Approved | Approved |
| "Ribavirin" | Approved | Approved | Approved |
| "Ribavirin and palivizumab" | Approved | Approved | Approved |
| "Ribavirin and palivizumab are used to treat bronchiolitis" | Held | Held | Held |

- J4-101-01 downgraded by this evidence: in Jev mode the check approves the joined gene items, so the gene sentence shows as on develop. What remains is the cost (one item per later clause, so more items and pair room) and the guard-tier mode, which I did not run. Severity now minor, not blocking.
- J4-101-02 confirmed: with the check's own verdicts, 3 of 3, the answer shows "Ribavirin [1] and palivizumab [2]." (offline second pass with exactly those approvals, then `drop_record_restatements`: unchanged). Develop shows the full, unsupported sentence; round 3 and round 4 both show the fragment.
- Partial approvals on the 168 recorded drafts (`j4out/partial2.py`: every subset of each draft's items, or 200 random subsets above 8 items, 504 runs, both `core_ask_required` settings): 0 sentences shown that develop does not show, comparing text with markers removed. So the fragment is constructed, not seen in a recorded draft.

### J4-101-03: a faithful copy of a whole record sentence now goes to the check when it, or the sentence after it, opens on a lowercase letter, a digit or a Greek letter, or follows a closing quote mark
- Severity: minor, not blocking (it is the card's rule working in the fail-closed direction, and 0 of 265 recorded whole copies move). New in round 4: the J3-101-03 fix adopted `_RECORD_SENTENCE_BOUNDARY` (`grounding.py:806`, a break needs a capital, `"` or `(` after it), so `_record_sentences` (`grounding.py:945`) merges such neighbours into one "sentence". Round 3 and develop showed these copies with no check.
- Reproduction (`j4out/faithful.py`, one abstract value "Cells were treated with drug X. p53 levels rose sharply after treatment. 30 patients died in the first year. α-Synuclein aggregated in neurons. “Quoted claims were tested.” Mortality fell by half. ..."; writer copies each sentence word for word with "[1]."):

| Copy | develop | round 3 | round 4 |
|---|---|---|---|
| "Cells were treated with drug X" (the value's first sentence) | shown | shown | check item |
| "p53 levels rose sharply after treatment" | shown | shown | check item |
| "30 patients died in the first year" | shown | shown | check item |
| "α-Synuclein aggregated in neurons" | shown | shown | check item |
| "Mortality fell by half" (after `.”`) | shown | check item | check item |

- Why it matters: in molecular abstracts a sentence opening on "p53", "mRNA", "miR-21", "iPSCs", a number or a Greek letter is ordinary, and it takes its neighbour with it. Each becomes a check item; when the check cannot run (too little time, the cost cap, a failed call) the faithful sentence is not shown where develop showed it, and each adds to the pair calls the adversary measured filling at 3 list sentences (A3-101-09). The recorded drafts (bronchiolitis, GERD, Mediterranean) contain none, so the replay cannot see it; no gene-summary or molecular-abstract draft was replayed.
- Also seen, develop shares it: the writer's "The U.S. Food and Drug Administration approved it [1]." is split by the narrative splitter at "U.S." and shows as "Food and Drug Administration approved it [1]." on all three trees.
- NOT FIXED

### J4-101-04: the abbreviation residual is wider than "Dr. Smith": any acronym, gene symbol or capitalised drug after "e.g.", "i.e." or "vs." still makes a cut "whole", so the paper's opposite shows unchecked
- Severity: major as a product defect; not blocking. A residual develop shares (identical output on develop), not a regression; but `build_r4.md` marks J3-101-03 "Fixed, with the residual the widener shares ('Dr. Smith')", which understates it.
- Where: `_RECORD_SENTENCE_BOUNDARY`, `grounding.py:806`, used by `_record_sentences`, `grounding.py:945`.
- Reproduction (`j4out/abbr.py`, `run_grounding_pass`, no approvals), shown with no check item on develop and on round 4 alike:
  - record "Several popular claims lack support, e.g. HRT prevents dementia in women."; writer "HRT prevents dementia in women [1]." -> shown 'HRT prevents dementia in women [1].'
  - record "The trial did not show that aspirin vs. NSAIDs reduce pain in adults."; writer "NSAIDs reduce pain in adults [1]." -> shown.
  - record "No trial supports the idea, i.e. BRCA1 testing reduces mortality."; writer "BRCA1 testing reduces mortality [1]." -> shown.
- Why it matters: this is J3-101-03's own attack ("e.g. aspirin prevents colorectal cancer") with the noun in capitals, which is how biomedical text writes genes, acronyms and many drug names. The adversary measured the check holding the abbreviation shape 3 of 3 when asked (`adversary_r3.md`, "Evidence"); routing is the only gap.
- NOT FIXED

### J4-101-05: two of round 4's routing properties survive mutation with every synthesis test green
- Severity: minor, not blocking. Inside this round's fix (its tests).
- Method: my own mutations (`j4out/mutate_j4.py`), applied to a `git archive` copy of a8223b96, never a worktree another agent uses, each restored and compared byte for byte; `pytest -m "not integration"` over `tests/system_03_search_agent/synthesis` (650 passed at baseline).
- Survivors that change behaviour:
  - N7, a held clause also counts as a middle strip (`grounding.py:1775`, `or (later in held_for_check)`): 650 passed, 0 failed. What it changes, my probe `j4out/n7probe.py`: records "Drug X was well tolerated.", "There is no evidence that drug X reduces mortality in adults.", population "Children"; writer "Drug X was well tolerated [1], and drug X reduces mortality [2] in children [3]."; check approves nothing. Round 4 shows 'Drug X was well tolerated [1].'; the mutant shows ''. The code comment's "a held clause itself is still an end strip" has no test, so a later edit can silently drop a whole clause develop showed.
  - N8, a clause held by code for a verdict opener is not counted as held (`grounding.py:1699`, `if held and not held_by_code:`): 650 passed, 0 failed. It changes only a sentence with a kept clause, then a code-stripped clause, then a "yes, ..." cut, which develop drops whole and the mutant shows in part. Contrived; recorded for completeness.
- Survivors I judge equivalent or near it: N5 (listing row read without removing glue; listing rows never start with a separator), N13 (question rule reads only the last character; differs only for a "?" followed by a closing mark), N14 (verdict hold applied to joined clauses too; holds more, the safe direction).
- Killed: N1 clean-claim form dropped (2 red), N2 every copy counts as asking (2 red), N3 record value never split (27 red), N4 listing rows lose the split pieces (1 red), N6 wraps after a cut not joined (3 red), N9 item text keeps the space before a comma (1 red).
- NOT FIXED

### J4-101-06: the branch no longer merges cleanly into develop: DECISIONS.md conflicts
- Severity: minor (process), not blocking for the code; the lead resolves it before merging.
- What: develop moved from d8179c4e to 5301cc6e (pull request #196, documents only; no change under `src` or `tests`). Both sides appended rows at the end of `DECISIONS.md`.
- Reproduction: `git merge-tree --write-tree --name-only origin/develop a8223b96` -> "CONFLICT (content): Merge conflict in DECISIONS.md", the only conflicted file. `git diff --stat d8179c4e origin/develop -- src tests` is empty, so the code judged here is the code that would merge.
- Why it matters: an append-only log resolved by hand can lose or reorder a row; keep both sides' rows, the branch's three after develop's.
- NOT FIXED

### J4-101-07: the listing flag is pinned at one of its three callers only; dropping it from the structured fallback or the repair probe leaves every core and synthesis test green
- Severity: minor, not blocking (the shipped code passes the flag at all three callers, and my byte-for-byte listing probe below shows the effect is exactly develop's). Inside this round's fix (its tests).
- Where: `core/graph.py:13223` (structured fallback) and `core/graph.py:9821` (`_code_built_lines_will_cite`, the repair probe). `graph.py:13328` (findings tail) is pinned by `test_breadth_wiring.py`.
- Reproduction (`j4out/mutate_j4.py`, scratch tree, `pytest -m "not integration"` over `tests/system_03_search_agent/core` and `tests/system_03_search_agent/synthesis`, 1998 passed at baseline):
  - N10, the tail caller without the flag: 4 failed (`test_breadth_wiring.py`, the OMIM rows).
  - N11, the structured fallback caller without the flag: 1998 passed, 0 failed.
  - N12, the repair probe caller without the flag: 1998 passed, 0 failed.
- What a missing flag does (`j4out/noflag.py`, branch): findings OMIM title "GLUCOKINASE; GCK" and abstract "Mortality fell in the U.S. but rose elsewhere. Then it stabilised."; listing 'GLUCOKINASE [1]. GCK [1]. Mortality fell in the U.S [2]. but rose elsewhere [2]. Then it stabilised [2].'; grounded with the flag: 'GLUCOKINASE [1]. GCK [1]. Mortality fell in the U.S [2]. It stabilised [2].' (identical to develop); without it: 'It stabilised [1].' So a later edit to either caller would make the fallback record list, the reader's floor when the writer's prose fails, lose rows, with CI green.
- NOT FIXED

Addendum to J4-101-02, severity revised to minor, not blocking. Develop already shows this exact fragment through the same end-strip rule (T-6.2-15) whenever the last clause fails code's own check: records [1] name "Ribavirin", [2] name "Palivizumab", [3] "Several antivirals are used to treat bronchiolitis in infants."; writer "Ribavirin [1] and palivizumab [2] are used to treat babies [3]." -> develop and round 4 both show 'Ribavirin [1] and palivizumab [2].', unchanged by `drop_record_restatements`. So the fragment is a develop residual that the check's hold now also triggers, not a new kind of output; and on the input above develop's alternative is the unsupported claim the check held 3 of 3. What stays true: `build_r4.md`'s sentence "never a leftover piece such as 'Ribavirin [1].'" is accurate only for the all-or-nothing outcomes, and the owner's round 4 wording "a held cut never leaves a fragment" is not met for a partial verdict. The owner should hear that in those words.

Addendum to J4-101-07, full suite: N11 and N12 each run against the whole unit suite as gate04 runs it (`pytest -m "not integration"`), in the scratch tree: 7071 passed, 1 failed, and the one failure (`test_system3_cli_package.py::test_the_wheel_is_built_from_the_servers_own_source_files`) fails identically on the unmutated scratch tree (an archive with no git metadata), so it is not caused by the mutation. Both mutants survive the full suite.

### J4-101-08: in guard mode an unexpected exception from the check's model call still escapes the sentence check instead of approving nothing
- Severity: minor, not blocking. A residual develop shares (`graph.py:9746` catches three classes on develop too; J3 recorded it in round 3). Round 4 widens its reach slightly: more answers now make a check call (the replay's three drafts with new joined items, and any answer with a cut).
- Reproduction (`j4out/failclosed.py`, `_ground_with_sentence_check` with `_dispatch_tier_call` replaced, `CLASSIFIER_PROVIDER` unset): a dispatch raising `RuntimeError("boom")` -> propagated `RuntimeError`; raising a bare `TimeoutError` -> propagated `TimeoutError`. In Jev mode the same `RuntimeError` is caught inside `check_reworded_sentences` and the answer shows only the safe sentence.
- Why it matters: the real dispatch turns timeouts into `HarnessCallError`, so this needs an unclassified failure; if one happens the Write step fails rather than showing the code-safe answer.
- NOT FIXED

## Checklist

| Item from the brief | Verdict | Own probe or read |
|---|---|---|
| 1. Round 3 findings marked fixed | PASS, with J4-101-04 | Own probe `j4out/attacks.py`, 66 cases, develop and branch. Every judge_r3 and adversary_r3 reproduction that showed unchecked now gives a check item and shows nothing with no approval, and the item's text when approved: colon labels (hypothesis, myth, misconception, "Not recommended:", RETRACTED, "the claim:", "Do not:"), semicolons (aspirin, contraindications, safe in children, antibiotics), abbreviations (e.g., U.S. both forms, yrs., vs., approx., et al., "e.g. corticosteroids"), record questions (title, abstract, "Does ..."), stripped quote marks and brackets (straight, curly, single, parenthesis, square), the joined reads ("in children", "in bronchiolitis in infants", a whole sentence after a cut, cut then wrap then whole across three records, with every record's text in the quotes), case mid-sentence, the "Yes," hold. "Dr. Smith" and "U.S. Patients" still show unchecked, as the build names; J4-101-04 shows the residual is wider. Connective sentences: writer path identical to develop (But, And, Then, Or, Also). hb4 and the synthetic "Ribavirin [1]." case: nothing shown, as develop. J3-101-06's three tests and J3-101-08's comments: read, and the build's M9, M11, M12 not re-run by me |
| 2. No regression against develop | PASS | Own runs. `replay_r4.py` on my worktrees: develop 59/59/0, branch 52/59/34, the build's numbers; my comparison: 0 sentences shown that develop does not show, 0 drafts emptied, approve-all identical to develop in all 168, the 7 lost sentences are the cuts. My partial-approval replay (`partial2.py`, 504 runs): 0 new sentences. Code-built list (`listing.py`): 144 finding sets (4 recorded, 35 synthetic values in 4 rendering shapes: semicolons, abbreviations, colon labels, quotes, questions, connectives, inner "[3]", curly quotes, lowercase starts), both `core_ask_required` values, two questions, full list and tail form: develop and branch JSON byte-identical, narrative, claim ids, claim text, strip counts, sentences and origins. J4-101-01 and J4-101-03 are costs within the rule, not shown-text regressions |
| 3. Fail closed for every new item type | PASS (J4-101-08 a residual) | Own probe `failclosed.py`, one answer carrying a whole sentence, a RETRACTED-label copy, a joined cut plus wrap, a record question, a stripped quote, a semicolon cut and a cut plus whole sentence (8 items). Approves none, unreadable text, bad JSON, out-of-range, string and boolean indices, no response, `HarnessCallError`, cost cap: 1 call, only the whole sentence shown. Budget 3.9 s: 0 calls, only the whole sentence. Jev mode with `SentenceCheckUnreadable`, `RuntimeError`, cost cap: only the whole sentence. Approve all: all shown. Approve only the joined items: those sentences dropped whole. Approve only the cuts: the approved prefixes |
| 4. Mutations | PASS with gaps (J4-101-05, J4-101-07) | Own set N1 to N14, different from the build's M1 to M12, in a scratch archive: killed N1, N2, N3, N4, N6, N9, N10; survived N7 and N8 (behaviour changes, untested), N11 and N12 (two of three listing callers, survive the full suite), N5, N13, N14 (judged equivalent or safe-direction) |
| 5. Gates and leak scan | PASS | My detached worktree at a8223b96: `gate02_import_order.sh` exit 0; `gate03_lint.sh` (ruff, no path) "All checks passed!" exit 0; `gate04_unit_suite.sh` 7072 passed, 143 skipped, 24 deselected, 1 xfailed, 0 failed, exit 0, 457 s; `check_public_leaks.py --base origin/develop` 0 findings, PASS |

## What I verified with my own probes, and what I only read

- Own probes: every row above; the live check on round 4's joined items (Jev mode, 3 repetitions, $0.00135); the end-strip fragment on develop for comparison; the merge check against today's develop.
- Read only: the build's M1 to M12 results; the J3-101-08 comment update (read in `graph.py:9670-9712`, accurate); the build's statement that `raw/build_r4/` scripts are counts-only; the guard-tier mode of the check (no guard call made by me); researcher and plain-language depth through `write_node` end to end.

## Inside fixes made during this phase

Stated prominently, as the review rules ask. J4-101-01 (joined reads of wrapped gene rows), J4-101-03 (the record-sentence boundary adopted for J3-101-03), J4-101-05 and J4-101-07 (round 4's tests) sit inside round 4's own fixes; J4-101-02 sits inside round 3's prefix design and contradicts round 4's stated property for partial verdicts. None of them shows a sentence develop would not show beyond the rule's intent, and none is blocking in my judgement after the live and develop comparisons above.

## Verdict

PASS against card 101's goal contract. A copied sentence is either a whole record sentence or a check item, and every failure of the check shows only what is safe; the code-built list is byte-identical to develop; no recorded draft shows a sentence develop does not show or loses all its prose, under no, all, or any partial approval. No blocking finding. For the owner, in plain words: the round closes what it set out to close; a capitalised word after "e.g." or "vs." can still slip a paper's opposite through (J4-101-04, as on develop today); a list of names can be cut back to just the names when the check holds the claim joined to them (J4-101-02, a shape develop already shows); and two test gaps mean a later edit could quietly change the fallback record list (J4-101-07). DECISIONS.md needs a hand merge (J4-101-06).
