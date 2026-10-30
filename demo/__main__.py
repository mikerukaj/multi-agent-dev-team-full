"""``python -m demo``: watch the whole team work offline, with no API key and no spend.

It builds the real PM, Coder and QA agents on ``demo.client.DemoClient`` (scripted model
replies) and ``demo.sandbox`` (simulated program and test runs), then runs the real team
graph on ``demo.script.REQUIREMENT``. It prints the same progress lines a live run does,
between two lines saying that it is simulated. Everything it writes goes to a new
temporary folder.
"""

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

from agents.coder_agent import CoderAgent, CoderConfig, print_step_progress
from agents.pm_agent import PMAgent, PMConfig
from agents.qa_agent import QAAgent, QAConfig
from demo.client import DemoClient
from demo.sandbox import InMemoryMemory, simulated_exec_python, simulated_run_tests
from demo.script import REQUIREMENT
from orchestration.services import RunServices
from orchestration.team import print_progress, run_team

BANNER = ("[demo] SIMULATED: scripted model replies and simulated sandbox; "
          "no API key, no network, no spend")
MAX_ITERATIONS = 3


def demo_env(folder: Path) -> dict[str, str]:
    """The run's settings: the caller's environment with secrets and tracing switched off."""
    return {**os.environ, "ANTHROPIC_API_KEY": "sk-ant-demo-not-a-key",
            "ANTHROPIC_AUTH_TOKEN": "", "LANGSMITH_TRACING": "false", "LANGSMITH_API_KEY": "",
            "RUN_BUDGET_USD": "", "COST_REPORT_DIR": str(folder / "cost_reports")}


def build_team(folder: Path, services: RunServices) -> tuple[PMAgent, CoderAgent, QAAgent]:
    """The real agents, each on its own scripted client, with the sandbox simulated."""
    pm = PMAgent(PMConfig(), client=DemoClient(), services=services)
    coder = CoderAgent(
        CoderConfig(workspace_root=folder, chroma_path=folder / "chroma"),
        client=DemoClient(), on_step=print_step_progress, services=services,
        memory_factory=InMemoryMemory, run_code=simulated_exec_python,
    )
    qa = QAAgent(QAConfig(), client=DemoClient(), run_tests=simulated_run_tests,
                 services=services)
    return pm, coder, qa


def main(argv: list[str] | None = None) -> int:
    """Run the demo; 0 when the run completes, 1 otherwise (a bug in the demo)."""
    argparse.ArgumentParser(
        prog="python -m demo",
        description="Run the PM -> Coder <-> QA team offline on a temperature converter, "
                    "with scripted model replies and a simulated sandbox.",
    ).parse_args(argv)
    folder = Path(tempfile.mkdtemp(prefix="demo-"))
    print(BANNER, file=sys.stderr, flush=True)
    services = RunServices.create(env=demo_env(folder))
    services.events.subscribers.append(print_progress)
    pm, coder, qa = build_team(folder, services)
    final = run_team(REQUIREMENT, pm, coder, folder, qa=qa, max_iterations=MAX_ITERATIONS,
                     services=services)
    print(json.dumps(services.redactor.redact(final), indent=2))
    print(f"[demo] files: {folder}", file=sys.stderr)
    print(BANNER, file=sys.stderr, flush=True)
    return 0 if final["status"] == "completed" else 1


if __name__ == "__main__":
    sys.exit(main())
