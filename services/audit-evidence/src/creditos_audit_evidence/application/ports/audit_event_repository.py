from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Protocol

from creditos_audit_evidence.domain.entities import AuditEvent


class AuditEventRepository(Protocol):
    def append(
        self,
        event: AuditEvent,
        *,
        before_commit: Callable[[], None] | None = None,
    ) -> AuditEvent: ...

    def get(self, *, tenant_id: str, event_id: str) -> AuditEvent | None: ...

    def list_by_aggregate(
        self,
        *,
        tenant_id: str,
        aggregate_type: str,
        aggregate_id: str,
    ) -> tuple[AuditEvent, ...]: ...

    def list_by_time_window(
        self,
        *,
        tenant_id: str,
        occurred_from: datetime,
        occurred_to: datetime,
    ) -> tuple[AuditEvent, ...]: ...

    def list_by_tenant_chain(self, *, tenant_id: str) -> tuple[AuditEvent, ...]: ...
