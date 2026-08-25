from __future__ import annotations

from threading import Condition

from creditos_integration.application.ports.integration_execution import IntegrationExecutionEvent
from creditos_integration.domain.entities import IntegrationExecution
from creditos_integration.domain.errors import IntegrationValidationError


class InMemoryIntegrationExecutionStore:
    def __init__(self) -> None:
        self._executions: dict[tuple[str, str], IntegrationExecution] = {}
        self._events: dict[tuple[str, str], tuple[IntegrationExecutionEvent, ...]] = {}
        self._published_event_ids: dict[tuple[str, str], set[str]] = {}
        self._reservations: dict[tuple[str, str], str] = {}
        self._condition = Condition()

    def reserve_or_get(
        self,
        *,
        tenant_id: str,
        idempotency_key: str,
        plan_fingerprint: str,
    ) -> IntegrationExecution | None:
        key = (tenant_id, idempotency_key)
        with self._condition:
            while True:
                existing = self._executions.get(key)
                if existing is not None:
                    if existing.plan_fingerprint != plan_fingerprint:
                        raise IntegrationValidationError(
                            "chave de idempotência já usada para outro plano de integração",
                            code="integration_execution_idempotency_conflict",
                            field_path="idempotency_key",
                        )
                    return existing

                reserved_fingerprint = self._reservations.get(key)
                if reserved_fingerprint is None:
                    self._reservations[key] = plan_fingerprint
                    return None
                if reserved_fingerprint != plan_fingerprint:
                    raise IntegrationValidationError(
                        "chave de idempotência já usada para outro plano de integração",
                        code="integration_execution_idempotency_conflict",
                        field_path="idempotency_key",
                    )
                self._condition.wait()

    def save(self, execution: IntegrationExecution) -> None:
        key = (execution.tenant_id, execution.idempotency_key)
        with self._condition:
            existing = self._executions.get(key)
            if existing is not None and existing.plan_fingerprint != execution.plan_fingerprint:
                raise IntegrationValidationError(
                    "chave de idempotência já usada para outro plano de integração",
                    code="integration_execution_idempotency_conflict",
                    field_path="idempotency_key",
                )
            self._executions[key] = execution
            self._reservations.pop(key, None)
            self._condition.notify_all()

    def get_by_execution_id(
        self,
        *,
        tenant_id: str,
        execution_id: str,
    ) -> IntegrationExecution | None:
        with self._condition:
            for (stored_tenant_id, _), execution in self._executions.items():
                if stored_tenant_id == tenant_id and execution.execution_id == execution_id:
                    return execution
        return None

    def release_reservation(
        self,
        *,
        tenant_id: str,
        idempotency_key: str,
        plan_fingerprint: str,
    ) -> None:
        key = (tenant_id, idempotency_key)
        with self._condition:
            if self._reservations.get(key) == plan_fingerprint:
                self._reservations.pop(key, None)
                self._condition.notify_all()

    def stage_execution_events(
        self,
        *,
        tenant_id: str,
        idempotency_key: str,
        events: tuple[IntegrationExecutionEvent, ...],
    ) -> None:
        key = (tenant_id, idempotency_key)
        with self._condition:
            if key not in self._events:
                self._events[key] = events
                self._published_event_ids[key] = set()

    def list_unpublished_execution_events(
        self,
        *,
        tenant_id: str,
        idempotency_key: str,
    ) -> tuple[IntegrationExecutionEvent, ...]:
        key = (tenant_id, idempotency_key)
        with self._condition:
            published_event_ids = self._published_event_ids.get(key, set())
            return tuple(
                event for event in self._events.get(key, ()) if event.id not in published_event_ids
            )

    def mark_execution_event_published(
        self,
        *,
        tenant_id: str,
        idempotency_key: str,
        event_id: str,
    ) -> None:
        key = (tenant_id, idempotency_key)
        with self._condition:
            self._published_event_ids.setdefault(key, set()).add(event_id)
