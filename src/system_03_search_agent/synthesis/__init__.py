"""The Write step's deterministic half: Sections 8 and 9.

Build phase 2.2. The split this package exists to enforce is stated in
Section 8's opening line: the model writes narrative, and the harness
decides what counts as grounded, cited, and trustworthy. Nothing in here
asks a model anything.

Module map, one Section per module:

    findings.py    Section 8.1: the code-built findings list Synth is given,
                   and the prompt assembled around it.
    grounding.py   Section 8.2: deterministic cite-or-refuse. Parse markers,
                   resolve, normalize, exact-or-substring match, strip.
    trust.py       Section 8.3: risk tier, triangulation, the decision table,
                   answer-level aggregation.
    refuse.py      Section 8.4: the NCBI cross-database fallback link.

`core/graph.py`'s `write_node` is the only caller. It runs them in that
order, which is also the order Section 8 defines them in.
"""
