"""Structured in-memory mission event log."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class EventLog:
    records: list[dict[str, Any]] = field(default_factory=list)

    def add(self, timestamp: float, category: str, event: str, detail: str = "", severity: str = "info") -> None:
        self.records.append(
            {"timestamp": timestamp, "category": category, "event": event, "detail": detail, "severity": severity}
        )
        self.records = self.records[-5000:]

