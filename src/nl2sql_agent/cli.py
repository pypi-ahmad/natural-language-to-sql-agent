"""Command-line entry point.

Examples::

    # Run a single question against the configured default (Ollama).
    uv run nl2sql-agent ask "How many employees are there?"

    # Override the model and provider.
    uv run nl2sql-agent ask --provider openai --model gpt-4o-mini \\
        --api-key "$OPENAI_API_KEY" "What is the total salary?"

    # Show the resolved configuration.
    uv run nl2sql-agent config
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

from .agent import NL2SQLAgent
from .config import get_settings
from .llm import LLMProviderError, build_chat_model
from .utils import configure_logging, get_logger

logger = get_logger(__name__)


def _build_agent(
    *,
    provider: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
) -> NL2SQLAgent:
    settings = get_settings()
    # Apply CLI overrides via env-style fields.
    if provider:
        settings.provider = provider  # type: ignore[assignment]
    if model:
        settings.model = model
    if api_key:
        if settings.provider == "openai":
            settings.openai_api_key = api_key
        elif settings.provider == "gemini":
            settings.google_api_key = api_key
        elif settings.provider == "anthropic":
            settings.anthropic_api_key = api_key
    try:
        llm = build_chat_model(settings)
    except LLMProviderError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
    return NL2SQLAgent(llm, settings=settings)


def cmd_ask(args: argparse.Namespace) -> int:
    configure_logging(level="WARNING")
    agent = _build_agent(
        provider=args.provider,
        model=args.model,
        api_key=args.api_key,
    )
    result = agent.run(args.question)
    print(result.get("final_answer", ""))
    if args.show_sql:
        print("\n--- SQL ---\n", result.get("sql_query", ""), sep="")
    return 0


def cmd_config(args: argparse.Namespace) -> int:
    settings = get_settings()
    print(json.dumps(settings.model_dump(mode="json"), indent=2))
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    """Launch the Streamlit app."""
    import subprocess

    cmd = [
        sys.executable, "-m", "streamlit", "run",
        "src/nl2sql_agent/ui/streamlit_app.py",
        "--server.port", str(args.port),
        "--server.address", args.host,
    ]
    return subprocess.call(cmd)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nl2sql-agent",
        description="Natural Language to SQL data analyst agent.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_ask = sub.add_parser("ask", help="Ask a single question and print the answer.")
    p_ask.add_argument("question", help="The question to ask.")
    p_ask.add_argument("--provider", help="Override the LLM provider.")
    p_ask.add_argument("--model", help="Override the LLM model.")
    p_ask.add_argument("--api-key", help="Override the API key.")
    p_ask.add_argument(
        "--show-sql", action="store_true", help="Print the generated SQL after the answer."
    )
    p_ask.set_defaults(func=cmd_ask)

    p_cfg = sub.add_parser("config", help="Print resolved configuration as JSON.")
    p_cfg.set_defaults(func=cmd_config)

    p_serve = sub.add_parser("serve", help="Launch the Streamlit UI.")
    p_serve.add_argument("--port", type=int, default=8501)
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.set_defaults(func=cmd_serve)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args) or 0)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
