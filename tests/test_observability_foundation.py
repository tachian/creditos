from __future__ import annotations

import json
import re

import pytest
from creditos_observability.context import ObservabilityContext
from creditos_observability.health import health_response, readiness_response
from creditos_observability.logging import build_structured_log
from creditos_observability.telemetry import InMemoryTelemetry


def test_http_context_does_not_trust_tenant_from_external_headers() -> None:
    context = ObservabilityContext.from_http_headers(
        {
            "x-correlation-id": "corr-123",
            "x-request-id": "req-123",
            "x-tenant-id": "tenant-alpha",
            "x-tenant-isolation-tier": "bridge",
            "traceparent": "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01",
        }
    )

    assert context.correlation_id == "corr-123"
    assert context.request_id == "req-123"
    assert context.tenant_id is None
    assert context.tenant_isolation_tier is None
    assert context.trace_id == "4bf92f3577b34da6a3ce929d0e0e4736"

    generated = ObservabilityContext.new()

    assert generated.correlation_id
    assert generated.request_id
    assert len(generated.trace_id) == 32


def test_grpc_and_cloudevent_contexts_can_use_trusted_tenant_metadata() -> None:
    grpc_context = ObservabilityContext.from_grpc_metadata(
        [
            ("x-correlation-id", "corr-grpc"),
            ("x-creditos-tenant-id", "tenant-alpha"),
            ("x-creditos-tenant-isolation-tier", "bridge"),
        ]
    )
    event_context = ObservabilityContext.from_cloudevent_attributes(
        {
            "correlationid": "corr-event",
            "tenantid": "tenant-beta",
            "tenanttier": "bridge",
        }
    )

    assert grpc_context.tenant_id == "tenant-alpha"
    assert grpc_context.tenant_isolation_tier == "bridge"
    assert event_context.tenant_id == "tenant-beta"
    assert event_context.tenant_isolation_tier == "bridge"


def test_traceparent_validation_and_injection_use_valid_non_zero_ids() -> None:
    invalid = ObservabilityContext.from_carrier(
        {
            "traceparent": "00-00000000000000000000000000000000-0000000000000000-01",
        }
    )
    carrier = ObservabilityContext.new(trace_id="4bf92f3577b34da6a3ce929d0e0e4736").to_carrier()
    traceparent = carrier["traceparent"]

    assert invalid.trace_id != "0" * 32
    assert re.fullmatch(r"00-[0-9a-f]{32}-[0-9a-f]{16}-01", traceparent)
    assert not traceparent.endswith("-0000000000000000-01")


def test_structured_log_contains_required_fields_and_never_raw_sensitive_values() -> None:
    context = ObservabilityContext.new(
        correlation_id="corr-456",
        request_id="req-456",
        trace_id="4bf92f3577b34da6a3ce929d0e0e4736",
        tenant_id="tenant-alpha",
        tenant_isolation_tier="bridge",
    )

    event = build_structured_log(
        context=context,
        service_name="proposal-intake",
        service_version="0.1.0",
        environment="test",
        operation="submit_proposal",
        source="public-api",
        destination="proposal-intake",
        contract="proposal-intake-public-api",
        contract_version="v1",
        status="accepted",
        status_code=202,
        duration_ms=12.4,
        error_type="ValueError: CPF 123.456.789-09",
        payload={"cpf": "123.456.789-09", "email": "joao.silva@example.com"},
        extra={
            "authorization": "Bearer token-super-secreto",
            "status": "rejected-by-extra",
            "trace_id": "trace-extra",
        },
    )

    serialized_event = json.dumps(event, ensure_ascii=False)

    assert event["service.name"] == "proposal-intake"
    assert event["service.version"] == "0.1.0"
    assert event["deployment.environment"] == "test"
    assert event["tenant_id"] == "tenant-alpha"
    assert event["tenant_isolation_tier"] == "bridge"
    assert event["correlation_id"] == "corr-456"
    assert event["trace_id"] == "4bf92f3577b34da6a3ce929d0e0e4736"
    assert event["request_id"] == "req-456"
    assert event["source"] == "public-api"
    assert event["destination"] == "proposal-intake"
    assert event["contract"] == "proposal-intake-public-api"
    assert event["contract_version"] == "v1"
    assert event["status"] == "accepted"
    assert event["duration_ms"] == 12.4
    assert event["error_type"] != "ValueError: CPF 123.456.789-09"
    assert event["extra"]["status"] == "rejected-by-extra"
    assert "123.456.789-09" not in serialized_event
    assert "joao.silva@example.com" not in serialized_event
    assert "token-super-secreto" not in serialized_event


def test_structured_log_rejects_invalid_duration_and_status_code() -> None:
    context = ObservabilityContext.new()

    with pytest.raises(ValueError, match="duration_ms"):
        build_structured_log(
            context=context,
            service_name="proposal-intake",
            service_version="0.1.0",
            environment="test",
            operation="submit_proposal",
            source="public-api",
            destination="proposal-intake",
            contract="proposal-intake-public-api",
            contract_version="v1",
            status="accepted",
            status_code=202,
            duration_ms=-1,
        )

    with pytest.raises(ValueError, match="status_code"):
        build_structured_log(
            context=context,
            service_name="proposal-intake",
            service_version="0.1.0",
            environment="test",
            operation="submit_proposal",
            source="public-api",
            destination="proposal-intake",
            contract="proposal-intake-public-api",
            contract_version="v1",
            status="accepted",
            status_code=99,
            duration_ms=1,
        )


def test_health_and_readiness_do_not_expose_sensitive_details() -> None:
    health = health_response(service_name="proposal-intake", service_version="0.1.0")
    readiness = readiness_response(
        service_name="proposal-intake",
        service_version="0.1.0",
        checks={
            "database": True,
            "external_api_password=super-secret": False,
            "postgresql-primary.internal": "yes",
        },
    )
    serialized_readiness = json.dumps(readiness, ensure_ascii=False)

    assert health["status"] == "ok"
    assert readiness["status"] == "not_ready"
    assert "super-secret" not in serialized_readiness
    assert "external_api_password" not in serialized_readiness
    assert "postgresql-primary.internal" not in serialized_readiness
    assert "dependency_2" in serialized_readiness
    assert "dependency_3" in serialized_readiness
    checks = readiness["checks"]
    assert isinstance(checks, list)
    assert all(set(item) == {"name", "status"} for item in checks)


def test_in_memory_telemetry_emits_opentelemetry_metrics_and_traces_safely() -> None:
    context = ObservabilityContext.new(
        correlation_id="corr-789",
        trace_id="4bf92f3577b34da6a3ce929d0e0e4736",
        tenant_id="tenant-alpha",
    )
    telemetry = InMemoryTelemetry(service_name="proposal-intake", service_version="0.1.0")

    with telemetry.start_span(
        "submit_proposal",
        context=context,
        attributes={"cpf": "123.456.789-09", "contract": "proposal-intake-public-api"},
    ):
        telemetry.record_request(
            context=context,
            operation="submit_proposal",
            status="accepted",
            duration_ms=15.2,
            attributes={
                "contract": "proposal-intake-public-api",
                "email": "joao.silva@example.com",
                "proposal_id": "proposal-alta-cardinalidade",
            },
        )

    spans = telemetry.finished_spans()
    metrics = telemetry.metrics_data()
    serialized_spans = json.dumps(
        [dict(span.attributes or {}) for span in spans], ensure_ascii=False
    )
    serialized_metrics = str(metrics)

    assert len(spans) == 1
    assert spans[0].name == "submit_proposal"
    assert "creditos.requests.total" in serialized_metrics
    assert "creditos.request.duration" in serialized_metrics
    assert "123.456.789-09" not in serialized_spans
    assert "joao.silva@example.com" not in serialized_metrics
    assert "proposal-alta-cardinalidade" not in serialized_metrics
    assert "corr-789" not in serialized_metrics
    assert "tenant-alpha" not in serialized_metrics


def test_in_memory_telemetry_rejects_invalid_duration_and_does_not_record_exceptions() -> None:
    context = ObservabilityContext.new()
    telemetry = InMemoryTelemetry(service_name="proposal-intake", service_version="0.1.0")

    with pytest.raises(ValueError, match="duration_ms"):
        telemetry.record_request(
            context=context,
            operation="submit_proposal",
            status="accepted",
            duration_ms=-1,
        )

    with (
        pytest.raises(RuntimeError),
        telemetry.start_span(
            "submit_proposal",
            context=context,
            attributes={"contract": "proposal-intake-public-api"},
        ),
    ):
        raise RuntimeError("CPF 123.456.789-09")

    serialized_spans = json.dumps(
        [dict(span.attributes or {}) for span in telemetry.finished_spans()], ensure_ascii=False
    )

    assert "123.456.789-09" not in serialized_spans
