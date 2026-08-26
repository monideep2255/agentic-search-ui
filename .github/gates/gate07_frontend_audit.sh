#!/usr/bin/env bash
# Section 24 gate 7: frontend dependency audit.
#
# `--audit-level=high` is the threshold Section 24 sets. `critical` would pass
# a High CVE.
set -euo pipefail
npm audit --audit-level=high
