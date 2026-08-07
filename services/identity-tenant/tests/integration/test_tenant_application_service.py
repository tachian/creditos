from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest
from creditos_identity_tenant.adapters.external.local_m2m_token_verifier import (
    LocalM2MTokenClaims,
    LocalM2MTokenVerifier,
)
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
from creditos_identity_tenant.application.use_cases.resolve_m2m_tenant_context import (
    ResolveM2MTenantContextCommand,
)
from creditos_identity_tenant.bootstrap.app import build_local_tenant_application_service
from creditos_identity_tenant.domain.entities.tenant import Tenant
from creditos_identity_tenant.domain.errors import (
    InvalidTenantStatusError,
    InvalidTokenError,
    MissingTokenError,
)
from creditos_observability.context import ObservabilityContext


class FailingOperationLogger:
    def log(self, event: dict[str, object]) -> None:
        raise RuntimeError("logger indisponível")


NOW = datetime(2026, 8, 6, 12, 0, tzinfo=UTC)


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


def test_application_service_resolves_m2m_context_and_logs_without_token_leakage() -> None:
    logger = InMemoryOperationLogger()
    repository = InMemoryTenantRepository()
    repository.save_unique(
        Tenant.create(
            tenant_id="tenant_alpha",
            name="Financeira Alpha",
            status="active",
            operator_id="operator-platform",
        )
    )
    service = TenantApplicationService(
        repository=repository,
        operation_logger=logger,
        m2m_token_verifier=_local_verifier(),
        environment="test",
    )

    result = service.resolve_m2m_tenant_context(
        ResolveM2MTenantContextCommand(
            authorization_header="Bearer local-token-alpha",
            payload_tenant_id="tenant_alpha",
            now=NOW,
        ),
        context=ObservabilityContext.new(
            correlation_id="corr-auth",
            request_id="req-auth",
            trace_id="4bf92f3577b34da6a3ce929d0e0e4736",
        ),
    )

    assert result["tenant_id"] == "tenant_alpha"
    assert result["tenant_isolation_tier"] == "bridge"
    assert logger.events[-1]["operation"] == "identity_tenant.resolve_m2m_tenant_context"
    assert logger.events[-1]["status"] == "accepted"
    assert logger.events[-1]["tenant_id"] == "tenant_alpha"
    assert logger.events[-1]["tenant_isolation_tier"] == "bridge"
    assert logger.events[-1]["extra"]["client_id"] == "client-alpha"

    serialized_event = json.dumps(logger.events[-1], ensure_ascii=False)
    assert "local-token-alpha" not in serialized_event
    assert "Authorization" not in serialized_event
    assert "Bearer" not in serialized_event


def test_application_service_logs_m2m_failures_without_token_or_authorization_header() -> None:
    logger = InMemoryOperationLogger()
    service = TenantApplicationService(
        repository=InMemoryTenantRepository(),
        operation_logger=logger,
        m2m_token_verifier=_local_verifier(),
        environment="test",
    )

    with pytest.raises(MissingTokenError):
        service.resolve_m2m_tenant_context(
            ResolveM2MTenantContextCommand(
                authorization_header=None,
                payload_tenant_id="tenant_alpha",
                now=NOW,
            ),
            context=ObservabilityContext.new(
                correlation_id="corr-auth-fail",
                request_id="req-auth-fail",
            ),
        )

    serialized_event = json.dumps(logger.events[-1], ensure_ascii=False)
    assert logger.events[-1]["operation"] == "identity_tenant.resolve_m2m_tenant_context"
    assert logger.events[-1]["status"] == "rejected"
    assert logger.events[-1]["payload"] == "[OMITIDO]"
    assert "local-token-alpha" not in serialized_event
    assert "Authorization" not in serialized_event
    assert "Bearer" not in serialized_event


def test_application_service_does_not_log_raw_invalid_m2m_token() -> None:
    logger = InMemoryOperationLogger()
    service = TenantApplicationService(
        repository=InMemoryTenantRepository(),
        operation_logger=logger,
        m2m_token_verifier=_local_verifier(),
        environment="test",
    )

    with pytest.raises(InvalidTokenError):
        service.resolve_m2m_tenant_context(
            ResolveM2MTenantContextCommand(
                authorization_header="Bearer raw-secret-token",
                payload_tenant_id="tenant_alpha",
                now=NOW,
            ),
            context=ObservabilityContext.new(
                correlation_id="corr-invalid",
                request_id="req-invalid",
            ),
        )

    serialized_event = json.dumps(logger.events[-1], ensure_ascii=False)
    assert logger.events[-1]["operation"] == "identity_tenant.resolve_m2m_tenant_context"
    assert logger.events[-1]["status"] == "rejected"
    assert logger.events[-1]["payload"] == "[OMITIDO]"
    assert "raw-secret-token" not in serialized_event
    assert "Bearer" not in serialized_event


def test_application_service_clears_untrusted_tenant_from_m2m_failure_logs() -> None:
    logger = InMemoryOperationLogger()
    service = TenantApplicationService(
        repository=InMemoryTenantRepository(),
        operation_logger=logger,
        m2m_token_verifier=_local_verifier(),
        environment="test",
    )

    with pytest.raises(MissingTokenError):
        service.resolve_m2m_tenant_context(
            ResolveM2MTenantContextCommand(
                authorization_header=None,
                payload_tenant_id="tenant_alpha",
                now=NOW,
            ),
            context=ObservabilityContext.new(
                correlation_id="corr-untrusted",
                request_id="req-untrusted",
                tenant_id="tenant_spoofed",
                tenant_isolation_tier="silo",
            ),
        )

    assert "tenant_id" not in logger.events[-1]
    assert "tenant_isolation_tier" not in logger.events[-1]


def test_local_bootstrap_can_compose_m2m_verifier_for_harness() -> None:
    service = build_local_tenant_application_service(
        environment="test",
        tenant_id_generator=lambda: "tenant_alpha",
        m2m_token_verifier=_local_verifier(),
    )
    service.create_tenant(
        CreateTenantCommand(name="Financeira Alpha", status="active"),
        operator=OperatorContext.platform_operator("operator-platform"),
        context=ObservabilityContext.new(
            correlation_id="corr-bootstrap",
            request_id="req-bootstrap",
        ),
    )

    resolved = service.resolve_m2m_tenant_context(
        ResolveM2MTenantContextCommand(
            authorization_header="Bearer local-token-alpha",
            payload_tenant_id="tenant_alpha",
            now=NOW,
        ),
        context=ObservabilityContext.new(
            correlation_id="corr-bootstrap",
            request_id="req-bootstrap",
        ),
    )

    assert resolved["tenant_id"] == "tenant_alpha"


def _local_verifier() -> LocalM2MTokenVerifier:
    return LocalM2MTokenVerifier(
        issuer="https://issuer.creditos.local",
        audience="creditos-api",
        trusted_key_ids={"kid-local"},
        tokens={
            "local-token-alpha": LocalM2MTokenClaims(
                issuer="https://issuer.creditos.local",
                audience="creditos-api",
                subject="client-alpha",
                client_id="client-alpha",
                tenant_id="tenant_alpha",
                tenant_isolation_tier="bridge",
                scopes=("proposal:submit",),
                token_id="jti-local-alpha",
                issued_at=NOW - timedelta(minutes=1),
                expires_at=NOW + timedelta(minutes=5),
                key_id="kid-local",
            )
        },
    )
