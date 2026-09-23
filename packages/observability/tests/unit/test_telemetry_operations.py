from __future__ import annotations

import json

import pytest
from creditos_observability import (
    InMemoryTelemetry,
    ObservabilityContext,
    TelemetryOperationType,
    technical_signal_taxonomy,
)

TRACE_ID = "4bf92f3577b34da6a3ce929d0e0e4736"


def test_technical_signal_taxonomy_classifies_allowed_and_deferred_signals() -> None:
    taxonomy = {signal.name: signal for signal in technical_signal_taxonomy()}

    assert taxonomy["operation.duration"].signal_type == "metric"
    assert taxonomy["operation.trace"].signal_type == "trace/span"
    assert taxonomy["operation.log"].signal_type == "log"
    assert taxonomy["customer-facing.dashboard"].signal_type == "projeção futura"
    assert taxonomy["operation.duration"].allowed_attributes == (
        "channel",
        "contract",
        "contract_version",
        "destination",
        "operation",
        "operation_type",
        "product_type",
        "source",
        "status",
        "tenant_isolation_tier",
    )
    assert "tenant_id" in taxonomy["operation.duration"].forbidden_attributes
    assert "correlation_id" in taxonomy["operation.duration"].forbidden_attributes
    assert "payload" in taxonomy["operation.duration"].forbidden_attributes


def test_record_operation_emits_safe_log_metric_and_span_for_all_operation_types() -> None:
    context = ObservabilityContext.new(
        correlation_id="corr-op-001",
        request_id="req-op-001",
        trace_id=TRACE_ID,
        tenant_id="tenant-alpha",
        tenant_isolation_tier="bridge",
    )
    telemetry = InMemoryTelemetry(
        service_name="integration-service",
        service_version="0.1.0",
        environment="test",
    )

    events = []
    for operation_type in TelemetryOperationType:
        events.append(
            telemetry.record_operation(
                context=context,
                operation_type=operation_type,
                operation=f"{operation_type.value}.execute",
                status="accepted",
                duration_ms=12.5,
                source="creditos-test",
                destination="mock-provider",
                contract="technical-observability",
                contract_version="v1",
                channel="api",
                product_type="personal_credit",
                status_code=202 if operation_type is TelemetryOperationType.HTTP else None,
                payload={"cpf": "123.456.789-09", "email": "pessoa.sintetica@example.test"},
                extra={
                    "headers": {"authorization": "Bearer valor-local"},
                    "prompt": "avaliar documento 123.456.789-09",
                    "attempts": 1,
                },
                attributes={
                    "tenant_id": "tenant-alpha",
                    "correlation_id": "corr-op-001",
                    "request_id": "req-op-001",
                    "proposal_id": "proposal-alta-cardinalidade",
                    "decision_id": "decision-alta-cardinalidade",
                    "cpf": "123.456.789-09",
                    "email": "pessoa.sintetica@example.test",
                    "raw_error": "CPF 123.456.789-09",
                    "operation_type": operation_type.value,
                },
            )
        )

    serialized_events = json.dumps(events, ensure_ascii=False)
    serialized_spans = json.dumps(
        [dict(span.attributes or {}) for span in telemetry.finished_spans()],
        ensure_ascii=False,
    )
    serialized_metrics = str(telemetry.metrics_data())

    assert len(events) == len(tuple(TelemetryOperationType))
    assert len(telemetry.finished_spans()) == len(tuple(TelemetryOperationType))
    assert events[0]["service.name"] == "integration-service"
    assert events[0]["service.version"] == "0.1.0"
    assert events[0]["deployment.environment"] == "test"
    assert events[0]["correlation_id"] == "corr-op-001"
    assert events[0]["request_id"] == "req-op-001"
    assert events[0]["trace_id"] == TRACE_ID
    assert events[0]["tenant_id"] == "tenant-alpha"
    assert events[0]["tenant_isolation_tier"] == "bridge"
    assert events[0]["payload"] == "[OMITIDO]"

    assert "creditos.requests.total" in serialized_metrics
    assert "creditos.request.duration" in serialized_metrics
    assert '"trace_id": "4bf92f3577b34da6a3ce929d0e0e4736"' in serialized_spans
    assert '"duration_ms": 12.5' in serialized_spans
    assert '"request_id": "req-op-001"' in serialized_spans
    assert '"tenant_id": "tenant-alpha"' in serialized_spans
    assert '"tenant_isolation_tier": "bridge"' in serialized_spans
    first_span = telemetry.finished_spans()[0]
    assert first_span.get_span_context() is not None
    assert first_span.parent is None
    assert first_span.start_time is not None
    assert first_span.end_time is not None
    assert (first_span.end_time - first_span.start_time) / 1_000_000 == pytest.approx(12.5)

    for forbidden in (
        "123.456.789-09",
        "pessoa.sintetica@example.test",
        "Bearer valor-local",
        "proposal-alta-cardinalidade",
        "decision-alta-cardinalidade",
    ):
        assert forbidden not in serialized_events
        assert forbidden not in serialized_spans
        assert forbidden not in serialized_metrics

    for high_cardinality_label in (
        "tenant-alpha",
        "corr-op-001",
        "req-op-001",
        TRACE_ID,
    ):
        assert high_cardinality_label not in serialized_metrics


def test_record_operation_validates_before_recording_any_metric_or_span() -> None:
    telemetry = InMemoryTelemetry(service_name="proposal-intake", service_version="0.1.0")

    with pytest.raises(ValueError, match="duration_ms"):
        telemetry.record_operation(
            context=ObservabilityContext.new(trace_id=TRACE_ID),
            operation_type=TelemetryOperationType.HTTP,
            operation="submit_proposal",
            status="accepted",
            duration_ms=-1,
            source="public-api",
            destination="proposal-intake",
            contract="proposal-intake-public-api",
            contract_version="v1",
        )

    assert telemetry.finished_spans() == ()
    assert "creditos.requests.total" not in str(telemetry.metrics_data())


def test_record_operation_rejects_high_cardinality_operation_attributes_atomically() -> None:
    telemetry = InMemoryTelemetry(service_name="proposal-intake", service_version="0.1.0")

    with pytest.raises(ValueError, match="operation"):
        telemetry.record_operation(
            context=ObservabilityContext.new(trace_id=TRACE_ID),
            operation_type=TelemetryOperationType.HTTP,
            operation="proposal.1234567890abcdef1234567890abcdef",
            status="accepted",
            duration_ms=1,
            source="public-api",
            destination="proposal-intake",
            contract="proposal-intake-public-api",
            contract_version="v1",
        )

    with pytest.raises(ValueError, match="source"):
        telemetry.record_operation(
            context=ObservabilityContext.new(trace_id=TRACE_ID),
            operation_type=TelemetryOperationType.HTTP,
            operation="submit_proposal",
            status="accepted",
            duration_ms=1,
            source="/tenants/{tenant_id}/proposals",
            destination="proposal-intake",
            contract="proposal-intake-public-api",
            contract_version="v1",
        )

    with pytest.raises(ValueError, match="channel"):
        telemetry.record_operation(
            context=ObservabilityContext.new(trace_id=TRACE_ID),
            operation_type=TelemetryOperationType.HTTP,
            operation="submit_proposal",
            status="accepted",
            duration_ms=1,
            source="public-api",
            destination="proposal-intake",
            contract="proposal-intake-public-api",
            contract_version="v1",
            attributes={"channel": "550e8400-e29b-41d4-a716-446655440000"},
        )

    assert telemetry.finished_spans() == ()
    assert "creditos.requests.total" not in str(telemetry.metrics_data())


def test_record_operation_ignores_reserved_and_out_of_taxonomy_attributes() -> None:
    context = ObservabilityContext.new(
        correlation_id="corr-op-002",
        request_id="req-op-002",
        trace_id=TRACE_ID,
        tenant_id="tenant-alpha",
        tenant_isolation_tier="bridge",
    )
    telemetry = InMemoryTelemetry(service_name="integration-service", service_version="0.1.0")

    event = telemetry.record_operation(
        context=context,
        operation_type=TelemetryOperationType.INTEGRATION,
        operation="integration.execute",
        status="accepted",
        duration_ms=2,
        source="integration-service",
        destination="mock-provider",
        contract="technical-observability",
        contract_version="v1",
        extra={
            "operation_type": "spoofed",
            "rawError": "provider returned synthetic camel-case failure text",
            "raw_error": "provider returned synthetic failure text",
            "headers": {"authorization": "Bearer valor-local"},
            "nested": {"raw_error": "nested synthetic failure text"},
            "attempts": 1,
        },
        attributes={
            "tenant_id": "evil-tenant",
            "tenant_isolation_tier": "evil-tier",
            "classification": "extra-label",
            "fallback_action": "extra-action",
            "operation_type": "spoofed",
            "contract": "technical-observability",
        },
    )

    spans = telemetry.finished_spans()
    serialized_spans = json.dumps([dict(span.attributes or {}) for span in spans])
    serialized_metrics = str(telemetry.metrics_data())

    assert event["tenant_id"] == "tenant-alpha"
    assert event["tenant_isolation_tier"] == "bridge"
    assert event["extra"]["operation_type"] == "integration"
    assert event["extra"]["attempts"] == 1
    assert "rawError" not in event["extra"]
    assert "raw_error" not in event["extra"]
    assert "headers" not in event["extra"]
    assert "nested" not in event["extra"]
    assert "provider returned" not in json.dumps(event, ensure_ascii=False)
    assert "evil-tenant" not in serialized_spans
    assert "evil-tier" not in serialized_spans
    assert "evil-tenant" not in serialized_metrics
    assert "evil-tier" not in serialized_metrics
    assert "classification" not in serialized_metrics
    assert "fallback_action" not in serialized_metrics
    assert "extra-label" not in serialized_metrics
    assert "extra-action" not in serialized_metrics


def test_start_span_preserves_current_span_hierarchy_when_nested() -> None:
    context = ObservabilityContext.from_carrier(
        {
            "traceparent": f"00-{TRACE_ID}-00f067aa0ba902b7-01",
        }
    )
    telemetry = InMemoryTelemetry(service_name="proposal-intake", service_version="0.1.0")

    with telemetry.start_span("outer", context=context) as outer:
        outer_context = outer.get_span_context()
        with telemetry.start_span("inner", context=context):
            pass

    spans = {span.name: span for span in telemetry.finished_spans()}
    outer_readable_context = spans["outer"].get_span_context()

    assert outer_readable_context is not None
    assert f"{outer_readable_context.trace_id:032x}" == TRACE_ID
    assert spans["inner"].parent is not None
    assert outer_context is not None
    assert spans["inner"].parent.span_id == outer_context.span_id


def test_start_span_without_parent_context_starts_root_span() -> None:
    context = ObservabilityContext.new(trace_id=TRACE_ID)
    telemetry = InMemoryTelemetry(service_name="proposal-intake", service_version="0.1.0")

    with telemetry.start_span("root", context=context):
        pass

    spans = telemetry.finished_spans()

    assert len(spans) == 1
    assert spans[0].parent is None
    assert dict(spans[0].attributes or {})["trace_id"] == TRACE_ID


def test_context_and_log_reject_invalid_trace_id_and_status_code_types() -> None:
    with pytest.raises(ValueError, match="trace_id"):
        ObservabilityContext(
            correlation_id="corr-invalid",
            request_id="req-invalid",
            trace_id="0" * 32,
        )

    with pytest.raises(ValueError, match="status_code"):
        telemetry = InMemoryTelemetry(service_name="proposal-intake", service_version="0.1.0")
        telemetry.record_operation(
            context=ObservabilityContext.new(trace_id=TRACE_ID),
            operation_type=TelemetryOperationType.HTTP,
            operation="submit_proposal",
            status="accepted",
            duration_ms=1,
            source="public-api",
            destination="proposal-intake",
            contract="proposal-intake-public-api",
            contract_version="v1",
            status_code=200.5,  # type: ignore[arg-type]
        )
