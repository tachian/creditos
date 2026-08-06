from __future__ import annotations

from typing import Any


class InMemoryOperationLogger:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def log(self, event: dict[str, Any]) -> None:
        self.events.append(event)
