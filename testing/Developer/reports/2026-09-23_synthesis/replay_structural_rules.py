"""Item 12.16 part 4: what do the structural rules drop from real model replies?

Replays the captured live replies in `probe_gate_verdicts/` through the
current grounding pass with the model check simulated as approving EVERY
candidate, once with the two structural rules on and once with each switched
off. So the difference printed is exactly what each rule removes, sentence by
sentence, on text the answer model actually wrote.

Run from the repository root:
    PYTHONPATH=src python testing/Developer/reports/2026-09-23_synthesis/replay_structural_rules.py
"""
import glob
import json
import pathlib

from system_03_search_agent.synthesis import grounding
from system_03_search_agent.synthesis.findings import SynthFinding

HERE = pathlib.Path(__file__).parent


def surviving(record: dict) -> tuple[str, ...]:
    findings = [SynthFinding(**f) for f in record["findings"]]
    kwargs = {
        "question": record.get("question_text", record["question"]),
        "evidence_quotes": tuple(record["quotes"]),
    }
    sink: list = []
    grounding.run_grounding_pass(record["reply_keyed"], findings, candidate_sink=sink, **kwargs)
    approved = frozenset(candidate.key for candidate in sink)
    result = grounding.run_grounding_pass(
        record["reply_keyed"], findings, verified_syntheses=approved, **kwargs
    )
    return result.sentences


def main() -> None:
    real_fragment = grounding._starts_inside_record_sentence
    real_names = grounding._names_its_record
    for path in sorted(glob.glob(str(HERE / "probe_gate_verdicts" / "*.json"))):
        record = json.loads(pathlib.Path(path).read_text())
        if "findings" not in record:
            continue
        on = surviving(record)
        grounding._starts_inside_record_sentence = lambda *a, **k: False
        no_fragment_rule = surviving(record)
        grounding._starts_inside_record_sentence = real_fragment
        grounding._names_its_record = lambda *a, **k: True
        no_switch_rule = surviving(record)
        grounding._names_its_record = real_names
        written = len(grounding._split_sentences(record["reply_keyed"]))
        print(f"##### {pathlib.Path(path).name}: {len(on)} of {written} shown with both rules on")
        for sentence in no_fragment_rule:
            if sentence not in on:
                print(f"  dropped as a record fragment: {sentence[:150]}")
        for sentence in no_switch_rule:
            if sentence not in on:
                print(f"  dropped for switching records unnamed: {sentence[:150]}")


main()
