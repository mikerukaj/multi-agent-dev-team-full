"""The published documentation is self-contained, correct and free of secrets.

Every relative link, anchor and backticked repository path in the published Markdown
must resolve; nothing may point at the private planning folders; every documented
command must exist (and the offline ones must answer ``--help``); the README stays short
and readable; and no published file holds anything shaped like an Anthropic key.
"""

import importlib.util
import os
import re
import subprocess
import sys
import unittest
from pathlib import Path

from observability.redaction import ANTHROPIC_KEY_PATTERN

REPO_ROOT = Path(__file__).resolve().parents[1]
PRIVATE = re.compile(r"(?<![\w.-])(specs|\.specify|\.claude)/")
LINK = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)\)|<(?:a|img)\s[^>]*(?:href|src)=\"([^\"]+)\"")
BACKTICK = re.compile(r"`([^`\s]+)`")
COMMAND = re.compile(r"python3?(?:\.12)? -m ([A-Za-z_][\w.]*)|(scripts/[\w.-]+)")
REQUIREMENT_ID = re.compile(r"\b(FR|SC)-\d{3}\b")
OFFLINE_COMMANDS = ("demo", "cost.audit", "orchestration.health", "benchmarks.run_benchmark",
                    "orchestration.team")
REQUIRED_HEADINGS = {
    "README.md": ["## What it does", "## Highlights", "## How it works",
                  "## Quick start (10 minutes)", "## Run with Docker Compose", "## Results",
                  "## Documentation", "## Where to look", "## Project layout",
                  "## Known limitations", "## License"],
    "docs/ARCHITECTURE.md": ["## Overview", "## Data flow", "## Agents",
                             "### Product Manager", "### Coder", "### QA & Debugger",
                             "## Orchestration", "## Messaging and tools",
                             "## Design trade-offs"],
    "docs/REFLECTION.md": ["## Three design decisions", "## A bug and how it was resolved",
                           "## What I would do differently"],
    "docs/E2E_RESULTS.md": ["## Results", "## Failures and fixes", "## Final status"],
    "docs/PERFORMANCE.md": ["## Method", "## Before", "## Highest-cost interaction",
                            "## Optimization", "## After", "## Result"],
    "docs/DEMO_GUIDE.md": ["## Pre-flight checklist", "## Core demo (10 minutes)",
                           "## Deep dive (optional, 10 minutes)", "## If the live service fails"],
}


def repository_files() -> set[str]:
    """Tracked files plus new files not yet committed (but never ignored ones)."""
    try:
        result = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
            cwd=REPO_ROOT, capture_output=True, text=True, check=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise unittest.SkipTest(f"git is not available: {error}") from error
    return {line for line in result.stdout.splitlines() if (REPO_ROOT / line).exists()}


FILES = repository_files()
FOLDERS = {str(Path(name).parents[n]) for name in FILES
           for n in range(len(Path(name).parents) - 1)}
TOP_LEVEL = {name.split("/")[0] for name in FILES}
MARKDOWN = sorted(name for name in FILES if name.endswith(".md") and (
    name in ("README.md", "CONTRIBUTING.md") or name.startswith("docs/")))


def read(name: str) -> str:
    return (REPO_ROOT / name).read_text(encoding="utf-8")


def slug(heading: str) -> str:
    """The anchor GitHub gives a heading."""
    text = re.sub(r"[`*_]", "", heading.strip().lstrip("#").strip().lower())
    return re.sub(r"[^\w\- ]", "", text).replace(" ", "-")


def anchors(name: str) -> set[str]:
    return {slug(line) for line in read(name).splitlines() if line.startswith("#")}


def exists(path: str) -> bool:
    path = path.rstrip("/")
    return path in FILES or path in FOLDERS


def prose(text: str) -> str:
    """``text`` without fenced code blocks."""
    return re.sub(r"```.*?```", "", text, flags=re.S)


class LinkTests(unittest.TestCase):
    def test_every_relative_link_and_anchor_resolves(self) -> None:
        for name in MARKDOWN:
            base = Path(name).parent
            for match in LINK.finditer(read(name)):
                target = match.group(1) or match.group(2)
                if re.match(r"[a-z]+:", target):
                    continue
                path, _, anchor = target.partition("#")
                resolved = os.path.normpath(base / path) if path else name
                with self.subTest(file=name, link=target):
                    self.assertTrue(exists(resolved), f"{resolved} does not exist")
                    if anchor and resolved.endswith(".md"):
                        self.assertIn(anchor, anchors(resolved))

    def test_every_backticked_repository_path_exists(self) -> None:
        for name in MARKDOWN:
            for path in BACKTICK.findall(prose(read(name))):
                if "/" not in path or path.split("/")[0] not in TOP_LEVEL \
                        or re.search(r"[<>*{}$…]", path):
                    continue
                with self.subTest(file=name, path=path):
                    self.assertTrue(exists(path), f"{path} does not exist")

    def test_nothing_points_at_the_private_planning_folders(self) -> None:
        for name in MARKDOWN:
            with self.subTest(file=name):
                self.assertIsNone(PRIVATE.search(read(name)))
        for name in (n for n in FILES if n.startswith("docs/api/") and n.endswith(".html")):
            with self.subTest(file=name):
                self.assertNotRegex(read(name), r"href=\"[^\"]*(specs|\.specify|\.claude)/")


class CommandTests(unittest.TestCase):
    def test_every_documented_command_exists(self) -> None:
        sys.path.insert(0, str(REPO_ROOT))
        try:
            for name in MARKDOWN:
                for module, script in COMMAND.findall(read(name)):
                    with self.subTest(file=name, command=module or script):
                        if module:
                            self.assertIsNotNone(importlib.util.find_spec(module), module)
                        else:
                            self.assertIn(script, FILES)
                            if script.endswith(".sh"):
                                self.assertTrue(os.access(REPO_ROOT / script, os.X_OK))
        finally:
            sys.path.remove(str(REPO_ROOT))

    def test_the_offline_commands_answer_help(self) -> None:
        scripts = [["scripts/" + Path(n).name] for n in FILES
                   if n.startswith("scripts/") and n.endswith(".py")]
        commands = [["-m", module] for module in OFFLINE_COMMANDS] + scripts
        env = {**os.environ, "ANTHROPIC_API_KEY": "sk-ant-docs-test-not-a-key"}
        for command in commands:
            with self.subTest(command=command):
                result = subprocess.run([sys.executable, *command, "--help"], cwd=REPO_ROOT,
                                        env=env, capture_output=True, text=True, timeout=120)
                self.assertEqual(result.returncode, 0, result.stderr[-500:])
                self.assertIn("usage:", result.stdout)


class ContentTests(unittest.TestCase):
    def test_required_sections_are_present(self) -> None:
        for name, headings in REQUIRED_HEADINGS.items():
            lines = read(name).splitlines()
            for heading in headings:
                with self.subTest(file=name, heading=heading):
                    self.assertIn(heading, lines)

    def test_the_readme_is_short_and_free_of_internal_labels(self) -> None:
        text = read("README.md")
        self.assertLessEqual(len(text.splitlines()), 350)
        self.assertIsNone(REQUIREMENT_ID.search(text))
        self.assertNotIn("Increment", text)
        self.assertNotIn("Course:", text)

    def test_the_project_layout_names_every_top_level_folder(self) -> None:
        text = read("README.md")
        layout = text[text.index("## Project layout"):text.index("## Known limitations")]
        folders = {top for top in TOP_LEVEL if (REPO_ROOT / top).is_dir()}
        for folder in sorted(folders):
            with self.subTest(folder=folder):
                self.assertIn(f"{folder}/", layout)

    def test_the_reflection_is_600_to_1000_words(self) -> None:
        text = prose(read("docs/REFLECTION.md"))
        words = len(" ".join(line for line in text.splitlines()
                             if not line.startswith("#")).split())
        self.assertGreaterEqual(words, 600)
        self.assertLessEqual(words, 1000)


class SecretTests(unittest.TestCase):
    def test_no_published_file_holds_a_key_shaped_string(self) -> None:
        published = [name for name in FILES if name in ("README.md", "CONTRIBUTING.md")
                     or name.startswith(("docs/", "benchmarks/results/"))]
        for name in published:
            try:
                text = read(name)
            except UnicodeDecodeError:
                continue
            with self.subTest(file=name):
                self.assertIsNone(ANTHROPIC_KEY_PATTERN.search(text))


if __name__ == "__main__":
    unittest.main()
