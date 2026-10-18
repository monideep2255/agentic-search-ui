# Card 126 adversary: the disagree line under an ask floor

One round, dial position 2, on branch `fix/card126-disagree-line` at commit 6a8af489. Findings are appended as they are found. The adversary files and never fixes or closes.

## Findings

### A-126-01: "Sources disagree" now shows over one cited source, when the only disagreeing record is uncited and about a different variant

- Severity: major (reachability unsure, see below)
- What: `triangulate` compares a cited claim against the WHOLE findings pool by field name only, never by variant, and never only against cited records. Card 126's "cited only" guard checks that the discordant claim is cited, not that the record it disagrees with is. So one cited dbSNP record plus an uncited LitVar2 row about a different rs id, in the same field, yields "Sources disagree on at least one claim" under an ask floor. Develop said "Based on 1 source cited, from dbSNP" for the same answer.
- Reproduction: `<scratchpad>/card126_adv/probe1.py`, real `trust_for_claims`, `aggregate([out, "ask"])` and `answer_trust_line`, branch against develop's `trust.py` from `origin/develop`. Cited: `ncbi_dbsnp` rs80357713 `clinical_significance="pathogenic"`. Pool only: `litvar2_lookup` row for rs1799966 `clinical_significance="benign"`.
  ```
  == B cited dbSNP rsX vs UNCITED LitVar2 row for a different variant, ask floor
     trust ncbi_dbsnp-1: tier=high tri=discordant outcome=flag
     outcome=ask
     branch : 'Sources disagree on at least one claim'
     develop: 'Based on 1 source cited, from dbSNP'
  ```
  With no floor, develop already prints the same false line (case B' in the output), so the root is pre-existing; card 126 extends it to every floored answer.
- Why it matters: a reader sees one source in the Sources list and is told sources disagree about it. They cannot find the disagreement, because the other record is not shown and is not about their variant. A false alarm on a pathogenicity claim. The "Confirmed by" path was restricted to cited records for exactly this reason (V-22-01); the disagree path was not.
- Worse than develop for a person: yes, in the floored case.
- Reachability, unsure: a LitVar2 row's representative field is `name` when the match has a name (`core/graph.py` `_pseudo_row` puts `name` first), so the LitVar2 side needs a match with no name; any second tool emitting `clinical_significance` (a model-written Cypher returning it, `ncbi_efetch` with a non-breadth purpose) reaches the same shape.
- NOT FIXED

### A-126-02: two different variants, both cited, with different classifications now read "Sources disagree"

- Severity: major (reachability unsure, as A-126-01)
- What: `triangulate` matches on `field` alone, so a question that brings back variant X as pathogenic from one tool and variant Y as benign from another marks both claims `discordant`. Card 126 turns that into "Sources disagree on at least one claim" on a floored answer, where develop said "Based on 2 sources cited from dbSNP and LitVar2". The two sources do not disagree: they describe two different variants.
- Reproduction: `<scratchpad>/card126_adv/probe1.py` case C. Cited: `ncbi_dbsnp` rs80357713 "pathogenic", `litvar2_lookup` rs1799966 "benign".
  ```
  == C two different variants both cited, ask floor
     trust ncbi_dbsnp-1: tier=high tri=discordant outcome=flag
     trust litvar2_lookup-2: tier=high tri=discordant outcome=flag
     outcome=ask
     branch : 'Sources disagree on at least one claim'
     develop: 'Based on 2 sources cited from dbSNP and LitVar2'
  ```
- Why it matters: a two-variant comparison is exactly the question that also trips the partial-answer floor (two or more target entities, one unaddressed), so this is the floored shape card 126 now reaches. A clinician comparing two variants is told the databases conflict, and may distrust a correct pathogenic call.
- Worse than develop for a person: yes, in the floored case. Unfloored, develop already said it (pre-existing root in `triangulate`).
- NOT FIXED

### A-126-03: one ClinVar record, graph snapshot against live fetch, reads "Sources disagree" over "1 source"

- Severity: minor (unsure whether a reader would call this disagreement)
- What: `_origin_of` takes the origin from the tool name unless the field is `curie`, so a graph `cypher_query` row and a live `ncbi_efetch` row of the SAME ClinVar page are two origins. If the record was reclassified after the snapshot, both claims go `discordant`, and card 126 now shows "Sources disagree on at least one claim" under a floor, while `citation_count` (keyed by `source_page_key`) is 1. Develop said "Based on 1 source cited, from ClinVar".
- Reproduction: `<scratchpad>/card126_adv/probe1.py` case D, `.../clinvar/variation/17661/` "Uncertain significance" (cypher_query) and `.../clinvar/variation/17661` "Pathogenic" (ncbi_efetch).
  ```
  == D one ClinVar record, graph snapshot vs live (reclassified), ask floor
     trust cypher_query-1: tier=high tri=discordant outcome=flag
     trust ncbi_efetch-2: tier=high tri=discordant outcome=flag
     outcome=ask
     branch : 'Sources disagree on at least one claim'
     develop: 'Based on 1 source cited, from ClinVar'
  ```
- Why it matters: "sources disagree" over a single source page is self-contradicting. What happened is that the record changed; the live-wins-for-currency note (`_apply_live_wins_for_currency`) is the honest words for that. Card 22 already ruled a graph row and a live fetch of one record are one database for "Confirmed by"; the disagree path counts them as two.
- Worse than develop for a person: arguably yes (a new self-contradiction), arguably no (it does surface a real change). Filed on purpose.
- NOT FIXED

### A-126-04: "no assertion criteria provided" counts as a contrary verdict, so it now raises "Sources disagree"

- Severity: minor (bucket table is pre-existing; card 126 widens where it shows)
- What: `_BUCKET_BY_VALUE` maps "no assertion criteria provided", a ClinVar review status meaning the submitter gave no criteria, into the `uncertain` bucket. Against "pathogenic" from another tool that is `discordant`, and card 126 now prints "Sources disagree on at least one claim" under a floor. A reader would not call "this submitter gave no criteria" a disagreement with "pathogenic".
- Reproduction: `<scratchpad>/card126_adv/probe1.py` case E.
  ```
  == E pathogenic vs 'no assertion criteria provided', ask floor
     trust ncbi_dbsnp-1: tier=high tri=discordant outcome=flag
     trust ncbi_efetch-2: tier=high tri=discordant outcome=flag
     outcome=ask
     branch : 'Sources disagree on at least one claim'
     develop: 'Based on 2 sources cited from ClinVar and dbSNP'
  ```
- Why it matters: a lying trust signal on a pathogenicity claim. Unsure whether a live value ever reads exactly that string in a `clinical_significance` field.
- Worse than develop for a person: yes in the floored case.
- NOT FIXED

### A-126-05: the builder's case H fixture cannot produce `discordant` through the real code; the test hand-builds the verdict

- Severity: minor (test vacuity, not a user defect by itself)
- What: every new test passes a hand-written `ClaimTrust(..., "discordant", ...)`. Fed through the real `trust_for_claims`, the test's own fixture (two `cypher_query` rows, ClinVar "Pathogenic" and dbSNP "Benign") is one origin, so `triangulate` returns `insufficient` and the line is the "could not be compared" one on both branch and develop. The tests prove the line's string mapping, not that any real answer reaches it.
- Reproduction: `<scratchpad>/card126_adv/probe1.py` case A.
  ```
  == A builder fixture via real triangulate
     trust cypher_query-1: tier=high tri=insufficient outcome=ask
     trust cypher_query-2: tier=high tri=insufficient outcome=ask
     outcome=ask
     branch : 'Based on 2 sources cited from ClinVar and dbSNP; their values could not be compared'
     develop: 'Based on 2 sources cited from ClinVar and dbSNP; their values could not be compared'
  ```
  Also: graph templates return no `clinical_significance` column (`grep clinical_significance tools/cypher_templates.py` is empty), and `ncbi_efetch`'s ClinVar breadth purpose leads with `title`, so the representative field of a ClinVar record is rarely a classification. The shapes that do reach `discordant` are the ones in A-126-01 to A-126-04.
- Why it matters: the card's own acceptance shape ("ClinVar says Pathogenic, dbSNP says Benign") may be rare or unreachable live, while the shapes it does reach are the false ones above. No test runs the real `triangulate` into the new branch.
- NOT FIXED

### A-126-06: a pathogenic against benign contradiction on one ClinVar record still shows no warning at all

- Severity: major (pre-existing, not worse than develop, but the card's promise does not hold for it)
- What: graph ClinVar says "Pathogenic/Likely pathogenic", the live fetch of the same record says "Benign". "Pathogenic/Likely pathogenic" is outside the bucket table, so `triangulate` returns `insufficient` and each claim is already `ask`. The Section 7.2 conflict check (`_apply_conflict_flags_to_claim_trusts`) floors at `flag`, which `aggregate` ranks below `ask`, so it changes nothing. The card 126 branch keys only on `triangulation == "discordant"`, so it never fires. The line reads "Based on 1 source cited, from ClinVar", with no "could not be compared" clause either, because both pages are one database.
- Reproduction: `<scratchpad>/card126_adv/probe2.py`, real `trust_for_claims`, real `core.graph._apply_conflict_flags_to_claim_trusts`, real `answer_trust_line`.
  ```
  == H ClinVar graph 'Pathogenic/Likely pathogenic' vs live 'Benign', same record (floor=False)
     trust cypher_query-1: tier=high tri=insufficient outcome=ask
     trust ncbi_efetch-2: tier=high tri=insufficient outcome=ask
     outcome=ask
     branch : 'Based on 1 source cited, from ClinVar'
     develop: 'Based on 1 source cited, from ClinVar'
  ```
- Why it matters: the most consequential disagreement there is (pathogenic against benign) gets the calmest line on the screen. A confident reading of a contradicted classification.
- Worse than develop for a person: no. Same as develop.
- NOT FIXED

### A-126-07: a Section 7.2 conflict still loses its warning under a floor; card 126 only covers triangulation

- Severity: minor (pre-existing; shows the fix is narrower than "a disagreement under ask says so")
- What: there are two disagreement mechanisms, `triangulate` (sets `triangulation`) and the Section 7.2 graph against live conflict check (sets only `outcome = flag`, never `triangulation`). Card 126 reads `triangulation` only. A conflict on the same record, unfloored, reads "Sources disagree on at least one claim"; add any ask floor and it reads "Based on 1 source cited", the exact inconsistency card 126 set out to remove.
- Reproduction: `<scratchpad>/card126_adv/probe2.py` case L, NCBI Gene page 672, graph `chromosome="17"` against live `chromosome="13"`.
  ```
  == L low-risk field conflict graph vs live, same gene page (floor=False)
     outcome=flag
     branch : 'Sources disagree on at least one claim'
  == L low-risk field conflict graph vs live, same gene page (floor=True)
     outcome=ask
     branch : 'Based on 1 source cited, from NCBI Gene'
  ```
  (Trust rows: both `tier=low tri=insufficient outcome=flag` in both runs.)
- Why it matters: whether a reader is told the sources disagree still depends on an unrelated floor (a failed background search, omitted records) for this mechanism. The builder's report does not mention the conflict path.
- Worse than develop for a person: no. Same as develop.
- NOT FIXED

### A-126-08: a real disagreement spelled the way dbSNP and LitVar2 spell it reads "could not be compared"

- Severity: minor (pre-existing bucket table)
- What: dbSNP and LitVar2 send hyphenated terms ("likely-pathogenic", "uncertain-significance"). `bucket_for` normalises whitespace and case only, so a hyphenated term is outside the table and `triangulate` returns `insufficient`. "likely-pathogenic" against "benign" is a real disagreement; the line says "their values could not be compared".
- Reproduction: `<scratchpad>/card126_adv/probe1.py` case G.
  ```
  == G 'likely-pathogenic' vs 'benign' (real disagreement), ask floor
     trust ncbi_dbsnp-1: tier=high tri=insufficient outcome=ask
     trust litvar2_lookup-2: tier=high tri=insufficient outcome=ask
     outcome=ask
     branch : 'Based on 2 sources cited from dbSNP and LitVar2; their values could not be compared'
  ```
- Why it matters: together with A-126-05 this means the only two-tool shapes that reach `discordant` are single plain words ("pathogenic", "benign"), while the commonest real spellings never do. The new line fires on the rare shape and on the false ones (A-126-01 to 04), and stays silent on the common real one.
- Worse than develop for a person: no.
- NOT FIXED

### A-126-09: the "cited claims only" guard is a no-op in production and guards the wrong side

- Severity: minor
- What: `cited_ids = {claim.finding.citation_id for claim in claims}` is built from the same `grounding.claims` list that `trust_for_claims` built every `ClaimTrust` from (`core/graph.py` line 15000, trusts; line 15615, the line; `grounding` is not reassigned between them, checked with an awk over lines 15000 to 15620 for `grounding =`, `claim_trusts =`). So `trust.citation_id in cited_ids` is always true on the live path; only the hand-built `c-99` unit test exercises it. The property a reader needs, that the record the claim disagrees WITH is cited, is not checked anywhere (A-126-01).
- Reproduction: `awk 'NR>=15000 && NR<=15620 && /grounding *=|claim_trusts *=/' src/system_03_search_agent/core/graph.py` prints only line 15000 (`claim_trusts = trust_for_claims(grounding.claims, ...)`) and line 15038 (the conflict floor, same ids). No `grounding =` reassignment.
- Why it matters: the build report presents "Cited only" as a safety property. It gives no protection against the uncited disagreeing record, which is the case that produces a false alarm.
- Worse than develop for a person: no by itself.
- NOT FIXED

### A-126-10: the terminal client now prints "[answer]" directly above "Sources disagree on at least one claim"

- Severity: minor
- What: the CLI tags a server `ask` as `[answer]` (card 62, `_tag_word`) and a server `flag` as `[flag]`. Before card 126, "Sources disagree" only ever arrived with `flag`. Now the same disagreement prints under `[answer]` when a floor applied and under `[flag]` when not.
- Reproduction: `<scratchpad>/card126_adv/probe3.py`, real `adapters.cli.render.Renderer`, one answer-scope `trust_signal` and one `done` with `trust_line="Sources disagree on at least one claim"`.
  ```
  --- trust_outcome=flag

  [flag]
  Sources disagree on at least one claim · High-risk claim

  --- trust_outcome=ask

  [answer]
  Sources disagree on at least one claim · High-risk claim
  ```
- Why it matters: a terminal user, or a script grepping the tag, reads the floored, MORE cautious answer as the plain `[answer]` state while the floored one has the less alarming tag. The builder's report says the CLI "does not key off the text", true, but the tag beside the text now contradicts it.
- Worse than develop for a person: yes, a new contradictory pairing on the CLI surface (develop never paired `[answer]` with the disagree line).
- NOT FIXED

### A-126-11: on the web the disagree line is muted grey and the info card beside it never explains it

- Severity: minor (pre-existing for `flag`; card 126 puts it on more answers)
- What: `useRunView.ts` line 1018 renders every line not starting with "Confirmed" as kind `plain`, which `AnswerScreen.tsx` colours `inkMuted`. The "Trust signals" info card (`TRUST_LINE_EXPLAINER`, `AnswerScreen.tsx` line 131) explains "Sources cited", "Confirmed", "Based on" and "their values could not be compared", and says nothing about "Sources disagree": not what it means, not which claim, not where to look. The line also replaces the "Based on N sources cited from X and Y" words, so the reader loses the count and the database names on a floored answer.
- Reproduction: read only, `frontend/src/hooks/useRunView.ts` line 1018 `kind: summary.startsWith("Confirmed") ? "good" : "plain"`; `AnswerScreen.tsx` lines 131 to 137 (the explainer text, no "disagree"), lines 2596 to 2602 (muted colour for `plain`).
- Why it matters: the reader is told there is a disagreement in the quietest colour on the line, cannot open anything that says which claim, and the builder's report reasons the explainer "stays true" because it never mentions the line, which is the gap.
- Worse than develop for a person: not worse; less helpful than it could be.
- NOT FIXED

### A-126-12: ClinVar's live classification field is low risk, so a ClinVar pathogenic against benign can never reach the new line

- Severity: major (pre-existing blind spot; not worse than develop; it is the shape a person most needs the card's line for)
- What: `ncbi_efetch` names ClinVar's classification `germline_classification` (`tools/ncbi_efetch.py` line 103, and the `clinvar_summary` breadth fields). `risk_tier_for("germline_classification", "clinvar")` is `low`, because `_HIGH_RISK_FIELD_TOKENS` lists `clinical_significance` but not `germline_classification`. A low-risk claim is never triangulated, so it is never `discordant`, so card 126's condition can never be true for it. `triangulate` also compares on the exact field name, so dbSNP's `clinical_significance` and ClinVar's `germline_classification` are never compared with each other. Card 30's `_CLASSIFICATION_FIELDS` (`synthesis/answer_layout.py` line 395) already treats both names as the classification.
- Reproduction: `<scratchpad>/card126_adv/probe4.py`. Direct: `risk_tier_for` printed `germline_classification 'clinvar' low`, `clinical_significance '' high`, and `somatic_classification`, `oncogenicity_classification`, `clinvar_classification` all `low`. Pipeline, dbSNP rs80357713 "pathogenic" against ClinVar `germline_classification` "Benign", ask floor:
  ```
     trust ncbi_dbsnp-1: tier=high tri=insufficient outcome=ask
     trust ncbi_efetch-2: tier=low tri=insufficient outcome=answer
     line: 'Based on 2 sources cited from ClinVar and dbSNP; their values could not be compared'
  ```
  ClinVar cited alone: `tier=low ... outcome=answer`, line `'Based on 1 source cited, from ClinVar'`, and no "High-risk claim" tag.
- Why it matters: "a claim the risk tier calls low but a person would call high-stakes", exactly. A live ClinVar classification is treated like a gene symbol lookup.
- Worse than develop for a person: no.
- NOT FIXED

### A-126-13: deleting the plain `flag` clause from the edited condition leaves every trust line test green

- Severity: minor (test gap inside this phase's fix)
- What: the edited line is `if trust_outcome == "flag" or any(...discordant...)`. The new `test_plain_flag_is_unchanged` passes a DISCORDANT trust, so the `any(...)` half alone satisfies it. No test pins a `flag` outcome whose trusts are not discordant, which is exactly what the Section 7.2 conflict path produces (A-126-07, case L unfloored: `tri=insufficient outcome=flag`, line "Sources disagree on at least one claim"). A later edit that drops the clause would silently turn every conflict-flagged answer back to "Based on".
- Reproduction: `<scratchpad>/card126_adv/mut.sh` in a detached worktree at 6a8af489, targeted run of `test_trust_line.py`, `test_trust_line_discordant_under_ask.py`, `test_trust_line_names_its_count.py`:
  ```
  ### baseline
  113 passed in 31.03s
  ### M1 drop cited filter
  1 failed, 112 passed   (the hand-built c-99 test)
  ### M2 drop the plain flag clause
  113 passed in 26.44s
  ### M3 discordant to not concordant
  8 failed, 105 passed
  ### M4 all tiers
  1 failed, 112 passed
  ```
- Why it matters: M2 is a surviving mutant on the line card 126 rewrote. The builder's three mutations did not include it.
- Worse than develop for a person: no today; it removes a guard for tomorrow.
- NOT FIXED

### A-126-14: an rs-level dbSNP value against an allele-level record reads as disagreement

- Severity: unsure
- What: dbSNP's `clinical_significance` is per rs id, pooled over every allele; a ClinVar or LitVar2 record can be about one allele. One plain word on each side in different buckets ("benign" for the rs, "pathogenic" for one allele) is `discordant` by the same field-only comparison as A-126-02, and card 126 now shows "Sources disagree on at least one claim" under a floor. A geneticist would say the two records describe different alleles, not that they disagree.
- Reproduction: same mechanism and output as `<scratchpad>/card126_adv/probe1.py` case C (`tri=discordant`, branch "Sources disagree on at least one claim", develop "Based on 2 sources cited from dbSNP and LitVar2"); no separate probe, since `triangulate` reads no allele or variant identity at all (`trust.py` `triangulate`, the `same_field` list filters on `field` and origin only).
- Why it matters: filed on purpose as a possible false alarm; the owner or a domain reader decides whether this counts as disagreement.
- Worse than develop for a person: yes in the floored case, if it is a false alarm.
- NOT FIXED

## Checked and not a finding

- Refuse with a discordant claim still gives no line (`answer_trust_line` returns None first; builder test plus probe outputs never print a line for refuse).
- Card 30's classification note and the new line cannot appear together: the note needs no `clinical_significance` or `germline_classification` finding (`variant_classification_note`), and `discordant` needs one.
- The floor notes (failed search, omitted records, partial answer, structured fallback, cap, writer failed) never quote the trust line's words, so none contradicts "Sources disagree" (`core/graph.py` note builders read).
- Citation id collisions: ids are `{call_id}-{ref_index}` with a call id of about 20 characters against a 64 character clip, so two findings cannot share an id.
- A reopened saved answer, MCP, GraphQL and the JSON renderer pass the stored or sent line through unchanged; only the CLI's tag pairs badly with it (A-126-10).
- Web status strip: `ask` with a trust line reads "Answered" in the warn tone, which is more cautious than `flag`'s good tone, so the floored disagreement is not shown as calmer on the web.
- dbSNP's multi-value significance ("pathogenic, benign") stays `insufficient` and keeps the "could not be compared" clause (probe1 case F), same as develop and verifier3 case I.

## Not done

- No live answer: the deployed develop API returned 401 to an unauthenticated `POST /v1/query`, and the brief allows reads only without sign-in. Reachability of A-126-01 to A-126-04 and A-126-14 on live traffic is therefore argued from the code, not observed.

## Verdict

FAIL against the card's claim "when a cited high-risk claim is discordant, the line reads Sources disagree; nothing else changes", read from the user's chair.

- The words appear where the sources do not disagree (A-126-01, 02, 03, 04, 14), each newly reachable under a floor, which is worse than develop for that reader.
- Real disagreements still read calm (A-126-06, 07, 08, 12), not worse than develop.
- The fix itself carries a surviving mutant (A-126-13) and a guard that never fires live (A-126-09); the tests feed hand-built verdicts the real code does not produce from their own fixture (A-126-05).

Findings A-126-01, 02, 09, 10 and 13 sit inside or directly on this phase's fix (the new condition and its tests).

Verified with my own probes: A-126-01 to 08, 10, 12, 13 (outputs pasted above, scripts in `<scratchpad>/card126_adv/`). Read only: A-126-09 (awk over the caller), A-126-11 (frontend source), A-126-14 (same mechanism as probe case C), and every "Checked and not a finding" bullet except the multi-value one.
