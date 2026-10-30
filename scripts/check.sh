#!/usr/bin/env bash
# Everything CI checks, in the same order: style, the suite with its coverage gate, API docs.
set -euo pipefail
cd "$(dirname "$0")/.."
ruff check .
scripts/test.sh
scripts/build_api_docs.sh --check
