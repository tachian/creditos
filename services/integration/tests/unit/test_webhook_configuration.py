from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

import pytest
from creditos_integration.adapters.persistence import InMemoryWebhookConfigurationRepository
from creditos_integration.application.ports.audit_event_publisher import InMemoryAuditEventPublisher
from creditos_integration.application.service import (
    ConfigureWebhookCommand,
    DisableWebhookConfigurationCommand,
    IntegrationCatalogApplicationService,
    ListWebhookConfigurationsQuery,
)
from creditos_integration.domain.errors import IntegrationValidationError
from creditos_observability.context import ObservabilityContext

_FIXED_TIME = datetime(2026, 10, 6, 12, 0, tzinfo=UTC)
_PUBLIC_CALLBACK_IP = "93.184.216.34"


def test_configure_webhook_records_tenant_scoped_config_audit_and_safe_log() -> None:
    repository = InMemoryWebhookConfigurationRepository()
    audit_publisher = InMemoryAuditEventPublisher()
    service = _service(repository=repository, audit_publisher=audit_publisher)

    configuration = service.configure_webhook(
        _configure_command(),
        context=_context(),
    )

    assert configuration.tenant_id == "tenant-bridge-001"
    assert configuration.webhook_configuration_id == "wcfg_fixed"
    assert configuration.endpoint_url == "https://callbacks.example.com/creditos/status"
    assert configuration.endpoint_host == "callbacks.example.com"
    assert configuration.events == ("decision.completed", "decision.status_changed")
    assert configuration.status == "active"
    assert configuration.signing_algorithm == "hmac_sha256"
    assert configuration.signing_key_ref == "wkey_creditos_callback_v1"
    assert configuration.retry_strategy == "standard_exponential_backoff"
    assert repository.get("wcfg_fixed", "tenant-bridge-001") == configuration
    assert audit_publisher.events[0].operation == "webhook_configuration.create"
    assert audit_publisher.events[0].tenant_id == "tenant-bridge-001"
    assert audit_publisher.events[0].webhook_configuration_id == "wcfg_fixed"
    assert audit_publisher.events[0].event_types == (
        "decision.completed",
        "decision.status_changed",
    )
    log = service.logged_events[-1]
    assert log["operation"] == "webhook_configuration.create"
    assert log["status"] == "accepted"
    assert log["extra"]["endpoint_host"] == "callbacks.example.com"
    serialized_log = str(log).lower()
    assert "tenant-alpha" not in serialized_log
    assert "signing_secret" not in serialized_log
    assert "token-local" not in serialized_log


def test_webhook_configuration_rejects_unsafe_endpoint_without_persisting_and_audits() -> None:
    repository = InMemoryWebhookConfigurationRepository()
    audit_publisher = InMemoryAuditEventPublisher()
    service = _service(repository=repository, audit_publisher=audit_publisher)

    with pytest.raises(IntegrationValidationError) as error:
        service.configure_webhook(
            _configure_command(endpoint_url="http://127.0.0.1/internal?token=abc"),
            context=_context(),
        )

    assert error.value.code == "insecure_webhook_endpoint"
    assert repository.list_all() == []
    assert audit_publisher.events[-1].operation == "webhook_configuration.configure"
    assert audit_publisher.events[-1].result == "rejected"
    assert audit_publisher.events[-1].denial_reason == "insecure_webhook_endpoint"
    log = service.logged_events[-1]
    assert log["status"] == "rejected"
    assert log["extra"]["denial_reason"] == "insecure_webhook_endpoint"
    assert "127.0.0.1" not in str(log)
    assert "token=abc" not in str(log)


def test_webhook_configuration_rejects_endpoint_outside_trusted_tenant_allowlist() -> None:
    service = _service(allowed_domains_by_tenant={"tenant-bridge-001": ("example.com",)})

    with pytest.raises(IntegrationValidationError) as error:
        service.configure_webhook(
            _configure_command(endpoint_url="https://callbacks.evil.test/status"),
            context=_context(),
        )

    assert error.value.code == "webhook_endpoint_not_allowed"


def test_webhook_configuration_rejects_hostname_resolving_to_private_address() -> None:
    service = _service(dns_resolver=lambda _hostname: ("10.10.10.10",))

    with pytest.raises(IntegrationValidationError) as error:
        service.configure_webhook(
            _configure_command(endpoint_url="https://callbacks.example.com/status"),
            context=_context(),
        )

    assert error.value.code == "insecure_webhook_endpoint"


def test_webhook_configuration_rejects_sensitive_query_variants_and_non_policy_port() -> None:
    service = _service()

    with pytest.raises(IntegrationValidationError) as query_error:
        service.configure_webhook(
            _configure_command(endpoint_url="https://callbacks.example.com/status?api_key=abc"),
            context=_context(),
        )
    with pytest.raises(IntegrationValidationError) as port_error:
        service.configure_webhook(
            _configure_command(endpoint_url="https://callbacks.example.com:8443/status"),
            context=_context(),
        )

    assert query_error.value.code == "sensitive_webhook_query"
    assert port_error.value.code == "insecure_webhook_endpoint"


def test_webhook_configuration_rejects_rejected_status_and_invalid_idempotency_key() -> None:
    service = _service()

    with pytest.raises(IntegrationValidationError) as status_error:
        service.configure_webhook(_configure_command(status="rejected"), context=_context())
    with pytest.raises(IntegrationValidationError) as idempotency_error:
        service.configure_webhook(_configure_command(idempotency_key="short"), context=_context())

    assert status_error.value.code == "unsupported_webhook_status"
    assert idempotency_error.value.code == "invalid_integration_execution_idempotency_key"


def test_webhook_configuration_id_seed_uses_normalized_endpoint() -> None:
    seeds: list[str] = []
    service = _service(id_factory=lambda seed: seeds.append(seed) or "wcfg_fixed")

    configuration = service.configure_webhook(
        _configure_command(endpoint_url="https://CALLBACKS.EXAMPLE.COM./creditos/status"),
        context=_context(),
    )

    assert configuration.endpoint_url == "https://callbacks.example.com/creditos/status"
    assert seeds == [
        "tenant-bridge-001|https://callbacks.example.com/creditos/status|decision.completed,decision.status_changed"
    ]


def test_list_webhook_configurations_is_tenant_scoped_and_requires_scope() -> None:
    repository = InMemoryWebhookConfigurationRepository()
    service = _service(repository=repository)
    service.configure_webhook(_configure_command(), context=_context("tenant-bridge-001"))
    service.configure_webhook(_configure_command(), context=_context("tenant-bridge-002"))

    configurations = service.list_webhook_configurations(
        ListWebhookConfigurationsQuery(scopes=("webhook_configuration:read",)),
        context=_context("tenant-bridge-001"),
    )

    assert len(configurations) == 1
    assert configurations[0].tenant_id == "tenant-bridge-001"
    assert service.logged_events[-1]["operation"] == "webhook_configuration.list"

    with pytest.raises(IntegrationValidationError) as error:
        service.list_webhook_configurations(
            ListWebhookConfigurationsQuery(scopes=("proposal:read",)),
            context=_context("tenant-bridge-001"),
        )

    assert error.value.code == "insufficient_scope"


def test_disable_webhook_configuration_updates_status_and_audits() -> None:
    repository = InMemoryWebhookConfigurationRepository()
    audit_publisher = InMemoryAuditEventPublisher()
    service = _service(repository=repository, audit_publisher=audit_publisher)
    service.configure_webhook(_configure_command(), context=_context())

    disabled = service.disable_webhook_configuration(
        DisableWebhookConfigurationCommand(
            idempotency_key="idem-webhook-disable-001",
            webhook_configuration_id="wcfg_fixed",
            scopes=("webhook_configuration:write",),
        ),
        context=_context(),
    )

    assert disabled.status == "disabled"
    assert repository.get("wcfg_fixed", "tenant-bridge-001") == disabled
    assert audit_publisher.events[-1].operation == "webhook_configuration.disable"
    assert service.logged_events[-1]["extra"]["webhook_status"] == "disabled"


def test_configure_webhook_rolls_back_when_audit_fails() -> None:
    repository = InMemoryWebhookConfigurationRepository()
    service = _service(repository=repository, audit_publisher=FailingAuditEventPublisher())

    with pytest.raises(RuntimeError, match="audit unavailable"):
        service.configure_webhook(_configure_command(), context=_context())

    assert repository.list_all() == []
    assert service.logged_events[-1]["status"] == "rejected"


def _service(
    *,
    repository: InMemoryWebhookConfigurationRepository | None = None,
    audit_publisher: InMemoryAuditEventPublisher | FailingAuditEventPublisher | None = None,
    allowed_domains_by_tenant: dict[str, tuple[str, ...]] | None = None,
    dns_resolver: Callable[[str], tuple[str, ...]] | None = None,
    id_factory: Callable[[str], str] | None = None,
) -> IntegrationCatalogApplicationService:
    from creditos_integration.adapters.persistence import InMemoryIntegrationCatalogRepository
    from creditos_integration.application.ports.adapter_registry import InMemoryAdapterRegistry

    return IntegrationCatalogApplicationService(
        repository=InMemoryIntegrationCatalogRepository(),
        adapter_registry=InMemoryAdapterRegistry({}),
        audit_publisher=audit_publisher or InMemoryAuditEventPublisher(),
        environment="test",
        clock=lambda: _FIXED_TIME,
        webhook_configuration_repository=repository or InMemoryWebhookConfigurationRepository(),
        webhook_configuration_id_factory=id_factory or (lambda _seed: "wcfg_fixed"),
        webhook_allowed_domains_by_tenant=allowed_domains_by_tenant,
        webhook_dns_resolver=dns_resolver or (lambda _hostname: (_PUBLIC_CALLBACK_IP,)),
    )


def _configure_command(
    *,
    idempotency_key: str = "idem-webhook-config-001",
    endpoint_url: str = "https://callbacks.example.com/creditos/status",
    status: str = "active",
) -> ConfigureWebhookCommand:
    return ConfigureWebhookCommand(
        idempotency_key=idempotency_key,
        endpoint_url=endpoint_url,
        events=("decision.status_changed", "decision.completed"),
        status=status,
        signing_algorithm="hmac_sha256",
        signing_key_ref="wkey_creditos_callback_v1",
        retry_strategy="standard_exponential_backoff",
        max_attempts=3,
        initial_backoff_ms=250,
        max_backoff_ms=30_000,
        timeout_ms=3_000,
        scopes=("webhook_configuration:write",),
    )


def _context(tenant_id: str | None = "tenant-bridge-001") -> ObservabilityContext:
    return ObservabilityContext.new(
        correlation_id="corr-webhook-001",
        request_id="req-webhook-001",
        trace_id="33333333333333333333333333333333",
        tenant_id=tenant_id,
        tenant_isolation_tier="bridge" if tenant_id is not None else None,
    )


class FailingAuditEventPublisher:
    events: list[object] = []

    def publish(self, event: object) -> None:
        raise RuntimeError("audit unavailable")
