"""Application configuration via Pydantic Settings.

Loads from environment variables, .env file, and program defaults.
Single source of truth for all runtime knobs.
"""

from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Provider = Literal["ollama", "huggingface", "openai", "anthropic", "gemini", "xai"]

_PROVIDER_MODELS: dict[Provider, tuple[str, ...]] = {
    "ollama": (
        "phi4-mini:3.8b",
        "qwen3.5:4b",
        "qwen3.5:2b",
        "llama3.1",
        "mistral",
    ),
    "huggingface": ("openai/gpt-oss-120b:fastest",),
    "openai": ("gpt-5.6-luna", "gpt-5.6-terra"),
    "anthropic": ("claude-sonnet-5",),
    "gemini": ("gemini-3.7-flash", "gemini-3.5-flash-lite"),
    "xai": ("grok-4.6",),
}
_HUGGING_FACE_MODEL_ID = re.compile(
    r"[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*"
    r"(?::[A-Za-z0-9][A-Za-z0-9._-]*)?"
)


def supported_models_for(provider: Provider) -> tuple[str, ...]:
    """Return the deterministic model choices shown for ``provider``."""
    return _PROVIDER_MODELS[provider]


def default_model_for(provider: Provider) -> str:
    """Return the default model used when a provider is selected."""
    return _PROVIDER_MODELS[provider][0]


def validate_model_for(provider: Provider, model: str) -> str:
    """Validate and normalize a model identifier for its provider."""
    model = model.strip()
    if not model:
        raise ValueError("model must not be empty")
    if provider == "ollama":
        return model
    if provider == "huggingface":
        if _HUGGING_FACE_MODEL_ID.fullmatch(model):
            return model
        raise ValueError("Hugging Face model must use namespace/model[:routing-policy]")
    allowed = supported_models_for(provider)
    if model not in allowed:
        raise ValueError(
            f"model {model!r} is not supported for provider={provider}; "
            f"choose one of: {', '.join(allowed)}"
        )
    return model


class Settings(BaseSettings):
    """Runtime configuration for the NL2SQL agent.

    Values are resolved in this order:
    1. Programmatic arguments (e.g. ``Settings(provider="openai")``)
    2. Environment variables (e.g. ``NL2SQL_MODEL=qwen3.5:4b``)
    3. .env file in the current working directory
    4. Field defaults
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="NL2SQL_",
        case_sensitive=False,
        extra="ignore",
    )

    # ---- Provider selection ----
    provider: Provider = Field(
        default="ollama",
        description="LLM provider. Defaults to local Ollama.",
    )
    model: str = Field(
        default="phi4-mini:3.8b",
        description="Model identifier for the selected provider. Default is Microsoft Phi-4-mini running locally via Ollama; tested on 8GB VRAM. Override with NL2SQL_MODEL.",
    )
    ollama_base_url: str = Field(
        default="http://localhost:11434",
        description="Ollama HTTP endpoint.",
    )
    ollama_keep_alive: str = Field(
        default="5m",
        description="How long Ollama keeps the model loaded after the last request.",
    )
    openai_api_key: str | None = Field(default=None, alias="openai_api_key")
    google_api_key: str | None = Field(default=None, alias="google_api_key")
    anthropic_api_key: str | None = Field(default=None, alias="anthropic_api_key")
    hf_token: str | None = Field(
        default=None,
        validation_alias=AliasChoices("hf_token", "NL2SQL_HF_TOKEN"),
    )
    xai_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("xai_api_key", "NL2SQL_XAI_API_KEY"),
    )

    # ---- Database ----
    db_path: Path = Field(
        default=Path("company.db"),
        description="SQLite database file. Created on first run.",
    )
    db_seed: bool = Field(
        default=True,
        description="If True, seed the database with sample data on first run.",
    )
    db_max_rows: int = Field(
        default=1000,
        ge=1,
        le=100_000,
        description="Maximum rows returned per SQL execution.",
    )
    db_query_timeout_seconds: float = Field(
        default=15.0,
        ge=0.1,
        le=120.0,
        description="Per-query execution timeout.",
    )
    db_max_vm_steps: int = Field(
        default=5_000_000,
        ge=10_000,
        description="Maximum SQLite virtual-machine steps per query.",
    )
    db_upload_max_mb: int = Field(
        default=50,
        ge=1,
        le=50,
        description="Maximum SQLite upload size accepted by the UI.",
    )

    # ---- Agent behavior ----
    max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Maximum SQL rewrite attempts after a failed execution.",
    )
    llm_temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    llm_max_tokens: int = Field(default=1024, ge=64, le=8192)
    llm_request_timeout_seconds: float = Field(default=60.0, ge=1.0, le=600.0)

    # ---- Safety ----
    sql_allow_subqueries: bool = Field(
        default=True,
        description="If False, reject queries that contain nested SELECT.",
    )
    sql_allow_joins: bool = Field(default=True)
    sql_allow_aggregates: bool = Field(default=True)
    sql_allow_cte: bool = Field(default=True)
    sql_max_joins: int = Field(default=8, ge=0, le=64)
    sql_max_subqueries: int = Field(default=8, ge=0, le=64)
    sql_max_ctes: int = Field(default=8, ge=0, le=64)
    schema_max_tables: int = Field(default=8, ge=1, le=100)

    # ---- Observability ----
    log_level: Literal["TRACE", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    log_json: bool = Field(
        default=False,
        description="If True, emit structured JSON logs (suitable for log aggregators).",
    )
    audit_enabled: bool = Field(
        default=True,
        description="Write privacy-preserving query audit events.",
    )
    audit_path: Path = Field(
        default=Path("logs/audit.jsonl"),
        description="JSONL audit event destination.",
    )

    # ---- Paths ----
    project_root: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parents[2],
    )

    @field_validator("provider", mode="before")
    @classmethod
    def _normalize_provider(cls, v: object) -> object:
        if isinstance(v, str):
            return v.strip().lower()
        return v

    @field_validator("ollama_base_url")
    @classmethod
    def _validate_ollama_base_url(cls, value: str) -> str:
        parsed = urlsplit(value)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("Ollama base URL must be a plain HTTP(S) endpoint")
        loopback = parsed.hostname.casefold() in {"localhost", "127.0.0.1", "::1"}
        if parsed.scheme != "https" and not loopback:
            raise ValueError("remote Ollama endpoints must use HTTPS")
        return value.rstrip("/")

    @field_validator("db_path", "audit_path", mode="before")
    @classmethod
    def _coerce_db_path(cls, v: object) -> object:
        if isinstance(v, str):
            return Path(v)
        return v

    @model_validator(mode="after")
    def _validate_provider_model(self) -> Settings:
        if "model" not in self.model_fields_set and self.provider != "ollama":
            self.model = default_model_for(self.provider)
        self.model = validate_model_for(self.provider, self.model)
        return self

    def api_key_for(self, provider: Provider) -> str | None:
        """Return the API key configured for ``provider``, or ``None``."""
        return {
            "ollama": None,  # No key required
            "openai": self.openai_api_key,
            "gemini": self.google_api_key,
            "anthropic": self.anthropic_api_key,
            "huggingface": self.hf_token,
            "xai": self.xai_api_key,
        }.get(provider)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached :class:`Settings` instance.

    Use this as a FastAPI-/dependency-style accessor in the rest of the app.
    """
    return Settings()


def reset_settings_cache() -> None:
    """Clear the settings cache. Tests use this to pick up env changes."""
    get_settings.cache_clear()


def env_var_for(provider: Provider) -> str | None:
    """Return the standard environment variable name for the provider's API key."""
    return {
        "ollama": None,
        "openai": "OPENAI_API_KEY",
        "gemini": "GOOGLE_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "huggingface": "HF_TOKEN",
        "xai": "XAI_API_KEY",
    }.get(provider)


def env_var_value(name: str) -> str | None:
    """Read a name from the process environment without a Settings instance."""
    val = os.getenv(name)
    return val.strip() if val and val.strip() else None
