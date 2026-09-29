from __future__ import annotations

import json

import pytest
from creditos_observability import (
    InMemoryTelemetry,
    ObservabilityCapability,
    ObservabilityContext,
    ObservabilitySignal,
    TelemetryOperationType,
    internal_alert_catalog,
    internal_dashboard_catalog,
    observability_gate_catalog,
    validate_customer_facing_observability_payload,
    validate_observability_exposure_payload,
    validate_observability_gate_catalog,
)

TRACE_ID = "4bf92f3577b34da6a3ce929d0e0e4736"


def test_observability_gate_catalog_covers_required_capabilities_and_signals() -> None:
    catalog = observability_gate_catalog()

    validate_observability_gate_catalog(catalog)

    operation_capabilities = {
        capability.operation_type for capability in catalog if capability.operation_type is not None
    }
    assert operation_capabilities == set(TelemetryOperationType)

    for operation_type in TelemetryOperationType:
        capability = next(item for item in catalog if item.operation_type is operation_type)
        assert set(capability.required_signals) >= {
            ObservabilitySignal.STRUCTURED_LOG,
            ObservabilitySignal.METRIC,
            ObservabilitySignal.TRACE_SPAN,
            ObservabilitySignal.CORRELATION_ID,
        }

    all_signals = {signal for capability in catalog for signal in capability.required_signals}
    assert {
        ObservabilitySignal.HEALTH,
        ObservabilitySignal.READINESS,
    }.issubset(all_signals)

    missing_trace_catalog = (
        ObservabilityCapability(
            name="http_without_trace",
            service_name="proposal-intake",
            operation_type=TelemetryOperationType.HTTP,
            required_signals=(
                ObservabilitySignal.STRUCTURED_LOG,
                ObservabilitySignal.METRIC,
                ObservabilitySignal.CORRELATION_ID,
            ),
        ),
    )

    with pytest.raises(ValueError, match="trace_span|gRPC|job|integration|readiness"):
        validate_observability_gate_catalog(missing_trace_catalog)


def test_technical_operation_artifacts_pass_exposure_gate_without_sensitive_values() -> None:
    context = ObservabilityContext.new(
        correlation_id="corr-epic7",
        request_id="req-epic7",
        trace_id=TRACE_ID,
        tenant_id="tenant-alpha",
        tenant_isolation_tier="bridge",
    )
    telemetry = InMemoryTelemetry(
        service_name="observability-gate",
        service_version="0.1.0",
        environment="test",
    )

    events = [
        telemetry.record_operation(
            context=context,
            operation_type=operation_type,
            operation=f"{operation_type.value}.execute",
            status="accepted",
            duration_ms=7.6,
            source="creditos-test",
            destination="mock-dependency",
            contract="observability-gate",
            contract_version="v1",
            payload={"cpf": "123.456.789-09", "token": "token-local"},
            extra={"attempts": 1},
            attributes={
                "tenant_id": "tenant-alpha",
                "correlation_id": "corr-epic7",
                "proposal_id": "proposal-unsafe",
            },
        )
        for operation_type in TelemetryOperationType
    ]

    payload = {
        "events": events,
        "spans": [dict(span.attributes or {}) for span in telemetry.finished_spans()],
        "metrics": str(telemetry.metrics_data()),
    }
    serialized = json.dumps(payload, ensure_ascii=False)

    validate_observability_exposure_payload(payload, exposure="technical_internal")
    assert "123.456.789-09" not in serialized
    assert "token-local" not in serialized
    assert "proposal-unsafe" not in serialized
    assert "tenant-alpha" not in str(telemetry.metrics_data())
    assert "corr-epic7" not in str(telemetry.metrics_data())


def test_internal_dashboard_and_alert_artifacts_pass_secure_exposure_gate() -> None:
    payload = {
        "dashboards": [dashboard.to_dict() for dashboard in internal_dashboard_catalog()],
        "alerts": [group.to_dict() for group in internal_alert_catalog()],
    }

    validate_observability_exposure_payload(payload, exposure="internal_catalog")

    with pytest.raises(ValueError, match="raw_log"):
        validate_observability_exposure_payload(
            {"panel": {"query": "raw_log_payload", "labels": {"tenant_id": "tenant-a"}}},
            exposure="internal_catalog",
        )


def test_customer_facing_payload_gate_blocks_telemetry_and_infrastructure_leaks() -> None:
    safe_payload = {
        "tenant_ref": "tenant-alpha",
        "sections": {
            "business_funnel": {"cards": {"received": {"count": 1}}},
            "operational_health": {
                "cards": {"api": {"status": "unknown", "message": "signal_not_available"}}
            },
        },
    }

    validate_customer_facing_observability_payload(
        safe_payload,
        expected_tenant_ref="tenant-alpha",
        granted_scopes=frozenset({"dashboard:read"}),
        curated_source="reporting_insights_projection",
    )

    unsafe_payload = {
        "tenant_ref": "tenant-alpha",
        "prometheus_query": "rate(creditos_requests_total[5m])",
        "trace_id": TRACE_ID,
        "pod": "creditos-api-123",
    }

    with pytest.raises(ValueError, match="prometheus|trace_id|pod"):
        validate_customer_facing_observability_payload(
            unsafe_payload,
            expected_tenant_ref="tenant-alpha",
            granted_scopes=frozenset({"dashboard:read"}),
            curated_source="reporting_insights_projection",
        )


@pytest.mark.parametrize(
    "unsafe_payload,expected_term",
    [
        ({"payload": {"cpf": "12345678909"}}, "payload"),
        ({"auth_token": "valor-local"}, "token"),
        ({"clientSecret": "valor-local"}, "secret"),
        ({"message": "secret=valor-local"}, "secret"),
        ({"message": "cpf 12345678909"}, "cpf"),
        ({"message": "cnpj 11222333000181"}, "cnpj"),
        ({"prompt": "texto minimizado"}, "prompt"),
        ({"output": "texto minimizado"}, "output"),
    ],
)
def test_technical_exposure_gate_blocks_aliases_digit_only_documents_and_raw_payloads(
    unsafe_payload: dict[str, object],
    expected_term: str,
) -> None:
    with pytest.raises(ValueError, match=expected_term):
        validate_observability_exposure_payload(unsafe_payload, exposure="technical_internal")


def test_customer_facing_gate_requires_tenant_scope_and_curated_source() -> None:
    payload = {"tenant_ref": "tenant-alpha", "sections": {"business_funnel": {"cards": {}}}}

    with pytest.raises(ValueError, match="expected_tenant_ref"):
        validate_customer_facing_observability_payload(
            payload,
            expected_tenant_ref=None,
            granted_scopes=frozenset({"dashboard:read"}),
            curated_source="reporting_insights_projection",
        )
    with pytest.raises(ValueError, match="tenant_ref"):
        validate_customer_facing_observability_payload(
            payload,
            expected_tenant_ref="tenant-beta",
            granted_scopes=frozenset({"dashboard:read"}),
            curated_source="reporting_insights_projection",
        )
    with pytest.raises(ValueError, match="escopo"):
        validate_customer_facing_observability_payload(
            payload,
            expected_tenant_ref="tenant-alpha",
            granted_scopes=frozenset({"proposal:read"}),
            curated_source="reporting_insights_projection",
        )
    with pytest.raises(ValueError, match="curada"):
        validate_customer_facing_observability_payload(
            payload,
            expected_tenant_ref="tenant-alpha",
            granted_scopes=frozenset({"dashboard:read"}),
            curated_source="prometheus",
        )


@pytest.mark.parametrize(
    "unsafe_payload,expected_term",
    [
        ({"billing": {"amount": 10}}, "billing"),
        ({"price": 10}, "price"),
        ({"cost_currency": "BRL"}, "cost_currency"),
        ({"transactional_database": "proposal-db"}, "transactional_database"),
    ],
)
def test_customer_facing_gate_blocks_billing_price_currency_and_transactional_sources(
    unsafe_payload: dict[str, object],
    expected_term: str,
) -> None:
    payload = {"tenant_ref": "tenant-alpha", "sections": unsafe_payload}

    with pytest.raises(ValueError, match=expected_term):
        validate_customer_facing_observability_payload(
            payload,
            expected_tenant_ref="tenant-alpha",
            granted_scopes=frozenset({"dashboard:read"}),
            curated_source="reporting_insights_projection",
        )


def test_exposure_gate_rejects_invalid_exposure_and_problematic_iterables() -> None:
    with pytest.raises(ValueError, match="exposure inválido"):
        validate_observability_exposure_payload({}, exposure="typo")  # type: ignore[arg-type]

    cyclic: dict[str, object] = {}
    cyclic["self"] = cyclic
    with pytest.raises(ValueError, match="cycle"):
        validate_observability_exposure_payload(cyclic, exposure="technical_internal")

    with pytest.raises(ValueError, match="bytes"):
        validate_observability_exposure_payload({"artifact": b"raw"}, exposure="technical_internal")

    validate_observability_exposure_payload({"artifact": b""}, exposure="technical_internal")
    validate_customer_facing_observability_payload(
        {"tenant_ref": "tenant-alpha", "sections": {"latency": {"cards": {"tempo_medio": 1}}}},
        expected_tenant_ref="tenant-alpha",
        granted_scopes=frozenset({"dashboard:read"}),
        curated_source="reporting_insights_projection",
    )


def test_observability_gate_catalog_requires_health_and_readiness_per_operation_service() -> None:
    catalog = tuple(
        ObservabilityCapability(
            name=f"{operation_type.value}_operation",
            service_name="service-without-readiness",
            operation_type=operation_type,
            required_signals=(
                ObservabilitySignal.STRUCTURED_LOG,
                ObservabilitySignal.METRIC,
                ObservabilitySignal.TRACE_SPAN,
                ObservabilitySignal.CORRELATION_ID,
            ),
        )
        for operation_type in TelemetryOperationType
    ) + (
        ObservabilityCapability(
            name="other_service_health",
            service_name="other-service",
            required_signals=(ObservabilitySignal.HEALTH, ObservabilitySignal.READINESS),
        ),
    )

    with pytest.raises(ValueError, match="service-without-readiness"):
        validate_observability_gate_catalog(catalog)
