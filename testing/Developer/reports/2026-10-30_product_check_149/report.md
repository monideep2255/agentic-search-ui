# Product check of card 149 on develop, 2026-10-30

A pre-screen before the owner retests card 149 (merged #320). It closes nothing; the owner's verdict closes.

- Target: develop web `https://search-agent-web-develop-2aeb.up.railway.app`, API `https://search-agent-api-develop-43b3.up.railway.app`. `/health` read `{"status":"ok","app_env":"develop"}` before the first capture, and every run logged it again (field `health` in each `*_log.json`).
- Deployed commit: abea730d, the merge of #320, as stated in the brief.
- Asked as a guest, Researcher mode, no sign-in. No golden run, by the brief.
- Capture: a short Playwright script kept outside the repository, run from `frontend/`, one fresh browser per question and width. It picks Researcher, asks, times from the Search click to the end of streaming, saves the answer text, opens Sources, every layer group and every source card, reads every source card's link hrefs from the page, saves a full-page screenshot before and after opening Sources, and measures `scrollWidth - clientWidth`.

## Findings

### PR-149-01: Query 21 at 1280 cites only human GCK, gene 2645, and OMIM 138079; no source links to gene 24385 or reads "Gck @GENE_GCK"
- Kind: answer
- Verdict: pass
- Card: 149
- What: Researcher, guest, answered in 13.9 s (meta line "Answered13.4s · 13 tool calls · 21 sources cited from 2 layers"). All 21 source cards opened; their hrefs, read from the page, include `https://www.ncbi.nlm.nih.gov/gene/2645/` (card [5][9], "gene 2645") and `https://omim.org/entry/138079` (card [8], "omim 138079"). No href on the page contains `gene/24385`, and no source card reads "Gck" or "@GENE_GCK". The gene table reads "GCK NCBIGene:2645 5, 9".
- Evidence: `testing/Developer/reports/2026-10-30_product_check_149/q21_gck_1280_log.json` (fields `sources`, `all_page_hrefs`), `q21_gck_1280_sources_open_full.png`, `q21_gck_1280_answer.txt`.
- Why a person would care: a clinician who clicks the gene citation lands on the human GCK page, not the rat one.
- NOT CLOSED

### PR-149-02: The GCK answer carries the sentence "The gene symbol GCK and its corresponding gene name GCK."
- Kind: answer
- Verdict: needs your eye
- Card: not established. Its markers 5 and 9 both resolve to gene 2645, and card 149 changed which PubTator3 gene rows survive, so the sentence may be new with this card; I have no before capture to compare.
- What: the second paragraph of the answer is one sentence with no verb that names the symbol twice: "The gene symbol GCK and its corresponding gene name GCK.⁠5, 9". The gene's name, glucokinase, does not appear in it.
- Evidence: `testing/Developer/reports/2026-10-30_product_check_149/q21_gck_1280_answer.txt`, line 12.
- Why a person would care: "it told me GCK is called GCK"; it reads as broken and teaches nothing.
- NOT CLOSED

### PR-149-03: A rodent heart paper sits among GCK's papers under a human disease question
- Kind: answer
- Verdict: needs your eye
- Card: earlier (the PubMed search, not the PubTator3 gene row card 149 changed; same family as card 122)
- What: the "PubMed records found" table lists "Inhibition of Hmbox1 Promotes Cardiomyocyte Survival and Glucose Metabolism Through Gck Activation in Ischemia/Reperfusion Injury." PMID:38708602, marker 17. Its title writes the rodent-style "Gck". It is a paper, not a gene record, so it is outside card 149's promise.
- Evidence: `testing/Developer/reports/2026-10-30_product_check_149/q21_gck_1280_answer.txt`, line 28.
- Why a person would care: a clinician asking which diseases GCK causes gets a cardiac injury study among five papers.
- NOT CLOSED

### PR-149-04: KRAS at 1280 cites human KRAS, gene 3845, and nothing links to gene 24525
- Kind: answer
- Verdict: pass
- Card: 149
- What: Researcher, guest, answered in 12.9 s ("Answered12.4s · 13 tool calls · 17 sources cited from 3 layers"). All 17 source cards opened. The only gene href on the page is `https://www.ncbi.nlm.nih.gov/gene/3845` (card "[1][2] NCBIGene 3845 L1 · graph, L2 · live"). No href contains `gene/24525`, and no card reads "Kras". OMIM 190070, the human KRAS entry, is cited at marker 5.
- Evidence: `testing/Developer/reports/2026-10-30_product_check_149/kras_1280_log.json`, `kras_1280_sources_open_full.png`, `kras_1280_answer.txt`.
- Why a person would care: the KRAS citation opens the human KRAS page.
- NOT CLOSED

### PR-149-05: "What does KRAS do?" gets no written answer, only a record list
- Kind: answer
- Verdict: fail
- Card: not established. No before capture; card 149 removed a PubTator3 row from this answer's records, which could change what the summary had to work with, but the note's wording is the existing summary check's.
- What: the answer opens "Found 1 gene record for KRAS: KRAS proto-oncogene, GTPase.⁠1", then tables, then the note "no written summary could be checked against the records, so this answer lists the records found with their sources". No sentence says what KRAS does. Rubric line 1 fail (it lists what was found instead of answering); rubric line 2 fail (a general chatbot says KRAS is a GTPase switch in growth signalling; this answer does not).
- Evidence: `testing/Developer/reports/2026-10-30_product_check_149/kras_1280_answer.txt`, lines 10 and the NOTES line.
- Why a person would care: "I asked what KRAS does and it gave me a list of links."
- NOT CLOSED

### PR-149-06: SHH at 1280 cites human SHH, gene 6469, and nothing links to gene 20423
- Kind: answer
- Verdict: pass
- Card: 149
- What: Researcher, guest, answered in 13.4 s ("Answered12.9s · 13 tool calls · 17 sources cited from 3 layers"). All 17 source cards opened. The only gene href on the page is `https://www.ncbi.nlm.nih.gov/gene/6469` (card "[1][2][19] NCBIGene 6469"). No href contains `gene/20423`, and no card reads "Shh" as a gene record. OMIM 600725, human SHH, is cited at marker 5.
- Evidence: `testing/Developer/reports/2026-10-30_product_check_149/shh_1280_log.json`, `shh_1280_sources_open_full.png`, `shh_1280_answer.txt`.
- Why a person would care: the SHH gene citation opens the human page, not the mouse one.
- NOT CLOSED

### PR-149-07: The SHH answer opens on "This cholesterol modification", with nothing before it for "This" to point at
- Kind: answer
- Verdict: needs your eye
- Card: earlier (the known "These include..." opening with no referent, listed in the test queries document as still worth reporting)
- What: the first sentence is "This cholesterol modification restricts the signalling molecule to the cell surface and prevents free diffusion throughout the developing embryo.⁠19". The next is "Found 1 gene record for SHH, of 126 available: sonic hedgehog signaling molecule.⁠1". No sentence says what SHH does in general (rubric line 1 fail; line 2 partial, the cholesterol detail is specific). The note reads "this answer was truncated because only 68 of the 126 records that matched this question in the graph were retrieved", while the opening line says 1 gene record of 126.
- Evidence: `testing/Developer/reports/2026-10-30_product_check_149/shh_1280_answer.txt`, first answer paragraph and the NOTES line.
- Why a person would care: "which cholesterol modification?"; the answer starts mid-thought, and "1 gene record of 126" reads as if 125 SHH genes were left out.
- NOT CLOSED

### PR-149-08: "What does the AR gene do?" lists no Arginine, Arsenic or Arthritis entity, cites human AR, gene 367, and answers what AR does
- Kind: answer
- Verdict: pass
- Card: 149
- What: Researcher, guest, answered in 23.9 s ("Answered23.2s"). All 17 source cards opened. The only gene href is `https://www.ncbi.nlm.nih.gov/gene/367` (card "[1][2][19] NCBIGene 367"); OMIM 313700 is cited. The page text with every source open contains none of "Arginine", "Arsenic", "Arthritis" or "Literature entity". The answer opens "Upon binding its hormone ligand, the receptor dissociates from accessory proteins, translocates into the nucleus, dimerizes, and stimulates transcription of androgen-responsive genes.⁠19", which answers the question (rubric lines 1 and 2 pass), though "the receptor" comes before AR is named.
- Evidence: `testing/Developer/reports/2026-10-30_product_check_149/ar_1280_log.json`, `ar_1280_answer_sources_open.txt`, `ar_1280_sources_open_full.png`.
- Why a person would care: the AR answer is about the androgen receptor, with no stray amino acid, poison or joint disease in its sources.
- NOT CLOSED

### PR-149-09: Control TP53 cites human TP53, gene 7157, as before in kind, but gets no written answer either
- Kind: answer
- Verdict: needs your eye
- Card: earlier, by inference. TP53's PubTator3 gene entity is the human one per the card 149 diagnosis, so card 149 should not touch this answer; it shows the same "no written summary" shape as KRAS (PR-149-05), which makes that shape unlikely to be card 149's.
- What: Researcher, guest, 12.9 s. The only gene href is `https://www.ncbi.nlm.nih.gov/gene/7157`; OMIM 191170 is cited. The answer's only sentence is "Found 1 gene record for TP53, of 125 available: tumor protein p53.⁠1", and the note reads "this answer was truncated because only 60 of the 125 records that matched this question in the graph were retrieved". Rubric line 1 and line 2 fail.
- Evidence: `testing/Developer/reports/2026-10-30_product_check_149/tp53_1280_answer.txt`, `tp53_1280_log.json`.
- Why a person would care: "What does TP53 do?" is one of the most common questions anyone asks, and the answer does not say.
- NOT CLOSED

### PR-149-10: Control query 1 (BRCA1 diseases) cites human BRCA1, gene 672, but opens on the fragment "The association with Fanconi anemia complementation group S."
- Kind: answer
- Verdict: needs your eye
- Card: earlier (the known broken-first-sentence class, listed in the test queries document as still worth reporting)
- What: Researcher, guest, 13.9 s, 21 sources. The only gene href is `https://www.ncbi.nlm.nih.gov/gene/672/`; OMIM 113705 is cited. Four diseases are named in words. The first sentence is the fragment "The association with Fanconi anemia complementation group S.⁠4", then "Found 4 disease records for BRCA1: ...".
- Evidence: `testing/Developer/reports/2026-10-30_product_check_149/q1_brca1_1280_answer.txt`, `q1_brca1_1280_log.json`.
- Why a person would care: the first thing a first-time visitor reads is a half sentence.
- NOT CLOSED

### PR-149-11: At 390, query 21 again cites only gene 2645 and OMIM 138079, fits the width, and this time reads well
- Kind: screen
- Verdict: pass
- Card: 149
- What: a separate run at 390, Researcher, 9.9 s. The only gene href is `https://www.ncbi.nlm.nih.gov/gene/2645/` (card "[5][9][23] gene 2645"); `https://omim.org/entry/138079` is cited; no href contains `gene/24385`, no card reads "Gck @GENE_GCK". Horizontal overflow 0 px. Tables stack name over identifier; nothing clipped. This run has no "The gene symbol GCK and its corresponding gene name GCK." sentence (PR-149-02); in its place: "Tissue-specific isoforms in the pancreas mediate glucose-stimulated insulin secretion, while hepatic isoforms drive glucose uptake and glycogen conversion.⁠23", so PR-149-02 varies between runs.
- Evidence: `testing/Developer/reports/2026-10-30_product_check_149/q21_gck_390_full.png`, `q21_gck_390_log.json` (`sw_minus_cw: 0`), `q21_gck_390_answer.txt`.
- Why a person would care: on a phone the GCK answer reads cleanly and its gene link is the human one.
- NOT CLOSED

### PR-149-12: At 390, KRAS again cites only gene 3845, fits the width, and again has no written answer
- Kind: screen
- Verdict: pass for the card and the layout; the missing summary is PR-149-05
- Card: 149
- What: 13.9 s, 17 sources, only gene href `https://www.ncbi.nlm.nih.gov/gene/3845`, no `gene/24525`, overflow 0 px. Same "no written summary could be checked against the records" note as at 1280.
- Evidence: `testing/Developer/reports/2026-10-30_product_check_149/kras_390_full.png`, `kras_390_log.json`, `kras_390_answer.txt`.
- Why a person would care: the phone view is clean; the content gap is the same as on desktop.
- NOT CLOSED

## Summary

- Card 149's promise holds on all 8 runs: no source links to gene 24385, 24525 or 20423, or reads "@GENE_", or lists an Arginine, Arsenic or Arthritis entity (searched across every `*_log.json` and answer text). Each gene question cites its human record: GCK 2645, KRAS 3845, SHH 6469, AR 367, TP53 7157, BRCA1 672.
- Answer times, Search click to end of streaming: GCK 13.9 s (1280) and 9.9 s (390), KRAS 12.9 s and 13.9 s, SHH 13.4 s, AR 23.9 s, TP53 12.9 s, BRCA1 13.9 s. Median 13.6 s, worst 23.9 s (AR). None over 25 s.
- Overflow at 390: 0 px on both runs. No new screen, so no design gap.
- Fails: PR-149-05 (KRAS gets no written answer). Needs your eye: PR-149-02, 03, 07, 09, 10.
- Every verdict rests on a log, answer text or screenshot I read myself. Screenshots read: `q21_gck_1280_sources_open_full.png`, `q21_gck_390_full.png`; the other runs are judged from their answer text and hrefs read from the page.
- Not captured: no golden run (brief); no before-the-card captures, so where a finding's origin says "not established" or "by inference" it is not proved; no prototype comparison, since no screen changed; card 155 (unrelated trials) and card 156 (species follow-ups) not re-filed.

## The lead's follow-up on PR-149-05

The lead asked `What does KRAS do?` twice on develop's code before card 149 (`15363460`) and twice after it (`abea730d`), locally in Researcher, on 2026-10-30. All four answers read only "Found 1 gene record for KRAS: KRAS proto-oncogene, GTPase [1]." with no written summary. The missing summary is not from card 149; it is the older no-summary case of cards 128 and 130.
