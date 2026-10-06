# Card 101 adversary report

Round 1, fresh context, 2026-10-06. Branch `fix/card101-keep-limit-words`. Written as findings are established.

## Findings

### A-101-01: the "ly" ending turns every long hedge adverb into its adjective, so a sentence that uses the adjective anywhere silences the pair check on the dropped hedge

- Severity: blocking (offline fact established; live Jev result appended below as A-101-01b)
- Where: `PAIR_WORD_FORM_ENDINGS` includes `("ly", "")`, and `_proposed_pairs` treats a quote word as used when any sentence word shares a form, at any position. "ly" is not an inflection: it is the ending that makes the hedge and frequency adverbs the pair check exists to catch. The 5-character floor only protects the short ones (likely, mainly, highly, mostly, rarely, mildly).
- Input (offline, no model, `raw/adversary/probe_forms.py`, output `probe_forms.txt`): each quote and a sentence that drops the limit but carries another form of the limiting word elsewhere, run through develop's `check_phrases` (exported from `origin/develop`) and the branch's. 22 of 25 cases go from 1 or 2 pairs on the limiting word on develop to none on the branch, and in every one of the 22 the branch proposes no pair at all, so the pair check is silent and the sentence rests on the item question alone. Examples:
  - quote "Symptoms potentially caused by GERD are among the most common reasons for visits to primary care physicians.", sentence "Symptoms caused by GERD, a condition with potential complications, are among the most common reasons for visits to primary care physicians": develop `['symptoms potentially', 'potentially caused']`, branch `[]`. This is the card's own measured "potentially" case; GERD answers routinely say "potential complications".
  - "Proton pump inhibitors are generally safe for long-term use." to "Proton pump inhibitors are safe for long-term use in the general population": develop `['are generally', 'generally safe']`, branch `[]`.
  - "Heartburn is commonly caused by gastroesophageal reflux." to "Heartburn, a common complaint, is caused by gastroesophageal reflux": develop `['is commonly', 'commonly caused']`, branch `[]`.
  - "Infant reflux typically resolves by 12 months of age." to "Typical infant reflux resolves by 12 months of age": develop 2 pairs, branch `[]`.
  - "Obesity significantly increases the risk of GERD." to "Obesity, a significant public health problem, increases the risk of GERD": develop 2 pairs, branch `[]`.
  - The card's own word the other way round: "Factors include abnormal transient relaxations of the lower esophageal sphincter." to "Factors include abnormal relaxations of the lower esophageal sphincter, which open transiently": develop `['abnormal transient', 'transient relaxations']`, branch `[]`.
  - Also hidden: usually/usual, frequently/frequent, largely/large, partially/partial, moderately/moderate, occasionally/occasional, relatively/relative, slightly/slight, approximately/approximate, certain/certainly.
- Controls that held: "young" against "younger" (by design), "rarely" against "rare" (stem "rare" is 4, below the floor), "chronically" against "chronic" (stem "chronical" does not match "chronic").
- What the person sees: "PPIs are safe for long-term use" or "Symptoms caused by GERD are among the most common reasons for visits" where the paper hedged, whenever the writer's sentence also uses the adjective form, which plain-language GERD prose does constantly ("a common condition", "potential complications", "typical symptoms"). Card 99 would have asked Jev about the hedge; card 101 does not ask.
- Why the build did not see it: the labelled set's A items have no sentence of this shape except `w-gp1-c2-i6` and `w-gp4-c2-i6`, where "most commonly" vanished because the sentence says "common" (the build lists it and accepts it because "symptoms potentially" still catches those two). The build's not-covered line says the "large" for "largely" case "holds for exact matches already"; it does not: develop proposes "is largely" and "largely asymptomatic" against a sentence that says "large", the branch proposes nothing (probe case 7).
- Suggested fix: drop `("ly", "")` from the endings (the recovered "effective treatment" case is carried by "ment" for "treated" and by exact "effective"? measure), or count a form as used only at the position-adjacent word of the phrase rather than anywhere in the sentence, and add labelled A items of this shape before shipping.
- NOT FIXED

### A-101-02: the shape of A-101-01 already occurs in recorded writer output; the branch stops asking about "most commonly" and "most affected" in three live sentences

- Severity: non-blocking on its own (in all 6 recorded replay runs the item question rejected these three sentences, so none reached the screen); it is the evidence that A-101-01 is not a constructed corner
- Input (offline, no model, `raw/adversary/scan_removed.py` and `show_items.py`, output `scan_removed.txt`): the 304 recorded candidates of 2026-10-05 wave 3 through develop's and the branch's `check_phrases`.
- Observed:
  - `md5c2i1`: quote "This X-linked inherited disorder most commonly affects persons of African, Asian, Mediterranean, or Middle-Eastern descent."; sentence "... the most common enzyme deficiency worldwide, affecting people of African, Asian, Mediterranean, or Middle-Eastern descent ...". Develop asks "most commonly"; the branch does not, because "common" from the other quote's clause now "uses" "commonly". The branch asks "affects persons" instead, whose missing word is "persons", not the limit.
  - `cm4c1i1`: the same quote and the same drop, the same result ("most commonly" no longer asked, "affects persons" asked).
  - `cm2c2i3`: quote "African, Asian, and Mediterranean populations and their descendants being amongst the most affected"; sentence "Hemoglobin variants, which affect the oxygen-carrying part of blood, are also among the most common single-gene disorders in Mediterranean populations". Develop asks "most affected"; the branch does not, because the unrelated verb "affect" (oxygen-carrying part) now "uses" "affected". Only "amongst the" is left.
- Of the 59 recorded candidates whose pairs changed, the most frequent removal is "commonly" counted as used through "common" (16 pairs), the very word whose dropped limit card 99's labelled A items carry.
- Approvals: item-only arm, card 99 pair arm and card 101 replay all reject these three in both runs each, so the item question is what holds them today.
- What the person sees: today, nothing different. The protection for these sentences has gone from two questions to one; any run in which the item question approves one of them shows "affecting people of African ... descent" where the paper says "most commonly".
- NOT FIXED

### A-101-01b: live, the branch approves four widened sentences that develop's pair check held back

- Severity: blocking. A widened claim that develop would not show now passes the check; the defect is inside this card's own new code (`_word_forms`, the "ly", "ment" and "ed" endings, commit cd9500fe and 56098e1d).
- Input: `raw/adversary/live_forms.py`, one check of 7 sentences through `check_reworded_sentences` in Jev mode, run once with develop's `sentence_check.py` (exported from `origin/develop`) and once with the branch's; the item question is identical in both. Each sentence drops a limit and carries another form of the limiting word from a second quote:
  - "generally": quotes "Proton pump inhibitors are generally safe for long-term use." and "Their use in the general population has increased."; sentence "Proton pump inhibitors are safe for long-term use, and their use in the general population has increased".
  - "usually": quotes "GERD symptoms usually respond to proton pump inhibitor therapy." and "Usual dosing is once daily before breakfast."; sentence "GERD symptoms respond to proton pump inhibitor therapy, with usual dosing once daily before breakfast".
  - "treated": quotes "Complications are rare in treated patients." and "Treatment with proton pump inhibitors heals esophagitis."; sentence "Complications are rare in patients, and treatment with proton pump inhibitors heals esophagitis".
  - "commonly": quotes "G6PD deficiency is the most common enzyme deficiency worldwide." and "This X-linked disorder most commonly affects persons of African, Asian, Mediterranean, or Middle-Eastern descent."; sentence "G6PD deficiency, the most common enzyme deficiency worldwide, is an X-linked disorder that affects persons of African, Asian, Mediterranean, or Middle-Eastern descent".
  - also "potentially", "frequently", "transient" (full text in the script).
- Observed (`raw/adversary/live_forms.jsonl`, run 1 of each, 4 billed calls, $0.00063):
  - Item question, both arms: approves "generally" (no 0.56 and 0.62), "usually" (0.87 and 0.85), "treated" (0.60 and 0.52), "commonly" (0.70 and 0.66), "transient" (0.82 and 0.76); "potentially" 0.53 then 0.44; rejects "frequently".
  - Develop's pair check vetoes every one of the widened four: "are generally" yes (no 0.02), "generally safe" (0.03), "symptoms usually" (0.02), "usually respond" (0.02), "in treated" (0.03), "treated patients" (0.05), "commonly affects" (0.29). Develop approved only "transient".
  - The branch proposes no pair for "generally", "usually" and "treated", and only "this x-linked" (no 0.78) for "commonly". Branch approved: commonly, generally, transient, treated, usually.
- What the person sees, on the branch and not on develop: "Proton pump inhibitors are safe for long-term use" (the paper: generally safe), "GERD symptoms respond to proton pump inhibitor therapy" (usually respond), "Complications are rare in patients" (in treated patients), "G6PD deficiency ... affects persons of African, Asian ..." (most commonly affects), each with the same trust line as a fully checked sentence.
- Why it reaches the screen: the item question alone approves these drops at 0.52 to 0.87; card 99's pair check was the only thing holding them, at no 0.02 to 0.29, and the word-form rule removes exactly those pairs whenever the sentence has another form of the limiting word anywhere.
- NOT FIXED

### A-101-01c: the A-101-01b result holds in 3 of 3 clean branch runs and 3 of 3 develop runs

- Severity: blocking (confirms A-101-01b)
- Runs (`raw/adversary/live_forms.jsonl`, 14 billed calls in all, about $0.0021):
  - Develop, 3 runs: approved only "transient" every time. Every widened sentence the item question approved was vetoed by a pair: "are generally" and "generally safe" at no 0.02 to 0.04, "symptoms usually" and "usually respond" at 0.01 to 0.02, "in treated" and "treated patients" at 0.03 to 0.05, "commonly affects" at 0.29 to 0.37, "symptoms potentially" at 0.07 to 0.13.
  - Branch, 3 clean runs (rows 2, 4 and 7): approved "commonly", "generally", "treated", "usually" and "transient" in all 3, and "potentially" in 1 of 3 (its item answer flips around 0.5: no 0.52, yes 0.44, yes 0.41). No pair is asked for "generally", "usually" or "treated"; the only pair for "commonly" is "this x-linked" (no 0.78 to 0.86).
- So, on the same 7 sentences, develop shows 0 widened claims in 3 of 3 runs and the branch shows 4 or 5 in 3 of 3 runs.
- Row 6 of the file (the fifth run, labelled "branch") is discarded: its pair set is neither develop's nor the branch's (it asks "are generally" but not "in treated"), because `sentence_check.py` in this shared worktree was modified and restored while it ran (file time 16:19:39, after the build's last commit; `git diff` is clean afterwards). See A-101-05.
- NOT FIXED

