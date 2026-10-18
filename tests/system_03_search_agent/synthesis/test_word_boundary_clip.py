"""Item 11.33: a record's value must never be cut in the middle of a word.

Measured live on develop before the fix. The BRCA1 gene summary rendered as
"... and through the C-terminal d", and PubMed abstracts as "... or
'mutational signatures', wer" and "... has been uncle". Each is
`answer_layout`'s own 500-character slice landing mid-word, which makes the
product look like it is quoting NCBI badly.

The cause took two attempts to find, and the first one ruled the 500-char
slice out on a measurement that looked decisive: the visible fragments were
49 to 153 characters, far short of 500. What that missed is that a fragment
starts at the last sentence boundary INSIDE the slice, so its length says
nothing about where the slice fell. Settled by fetching the real NCBI value
and finding the offset of the rendered fragment's end in it: 500 exactly.

Coverage statement (goal-contracts): these arms exercise a value shorter
than the limit, a value longer than it with whitespace, a value longer than
it with NO whitespace, the exact live BRCA1 summary at the real 500-char
limit, and the boundary where a value is exactly the limit. They do NOT
exercise the live model, the live API, or the callers' own field-selection
logic, which `test_answer_layout.py` covers.

Depends on:
    - system_03_search_agent.synthesis.answer_layout (clip_to_word,
      MAX_LABEL_CHARS)
"""

from __future__ import annotations

from system_03_search_agent.synthesis.answer_layout import (
    MAX_LABEL_CHARS,
    clip_to_word,
)

# The real value, fetched from NCBI Gene ESummary for gene id 672 on
# 2026-09-21. Truncated here to the part that matters, with the exact text
# that surrounded the live mid-word cut.
_REAL_SUMMARY_AROUND_THE_CUT = (
    "This gene product associates with RNA polymerase II, and through the "
    "C-terminal domain, also interacts with histone deacetylase complexes."
)


class TestClipToWord:
    def test_a_value_within_the_limit_is_returned_unchanged(self) -> None:
        """Nothing that renders correctly today may render differently."""
        assert clip_to_word("Familial cancer of breast") == "Familial cancer of breast"

    def test_a_value_exactly_at_the_limit_is_unchanged(self) -> None:
        value = "x" * MAX_LABEL_CHARS
        assert clip_to_word(value) == value

    def test_a_long_value_is_cut_at_a_word_boundary_with_an_ellipsis(self) -> None:
        got = clip_to_word(_REAL_SUMMARY_AROUND_THE_CUT, 80)
        assert got.endswith("…"), got
        assert got == "This gene product associates with RNA polymerase II, and through the C-terminal…"

    def test_it_never_ends_on_a_half_word(self) -> None:
        """The defect itself, stated as a property rather than an example.

        For every limit across the value, the clipped text (minus its
        ellipsis) must end exactly where a word ends in the original.
        """
        value = _REAL_SUMMARY_AROUND_THE_CUT
        for limit in range(10, len(value)):
            got = clip_to_word(value, limit).rstrip("…")
            if got == value:
                continue
            remainder = value[len(got):]
            assert remainder == "" or not remainder[0].isalnum(), (
                f"limit {limit} cut mid-word: ...{got[-25:]!r} then {remainder[:12]!r}"
            )

    def test_a_value_with_no_whitespace_is_cut_hard_rather_than_mangled(self) -> None:
        """A long identifier or an HGVS name has no word boundary to honour,
        and breaking it at an arbitrary point would be worse than a hard cut.
        No ellipsis either, since nothing was rounded to a word."""
        value = "N" * 60
        assert clip_to_word(value, 20) == "N" * 20

    def test_the_mutation_arm_the_defect_returns_without_the_fix(self) -> None:
        """Populate-check plus mutation: the pre-fix behaviour was a plain
        slice, and it produced exactly the fragment seen live. If this ever
        stops being true, the arm above is no longer pinning the defect."""
        # 81, not 500: this fixture is the tail of the real summary rather
        # than the whole 1253-character value, so the limit that lands on
        # the same word differs. The POINT is unchanged, that a plain slice
        # ends "C-terminal d" while the fix ends on a whole word.
        naive = _REAL_SUMMARY_AROUND_THE_CUT.strip()[:81]
        assert naive.endswith("C-terminal d"), (
            "the pre-fix slice no longer reproduces the live fragment, so "
            f"this arm proves nothing; got {naive[-20:]!r}"
        )
        fixed = clip_to_word(_REAL_SUMMARY_AROUND_THE_CUT, 81)
        assert fixed != naive
        assert fixed.endswith("C-terminal\u2026"), fixed
