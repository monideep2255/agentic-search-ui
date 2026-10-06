import os
import pathlib
import subprocess
import sys

G = pathlib.Path("src/system_03_search_agent/synthesis/grounding.py")
GR = pathlib.Path("src/system_03_search_agent/core/graph.py")
LABELS = '" ".join(labels_by_url.get((c.source_url or "").strip(), "") for _, c in pairs)'
OLD_COND = """            if (
                not strict_ok
                and pairs
                and exact_synthesis_checks_pass(claim_text, pairs, licensed_question)
            ):"""
muts = {
 "M1_code_approves_again": [(G, "            synthesized = False\n",
     f"            synthesized = (not strict_ok and bool(pairs) and synthesis_is_supported_by(claim_text, pairs, licensed_question, {LABELS}))\n"),
     (G, OLD_COND, OLD_COND.replace("not strict_ok\n", "not strict_ok\n                and not synthesized\n"))],
 "M2_copies_go_to_check": [(G, OLD_COND, OLD_COND.replace("                not strict_ok\n                and pairs", "                pairs"))],
 "M3_collect_and_accept": [(G, "            synthesized = False\n",
     f"            synthesized = (candidate_sink is not None and not strict_ok and bool(pairs) and synthesis_is_supported_by(claim_text, pairs, licensed_question, {LABELS}))\n")],
 "M4_repair_skips_check": [(GR, "                repaired_grounding = await _ground_with_sentence_check(\n",
     "                repaired_grounding = await _card101_plain_ground(\n"),
     (GR, "\n\ndef _code_built_lines_will_cite(",
     "\n\nasync def _card101_plain_ground(narrative, findings, *, question, evidence_quotes, **_kwargs):\n    return run_grounding_pass(narrative, findings, core_ask_required=True, question=question, evidence_quotes=evidence_quotes)\n\n\ndef _code_built_lines_will_cite(")],
}
py = os.environ.get("PYTHON", sys.executable)
for name, edits in muts.items():
    saved = {p: p.read_text() for p, _, _ in edits}
    try:
        for p, old, new in edits:
            t = p.read_text(); assert t.count(old) == 1, (name, old[:50]); p.write_text(t.replace(old, new, 1))
        r = subprocess.run([py, "-m", "pytest", "-q", "--no-header", "-p", "no:cacheprovider",
                            "tests/system_03_search_agent/synthesis/test_check_every_rewording.py"],
                           capture_output=True, text=True, check=False)
        failed = [l.split("::")[1].split(" ")[0] for l in r.stdout.splitlines() if l.startswith("FAILED")]
        print(f"{name}: {r.stdout.strip().splitlines()[-1]}")
        for f in failed: print("   red:", f)
    finally:
        for p, t in saved.items(): p.write_text(t)
