"""Deterministic planning helpers for "search broad, cite exact" (UI fix set 11).

The product owner approved widening every gene-anchored question from four
fixed Layer 2 and 3 calls to a fan-out across the literature, live ClinVar
and OMIM, with two constraints the audit in
`testing/Developer/reports/2026-09-14_handover_inputs/breadth/findings.md`
set: the same input must produce the same planned calls every run, and
untrusted abstract text never becomes a finding on the model's say-so.
This module is the planning half and nothing else (see the hold-back note
below). It makes no network call and no model call; every
function is a pure function of its arguments, so `plan_node` in
`core/graph.py` can call it and hand the results to its own `_layer_call`
without owning any of the logic here.

Two stages, because the literature calls depend on PMIDs the planner does
not hold until PubMed answers:

- `plan_first_stage(gene_symbol, disease_title)`: the calls that need only
  the resolved symbol or the disease title. A PubMed ESearch on the symbol
  and title, capped at `PUBMED_RESULT_CAP`; for a symbol, a live ClinVar
  ESearch on `SYMBOL[gene]` and an OMIM ESearch on the bare symbol, each
  capped. Verified live 2026-09-14: all three term shapes are accepted and
  translated by ESearch exactly as written. `hasabstract` was tried as a
  PubMed filter and rejected here, because ESearch translated both its
  bare and `[Filter]` forms into a plain text search for the word.
- `plan_literature_follow_up(pmids)`: the abstract fetch and the PubTator3
  `annotate_publications` call on the SAME PMIDs, after the ids are sorted
  and capped, so both calls always name the identical paper set.
- `plan_clinvar_follow_up(ids)` and `plan_omim_follow_up(ids)`: the
  ESummary calls on the ids the first-stage searches returned, sorted and
  capped the same way.
- `plan_topic_search(question)`: the ONE call a question that names no
  gene and no disease earns (fix-plan item 12.7, 2026-09-23). Its term is
  `build_topic_term(question)`, the question's own content words joined
  with ` AND `, untagged so PubMed's automatic term mapping expands them.
  It is planned with the purpose `pubmed_search`, so the abstract fetch and
  the PubTator3 annotation below follow it exactly as they follow a gene's.
- `plan_first_stage(..., datasets=True)` adds a GEO DataSets ESearch on the
  symbol (2026-09-22, fix-plan item 1), planned by `core/graph.py` only when
  `wants_dataset_search(question)` says the question asks for datasets, and
  `plan_gds_follow_up(ids)` is its ESummary. GEO is the one place expression
  datasets live, the graph has no dataset vertex, and golden G-037 ("Find
  GEO expression datasets studying TP53 in human tumour samples") answered
  with no dataset at all until then. The term shape was verified live the
  same day against ESearch's own `querytranslation`.

Sorting: every id list is sorted numerically, highest first, before it is
capped. ESearch returns PubMed ids in date-added order rather than id
order (live-measured the same day: `33180404` ahead of `42470517`), and
"most recently indexed" is not stable between runs, while "the five
highest PMIDs among the hits" is a fixed function of the hit set. The
planner never re-sorts by relevance.

`filter_omim_titles(records, symbol)` keeps only OMIM summary records whose
title names the symbol in one of its semicolon-separated symbol fields,
exactly. An OMIM title reads `NAME; SYMBOL[; SYMBOL2...]`, so the symbol
fields are every segment after the first. The audit found OMIM's first hit
for `GCK` was `MAP4K2`, so an unfiltered OMIM result cites the wrong gene.
Review F-07: a word-anywhere match let `T` keep `T-CELL RECEPTOR ALPHA
LOCUS; TRA`, so the match is field-exact, never a word in the name.

Held back by product-owner decision after review round 2 (2026-09-14):
abstract sentences do not become findings until a new design exists. The
abstract quote check this module first carried was removed outright,
because a regex sentence rule accepted meaning-reversing fragments (N-01)
and cannot see a refutation in the next sentence (N-03). The abstracts
`plan_literature_follow_up` fetches are retrieved for the PubTator3 call on
the same PMIDs and for the paper's citation, not for quotation.

Depends on:
    - system_03_search_agent.tools.ncbi_efetch_schemas (NcbiEfetchInput)
    - system_03_search_agent.tools.pubtator_annotate_schemas
      (PubtatorAnnotateInput)

Reads:
    - Nothing. Pure functions over their arguments.

Writes:
    - Nothing.

Depended by:
    - system_03_search_agent.core.graph (`plan_node`, the wiring that hands
      each `PlannedCall` to `_layer_call`; not yet wired when this module
      landed, see the report for UI fix set 11)
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any, Final

from system_03_search_agent.tools.ncbi_efetch_schemas import NcbiEfetchInput
from system_03_search_agent.tools.pubtator_annotate_schemas import PubtatorAnnotateInput

# Per-source caps, the "cap per source" the findings document sets. Five
# papers is the audit's measured sweet spot (0.22 s for five abstracts,
# 1,000 to 1,300 characters each); ten ClinVar and ten OMIM records match
# the audit's own probe sizes.
PUBMED_RESULT_CAP: Final[int] = 5
CLINVAR_RESULT_CAP: Final[int] = 10
OMIM_RESULT_CAP: Final[int] = 10
GDS_RESULT_CAP: Final[int] = 5

# T-8.1-07 (tracker/phase_8.1.md): the ESearch call for a PubMed literature
# search asks for a CANDIDATE POOL, not the final five. Before this constant
# existed, the search's own `retmax` WAS `PUBMED_RESULT_CAP`, so
# `plan_literature_follow_up`'s `select_ids` (highest PMID first, "the
# planner never re-sorts by relevance", see the module docstring) had
# nothing to re-sort: it received at most five ids and could only reorder
# them, never correct for which five NCBI's own relevance ranking put in
# that window on a given call. Requesting a wider pool first and picking the
# five highest PMIDs out of it, deterministically, is what the module's own
# design intent already says should happen; this constant is what makes it
# actually happen. `total_available` and the search step's own displayed
# summary are unaffected (`core/graph.py` reports them from ESearch's own
# `count` field, never from `retmax`), so widening this pool changes nothing
# a reader sees except which five papers are consistently the ones cited.
PUBMED_SEARCH_OVERFETCH: Final[int] = 30
# One concept id resolves to one MedGen record, so this cap is a bound on a
# malformed response rather than a choice about how much to show.
MEDGEN_RESULT_CAP: Final[int] = 5

# Bounds on the two free-text inputs. A gene symbol is at most 30
# characters (`NcbiEfetchDatasetReportInput.symbol` uses the same bound) and
# is restricted to the characters a real HGNC symbol or NCBI alias uses, so
# no PubMed operator, bracket or quote can ride in on it. A disease title is
# free text from a MedGen record, so it is not shape-validated, only
# stripped of the characters that carry meaning in a PubMed term and capped.
_MAX_SYMBOL_CHARS: Final[int] = 30
_MAX_TITLE_CHARS: Final[int] = 200
_SYMBOL_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9_.@-]{0,29}$", re.ASCII
)
# A balanced parenthesised segment, removed WHOLE rather than having its
# brackets deleted. Fix-plan item 12.1 (2026-09-23), measured: MedGen's
# preferred name for C5563728 is `Gastroesophageal reflux (GERD)`, and
# deleting only the two brackets leaves the phrase `gastroesophageal reflux
# gerd`, which is not a phrase any paper or trial record contains. A
# MedGen parenthetical is an acronym gloss beside the name, so dropping it
# leaves the name itself. Every character the strip pattern below exists to
# remove is removed by this too, so it never widens what may reach a term.
_PARENTHETICAL: Final[re.Pattern[str]] = re.compile(r"\([^()]*\)")
_TITLE_STRIP_PATTERN: Final[re.Pattern[str]] = re.compile(r'["\[\]():*?]')
_WHITESPACE_RUN: Final[re.Pattern[str]] = re.compile(r"\s+")

# A MedGen concept id, the local half of a `MedGen:` CURIE: `C` or `CN`
# then digits. The same shape `synthesis/disease_names.MEDGEN_CONCEPT_ID`
# enforces, restated here so this module stays a pure function of its
# arguments with no import of the synthesis layer.
_MEDGEN_CONCEPT_ID: Final[re.Pattern[str]] = re.compile(r"^CN?\d+$", re.ASCII)

# The words that say a question is asking for expression datasets, which
# live in GEO and nowhere the graph or the other searches reach. Word-bounded
# and deliberately narrow: "dataset" alone, GEO's own names, and the ways
# people say expression profiling. "expression" on its own is not here,
# since "how is its expression regulated" describes what a gene does, not a
# request for data.
_DATASET_WORDS: Final[re.Pattern[str]] = re.compile(
    r"\b(geo|gds|gse\d*|datasets?|expression\s+(?:data|profiles?|profiling)|microarrays?|rna-?seq)\b",
    re.IGNORECASE,
)

# An E-utilities uid is a plain positive integer (`ncbi_efetch_schemas`
# caps an id at 30 characters; PubTator3 at 15). Anything else is not an
# id this module will plan a fetch for.
_UID_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[0-9]{1,15}$", re.ASCII)

# Call id prefixes, matching the ones `core/graph.py` already stamps on the
# same tools (`ne` for `ncbi_efetch`, `pa` for `pubtator_annotate`), so a
# call planned here reads the same in the audit log as one planned there.
_NCBI_EFETCH: Final[str] = "ncbi_efetch"
_PUBTATOR: Final[str] = "pubtator_annotate"
_LAYER_2: Final[str] = "layer_2_api"
_LAYER_3: Final[str] = "layer_3_enrichment"


@dataclass(frozen=True)
class PlannedCall:
    """One Layer 2 or 3 call the planner should issue, fully specified.

    `tool_input` is an already-validated tool input model, so a value that
    reaches `plan_node` has passed the tool's own schema bounds. `purpose`
    names what the call is for in the fan-out, so Act and Write can route
    its result (an OMIM summary to the title filter, for one) without
    inspecting the input again.
    """

    tool: str
    layer: str
    prefix: str
    purpose: str
    tool_input: NcbiEfetchInput | PubtatorAnnotateInput | Any


def _normalise_symbol(gene_symbol: str | None) -> str | None:
    """Uppercase, trimmed, shape-checked. None when nothing usable was given.

    Raises `TypeError` for a non-string, and `ValueError` for a non-empty
    symbol that is not symbol-shaped,
    since a term like `BRCA1 OR cancer` planned silently would search for
    something the caller never asked about.
    """
    if gene_symbol is None:
        return None
    if not isinstance(gene_symbol, str):
        raise TypeError("gene_symbol must be a string or None")
    trimmed = gene_symbol.strip()
    if not trimmed:
        return None
    if len(trimmed) > _MAX_SYMBOL_CHARS or _SYMBOL_PATTERN.match(trimmed) is None:
        raise ValueError(
            f"gene_symbol {trimmed[:40]!r} is not a gene symbol shape "
            "(letters, digits, '_', '.', '@' or '-', at most 30 characters); "
            "pass the resolved symbol, never free text"
        )
    return trimmed.upper()


def _normalise_title(disease_title: str | None) -> str | None:
    """Lowercase, whitespace-collapsed, operator characters removed, capped.

    A balanced parenthesised segment is dropped WHOLE before anything else
    (see `_PARENTHETICAL`), so `Gastroesophageal reflux (GERD)` becomes
    `gastroesophageal reflux` rather than `gastroesophageal reflux gerd`.
    Any bracket left unbalanced is still removed as a character, so nothing
    that carries meaning in a PubMed term survives either path.

    None when nothing usable remains, so a title made only of quotes or
    brackets plans no disease clause rather than an empty quoted string.
    """
    if disease_title is None:
        return None
    if not isinstance(disease_title, str):
        raise TypeError("disease_title must be a string or None")
    without_gloss = _PARENTHETICAL.sub(" ", disease_title)
    stripped = _TITLE_STRIP_PATTERN.sub(" ", without_gloss)
    collapsed = _WHITESPACE_RUN.sub(" ", stripped).strip().lower()
    if not collapsed:
        return None
    return collapsed[:_MAX_TITLE_CHARS].strip()


def disease_search_text(disease_title: str | None) -> str | None:
    """The one text a disease-anchored question searches on, or None.

    Fix-plan item 12.1 (2026-09-23). `core/graph.py` plans three different
    calls from a disease: the PubMed term, the trials condition and the
    PubTator3 entity lookup. All three take THIS string, so a question's
    three searches can never disagree about which disease they are about.

    The argument is the MedGen record's own preferred name, fetched live
    from the resolved `MedGen:` CURIE, never the user's phrasing and never
    a model-extracted span, which is what makes the result the same on
    every run of one question. The normalisation is the same one
    `build_pubmed_term` applies, exposed so the other two calls use the
    identical bytes rather than a second cleanup of their own.
    """
    return _normalise_title(disease_title)


def build_pubmed_term(gene_symbol: str | None, disease_title: str | None) -> str | None:
    """The PubMed ESearch term for a symbol, a title, or both. None for neither.

    Shapes, each verified live on 2026-09-14 against ESearch's own
    `querytranslation`:

    - symbol only: `BRCA1[Title/Abstract]`
    - title only: `"maturity-onset diabetes of the young"[Title/Abstract]`
    - both: the two joined with ` AND `
    """
    symbol = _normalise_symbol(gene_symbol)
    title = _normalise_title(disease_title)
    clauses: list[str] = []
    if symbol:
        clauses.append(f"{symbol}[Title/Abstract]")
    if title:
        clauses.append(f'"{title}"[Title/Abstract]')
    if not clauses:
        return None
    return " AND ".join(clauses)


def wants_dataset_search(question: str | None) -> bool:
    """Whether `question` asks for expression datasets, the one kind of
    record only GEO holds. Golden G-037, "Find GEO expression datasets
    studying TP53 in human tumour samples", answered with no dataset at all
    until 2026-09-22 because nothing searched GEO, and the graph has no
    dataset vertex, so its own search could not stand in. Pure and
    deterministic; False for anything that is not a string."""
    if not isinstance(question, str):
        return False
    return _DATASET_WORDS.search(question) is not None


def build_gds_term(gene_symbol: str | None) -> str | None:
    """The GEO DataSets ESearch term for a symbol: the symbol in every field,
    restricted to series (`gse[Entry Type]`), so the hits are datasets a
    person can open rather than the samples inside them. Verified live on
    2026-09-22 against ESearch's own `querytranslation`: `TP53[All Fields]
    AND gse[Entry Type]` is translated exactly as written and matches 1,569
    series, where the unrestricted term matched 19,092 entries, most of
    them single samples. No organism clause, deliberately: a mouse question
    would be silently narrowed to human, and the summary rows carry `taxon`
    for the reader to see. None for no usable symbol; a symbol that is not
    symbol-shaped raises, as `build_pubmed_term` does."""
    symbol = _normalise_symbol(gene_symbol)
    if not symbol:
        return None
    return f"{symbol}[All Fields] AND gse[Entry Type]"


# ---------------------------------------------------------------------------
# Fix-plan item 12.7 (2026-09-23): the topic search, for a question that
# names no gene and no disease.
#
# THE INSIGHT THIS IS BUILT ON, because the obvious reading of the defect
# leads somewhere much worse. Four questions a second tester asked refused
# outright: two about caffeine and exercise, two about the variants a
# population carries. They refused because the product has a gene resolver
# and a disease resolver and nothing else, so Think resolved no entity and
# the graph call had nothing to bind. The obvious fix is a chemical
# resolver and a population resolver. That is the wrong layer and it is an
# infinite list, since the next question names a diet, a sport, an
# occupation or a country.
#
# A LITERATURE QUESTION NEEDS NO ENTITY AT ALL. "What has been published
# about caffeine and exercise performance" is answerable by searching
# PubMed with the question's own words. The entity resolver exists so the
# GRAPH can be queried by CURIE, and the graph is not what answers these.
#
# WHY THIS IS SAFE WHERE A MODEL-EXTRACTED SPAN WAS NOT. Item 11.21
# promised the same question always shows the same sources, which is why
# `_build_layer_tool_calls` refuses a model-extracted disease span. The
# term below is built from the USER'S OWN TYPED WORDS by a fixed rule with
# no model call and no network call in it, so it is a pure function of the
# question text and cannot vary between runs of one question.

# Grammar words: articles, prepositions, conjunctions, pronouns,
# determiners, auxiliaries and the question words. A closed class, so this
# list is finite rather than a growing pile of special cases.
_TOPIC_STOPWORDS: Final[frozenset[str]] = frozenset(
    (
        "a", "about", "above", "across", "after", "again", "against", "all",
        "almost", "along", "also", "although", "always", "am", "among", "an", "and",
        "another", "any", "anybody", "anyone", "anything", "are", "around", "as",
        "at", "be", "because", "been", "before", "being", "below", "beneath",
        "beside", "between", "beyond", "both", "but", "by", "can", "cannot",
        "could", "did", "do", "does", "doing", "done", "down", "during", "each",
        "either", "else", "enough", "even", "ever", "every", "everybody",
        "everyone", "everything", "except", "few", "for", "from", "further", "had",
        "has", "have", "having", "he", "her", "hers", "herself", "him", "himself",
        "his", "how", "however", "i", "if", "in", "inside", "into", "is", "it",
        "its", "itself", "just", "let", "many", "may", "me", "might", "mine",
        "more", "most", "much", "must", "my", "myself", "near", "neither", "never",
        "no", "nobody", "none", "nor", "not", "nothing", "now", "of", "off", "on",
        "once", "one", "only", "onto", "or", "other", "others", "ought", "our",
        "ours", "ourselves", "out", "over", "own", "per", "rather", "same", "shall",
        "she", "should", "since", "so", "some", "somebody", "someone", "something",
        "still", "such", "than", "that", "the", "their", "theirs", "them",
        "themselves", "then", "there", "these", "they", "this", "those", "though",
        "through", "throughout", "thus", "to", "too", "toward", "towards", "under",
        "unless", "until", "up", "upon", "us", "very", "via", "was", "we", "were",
        "what", "whatever", "when", "whenever", "where", "whether", "which",
        "while", "who", "whoever", "whom", "whose", "why", "will", "with", "within",
        "without", "would", "yet", "you", "your", "yours", "yourself", "yourselves",
    )
)

# Words the asker uses to describe the SEARCH, or the act of asking,
# rather than the subject. A paper is not indexed under "paper". Measured
# 2026-09-23: the verbatim question `papers on the effects of caffeine on
# exercise performance` translated `papers` to `"paper"[MeSH Terms]`, the
# physical material, and the search collapsed from 1,356 hits to 35
# largely irrelevant ones.
_TOPIC_META_WORDS: Final[frozenset[str]] = frozenset(
    (
        "abstract", "abstracts", "article", "articles", "ask", "asks", "believe",
        "believes", "citation", "citations", "consider", "curious", "describe",
        "describes", "evidence", "explain", "explains", "find", "finding",
        "information", "journal", "journals", "know", "knows", "literature",
        "paper", "papers", "publication", "publications", "published", "reference",
        "references", "report", "reports", "research", "review", "reviews", "said",
        "say", "says", "search", "show", "studies", "study", "summarise",
        "summarize", "summary", "tell", "think", "thinks", "thought", "understand",
        "wonder", "wondering",
    )
)

# Light verbs and hedging adverbs: grammatical filler that carries no
# subject. Measured 2026-09-23, and this category is load-bearing rather
# than tidy: `coffee AND help AND make AND exercise AND effective` returned
# ZERO hits, while `coffee AND exercise AND effective` returned 532, and
# `variants AND found AND mediterranean AND descent` returned zero while
# `variants AND mediterranean AND descent` returned 22.
_TOPIC_FILLER_WORDS: Final[frozenset[str]] = frozenset(
    (
        "actually", "always", "commonly", "found", "generally", "get", "gets",
        "getting", "give", "given", "gives", "got", "help", "helped", "helpful",
        "helping", "helps", "known", "let", "make", "makes", "making", "mean",
        "means", "often", "really", "seen", "simply", "sometimes", "take", "takes",
        "taking", "tell", "told", "typical", "typically", "usual", "usually", "well",
    )
)

# The asker's VALUE JUDGEMENT about the answer. A paper is not indexed
# under whether its subject is a good thing. Measured 2026-09-23: `variants
# AND people AND mediterranean AND descent` returned 17 hits, and adding
# `beneficial` to it returned ZERO.
#
# `positive` and `negative` are DELIBERATELY ABSENT, and the omission is
# the line this category is drawn at rather than an oversight. In
# biomedical text both are technical ("HER2-positive", "gram-negative",
# "negative regulation"), so dropping them would damage questions this path
# is not even about; and the question that prompted the worry, `What
# positive and negative genes do ashkenazi jewish people have?`, was
# measured to return 27 relevant hits with both words KEPT. Nothing needed
# dropping, so nothing was dropped.
_TOPIC_JUDGEMENT_WORDS: Final[frozenset[str]] = frozenset(
    (
        "bad", "beneficial", "benefit", "benefits", "best", "better", "dangerous",
        "good", "great", "harmful", "important", "interesting", "nice", "safe",
        "unsafe", "useful", "useless", "worse", "worst",
    )
)

#: A word a topic term may be built from: a letter first, then letters,
#: digits, apostrophes or hyphens. Everything else in the question, every
#: bracket, quote, colon and operator character, is not matched at all, so
#: no PubMed operator can ride into the term on the user's own text.
_TOPIC_WORD: Final[re.Pattern[str]] = re.compile(r"[A-Za-z][A-Za-z0-9'-]*")

#: At most this many words are ANDed together. Every word in an AND chain
#: is REQUIRED, so a long chain fails catastrophically: one word the
#: literature does not use zeroes the whole search. The four measured
#: questions yield three to six words; eight is a ceiling on a pathological
#: input rather than a tuning knob.
TOPIC_MAX_WORDS: Final[int] = 8

#: What one topic search asks for, the same cap the literature leg of a
#: gene question uses, so a topic answer is the same size as any other.
TOPIC_RESULT_CAP: Final[int] = PUBMED_RESULT_CAP


#: Words that say the reader is asking for the PUBLISHED LITERATURE. Added
#: 2026-09-23 after review, for the defect below.
#:
#: THE DEFECT. `resolve_disease_mention_to_curies("caffeine")` binds EIGHT
#: MedGen concepts, measured live: "Caffeine dependence", "Caffeine
#: withdrawal", "Organic mental disorder caused by caffeine", "Allergy to
#: caffeine" and four more. Every one of them is a real disorder, so no
#: semantic-type check can reject them; that hypothesis was built, measured
#: and killed. They bind because MedGen's NAME INDEX matches any title
#: CONTAINING the word, and the question was not about any of them. Whether
#: they reach the answer depends on whether the Think model happens to label
#: `caffeine` a disease span on that run, which is a sample, not a rule: a
#: reviewer measured the flip at about 1 run in 3 and eight runs here
#: reproduced it 0 times. On a flipped run the reader who asked for papers
#: on caffeine and exercise got two MedGen records about caffeine
#: intoxication instead of five papers.
#:
#: THE RULE, from the reader's chair: they typed "papers on". They should
#: get papers. So when the question asks for the published literature and
#: no gene resolved, the literature search is what runs, whatever the model
#: labelled. That is deterministic because it reads only the typed text.
#:
#: WHAT IS DELIBERATELY ABSENT, and each omission is the line this list is
#: drawn at rather than an oversight:
#:
#: - `trial`, `trials`. A trial is the ClinicalTrials.gov registry, a
#:   different source, and the disease path ALREADY searches it. `Any
#:   trials for GERD?` must keep its 20 citations, and it does.
#: - `study`, `studies`, `research`. Ambiguous: "what studies exist for
#:   GERD?" is a disease question that would lose its MedGen record and its
#:   trials leg to a bare PubMed search. Narrow beats broad where the
#:   broad version takes something away.
_LITERATURE_WORDS: Final[frozenset[str]] = frozenset(
    (
        "article", "articles", "literature", "paper", "papers", "preprint",
        "preprints", "pubmed", "publication", "publications",
    )
)


def asks_for_published_literature(question: str | None) -> bool:
    """Whether the question asks for the published literature by name.

    A pure function of the typed text, word-bounded, with no model call and
    no network call in it, which is what lets it decide a path without
    breaking item 11.21's one-question-one-source-set promise.
    """
    if not isinstance(question, str):
        return False
    return any(
        match.group(0).strip("'-") in _LITERATURE_WORDS
        for match in _TOPIC_WORD.finditer(question.lower())
    )


def topic_search_words(question: str | None) -> list[str]:
    """The content words of `question`, in question order, deduplicated.

    Lowercased, with the four dropped categories above removed. A pure
    function of the string: no model call, no network call, no randomness,
    so the same question yields the same words on every run.
    """
    if not isinstance(question, str):
        return []
    words: list[str] = []
    for match in _TOPIC_WORD.finditer(question.lower()):
        word = match.group(0).strip("'-")
        if not word:
            continue
        if (
            word in _TOPIC_STOPWORDS
            or word in _TOPIC_META_WORDS
            or word in _TOPIC_FILLER_WORDS
            or word in _TOPIC_JUDGEMENT_WORDS
        ):
            continue
        if word not in words:
            words.append(word)
    return words[:TOPIC_MAX_WORDS]


def build_topic_term(question: str | None) -> str | None:
    """The PubMed ESearch term for a question with nothing to resolve.

    The content words joined with ` AND `, UNTAGGED, so PubMed's own
    automatic term mapping expands each one against its translation table.
    None when no content word survives, which is this module's signal to
    plan nothing rather than an error.

    UNTAGGED IS A MEASURED CHOICE, NOT AN OVERSIGHT, and it is the opposite
    of what `build_pubmed_term` does for a gene. Tagging each word
    `[Title/Abstract]` turns off the mapping, and on 2026-09-23 that took
    `What positive and negative genes do ashkenazi jewish people have?`
    from 27 hits to ZERO. Untagged, ESearch's own `querytranslation`
    expanded `caffeine` to `"caffeine"[Supplementary Concept] OR
    "caffeine"[All Fields] ...` and `coffee` to its MeSH term, which is the
    behaviour a lay question needs. The gene path keeps its tag for the
    opposite reason: a symbol in All Fields matches author names and
    addresses.

    Live hit counts, all measured on 2026-09-23 with the term read back
    through `querytranslation`:

    - `papers on the effects of caffeine on exercise performance`
      -> `effects AND caffeine AND exercise AND performance`, 1,356 hits
    - `Does coffee help make exercise more effective?`
      -> `coffee AND exercise AND effective`, 532 hits
    - `Are there any beneficial variants typically found in people of
      mediterranean descent?`
      -> `variants AND people AND mediterranean AND descent`, 17 hits
    - `What positive and negative genes do ashkenazi jewish people have?`
      -> `positive AND negative AND genes AND ashkenazi AND jewish AND
      people`, 27 hits
    """
    words = topic_search_words(question)
    if not words:
        return None
    return " AND ".join(words)


def plan_topic_search(question: str | None) -> tuple[PlannedCall, ...]:
    """The single PubMed search a topic question earns, or an empty tuple.

    Its purpose is `pubmed_search`, the SAME purpose the gene and disease
    paths use, deliberately: `core/graph.py`'s `_BREADTH_FOLLOW_UPS` keys
    the abstract fetch and the PubTator3 annotation on that purpose, so a
    topic question gets the identical two follow-ups on the identical PMIDs
    with no second wiring to keep in step with the first.
    """
    term = build_topic_term(question)
    if term is None:
        return ()
    return (_search_call("pubmed_search", "pubmed", term, PUBMED_SEARCH_OVERFETCH),)


def _search_call(purpose: str, db: str, term: str, retmax: int) -> PlannedCall:
    return PlannedCall(
        tool=_NCBI_EFETCH,
        layer=_LAYER_2,
        prefix="ne",
        purpose=purpose,
        tool_input=NcbiEfetchInput.model_validate(
            {"action": "search", "db": db, "term": term[:500], "retmax": retmax}
        ),
    )


def plan_first_stage(
    gene_symbol: str | None, disease_title: str | None, *, datasets: bool = False
) -> tuple[PlannedCall, ...]:
    """The calls that need only the symbol or the title, in fixed order.

    Order: PubMed search, then for a symbol the ClinVar search and the OMIM
    search, then, with `datasets` and a symbol, the GEO DataSets search
    (2026-09-22, fix-plan item 1), planned last so that under the Section
    21.3 ceiling it is the first search admission would skip. An empty
    tuple when neither input is usable, which is the planner's signal to
    plan nothing extra rather than an error: a question that resolved no
    gene and bound no disease earns no fan-out.

    THE TITLE-ONLY PATH IS LIVE AS OF 2026-09-23 (fix-plan item 12.1) and
    had no caller until then. A disease-anchored question passes the
    MedGen record's own preferred name here and gets the PubMed search;
    ClinVar, OMIM and GEO stay gene-only, because each of those three
    terms is a gene field (`SYMBOL[gene]`) or a gene symbol, and there is
    no disease equivalent that returns the same kind of record.
    """
    symbol = _normalise_symbol(gene_symbol)
    term = build_pubmed_term(symbol, disease_title)
    calls: list[PlannedCall] = []
    if term:
        calls.append(_search_call("pubmed_search", "pubmed", term, PUBMED_SEARCH_OVERFETCH))
    if symbol:
        calls.append(
            _search_call("clinvar_search", "clinvar", f"{symbol}[gene]", CLINVAR_RESULT_CAP)
        )
        calls.append(_search_call("omim_search", "omim", symbol, OMIM_RESULT_CAP))
        if datasets:
            gds_term = build_gds_term(symbol)
            if gds_term:
                calls.append(_search_call("gds_search", "gds", gds_term, GDS_RESULT_CAP))
    return tuple(calls)


def build_medgen_term(disease_curie: str | None) -> str | None:
    """The MedGen ESearch term for one resolved `MedGen:` CURIE, or None.

    Shape: `C5563728[ConceptId]`. Verified live on 2026-09-23, and it is
    the same field `synthesis/disease_names` already searches on to read a
    concept's preferred name, so this is a known-good term rather than a
    new query shape. A concept id is not a uid, so an ESummary keyed on it
    is rejected outright and the search is genuinely needed.

    None for anything that is not a `MedGen:` CURIE with a concept-shaped
    local id, which is this module's own signal to plan nothing rather
    than an error, the same contract `plan_gene_summary` carries.
    """
    if not isinstance(disease_curie, str):
        return None
    prefix, separator, local = disease_curie.strip().partition(":")
    if not separator or prefix.strip() != "MedGen":
        return None
    concept_id = local.strip().upper()
    if _MEDGEN_CONCEPT_ID.match(concept_id) is None:
        return None
    return f"{concept_id}[ConceptId]"


def plan_disease_search(disease_curie: str | None) -> tuple[PlannedCall, ...]:
    """The MedGen record search for a disease-anchored question.

    Fix-plan item 12.1 (2026-09-23). The disease's own MedGen record is
    the live record leg of a disease question's breadth, the counterpart
    of the Gene ESummary a gene question gets (`plan_gene_summary`): it
    carries the concept's name, its definition and its semantic type, all
    citable to `ncbi.nlm.nih.gov/medgen/<uid>`.

    A search rather than a direct summary, and this is the one place a
    reader will reasonably expect a single call: a MedGen CONCEPT id is
    not an E-utilities uid, and `synthesis/disease_names` measured NCBI
    rejecting an ESummary keyed on one outright (`Invalid uid C0346153`).
    The uid the record page is addressed by only exists in the search
    result, so the pair is the minimum, not an extra hop.

    An empty tuple for a CURIE this module cannot build a term from.
    """
    term = build_medgen_term(disease_curie)
    if term is None:
        return ()
    return (_search_call("medgen_search", "medgen", term, MEDGEN_RESULT_CAP),)


def select_ids(ids: Iterable[Any], cap: int) -> list[str]:
    """Sort uids numerically, highest first, drop non-uids and repeats, cap.

    Deterministic by construction: the output depends only on the SET of
    valid ids in `ids`, never on the order or repetition they arrived in.
    """
    valid: set[str] = set()
    for value in ids:
        if isinstance(value, int) and not isinstance(value, bool) and value > 0:
            value = str(value)
        if not isinstance(value, str):
            continue
        candidate = value.strip()
        if _UID_PATTERN.match(candidate) is None:
            continue
        # Review F-06: a uid is a POSITIVE integer. `"0"` and `"000"` are
        # digit strings and not ids; PMID 0 does not exist.
        normalised = candidate.lstrip("0")
        if not normalised:
            continue
        valid.add(normalised)
    ordered = sorted(valid, key=int, reverse=True)
    return ordered[:cap]


def plan_literature_follow_up(pmids: Iterable[Any]) -> tuple[PlannedCall, ...]:
    """Abstract fetch plus PubTator3 annotation on the same sorted, capped PMIDs.

    Both calls carry the identical id list, so the relations PubTator3
    returns are for exactly the papers that were fetched. An empty tuple
    when no valid PMID was given.
    """
    selected = select_ids(pmids, PUBMED_RESULT_CAP)
    if not selected:
        return ()
    fetch = PlannedCall(
        tool=_NCBI_EFETCH,
        layer=_LAYER_2,
        prefix="ne",
        purpose="pubmed_abstracts",
        tool_input=NcbiEfetchInput.model_validate(
            {
                "action": "fetch",
                "db": "pubmed",
                "ids": selected,
                "rettype": "abstract",
                "retmode": "xml",
            }
        ),
    )
    annotate = PlannedCall(
        tool=_PUBTATOR,
        layer=_LAYER_3,
        prefix="pa",
        purpose="pubtator_publications",
        tool_input=PubtatorAnnotateInput.model_validate(
            {"mode": "annotate_publications", "pmids": selected}
        ),
    )
    return (fetch, annotate)


def _summary_call(purpose: str, db: str, ids: list[str]) -> PlannedCall:
    return PlannedCall(
        tool=_NCBI_EFETCH,
        layer=_LAYER_2,
        prefix="ne",
        purpose=purpose,
        tool_input=NcbiEfetchInput.model_validate({"action": "summary", "db": db, "ids": ids}),
    )


def plan_clinvar_follow_up(ids: Iterable[Any]) -> tuple[PlannedCall, ...]:
    """ClinVar ESummary on the sorted, capped uids a ClinVar search returned."""
    selected = select_ids(ids, CLINVAR_RESULT_CAP)
    if not selected:
        return ()
    return (_summary_call("clinvar_summary", "clinvar", selected),)


def plan_omim_follow_up(ids: Iterable[Any]) -> tuple[PlannedCall, ...]:
    """OMIM ESummary on the sorted, capped uids an OMIM search returned.

    The caller filters the RESULT with `filter_omim_titles`; the ids
    themselves cannot be filtered before the titles are known.
    """
    selected = select_ids(ids, OMIM_RESULT_CAP)
    if not selected:
        return ()
    return (_summary_call("omim_summary", "omim", selected),)


def plan_gds_follow_up(ids: Iterable[Any]) -> tuple[PlannedCall, ...]:
    """GEO DataSets ESummary on the sorted, capped uids a GEO search returned.
    The summary carries the series accession, title, organism, dataset type
    and sample count (`ncbi_eutils_actions._SUMMARY_FIELDS_BY_DB["gds"]`),
    and the record URL is NCBI's own `gds/{uid}` page."""
    selected = select_ids(ids, GDS_RESULT_CAP)
    if not selected:
        return ()
    return (_summary_call("gds_summary", "gds", selected),)


def plan_medgen_follow_up(ids: Iterable[Any]) -> tuple[PlannedCall, ...]:
    """MedGen ESummary on the sorted, capped uids a MedGen search returned.

    The summary carries the concept id, the preferred title, the
    definition and the semantic type
    (`ncbi_eutils_actions._SUMMARY_FIELDS_BY_DB["medgen"]`), and the record
    URL is NCBI's own `medgen/{uid}` page.
    """
    selected = select_ids(ids, MEDGEN_RESULT_CAP)
    if not selected:
        return ()
    return (_summary_call("medgen_summary", "medgen", selected),)


def filter_omim_titles(
    records: Iterable[Mapping[str, Any]], gene_symbol: str | None
) -> list[Mapping[str, Any]]:
    """Keep only the OMIM records whose title names the symbol in a symbol field.

    `records` are the `fields` mappings of `ncbi_efetch` summary records
    (or the records themselves, since `fields` is read when present). An
    OMIM title is `NAME; SYMBOL[; SYMBOL2...]`; every segment after the
    first is a symbol field, and one of them must equal the symbol exactly
    (case-insensitive, whitespace-trimmed). Review F-07: never a word
    anywhere in the title, so `T` does not keep `T-CELL RECEPTOR ALPHA
    LOCUS; TRA` and `GCK` does not keep `...; GCK, INCLUDED`. An unusable
    symbol keeps nothing: with no symbol to check against, no OMIM title
    can be stood behind.
    """
    symbol = _normalise_symbol(gene_symbol)
    if symbol is None:
        return []
    kept: list[Mapping[str, Any]] = []
    for record in records:
        if not isinstance(record, Mapping):
            continue
        fields = record.get("fields")
        source = fields if isinstance(fields, Mapping) else record
        title = source.get("title")
        if not isinstance(title, str):
            continue
        symbol_fields = [segment.strip().upper() for segment in title.split(";")[1:]]
        if symbol in symbol_fields:
            kept.append(record)
    return kept


def plan_gene_summary(gene_curie: str | None) -> tuple[PlannedCall, ...]:
    """The Gene ESummary call that carries NCBI's plain-English description.

    Item 11.31 (2026-09-21). One call, not the search-then-summary pair the
    ClinVar and OMIM follow-ups use, because a resolved gene CURIE ALREADY
    HOLDS the uid: `NCBIGene:672` is Entrez gene 672. Planning an ESearch to
    rediscover an identifier the question already resolved would add a
    round trip and a second chance to resolve the wrong gene, which is the
    failure `filter_omim_titles` exists to undo for OMIM.

    WHY THIS EXISTS AT ALL, since a reader will reasonably ask why the
    product needs a gene record it already has a graph row for:
    `grounding.ground_claim` accepts a claim only on contiguous containment,
    so against long source text the gate permits quoting and forbids
    paraphrase. The product therefore cannot explain a record in its own
    words at any depth. NCBI's Gene ESummary `summary` field is the only
    plain-English explanatory prose NCBI publishes per gene, so quoting it
    is the one way a plain-language answer explains anything while every
    sentence keeps a source. Measured evidence:
    `testing/Developer/reports/2026-09-21_11.31_divergence/findings.md`.

    Returns an empty tuple for anything that is not an `NCBIGene:` CURIE
    with a positive integer uid, which is the planner's own signal to plan
    nothing rather than an error, matching `plan_first_stage`'s contract.
    """
    if not isinstance(gene_curie, str):
        return ()
    prefix, _, uid = gene_curie.strip().partition(":")
    if prefix.lower() != "ncbigene":
        return ()
    # Digits only, and non-zero: an Entrez uid is a positive integer, and a
    # value like "672abc" or "-1" is a malformed CURIE rather than a gene
    # this call should go and ask NCBI about.
    if not uid.isdigit() or int(uid) <= 0:
        return ()
    return (_summary_call("gene_summary", "gene", [uid]),)
