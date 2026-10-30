"""A scripted stand-in for the Anthropic client, for the offline demo.

``DemoClient().beta.messages.create(**request)`` returns a real ``BetaMessage``, chosen
by what the request asks for (its output schema, or a tool-using Coder turn), the way
the live model would be asked. The replies come from ``demo.script``. Usage is filled in
with simulated token counts so the run's cost report has something to show.
"""

import itertools
import json
import re
from types import SimpleNamespace

from anthropic.types.beta import BetaMessage

from agents.coder_agent import CRITIQUE_FORMAT, SUMMARY_FORMAT
from agents.pm_agent import CONSOLIDATION_SCHEMA, SPEC_SCHEMA
from agents.qa_agent import REVIEW_FORMAT, WRITE_TESTS_FORMAT
from demo import script

_ids = itertools.count(1)
ANSWER_IDS = re.compile(r"\[([CF]\d+-\d+)\]")


class DemoClient:
    """Answers every request the team makes from ``demo.script``; records nothing secret."""

    def __init__(self) -> None:
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self.create))
        self.critiques = 0

    def create(self, **request) -> BetaMessage:
        """The scripted reply to ``request``.

        Raises:
            ValueError: for a request the demo has no script for (a bug in the demo).
        """
        kind = request_kind(request)
        if kind == "spec":
            return _reply(request, kind, text=script.SPEC)
        if kind == "critique":
            self.critiques += 1
            return _reply(request, kind,
                          text=script.CRITIQUES[min(self.critiques, len(script.CRITIQUES)) - 1])
        if kind == "summary":
            return _reply(request, kind, text=_summary(current_task(request)))
        if kind == "tests":
            return _reply(request, kind, text=script.QA_TESTS)
        if kind == "review":
            passed = "failed=0" in _all_text(request)
            return _reply(request, kind, text=script.REVIEW_PASS if passed else script.REVIEW_FAIL)
        if kind == "loop":
            return _loop_reply(request)
        raise ValueError(f"the offline demo has no scripted reply for a {kind!r} request")


def request_kind(request: dict) -> str:
    """What a request asks for: spec, consolidate, critique, summary, tests, review,
    disputes, or a tool-using ``loop`` turn."""
    output_format = request.get("output_config", {}).get("format") or {}
    schema = output_format.get("schema", output_format) if output_format else None
    if schema == SPEC_SCHEMA:
        return "spec"
    if schema == CONSOLIDATION_SCHEMA:
        return "consolidate"
    if output_format == CRITIQUE_FORMAT:
        return "critique"
    if output_format == SUMMARY_FORMAT:
        return "summary"
    if schema == WRITE_TESTS_FORMAT:
        return "tests"
    if schema == REVIEW_FORMAT:
        return "review"
    return "disputes" if schema is not None else "loop"


def current_task(request: dict) -> str:
    """The task this Coder session is working on (earlier turns are listed above it)."""
    first = _text(request["messages"][0]["content"])
    return first.rsplit("Task:\n", 1)[-1]


def _loop_reply(request: dict) -> BetaMessage:
    """The session's next scripted tool step, or "Done." when its steps are used up."""
    steps = _steps_for(current_task(request))
    taken = sum(1 for message in request["messages"] if _is_tool_result(message))
    if taken < len(steps):
        name, tool_input = steps[taken]
        block = {"type": "tool_use", "id": f"toolu_demo_{next(_ids)}", "name": name,
                 "input": tool_input}
        return _message(request, "loop", [block], "tool_use")
    return _message(request, "loop", [{"type": "text", "text": "Done."}], "end_turn")


def _steps_for(task: str) -> list[tuple[str, dict]]:
    if task.startswith("You are fixing:"):
        return script.FIX_STEPS
    if task.startswith("Self-review before QA"):
        return script.REVISION_STEPS
    match = re.search(r"Task (T\d+) of", task)
    return script.BUILD_STEPS.get(match.group(1) if match else "", script.REVISION_STEPS)


def _summary(task: str) -> dict:
    """The Coder's closing summary, answering every C... or F... ID its task listed."""
    fixing = task.startswith("You are fixing:")
    responses = [{"finding_id": answer_id, "action": "fixed", "reason": ""}
                 for answer_id in dict.fromkeys(ANSWER_IDS.findall(task))]
    explanation = ("Allowed an optional leading sign and matched the whole input, so -40F "
                   "converts to -40.0C." if fixing else
                   "temp.py parses the temperature and converts it to the other scale.")
    return {"plan": ["Parse the value and scale", "Convert and print, rounded",
                     "Exit 2 with a message on bad input"],
            "explanation": explanation, "main_file": "temp.py", "finding_responses": responses}


def _is_tool_result(message: dict) -> bool:
    content = message.get("content")
    return message.get("role") == "user" and isinstance(content, list) and any(
        isinstance(block, dict) and block.get("type") == "tool_result" for block in content)


def _text(content) -> str:
    if isinstance(content, str):
        return content
    return "\n".join(block.get("text", "") for block in content if isinstance(block, dict))


def _all_text(request: dict) -> str:
    return "\n".join(_text(message.get("content", "")) for message in request["messages"])


def _reply(request: dict, kind: str, text: dict) -> BetaMessage:
    return _message(request, kind, [{"type": "text", "text": json.dumps(text)}], "end_turn")


def _message(request: dict, kind: str, content: list[dict], stop_reason: str) -> BetaMessage:
    input_tokens, output_tokens = script.USAGE[kind]
    return BetaMessage.model_validate({
        "id": f"msg_demo_{next(_ids)}", "type": "message", "role": "assistant",
        "model": request["model"], "content": content, "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens,
                  "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0},
    })
