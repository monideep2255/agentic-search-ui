# Card 56 round 3: judge report

Fresh-context judge, one round, 2026-10-06. Branch `fix/card56-r3-minimal`, reviewed as `git diff origin/develop...HEAD -- src tests`.

## Findings

### J3-56-01: In a conversation, the SARS-CoV-2 question with no entity is now answered about the previous turn's gene

- Severity: major. Blocking: I lean yes, but it is the owner's call (see "Why it matters"). Unsure whether the owner already accepted it.
- Regression of: J-56-04 is not involved. This sits inside this round's own new skip (`graph.py:4322` to `4327`), the code written to remove the SARS binding. It is a new outcome that the skip routes into develop's existing memory binding (`graph.py:6541` to `6546`), not a defect in the skip's logic.
- What: in a conversation whose last subject was BRCA1, the findings.md question ("Find SRA runs of SARS-CoV-2 sequenced on Illumina from clinical respiratory samples, and explain why each one matched.") with Think returning no entity (5 of 26 live runs on develop's plan model, findings.md) now binds nothing in Think. `_needs_clarification` (`graph.py:6385`) returns False because memory holds an antecedent, so the question is not asked back. Plan then binds the remembered BRCA1 (`graph.py:6541` to `6546`, `memory_bound=True`). The word "one" in "each one" is a referring word (`graph.py:6259`), so the topic-search escape at `graph.py:6838` to `6846` does not apply either.
- Reproduction: an offline probe (scratchpad `probe_plan.py`, the branch test file's fakes, MedGen faked to bind any term except "SRA[title]", which is 0 hits live, judge round 1), think_node then plan_node, `record_type="sra"`, entities `[]`, memory `("BRCA1", "NCBIGene:672", "Gene")`:
  - develop (fcfc6827 `graph.py`, byte-identical to origin/develop's): resolved `['SARS']`, one cypher_query on `target_entities=['MedGen:C141626']`, memory_bound False.
  - branch: resolved `[]`, clarification None, 13 planned calls starting with `cypher_query target_entities=['NCBIGene:672']` with memory_bound True, then dataset reports, layer calls and a second cypher on NCBIGene:672.
  - With no memory the branch does what the brief says: clarification `CLARIFICATION_QUESTION`, no calls.
- Why it matters: the brief's contract says "when Think misses the organism the person gets develop's existing question asked back". In a conversation that holds a gene, the person who asked for SARS-CoV-2 sequencing runs instead gets a confident, cited answer about BRCA1. Develop's wrong subject (the disease SARS) is swapped for a different wrong subject (the earlier gene). From the user's chair a BRCA1 answer to a virus question may be easier to spot as wrong than SARS records, but it is still "a confident wrong record". build_r3.md's follow-up tests cover only questions with no organism in them ("What SRA runs are there for it?", "And its SRA runs?"), so this case is untested and unreported.
- Suggested fix: the owner decides whether this is acceptable for the smallest fix. If not, the narrowest option is to also ask the question back (or skip the memory binding) when the D3 skip fired, which means recording in Think that a piece was skipped. That is new behaviour beyond the owner's "no new question" scope, so it needs the owner.
- NOT FIXED

### J3-56-02: Two of the skip's stated rules have no test: a word that also stands alone, and the spaced dash

- Severity: minor. Non-blocking (the code behaves correctly on both today, by my probe; only the guard against a future edit is missing).
- What: `tests/system_03_search_agent/core/test_think_sra_disease_fallback.py` never puts a token both inside a joined name and alone in one question, and never has a dash with a space on its far side. Two mutants of `_only_a_piece_of_a_joined_name` survive all 49 Think tests (the new file plus `test_think_retry.py`, `test_think_organisms.py`, `test_think_disease_and_organism.py`):
  - B, "skip when any one place is a piece" (`graph.py:3519` to `3520` changed to `if joined_before or joined_after: return True` and the final line to `return False`): 49 passed.
  - C, the far-side letter-or-digit check removed after the token (`graph.py:3516` `and query_text[end + 1].isalnum()` deleted): 49 passed.
- Reproduction: mutants applied to a scratch export of the branch (never the worktree) by scratchpad `mutate.py`; output `== B_any_joined_skips 49 passed in 2.19s`, `== C_no_far_side_check 49 passed in 2.13s`. On the unmutated branch my offline probe shows the right behaviour: "SARS and SARS-CoV-2 runs in SRA" (record type sra, empty extraction) still tries "SARS[title]" exactly as develop does, and "SRA runs - MODY patients" still tries "MODY[title]".
- Why it matters: the first rule is the brief's own question ("what if the same word also stands alone elsewhere in the question?") and build_r3.md's first logged choice; the second is its third logged choice. Either can be broken by the next edit with every test green, and the B mutant would silently stop binding a disease the person typed as a word of its own.
- Suggested fix: add two arms to the new file, "SARS and SARS-CoV-2 runs in SRA" binds the SARS records, and "SRA runs - MODY patients" binds MODY, both with record type sra and no entity.
- NOT FIXED

### J3-56-03: A disease whose own name is hyphen-joined no longer binds on an SRA or assembly question

- Severity: minor. Non-blocking: it is what the owner's wording ("never binds a word cut out of a hyphen-joined name") literally asks for, and build_r3.md discloses the COVID-19 case. Filed so the owner sees the other names it reaches.
- What: with record type sra or assembly and no entity extracted, every token that only appears inside a hyphen-joined name is skipped, including names that are the disease itself.
- Reproduction: offline probe on develop (fcfc6827 `graph.py`) and the branch, same fakes, MedGen faked to bind any term but "SRA[title]":

| Question (record type sra, no entity) | Develop tries and binds | Branch tries and binds |
|---|---|---|
| SRA runs from COVID-19 patients | COVID | nothing; Plan runs a PubMed topic search "sra AND runs AND covid-19 AND patients" |
| SRA runs from GCK-MODY patients | GCK, MODY | nothing |
| SRA runs of HIV-1 isolates | HIV | nothing |
| SRA-runs of MODY | SRA, MODY | MODY |
| MODY-SRA runs | MODY, SRA | nothing |

- Why it matters: a person asking for sequencing runs from patients with a hyphen-named condition (GCK-MODY, HNF1A-MODY, COVID-19) no longer has the condition recognised when Think misses it. In my probe the branch's outcome (a PubMed topic search on the whole question) is arguably better than develop's MedGen graph call, so I am unsure this is a loss. Only the COVID-19 row is in build_r3.md's "Not covered".
- Suggested fix: none needed for this card if the owner accepts it; list GCK-MODY and HIV-1 beside COVID-19 in the report.
- NOT FIXED

### J3-56-04: "The person gets develop's question asked back" holds only for a question with a referring word and no conversation

- Severity: minor. Non-blocking. Accuracy of the stated behaviour, not of the code.
- What: the question is asked back only when `_needs_clarification` (`graph.py:6383` to `6388`) finds a referring word ("each one" in the findings.md question) and no remembered entity. Otherwise, after the skip, nothing binds and Plan runs develop's path for "nothing resolved".
- Reproduction: branch, offline probe, record type sra or assembly, no entity, no memory:
  - "SRA runs of SARS-CoV-2": no question asked back; Plan plans `ncbi_efetch` PubMed search `topic_search_term='sra AND runs AND sars-cov-2'` plus two follow-ups.
  - "SARS-CoV-2 genome assemblies": same, `'sars-cov-2 AND genome AND assemblies'`.
  - The findings.md question: `CLARIFICATION_QUESTION`, no calls.
  - With a remembered gene, see J3-56-01.
- Why it matters: the brief's one-line contract ("when Think misses the organism the person gets develop's existing question asked back") overstates it. The comment at `graph.py:4316` is accurate ("on that question"). The owner should read the outcome as "a literature search, or the question, or the previous subject (J3-56-01)", not "always the question".
- Suggested fix: correct the wording in build_r3.md and the pull request body.
- NOT FIXED

### J3-56-05: A soft hyphen or superscript minus inside the name is not treated as a joiner

- Severity: unsure, minor. Non-blocking.
- What: `_is_name_joiner` (`graph.py:3483` to `3488`) accepts Unicode category Pd and U+2212. The soft hyphen U+00AD (category Cf) and the superscript minus U+207B (category Sm) are not joiners, so "SRA runs of SARS­CoV" and "SRA runs of SARS⁻CoV" still try "SARS[title]", as develop does.
- Reproduction: offline probe, record type sra, no entity: both questions give branch `medgen: ['SRA[title]', 'SARS[title]']`, identical to develop. The other dashes I tried (U+2012, U+2015, U+FE63, U+2E3A, U+30A0, U+2212) were skipped correctly.
- Why it matters: only text pasted from a hyphenated web page carries a soft hyphen inside a word, and then the person sees no dash at all. I am not sure anyone will meet this; filed because the brief asked about the dash set.
- Suggested fix: none required; if wanted, add U+00AD to `_is_name_joiner`.
- NOT FIXED

### J3-56-06: gate03 fails in the worktree today, on the round 3 adversary's untracked scripts, not on this branch

- Severity: minor. Non-blocking for this branch; a warning for whoever commits the adversary's evidence.
- What: `bash .github/gates/gate03_lint.sh` in the worktree exits 1 with 12 errors, all in untracked files another reviewer is writing now: `testing/Developer/reports/2026-10-06_card56/raw/adversary_r3/medgen_live.py` (5), `medgen_titles.py` (2), `probe.py` (5).
- Reproduction: gate03 as briefed, `rc=1`, "Found 12 errors."; `ruff check --extend-exclude testing/Developer/reports/2026-10-06_card56/raw/adversary_r3` gives "All checks passed!", and so does `ruff check` on the two changed files. gate02 passes.
- Why it matters: gate03 lints the whole repository with no path, so committing those scripts as they are would turn CI red.
- Suggested fix: `ruff check --fix` on those scripts before they are committed, or leave them uncommitted.
- NOT FIXED

## Checklist

| Item | Verdict | Evidence |
|---|---|---|
| 1a. Skip only on record types in `ORGANISM_RECORD_DBS` | Pass, probed | `graph.py:4322`; `breadth_plan.py:136` names sra and assembly. Probe: "papers on SARS-CoV-2" with record type none tries and binds SARS exactly as develop. Mutant E (skip on every record type) turns `test_a_paper_question_is_unchanged_from_develop` red |
| 1b. Only tokens that stand solely as a piece of a hyphen-joined name | Pass in code, probed; untested (J3-56-02) | `graph.py:3491` to `3522`. "SARS and SARS-CoV-2 runs in SRA" and "SRA runs of sars-CoV-2 from SARS patients" still try SARS, as develop. Mutant B survives |
| 1c. Whole words such as MODY unaffected | Pass, probed | "SRA runs from MODY patients" and "SRA runs - MODY patients" try MODY on both trees; the spaced dash case is untested (J3-56-02, mutant C survives) |
| 1d. Gene fallback untouched | Pass, read and probed | The diff does not touch `graph.py:4233` to `4251`. "SRA runs of BRCA1-mutant tumours" and "SRA runs of TP53-null cells" still bind the gene on the branch |
| 1e. Unicode dash set | Pass, probed, with an unsure edge | ASCII hyphen, U+2010, U+2011, U+2012, U+2013, U+2015, U+2212, U+2E3A, U+30A0, U+FE63 skipped; U+00AD and U+207B are not (J3-56-05). Mutant A (ASCII only) turns 3 tests red |
| 2. No regression on other shapes | Pass for every shape except the conversation case (J3-56-01) | 109-scenario differential probe, develop's `graph.py` (fcfc6827, `cmp` identical to origin/develop's) against the branch, same fakes: 38 differences, every one an sra or assembly question with no entity and a hyphen-joined token. Identical on record type none in all 31 questions, gene questions, "What causes type-2 diabetes?", tagged-organism, mis-tagged gene ("Illumina") and disease-tagged cases, and on "What SRA runs are there for it?" with memory. Window, accession and isolate shapes: the D3 block is gated on `accession_plan is None and isolate_question is None` (`graph.py:4298` to `4302`), and a window question with an empty extraction would only differ if it also had a joined token and an sra or assembly record type; not probed |
| 3. Parse retry | Pass, probed | `_THINK_RETRY_KEY_LIST` prints `"query_class", "narrative", "entities", "record_type"` (`graph.py:2402`). The repair now repairs "why" beside `record_type` and still refuses "why" beside an unknown key, "why" beside "reason", and an invalid record type ("plasmid", rejected by the schema after repair). No field became required: the schema is unchanged and `record_type` keeps its default; the system prompt already asked for it (`graph.py:2495` to `2500`). Mutant D turns the retry test red |
| 4. Tests | 49 passed; 3 of my 5 mutants caught | New file plus `test_think_retry.py`, `test_think_organisms.py`, `test_think_disease_and_organism.py`: 49 passed. Mutants on a scratch export (never the worktree): A red 3, B green, C green, D red 1, E red 1. `git status` shows no tracked change |
| 5. gate03 | Branch clean; worktree red from another reviewer's files | J3-56-06 |
| 6. Rule 4 | J3-56-01 sits inside this round's own fix (the skip); none sits inside the J-56-04 retry fix | J3-56-01 |
| Merge onto current develop | Clean | `git merge-tree --write-tree origin/develop HEAD` exit 0; develop has not changed `graph.py` since fcfc6827 |

## What I verified by my own probes and what I only read

- Probed: every row above marked probed, the J3-56-01 outcome (think_node then plan_node, both trees), the topic searches in J3-56-04, the retry key list and repair cases, five mutants, gate03, the merge.
- Read only: that the D3 block cannot run for accession and isolate shapes (gates at `graph.py:4298` to `4302`); that no user-visible note tells the person the answer was bound to the earlier gene in J3-56-01 (a grep for `memory_bound` found none in Write; I did not trace Write).
- Not covered: live model runs (none, as briefed); Act and Write; build_r3.md's 38 live runs and its `compare_r3.py` (not re-run, my own differential replaces it); the whole unit suite; whether `resolve_symbol_to_curie("SARS")` resolves live to the renamed human gene SARS1 through the untouched gene fallback (develop's live evidence suggests not).

## Verdict

FAIL, pending the owner. One blocking item, J3-56-01, and it sits inside this round's own fix, so the review rule sends it to the owner rather than into a fix round. Without a remembered subject the change does what the owner asked: no SARS records, the question asked back on the findings.md question, every other shape identical to develop. If the owner accepts J3-56-01 as part of the smallest fix, the rest is non-blocking and the branch would pass.

## Errata to the line numbers above

- J3-56-02, mutant B: the lines changed are `graph.py:3520` to `3522` (the `if not (joined_before or joined_after)` test and the final `return found`), not 3519 to 3520.
- J3-56-02, mutant C: the deleted far-side check is `graph.py:3518`, not 3516.
- Checklist row 2: the D3 gate is `graph.py:4297` to `4303`; the skip itself is `graph.py:4322` and `4326`.
