"""Was the completeness repair's reply the one the reader got?

For each local trace, the written prose of the final answer (between the
code-built opening line and the first listing heading or note) is split into
sentences, citation markers removed, and each sentence is looked for in the
first writer reply and in the repair's reply. A sentence found only in the
repair's reply means the repair was kept. Output: repair_kept_output.txt.
"""
import json
import re
from pathlib import Path

here = Path(__file__).parent


def norm(s):
    s = re.sub(r"\[\d+(?::[^\]]*)?\]", "", s)
    s = re.sub(r"[^a-z0-9%.]+", " ", s.lower())
    return s.strip()


lines = []
for f in sorted((here / "local_traces").glob("G-*.json")):
    d = json.loads(f.read_text())
    synth = [m for m in d["rec"]["model"] if m["role"] == "synth"]
    replies = [norm(m.get("reply") or "") for m in synth]
    paras = [p.strip() for p in d["answer_text"].split("\n\n") if p.strip()]
    prose = []
    for p in paras[1:]:
        if p.endswith("records found") or p.startswith("Note:"):
            break
        prose.append(p)
    sents = [s for s in re.split(r"(?<=[.])\s+", " ".join(prose)) if len(norm(s)) > 25]
    in1 = sum(1 for s in sents if norm(s)[:60] in replies[0])
    in2 = sum(1 for s in sents if len(replies) > 1 and norm(s)[:60] in replies[1])
    only2 = sum(1 for s in sents if len(replies) > 1 and norm(s)[:60] in replies[1] and norm(s)[:60] not in replies[0])
    verdict = "no written prose shipped" if not sents else ("repair reply shipped" if only2 else "first reply shipped")
    lines.append(f"{d['id']}: prose sentences {len(sents)}, found in reply 1: {in1}, in repair reply: {in2}, only in repair: {only2} -> {verdict}; "
                 f"repair seconds {synth[1]['dur'] if len(synth) > 1 else None}")
(here / "repair_kept_output.txt").write_text("\n".join(lines) + "\n")
print("\n".join(lines))
