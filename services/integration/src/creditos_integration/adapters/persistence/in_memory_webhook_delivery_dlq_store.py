from __future__ import annotations

from datetime import datetime
from threading import RLock

from creditos_integration.domain.entities.webhook_delivery import WebhookDeliveryDlqRecord
from creditos_integration.domain.errors import IntegrationValidationError


class InMemoryWebhookDeliveryDlqStore:
    def __init__(self) -> None:
        self._records: dict[tuple[str, str], WebhookDeliveryDlqRecord] = {}
        self._lock = RLock()

    def save(self, record: WebhookDeliveryDlqRecord) -> WebhookDeliveryDlqRecord:
        with self._lock:
            self._records[(record.tenant_id, record.dlq_id)] = record
            return record

    def get(
        self,
        *,
        tenant_id: str,
        dlq_id: str,
    ) -> WebhookDeliveryDlqRecord | None:
        with self._lock:
            return self._records.get((tenant_id, dlq_id))

    def mark_reprocessed(
        self,
        *,
        tenant_id: str,
        dlq_id: str,
        reprocess_job_id: str,
        reprocessed_at: datetime,
    ) -> WebhookDeliveryDlqRecord:
        with self._lock:
            record = self._records.get((tenant_id, dlq_id))
            if record is None:
                raise IntegrationValidationError(
                    "registro de DLQ de webhook não encontrado",
                    code="webhook_delivery_dlq_not_found",
                    field_path="dlq_id",
                )
            updated_record = record.mark_reprocessed(
                reprocessed_at=reprocessed_at,
                reprocess_job_id=reprocess_job_id,
            )
            self._records[(tenant_id, dlq_id)] = updated_record
            return updated_record

    def list_for_tenant(self, *, tenant_id: str) -> tuple[WebhookDeliveryDlqRecord, ...]:
        with self._lock:
            return tuple(
                sorted(
                    (
                        record
                        for (record_tenant_id, _dlq_id), record in self._records.items()
                        if record_tenant_id == tenant_id
                    ),
                    key=lambda record: record.dlq_id,
                )
            )
