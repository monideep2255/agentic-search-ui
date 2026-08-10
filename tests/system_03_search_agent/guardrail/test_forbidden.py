"""`guardrail.forbidden`: Section 10.5's forbidden query types.

No model, no network, same as `prefilter`. The tests are organised around
the module's own two-factor design: what needs BOTH a verb and a store
object before it refuses, what a bare pattern match refuses on its own, and
the read-only guarantee this module is the first, weakest layer of.
"""

from __future__ import annotations

import pytest

from system_03_search_agent.guardrail.forbidden import (
    _VERDICT_PATTERNS,
    screen,
    seeks_verdict,
    seeks_write,
)

# ---------------------------------------------------------------------------
# The structural guarantee: screen() can refuse or abstain, never admit.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "",
        "     ",
        "Which diseases are associated with BRCA1?",
        "add a node for gene X to the graph",
        "Is this patient likely to relapse?",
        "a" * 2000,
    ],
)
def test_screen_never_returns_an_admitting_verdict(text: str) -> None:
    """The load-bearing property of the whole module.

    Section 10.5 runs after Guard-tier classification clears. If it could
    admit, it would be short-circuiting a decision the classifier already
    made rather than adding a backstop on top of it. `None` means "neither
    forbidden check matched", not "admitted".
    """
    verdict = screen(text)
    assert verdict is None or verdict.admitted is False


# ---------------------------------------------------------------------------
# The two-factor write rule: verb alone is not enough, object alone is not
# enough, both together is a refusal.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "add a node for gene X to the graph",
        "update the BRCA1 record",
        "delete these rows from the database",
        "please remove this edge from the knowledge graph",
        "can you create a new entry in the table",
    ],
)
def test_verb_and_store_object_together_is_a_write_request(text: str) -> None:
    """Both factors present. This is the case the rule exists to catch."""
    assert seeks_write(text) is True, f"should have been flagged as a write: {text!r}"


@pytest.mark.parametrize(
    "text",
    [
        "Which pathogenic variants in DMD are whole-exon deletions?",
        "what genes are deleted in this syndrome",
        "which exons are removed in this transcript",
    ],
)
def test_write_verb_with_no_store_object_is_not_a_write_request(text: str) -> None:
    """The critical case the two-factor rule was built to avoid refusing.

    Each question here carries a write verb ("deletions", "deleted",
    "removed") describing biology, not an instruction to the data store.
    The module docstring names the first of these directly as the
    admit-arm case pinned in the phase 3.0 premise gate. A one-factor rule
    refuses all three; this rule must not.
    """
    assert seeks_write(text) is False, f"false positive on a biology question: {text!r}"


@pytest.mark.parametrize(
    "text",
    [
        "how many records mention BRCA1",
        "what is in the graph for TP53",
    ],
)
def test_store_object_with_no_write_verb_is_not_a_write_request(text: str) -> None:
    """A data-store noun with no verb attached is just a question about it."""
    assert seeks_write(text) is False, f"false positive on a read question: {text!r}"


@pytest.mark.parametrize(
    "text",
    [
        "What is BRCA1?",
        "Which diseases are associated with BRCA1?",
        "",
        "     ",
    ],
)
def test_neither_verb_nor_store_object_is_not_a_write_request(text: str) -> None:
    assert seeks_write(text) is False, f"false positive with neither factor: {text!r}"


# ---------------------------------------------------------------------------
# Verdict-seeking: one match against _VERDICT_PATTERNS is enough.
# ---------------------------------------------------------------------------


def test_every_verdict_pattern_is_covered_by_a_test_case() -> None:
    """Guards the parametrize list below against silently going stale.

    If a pattern is added to `_VERDICT_PATTERNS` without a matching case
    added here, this assertion catches the drift instead of the coverage
    quietly shrinking.
    """
    assert len(_VERDICT_PATTERNS) == 15, (
        "the number of verdict patterns changed; update the parametrized "
        "cases in this file to match, one text per pattern"
    )


@pytest.mark.parametrize(
    "text,pattern_index",
    [
        ("Can you tell me whether I have this mutation", 0),
        ("what treatment should I take for this", 1),
        ("diagnosis for me based on these symptoms", 2),
        ("is this patient likely to relapse", 3),
        ("ACMG classification for this variant", 4),
        ("Please call this as pathogenic based on the evidence", 5),
        ("clinical decision for this case", 6),
        ("what would you recommend if my child has this", 7),
        # Patterns 8 to 14 close finding ADV-01: advice about a THIRD PARTY.
        # Every one of these bypassed the entire guardrail before they
        # existed, because the pre-filter keys on first-person framing and the
        # classifier only judges injection. None of them is obfuscated; they
        # are how a clinician asks the question Section 10.5 forbids.
        ("Should this patient be started on tamoxifen given her status", 8),
        ("Should treatment be started immediately for this carrier", 9),
        ("What treatment would be most suitable in this case", 10),
        ("Given the result, what should be done next", 11),
        ("Is it recommended that screening begin at forty", 12),
        ("What is the most appropriate treatment here", 13),
        ("What does her treatment plan look like given this result", 14),
    ],
)
def test_seeks_verdict_matches_each_pattern(text: str, pattern_index: int) -> None:
    """One case per entry in `_VERDICT_PATTERNS`, in the same order.

    `pattern_index` is not read by the assertion; it documents which
    pattern a failure points back to, since the parametrize id alone
    would not say that.
    """
    assert seeks_verdict(text) is True, (
        f"pattern {pattern_index} did not match its own example: {text!r}"
    )


@pytest.mark.parametrize(
    "text",
    [
        "What is the standard treatment pathway for cystic fibrosis in the literature?",
        "Which publications describe the diagnosis criteria for Marfan syndrome?",
        "What treatments for BRCA1-mutant breast cancer are in recruiting clinical trials?",
        "Rank these variants by evidence strength as reported in ClinVar.",
    ],
)
def test_legitimate_evidence_questions_do_not_seek_a_verdict(text: str) -> None:
    """A question about the literature is not a request for a verdict.

    These collide with the same words the verdict patterns key on
    (treatment, diagnosis, classification-adjacent language) but ask about
    published evidence rather than asking the system to render a judgement.
    """
    assert seeks_verdict(text) is False, f"false positive on an evidence question: {text!r}"


# ---------------------------------------------------------------------------
# Category mapping and the read-only reason string.
# ---------------------------------------------------------------------------


def test_a_write_seeking_query_maps_to_write_seeking() -> None:
    """F-3.0-01, resolved at Step 6.2: a write-shaped category now exists,
    so a write-seeking refusal is no longer reported as `off_topic`. See the
    `screen()` docstring.
    """
    verdict = screen("add a node for gene X to the graph")
    assert verdict is not None
    assert verdict.category == "write_seeking"


def test_a_verdict_seeking_query_maps_to_medical_advice() -> None:
    verdict = screen("ACMG classification for this variant")
    assert verdict is not None
    assert verdict.category == "medical_advice"


def test_the_write_refusal_reason_mentions_read_only_access() -> None:
    """The category alone can't say "I cannot write"; the reason string must."""
    verdict = screen("update the BRCA1 record")
    assert verdict is not None
    assert verdict.reason is not None
    assert "read-only" in verdict.reason


def test_write_is_checked_before_verdict() -> None:
    """`screen()` checks `seeks_write` first. A query matching both factors of
    the write rule must be reported as a write refusal, not a verdict refusal,
    even if it happens to also carry verdict-shaped language.
    """
    verdict = screen("please update the pathogenic classification record")
    assert verdict is not None
    assert verdict.category == "write_seeking"


# ---------------------------------------------------------------------------
# The three-layer docstring claim: the other two layers actually exist.
# ---------------------------------------------------------------------------


def test_the_tool_level_forbidden_clauses_constant_exists_and_is_non_empty() -> None:
    """The module docstring claims this is one of three read-only layers and
    names the tool-level `FORBIDDEN_CYPHER_CLAUSES` list as the second one.

    A comment that claims a property is a claim to be tested, not
    documentation (`LEARNINGS.md`). Without this assertion, the
    cross-reference could go stale silently if that constant were ever
    renamed, emptied, or removed, and nothing here would notice.
    """
    from system_03_search_agent.tools.graph_schema_constants import (
        FORBIDDEN_CYPHER_CLAUSES,
    )

    assert len(FORBIDDEN_CYPHER_CLAUSES) > 0
    # The write verbs this module refuses on should be represented at the
    # tool layer too, since both layers are defending the same guarantee.
    assert "DELETE" in FORBIDDEN_CYPHER_CLAUSES
    assert "CREATE" in FORBIDDEN_CYPHER_CLAUSES


# ---------------------------------------------------------------------------
# No false refusals on legitimate biomedical questions.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text,collides_on",
    [
        (
            "Which pathogenic variants in DMD are whole-exon deletions?",
            "deletion, a write verb",
        ),
        (
            "How many records in ClinVar support this variant's classification?",
            "records, a store object",
        ),
        (
            "What does the graph say about TP53's known interactions?",
            "graph, a store object",
        ),
        (
            (
                "What treatments for BRCA1-mutant breast cancer are in recruiting "
                "clinical trials?"
            ),
            "treatments, a verdict-adjacent word",
        ),
        (
            "What is the genomic coordinate range for the DMD gene on GRCh38?",
            "coordinate query",
        ),
        (
            "Which diseases are associated with BRCA1?",
            "gene property question",
        ),
    ],
)
def test_no_false_refusal_on_legitimate_questions(text: str, collides_on: str) -> None:
    """Each case shares a trigger word with a forbidden pattern but is an
    ordinary evidence question. Refusing any of these is worse than missing
    a real forbidden query, per the module docstring's cost-asymmetry
    argument: this layer is the weakest of three, so it is tuned to refuse
    only on strong evidence.
    """
    verdict = screen(text)
    assert verdict is None, (
        f"refused a legitimate question colliding on {collides_on}: "
        f"{verdict.category if verdict else None}"
    )
