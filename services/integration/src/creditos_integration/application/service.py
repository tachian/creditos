from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from time import perf_counter
from typing import Any

from creditos_observability.context import ObservabilityContext
from creditos_observability.logging import build_structured_log

from creditos_integration.application.ports.adapter_registry import AdapterRegistry
from creditos_integration.application.ports.audit_event_publisher import (
    AuditEventPublisher,
    IntegrationAuditEvent,
)
from creditos_integration.application.ports.catalog_repository import IntegrationCatalogRepository
from creditos_integration.domain.entities import (
    IntegrationConfiguration,
    IntegrationPlan,
    IntegrationPlanItem,
)
from creditos_integration.domain.errors import IntegrationValidationError
from creditos_integration.domain.value_objects.catalog import (
    IntegrationPlanStatus,
    parse_integration_class,
    parse_product_type,
)

SERVICE_NAME = "integration"
SERVICE_VERSION = "0.1.0"
CONTRACT = "integration-catalog-application"
CONTRACT_VERSION = "v1"


@dataclass(frozen=True, slots=True)
class ConfigureIntegrationClassCommand:
    product_type: str
    integration_class: str
    adapter_id: str
    requirement: str
    timeout_ms: int
    max_attempts: int
    max_concurrency: int
    estimated_cost_units: int
    fallback_strategy: str
    enabled: bool = True
    scopes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class BuildIntegrationPlanCommand:
    product_type: str
    required_classes: tuple[str, ...] = ()
    optional_classes: tuple[str, ...] = ()
    conditional_classes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ListIntegrationConfigurationsQuery:
    product_type: str


class IntegrationCatalogApplicationService:
    def __init__(
        self,
        *,
        repository: IntegrationCatalogRepository,
        adapter_registry: AdapterRegistry,
        audit_publisher: AuditEventPublisher,
        environment: str,
        clock: Callable[[], datetime] | None = None,
        configuration_id_factory: Callable[[str], str] | None = None,
    ) -> None:
        self._repository = repository
        self._adapter_registry = adapter_registry
        self._audit_publisher = audit_publisher
        self._environment = environment
        self._clock = clock or (lambda: datetime.now(UTC))
        self._configuration_id_factory = configuration_id_factory or _default_configuration_id
        self._logged_events: list[dict[str, Any]] = []

    @property
    def logged_events(self) -> list[dict[str, Any]]:
        return list(self._logged_events)

    def configure_integration_class(
        self,
        command: ConfigureIntegrationClassCommand,
        *,
        context: ObservabilityContext,
    ) -> IntegrationConfiguration:
        started_at = perf_counter()
        tenant_id = context.tenant_id
        try:
            tenant_id = _require_trusted_tenant(context)
            _require_scope(command.scopes, "integration_catalog:write")
            product_type = parse_product_type(command.product_type)
            integration_class = parse_integration_class(command.integration_class)
            if not self._adapter_registry.is_adapter_allowed(integration_class, command.adapter_id):
                raise IntegrationValidationError(
                    "adapter não registrado para a classe de integração",
                    code="adapter_not_registered",
                    field_path="adapter_id",
                )
            configuration_id = self._configuration_id_factory(
                _configuration_seed(
                    tenant_id,
                    product_type,
                    integration_class,
                )
            )
            previous_configuration = self._repository.get(configuration_id, tenant_id)
            configuration = IntegrationConfiguration.create(
                configuration_id=configuration_id,
                tenant_id=tenant_id,
                product_type=product_type,
                integration_class=integration_class,
                adapter_id=command.adapter_id,
                requirement=command.requirement,
                timeout_ms=command.timeout_ms,
                max_attempts=command.max_attempts,
                max_concurrency=command.max_concurrency,
                estimated_cost_units=command.estimated_cost_units,
                fallback_strategy=command.fallback_strategy,
                enabled=command.enabled,
                now=self._clock(),
                created_at=previous_configuration.created_at
                if previous_configuration is not None
                else None,
            )
            operation = (
                "integration_catalog.update_configuration"
                if previous_configuration is not None
                else "integration_catalog.create_configuration"
            )
            self._repository.save(configuration)
            try:
                self._audit_publisher.publish(
                    IntegrationAuditEvent(
                        tenant_id=tenant_id,
                        operation=operation,
                        product_type=configuration.product_type,
                        integration_class=configuration.integration_class,
                        adapter_id=configuration.adapter_id,
                        result="accepted",
                        correlation_id=context.correlation_id,
                        trace_id=context.trace_id,
                        schema_version=configuration.schema_version,
                        occurred_at=configuration.updated_at,
                    )
                )
            except Exception:
                if previous_configuration is None:
                    self._repository.delete(configuration.configuration_id, tenant_id)
                else:
                    self._repository.save(previous_configuration)
                raise
            self._log_operation(
                context=context,
                operation=operation,
                status="accepted",
                duration_ms=_duration_ms(started_at),
                payload=command,
                extra=_configuration_log_extra(configuration),
            )
            return configuration
        except Exception as error:
            self._log_operation(
                context=context,
                operation="integration_catalog.configure",
                status="rejected",
                duration_ms=_duration_ms(started_at),
                payload=command,
                error_type=type(error).__name__,
                extra={
                    "tenant_id_present": _tenant_id_present(tenant_id),
                    "denial_reason": getattr(error, "code", type(error).__name__),
                },
            )
            raise

    def build_integration_plan(
        self,
        command: BuildIntegrationPlanCommand,
        *,
        context: ObservabilityContext,
    ) -> IntegrationPlan:
        started_at = perf_counter()
        tenant_id = context.tenant_id
        try:
            tenant_id = _require_trusted_tenant(context)
            product_type = parse_product_type(command.product_type)
            required_classes = _parse_classes(command.required_classes)
            optional_classes = _parse_classes(command.optional_classes)
            conditional_classes = _parse_classes(command.conditional_classes)
            requested_classes = required_classes | optional_classes | conditional_classes
            configurations = self._repository.list_for_tenant_product(
                tenant_id=tenant_id,
                product_type=product_type,
            )
            configurations_by_class = {
                configuration.integration_class: configuration for configuration in configurations
            }
            if not requested_classes and not configurations:
                plan = IntegrationPlan(
                    tenant_id=tenant_id,
                    product_type=product_type,
                    status=IntegrationPlanStatus.NO_APPLICABLE_INTEGRATIONS.value,
                    items=(),
                )
            else:
                invalid_configuration_classes = _invalid_configuration_classes(
                    configurations=configurations,
                    required_classes=required_classes,
                    adapter_registry=self._adapter_registry,
                )
                if invalid_configuration_classes:
                    plan = IntegrationPlan(
                        tenant_id=tenant_id,
                        product_type=product_type,
                        status=IntegrationPlanStatus.INVALID_CONFIGURATION.value,
                        items=(),
                        invalid_configuration_classes=invalid_configuration_classes,
                    )
                    self._log_operation(
                        context=context,
                        operation="integration_catalog.build_plan",
                        status="accepted",
                        duration_ms=_duration_ms(started_at),
                        payload=command,
                        extra=_plan_log_extra(product_type=product_type, plan=plan),
                    )
                    return plan
                missing_required = tuple(
                    sorted(
                        integration_class
                        for integration_class in required_classes
                        if integration_class not in configurations_by_class
                    )
                )
                if missing_required:
                    plan = IntegrationPlan(
                        tenant_id=tenant_id,
                        product_type=product_type,
                        status=IntegrationPlanStatus.MISSING_REQUIRED_CONFIGURATION.value,
                        items=(),
                        missing_required_classes=missing_required,
                    )
                else:
                    selected_classes = requested_classes or set(configurations_by_class)
                    items = tuple(
                        IntegrationPlanItem.from_configuration(
                            configurations_by_class[integration_class]
                        )
                        for integration_class in sorted(selected_classes)
                        if integration_class in configurations_by_class
                    )
                    plan_status = (
                        IntegrationPlanStatus.READY.value
                        if items
                        else IntegrationPlanStatus.NO_APPLICABLE_INTEGRATIONS.value
                    )
                    plan = IntegrationPlan(
                        tenant_id=tenant_id,
                        product_type=product_type,
                        status=plan_status,
                        items=items,
                    )
            self._log_operation(
                context=context,
                operation="integration_catalog.build_plan",
                status="accepted",
                duration_ms=_duration_ms(started_at),
                payload=command,
                extra=_plan_log_extra(product_type=product_type, plan=plan),
            )
            return plan
        except Exception as error:
            self._log_operation(
                context=context,
                operation="integration_catalog.build_plan",
                status="rejected",
                duration_ms=_duration_ms(started_at),
                payload=command,
                error_type=type(error).__name__,
                extra={
                    "tenant_id_present": _tenant_id_present(tenant_id),
                    "denial_reason": getattr(error, "code", type(error).__name__),
                },
            )
            raise

    def list_integration_configurations(
        self,
        query: ListIntegrationConfigurationsQuery,
        *,
        context: ObservabilityContext,
    ) -> tuple[IntegrationConfiguration, ...]:
        started_at = perf_counter()
        tenant_id = context.tenant_id
        try:
            tenant_id = _require_trusted_tenant(context)
            product_type = parse_product_type(query.product_type)
            configurations = self._repository.list_for_tenant_product(
                tenant_id=tenant_id,
                product_type=product_type,
            )
            self._log_operation(
                context=context,
                operation="integration_catalog.list_configurations",
                status="accepted",
                duration_ms=_duration_ms(started_at),
                payload=query,
                extra={
                    "product_type": product_type,
                    "configured_items": len(configurations),
                    "integration_classes": tuple(
                        configuration.integration_class for configuration in configurations
                    ),
                },
            )
            return configurations
        except Exception as error:
            self._log_operation(
                context=context,
                operation="integration_catalog.list_configurations",
                status="rejected",
                duration_ms=_duration_ms(started_at),
                payload=query,
                error_type=type(error).__name__,
                extra={
                    "tenant_id_present": _tenant_id_present(tenant_id),
                    "denial_reason": getattr(error, "code", type(error).__name__),
                },
            )
            raise

    def _log_operation(
        self,
        *,
        context: ObservabilityContext,
        operation: str,
        status: str,
        duration_ms: float,
        extra: dict[str, Any],
        payload: Any,
        error_type: str | None = None,
    ) -> None:
        self._logged_events.append(
            build_structured_log(
                context=context,
                service_name=SERVICE_NAME,
                service_version=SERVICE_VERSION,
                environment=self._environment,
                operation=operation,
                source="integration-catalog-command",
                destination=SERVICE_NAME,
                contract=CONTRACT,
                contract_version=CONTRACT_VERSION,
                status=status,
                duration_ms=duration_ms,
                payload=payload,
                extra=extra,
                error_type=error_type,
            )
        )


def _configuration_log_extra(configuration: IntegrationConfiguration) -> dict[str, object]:
    return {
        "configuration_id": configuration.configuration_id,
        "product_type": configuration.product_type,
        "integration_class": configuration.integration_class,
        "adapter_id": configuration.adapter_id,
        "requirement": configuration.requirement,
        "fallback_strategy": configuration.fallback_strategy,
        "timeout_ms": configuration.timeout_ms,
        "max_attempts": configuration.max_attempts,
        "max_concurrency": configuration.max_concurrency,
        "estimated_cost_units": configuration.estimated_cost_units,
    }


def _tenant_id_present(tenant_id: str | None) -> bool:
    return bool(tenant_id and tenant_id.strip())


def _plan_log_extra(*, product_type: str, plan: IntegrationPlan) -> dict[str, object]:
    return {
        "product_type": product_type,
        "plan_status": plan.status,
        "configured_items": len(plan.items),
        "missing_required_classes": plan.missing_required_classes,
        "invalid_configuration_classes": plan.invalid_configuration_classes,
        "integration_classes": tuple(item.integration_class for item in plan.items),
        "adapter_ids": tuple(item.adapter_id for item in plan.items),
    }


def _require_trusted_tenant(context: ObservabilityContext) -> str:
    if not context.tenant_id or not context.tenant_id.strip():
        raise IntegrationValidationError(
            "tenant confiável ausente",
            code="missing_trusted_tenant",
            field_path="context.tenant_id",
        )
    tenant_id = context.tenant_id.strip()
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.:-]{2,120}", tenant_id):
        raise IntegrationValidationError(
            "tenant confiável inválido",
            code="invalid_trusted_tenant",
            field_path="context.tenant_id",
        )
    if not context.tenant_isolation_tier:
        raise IntegrationValidationError(
            "tier de isolamento do tenant ausente",
            code="missing_tenant_isolation_tier",
            field_path="context.tenant_isolation_tier",
        )
    if context.tenant_isolation_tier != "bridge":
        raise IntegrationValidationError(
            "tier de isolamento do tenant não suportado nesta story",
            code="unsupported_tenant_isolation_tier",
            field_path="context.tenant_isolation_tier",
        )
    return tenant_id


def _require_scope(scopes: tuple[str, ...], required_scope: str) -> None:
    if required_scope not in set(scopes):
        raise IntegrationValidationError(
            "escopo insuficiente para configurar catálogo de integrações",
            code="insufficient_scope",
            field_path="scopes",
        )


def _parse_classes(values: tuple[str, ...]) -> set[str]:
    return {parse_integration_class(value) for value in values}


def _invalid_configuration_classes(
    *,
    configurations: tuple[IntegrationConfiguration, ...],
    required_classes: set[str],
    adapter_registry: AdapterRegistry,
) -> tuple[str, ...]:
    invalid_classes: set[str] = set()
    seen_classes: set[str] = set()
    for configuration in configurations:
        if configuration.integration_class in seen_classes:
            invalid_classes.add(configuration.integration_class)
        seen_classes.add(configuration.integration_class)
        if not adapter_registry.is_adapter_allowed(
            configuration.integration_class,
            configuration.adapter_id,
        ):
            invalid_classes.add(configuration.integration_class)
        if configuration.integration_class in required_classes and (
            configuration.requirement != "required"
            or configuration.fallback_strategy == "skip_optional"
        ):
            invalid_classes.add(configuration.integration_class)
    return tuple(sorted(invalid_classes))


def _configuration_seed(
    tenant_id: str,
    product_type: str,
    integration_class: str,
) -> str:
    return ":".join((tenant_id, product_type, integration_class))


def _default_configuration_id(seed: str) -> str:
    return f"icfg_{sha256(seed.encode('utf-8')).hexdigest()[:32]}"


def _duration_ms(started_at: float) -> float:
    return round((perf_counter() - started_at) * 1000, 3)
