#!/usr/bin/env python3
"""Render tracker/BOARD.md into the kanban views.

BOARD.md is the source of truth. This script is the only thing that writes
board.html, so the two can never drift by hand.

Depends on:
    - tracker/BOARD.md (parsed; the nine-column build table and the planning table)

Writes:
    - tracker/board.html      standalone page, opens in a browser with no server
    - tracker/board.body.html fragment for publishing as an artifact

Usage:
    python3 tracker/render_board.py            render both views
    python3 tracker/render_board.py --check    parse and report, write nothing

Exits non-zero on a malformed board, because a board that silently drops a
phase is worse than one that refuses to render.
"""

from __future__ import annotations

import html
import json
import re
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BOARD_MD = ROOT / "BOARD.md"
OUT_PAGE = ROOT / "board.html"
OUT_BODY = ROOT / "board.body.html"

# Flow order. Left to right is the direction work travels. "rejected" is
# deliberately absent: it is transient and routes straight back to in-progress.
COLUMNS = [
    ("todo", "To do", "var(--todo)"),
    ("in-progress", "In progress", "var(--active)"),
    ("blocked", "Blocked", "var(--blocked)"),
    ("in-review", "In review", "var(--accent)"),
    ("done", "Done", "var(--done)"),
]
KNOWN_STATUSES = {key for key, _, _ in COLUMNS} | {"rejected"}


@dataclass
class Phase:
    id: str
    group: str
    status: str
    title: str
    body: str
    deps: list[str] = field(default_factory=list)
    gates: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)
    po: bool = False


class BoardError(Exception):
    """The board is malformed. Refuse to render rather than hide a phase."""


def split_row(line: str) -> list[str]:
    return [cell.strip().strip("`") for cell in line.strip().strip("|").split("|")]


def csv_cell(cell: str) -> list[str]:
    if not cell or cell.lower() in {"none", "n/a", "-"}:
        return []
    return [part.strip() for part in cell.split(",") if part.strip()]


def find_table(lines: list[str], heading: str) -> list[list[str]]:
    """Return the data rows of the first markdown table under `heading`."""
    try:
        start = next(i for i, ln in enumerate(lines) if ln.strip().lower() == heading.lower())
    except StopIteration:
        raise BoardError(f"heading not found: {heading}")

    rows: list[list[str]] = []
    seen_table = False
    for line in lines[start + 1:]:
        stripped = line.strip()
        if stripped.startswith("##"):
            break
        if not stripped.startswith("|"):
            if seen_table:
                break
            continue
        seen_table = True
        cells = split_row(stripped)
        if all(set(c) <= set("-: ") for c in cells):  # separator row
            continue
        rows.append(cells)

    if not rows:
        raise BoardError(f"no table rows under {heading}")
    return rows[1:]  # drop the header row


def parse_board(md: str) -> dict:
    lines = md.splitlines()

    phases: list[Phase] = []

    for cells in find_table(lines, "## Planning phases"):
        if len(cells) < 4:
            raise BoardError(f"planning row needs 4 columns, got {len(cells)}: {cells}")
        pid, delivered, status, closed = cells[0], cells[1], cells[2], cells[3]
        if status not in KNOWN_STATUSES:
            raise BoardError(f"unknown status {status!r} on planning phase {pid}")
        phases.append(Phase(
            id=pid, group="planning", status=status,
            title=delivered.split(",")[0].strip(),
            body=f"{delivered}. Closed {closed}." if closed else delivered,
        ))

    for cells in find_table(lines, "## Build phases"):
        if len(cells) != 9:
            raise BoardError(
                f"build row needs 9 columns, got {len(cells)}. "
                f"Keep the column order documented in BOARD.md. Row: {cells[:2]}"
            )
        pid, branch, delivers, deps, group, status, owner, gates, flags = cells
        if status not in KNOWN_STATUSES:
            raise BoardError(f"unknown status {status!r} on phase {pid}")
        if group not in {"prototype", "v1"}:
            raise BoardError(f"unknown group {group!r} on phase {pid}")
        title = branch.split("-", 1)[1].replace("-", " ") if "-" in branch else branch
        phases.append(Phase(
            id=pid, group=group, status=status,
            title=title[:1].upper() + title[1:],
            body=delivers,
            deps=csv_cell(deps),
            gates=csv_cell(gates),
            flags=csv_cell(flags),
            po=owner.strip().lower() == "product owner",
        ))

    seen: set[str] = set()
    for p in phases:
        if p.id in seen:
            raise BoardError(f"duplicate phase id {p.id}")
        seen.add(p.id)

    open_flags = []
    for cells in find_table(lines, "## Open flags"):
        if len(cells) >= 3:
            open_flags.append({"flag": cells[0], "detail": cells[1], "before": cells[2]})

    m = re.search(r"^Last updated:\s*(.+?)\.?$", md, re.MULTILINE)
    updated = m.group(1).strip() if m else "unknown"

    return {"phases": phases, "open_flags": open_flags, "updated": updated}


def counts(phases: list[Phase]) -> dict:
    by_status = {key: sum(1 for p in phases if p.status == key) for key, _, _ in COLUMNS}
    return {
        "by_status": by_status,
        "planning_done": sum(1 for p in phases if p.group == "planning" and p.status == "done"),
        "planning_total": sum(1 for p in phases if p.group == "planning"),
        "proto_done": sum(1 for p in phases if p.group == "prototype" and p.status == "done"),
        "proto_total": sum(1 for p in phases if p.group == "prototype"),
        "v1_done": sum(1 for p in phases if p.group == "v1" and p.status == "done"),
        "v1_total": sum(1 for p in phases if p.group == "v1"),
        "flagged": sum(len(p.flags) for p in phases),
        "po": sum(1 for p in phases if p.po),
    }


def pct(done: int, total: int) -> int:
    return round(100 * done / total) if total else 0


def esc(s: str) -> str:
    return html.escape(s, quote=True)


CSS = (ROOT / "board.css").read_text(encoding="utf-8") if (ROOT / "board.css").exists() else ""


def render_body(data: dict) -> str:
    phases: list[Phase] = data["phases"]
    c = counts(phases)
    payload = json.dumps([asdict(p) for p in phases], indent=None, separators=(",", ":"))
    cols = json.dumps([{"key": k, "label": l, "tone": t} for k, l, t in COLUMNS])

    stats = [
        ("todo", "To do", c["by_status"]["todo"], "phases not started"),
        ("active", "In progress", c["by_status"]["in-progress"], "in flight"),
        ("blocked", "Blocked", c["by_status"]["blocked"], "hard blockers"),
        ("review", "In review", c["by_status"]["in-review"], "awaiting the judge"),
        ("done", "Done", c["by_status"]["done"], "closed"),
        ("", "Open flags", c["flagged"], "resolve before their phase"),
    ]
    stat_html = "\n".join(
        f'    <div class="stat"{f" data-tone={tone}" if tone else ""}>\n'
        f'      <span class="stat-label">{esc(label)}</span>\n'
        f'      <span class="stat-value">{value}</span>\n'
        f'      <span class="stat-note">{esc(note)}</span>\n'
        f'    </div>'
        for tone, label, value, note in stats
    )

    meters = [
        ("Planning", c["planning_done"], c["planning_total"], "var(--done)"),
        ("Prototype &middot; step 6.1", c["proto_done"], c["proto_total"], "var(--active)"),
        ("v1 &middot; step 6.3", c["v1_done"], c["v1_total"], "var(--accent)"),
    ]
    meter_html = "\n".join(
        f'    <div class="meter-row">\n'
        f'      <div class="meter-head"><span>{label}</span>'
        f'<span><b>{done}</b> of <b>{total}</b> phases</span></div>\n'
        f'      <div class="meter-track"><div class="meter-fill" '
        f'style="width:{pct(done, total)}%;background:{tone}"></div></div>\n'
        f'    </div>'
        for label, done, total, tone in meters
    )

    flag_rows = "\n".join(
        f"          <tr><td>{esc(f['flag'])}</td><td>{esc(f['detail'])}</td>"
        f"<td class=\"when\">{esc(f['before'])}</td></tr>"
        for f in data["open_flags"]
    ) or '          <tr><td colspan="3">No open flags.</td></tr>'

    return TEMPLATE.format(
        css=CSS,
        updated=esc(data["updated"]),
        total_phases=len(phases),
        stat_html=stat_html,
        meter_html=meter_html,
        flag_rows=flag_rows,
        payload=payload,
        cols=cols,
    )


TEMPLATE = """<title>System 3 build board</title>

<style>
{css}</style>

<div class="wrap">

  <header class="masthead">
    <div class="eyebrow">System 3 &middot; agentic search</div>
    <h1>Build board</h1>
    <p class="standfirst">Every phase between a locked specification and a running biomedical
      search agent. Phases, dependencies, and gates come from the technical specification,
      section 25. This page is generated from tracker/BOARD.md and is never hand-edited.</p>
    <div class="stamp">
      <span>Updated {updated}</span>
      <span>{total_phases} phases</span>
      <span>Source: tracker/BOARD.md</span>
    </div>
  </header>

  <section class="summary" aria-label="Status counts">
{stat_html}
  </section>

  <section class="meters" aria-label="Progress">
{meter_html}
  </section>

  <div class="toolbar">
    <div class="controls" role="group" aria-label="Filter phases">
      <button class="filter" data-filter="all" aria-pressed="true">All phases</button>
      <button class="filter" data-filter="planning" aria-pressed="false">Planning</button>
      <button class="filter" data-filter="prototype" aria-pressed="false">Prototype</button>
      <button class="filter" data-filter="v1" aria-pressed="false">v1</button>
      <button class="filter" data-filter="flagged" aria-pressed="false">Open flags only</button>
      <button class="filter" data-filter="po" aria-pressed="false">Needs you</button>
    </div>
    <div class="legend">
      <span><i class="chip dep">1.0</i> depends on</span>
      <span><i class="chip gate">gate</i> must pass before ship</span>
      <span><i class="chip po">product owner</i> a human decides, not an agent</span>
      <span><i class="chip flag">flag</i> unresolved, blocks that phase</span>
    </div>
  </div>

  <div class="board-section">
    <p class="orphan-warning" id="orphanWarning" role="status" hidden></p>
    <div class="flow-note">
      <span>Work moves left to right</span>
      <span class="flow-rule" aria-hidden="true"></span>
      <span class="flow-arrow" aria-hidden="true">&#9656;</span>
    </div>
    <div class="board-scroll">
      <div class="board" id="board"></div>
    </div>
  </div>

  <section>
    <h2>Open flags</h2>
    <div class="table-scroll">
      <table>
        <thead>
          <tr><th>Flag</th><th>Why it matters</th><th>Resolve before</th></tr>
        </thead>
        <tbody>
{flag_rows}
        </tbody>
      </table>
    </div>
  </section>

  <footer>
    <span>Generated from tracker/BOARD.md by tracker/render_board.py. Edit the markdown,
      never this page.</span>
    <span>Statuses follow the board's single-writer rule: a builder may set in progress,
      blocked, or in review, and only the judge sets done.</span>
  </footer>

</div>

<script>
  var PHASES = {payload};
  var COLUMNS = {cols};
  var activeFilter = "all";

  function matches(p) {{
    if (activeFilter === "all") return true;
    if (activeFilter === "flagged") return p.flags.length > 0;
    if (activeFilter === "po") return p.po === true;
    return p.group === activeFilter;
  }}

  function el(tag, cls, text) {{
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined) n.textContent = text;
    return n;
  }}

  function makeCard(p, tone) {{
    var card = el("article", "card");
    card.style.setProperty("--card-tone", tone);
    var top = el("div", "card-top");
    top.appendChild(el("span", "phase-id", p.id));
    top.appendChild(el("span", "group-tag", p.group));
    card.appendChild(top);
    card.appendChild(el("div", "card-title", p.title));
    card.appendChild(el("p", "card-body", p.body));
    var chips = el("div", "chips");
    p.deps.forEach(function (d) {{ chips.appendChild(el("span", "chip dep", d)); }});
    if (p.po) chips.appendChild(el("span", "chip po", "product owner"));
    p.gates.forEach(function (g) {{ chips.appendChild(el("span", "chip gate", g)); }});
    p.flags.forEach(function (f) {{ chips.appendChild(el("span", "chip flag", f)); }});
    if (chips.children.length) card.appendChild(chips);
    return card;
  }}

  function render() {{
    var board = document.getElementById("board");
    board.textContent = "";

    // A status with no column would vanish silently, which is the one thing a
    // board must never do. Surface it instead.
    var known = COLUMNS.map(function (c) {{ return c.key; }});
    var orphans = PHASES.filter(function (p) {{ return known.indexOf(p.status) === -1; }});
    var warn = document.getElementById("orphanWarning");
    if (orphans.length) {{
      warn.hidden = false;
      warn.textContent = orphans.length + " phase(s) carry a status with no column: " +
        orphans.map(function (p) {{ return p.id + " (" + p.status + ")"; }}).join(", ") +
        ". Fix the board definition; nothing may be hidden.";
    }} else {{
      warn.hidden = true;
    }}

    COLUMNS.forEach(function (col) {{
      var items = PHASES.filter(function (p) {{ return p.status === col.key && matches(p); }});
      var wrap = el("section", "col");
      wrap.style.setProperty("--col-tone", col.tone);
      var head = el("div", "col-head");
      head.appendChild(el("span", "dot"));
      head.appendChild(el("h2", "col-title", col.label));
      head.appendChild(el("span", "col-count", String(items.length)));
      wrap.appendChild(head);
      var cards = el("div", "cards");
      if (items.length === 0) {{
        cards.appendChild(el("div", "empty", "Nothing here"));
      }} else {{
        items.forEach(function (p) {{ cards.appendChild(makeCard(p, col.tone)); }});
      }}
      wrap.appendChild(cards);
      board.appendChild(wrap);
    }});
  }}

  Array.prototype.forEach.call(document.querySelectorAll(".filter"), function (btn) {{
    btn.addEventListener("click", function () {{
      activeFilter = btn.dataset.filter;
      Array.prototype.forEach.call(document.querySelectorAll(".filter"), function (b) {{
        b.setAttribute("aria-pressed", String(b === btn));
      }});
      render();
    }});
  }});

  render();
</script>
"""

STANDALONE_HEAD = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>System 3 build board</title>
<style>
  *, *::before, *::after { box-sizing: border-box; }
  html, body { margin: 0; padding: 0; }
  h1, h2, p, table { margin: 0; }
  button { font: inherit; }
  .theme-toggle {
    position: fixed; top: 16px; right: 16px; z-index: 10;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 11px; letter-spacing: .08em; text-transform: uppercase;
    padding: 7px 13px; border-radius: 999px; cursor: pointer;
    background: var(--surface); color: var(--muted); border: 1px solid var(--line);
  }
  .theme-toggle:hover { color: var(--ink); }
</style>
</head>
<body>
<button class="theme-toggle" id="themeToggle" type="button">Theme</button>
"""

STANDALONE_FOOT = """<script>
  (function () {
    var root = document.documentElement;
    var btn = document.getElementById("themeToggle");
    btn.addEventListener("click", function () {
      var now = root.getAttribute("data-theme");
      if (!now) {
        now = window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
      }
      root.setAttribute("data-theme", now === "dark" ? "light" : "dark");
    });
  })();
</script>
</body>
</html>
"""


def main(argv: list[str]) -> int:
    check_only = "--check" in argv

    if not BOARD_MD.exists():
        print(f"error: {BOARD_MD} not found", file=sys.stderr)
        return 2

    try:
        data = parse_board(BOARD_MD.read_text(encoding="utf-8"))
    except BoardError as exc:
        print(f"error: malformed board, refusing to render.\n  {exc}", file=sys.stderr)
        return 1

    phases = data["phases"]
    c = counts(phases)
    body = render_body(data)

    flag_count_in_table = len(data["open_flags"])
    if c["flagged"] != flag_count_in_table:
        print(
            f"error: {c['flagged']} flag(s) on phases but {flag_count_in_table} row(s) in the "
            f"Open flags table. They must reconcile, or the summary count lies.",
            file=sys.stderr,
        )
        return 1

    summary = (
        f"{len(phases)} phases | "
        + " ".join(f"{label.lower()}={c['by_status'][key]}" for key, label, _ in COLUMNS)
        + f" | flags={c['flagged']} needs-you={c['po']}"
    )

    if check_only:
        print(f"ok: {summary}")
        return 0

    OUT_BODY.write_text(body, encoding="utf-8")
    OUT_PAGE.write_text(STANDALONE_HEAD + body + STANDALONE_FOOT, encoding="utf-8")
    print(f"rendered: {summary}")
    print(f"  {OUT_PAGE.relative_to(ROOT.parent)}")
    print(f"  {OUT_BODY.relative_to(ROOT.parent)}  (publish this one as the artifact)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
