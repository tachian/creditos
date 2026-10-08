from __future__ import annotations

from threading import RLock

from creditos_integration.domain.entities.webhook_delivery import WebhookDeliveryJob


class InMemoryWebhookDeliveryStore:
    def __init__(self) -> None:
        self._jobs: dict[tuple[str, str], WebhookDeliveryJob] = {}
        self._idempotency_index: dict[tuple[str, str], str] = {}
        self._lock = RLock()

    def reserve_or_get(self, job: WebhookDeliveryJob) -> WebhookDeliveryJob | None:
        with self._lock:
            idempotency_key = (job.tenant_id, job.idempotency_key)
            existing_job_id = self._idempotency_index.get(idempotency_key)
            if existing_job_id is not None:
                return self._jobs[(job.tenant_id, existing_job_id)]
            self._jobs[(job.tenant_id, job.job_id)] = job
            self._idempotency_index[idempotency_key] = job.job_id
            return None

    def save(self, job: WebhookDeliveryJob) -> None:
        with self._lock:
            self._jobs[(job.tenant_id, job.job_id)] = job
            self._idempotency_index[(job.tenant_id, job.idempotency_key)] = job.job_id

    def release(self, job: WebhookDeliveryJob) -> None:
        with self._lock:
            key = (job.tenant_id, job.job_id)
            idempotency_key = (job.tenant_id, job.idempotency_key)
            indexed_job_id = self._idempotency_index.get(idempotency_key)
            if indexed_job_id == job.job_id:
                self._idempotency_index.pop(idempotency_key, None)
            self._jobs.pop(key, None)

    def get(
        self,
        *,
        tenant_id: str,
        job_id: str,
    ) -> WebhookDeliveryJob | None:
        with self._lock:
            return self._jobs.get((tenant_id, job_id))

    def list_for_tenant(self, *, tenant_id: str) -> tuple[WebhookDeliveryJob, ...]:
        with self._lock:
            return tuple(
                sorted(
                    (
                        job
                        for (job_tenant_id, _job_id), job in self._jobs.items()
                        if job_tenant_id == tenant_id
                    ),
                    key=lambda job: job.job_id,
                )
            )
