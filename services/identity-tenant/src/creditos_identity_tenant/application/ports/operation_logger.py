from __future__ import annotations

from typing import Any, Protocol


class OperationLogger(Protocol):
    def log(self, event: dict[str, Any]) -> None: ...
