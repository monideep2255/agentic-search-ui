# Card 125 build report: a paper title is a name, never an instruction

Branch `fix/card125-title-cleaning`, cut from origin/develop 535943bc. Builder report for the lead.

## Table of contents

- [Path trace](#path-trace)
- [Design](#design)
- [Tests](#tests)
- [Mutations](#mutations)
- [Title sample](#title-sample)
- [Citation and sentence checks](#citation-and-sentence-checks)
- [Decisions and gaps for the lead](#decisions-and-gaps-for-the-lead)
- [Commit](#commit)
- [Second commit](#second-commit)
- [Third commit](#third-commit)

## Path trace

Every way a PubMed paper title becomes text in the writer prompt:

| Path | Where | Cleaned before |
|---|---|---|
| Live: an EFetch PubMed record is read | `src/system_03_search_agent/tools/ncbi_eutils_actions.py`, `_extract_pubmed_articles`, the `ArticleTitle` read (about line 1257) | Nothing, before this card. This is the one place a live PubMed title is born. |
| Live, planned breadth call (`pubmed_abstracts`) | `core/graph.py`, `_ncbi_efetch_output_to_structured_fields` (about line 8229) copies `record.fields["title"]` into a row | Takes the born value |
| Live, any other planned or model chosen `ncbi_efetch` fetch of `db=pubmed` | same function, no purpose allow list, all fields copied | Takes the born value |
| Row to finding | `synthesis/findings.py`, `build_synth_findings` (about line 497), `SynthFinding(... field_value=...)` at about line 659 | Takes the born value |
| Finding to prompt | `findings.py`, `render_findings_block` and `render_finding_body` (about lines 927 and 989), then `build_synth_messages` (about line 2068, the `FINDINGS:` block) | Takes the born value |
| Graph: a bare PMID paper is named | `synthesis/article_titles.py`, `_fetch_titles` calls `ncbi_eutils_actions.fetch`, which goes through the same `_extract_pubmed_articles` | Now neutralised at birth, and again by `clean_article_title` |
| Graph: the cleaned title replaces the finding | `article_titles.py`, `apply_resolved_article_titles`, called from `core/graph.py` at about lines 8939 and 14223 | `clean_article_title` (existing) |

Tools that carry no PubMed title, checked:

- `cypher_query`: an `Article` row's `fields` are emptied by `core/graph.py` `_sanitized_citeable_row` (about line 7694), so the graph title never travels; only the PMID does.
- `ncbi_efetch` ESummary for `pubmed`: the field allow list (`_SUMMARY_FIELDS_BY_DB["pubmed"]`) has no title.
- PubTator3 (`tools/pubtator_annotate.py`) and LitVar2 (`tools/litvar2_lookup.py`): no title field in their schemas or outputs; only PubMed URLs and PMIDs.
- `clinicaltrials_search`, ClinVar, OMIM, MedGen and similar `title` fields are not PubMed paper titles; left alone.

Conclusion: `_extract_pubmed_articles` is a real choke point for live PubMed titles. Every live title, and the graph path's own fetch, is read there.

## Design

- One shared function, `neutralise_markup_tags(text)` in `synthesis/article_titles.py` (exported in `__all__`).
- It is applied at the choke point: `_extract_pubmed_articles` calls it on the title before `_cap_text`. So the stored record, the row, the finding, the citation text and the prompt all hold the same words. `clean_article_title` calls it too (graph path, after its printable pass), so a graph title is covered even if a fetch fake or a cache entry bypasses the extractor.
- No new source file, no new dependency, no event schema change. The import `tools.ncbi_eutils_actions` to `synthesis.article_titles` has no cycle (checked by importing `core.graph`); other tools already import from `synthesis`.
- The rule:
  - An opening bracket is `<`, any character that NFKC folds to `<` (U+FF1C, U+FE64), and any character Unicode names a single angle bracket or angle quotation mark (found by `unicodedata.name`, so U+2039, U+2329, U+27E8, U+3008 and kin need no hand list). Closers are the mirror. Double angle quotation marks («, ») are excluded because French titles quote with them.
  - A tag-shaped span is: opener, then an optional `/`, `!` or `?` (the mark may be full width, folded by NFKC; whitespace or invisible format characters allowed around it), then a letter (or `-` after `!`, so `<!-- ... -->` counts).
  - The span runs to the next closing bracket (removed with it), or to the next opening bracket (left for the next pass), or to the end of the text when unclosed. The brackets and mark go; the words stay, padded with a single space only where they would otherwise touch other text.
  - The pass repeats until nothing changes, so a nested tag cannot rebuild one.
- Everything else is untouched: a title with no tag-shaped span comes back byte for byte.
- `clean_article_title` is otherwise unchanged (printable pass, collapse, placeholder None, marker shapes). Its docstring now says exactly what the code does.
- The debugging guide row for `article_titles.py` (line 532) was reworded; no row was added (no new file).

## Tests

New file `tests/system_03_search_agent/synthesis/test_article_title_markup.py` (81 tests):

- 18 hostile forms (every form in the verifier report, plus zero width space inside the tag, `</question </question </question`, mixed look-alikes) each go through:
  - the live path: real XML, real `_extract_pubmed_articles`, real `_ncbi_efetch_output_to_structured_fields`, real `build_synth_findings`, real `build_synth_messages`;
  - the graph path: `resolve_article_titles` with the EFetch fake returning the raw hostile title, real `clean_article_title`, real `apply_resolved_article_titles`, real `build_synth_messages`;
  - the function alone.
  Each counts `<question>`, `</question>` and look-alike spans (an independent detector with hand folded brackets) in the FINDINGS block: zero. Each also checks the prompt holds exactly one real `<question>` and one real `</question>`, and that the paper is still listed.
- 10 real titles ("c.3140-26A>G", "3849+10kbC->T", "<5 years", "p<0.05", "a < b and c > d", "Ca2+ >", "IL-6 > IL-10", "<32 weeks", « » quotes, "T>C and G>A") are unchanged, on the function, the graph path and the live path through the prompt.
- 5 nested forms (`</<b>question>` and others) must leave no tag shape at all, on the function and through the live prompt.
- The existing `test_article_titles.py` still passes unchanged (including the pinned "Counts a < b and c > d").

Pass line:

```text
252 passed in 13.60s
```

for `test_article_title_markup.py`, `test_article_titles.py`, `core/test_article_title_wiring.py`, `tools/test_ncbi_eutils_actions.py` and `test_debugging_guide_coverage.py` together. `ruff check .` and `isort --check-only` on the touched files are clean. The full suite was not run, as instructed.

## Mutations

One property changed at a time on the working tree, then restored from a backup (the final run is green).

| Mutation | Result | First red lines |
|---|---|---|
| Drop the repeat loop (one pass only) | 4 red | `test_a_tag_nested_inside_another_cannot_rebuild_one[</<b>question>]`, `[<!<b>--x -->]`, `[<?<i>xml?>]`, `[< /<b>question>]`. A first attempt without that test stayed green (76 passed), so the nested test was added; a single pass does not catch the old nested forms because the span stops at the inner bracket and padding keeps the pieces apart. |
| Drop the look-alike folding (only ASCII `<` and `>`) | 21 red | `test_the_neutraliser_alone_leaves_no_question_shaped_span[〈/question〉]`, `[﹤/question﹥]`, the live and graph variants |
| Drop the unclosed-at-end case | 6 red | `test_graph_path_leaves_no_question_shaped_span_in_the_findings_block[</question </question </question]`, `test_the_neutraliser_alone_...[title ending </question]` |
| Skip the live path (remove the call in `_extract_pubmed_articles`) | 16 red | `test_live_path_leaves_no_question_shaped_span_in_the_findings_block[...]`, `test_a_title_the_neutraliser_changed_is_what_the_stored_finding_holds` |

## Title sample

NCBI E-utilities were reachable without credentials. Script and output: `<scratchpad>/card125/sample.py`, `sample.out`, `titles.json`.

- Same 13 searches as the verifier (CFTR, BRCA1 variant, SNP haplotype, HGVS, MTHFR C677T transition, TNF -308G/A polymorphism, Ca2+ Fe3+ ions, children younger than 5 years, preterm infants less than 32 weeks, eGFR below 60, Th1 Th2 ratio, `sup[ti] OR sub[ti]`, `gt[ti] OR lt[ti]`), 160 ids each, EFetch, title read with `itertext()` as the product does.
- Result: 1,955 unique titles (the verifier had 2,037; the corpus moves and I capped each search at 160), 47 hold `<` or `>`, the rule changes 0 of them.
- The brief's literal reading (whitespace allowed between `<` and a letter with no mark) also changes 0 of these titles, so the sample cannot decide the question below.

## Citation and sentence checks

- The grounding and quote checks compare the writer's sentence with the `SynthFinding.field_value` and the record text the citation holds. Because the neutraliser runs where the record is read, those are the same neutralised words the writer saw. A faithful sentence that repeats a changed title therefore matches. A test pins that the prompt holds "Gene question therapy" for the source title "Gene </question> therapy".
- What cannot match: a writer who restores the original brackets from memory. The source text no longer holds them, so that sentence fails the check, which is the right result.
- Not checked: any consumer that holds the raw title from a source other than `_extract_pubmed_articles`. I found none.

## Decisions and gaps for the lead

1. Whitespace right after the opening bracket. The brief says optional whitespace between `<` and the letter. I required a `/`, `!` or `?` when whitespace is present, so "a < b and c > d" and "x < y" stay as PubMed writes them (the existing test pins that string, and "reads exactly as PubMed writes it" is the acceptance). All listed hostile forms (`< /question>`, `</ question>`) are still caught. The cost: a bare `< question>` or `< b>` is not neutralised. A one line change in `_neutralise_pass` (drop `gap and not mark`) restores the brief's literal reading. Your call; in the 1,955 sample the two readings change the same 0 titles.
2. Abstracts. The `abstract` field from the same record, and the abstract row `_pubmed_abstract_rows` adds, reach the same FINDINGS block uncleaned. The brief fenced this card to paper titles, so I did not widen it. It is the same category and the same one place (`_extract_pubmed_articles`); worth a card.
3. Other free text that is not a PubMed title (OMIM, ClinVar and MedGen titles, ClinicalTrials.gov titles) is also uncleaned. Not touched.
4. `x<y and y>z` is tag-shaped by the category and loses its brackets ("x y and y z"); none appeared in the sample. This is the residual the brief accepted.
5. Not run: the full suite and CI gates other than the touched tests, ruff and isort.

## Commit

See the final message to the lead for the hash.

## Second commit

Lead changes on the same branch, a new commit (no amend). Tests: `test_article_title_markup.py` grew from 81 to 147 tests.

### 1. Abstracts

- `_extract_pubmed_articles` reads exactly two free text fields from a PubMed record: `title` and `abstract`. Both now pass through `neutralise_markup_tags` at that choke point. The abstract is neutralised after its parts are joined, so a tag split across two `AbstractText` parts is seen whole (pinned by a test).
- Hostile forms for abstracts (all of the title forms plus the new ones below) go through the real XML extraction, `_pubmed_abstract_rows`, `build_synth_findings` and `build_synth_messages`: zero question shaped spans in the FINDINGS block, one real `<question>` and one real `</question>`.
- NCBI sample on abstracts (same 13 searches, `<scratchpad>/card125/sample2.py`, `sample2.out`): 1,904 abstracts, 673 contain `<` or `>`, the rule changes 8. Target 0 is not met. Titles: 1,955, 47 with angle brackets, 0 changed. The 8, with the first change of each:

```text
40856760 'recoveries (0.5%< RSD <2%), confirming' -> '(0.5% RSD <2%), confirming'
38068222 'higher (2 < log10(Kd)< 3) than' -> 'higher (2 log10(Kd) < 3) than'
42832849 '(AUD<MC, pcor=.016) and vmDMN-pDMN (AUD>MC, p' -> '(AUD MC, pcor=.016) and vmDMN-pDMN (AUD MC, p'
41505377, 40730036, 41086127, 41569955, 41569950: '<p>Introduction: ...' -> 'p Introduction: ...'
```

  Two causes. Five abstracts carry a literal `<p>` paragraph tag as text, which is a real tag by the category, so its brackets go and a stray "p" stays. Three are comparisons: a single word between two angle brackets ("< RSD <", "< log10(Kd)<") and "AUD<MC ... AUD>" (a no gap letter after the opener with a closer later). The rule cannot tell these from a tag without a new rule (for example a length limit on a closed span, or an allow list of tag names); that is the lead's call.

### 2. Whitespace after the opener

A span with ASCII whitespace right after the opener is a tag when, up to its closer (or the next bracket, or the end), it holds a single word, optionally preceded by `/`, `!` or `?` and followed by whitespace. So `< question>`, `< question >`, `<  question  >` and `< /question>` are neutralised and "a < b and c > d", "x < y and more words > z" stay. Pinned both ways. A consequence of the lead's rule: a title or abstract that ends "x < y" (one word to the end of the text) is tag-shaped and loses its `<`.
Mutation: the single word test made always true. 16 red, for example `test_a_single_word_after_an_ascii_gap_is_a_tag[< question>]`, `[< question >]`, `[<  question  >]` and `test_live_path_neutralises_the_abstract_in_the_findings_block[< question >]`.

### 3. Invisible characters never count as a gap

Only ASCII whitespace is an ordinary gap. Every other space or invisible character after the opener (zero width space, bidi controls, soft hyphen, NBSP, full width space, every other Zs, word joiner, any Cf or Cc) makes the span a tag whatever follows. `<` + U+200B + `question>`, `<` + NBSP + `question>`, `<` + U+3000 + `question>`, plus U+202E and U+00AD forms, are in the hostile forms on the live path, the graph path, the function alone and the abstract path. The test detector also folds those characters, so it cannot be blind to them.
Mutation: invisible characters counted as an ordinary gap. 7 red, for example `test_an_invisible_or_non_ascii_gap_never_makes_a_comparison[\xa0]`, `[　]`, `[ ]`, `[⁠]`.

### 4. Linear time

The repeat loop is gone: `neutralise_markup_tags` is one left to right scan. It reads the whole run of brackets, marks and gaps after an opener, once; a kept opener skips the rest of its run in one step (`safe_until`); a span ends at the next bracket, so no character is read by two spans. Why one scan suffices: every opener inside a run that has a second opener is removed together with the run, so a kept opener is always followed in the output by its own run and a non letter; removing a span cannot put a name next to a kept opener. A 200,000 case random fuzz (alphabet of brackets, marks, gaps, invisible characters, letters) found no output that was not a fixed point and none with a leftover tag shape.
Test: 100,000 character shapes (`<b`*50000, `<`*100000, `</`*50000, `< a `*25000, `<` + U+200B repeated, and a nested mix) all finish in under 1.5 s together, and the nested one under 0.5 s; measured about 0.1 s each.
Mutation: remove the run skip (`safe_until`), which makes `<`*100000 quadratic. The linear test never finished: pytest was killed by a 150 s alarm after the earlier tests passed. That is a hang, not a clean assertion failure.

### Results

```text
318 passed in 11.19s
```

for the markup tests, `test_article_titles.py`, `core/test_article_title_wiring.py`, `tools/test_ncbi_eutils_actions.py` and `test_debugging_guide_coverage.py`, re-run after the last edit. `ruff check .` and `isort --check-only` on the touched files are clean. The debugging guide row for `article_titles.py` now says title and abstract.

## Third commit

Lead changes: a tag is defined by grammar, not by "runs to the next bracket"; the three real comparisons must stay; combining marks are invisible too. Tests: `test_article_title_markup.py` is now 234 tests.

### The grammar

`neutralise_markup_tags` now judges each opener by this grammar, in two linear passes (a right to left pass that judges every opener, a left to right pass that writes the result):

- Opener (any angle look-alike), an optional gap, an optional `/`, `!` or `?`, a name (letter, then letters, digits, `-`, `_`, `:`, `.`), zero or more attributes (a name, optionally `=` and a quoted value or an unquoted value with no space and no bracket), an optional `/`, then a closer or the end of the text. Brackets, mark and closer go; name and attributes stay.
- A gap is any space or invisible character. Only ASCII whitespace can be a comparison gap, and after one no attributes are allowed: just the name, an optional `/`, and the closer or the end. So `< question>` and `< question >` are tags and "a < b and c > d" is not (name `b`, then `and` is not allowed).
- Comments: `<!--` is dropped alone and its text is scanned on, so a tag inside a comment is still found. `<?name ...?>` and `<!name ...>` are tags.
- A span never ends at another opener. It is a tag only if that opener is itself a tag (judged first, right to left); then both go. This is what stops nesting from rebuilding a tag, in linear time: the inner tag is judged before the outer one, so the outer one is removed with it. An opener followed, after a gap or mark, by an opener that is a tag also goes (`<<b>>`).
- Combining marks and variation selectors (categories Mn, Me, Mc) are treated like Cf and Cc everywhere: never a comparison gap, skipped before the name, and they do not end a name or an attribute.

Two choices beyond the lead's grammar, for the lead to confirm:

1. After `/`, `!` or `?` the body runs to the closer whatever it holds (as an HTML reader takes `</question junk,>`), and such a span is a tag even when an opener interrupts it (`</question <5 years` becomes `question <5 years`). Without this, `</question ,>` would pass the attribute grammar's "no". These forms are never real notation; none appeared in the samples.
2. A no gap, no mark opener followed by a failing character stays as written (`<MC, pcor`), which is what keeps the real comparisons; so `<question ,>` survives. That is the lead's grammar working as written.

### Checks

- Fixed point: 1.8 million random strings (brackets, marks, gaps, invisible characters, quotes, `=`, look-alikes) were neutralised twice; the second pass changed nothing in any case. The fuzz found three gaps while I wrote this (an empty attribute value, a `/` and a gap form each followed by a tag) and they are closed. A 20,000 case version is in the test file.
- Hostile forms, all four paths (live title, graph title, live abstract, function alone): the earlier forms plus `<` + U+FE0F + `question>`, `<` + U+034F + `question>`, `<` + U+E0100 + `question>`, `<` + U+0301 + `/question>`, `</` + U+FE0F + `question>`, a gap form with attributes, `<question a=b c='d'>`, `<question a="x" />`, `</question junk,>`, `<question<b>>`, a comment holding `</question>`, `<?question x?>` and `<!question x>`. Zero question shaped spans in the FINDINGS block; one real `<question>` and one real `</question>` in the prompt.
- Real notation that must stay, added to the real title and real abstract tests (live path through the prompt): "(0.5%< RSD <2%)", "(2 < log10(Kd)< 3)" and "(AUD<MC, pcor=.016) and (AUD>MC, pcor=.02)", the three that changed before.
- Timing: the 100,000 character test now also covers `<a b=`, `<a x="`, `< <` and `<!--` repeated; each shape takes about 0.1 to 0.25 s, the test asserts under 1.5 s together.

### NCBI sample, same searches (`<scratchpad>/card125/sample3.out`)

- Titles: 1,955, 47 with angle brackets, 0 changed.
- Abstracts: 1,904, 673 with angle brackets, 5 changed. Every one is a literal paragraph tag and nothing else in the abstract changed (the full diff of each is a `<`, a `>`, a `</` and a `>`):

```text
41505377 '<p>Introduction: FIREFLEYE next 3 years o' -> 'p Introduction: FIREFLEYE next 3 years o'
40730036 '<p>Introduction: This study aimed to comp' -> 'p Introduction: This study aimed to comp'
41086127 '<p>Objective: The primary goal of this st' -> 'p Objective: The primary goal of this st'
41569955 '<p>Introduction: Preterm infants are comm' -> 'p Introduction: Preterm infants are comm'
41569950 '<p>Introduction: Multi-morbidity is a kno' -> 'p Introduction: Multi-morbidity is a kno'
```

  The three comparisons (40856760, 38068222, 42832849) are no longer changed.

### Mutations

| Property mutated | Result |
|---|---|
| A span may end at any opener (the interrupted span is always a tag) | 1 red: `test_a_span_interrupted_by_an_opener_is_judged_by_that_opener` |
| Drop Mn, Me and Mc from the invisible set | 7 red, for example `test_a_combining_mark_is_never_a_comparison_gap_or_a_name_end[\U000e0100]`, `[́]`, `[⃝]`, `[ः]` |
| An ASCII gap allows attributes | 7 red, for example `test_several_words_after_an_ascii_gap_are_a_comparison[a < b and c > d]` and the timing test |

### Results

```text
405 passed in 24.12s
```

for the markup tests, `test_article_titles.py`, `core/test_article_title_wiring.py`, `tools/test_ncbi_eutils_actions.py` and `test_debugging_guide_coverage.py`. `ruff check .` and `isort --check-only` on the touched files are clean.
