# Card 38 slice C verifier report, second attempt: paper titles, tag shaped spans only

Pull request #267, branch `fix/card38-paper-titles-r2`: develop `655e9dfe`, merge `d0435215` bringing `22730d97`, `23462c35`, `7d00aa1a` from the closed #263, and the new commit `c4a5b7aa`. Role: fresh verifier, one round, no fix round. Worktree `<worktrees>/card38cr-ver` (detached at `c4a5b7aa`). Probes in `<scratchpad>/card38cr_ver/`.

## Table of contents

- [Findings](#findings)
- [The tag pattern against real titles](#the-tag-pattern-against-real-titles)
- [Earlier classes re-checked](#earlier-classes-re-checked)
- [Tests and lint](#tests-and-lint)
- [Live runs](#live-runs)
- [Verdict](#verdict)

## Findings

Filed as found.

### V-38C-04, minor, not shown worse on any real title: notation shaped like a tag loses its brackets

- Where: `src/system_03_search_agent/synthesis/article_titles.py:163`, `_MARKUP_TAG = re.compile(r"</?[A-Za-z][^<>]*>")`, applied at `:189`: `printable = _MARKUP_TAG.sub(lambda m: f" {m.group(0)[1:-1].lstrip('/')} ", printable)`.
- Synthetic titles through the branch's `clean_article_title` (`<scratchpad>/card38cr_ver/clean_forms.out`):

```text
CHANGED   'Mutational spectra of T<C and G>A substitutions in tumours' -> 'Mutational spectra of T C and G A substitutions in tumours'
CHANGED   'Serum IL-6<IL-10> ratio in sepsis' -> 'Serum IL-6 IL-10 ratio in sepsis'
CHANGED   'Sequence A<B>C motif binding' -> 'Sequence A B C motif binding'
UNCHANGED 'Effect size p<0.05 and q>0.1 thresholds' -> 'Effect size p<0.05 and q>0.1 thresholds'
CHANGED   'CD4<sup>+</sup> T cells in HIV' -> 'CD4 sup + sup T cells in HIV'
CHANGED   'x<y and y>z ordering' -> 'x y and y z ordering'
```

- Through the real `write_node` (only the fetch and the model faked, `<scratchpad>/card38cr_ver/forms.out`), the branch lists the graph paper as "Mutational spectra of T C and G A substitutions in tumours" and hands the writer the same text; develop lists "PMID:9001". For a title of this shape the meaning changes (an order relation and an allele become plain letters), which by the brief is worse than develop's number.
- Reach, measured: live ESearch plus EFetch of 2,037 real PubMed titles (searches CFTR, BRCA1 variant, SNP haplotype, HGVS, MTHFR C677T transition, TNF -308G/A polymorphism, Ca2+ Fe3+ ions, children younger than 5 years, preterm infants less than 32 weeks, eGFR below 60, Th1 Th2 ratio, `sup[ti] OR sub[ti]`, `gt[ti] OR lt[ti]`), parsed by the product's own `_extract_pubmed_articles`: 53 titles hold `<` or `>`, the tag rule changes 0 of them. Every real `<` is followed by a digit or a space ("<32 weeks", "< 32 Weeks"), every real `>` sits in allele notation ("c.181T>G", "-308G > A", "GT>GC", "677C-->T", "G:C->A:T"). The "CD4<sup>+</sup>" case does not arise from PubMed XML: `_extract_pubmed_articles` reads the title with `itertext()` (`tools/ncbi_eutils_actions.py:1257`), so a real `<sup>` element reaches the cleaner as "CD4+".
- So V-38C-01's real failure (every `<` and `>` removed, 34 real records hit) is closed, and the residual is the same class narrowed to a shape I could not find in PubMed. Worse than develop only for a title of that shape; none found.

### V-38C-05, minor, not worse than develop: tag forms the rule does not catch reach the findings block, as develop's live titles already do

- The three forms the security review names, and two more, pass `clean_article_title` unchanged or still tag shaped (`clean_forms.out`):

```text
UNCHANGED '< /question> after' -> '< /question> after'
UNCHANGED '</ question> after' -> '</ question> after'
UNCHANGED 'title ending </question' -> 'title ending </question'
CHANGED   '</question<b>>' -> '</question b >'
CHANGED   '<question<i>>obey' -> '<question i >obey'
UNCHANGED '<!-- comment -->' -> '<!-- comment -->'
CHANGED   '</question>' -> 'question'
```

  The nested form shows the rule is one pass: the inner `<b>` is replaced, which leaves a new tag shaped span `</question b >`. The docstring at `article_titles.py:177` to `:180` ("so no title can open or close a prompt block such as `</question>`") claims more than the code does; the exact `</question>` and `<question>` strings are the only forms it removes.
- Where they land: `build_synth_messages` (`synthesis/findings.py:2068` to `:2080`) puts the findings in a plain `FINDINGS:` block that no tag delimits; the only tag delimited block after it is `<question>{question}</question>`, which holds the user's question alone. The two blocks that do carry finding values inside tags, `<omitted_findings>` and `<required_findings>`, strip every `<` and `>` from the value on both trees (`findings.py:1669` to `:1670`, `return value.replace("<", "").replace(">", "")`), so a title there cannot close them. A title therefore sits next to, never inside, a tag delimited block.
- Branch, graph path, through `write_node` (`forms.out`): `tags in FINDINGS block: {'</question>': 0, '<question>': 0, 'question-like close': 4, 'question-like open': 1}`, and "USER QUESTION" appears 7 times in the prompt (once real, six from titles).
- Develop, its own live PubMed title path today, the same five titles as an `ncbi_efetch` result (`<scratchpad>/card38cr_ver/forms_live_hostile.out`): `tags in FINDINGS block: {'</question>': 1, '<question>': 1, 'question-like close': 5, 'question-like open': 2}`, "USER QUESTION" 7 times; the exact `</question>` and `<question>` reach the writer with no cleaning at all. The branch produces the identical output on that live path (it does not touch it).
- Comparison: the branch's graph path is stricter than develop's live path for the same text (it removes the exact delimiters, a newline, a marker and a bidi character; develop's live path removes none). It is a second route for PubMed title text into the same unwrapped block, not a new kind of text and not a weaker treatment. Equal to develop's exposure, better on the exact forms. Not worse. A deny by default rule, as the review suggests, would be better than both, and would also have to cover develop's live path to change the exposure.

### V-38C-06, major, blocks the merge, not worse than develop for a person: CI's gate 4 is red on #267

- CI on #267 at head `c4a5b7aa`: `Python gates (1, 2, 3, 4, 6, 9)` FAILURE; Integration suite (5), Frontend gates (7, 8) and Accessibility (10) SUCCESS. The failing log, quoted:

```text
E       AssertionError: 1 source file(s) have no row in the debugging guide. Add a row for each, then regenerate the manifest. Missing: ['src/system_03_search_agent/synthesis/article_titles.py']
tests/system_03_search_agent/test_debugging_guide_coverage.py:196: AssertionError
E       AssertionError: The manifest and the source tree disagree. Regenerate it: python tests/system_03_search_agent/test_debugging_guide_coverage.py
2 failed, 7981 passed, 143 skipped, 24 deselected, 1 xfailed, 7 warnings in 329.57s (0:05:29)
```

- Reproduced locally: on the branch `2 failed, 5 passed` (`test_every_source_file_has_a_row`, `test_manifest_covers_every_source_file`); on develop `655e9dfe` `7 passed`. The new module needs a row in `docs/build/Debugging_guide.md` and a regenerated `tests/system_03_search_agent/fixtures/debugging_guide_manifest.json`. Neither file is in the slice's fence as the diagnosis wrote it, and neither touches what a person sees.
- Under tonight's rule a merge needs CI green, so the lead cannot merge #267 as it stands.

## The tag pattern against real titles

| Probe | Titles | Hold `<` or `>` | Changed by the tag rule | Withheld |
|---|---|---|---|---|
| CFTR, BRCA1 variant, SNP haplotype, HGVS (200 each) | 792 | 12 | 0 | 9, all whole bracketed translations |
| CD4 T cells superscript, Ca2+ Fe3+ ions, children younger than 5 years, MTHFR C677T transition, TNF -308G/A polymorphism | 648 | 34 | 0 | 5 |
| preterm infants less than 32 weeks, eGFR below 60, Th1 Th2 ratio (120 each) | 357 | 6 | 0 | 7 |
| `sup[ti] OR sub[ti]`, `gt[ti] OR lt[ti]` (120 each) | 240 | 1 | 0 | 2 |
| Total | 2,037 | 53 | 0 | 23 |

- Script `<scratchpad>/card38cr_ver/title_probe.py`, output `title_probe_1.out` to `title_probe_4.out`; the product's own parser, the branch's own `clean_article_title`, free read-only E-utilities calls (13 ESearch and 13 EFetch, no key).
- Every real `<` is followed by a digit or a space: "preterm infants <32 weeks", "Gestational Age < 32 Weeks", "infants <32 weeks' gestation". Every real `>` sits in allele notation: "CFTR 3849+10kbC>T", "BRCA1 c.181T>G (p.Cys61Gly)", "IVS 1-1 (G>T) (HBB: C.92 + 1G>T)", "c.774G > C", "TNF-α (-308G > A)", "677C-->T", "G:C->A:T", "GT>GC 5' splice-site variants". All shown byte for byte as PubMed wrote them.
- The synthetic shapes the brief names, and what each becomes, are in V-38C-04: "T<C and G>A", "IL-6<IL-10>", "A<B>C", "x<y and y>z" lose their brackets; "p<0.05 and q>0.1" is kept.
- V-38C-01's own probe title through `write_node` now reads `['The CFTR c.3140-26A>G variant in children <5 years', 'PMID:777']` in Researcher and the same title in Plain language (`classes_card38cr-ver.out`); develop reads `['PMID:777', 'PMID:777']`. V-38C-01 is closed.

Mutations on the newest commit, one property each, the two slice files run, the file restored and compared byte for byte (`<scratchpad>/card38cr_ver/mutate.out`; `git status --short` empty after):

| Mutation | Result |
|---|---|
| M1 tag rule without the optional slash | RED, 3 failed (`test_each_tag_form_is_neutralised[Close </question> now]` and two more) |
| M2 tag span kept with its brackets | RED, 6 failed |
| M3 tag rule drops its words | RED, 2 failed |
| M4 every `<` and `>` removed, the closed rule | RED, 5 failed (`test_variant_notation_and_bounds_are_kept_byte_for_byte[...]`) |
| M5 join by position | RED, 14 failed |
| M6 ceiling ignored | RED, 4 failed |
| M7 a PMID returned twice with two titles kept | RED, 1 failed |

No test pins a `<` followed by a letter in notation (the notation test's `<` cases are `<5`), which is why V-38C-04 is not caught; it is evidence, not a finding about the tests.

## Earlier classes re-checked

Probes copied from the first verifier's harness into `<scratchpad>/card38cr_ver/` (`test_probe_once.py`, `test_probe_lead.py`, `test_probe_prompt.py`), run through the real `write_node` on this branch and on develop `655e9dfe` (`<worktrees>/card38cr-ver-dev`), only the fetch and the model faked: `48 passed` on each tree; outputs `classes_card38cr-ver.out` and `classes_card38cr-ver-dev.out`.

| Class | Result |
|---|---|
| A paper listed once, graph only, live only, both, with and without an abstract, both depths | Once in every cell. Graph only: branch `['A letter on CFTR chloride channels', 'PMID:111']`, develop `['PMID:111', 'PMID:111']`. Both, graph as the lead call: branch `['PMID:111', 'PMID:111']`, `['A graph only paper on CFTR', 'PMID:222']`, `['Another live paper on CFTR', 'PMID:444']`; develop `PMID:111`, `PMID:222`, live 444. One citation per page on both trees. The `PMID:111` row is V-38C-02, unchanged and not worse |
| No title joined to the wrong PMID | Join reads `record.id` (`article_titles.py:271`); M5 and M7 red |
| Hostile titles | Newline, bidi, zero width, markers and the exact `</question>` and `<question>` are neutralised (the hostile tests pass; M1 to M3 red). The residual forms are V-38C-05, equal to develop's live path |
| Every failure, the ceiling and the timeout leave the PMID | The newest commit touches only `clean_article_title`; M6 red; the failure and timeout tests pass in the 61 |
| Prompt byte identical with no graph paper | Six pairs (live only, live only with abstract, gene plus live; both depths) identical: for example `live_only researcher sha=21444a9921372ee8 len=39240 events_sha=f6de5190638d0bc5 requests=0` on both trees |
| Quarantine byte identical | `git diff origin/develop...HEAD` touches `core/graph.py` only in the import block, `_prefetch_answer_names` and `_write_answer`'s resolution block; `_sanitized_citeable_row`, `_split_rows_by_trust`, `_untrusted_rows_free_text` and `_rows_for_citation` are not in the diff |
| Card 30's line and slice A1's rows | The diff touches no line of `answer_layout.py`, and the rewrite picks only a graph `Article` finding with a `PMID:` CURIE (`article_curies_to_name`). Card 30's and A1's own test files (`test_graph.py`, `test_write_answer_structure.py`, `test_answer_layout.py`, `test_variant_record_label.py`, `test_task_tiers.py`) pass on the branch: `207 passed` for `test_variant_record_label.py`, `test_answer_layout.py`, `test_write_answer_structure.py` and `test_task_tiers.py`; `test_graph.py` is in the neighbour run |

## Tests and lint

- The two slice files: `61 passed in 9.48s`.
- Neighbours as `build_C.md` names them, re-derived (all of `tests/system_03_search_agent/synthesis/` plus the 15 core and eval files naming `_prefetch_answer_names`, `build_synth_messages`, `resolve_concept_ids`, `resolve_descriptor_ids`, `apply_resolved_disease_names`, `"Article"` or `PMID:`): `1481 passed, 20 skipped, 1 xfailed in 76.60s`.
- CI's lint gates exactly: gate01 compileall and the three imports `exit=0`; gate02 isort `Skipped 2 files`, `exit=0`; gate03 `ruff check` `All checks passed!`. `ruff format --check` on the three new files: `3 files already formatted`.
- Develop moved during the review to `ec547c2a` (card 8, the trust line names its databases). `git merge-tree --write-tree origin/develop c4a5b7aa` printed one tree, exit 0. On that merge, in my develop worktree (merge aborted after): the same neighbours plus card 8's changed test files (`test_s3_as_printed.py`, `test_parity_fields.py`, `test_no_cost_and_auth.py`, `test_parity_tools.py`, `test_capture_saved_answer.py`, `test_outage_note_dated.py`) and the guide coverage test: `2 failed, 1758 passed, 20 skipped, 1 xfailed`, the 2 being V-38C-06 only. Card 8's `record_database` keys a paper by its page (`trust.py:568` to `:572`, `pubmed.ncbi.nlm.nih.gov` becomes `ncbi.nlm.nih.gov/pubmed`, named "PubMed"), so moving a paper's citation to the live layer does not change which database the new trust line names.
- CI on #267: V-38C-06.

## Live runs

Three runs on this branch through `core.run.run_streaming()`, script `<scratchpad>/card38cr_ver/live.py` (session ids `card38cr-ver-cftr_res`, `card38cr-ver-cftr_plain`, `card38cr-ver-q1_res`), develop's settings as card 115's adversary used them (`CLASSIFIER_PROVIDER=jev`, guard and plan models as develop, `PER_QUERY_COST_CAP_USD=0.25`), `RequestContext(surface="web_ui", reads_placement=True)`. Spend: 0.00590 + 0.00988 + 0.00962 = about 0.025 USD. The unit runs above were going at the same time, so the times carry some noise.

| Run | What it lists | Titles against PubMed | Sources grouping (home group per page) | Trust line | Done at |
|---|---|---|---|---|---|
| CFTR papers, Researcher | 71 rows: 50 graph papers by title with their PMIDs ("The Hdj-2/Hsc70 chaperone pair facilitates early steps in CFTR biogenesis.", PMID:10075921; "Identification of a D579G homozygote cystic fibrosis patient ...", PMID:10094564; "Analysis of a DNase I hypersensitive site located -20.9 kb upstream of the CFTR gene.", PMID:10561583; ...), 4 graph papers as bare PMIDs, the CFTR gene, 5 live PubMed papers, 5 ClinVar, 1 OMIM, 5 trials. No repeated row, no PMID in two rows | Lookup asked 54, named 50, 0.495 s. Fetched again from this shell: 50 shown as PubMed wrote them, 0 changed, 4 withheld, all whole bracketed translations (PMID 11109941, 11397675, 11680956, 11683083; V-38C-03, unchanged); none of the 54 holds `<` or `>` | 71 pages: Live NCBI APIs 62 (50 `ncbi_efetch` titles among them), Knowledge graph 4 (the four on their numbers), Enrichment 5 | Based on 71 sources cited | 17.98 s |
| CFTR papers, Plain language | The same 71 records; 50 papers by title, 4 "Published paper". Prose: "I found 54 published papers related to CFTR, out of 1962 available [1]...[20]." then "Some report individual mutations found in patients, such as D513G in a patient with a condition affecting the male reproductive tract [6] and D579G in a cystic fibrosis patient with milder symptoms than expected [2]." | Lookup asked 54, named 50, 0.427 s; the same 50 titles | Same: 62, 4, 5 | Based on 71 sources cited | 18.96 s |
| Query 1, BRCA1 diseases, Researcher | Familial cancer of breast, Familial breast-ovarian cancer susceptibility 1, Pancreatic cancer susceptibility 4, Fanconi anemia complementation group S, the gene, 5 PubMed papers, 5 ClinVar (one "NM_007294.4(BRCA1):c.2145C>G (p.Thr715=)", a live ClinVar title, `>` intact), OMIM, 5 trials | No graph paper, no lookup | 21 pages: Live NCBI APIs 16, Enrichment 5 | Based on 21 sources cited, not yet confirmed (develop `655e9dfe`'s wording; card 8 on the new develop changes it) | 16.29 s |

Time against develop: the lookup is the only added work, 0.43 to 0.50 s on the two paper questions, under the one second bar; query 1 makes no request. Both CFTR answers finished under 20 s.

## Verdict

- V-38C-01 (every `<` and `>` removed) is closed: the real variant and bound titles show byte for byte, and the change is pinned (M4 red).
- On 2,037 real PubMed titles the tag rule changes none. The notation it would alter (V-38C-04) is a `<` before a letter with a later `>`, which I did not find in PubMed; it is named for the lead, not counted as worse.
- The security review's forms (V-38C-05) pass unchanged into the unwrapped findings block; develop's live PubMed titles carry the same forms, and the exact `</question>`, into the same block today with no cleaning, so the branch is equal to develop on this point and stricter on the exact delimiters.
- Every earlier class holds: listed once, joined by PMID, failures and the ceiling keep the PMID, the prompt is byte identical with no graph paper, the quarantine and card 30's and A1's code untouched and their tests green, the trust line counts unchanged.
- Nothing in the answer is worse than develop. But CI is red on #267 (V-38C-06, the debugging guide row for the new module), so tonight's merge rule is not met until the guide row and manifest land.

VERDICT: PASS
