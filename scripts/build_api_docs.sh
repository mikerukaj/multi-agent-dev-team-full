#!/usr/bin/env bash
# Build the HTML API reference into docs/api with pdoc (pinned in requirements-dev.txt).
#   scripts/build_api_docs.sh          regenerate docs/api
#   scripts/build_api_docs.sh --check  exit 1 if docs/api differs from a fresh build
set -euo pipefail
cd "$(dirname "$0")/.."
MODULES=(agents orchestration tools messaging cost resilience observability benchmarks demo)

build() {
  # pdoc shows the value of every module constant, and constants built from __file__
  # hold absolute paths, whose length even changes the page layout. So the build runs on
  # a copy at a path of fixed length, which is then shown as "." on every machine.
  local out="$1" root
  root="$(mktemp -d /tmp/pdoc.XXXXXXXX)"
  for module in "${MODULES[@]}"; do
    cp -R "$module" "$root/"
  done
  find "$root" -name __pycache__ -prune -exec rm -rf {} +
  # A dummy key and no tracing: importing the modules must reach nothing outside.
  # A fixed hash seed makes set and frozenset values print in the same order every time.
  (cd "$root" && env -u LANGSMITH_TRACING -u LANGSMITH_API_KEY \
    ANTHROPIC_API_KEY=sk-ant-docs-not-a-key PYTHONHASHSEED=0 \
    python -m pdoc --docformat google --no-show-source --no-search -o "$root/.api" \
    "${MODULES[@]}")
  python - "$root/.api" "$root" <<'PY'
import sys
from pathlib import Path
out, root = Path(sys.argv[1]), sys.argv[2]
for page in out.rglob("*.html"):
    text = page.read_text(encoding="utf-8")
    if root in text:
        page.write_text(text.replace(root, "."), encoding="utf-8")
PY
  rm -rf "$out"
  mv "$root/.api" "$out"
  rm -rf "$root"
}

if [[ "${1:-}" == "--check" ]]; then
  fresh="$(mktemp -d)"
  trap 'rm -rf "$fresh"' EXIT
  build "$fresh/api"
  if ! diff -r -q "$fresh/api" docs/api; then
    echo "docs/api is out of date: run scripts/build_api_docs.sh" >&2
    exit 1
  fi
  echo "docs/api is up to date"
else
  build docs/api
  echo "wrote docs/api"
fi
