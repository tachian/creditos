from __future__ import annotations

import json
from typing import Any

import pytest
from creditos_observability.context import ObservabilityContext
from creditos_observability.logging import build_structured_log


def test_structured_log_enforces_safe_envelope_and_omits_payload() -> None:
    event = build_structured_log(
        context=ObservabilityContext(
            correlation_id="corr-alpha",
            request_id="req-alpha",
            trace_id="4bf92f3577b34da6a3ce929d0e0e4736",
            tenant_id="tenant_alpha",
            tenant_isolation_tier="bridge",
        ),
        service_name="integration\nservice",
        service_version="0.1.0\rmalicious",
        environment="test\t",
        operation="integration.execute\nforged=true",
        source="integration.application",
        destination="external-provider\rheaders",
        contract="integration-execution",
        contract_version="v1\nv2",
        status="accepted\nfailed",
        technical_result="provider:accepted=queued",
        status_code=202,
        duration_ms=12.5,
        error_type="Provider\nTimeout 000.000.001-91",
        payload={"document": "00000000191", "token": "secret-token"},
        extra={
            "attempts": 2,
            "timeout_ms": 750,
            "headers": {"Authorization": "Bearer raw-token", "X-Cpf": "00000000191"},
            "request_body": {"document": "00000000191"},
            "provider_payload": {"email": "cliente.sensivel@example.com"},
            "prompt": "avalie 00000000191",
            "completion": "aprovado para cliente.sensivel@example.com",
            "monthly_income": 500000,
        },
    )

    assert event["service.name"] == "integration_service"
    assert event["service.version"] == "0.1.0_malicious"
    assert event["deployment.environment"] == "test"
    assert event["operation"] == "integration.execute_forged_true"
    assert event["destination"] == "external-provider_headers"
    assert event["contract_version"] == "v1_v2"
    assert event["status"] == "accepted_failed"
    assert event["technical_result"] == "provider_accepted_queued"
    assert event["payload"] == "[OMITIDO]"
    assert event["extra"]["headers"] == "[OMITIDO]"
    assert event["extra"]["request_body"] == "[OMITIDO]"
    assert event["extra"]["provider_payload"] == "[OMITIDO]"
    assert event["extra"]["prompt"] == "[OMITIDO]"
    assert event["extra"]["completion"] == "[OMITIDO]"
    assert event["extra"]["monthly_income"] == "[DADO_FINANCEIRO_OMITIDO]"

    serialized = _serialized(event)
    assert "\n" not in serialized
    assert "\r" not in serialized
    assert "\t" not in serialized
    assert "00000000191" not in serialized
    assert "000.000.001-91" not in serialized
    assert "cliente.sensivel@example.com" not in serialized
    assert "raw-token" not in serialized
    assert "secret-token" not in serialized
    assert "500000" not in serialized


def test_structured_log_rejects_empty_required_technical_fields() -> None:
    with pytest.raises(ValueError, match="service_name"):
        build_structured_log(
            context=ObservabilityContext.new(),
            service_name="",
            service_version="0.1.0",
            environment="test",
            operation="operation",
            source="source",
            destination="destination",
            contract="contract",
            contract_version="v1",
            status="accepted",
            duration_ms=1.0,
        )

    with pytest.raises(ValueError, match="operation"):
        build_structured_log(
            context=ObservabilityContext.new(),
            service_name="service",
            service_version="0.1.0",
            environment="test",
            operation=None,  # type: ignore[arg-type]
            source="source",
            destination="destination",
            contract="contract",
            contract_version="v1",
            status="accepted",
            duration_ms=1.0,
        )


def _serialized(event: dict[str, Any]) -> str:
    return json.dumps(event, sort_keys=True, ensure_ascii=False)
