from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True, slots=True)
class IntegrationAuditEvent:
    tenant_id: str
    operation: str
    product_type: str
    integration_class: str
    adapter_id: str
    result: str
    correlation_id: str
    trace_id: str
    schema_version: str
    occurred_at: datetime
    dlq_id: str | None = None
    reprocess_execution_id: str | None = None

    def to_log_safe_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "tenant_id": self.tenant_id,
            "operation": self.operation,
            "product_type": self.product_type,
            "integration_class": self.integration_class,
            "adapter_id": self.adapter_id,
            "result": self.result,
            "correlation_id": self.correlation_id,
            "trace_id": self.trace_id,
            "schema_version": self.schema_version,
            "occurred_at": self.occurred_at.isoformat(),
        }
        if self.dlq_id is not None:
            payload["dlq_id"] = self.dlq_id
        if self.reprocess_execution_id is not None:
            payload["reprocess_execution_id"] = self.reprocess_execution_id
        return payload


class AuditEventPublisher(Protocol):
    def publish(self, event: IntegrationAuditEvent) -> None: ...


class InMemoryAuditEventPublisher:
    def __init__(self) -> None:
        self.events: list[IntegrationAuditEvent] = []

    def publish(self, event: IntegrationAuditEvent) -> None:
        self.events.append(event)
