#!/usr/bin/env bash
# Everything CI checks, in the same order: style, then the suite with its coverage gate.
set -euo pipefail
cd "$(dirname "$0")/.."
ruff check .
scripts/test.sh
