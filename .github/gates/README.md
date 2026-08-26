# Gate scripts

One script per Section 24 gate. The CI workflow does not contain shell code any
more: each gate step is exactly one token, the path to the script below it runs.

## Why this exists, rather than shell inline in the workflow

Build phase 4.14 tried twice to verify inline shell by matching strings in the
`run:` body, and was defeated twice. The second defeat is the one that forced
this rework, and it is worth stating precisely because it is not obvious:

    run: ":;#ruff check"

That runs NOTHING. Bash starts a comment at `#` whenever `#` begins a word, and
`;` ends a word, so the whole command is commented out. A checker that strips
comments only where `#` follows WHITESPACE sees `ruff check` and reports the
gate as present and correct. Eight of the ten gates were neutralised this way
with all 97 premise tests still green, including the mutation harness whose job
is to prove those tests can fail.

The lesson is not "handle `;#` too". That is the fifth instance of a class, and
the sixth was always going to be `&&#`, `(#`, a YAML block scalar, or something
nobody had thought of. Matching substrings inside arbitrary shell is the thing
that cannot be made safe.

## What replaces it

Two properties, both cheap to check and neither requiring a shell parser:

- A gate step's `run:` body must EQUAL the path of its script. Not contain it,
  equal it. There is no room in a whole-string equality for a comment, a
  separator, or a second command.
- Each script is CANONICAL: a shebang, `set -euo pipefail`, comments, and
  exactly one executable line, which must match its expected command anchored
  at both ends. A `:;#` prefix is a different line and fails the match.

The attack surface shrinks from "arbitrary multi-line shell embedded in YAML"
to "one anchored line in a file that must also be executable".

## And the property text can never prove

Whether a gate actually goes RED when the thing it guards is broken is
behavioural, and no amount of reading proves it. `tests/ci/test_gate_scripts.py`
executes the cheap gates against deliberately broken fixtures and asserts a
non-zero exit. Which gates are covered that way, and which are not, is stated in
that file rather than left to be discovered.
