"""Shared deterministic schema ranking and operator-authored catalog validation."""

from __future__ import annotations

import json
import re
from collections import deque
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class CatalogEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    description: str = ""
    aliases: list[str] = Field(default_factory=list)
    metrics: dict[str, str] = Field(default_factory=dict)
    values: dict[str, list[str | int | float | None]] = Field(default_factory=dict)


class SchemaCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    tables: dict[str, CatalogEntry] = Field(default_factory=dict)

    @classmethod
    def load(cls, path: Path | None, schema: str) -> SchemaCatalog:
        catalog = cls.model_validate_json(path.read_text(encoding="utf-8")) if path else cls()
        known = {
            match.group(1): match.group(2)
            for match in re.finditer(r"^Table ([^(]+)\((.*)\)$", schema, re.MULTILINE)
        }
        for table, entry in catalog.tables.items():
            if table not in known:
                raise ValueError(f"Catalog references unknown table: {table}")
            for column in entry.values:
                if not re.search(r"(?:^|, )" + re.escape(column) + r"\s", known[table]):
                    raise ValueError(f"Catalog references unknown column: {table}.{column}")
        return catalog

    def search_question(self, question: str, allowed: frozenset[str]) -> str:
        hints = [
            table
            for table, entry in self.tables.items()
            if table in allowed
            and any(
                alias.casefold() in question.casefold()
                for alias in [*entry.aliases, *entry.metrics]
            )
        ]
        return question + " " + " ".join(hints)

    def context(self, selected: list[str]) -> str:
        return json.dumps(
            {table: self.tables[table].model_dump() for table in selected if table in self.tables},
            ensure_ascii=False,
        )


def rank_tables(
    columns: dict[str, list[str]],
    question: str,
    maximum: int | None,
    links: dict[str, set[str]] | None = None,
) -> list[str]:
    """Rank authorized tables and prioritize a connecting FK path when it fits."""
    if maximum is None or len(columns) <= maximum:
        return sorted(columns)
    tokens = set(re.findall(r"[a-z0-9]+", question.casefold()))

    def score(table: str) -> int:
        return sum(
            len(tokens & set(re.findall(r"[a-z0-9]+", name.casefold()))) * (5 if index == 0 else 2)
            for index, name in enumerate([table, *columns[table]])
        )

    ranked = sorted(columns, key=lambda table: (-score(table), table.casefold()))
    selected = ranked[: min(2, maximum)]
    if len(selected) == 2 and links:
        queue = deque([[selected[0]]])
        visited = {selected[0]}
        while queue:
            path = queue.popleft()
            if path[-1] == selected[1]:
                if len(path) <= maximum:
                    selected = path
                break
            for neighbor in sorted(links.get(path[-1], set())):
                if neighbor in columns and neighbor not in visited:
                    visited.add(neighbor)
                    queue.append([*path, neighbor])
    return (
        sorted(dict.fromkeys([*selected, *ranked]))
        if maximum >= len(columns)
        else sorted(list(dict.fromkeys([*selected, *ranked]))[:maximum])
    )
