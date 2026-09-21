import json
import sys

with open(sys.argv[1]) as handle:
    rows = [json.loads(l) for l in handle]
ok = 0
for i, r in enumerate(rows, 1):
    resolved = [e["curie"] for e in r["resolved"]]
    gck = "NCBIGene:2645" in resolved
    ok += gck
    print(i, "gck" if gck else "NO-GCK", f"{r['elapsed_s']}s", "err=" + str(r["error"])[:60],
          "spans=" + json.dumps(r["spans"]),
          "lookups=" + json.dumps([{k: v for k, v in l.items() if k != 'taxon'} for l in r["lookups"]]),
          "resolved=" + json.dumps(resolved), "cache_before=" + json.dumps(r["cache_before"]))
print("GCK resolved", ok, "of", len(rows))
