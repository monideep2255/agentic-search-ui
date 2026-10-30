# Card 84 and 72: a week of guard lag lines

The owner asked on 2026-10-25 for the last week of "event loop lag" lines from develop and production, read only, with the numbers and one recommendation. Read on the night of 2026-10-29 with the Railway command-line tool, every deployment of the API service from 2026-10-18 on, no setting changed.

## Table of contents

- [In one minute](#in-one-minute)
- [Develop](#develop)
- [Production](#production)
- [What the numbers mean for step 3b](#what-the-numbers-mean-for-step-3b)
- [What the numbers mean for card 72](#what-the-numbers-mean-for-card-72)
- [Recommendation](#recommendation)
- [How it was read](#how-it-was-read)

## In one minute

- Develop logged 6 lag lines in the week, the longest 0.40 s. Step 3b's design needs a pause of about 2.6 s before a guard verdict changes.
- Develop answered 38 questions in the week, all on the night of 2026-10-23, during the overnight product checks. No guard call timed out, was rate limited or retried.
- Production's logs hold no question at all in the window they keep, and no lag line.
- Recommendation: do not build step 3b. Keep the watcher on, since it costs nothing.

## Develop

Lag lines, all six:

| Time (UTC) | Lag | Questions within 60 s |
|---|---|---|
| 2026-10-23 02:56:46 | 0.28 s | 22 model calls |
| 2026-10-23 03:00:06 | 0.26 s | 32 model calls |
| 2026-10-23 03:00:07 | 0.26 s | 32 model calls |
| 2026-10-23 18:46:25 | 0.26 s | none |
| 2026-10-27 14:11:34 | 0.40 s | none |
| 2026-10-28 23:14:49 | 0.25 s | none |

Three came while several product-check questions ran at once, and three came with no question in flight, which reads as the host pausing the process, not a question's own work.

Model calls, from the one line per guard and Jev call:

| Kind | Calls | Median | 90th percentile | Longest | Not ok |
|---|---|---|---|---|---|
| Guard | 38 | 1.49 s | 2.93 s | 6.77 s | 0 |
| Jev | 211 | 0.22 s | 0.29 s | 1.63 s | 0 |

- Retries: none. Every call ended on its first attempt.
- Guard upstream hosts: Relace 18, GMICloud 10, StreamLake 5, Venice 2, SiliconFlow 2, DigitalOcean 1. The slowest guard call, 6.77 s, went to SiliconFlow; the next, 3.09 s, also on 2026-10-23.
- Jev's replies carried no host, so all 211 read "unknown", as the log line's design expects.

## Production

- Production runs v0.3.2 (`93e8b638`), which carries the lag watcher (#251) and the call log.
- Its API logs hold five requests, from 2026-10-29 06:25 UTC on: a robots file, the root path, two allowance checks and one persona read. No question, no model call, no lag line.
- The command-line tool cannot say whether older lines were trimmed or never written, so production gives no evidence either way.

## What the numbers mean for step 3b

Step 3b (`testing/Developer/reports/2026-10-15_card84_72/design.md`) gives a late Jev reply back the time the server was frozen. Its own analysis says a freeze has to last about 2.6 s on develop before it changes a verdict. The longest lag in a week was 0.40 s, about a sixth of that. A person asking a question would not have been turned away, or let through, by a pause this week.

The sample is thin: 38 questions on one night, from the team's checks, not from people using the product.

## What the numbers mean for card 72

Card 72's failure is the guard not answering in time. In 38 guard calls none timed out, and the longest took 6.77 s. Step 2, ranking upstream hosts, needs many more calls per host than one to eighteen to rank anything.

## Recommendation

Do not build step 3b. Close it as not needed on this evidence, keep the watcher on, and reopen it only if a lag line of 1 s or more appears. Card 72's step 2 keeps waiting for more guard calls; nothing in this week argues for building it now.

## How it was read

- `railway deployment list` for the `search-agent-api` service in each project, then `railway logs <deployment>` with the filters `"event loop lag"` and `"model call point"`, at most 5,000 lines per filter per deployment. No deployment reached the limit.
- Develop: 20 deployments from 2026-10-18 to 2026-10-30, of which four held matching lines. Production: 6 deployments, none with a matching line.
- Read only: no deploy, no setting, no restart.
