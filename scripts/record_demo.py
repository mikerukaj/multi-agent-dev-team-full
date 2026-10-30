"""Record ``python -m demo`` as docs/assets/demo.txt and an animated docs/assets/demo.svg.

The SVG is a self-contained terminal replay (inline CSS animation, no scripts or external
fonts) that GitHub shows inline. Lines appear at an even, readable pace and the whole
replay lasts under a minute, so its timing is not the run's real timing, which is a few
seconds. The title bar says it is a simulated run. The demo is deterministic apart from
durations and IDs, which ``demo.transcript.normalize`` replaces.

Usage:
    python scripts/record_demo.py [--out docs/assets]
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from xml.sax.saxutils import escape

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from demo.transcript import normalize  # noqa: E402 (needs the repository on the path)

WIDTH, LINE_HEIGHT, TOP, LEFT = 920, 19, 46, 16
SECONDS_PER_LINE, HOLD_SECONDS = 1.4, 8.0
COLORS = {"background": "#0d1117", "bar": "#161b22", "text": "#c9d1d9", "dim": "#8b949e",
          "banner": "#e3b341", "bad": "#f85149", "good": "#3fb950", "agent": "#79c0ff"}


def run_demo() -> tuple[int, str]:
    """Run ``python -m demo`` offline (no API key) and return its exit code and stderr."""
    env = {key: value for key, value in os.environ.items()
           if key not in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")}
    result = subprocess.run([sys.executable, "-m", "demo"], cwd=REPO_ROOT, env=env,
                            capture_output=True, text=True, timeout=300, check=False)
    return result.returncode, result.stderr


def line_color(line: str) -> str:
    """The colour a progress line is drawn in, by what it reports."""
    if line.startswith("[demo]"):
        return COLORS["banner"] if "SIMULATED" in line else COLORS["dim"]
    if " failed" in line and not line.startswith("[qa] #") or "1 blocking" in line:
        return COLORS["bad"]
    if "→ complete" in line or line.startswith("[finish] completed"):
        return COLORS["good"]
    if line.startswith("[step"):
        return COLORS["dim"]
    return COLORS["agent"] if line.startswith(("[pm]", "[coder]", "[qa]", "[a2a]")) \
        else COLORS["text"]


def render_svg(lines: list[str]) -> str:
    """An animated terminal that reveals ``lines`` one by one, then holds and repeats."""
    total = len(lines) * SECONDS_PER_LINE + HOLD_SECONDS
    height = TOP + LINE_HEIGHT * len(lines) + 20
    keyframes, texts = [], []
    for index, line in enumerate(lines):
        start = round(index * SECONDS_PER_LINE / total * 100, 2)
        keyframes.append(f"@keyframes l{index}{{0%,{start}%{{opacity:0}}"
                         f"{min(start + 0.5, 100)}%,100%{{opacity:1}}}}")
        y = TOP + LINE_HEIGHT * index
        texts.append(f'<text x="{LEFT}" y="{y}" fill="{line_color(line)}" '
                     f'style="animation:l{index} {total:.1f}s linear infinite">'
                     f"{escape(line)}</text>")
    style = ("text{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;"
             "font-size:13px;white-space:pre;opacity:0}" + "".join(keyframes))
    return "\n".join([
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}" '
        f'viewBox="0 0 {WIDTH} {height}" role="img" '
        'aria-label="Simulated run of python -m demo: the agents plan, code, fail a test, '
        'fix it and pass">',
        f"<style>{style}</style>",
        f'<rect width="{WIDTH}" height="{height}" rx="8" fill="{COLORS["background"]}"/>',
        f'<rect width="{WIDTH}" height="26" rx="8" fill="{COLORS["bar"]}"/>',
        *(f'<circle cx="{18 + 18 * n}" cy="13" r="5" fill="{color}"/>'
          for n, color in enumerate(("#ff5f56", "#ffbd2e", "#27c93f"))),
        f'<text x="{WIDTH // 2}" y="17" text-anchor="middle" fill="{COLORS["dim"]}" '
        'style="opacity:1">Simulated run · python -m demo</text>',
        *texts,
        "</svg>",
    ]) + "\n"


def main(argv: list[str] | None = None) -> int:
    """Record the demo into ``--out``; returns the demo's exit code."""
    parser = argparse.ArgumentParser(prog="python scripts/record_demo.py",
                                     description="Record the offline demo as text and SVG.")
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "docs" / "assets",
                        help="folder for demo.txt and demo.svg")
    args = parser.parse_args(argv)
    code, stderr = run_demo()
    folder = re.search(r"\[demo\] files: (.+)", stderr)
    if folder:
        shutil.rmtree(folder.group(1), ignore_errors=True)
    if code != 0:
        print(stderr, file=sys.stderr)
        return code
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "demo.txt").write_text(normalize(stderr), encoding="utf-8")
    # The replay shows the run's own durations; only the temporary folder is hidden.
    shown = [re.sub(r"\[demo\] files: .+", "[demo] files: /tmp/demo-…", line)
             for line in stderr.splitlines()]
    (args.out / "demo.svg").write_text(render_svg(shown), encoding="utf-8")
    print(f"wrote {args.out / 'demo.txt'} and {args.out / 'demo.svg'}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
