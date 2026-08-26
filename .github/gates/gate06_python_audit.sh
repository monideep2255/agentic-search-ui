#!/usr/bin/env bash
# Section 24 gate 6: Python dependency audit.
#
# `-r requirements.txt`, never bare. A bare `pip-audit` audits the ambient
# environment rather than the project, and reported two findings for packages
# this project does not declare at all (F-4.14-01). Do not "simplify" this.
set -euo pipefail
pip-audit -r requirements.txt
