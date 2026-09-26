#!/usr/bin/env bash
# Deploy the read-only HTTPS graph query service to the Hetzner box.
#
# Build phase 4.11, Technical_specification.md Section 24.
#
# Run from the repository root. Idempotent: running it twice leaves the same
# state, and it is the ONLY way code reaches the box. A file hand-edited on
# the server is invisible to this repository and survives until it causes an
# outage nobody can explain, so this script overwrites rather than merges.
#
# It deliberately does NOT create the credential. That is a separate,
# once-only step run on the box itself, because a credential generated on a
# laptop has already travelled further than it should.
#
# The box to deploy to is named by the GRAPH_BOX_HOST setting (see
# env.example for its format, root@<the box's address>): the GRAPH_BOX_HOST
# environment variable if set, otherwise the GRAPH_BOX_HOST= line in .env at
# the repository root. Refuses to run with a plain message, never a stack
# trace, when neither is set.
#
# depends_on: [services/graph_query_service/app.py, services/graph_query_service/deploy/Caddyfile, services/graph_query_service/deploy/graph-query-service.service]
# depended_by: [docs/data-engineering/Graph_query_service_runbook.md, services/graph_query_service/deploy/check_drift.sh]

set -euo pipefail

HOST="${GRAPH_BOX_HOST:-}"
if [ -z "$HOST" ] && [ -f .env ]; then
    # `|| true`: a .env without the line must reach the message below, not
    # end the script silently under pipefail. Quotes and a CR are dropped.
    HOST="$( { grep -m1 '^GRAPH_BOX_HOST=' .env || true; } | cut -d= -f2- | tr -d "\"' \r")"
fi
if [ -z "$HOST" ]; then
    echo "GRAPH_BOX_HOST is not set. Set it in the environment, or add a GRAPH_BOX_HOST= line to .env at the repository root; env.example shows its format." >&2
    exit 1
fi
TARGET=/opt/graph-query-service

# The four modules the service imports out of the agent package. Copied
# rather than re-implemented, so the server-side checks cannot drift from
# the client-side ones they exist to backstop. check_drift.sh proves the
# copies stayed identical.
TOOL_MODULES=(
    cypher_validator.py
    graph_schema_constants.py
    graph_connection.py
    graph_http_transport.py
)

echo "==> staging"
STAGE="$(mktemp -d)"
cleanup() { [ -n "${STAGE:-}" ] && find "$STAGE" -mindepth 0 -delete; }
trap cleanup EXIT

mkdir -p "$STAGE/services/graph_query_service"
mkdir -p "$STAGE/system_03_search_agent/tools"

cp services/__init__.py "$STAGE/services/"
cp services/graph_query_service/__init__.py "$STAGE/services/graph_query_service/"
cp services/graph_query_service/app.py "$STAGE/services/graph_query_service/"
cp services/graph_query_service/README.md "$STAGE/services/graph_query_service/"

cp src/system_03_search_agent/__init__.py "$STAGE/system_03_search_agent/"
cp src/system_03_search_agent/tools/__init__.py "$STAGE/system_03_search_agent/tools/"
for module in "${TOOL_MODULES[@]}"; do
    cp "src/system_03_search_agent/tools/$module" "$STAGE/system_03_search_agent/tools/"
done

echo "==> copying to $HOST:$TARGET"
tar -C "$STAGE" -cf - . | ssh "$HOST" "tar -C $TARGET -xf -"

echo "==> python environment"
ssh "$HOST" "test -d $TARGET/venv || python3 -m venv $TARGET/venv"
ssh "$HOST" "$TARGET/venv/bin/pip install --quiet --upgrade pip"
# F-4.11-13: pinned, from requirements.txt, never a bare package list.
# This line used to install five packages with no versions on the box that
# holds the graph credential, so every redeploy took whatever was newest.
# --require-hashes is deliberately NOT used yet: it needs a hash for every
# transitive dependency too, and generating that set is its own task with
# its own verification. The pins are the first half and the honest state is
# recorded rather than implied.
scp -q services/graph_query_service/deploy/requirements.txt "$HOST:$TARGET/"
ssh "$HOST" "$TARGET/venv/bin/pip install --quiet -r $TARGET/requirements.txt"

echo "==> units"
scp -q services/graph_query_service/deploy/graph-query-service.service "$HOST:/etc/systemd/system/"
scp -q services/graph_query_service/deploy/Caddyfile "$HOST:/etc/caddy/Caddyfile"

echo "==> ownership"
ssh "$HOST" "chown -R kgquery:kgquery $TARGET"
ssh "$HOST" "install -d -o caddy -g caddy -m 0755 /var/log/caddy"

echo "==> reload and restart"
ssh "$HOST" "systemctl daemon-reload"
ssh "$HOST" "systemctl enable --now graph-query-service"
ssh "$HOST" "systemctl restart graph-query-service"
ssh "$HOST" "systemctl reload-or-restart caddy"

echo "==> deployed. Verify with check_drift.sh and the premise gate."
