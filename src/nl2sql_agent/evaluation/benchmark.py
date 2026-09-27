"""Reproducible local benchmark driver; never publishes or deploys anything."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import shutil
import sqlite3
import subprocess
from collections import Counter
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import cast

from ..agent import NL2SQLAgent
from ..config import Provider, Settings
from ..db import Database
from ..llm import build_chat_model
from ..llm.budget import BudgetedModel, BudgetLedger, Rates
from ..utils import configure_logging
from .runner import EvalCase, EvaluationRunner


class Recorder:
    """Wrap an agent and retain its latest state for benchmark artifact collection."""

    def __init__(self, agent: NL2SQLAgent) -> None:
        self.agent = agent
        self.state: dict = {}

    def run(self, question: str) -> dict:
        """Run question and retain/return the wrapped agent's resulting state."""
        self.state = self.agent.run(question)
        return self.state


BIRD_REVISION = "f65faf4ae3b638c1fa6df1d3370c8d92c8366301"  # pragma: allowlist secret
MODEL_RATES = {
    # Input uses the maximum cache-write/standard rate conservatively.
    ("openai", "gpt-6-luna"): Rates(Decimal(".125"), Decimal(".50")),
    ("agnes", "agnes-3.0-flash"): Rates(Decimal(".05"), Decimal(".15")),
    ("huggingface", "openai/gpt-oss-120b:groq"): Rates(Decimal(".15"), Decimal(".75")),
}


def source_digest() -> str:
    """Hash the actual Python source, including uncommitted benchmark changes."""
    root = Path(__file__).resolve().parents[1]
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*.py")):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def select_bird(source: Path, *, size: int = 50) -> list[dict]:
    """Select stable difficulty-stratified rows, without inspecting model results."""
    quotas = {
        50: {"simple": 15, "moderate": 25, "challenging": 10},
        20: {"simple": 6, "moderate": 10, "challenging": 4},
    }
    if size not in quotas:
        raise ValueError("BIRD selection size must be 20 or 50")
    rows = sorted(
        json.loads(source.read_text(encoding="utf-8")), key=lambda row: int(row["question_id"])
    )
    selected, counts = [], Counter()
    for row in rows:
        difficulty = row["difficulty"]
        if counts[difficulty] < quotas[size].get(difficulty, 0):
            selected.append(row)
            counts[difficulty] += 1
    if len(selected) != size:
        raise ValueError("Source does not meet difficulty quotas")
    return selected


def curated_database(root: Path, domain: str, output: Path) -> Database:
    """Return a content-named SQLite fixture in output using root/fixtures DDL.

    Unknown domains raise ValueError; file and SQLite errors propagate."""
    if domain not in {"hr", "retail", "inventory", "support"}:
        raise ValueError("Unknown fixture domain")
    ddl = (root / "fixtures" / f"{domain}.sql").read_text(encoding="utf-8")
    digest = hashlib.sha256(ddl.encode()).hexdigest()[:16]
    path = output / f"{domain}-{digest}.db"
    output.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        with sqlite3.connect(path) as conn:
            conn.executescript(ddl)
    return Database(path)


def main(argv: list[str] | None = None) -> int:
    """Parse argv and run a bounded comparison with checkpointed output.

    Invalid arguments or existing output cause argparse to exit. Paid calls
    require configured rates and the persistent ledger and can incur charges."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--provider", required=True, choices=["ollama", "openai", "agnes", "huggingface"]
    )
    parser.add_argument("--model", required=True)
    parser.add_argument("--suite", choices=["synthetic", "bird"], default="synthetic")
    parser.add_argument("--cases", type=Path, default=Path("benchmarks/cases.jsonl"))
    parser.add_argument(
        "--bird-source",
        type=Path,
        default=Path("outputs/bird/source/data/mini_dev_sqlite-00000-of-00001.json"),
    )
    parser.add_argument("--bird-databases", type=Path, default=Path("outputs/bird/databases"))
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--offset", type=int, default=0, help="Skip already attempted case IDs")
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--schema-tables", type=int, default=8)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, default=Path("outputs/benchmark-budget.db"))
    args = parser.parse_args(argv)
    if args.limit <= 0:
        parser.error("--limit must be positive")
    if args.offset < 0:
        parser.error("--offset must be non-negative")
    if args.output.exists():
        parser.error("Output exists; choose a new file to preserve prior attempts")
    configure_logging(level="ERROR")
    cfg = Settings(
        provider=cast(Provider, args.provider),
        model=args.model,
        audit_enabled=False,
        ollama_keep_alive="5m",
        ollama_num_ctx=4096,
        llm_request_timeout_seconds=90,
        max_retries=args.retries,
        schema_max_tables=args.schema_tables,
    )
    ledger = BudgetLedger(args.ledger)
    if args.provider != "ollama" and (args.provider, args.model) not in MODEL_RATES:
        parser.error("No verified price configured; refusing paid calls")
    model = build_chat_model(cfg)
    if args.provider != "ollama":
        model = BudgetedModel(
            model, ledger, MODEL_RATES[args.provider, args.model], max_tokens=cfg.llm_max_tokens
        )
    if args.suite == "synthetic":
        source = args.cases
        rows = [
            json.loads(line)
            for line in source.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ][args.offset : args.offset + args.limit]
    else:
        source = args.bird_source
        rows = [
            {
                "id": f"bird-{row['question_id']}",
                "domain": row["db_id"],
                "question": row["question"] + "\nEvidence: " + row["evidence"],
                "expected_outcome": "result",
                "reference_sql": row["SQL"],
                "difficulty": row["difficulty"],
            }
            for row in select_bird(source, size=20)
        ][args.offset : args.offset + args.limit]
    if not rows:
        parser.error("The requested offset selects no cases")
    git = shutil.which("git")
    if git is None:
        raise RuntimeError("Git is required for benchmark provenance")
    commit = subprocess.run(  # noqa: S603 - resolved Git binary and fixed arguments
        [git, "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    report = {
        "report_version": 2,
        "started_at": datetime.now(UTC).isoformat(),
        "commit": commit,
        "source_tree_sha256": source_digest(),
        "working_tree_dirty": bool(
            subprocess.run(  # noqa: S603 - resolved Git binary and fixed arguments
                [git, "status", "--porcelain"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout
        ),
        "provider": args.provider,
        "model": args.model,
        "suite": args.suite,
        "dataset_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "dataset_revision": BIRD_REVISION if args.suite == "bird" else None,
        "prompt_version": "decision-v2",
        "context_tokens": cfg.ollama_num_ctx if args.provider == "ollama" else None,
        "max_output_tokens": cfg.llm_max_tokens,
        "max_attempts": args.retries,
        "schema_tables": args.schema_tables,
        "platform": platform.platform(),
        "planned": len(rows),
        "selection_offset": args.offset,
        "database_sha256": {},
        "cases": [],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    consecutive_provider_errors = 0
    for row in rows:
        if args.suite == "synthetic":
            database = curated_database(
                args.cases.parent, row["domain"], args.output.parent / "fixtures"
            )
        else:
            matches = list(args.bird_databases.rglob(f"{row['domain']}.sqlite"))
            if len(matches) != 1:
                report["cases"].append(
                    {
                        "id": row["id"],
                        "outcome": "benchmark_blocked",
                        "error_code": "missing_or_duplicate_database",
                        "passed": False,
                    }
                )
                args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
                continue
            database = Database(matches[0])
        if row["domain"] not in report["database_sha256"]:
            with database.path.open("rb") as database_file:
                report["database_sha256"][row["domain"]] = hashlib.file_digest(
                    database_file, "sha256"
                ).hexdigest()
        agent = NL2SQLAgent(model, settings=cfg, database=database, include_sample_values=False)
        recorder = Recorder(agent)
        case_report = (
            EvaluationRunner(recorder, database)
            .run([EvalCase.from_mapping(row)])
            .to_dict()["cases"][0]
        )
        captured = recorder.state
        case_report.update(
            {
                key: captured[key]
                for key in (
                    "sql_query",
                    "selected_tables",
                    "schema_incomplete",
                    "assumptions",
                    "error_code",
                )
                if key in captured
            }
        )
        report["cases"].append(case_report)
        report["budget_committed_usd"] = str(ledger.committed)
        report["completed_at"] = datetime.now(UTC).isoformat()
        consecutive_provider_errors = (
            consecutive_provider_errors + 1 if case_report["outcome"] == "provider_error" else 0
        )
        if consecutive_provider_errors >= 3:
            report["stop_reason"] = "three_consecutive_provider_errors"
        args.output.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
        print(
            f"{args.model}: {len(report['cases'])}/{len(rows)} {case_report['outcome']}", flush=True
        )
        if case_report["outcome"] == "budget_exhausted" or consecutive_provider_errors >= 3:
            break
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
