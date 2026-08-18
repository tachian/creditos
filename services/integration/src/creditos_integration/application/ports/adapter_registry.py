from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol


class AdapterRegistry(Protocol):
    def is_adapter_allowed(self, integration_class: str, adapter_id: str) -> bool: ...


class InMemoryAdapterRegistry:
    def __init__(self, adapters_by_class: Mapping[str, set[str]]) -> None:
        self._adapters_by_class = {
            integration_class: set(adapter_ids)
            for integration_class, adapter_ids in adapters_by_class.items()
        }
        self.execution_attempts: list[tuple[str, str]] = []

    def is_adapter_allowed(self, integration_class: str, adapter_id: str) -> bool:
        return adapter_id in self._adapters_by_class.get(integration_class, set())

    def record_execution_attempt(self, integration_class: str, adapter_id: str) -> None:
        self.execution_attempts.append((integration_class, adapter_id))

    def unregister_adapter(self, integration_class: str, adapter_id: str) -> None:
        self._adapters_by_class.setdefault(integration_class, set()).discard(adapter_id)
