#!/usr/bin/env bash
# Section 24 gate 8: frontend build and test.
#
# `npm run build` is `tsc -b && vite build`, so this is the typecheck too. The
# license check after it is card 60: React, React DOM, their scheduler, and
# MUI are MIT licensed, and a build that drops any of their notices from what
# it hands to every visitor fails here rather than shipping quietly.
set -euo pipefail
npm run build && npm test && python3 ../.github/scripts/assert_license_notices.py dist
