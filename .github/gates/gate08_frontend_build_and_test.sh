#!/usr/bin/env bash
# Section 24 gate 8: frontend build and test.
#
# `npm run build` is `tsc -b && vite build`, so this is the typecheck too.
set -euo pipefail
npm run build && npm test
