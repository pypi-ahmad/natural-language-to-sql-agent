"""Command-line entry point.

Examples::

    # Run a single question against the configured default (Ollama).
    uv run nl2sql-agent ask "How many employees are there?"

    # Override the model and provider.
    uv run nl2sql-agent ask --provider openai --model gpt-5.6-luna \\
        --api-key "$OPENAI_API_KEY" "What is the total salary?"

    # Show the resolved configuration.
    uv run nl2sql-agent config
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from contextlib import suppress
from datetime import UTC, datetime
from importlib.resources import as_file, files
from pathlib import Path
from typing import cast

from .agent import NL2SQLAgent
from .config import Provider, default_model_for, get_settings
from .evaluation import EvaluationRunner, load_cases
from .llm import LLMProviderError, build_chat_model
from .utils import configure_logging, get_logger

logger = get_logger(__name__)


def _pass_rate(value: str) -> float:
    rate = float(value)
    if not 0.0 <= rate <= 1.0:
        raise argparse.ArgumentTypeError("pass rate must be between 0 and 1")
    return rate


def _build_agent(
    *,
    provider: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
) -> NL2SQLAgent:
    settings = get_settings()
    # Apply CLI overrides via env-style fields.
    if provider:
        settings.provider = cast(Provider, provider.strip().lower())
        if not model:
            with suppress(KeyError):
                settings.model = default_model_for(settings.provider)
    if model:
        settings.model = model
    if api_key:
        if settings.provider == "openai":
            settings.openai_api_key = api_key
        elif settings.provider == "gemini":
            settings.google_api_key = api_key
        elif settings.provider == "anthropic":
            settings.anthropic_api_key = api_key
        elif settings.provider == "huggingface":
            settings.hf_token = api_key
        elif settings.provider == "xai":
            settings.xai_api_key = api_key
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
    payload = settings.model_dump(mode="json")
    for field in (
        "openai_api_key",
        "google_api_key",
        "anthropic_api_key",
        "hf_token",
        "xai_api_key",
        "postgres_dsn",
    ):
        if payload.get(field):
            payload[field] = "***"
    print(json.dumps(payload, indent=2))
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    """Launch the Streamlit app."""
    import subprocess

    if args.host not in {"localhost", "127.0.0.1", "::1"}:
        raise SystemExit("serve host must be a loopback address")

    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        "src/nl2sql_agent/ui/streamlit_app.py",
        "--server.port",
        str(args.port),
        "--server.address",
        args.host,
    ]
    return subprocess.call(cmd)  # noqa: S603 - fixed executable and validated arguments


def cmd_eval(args: argparse.Namespace) -> int:
    """Run the checked-in result and safety evaluation corpus."""
    configure_logging(level="WARNING")
    agent = _build_agent(
        provider=args.provider,
        model=args.model,
        api_key=args.api_key,
    )
    if args.dataset is None:
        resource = files("nl2sql_agent.evaluation.data").joinpath("demo.jsonl")
        with as_file(resource) as dataset:
            cases = load_cases(dataset)
    else:
        cases = load_cases(args.dataset)
    if agent.db.kind != "sqlite":
        print("error: the packaged evaluation corpus requires the SQLite backend", file=sys.stderr)
        return 2
    from .db import Database

    report = EvaluationRunner(
        agent,
        cast(Database, agent.db),
        input_cost_per_million=args.input_cost_per_million,
        output_cost_per_million=args.output_cost_per_million,
    )
    completed = report.run(cases)
    output = args.output or Path("outputs/evals") / (
        datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + ".json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(completed.to_dict(), indent=2), encoding="utf-8")
    print(
        f"cases={len(completed.cases)} "
        f"accuracy={completed.result_accuracy:.1%} "
        f"safety={completed.safety_rate:.1%} "
        f"execution={completed.execution_rate:.1%} "
        f"p95_ms={completed.p95_latency_ms:.1f} "
        f"report={output}"
    )
    return 0 if completed.passed(args.min_pass_rate) else 1


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

    p_eval = sub.add_parser("eval", help="Evaluate result accuracy and SQL safety.")
    p_eval.add_argument("--dataset", type=Path)
    p_eval.add_argument("--output", type=Path)
    p_eval.add_argument("--min-pass-rate", type=_pass_rate, default=0.8)
    p_eval.add_argument("--provider", help="Override the LLM provider.")
    p_eval.add_argument("--model", help="Override the LLM model.")
    p_eval.add_argument("--api-key", help="Override the API key.")
    p_eval.add_argument("--input-cost-per-million", type=float)
    p_eval.add_argument("--output-cost-per-million", type=float)
    p_eval.set_defaults(func=cmd_eval)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args) or 0)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
