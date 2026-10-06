"""Do the key documents agree with each other, and can each rule fail?

`tracker/check_doc_sync.py` compares the board, the done file, the test
queries, the board plan, the Factory brief, the handoff and the registry with
each other. It exists because cards 44 and 47 stayed in To do after they
merged on 2026-10-06, while every per-file check stayed green. The product
owner chose that it runs at every `/phase-checkpoint` and before every push in
`/ship`, and blocks the push on a finding.

What this file pins down:

- The script's own `--self-test` and `--mutation-test` pass: its readers read
  what they should, a set of documents that agree gives no finding, and each
  rule reports the one disagreement its mutation adds and no other rule fires.
- A card marked ", part" in the retest list may stay in To do; the same card
  without the marker may not.
- A Queries cell that only quotes a question ("What does BRCA1 do?") names
  no query, so it is a finding; "none" is not.
- A Waiting on cell that says "Out of Factory's lane" does not give the card
  to Factory.
- A missing section exits 2, never 0, and so does a missing document.
- On the real repository the check runs in under 5 seconds and exits 0 or 1,
  never 2: every section it reads is there.

Every rule test builds its documents in memory from the script's own golden
set, so none depends on the state of this repository's real documents.
"""

from __future__ import annotations

import importlib.util
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TRACKER_DIR = REPO_ROOT / "tracker"


def _load(name: str):
    """Import a `tracker/` script by path; `tracker/` is not a package."""
    if str(TRACKER_DIR) not in sys.path:
        sys.path.insert(0, str(TRACKER_DIR))
    spec = importlib.util.spec_from_file_location(name, TRACKER_DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


sync = _load("check_doc_sync")


def _rules(texts: dict[str, str]) -> list[str]:
    return [f.rule for f in sync._golden_run(texts)]


def test_the_self_test_passes():
    assert sync.run_self_test() == 0


def test_the_mutation_test_passes_and_every_rule_has_an_arm():
    assert sync.run_mutation_test() == 0
    rules = {rule for _, _, rule in sync._mutations()}
    assert rules == {
        "card-in-one-place", "retest-names-query", "card-exists",
        "factory-lane", "handoff-agrees", "registry-paths",
    }


def test_the_golden_documents_agree():
    assert sync._golden_run(dict(sync.GOLDEN)) == []


def test_a_part_card_may_stay_in_to_do_but_a_whole_one_may_not():
    assert "card-in-one-place" not in _rules(dict(sync.GOLDEN))
    whole = sync._mutate(sync.DONE, "card 94, part (#158)", "card 94 (#158)")
    assert _rules(whole) == ["card-in-one-place"]


def test_a_quoted_question_is_not_a_query_number():
    texts = sync._mutate(sync.DONE, "| none, a design file |", '| the answer to "What does BRCA1 do?" |')
    assert _rules(texts) == ["retest-names-query"]


def test_none_says_there_is_no_query():
    texts = sync._mutate(sync.DONE, "| none, a design file |", "| no query, a design file |")
    assert _rules(texts) == []


def test_out_of_factorys_lane_does_not_give_a_card_to_factory():
    # Card 18's cell in the golden board reads "Out of Factory's lane", and it
    # has no section in the brief, yet the golden set is clean.
    assert "Out of Factory's lane" in sync.GOLDEN[sync.BOARD]
    assert "## Card 18" not in sync.GOLDEN[sync.FACTORY]
    assert _rules(dict(sync.GOLDEN)) == []


def test_a_finding_prints_file_line_rule_and_fix():
    texts = sync._mutate(sync.HANDOFF, "cards 24 and 18", "cards 24 and 17")
    (finding,) = sync._golden_run(texts)
    line = finding.format()
    assert line.startswith("HANDOFF.md:")
    assert ": handoff-agrees: card 17 is on no list" in line
    assert "Correct the number" in line


def test_a_missing_document_exits_2(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(sync, "REPO_ROOT", tmp_path)
    assert sync.main([]) == 2
    assert "cannot run" in capsys.readouterr().out


def test_a_missing_section_exits_2(tmp_path, monkeypatch, capsys):
    texts = sync._mutate(sync.DONE, sync.WAITING_HEADING, "## Somewhere else")
    for rel, text in texts.items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(text, encoding="utf-8")
    monkeypatch.setattr(sync, "REPO_ROOT", tmp_path)
    assert sync.main([]) == 2
    assert "Waiting for your retest" in capsys.readouterr().out


def test_an_unknown_argument_exits_2():
    assert sync.main(["--fix"]) == 2


def test_the_real_documents_are_read_in_under_five_seconds(capsys):
    started = time.monotonic()
    code = sync.main([])
    elapsed = time.monotonic() - started
    assert code in (0, 1), capsys.readouterr().out
    assert elapsed < 5
