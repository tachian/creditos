from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from hashlib import sha256
from threading import Event, Thread
from typing import Any

import pytest
from creditos_integration.adapters.events import InMemoryWebhookDeliveryDispatcher
from creditos_integration.adapters.persistence import (
    InMemoryWebhookConfigurationRepository,
    InMemoryWebhookDeliveryDlqStore,
    InMemoryWebhookDeliveryStore,
)
from creditos_integration.application.ports.audit_event_publisher import InMemoryAuditEventPublisher
from creditos_integration.application.ports.webhook_delivery import (
    CLOUDEVENT_WEBHOOK_DELIVERY_MAPPING,
    WEBHOOK_DELIVERY_EVENT_TYPES,
    InMemoryWebhookDeliveryAdapter,
    StaticWebhookSigningKeyResolver,
    WebhookDeliveryAdapterResult,
    WebhookDeliveryDispatcher,
    WebhookDeliveryDispatchResult,
)
from creditos_integration.application.service import (
    ConfigureWebhookCommand,
    DispatchWebhookNotificationCommand,
    IntegrationCatalogApplicationService,
    ProcessWebhookRetriesCommand,
    ReprocessWebhookDlqCommand,
)
from creditos_integration.domain.entities import WebhookDeliveryJob, WebhookNotificationEvent
from creditos_integration.domain.errors import IntegrationValidationError
from creditos_observability.context import ObservabilityContext
from creditos_observability.gates import validate_observability_exposure_payload

_FIXED_TIME = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)
_EVENT_ID = "evt_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
_PUBLIC_CALLBACK_IP = "93.184.216.34"


class RecordingTelemetry:
    def __init__(self) -> None:
        self.operations: list[dict[str, object]] = []

    def record_operation(self, **kwargs: object) -> dict[str, object]:
        self.operations.append(dict(kwargs))
        return {"telemetry_recorded": True}


def test_dispatch_webhook_notification_creates_signed_minimized_idempotent_job() -> None:
    adapter = InMemoryWebhookDeliveryAdapter(
        [WebhookDeliveryAdapterResult.accepted(status_code=202)]
    )
    service = _service(delivery_adapter=adapter)
    service.configure_webhook(_configure_command(), context=_context())

    result = service.dispatch_webhook_notification(_notification_command(), context=_context())
    replay = service.dispatch_webhook_notification(_notification_command(), context=_context())

    assert len(result.jobs) == 1
    assert replay.jobs == result.jobs
    assert len(adapter.requests) == 1
    job = result.jobs[0]
    assert job.tenant_id == "tenant-bridge-001"
    assert job.webhook_configuration_id == "wcfg_fixed"
    assert job.event_id == _EVENT_ID
    assert job.status == "sent"
    request = adapter.requests[0]
    assert request.endpoint_url == "https://callbacks.example.com/creditos/status"
    assert request.headers["X-CreditOS-Event-Id"] == _EVENT_ID
    assert request.headers["X-CreditOS-Event-Type"] == "decision.completed"
    assert request.headers["X-CreditOS-Idempotency-Key"] == (
        "webhook:evt_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa:wcfg_fixed"
    )
    assert request.headers["X-CreditOS-Correlation-Id"] == "corr-webhook-001"
    assert request.headers["X-CreditOS-Signature-Algorithm"] == "hmac_sha256"
    assert request.headers["X-CreditOS-Signature"].startswith("sha256=")
    assert request.payload == {
        "contract_version": "v1",
        "correlation_id": "corr-webhook-001",
        "decision_outcome": "approved",
        "decision_status": "completed",
        "event_id": _EVENT_ID,
        "event_type": "decision.completed",
        "idempotency_key": "webhook:evt_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa:wcfg_fixed",
        "occurred_at": "2026-10-07T12:00:00+00:00",
        "proposal_id": "proposal-123",
        "trace_id": "33333333333333333333333333333333",
    }
    serialized_payload = json.dumps(request.payload, ensure_ascii=False).lower()
    assert "123.456.789-09" not in serialized_payload
    assert "cliente@example.com" not in serialized_payload
    assert "secret" not in serialized_payload
    assert "token" not in serialized_payload


def test_webhook_delivery_schedules_retry_without_consuming_remaining_attempts() -> None:
    adapter = InMemoryWebhookDeliveryAdapter(
        [
            WebhookDeliveryAdapterResult.temporary_failure(
                status_code=503,
                failure_code="endpoint_unavailable",
            ),
        ]
    )
    dlq_store = InMemoryWebhookDeliveryDlqStore()
    service = _service(delivery_adapter=adapter, dlq_store=dlq_store)
    service.configure_webhook(_configure_command(), context=_context())

    result = service.dispatch_webhook_notification(_notification_command(), context=_context())

    assert result.jobs[0].status == "retry_scheduled"
    assert len(adapter.requests) == 1
    assert [schedule.attempt_count for schedule in result.retry_schedules] == [1]
    assert result.retry_schedules[0].next_attempt_count == 2
    assert result.retry_schedules[0].retry_delay_ms >= 250
    assert result.dlq_records == ()
    serialized_logs = json.dumps(service.logged_events, default=str, ensure_ascii=False).lower()
    assert "callbacks.example.com/creditos/status" not in serialized_logs
    assert "signing-secret" not in serialized_logs
    assert "123.456.789-09" not in serialized_logs
    assert "cliente@example.com" not in serialized_logs
    assert "webhook_delivery.retry_scheduled" in serialized_logs


def test_webhook_delivery_records_dlq_on_terminal_failure_without_sensitive_logs() -> None:
    adapter = InMemoryWebhookDeliveryAdapter(
        [
            WebhookDeliveryAdapterResult.final_failure(
                status_code=400,
                failure_code="endpoint_rejected",
            )
        ]
    )
    dlq_store = InMemoryWebhookDeliveryDlqStore()
    service = _service(delivery_adapter=adapter, dlq_store=dlq_store)
    service.configure_webhook(_configure_command(), context=_context())

    result = service.dispatch_webhook_notification(_notification_command(), context=_context())

    assert result.jobs[0].status == "dlq_recorded"
    assert result.retry_schedules == ()
    assert len(result.dlq_records) == 1
    dlq_record = result.dlq_records[0]
    assert dlq_record.tenant_id == "tenant-bridge-001"
    assert dlq_record.webhook_configuration_id == "wcfg_fixed"
    assert dlq_record.failure_code == "endpoint_rejected"
    assert dlq_store.get(tenant_id="tenant-bridge-001", dlq_id=dlq_record.dlq_id) == dlq_record
    serialized_logs = json.dumps(service.logged_events, default=str, ensure_ascii=False).lower()
    assert "callbacks.example.com/creditos/status" not in serialized_logs
    assert "signing-secret" not in serialized_logs
    assert "123.456.789-09" not in serialized_logs
    assert "cliente@example.com" not in serialized_logs
    assert "webhook_delivery.dlq_recorded" in serialized_logs


def test_webhook_dlq_reprocess_requires_scope_active_configuration_and_preserves_tenant() -> None:
    failing_adapter = InMemoryWebhookDeliveryAdapter(
        [
            WebhookDeliveryAdapterResult.final_failure(
                status_code=400,
                failure_code="endpoint_rejected",
            )
        ]
    )
    dlq_store = InMemoryWebhookDeliveryDlqStore()
    delivery_store = InMemoryWebhookDeliveryStore()
    repository = InMemoryWebhookConfigurationRepository()
    service = _service(
        repository=repository,
        delivery_store=delivery_store,
        dlq_store=dlq_store,
        delivery_adapter=failing_adapter,
    )
    service.configure_webhook(_configure_command(), context=_context())
    failed = service.dispatch_webhook_notification(_notification_command(), context=_context())
    dlq_id = failed.dlq_records[0].dlq_id

    with pytest.raises(IntegrationValidationError) as missing_scope:
        service.reprocess_webhook_dlq(
            ReprocessWebhookDlqCommand(
                dlq_id=dlq_id,
                idempotency_key="idem-webhook-reprocess-001",
                scopes=("webhook_delivery:dispatch",),
            ),
            context=_context(),
        )

    assert missing_scope.value.code == "insufficient_scope"

    retry_adapter = InMemoryWebhookDeliveryAdapter(
        [WebhookDeliveryAdapterResult.accepted(status_code=200)]
    )
    service = _service(
        repository=repository,
        delivery_store=delivery_store,
        dlq_store=dlq_store,
        delivery_adapter=retry_adapter,
    )

    result = service.reprocess_webhook_dlq(
        ReprocessWebhookDlqCommand(
            dlq_id=dlq_id,
            idempotency_key="idem-webhook-reprocess-001",
            scopes=("webhook_delivery:reprocess",),
        ),
        context=_context(),
    )

    assert result.jobs[0].status == "sent"
    assert result.jobs[0].tenant_id == "tenant-bridge-001"
    updated_record = dlq_store.get(tenant_id="tenant-bridge-001", dlq_id=dlq_id)
    assert updated_record is not None
    assert updated_record.reprocess_count == 1
    assert updated_record.reprocess_job_ids == (result.jobs[0].job_id,)
    assert retry_adapter.requests[0].headers["X-CreditOS-Idempotency-Key"] == (
        f"widem_{sha256(f'webhook_delivery.reprocess|idem-webhook-reprocess-001|{dlq_id}'.encode()).hexdigest()}"
    )


def test_explicit_idempotency_key_is_scoped_per_webhook_configuration() -> None:
    adapter = InMemoryWebhookDeliveryAdapter(
        [
            WebhookDeliveryAdapterResult.accepted(status_code=202),
            WebhookDeliveryAdapterResult.accepted(status_code=202),
        ]
    )
    service = _service(
        delivery_adapter=adapter,
        configuration_id_factory=lambda seed: f"wcfg_{sha256(seed.encode()).hexdigest()[:12]}",
    )
    service.configure_webhook(
        _configure_command(
            idempotency_key="idem-webhook-config-001",
            endpoint_url="https://callbacks.example.com/creditos/status-a",
        ),
        context=_context(),
    )
    service.configure_webhook(
        _configure_command(
            idempotency_key="idem-webhook-config-002",
            endpoint_url="https://callbacks.example.com/creditos/status-b",
        ),
        context=_context(),
    )

    result = service.dispatch_webhook_notification(
        _notification_command(idempotency_key="idem-webhook-dispatch-001"),
        context=_context(),
    )
    replay = service.dispatch_webhook_notification(
        _notification_command(idempotency_key="idem-webhook-dispatch-001"),
        context=_context(),
    )

    assert len(result.jobs) == 2
    assert replay.jobs == result.jobs
    assert len(adapter.requests) == 2
    delivered_idempotency_keys = {
        request.headers["X-CreditOS-Idempotency-Key"] for request in adapter.requests
    }
    assert len(delivered_idempotency_keys) == 2
    assert all(key.startswith("webhook:evt_") for key in delivered_idempotency_keys)


def test_explicit_idempotency_does_not_duplicate_same_event_and_configuration() -> None:
    adapter = InMemoryWebhookDeliveryAdapter(
        [
            WebhookDeliveryAdapterResult.accepted(status_code=202),
            WebhookDeliveryAdapterResult.accepted(status_code=202),
        ]
    )
    service = _service(delivery_adapter=adapter)
    service.configure_webhook(_configure_command(), context=_context())

    first = service.dispatch_webhook_notification(
        _notification_command(idempotency_key="idem-webhook-dispatch-001"),
        context=_context(),
    )
    second = service.dispatch_webhook_notification(
        _notification_command(idempotency_key="idem-webhook-dispatch-002"),
        context=_context(),
    )

    assert second.jobs == first.jobs
    assert len(adapter.requests) == 1


def test_due_retry_processor_executes_schedules_until_success() -> None:
    now = _FIXED_TIME
    adapter = InMemoryWebhookDeliveryAdapter(
        [
            WebhookDeliveryAdapterResult.temporary_failure(
                status_code=503,
                failure_code="endpoint_unavailable",
            ),
            WebhookDeliveryAdapterResult.temporary_failure(
                status_code=503,
                failure_code="endpoint_unavailable",
            ),
            WebhookDeliveryAdapterResult.accepted(status_code=202),
        ]
    )
    delivery_store = InMemoryWebhookDeliveryStore()
    service = _service(
        delivery_store=delivery_store,
        delivery_adapter=adapter,
        clock=lambda: now,
    )
    service.configure_webhook(_configure_command(), context=_context())
    initial = service.dispatch_webhook_notification(_notification_command(), context=_context())

    assert initial.jobs[0].status == "retry_scheduled"

    now = datetime(2026, 10, 7, 12, 0, 1, tzinfo=UTC)
    first_retry = service.process_due_webhook_retries(
        ProcessWebhookRetriesCommand(scopes=("webhook_delivery:dispatch",)),
        context=_context(),
    )
    now = datetime(2026, 10, 7, 12, 0, 2, tzinfo=UTC)
    second_retry = service.process_due_webhook_retries(
        ProcessWebhookRetriesCommand(scopes=("webhook_delivery:dispatch",)),
        context=_context(),
    )

    assert first_retry.jobs[0].status == "retry_scheduled"
    assert second_retry.jobs[0].status == "sent"
    assert len(adapter.requests) == 3
    operations = [event["operation"] for event in service.logged_events]
    assert operations.count("webhook_delivery.retry_scheduled") == 2
    assert operations.count("webhook_delivery.failed") >= 2


def test_webhook_public_payload_rejects_sensitive_identifier_values() -> None:
    service = _service()
    service.configure_webhook(_configure_command(), context=_context())

    with pytest.raises(IntegrationValidationError) as error:
        service.dispatch_webhook_notification(
            _notification_command(proposal_id="123.456.789-09"),
            context=_context(),
        )

    assert error.value.code == "sensitive_webhook_delivery_payload"


def test_accepted_adapter_result_requires_2xx_http_status() -> None:
    with pytest.raises(IntegrationValidationError) as error:
        WebhookDeliveryAdapterResult.accepted(status_code=500)

    assert error.value.code == "invalid_webhook_delivery_accepted_status_code"


def test_webhook_reprocess_marks_dlq_only_after_successful_delivery() -> None:
    failing_adapter = InMemoryWebhookDeliveryAdapter(
        [
            WebhookDeliveryAdapterResult.final_failure(
                status_code=400,
                failure_code="endpoint_rejected",
            )
        ]
    )
    dlq_store = InMemoryWebhookDeliveryDlqStore()
    delivery_store = InMemoryWebhookDeliveryStore()
    repository = InMemoryWebhookConfigurationRepository()
    service = _service(
        repository=repository,
        delivery_store=delivery_store,
        dlq_store=dlq_store,
        delivery_adapter=failing_adapter,
    )
    service.configure_webhook(_configure_command(), context=_context())
    failed = service.dispatch_webhook_notification(_notification_command(), context=_context())
    dlq_id = failed.dlq_records[0].dlq_id
    retry_adapter = InMemoryWebhookDeliveryAdapter(
        [
            WebhookDeliveryAdapterResult.temporary_failure(
                status_code=503,
                failure_code="endpoint_unavailable",
            )
        ]
    )
    service = _service(
        repository=repository,
        delivery_store=delivery_store,
        dlq_store=dlq_store,
        delivery_adapter=retry_adapter,
    )

    result = service.reprocess_webhook_dlq(
        ReprocessWebhookDlqCommand(
            dlq_id=dlq_id,
            idempotency_key="idem-webhook-reprocess-002",
            scopes=("webhook_delivery:reprocess",),
        ),
        context=_context(),
    )

    assert result.jobs[0].status == "retry_scheduled"
    updated_record = dlq_store.get(tenant_id="tenant-bridge-001", dlq_id=dlq_id)
    assert updated_record is not None
    assert updated_record.reprocess_count == 0
    assert updated_record.reprocess_job_ids == ()


def test_webhook_reprocess_idempotency_is_bound_to_each_dlq_record() -> None:
    failing_adapter = InMemoryWebhookDeliveryAdapter(
        [
            WebhookDeliveryAdapterResult.final_failure(
                status_code=400,
                failure_code="endpoint_rejected",
            ),
            WebhookDeliveryAdapterResult.final_failure(
                status_code=400,
                failure_code="endpoint_rejected",
            ),
        ]
    )
    dlq_store = InMemoryWebhookDeliveryDlqStore()
    delivery_store = InMemoryWebhookDeliveryStore()
    repository = InMemoryWebhookConfigurationRepository()
    dlq_index = 0

    def dlq_id_factory(_seed: str) -> str:
        nonlocal dlq_index
        dlq_index += 1
        return f"wdlq_fixed_{dlq_index}"

    service = _service(
        repository=repository,
        delivery_store=delivery_store,
        dlq_store=dlq_store,
        delivery_adapter=failing_adapter,
        dlq_id_factory=dlq_id_factory,
    )
    service.configure_webhook(_configure_command(), context=_context())
    first_failed = service.dispatch_webhook_notification(
        _notification_command(), context=_context()
    )
    second_failed = service.dispatch_webhook_notification(
        _notification_command(event_id="evt_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"),
        context=_context(),
    )
    retry_adapter = InMemoryWebhookDeliveryAdapter(
        [
            WebhookDeliveryAdapterResult.accepted(status_code=202),
            WebhookDeliveryAdapterResult.accepted(status_code=202),
        ]
    )
    service = _service(
        repository=repository,
        delivery_store=delivery_store,
        dlq_store=dlq_store,
        delivery_adapter=retry_adapter,
        dlq_id_factory=dlq_id_factory,
    )

    first_reprocess = service.reprocess_webhook_dlq(
        ReprocessWebhookDlqCommand(
            dlq_id=first_failed.dlq_records[0].dlq_id,
            idempotency_key="idem-webhook-reprocess-shared",
            scopes=("webhook_delivery:reprocess",),
        ),
        context=_context(),
    )
    second_reprocess = service.reprocess_webhook_dlq(
        ReprocessWebhookDlqCommand(
            dlq_id=second_failed.dlq_records[0].dlq_id,
            idempotency_key="idem-webhook-reprocess-shared",
            scopes=("webhook_delivery:reprocess",),
        ),
        context=_context(),
    )

    assert first_reprocess.jobs[0].job_id != second_reprocess.jobs[0].job_id
    assert len(retry_adapter.requests) == 2


def test_webhook_delivery_store_waits_for_in_flight_reservation() -> None:
    store = InMemoryWebhookDeliveryStore()
    event = _notification_event()
    job = WebhookDeliveryJob.create(
        job_id="wjob_concurrent",
        tenant_id="tenant-bridge-001",
        webhook_configuration_id="wcfg_fixed",
        event=event,
        idempotency_key="webhook:evt_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa:wcfg_fixed",
        created_at=_FIXED_TIME,
    )
    saved_job = job.with_status(status="sent", attempt_count=1, updated_at=_FIXED_TIME)
    assert store.reserve_or_get(job=job, event=event) is None
    started = Event()
    finished = Event()
    result: list[WebhookDeliveryJob | None] = []

    def reserve_same_job() -> None:
        started.set()
        result.append(store.reserve_or_get(job=job, event=event))
        finished.set()

    thread = Thread(target=reserve_same_job)
    thread.start()
    assert started.wait(timeout=1)
    assert not finished.wait(timeout=0.05)
    store.save(saved_job)
    thread.join(timeout=1)

    assert finished.is_set()
    assert result == [saved_job]


def test_failed_dispatch_releases_pending_idempotency_reservation() -> None:
    repository = InMemoryWebhookConfigurationRepository()
    delivery_store = InMemoryWebhookDeliveryStore()
    service = _service(
        repository=repository,
        delivery_store=delivery_store,
        delivery_dispatcher=_RaisingWebhookDeliveryDispatcher(),
    )
    service.configure_webhook(_configure_command(), context=_context())

    with pytest.raises(RuntimeError, match="boom"):
        service.dispatch_webhook_notification(_notification_command(), context=_context())

    adapter = InMemoryWebhookDeliveryAdapter(
        [WebhookDeliveryAdapterResult.accepted(status_code=202)]
    )
    service = _service(
        repository=repository,
        delivery_store=delivery_store,
        delivery_adapter=adapter,
    )
    result = service.dispatch_webhook_notification(_notification_command(), context=_context())

    assert result.jobs[0].status == "sent"
    assert len(adapter.requests) == 1


def test_webhook_delivery_supports_ten_attempt_configurations() -> None:
    service = _service()
    service.configure_webhook(_configure_command(max_attempts=10), context=_context())
    result = service.dispatch_webhook_notification(_notification_command(), context=_context())

    assert result.jobs[0].status == "sent"


def test_static_webhook_signing_key_resolver_is_tenant_scoped() -> None:
    resolver = StaticWebhookSigningKeyResolver(
        {("tenant-bridge-001", "wkey_creditos_callback_v1"): b"signing-secret"}
    )

    assert (
        resolver.resolve(
            tenant_id="tenant-bridge-001",
            signing_key_ref="wkey_creditos_callback_v1",
        )
        == b"signing-secret"
    )
    with pytest.raises(IntegrationValidationError) as error:
        resolver.resolve(
            tenant_id="tenant-bridge-002",
            signing_key_ref="wkey_creditos_callback_v1",
        )

    assert error.value.code == "webhook_signing_key_unavailable"


def test_webhook_delivery_cloudevent_mapping_is_explicit() -> None:
    assert WEBHOOK_DELIVERY_EVENT_TYPES["retry_due"] == "creditos.webhook.delivery.retry_due.v1"
    assert CLOUDEVENT_WEBHOOK_DELIVERY_MAPPING["specversion"] == "1.0"
    assert CLOUDEVENT_WEBHOOK_DELIVERY_MAPPING["source"] == (
        "creditos.integration.webhook-delivery"
    )
    assert CLOUDEVENT_WEBHOOK_DELIVERY_MAPPING["datacontenttype"] == "application/json"
    assert "type" in CLOUDEVENT_WEBHOOK_DELIVERY_MAPPING
    assert "subject" in CLOUDEVENT_WEBHOOK_DELIVERY_MAPPING
    assert "data" in CLOUDEVENT_WEBHOOK_DELIVERY_MAPPING


def test_webhook_delivery_emits_safe_normalized_observability_and_business_signals() -> None:
    telemetry = RecordingTelemetry()
    now = _FIXED_TIME
    adapter = InMemoryWebhookDeliveryAdapter(
        [
            WebhookDeliveryAdapterResult.temporary_failure(
                status_code=503,
                failure_code="endpoint_unavailable",
            ),
            WebhookDeliveryAdapterResult.final_failure(
                status_code=400,
                failure_code="endpoint_rejected",
            ),
        ]
    )
    service = _service(delivery_adapter=adapter, telemetry=telemetry, clock=lambda: now)
    service.configure_webhook(_configure_command(), context=_context())

    initial = service.dispatch_webhook_notification(_notification_command(), context=_context())
    now = datetime(2026, 10, 7, 12, 0, 1, tzinfo=UTC)
    retry = service.process_due_webhook_retries(
        ProcessWebhookRetriesCommand(scopes=("webhook_delivery:dispatch",)),
        context=_context(),
    )

    operations = [operation["operation"] for operation in telemetry.operations]
    assert "webhook_delivery.created" in operations
    assert "webhook_delivery.retry_scheduled" in operations
    assert "webhook_delivery.failed" in operations
    assert "webhook_delivery.dlq_recorded" in operations
    assert {operation["operation_type"] for operation in telemetry.operations} == {"job"}
    assert "endpoint_unavailable" in str(telemetry.operations)
    assert "endpoint_rejected" in str(telemetry.operations)
    assert "proposal-123" not in str(telemetry.operations)
    assert "callbacks.example.com/creditos/status" not in str(telemetry.operations)
    assert "signing-secret" not in str(telemetry.operations)

    assert initial.business_events[-1]["callback_status"] == "retrying"
    assert initial.business_events[-1]["failure_code"] == "endpoint_unavailable"
    assert all(event["callback_status"] != "skipped" for event in initial.business_events)
    assert retry.business_events[-1]["callback_status"] == "dlq"
    assert retry.business_events[-1]["error_count"] == 1
    assert retry.business_events[-1]["failure_code"] == "endpoint_rejected"
    assert retry.business_events[-1]["product_type"] == "unknown"
    assert retry.business_events[-1]["channel"] == "api"
    assert "proposal_id" not in retry.business_events[-1]
    assert "endpoint_url" not in retry.business_events[-1]
    assert "event_ref" not in retry.business_events[-1]
    validate_observability_exposure_payload(
        {
            "logs": service.logged_events,
            "business_events": (*initial.business_events, *retry.business_events),
        },
        exposure="technical_internal",
    )


class _RaisingWebhookDeliveryDispatcher:
    def dispatch(
        self,
        *,
        job: Any,
        event: Any,
        configuration: Any,
        context: ObservabilityContext,
        clock: Callable[[], datetime],
        dlq_id_factory: Callable[[str], str],
    ) -> WebhookDeliveryDispatchResult:
        del job, event, configuration, context, clock, dlq_id_factory
        raise RuntimeError("boom")


def _service(
    *,
    repository: InMemoryWebhookConfigurationRepository | None = None,
    audit_publisher: InMemoryAuditEventPublisher | None = None,
    delivery_store: InMemoryWebhookDeliveryStore | None = None,
    dlq_store: InMemoryWebhookDeliveryDlqStore | None = None,
    delivery_adapter: InMemoryWebhookDeliveryAdapter | None = None,
    delivery_dispatcher: WebhookDeliveryDispatcher | None = None,
    telemetry: RecordingTelemetry | None = None,
    configuration_id_factory: Callable[[str], str] | None = None,
    job_id_factory: Callable[[str], str] | None = None,
    dlq_id_factory: Callable[[str], str] | None = None,
    clock: Callable[[], datetime] | None = None,
) -> IntegrationCatalogApplicationService:
    from creditos_integration.adapters.persistence import InMemoryIntegrationCatalogRepository
    from creditos_integration.application.ports.adapter_registry import InMemoryAdapterRegistry

    return IntegrationCatalogApplicationService(
        repository=InMemoryIntegrationCatalogRepository(),
        adapter_registry=InMemoryAdapterRegistry({}),
        audit_publisher=audit_publisher or InMemoryAuditEventPublisher(),
        environment="test",
        clock=clock or (lambda: _FIXED_TIME),
        webhook_configuration_repository=repository or InMemoryWebhookConfigurationRepository(),
        webhook_configuration_id_factory=configuration_id_factory or (lambda _seed: "wcfg_fixed"),
        webhook_allowed_domains_by_tenant={"tenant-bridge-001": ("example.com",)},
        webhook_dns_resolver=lambda _hostname: (_PUBLIC_CALLBACK_IP,),
        webhook_delivery_store=delivery_store or InMemoryWebhookDeliveryStore(),
        webhook_delivery_dlq_store=dlq_store or InMemoryWebhookDeliveryDlqStore(),
        webhook_delivery_dispatcher=delivery_dispatcher
        or InMemoryWebhookDeliveryDispatcher(
            adapter=delivery_adapter
            or InMemoryWebhookDeliveryAdapter([WebhookDeliveryAdapterResult.accepted()]),
            signing_key_resolver=StaticWebhookSigningKeyResolver(
                {("tenant-bridge-001", "wkey_creditos_callback_v1"): b"signing-secret"}
            ),
        ),
        webhook_delivery_job_id_factory=job_id_factory,
        webhook_delivery_dlq_id_factory=dlq_id_factory or (lambda _seed: "wdlq_fixed"),
        telemetry=telemetry,
    )


def _configure_command(**overrides: Any) -> ConfigureWebhookCommand:
    values = {
        "idempotency_key": "idem-webhook-config-001",
        "endpoint_url": "https://callbacks.example.com/creditos/status",
        "events": ("decision.status_changed", "decision.completed"),
        "status": "active",
        "signing_algorithm": "hmac_sha256",
        "signing_key_ref": "wkey_creditos_callback_v1",
        "retry_strategy": "standard_exponential_backoff",
        "max_attempts": 3,
        "initial_backoff_ms": 250,
        "max_backoff_ms": 30_000,
        "timeout_ms": 3_000,
        "scopes": ("webhook_configuration:write",),
    }
    values.update(overrides)
    return ConfigureWebhookCommand(**values)


def _notification_command(**overrides: Any) -> DispatchWebhookNotificationCommand:
    values = {
        "event_id": _EVENT_ID,
        "event_type": "decision.completed",
        "proposal_id": "proposal-123",
        "decision_status": "completed",
        "decision_outcome": "approved",
        "occurred_at": _FIXED_TIME,
        "idempotency_key": None,
        "scopes": ("webhook_delivery:dispatch",),
        "unsafe_payload": {
            "cpf": "123.456.789-09",
            "email": "cliente@example.com",
            "token": "token-local",
        },
    }
    values.update(overrides)
    return DispatchWebhookNotificationCommand(**values)


def _notification_event() -> WebhookNotificationEvent:
    return WebhookNotificationEvent.create(
        event_id=_EVENT_ID,
        event_type="decision.completed",
        proposal_id="proposal-123",
        decision_status="completed",
        decision_outcome="approved",
        occurred_at=_FIXED_TIME,
        correlation_id="corr-webhook-001",
        trace_id="33333333333333333333333333333333",
    )


def _context(
    tenant_id: str | None = "tenant-bridge-001",
    tenant_isolation_tier: str | None = None,
) -> ObservabilityContext:
    return ObservabilityContext.new(
        correlation_id="corr-webhook-001",
        request_id="req-webhook-001",
        trace_id="33333333333333333333333333333333",
        tenant_id=tenant_id,
        tenant_isolation_tier=tenant_isolation_tier
        if tenant_isolation_tier is not None
        else "bridge"
        if tenant_id is not None
        else None,
    )
