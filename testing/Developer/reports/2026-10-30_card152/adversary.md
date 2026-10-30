# Card 152 adversary round 1

Adversary for draft pull request #319, worktree at 0617e15e. Findings are appended as they are established. Ids A-152-NN.

## Findings

### A-152-01: A topic word next to a two-letter abbreviation is read by PubMed as an author's name, so the papers are that author's papers on anything, or none at all
- Severity: major (new with this diff; worse than develop; extends the judge's J-152-03 from the contrived `smith j` to plain questions a person types, and adds the mid-term and zero-hit cases)
- What a person sees: `Is gold good for RA?` searches `gold ra`, which PubMed maps to the author `Gold RA` only (`gold, ra[Author] OR gold ra[Author]`, 11 hits). The top five are "The Color of Rice and the Chinese Paradox", "Effect of age, parity, and race on the incidence of pregnancy associated hypertension...", "Changes in physician behavior and cost savings...", "High blood pressure and hospitals", "Ethoxyformylation and photooxidation of histidines in transferrins". None is about gold or rheumatoid arthritis. Develop's `gold AND ra` gives 1,827 hits (its top five are gold drugs and nanoparticles, mixed but on the words asked).
- More, same mechanism (live ESearch, relevance, 2026-10-30, branch `build_topic_term`):
  - `Does fish help MS?` -> `fish ms` -> `fish, ms[Author] OR fish ms[Author]`, 14 hits: "Oxidative N-dealkylation.", "Scope of practice.", "Laws of consent.", a Shigella preprint, a phonetics paper. Develop `fish AND ms`: 10,223.
  - `papers on fish and ad` -> author `Fish AD`, 2 hits (develop 18,233). `papers on bird and tb` -> author `Bird TB`, 1 hit (develop 468). `papers on rice and tb` -> author `Rice TB`, 96 (develop 207). `papers on hunt and hd` -> author `Hunt HD`, 67 (develop 856).
- The author mapping also fires on a pair INSIDE a longer term, and then ANDs it with the rest, so the search finds nothing:
  - `Does eating fish help MS?` -> `eating fish ms` -> `("eating"[MeSH Terms] OR "eating"[All Fields]) AND (fish, ms[Author] OR fish ms[Author])`, 0 hits. Develop `eating AND fish AND ms`: 105.
  - `papers on eating fish and ms risk` -> 0 (develop 31). `papers on fish and ms in women` -> 0 (develop 227).
  - So a person asking whether eating fish helps multiple sclerosis is told the literature has nothing, which is false.
- Evidence: the adversary's probe `probe.py` (scratchpad `c152adv`), querytranslation read back from ESearch for each term.
- Why it matters: in the zero case the person gets a confident "found nothing" refusal on a well-studied subject; in the non-zero case the abstracts handed to the summary are an unrelated author's bibliography, and the summary and "Based on N sources" are built on them (see the live run findings below if any). The ` AND ` join made every word a separate concept, so no pair could become a name.
- NOT FIXED
### A-152-02: Common topics, CAR T and brown rice, become author names, so "papers on CAR T in myeloma" and "papers on brown rice and diabetes" find nothing
- Severity: major (new with this diff; worse than develop; the same mechanism as A-152-01 but on everyday, high-volume subjects rather than abbreviations)
- What a person sees: a well-studied subject comes back as "found nothing" (the refusal), where develop returns hundreds to thousands of papers.
- Evidence, live ESearch, relevance, 2026-10-30, querytranslation read back:

| Question | Branch term | Branch translation (start) | Branch hits | Develop hits |
|---|---|---|---|---|
| papers on CAR T in myeloma | car t myeloma | `car t[Author] AND ("multiple myeloma"[MeSH Terms] ...` | 0 | 2,645 |
| papers on CAR T for lupus | car t lupus | `car t[Author] AND ("lupus vulgaris"[MeSH Terms] ...` | 0 | 330 |
| papers on car t | car t | author `Car T` | 4 | 36,628 |
| papers on brown rice and diabetes | brown rice diabetes | `brown rice[Author] AND ("diabete"[All Fields] ...` | 0 | 320 |
| Is brown rice healthier than white rice? | brown rice healthier white | `brown rice[Author] AND "healthier"[All Fields] AND ...` | 0 | 11 |
| papers on brown rice | brown rice | author `Brown Rice` | 6 | 6,097 |
| papers on marshall and warren | marshall warren | author | 2 | 664 |

- Not affected: `CAR T cell therapy` and `CAR-T therapy` map to `"immunotherapy, adoptive"[MeSH Terms]` because the longer phrase matches MeSH first. So whether a person gets thousands of papers or none turns on whether they typed "cell therapy" after "CAR T".
- Why it matters: "A refusal says what to type next" and "a confident wrong record is worse than a missing one": here a person asking about CAR T in myeloma, one of the most published subjects in haematology, is told the literature has nothing. Develop's AND join kept `car` and `t` separate, so the author lookup never fired.
- NOT FIXED
### A-152-03: Live, end to end: "papers on CAR T in myeloma" answers on develop and is refused on the branch
- Severity: critical (new with this diff; worse than develop; a well-answered question on develop becomes a false "the literature has nothing" on the branch, through the full pipeline)
- What a person sees, branch (live run 1, `run_streaming`, researcher, no window, 2026-10-30): plan line "you asked for published papers, so searching the literature for: car t myeloma"; the PubMed search, the abstract fetch and PubTator all `status: empty`; trust `refuse`; the whole answer is "I searched the published literature for car t myeloma and found nothing. Try different words, or NCBI's cross-database search: https://www.ncbi.nlm.nih.gov/search/all/?term=papers%20on%20CAR%20T%20in%20myeloma". `trust_line` None.
- What a person sees, develop (live run 2, same question, same settings): plan line "...for: car, t, myeloma"; trust `answer`, "Based on 5 sources cited, all from PubMed"; five on-topic papers ("CAR T-cell therapy in multiple myeloma: mission accomplished", "Bispecific BCMA/CD24 CAR-T cells control multiple myeloma growth", "Comparison of CAR T-cell and bispecific antibody as third-line or later-line treatments for multiple myeloma: a meta-analysis", "In vivo CRISPR screens identify modifiers of CAR T cell function in myeloma", "CAR T-cell therapy and bispecific antibodies in the management of multiple myeloma") and a grounded summary of idecabtagene vicleucel and ciltacabtagene autoleucel.
- Mechanism: A-152-02, `car t[Author] AND ...myeloma...`, 0 hits.
- Evidence: event logs `br_cart_022413.json` and `dv_cart_022420.json` in the adversary's scratchpad `c152adv/runs`.
- Why it matters: the refusal is confident and specific ("found nothing"), on one of the most published subjects in haematology. A researcher would trust it and stop. The card's goal (search the subject as written) is met in form and reversed in effect.
- NOT FIXED
### A-152-04: Live, end to end: "papers on brown rice" returns a confident, cited summary about adult children of alcoholics
- Severity: critical (new with this diff; worse than develop; the confident wrong answer the card exists to prevent, under a plan line that says the right subject was searched)
- What a person sees, branch (live run 3, `run_streaming`, researcher, no window, 2026-10-30):
  - plan line: "no gene, variant or disease was named, so searching the published literature for: brown rice" (looks exactly right)
  - "Found 5 papers [1][2][3][4][5]." then headings "ACoA Neural and Genetic Risk" and "ACoA Inflammation and Epigenetic Aging": "College students who were adult children of alcoholic parents and currently using alcohol hazardously reported more anxiety, depression, PTSD symptoms ... [6]", "Vulnerable ACoAs showed higher plasma CRP ... [7]", "Hazardous-use ACoAs exhibited lower predicted brain age but increased epigenetic age ... [8]"
  - records: "Stressors, Coping Resources, and Depressive Symptoms among Rural American Indian Older Adults", "Attitudes Toward Mental Health Services Among American Indians by Two Age Groups", "Neural and psychological characteristics of college students with alcoholic parents...", "Methylation of genes and regulation of inflammatory processes ... young adults with alcoholic parents", "Differing Effects of Alcohol Use on Epigenetic and Brain Age in Adult Children of Parents with Alcohol Use Disorder"
  - trust `answer`, "Based on 5 sources cited, all from PubMed". No word anywhere says the papers are not about brown rice.
- Develop (live run 4, same question): plan "...for: brown, rice"; two on-topic papers ("Germinated brown rice and its role in human health", "Germinated brown rice and its bio-functional compounds") summarised first, then three brown planthopper papers (a rice pest, off the person's likely meaning but still about rice). Mixed, but not wrong in kind.
- Mechanism: PubMed maps `brown rice` to the author `Brown Rice` (`brown rice[Author]`, 6 hits); every paper is that author's. See A-152-02.
- Evidence: `br_brice_*.json` and `dv_brice_*.json` in the adversary's scratchpad `c152adv/runs`.
- Why it matters: every surface that is meant to signal trust (the plan line naming the right subject, the grounded citations, the "Based on 5 sources" count) says this is a good answer. A student asking about brown rice gets a confident, well-cited answer about alcoholism in families. Develop's AND join could not produce this.
- NOT FIXED
### A-152-05: The picked publication window does not help: the author reading survives the date limit
- Severity: major (new with this diff; worse than develop; the windowed path the card's own example uses)
- What a person sees: `recent papers on brown rice`, "the last 5 years" picked, would list the author's two recent papers; `recent papers on CAR T in myeloma` with the window finds nothing.
- Evidence, live ESearch, 2026-10-30, the exact term `plan_topic_search` builds with a 5-year window:
  - `brown rice AND ("2021/10/30"[dp] : "3000"[dp])` -> 2 hits, translation `brown rice[Author] AND 2021/10/30:3000/12/31[Date - Publication]`. Develop's `brown AND rice AND (...)`: 2,249.
  - `car t myeloma AND (...)` -> 0, translation starts `car t[Author] AND ("multiple myeloma"[MeSH Terms] ...`. Develop's `car AND t AND myeloma AND (...)`: 2,059.
  - `fish ms AND (...)` -> 1, `(fish, ms[Author] OR fish ms[Author]) AND ...`.
- Why it matters: the card's acceptance example is a "recent papers on" question, so the windowed path is the one the card targets; it carries the same author defect as the unwindowed one.
- NOT FIXED
### A-152-06: Live, Plain language: "papers on fish and MS" opens "I found 5 published papers on this topic" over five papers by an author called Fish
- Severity: major (new with this diff; worse than develop's search; here the summary model caught the drift in its body text, but the count line, the plan line and the trust line did not)
- What a person sees, branch (live run 5, `run_streaming`, Plain language, no window, 2026-10-30):
  - plan line: "no gene, variant or disease was named, so searching the published literature for: fish ms"
  - first line: "I found 5 published papers on this topic [1][2][3][4][5]."
  - body: "The findings returned instead cover unrelated topics: one study describes how bilingual people ... develop two separate sound-category boundaries ... [6]. Another study reports how a bacterium called Shigella flexneri enters host cells ... [7]."
  - sources: "Laws of consent", "Oxidative N-dealkylation", "An analysis of the perception of stop consonants in bilinguals and monolinguals...", "Virus-like particle capture reveals coordination of actin remodeling during Shigella flexneri entry...", "Scope of practice"
  - trust `answer`, "Based on 5 sources cited, all from PubMed"; "This is a research summary, not medical advice."
- Contradiction on screen: "5 published papers on this topic" and "the findings returned instead cover unrelated topics" in consecutive sentences. The count line and the trust line are computed from the search result, so they cannot know the list drifted; only the model's honesty saved the body, and that is not guaranteed (A-152-04 shows the same model stating off-topic findings with no caveat).
- Develop (live run 6, same question, Plain language): Think's recent-work classifier asked "How far back should I search?" instead, so no develop answer to compare live. Develop's search for this question, by ESearch: `fish AND ms`, 10,223 hits, top five are fish-contaminant LC-MS/MS method papers (off the person's meaning, but about fish, and not one author's bibliography).
- Mechanism: `fish ms` -> `fish, ms[Author] OR fish ms[Author]`, 14 hits (A-152-01).
- Evidence: `br_fishms_plain_*.json`, `dv_fishms_plain_*.json` in the adversary's scratchpad `c152adv/runs`.
- NOT FIXED
### A-152-07: Extent: every CAR T question written "CAR T" with a space finds nothing on the branch
- Severity: major (new with this diff; worse than develop; quantifies A-152-02 and A-152-03)
- What a person sees: the refusal "I searched the published literature for car t ... and found nothing" for the whole CAR T literature, unless they happen to type a hyphen ("CAR-T") or "CAR T-cell therapy".
- Evidence, live ESearch, relevance, 2026-10-30, branch term against develop's AND term:

| Question | Branch term | Branch hits | Develop hits |
|---|---|---|---|
| papers on CAR T in lymphoma | car t lymphoma | 0 | 6,174 |
| papers on CAR T toxicity | car t toxicity | 0 | 5,245 |
| papers on CAR T for solid tumors | car t solid tumors | 0 | 4,188 |
| papers on CAR T and cytokine release syndrome | car t cytokine release syndrome | 0 | 2,972 |
| papers on CAR T in children | car t children | 0 | 4,584 |
| papers on CAR T relapse | car t relapse | 0 | 6,509 |
| papers on CAR T neurotoxicity | car t neurotoxicity | 0 | 2,017 |
| papers on CAR T cells in lupus | car t cells lupus | 0 | 269 |
| papers on CAR T cells | car t cells | 1 | 20,034 |
| papers on CAR-T in myeloma (hyphen) | car-t myeloma | 2,555 | 2,555 |
| papers on CAR T-cell therapy in myeloma | car t-cell therapy myeloma | 2,355 | 2,237 |
| papers on brown rice arsenic | brown rice arsenic | 0 | 183 |
| papers on brown rice vs white rice | brown rice vs white | 0 | 92 |
| papers on omega 3 fish and MS | omega fish ms | 0 | 265 |

- Every zero row's translation begins `car t[Author] AND`, `brown rice[Author] AND` or `(fish, ms[Author] OR fish ms[Author]) AND`.
- Counter-evidence, recorded so the extent is not overstated: 55 other everyday two-word topics (black rice, white rice, brown fat, red wine, sweet potato, music therapy, cord blood, pet ct, x ray, west nile, bird flu, fish allergy, salt intake, st john wort, saw palmetto and so on) produced no new author or journal tag. The defect is specific to word pairs PubMed's author index holds, but where it hits it is total.
- NOT FIXED
### A-152-08: Live: "papers on gold and RA" answers about gold therapy in rheumatoid arthritis on develop, and about eclampsia and transferrin on the branch
- Severity: major (new with this diff; worse than develop)
- What a person sees, branch (live run 7, researcher, no window, 2026-10-30): plan line "...searching the published literature for: gold ra"; "Found 5 papers [1][2][3][4][5]." then "The retrieved records instead cover unrelated topics: the incidence of pregnancy-associated hypertension and eclampsia ... [6], the chemical reactivity and essential role of histidines in transferrin iron-binding activity [7]." Records: eclampsia incidence, "The Color of Rice and the Chinese Paradox", "High blood pressure and hospitals", transferrin histidines, routine chest X rays. Trust `answer`, "Based on 5 sources cited, all from PubMed".
- Develop (live run 8, same question): plan "...for: gold, ra"; a grounded answer on gold in rheumatoid arthritis: auranofin "an approved gold metallic drug long used for RA treatment", gold nanoparticles in RA bone loss, gold nanorod microneedles for RA, gold compounds as nephrotoxic older DMARDs in RA patients. Four of five records on the person's subject.
- Pattern across the three live branch answers built on an author's bibliography: the body flagged the drift here and in A-152-06, and did not in A-152-04 (brown rice, presented as findings). In all three, the opening count line ("Found 5 papers", "I found 5 published papers on this topic"), the plan line naming the person's subject, and "Based on 5 sources cited" present the list as an answer. Whether the person is warned depends on the synthesis model noticing, run to run.
- Mechanism: `gold ra` -> `gold, ra[Author] OR gold ra[Author]`, 11 hits (A-152-01).
- Evidence: `br_goldra_*.json` and `dv_goldra_*.json` in the adversary's scratchpad `c152adv/runs`.
- NOT FIXED
### A-152-09: The judgement, filler and meta word lists also cut subject names, beyond the stopword cases in J-152-01
- Severity: minor (pre-existing, identical on develop, NOT introduced by this diff; filed because J-152-01 names only stopwords, numbers, Greek letters and accents, and the card's acceptance "searches for the subject as I wrote it" fails here too)
- What a person sees (branch `build_topic_term`, which is also the plan line text):
  - `papers on bad breath` -> `breath` ("bad" is a judgement word): halitosis becomes all of respiration, 426,032 hits, translation `"breath"[All Fields] OR ... "respiration"[MeSH Terms]`.
  - `papers on safe sex` -> `sex`; `papers on safe injection sites` -> `injection sites`; `papers on good clinical practice` -> `clinical practice`; `papers on best interests of the child` -> `interests child`
  - `papers on well being in nurses` -> `nurses` ("well" filler, "being" stopword); `papers on help seeking behaviour` -> `seeking behaviour`; `papers on take home naloxone` -> `home naloxone`
  - `papers on study design` -> `design`; `papers on journal clubs` -> `clubs`; `papers on research ethics` -> `ethics`; `papers on systematic reviews of acupuncture` -> `systematic acupuncture`; `papers on one health` -> `health`; `papers on the free will` -> `free`
- Why it matters: with the space join the plan line now shows these as one phrase ("for: breath", "for: nurses"), which reads as if it were what the person asked.
- NOT FIXED
### A-152-10: Nothing in the change, its tests or its live check would notice a term PubMed reads as an author or a journal
- Severity: minor (process and test gap; it is why A-152-01 to 08 shipped green)
- What: every new or changed test asserts the term STRING (`cystic fibrosis`, `car t myeloma` would pass the same assertions). A string test cannot see how PubMed translates it, and the build's live check (`build.md`, "Live counts") recorded hit counts for five terms only, none of them compared with develop's count for the same question beyond the four old ones, and none read back `querytranslation`. The runtime does not read it either: `querytranslation` appears in `src/system_03_search_agent/tools/` only in comments, so the product has no way to see that `car t myeloma` became `car t[Author] AND ...`.
- Reproduction: `grep -n "querytranslation" src/system_03_search_agent/tools/*.py` lists comment lines 261, 337, 436, 438, 451, 453 of `ncbi_eutils_actions.py` and no code that keeps or inspects the field. `grep -n -i author tests/system_03_search_agent/core/test_topic_search.py` finds one docstring (line 227) about the gene path, nothing on the topic term.
- "If this check were pointed at a subject that had done nothing at all": the build's live table would read the same for a term that silently became an author search, because it records only counts for questions that do not trigger the mapping.
- NOT FIXED

### Evidence (not a finding): what did not break
- Broader MeSH mapping did not drift the top five: `base editing` (maps to `"gene editing"[MeSH Terms]`, 47,227 against 8,732), `spatial transcriptomics` (109,147 against 21,659), `time restricted eating` (maps to intermittent fasting), `CAR T cell therapy` (maps to adoptive immunotherapy): branch top five on topic in each, by title.
- Journal ORing (`nature mental health`, `human mutation rates`, `public health nutrition`, `social science medicine`, `molecular cancer biology`) widened or narrowed counts but kept the top five on topic; `human mutation rates` pulled one Human Mutation paper on CHEK2 in yeast into rank 6, beyond the unwindowed cap of 5.
- The gate document's literature questions (GERD symptoms and risk factors, Ashkenazi variants, EGFR in NSCLC with trials, coffee and exercise): no new author or journal tag; counts equal or within 10 percent.
- 55 everyday two-word subjects produced no new tag (A-152-07).

## Verdict

FAIL against the card's goal ("a question about cystic fibrosis lists papers about cystic fibrosis" generalised to "searches for the subject as I wrote it"). The card's own example works. But the same space join lets PubMed read a pair of the person's words as an author's name, which the AND join made impossible, and through the full pipeline that produces either a false "found nothing" on a heavily published subject (CAR T in myeloma, lymphoma, toxicity, solid tumours and more; brown rice and diabetes) or a confident, cited answer built from an unrelated author's papers (brown rice -> adult children of alcoholics). All of A-152-01 to 08 are new with this diff and worse than develop. This is round one, so they are not inside a fix made during this phase's review loop, but they are inside this phase's own fix.

Verified by the adversary's own probes:
- Live ESearch with querytranslation for about 140 questions, branch term against develop's AND term (A-152-01, 02, 05, 07, 09 and the evidence above).
- Eight live answer runs through `run_streaming`, A/B against develop at 15363460: CAR T in myeloma (A-152-03), brown rice (A-152-04), fish and MS in Plain language (A-152-06, develop asked back instead), gold and RA (A-152-08).
- The runtime keeps no querytranslation (A-152-10), by grep.

Read only, not probed: whether a real person's CAR T or brown rice question always takes the topic path rather than a gene or disease path (three of four live branch runs took it; the one develop Plain language run asked for a window first), and the deployed product, which was not touched.
