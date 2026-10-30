"""What the simulated model says in the offline demo: one requirement, one real defect.

The first draft of ``temp.py`` finds the number with ``PATTERN.search`` and a pattern
with no sign, so ``-40F`` is read as ``40F`` and prints ``4.4C``. QA's test for it fails,
QA's review reports it, and the fix round writes ``FIXED_DRAFT``, which accepts a
leading sign. Whether a test passes is decided by ``demo.sandbox`` from the file on disk
(``FIX_MARKER``), not by this script, so the story follows what the Coder actually wrote.
"""

REQUIREMENT = (
    "A command-line tool temp.py that converts a temperature like '100C' or '-40F' to the "
    "other scale and prints it rounded to one decimal place, for example '212.0F'. "
    "Malformed input prints an error to stderr and exits with code 2."
)

CONVERTS = ("A value like '100C' or '-40F' is converted to the other scale and printed "
            "rounded to one decimal place, for example '212.0F'.")
MALFORMED = "Malformed input prints an error to stderr and exits with code 2."
PARSES = "'100C', '37.5F' and '-40F' are parsed into a number and a scale."

SPEC = {
    "name": "Temperature converter",
    "description": "A command-line tool that converts a temperature between Celsius and "
                   "Fahrenheit.",
    "acceptance_criteria": [CONVERTS, MALFORMED],
    "assumptions": ["The scale letter may be upper or lower case."],
    "tasks": [
        {"title": "Parse the temperature",
         "description": "Read a value like '100C' or '-40F' into a number and a scale.",
         "acceptance_criteria": [PARSES], "priority": "high"},
        {"title": "Convert and print",
         "description": "Convert to the other scale, print it rounded, and handle bad input.",
         "acceptance_criteria": [CONVERTS, MALFORMED], "priority": "high"},
    ],
    "rejection_reason": "",
}

FIX_MARKER = "# accepts a leading sign"

_PROGRAM = '''"""Convert a temperature like '100C' or '-40F' to the other scale."""

import re
import sys

{pattern}


def parse_temperature(text: str) -> tuple[float, str]:
    """Split '100C' into (100.0, 'C'); raise ValueError for anything else."""
    match = {match}
    if not match:
        raise ValueError(f"not a temperature: {{text!r}}")
    return float(match.group(1)), match.group(2)


def convert(value: float, scale: str) -> str:
    """The temperature on the other scale, rounded to one decimal place."""
    if scale == "C":
        return f"{{value * 9 / 5 + 32:.1f}}F"
    return f"{{(value - 32) * 5 / 9:.1f}}C"


def main(argv: list[str]) -> int:
    """Print the converted temperature; 2 for missing or malformed input."""
    if len(argv) != 2:
        print("usage: python temp.py TEMPERATURE (for example 100C)", file=sys.stderr)
        return 2
    try:
        print(convert(*parse_temperature(argv[1])))
    except ValueError as error:
        print(f"error: {{error}}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
'''

FIRST_DRAFT = _PROGRAM.format(
    pattern='PATTERN = re.compile(r"(\\d+(?:\\.\\d+)?)([CF])")',
    match="PATTERN.search(text.strip().upper())",
)
FIXED_DRAFT = _PROGRAM.format(
    pattern=f'PATTERN = re.compile(r"([+-]?\\d+(?:\\.\\d+)?)([CF])")  {FIX_MARKER}',
    match="PATTERN.fullmatch(text.strip().upper())",
)

TEST_FILE = "tests/test_temp.py"
FAILING_TEST = f"{TEST_FILE}::test_negative_forty_fahrenheit"
# The test IDs real pytest reports for QA_TESTS (checked against both drafts in the
# sandbox image: the first draft fails one test, the fixed draft passes all seven).
TEST_NAMES = (
    "test_celsius_to_fahrenheit", "test_fahrenheit_to_celsius",
    "test_negative_forty_fahrenheit", "test_rounds_to_one_decimal",
    "test_malformed_exits_2[]", "test_malformed_exits_2[hot]", "test_malformed_exits_2[40K]",
)
FAILURE_MESSAGE = "AssertionError: assert '4.4C' == '-40.0C'"
QA_TESTS = {
    "test_files": [{
        "path": TEST_FILE,
        "content": '''"""QA's tests for temp.py, written from the specification."""

import subprocess
import sys

import pytest

from temp import convert, parse_temperature


def run(*args):
    return subprocess.run([sys.executable, "temp.py", *args], capture_output=True, text=True)


def test_celsius_to_fahrenheit():
    assert convert(*parse_temperature("100C")) == "212.0F"


def test_fahrenheit_to_celsius():
    assert convert(*parse_temperature("212F")) == "100.0C"


def test_negative_forty_fahrenheit():
    assert convert(*parse_temperature("-40F")) == "-40.0C"


def test_rounds_to_one_decimal():
    assert convert(*parse_temperature("37.5F")) == "3.1C"


@pytest.mark.parametrize("bad", ["", "hot", "40K"])
def test_malformed_exits_2(bad):
    result = run(bad)
    assert result.returncode == 2 and result.stderr
''',
        "criteria": [PARSES, CONVERTS, MALFORMED],
    }],
    "notes": "The interface is parse_temperature(text) and convert(value, scale).",
}

REVIEW_FAIL = {
    "findings": [{
        "kind": "failing_test", "rule": "", "file": "temp.py", "location": "parse_temperature",
        "problem": "'-40F' is read as 40F, so the tool prints 4.4C instead of -40.0C.",
        "expected": "'-40F' converts to '-40.0C', as the specification's example says.",
        "likely_cause": "PATTERN has no sign and PATTERN.search skips the leading '-'.",
        "fix_instruction": "Allow an optional leading sign in PATTERN and match the whole "
                           "input with fullmatch.",
        "test_ids": [FAILING_TEST], "same_as": "",
    }],
    "regression_tests": [],
    "summary": "6 of 7 tests pass; negative temperatures lose their sign.",
}
REVIEW_PASS = {"findings": [], "regression_tests": [],
               "summary": "All 7 tests pass and the code matches the specification."}

CRITIQUES = [
    {"items": [{"kind": "edge_case", "location": "parse_temperature",
                "description": "Lower-case scale letters such as '100c' may not be accepted.",
                "suggested_change": "Upper-case the input before matching."}],
     "overall": "Small and readable; check the input forms the spec allows."},
    {"items": [{"kind": "edge_case", "location": "PATTERN",
                "description": "A leading '+' sign is now accepted too; that is harmless.",
                "suggested_change": "Keep it."}],
     "overall": "The sign fix is minimal and keeps every other behavior."},
]

# Tool steps per Coder session, chosen by the session's task text.
BUILD_STEPS = {
    "T1": [("write_file", {"path": "temp.py", "content": FIRST_DRAFT,
                           "purpose": "Write the parser and the command-line entry point."}),
           ("exec_python", {"path": "temp.py", "purpose": "Check that it runs."})],
    "T2": [("read_file", {"path": "temp.py", "purpose": "Check what task T1 left."}),
           ("exec_python", {"path": "temp.py", "purpose": "Run it again after T2."})],
}
REVISION_STEPS = [("exec_python", {"path": "temp.py", "purpose": "Re-run after the review."})]
FIX_STEPS = [
    ("write_file", {"path": "temp.py", "content": FIXED_DRAFT,
                    "purpose": "Accept a leading sign and match the whole input."}),
    ("exec_python", {"path": "temp.py", "purpose": "Run the fixed program."}),
]

# Simulated token counts per reply kind, so the run's cost report is filled in.
USAGE = {
    "spec": (2_400, 900), "critique": (3_100, 350), "summary": (2_800, 220),
    "loop": (3_600, 420), "tests": (2_900, 1_100), "review": (3_800, 380),
    "disputes": (1_000, 100),
}
