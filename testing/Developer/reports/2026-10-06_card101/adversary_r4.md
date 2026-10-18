# Card 101 round 4: adversary report

Fresh-context adversary, branch fix/card101-copied-cuts at a8223b96, base develop d8179c4e. Findings are appended as they are established.

## Findings

Probes run against `git worktree add --detach` copies of a8223b96 (branch) and d8179c4e (develop) in the session scratchpad, never against this worktree. Harness `h.py`: the real `run_grounding_pass` with a candidate sink (shown with no approvals, "none"), then again approving every collected item ("all"). Scripts and outputs in the session scratchpad, `adv101r4_raw/`.

### A4-101-01: a faithful writer copy of a negated record sentence shows its opposite when an abbreviation is followed by a capital (S. Typhimurium, U.S. FDA, vs. PCI, e.g. RSV)
- Severity: major. Not blocking for this round in my judgement: same as develop, and the mechanism is the residual round 4 names ("Dr. Smith"). Filed because the named residual is wider than stated: it needs no writer cut at all.
- What: the writer's narrative is split at every ". " (`_SENTENCE_BOUNDARY`), so a writer who copies the whole record sentence word for word has its head ("No isolates of S.") cut off as an unmarked sentence and stripped; the tail after the abbreviation is a whole record sentence by `_RECORD_SENTENCE_BOUNDARY` (a capital follows), so it shows with no check.
- Reproduction (`p1.py`, both trees identical, no check item on the branch):
  - record "No isolates of S. Typhimurium carried the blaCTX-M gene."; writer, word for word, "No isolates of S. Typhimurium carried the blaCTX-M gene [1]." Shown: "Typhimurium carried the blaCTX-M gene [1]."
  - record "It is unproven that the U.S. FDA-approved vaccine prevents bronchiolitis in infants."; writer the same words. Shown: "FDA-approved vaccine prevents bronchiolitis in infants [1]."
  - record "The trial did not show that surgery vs. PCI reduced mortality in adults."; writer the same words. Shown: "PCI reduced mortality in adults [1]."
  - record "No vaccine was effective, e.g. RSV prefusion F vaccine prevented no admissions."; writer the same. Shown: "RSV prefusion F vaccine prevented no admissions [1]."
- Why it matters: the reader sees the paper's opposite cited to the paper, and the writer did nothing wrong. Serovar names after "S." (pathogen records, a planned tool), agency acronyms after "U.S." and acronyms after "vs."/"e.g." are ordinary in NCBI text. Not a regression: develop shows the same four sentences.
- NOT FIXED

### A4-101-02: a sentence in the middle of a multi-sentence quotation or bracket carries no marks of its own, so it is "whole" and shows as the record's claim
- Severity: major. Not a regression (develop identical). Inside the claim of round 4's item 7 ("a copy with its quote marks or brackets left off goes to the check"), which holds only for the first and last sentence of a quotation.
- Reproduction (`p1.py`, both trees identical, no check item):
  - record 'Advertisers claimed that "this drug is a miracle. Drug X cures cancer. It is safe." Regulators found every claim false.'; writer "Drug X cures cancer [1]." Shown: "Drug X cures cancer [1]."
  - the same with curly quotes (U+201C, U+201D): shown.
  - record "An early uncontrolled report (since retracted. Ribavirin cured every infant. No controls were used.) prompted this trial, which found no benefit."; writer "Ribavirin cured every infant [1]." Shown.
- Why it matters: the claim a record quotes in order to reject it is printed as the record's finding, with no check. Rare shape; the check is never asked.
- NOT FIXED

### A4-101-03: when the check holds or cannot run, a held last clause still leaves a leftover piece, including "Ribavirin [1]." and a sentence with the writer's limit cut off
- Severity: major. Blocking: unsure, the owner's call. INSIDE THIS ROUND'S FIX: round 4's fragment rule keeps "a held clause itself" as an end strip (`grounding.py` 1764 to 1779, build_r4 "Choices": "Add back exactly develop's middle-strip drops"). It contradicts build_r4's user-words line "When the check holds something back or cannot run, a sentence is either shown as develop showed it or not at all; never a leftover piece such as 'Ribavirin [1].'" Regression against develop under the check's failure modes.
- What: a sentence whose first clause is whole (or a wrapped name) and whose last clause is a copied cut. The cut is held; nothing was stripped before it, so the middle-strip rule does not fire and the prefix is shown alone. Develop showed the whole sentence.
- Reproduction (`p2.py`, `p3_floor.py`):
  - records [1] name "Ribavirin" (Drug), [2] "Ribavirin is first-line care for bronchiolitis in infants with severe heart disease, but routine use is not recommended."; writer "Ribavirin [1] is first-line care for bronchiolitis in infants [2]." Develop shows the sentence. Branch, check holds: "Ribavirin [1]." Branch, check approves: the sentence.
  - writer "In babies, ribavirin [1] is first-line care for bronchiolitis in infants [2]." Branch, check holds: "In babies, ribavirin [1]."
  - records [1] title "Azithromycin shortens the course of bronchiolitis in infants." and [2] the same paper's abstract "Azithromycin shortens the course of bronchiolitis in infants only when a bacterial co-infection is confirmed by culture; otherwise it has no effect."; writer "Azithromycin shortens the course of bronchiolitis in infants [1] only when a bacterial co-infection is confirmed by culture [2]." Through the real `core.graph._ground_with_sentence_check`: budget 3.9 s (below the floor) and a `SentenceCheckUnreadable` check both show "Azithromycin shortens the course of bronchiolitis in infants [1]." Develop, same two failure modes: the whole sentence with its limit.
- Why it matters: the third case is the shape this card exists to stop, a limit dropped, produced by the fail-closed path. The words shown are a whole record sentence (the title), so the card's goal contract is met to the letter; what the reader sees is still a stronger claim than develop showed and than the writer wrote. The first two are verbless fragments on the page. `drop_record_restatements` may remove "Ribavirin [1]." later in `core.graph`, but not "In babies, ribavirin [1]." (a word the record lacks) and not the azithromycin sentence. The rejected alternative in build_r4 ("drop the whole sentence whenever a cut is held") closes all three. None of the 168 recorded drafts hits this (build_r4 replay), so it is constructed.
- NOT FIXED

### A4-101-04: past 600 characters the check approves a joined item it never read, so a cut or a join at the end of a long sentence is shown on an approval of the sentence's first 600 characters
- Severity: critical. Blocking in my judgement. INSIDE THIS ROUND'S FIX: round 4's per-clause joined items (J3-101-05, `_copied_clause_candidate`, "the last item a sentence sends is the whole shown sentence"). Not a regression against develop, which shows both sentences below with no check at all.
- What: `sentence_check._item_block` shows the checker `candidate.sentence[:MAX_SENTENCE_CHARS]` (600), and `_proposed_pairs` reads the same 600. A joined item is the writer's sentence up to its clause, so for any clause that starts after character 600 the checker is shown exactly the same SENTENCE text as for the item before it, plus one more quote. The approval is keyed on the whole prefix, so the unread clause is shown.
- Reproduction (`p4_trunc.py`, live, the shipped `check_reworded_sentences` in Jev mode, 6 runs, $0.0047 in all; `p4_trunc_live.jsonl`): record [1] "Methods: We reviewed 12 trials. Conclusions: supportive care remains the mainstay of treatment.", six trial titles [2] to [7], one long writer sentence listing them.
  - Cut variant: record [8] "Ribavirin halved mortality in adults with severe respiratory syncytial virus pneumonia after lung transplant."; the sentence ends ", and ribavirin halved mortality [8]." Items 7 and 8 both show the checker a sentence ending "chest physiotherapy in hospi" (item 8 is 701 characters). Approved 2 of 3 runs; the reader sees "... under two years of age [7], and ribavirin halved mortality [8]." in an answer about babies with bronchiolitis.
  - Join variant: record [8] "Ribavirin halved mortality. The trial enrolled adults after lung transplant.", record [9] population "Children"; the sentence ends ", and ribavirin halved mortality [8] in children [9]." Approved 3 of 3; shown: "... and ribavirin halved mortality [8] in children [9]." No record says children. This is J3-101-05's own "in children" join, which round 4 says is now read joined.
  - With no approvals, nothing from the sentence is shown, so the hole is the approval path, not the fail-closed path.
- Frequency: of 1,819 writer sentences in the 168 recorded drafts, 3 are longer than 600 characters (longest 1,298); none of the 34 items round 4 collects on them is (`p5_len.py`, `p5_len_branch.txt`). Researcher list sentences are where it lives.
- Why it matters: the card's contract is that a cut is shown only when the check approves it. Here the check approves something else. The same truncation also covers round 3's single cut items whenever the writer's sentence before the cut exceeds 600 characters, and quotes past 600 characters (`MAX_QUOTE_CHARS`) of a long record sentence.
- Suggested fix (for the lead, not applied): an item whose sentence or any quote exceeds the cap is not sent and so not approved (fail closed), or the cap is checked where items are built.
- NOT FIXED

### A4-101-05: the code-built listing drops a row whose piece opens on a comma, colon or semicolon, which develop showed
- Severity: minor (rare shape). Not blocking. INSIDE THIS ROUND'S FIX (`_is_code_built_row`, `grounding.py` 1021 to 1037) and a regression against develop on the listing path.
- What: `_is_code_built_row` compares `_whole_form(_without_glue(segment))` with `_whole_form(piece)`. `_without_glue` strips a leading ",", ";" or ":" from the segment but the piece keeps it, so the two never match; the row is then a cut with no candidate sink and is stripped.
- Reproduction (`p7_listing_real.py`, `build_structured_fallback_narrative` then `run_grounding_pass(..., code_built_listing=True)`):
  - abstract "Azithromycin was given for seven days. , but it did not shorten the illness in infants." Develop: ['Azithromycin was given for seven days [1].', 'It did not shorten the illness in infants [1].']. Branch: ['Azithromycin was given for seven days [1].'] (the limiting row is gone).
  - title "Does azithromycin shorten bronchiolitis? : a randomised controlled trial in infants under two." Develop: two rows. Branch: only 'Does azithromycin shorten bronchiolitis [1].'
- Fuzz (`p6_listing_fuzz.py`, 20,000 random values built from abbreviations, quote marks, brackets, list markers, line breaks, ellipses, non-breaking spaces and every boundary mark, seed 7, both trees, markers normalised): 4,196 cases differ; every one has a piece opening on ",", ";" or ":"; in 0 cases does the branch show a row develop does not (`p6_summary.txt`). So the listing flag lets nothing new through; this is its one loss.
- Why it matters: the listing is the floor when the writer's prose fails; losing the "but it did not" row leaves the record's limit off the page. The same fault makes the repair probe (`_code_built_lines_will_cite`) count such a finding as not covered.
- NOT FIXED

### A4-101-06: a marked segment of connective words only ("and with", "or") is read by the check but not shown, so the shown sentence differs from the approved item
- Severity: minor. Not blocking. Not a regression (develop drops such segments too, with no check at all); it qualifies round 4's property "every shown prefix is an approved item".
- What: `run_grounding_pass` skips a marked segment whose words are all in `_CONNECTIVES` ("X [1] and with [1], Y [2]"), so it never reaches `kept_parts`; `_copied_clause_candidate` builds the item from the raw sentence, so the item keeps those words.
- Reproduction (`p8_writer_fuzz.py`, seed 3, 4,000 random writer drafts over 11 record sentences, 3,383 with items, 4 random partial approval sets each): 54 shown sentences are neither a no-approval sentence nor an approved item; all 54 match an approved item once connective words are removed from both, and with that allowance 0 of 3,383 (seed 3) and 0 of 5,117 (seed 11) break the property. Example: writer "Montelukast [1], but showed no benefit in infants with [1] and with [1], Infants [2].", approved item "Montelukast, but showed no benefit in infants with and with, Infants"; shown "Montelukast [1], but showed no benefit in infants with [1], Infants [2]."
- Why it matters: small. An "or" or "as well as" the check read can vanish from what is shown. Recorded here because the fuzz otherwise confirms the per-clause property, which is worth stating: under random partial approvals no shown sentence was anything but an approved item or a no-approval sentence.
- NOT FIXED

### A4-101-07: when the record sentence around a cut is longer than 600 characters, the check is given the cut itself as its quote and approves it, so the "There is no evidence that" reversal is shown again
- Severity: critical. Blocking in my judgement. INSIDE CARD 101'S FIX (round 3's `_copied_record_span`, kept by round 4: a cut's quote is `widen_to_record_sentences(claim, value)`). Not a regression against develop, which shows the cut with no check.
- What: `widen_to_record_sentences` returns the quote unchanged when the run of record sentences holding it is longer than `MAX_WIDENED_QUOTE_CHARS` (600). For a writer's quote that was card 89's safe fallback; for a copied cut the "quote" is the cut, so the check item reads SENTENCE = the cut and QUOTES = the same words. A run passes 600 characters when one record sentence is long, or when the sentences after it open on a digit, a lowercase gene name or "p" (no capital, so `_RECORD_SENTENCE_BOUNDARY` does not split).
- Reproduction (`p10_quote.py`, live, shipped `check_reworded_sentences` in Jev mode, `p10_quote_live.jsonl`, $0.00014 for 6 calls):
  - VARIANT=neg: record "There was no evidence that azithromycin shortened the illness in infants with bronchiolitis. 142 infants were enrolled at six sites ... 95% of diaries were returned complete ... p values were adjusted ... 16 serious adverse events occurred, ..." (one run of about 700 characters); writer "Azithromycin shortened the illness in infants with bronchiolitis [1]." The one check item's quote is 64 characters, the writer's own words. Approved 3 of 3; shown "Azithromycin shortened the illness in infants with bronchiolitis [1]." The paper says there was no evidence for it.
  - Long single sentence: a 520-character methods clause then "azithromycin shortened the illness by two days, but only in the small subgroup with a bacterial co-infection confirmed by culture, ..."; writer "Azithromycin shortened the illness by two days [1]." Quote given to the check: 46 characters, the cut itself, no "but only". Approved 3 of 3, shown.
- Frequency: none of the 55 distinct record values in the recorded traces has a run over 600 characters, and none of the 34 items has an unwidened quote (`p11_runs.py`, `p11_counts.txt`). The traces cover three questions; long methods sentences, trial eligibility text and abstracts whose sentences open on numbers are where it lives.
- Why it matters: this is A2-101-01, the reversal card 101 was opened for, with the check now reporting it as approved.
- Suggested fix (not applied): for a copied clause, a widening that fails or is too long sends no item (held, fail closed), or the item quotes the record text around the cut cut to the cap rather than the cut itself.
- NOT FIXED

## What held, by my own probes

| Claim | How I tested it | Result |
|---|---|---|
| Round 4's named attacks (colon labels, semicolons, lowercase after an abbreviation, record questions as statements, quote marks or brackets left off the first or last sentence) go to the check | `p1.py`, both trees | Held. Also held: a fullwidth semicolon, a unicode ellipsis, a record line break with no stop, a cut before "(p < 0.05)", a sentence opening on a digit or lowercase word: each a check item |
| Every shown sentence under partial approvals is a no-approval sentence or an approved item | `p8_writer_fuzz.py`, 8,500 random drafts with items, 4 random approval sets each | Held, except connective-only segments (A4-101-06) |
| The listing flag lets no writer copy and no new row through | Read the three callers (`core/graph.py` 9816, 13218, 13323: each passes `build_structured_fallback_narrative`'s output); `p6_listing_fuzz.py`, 20,000 cases | No writer text reaches the flag; 0 rows shown that develop does not show; one loss class (A4-101-05) |
| The 168 recorded drafts | `p9_replay.py`, my own script, both trees, plus 8 random partial approval sets per draft | Develop 59 shown, branch 52 with no approvals and 59 with all; 0 sentences the branch shows that develop does not, under any approval set; 0 drafts emptied; hb4 shows what develop shows. Matches build_r4 |
| Fail closed | `p3_floor.py` through the real `_ground_with_sentence_check`: budget 3.9 s, and `SentenceCheckUnreadable` | Nothing unread is shown; but see A4-101-03 for what the prefix says |

## Not covered

- The guard-tier mode of the check (production's default); every live call was Jev mode.
- Live answers end to end, Researcher and Plain language depths, gene questions.
- The named residuals (A3-101-05 joined whole sentences, wrapped values, "Dr. Smith", the quoted claim the check approves, reworded clauses after a cut) were not re-attacked except where A4-101-01 and 02 show them wider than named.

## Spend

| Item | Calls | Cost |
|---|---|---|
| `p4_trunc.py`, 6 runs | item and pair calls, Jev | $0.00462 |
| `p10_quote.py`, 6 runs | Jev | $0.00014 |
| Everything else | 0 | $0 |

## Verdict

FAIL against card 101's goal contract ("a copied cut goes to the sentence check, which fails closed"). Two blocking findings, both inside card 101's own fix (the stop condition), neither a regression against develop, which shows both sentences with no check at all:

- A4-101-07: a cut from a record sentence run longer than 600 characters is sent to the check with its own words as its quote; the live check approved "Azithromycin shortened the illness in infants with bronchiolitis" from "There was no evidence that azithromycin shortened ..." 3 of 3.
- A4-101-04: past 600 characters a joined item is approved on text the checker never sees; live, "and ribavirin halved mortality [8] in children [9]" was shown 3 of 3, and a population-dropping cut 2 of 3.

Owner's call: A4-101-03 (inside round 4's fix and worse than develop when the check holds or cannot run: "Ribavirin [1].", and a limit dropped from the writer's sentence). Not blocking: A4-101-01 and 02 (residuals wider than named, same as develop), A4-101-05 (listing loss, inside this round's fix, rare), A4-101-06 (minor).

On merge: nothing I found makes the branch show a false sentence that develop does not already show unchecked. The blocking items are holes in the closure the card claims, not regressions. Whether to merge an improvement that does not yet meet its contract is the owner's decision.

Verified by my own probes: every shown or held output above (offline through `run_grounding_pass` on both trees), the five live results, the listing fuzz, the writer fuzz, the 168-draft replay, the failure modes through `_ground_with_sentence_check`. Read only: the build's mutation results and gate runs, and the guard-tier path.
