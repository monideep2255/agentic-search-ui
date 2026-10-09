#!/bin/bash
# poll develop every 60 s for up to 15 min until recent-onset diabetes treatment is not asked back
cd "$(dirname "$0")/../../../../../frontend" || exit 1
O=../testing/Developer/reports/2026-10-05_wave01_test_queries/runner_B
for i in $(seq 1 15); do
  FRONTEND_DIR=$PWD node $O/ask.mjs poll$i "recent-onset diabetes treatment" $O/probe >/dev/null 2>&1
  if grep -q "What would you like to know about" $O/probe/poll$i.txt; then echo "poll$i $(date -u +%H:%M:%S) asked back"; else echo "poll$i $(date -u +%H:%M:%S) NOT asked back"; break; fi
  sleep 60
done
echo done
