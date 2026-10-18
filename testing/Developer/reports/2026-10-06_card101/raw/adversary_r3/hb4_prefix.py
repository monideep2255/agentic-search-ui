"""Card 101 round 3 adversary: hb4's recorded draft (diagnosis traces), the
branch with its copied cuts held. A sentence develop drops whole (a clause
stripped from its middle) becomes an end strip, and its first clause shows.
Then `drop_record_restatements`, which runs next in `core.graph`. No model.
Usage: python hb4_prefix.py <src> <hb4.jsonl> <approve: develop|none>
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, sys.argv[1])
from system_03_search_agent.synthesis import grounding as gr
from system_03_search_agent.synthesis.answer_layout import drop_record_restatements
from system_03_search_agent.synthesis.findings import SynthFinding

rows = [json.loads(x) for x in Path(sys.argv[2]).read_text().splitlines() if x.strip()]
rows = [r for r in rows if isinstance(r, dict) and "tag" in r]
frows = next(r["data"] for r in rows if r["tag"] == "FINDINGS")
fs = [SynthFinding(ref_index=int(f["ref"]), citation_id=f"c-{f['ref']}", layer="", tool=f.get("tool", ""),
                   field=f["field"], field_value=f["text"] or "", source_url=f.get("url", "")) for f in frows]
narr = next(r for r in rows if r["tag"] == "GROUNDING")["data"]["narrative"]
sentence = [s for s in gr._split_sentences(narr) if s.startswith("The name Adenoviral")][0]  # noqa: RUF015
q = "What causes bronchiolitis in babies, and how is it usually treated?"
sink = []
gr.run_grounding_pass(sentence, fs, True, q, (), None, sink)
res = gr.run_grounding_pass(sentence, fs, True, q, (), frozenset(), None)
after, dropped = drop_record_restatements(res, fs)
print(json.dumps({"sentence": sentence, "check_items": [c.sentence for c in sink],
                  "shown_after_grounding_no_approval": res.narrative,
                  "shown_after_restatement_drop": after.narrative, "restatements_dropped": dropped}))
