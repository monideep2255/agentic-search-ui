#!/usr/bin/env bash
# Section 24 gate 6: Python dependency audit.
#
# `-r requirements.txt`, never bare. A bare `pip-audit` audits the ambient
# environment rather than the project, and reported two findings for packages
# this project does not declare at all (F-4.14-01). Do not "simplify" this.
#
# Accepted advisories, by the product owner's yes of 2026-10-29 (DECISIONS.md):
# the 13 filelock 3.32.7 advisories below are fixed only in filelock 4.x, and
# litellm (through 1.106.6, 2026-10-28) requires filelock<4.0, so no fix can be
# installed. Every one needs a second local user on the same machine, or
# Windows; the app runs as one user in a Linux container. Remove this list the
# day litellm accepts filelock 4: pin filelock to the fixed release and delete
# ACCEPTED. Any advisory not listed here still fails the gate.
set -euo pipefail
ACCEPTED=(
  CVE-2026-112907 CVE-2026-112908 CVE-2026-112909 CVE-2026-112910
  CVE-2026-112911 CVE-2026-112912 CVE-2026-112913 CVE-2026-112915
  CVE-2026-112935 CVE-2026-112936 CVE-2026-112938 CVE-2026-112939
  CVE-2026-112940
)
ignore_args=()
for id in "${ACCEPTED[@]}"; do ignore_args+=(--ignore-vuln "$id"); done
pip-audit -r requirements.txt "${ignore_args[@]}"
