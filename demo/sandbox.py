"""The offline demo's stand-ins for the Docker sandbox and the Chroma memory store.

Nothing here runs generated code. ``simulated_run_tests`` reads the program the Coder
wrote and reports what real pytest reports for it: the test IDs and the failure match
a sandbox run of ``demo.script``'s tests against each draft. So a fix round makes the
tests pass only if the Coder really wrote the fix to disk.
"""

from pathlib import Path

from demo.script import FAILING_TEST, FAILURE_MESSAGE, FIX_MARKER, TEST_FILE, TEST_NAMES
from orchestration.state import TestCaseResult, TestRun
from tools.python_exec import ExecutionResult

USAGE_LINE = "usage: python temp.py TEMPERATURE (for example 100C)\n"


def simulated_exec_python(
    workspace: Path, path: str, timeout_seconds: float, image: str | None = None,
    guard=None, run_id: str = "",
) -> ExecutionResult:
    """What running ``python <path>`` with no arguments gives: the usage line, exit 2."""
    if not (Path(workspace) / path).is_file():
        raise FileNotFoundError(f"{path} does not exist in the workspace")
    return ExecutionResult(path, 2, "", USAGE_LINE, False, 0.05)


def simulated_run_tests(
    workspace: Path, timeout_seconds: float, image: str, guard=None, run_id: str = "",
) -> TestRun:
    """QA's pytest run: all pass if ``temp.py`` has the fix, else the ``-40F`` test fails."""
    program = Path(workspace) / "temp.py"
    fixed = program.is_file() and FIX_MARKER in program.read_text(encoding="utf-8")
    cases = [_case(name, failed=not fixed and f"{TEST_FILE}::{name}" == FAILING_TEST)
             for name in TEST_NAMES]
    failed = sum(case["outcome"] == "failed" for case in cases)
    return TestRun(
        loaded=True, exit_code=int(failed > 0), timed_out=False,
        passed=len(cases) - failed, failed=failed, errors=0, skipped=0, cases=cases,
        output=f"{failed} failed, {len(cases) - failed} passed in 0.08s" if failed
        else f"{len(cases)} passed in 0.07s",
        duration_seconds=0.08,
    )


def _case(name: str, failed: bool) -> TestCaseResult:
    return TestCaseResult(
        test_id=f"{TEST_FILE}::{name}", file=TEST_FILE,
        outcome="failed" if failed else "passed",
        message=FAILURE_MESSAGE if failed else "",
        details="tests/test_temp.py:24: AssertionError" if failed else "",
    )


class InMemoryMemory:
    """The Coder's long-term memory, kept in a list (Chroma would download a model)."""

    def __init__(
        self, path: Path, collection: str = "coder_memory", guard=None, host=None, port=8000
    ) -> None:
        self.guard = guard
        self.records: list[tuple[str, str, str]] = []

    def add(self, run_id: str, kind: str, text: str) -> str:
        """Store one memory and return its ID."""
        self.records.append((run_id, kind, text))
        return f"{run_id}-{len(self.records)}"

    def query(self, text: str, top_k: int, exclude_run_id: str) -> list:
        """Memories from earlier runs: none, since every demo run starts fresh."""
        return []
