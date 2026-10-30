"""Exporting one benchmark run as the published sample run (scripts/export_sample_run.py)."""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "export_sample_run", REPO_ROOT / "scripts" / "export_sample_run.py")
exporter = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(exporter)

PLANTED = "sk-ant-api03-PLANTEDsecretvalue0000"


def iteration(number: int, failed: int) -> dict:
    return {"number": number, "verdict": "complete" if not failed else "fix_needed",
            "test_run": {"passed": 7 - failed, "failed": failed, "errors": 0}}


class ExportCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.out = self.root / "docs" / "sample-run"
        self.out.parent.mkdir(parents=True)

    def make_run(self, status: str = "completed", failures=(1, 0), extra: str = "") -> Path:
        """A run on disk like the benchmark leaves one; returns its results file."""
        bench = self.root / "workspace" / "benchmark-x"
        workspace = bench / "run-1"
        (workspace / "tests").mkdir(parents=True)
        (workspace / ".qa").mkdir()
        (workspace / "__pycache__").mkdir()
        (workspace / "temp.py").write_text(f"print('hi')  # {workspace}\n{extra}",
                                           encoding="utf-8")
        (workspace / "tests" / "test_temp.py").write_text("def test_x(): pass\n",
                                                          encoding="utf-8")
        (workspace / "__pycache__" / "temp.pyc").write_text("x", encoding="utf-8")
        (workspace / ".qa" / "report.md").write_text("# QA report\n", encoding="utf-8")
        run_dir = bench / ".runs" / "run-1"
        run_dir.mkdir(parents=True)
        run = {"requirement": "A tool.", "status": status, "end_reason": "complete",
               "iterations": [iteration(n + 1, f) for n, f in enumerate(failures)],
               "workspace": str(workspace)}
        (run_dir / "run.json").write_text(json.dumps(run), encoding="utf-8")
        events = [{"event": "stage_end", "details": {"progress": "[qa] #1: 6 passed, 1 failed"}},
                  {"event": "model_call", "details": {}}]
        (run_dir / "events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events),
                                              encoding="utf-8")
        report = self.root / "cost.json"
        report.write_text('{"total": {"cost_usd": 0.1}}', encoding="utf-8")
        results = {"requirements_file": "benchmarks/requirements.json",
                   "started_at": "2026-10-30T00:00:00Z",
                   "configuration": {"commit": "abc1234", "models": {"pm": "m"}},
                   "records": [{"id": "todo-cli", "run_id": "run-1", "cost_usd": 0.1,
                                "workspace": str(workspace), "cost_report": str(report)}]}
        path = self.root / "results.json"
        path.write_text(json.dumps(results), encoding="utf-8")
        return path

    def export(self, results: Path, item: str = "todo-cli") -> None:
        with mock.patch.object(exporter, "dotenv_values", return_value={}):
            exporter.export(results, item, self.out)


class ExportTests(ExportCase):
    def test_a_run_with_a_fix_round_is_exported_in_full(self) -> None:
        self.export(self.make_run())
        names = sorted(p.relative_to(self.out).as_posix() for p in self.out.rglob("*")
                       if p.is_file())
        self.assertEqual(names, ["README.md", "cost-report.json", "events.jsonl",
                                 "program/temp.py", "program/tests/test_temp.py",
                                 "progress.log", "report.md", "requirement.txt", "run.json"])
        self.assertEqual((self.out / "progress.log").read_text(encoding="utf-8"),
                         "[qa] #1: 6 passed, 1 failed\n")
        readme = (self.out / "README.md").read_text(encoding="utf-8")
        self.assertIn("`todo-cli`", readme)
        self.assertIn("#1: 6 passed, 1 failed; #2: 7 passed, 0 failed", readme)

    def test_host_paths_are_replaced(self) -> None:
        self.export(self.make_run())
        for path in self.out.rglob("*"):
            if path.is_file():
                self.assertNotIn(str(self.root), path.read_text(encoding="utf-8"), path)
        self.assertIn("<workspace>", (self.out / "program" / "temp.py").read_text())

    def test_an_existing_bundle_is_replaced_whole(self) -> None:
        self.out.mkdir()
        (self.out / "stale.txt").write_text("old", encoding="utf-8")
        self.export(self.make_run())
        self.assertFalse((self.out / "stale.txt").exists())
        self.assertEqual([p.name for p in self.out.parent.iterdir()], ["sample-run"])


class RefusalTests(ExportCase):
    def assert_refused(self, results: Path, words: str) -> None:
        with self.assertRaises(exporter.ExportRefused) as caught:
            self.export(results)
        self.assertIn(words, str(caught.exception))
        self.assertFalse(self.out.exists())

    def test_a_run_that_did_not_complete_is_refused(self) -> None:
        self.assert_refused(self.make_run(status="failed"), "not 'completed'")

    def test_a_run_that_never_failed_a_test_is_refused(self) -> None:
        self.assert_refused(self.make_run(failures=(0,)), "no QA review found a failing test")

    def test_a_run_whose_failure_was_never_fixed_is_refused(self) -> None:
        self.assert_refused(self.make_run(failures=(1, 1)), "no QA review found a failing test")

    def test_a_secret_shaped_string_is_redacted(self) -> None:
        self.export(self.make_run(extra=f"KEY = '{PLANTED}'\n"))
        text = (self.out / "program" / "temp.py").read_text(encoding="utf-8")
        self.assertNotIn(PLANTED, text)
        self.assertIn("[REDACTED]", text)

    def test_an_unknown_item_is_refused(self) -> None:
        with self.assertRaises(exporter.ExportRefused):
            self.export(self.make_run(), item="nope")

    def test_main_reports_a_refusal_with_exit_2(self) -> None:
        results = self.make_run(status="failed")
        with mock.patch.object(exporter, "dotenv_values", return_value={}), \
                mock.patch("sys.stderr"):
            code = exporter.main([str(results), "todo-cli", "--out", str(self.out)])
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
