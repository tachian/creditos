from __future__ import annotations

import json

import pytest
from creditos_identity_tenant.adapters.logging.in_memory_operation_logger import (
    InMemoryOperationLogger,
)
from creditos_identity_tenant.adapters.persistence.in_memory_tenant_repository import (
    InMemoryTenantRepository,
)
from creditos_identity_tenant.application.security import OperatorContext
from creditos_identity_tenant.application.service import TenantApplicationService
from creditos_identity_tenant.application.use_cases.create_tenant import CreateTenantCommand
from creditos_identity_tenant.application.use_cases.get_tenant import GetTenantQuery
from creditos_identity_tenant.domain.errors import InvalidTenantStatusError
from creditos_observability.context import ObservabilityContext


class FailingOperationLogger:
    def log(self, event: dict[str, object]) -> None:
        raise RuntimeError("logger indisponível")


def test_application_service_logs_create_and_get_with_traceability_fields() -> None:
    logger = InMemoryOperationLogger()
    service = TenantApplicationService(
        repository=InMemoryTenantRepository(),
        operation_logger=logger,
        tenant_id_generator=lambda: "tenant_alpha",
        environment="test",
    )
    operator = OperatorContext.platform_operator("operator-platform")
    context = ObservabilityContext.new(
        correlation_id="corr-tenant",
        request_id="req-tenant",
        trace_id="4bf92f3577b34da6a3ce929d0e0e4736",
    )

    created = service.create_tenant(
        CreateTenantCommand(name="Financeira Alpha", status="active"),
        operator=operator,
        context=context,
    )
    metadata = service.get_tenant(
        GetTenantQuery(tenant_id="tenant_alpha"),
        operator=operator,
        context=context,
    )

    assert created["tenant_id"] == "tenant_alpha"
    assert metadata["tenant_isolation_tier"] == "bridge"
    assert [event["operation"] for event in logger.events] == [
        "identity_tenant.create_tenant",
        "identity_tenant.get_tenant",
    ]
    assert all(event["correlation_id"] == "corr-tenant" for event in logger.events)
    assert all(event["request_id"] == "req-tenant" for event in logger.events)
    assert all(event["trace_id"] == "4bf92f3577b34da6a3ce929d0e0e4736" for event in logger.events)
    assert all(event["tenant_id"] == "tenant_alpha" for event in logger.events)
    assert all(event["tenant_isolation_tier"] == "bridge" for event in logger.events)


def test_application_service_logs_failures_without_sensitive_payload_leakage() -> None:
    logger = InMemoryOperationLogger()
    service = TenantApplicationService(
        repository=InMemoryTenantRepository(),
        operation_logger=logger,
        tenant_id_generator=lambda: "tenant_invalid",
        environment="test",
    )

    with pytest.raises(InvalidTenantStatusError):
        service.create_tenant(
            CreateTenantCommand(
                name="Tenant com email cliente.sensivel@example.com",
                status="deleted",
                tenant_isolation_tier="bridge",
            ),
            operator=OperatorContext.platform_operator("operator-platform"),
            context=ObservabilityContext.new(correlation_id="corr-error", request_id="req-error"),
        )

    serialized_event = json.dumps(logger.events[0], ensure_ascii=False)

    assert logger.events[0]["status"] == "rejected"
    assert logger.events[0]["payload"] == "[OMITIDO]"
    assert "cliente.sensivel@example.com" not in serialized_event
    assert "deleted" not in serialized_event


def test_application_service_does_not_fail_business_operation_when_logger_fails() -> None:
    repository = InMemoryTenantRepository()
    service = TenantApplicationService(
        repository=repository,
        operation_logger=FailingOperationLogger(),
        tenant_id_generator=lambda: "tenant_alpha",
        environment="test",
    )

    created = service.create_tenant(
        CreateTenantCommand(name="Financeira Alpha", status="active"),
        operator=OperatorContext.platform_operator("operator-platform"),
        context=ObservabilityContext.new(correlation_id="corr-log", request_id="req-log"),
    )

    assert created["tenant_id"] == "tenant_alpha"
    assert repository.get("tenant_alpha") is not None
