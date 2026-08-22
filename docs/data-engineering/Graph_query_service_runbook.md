# Graph query service runbook

Operations reference for the read-only HTTPS graph query service that fronts the AGE knowledge graph on the Hetzner box. Built at build phase 4.11 to the specification in `requirements/Technical_specification.md` Section 24, which names it the v1 Layer 1 transport under Decision D.

This file is written so someone who has never seen the service can rebuild it from nothing, and so someone woken by an outage can decide in a minute whether the service, the proxy, the graph, or the network is the thing that broke.

## Table of contents

- [What it is, in one paragraph](#what-it-is-in-one-paragraph)
- [Why it exists](#why-it-exists)
- [The moving parts](#the-moving-parts)
- [Install from nothing](#install-from-nothing)
- [Redeploy after a code change](#redeploy-after-a-code-change)
- [Verify](#verify)
- [Read the logs](#read-the-logs)
- [Diagnose an outage](#diagnose-an-outage)
- [Roll back](#roll-back)
- [The credential](#the-credential)
- [What this service must never do](#what-this-service-must-never-do)

## What it is, in one paragraph

One HTTPS endpoint, running on the same machine as the graph, that accepts an already-validated parameterized Cypher payload, re-runs this repository's own validator on it server-side, executes it through the read-only `kg_reader` role over localhost, and returns the rows unchanged. It is authenticated by a bearer credential, bounded by a row limit, a per-call timeout and a per-caller rate limit, and it terminates TLS through a reverse proxy. It holds no state.

## Why it exists

Two reasons, and the second is the one that got it built when it did.

The specification reason: Section 24 names this service as the v1 Layer 1 transport and says its credential is populated "when the service is built (Section 25 build order)", while Section 25 never assigns it to any phase. One locked section pointed at another for something that was not there.

The operational reason: before this service, every live test in this repository reached the graph through a hand-opened SSH local port-forward. That forward is a single point of failure for the project's entire live verification surface, and build phase 4.6 paid for it twice in one week. It was down for two days, then down again through all three of that phase's review rounds, so 4.6 merged with three live premise-gate arms unrun and accepted as such. This service deletes that dependency.

## The moving parts

| Part | Where | What it does |
|------|-------|--------------|
| Caddy | `systemd` unit `caddy`, package from Ubuntu `universe` | Terminates TLS on the reverse-DNS hostname, obtains and renews the certificate, proxies to the service on localhost |
| The service | `systemd` unit, a non-root user, bound to `127.0.0.1` | Auth, server-side revalidation, budgets, execution, audit logging |
| AGE Postgres | `systemd` unit `postgresql`, bound to `127.0.0.1:5432` | The graph. Reached only from this machine, only as `kg_reader` |

The hop from the service to Postgres never leaves the machine. The only network hop is a caller to Caddy over HTTPS.

Host: `46.225.128.133`, reverse-DNS name `static.133.128.225.46.clients.your-server.de`, which forward-resolves to the same address. That name is what the certificate is issued for, and it is why no domain had to be bought.

## Install from nothing

Run every step from the repository root on a machine with SSH access to the box.

1. Confirm nothing is filtering the ports. There is NO firewall on this box and none in the Hetzner project: `ufw` is inactive, `iptables`, `ip6tables` and `nftables` are all empty, and the Hetzner API reports zero firewalls. Ports 80 and 443 are reachable as soon as something listens on them. Verify by connecting to 80 once Caddy is up rather than by reading this sentence, since this is the one fact in this file that would be expensive to have wrong.
2. Install Caddy from the distribution repository. Not from the vendor apt repository and never from a script piped to a shell, per `.claude/rules/supply-chain-security.md`.
3. Create the service user. A non-login system user that owns nothing but the service directory and the credential file.
4. Copy the service and its three vendored modules with the deploy script. Never hand-edit a file on the box; a hand-edit is invisible to this repository and survives until it causes an outage nobody can explain.
5. Generate the credential on the box with a CSPRNG, readable only by the service user. It is never generated on a laptop, never pasted into a chat, and never committed.
6. Install and start the two systemd units, then enable them so they survive a reboot.
7. Verify with the section below. Do not skip it: the service starting is not evidence that it works.

The exact commands live in `services/graph_query_service/deploy/`, which is the executable form of this list. This section is the reasoning; that directory is the source of truth for the literal steps.

## Redeploy after a code change

Run the deploy script again and restart the service unit. The script copies from this repository, so a redeploy cannot drift from committed source. Then run the drift check, which asserts the deployed validator and schema constants are byte-identical to this repository's copies. A drift check failure means somebody edited a file on the box, and the fix is to redeploy rather than to reconcile by hand.

## Verify

Four checks, in this order, because each one rules out the layer below it.

1. The service answers its health endpoint over HTTPS with a certificate the system trust store accepts.
2. A real query returns rows, run through the premise gate rather than by hand.
3. The database port is still unreachable from the public internet, and is still bound to `127.0.0.1` on the box.
4. The full live premise gate passes with `RUN_PREMISE_GATE=1` and no SSH tunnel open anywhere. This last one is the phase's whole point, and running it with a tunnel still open proves nothing.

`tracker/preflight.py` probes the service as its own transport once `GRAPH_QUERY_URL` is set. A `skipped` result there is not a pass; it means the transport was not configured and nothing was verified.

## Read the logs

The service logs every call at INFO through journald: what was queried, when, and which caller, identified by a short non-reversible digest rather than by the credential. Caddy logs the TLS layer separately, including certificate issuance and renewal.

If a call is missing from the log, the request did not reach the service. That is a Caddy question, not a service question.

## Diagnose an outage

Work down this list. It is ordered so the cheapest check that can explain the symptom comes first.

- A caller times out and SSH also fails: the box or the network is down. Nothing below applies.
- A caller times out and SSH works: Caddy is not running, or is running and not listening on 443. Check `systemctl is-active caddy` and `ss -lnt` on the box. Do NOT go looking for a firewall rule: there is no firewall here, and an earlier version of this runbook sent readers hunting for one that never existed (finding F-4.11-J-04).
- A caller gets a TLS error: the certificate failed to renew. Renewal needs inbound port 80. The most likely cause is that port 80 was closed after install as a tidy-up.
- A caller gets 401: the credential in the caller's environment and the credential on the box disagree. Rotate deliberately rather than guessing, and remember Railway holds its own copy once build phase 4.12 has run.
- A caller gets 502 with `graph_unavailable`: the service is up and Postgres is not, or `kg_reader` cannot authenticate. This is the one failure that is genuinely the graph's rather than the transport's.
- A caller gets 429: the rate limit is doing its job. If it fires under legitimate load, the limit is the thing to change, in the service and in this repository, not on the box.
- Every call returns rows and the product's answers are wrong: this service is almost certainly not the cause. It returns rows unchanged. Look at `cypher_provenance` and the synthesis path instead.

## Roll back

Redeploy the previous commit's copy of the service with the deploy script and restart the unit. If the service itself is suspect, the fallback transport still exists: clear `GRAPH_QUERY_URL` in the caller's environment and `execute_cypher` returns to the psycopg2 path over an SSH local port-forward. That is the two-way door Decision D promised, and it is the reason the transport swap was built inside one function rather than spread across callers.

Rolling back does not require touching the graph, which cannot be written to from here in any case.

## The credential

`GRAPH_QUERY_TOKEN` in `env.example`'s Layer 1 block. The value lives in exactly three places: a root-readable file on the box, the local `.env` of anyone running live tests, and, after build phase 4.12, a Railway service variable.

It never appears in this repository, in a log line, in an exception string, in a test fixture, or in a commit. The premise gate asserts this rather than trusting it: it plants the real value and greps every response body and every log line for it.

To rotate: generate a new value on the box, update the service's credential file, restart the unit, then update every caller. Callers fail with 401 in the window between, which is the correct behaviour and the reason rotation is done deliberately rather than casually.

## What this service must never do

- Acquire a write credential. It uses `kg_reader`, which carries `default_transaction_read_only`, so a validator bug still cannot produce a write. This is enforcement at the connection level, not an instruction.
- Accept Cypher that its own server-side validator rejected. The point of re-running the checks here is that a bug in the client-side validator must not be the only barrier between a request and the database.
- Open the database port to the internet. It is bound to `127.0.0.1` and that binding is the WHOLE defense, not half of one. An earlier version of this file claimed a Hetzner firewall was the second half; there is no firewall, so nothing is holding that line except the binding. Treat it accordingly and never widen it.
- Grow a second feature. It is a transport. Anything that looks like query planning, caching, or result shaping belongs in the tool layer where it can be tested against the rest of the product.
