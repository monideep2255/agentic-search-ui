# Card 125, second attempt: the lead's full unit suite run

The lead ran CI gate 4's command (`pytest -m "not integration" -q -rs`) on `fix/card125-prompt-delimiter` at 348adb0b, 2026-10-17, on a loaded machine.

Result: `4 failed, 8438 passed, 143 skipped, 24 deselected, 1 xfailed, 7 warnings in 792.20s`.

## Findings

| Id | Severity | Finding | Worse than develop for a person |
|---|---|---|---|
| L-125b-01 | Major, blocks merge (CI gate 4 red) | Two tests compare two prompts built in separate calls byte for byte, and each call now draws its own random suffix, so they differ: `test_p1_the_default_depth_reaches_the_synth_prompt` and `test_p5_session_memory_never_reaches_the_synth_prompt` (the memory firewall test). Each must pin the suffix or compare with the suffix masked, so it still tests what it tested on develop: the firewall test must still go red if memory reaches the writer prompt | No: test only |
| L-125b-02 | Not a branch finding | `test_every_source_file_has_a_row` and `test_manifest_covers_every_source_file` failed on an untracked, gitignored copy `synthesis/findings 2.py` (created 14:05 in the builder's worktree, differs from develop's `findings.py` at line 78). It is not on the branch, so CI does not see it. The lead removes it with the worktree | No |
