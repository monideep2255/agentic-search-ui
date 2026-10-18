#!/usr/bin/env bash
# Build phase 8.10, T-8.10-01: every wheel this repository makes installs
# into a clean environment, and every console script it declares starts.
#
# Not one of Section 24's ten gates, which the locked technical
# specification numbers; added by the phase 8.10 ledger. It exists because
# `s3-kgx-export --help` crashed from every installed copy for four weeks
# while every other gate stayed green: the tests and the deployments read the
# source tree, never the package. `check_packages_install.py` says what it
# covers and what it does not.
set -euo pipefail
python .github/gates/check_packages_install.py
