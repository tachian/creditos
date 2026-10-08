from __future__ import annotations

import hmac
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from types import MappingProxyType
from typing import Any, Protocol

from creditos_observability.context import ObservabilityContext

from creditos_integration.domain.entities.webhook_configuration import WebhookConfiguration
from creditos_integration.domain.entities.webhook_delivery import (
    WebhookDeliveryDlqRecord,
    WebhookDeliveryJob,
    WebhookDeliveryRetrySchedule,
    WebhookNotificationEvent,
)
from creditos_integration.domain.errors import IntegrationValidationError

WEBHOOK_DELIVERY_EVENT_TYPES = MappingProxyType(
    {
        "created": "creditos.webhook.delivery.created.v1",
        "sent": "creditos.webhook.delivery.sent.v1",
        "failed": "creditos.webhook.delivery.failed.v1",
        "retry_scheduled": "creditos.webhook.delivery.retry_scheduled.v1",
        "dlq_recorded": "creditos.webhook.delivery.dlq_recorded.v1",
        "reprocess_requested": "creditos.webhook.delivery.reprocess_requested.v1",
    }
)

JETSTREAM_WEBHOOK_DELIVERY_MAPPING = MappingProxyType(
    {
        "stream": "CREDITOS_WEBHOOK_DELIVERY",
        "consumer": "integration-webhook-delivery",
        "dlq_stream": "CREDITOS_WEBHOOK_DELIVERY_DLQ",
        "ack_policy": "explicit",
        "storage": "file",
        "replicas": 3,
        "idempotency_key": "event_id + webhook_configuration_id",
    }
)

CLOUDEVENT_WEBHOOK_DELIVERY_MAPPING = MappingProxyType(
    {
        "specversion": "1.0",
        "source": "creditos.integration.webhook-delivery",
        "type": "WEBHOOK_DELIVERY_EVENT_TYPES[status]",
        "subject": "tenant_id + webhook_configuration_id + job_id",
        "id": "job_id + status + updated_at",
        "time": "updated_at",
        "datacontenttype": "application/json",
        "dataschema": "creditos.integration.webhook-delivery.v1",
        "data": {
            "tenant_id": "tenant_id",
            "webhook_configuration_id": "webhook_configuration_id",
            "job_id": "job_id",
            "event_id": "event_id",
            "event_type": "event_type",
            "status": "status",
            "attempt_count": "attempt_count",
            "correlation_id": "correlation_id",
            "trace_id": "trace_id",
        },
    }
)


@dataclass(frozen=True, slots=True)
class WebhookDeliveryRequest:
    endpoint_url: str
    payload: Mapping[str, Any]
    headers: MappingProxyType[str, str]
    timeout_ms: int
    tenant_id: str
    webhook_configuration_id: str
    job_id: str


@dataclass(frozen=True, slots=True)
class WebhookDeliveryAdapterResult:
    outcome: str
    status_code: int | None
    failure_code: str | None = None

    @classmethod
    def accepted(cls, *, status_code: int = 202) -> WebhookDeliveryAdapterResult:
        return cls(outcome="accepted", status_code=status_code)

    @classmethod
    def temporary_failure(
        cls,
        *,
        status_code: int | None,
        failure_code: str,
    ) -> WebhookDeliveryAdapterResult:
        return cls(outcome="temporary_failure", status_code=status_code, failure_code=failure_code)

    @classmethod
    def final_failure(
        cls,
        *,
        status_code: int | None,
        failure_code: str,
    ) -> WebhookDeliveryAdapterResult:
        return cls(outcome="final_failure", status_code=status_code, failure_code=failure_code)

    def __post_init__(self) -> None:
        if self.outcome not in {"accepted", "temporary_failure", "final_failure"}:
            raise IntegrationValidationError(
                "resultado de adapter de webhook não suportado",
                code="unsupported_webhook_delivery_adapter_result",
                field_path="outcome",
            )
        if self.status_code is not None and (
            type(self.status_code) is not int or self.status_code < 100 or self.status_code > 599
        ):
            raise IntegrationValidationError(
                "status HTTP de webhook inválido",
                code="invalid_webhook_delivery_status_code",
                field_path="status_code",
            )
        if self.outcome == "accepted" and (
            self.status_code is None or self.status_code < 200 or self.status_code >= 300
        ):
            raise IntegrationValidationError(
                "entrega aceita de webhook exige status HTTP 2xx",
                code="invalid_webhook_delivery_accepted_status_code",
                field_path="status_code",
            )
        if self.outcome != "accepted" and not self.failure_code:
            raise IntegrationValidationError(
                "falha de webhook sem código normalizado",
                code="missing_webhook_delivery_failure_code",
                field_path="failure_code",
            )


@dataclass(frozen=True, slots=True)
class WebhookDeliveryDispatchResult:
    jobs: tuple[WebhookDeliveryJob, ...]
    retry_schedules: tuple[WebhookDeliveryRetrySchedule, ...] = ()
    dlq_records: tuple[WebhookDeliveryDlqRecord, ...] = ()


class WebhookDeliveryAdapter(Protocol):
    def deliver(self, request: WebhookDeliveryRequest) -> WebhookDeliveryAdapterResult: ...


class WebhookSigningKeyResolver(Protocol):
    def resolve(self, *, tenant_id: str, signing_key_ref: str) -> bytes: ...


class WebhookDeliveryStore(Protocol):
    def reserve_or_get(
        self,
        *,
        job: WebhookDeliveryJob,
        event: WebhookNotificationEvent,
    ) -> WebhookDeliveryJob | None: ...

    def save(self, job: WebhookDeliveryJob) -> None: ...

    def release(self, job: WebhookDeliveryJob) -> None: ...

    def save_retry_schedule(self, schedule: WebhookDeliveryRetrySchedule) -> None: ...

    def list_due_retry_schedules(
        self,
        *,
        tenant_id: str,
        due_at: datetime,
    ) -> tuple[WebhookDeliveryRetrySchedule, ...]: ...

    def consume_retry_schedule(self, schedule: WebhookDeliveryRetrySchedule) -> None: ...

    def get_event(
        self,
        *,
        tenant_id: str,
        job_id: str,
    ) -> WebhookNotificationEvent | None: ...

    def get(
        self,
        *,
        tenant_id: str,
        job_id: str,
    ) -> WebhookDeliveryJob | None: ...


class WebhookDeliveryDlqStore(Protocol):
    def save(self, record: WebhookDeliveryDlqRecord) -> WebhookDeliveryDlqRecord: ...

    def get(
        self,
        *,
        tenant_id: str,
        dlq_id: str,
    ) -> WebhookDeliveryDlqRecord | None: ...

    def mark_reprocessed(
        self,
        *,
        tenant_id: str,
        dlq_id: str,
        reprocess_job_id: str,
        reprocessed_at: datetime,
    ) -> WebhookDeliveryDlqRecord: ...


class WebhookDeliveryDispatcher(Protocol):
    def dispatch(
        self,
        *,
        job: WebhookDeliveryJob,
        event: WebhookNotificationEvent,
        configuration: WebhookConfiguration,
        context: ObservabilityContext,
        clock: Callable[[], datetime],
        dlq_id_factory: Callable[[str], str],
    ) -> WebhookDeliveryDispatchResult: ...


class StaticWebhookSigningKeyResolver:
    def __init__(self, keys: Mapping[tuple[str, str], bytes]) -> None:
        self._keys = dict(keys)

    def resolve(self, *, tenant_id: str, signing_key_ref: str) -> bytes:
        secret = self._keys.get((tenant_id, signing_key_ref))
        if secret is None:
            raise IntegrationValidationError(
                "chave de assinatura de webhook indisponível",
                code="webhook_signing_key_unavailable",
                field_path="signing_key_ref",
            )
        return secret


class InMemoryWebhookDeliveryAdapter:
    def __init__(self, results: list[WebhookDeliveryAdapterResult] | None = None) -> None:
        self._results = list(results or [WebhookDeliveryAdapterResult.accepted()])
        self.requests: list[WebhookDeliveryRequest] = []

    def deliver(self, request: WebhookDeliveryRequest) -> WebhookDeliveryAdapterResult:
        self.requests.append(request)
        if not self._results:
            return WebhookDeliveryAdapterResult.accepted()
        if len(self._results) == 1:
            return self._results[0]
        return self._results.pop(0)


def build_signed_webhook_request(
    *,
    job: WebhookDeliveryJob,
    event: WebhookNotificationEvent,
    configuration: WebhookConfiguration,
    signing_key_resolver: WebhookSigningKeyResolver,
    delivered_at: datetime,
) -> WebhookDeliveryRequest:
    payload = event.public_payload(idempotency_key=job.idempotency_key)
    canonical_payload = canonical_webhook_payload(payload)
    secret = signing_key_resolver.resolve(
        tenant_id=job.tenant_id,
        signing_key_ref=configuration.signing_key_ref,
    )
    signature = hmac.new(secret, canonical_payload, sha256).hexdigest()
    headers = MappingProxyType(
        {
            "Content-Type": "application/json",
            "X-CreditOS-Correlation-Id": job.correlation_id,
            "X-CreditOS-Event-Id": event.event_id,
            "X-CreditOS-Event-Type": event.event_type,
            "X-CreditOS-Idempotency-Key": job.idempotency_key,
            "X-CreditOS-Signature": f"sha256={signature}",
            "X-CreditOS-Signature-Algorithm": configuration.signing_algorithm,
            "X-CreditOS-Timestamp": delivered_at.isoformat(),
        }
    )
    return WebhookDeliveryRequest(
        endpoint_url=configuration.endpoint_url,
        payload=payload,
        headers=headers,
        timeout_ms=configuration.timeout_ms,
        tenant_id=job.tenant_id,
        webhook_configuration_id=job.webhook_configuration_id,
        job_id=job.job_id,
    )


def canonical_webhook_payload(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(dict(payload), sort_keys=True, separators=(",", ":")).encode("utf-8")
