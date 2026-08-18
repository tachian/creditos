from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import asdict
from datetime import UTC, datetime
from itertools import chain
from typing import Any, cast

import pytest
from creditos_integration.adapters.persistence import InMemoryIntegrationCatalogRepository
from creditos_integration.application.ports.adapter_registry import InMemoryAdapterRegistry
from creditos_integration.application.ports.audit_event_publisher import (
    InMemoryAuditEventPublisher,
    IntegrationAuditEvent,
)
from creditos_integration.application.service import (
    BuildIntegrationPlanCommand,
    ConfigureIntegrationClassCommand,
    IntegrationCatalogApplicationService,
    ListIntegrationConfigurationsQuery,
)
from creditos_integration.domain.errors import IntegrationValidationError
from creditos_observability.context import ObservabilityContext

_FIXED_TIME = datetime(2026, 8, 17, 15, 30, tzinfo=UTC)


def test_configure_integration_class_records_governed_config_audit_and_log() -> None:
    repository = InMemoryIntegrationCatalogRepository()
    audit_publisher = InMemoryAuditEventPublisher()
    service = _service(repository=repository, audit_publisher=audit_publisher)

    configuration = service.configure_integration_class(
        _configure_command(),
        context=_context(),
    )

    assert configuration.tenant_id == "tenant-bridge-001"
    assert configuration.product_type == "personal_credit"
    assert configuration.integration_class == "kyc_kyb"
    assert configuration.adapter_id == "mock-kyc-basic-v1"
    assert configuration.requirement == "required"
    assert configuration.timeout_ms == 1_500
    assert configuration.max_attempts == 2
    assert configuration.max_concurrency == 3
    assert configuration.estimated_cost_units == 12
    assert configuration.fallback_strategy == "fail_closed"
    assert repository.get(configuration.configuration_id, "tenant-bridge-001") == configuration
    assert audit_publisher.events[0].operation == "integration_catalog.create_configuration"
    assert audit_publisher.events[0].tenant_id == "tenant-bridge-001"
    assert audit_publisher.events[0].result == "accepted"
    assert service.logged_events[-1]["status"] == "accepted"
    assert service.logged_events[-1]["extra"]["integration_class"] == "kyc_kyb"


def test_missing_required_configuration_returns_controlled_state_without_execution() -> None:
    registry = InMemoryAdapterRegistry({"kyc_kyb": {"mock-kyc-basic-v1"}})
    service = _service(adapter_registry=registry)

    plan = service.build_integration_plan(
        BuildIntegrationPlanCommand(
            product_type="personal_credit",
            required_classes=("kyc_kyb",),
        ),
        context=_context(),
    )

    assert plan.status == "missing_required_configuration"
    assert plan.missing_required_classes == ("kyc_kyb",)
    assert plan.items == ()
    assert registry.execution_attempts == []
    assert service.logged_events[-1]["extra"]["plan_status"] == "missing_required_configuration"


def test_build_ready_plan_uses_only_current_tenant_and_product_configurations() -> None:
    repository = InMemoryIntegrationCatalogRepository()
    service = _service(repository=repository)
    service.configure_integration_class(_configure_command(), context=_context("tenant-bridge-001"))
    service.configure_integration_class(
        _configure_command(
            product_type="bnpl",
            integration_class="anti_fraud",
            adapter_id="mock-antifraud-v1",
        ),
        context=_context("tenant-bridge-001"),
    )
    service.configure_integration_class(_configure_command(), context=_context("tenant-bridge-002"))

    plan = service.build_integration_plan(
        BuildIntegrationPlanCommand(
            product_type="personal_credit",
            required_classes=("kyc_kyb",),
        ),
        context=_context("tenant-bridge-001"),
    )

    assert plan.status == "ready"
    assert len(plan.items) == 1
    assert plan.items[0].tenant_id == "tenant-bridge-001"
    assert plan.items[0].product_type == "personal_credit"
    assert plan.items[0].integration_class == "kyc_kyb"


def test_list_configurations_is_tenant_scoped_and_logged() -> None:
    repository = InMemoryIntegrationCatalogRepository()
    service = _service(repository=repository)
    service.configure_integration_class(_configure_command(), context=_context("tenant-bridge-001"))
    service.configure_integration_class(_configure_command(), context=_context("tenant-bridge-002"))

    configurations = service.list_integration_configurations(
        ListIntegrationConfigurationsQuery(product_type="personal_credit"),
        context=_context("tenant-bridge-001"),
    )

    assert len(configurations) == 1
    assert configurations[0].tenant_id == "tenant-bridge-001"
    assert service.logged_events[-1]["operation"] == "integration_catalog.list_configurations"
    assert service.logged_events[-1]["extra"]["integration_classes"] == ["kyc_kyb"]


def test_missing_trusted_tenant_does_not_persist_or_audit() -> None:
    repository = InMemoryIntegrationCatalogRepository()
    audit_publisher = InMemoryAuditEventPublisher()
    service = _service(repository=repository, audit_publisher=audit_publisher)

    with pytest.raises(IntegrationValidationError) as error:
        service.configure_integration_class(_configure_command(), context=_context(None))

    assert error.value.code == "missing_trusted_tenant"
    assert repository.list_all() == []
    assert audit_publisher.events == []
    assert service.logged_events[-1]["status"] == "rejected"


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("integration_class", "raw_payload_lookup", "unsupported_integration_class"),
        ("product_type", "mortgage", "unsupported_product_type"),
        ("adapter_id", "unknown-adapter", "adapter_not_registered"),
        ("timeout_ms", 0, "invalid_timeout"),
        ("timeout_ms", 999_999, "invalid_timeout"),
        ("timeout_ms", True, "invalid_timeout"),
        ("timeout_ms", "1500", "invalid_timeout"),
        ("timeout_ms", 1500.5, "invalid_timeout"),
        ("max_attempts", 0, "invalid_attempt_limit"),
        ("max_attempts", 99, "invalid_attempt_limit"),
        ("max_attempts", False, "invalid_attempt_limit"),
        ("max_attempts", "2", "invalid_attempt_limit"),
        ("max_attempts", 2.5, "invalid_attempt_limit"),
        ("max_concurrency", 0, "invalid_concurrency_limit"),
        ("max_concurrency", 10_000, "invalid_concurrency_limit"),
        ("max_concurrency", True, "invalid_concurrency_limit"),
        ("max_concurrency", "3", "invalid_concurrency_limit"),
        ("max_concurrency", 3.5, "invalid_concurrency_limit"),
        ("estimated_cost_units", -1, "invalid_cost_limit"),
        ("estimated_cost_units", True, "invalid_cost_limit"),
        ("estimated_cost_units", "12", "invalid_cost_limit"),
        ("estimated_cost_units", 12.5, "invalid_cost_limit"),
        ("fallback_strategy", "raw_payload_fallback", "unsupported_fallback_strategy"),
    ],
)
def test_rejects_ungoverned_classes_adapters_and_unsafe_limits(
    field: str,
    value: object,
    code: str,
) -> None:
    service = _service()
    command_data = asdict(_configure_command()) | {field: value}

    with pytest.raises(IntegrationValidationError) as error:
        service.configure_integration_class(
            ConfigureIntegrationClassCommand(**cast(Any, command_data)),
            context=_context(),
        )

    assert error.value.code == code


@pytest.mark.parametrize(
    ("tenant_id", "tenant_isolation_tier", "code"),
    [
        ("   ", "bridge", "missing_trusted_tenant"),
        ("tenant with spaces", "bridge", "invalid_trusted_tenant"),
        ("tenant-bridge-001", None, "missing_tenant_isolation_tier"),
        ("tenant-silo-001", "silo", "unsupported_tenant_isolation_tier"),
    ],
)
def test_rejects_untrusted_tenant_context(
    tenant_id: str,
    tenant_isolation_tier: str | None,
    code: str,
) -> None:
    service = _service()
    context = ObservabilityContext.new(
        correlation_id="corr-integration-001",
        request_id="req-integration-001",
        trace_id="22222222222222222222222222222222",
        tenant_id=tenant_id,
        tenant_isolation_tier=tenant_isolation_tier,
    )

    with pytest.raises(IntegrationValidationError) as error:
        service.configure_integration_class(_configure_command(), context=context)

    assert error.value.code == code


def test_configuration_requires_authorized_scope() -> None:
    service = _service()

    with pytest.raises(IntegrationValidationError) as error:
        service.configure_integration_class(
            _configure_command(scopes=("proposal:read",)),
            context=_context(),
        )

    assert error.value.code == "insufficient_scope"


def test_audit_failure_rolls_back_configuration() -> None:
    repository = InMemoryIntegrationCatalogRepository()
    service = _service(
        repository=repository,
        audit_publisher=FailingAuditEventPublisher(),
    )

    with pytest.raises(RuntimeError, match="audit unavailable"):
        service.configure_integration_class(_configure_command(), context=_context())

    assert repository.list_all() == []
    assert service.logged_events[-1]["status"] == "rejected"


def test_reconfiguring_same_class_updates_single_configuration_and_preserves_created_at() -> None:
    repository = InMemoryIntegrationCatalogRepository()
    audit_publisher = InMemoryAuditEventPublisher()
    service = _service(
        repository=repository,
        audit_publisher=audit_publisher,
        clock=chain(
            (datetime(2026, 8, 17, 15, 30, tzinfo=UTC),),
            (datetime(2026, 8, 17, 15, 45, tzinfo=UTC),),
        ),
    )

    first_configuration = service.configure_integration_class(
        _configure_command(),
        context=_context(),
    )
    updated_configuration = service.configure_integration_class(
        _configure_command(
            adapter_id="mock-kyc-enhanced-v1",
            timeout_ms=2_500,
        ),
        context=_context(),
    )

    assert first_configuration.configuration_id == updated_configuration.configuration_id
    assert updated_configuration.adapter_id == "mock-kyc-enhanced-v1"
    assert updated_configuration.timeout_ms == 2_500
    assert updated_configuration.created_at == first_configuration.created_at
    assert updated_configuration.updated_at > first_configuration.updated_at
    assert len(repository.list_all()) == 1
    assert audit_publisher.events[-1].operation == "integration_catalog.update_configuration"


def test_required_plan_rejects_optional_or_skip_optional_configuration_as_invalid() -> None:
    service = _service()
    service.configure_integration_class(
        _configure_command(requirement="optional", fallback_strategy="skip_optional"),
        context=_context(),
    )

    plan = service.build_integration_plan(
        BuildIntegrationPlanCommand(
            product_type="personal_credit",
            required_classes=("kyc_kyb",),
        ),
        context=_context(),
    )

    assert plan.status == "invalid_configuration"
    assert plan.items == ()
    assert plan.invalid_configuration_classes == ("kyc_kyb",)


def test_plan_returns_invalid_when_registered_adapter_is_removed() -> None:
    registry = InMemoryAdapterRegistry({"kyc_kyb": {"mock-kyc-basic-v1"}})
    service = _service(adapter_registry=registry)
    service.configure_integration_class(_configure_command(), context=_context())
    registry.unregister_adapter("kyc_kyb", "mock-kyc-basic-v1")

    plan = service.build_integration_plan(
        BuildIntegrationPlanCommand(
            product_type="personal_credit",
            required_classes=("kyc_kyb",),
        ),
        context=_context(),
    )

    assert plan.status == "invalid_configuration"
    assert plan.invalid_configuration_classes == ("kyc_kyb",)
    assert registry.execution_attempts == []


def test_safe_logs_and_audit_events_do_not_expose_sensitive_or_raw_payload_fragments() -> None:
    audit_publisher = InMemoryAuditEventPublisher()
    service = _service(audit_publisher=audit_publisher)

    service.configure_integration_class(_configure_command(), context=_context())
    service.build_integration_plan(
        BuildIntegrationPlanCommand(product_type="personal_credit", required_classes=("kyc_kyb",)),
        context=_context(),
    )

    serialized = json.dumps(
        {
            "logs": service.logged_events,
            "audit": [event.to_log_safe_dict() for event in audit_publisher.events],
        },
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )
    for fragment in {
        "00000000191",
        "00000000000191",
        "Pessoa Exemplo",
        "Empresa Exemplo",
        "Authorization",
        "Bearer",
        "secret",
        "token",
        "raw_payload",
        "payload_bruto",
        "credential",
    }:
        assert fragment not in serialized


def _service(
    *,
    repository: InMemoryIntegrationCatalogRepository | None = None,
    adapter_registry: InMemoryAdapterRegistry | None = None,
    audit_publisher: InMemoryAuditEventPublisher | FailingAuditEventPublisher | None = None,
    clock: Iterator[datetime] | None = None,
) -> IntegrationCatalogApplicationService:
    allowed_adapters = {
        "kyc_kyb": {"mock-kyc-basic-v1", "mock-kyc-enhanced-v1"},
        "anti_fraud": {"mock-antifraud-v1"},
    }
    return IntegrationCatalogApplicationService(
        repository=repository or InMemoryIntegrationCatalogRepository(),
        adapter_registry=adapter_registry or InMemoryAdapterRegistry(allowed_adapters),
        audit_publisher=audit_publisher or InMemoryAuditEventPublisher(),
        environment="test",
        clock=(lambda: next(clock)) if clock is not None else (lambda: _FIXED_TIME),
        configuration_id_factory=lambda seed: f"icfg_{seed}",
    )


def _configure_command(
    *,
    product_type: str = "personal_credit",
    integration_class: str = "kyc_kyb",
    adapter_id: str = "mock-kyc-basic-v1",
    requirement: str = "required",
    timeout_ms: int = 1_500,
    max_attempts: int = 2,
    max_concurrency: int = 3,
    estimated_cost_units: int = 12,
    fallback_strategy: str = "fail_closed",
    scopes: tuple[str, ...] = ("integration_catalog:write",),
) -> ConfigureIntegrationClassCommand:
    return ConfigureIntegrationClassCommand(
        product_type=product_type,
        integration_class=integration_class,
        adapter_id=adapter_id,
        requirement=requirement,
        timeout_ms=timeout_ms,
        max_attempts=max_attempts,
        max_concurrency=max_concurrency,
        estimated_cost_units=estimated_cost_units,
        fallback_strategy=fallback_strategy,
        scopes=scopes,
    )


def _context(tenant_id: str | None = "tenant-bridge-001") -> ObservabilityContext:
    return ObservabilityContext.new(
        correlation_id="corr-integration-001",
        request_id="req-integration-001",
        trace_id="22222222222222222222222222222222",
        tenant_id=tenant_id,
        tenant_isolation_tier="bridge" if tenant_id else None,
    )


class FailingAuditEventPublisher:
    def publish(self, event: IntegrationAuditEvent) -> None:
        raise RuntimeError("audit unavailable")
