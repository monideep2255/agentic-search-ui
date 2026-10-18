"""Replay saved develop streams through the web client's pacing and reveal.

Card 58. For each saved stream, report in seconds after the question was
sent:

- first token: when the answer's first sentence ARRIVED;
- first trust signal: when Stop went grey before card 58, which switched it
  off at the first `trust_signal`; it arrives after the first token, in the
  same burst, so it is not early;
- server done: when `done` arrived;
- writing banner: when the paced screen enters Write;
- first word: when the first answer sentence is on screen;
- grey with nothing to read: first word shown minus first trust signal,
  floored at 0.

The rules are copied from the client, by value:
`frontend/src/hooks/usePacedEvents.ts` (`PACING`, `dwellAfter`, the release
formula and `maxLagFor`) and `frontend/src/hooks/useAnswerReveal.ts`
(`REVEAL_TIMING.minBannerMs`). The saved record keeps no plan payload, so
the helper count is the number of `tool_start` frames, one per planned call.

Usage: python pacing_replay.py <folder holding dev_*.json>
"""

import glob
import json
import sys
from pathlib import Path

GUARD_MS, THINK_MS, PLAN_MS = 0.6, 0.7, 0.7
HELPER_GAP_MS, HANDOFF_MS = 0.9, 0.9
BASE_MAX_LAG, PER_HELPER_LAG = 3.2, 1.9
MIN_BANNER = 1.5


def dwell(event: dict, following: dict) -> float:
    kind = event["type"]
    if kind == "guard":
        return GUARD_MS
    if kind == "think":
        return THINK_MS
    if kind == "plan":
        return PLAN_MS
    if kind == "tool_start":
        return HELPER_GAP_MS if following["type"] == "tool_start" else HANDOFF_MS
    if kind == "tool_result":
        return HELPER_GAP_MS if following["type"] == "tool_result" else 0.0
    return 0.0


def replay(path: Path) -> dict:
    record = json.loads(path.read_text())
    events = [e for e in record["events"] if e["type"] != "step"]  # the client drops `step`
    helpers = sum(1 for e in events if e["type"] == "tool_start")
    max_lag = BASE_MAX_LAG + max(0, helpers - 1) * PER_HELPER_LAG
    released: list[float] = []
    for index, event in enumerate(events):
        arrival = event["arrive_s"]
        earliest = arrival if index == 0 else released[-1] + dwell(events[index - 1], event)
        released.append(min(max(arrival, earliest), arrival + max_lag))
    done_at = next(e["arrive_s"] for e in events if e["type"] == "done")
    trust_at = next(e["arrive_s"] for e in events if e["type"] == "trust_signal")
    last_result = max(i for i, e in enumerate(events) if e["type"] == "tool_result")
    banner = released[last_result]
    first_token = next(i for i, e in enumerate(events) if e["type"] == "token")
    first_word = max(released[first_token], banner + MIN_BANNER)
    token_at = next(e["arrive_s"] for e in events if e["type"] == "token")
    return {
        "id": record["id"],
        "helpers": helpers,
        "token": token_at,
        "done": done_at,
        "trust": trust_at,
        "banner": banner,
        "first_word": first_word,
        "grey": max(0.0, first_word - trust_at),
    }


def main(folder: str) -> None:
    print(
        "| Run | Helpers | First token arrived | First trust signal, Stop greyed | "
        "Server done | Writing banner shown | First word shown | Grey with nothing to read |"
    )
    print("|---|---|---|---|---|---|---|---|")
    for path in sorted(glob.glob(str(Path(folder) / "dev_*.json"))):
        r = replay(Path(path))
        print(
            f"| {r['id']} | {r['helpers']} | {r['token']:.2f} | {r['trust']:.2f} | {r['done']:.2f} | "
            f"{r['banner']:.2f} | {r['first_word']:.2f} | {r['grey']:.2f} |"
        )


if __name__ == "__main__":
    main(sys.argv[1])
