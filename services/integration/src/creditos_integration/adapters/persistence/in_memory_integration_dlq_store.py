from __future__ import annotations

from datetime import datetime
from threading import Lock

from creditos_integration.domain.entities import IntegrationExecutionDlqRecord
from creditos_integration.domain.errors import IntegrationValidationError
from creditos_integration.domain.value_objects.execution import validate_idempotency_key


class InMemoryIntegrationDlqStore:
    def __init__(self) -> None:
        self._records: dict[tuple[str, str], IntegrationExecutionDlqRecord] = {}
        self._reprocess_keys: dict[tuple[str, str], str] = {}
        self._lock = Lock()

    def save(self, record: IntegrationExecutionDlqRecord) -> IntegrationExecutionDlqRecord:
        key = (record.tenant_id, record.dlq_id)
        with self._lock:
            existing = self._records.get(key)
            if existing is not None and existing.job_id != record.job_id:
                raise IntegrationValidationError(
                    "DLQ já registrada para outro job",
                    code="integration_dlq_record_conflict",
                    field_path="dlq_id",
                )
            if existing is not None:
                return existing
            self._records[key] = record
            return record

    def get(
        self,
        *,
        tenant_id: str,
        dlq_id: str,
    ) -> IntegrationExecutionDlqRecord | None:
        with self._lock:
            return self._records.get((tenant_id, dlq_id))

    def list_for_execution(
        self,
        *,
        tenant_id: str,
        execution_id: str,
    ) -> tuple[IntegrationExecutionDlqRecord, ...]:
        with self._lock:
            records = tuple(
                record
                for (record_tenant_id, _), record in self._records.items()
                if record_tenant_id == tenant_id and record.execution_id == execution_id
            )
        return tuple(sorted(records, key=lambda record: record.created_at))

    def mark_reprocessed(
        self,
        *,
        tenant_id: str,
        dlq_id: str,
        idempotency_key: str,
        reprocessed_at: datetime,
        reprocess_execution_id: str,
    ) -> IntegrationExecutionDlqRecord:
        idempotency_key = validate_idempotency_key(idempotency_key)
        key = (tenant_id, dlq_id)
        reprocess_key = (tenant_id, idempotency_key)
        with self._lock:
            record = self._records.get(key)
            if record is None:
                raise IntegrationValidationError(
                    "registro de DLQ não encontrado",
                    code="integration_dlq_record_not_found",
                    field_path="dlq_id",
                )
            existing_dlq_id = self._reprocess_keys.get(reprocess_key)
            if existing_dlq_id is not None and existing_dlq_id != dlq_id:
                raise IntegrationValidationError(
                    "chave de idempotência de reprocessamento já usada para outra DLQ",
                    code="integration_dlq_reprocess_idempotency_conflict",
                    field_path="idempotency_key",
                )
            if existing_dlq_id == dlq_id:
                return record
            updated = record.mark_reprocessed(
                reprocessed_at=reprocessed_at,
                reprocess_execution_id=reprocess_execution_id,
            )
            self._records[key] = updated
            self._reprocess_keys[reprocess_key] = dlq_id
            return updated
