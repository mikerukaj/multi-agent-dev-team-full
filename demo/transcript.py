"""The demo's progress transcript with run-specific details replaced, so runs compare equal.

Durations, A2A task IDs and the temporary folder change on every run; everything else
the demo prints is fixed by its script. ``docs/assets/demo.txt`` is stored in this form,
and ``tests/test_demo.py`` checks a fresh run against it.
"""

import re

_RULES = (
    (re.compile(r"\(\d+(?:\.\d+)? s\)"), "(<t> s)"),
    (re.compile(r"task [0-9a-f]{8}…"), "task <id>…"),
    (re.compile(r"\[demo\] files: .+"), "[demo] files: <tmp>"),
)


def normalize(stderr: str) -> str:
    """``stderr`` with durations, task IDs and the temporary folder replaced."""
    lines = []
    for line in stderr.splitlines():
        for pattern, replacement in _RULES:
            line = pattern.sub(replacement, line)
        lines.append(line)
    return "\n".join(lines) + "\n"
