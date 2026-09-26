"""The REST card says a stream is "Resumable after a dropped connection".
Re-open a finished guest run's event stream with Last-Event-ID and count what
comes back. No new run is started, so no question is spent."""
import json
import urllib.request

import live_lib as L

tok = L.token("guest")
run_id = json.loads((L.EVIDENCE / "rest_04_tell.json").read_text())["run_id"]
out = {}
for label, headers in (("full replay", {}), ("after Last-Event-ID 0", {"Last-Event-ID": "0"})):
    req = urllib.request.Request(f"{L.API}/v1/query/{run_id}/events",
                                 headers={"Authorization": f"Bearer {tok}", "Accept": "text/event-stream", **headers})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            ids = [ln.decode().strip()[3:].strip() for ln in resp if ln.startswith(b"id:")]
        out[label] = {"status": 200, "ids": ids}
    except urllib.error.HTTPError as exc:
        out[label] = {"status": exc.code, "body": exc.read().decode(errors="replace")[:200]}
    print(label, out[label])
L.save("rest_resume_probe", {"run": "rest_04_tell (black holes, 2 events)", **out})
