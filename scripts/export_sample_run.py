"""Export one real benchmark run into docs/sample-run/, redacted and checked for secrets.

The bundle holds what an evaluator needs to see a run without making one: the
requirement, the progress log (rebuilt from the run's events), the generated program and
QA's tests, QA's final report, the run record, the events and the cost report. A run is
exported only if it completed and shows QA finding a defect that a later review no
longer fails. Every text file passes through the project's ``Redactor``, host paths are
replaced with ``<workspace>``, and the export is refused if anything secret-shaped
remains.

Usage:
    python scripts/export_sample_run.py RESULTS.json ITEM_ID [--out docs/sample-run]
"""

import argparse
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from dotenv import dotenv_values  # noqa: E402 (needs the repository on the path)

from observability.events import progress_line, read_events  # noqa: E402
from observability.redaction import ANTHROPIC_KEY_PATTERN, Redactor  # noqa: E402

SKIPPED = (".qa", "__pycache__", ".pytest_cache")


class ExportRefused(Exception):
    """The run can't be published; the message names the rule it breaks."""


def find_record(results: dict, item_id: str) -> dict:
    """The results record for ``item_id``.

    Raises:
        ExportRefused: if the results file has no such item, or it has no run.
    """
    record = next((item for item in results.get("records", []) if item["id"] == item_id), None)
    if record is None or not record.get("workspace") or not record.get("run_id"):
        raise ExportRefused(f"no run for {item_id!r} in the results file")
    return record


def check_publishable(run: dict) -> None:
    """Refuse a run that didn't complete or never found and fixed a defect (FR-009).

    Raises:
        ExportRefused: naming the rule the run breaks.
    """
    if run.get("status") != "completed":
        raise ExportRefused(f"the run ended {run.get('status')!r}, not 'completed'")
    failed = [it["test_run"]["failed"] + it["test_run"]["errors"] for it in run["iterations"]]
    first_failing = next((n for n, count in enumerate(failed) if count > 0), None)
    if first_failing is None or 0 not in failed[first_failing + 1:]:
        raise ExportRefused("no QA review found a failing test that a later review fixed")


def program_files(workspace: Path) -> dict[str, str]:
    """The generated program and QA's tests, by path relative to the workspace."""
    files = {}
    for path in sorted(workspace.rglob("*")):
        relative = path.relative_to(workspace)
        if path.is_file() and not set(relative.parts) & set(SKIPPED):
            files[relative.as_posix()] = path.read_text(encoding="utf-8", errors="replace")
    return files


def bundle(record: dict, results: dict, run_dir: Path, workspace: Path) -> dict[str, str]:
    """Every file of the bundle, as text, before redaction."""
    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    check_publishable(run)
    events = read_events(run_dir / "events.jsonl")
    lines = [line for line in map(progress_line, events) if line]
    files = {f"program/{path}": text for path, text in program_files(workspace).items()}
    files.update({
        "requirement.txt": run["requirement"].strip() + "\n",
        "progress.log": "\n".join(lines) + "\n",
        "report.md": (workspace / ".qa" / "report.md").read_text(encoding="utf-8"),
        "run.json": json.dumps(run, indent=2) + "\n",
        "events.jsonl": "".join(json.dumps(event) + "\n" for event in events),
        "cost-report.json": _cost_report(record, run),
        "README.md": readme(record, results, run),
    })
    return files


def _cost_report(record: dict, run: dict) -> str:
    path = Path(record.get("cost_report") or run.get("cost_report_path") or "")
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path.read_text(encoding="utf-8")


def readme(record: dict, results: dict, run: dict) -> str:
    """The bundle's own README: what this run is, how it was chosen, how to regenerate it."""
    config = results.get("configuration", {})
    iterations = run["iterations"]
    reviews = "; ".join(f"#{it['number']}: {it['test_run']['passed']} passed, "
                        f"{it['test_run']['failed'] + it['test_run']['errors']} failed"
                        for it in iterations)
    return "\n".join([
        "# Sample run",
        "",
        f"A real, live run of the team on the benchmark item `{record['id']}`, exported "
        "unchanged apart from secret redaction and host paths (shown as `<workspace>`).",
        "",
        "- **Requirement:** see [requirement.txt](requirement.txt)",
        f"- **Run ID:** `{record['run_id']}`, status `{run['status']}` "
        f"({run['end_reason']}), {len(iterations)} QA reviews ({reviews})",
        f"- **Cost:** ${record.get('cost_usd')} (see [cost-report.json](cost-report.json))",
        f"- **Commit:** `{config.get('commit')}`; models {json.dumps(config.get('models'))}; "
        f"effort {json.dumps(config.get('effort'))}; "
        f"prompt cache {config.get('prompt_cache_ttl')}",
        f"- **From:** `{results.get('requirements_file')}`, results file of "
        f"{results.get('started_at', '')[:10]}",
        "",
        "It was chosen from the benchmark refresh because a QA review found a failing test "
        "and the Coder's fix round made a later review pass, which shows the whole loop.",
        "",
        "| File | What |",
        "|------|------|",
        "| [progress.log](progress.log) | The run's progress lines, rebuilt from its events |",
        "| [program/](program/) | The generated program, and QA's tests in `program/tests/` |",
        "| [report.md](report.md) | QA's final report |",
        "| [run.json](run.json) | The final run state: spec, tasks, every QA iteration |",
        "| [events.jsonl](events.jsonl) | Every event of the run |",
        "| [cost-report.json](cost-report.json) | Tokens and cost per agent |",
        "",
        "Regenerate it from a results file with "
        "`python scripts/export_sample_run.py <results.json> <item id>`.",
        "",
    ])


def scrub(files: dict[str, str], paths: list[str], redactor: Redactor) -> dict[str, str]:
    """Redact secrets and replace host paths; refuse if anything secret-shaped remains.

    Raises:
        ExportRefused: naming the file that still holds a secret-shaped string.
    """
    clean = {}
    for name, text in files.items():
        for path in sorted(paths, key=len, reverse=True):
            text = text.replace(path, "<workspace>")
        text = redactor.redact(text)
        if ANTHROPIC_KEY_PATTERN.search(text):
            raise ExportRefused(f"{name} still holds a secret-shaped string after redaction")
        clean[name] = text
    return clean


def write_bundle(files: dict[str, str], out: Path) -> None:
    """Write ``files`` into ``out``, replacing it whole only once everything is written."""
    staging = Path(tempfile.mkdtemp(prefix=".sample-run-", dir=out.parent))
    try:
        for name, text in files.items():
            target = staging / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
        if out.exists():
            shutil.rmtree(out)
        staging.rename(out)
    except OSError:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def export(results_path: Path, item_id: str, out: Path) -> None:
    """Export ``item_id``'s run from ``results_path`` into ``out``.

    Raises:
        ExportRefused: if the run is missing, unpublishable or still holds a secret.
    """
    results = json.loads(Path(results_path).read_text(encoding="utf-8"))
    record = find_record(results, item_id)
    workspace = Path(record["workspace"])
    if not workspace.is_absolute():
        workspace = REPO_ROOT / workspace
    run_dir = workspace.parent / ".runs" / record["run_id"]
    if not (run_dir / "run.json").is_file():
        raise ExportRefused(f"{run_dir}/run.json is missing")
    files = bundle(record, results, run_dir, workspace)
    redactor = Redactor.from_env({**os.environ, **dotenv_values(REPO_ROOT / ".env")})
    paths = [str(workspace.resolve()), str(workspace.parent.resolve()), str(REPO_ROOT)]
    write_bundle(scrub(files, paths, redactor), Path(out))


def main(argv: list[str] | None = None) -> int:
    """Export a run; 0 on success, 2 when the export is refused."""
    parser = argparse.ArgumentParser(prog="python scripts/export_sample_run.py",
                                     description="Export one benchmark run as the sample run.")
    parser.add_argument("results", type=Path, help="a benchmark results file")
    parser.add_argument("item_id", help="the benchmark item to export")
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "docs" / "sample-run")
    args = parser.parse_args(argv)
    try:
        export(args.results, args.item_id, args.out)
    except (ExportRefused, OSError, ValueError, KeyError) as error:
        print(f"export refused: {error}", file=sys.stderr)
        return 2
    print(f"exported {args.item_id} to {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
