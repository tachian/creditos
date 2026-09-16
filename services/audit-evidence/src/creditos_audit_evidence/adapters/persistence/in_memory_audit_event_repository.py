from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from threading import RLock

from creditos_audit_evidence.domain.entities import AuditEvent
from creditos_audit_evidence.domain.errors import AuditEvidenceConflictError


class InMemoryAuditEventRepository:
    def __init__(self) -> None:
        self._events: dict[tuple[str, str], AuditEvent] = {}
        self._by_aggregate: dict[tuple[str, str, str], tuple[str, ...]] = {}
        self._lock = RLock()

    def append(
        self,
        event: AuditEvent,
        *,
        before_commit: Callable[[], None] | None = None,
    ) -> None:
        key = _event_key(event.tenant_id, event.event_id)
        aggregate_key = _aggregate_key(event.tenant_id, event.aggregate_type, event.aggregate_id)
        with self._lock:
            if key in self._events:
                raise AuditEvidenceConflictError(
                    "evento de auditoria duplicado",
                    code="duplicate_audit_event",
                    field_path="event_id",
                )
            if before_commit is not None:
                before_commit()
            if key in self._events:
                raise AuditEvidenceConflictError(
                    "evento de auditoria duplicado",
                    code="duplicate_audit_event",
                    field_path="event_id",
                )
            self._events[key] = event
            self._by_aggregate[aggregate_key] = (
                *self._by_aggregate.get(aggregate_key, ()),
                event.event_id,
            )

    def get(self, *, tenant_id: str, event_id: str) -> AuditEvent | None:
        with self._lock:
            return self._events.get(_event_key(tenant_id, event_id))

    def list_by_aggregate(
        self,
        *,
        tenant_id: str,
        aggregate_type: str,
        aggregate_id: str,
    ) -> tuple[AuditEvent, ...]:
        with self._lock:
            event_ids = self._by_aggregate.get(
                _aggregate_key(tenant_id, aggregate_type, aggregate_id),
                (),
            )
            return tuple(
                event
                for event_id in event_ids
                if (event := self._events.get(_event_key(tenant_id, event_id))) is not None
            )

    def list_by_time_window(
        self,
        *,
        tenant_id: str,
        occurred_from: datetime,
        occurred_to: datetime,
    ) -> tuple[AuditEvent, ...]:
        with self._lock:
            return tuple(
                sorted(
                    (
                        event
                        for (event_tenant_id, _event_id), event in self._events.items()
                        if event_tenant_id == tenant_id
                        and occurred_from <= event.occurred_at <= occurred_to
                    ),
                    key=lambda event: (event.occurred_at, event.event_id),
                )
            )


def _event_key(tenant_id: str, event_id: str) -> tuple[str, str]:
    return (tenant_id, event_id)


def _aggregate_key(tenant_id: str, aggregate_type: str, aggregate_id: str) -> tuple[str, str, str]:
    return (tenant_id, aggregate_type, aggregate_id)
