# Card 99 live proof on develop

Run 2026-10-06 against the deployed develop API, guest sessions, no sign-in, nothing written to the repository. The raw answers (event logs, links and citation records) were kept outside the repository, because record text can carry personal names and addresses; this summary quotes what each run showed.

## Table of contents

- [Deploy check](#deploy-check)
- [Method](#method)
- [The 12 runs](#the-12-runs)
- [Done-when lines](#done-when-lines)
- [Quotes for the failures](#quotes-for-the-failures)
- [Spend](#spend)

## Deploy check

- Health: `{"status":"ok","app_env":"develop"}`.
- `gh run list --branch develop`: CI for the merge of #184 completed with success at 18:33Z.
- Railway deployments for the develop project: both services (API and the second service) show SUCCESS for commit f8802a277ea5 ("Merge pull request #184 ... fix(sentence-check): Hold back a sentence that drops a limit its record sets"), finished 18:35 and 18:37Z. The earlier deployments of #183 are REMOVED. Runs started about 18:56Z, so card 99 was serving.

## Method

- The 2026-10-05 measurement ran the write path locally (`core.run.run`). This proof runs the deployed API instead: `POST /auth/guest`, `POST /v1/query` with the question and `audience_depth`, then the SSE stream and `/citations`. Question texts are copied exactly: "What are the typical symptoms and risk factors of GERD?" and "Are there any beneficial variants typically found in people of mediterranean descent?".
- Time is from posting the query to the end of the stream.
- Written sentences: claim sentences above the records, excluding the code-built "I found N records" line. The researcher answer's record table is not counted.
- Baseline (2026-10-05, not paired, before card 99): branch of card 89, and the develop control, prose sentences shown per run.

## The 12 runs

| Run | Question, depth | Seconds | Written answer above records | Sentences shown | "children" for "young children" | "potentially" or "may" dropped | Hedged primary-care sentence | Trust line |
|---|---|---|---|---|---|---|---|---|
| gp1 | GERD, plain | 20.0 | Yes | 3 | 0 | 0 | No | Based on 12 sources |
| gp2 | GERD, plain | 11.4 | Yes | 4 | 0 (shows "young children"; "may lead to" kept, record says "may cause") | 0 | No | Based on 12 sources |
| gp3 | GERD, plain | 11.8 | Yes | 4 | 0 | 0 | No | Based on 12 sources |
| gp4 | GERD, plain | 21.9 | Yes | 2 | 0 | 0 | No | Based on 12 sources |
| gp5 | GERD, plain | 14.4 | Yes | 6 | 0 (shows "In young children") | 0 | No | Based on 12 sources |
| md1 | Mediterranean, plain | 40.3 | Yes | 5 | 0 | 0 | n/a | Based on 5 sources |
| md2 | Mediterranean, plain | 20.6 | No, bare record list | 0 | 0 | 0 | n/a | Based on 5 sources, not yet confirmed |
| md3 | Mediterranean, plain | 15.8 | Yes | 3 | 0 | 0 | n/a | Based on 5 sources |
| md4 | Mediterranean, plain | 31.0 | Yes | 1 | 0 | 0 | n/a | Based on 5 sources |
| md5 | Mediterranean, plain | 10.1 | Yes | 1 | 0 | 0 | n/a | Based on 5 sources |
| gr1 | GERD, researcher | 16.2 | Yes | 3 | 0 | 0 | n/a | Based on 12 sources, not yet confirmed (graph search error, upstream) |
| gr2 | GERD, researcher | 22.0 | Yes | 3 | 0 | 0 | n/a | Based on 12 sources |
| gr1r (rerun of gr1) | GERD, researcher | 15.6 | Yes | 8 | 0 | 0 | n/a | Based on 12 sources |

Familial Mediterranean fever is named in md1 and md4 (2 of 5).

Against the 2026-10-05 baseline (prose sentences shown per run, develop control / card 89 branch):

| Set | Baseline develop | Baseline branch | Now |
|---|---|---|---|
| GERD plain | 1, 3, 3, 4, 3 | 4, 3, 4, 2, 5 | 3, 4, 4, 2, 6 |
| Mediterranean plain | 1, 0, 0, 6, 3 (2 of 5 with no prose) | 2, 5, 3, 4, 2 (0 of 5 with no prose) | 5, 0, 3, 1, 1 (1 of 5 with no prose) |
| GERD researcher | 7, refused, 1, 3, 6 | 6, 5, 5, 5, 7 | 8 (rerun), 3 |
| Baseline times | | 15.7 to 35.9 s | 10.1 to 40.3 s |


## Done-when lines

| Line | Result | Why |
|---|---|---|
| "young children" shown as "children": 0 of 10 plain-language runs | PASS | 0 of 10. Two runs (gp2, gp5) show the young-children sentence with "young" kept. No run drops "may" or "potentially" either, and the hedged primary-care sentence is shown in 0 of 5 GERD plain runs (held back or not written, as designed). The baseline showed the "children" wording in 4 of 5 branch runs and 3 of 5 develop runs |
| No run lost its written answer where the baseline had one | FAIL | md2 has no written answer. The 2026-10-05 branch run md2 had 5 sentences. The develop control also had no prose in 2 of 5 Mediterranean runs, so the card 99 effect on md2 cannot be separated from run to run variation without a paired control, which was not run |
| Times within 20 seconds per answer | FAIL (flagged) | Over 20 s: gp4 21.9, md1 40.3, md2 20.6, md4 31.0, gr2 22.0; gp1 at 19.99 is on the line. Baseline times already ranged to 35.9 s; the sentence check is a fraction of a second of this, so I do not attribute the slowness to card 99 |

Other no-worse observations: md4 and md5 show 1 sentence each (baseline 4 and 2 on the branch), gr2 shows 3 (baseline 5 to 7 on the branch, 1 to 7 on develop). Fewer sentences is the price the design predicted for holding back limit-dropping sentences, but md4 and md5 are thin answers.

## Quotes for the failures

md2, the run that lost its written answer. Trust line: "Based on 5 sources, not yet confirmed". Note shown: "Note: no written summary could be checked against the records, so the records found are listed below with their sources". All four tools returned ok; no upstream error, so this is not a rerun case.

gr1 (first run): trust line "Based on 12 sources, not yet confirmed", note "The background search of the knowledge graph did not finish, so this answer may be missing sources from it. Ask again to retry." The graph query returned an error, an upstream failure, so it was rerun once as gr1r, which gave a normal answer of 8 sentences.

One unrelated observation: md1's first sentence says G6PD attacks are triggered by "infections, certain drugs, or fava beans"; the record text returned for that citation only says different gene mutations cause different levels of deficiency. It was approved by the existing check, is not a dropped limit, and is outside card 99.

## Spend

- 14 live answers: 1 lost to a bug in my own client (it did not parse the stream, so that run's answer was discarded and gp1 was run again), 12 counted runs, 1 upstream rerun (gr1r). The brief allowed 12 plus 2 reruns, so this is the cap. Every answer reported a total cost of 0.0 in its own done event, so I cannot give a dollar figure; the earlier measurement put an answer at about 1 to 2 cents, so roughly 15 to 30 cents in all.
- No other live calls beyond the guest sign-ups (4 guests, 5 free runs each, discarded) and the 14 answers.
