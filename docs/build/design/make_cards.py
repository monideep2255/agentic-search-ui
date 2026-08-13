#!/usr/bin/env python3
"""Generate design-system component cards from the prototype.

A card is the isolated statement of one component, and it is what build phase
4.8's premise gate asserts against. Hand-authoring cards alongside a prototype
that keeps moving guarantees they drift, and a drifted fixture is worse than no
fixture, because it certifies the wrong thing.

So cards are generated. The prototype is the single source of truth for both
the behaviour and the components, and a card is a slice of it: the shared token
block, the component's own CSS rules, and markup lifted verbatim.

Usage:
    python3 docs/build/design/make_cards.py

Reads:
    design-system/prototype/app.html

Writes:
    design-system/<group>/<name>.html   for every card in CARDS below
"""

import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
PROTOTYPE = HERE / "design-system" / "prototype" / "app.html"
ROOT = HERE / "design-system"

# (path, group, title, note, css-class-prefixes, markup)
# Markup is written here rather than sliced by selector because a card shows a
# component in several states, which the running app never does at one moment.
CARDS = []


def add(path, group, title, note, prefixes, markup, width=880):
    CARDS.append((path, group, title, note, prefixes, markup, width))


add("components/persona.html", "Components", "Named scientist persona",
    "Technical specification 12.7 and 14.2. Presentation only: the persona never changes which tools run "
    "or what is asserted. A small static label and a muted icon, never an animated mascot or a cartoon "
    "avatar. Assignment is drawn once per anonymous session, or once per account for its lifetime. "
    "Wired in build phase 4.5.",
    ["persona", "pcap"],
    """<div class="panel"><p class="lbl">In the app bar, on navy</p>
<div style="background:var(--navy);border-radius:var(--r);padding:16px 18px">
  <span class="persona on-navy"><span class="pav">{ICON}</span>Working as <b>Mendel</b></span>
</div></div>

<div class="panel"><p class="lbl">On a light surface</p>
<span class="persona"><span class="pav">{ICON}</span>Working as <b>Franklin</b></span></div>

<div class="panel"><p class="lbl">The per-step caption, driven by the step's own narrative</p>
<div class="pcap"><span class="pav">{ICON}</span><span><b>Mendel</b> is checking the question is answerable and in scope</span></div>
<div class="pcap"><span class="pav">{ICON}</span><span><b>Mendel</b> is choosing which sources to read</span></div>
<div class="pcap"><span class="pav">{ICON}</span><span><b>Mendel</b> is reading the records</span></div>
<div class="pcap"><span class="pav">{ICON}</span><span><b>Mendel</b> is writing the answer, citing as it goes</span></div>
<p style="font-size:13px;color:var(--ink-muted);margin:14px 0 0;max-width:64ch">The caption is cleared the moment a run
finishes or is stopped, so a halted run never reads as still working.</p></div>""")

add("components/depth-control.html", "Components", "Audience depth control",
    "Technical specification 12.9. Three-way, mirroring Query.audience_depth exactly: clinical_brief, "
    "researcher as the default, deep_technical. Disabled once a run is mid-stream, because the depth a run "
    "was dispatched with is locked for that run, so Write never reconciles a depth change against tokens it "
    "has already streamed. Wired in build phase 4.5.",
    ["depth"],
    """<div class="panel" style="background:var(--navy);border-color:var(--navy)">
<p class="lbl" style="color:var(--ink-on-navy-mute)">On the landing hero, default state</p>
<div class="depthwrap" style="margin:0">
  <span class="dl">Answer depth</span>
  <div class="depth" role="group" aria-label="Audience-level depth">
    <button type="button">Clinical brief</button>
    <button type="button" class="on">Researcher</button>
    <button type="button">Deep technical</button>
  </div>
</div></div>

<div class="panel"><p class="lbl">Each selection</p>
<div style="display:flex;flex-direction:column;gap:10px;align-items:flex-start">
  <div class="depth"><button class="on">Clinical brief</button><button>Researcher</button><button>Deep technical</button></div>
  <div class="depth"><button>Clinical brief</button><button class="on">Researcher</button><button>Deep technical</button></div>
  <div class="depth"><button>Clinical brief</button><button>Researcher</button><button class="on">Deep technical</button></div>
</div></div>

<div class="panel"><p class="lbl">Locked, while a run is mid-stream</p>
<div class="depth"><button disabled>Clinical brief</button><button class="on" disabled>Researcher</button><button disabled>Deep technical</button></div>
<p style="font-size:13px;color:var(--ink-muted);margin:14px 0 0;max-width:64ch">Re-enabled when the run reaches an
answer, or is stopped.</p></div>""")

ICON = ('<svg width="12" height="12" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">'
        '<circle cx="8" cy="5.2" r="2.9"/><path d="M2.6 14a5.4 5.4 0 0 1 10.8 0z"/></svg>')

SHELL_CSS = """
.card-title{font-size:11px;letter-spacing:.14em;text-transform:uppercase;font-weight:700;color:var(--ink-faint);margin:0 0 4px}
.card-note{font-size:13px;color:var(--ink-muted);margin:0 0 20px;max-width:70ch}
.panel{background:var(--surface);border:1px solid var(--line);border-radius:var(--r);padding:20px;margin-bottom:16px}
.lbl{font-size:10.5px;letter-spacing:.1em;text-transform:uppercase;font-weight:700;color:var(--ink-faint);margin:0 0 14px}
body{padding:28px}
"""


def extract_tokens(source: str) -> str:
    match = re.search(r"(:root\{.*?\n\})", source, re.S)
    if match is None:
        sys.exit("error: token block not found in the prototype")
    return match.group(1) + "\n*{box-sizing:border-box}\n"


def extract_rules(source: str, prefixes) -> str:
    """Pull every top-level CSS rule whose selector mentions one of the prefixes."""
    style = re.search(r"<style>(.*?)</style>", source, re.S)
    if style is None:
        sys.exit("error: style block not found")
    body = style.group(1)
    out = []
    for selector, block in re.findall(r"([^{}]+)\{([^{}]*)\}", body):
        selector = selector.strip()
        if selector.startswith(("@", ":root")):
            continue
        if any(re.search(r"\.%s\b" % re.escape(p), selector) for p in prefixes):
            out.append("%s{%s}" % (selector, block.strip()))
    return "\n".join(out)


def main() -> None:
    if not PROTOTYPE.exists():
        sys.exit("error: %s does not exist" % PROTOTYPE)
    source = PROTOTYPE.read_text(encoding="utf-8")
    tokens = extract_tokens(source)

    for path, group, title, note, prefixes, markup, width in CARDS:
        rules = extract_rules(source, prefixes)
        if not rules:
            sys.exit("error: no CSS matched %r for %s" % (prefixes, path))
        page = (
            '<!-- @dsCard group="%s" width=%d -->\n'
            "<!doctype html>\n"
            '<html lang="en"><head><meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
            "<title>%s</title>\n"
            "<style>%s%s%s</style></head><body>\n"
            '<p class="card-title">%s</p>\n'
            '<p class="card-note">%s</p>\n'
            "%s\n</body></html>\n"
        ) % (group, width, title, tokens, SHELL_CSS, rules, title, note,
             markup.replace("{ICON}", ICON))

        target = ROOT / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(page, encoding="utf-8")
        print("  wrote %-34s (%d CSS rules, %s bytes)"
              % (path, rules.count("}"), format(len(page), ",")))


if __name__ == "__main__":
    main()
