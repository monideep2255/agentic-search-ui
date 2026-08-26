#!/usr/bin/env bash
# Setup, not a gate: create the user schema in the running PostgreSQL service.
#
# The service gives the job a database; this gives it tables. The tests own
# probe checks CONNECTIVITY only, so against an empty database they connect
# happily and then fail on missing tables.
set -euo pipefail
alembic upgrade head
