# Card 29 verifier report, 2026-10-16

Fresh verifier, dial position 3, no prior context, closes nothing. Subject: fix/card29-abstract-sentence at 29767418, base b25e4c6d (`git diff b25e4c6d...29767418`). Worktrees: `<scratchpad>/v29` (29767418) and `<scratchpad>/v29dev` (b25e4c6d). Findings are appended the moment each is established, V-29-NN. Every live run goes through `core/run.py` `run_streaming`, `reads_placement=True`, develop's settings (CLASSIFIER_PROVIDER=jev, GUARD_MODEL and PLAN_MODEL deepseek/deepseek-v4-flash, SYNTH_MODEL z-ai/glm-5.2, PER_QUERY_COST_CAP_USD=0.25), never Opus.

## Findings

### Closures reproduced at unit level (verifier's own probe, `<scratchpad>/vscratch/probe_units.py`, branch tree)

- A-29-01, A-29-05, A-29-10, A-29-12 (retracted papers): real PubMed XML fetched by the verifier for PMIDs 32205204, 9500320, 11007230 (all three "Retracted Publication") and 32373993, 26178694 (controls), run through the branch's `_extract_pubmed_articles`: `retracted_field= True` for the three retracted records, `None` for the two controls. `has_retraction_notice` on 32205204's real abstract: True (its text carries the Elsevier notice); on the two Lancet-era papers False, so those rely on the record flag alone. `pick_snippets` over seven fake papers (one flagged retracted, one with a notice in its abstract): `asked: 3 shown keys: ['u0', 'u3', 'u4']`, the retracted and noticed papers used a place and were never asked, papers six and seven were never reached.
- J-29-10, A-29-02, A-29-13 (cut sentences): `abstract_candidates` on a three-sentence text whose last sentence ends in the ellipsis, in `[truncated]`, or is flagged `cut=True` with no marker: `candidates=2` each time, the cut tail dropped; the uncut control: `candidates=3`. `verified_sentence` on a sentence ending in the ellipsis: `None`.
- A-29-16 (batch removed): `grep call_jev_batch synthesis/snippets.py` prints nothing; the only gather is `asyncio.gather` over one `pick_snippet` per paper at line 515.
- J-29-03 (MCP allowlist): `git diff b25e4c6d 29767418 --stat -- tests/.../test_no_cost_and_auth.py` prints nothing, exit 0: the file is develop's bytes.

- J-29-07 (grace clamp): verifier probe `<scratchpad>/vscratch/probe_grace.py` with a real `Harness` key and a pick that never finishes: `budget spent 5 s ago: waited_ms=0 task.cancelled()=True`, `0.3 s of budget left: waited_ms=302 task.cancelled()=True`, `budget far away: waited_ms=1002 task.cancelled()=True`. Nothing is attached in any case and the slot is cleared. A finished pick attaches to the abstract citation, not the title citation (`title.snippet= None abstract.snippet= the finding`).
- J-29-06 (cancel on every exit): `_drop_snippet_pick` on a pending task: `cancelled= True slot_cleared= True`. The branch's `test_the_pick_is_cancelled_when_the_answer_ends_without_reading_it` makes `build_synth_messages` raise and asserts the task is cancelled, which is the probe the judge said was missing. Read, and run in the gate below; not mutated by me (my one mutation is on the retraction flag).
- J-29-08 (null key): `CitationPayload(...)` with no sentence: `'snippet' in model_dump: False`, in json dump False; with a sentence the key is present. Develop's strict model (`<scratchpad>/v29dev`) run over the branch's dumps: `develop reads no sentence : OK`, `develop reads with sentence : REJECTED`. See V-29-01.
- Adapter contract: `updates_citation`: `snippet+claim_text: True`, `snippet+display_index: False`. GraphQL `Citation.from_payload` of a citation with a sentence: `has snippet attr: False` (no key added). MCP `_citations_without_snippet` over one citation with and one without: both dumps have exactly develop's keys, `any snippet: False`.
- `_snippet_papers` with the fetched record held: the pick gets the record's own text (`len= 4012`, the 4,000 cap plus the ` [truncated]` marker), `cut= False`, `retracted= True` carried; `abstract_candidates` on it: 11 candidates, none ending in a marker. Without the record: the trimmed 2,000-character finding, `cut= True`.

### V-29-01: After a rollback to develop, a citation that carried a sentence still reopens over MCP as missing; J-29-08 is closed only for citations without one
- Severity: minor
- What: the fix round marks J-29-08 "Yes" closed. The branch leaves the key out only when the sentence is empty. A citation saved with a sentence (up to five per answer during the window) still carries `snippet`, and develop's `CitationPayload` is `extra="forbid"`, so develop's MCP `_reopened_citations` rejects it. The window shrank from every citation to the first five papers; it did not close.
- Reproduction: `<scratchpad>/vscratch/probe_dev_reads.py` run under `<scratchpad>/v29dev/src` over the branch's two dumps: `develop reads no sentence : OK` / `develop reads with sentence : REJECTED 1 validation error for CitationPayload`.
- Why it matters: only on a revert, and only for MCP reopen of answers saved during the window: those answers lose their first five papers' links. The judge named this residual in J-29-08 itself. The fix round's "Yes" overstates the closure.
- NOT FIXED

### Live runs (verifier's own, `<scratchpad>/vscratch/drive.py`, 19 branch runs and 6 develop runs, sequential, load average 7 to 10 falling to 6)

Branch at 29767418, wall seconds to `done`, pick time and attach wait measured by wrapping `pick_snippets` and `_attach_snippets`:

| Question, depth | Runs | Wall s | Pick ms | Attach wait ms | Papers asked of 5 | Sentences shown |
|---|---|---|---|---|---|---|
| hydroxychloroquine for COVID-19, researcher | probe0, hcq1 to 3 | 12.40, 15.53, 13.80, 12.26 | 561, 544, 267, 766 | 0 | 5, 5, 4 (32205204 retracted, skipped), 5 | 1, 1, 1, 1 |
| does vitamin C prevent the common cold, plain_language | vitc1 to 3 | 7.98, 10.49, 9.82 | 408, 497, 285 | 0 | 5, 5, 2 | 5, 5, 0 |
| treatment of acute migraine, clinical_brief | mig1 to 3 | 8.81, 9.10, 8.96 | 1217, 385, 269 | 0 | 5, 5, 5 | 4, 4, 4 |
| ileal LNH, colitis and autism, researcher | mmr1 to 3 | 15.55, 9.75, 8.89 | 257, 360, 417 | 0 | 3 (9500320 and 11007230 retracted, skipped, every run) | 2, 2, 2 |
| metformin anticancer mechanism, deep_technical | metc1 to 3 | 11.75, 10.53, 8.41 | 401, 335, 280 | 0 | 5, 5, 5 | 5, 5, 5 |
| probiotics and antibiotic-associated diarrhea in children, clinical_brief (new, not in any earlier round) | prob1 to 3 | 10.08, 18.88, 8.57 | 335, 352, 1484 | 0 | 5, 5, 5 | 5, 5, 5 |

Develop at b25e4c6d, same sitting, after the branch runs: hcq 18.18, 13.87; vitc 9.84, 8.79; mig 10.52, 11.02. Means, branch against develop: hcq 13.86 vs 16.02, vitc 9.43 vs 9.31, mig 8.96 vs 10.77. No branch run over 20 s (max 18.88, prob2, whose first token came at 15.12 s, before the pick is read). Attach wait was 0 ms in all 19 runs: the pick, even at 1,484 ms, finished before the writer. Total live spend $0.341 of $0.60.

Independent PubMed check (`<scratchpad>/vscratch/xcheck.py`, efetch of every shown PMID, publication types and comments read by the verifier, not by the code under test): `shown 62 distinct 24 retracted 0 not_in_real_abstract 0 incomplete 0`. `null snippet keys: [] count 0` over every citation event of 19 runs. The string "retracted" appears in 3 non-done events, all in hcq2, all develop's own title text "RETRACTED: Hydroxychloroquine and azithromycin..." in a token and a citation's record; the new `retracted` field never reaches an event. The retracted papers 32205204 (hcq2), 9500320 and 11007230 (mmr1 to 3) were among the cited five and were never asked about or shown. 32205204's abstract also tripped `has_retraction_notice`; the two Lancet-era papers relied on the record flag.

Every distinct shown sentence, read by the verifier against the question and the real abstract (24 distinct, 62 shown; "mislead" is the owner's shape: retracted, cut, out of context, or background shown as the finding):

| PMID | Sentence (start) | Runs shown | Answers | Misleads | Why |
|---|---|---|---|---|---|
| 32373993 | These studies were all suggestive that chloroquine and hydroxychloroquine can successfully treat COVID-19 infections. | 3 (probe0, hcq1, hcq3; Jev 0.28 to 0.32) | partly | yes | "These studies" are 9 reports as of 28 March 2020 (3 trials, 150 patients); shown alone under "what does the literature say" it reads as the literature's verdict. See V-29-03 |
| 32373993 | Hydroxychloroquine has been demonstrated to limit the replication of SARS-CoV-2 virus in vitro. | 1 (hcq2) | partly | no | in vitro, says so |
| 29272251 | In vivo and in vitro cancer cell culture studies demonstrate that metformin induces both AMPK-dependent and AMPK-independent genes/pathways... | 3 | yes | no | |
| 31178149 | Combination treatment upregulated phosphorylated AMPK and downregulated downstream phosphorylated S6, suggesting mTOR inhibition... | 3 | partly | no | the combination with simvastatin, not metformin alone |
| 34162423 | Metformin induces ferroptosis in an AMPK-independent manner to suppress tumor growth. | 3 | yes | no | |
| 40091020 | Mechanistically, metformin inhibited histone acetylation on FGFR4, thereby blocking the feedback activation of FGFR4 downstream pathways induced by SAHA. | 3 | yes | no | the sentence the adversary saw cut (A-29-02) is now complete |
| 40140842 | Mechanistically, this is achieved through AMPK activation and subsequent inhibition of downstream mTOR phosphorylation. | 3 (Jev 0.47 to 0.50) | no | yes | "this" is knockdown of 6PGD, not metformin. See V-29-02 |
| 30681821 | Lasmiditan, ubrogepant, and rimegepant are currently emerging acute migraine therapies that may be added to the arsenal... | 3 | no | no | background, not a finding |
| 34128998 | Compared with placebo, triptans and nonsteroidal anti-inflammatory drugs used individually were significantly associated with reduced pain at 2 hours and 1 day... | 3 | yes | no | the sentence the adversary saw lose to the objective fragment (A-29-03) |
| 26178694 | For 2-hour headache relief, standard dose triptan achieved better outcomes (42 to 76% response) than ergots (38%)... | 2 | yes | no | |
| 26178694 | Standard dose triptans relieved headaches within 2 hours in 42 to 76% of patients... | 1 | yes | no | |
| 38568487 | These new treatments have not been associated with vasospasm or increased cardiovascular risk... | 3 | partly | no | "These new treatments" (gepants, lasmiditan) is the sentence before |
| 16003132 | The severity of ileal LNH was significantly greater in ASD children compared with controls... (P < 0.0001). | 3 | yes | no | the paper's own finding |
| 11241044 | We have reported colitis with ileal lymphoid nodular hyperplasia (LNH) in children with regressive autism. | 3 (Jev 0.45 to 0.52) | no | yes | the authors citing their own earlier, retracted report (9500320), shown as this paper's finding while its findings (s4, s9) were on offer. See V-29-04 |
| 26756877 | If the use of probiotics for preventing AAD is considered... the WG recommends using Lactobacillus rhamnosus GG... or Saccharomyces boulardii... | 3 | yes | no | long, complete |
| 29257353 | The incidence of CDAD was 1.5% (70/4525) in the probiotic group compared to 4.0%... (RR 0.40...). | 3 | yes | no | |
| 31039287 | After making assumptions for those lost, the observed benefit was still statistically significant... 12% vs 19%... | 3 | yes | no | |
| 35727573 | Compared with placebo (n = 155), the probiotic (n = 158) had no effect on risk of AAD (RR 0.81; 95% CI, 0.49-1.33). | 3 | yes | no | a negative trial, shown honestly |
| 40931979 | Our pooled analysis indicates that probiotics probably result in a small ARR of 1.7%... (RR 0.86, 95% CI 0.72 to 1.01; P = 0.074...). | 3 | yes | no | |
| 30113569 | We concluded the consumption of vitamin C does not prevent the incidence of common cold. | 2 | yes | no | |
| 33193359 | No current clinical recommendations support the possibility of significantly decreasing the risk of respiratory infections by using high-dose supplements of vitamin C... | 2 | yes | no | |
| 39803741 | In controlled trials in the general human population, vitamin C at a dose greater than 1 g/day did not prevent common colds. | 2 | yes | no | |
| 23440782 | The failure of vitamin C supplementation to reduce the incidence of colds in the general population indicates that routine vitamin C supplementation is not justified... | 2 | yes | no | |
| 16373990 | These trials document that adequate intakes of vitamin C and zinc ameliorate symptoms and shorten the duration of respiratory tract infections... | 2 | partly | no | duration, not prevention; "These trials" is the sentence before |

Counts: 24 distinct sentences, 16 answer, 5 partly, 3 do not. 3 distinct sentences mislead a person, 9 of the 62 shown (each shown on every run of its question). Of the three, 40140842 and 32373993 ("These studies") are worse than showing nothing; 11241044 is a background claim shown as a finding and is arguable.

### V-29-02: Under the metformin question, a sentence whose "this" is 6PGD knockdown is quoted as the paper's finding, on every run, after the fix that was meant to exclude it
- Severity: major
- Sits inside a fix made during this phase: yes. The fix round rewrote `_INSTRUCTIONS` and `_NONE_CRITERION` to exclude a sentence that "leans on the sentences before" it and claimed A-29-04 "partly" closed; it never re-ran the question A-29-04 was found on.
- What: PMID 40140842 ("Inhibition of 6-phosphogluconate dehydrogenase suppresses esophageal squamous cell carcinoma...") is cited for `papers on the mechanism by which metformin inhibits cancer cell growth` (deep_technical). On all three runs (metc1 to 3, Jev 0.47, 0.49, 0.50) the card quotes: "Mechanistically, this is achieved through AMPK activation and subsequent inhibition of downstream mTOR phosphorylation." In the abstract, the sentence before is "The experiments demonstrated that knockdown of 6PGD induces oxidative stress and suppresses ESCC cell proliferation." Metformin enters the paper only as physcion's combination partner (s6, s9). The option list offered s6 and s9, which name metformin, and "none".
- Reproduction: `<scratchpad>/vscratch/out/metc1.summary.json` (`shown` entry for 40140842, `snippet_decisions[4]` = s4 at 0.47); the real abstract from the verifier's own efetch, `<scratchpad>/vscratch/ncbi/abstracts.json`, printed by `<scratchpad>/vscratch/context.py 40140842`.
- Why it matters: a researcher asking for metformin's mechanism reads, under this paper, a mechanism claim that the paper makes for 6PGD knockdown, not for metformin. Develop shows the title only, which asserts nothing about metformin. This is the "out-of-context sentence" shape the owner ranks as the highest risk, and it is the same sentence A-29-04 named.
- NOT FIXED

### V-29-03: "These studies were all suggestive that chloroquine and hydroxychloroquine can successfully treat COVID-19 infections" is still the hydroxychloroquine answer's only quoted sentence, picked at 0.28 to 0.32 with no floor
- Severity: major (unsure whether the owner reads it as worse than nothing: the paper did say it)
- Sits inside a fix made during this phase: yes, the same criteria rewrite; the fix round's own table shows it on 7 of its runs and marks it "yes, but These studies needs the sentence before".
- What: for `what does the literature say about hydroxychloroquine for COVID-19` (researcher), the classifier answers "none" for four of five papers and, for PMID 32373993 (a review of 9 reports as of 28 March 2020, three trials with 150 patients in total), picks s5, the "These studies" sentence, at 0.28 (hcq3), 0.30 (probe0) and 0.32 (hcq1), the lowest confidences of the whole sitting. It is the only quoted sentence on the page. The abstract's own hedge, "the hypothetical benefit of these two drugs" (s10), and the in-vitro sentence (s2, picked once in hcq2) were on offer.
- Reproduction: `<scratchpad>/vscratch/out/hcq1.summary.json`, `snippet_decisions` = `none 0.9, none 1.0, none 0.97, none 0.55, s5 0.32`; the sentence and options in `<scratchpad>/vscratch/context.py 32373993`.
- Why it matters: a person asking what the literature says sees, in quotation marks, that the drugs "can successfully treat COVID-19 infections", a claim the later trials refuted, lifted from a sentence about nine early reports. The pick's own confidence (0.28 to 0.32) says the classifier was close to "none"; nothing in the code uses that number. Develop shows the title only.
- NOT FIXED

### V-29-04: A paper's opening sentence citing the authors' own retracted report is shown as that paper's finding, while its findings were on offer
- Severity: minor
- What: PMID 11241044 (Furlano and others 2001, not retracted) opens "We have reported colitis with ileal lymphoid nodular hyperplasia (LNH) in children with regressive autism", a reference to the retracted 9500320. On all three mmr runs (Jev 0.45 to 0.52) that sentence is quoted under the paper, while s4 ("Histology demonstrated lymphocytic colitis in the autistic children, less severe than classical inflammatory bowel disease") and s9 (the immunohistochemistry conclusion) were on offer. The retracted paper itself is skipped on every run, so its claim re-enters the page through this companion paper's background sentence.
- Reproduction: `<scratchpad>/vscratch/out/mmr1.summary.json` (`snippet_decisions[1]` = s0 at 0.51); `<scratchpad>/vscratch/context.py 11241044`.
- Why it matters: the owner's "background claim shown as the paper's finding" shape. The claim is one the authors do make, so it is less severe than V-29-02.
- NOT FIXED

### Mutation and gates (verifier's own runs, `<scratchpad>/v29` at 29767418)

One mutation, the highest-risk property: in `tools/ncbi_eutils_actions.py` line 1298 the parse's `if _pubmed_record_is_retracted(article_el):` became `if False and ...`. `pytest` over the four card 29 test files: `3 failed, 169 passed in 4.02s`, the three being `test_a_record_pubmed_marks_retracted_carries_that_flag` (two cases) and `test_a_retraction_comment_marks_the_record_retracted`. Restored from a copy; `git diff --stat` empty afterwards.

| Gate | Result |
|---|---|
| `ruff check` (no path) | All checks passed! |
| `isort --check-only --diff src tests services tracker alembic .claude .github` | exit 0 (Skipped 2 files) |

### V-29-05: The retraction-notice pattern reads an ordinary clinical sentence as a retraction, so such a paper is silently treated as retracted and shows no sentence
- Severity: minor (fails safe: a missing sentence, never a wrong one; the paper keeps its place among the five)
- Sits inside a fix made during this phase: yes, `has_retraction_notice` is new in the fix round.
- What: `_RETRACTION_NOTICE` matches "(this|the) (article|paper|publication|manuscript|study|work|report)" followed by up to 60 non-period characters and then "retracted" or "withdrawn". Any sentence about a study in which something was withdrawn matches. The fix round's "tested non-match" covers "the drug was withdrawn" only because "drug" is not in the noun list.
- Reproduction: `has_retraction_notice` on the branch, verifier's inputs: `True | The study drug was withdrawn in three patients because of nausea.` / `True | The study was stopped early and the drug withdrawn from the market.` / `True | In this study, consent was withdrawn by two participants before dosing.` / `True | This report describes a patient in whom the catheter was withdrawn.` / `False | Opioid withdrawal symptoms were scored daily.` / `True | This article has been retracted at the request of the editor.`
- Why it matters: a trial abstract that mentions withdrawn consent or a withdrawn drug (common in clinical abstracts) gets no sentence and uses up one of the five places, with no log line saying why. Not a degradation against develop.
- NOT FIXED

### Contract on every adapter and reopened answers (verifier's own probes and greps)

- Event stream (REST, SSE, web): no citation event of 19 live runs carried `snippet: null`; the key appears only with a sentence (`null snippet keys: [] count 0`).
- MCP: `_citations_without_snippet` clears it on both the live fold and the reopen return; dumps after clearing have exactly develop's keys (probe part H).
- GraphQL: `Citation.from_payload` of a citation with a sentence has no `snippet` attribute; the type is unchanged against develop.
- CLI: `grep -n snippet src/system_03_search_agent/adapters/cli/render.py` prints nothing; unchanged against develop.
- Reopened answers (web): `grep -n snippet frontend/src/lib/api.ts frontend/src/components/screens/SavedAnswerScreen.tsx` prints nothing; those files are not in the diff, so a reopened answer renders as on develop (J-29-09 remains open by design).
- Frontend: `npx vitest run` over the verifier's probe `<scratchpad>/v29/frontend/src/zzVerifier29.probe.test.tsx` (a sentence holding `<img onerror>`, a markdown link, a `javascript:` anchor and `**bold**`: 0 img, 0 a, 0 strong elements; the summary's `aria-labelledby` name does not contain the sentence; a click on the sentence leaves the card closed) plus the branch's `AnswerScreen.sourceSnippet.test.tsx` and `useRunView.snippet.test.ts`: `Test Files 3 passed (3)`, `Tests 16 passed (16)`. The probe file is the verifier's and is removed with the worktree.
- 1280 and 390 pixel rendering: not looked at by the verifier either; no screenshot exists in any round.

| `npm run build` | built in 220ms, exit 0, only the existing large-chunk warning |
| `npx vitest run --maxWorkers=2 --testTimeout=90000` | Test Files 72 passed (72), Tests 648 passed (648): the branch's 71 files and 647 tests plus the verifier's one probe file |
| `pytest tests/system_03_search_agent -m "not integration" -q` | 7020 passed, 143 skipped, 24 deselected, 1 xfailed, 7 warnings in 245.06s, exit 0 |

## Verdict

HOLD, naming V-29-02 (and V-29-03 for the owner's reading). Both sit inside the fix round's criteria rewrite, the change this phase made to close A-29-03 and A-29-04, which fires the stop condition: the fix round never re-ran the metformin question its A-29-04 example came from, and on every one of the verifier's three runs the same out-of-context sentence is quoted under the same paper. Against the owner's bar, "nothing worse than develop for a person": develop shows that paper's title only, which asserts nothing about metformin; the branch quotes a 6PGD-knockdown mechanism under a metformin question. That is the highest-risk shape the owner named.

What the branch does better than its first commit, verified: 0 of 62 shown sentences on a retracted paper (3 retracted papers were in the cited five and were skipped on every run), 0 cut, 0 outside the real abstract, every answer under 20 s, no added wait (attach wait 0 ms in 19 of 19 runs), no key on a citation without a sentence on any adapter, MCP keys exactly develop's. A fresh question (probiotics) gave five clean finding sentences on all three runs.

Verified with the verifier's own probes: the retracted-paper closure (real PubMed XML through the parser, `pick_snippets` skipping, three retracted PMIDs skipped live), the cut-sentence closure (unit and the 4,000-cap record path, 0 incomplete live), the batch removal, the MCP allowlist bytes, the null-key rule (branch dumps read by develop's strict model), the grace clamp and cancel on exit (real `Harness` key), the adapter folds, the hostile-sentence render, the live timing against develop in the same sitting, the independent PubMed cross-check of every shown sentence, and the mutation on the retraction parse (3 red, restored).

Only read, not run: the exception-exit cancel test's own body (its behaviour was probed through `_drop_snippet_pick` instead), the saved-row path that stores the sentence, and 1280 and 390 pixel rendering, which no round has looked at.

Worktrees `<scratchpad>/v29` (29767418) and `<scratchpad>/v29dev` (b25e4c6d) removed after this report; the probe file and the `node_modules` symlink went with the first.
