#!/usr/bin/env bash
# Prove the deployed copies are byte-identical to this repository's.
#
# Build phase 4.11, ticket T-4.11-04.
#
# The service re-runs this repository's own validator server-side, which is
# what makes Section 24's defense in depth real rather than nominal. That
# argument holds only while the deployed copy IS this repository's copy. The
# moment somebody edits a file on the box to fix something quickly, the
# server-side check silently becomes a different check from the client-side
# one, and nothing reports it.
#
# A failure here is never reconciled by hand. Re-run deploy.sh.
#
# depends_on: [services/graph_query_service/deploy/deploy.sh]
# depended_by: [docs/data-engineering/Graph_query_service_runbook.md]

set -euo pipefail

HOST="${GRAPH_BOX_HOST:-root@46.225.128.133}"
TARGET=/opt/graph-query-service

PAIRS=(
    "$TARGET/system_03_search_agent/tools/cypher_validator.py|src/system_03_search_agent/tools/cypher_validator.py"
    "$TARGET/system_03_search_agent/tools/graph_schema_constants.py|src/system_03_search_agent/tools/graph_schema_constants.py"
    "$TARGET/system_03_search_agent/tools/graph_connection.py|src/system_03_search_agent/tools/graph_connection.py"
    "$TARGET/system_03_search_agent/tools/graph_http_transport.py|src/system_03_search_agent/tools/graph_http_transport.py"
    "$TARGET/services/graph_query_service/app.py|services/graph_query_service/app.py"
    # Build phase 4.12. The Caddyfile was NOT checked here, and it is the one
    # file whose own header comment says a hand-edit "is invisible to this
    # repository and survives until it causes an outage nobody can explain".
    # The file warning about invisible edits was the file this script could
    # not see, so the warning was unenforceable exactly where it was written.
    #
    # It matters more after build phase 4.12 than before it: the Caddyfile now
    # carries a SECURITY control (`header_up X-Forwarded-For {remote_host}`,
    # closing F-4.11-RV-02). Someone removing that line on the box while
    # debugging a proxy problem would silently return the service to one
    # safeguard instead of two, and nothing would report it.
    #
    # Note the asymmetry with every pair above: those live under $TARGET,
    # because deploy.sh copies the service tree there. The Caddyfile is
    # installed to /etc/caddy/Caddyfile instead, which is Caddy's own
    # location, so this pair is absolute rather than $TARGET-relative.
    "/etc/caddy/Caddyfile|services/graph_query_service/deploy/Caddyfile"
)

status=0
for pair in "${PAIRS[@]}"; do
    remote="${pair%%|*}"
    local_path="${pair##*|}"
    remote_sum="$(ssh "$HOST" "sha256sum $remote" | awk '{print $1}')"
    local_sum="$(shasum -a 256 "$local_path" | awk '{print $1}')"
    if [ "$remote_sum" = "$local_sum" ]; then
        echo "ok    $(basename "$remote")"
    else
        echo "DRIFT $(basename "$remote")"
        echo "      deployed: $remote_sum"
        echo "      repo:     $local_sum"
        status=1
    fi
done

if [ "$status" -ne 0 ]; then
    echo
    echo "The deployed service is not this repository's code. Do not reconcile"
    echo "by hand: re-run services/graph_query_service/deploy/deploy.sh."
fi
exit "$status"
