from __future__ import annotations

import re
from collections.abc import Callable, Mapping
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
from creditos_integration.application.ports.mock_integration_adapter import (
    MockIntegrationAdapter,
    MockIntegrationAdapterRegistry,
)
from creditos_integration.domain.entities import (
    IntegrationConfiguration,
    IntegrationPlan,
    IntegrationPlanItem,
    IntegrationResult,
)
from creditos_integration.domain.errors import IntegrationValidationError
from creditos_integration.domain.value_objects.catalog import (
    IntegrationPlanStatus,
    parse_integration_class,
    parse_product_type,
)
from creditos_integration.domain.value_objects.result import (
    MockIntegrationScenario,
    parse_mock_scenario,
    validate_supported_mock_integration_class,
    validate_synthetic_subject_reference,
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


@dataclass(frozen=True, slots=True)
class ExecuteMockIntegrationCommand:
    plan: IntegrationPlan
    scenario_by_class: Mapping[str, str] | None = None
    synthetic_subject_reference: str = "synthetic-subject"
    scopes: tuple[str, ...] = ()


class IntegrationCatalogApplicationService:
    def __init__(
        self,
        *,
        repository: IntegrationCatalogRepository,
        adapter_registry: AdapterRegistry,
        audit_publisher: AuditEventPublisher,
        environment: str,
        mock_adapter_registry: MockIntegrationAdapterRegistry | None = None,
        clock: Callable[[], datetime] | None = None,
        configuration_id_factory: Callable[[str], str] | None = None,
    ) -> None:
        self._repository = repository
        self._adapter_registry = adapter_registry
        self._audit_publisher = audit_publisher
        self._environment = environment
        self._mock_adapter_registry = mock_adapter_registry
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
            from creditos_integration.domain.value_objects.catalog import validate_adapter_id

            adapter_id = validate_adapter_id(command.adapter_id)
            if not self._adapter_registry.is_adapter_allowed(integration_class, adapter_id):
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

    def execute_mock_integration_plan(
        self,
        command: ExecuteMockIntegrationCommand,
        *,
        context: ObservabilityContext,
    ) -> tuple[IntegrationResult, ...]:
        started_at = perf_counter()
        tenant_id = context.tenant_id
        try:
            _require_non_production_environment(self._environment)
            tenant_id = _require_trusted_tenant(context)
            _require_scope(command.scopes, "integration_mock:execute")
            if command.plan.tenant_id != tenant_id:
                raise IntegrationValidationError(
                    "plano de integração pertence a outro tenant",
                    code="cross_tenant_integration_plan",
                    field_path="plan.tenant_id",
                )
            if command.plan.status != IntegrationPlanStatus.READY.value:
                raise IntegrationValidationError(
                    "plano de integração não está pronto para execução mock",
                    code="integration_plan_not_ready",
                    field_path="plan.status",
                )
            if not command.plan.items:
                raise IntegrationValidationError(
                    "plano de integração não possui itens executáveis",
                    code="empty_integration_plan",
                    field_path="plan.items",
                )
            if self._mock_adapter_registry is None:
                raise IntegrationValidationError(
                    "registry de adapters mock/sandbox não configurado",
                    code="mock_adapter_registry_not_configured",
                    field_path="mock_adapter_registry",
                )

            scenario_by_class = command.scenario_by_class or {}
            synthetic_subject_reference = validate_synthetic_subject_reference(
                command.synthetic_subject_reference
            )
            execution_items = _preflight_mock_execution(
                plan=command.plan,
                tenant_id=tenant_id,
                scenario_by_class=scenario_by_class,
                registry=self._mock_adapter_registry,
            )
            results: list[IntegrationResult] = []
            for item, scenario, adapter in execution_items:
                result_started_at = self._clock()
                result_perf_started_at = perf_counter()
                raw_result = adapter.execute(
                    item,
                    scenario=scenario,
                    synthetic_subject_reference=synthetic_subject_reference,
                    context=context,
                    started_at=result_started_at,
                    completed_at=result_started_at,
                    duration_ms=0.0,
                )
                result = _finalize_mock_result(
                    result=raw_result,
                    completed_at=self._clock(),
                    duration_ms=_duration_ms(result_perf_started_at),
                )
                _validate_mock_result(
                    result=result,
                    item=item,
                    tenant_id=tenant_id,
                    scenario=scenario,
                )
                results.append(result)

            self._log_operation(
                context=context,
                operation="integration_mock.execute_plan",
                status="accepted",
                duration_ms=_duration_ms(started_at),
                payload=command,
                extra=_mock_execution_log_extra(
                    product_type=command.plan.product_type,
                    results=tuple(results),
                ),
            )
            return tuple(results)
        except Exception as error:
            self._log_operation(
                context=context,
                operation="integration_mock.execute_plan",
                status="rejected",
                duration_ms=_duration_ms(started_at),
                payload=command,
                error_type=type(error).__name__,
                extra=_mock_rejection_log_extra(
                    command=command,
                    tenant_id_present=_tenant_id_present(tenant_id),
                    denial_reason=getattr(error, "code", type(error).__name__),
                ),
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
        from dataclasses import replace

        safe_context = context
        if context.tenant_id or context.tenant_isolation_tier:
            candidate_tenant = (context.tenant_id or "").strip()
            if (
                candidate_tenant
                and re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.:-]{2,120}", candidate_tenant)
                and context.tenant_isolation_tier == "bridge"
            ):
                safe_context = replace(context, tenant_id=candidate_tenant)
            else:
                safe_context = replace(context, tenant_id=None, tenant_isolation_tier=None)

        self._logged_events.append(
            build_structured_log(
                context=safe_context,
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


def _mock_execution_log_extra(
    *,
    product_type: str,
    results: tuple[IntegrationResult, ...],
) -> dict[str, object]:
    return {
        "product_type": product_type,
        "result_count": len(results),
        "integration_classes": tuple(result.integration_class for result in results),
        "adapter_ids": tuple(result.adapter_id for result in results),
        "result_statuses": tuple(result.status for result in results),
        "scenarios": tuple(result.scenario for result in results),
        "result_schema_versions": tuple(result.schema_version for result in results),
    }


def _mock_rejection_log_extra(
    *,
    command: ExecuteMockIntegrationCommand,
    tenant_id_present: bool,
    denial_reason: str,
) -> dict[str, object]:
    plan = command.plan
    plan_items = getattr(plan, "items", ())
    scenario_by_class = command.scenario_by_class or {}
    item_classes = tuple(getattr(item, "integration_class", "") for item in plan_items)
    return {
        "tenant_id_present": tenant_id_present,
        "product_type": getattr(plan, "product_type", ""),
        "plan_status": getattr(plan, "status", ""),
        "configured_items": len(plan_items),
        "integration_classes": item_classes,
        "adapter_ids": tuple(getattr(item, "adapter_id", "") for item in plan_items),
        "scenarios": tuple(
            scenario_by_class.get(
                integration_class,
                MockIntegrationScenario.SYNTHETIC_SUCCESS.value,
            )
            for integration_class in item_classes
        ),
        "denial_reason": denial_reason,
    }


def _preflight_mock_execution(
    *,
    plan: IntegrationPlan,
    tenant_id: str,
    scenario_by_class: Mapping[str, str],
    registry: MockIntegrationAdapterRegistry,
) -> tuple[tuple[IntegrationPlanItem, str, MockIntegrationAdapter], ...]:
    item_classes = {item.integration_class for item in plan.items}
    unknown_scenario_classes = tuple(sorted(set(scenario_by_class) - item_classes))
    if unknown_scenario_classes:
        raise IntegrationValidationError(
            "cenário mock informado para classe fora do plano",
            code="unknown_mock_scenario_class",
            field_path="scenario_by_class",
            details={"integration_classes": unknown_scenario_classes},
        )

    execution_items: list[tuple[IntegrationPlanItem, str, MockIntegrationAdapter]] = []
    for index, item in enumerate(plan.items):
        if item.tenant_id != tenant_id:
            raise IntegrationValidationError(
                "item do plano pertence a outro tenant",
                code="cross_tenant_integration_plan_item",
                field_path=f"plan.items[{index}].tenant_id",
            )
        if item.product_type != plan.product_type:
            raise IntegrationValidationError(
                "item do plano pertence a outro produto",
                code="cross_product_integration_plan_item",
                field_path=f"plan.items[{index}].product_type",
            )
        validate_supported_mock_integration_class(item.integration_class)
        scenario = parse_mock_scenario(
            scenario_by_class.get(
                item.integration_class,
                MockIntegrationScenario.SYNTHETIC_SUCCESS.value,
            )
        )
        adapter = registry.get_adapter(item.integration_class, item.adapter_id)
        if adapter is None:
            raise IntegrationValidationError(
                "adapter mock/sandbox não registrado para execução",
                code="mock_adapter_not_registered",
                field_path=f"plan.items[{index}].adapter_id",
            )
    for item in plan.items:
        scenario = parse_mock_scenario(
            scenario_by_class.get(
                item.integration_class,
                MockIntegrationScenario.SYNTHETIC_SUCCESS.value,
            )
        )
        adapter = registry.get_adapter(item.integration_class, item.adapter_id)
        if adapter is not None:
            execution_items.append((item, scenario, adapter))
    return tuple(execution_items)


def _finalize_mock_result(
    *,
    result: IntegrationResult,
    completed_at: datetime,
    duration_ms: float,
) -> IntegrationResult:
    return IntegrationResult.create(
        result_id=result.result_id,
        tenant_id=result.tenant_id,
        product_type=result.product_type,
        integration_class=result.integration_class,
        adapter_id=result.adapter_id,
        status=result.status,
        scenario=result.scenario,
        schema_version=result.schema_version,
        reason_codes=result.reason_codes,
        summary=result.summary,
        correlation_id=result.correlation_id,
        trace_id=result.trace_id,
        started_at=result.started_at,
        completed_at=completed_at,
        duration_ms=duration_ms,
    )


def _validate_mock_result(
    *,
    result: IntegrationResult,
    item: IntegrationPlanItem,
    tenant_id: str,
    scenario: str,
) -> None:
    if result.tenant_id != tenant_id:
        raise IntegrationValidationError(
            "resultado mock/sandbox pertence a outro tenant",
            code="mock_result_tenant_mismatch",
            field_path="result.tenant_id",
        )
    if result.product_type != item.product_type:
        raise IntegrationValidationError(
            "resultado mock/sandbox pertence a outro produto",
            code="mock_result_product_mismatch",
            field_path="result.product_type",
        )
    if result.integration_class != item.integration_class:
        raise IntegrationValidationError(
            "resultado mock/sandbox pertence a outra classe",
            code="mock_result_class_mismatch",
            field_path="result.integration_class",
        )
    if result.adapter_id != item.adapter_id:
        raise IntegrationValidationError(
            "resultado mock/sandbox pertence a outro adapter",
            code="mock_result_adapter_mismatch",
            field_path="result.adapter_id",
        )
    if result.scenario != scenario:
        raise IntegrationValidationError(
            "resultado mock/sandbox pertence a outro cenário",
            code="mock_result_scenario_mismatch",
            field_path="result.scenario",
        )
    if result.schema_version != "1.0":
        raise IntegrationValidationError(
            "schema de resultado mock/sandbox não suportado",
            code="unsupported_mock_result_schema_version",
            field_path="result.schema_version",
        )


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
    if required_scope not in scopes:
        raise IntegrationValidationError(
            "escopo insuficiente para operação de integração",
            code="insufficient_scope",
            field_path="scopes",
        )


def _parse_classes(values: tuple[str, ...]) -> set[str]:
    return {parse_integration_class(value) for value in values}


def _require_non_production_environment(environment: str) -> None:
    normalized_environment = environment.strip().lower()
    allowed_non_production = {
        "ci",
        "dev",
        "development",
        "homolog",
        "homologation",
        "hml",
        "local",
        "qa",
        "sandbox",
        "stage",
        "staging",
        "test",
        "testing",
    }
    if normalized_environment in allowed_non_production:
        return
    if normalized_environment.startswith(
        (
            "ci-",
            "dev-",
            "development-",
            "homolog-",
            "hml-",
            "local-",
            "qa-",
            "sandbox-",
            "stage-",
            "staging-",
            "test-",
            "testing-",
        )
    ):
        return
    if normalized_environment in {"prod", "production", "prd"} or normalized_environment.startswith(
        ("prod-", "production-", "prd-")
    ):
        raise IntegrationValidationError(
            "execução mock/sandbox não permitida em ambiente produtivo",
            code="mock_execution_not_allowed_in_production",
            field_path="environment",
        )
    raise IntegrationValidationError(
        "execução mock/sandbox permitida apenas em ambiente não produtivo conhecido",
        code="unknown_mock_execution_environment",
        field_path="environment",
    )


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
