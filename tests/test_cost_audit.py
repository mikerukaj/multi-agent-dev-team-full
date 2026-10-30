"""Per-interaction cost ranking and before/after comparison (``python -m cost.audit``)."""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from cost.audit import (
    compare,
    interaction_rows,
    main,
    rank,
    read_model_calls,
    run_dirs_from_results,
)


def model_call(agent: str, stage: str, operation: str | None, cost: float | None,
               input_tokens: int = 100, output_tokens: int = 50, cache_read: int = 0,
               outcome: str = "ok") -> dict:
    """One ``model_call`` event line as ``events.jsonl`` holds it."""
    details = {"model": "claude-haiku-5-5", "cost_usd": cost, "tokens": {
        "input_tokens": input_tokens, "output_tokens": output_tokens,
        "cache_creation_input_tokens": 10, "cache_read_input_tokens": cache_read}}
    if operation is not None:
        details["operation"] = operation
    return {"ts": "2026-10-29T00:00:00Z", "run_id": "r", "agent": agent, "stage": stage,
            "event": "model_call", "severity": "info", "outcome": outcome, "details": details}


class AuditCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def write_run(self, run_id: str, events: list[dict], report_cost: float | None = None,
                  benchmark: str = "bench") -> dict:
        """A run's events (and cost report); returns its results-file record."""
        run_dir = self.root / benchmark / ".runs" / run_id
        run_dir.mkdir(parents=True)
        lines = [json.dumps(event) for event in events]
        lines.append('{"torn line')  # A crash mid-write must not break the audit.
        (run_dir / "events.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
        report = self.root / "reports" / f"{run_id}.json"
        report.parent.mkdir(exist_ok=True)
        if report_cost is not None:
            report.write_text(json.dumps({"total": {"cost_usd": report_cost}}), encoding="utf-8")
        return {"id": run_id, "run_id": run_id, "status": "completed", "succeeded": True,
                "workspace": str(self.root / benchmark / run_id), "cost_report": str(report),
                "input_tokens": 1000, "output_tokens": 100, "cost_usd": report_cost}

    def write_results(self, name: str, records: list[dict]) -> Path:
        path = self.root / name
        path.write_text(json.dumps({"records": records}), encoding="utf-8")
        return path

    def run_main(self, argv: list[str]) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(argv)
        return code, out.getvalue(), err.getvalue()


class RowTests(AuditCase):
    def test_calls_are_grouped_and_summed_across_runs(self) -> None:
        self.write_run("r1", [model_call("qa", "qa_review", "QATestFilesReply", 0.02),
                              model_call("pm", "plan", "PMSpecReply", 0.05)])
        self.write_run("r2", [model_call("qa", "qa_review", "QATestFilesReply", 0.03)])
        events = [event for run in ("r1", "r2")
                  for event in read_model_calls(self.root / "bench" / ".runs" / run)]
        rows = {row["operation"]: row for row in interaction_rows(events)}
        qa = rows["QATestFilesReply"]
        self.assertEqual((qa["calls"], qa["cost_usd"]), (2, 0.05))
        self.assertEqual(qa["input_tokens"], 200)
        self.assertEqual(qa["billed_tokens"], 200 + 100 + 20)
        self.assertEqual(qa["model"], "claude-haiku-5-5")

    def test_ranking_is_by_cost_then_billed_tokens_with_shares(self) -> None:
        rows = interaction_rows([
            model_call("pm", "plan", "PMSpecReply", 0.01, input_tokens=10),
            model_call("qa", "qa_review", "QAReviewReply", 0.01, input_tokens=900),
            model_call("coder", "build", "tool_turn", 0.02),
        ])
        ranked = rank(rows)
        self.assertEqual([row["operation"] for row in ranked],
                         ["tool_turn", "QAReviewReply", "PMSpecReply"])
        self.assertEqual(ranked[0]["share"], 0.5)

    def test_a_missing_operation_is_unknown_and_a_null_cost_is_counted(self) -> None:
        self.write_run("r1", [model_call("coder", "build", None, None)])
        (row,) = interaction_rows(read_model_calls(self.root / "bench" / ".runs" / "r1"))
        self.assertEqual(row["operation"], "unknown")
        self.assertEqual((row["unpriced_calls"], row["cost_usd"]), (1, 0.0))

    def test_failed_calls_add_tokens_but_not_calls(self) -> None:
        (row,) = interaction_rows([
            model_call("qa", "qa_review", "QAReviewReply", 0.01),
            model_call("qa", "qa_review", "QAReviewReply", None, 0, 0, outcome="failed"),
        ])
        self.assertEqual((row["calls"], row["unpriced_calls"]), (1, 0))


class ResultsAndCompareTests(AuditCase):
    def test_runs_are_found_from_a_results_file(self) -> None:
        record = self.write_run("r1", [model_call("pm", "plan", "PMSpecReply", 0.05)], 0.05)
        crashed = {"id": "x", "run_id": None, "workspace": None}
        pairs = run_dirs_from_results(self.write_results("res.json", [record, crashed]))
        self.assertEqual([run_dir for run_dir, _ in pairs],
                         [self.root / "bench" / ".runs" / "r1"])

    def test_results_mode_prints_a_ranked_table(self) -> None:
        record = self.write_run("r1", [model_call("pm", "plan", "PMSpecReply", 0.05),
                                       model_call("qa", "qa_review", "QAReviewReply", 0.01)],
                                report_cost=0.06)
        code, out, _ = self.run_main(["--results", str(self.write_results("r.json", [record]))])
        self.assertEqual(code, 0)
        lines = out.splitlines()
        self.assertIn("PMSpecReply", lines[1])
        self.assertNotIn("warning", out)

    def test_a_cost_report_mismatch_or_absence_warns_but_exits_0(self) -> None:
        drifted = self.write_run("r1", [model_call("pm", "plan", "PMSpecReply", 0.05)], 0.09)
        absent = self.write_run("r2", [model_call("pm", "plan", "PMSpecReply", 0.05)])
        results = self.write_results("r.json", [drifted, absent])
        code, out, _ = self.run_main(["--results", str(results), "--json"])
        self.assertEqual(code, 0)
        warnings = json.loads(out)["cost_report_mismatch"]
        self.assertEqual(len(warnings), 2)
        self.assertIn("cost report says $0.09", warnings[0])
        self.assertIn("unreadable", warnings[1])

    def test_compare_reports_total_and_per_call_deltas(self) -> None:
        before = [self.write_run("b1", [model_call("pm", "plan", "PMSpecReply", 0.10,
                                                   output_tokens=1000)] * 2, 0.20, "before")]
        after = [self.write_run("a1", [model_call("pm", "plan", "PMSpecReply", 0.06,
                                                  output_tokens=500)] * 3, 0.18, "after")]
        code, out, _ = self.run_main(["--compare", str(self.write_results("b.json", before)),
                                      str(self.write_results("a.json", after)), "--json"])
        self.assertEqual(code, 0)
        result = json.loads(out)
        (row,) = result["interactions"]
        self.assertEqual(row["delta_tokens"], 3 * 610 - 2 * 1110)
        self.assertEqual(row["per_call_delta_tokens_pct"], round((610 - 1110) / 1110 * 100, 1))
        self.assertEqual(row["delta_cost_pct"], -10.0)
        self.assertEqual(result["runs"]["before"][0]["tokens"], 1100)

    def test_compare_keeps_interactions_that_only_one_side_has(self) -> None:
        rows = compare(interaction_rows([model_call("pm", "plan", "PMSpecReply", 0.1)]),
                       interaction_rows([model_call("qa", "qa_review", "QAReviewReply", 0.1)]))
        self.assertEqual([row["operation"] for row in rows], ["PMSpecReply", "QAReviewReply"])
        self.assertIsNone(rows[0]["after"])
        self.assertIsNone(rows[1]["delta_tokens_pct"])


class UsageTests(AuditCase):
    def test_no_readable_events_exits_2_and_names_the_run(self) -> None:
        missing = self.root / "bench" / ".runs" / "gone"
        code, _, err = self.run_main([str(missing)])
        self.assertEqual(code, 2)
        self.assertIn(str(missing), err)

    def test_no_arguments_exits_2(self) -> None:
        self.assertEqual(self.run_main([])[0], 2)

    def test_json_output_parses(self) -> None:
        self.write_run("r1", [model_call("coder", "build", "tool_turn", 0.01)])
        code, out, _ = self.run_main([str(self.root / "bench" / ".runs" / "r1"), "--json"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["interactions"][0]["operation"], "tool_turn")


if __name__ == "__main__":
    unittest.main()
