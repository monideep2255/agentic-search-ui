#!/usr/bin/env python3
"""Verify that a copied/adapted skill or agent has been cleaned for this repo.

Usage:
    python verify_adaptation.py <path-to-file>
    python verify_adaptation.py --recent      # all modified .claude/ files per git

Exit codes:
    0 = clean, ready to commit
    1 = issues found, see report
    2 = bad invocation

This is a text-grep check, not a semantic one. It catches the common drift
patterns when skills are copied from reference-repos/personal-os/ or similar
external repos. It will not catch everything, but it will catch the stuff
that took three hours of manual editing last time.
"""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]

STALE_PATHS = [
    "NIH/",
    "Forge/",
    "Learning/",
    "Automations/",
    "Brainstorming/",
    "Computercraft/",
    "personal-os-work/",
    "GROWTH_SYSTEM.md",
    "EXTENSIONS.md",
    "DEPENDENCIES.md",
]

WRONG_REPO_TERMS = [
    "GQuery",
    "gquery",
    "django-gquery",
    "USWDS",
    "NWS",
    "ai-digest",
    "book-builder",
    "meeting-notes",
    "Confluence",
    "chakrabortim2",
]

# tools/integrations this repo does not use
FOREIGN_TOOLS = [
    "Tavily",
    "Firecrawl",
    "Perplexity",
    "Gmail",
    "Jira",
    "Slack",
]

EMOJI_RE = re.compile(
    "["
    "\U0001f300-\U0001f5ff"
    "\U0001f600-\U0001f64f"
    "\U0001f680-\U0001f6ff"
    "\U0001f700-\U0001f77f"
    "\U0001f900-\U0001f9ff"
    "\U00002600-\U000026ff"
    "\U00002700-\U000027bf"
    "]"
)

EM_DASH_RE = re.compile(r"[\u2013\u2014]")  # en dash, em dash
BOLD_RE = re.compile(r"\*\*[^*\n]+\*\*")
HEADING_RE = re.compile(r"^#{1,6}\s+(.+?)\s*$", re.MULTILINE)


@dataclass
class Finding:
    category: str
    line_no: int
    snippet: str
    hint: str


@dataclass
class Report:
    path: Path
    findings: list[Finding] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.findings

    def add(self, category: str, line_no: int, snippet: str, hint: str) -> None:
        self.findings.append(Finding(category, line_no, snippet.strip(), hint))


def check_frontmatter(text: str, report: Report) -> None:
    if not text.startswith("---\n"):
        report.add("frontmatter", 1, "(missing)", "File must start with YAML frontmatter")
        return
    end = text.find("\n---\n", 4)
    if end < 0:
        report.add("frontmatter", 1, "(unterminated)", "Frontmatter block never closes")
        return
    block = text[4:end]
    if not re.search(r"^name:\s*\S+", block, re.MULTILINE):
        report.add("frontmatter", 1, "(no name)", "Add `name: <skill-name>`")
    desc_match = re.search(r"^description:\s*(.+)$", block, re.MULTILINE)
    if not desc_match:
        report.add("frontmatter", 1, "(no description)", "Add `description: <what + when>`")
    elif len(desc_match.group(1).strip()) < 20:
        report.add("frontmatter", 1, desc_match.group(0), "Description too short, explain when to use")


INLINE_CODE_RE = re.compile(r"`[^`\n]*`")


def _strip_code(line: str) -> str:
    """Remove backtick-wrapped spans so tokens quoted as examples are ignored."""
    return INLINE_CODE_RE.sub("", line)


def check_lines(text: str, report: Report) -> None:
    lines = text.splitlines()
    in_fence = False
    in_frontmatter = False
    for i, line in enumerate(lines, start=1):
        stripped = line.strip()
        if i == 1 and stripped == "---":
            in_frontmatter = True
            continue
        if in_frontmatter:
            if stripped == "---":
                in_frontmatter = False
            continue
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue

        # For path/term checks, strip backtick-wrapped spans so that tokens
        # quoted as examples ("`NIH/`") do not trip the scanner.
        scan = _strip_code(line)

        for bad in STALE_PATHS:
            if bad in scan:
                report.add("stale-path", i, line, f"Remove reference to {bad}")
        for term in WRONG_REPO_TERMS:
            if re.search(rf"\b{re.escape(term)}\b", scan):
                report.add("wrong-repo", i, line, f"Delete: {term} belongs to another repo")
        for tool in FOREIGN_TOOLS:
            if re.search(rf"\b{re.escape(tool)}\b", scan):
                report.add("foreign-tool", i, line, f"{tool} is not used in this repo")

        # Writing-style checks also skip backtick-wrapped spans so that
        # documentation examples like `**text**` or em dash examples do not
        # trip the scanner. Emoji check stays strict.
        if EM_DASH_RE.search(scan):
            report.add("writing-style", i, line, "Replace en/em dash with comma, period, or transition word")
        if BOLD_RE.search(scan):
            report.add("writing-style", i, line, 'Replace **bold** with "word:" format')
        if EMOJI_RE.search(line):
            report.add("writing-style", i, line, "Remove emoji (writing-style.md)")


def check_headings(text: str, report: Report) -> None:
    for m in HEADING_RE.finditer(text):
        heading = m.group(1)
        line_no = text[: m.start()].count("\n") + 1
        # title case heuristic: multiple capitalized words, excluding known proper nouns
        words = heading.split()
        if len(words) < 3:
            continue
        allowed = {
            "BioLink", "LinkML", "KGX", "ETL", "KG", "AGE", "PostgreSQL",
            "NCBI", "API", "APIs", "LLM", "AI", "ML", "RAG", "MCP", "SQL",
            "Claude", "Python", "Gene", "ClinVar", "MedGen", "PubMed", "SNP",
            "Taxonomy", "FastAPI", "LangGraph", "Neo4j", "MONDO",
        }
        cap_non_first = sum(
            1
            for w in words[1:]
            if w[0].isupper() and w.strip(",:;.") not in allowed
        )
        if cap_non_first >= 2:
            report.add(
                "writing-style",
                line_no,
                heading,
                "Sentence case headings: only first word + proper nouns capitalized",
            )


def check_pointers(text: str, target: Path, report: Report) -> None:
    """Flag references to .claude/agents/<x> or .claude/skills/<x> that do not exist."""
    claude_dir = REPO_ROOT / ".claude"
    if not claude_dir.exists():
        return
    existing_agents = {p.stem for p in (claude_dir / "agents").glob("*.md")}
    existing_skills = {p.name for p in (claude_dir / "skills").iterdir() if p.is_dir()}

    # look for backtick-wrapped slash-commands and table-row agent/skill names
    slash_cmds = re.finditer(r"`/([a-z][a-z0-9-]*)`", text)
    for m in slash_cmds:
        name = m.group(1)
        if name in existing_skills:
            continue
        # allow common built-ins and self-reference
        if name in {"bossman", "objective-review", "ship", "repo-dive", "skill-adapt-verify"}:
            continue
        line_no = text[: m.start()].count("\n") + 1
        report.add(
            "broken-pointer",
            line_no,
            m.group(0),
            f"No skill named '{name}' in .claude/skills/",
        )

    # look for agent table rows like `| agent-name |` (rough heuristic)
    for i, line in enumerate(text.splitlines(), start=1):
        if not line.strip().startswith("|"):
            continue
        first_col = line.split("|")[1].strip().strip("`")
        if not first_col or " " in first_col or first_col in {"Agent", "Skill", "---", "Doc", "Rule"}:
            continue
        if first_col.startswith("-") or first_col.startswith(":"):
            continue
        # only flag if it looks like a kebab-case identifier
        if re.fullmatch(r"[a-z][a-z0-9-]*", first_col):
            if first_col not in existing_agents and first_col not in existing_skills:
                # self-reference is OK
                if first_col == target.stem:
                    continue
                report.add(
                    "broken-pointer",
                    i,
                    line,
                    f"'{first_col}' is not an existing agent or skill",
                )


def verify(path: Path) -> Report:
    report = Report(path=path)
    if not path.exists():
        report.add("io", 0, str(path), "File does not exist")
        return report
    text = path.read_text(encoding="utf-8")
    check_frontmatter(text, report)
    check_lines(text, report)
    check_headings(text, report)
    check_pointers(text, path, report)
    return report


def recent_targets() -> list[Path]:
    try:
        out = subprocess.check_output(
            ["git", "-C", str(REPO_ROOT), "diff", "--name-only", "HEAD"],
            text=True,
        )
    except subprocess.CalledProcessError:
        return []
    paths: list[Path] = []
    for line in out.splitlines():
        if line.startswith(".claude/") and line.endswith(".md"):
            p = REPO_ROOT / line
            if p.exists():
                paths.append(p)
    return paths


def print_report(report: Report) -> None:
    rel = report.path.relative_to(REPO_ROOT) if report.path.is_absolute() else report.path
    if report.ok:
        print(f"OK  {rel}")
        return
    print(f"FAIL {rel}  ({len(report.findings)} issues)")
    by_cat: dict[str, list[Finding]] = {}
    for f in report.findings:
        by_cat.setdefault(f.category, []).append(f)
    for cat, items in sorted(by_cat.items()):
        print(f"  [{cat}] {len(items)}")
        for f in items[:10]:
            print(f"    L{f.line_no}: {f.snippet[:100]}")
            print(f"           -> {f.hint}")
        if len(items) > 10:
            print(f"    ... and {len(items) - 10} more")


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    if argv[1] == "--recent":
        targets = recent_targets()
        if not targets:
            print("No modified .claude/ files to check.")
            return 0
    else:
        targets = [Path(argv[1]).resolve()]
    failures = 0
    for t in targets:
        report = verify(t)
        print_report(report)
        if not report.ok:
            failures += 1
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
