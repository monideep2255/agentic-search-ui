"""Read-only: fetch Disease MedGen:C1321489 over the app's HTTPS client, show raw bytes."""
import binascii
import sys

from dotenv import load_dotenv

load_dotenv()  # values are never printed
sys.path.insert(0, "src")
from system_03_search_agent.tools import agtype
from system_03_search_agent.tools import graph_http_transport as t

captured = {}
orig_post = t._post
def spy(**kw):
    r = orig_post(**kw)
    captured["content"] = r.content
    captured["ctype"] = r.headers.get("content-type")
    captured["enc"] = r.encoding
    return r
t._post = spy
rows, _ = t.execute_cypher_over_http(
    cypher="MATCH (d:Disease {id: $id}) RETURN d",
    params={"id": "MedGen:C1321489"}, as_clause="(d agtype)")
raw = captured["content"]
i = raw.find(b"Muir")
print("content-type:", captured["ctype"], "| httpx encoding:", captured["enc"])
print("raw bytes around name:", raw[i:i+30])
print("hex:", binascii.hexlify(raw[i:i+30]).decode())
print("row type:", type(rows[0]["d"]).__name__)
print("row repr:", ascii(rows[0]["d"])[:400])
v = agtype.parse_agtype(rows[0]["d"]) if hasattr(agtype, "parse_agtype") else None
print("parsed:", ascii(v)[:400])
