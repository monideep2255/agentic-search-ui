"""Apply one mutation at a time, run the arm that should go red, restore the
file and prove it is byte-identical. Prints one line per mutation."""

import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = "/Users/anuradhachakraborti/Desktop/Tech Skills/agentic-search-ui"
SRC = ROOT + "/src/system_03_search_agent"
T = ROOT + "/tests/system_03_search_agent"

MUTATIONS = [
    ("M1 fold not applied", SRC + "/tools/cypher_query.py",
     "        _apply_fold(raw_row, shaped_rows, normalized_cypher, fold)\n",
     "        pass\n",
     T + "/tools/test_cypher_fold_templates.py::test_variant_rows_carry_their_conditions_and_disease_rows_are_cited"),
    ("M2 placeholder findings kept", SRC + "/core/graph.py",
     "    synth_findings, placeholder_findings_dropped = drop_placeholder_condition_findings(\n        synth_findings\n    )\n",
     "    synth_findings, placeholder_findings_dropped = synth_findings, 0\n",
     T + "/core/test_write_answer_structure.py::test_variant_records_become_a_variant_to_disease_table"),
    ("M3 organism not confirmed live", SRC + "/core/graph.py",
     "    taxon = await _confirmed_taxon_for_extraction(entities)\n",
     "    taxon = _taxon_for_extraction(entities)\n",
     T + "/core/test_think_disease_and_organism.py::test_an_organism_taxonomy_rejects_does_not_change_the_taxon"),
    ("M4 fallback gate restored", SRC + "/core/graph.py",
     "    if not model_resolution.curies:\n        fallback_taxon = await _confirmed_taxon_for_extraction(classification.entities)\n",
     "    if not model_resolution.curies and not model_resolution.unresolved_symbols:\n        fallback_taxon = await _confirmed_taxon_for_extraction(classification.entities)\n",
     T + "/core/test_think_disease_and_organism.py::test_the_fallback_runs_when_every_model_span_failed"),
    ("M5 template fallback never run", SRC + "/tools/cypher_query.py",
     "        candidates.append(template.fallback)\n",
     "        pass\n",
     T + "/tools/test_cypher_fold_templates.py::test_the_disease_genes_fallback_runs_only_when_the_gene_edge_is_empty"),
    ("M6 summary fold clause removed", SRC + "/synthesis/answer_layout.py",
     "    if not anchors:\n        return body + \".\"\n",
     "    return body + \".\"\n",
     T + "/synthesis/test_answer_layout.py::test_the_summary_counts_variants_and_their_distinct_linked_diseases"),
    ("M7 exact-title rule removed", SRC + "/core/graph.py",
     "    if exact:\n        curies = [f\"MedGen:{cid}\" for cid in exact]\n    else:\n",
     "    if False:\n        curies = [f\"MedGen:{cid}\" for cid in exact]\n    else:\n",
     T + "/core/test_think_disease_and_organism.py::test_an_exact_title_binds_that_record_alone"),
    ("M8 list suffix strip removed", SRC + "/tools/agtype.py",
     "        payload = _INNER_SUFFIX_PATTERN.sub(\"}\", payload)\n",
     "        pass\n",
     T + "/tools/test_cypher_fold_templates.py::test_variant_rows_carry_their_conditions_and_disease_rows_are_cited"),
    ("M9 retry removed", SRC + "/core/graph.py",
     "    if curie is None and not cacheable:\n",
     "    if False:\n",
     T + "/core/test_resolve_symbol_to_curie.py::test_transient_outage_is_never_cached_and_retries_on_the_next_call"),
]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


for name, path, old, new, test in MUTATIONS:
    original = Path(path).read_bytes()
    text = original.decode()
    assert text.count(old) == 1, f"{name}: anchor found {text.count(old)} times"
    Path(path).write_text(text.replace(old, new))
    try:
        run = subprocess.run([sys.executable, "-m", "pytest", test, "-q", "-p", "no:cacheprovider", "-x"],
                             capture_output=True, text=True, cwd=ROOT, check=False)
        verdict = "RED (arm caught it)" if run.returncode != 0 else "GREEN (arm did NOT catch it)"
    finally:
        Path(path).write_bytes(original)
    restored = sha(path) == hashlib.sha256(original).hexdigest()
    print(f"{name}: {verdict}; restored byte-identical: {restored}")
