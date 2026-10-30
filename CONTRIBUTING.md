# Contributing

## Set up

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt    # the runtime packages plus coverage, ruff and pdoc
```

Docker is needed for the sandbox tests; without it they skip with a reason. No API key
is needed: the test suite never makes a paid model call.

## Check your change

```bash
scripts/check.sh
```

It runs what CI runs, in the same order, and stops at the first failure:

1. `ruff check .`: PEP 8 with a 99-character line, import order, a docstring on every
   public module, class, function and method, and a return type on every public
   function (configuration in `ruff.toml`).
2. `scripts/test.sh`: the whole offline suite under `coverage`, failing below 85%
   statement coverage. `python -m unittest discover -s tests -t .` runs the same tests
   without coverage.
3. `scripts/build_api_docs.sh --check`: fails if `docs/api/` no longer matches the code.

Every change in behavior comes with a test that exercises it. Tests use the standard
library's `unittest`; see [docs/TESTING.md](docs/TESTING.md) for the layers and fakes.

## Live tests

`RUN_LIVE_E2E=1` (with `ANTHROPIC_API_KEY` set and Docker running) also runs the
end-to-end pipeline test and the Coder smoke test. They make **paid model calls**.
Benchmark runs (`python -m benchmarks.run_benchmark`) are live and paid too; pass a
budget with `RUN_BUDGET_USD`.

## Regenerate generated files

| File | Command | When |
|------|---------|------|
| `docs/api/` | `scripts/build_api_docs.sh` | After changing a public docstring or signature |
| `docs/assets/demo.txt`, `demo.svg` | `python scripts/record_demo.py` | After changing the demo or the progress lines |
| The published sample run | `python scripts/export_sample_run.py <results.json> <item id>` | After a new benchmark run |

## Commits

One concern per commit, with a message of the form `<area>: <what> (<why>)`. For
example: `qa: count only still-open blocking findings in the report's iteration lines`.
The body says what changed and why, and names any test added.
