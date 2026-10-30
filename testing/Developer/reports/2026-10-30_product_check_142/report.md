# Card 142: Ctrl-C on deployed develop

The lead ran the merged command line (`15363460`) against deployed develop on the night of 2026-10-30, signed in as a throwaway develop account in a scratch home folder, asking `Which diseases are associated with BRCA1?` and sending a real Ctrl-C to the process.

## Table of contents

- [Results](#results)
- [What it does not cover](#what-it-does-not-cover)

## Results

| Case | Exit | Time | What the person reads |
|---|---|---|---|
| One press, 4 s into the answer | 130 | 4.5 s | "s3: interrupted, stopping the run..." then "s3: the run was stopped at your request; the answer above is incomplete." |
| Two presses 0.3 s apart, 6 s in | 130 | under 7 s | The same two lines: the server confirmed the stop before the second press landed |

- Neither run printed "error: the run ended before a final answer was received", the line the card was about.
- No traceback in either run.

## What it does not cover

- A slow or failed stop confirmation, piped output and `--json` were proven against a local stub by the builder, the judge, the adversary and the fresh verifier (`testing/Developer/reports/2026-10-29_card142/`), not against develop.
- Open and named on the card: when the run finishes after the press but before the stop takes effect, the line says "the run had already finished", which is not quite true (the fresh verifier's finding 1); develop prints an error in the same case.
