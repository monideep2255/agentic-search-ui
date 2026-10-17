# Card 37 slice A2 adversary report

Pull request #264, branch `fix/card37-writer-given-the-gene`, commit `e146bb8b` on develop `ec30edb4`. Worktrees: `<worktrees>/card37a2-adv` (detached at `e146bb8b`) and `<worktrees>/card37a2-adv-dev` (develop, for comparison). Probes in `<scratchpad>/card37a2_adv/`. Written as each finding is established.

## Table of contents

- [Findings](#findings)
- [Local probes](#local-probes)
- [Live runs](#live-runs)
- [Verdict](#verdict)

## Findings

### A-37-01, major: a gene attaches to the wrong rs id and ships as a cited sentence

Worse than develop: yes. On a two-rs-id question the gate licenses any rs id the question names beside any gene companion, so a swapped or wrong gene sentence passes, is cited, and its claim reads `answer`. Develop has no gene finding, so no such sentence can pass there; develop's own cross-record case on the significance field is stripped.

Evidence, `<scratchpad>/card37a2_adv/gate.py` and `gate2.py`, question `What are rs334 and rs6025?`, findings from the real dbSNP shaping (`[1]` rs334 clinical_significance, `[2]` rs334 gene HBB, `[3]` rs6025 functional_consequence, `[4]` rs6025 gene F5), `run_grounding_pass(..., question=q)` then `trust_for_claims`:

```
branch:  PASS ['answer'] | rs6025 is in the HBB gene [2]. -> 'rs6025 is in the HBB gene [1].'
branch:  PASS ['answer'] | rs334 is in the F5 gene [4]. -> 'rs334 is in the F5 gene [1].'
branch:  PASS ['answer'] | Both rs334 and rs6025 are in the HBB gene [2].
branch:  PASS ['F5', 'HBB'] | rs334 is in F5 [4]. rs6025 is in HBB [2]. -> 'rs334 is in F5 [1]. rs6025 is in HBB [2].'
branch:  strip [] | rs6025 is pathogenic [1].          (develop: strip as well)
develop: strip on every gene sentence (no gene finding exists)
```

Through `write_node` (`<scratchpad>/card37a2_adv/probe_a2.py`, faked writer, network blocked), scenarios `two_one_call`, `two_calls`, `two_calls_rev`, Researcher, web: the page shows `claim: rs6025 is in the HBB gene [3].` and `claim: rs334 is in the F5 gene [3].` under the opening sentence, with a citation chip that links to the other variant's dbSNP page. The answer level line stays "Based on 2 sources cited, not yet confirmed" only because rs334's high-risk significance row is in the listing.

Cause: the companion's only content words are the gene symbol and the field name `gene`; `claim_introduces_no_new_content` (`synthesis/grounding.py:456`) lets every other content word come from the question, and both rs ids are in the question. Nothing ties the sentence's rs id to the record the marker cites. A swapped pair is an ordinary writer slip on a two-variant question, and a confident wrong record is the failure the product ranks worst.

### A-37-02, major: an rs id with no significance list moves from "not yet confirmed" to a clean trust line while its condition half is unanswered

Worse than develop: yes, for the case the brief names. For rs334 itself it does not happen (below), but for every dbSNP record without a `clinical_significance` value (rs6025 live today: its list is withheld, `verifier2_A1.md`, V-37-01; any rs id whose record carries only a consequence or only its id), a writer that writes only the gene sentence turns develop's structured fallback (floored at `ask`) into a written answer at `answer`.

Evidence, `<scratchpad>/card37a2_adv/probe_b.py`, writer reply "rs6025 is in the F5 gene [2]." (develop has no `[2]` gene line, so the same reply grounds nothing):

```
rs6025_cond|researcher|g6025|web_ui      outcome ask -> answer | line "Based on 1 source cited, not yet confirmed" -> "Based on 1 source cited"
rs6025_cond|plain_language|g6025|web_ui  outcome ask -> answer | same line change
rs6025_cond|researcher|g6025|cli and mcp outcome ask -> answer | same line change
rs6025_litvar|...|g6025 (dbSNP plus LitVar2)  ask -> answer | "Based on 2 sources cited, not yet confirmed" -> "Based on 2 sources cited"
rs_neither|...|g999 (no significance, no consequence)  ask -> answer
```

Question `What is rs6025 and what condition is it associated with?`: the page answers only "rs6025 is in the F5 gene", names no condition, drops the "no written summary could be checked" note, and the trust line reads as fully supported. The builder's own test asserts this move (`test_only_the_gene_sentence_surviving_still_answers_and_the_most_restrictive_governs`: "on its own the verdict is `answer` instead of the fallback's refusal"); the diagnosis named it as A2's risk (risk table, row A2) and asked for live G-024 before and after, which was not run. Develop already reaches `answer` on rs6025 when the writer's prose grounds on the consequence line (`echo` pages: `answer` on both trees), so the branch adds a new route to a clean line rather than creating the first one; it is still a trust line that says more than an answer to half the question bears, and the lead's decision says nothing else may change.

For rs334 the line does not move: on all 432 pages of `probe_a2.py` (14 scenarios, 12 writer replies, Researcher and Plain language, web, command line and MCP) no page changes outcome or trust line; the listing's high-risk significance claim is merged into the claims and governs (`rs334|researcher|gene_only|web_ui`: claims `('...-1-1', 'ask', 'high'), ('...-1-2', 'answer', 'low')`, answer `ask`, "Based on 1 source cited, not yet confirmed").

### A-37-03, minor: a gene sentence can carry an unlicensed quantifier or presuppose a condition

Worse than develop: newly reachable on rs id questions; the gate class (stop words and question words license anything) is develop's own. Evidence, `gate.py`, question 23, branch:

```
PASS ['answer'] | rs334 is the only variant in the HBB gene [2].                       (false)
PASS ['answer'] | The rs334 variant associated with this condition is in HBB [2].     (presupposes an unnamed condition)
PASS ['answer'] | The condition associated with rs334 is in the HBB gene [2].
strip           | rs334 in HBB causes sickle cell disease [2].   | rs334 is in HBB, so it is associated with sickle cell disease [2].
strip           | rs334 is a pathogenic variant in the HBB gene [2].   | rs334 is in HBB, a protective gene [2].   | rs334 is not in the HBB gene [2].
trimmed         | rs334 is in the HBB gene [2] and is associated with sickle cell disease. -> 'rs334 is in the HBB gene [1].'
```

So the gene never becomes a named condition claim, and every causal or significance word is stripped. For rs334 the answer level line stays "not yet confirmed" (A-37-02's last paragraph).

### A-37-04, minor: the companion takes one of the writer's 30 prompt slots

Worse than develop: the writer sees one record fewer; the page does not change. `probe_a2.py`, `prompt30_334_then_40` (rs334 then 40 trials): develop's last prompt line `['30', 'Clinical trial name: A sickle cell trial 29']`, branch `['30', 'Clinical trial name: A sickle cell trial 28']`. Listing, citations (41) and trust line identical on the `none` reply. At the display cap of 100 nothing changes (`cap_334_then_99`, `cap_99_then_334`, `cap_334_then_120`: 100 citations, same rows, same line on both trees; the companion is not emitted).

### A-37-05, minor: an echoing writer puts the field label on the page

Worse than develop: only with a writer that copies its prompt lines, which no live run did. `rs334|researcher|echo` and `multi_gene|plain_language|echo`: the branch shows `claim: Variant record gene: HBB [2].` and `claim: Variant record gene: HBB, HBD [2].` as prose; develop drops its one echoed line as a restatement of the listed row. The companion is never listed, so its echo is never a restatement.

### Not findings, recorded as evidence

- A variant in several genes: the companion value is `HBB, HBD` (`core/graph.py:5101` joins with ", "). Every natural sentence I tried is stripped (`gate.py`, `multi`: five sentences, all `strip`), so the companion has no effect there, and nothing worse shows.
- An intergenic variant (`genes` empty): no companion, pages identical to develop (`intergenic`, 12 replies).
- The citation: `_layer3_citation_for_synth_finding` on the gene finding gives `dbsnp gene asserted`, the significance finding keeps `dbsnp clinical_significance hedged` (`cit.py`). Live, the gene chip is `C 2 dbsnp gene asserted .../snp/rs334`. The count line stays "Based on 1 source cited" with three chips on one page.
- Command line and MCP: no crash on any of 512 pages; their diffs match the web pages'.
- The RS1 control has no dbSNP row, so its findings are byte identical by construction; live it answered at `ask` with the structured fallback (writer variance; the A1 verifier's run of the same question gave `flag`).
- Tests: `pytest -q tests/system_03_search_agent/synthesis/test_gene_companion_finding.py tests/system_03_search_agent/core/test_layer_handoff.py`: `36 passed in 11.59s`.

## Local probes

All in `<scratchpad>/card37a2_adv/`, run on both trees with `PYTHONPATH=src`:

| Probe | What it does | Result |
|---|---|---|
| `probe_a2.py` | `write_node` with a faked writer and the real dbSNP shaping, network blocked, 14 scenarios (rs334, with LitVar2 on its page and on its own, several genes, intergenic, significance only, two rs ids in one call and in two calls in both orders, display cap 100 three ways, prompt slice 30, graph genes plus rs334) times 12 writer replies, Researcher and Plain language, web, command line and MCP: 432 pages per tree | No crash. 92 pages differ, all in written claims and chips; no page changes outcome or trust line |
| `probe_b.py` | the same for rs ids with no significance list (rs6025 shape, a record with only an rs id), 80 pages | 24 pages move from `ask` "not yet confirmed" to `answer` with a clean line (A-37-02) |
| `gate.py`, `gate2.py` | `run_grounding_pass` and `trust_for_claims` on hostile sentences | A-37-01, A-37-03 |
| `cit.py` | citation builder on the companion | `dbsnp`, field `gene`, asserted |

## Live runs

`<scratchpad>/card37a2_adv/live.py` through `core.run.run_streaming()`, web surface, develop's settings (classifier provider as develop, guard and plan models as develop, per query cap 0.25), session ids `card37a2-adv-br-*` and `card37a2-adv-dev-*`. Six runs on the branch tree as briefed, five on develop for comparison. Spend: branch 0.0562 USD, develop 0.0200 USD, total 0.0762 USD.

| Tree | Question | Depth | Time | Outcome and line | Written answer (reading order) | Chips |
|---|---|---|---|---|---|---|
| Branch | Query 23 | Researcher | 12.79 s | ask, "Based on 1 source cited, not yet confirmed" | "The variant rs334 is linked to gene HBB [2], and its literature variant name is c.20A>T [3]." "Found 1 literature variant record for rs334: c.20A>T [3]." Table: rs334's significance row [1] | 1 dbsnp clinical_significance hedged; 2 dbsnp gene asserted; 3 litvar2 name hedged; all `snp/rs334` |
| Branch | Query 23 | Researcher | 12.40 s | ask, same line | "Found 1 literature variant record for rs334: c.20A>T [2]." "The literature variant name is c.20A>T [2]." Table [1] | 1 dbsnp significance hedged; 2 litvar2 name hedged |
| Branch | Query 23 | Researcher | 9.82 s | ask, same line | "Found 1 literature variant record for rs334: c.20A>T [3]." Heading "Gene and Variant Identity". "The variant is associated with the HBB gene [2]." "In the literature, rs334 is identified by the variant name c.20A>T [3]." Table [1] | 1 significance hedged; 2 dbsnp gene asserted; 3 litvar2 hedged |
| Branch | Query 23 | Plain language | 10.79 s | ask, same line | "I found 1 genetic variant related to rs334 [1]." List [1]. Note "no written summary could be checked". Medical advice note | 1 dbsnp significance hedged |
| Branch | What are rs334 and rs6025? | Researcher | 8.62 s | ask, "Based on 2 sources cited, not yet confirmed" | Structured fallback: "Found 2 variant record records for rs334 and rs6025: ... [1] and coding_sequence_variant, missense_variant [2]." Table [1], [2]. Note | 1 rs334 significance hedged; 2 rs6025 consequence asserted |
| Branch | What does the RS1 gene do? | Researcher | 8.17 s | ask, "Based on 18 sources cited, not yet confirmed" | Structured fallback, 19 rows (gene, papers, ClinVar, OMIM, trials) | 19, unchanged kinds |
| Develop | Query 23 | Researcher | 15.18 s | ask, "Based on 1 source cited, not yet confirmed" | "Found 1 literature variant record for rs334: c.20A>T [2]." "A literature variant name for this variant is c.20A>T [2]." Table [1] | 1 significance hedged; 2 litvar2 hedged |
| Develop | Query 23 | Researcher | 9.51 s | ask, same line | "Found 1 ... c.20A>T [2]." Heading "Retrieved Variant Records". "The literature variant name c.20A>T was returned in the search results [2]." Table [1] | same two |
| Develop | Query 23 | Plain language | 9.24 s | ask, same line | as the branch's Plain language run | 1 |
| Develop | What are rs334 and rs6025? | Researcher | 10.67 s | ask, "Based on 2 sources cited, not yet confirmed" | as the branch's run | 2 |
| Develop | What is rs6025 and what condition is it associated with? | Researcher | 10.37 s | ask, "Based on 1 source cited, not yet confirmed" | Structured fallback: "Found 1 variant record record for rs6025: coding_sequence_variant, missense_variant [1]." Table [1]. Note | 1 dbsnp consequence asserted |

What the live runs show:

- The card works as intended on query 23: the writer used the gene in 2 of 3 Researcher runs, cited to rs334's dbSNP record, and the line stayed "not yet confirmed" every time. No run named a condition or turned the gene into one.
- Plain language and the two-rs-id question fell back to the list on both trees, so the live runs did not exercise A-37-01; the offline gate did.
- The last develop row is A-37-02's baseline: rs6025's record has no significance list live, so develop answers "not yet confirmed". The branch counterpart was not run (the brief caps branch runs at six); the offline probe shows the branch reaches a clean line whenever the writer's only surviving sentence is "rs6025 is in the F5 gene", which is what it wrote for rs334 in two of three runs.
- Time: no new call; the spread (branch 8.2 to 12.8 s, develop 9.2 to 15.2 s) is model variance.

## Verdict

Two findings are worse than develop for a person: a wrong gene attached to the other rs id on a two-variant question (A-37-01), and a clean trust line on half-answered rs id questions whose record has no significance list (A-37-02). Both sit in `build_synth_findings`'s new companion and look fixable inside the card's fence in one round by closing when the companion is emitted (for example, only when the admitted set holds exactly one `Variant record` row, and only when that row also carries the high-risk `clinical_significance` finding that keeps the line honest); those conditions are untested suggestions, and the lead or builder must re-run `probe_b.py` and `gate2.py` on any fix. A residual remains even then: a question naming two rs ids where only one record came back. A-37-03 to A-37-05 are minor.

VERDICT: FIX FIRST
