from __future__ import annotations

from datetime import datetime
from threading import Condition

from creditos_integration.domain.entities.webhook_delivery import (
    WebhookDeliveryJob,
    WebhookDeliveryRetrySchedule,
    WebhookNotificationEvent,
)


class InMemoryWebhookDeliveryStore:
    def __init__(self) -> None:
        self._jobs: dict[tuple[str, str], WebhookDeliveryJob] = {}
        self._events: dict[tuple[str, str], WebhookNotificationEvent] = {}
        self._idempotency_index: dict[tuple[str, str], str] = {}
        self._reservations: dict[tuple[str, str], str] = {}
        self._retry_schedules: dict[tuple[str, str, int], WebhookDeliveryRetrySchedule] = {}
        self._condition = Condition()

    def reserve_or_get(
        self,
        *,
        job: WebhookDeliveryJob,
        event: WebhookNotificationEvent,
    ) -> WebhookDeliveryJob | None:
        with self._condition:
            idempotency_key = (job.tenant_id, job.idempotency_key)
            while True:
                existing_job_id = self._idempotency_index.get(idempotency_key)
                if existing_job_id is not None:
                    return self._jobs[(job.tenant_id, existing_job_id)]
                reserved_job_id = self._reservations.get(idempotency_key)
                if reserved_job_id is None:
                    self._reservations[idempotency_key] = job.job_id
                    self._events[(job.tenant_id, job.job_id)] = event
                    return None
                self._condition.wait()

    def save(self, job: WebhookDeliveryJob) -> None:
        with self._condition:
            self._jobs[(job.tenant_id, job.job_id)] = job
            self._idempotency_index[(job.tenant_id, job.idempotency_key)] = job.job_id
            self._reservations.pop((job.tenant_id, job.idempotency_key), None)
            self._condition.notify_all()

    def release(self, job: WebhookDeliveryJob) -> None:
        with self._condition:
            key = (job.tenant_id, job.job_id)
            idempotency_key = (job.tenant_id, job.idempotency_key)
            indexed_job_id = self._idempotency_index.get(idempotency_key)
            if indexed_job_id == job.job_id:
                self._idempotency_index.pop(idempotency_key, None)
            reserved_job_id = self._reservations.get(idempotency_key)
            if reserved_job_id == job.job_id:
                self._reservations.pop(idempotency_key, None)
            self._jobs.pop(key, None)
            self._events.pop(key, None)
            self._condition.notify_all()

    def save_retry_schedule(self, schedule: WebhookDeliveryRetrySchedule) -> None:
        with self._condition:
            self._retry_schedules[
                (schedule.tenant_id, schedule.job_id, schedule.next_attempt_count)
            ] = schedule

    def list_due_retry_schedules(
        self,
        *,
        tenant_id: str,
        due_at: datetime,
    ) -> tuple[WebhookDeliveryRetrySchedule, ...]:
        with self._condition:
            return tuple(
                sorted(
                    (
                        schedule
                        for schedule in self._retry_schedules.values()
                        if schedule.tenant_id == tenant_id and schedule.next_attempt_at <= due_at
                    ),
                    key=lambda schedule: (
                        schedule.next_attempt_at,
                        schedule.job_id,
                        schedule.next_attempt_count,
                    ),
                )
            )

    def consume_retry_schedule(self, schedule: WebhookDeliveryRetrySchedule) -> None:
        with self._condition:
            self._retry_schedules.pop(
                (schedule.tenant_id, schedule.job_id, schedule.next_attempt_count),
                None,
            )

    def get_event(
        self,
        *,
        tenant_id: str,
        job_id: str,
    ) -> WebhookNotificationEvent | None:
        with self._condition:
            return self._events.get((tenant_id, job_id))

    def get(
        self,
        *,
        tenant_id: str,
        job_id: str,
    ) -> WebhookDeliveryJob | None:
        with self._condition:
            return self._jobs.get((tenant_id, job_id))

    def list_for_tenant(self, *, tenant_id: str) -> tuple[WebhookDeliveryJob, ...]:
        with self._condition:
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
