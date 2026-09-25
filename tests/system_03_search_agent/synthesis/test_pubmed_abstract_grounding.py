"""UI fix 11.22: a PubMed abstract's own retrieved text becomes citeable.

`core/breadth_plan.py`'s module docstring records that a prior design tried
to pick one "representative" sentence out of an abstract with a regex rule,
and that it was held back by product-owner decision (2026-09-14) because a
regex sentence rule accepted meaning-reversing fragments and could not see
a refutation sitting in the very next sentence. This file is not that
design. `core/graph.py`'s `_pubmed_abstract_rows` selects nothing and
asserts nothing about which sentence of an abstract matters: it hands the
WHOLE retrieved abstract text to `synthesis/findings.py` as one finding's
`field_value`, verbatim, exactly as `ncbi_eutils_actions._extract_pubmed_
articles` already parsed and capped it. Whether any clause of Synth's
narrative becomes a citeable quote is decided entirely by `synthesis/
grounding.py`'s existing, unmodified, deterministic `ground_claim`: a
clause grounds only when it equals, or is contained in, that exact string.
No similarity scoring is introduced anywhere in this file or in the
production code it exercises.

What this file proves, each with a populate-check so a negative assertion
cannot pass on nothing:

1. A clause Synth writes that is a verbatim excerpt of the retrieved
   abstract grounds, survives `run_grounding_pass`, and the finding it
   grounds against carries the source PMID's own `source_url`.
2. A clause that is NOT drawn from any retrieved finding (a fabricated
   claim, even one naming the real gene and citing a real marker) is
   stripped, never accepted, by the same unmodified grounding pass. This
   is the arm that matters most: it is the difference between quoting
   evidence and inventing a plausible-sounding sentence.
3. The rendered findings block stays within `MAX_FINDINGS_BLOCK_CHARS`
   even when a long abstract is admitted alongside other findings, and a
   finding that does not fit is left off rather than truncated mid-value.
4. A PubMed record with NO usable abstract still produces exactly the
   title-only finding it always has: `_pubmed_abstract_rows` only ever
   ADDS a row, never changes what the title path already builds.

Depends on:
    - system_03_search_agent.core.graph (_ncbi_efetch_output_to_structured_
      fields, _pubmed_abstract_rows, _pick_representative_field,
      _layer2_citation_for_synth_finding)
    - system_03_search_agent.synthesis.findings (build_synth_findings,
      render_findings_block, MAX_FINDINGS_BLOCK_CHARS)
    - system_03_search_agent.synthesis.grounding (run_grounding_pass)
    - system_03_search_agent.harness.coordinator_worker (Finding)

Writes:
    - Nothing.
"""

from __future__ import annotations

from typing import Any

from system_03_search_agent.core import graph as graph_module
from system_03_search_agent.harness.coordinator_worker import Finding
from system_03_search_agent.synthesis.findings import (
    MAX_FIELD_VALUE_CHARS,
    MAX_FINDINGS_BLOCK_CHARS,
    build_synth_findings,
    render_findings_block,
)
from system_03_search_agent.synthesis.grounding import run_grounding_pass
from system_03_search_agent.tools.ncbi_efetch_schemas import NcbiEfetchOutput, NcbiEfetchRecord

_ABSTRACT = (
    "Background: BRCA1 encodes a tumor suppressor. Methods: we sequenced "
    "312 tumors. Results: pathogenic BRCA1 variants abolish homologous "
    "recombination in this cohort. Conclusion: carriers should be offered "
    "enhanced surveillance."
)
_PMID = "30000003"
_URL = f"https://pubmed.ncbi.nlm.nih.gov/{_PMID}/"


def _abstract_output(*, with_abstract: bool = True) -> NcbiEfetchOutput:
    fields: dict[str, Any] = {"title": f"BRCA1 paper {_PMID}"}
    if with_abstract:
        fields["abstract"] = _ABSTRACT
    return NcbiEfetchOutput(
        status="ok",
        action="fetch",
        records=[
            NcbiEfetchRecord(id=_PMID, db="pubmed", fields=fields, source_url=_URL),
        ],
        record_count=1,
        total_available=1,
        truncated=False,
    )


def _findings_for(output: NcbiEfetchOutput) -> list[Finding]:
    structured = graph_module._ncbi_efetch_output_to_structured_fields(
        output, purpose="pubmed_abstracts"
    )
    return [
        Finding(
            call_id="ne-abs-1",
            tool="ncbi_efetch",
            layer="layer_2_api",
            source="structured_pass_through",
            structured_fields=structured,
            extracted_entities=None,
            normalized_ids=None,
            evidence_summary=None,
        )
    ]


# ---------------------------------------------------------------------------
# Arm 1: a verbatim excerpt grounds and cites the source paper.
# ---------------------------------------------------------------------------


def test_a_verbatim_abstract_excerpt_grounds_and_cites_its_own_paper() -> None:
    findings = _findings_for(_abstract_output())
    synth_findings, capped = build_synth_findings(findings, graph_module._pick_representative_field)
    assert not capped, "populate-check: nothing should have been capped for one record"

    fields_seen = {sf.field for sf in synth_findings}
    assert "title" in fields_seen, "populate-check: the pre-existing title finding must still exist"
    assert "abstract" in fields_seen, "the abstract must reach synthesis as its own finding"

    abstract_finding = next(sf for sf in synth_findings if sf.field == "abstract")
    assert abstract_finding.source_url == _URL

    excerpt = "pathogenic BRCA1 variants abolish homologous recombination in this cohort"
    assert excerpt in _ABSTRACT, "populate-check: the excerpt really is verbatim in the fixture"
    # No unmarked prefix text: an unmarked segment that asserts something of
    # its own (rather than framing) would be stripped as its own clause and,
    # since a kept clause follows it, would drop the WHOLE sentence under
    # the "dropped from the middle" rule (`run_grounding_pass`,
    # DECISIONS.md 2026-09-01). This test is about whether the MARKED
    # excerpt itself grounds, so the sentence carries nothing else.
    narrative = f"{excerpt} [{abstract_finding.ref_index}]."

    result = run_grounding_pass(narrative, synth_findings, question="What is known about BRCA1?")
    assert result.grounded, "a verbatim excerpt of the retrieved abstract must ground"
    assert result.stripped_count == 0, result
    assert any(excerpt in claim.claim_text for claim in result.claims), result.claims

    citation = graph_module._layer2_citation_for_synth_finding(
        abstract_finding,
        findings,
        {"ne-abs-1": _abstract_output()},
        "ne-abs-1-cit",
        1,
        f"{excerpt} [1]",
    )
    assert citation is not None, "the grounded abstract claim must be citeable"
    assert citation.source_url == _URL
    assert citation.source_id == _PMID
    assert excerpt in _ABSTRACT and excerpt in citation.claim_text


# ---------------------------------------------------------------------------
# Arm 2: a sentence NOT drawn from any retrieved finding is rejected.
# ---------------------------------------------------------------------------


def test_a_sentence_absent_from_every_retrieved_abstract_is_stripped_not_accepted() -> None:
    findings = _findings_for(_abstract_output())
    synth_findings, _ = build_synth_findings(findings, graph_module._pick_representative_field)
    abstract_finding = next(sf for sf in synth_findings if sf.field == "abstract")

    fabricated = "BRCA1 variants respond well to pembrolizumab combination therapy"
    assert fabricated not in _ABSTRACT, "populate-check: the fabrication really is absent"
    for finding in synth_findings:
        assert fabricated not in finding.field_value, "populate-check: absent from every finding"

    narrative = f"{fabricated} [{abstract_finding.ref_index}]."
    result = run_grounding_pass(narrative, synth_findings, question="What is known about BRCA1?")

    assert not result.grounded, "a fabricated sentence must not survive as evidence"
    assert result.stripped_count == 1, result
    assert result.claims == [], result.claims
    assert fabricated not in result.narrative


def test_a_true_but_uncited_paraphrase_of_the_abstract_is_also_stripped() -> None:
    """Not just a fabrication: a paraphrase in different WORDS is stripped
    too, because Section 8.2 matches text, never meaning. This is the same
    "no similarity scoring" boundary the goal contract names: only a
    verbatim excerpt (or its exact substring/superstring) may ground.
    """
    findings = _findings_for(_abstract_output())
    synth_findings, _ = build_synth_findings(findings, graph_module._pick_representative_field)
    abstract_finding = next(sf for sf in synth_findings if sf.field == "abstract")

    paraphrase = "the mutation destroys the cell's ability to repair its own DNA"
    assert paraphrase not in _ABSTRACT

    narrative = f"{paraphrase} [{abstract_finding.ref_index}]."
    result = run_grounding_pass(narrative, synth_findings, question="What is known about BRCA1?")

    assert not result.grounded
    assert result.stripped_count == 1, result


# ---------------------------------------------------------------------------
# Arm 3: the rendered block stays within its character budget.
# ---------------------------------------------------------------------------


def test_a_raw_abstract_longer_than_the_field_cap_is_clipped_before_a_finding_exists() -> None:
    """`synthesis/findings.py`'s `MAX_FIELD_VALUE_CHARS` clip runs on EVERY
    finding regardless of source (`build_synth_findings`'s `_clip(field_
    value, MAX_FIELD_VALUE_CHARS)`), so this is defense in depth rather
    than a new cap this ticket invents: even a raw abstract longer than
    `ncbi_eutils_actions._cap_text` would ever let through (constructed
    directly here, bypassing that fetch-time cap entirely, to prove THIS
    layer holds on its own) cannot reach a `SynthFinding.field_value`
    uncapped.
    """
    raw_abstract = "BRCA1 loss impairs homologous recombination. " * 200  # well over 2000 chars
    assert len(raw_abstract) > MAX_FIELD_VALUE_CHARS, "populate-check: the raw text is oversized"

    output = NcbiEfetchOutput(
        status="ok",
        action="fetch",
        records=[
            NcbiEfetchRecord(
                id=_PMID, db="pubmed",
                fields={"title": f"BRCA1 paper {_PMID}", "abstract": raw_abstract},
                source_url=_URL,
            )
        ],
        record_count=1, total_available=1, truncated=False,
    )
    findings = [
        Finding(
            call_id="ne-abs-1", tool="ncbi_efetch", layer="layer_2_api",
            source="structured_pass_through",
            structured_fields=graph_module._ncbi_efetch_output_to_structured_fields(
                output, purpose="pubmed_abstracts"
            ),
            extracted_entities=None, normalized_ids=None, evidence_summary=None,
        )
    ]
    synth_findings, _ = build_synth_findings(findings, graph_module._pick_representative_field)
    abstract_finding = next(sf for sf in synth_findings if sf.field == "abstract")
    assert len(abstract_finding.field_value) <= MAX_FIELD_VALUE_CHARS, (
        f"abstract finding carried {len(abstract_finding.field_value)} chars, "
        f"over the {MAX_FIELD_VALUE_CHARS} bound"
    )
    assert abstract_finding.field_value == raw_abstract[:MAX_FIELD_VALUE_CHARS]


def test_the_findings_block_truncates_rather_than_overflow_when_abstracts_push_it_over() -> None:
    """Forces `render_findings_block`'s own budget to actually bind: five
    near-2000-char abstract findings alone sum to roughly 10KB, under the
    12,000-char block cap, so a test that stops there never exercises the
    truncation branch at all (measured directly: reverting `render_
    findings_block`'s break to a no-op left that narrower version of this
    test green). Padding the finding set with additional same-shape
    findings past the 12,000-char block cap is what actually exercises it.
    """
    long_abstract = ("Background: BRCA1 loss impairs repair. " * 80)[:1999]
    pubmed_records = [
        NcbiEfetchRecord(
            id=str(30000000 + n), db="pubmed",
            fields={"title": f"paper {n}", "abstract": long_abstract},
            source_url=f"https://pubmed.ncbi.nlm.nih.gov/{30000000 + n}/",
        )
        for n in range(5)
    ]
    output = NcbiEfetchOutput(
        status="ok", action="fetch", records=pubmed_records,
        record_count=len(pubmed_records), total_available=len(pubmed_records), truncated=False,
    )
    findings = [
        Finding(
            call_id="ne-abs-many", tool="ncbi_efetch", layer="layer_2_api",
            source="structured_pass_through",
            structured_fields=graph_module._ncbi_efetch_output_to_structured_fields(
                output, purpose="pubmed_abstracts"
            ),
            extracted_entities=None, normalized_ids=None, evidence_summary=None,
        )
    ]
    # A second, independent source of equally bulky findings (a graph-shaped
    # Finding, the same shape `_finding()` in test_breadth_wiring.py already
    # uses), so the COMBINED set, as a real multi-source answer would
    # assemble it, is what pushes the block past MAX_FINDINGS_BLOCK_CHARS, not the
    # pubmed abstracts alone.
    filler_rows = [
        {
            "curie": f"MedGen:C{n}", "node_or_edge_type": "Disease",
            "fields": {"name": ("padding disease description " * 60)[:1999]},
            "source_url": f"https://www.ncbi.nlm.nih.gov/medgen/C{n}",
        }
        for n in range(10)
    ]
    findings.append(
        Finding(
            call_id="cy-filler", tool="cypher_query", layer="layer_1_graph",
            source="structured_pass_through",
            structured_fields={"status": "ok", "row_count": len(filler_rows), "rows": filler_rows},
            extracted_entities=None, normalized_ids=None, evidence_summary=None,
        )
    )

    synth_findings, _capped = build_synth_findings(
        findings, graph_module._pick_representative_field, max_findings=25
    )
    assert any(sf.field == "abstract" for sf in synth_findings), (
        "populate-check: at least one long abstract finding must be present"
    )
    naive_total = sum(len(f"[{sf.ref_index}] " + sf.field_value) for sf in synth_findings)
    assert naive_total > MAX_FINDINGS_BLOCK_CHARS, (
        f"populate-check: the untruncated total ({naive_total} chars) must actually "
        f"exceed the {MAX_FINDINGS_BLOCK_CHARS} cap for this test to exercise truncation"
    )

    block = render_findings_block(synth_findings)
    assert len(block) <= MAX_FINDINGS_BLOCK_CHARS, (
        f"rendered block ({len(block)} chars) exceeded the {MAX_FINDINGS_BLOCK_CHARS} cap"
    )
    assert len(block) < naive_total, "the block must actually have been cut down, not just measured"
    # Whatever DID make it through the truncation is not itself corrupted:
    # `render_findings_block` breaks BEFORE adding a finding that would
    # overflow, so every line present is a complete, unbroken finding line.
    for line in block.splitlines():
        assert line.startswith("["), line


# ---------------------------------------------------------------------------
# Arm 4: a record with no abstract renders exactly as it always has.
# ---------------------------------------------------------------------------


def test_a_record_with_no_abstract_still_yields_only_the_title_finding() -> None:
    findings = _findings_for(_abstract_output(with_abstract=False))
    synth_findings, capped = build_synth_findings(findings, graph_module._pick_representative_field)
    assert not capped

    assert len(synth_findings) == 1, "populate-check: exactly one finding, no phantom second row"
    only = synth_findings[0]
    assert only.field == "title"
    assert only.field_value == f"BRCA1 paper {_PMID}"
    assert only.source_url == _URL


# ---------------------------------------------------------------------------
# Arm 5: `ground_claim` itself is exact, and nothing may loosen it.
# ---------------------------------------------------------------------------


def test_ground_claim_rejects_a_word_overlapping_claim_that_is_not_a_substring() -> None:
    """Added 2026-09-20 after mutation testing found this file over-claiming.

    The arms above assert that a fabricated or paraphrased sentence does not
    survive `run_grounding_pass`, and this file's docstring explains that
    outcome by `ground_claim`'s exactness. MEASURED, AND THAT EXPLANATION WAS
    WRONG: splicing a word-overlap fallback into `ground_claim` (`overlap >= 2`
    alongside the real equality/containment test) left every one of those arms
    green, and left all 308 tests under `tests/system_03_search_agent/
    synthesis/` green. The fabrication is stripped by a DIFFERENT gate in
    `run_grounding_pass`, `claim_introduces_no_new_content`, which catches the
    invented word "pembrolizumab" regardless of what `ground_claim` returned.

    So the defence was real and the stated mechanism was not, which is the
    safety-by-proxy shape this repository has shipped as a critical before
    (build phase 4.3, twice). This arm pins the mechanism directly, at the
    function, with no other gate able to stand in for it:
    `.claude/rules/production-standards.md` requires a citation-grounding
    check to decide accept or reject "by deterministic rule (exact or
    substring match after normalization), never by a fuzzy similarity
    threshold, because a fuzzy accept silently passes a hallucinated quote",
    and until this arm existed nothing in the suite enforced it.
    """
    field_value = "pathogenic BRCA1 variants abolish homologous recombination in this cohort"
    overlapping = "pathogenic BRCA1 variants restore homologous recombination in every cohort"

    shared = set(overlapping.lower().split()) & set(field_value.lower().split())
    assert len(shared) >= 4, (
        f"populate-check: the two strings must genuinely share words for this "
        f"arm to distinguish exactness from similarity, shared={sorted(shared)}"
    )
    assert overlapping not in field_value and field_value not in overlapping, (
        "populate-check: neither string may contain the other, or exactness "
        "and similarity would agree here and this arm would prove nothing"
    )

    from system_03_search_agent.synthesis.grounding import ground_claim

    assert not ground_claim(overlapping, field_value), (
        "ground_claim accepted a claim that merely shares words with the "
        "finding. Section 8.2 step 5 is equality or containment after "
        "normalization, with no similarity fallback and no partial credit: a "
        "fuzzy accept here silently passes a hallucinated quote, and this "
        "example reverses the finding's meaning while sharing most of its "
        "words."
    )
    assert ground_claim(field_value, field_value), (
        "populate-check: an exact match must still ground, or this arm would "
        "pass on a ground_claim that rejects everything."
    )


def _prompt_finding(ref: int, field: str, value: str, url: str, entity_type: str) -> Any:
    from system_03_search_agent.synthesis.findings import SynthFinding

    return SynthFinding(
        ref_index=ref,
        citation_id=f"call-{ref}",
        layer="layer_2_api",
        tool="ncbi_efetch",
        field=field,
        field_value=value,
        source_url=url,
        entity_type=entity_type,
    )


def test_a_thirty_finding_prompt_with_long_abstracts_reaches_the_model_whole() -> None:
    """F-8.1-A08 (fix-and-verify round): the prompt slice is 30 findings
    (`core/graph.py`'s `_MAX_FINDINGS_FOR_MODEL_PROMPT`, the product owner's
    decision of 2026-09-25), and the rendered block must not silently cut it.

    The shape is the longest one the live path can put in a prompt: the
    breadth plan fetches at most `PUBMED_RESULT_CAP` (5) papers per
    question, so 5 abstracts, each at the 2,000-character field cap, plus a
    Gene ESummary summary at the same cap, beside 24 short rows (graph
    records, paper titles, ClinVar rows). At the old 12,000 characters the
    block stopped before the last of them; at `MAX_FINDINGS_BLOCK_CHARS`
    every one of the 30 is in the text the model reads, which is what "your
    30-source choice actually takes effect" requires.
    """
    from system_03_search_agent.synthesis.findings import build_synth_messages

    long_text = ("Results: the cohort showed a consistent association. " * 60)[
        :MAX_FIELD_VALUE_CHARS
    ]
    prompt: list[Any] = []
    for n in range(10):
        prompt.append(
            _prompt_finding(
                len(prompt) + 1,
                "name",
                f"Disease number {n}",
                f"https://www.ncbi.nlm.nih.gov/medgen/{100 + n}",
                "Disease",
            )
        )
    prompt.append(
        _prompt_finding(
            len(prompt) + 1, "summary", long_text, "https://www.ncbi.nlm.nih.gov/gene/672", "gene"
        )
    )
    for n in range(5):
        url = f"https://pubmed.ncbi.nlm.nih.gov/{3000 + n}/"
        prompt.append(
            _prompt_finding(
                len(prompt) + 1, "title", f"A cohort study of BRCA1 carriers {n}", url, "pubmed"
            )
        )
        prompt.append(_prompt_finding(len(prompt) + 1, "abstract", long_text, url, "pubmed"))
    while len(prompt) < 30:
        n = len(prompt)
        prompt.append(
            _prompt_finding(
                n + 1,
                "title",
                f"ClinVar variant record {n}",
                f"https://www.ncbi.nlm.nih.gov/clinvar/variation/{5000 + n}/",
                "clinvar",
            )
        )
    assert len(prompt) == 30
    long_values = sum(1 for f in prompt if len(f.field_value) >= 1900)
    assert long_values == 6, "populate-check: five abstracts and one summary at the cap"

    old_cap_lines = render_findings_block(prompt, 12_000).count("\n") + 1
    assert old_cap_lines < 30, (
        f"populate-check: this shape must be cut at the old 12,000 characters "
        f"({old_cap_lines} of 30 rendered), or it proves nothing about the raise"
    )

    messages = build_synth_messages("What research papers discuss BRCA1?", prompt)
    user_content = messages[-1]["content"]
    shown = [n for n in range(1, 31) if f"\n[{n}] " in f"\n{user_content}"]
    assert len(shown) == 30, f"only {len(shown)} of 30 prompt findings reached the model"
    assert len(render_findings_block(prompt)) <= MAX_FINDINGS_BLOCK_CHARS


def test_block_cap_is_the_fix_round_value() -> None:
    """F-8.1-A08: pinned so a later edit that lowers it is a visible change."""
    assert MAX_FINDINGS_BLOCK_CHARS == 18_000
