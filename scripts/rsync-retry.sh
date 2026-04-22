#!/bin/bash
# Auto-retry rsync to VPS until completion. Resumes from --partial on each drop.
# Home Wi-Fi + consumer router drops SSH sessions after ~5 min / ~1.4 GB.
set -u
MAX_RETRIES=200
i=0
while [ $i -lt $MAX_RETRIES ]; do
  i=$((i + 1))
  echo "=== attempt $i at $(date '+%H:%M:%S') ===" | tee -a /tmp/phase4_rsync.log
  MSYS_NO_PATHCONV=1 rsync -avP --compress --partial --inplace --append --timeout=600 \
    -e "/cygdrive/c/Users/chakrabortim2/scoop/apps/cwrsync/6.4.7/bin/ssh.exe -i /cygdrive/c/Users/chakrabortim2/.ssh/id_ed25519 -o StrictHostKeyChecking=accept-new -o ServerAliveInterval=30 -o ServerAliveCountMax=20 -o TCPKeepAlive=yes" \
    "/cygdrive/c/Users/chakrabortim2/Desktop/agentic-search-data-engineering/data/kgx/merged/" \
    root@46.225.128.133:/root/data/kgx/merged/ 2>&1 | tee -a /tmp/phase4_rsync.log
  rc=${PIPESTATUS[0]}
  if [ $rc -eq 0 ]; then
    echo "=== rsync complete after $i attempts at $(date '+%H:%M:%S') ===" | tee -a /tmp/phase4_rsync.log
    exit 0
  fi
  echo "attempt $i exited $rc, sleeping 10s" | tee -a /tmp/phase4_rsync.log
  sleep 10
done
echo "=== gave up after $MAX_RETRIES attempts ===" | tee -a /tmp/phase4_rsync.log
exit 1
