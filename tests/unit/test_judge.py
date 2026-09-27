"""Judge failures are never scores or policy decisions."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from nl2sql_agent.evaluation.judge import judge_sql, parse_score


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("<score>yes</score>", True),
        ("<score>no</score>", False),
        ("yes", None),
        ("<think>trace</think><score>yes</score>", None),
        ("", None),
    ],
)
def test_score_contract(text, expected):
    assert parse_score(text) is expected


def test_judge_is_evaluation_only():
    client = Mock()
    client.chat.return_value = SimpleNamespace(
        message=SimpleNamespace(content="<score>yes</score>")
    )
    assert judge_sql(client, "SELECT 1") == {"score": True, "outcome": "scored"}
    assert client.chat.call_args.kwargs["think"] is False
    client.chat.side_effect = RuntimeError("offline")
    assert judge_sql(client, "SELECT 1") == {"score": None, "outcome": "judge_failure"}
