from __future__ import annotations

from threading import Condition

from creditos_integration.domain.entities import IntegrationExecution
from creditos_integration.domain.errors import IntegrationValidationError


class InMemoryIntegrationExecutionStore:
    def __init__(self) -> None:
        self._executions: dict[tuple[str, str], IntegrationExecution] = {}
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
