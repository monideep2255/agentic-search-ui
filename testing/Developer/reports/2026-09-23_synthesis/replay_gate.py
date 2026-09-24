"""Replay the grounding pass over captured live replies, offline.

`probe_gate_verdicts.py` saves the model's keyed reply, its quotes and every
finding it was given. This re-runs the CURRENT `run_grounding_pass` over them,
so a change to the gate is measured against real model output without
spending another live run. It prints, per capture, how many of the model's
sentences survive and the surviving prose itself.

Run from the repository root:
    PYTHONPATH=src python testing/Developer/reports/2026-09-23_synthesis/replay_gate.py
"""
import glob
import json
import pathlib

from system_03_search_agent.synthesis.findings import SynthFinding
from system_03_search_agent.synthesis.grounding import _split_sentences, run_grounding_pass

HERE = pathlib.Path(__file__).parent

for path in sorted(glob.glob(str(HERE / "probe_gate_verdicts" / "*.json"))):
    record = json.loads(pathlib.Path(path).read_text())
    if "findings" not in record:
        continue
    findings = [SynthFinding(**f) for f in record["findings"]]
    result = run_grounding_pass(
        record["reply_keyed"],
        findings,
        question=record.get("question_text", record["question"]),
        evidence_quotes=tuple(record["quotes"]),
    )
    written = len(_split_sentences(record["reply_keyed"]))
    print(f"##### {pathlib.Path(path).name}: {len(result.sentences)} of {written} sentences survive")
    for sentence in result.sentences:
        print("  -", sentence)


def why(record: dict) -> None:
    """Per clause: which of the four checks fails, under the CURRENT rules."""
    from system_03_search_agent.synthesis import grounding as g

    findings = {f["ref_index"]: SynthFinding(**f) for f in record["findings"]}
    quotes = record["quotes"]
    licensed = g._licensed_question_content(record.get("question_text", ""))
    labels_by_url: dict[str, str] = {}
    for f in findings.values():
        if f.field in g.LABEL_FIELDS:
            labels_by_url[f.source_url] = labels_by_url.get(f.source_url, "") + " " + f.field_value
    for sentence in _split_sentences(record["reply_keyed"]):
        segments = g._segments(sentence)
        for index, (text, marker, key) in enumerate(segments):
            claim = g._clean_claim(text)
            if marker is None or not g._asserts_something(claim):
                continue
            pairs = []
            if key is not None:
                pairs.append((quotes[key], findings[marker]))
            for later_text, later_marker, later_key in segments[index + 1 :]:
                if later_marker is None or g._asserts_something(g._clean_claim(later_text)):
                    break
                if later_key is not None:
                    pairs.append((quotes[later_key], findings[later_marker]))
            if not pairs:
                print(f"  [{marker}] no quote: {claim[:90]}")
                continue
            bad = [q for q, f in pairs if not g._quote_is_valid(q, f)]
            if bad:
                print(f"  [{marker}] quote not in record: {bad[0][:90]}")
                continue
            joined = " ".join(q for q, _ in pairs)
            ctx = " ".join(f"{f.curie} {f.entity_type}" for _, f in pairs)
            labels = " ".join(labels_by_url.get(f.source_url, "") for _, f in pairs)
            if not g.numbers_are_supported(claim, joined, licensed, record_context=ctx):
                print(f"  [{marker}] number: {claim[:90]}")
                continue
            if g._negates(claim) != any(g._negates(q) for q, _ in pairs):
                print(f"  [{marker}] polarity: {claim[:90]}")
                continue
            support = g.content_tokens(f"{joined} {labels} {ctx} {licensed}")
            allowed = g._stemmed(support) | g._stemmed(set(g._SYNTHESIS_VOCABULARY))
            extra = sorted(g._stemmed(g.content_tokens(claim)) - allowed)
            print(f"  [{marker}] {'PASS' if not extra else 'words ' + str(extra)}: {claim[:90]}")


for path in sorted(glob.glob(str(HERE / "probe_gate_verdicts" / "*.json"))):
    record = json.loads(pathlib.Path(path).read_text())
    if "findings" in record:
        print("#####", pathlib.Path(path).name)
        why(record)
