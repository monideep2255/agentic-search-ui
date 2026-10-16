# Card 17 adversary round: option E, the lead-in that names the paper

Adversary, dial position 2, 2026-10-15, against `fix/card17-name-the-paper` at `ec0349a7` with `develop` at `7626fe85` as control. Paths are relative to `<repo-root>`. Findings are appended the moment each is established; nothing here is closed by this round.

## Findings

### A-17-01: the reader's order is not final when the pass runs: the lead pick and card 111's drop both come later
- Severity: major (unsure how often; the lead pick is a model decision)
- What: `name_switched_records` decides "the sentence shown before it" from `grounding.sentences` right after `drop_record_restatements` (`core/graph.py`, line 14599). Two later steps change which sentence the reader sees above which: `_answer_parts` skips `lead_index` from the prose and shows that sentence first (`core/graph.py`, lines 13558 to 13568), and card 111's `_label_only_positions` leaves sentences out there too. The design's sentence "Reading order is only final after that drop" (design.md, "Where it runs") is false. The builder's own test `test_a_sentence_with_a_card_17_lead_in_stays_in_the_prose_and_may_lead` asserts a led-in sentence at index 1 is offered as the lead, so the first line on screen can read `From the paper "...": ...`, which condition 1 of the design says never happens, and the sentence that was index 2 is then read against index 0, a sentence it was never compared with.
- Reproduction: my probe over the builder's 24 saved traces (`raw/live/*.jsonl`), matching each shown summary claim back to the pass's output index, prints the shown order against the pass order. Four runs moved sentence 1 to the top: `ashk-res-3: pass_n=2 led=[] shown_order=[1, 0]`, `gerd-plain-4: pass_n=4 led=[] shown_order=[1, 0, 2, 3]`, `gerd-res-2: pass_n=4 led=[2] shown_order=[1, 0, 2, 3]`, `gerd-res-4: pass_n=4 led=[2, 3] shown_order=[1, 0, 2, 3]`. In `gerd-res-3: pass_n=5 led=[1] shown_order=[0, 1, 2, 3, 4]` the led-in sentence sat at index 1, inside the two lead candidates; had the pick gone to it, the answer's first line would have been the lead-in. In gerd-res-2 and gerd-res-4 the reorder was harmless only because sentences 0 and 1 cite the same page.
- What a person sees: either an answer that opens on `From the paper "X": ...` before the count line, or a sentence that switches paper with no lead-in because the sentence it was compared with was lifted out from above it. The second is the card's own failure shape, reintroduced one step later.
- NOT FIXED

### A-17-02: the lead-in names a title that several listed papers share, so it reads as the paper above
- Severity: major (unsure: the fix is true to the record, but it does not do the card's job here)
- What: the pass fires on page disjointness and quotes the title, so two different PubMed pages with the same title produce `From the paper "<same title>"` after a sentence from the other. In the GERD answers four of the five PubMed records are titled "Gastroesophageal Reflux Disease" (listing rows [1], [5], [7] and [11] in `raw/live/gerd-res-2.jsonl` and `gerd-res-4.jsonl`).
- Reproduction: (1) `raw/probe_switches.txt`, `sentence_check_raw/gp4 draft1 live sent1`: prev "The typical symptoms of GERD are heartburn and regurgitation of stomach contents into the throat." with prev titles ['Gastroesophageal Reflux Disease.'], then this sentence "Reflux symptoms are among the most common reasons people visit their primary care doctor." to 'Gastroesophageal Reflux Disease.' shared=['reflux']; the replay (`raw/replay_option_e.txt`, line 58) adds `From the record "Gastroesophageal Reflux Disease": | Reflux symptoms ...` to it. (2) My unit probe: two pages, both titled "Alpine lakes and glacier melt.", a copied first sentence on page 1 and a reworded second on page 4 sharing the word "glacier": output `1 From the paper "Alpine lakes and glacier melt": Glacier retreat exposes bare rock [4].`
- What a person sees: a sentence that announces it comes "From the paper 'Gastroesophageal Reflux Disease'" directly under a sentence from a paper of that same name. They read it as the same paper, which is the misreading the lead-in exists to prevent, or they go to the listing and find four rows with that title and cannot tell which. The card's own promise, "the answer says which paper the sentence comes from", is not kept when the title is the only thing quoted.
- NOT FIXED

### A-17-03: a lead-in before "This condition" leaves the pointer dangling; the condition is never named
- Severity: minor
- What: build.md item 1 says "This condition" now "resolves to the MEFV paper, not the sentence above". A paper is not a condition. The sentence names no condition, the previous sentence is about RTEL1 carriers, and nothing in the answer says familial Mediterranean fever.
- Reproduction: `raw/live/ashk-plain-1.jsonl`, shown summary claims in order: "This study was designed to recruit people who carry this mutation and to prepare them for possible future trials of gene-directed therapies [7]." then `From the paper "Molecular analyses of MEFV gene mutation variants in Turkish population": This condition primarily affects people of Turkish, Armenian, Arab, and non-Ashkenazi Jewish descent [8].`
- What a person sees: a Plain language reader asking about Ashkenazi variants gets a sentence about "this condition" with no condition on the page, now framed as a paper's statement. Less wrong than before (it no longer reads as the RTEL1 study), but still a confident sentence a reader cannot pin to anything. The design's claim "the pointer resolves" is overstated for pronoun openers.
- NOT FIXED

### A-17-04: the replay never exercised the user-facing words: every one of its 65 lead-ins reads "From the record"
- Severity: minor
- What: `raw/replay_option_e.py` builds findings with no `entity_type` (grep for `entity_type` in the script returns nothing), so `_lead_in_noun` falls to "the record" for all 65 lead-ins in `raw/replay_option_e.txt` (lines 52 to 116, every line `From the record "..."`). The design says the replay lets "a reviewer read all 65 and say whether any one names a paper the sentence is not about"; it does, but not in the words a user sees. The "From the paper" wording has only hand-built unit tests and six live cases behind it.
- Reproduction: `grep -c 'From the record' raw/replay_option_e.txt` gives 65; `grep -c 'From the paper' raw/replay_option_e.txt` gives 0.
- What a person sees: nothing directly; the evidence for the wording is thinner than build.md's replay table suggests.
- NOT FIXED

### A-17-05: three edge cases the pass handles in a way the design does not describe
- Severity: minor (unsure whether each can occur live)
- What and reproduction, my unit probes on `name_switched_records` and `lead_in_title`:
  - A sentence citing a labelled page (one shared word) and an unlabelled page is led in with only the labelled page named: input sentence "Valleys hold fine silt [2] and floods leave layers [3]." with page 3 carrying only an abstract; output `From the paper "Lake sediment cores from northern valleys": Valleys hold fine silt [2] and floods leave layers [3].` The lead-in says the whole sentence is from one paper; half of it is from a record it does not name.
  - A previous sentence with no marker counts as "a sentence shown before it" with an empty page set, so the next sentence fires: input ("Glaciers are melting faster each decade.", "Valleys like these hold fine silt [2].") gives `1 (... 'From the paper "Lake sediment cores from northern valleys": Valleys like these hold fine silt [2].')`. Whether an unmarked sentence can reach the pass I did not establish.
  - `lead_in_title("A title with a trailing ellipsis...")` returns `A title with a trailing ellipsis..`; `lead_in_title("Title ending in a semicolon;")` keeps the semicolon before the closing quote. HTML entities pass through untouched (`WHAT&apos;S NEW &amp;` stays as is); PubMed titles arrive decoded through `itertext()` (`tools/ncbi_eutils_actions.py`, line 1257), so this only bites a source that ships escaped text.
- What a person sees: a lead-in that credits one paper for a two-record sentence; or odd punctuation inside the quotes.
- NOT FIXED

### A-17-06: a retracted paper's title gets the same "From the paper" framing as any other
- Severity: unsure
- What: no code under `src/system_03_search_agent/` mentions retraction (`grep -rni retract src/system_03_search_agent/` returns nothing), and PubMed's `ArticleTitle` does not carry a "RETRACTED" label (retraction sits in PublicationType and CommentsCorrections, which the efetch reader at `tools/ncbi_eutils_actions.py` lines 1256 to 1268 does not read). The design's risk row says a "RETRACTED:" label "cannot be dropped" by the cut; it is never there to keep.
- Reproduction: `lead_in_title("RETRACTED: " + "word " * 40)` keeps the prefix, as designed, but the title field for a retracted PubMed record has no such prefix in the first place.
- What a person sees: `From the paper "<title>":` in front of a sentence from a retracted paper, with the same weight as a sound one. This is pre-existing for the citation chip; the lead-in puts the title in the prose, which lends it more.
- NOT FIXED

### A-17-01 addendum: how often the two ingredients occur, measured
- The lead pick lifted sentence 1 above sentence 0 in 5 of the 10 GERD runs I made (branch `gerd-a17-4`, develop `gerd-a17dev-1`, `-2`, `-4`, `-5`: `shown_order=[1, 0, 2, ...]`), and in 4 of the builder's 24 traces. In the replay, 7 of the 20 live lead-ins sit at index 1 (`grep -c ' live sent1:' raw/replay_option_e.txt` gives 7 of 20). The two conditions that together put a lead-in on the answer's first line, or strand the sentence after it, each occur in roughly a third to a half of GERD runs; I did not catch both in one run in 10 tries.
- NOT FIXED

### A-17-07: the 20 s bar held on both trees, run one at a time
- Severity: none (a measurement, not a defect)
- What: five GERD Researcher and five Ashkenazi Plain language runs per tree, strictly sequential, alternating branch and develop, develop's settings (CLASSIFIER_PROVIDER=jev, guard and plan deepseek/deepseek-v4-flash, synth z-ai/glm-5.2, cap 0.25 USD), my own runner, not the builder's. Every branch run finished in 8.5 to 12.6 s. One develop run (`gerd-a17dev-3`) took 40.2 s and ended `ask` with the knowledge graph note; it is develop, not the branch. The builder's 44 to 47 s runs were four at a time and all ended `ask` with the same graph timeout note (`raw/live/gerd-res-2.jsonl`: "The background search of the knowledge graph did not finish because it took too long"), which is where the time goes, not the pass. Total spend 0.251 USD of the 0.60 budget.
- Reproduction: the table.

| Run | Elapsed s | Trust outcome | Cost USD | Lead-ins shown |
|---|---|---|---|---|
| gerd-a17-1 | 9.8 | answer | 0.0156 | 0 |
| gerd-a17-2 | 9.7 | answer | 0.0113 | 2 |
| gerd-a17-3 | 9.5 | answer | 0.0124 | 1 |
| gerd-a17-4 | 8.9 | answer | 0.0136 | 1 |
| gerd-a17-5 | 9.0 | answer | 0.0133 | 0 |
| gerd-a17dev-1 | 12.1 | answer | 0.0125 | develop |
| gerd-a17dev-2 | 7.3 | answer | 0.0144 | develop |
| gerd-a17dev-3 | 40.2 | ask | 0.0137 | develop |
| gerd-a17dev-4 | 7.9 | answer | 0.0142 | develop |
| gerd-a17dev-5 | 11.3 | answer | 0.0124 | develop |
| ashk-a17-1 | 12.6 | ask | 0.0100 | 0 (no pass ran) |
| ashk-a17-2 | 8.5 | ask | 0.0086 | 0 (no pass ran) |
| ashk-a17-3 | 8.5 | answer | 0.0160 | 0 |
| ashk-a17-4 | 9.4 | answer | 0.0133 | 0 |
| ashk-a17-5 | 10.9 | answer | 0.0131 | 0 |
| ashk-a17dev-1 | 11.1 | answer | 0.0089 | develop |
| ashk-a17dev-2 | 8.5 | ask | 0.0032 | develop |
| ashk-a17dev-3 | 11.1 | answer | 0.0153 | develop |
| ashk-a17dev-4 | 9.9 | answer | 0.0144 | develop |
| ashk-a17dev-5 | 10.2 | ask | 0.0151 | develop |

- Every lead-in shown on the branch, with the sentence the reader sees above it:
  - gerd-a17-2, after "The disease affects quality of life and may cause erosive esophagitis, esophageal strictures, and Barrett esophagus, a precursor to esophageal adenocarcinoma [13].": `From the paper "Gastroesophageal reflux disease in children: What's new right now?": In young children, clinical manifestations are varied and nonspecific, prompting the necessity for careful diagnostic evaluation [14].` Right paper.
  - gerd-a17-2, after "Additional factors include defects in esophageal mucosal defense, impaired esophageal and gastric motility and clearance, and anatomical defects such as hiatal hernia [14].": `From the paper "Gastroesophageal Reflux Disease": Long-term use of proton-pump inhibitors is associated with bone fractures, chronic renal disease, acute renal disease, community-acquired pneumonia, and Clostridium difficile intestinal infection [13].` Right paper by chip; see A-17-08 for what the title tells the reader.
  - gerd-a17-3, after "GERD is a gastrointestinal motility disorder arising from reflux ... Barrett esophagus [13].": `From the paper "Gastroesophageal reflux disease in children: What's new right now?": Clinical manifestations in young children are varied and nonspecific, necessitating careful diagnostic evaluation [14].` Right paper.
  - gerd-a17-4, after "Long-term use of proton-pump inhibitors, the most effective treatment, is associated with ... Clostridium difficile ... [13].": `From the paper "Gastroesophageal reflux disease in children: What's new right now?": Clinical manifestations in young children are varied and nonspecific, prompting the necessity for careful diagnostic evaluation [14].` Right paper.
  - Ashkenazi Plain language, five runs: no lead-in; the builder's one Plain language lead-in (A-17-03) did not recur. Sentence counts the pass received and returned were equal in every run.
- NOT FIXED (nothing to fix)

### A-17-08: live, the lead-in quotes a title four listing rows share, and its chip number is not in the listing
- Severity: major (unsure; the chip opens the right page, the words do not identify it)
- What: A-17-02 reproduced live on the branch. The GERD listing shows "Pubmed title: Gastroesophageal Reflux Disease" at [1], [5], [7] and [11]. The lead-in `From the paper "Gastroesophageal Reflux Disease": Long-term use of proton-pump inhibitors ... [13]` names a title that matches four rows, and its chip [13] is a number no listing row carries (the prose cites the abstract ref, the listing the title ref; develop numbers the same way, `gerd-a17dev-1` prose chips are [13] too, so the numbering is not this card's). Query 113's "Click the sentence's citation: it opens the paper named in the lead-in" holds; "the answer says which paper the sentence comes from" does not, in words.
- Reproduction: `gerd-a17-2.jsonl` in my run folder, shown order quoted in A-17-07.
- What a person sees: "From the paper 'Gastroesophageal Reflux Disease'" in an answer whose source list has four papers by that name, cited as [13] where the list stops at [12].
- NOT FIXED

### A-17-09: a prose sentence that is a bare list of PubMed ids, not this card's but on the same screen
- Severity: unsure (pre-existing; out of this card's fence)
- What: `gerd-a17-2` ends its prose with `Publication pmid 29132520 [15], pmid 33351044 [16], pmid 36170502 [17], pmid 37034973 [18], and pmid 37516506 [19].` under the heading "Clinical Management and Related Records". Not touched by the pass; recorded because a reviewer reading lead-ins will see it on the same answer.
- NOT FIXED

## Verdict

FAIL, on A-17-01 and A-17-02 (A-17-08 is A-17-02 seen live). Both sit inside this card's own change, not in surrounding code.

- Verified by my own probes: the reading-order change after the pass (A-17-01, 24 saved traces plus 10 fresh GERD runs); the same-title lead-in (A-17-02, unit probe and live `gerd-a17-2`); the edge cases in A-17-05; the replay's noun (A-17-04); the 20 s bar and every lead-in on 20 sequential runs (A-17-07). Branch worktree at `ec0349a7`, develop control at `7626fe85`, both removed after the round.
- Read only, not run: the grounding refactor's "no behaviour change" claim (I did not re-run the switch tests); the retraction path (A-17-06, from the efetch reader and a grep); the builder's unit tests and mutation table.
- The change's core promise holds where I looked: no sentence was lost by the pass in any run (input and output sentence counts equal in all 20), every lead-in's chip opened the page whose title it quoted, and the sentence after the colon was unchanged. The failures are that the paper named is not always identifiable (four papers share the title), and that the sentence the lead-in was judged against is not always the one above it on screen.
