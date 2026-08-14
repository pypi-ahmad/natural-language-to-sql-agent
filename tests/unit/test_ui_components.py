"""Tests for user-visible Streamlit provider controls."""

from streamlit.testing.v1 import AppTest


def _sidebar_app() -> AppTest:
    return AppTest.from_string(
        "from nl2sql_agent.ui.components import render_sidebar\nrender_sidebar()"
    ).run()


def test_sidebar_shows_only_approved_cloud_models():
    app = _sidebar_app()
    assert app.selectbox[0].options == [
        "Ollama",
        "Hugging Face",
        "OpenAI",
        "Anthropic",
        "Gemini",
        "xAI",
    ]

    app.selectbox[0].select("OpenAI").run()
    assert app.selectbox[1].options == ["gpt-5.6-luna", "gpt-5.6-terra"]
    assert len(app.button) == 0


def test_sidebar_accepts_custom_hugging_face_model():
    app = _sidebar_app()
    app.selectbox[0].select("Hugging Face").run()
    assert app.selectbox[1].proto.accept_new_options is True
    assert app.selectbox[1].proto.placeholder == (
        "Select or enter namespace/model[:routing-policy]"
    )


def test_run_result_shows_token_usage_and_estimated_cost():
    app = AppTest.from_string(
        """
from nl2sql_agent.ui.components import render_run_result
render_run_result(
    final_answer="Done",
    sql_query="SELECT 1",
    columns=None,
    raw_rows=None,
    model="gpt-5.6-luna",
    token_usage={"input_tokens": 1000, "output_tokens": 500},
)
"""
    ).run()

    assert [metric.label for metric in app.metric] == [
        "Input tokens",
        "Output tokens",
        "Estimated cost",
    ]
    assert [metric.value for metric in app.metric] == ["1,000", "500", "$0.000800"]
    assert "Compatibility estimate uses standard rates" in app.caption[-1].value
