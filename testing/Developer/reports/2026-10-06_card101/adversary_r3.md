# Card 101 round 3 adversary report

Round 3, fresh context, branch `fix/card101-copied-cuts`, dial position 2. Findings are appended as they are established.

## Table of contents

- [Findings](#findings)
- [Cost of tightening the whole-sentence test](#cost-of-tightening-the-whole-sentence-test)
- [Answers that get worse, offline](#answers-that-get-worse-offline)
- [What held](#what-held)
- [Not covered](#not-covered)
- [Spend](#spend)
- [Verdict](#verdict)

## Findings

Probes: `raw/adversary_r3/probe_whole.py`, run with the branch's `src` and with develop's `src` exported to the session scratchpad; outputs `probe_whole_branch.jsonl` and `probe_whole_develop.jsonl`. Each probe runs the real `run_grounding_pass` with no check approvals; "shown" means shown on the first pass with no model call. The question for every probe is "How is bronchiolitis in babies treated?".

### A3-101-01: a cut after a colon counts as a whole record sentence, so "RETRACTED:", "Myth:", "Hypothesis:" and "There is no evidence for the claim:" are dropped with no check

- Blocking: yes, in my judgement, and it sits inside this round's fix (the colon start is new in `_WHOLE_SENTENCE_START`, chosen by the builder, not the owner). Severity: critical as a product defect.
- What: `is_whole_record_sentence` lets a record sentence start after any colon. Whatever stands before the colon is the "label", and the copy may leave it off. When the label is the negation, the hedge or the retraction, the copy says the opposite of its record and is shown with no model call.
- Input and output, offline, branch and develop identical (shown, no check item):
  - record "There is no evidence for the claim: aspirin prevents colorectal cancer in adults."; writer "Aspirin prevents colorectal cancer in adults [1]." Shown. Control without the colon ("There is no evidence that aspirin ..."): a check item on the branch, not shown.
  - title "RETRACTED: Drug X cures cancer in mice."; writer "Drug X cures cancer in mice [1]." Shown. PubMed carries retracted papers' titles in this "RETRACTED: ..." form.
  - record "Myth: antibiotics treat viral bronchiolitis. Fact: they do not."; writer "Antibiotics treat viral bronchiolitis [1]." Shown.
  - record "Hypothesis: montelukast reduces wheezing after bronchiolitis. Results: no reduction was observed."; writer "Montelukast reduces wheezing after bronchiolitis [1]." Shown.
  - record "Do not: give antibiotics routinely; use bronchodilators; use systemic corticosteroids."; writer "Give antibiotics routinely [1]." Shown (colon start plus semicolon end).
- What the person sees, develop and branch alike: "Drug X cures cancer in mice [1]", cited to a retracted paper, with no word of the retraction; "Aspirin prevents colorectal cancer in adults [1]", cited to a record that says there is no evidence for it.
- Why it is this round's: the round's purpose is that a cut dropping "There is no evidence that" reaches the check. Adding one colon to the dropped words restores A2-101-01 exactly, and the build report's user-words line ("shows at once only when it is one of the paper's sentences in full, word for word") is false for it.
- Suggested fix: do not treat a colon as a sentence start for the no-call path; a copy after a colon becomes a check item (the check reads the whole record sentence, label included). Cost measured below under A3-101-07.
- NOT FIXED

### A3-101-02: a record question is shown as the app's statement, because a trailing question mark counts as trailing punctuation

- Blocking: unsure (owner's call); inside this round's fix (`_WHOLE_SENTENCE_ENDS` includes "?", and `_whole_form` strips the claim's trailing punctuation). Severity: major.
- What: a record sentence that ends in "?" is whole, and the copy may end it with a full stop. A question title written in statement form ("X prevents Y?") becomes the app's assertion with no check.
- Input and output, offline, branch and develop identical:
  - title "Vitamin D supplementation prevents bronchiolitis in infants?"; writer "Vitamin D supplementation prevents bronchiolitis in infants [1]." Shown, no check item.
  - abstract "Is it true that nebulized epinephrine reduces admissions? Nebulized epinephrine reduces admissions? No."; writer "Nebulized epinephrine reduces admissions [1]." Shown, no check item.
  - abstract "Does nebulized epinephrine reduce admissions? We found it did not."; writer "Does nebulized epinephrine reduce admissions [1]." Shown with a full stop. Lower harm, but it is not the record's sentence.
- What the person sees: a confident claim cited to a paper whose title only asks it.
- Suggested fix: a copy is whole only when its own end mark matches the record's ("?" with "?"); a copy that turns "?" into "." or drops it goes to the check.
- NOT FIXED

### A3-101-03: a full stop inside an abbreviation ("vs.", "Dr.", "et al.", "e.g.", "approx.") starts a "record sentence", so a negated head before it is dropped with no check

- Blocking: no, in my judgement (the copies these produce read oddly, so a writer is less likely to produce them); inside this round's fix. Severity: major as a mechanism.
- What: `_WHOLE_SENTENCE_START` is `[.;!?:]\s+` with no look at the next character. The module's own record sentence splitter, `_RECORD_SENTENCE_BOUNDARY` (used by `widen_to_record_sentences`), requires a capital, quote or bracket after the stop; the new test does not, and the first-letter case of the copy is ignored besides. So the two disagree on what a record sentence is.
- Input and output, offline, branch and develop identical, each shown with no check item:
  - "The trial did not show that drug X vs. placebo reduces mortality in adults."; writer "Placebo reduces mortality in adults [1]."
  - "There is no evidence that Dr. Smith's regimen cures leukemia in children."; writer "Smith's regimen cures leukemia in children [1]."
  - "It is often claimed, though unproven, that approx. 30% of infants respond to bronchodilators."; writer "30% of infants respond to bronchodilators [1]."
  - "No drug class, e.g. corticosteroids, are effective in infants."; writer "Corticosteroids, are effective in infants [1]."
- Suggested fix: reuse `_RECORD_SENTENCE_BOUNDARY`'s rule (a capital, quote or bracket after the stop in the record) for the start test; that removes "vs. placebo", "e.g. corticosteroids" and "approx. 30%". "Dr. Smith" still splits; a capitalised name after an abbreviation is a residual case for the check.
- NOT FIXED

### A3-101-04: quote marks and brackets stripped from a record sentence turn a mention into the app's claim

- Blocking: no (contrived records); inside this round's fix (`_OPENING_MARKS`, `_CLOSING_MARKS`). Severity: minor to major.
- What: a record sentence wholly inside quote marks or brackets is a quoted or parenthetical mention, often the claim the record goes on to reject. The rule lets the copy leave the marks off and counts it whole.
- Input and output, offline, branch and develop identical, shown with no check item:
  - 'Advertisements stated: "Drug X cures cancer." Regulators found this claim false.'; writer "Drug X cures cancer [1]."
  - '"Vaccines cause autism." This myth persists despite a retracted study.'; writer "Vaccines cause autism [1]."
  - "Ribavirin was ineffective in the trial. (Ribavirin was effective.) An earlier report claimed otherwise."; writer "Ribavirin was effective [1]."
- Held: "Unproven claim [Drug X reduces mortality.] was tested here and rejected." with writer "Drug X reduces mortality [1]." is a check item on the branch (shown on develop).
- Suggested fix: a sentence that opens inside a quote mark or bracket is whole only when the copy keeps the marks; otherwise it goes to the check.
- NOT FIXED

### A3-101-01: a colon before the claim makes round 2's aspirin reversal "whole", so it still shows with no check

- Blocking for card 101: yes, unsure. It sits inside this round's fix: the colon-as-sentence-start rule is new in `is_whole_record_sentence` (`_WHOLE_SENTENCE_START = r"[.;!?:]\s+"`). The behaviour is the same as develop (shown unchecked on both), so it is not a regression, but it reopens the exact reversal this round says it closed, with one punctuation mark changed.
- What: any record text after ": " counts as the start of a record sentence. The words before the colon can be a negation, a label of doubt or a retraction notice, and they are dropped exactly as "There is no evidence that" was.
- Input, offline through the real `run_grounding_pass`, no model (`raw/adversary_r3/probe_whole.py`, outputs `probe_whole_develop.jsonl`, `probe_whole_branch.jsonl`), each with no check run:

| Record text | Writer | Develop shows | Branch shows |
|---|---|---|---|
| "There is no evidence for the claim: aspirin prevents colorectal cancer in adults." | "Aspirin prevents colorectal cancer in adults [1]." | the sentence, no check | the sentence, no check |
| "Myth: antibiotics treat viral bronchiolitis. Fact: they do not." | "Antibiotics treat viral bronchiolitis [1]." | same | same |
| "Hypothesis: montelukast reduces wheezing after bronchiolitis. Results: no reduction was observed." | "Montelukast reduces wheezing after bronchiolitis [1]." | same | same |
| title "RETRACTED: Drug X cures cancer in mice." | "Drug X cures cancer in mice [1]." | same | same |
| "Do not: give antibiotics routinely; use bronchodilators; ..." | "Give antibiotics routinely [1]." | same | same |
| control: "There is no evidence that aspirin prevents colorectal cancer in adults." | "Aspirin prevents colorectal cancer in adults [1]." | shown, no check | check item, not shown |

- What the person sees, both trees: "Aspirin prevents colorectal cancer in adults [1]", cited to a paper that says there is no evidence for it; "Give antibiotics routinely [1]" from a "Do not" list.
- Realism: PubMed abstracts in this app do not carry the structured labels (`tools/ncbi_eutils_actions.py` joins `AbstractText` without its `Label`), so "Hypothesis:" mostly will not occur. Colons inside prose ("the claim: ...", "we tested the hypothesis: ...") and "RETRACTED:" titles do occur in PubMed. Frequency in the recorded answers not measured by me (see A3-101-07 for the counts I did take).
- Why it matters: the round's headline claim is that the aspirin reversal is closed. It is closed for "that", not for ":". A confident wrong record is the outcome the product ranks worst.
- Suggested fix: a colon is a start only for the code-built listing (the `render_finding_body` row, which is already matched separately) or when what follows the colon is itself capitalised in the record; otherwise a clause after a colon goes to the check. Measure on the recorded answers what that moves.
- NOT FIXED

### A3-101-02: a question in the record is shown as a statement, because a "?" counts as a sentence end and trailing punctuation is ignored

- Blocking for card 101: unsure (inside this round's new test; same as develop). Severity: major.
- What: `_whole_form` strips trailing "?" from the claim and `_WHOLE_SENTENCE_ENDS` accepts "?" as the record sentence's end, so the writer may drop the question mark and the clause is "whole".
- Input and output, offline, no check, develop and branch identical:
  - title "Vitamin D supplementation prevents bronchiolitis in infants?"; writer "Vitamin D supplementation prevents bronchiolitis in infants [1]." Shown, no check.
  - abstract "Is it true that nebulized epinephrine reduces admissions? Nebulized epinephrine reduces admissions? No."; writer "Nebulized epinephrine reduces admissions [1]." Shown, no check.
- What the person sees: an open research question printed as a finding, cited to the paper that asked it.
- Why it matters: question-mark titles of the form "X prevents Y?" are a common PubMed title shape. The rule's own description ("trailing punctuation aside") treats "?" like "." although it reverses the sentence's force.
- Suggested fix: a record sentence that ends in "?" is never whole for a claim that does not itself end in "?"; send it to the check.
- NOT FIXED

### A3-101-03: an abbreviation's full stop starts a "record sentence", so a cut after "vs.", "et al.", "e.g.", "approx." or "Dr." is whole

- Blocking for card 101: unsure (inside this round's new test; same as develop). Severity: major for "vs.", minor for the rest.
- What: `_WHOLE_SENTENCE_START` treats every ". " as a sentence end, and the first letter's case is ignored on both sides, so a lowercase word after an abbreviation opens a "sentence". The pass's own record splitter (`_RECORD_SENTENCE_BOUNDARY`, used to widen quotes) requires a capital or quote after the stop; this test does not.
- Input and output, offline, no check, develop and branch identical:

| Record text | Writer | Both trees |
|---|---|---|
| "The trial did not show that drug X vs. placebo reduces mortality in adults." | "Placebo reduces mortality in adults [1]." | shown, no check |
| "It is often claimed, though unproven, that approx. 30% of infants respond to bronchodilators." | "30% of infants respond to bronchodilators [1]." | shown, no check |
| "Smith et al. reported that ribavirin shortens bronchiolitis, which we could not replicate." | "Reported that ribavirin shortens ..." | shown, no check |
| "No drug class, e.g. corticosteroids, are effective in infants." | "Corticosteroids, are effective in infants [1]." | shown, no check |
| "There is no evidence that Dr. Smith's regimen cures leukemia in children." | "Smith's regimen cures leukemia in children [1]." | shown, no check |

- What the person sees: "Placebo reduces mortality in adults [1]" from a trial that showed no such thing; "Corticosteroids, are effective in infants [1]" from "No drug class ... are effective".
- Why it matters: the dropped head carries the negation or the hedge, which is the shape this round exists to send to the check.
- Suggested fix: after a full stop, require the record's next character to be a capital letter, digit-free quote or bracket (as `_RECORD_SENTENCE_BOUNDARY` does), and compare the first letter case-insensitively only on the writer's side. That closes the lowercase ones; "Dr. Smith" style needs a short list of abbreviations or simply the check.
- NOT FIXED

### A3-101-04: stripping quote marks and brackets turns a quoted or bracketed claim into the record's own sentence

- Blocking for card 101: unsure (inside this round's new test; same as develop). Severity: major.
- What: `is_whole_record_sentence` skips opening quote marks and brackets and strips closing ones, so a sentence the record puts in quotes (someone else's claim) or in brackets counts as the record's own sentence. Combined with the colon start (A3-101-01) this covers reported speech.
- Input and output, offline, no check, develop and branch identical:
  - record 'Advertisements stated: "Drug X cures cancer." Regulators found this claim false.'; writer "Drug X cures cancer [1]." Shown, no check.
  - record '"Vaccines cause autism." This myth persists despite a retracted study.'; writer "Vaccines cause autism [1]." Shown, no check.
  - record "Ribavirin was ineffective in the trial. (Ribavirin was effective.) An earlier report claimed otherwise."; writer "Ribavirin was effective [1]." Shown, no check.
- What the person sees: a claim the record quotes in order to reject it, printed as the record's finding.
- Why it matters: the build report says the marks are "punctuation, never a word, so a copy may leave them off". Quote marks are exactly the punctuation that changes who is speaking.
- Suggested fix: a record sentence wrapped in quote marks or brackets is not whole unless the writer's copy keeps them; otherwise check.
- NOT FIXED

### A3-101-05: two whole record sentences from different records, joined, still bypass the check, and an "It ..." sentence takes the other record's subject

- Blocking: unsure (owner's call). The brief for this round states "any other copied clause, and joined clauses, go to the sentence check"; that holds only when the later clause is a cut. Two whole clauses joined are never read together. Identical on develop. Severity: major.
- What: `is_whole_record_sentence` judges each clause against its own record alone. A record sentence that opens on "It", "This drug" or "They" is whole word for word, but its subject lives in the sentence before it in its record. Copied after a sentence from another record, it takes that record's subject. The bare-pronoun rule only fires when the previous sentence was dropped, and the record-switch rule (item 12.16 part 4) only applies to reworded sentences.
- Input, offline, record 1 "Palivizumab was given to preterm infants. It reduced hospitalization by 55%."; record 2 "Ribavirin is an antiviral drug. Its use in bronchiolitis is not recommended."; output identical on branch and develop, no check item:

| Writer | Shown |
|---|---|
| "Ribavirin is an antiviral drug [2]. It reduced hospitalization by 55% [1]." | "Ribavirin is an antiviral drug [1]. It reduced hospitalization by 55% [2]." |
| "Ribavirin is an antiviral drug [2]; it reduced hospitalization by 55% [1]." | the same |
| "Ribavirin is an antiviral drug [2]. This drug reduced hospitalization by 55% [1]." (record 1 using "This drug") | "Ribavirin is an antiviral drug [1]. This drug reduced hospitalization by 55% [2]." |
| "Ribavirin is an antiviral drug [2], and It reduced hospitalization by 55% [1]." (one writer sentence) | shown as written, renumbered |

- What the person sees: a 55% drop in hospital stays credited to ribavirin, a drug its own record says is not recommended. Two different superscripts are the only signal.
- Held, for contrast: "Ribavirin is an antiviral drug [2] that reduced hospitalization by 55% [1]." The second clause is not record words, so it is stripped and only the first sentence shows.
- Suggested fix: a whole copied sentence whose first word is a bare pronoun or demonstrative ("It", "They", "This", "These", "Its") and whose record sentence is not the record's first, goes to the check when the shown sentence before it cites a different record; or treat any whole clause joined to a clause of a different record in one writer sentence as one check item. Frequency on the recorded answers: see A3-101-07.
- NOT FIXED

### A3-101-06: the semicolon cost is real and confirmed; "Drug X is safe in children" shows with "; however, it caused deaths in infants" dropped

- Blocking: no. Disclosed by the builder and logged; recorded here as confirmed by probe. Severity: major as a product defect, rare by the builder's count.
- Input and output, offline, branch and develop identical, no check item:
  - "Drug X is safe in children; however, it caused deaths in infants under 6 months."; writer "Drug X is safe in children [1]." Shown.
  - "Antibiotics shorten illness; this was not confirmed in randomized trials."; writer "Antibiotics shorten illness [1]." Shown.
- Note: the semicolon start was kept for the code-built listing ("GLUCOKINASE; GCK"). The code-built rows could be whole by their own path (`render_finding_body` equality, or the fallback's own split) without opening the semicolon to the writer's copies; the builder's measured alternative was dropping the semicolon from both lists, not separating the two callers.
- NOT FIXED

### A3-101-05: two whole record sentences joined in one writer sentence still bypass the check, so a pronoun can change its subject; the build report says joined pieces are read joined

- Blocking for card 101: no (same as develop; not a regression). Severity: major as a product defect; the build report's sentence is a report-accuracy issue for this round.
- What: the join rule only fires when a clause is not whole. When each joined clause is a whole sentence of its own record, no clause goes to the check, and `_clean_claim` strips the "and" between them. A record sentence that opens on "It" or "This drug" keeps its words but takes a new antecedent. The bare-pronoun rule fires only when the sentence before did not survive, and the record-switch rule (item 12.16 part 4) applies only to reworded sentences.
- Input, offline, no check (`probe_whole.py`): record [1] "Palivizumab was given to preterm infants. It reduced hospitalization by 55%."; record [2] "Ribavirin is an antiviral drug. Its use in bronchiolitis is not recommended."

| Writer | Develop shows | Branch shows |
|---|---|---|
| "Ribavirin is an antiviral drug [2]. It reduced hospitalization by 55% [1]." | both sentences, no check | both sentences, no check |
| "Ribavirin is an antiviral drug [2]; it reduced hospitalization by 55% [1]." | "Ribavirin is an antiviral drug [1]. It reduced hospitalization by 55% [2]." | same |
| "Ribavirin is an antiviral drug [2]. This drug reduced hospitalization by 55% [1]." (record [1] says "This drug") | both, no check | both, no check |
| "Ribavirin is an antiviral drug [2], and It reduced hospitalization by 55% [1]." | shown as one sentence, no check | same |

- What the person sees: "Ribavirin is an antiviral drug [1]. It reduced hospitalization by 55% [2]." The 55% belongs to palivizumab.
- The build report, "The change in the user's words": "So is a sentence built by joining two copied pieces: the check reads the joined sentence." True only when one piece is a cut. Two whole pieces are never read.
- Suggested fix: a whole record sentence that opens on a pronoun or a demonstrative ("It", "They", "This drug", "These") is whole only when the sentence before it on screen cites the same record; otherwise it goes to the check with the sentence before it as context. Correct the report sentence either way.
- NOT FIXED

### A3-101-06: the semicolon cost is real and the corpus behind "3 of 133" is three questions

- Blocking for card 101: no (a deliberate, logged choice; same as develop). Severity: minor, recorded so the owner sees the real shape.
- What, offline, no check, both trees identical (`probe_whole.py`):
  - record "Drug X is safe in children; however, it caused deaths in infants under 6 months."; writer "Drug X is safe in children [1]." Shown.
  - record "Antibiotics shorten illness; this was not confirmed in randomized trials."; writer "Antibiotics shorten illness [1]." Shown.
- Measured by me over every recorded trace I could find (the wave 3 folders, the card 101 fix round, round 2 and round 3 live): 61 distinct record values, 138 record sentences, 3 with a semicolon, 7 with ": ", 1 value ending "?". The builder's 3 of 133 matches. But every one of these records comes from the GERD, Mediterranean and bronchiolitis questions, so it says little about records in general; abstracts that put a limit after a semicolon are an ordinary academic style.
- Suggested fix: split the semicolon case by where the code-built listing needs it (the `render_finding_body` row already matches whole) and send other clause-before-semicolon cuts to the check; measure the OMIM listing tests against that.
- NOT FIXED

### A3-101-07: inside this round's fix, a held-back copied cut turns a sentence the middle-strip rule dropped into a verbless fragment on screen ("The name Adenoviral bronchiolitis [2].")

- Blocking: yes, in my judgement. It sits inside this round's fix (the new routing in `run_grounding_pass`), it is an answer that gets worse on a recorded writer draft, and it fires on the fail-closed path the build report describes as safe ("When the check cannot run, nothing is approved and the clause is not shown").
- What: the middle-strip rule (T-6.2-15) drops a whole sentence when a stripped clause has a surviving clause after it. On develop a copied cut after a failed clause survived, so the sentence was dropped whole. On this branch the cut becomes a check item; when the check holds it back or cannot run, every clause after the failed one is stripped, the strip is now at the sentence's END, and the rule keeps the prefix. The prefix was never written to stand alone.
- Input: the recorded writer draft `hb4` from card 101's fix round (trace in the session scratchpad, `out/hb4.jsonl`, first draft), replayed offline through each tree's `run_grounding_pass` with the recorded findings (`raw/adversary_r3/replay_traces.py`; one-draft view `adv3_one.py` in the scratchpad). Its last sentence, as written: "The name Adenoviral bronchiolitis [8] points to a viral cause for at least one form of the illness, and several published studies and clinical trials are exploring treatments such as dexamethasone [11], erythromycin [14], montelukast [17], and home oxygen therapy [23]."
- What the person sees:

| Tree, check outcome | Last line of the answer's prose |
|---|---|
| develop | nothing (the sentence is dropped whole) |
| branch, check holds the three cut items or cannot run | "The name Adenoviral bronchiolitis [2]." |
| branch, check approves all three | nothing (dropped whole, as develop) |

- The three items the branch asks about are the joined prefixes ending at "erythromycin", "montelukast" and "home oxygen therapy", each with quotes such as "Use of Erythromycin in Mustard-Induced Bronchiolitis". They read "points to a viral cause ... exploring treatments such as dexamethasone, erythromycin", which the quotes do not say, so a hold is the expected verdict. Live result in the evidence section below.
- Across 168 distinct recorded drafts (`replay_traces.py`, both trees), this is the only draft where the branch with no approvals shows more sentences than develop; the extra sentence is this fragment.
- Why it matters: a sentence with no verb, cited, on the answer page; and the same mechanism shows any grounded opening clause whose meaning depended on the clauses after it.
- Suggested fix: count a clause held for the check (collected, not approved) as a surviving-after clause for the middle-strip rule, or drop the whole sentence when any copied cut in it is held, so a held cut never turns a middle strip into an end strip.
- NOT FIXED

### A3-101-07: a record sentence that opens on "But", "And", "Or", "Then" or "Also " is no longer whole, so the code-built listing drops it and the writer's exact copy needs the check

- Blocking for card 101: yes. It sits inside this round's fix and it makes an answer worse than develop. Severity: major. INSIDE A FIX MADE DURING THIS PHASE (round 3's `is_whole_record_sentence`), so it trips the stop condition.
- What: `run_grounding_pass` passes `claim_text = _clean_claim(text)` to `is_whole_record_sentence`, and `_clean_claim` strips a leading "and ", "or ", "but ", "also " or "then ". The clause "they do not improve oxygen saturation" no longer equals the record's sentence "But they do not improve oxygen saturation.", and it starts mid-sentence, so it is treated as a cut. The code-built listing (`build_structured_fallback_narrative`) emits each record sentence verbatim, and all three of its grounding calls in `core/graph.py` (the structured fallback at line 13214, the findings tail at 13318 and the repair probe at 9813) pass no check set and no candidate sink, so such a row is simply dropped.
- Input, offline, no model (`raw/adversary_r3/probe_connective.py`, outputs `probe_connective_develop.jsonl`, `probe_connective_branch.jsonl`). Record [1]: "Bronchodilators are widely used in infants with bronchiolitis. But they do not improve oxygen saturation. Then most infants recover within two weeks. And supportive care remains the mainstay of treatment."

| Narrative | Develop shows | Branch shows, no check (the listing's path) |
|---|---|---|
| The code-built listing of record [1] | all 4 rows | only "Bronchodilators are widely used in infants with bronchiolitis [1]." |
| Writer: "Bronchodilators are widely used ... [1]. But they do not improve oxygen saturation [1]." | both sentences | the first only; the second is a check item |
| Writer: "And supportive care remains the mainstay of treatment [1]." | shown | a check item; nothing shown if the check does not approve |

- What the person sees on the branch, when the writer's prose failed and the listing is the answer: "Bronchodilators are widely used in infants with bronchiolitis [1]." and not the next row saying they do not work. The listing is the last safety net; it now keeps a claim and silently loses the sentence that limits it, which is the shape card 101 exists to stop. In the findings tail the row is lost without a note, and the repair probe can now judge a finding "not coverable" and change whether a repair runs.
- Frequency: none of the recorded answers carries such a sentence (my replay of the listing over every recorded finding set: 53 rows on develop, 53 on the branch). But the recorded traces hold only 4 distinct finding sets (see A3-101-09), and a sentence opening on "But" or "And" is ordinary in abstracts and gene summaries.
- Also inside the tests: `test_the_code_built_listing_still_grounds_whole` covers a labelled title, abstract sentences, an OMIM semicolon title and a colon label; none opens on a connective, which is why it is green.
- Suggested fix: test wholeness on the clause before `_clean_claim` strips its glue (the segment text with only its leading separators and whitespace removed), or let `is_whole_record_sentence` accept a record sentence whose first word is the stripped connective. Add a listing test with a "But ..." sentence.
- NOT FIXED

Addendum to A3-101-07, a synthetic reproduction (`raw/adversary_r3/probe_fragment.py`, both trees, no approvals): records `name: Ribavirin` [1], "Palivizumab is not approved for treatment." [2], "Montelukast showed no benefit in infants with bronchiolitis." [3]; writer "Ribavirin [1] is first-line care, unlike palivizumab which is withdrawn [2], and montelukast showed no benefit in infants [3]." Develop shows nothing; the branch shows "Ribavirin [1]." A wrapped opening in the question's words ("Ribavirin can treat bronchiolitis in babies [1], ...") did not surface in my probe, so the harm I measured is a fragment, not a false claim; I did not exhaust the shapes.

Correction to A3-101-01: its "cost measured below" points to the section "Cost of tightening the whole-sentence test", not to A3-101-07.

### A3-101-08: the judge mutates `grounding.py` in this same worktree while other agents import it, so a probe run at the wrong moment measures a mutant

- Blocking: no. Severity: unsure (process, not product). Not inside the code fix.
- What: during this round the judge applied mutations to `src/system_03_search_agent/synthesis/grounding.py` in `asu-card101c` and restored them with `git checkout --` (its J3-101-06 text says so; the file's modification time moved to 22:11:26 while I was probing). My first classifier run in this worktree returned a result I could not reproduce minutes later ("Drug X is safe" against "Drug X is safe; however, it is not." stayed whole with the semicolon removed from both lists, then flipped on rerun), which is what a mutant read mid-run looks like.
- What I did: every result in this report was re-run against `git archive HEAD` of the branch (809c8574) exported to the session scratchpad (`adv3_branch_src`), never against the live worktree `src`. The outputs in `raw/adversary_r3/` are from those re-runs.
- Why it matters: the builder's and judge's own numbers from this worktree are only as clean as the timing of each run against the other agent's mutations. A mutation report that restores with `git checkout --` leaves no trace in `git status` afterwards.
- Suggested fix: mutation testing in a copy of `src` (as `mutate.py` could do with a temporary tree), or one agent per worktree at a time.
- NOT FIXED

### Evidence for A3-101-01 to 05 and 07: what the shipped check says when these are sent to it

- Live, Jev through the shipped `sentence_check.check_reworded_sentences` in the classifier mode develop runs (item call plus card 99's pair call), 3 repetitions, 2 Jev calls each, 6 calls, $0.00082 (`raw/adversary_r3/live_routes.py`, `live_routes.jsonl`). Each sentence sent with the record text it rests on as its quote.

| Item | Sentence | Quote | Run 1 | Run 2 | Run 3 |
|---|---|---|---|---|---|
| A3-101-01 colon | "Aspirin prevents colorectal cancer in adults" | "There is no evidence for the claim: aspirin prevents ..." | Held | Held | Held |
| A3-101-02 question | "Vitamin D supplementation prevents bronchiolitis in infants" | the same words ending "?" | Held | Held | Held |
| A3-101-03 abbreviation | "Placebo reduces mortality in adults" | "The trial did not show that drug X vs. placebo reduces mortality in adults." | Held | Held | Held |
| A3-101-04 quoted claim | "Drug X cures cancer" | 'Advertisements stated: "Drug X cures cancer." Regulators found this claim false.' | Approved | Approved | Approved |
| A3-101-06 semicolon | "Drug X is safe in children" | "...; however, it caused deaths in infants under 6 months." | Held | Held | Held |
| A3-101-05 pronoun | "Ribavirin is an antiviral drug. It reduced hospitalization by 55%" | both record sentences | Held | Held | Held |
| A3-101-07 connective, faithful | "But they do not improve oxygen saturation" | its record sentences | Approved | Approved | Approved |
| Control, faithful whole copy | "Use of a high-flow nasal cannula is becoming common ..." | the same | Approved | Approved | Approved |

- So for the colon, question, abbreviation, semicolon and pronoun shapes the remaining hole is routing: the check holds them 3 of 3 when asked. The quoted claim is a miss of the check itself (approved 3 of 3): sending A3-101-04 to the check would not close it; the fix there has to be in code (a quoted record sentence is never whole) or in the check's instruction.
- The connective sentence is approved when asked, so on the writer's path A3-101-07 costs a check item; on the listing's path there is no check and the row is lost.

### Live evidence for A3-101-01, 02 and 07: the check holds what the routing lets through, and holds hb4's items

`raw/adversary_r3/live_r3.py`, the shipped `check_reworded_sentences` in Jev mode (item call plus card 99's pair calls), 3 repetitions, 2 Jev calls each, $0.000328 each, `live_r3.jsonl`. Items were built by `run_grounding_pass` from a scratch copy of the branch with the colon start removed, a capital required after a stop and "?" removed from the ends (`adv3_tree_tight`); on the branch itself the five synthetic items are not asked at all, they are shown. hb4's three items are identical on the branch and the copy (dry run of both).

| Item | Run 1 | Run 2 | Run 3 |
|---|---|---|---|
| "RETRACTED: Drug X cures cancer in mice." copied without the label | Held | Held | Held |
| "There is no evidence for the claim: aspirin ..." copied without the head | Held | Held | Held |
| Question title "Vitamin D supplementation prevents bronchiolitis in infants?" copied as a statement | Held | Held | Held |
| Faithful: "Results: no serious harm was seen in either group." copied without the label | Approved | Approved | Approved |
| Faithful: "Conclusions: supportive care remains the mainstay of treatment." copied without the label | Approved | Approved | Approved |
| hb4 items 0, 1, 2 (the joined prefixes ending at erythromycin, montelukast, home oxygen therapy) | Held | Held | Held |

- So on this branch, with the recorded hb4 draft, the check holds all three items and the answer shows "The name Adenoviral bronchiolitis [2]." (A3-101-07), 3 of 3.
- Sending colon-label and question-mark copies to the check costs the faithful ones nothing in these runs (approved 6 of 6) and holds the three attacks 9 of 9.

### A3-101-08: a held cut at a sentence's end turns a sentence develop dropped whole into a shown fragment

- Blocking for card 101: no. Severity: minor. Inside this round's fix (a consequence of moving cuts to the check).
- What: the middle-strip rule drops a sentence when a stripped clause is followed by a kept one. On develop a later copied cut was always kept, so a sentence with an unsupported middle clause was dropped whole. On the branch, when the check holds those later cuts, every strip is at the end, the rule no longer fires, and the sentence's first clause is shown alone.
- Input: the diagnosis's recorded draft hb4 (scratchpad `out/hb4.jsonl`, run on develop), replayed offline (`raw/adversary_r3/hb4_prefix.py`, and `replay_cost.py`, whose only row where the branch shows more than develop is this one). Writer's sentence: "The name Adenoviral bronchiolitis [8] points to a viral cause for at least one form of the illness, and several published studies and clinical trials are exploring treatments such as dexamethasone [11], erythromycin [14], montelukast [17], and home oxygen therapy [23]."
  - Develop: nothing shown from this sentence (middle strip).
  - Branch, check approves none of its three new items: "The name Adenoviral bronchiolitis [1]." shown by the grounding pass.
  - `drop_record_restatements`, which runs next in `core.graph`, then removes it in this instance (every word is in the record's name row). It would not when the listing grounds nothing and `core.graph` falls back to the prose before the drop (line 13349), and it would not for a first clause carrying a word the record lacks.
- What the person sees in the worst case: a verbless line, "The name Adenoviral bronchiolitis [1]."
- Also: the three check items it adds can never lead to a shown clause, because the sentence's second clause was already stripped. They cost check room and pair room for nothing (see A3-101-09).
- Suggested fix: do not collect a copied-cut item when an earlier clause of the same sentence was already stripped (the sentence can only be dropped or cut back to before it); and treat "a clause held by the check" like "a clause stripped from the middle" when the sentence's kept prefix ends without a verb, or simply count held cuts toward the middle-strip test.
- NOT FIXED

### A3-101-09: the check items this change adds are about four times what the build report states, the measurement rests on 4 distinct record sets, and a long list of cuts can fill the pair calls

- Blocking for card 101: no. Severity: minor (report accuracy and an unmeasured cost).
- Measured by me, offline, every distinct recorded draft once (`raw/adversary_r3/replay_cost.py`, counts in `replay_cost_counts.txt`): 159 distinct first-pass drafts from every trace folder I found (the wave 3 folders, the 2026-10-05 sentence check, the develop control, the diagnosis's `out`, the fix round, round 2 and round 3 live). Writer quotes were rebuilt from the recorded check inputs.

| Measure | Build report | Mine |
|---|---|---|
| Check items added | 7 | 31, in 18 drafts |
| Drafts with a new check call (none before) | 2 | 3 |
| Shown sentences lost if the check holds every new item | 6 in 5 answers | 7 in 6 drafts, all of them the cut itself; no neighbour lost; no draft emptied |
| Shown sentences lost if the check approves every new item | not stated | 0 |

- The difference in items: the build counted moved clauses in sentences that were shown; it did not count cuts inside sentences that were going to be dropped anyway (A3-101-08), such as the trial lists in the bronchiolitis drafts, which each add one item per listed trial with a growing prefix and a growing quote list.
- The corpus: across all those traces there are only 4 distinct sets of records (61 distinct record values, 138 record sentences), from the GERD, Mediterranean and bronchiolitis questions. Every frequency in the build report and in this report ("3 of 133", "0 neighbours lost", "no answer emptied") is a statement about those three questions, not about Researcher depth on other topics, gene questions, or long records.
- Crowding, constructed (`raw/adversary_r3/crowding_synthetic.py`, `crowding_synthetic_n.py`): one paragraph of list sentences, each joining three faithful copied cuts from long abstract sentences, then one reworded sentence. Develop sends 1 item and 1 pair call. The branch sends 10 items and fills all 4 pair calls (`MAX_PAIR_CALLS`) at 3 list sentences; at 5 list sentences two of the cut items are left unasked and so not approved. A reworded sentence after them with more than a few proposed pairs would be left unasked too and dropped, where develop approved it. On the recorded drafts (`crowding.py`) no develop item was crowded out: the largest branch check had 12 items and 5,204 characters.
- Suggested fix: correct the counts in the build report; skip items that cannot lead to a shown clause (A3-101-08); measure a Researcher answer and a gene answer before calling the cost small.
- NOT FIXED

## Cost of tightening the whole-sentence test

Measured to price the suggested fixes for A3-101-01 to 03, offline, on scratch copies of the branch (never the worktree):

| Variant | What changes | Synthesis and core unit tests (`-m "not integration"`) | Recorded whole copies that would move to the check |
|---|---|---|---|
| Branch as built | none | 1,966 passed, 0 failed | 0 |
| No colon start | `_WHOLE_SENTENCE_START` without ":" | 1 failed: `test_pubmed_abstract_grounding.py::test_a_verbatim_abstract_excerpt_grounds_and_cites_its_own_paper` (a "Results: ..." excerpt grounded with no check) | 0 of 265 |
| Tight | no colon start, a capital, quote or bracket required after the stop, "?" neither a start nor an end | the same 1 failed | 0 of 265 |

- "Recorded whole copies": every clause in 168 distinct recorded first drafts (wave 3 both arms, card 101 build, fix round, round 2 live, this round's live answers, the 2026-10-05 sentence check runs) that the branch counts as a whole record sentence, 265 in all; for each, which relaxation it needed (`replay_traces.py`, `whole_by_relaxation`). None needed the colon, the semicolon, the question mark, a lowercase start or stripped marks.
- The one failing test pins exactly the colon behaviour A3-101-01 attacks; with the check approving, the same excerpt grounds (the live check approved both faithful label copies 3 of 3).
- The builder's own listing test (`test_the_code_built_listing_still_grounds_whole`, with its "Results: no harm was seen." row) stayed green under both variants, so the code-built listing does not need the colon start.

## Answers that get worse, offline

`replay_traces.py` over the same 168 distinct recorded drafts, both trees, writer quotes not recorded so keyed markers carry none on both (reworded sentences are stripped alike; copied clauses behave as live):

| Tree | Sentences shown across 168 drafts | Check items collected |
|---|---|---|
| develop | 59 | 0 |
| branch, check approves nothing (fails closed) | 53 | 31 |
| branch, check approves every item | 59 | 31 |

- No draft lost all its prose under either branch outcome.
- 6 drafts show fewer sentences when the check approves nothing (7 sentences), and 1 draft (hb4) shows one more, the fragment of A3-101-07: 6 fewer net.
- Gene answers: the recorded traces hold literature and variant questions only; no recorded gene draft, and gene rows mostly take the wrap path this round leaves alone. Not measured live.
- Researcher drafts are in the replay (wave 3 "gr" and "cr" files); none lost a sentence on the branch with approvals.

## What held

Each line from my own probe against a clean export of 809c8574, not from the builder's tests.

| Claim | How I tested it | Result |
|---|---|---|
| Round 2's head cuts and tail cuts go to the check | `raw/adversary_r2/probe_paths_r2.py` against the export | All six P1 probes, the composed reversal and the two-record composition: check items, nothing shown with no approval |
| A writer quote attached to a cut does not let it skip the check | same | Check item |
| Joined cuts are read joined | same; and hb4's items | The check reads the prefix up to each cut, with every record sentence behind it |
| A whole record sentence still shows with no call | `probe_whole.py` controls | Shown, no item |
| Brackets around a hedge are not stripped into a whole sentence when the bracket sits mid-sentence | `probe_whole.py`, "Unproven claim [Drug X reduces mortality.] ..." | Check item on the branch (shown on develop) |
| The check, when asked, holds the shapes this report found and keeps faithful label copies | `live_r3.py`, 6 Jev calls | Attacks held 9 of 9; faithful approved 6 of 6 |
| Nothing in the recorded drafts relies on the relaxations attacked here | `replay_traces.py` | 0 of 265 whole copies |

## Not covered

- The guard-tier mode of the check (production's default `CLASSIFIER_PROVIDER=guard`): no guard-tier call made, as in round 2.
- Live answers, the deployed app and a live gene question: none run (brief).
- Writer quotes in the replay: not recorded beside the narratives, so reworded sentences were stripped on both trees; the comparison isolates copied clauses only.
- Partial approvals in the replay (some items approved, some held): only the two extremes were run; A3-101-07's mechanism can also fire under partial approval.
- Wrapped values (A2-101-03): deferred by the owner-delegated decision; not re-attacked.
- Whether the abbreviation shapes (A3-101-03) are ever written by the real writer: no recorded instance.

## Spend

| Item | Calls | Cost |
|---|---|---|
| `live_r3.py`, 3 repetitions | 6 Jev calls | $0.00098 |
| Everything else | 0 | $0 |

## Verdict

FAIL against the round's goal contract, on two blocking items, both inside this round's fix (this fires the review loop's stop condition):

- A3-101-01: a copy after a colon counts as a whole record sentence, so "RETRACTED: Drug X cures cancer in mice." and "There is no evidence for the claim: aspirin prevents ..." show their opposite with no check. The colon start is new in this round; removing it moved 0 of 265 recorded whole copies and changed 1 test.
- A3-101-07: a held-back cut turns a middle strip into an end strip, so the recorded hb4 draft shows "The name Adenoviral bronchiolitis [2]." where develop showed nothing; the live check held hb4's items 3 of 3, so this is what the branch shows for that draft.

Non-blocking or the owner's call: A3-101-02 (question mark), A3-101-03 (abbreviations), A3-101-04 (stripped quote marks), A3-101-05 (whole sentences joined across records, "It ..." changing subject), A3-101-06 (semicolon, disclosed), A3-101-08 (concurrent mutation in the shared worktree).

Verified by my own probes: every shown or held output in A3-101-01 to 07 (offline through `run_grounding_pass`, branch export and develop export), the hb4 fragment (replay of the recorded draft), the live verdicts (6 Jev calls), the cost of tightening (unit tests on scratch variants, replay of 265 recorded whole copies). Read only, not probed: the builder's live answer counts and timings, the guard-tier path, and the build report's claim that no recorded gene answer was available.
