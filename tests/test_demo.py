"""The offline demo runs the whole team with no key, no Docker and no network.

One run happens in this process (so coverage measures ``demo``), with Docker and the
network pointed at addresses that can't answer, and no API key. A second run is the real
``python -m demo`` command, whose transcript must match ``docs/assets/demo.txt``.
"""

import contextlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import time
import unittest
from pathlib import Path
from unittest import mock

from demo.__main__ import BANNER, main
from demo.transcript import normalize

REPO_ROOT = Path(__file__).resolve().parents[1]
TRANSCRIPT = REPO_ROOT / "docs" / "assets" / "demo.txt"
OFFLINE = {"DOCKER_HOST": "unix:///nonexistent/docker.sock",
           "HTTPS_PROXY": "http://127.0.0.1:9", "HTTP_PROXY": "http://127.0.0.1:9"}
STAGES = ("[pm]", "[handoff]", "[coder]", "[reflect]", "[qa] #1", "[fix]", "[qa] #2",
          "[finish]")


def offline_environment() -> dict[str, str]:
    env = {key: value for key, value in os.environ.items()
           if key not in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")}
    return {**env, **OFFLINE}


def files_folder(stderr: str) -> Path:
    return Path(re.search(r"\[demo\] files: (.+)", stderr).group(1))


class InProcessDemoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.dict(os.environ, offline_environment(), clear=True), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            cls.code = main([])
        cls.stdout, cls.stderr = out.getvalue(), err.getvalue()
        cls.final = json.loads(cls.stdout)
        cls.folder = files_folder(cls.stderr)

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.folder, ignore_errors=True)

    def test_the_run_completes(self) -> None:
        self.assertEqual(self.code, 0)
        self.assertEqual((self.final["status"], self.final["end_reason"]),
                         ("completed", "complete"))

    def test_it_is_labeled_simulated_at_the_start_and_the_end(self) -> None:
        lines = self.stderr.splitlines()
        self.assertEqual((lines[0], lines[-1]), (BANNER, BANNER))

    def test_every_stage_appears_in_order(self) -> None:
        positions = [self.stderr.index(stage) for stage in STAGES]
        self.assertEqual(positions, sorted(positions))

    def test_qa_finds_the_defect_and_the_fix_round_resolves_it(self) -> None:
        self.assertRegex(self.stderr, r"\[qa\] #1: 6 passed, 1 failed, 0 errors → 1 blocking")
        self.assertRegex(self.stderr, r"\[qa\] #2: 7 passed, 0 failed, 0 errors → complete")
        program = Path(self.final["workspace"]) / "temp.py"
        self.assertIn("# accepts a leading sign", program.read_text(encoding="utf-8"))

    def test_it_writes_its_records_in_the_temporary_folder(self) -> None:
        self.assertTrue((Path(self.final["workspace"]) / ".qa" / "report.md").is_file())
        self.assertEqual(len(list((self.folder / "cost_reports").glob("*.json"))), 1)
        self.assertEqual(len(list((self.folder / ".runs").glob("*/events.jsonl"))), 1)


class CommandTests(unittest.TestCase):
    def test_python_m_demo_is_offline_fast_and_matches_the_recorded_transcript(self) -> None:
        before = _git_status()
        started = time.monotonic()
        result = subprocess.run(
            [sys.executable, "-m", "demo"], cwd=REPO_ROOT, env=offline_environment(),
            capture_output=True, text=True, timeout=120, check=False,
        )
        elapsed = time.monotonic() - started
        shutil.rmtree(files_folder(result.stderr), ignore_errors=True)
        self.assertEqual(result.returncode, 0, result.stderr[-2000:])
        self.assertLess(elapsed, 60)
        self.assertEqual(json.loads(result.stdout)["status"], "completed")
        self.assertEqual(_git_status(), before)
        if not TRANSCRIPT.exists():
            self.skipTest("docs/assets/demo.txt is created by scripts/record_demo.py")
        self.assertEqual(normalize(result.stderr), TRANSCRIPT.read_text(encoding="utf-8"))


def _git_status() -> str | None:
    try:
        return subprocess.run(["git", "status", "--porcelain"], cwd=REPO_ROOT,
                              capture_output=True, text=True, check=False).stdout
    except OSError:
        return None


if __name__ == "__main__":
    unittest.main()
