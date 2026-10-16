# Card 29 adversary round, 2026-10-15

Adversary, dial position 3, one round. Subject: `git diff b25e4c6d...80b28466` (card 29, per-paper answering sentence). Worktrees: a29 at 80b28466, a29dev at b25e4c6d, both under the session scratchpad. Findings are appended as they are established.

## Findings

### A-29-01: A retracted paper's own positive finding is quoted under it as the sentence that answers the question
- Severity: critical
- What: the pick has no notion of retraction or evidence strength. For a question about hydroxychloroquine and COVID-19, the first cited paper is the retracted open-label trial (PMID 32205204, its title begins "RETRACTED:"), and the card quotes its conclusion as the answering sentence. The third paper, an indirect prevalence comparison (PMID 32373993), gets "These studies were all suggestive that chloroquine and hydroxychloroquine can successfully treat COVID-19 infections." The summary above says nothing about efficacy, so the only efficacy statements a reader sees on the answer are these two quoted positive claims.
- Reproduction: `run_streaming`, `reads_placement=True`, develop's settings, Researcher, question `what does the literature say about hydroxychloroquine for COVID-19` (run q7). Summary: "Found 5 pubmed records for hydroxychloroquine: RETRACTED: Hydroxychloroquine and azithromycin as a treatment of COVID-19 ... [1], ... A critical analysis of hydroxychloroquine and remdesivir raised ethical issues surrounding their emergency use authorisation by the US FDA [6]." Shown sentences:
  - [1] PMID 32205204 (retracted), Jev choice s7 p=0.44, none p=0.14: "Despite its small sample size, our survey shows that hydroxychloroquine treatment is significantly associated with viral load reduction/disappearance in COVID-19 patients and its effect is reinforced by azithromycin."
  - [3] PMID 32373993, s10 p=0.73: "These studies were all suggestive that chloroquine and hydroxychloroquine can successfully treat COVID-19 infections."
  - [2] PMID 32293710, s3 p=0.59 vs none 0.41: "It also allows consideration of agents, such as hydroxychloroquine, which may interfere with this overly brisk macrophage inflammatory response and perhaps influence the course of the disease, ..." (speculation shown as the answer)
  - [4] PMID 32495226: "Hydroxychloroquine and chloroquine are among the proposed drugs and are the most widely used so far, despite the lack of robust evidence on their usefulness."
- What a person sees: under the top source, in quotation marks, a sentence saying hydroxychloroquine significantly cleared the virus, from a paper later retracted; under the third, that the drug "can successfully treat" COVID-19. The card's purpose ("so I know why it was cited without opening it") makes the quote read as the paper's verified finding. The large trials that found no benefit are not among the cited papers, and nothing in the quoted line says the claim was withdrawn. This is the confident wrong answer the product's rules rank worse than a missing one.
- Why it is this card's: before card 29 these papers showed their title only, so the retracted paper's conclusion was one click away, not on the answer.
- NOT FIXED

### A-29-02: The shown "sentence" can be a fragment cut off mid-sentence by the 2,000-character abstract limit, ending in an ellipsis
- Severity: major
- Sits inside a change made during this phase: yes. The builder's window change (first 3 and LAST 8 sentences of a long abstract) puts the truncated last fragment into the candidate list of every abstract longer than the retrieval limit.
- What: the abstract the pick reads is the retrieved `abstract` field, which is cut at 2,000 characters and ends with "…". `split_abstract_sentences` treats the cut tail as a sentence, the window always offers it (it is the last one), and `verified_sentence` accepts it because it is a substring of the cut text. The "word for word in its own abstract" guarantee therefore checks against the truncated copy, not the paper's abstract. The cut can fall before a hedge, a negation or the actual result.
- Reproduction: run q8, Deep technical, `papers on the mechanism by which metformin inhibits cancer cell growth`. Paper [4], PMID 40091020. The abstract handed to the pick is 2000 characters and ends `'... Mechanistically, metformin inhibited histone acetylation on FGFR4, thereby…'`. Offered option s10 = "Mechanistically, metformin inhibited histone acetylation on FGFR4, thereby…". Jev choice s10, p=0.80. Shown under the paper, in quotation marks: `"Mechanistically, metformin inhibited histone acetylation on FGFR4, thereby…"`.
- What a person sees: a quotation presented as the paper's own sentence that stops mid-clause. The product's own words for this field ("quoted VERBATIM", "never paraphrase") are not true of it.
- NOT FIXED

### A-29-03: Objective, method and scope sentences are picked over a finding sentence that was on offer in the same abstract
- Severity: major
- What: the "none" bar and the instructions do not separate a sentence that says what a paper set out to do from one that says what it found. With result sentences among the options, the classifier still picked the objective or scope sentence, often at low confidence, and there is no confidence floor (the argmax is shown however low).
- Reproduction: run q9, Clinical brief, `papers on treatment of acute migraine`. 4 of 5 shown sentences state aims or scope:
  - [1] PMID 26178694, s1 p=0.40: "We conducted systematic reviews and network meta-analyses to compare the relative efficacy of triptans ..." while option s10 on offer was "Among individual triptans, sumatriptan subcutaneous injection, rizatriptan ODT, zolmitriptan ODT, and eletriptan tablets were associated with the most favorable outcomes." and s6 "Standard dose triptans relieved headaches within 2 hours in 42 to 76% of patients, ...".
  - [3] PMID 34128998, s1 p=0.28 (none 0.07): "To evaluate the benefits and harms associated with acute treatments for episodic migraine in adults." This is the structured abstract's OBJECTIVE fragment. On offer: s8 "Compared with placebo, triptans and nonsteroidal anti-inflammatory drugs used individually were significantly associated with reduced pain at 2 hours and 1 day ...".
  - [4] PMID 34379793, s2 p=0.64: "In this review, we analyse historical and current pharmaceutical development approaches in acute and chronic migraine ...".
  - [5] PMID 38568487, s1 p=0.79: "This article reviews the approach to the acute treatment of migraine, ..." while on offer: "The number of available migraine treatments continues to expand, although triptans are still the mainstay of migraine-specific acute treatment."
  Same pattern elsewhere: run q3 PMID 37928189 (s4 p=0.54 vs none 0.44) "To enhance therapeutic outcomes, novel therapeutic regimens ... have been attempted ...".
- What a person sees: under a meta-analysis of 133 trials, a quoted line saying the authors did a meta-analysis, presented as the sentence that answers "how is acute migraine treated". The card promises the sentence that answers the question; for a clinician this is noise that looks like evidence.
- NOT FIXED

### A-29-04: A sentence whose subject is a pronoun from the sentence before is shown alone, and then says something the paper did not say
- Severity: major
- What: a sentence is lifted out of its abstract with no check that it stands on its own. A sentence opening "Mechanistically, this is achieved ..." or "Moreover, ..." refers back to a sentence the reader cannot see.
- Reproduction: run q8, `papers on the mechanism by which metformin inhibits cancer cell growth`. Paper [5], PMID 40140842, s4 p=0.78: "Mechanistically, this is achieved through AMPK activation and subsequent inhibition of downstream mTOR phosphorylation." In the abstract, "this" is the preceding sentence: "knockdown of 6PGD induces oxidative stress and suppresses ESCC cell proliferation". Under a question about metformin, the quoted line reads as metformin's mechanism; the paper says it is the mechanism of 6PGD knockdown. Also run q6 PMID 38892706: "Moreover, the most recent systematic reviews and meta-analyses and one umbrella review demonstrated that ..." is a narrative review reporting other reviews, shown as the paper's own answer.
- What a person sees: a quoted mechanism attributed by position to a paper that never claimed it for the drug asked about.
- NOT FIXED

### A-29-05: The retracted 1998 MMR-autism paper gets a quoted finding, with nothing on the card saying it was retracted
- Severity: major
- What: same root as A-29-01, a second shape. Here the record's title does not carry "RETRACTED:", so the quoted sentence is the only thing under the paper besides its title, and it reads as an ordinary finding. A companion paper by the same group gets its own "we have reported" background sentence quoted.
- Reproduction: run q12, Researcher, `papers on ileal lymphoid nodular hyperplasia, colitis and autism in children`. Paper [4], PMID 9500320, title "Ileal-lymphoid-nodular hyperplasia, non-specific colitis, and pervasive developmental disorder in children" (the retracted Lancet paper), Jev s6 p=0.29 vs none 0.19 (a 0.29 pick is shown): "Histology showed patchy chronic inflammation in the colon in 11 children and reactive ileal lymphoid hyperplasia in seven, but no granulomas." Paper [2], PMID 11241044: "We have reported colitis with ileal lymphoid nodular hyperplasia (LNH) in children with regressive autism." Paper [1], PMID 11007230 and [3], PMID 16003132: the abstract's opening "has been described / has been reported in children with ..." sentence.
- What a person sees: four of five sources carry a quoted line asserting gut pathology in autistic children, one from a paper withdrawn for fraud, none marked. Only paper [5] (PMID 22428439) says the 1998 paper "set off a media storm and galvanized the anti-vaccine movement", and it has no title on its card (the listing names it "22428439 [5]").
- NOT FIXED

### A-29-06: GraphQL drops the sentence; the build report says it reaches every surface
- Severity: minor
- What: `adapters/graphql/types.py`'s `Citation` type has no `snippet` field and `Citation.from_payload` copies fields one by one, so a GraphQL client never receives the sentence. The CLI's References block prints only markers, source name and link, so it does not show it either (consistent with the CLI showing no titles). The build report's line "The CLI, GraphQL fold, MCP and web adapters all read this one rule, so the sentence reaches every surface" is true of the re-send rule, not of the sentence.
- Reproduction: a citation payload with a sentence from live run q6 (`papers on whether vitamin D supplements prevent fractures`), `CitationPayload.model_validate(p)`, then `Citation.from_payload(c)`:
  ```
  payload has snippet: True
  graphql Citation fields: ['citation_id', 'display_index', 'source', 'source_id', 'source_url', 'layer', 'field', 'claim_text', 'evidence_kind', 'assertion_confidence', 'population_ancestry_context', 'license', 'snapshot_date', 'entity_name']
  graphql has snippet: False
  ```
  MCP carries the raw payload dict through, so an MCP client does get `snippet`.
- What a person sees: the same answer has the per-paper sentence on the web and MCP, and not on GraphQL or saved answers (the last is stated in query 112). Not a degradation, but the report's claim should not be repeated as verified.
- NOT FIXED

### A-29-07: When the writer's summary fails, the quoted sentences become the only substantive answer, under a note saying no summary could be checked
- Severity: unsure
- What: the pick runs over the listing's papers, not over the papers the summary relies on, and it runs whether or not the summary survived. When the writer's summary fails its check, the answer says "no written summary could be checked against the records", and the five quoted sentences are then the only content on the page that answers the question. Each is word for word from its paper, so this may be what the owner wants; it is also a route by which an unweighed claim (A-29-01) becomes the whole answer.
- Reproduction: run q4, Researcher, `risk factors for preeclampsia`: listing note "Note: no written summary could be checked against the records, so the records found are listed below with their sources"; summary "Found 1 disease record for preeclampsia: Preeclampsia [1]." Quoted under [9], PMID 33771361: "Preeclampsia and cardiovascular disease share the same risk factors, preexisting cardiovascular disease is the strongest risk factor (chronic hypertension, congenital heart disease) for developing preeclampsia, ...". Same shape in run q1 (`does the MMR vaccine cause autism`, Plain language): summary "I found 5 published papers and 1 condition related to MMR [1]...[6]" under the same failed-summary note, with the two quoted no-association sentences the only answer to the question (here the quotes help).
- NOT FIXED

### A-29-08: A hedged or qualified finding is shown without the very next sentence that qualifies it
- Severity: minor
- What: one sentence is shown alone; when the abstract's next sentence is its hedge ("However, ... has not yet been thoroughly studied"), the reader sees the claim without it. Nothing in the pick looks at the following sentence.
- Reproduction: run q13, Clinical brief, `papers on smoking as a risk factor for rheumatoid arthritis`, PMID 35904251, s4 p=0.97: shown "Current epidemiological evidence suggests a significant impact of smoking, sex hormones, and lifestyle status in RA occurrence." The abstract's next sentence: "However, the association between these variables has not yet been thoroughly studied." Run q10, Plain language, `does vitamin C prevent the common cold`, PMID 16373990, s8 p=0.55 vs none 0.35: "These trials document that adequate intakes of vitamin C and zinc ameliorate symptoms and shorten the duration of respiratory tract infections including the common cold." ("These trials" points at a sentence not shown), under a summary whose first line is that vitamin C "did not stop people from getting colds".
- NOT FIXED

### A-29-09: The sentence ignores the reading depth; a Plain language answer quotes bare statistics
- Severity: minor
- What: the pick's state is only the question; the depth the person chose is not passed, so the Plain language card gets the same statistical sentence a Researcher would.
- Reproduction: run q10, Plain language, `does vitamin C prevent the common cold`, PMID 23440782, s6 p=0.87: "In the general community trials involving 10,708 participants, the pooled RR was 0.97 (95% confidence interval (CI) 0.94 to 1.00)." Run q6, Plain language, PMID 35939577: "Supplemental vitamin D3, as compared with placebo, did not have a significant effect on total fractures (which occurred in 769 of 12,927 participants ...; hazard ratio, 0.98; 95% confidence interval [CI], 0.89 to 1.08; P = 0.70), ...".
- What a person sees: a plain-language reader gets "pooled RR was 0.97" with no outcome named as the reason the paper was cited. Possibly by design (a verbatim quote cannot be simplified), so filed minor.
- NOT FIXED

### A-29-10: PubMed itself marks three of the quoted papers "Retracted Publication"; the pick never looks
- Severity: major (evidence for A-29-01 and A-29-05, filed separately because it names the data the product already has access to)
- What: an independent cross-check of every sentence shown in this round (73 shown sentences, 52 distinct PMIDs, across 22 live runs) against PubMed's own record, fetched with E-utilities `efetch` (`db=pubmed&retmode=xml`), found three shown under papers whose PubMed publication types include "Retracted Publication". The pick receives only the abstract text, so it cannot weigh this.
- Reproduction: script in the session scratchpad (`adv29/xcheck.py`), output:
  ```
  q12 [1] PMID 11007230 in_real_abstract=True types=['Retracted Publication'] :: Intestinal pathology, i.e., ileocolonic lymphoid nodular hyperplasia (LNH) and mucosal inflammation, has been described in children with dev
  q12 [4] PMID 9500320 in_real_abstract=True types=['Retracted Publication'] :: Histology showed patchy chronic inflammation in the colon in 11 children and reactive ileal lymphoid hyperplasia in seven, but no granulomas
  q7 [1] PMID 32205204 in_real_abstract=True types=['Retracted Publication'] :: Despite its small sample size, our survey shows that hydroxychloroquine treatment is significantly associated with viral load reduction/disa
  q8 [4] PMID 40091020 in_real_abstract=False types=[] :: Mechanistically, metformin inhibited histone acetylation on FGFR4, thereby…
  total shown 73 distinct pmids 52 flagged 4
  ```
- Also established by the same run (a negative result, recorded so it is not re-tested): 72 of 73 shown sentences are word for word in the real PubMed abstract of the PMID they sit under, so no sentence was attached to the wrong paper in this round. The one that is not is the truncated fragment of A-29-02.
- What a person sees: the run q12 answer has two retracted papers out of five with quoted findings, neither marked; the run q7 answer has its first source's withdrawn conclusion quoted.
- NOT FIXED

### A-29-11: In the web client a later send of a citation without the sentence erases the sentence (last send wins)
- Severity: minor (unsure whether any real path delivers sends out of order; in every live run of this round the sentence-bearing send came last)
- What: `updatesCitation` ignores `snippet` in both directions, so a send WITHOUT the sentence counts as an update of one WITH it and replaces it. The same is true of two sends with two different sentences: the second wins silently.
- Reproduction: a vitest probe in the scratchpad worktree (not in the repository) feeding `useRunView` the events below, output:
  ```
  [citation k1 with snippet S, token, citation k1 without snippet, done]  -> OUT_OF_ORDER snippet = undefined
  [citation k1 with snippet S, token, citation k1 with a different snippet, done] -> TWO_SENTENCES snippet = "Another sentence entirely, from somewhere else in the abstract text."
  ```
- What a person sees: nothing today, since the server sends the sentence-bearing citation last; any future re-send (a replay after a reconnect that is not in order, or a later claim_text update sent from a copy without the sentence) would drop the sentence or swap it without a trace.
- NOT FIXED

### A-29-12: The retracted paper's abstract offered its own retraction notice as an option; the classifier chose the withdrawn finding instead
- Severity: critical (adds to A-29-01; the information needed to avoid the wrong quote was inside the very options the pick was given)
- What: for PMID 32205204, the abstract the pick received ends with the publisher's retraction notice. The window offered it as s8 and s9; the classifier picked s7, the withdrawn conclusion. The instructions ask only for "the sentence that most directly answers the question", so a retraction sentence is, by those instructions, a worse answer than the claim it retracts.
- Reproduction: run q7 (`what does the literature say about hydroxychloroquine for COVID-19`, Researcher), batch question p0, options as offered and Jev's probabilities:
  ```
  s7 Despite its small sample size, our survey shows that hydroxychloroquine treatment is significantly associated with viral load reduction/disappearance in COVID-19 patients and its effect is reinforced by azithromycin.
  s8 This article has been retracted: please see Elsevier Policy on Article Withdrawal (https://www.elsevier.com/locate/withdrawalpolicy).
  s9 Concerns have been raised regarding this article, ...
  s10 Elsevier's Research Integrity and Publishing Ethics Team, in collaboration with the journal's co-owner, the…
  {'choice': 's7', 'probs': {'s0': 0.21, ..., 's7': 0.44, 's8': 0.11, 's9': 0.01, 's10': 0.0, 'none': 0.14}}
  ```
  Shown on the card: s7. Note s10 is also a 2,000-character truncation fragment (A-29-02).
- What a person sees: a withdrawn claim quoted as the reason the paper was cited, when the record itself said "This article has been retracted".
- NOT FIXED

### A-29-13: Truncated fragments are offered on most long abstracts; a closing conclusion arrives cut
- Severity: minor (the shape behind A-29-02; recorded for the count)
- What: of 584 distinct options offered across this round's runs, 10 ended in the retrieval limit's "…", each the last option of its paper (the window always includes the last sentence). Example, run q6 PMID 26510847 s10: "This meta-analysis of RCTs supports the use of calcium plus…", the paper's conclusion, cut before what it supports. Once shown (A-29-02) it is a misquote; when not shown, the paper's actual conclusion was never available to the pick.
- Reproduction: scan of every `jev_options` value in the run captures, lines ending "…": q10 p1 s10, q11 p0 s10, q12 p0 s10, q12 p2 s10, q4 p2 s8, q6 p0 s10, q7 p0 s10, q8 p3 s10, t3new1 p2 s10 (and the shown q8 one). "distinct options scanned 584".
- NOT FIXED

Correction to A-29-13: the scan listed 9 truncated options, not 10 (the q8 one is among the nine).

### A-29-14: When the classifier stalls, every answer's summary is held a full extra second
- Severity: minor
- What: `_attach_snippets` runs before the summary is sent and waits up to the 1 s late-read grace for an unfinished pick. If Jev is slow or hanging, the summary of every answer appears 1 s later than develop's, for no sentence at all. This is the documented grace, so it is the design working; filed because the brief asked about the grace's cost and because a Jev stall makes it apply to every question at once.
- Reproduction: `run_streaming` with `call_jev_batch` replaced by a coroutine that sleeps 30 s then raises `JevCallError` (scratchpad driver `drive_fail2.py`), question `papers on treatment of acute migraine`, Clinical brief, with `_attach_snippets` timed:
  ```
  {"tag": "f3_30", "wall": 12.76, ..., "picked": 0, "attach_wait_ms": 1001}
  {"tag": "f3_0",  "wall": 7.78,  ..., "pick_ms": 854, "picked": 5, "attach_wait_ms": 0}
  ```
  Log line in the stalled run: "snippet pick was late; the papers show their titles only". The fallback path (batch fails at once, each paper asked through `decide()`) finished in 854 to 865 ms and showed 4 to 5 sentences with no wait.
- Healthy-path timing, same sitting, sequential, develop (b25e4c6d) vs card 29 (80b28466), seconds to `done`: MMR Plain language 11.17, 8.81 vs 12.08, 9.79; migraine Clinical brief 11.68, 12.39 vs 7.71, 8.74; caffeine Plain language 10.84, 10.22 vs 12.90, 13.08. Pick 223 to 735 ms in all healthy runs, `attach_wait_ms` 0 where measured. The slowest answer in the whole round was 18.54 s (run q1, run four at once). No answer over 20 s. The caffeine runs were about 2 s slower on card 29 in both pairs, but the gap sits in the writer's span (first token to last), not in the attach step, so I attribute it to writer variance and do not file it.
- NOT FIXED

### A-29-15: The splitter glues two sentences together when the second starts with a lowercase letter, a Greek letter, markup or follows "et al."
- Severity: minor
- What: the boundary rule needs an uppercase letter or digit after the period. A sentence starting "β-blockers", "p53", "mRNA", a quote mark or a tag, or a sentence ending in "et al.", is joined to its neighbour. The pair is then offered and shown as one "sentence", or, when the pair exceeds 500 characters, silently dropped, so a finding sentence can never be picked.
- Reproduction: `split_abstract_sentences` on these inputs (scratchpad worktree at 80b28466), output:
  ```
  ['Beta blockers were studied in a cohort of older adults with heart failure. β-blockers reduced all-cause mortality by thirty percent over two years of follow-up.']
  ['We measured tumour suppressor expression in forty colorectal tumours from patients. p53 mutations did not predict survival in this cohort of colorectal cancer patients.']
  ['Patients were followed for many years after their surgery was completed in the clinic.', 'Results were compared with those reported by Smith et al. Survival was not improved by adjuvant chemotherapy in this population of patients.']
  ```
  Live: run q10 PMID 23440782 option s4 was two sentences ("... during the study period. 'Duration' was the mean number of days of illness of cold episodes."). A planted abstract with markup gave one shown "sentence" of two: "Background sentence about the general popularity of coffee drinking in many countries. <b>Caffeine</b> improved endurance <a href=\"javascript:alert(1)\">performance</a> in all trained runners we tested."
- NOT FIXED

### A-29-16: The batched pick (new in this card) chooses aim and method sentences where the one-paper pick on the same papers chooses the finding
- Severity: major
- Sits in code new to this phase: `pick_snippets` and its one-call batch are this card's own; the one-paper `pick_snippet` is the lifted, older path and is now only the fallback.
- What: with the same question, the same five abstracts, the same option lists and the same instructions, the batched Jev call and the per-paper path disagree, and the per-paper path picks the result sentence. The cause of most of A-29-03 is the batching, not the instructions alone.
- Reproduction: scratchpad script `adv29/batchvs.py` calls `pick_snippets` on the five papers captured from run q9 (`papers on treatment of acute migraine`), three times with the real batch and three times with `call_jev_batch` forced to raise so every paper goes through `pick_snippet`/`decide()`. First 70 characters of each pick:
  ```
  batch  26178694 "We conducted systematic reviews and network meta-analyses to compare t"   (3 of 3 runs)
  single 26178694 "For 2-hour headache relief, standard dose triptan achieved better outc"   (3 of 3 runs)
  batch  34128998 "To evaluate the benefits and harms associated with acute treatments fo"   (2 of 3 runs; 1 run "Compared with placebo, calcitonin gene-related peptide receptor antago")
  single 34128998 "Compared with placebo, triptans and nonsteroidal anti-inflammatory dru"   (3 of 3 runs)
  ```
  The other three papers picked the same sentence on both paths. Same comparison on runs q7 and q8: identical picks on both paths in all six calls, so A-29-01, A-29-02 and A-29-04 are not caused by batching.
- What a person sees: on the default path (the batch), a meta-analysis is quoted saying what it set out to do, when the system's own older path would have quoted what it found.
- NOT FIXED

## Every shown sentence judged

54 distinct sentences, 73 shown in total across 22 live runs (q1 to q13, t1 to t3 on card 29, f1 and f3_0 on the forced fallback path). Runs are named in the second column; "fb" marks a sentence seen only on the fallback path. Sentences are cut to their first words where long; the full text is in the findings above or in the run captures in the session scratchpad. Answers: yes, partly or no.

| # | Question | PMID | Sentence | Answers | Problem |
|---|---|---|---|---|---|
| 0 | treatment of acute migraine (q9, t2, fb) | 30681821 | "Lasmiditan, ubrogepant, and rimegepant are currently emerging acute migraine therapies ..." | yes | none |
| 1 | treatment of acute migraine (fb) | 34128998 | "Compared with placebo, triptans and nonsteroidal anti-inflammatory drugs used individually were significantly associated with reduced pain ..." | yes | only on the fallback path (A-29-16) |
| 2 | treatment of acute migraine (q9, t2, fb) | 34379793 | "In this review, we analyse historical and current pharmaceutical development approaches ..." | no | scope sentence (A-29-03) |
| 3 | treatment of acute migraine (q9, t2, fb) | 38568487 | "This article reviews the approach to the acute treatment of migraine, ..." | no | scope sentence, a finding was on offer (A-29-03) |
| 4 | treatment of acute migraine (fb) | 26178694 | "For 2-hour headache relief, standard dose triptan achieved better outcomes ..." | yes | only on the fallback path (A-29-16) |
| 5 | treatment of acute migraine (t2, fb) | 34048394 | "This article discusses acute migraine therapy, focusing on best-level evidence." | no | scope sentence |
| 6 | does the MMR vaccine cause autism (q1) | 12421889 | "This study provides strong evidence against the hypothesis that MMR vaccination causes autism." | yes | none |
| 7 | does the MMR vaccine cause autism (q1, t1) | 30831578 | "The study strongly supports that MMR vaccination does not increase the risk for autism, ..." | yes | none |
| 8 | does vitamin C prevent the common cold (q10) | 16373990 | "These trials document that adequate intakes of vitamin C and zinc ameliorate symptoms and shorten the duration ..." | partly | "These trials" unseen; about duration, not prevention (A-29-08) |
| 9 | does vitamin C prevent the common cold (q10) | 30113569 | "We concluded the consumption of vitamin C does not prevent the incidence of common cold." | yes | none |
| 10 | does vitamin C prevent the common cold (q10) | 33193359 | "No current clinical recommendations support the possibility of significantly decreasing the risk ..." | yes | none |
| 11 | does vitamin C prevent the common cold (q10) | 39803741 | "In controlled trials in the general human population, vitamin C at a dose greater than 1 g/day did not prevent common colds." | yes | none |
| 12 | does vitamin C prevent the common cold (q10, Plain language) | 23440782 | "In the general community trials involving 10,708 participants, the pooled RR was 0.97 ..." | yes | outcome unnamed, bare statistics at Plain language (A-29-09) |
| 13 | aspirin for primary prevention (q11) | 30158069 | "In the intention-to-treat analysis, the primary endpoint occurred in 269 (4·29%) ..." | yes | picked at p=0.26 against none 0.24 |
| 14 | aspirin for primary prevention (q11) | 34824680 | "While historical trials reported a reduction in MI and stroke, more contemporary trials have suggested diminishing benefit ..." | yes | none |
| 15 | aspirin for primary prevention (q11) | 33502899 | "Its role in primary prevention of CVD is still debated." | yes | pronoun subject |
| 16 | aspirin for primary prevention (q11) | 38839268 | "During the past 30 years, several developments have occurred in the antiplatelet field, ..." | no | background sentence |
| 17 | ileal LNH, colitis and autism (q12) | 11007230 | "Intestinal pathology, ... has been described in children with developmental disorders." | no | background; paper is a Retracted Publication (A-29-10) |
| 18 | ileal LNH, colitis and autism (q12) | 16003132 | "Intestinal mucosal pathology, ... has been reported in children with autistic spectrum disorder (ASD)." | no | background reporting others' claims |
| 19 | ileal LNH, colitis and autism (q12) | 9500320 | "Histology showed patchy chronic inflammation in the colon in 11 children ..." | yes | retracted paper, not marked (A-29-05, A-29-10) |
| 20 | ileal LNH, colitis and autism (q12) | 22428439 | "The Lancet's 1998 publication of ... set off a media storm and galvanized the anti-vaccine movement." | partly | useful context; the card has no title |
| 21 | ileal LNH, colitis and autism (q12) | 11241044 | "We have reported colitis with ileal lymphoid nodular hyperplasia (LNH) in children with regressive autism." | no | the authors citing their own earlier (retracted) work (A-29-05) |
| 22 | smoking and rheumatoid arthritis (q13) | 35904251 | "Current epidemiological evidence suggests a significant impact of smoking, ..." | yes | the next sentence's hedge dropped (A-29-08) |
| 23 | smoking and rheumatoid arthritis (q13) | 24594022 | "Compared to never smokers, the risk of developing RA increased by 26% ..." | yes | none |
| 24 | smoking and rheumatoid arthritis (q13) | 29221595 | "Of these, the strongest associations have been seen with female sex, ... and exposure to tobacco smoke." | yes | "Of these" points back |
| 25 | treatment of H. pylori (q3) | 37928189 | "To enhance therapeutic outcomes, novel therapeutic regimens, ... have been attempted ..." | no | background, picked at p=0.54 against none 0.44 (A-29-03) |
| 26 | treatment of H. pylori (q3) | 28071659 | "Most patients will be better served by first-line treatment with bismuth quadruple therapy or concomitant therapy ..." | yes | none |
| 27 | risk factors for preeclampsia (q4) | 31301487 | "Our revised two-stage model accommodates most risk factors for preeclampsia including primiparity, ..." | yes | none |
| 28 | risk factors for preeclampsia (q4) | 33771361 | "Preeclampsia and cardiovascular disease share the same risk factors, ..." | yes | shown while the summary failed (A-29-07) |
| 29 | vitamin D and fractures (q6) | 26510847 | "Meta-analysis showed a significant 15 % reduced risk of total fractures ..." | yes | calcium plus vitamin D, not vitamin D alone |
| 30 | vitamin D and fractures (q6, Plain language) | 35939577 | "Supplemental vitamin D3, as compared with placebo, did not have a significant effect on total fractures ..." | yes | bare statistics at Plain language (A-29-09) |
| 31 | vitamin D and fractures (q6) | 38892706 | "Moreover, the most recent systematic reviews and meta-analyses and one umbrella review demonstrated ..." | partly | a review reporting other reviews, opens with "Moreover" (A-29-04) |
| 32 | vitamin D and fractures (q6) | 42161415 | "For the primary outcome of any fracture, little to no effect was found ..." | yes | none |
| 33 | hydroxychloroquine for COVID-19 (q7) | 32205204 | "Despite its small sample size, our survey shows that hydroxychloroquine treatment is significantly associated with viral load reduction ..." | no | retracted paper's withdrawn finding; its retraction notice was on offer (A-29-01, A-29-12) |
| 34 | hydroxychloroquine for COVID-19 (q7) | 32293710 | "It also allows consideration of agents, such as hydroxychloroquine, which may ... perhaps influence the course of the disease, ..." | no | speculation shown as the answer, picked at p=0.59 against none 0.41 |
| 35 | hydroxychloroquine for COVID-19 (q7) | 32373993 | "These studies were all suggestive that chloroquine and hydroxychloroquine can successfully treat COVID-19 infections." | no | an indirect study's claim, contrary to the trial evidence, shown as the finding (A-29-01) |
| 36 | hydroxychloroquine for COVID-19 (q7) | 32495226 | "... the most widely used so far, despite the lack of robust evidence on their usefulness." | yes | none |
| 37 | metformin anticancer mechanism (q8) | 31178149 | "Combination treatment upregulated phosphorylated AMPK and downregulated downstream phosphorylated S6, ..." | yes | about the combination with simvastatin |
| 38 | metformin anticancer mechanism (q8) | 40091020 | "Mechanistically, metformin inhibited histone acetylation on FGFR4, thereby…" | no | cut at the retrieval limit, not in the real abstract (A-29-02) |
| 39 | metformin anticancer mechanism (q8) | 40140842 | "Mechanistically, this is achieved through AMPK activation and subsequent inhibition of downstream mTOR phosphorylation." | no | "this" is 6PGD knockdown, reads as metformin (A-29-04) |
| 40 | metformin anticancer mechanism (q8) | 29272251 | "In vivo and in vitro cancer cell culture studies demonstrate that metformin induces both AMPK-dependent and AMPK-independent ..." | yes | none |
| 41 | metformin anticancer mechanism (q8) | 34162423 | "Metformin induces ferroptosis in an AMPK-independent manner to suppress tumor growth." | yes | none |
| 42 | treatment of acute migraine (q9) | 34128998 | "To evaluate the benefits and harms associated with acute treatments for episodic migraine in adults." | no | the objective fragment (A-29-03, A-29-16) |
| 43 | treatment of acute migraine (q9, t2) | 26178694 | "We conducted systematic reviews and network meta-analyses to compare the relative efficacy of triptans ..." | no | method sentence (A-29-03, A-29-16) |
| 44 | does the MMR vaccine cause autism (t1) | 25898051 | "MMR vaccine receipt was not associated with an increased risk of ASD at any age." | yes | none |
| 45 | does the MMR vaccine cause autism (t1) | 24814559 | "Furthermore, the components of the vaccines ... are not associated with the development of autism ..." | yes | opens with "Furthermore" |
| 46 | does the MMR vaccine cause autism (t1) | 30986133 | "Several epidemiologic studies have not found an association between MMR vaccination and autism, ..." | yes | none |
| 47 | caffeine and exercise performance (t3) | 36615805 | "Caffeine (1,3,7-trimethylxanthine) is one of the most widely consumed performance-enhancing substances ..." | partly | background (also in build.md) |
| 48 | caffeine and exercise performance (t3) | 38466174 | "Caffeine is a popular ergogenic aid that has a plethora of evidence highlighting its positive effects." | partly | background |
| 49 | caffeine and exercise performance (t3) | 33388079 | "Supplementation with caffeine has been shown to acutely enhance various aspects of exercise performance in many but not all studies." | yes | none |
| 50 | caffeine and exercise performance (t3) | 11583104 | "It can be a powerful ergogenic aid at levels that are considerably lower than ..." | yes | pronoun subject |
| 51 | caffeine and exercise performance (t3) | 25355191 | "These caffeine doses have profound effects on the responses to exercise ..." | yes | "These caffeine doses" points back |
| 52 | caffeine and exercise performance (t3) | 32589582 | "Caffeine intake has also shown ergogenic effects, ..." | yes | none |
| 53 | caffeine and exercise performance (t3) | 34291426 | "Consuming lower doses of caffeine (e.g., 2-3 mg/kg) appears to be comparably ergogenic ..." | yes | none |

Counts: 54 distinct sentences: 34 answer, 5 partly, 15 do not. Of all 54, 6 misstate a paper or make a weak or withdrawn one look stronger (#17, #19, #33, #35, #38, #39). On the default batch path alone (dropping #1 and #4, seen only on the fallback path): 52 sentences, 32 answer.

## Verdict

FAIL. Critical: A-29-01 and A-29-12, a retracted paper's withdrawn finding quoted as the answering sentence when its own retraction notice was on offer. Major: A-29-02 (truncated fragment shown as a verbatim quote, caused by this card's window change), A-29-03 and A-29-16 (aim and method sentences picked over findings, worse on this card's new batch path than on the older one-paper path), A-29-04 (a pronoun sentence misattributes a mechanism), A-29-05 and A-29-10 (retracted papers quoted, unmarked). Minor or unsure: A-29-06, 07, 08, 09, 11, 13, 14, 15.

Inside a change made during this phase: A-29-02 (the builder's first 3 and last 8 window) and A-29-16 (the new batched call). This is the first round, so neither sits inside a review-round fix.

Verified with my own probes: every sentence-quality judgement (22 live runs through `run_streaming`, develop's settings); the PubMed cross-check (72 of 73 shown sentences are word for word in the real abstract of the paper they sit under, so none was attached to the wrong paper); the retraction status of three papers; batch against one-paper picks on the same inputs (3 runs each, 3 questions); timing against develop b25e4c6d (6 pairs, sequential); the 1 s grace under a stalled batch (attach wait 1001 ms) and the fallback path (854 to 865 ms, sentences shown); that injected instructions in an abstract did not move the pick (2 runs); that the guardrail rejects a question with instructions or markup (2 runs, $0.00015 each, no papers); that markup in a sentence renders as literal text with no element created (vitest probe); that the merged card shows a sentence carried on the abstract citation [6] under title citation [1]; last-send-wins in `useRunView`; the GraphQL `Citation` type missing `snippet`; the splitter's merges.

Only read, not run: that MCP carries `snippet` through (its `citations` field is `list[CitationPayload]`); that the CLI References block prints no title or sentence; that saved answers store the field; screenshots at 1280 and 390 pixels (not taken).

Spend: $0.37 of the $0.80 on live runs (sum of `done.total_cost_usd`), plus about $0.001 on direct pick calls.
