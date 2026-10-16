# Card 101 adversary, round A2

Adversary, dial position 2, one round, 2026-10-16. Subject: pull request #248, `git diff 7626fe85...81550539`. Branch tree at 81550539, develop tree at 7626fe85, both probed through `run_grounding_pass` offline.

## Findings

Method: my own probe (scratchpad `adv/probe.py`, not the builder's scripts) runs each case through the real `run_grounding_pass` on each tree in a separate process, first pass with a `candidate_sink`, then a second pass approving every item `sentence_check._read_whole` would send. "shown(none)" is the check approving nothing, "shown(all)" approving everything. Output pasted as printed.

### A2-101-01: A curly apostrophe closes a stray curly opener, and a whole copy develop showed vanishes with no check asked
- Severity: critical (inside this phase's fix, slice 2 `_mark_spans`)
- What: `_mark_spans` puts every Pi and Pf character in one class "q", so the right single quotation mark used as an apostrophe (U+2019, category Pf, as in "patients’") pairs with any earlier unclosed “ or ‘. The "unmatched opener is ignored" rule (A-101N-13) never fires, because the opener is no longer unmatched. Every break between them is graded `mark`, every whole copy in between becomes a cut, the glued run passes 600 characters, and the clause is held unsent. A reworded sentence develop sent to the check is held too.
- Reproduction: record = `We studied the so-called “miracle regimen in a cohort. ` + seven sentences `Secondary outcome number i was measured in every enrolled participant at baseline and follow-up.` + ` Mortality was unchanged in the treated group. The patients’ families were surveyed.`
  - narrative `Mortality was unchanged in the treated group [1].`
    - DEV shown(none)=['Mortality was unchanged in the treated group [1].'] shown(all)=same, no item
    - NEW shown(none)=[] shown(all)=[] and no item at all
    - NEW units: every break after the first graded 'mark' (10 units, grades start, mark x9)
  - narrative `Treated patients had the same mortality [1: "Mortality was unchanged in the treated group"].`
    - DEV item sent=True q=['Mortality was unchanged in the treated group.']
    - NEW no item, shown(none)=[] shown(all)=[]
- Why it matters: the person loses a word-for-word sentence of the paper that develop showed, in every approval mode, because of one typographic apostrophe after one stray opening quote. This is the A-101N-13 drop the design says is impossible by construction ("A stray bracket or quote mark earlier in the abstract changes nothing"). Curly apostrophes are common in publisher-typeset abstracts. The fuzz could not see it: its alphabet named quote marks and brackets but no Pf apostrophe after a word.
- NOT FIXED

### A2-101-02: A curly apostrophe inside a curly quotation ends the quotation early, and the quoted claim shows unchecked as the paper's finding
- Severity: major (the slice 2 claim "closed for curly double" does not hold; outcome same as develop)
- What: the same Pf apostrophe closes the “ it sits inside, so the quotation's span ends at "drug’s" and the breaks inside the quotation grade `hard`.
- Reproduction: record `Advertisers claimed that “this drug’s effect is a miracle. Drug X cures cancer. It is safe.” Regulators found every claim false.`, narrative `Drug X cures cancer [1].`
  - DEV shown(none)=['Drug X cures cancer [1].'] shown(all)=same
  - NEW shown(none)=['Drug X cures cancer [1].'] shown(all)=same, no item
  - NEW units: [('Advertisers claimed that “this drug’s effect is a ', 'start'), ('Drug X cures cancer.', 'hard'), ('It is safe.” Regulators found every claim false.', 'hard')]
- Why it matters: a claim the paper quotes in order to reject it is printed as the paper's finding with no check, which is A4-101-02, the case slice 2 exists to close. Any possessive or contraction inside a typographic quotation reopens it.
- NOT FIXED

### A2-101-03: Two abbreviations in one sentence: the check reads the copy without the paper's "No"
- Severity: major (inside this phase's fix, slice 3's glue "once")
- What: `record_sentence_run` glues across one `abbrev` break each side. A sentence with two single-capital abbreviations is three develop units; a copy of the last unit gets a run of the last two, and the negation in the first unit is not in what the check reads.
- Reproduction: record `No isolates of S. Typhimurium or S. Enteritidis carried the blaCTX-M gene. Resistance was rare.`
  - narrative `Enteritidis carried the blaCTX-M gene [1].`
    - DEV shown(none)=['Enteritidis carried the blaCTX-M gene [1].'] (unchecked)
    - NEW shown(none)=[] shown(all)=['Enteritidis carried the blaCTX-M gene [1].'] item sent=True q=['Typhimurium or S. Enteritidis carried the blaCTX-M gene.']
  - narrative `Enteritidis isolates carry the gene [1: "Enteritidis carried the blaCTX-M gene"].` (reworded)
    - DEV item q=['Enteritidis carried the blaCTX-M gene.']
    - NEW item q=['Typhimurium or S. Enteritidis carried the blaCTX-M gene.']
  - NEW units: [('No isolates of S.', 'start'), ('Typhimurium or S.', 'abbrev'), ('Enteritidis carried the blaCTX-M gene.', 'abbrev'), ...]
- Why it matters: the bar's first half ("every case gives the check a run that contains the paper's negation, or holds") fails. The check is shown a qualifier-free run that literally says the isolates carried the gene, so an approval prints the reversal with a check behind it. Better than develop (which showed it unchecked) on the copy path, but the card's promise is not met. "S. Typhi or S. Paratyphi", "E. coli and K. pneumoniae" with capitals, "U.S. and E.U." are the realistic shapes.
- NOT FIXED

### A2-101-04: The adjacency rule holds a whole copy develop showed when the writer's previous sentence is an unmarked copy of the record's previous sentence
- Severity: major (inside this phase's fix, slice 4 `_joined_to_cut_head`)
- What: `_joined_to_cut_head` joins the previous stripped unmarked sentence and the copy with a space and asks whether the result is contiguous in the record. When the previous reply sentence is the record's previous WHOLE sentence (with its full stop), the join is contiguous too, so a hard break is read as a cut. Nothing tests that the record's break between them is soft.
- Reproduction: record `Drug X was given to 40 patients. Mortality fell by 20% in the treated group.`, narrative `Drug X was given to 40 patients. Mortality fell by 20% in the treated group [1].`
  - DEV shown(none)=['Mortality fell by 20% in the treated group [1].'] shown(all)=same, no item
  - NEW shown(none)=[] shown(all)=['Mortality fell by 20% in the treated group [1].'] item sent=True q=['Drug X was given to 40 patients. Mortality fell by 20% in the treated group.']
  - NEW units: second unit graded 'hard'
- Why it matters: a sentence copied word for word, which develop showed, now waits on the check and is lost when the check holds it, errs or times out. Writers often leave the first of two copied sentences unmarked. The design's controls tested framing (not in the record) and a marked predecessor, never an unmarked predecessor that is itself a whole record sentence. The bar "0 develop sentences dropped under approves none" fails.
- NOT FIXED

### A2-101-05: Abbreviation-shaped sentence ends ("U.S.", "i.e.") turn whole copies develop showed into check items
- Severity: minor (the design names this cost as A-101N-05; filed because build.md's bar reports 0 dropped, which only holds on corpora with no such ends)
- Reproduction:
  - record `The vaccine was approved in the U.S. Mortality was unchanged in the trial.`, narrative `Mortality was unchanged in the trial [1].`: DEV shown(none)=['Mortality was unchanged in the trial [1].']; NEW shown(none)=[], item sent q=['The vaccine was approved in the U.S. Mortality was unchanged in the trial.']
  - record `Neither arm improved, i.e. Placebo and Drug X performed alike. Mortality was 4%.`, narrative `Placebo and Drug X performed alike [1].`: DEV shown(none)=['Placebo and Drug X performed alike [1].']; NEW shown(none)=[], item sent with the "Neither arm improved, i.e." unit (this one is the intended catch)
- Why it matters: "approved in the U.S." or "in the U.K." at a sentence end is common in clinical abstracts; every following whole copy now depends on the check. Not a reversal, a cost the replay could not see.
- NOT FIXED

### A2-101-06: Any later closer of the same class rescues a stray opener: an enumeration "1)", an inch mark, a curly possessive
- Severity: critical (inside this phase's fix, slice 2; widens A2-101-01 beyond curly quotes)
- What: the "an unclosed opener holds nothing" rule only applies to openers still open at the value's end. A stray `(` is closed by an enumeration's `1)`; a stray straight `"` in opening shape is closed by an inch mark `5"` (closing shape, before whitespace); a stray `‘` by a possessive `children’s`. Each makes a span across many sentences, so a whole copy develop showed is dropped with no item. Below 600 characters the copy becomes a check item instead (shown(none) loses it).
- Reproduction (filler = seven sentences `Secondary outcome number i was measured in every enrolled participant at baseline and follow-up.`; narrative `Mortality was unchanged in the treated group [1].` in every case):
  - `Children were enrolled (aged 2 to 10 years. ` + filler + ` Mortality was unchanged in the treated group. Aims were 1) safety and 2) efficacy.`: DEV shown(none)=['Mortality was unchanged in the treated group [1].'], shown(all)=same; NEW shown(none)=[] shown(all)=[], no item
  - `The so-called "miracle regimen was tested. ` + filler + ` Mortality was unchanged in the treated group. A 5" catheter was used.`: DEV shown, NEW shown(none)=[] shown(all)=[], no item
  - `Clinicians call it the ‘wait and see approach. ` + filler + ` Mortality was unchanged in the treated group. The children’s parents agreed.`: DEV shown, NEW shown(none)=[] shown(all)=[], no item
  - short form `The “miracle regimen was tested. Mortality was unchanged in the treated group. The patients’ families agreed.`: DEV shown(none) shown; NEW shown(none)=[], item sent with the whole value as its run
- Why it matters: the design's A-101N-13 guarantee ("every later whole copy after a stray mark shows") holds only when nothing later in the abstract has the closer's category. Enumerations "1) 2)" and possessives are ordinary abstract text. This is the 8 October J-101N-02 / A-101N-13 drop reintroduced by the fix meant to prevent it.
- NOT FIXED

## Probes that found nothing (same output on both trees, or the branch better)

- Speed: a 2,588-character abstract with brackets, curly quotes and apostrophes, 12 copied clauses and one reworded quote: develop 0.0062 s per pass, branch 0.0118 s; with 40 stray `(` the branch 0.0181 s. About two to three times develop, still milliseconds; no slower answer a person would notice.
- "Fig. 2.", decimals ("0.5 mg.", "4.2%"), lowercase species ("E. coli." at a sentence end, "S. aureus"), "et al." (graded hard, same as develop), a negation in the next unit ("Drug X reduced mortality in mice. This was not observed in humans.": shown on both, develop's residual, not the branch's), nested straight quotes and a bracket spanning sentences (branch sends with the frame where develop showed unchecked or sent a cut), a quotation that opens a unit (branch's run now carries "Both claims were false.", develop's did not), "No strains of E. Coli carried mcr-1" (branch sends with the "No").
- Not run: live. Time box; the offline cases above already reproduce every finding through the real `run_grounding_pass`, no model needed. Spend $0.

## Verdict

FAIL.

- A2-101-01 critical, inside this phase's fix (slice 2): a curly apostrophe closes a stray curly opener; a whole copy develop showed is dropped with no check, and a reworded sentence develop sent is held.
- A2-101-02 major: a curly apostrophe inside a curly quotation ends it early; the quoted claim shows unchecked (same as develop, the slice 2 claim does not hold).
- A2-101-03 major, inside this phase's fix (slice 3): two abbreviations in one sentence; the check reads the copy without the paper's "No".
- A2-101-04 major, inside this phase's fix (slice 4): an unmarked previous sentence that is itself a whole record sentence turns the next whole copy into a check item; develop showed it.
- A2-101-05 minor: "U.S." or "i.e." at a sentence end turns the next whole copy into a check item (the named A-101N-05 cost; build.md's "0 dropped" cannot see it).
- A2-101-06 critical, inside this phase's fix (slice 2): any later closer of the same class (enumeration "1)", inch mark, curly possessive) rescues a stray opener; whole copies develop showed are dropped.

Verified with my own probes: every finding above and every "found nothing" line, run on both trees from scratchpad worktrees at 81550539 and 7626fe85. Only read, not run: build.md's live counts, mutation table, replay, fuzz and gate results. Findings 01, 03, 04 and 06 sit inside fixes made in this phase, which fires the review loop's stop condition.
