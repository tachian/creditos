from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from json import dumps
from time import perf_counter
from types import MappingProxyType
from typing import Any

from creditos_observability.context import ObservabilityContext
from creditos_observability.logging import build_structured_log

from creditos_integration.application.ports.adapter_registry import AdapterRegistry
from creditos_integration.application.ports.audit_event_publisher import (
    AuditEventPublisher,
    IntegrationAuditEvent,
)
from creditos_integration.application.ports.catalog_repository import IntegrationCatalogRepository
from creditos_integration.application.ports.integration_execution import (
    IntegrationDlqStore,
    IntegrationExecutionDispatcher,
    IntegrationExecutionEvent,
    IntegrationExecutionJobRequest,
    IntegrationExecutionResultPublisher,
    IntegrationExecutionRetrySchedule,
    IntegrationExecutionStore,
)
from creditos_integration.application.ports.mock_integration_adapter import (
    MockIntegrationAdapter,
    MockIntegrationAdapterRegistry,
)
from creditos_integration.domain.entities import (
    IntegrationConfiguration,
    IntegrationExecution,
    IntegrationExecutionCostRecord,
    IntegrationExecutionDlqRecord,
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
from creditos_integration.domain.value_objects.execution import (
    IntegrationExecutionStatus,
    validate_dlq_id,
    validate_failure_code,
    validate_idempotency_key,
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
    provider_id: str | None = None
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


@dataclass(frozen=True, slots=True)
class StartIntegrationExecutionCommand:
    plan: IntegrationPlan
    idempotency_key: str
    scenario_by_class: Mapping[str, str] | None = None
    synthetic_subject_reference: str = "synthetic-subject"
    scopes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ReprocessIntegrationDlqCommand:
    dlq_id: str
    idempotency_key: str
    reason_code: str = "operator_requested"
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
        integration_execution_store: IntegrationExecutionStore | None = None,
        integration_dlq_store: IntegrationDlqStore | None = None,
        integration_execution_dispatcher: IntegrationExecutionDispatcher | None = None,
        integration_execution_result_publisher: IntegrationExecutionResultPublisher | None = None,
        execution_id_factory: Callable[[str], str] | None = None,
        job_id_factory: Callable[[str], str] | None = None,
    ) -> None:
        self._repository = repository
        self._adapter_registry = adapter_registry
        self._audit_publisher = audit_publisher
        self._environment = environment
        self._mock_adapter_registry = mock_adapter_registry
        self._integration_execution_store = integration_execution_store
        self._integration_dlq_store = integration_dlq_store
        self._integration_execution_dispatcher = integration_execution_dispatcher
        self._integration_execution_result_publisher = integration_execution_result_publisher
        self._clock = clock or (lambda: datetime.now(UTC))
        self._configuration_id_factory = configuration_id_factory or _default_configuration_id
        self._execution_id_factory = execution_id_factory or _default_execution_id
        self._job_id_factory = job_id_factory or _default_job_id
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
                provider_id=command.provider_id,
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

    def start_integration_execution(
        self,
        command: StartIntegrationExecutionCommand,
        *,
        context: ObservabilityContext,
    ) -> IntegrationExecution:
        started_at = perf_counter()
        tenant_id = context.tenant_id
        idempotency_key = ""
        plan_fingerprint = ""
        reservation_acquired = False
        try:
            _require_non_production_environment(self._environment)
            tenant_id = _require_trusted_tenant(context)
            _require_scope(command.scopes, "integration_execution:start")
            idempotency_key = validate_idempotency_key(command.idempotency_key)
            synthetic_subject_reference = validate_synthetic_subject_reference(
                command.synthetic_subject_reference
            )
            _validate_execution_plan(command.plan, tenant_id=tenant_id)
            scenario_by_class = command.scenario_by_class or {}
            _validate_scenario_classes(plan=command.plan, scenario_by_class=scenario_by_class)
            normalized_scenario_by_class = _normalized_scenario_by_class(
                plan=command.plan,
                scenario_by_class=scenario_by_class,
            )
            plan_fingerprint = _integration_plan_fingerprint(
                plan=command.plan,
                scenario_by_class=normalized_scenario_by_class,
                synthetic_subject_reference=synthetic_subject_reference,
            )
            if self._integration_execution_store is None:
                raise IntegrationValidationError(
                    "store de execução de integração não configurado",
                    code="integration_execution_store_not_configured",
                    field_path="integration_execution_store",
                )
            if self._integration_dlq_store is None:
                raise IntegrationValidationError(
                    "store de DLQ de integração não configurado",
                    code="integration_dlq_store_not_configured",
                    field_path="integration_dlq_store",
                )
            existing_execution = self._integration_execution_store.reserve_or_get(
                tenant_id=tenant_id,
                idempotency_key=idempotency_key,
                plan_fingerprint=plan_fingerprint,
            )
            if existing_execution is not None:
                _publish_pending_integration_execution_events(
                    store=self._integration_execution_store,
                    publisher=self._integration_execution_result_publisher,
                    tenant_id=tenant_id,
                    idempotency_key=idempotency_key,
                )
                self._log_operation(
                    context=context,
                    operation="integration_execution.idempotency_hit",
                    status="accepted",
                    duration_ms=_duration_ms(started_at),
                    payload=command,
                    extra=_execution_log_extra(existing_execution) | {"idempotency_hit": True},
                )
                return existing_execution
            reservation_acquired = True

            if self._integration_execution_dispatcher is None:
                raise IntegrationValidationError(
                    "dispatcher de execução de integração não configurado",
                    code="integration_execution_dispatcher_not_configured",
                    field_path="integration_execution_dispatcher",
                )
            if self._mock_adapter_registry is None:
                raise IntegrationValidationError(
                    "registry de adapters mock/sandbox não configurado",
                    code="mock_adapter_registry_not_configured",
                    field_path="mock_adapter_registry",
                )
            execution_id = self._execution_id_factory(
                "|".join((tenant_id, idempotency_key, plan_fingerprint))
            )
            execution_started_at = self._clock()
            execution_items = _preflight_mock_execution(
                plan=command.plan,
                tenant_id=tenant_id,
                scenario_by_class=normalized_scenario_by_class,
                registry=self._mock_adapter_registry,
            )
            job_requests = tuple(
                IntegrationExecutionJobRequest(
                    job_id=self._job_id_factory(
                        "|".join(
                            (
                                execution_id,
                                str(index),
                                item.integration_class,
                                item.adapter_id,
                                scenario,
                            )
                        )
                    ),
                    item=item,
                    scenario=scenario,
                    adapter=adapter,
                )
                for index, (item, scenario, adapter) in enumerate(execution_items)
            )
            self._log_operation(
                context=context,
                operation="integration_execution.start",
                status="accepted",
                duration_ms=_duration_ms(started_at),
                payload=command,
                extra={
                    "execution_id": execution_id,
                    "product_type": command.plan.product_type,
                    "plan_status": command.plan.status,
                    "job_count": len(job_requests),
                    "schema_version": "1.0",
                },
            )
            for job_request in job_requests:
                self._log_operation(
                    context=context,
                    operation="integration_execution.job_dispatched",
                    status="accepted",
                    duration_ms=0.0,
                    payload=command,
                    extra={
                        "execution_id": execution_id,
                        "job_id": job_request.job_id,
                        "product_type": job_request.item.product_type,
                        "integration_class": job_request.item.integration_class,
                        "adapter_id": job_request.item.adapter_id,
                        "timeout_ms": job_request.item.timeout_ms,
                        "max_attempts": job_request.item.max_attempts,
                        "max_concurrency": job_request.item.max_concurrency,
                        "schema_version": "1.0",
                    },
                )

            dispatch_result = self._integration_execution_dispatcher.dispatch(
                execution_id=execution_id,
                job_requests=job_requests,
                synthetic_subject_reference=synthetic_subject_reference,
                context=context,
                clock=self._clock,
            )
            for retry_schedule in dispatch_result.retry_schedules:
                self._log_operation(
                    context=context,
                    operation="integration_execution.retry_scheduled",
                    status="accepted",
                    duration_ms=0.0,
                    payload=command,
                    extra=retry_schedule.to_log_safe_dict(),
                )
            for dlq_record in dispatch_result.dlq_records:
                self._log_operation(
                    context=context,
                    operation="integration_execution.dlq_recorded",
                    status="accepted",
                    duration_ms=0.0,
                    payload=command,
                    extra=dlq_record.to_log_safe_dict(),
                )
            execution = IntegrationExecution.create(
                execution_id=execution_id,
                tenant_id=tenant_id,
                product_type=command.plan.product_type,
                plan_fingerprint=plan_fingerprint,
                idempotency_key=idempotency_key,
                jobs=dispatch_result.jobs,
                results=dispatch_result.results,
                correlation_id=context.correlation_id,
                trace_id=context.trace_id,
                started_at=execution_started_at,
                completed_at=self._clock(),
                duration_ms=_duration_ms(started_at),
            )
            cost_records = _validate_cost_records(
                execution=execution,
                cost_records=dispatch_result.cost_records,
            )
            self._integration_execution_store.save(execution)
            self._log_operation(
                context=context,
                operation="integration_execution.cost_recorded",
                status="accepted",
                duration_ms=0.0,
                payload=command,
                extra=_cost_projection_log_extra(
                    execution=execution,
                    cost_records=cost_records,
                ),
            )
            if self._integration_execution_result_publisher is not None:
                _publish_integration_execution_events(
                    store=self._integration_execution_store,
                    publisher=self._integration_execution_result_publisher,
                    tenant_id=tenant_id,
                    idempotency_key=idempotency_key,
                    events=_integration_execution_events(
                        execution,
                        context=context,
                        cost_records=cost_records,
                        retry_schedules=dispatch_result.retry_schedules,
                        dlq_records=dispatch_result.dlq_records,
                    ),
                )
            self._log_operation(
                context=context,
                operation="integration_execution.fan_in",
                status="accepted",
                duration_ms=execution.duration_ms,
                payload=command,
                extra=_execution_log_extra(execution)
                | {
                    "max_observed_concurrency": dispatch_result.max_observed_concurrency,
                    "idempotency_hit": False,
                },
            )
            return execution
        except Exception as error:
            if reservation_acquired and self._integration_execution_store is not None:
                self._integration_execution_store.release_reservation(
                    tenant_id=tenant_id or "",
                    idempotency_key=idempotency_key,
                    plan_fingerprint=plan_fingerprint,
                )
            self._log_operation(
                context=context,
                operation="integration_execution.start",
                status="rejected",
                duration_ms=_duration_ms(started_at),
                payload=command,
                error_type=type(error).__name__,
                extra=_execution_rejection_log_extra(
                    command=command,
                    tenant_id_present=_tenant_id_present(tenant_id),
                    denial_reason=getattr(error, "code", type(error).__name__),
                ),
            )
            raise

    def reprocess_integration_dlq(
        self,
        command: ReprocessIntegrationDlqCommand,
        *,
        context: ObservabilityContext,
    ) -> IntegrationExecutionDlqRecord:
        started_at = perf_counter()
        tenant_id = context.tenant_id
        dlq_id = ""
        idempotency_key = ""
        plan_fingerprint = ""
        reservation_acquired = False
        record: IntegrationExecutionDlqRecord | None = None
        reprocess_execution_id: str | None = None
        try:
            _require_non_production_environment(self._environment)
            tenant_id = _require_trusted_tenant(context)
            _require_scope(command.scopes, "integration_execution:reprocess")
            dlq_id = validate_dlq_id(command.dlq_id)
            idempotency_key = validate_idempotency_key(command.idempotency_key)
            reason_code = validate_failure_code(command.reason_code)
            if self._integration_dlq_store is None:
                raise IntegrationValidationError(
                    "store de DLQ de integração não configurado",
                    code="integration_dlq_store_not_configured",
                    field_path="integration_dlq_store",
                )
            if self._integration_execution_store is None:
                raise IntegrationValidationError(
                    "store de execução de integração não configurado",
                    code="integration_execution_store_not_configured",
                    field_path="integration_execution_store",
                )
            if self._mock_adapter_registry is None:
                raise IntegrationValidationError(
                    "registry de adapters mock/sandbox não configurado",
                    code="mock_adapter_registry_not_configured",
                    field_path="mock_adapter_registry",
                )
            if self._integration_execution_dispatcher is None:
                raise IntegrationValidationError(
                    "dispatcher de execução de integração não configurado",
                    code="integration_execution_dispatcher_not_configured",
                    field_path="integration_execution_dispatcher",
                )
            record = self._integration_dlq_store.get(tenant_id=tenant_id, dlq_id=dlq_id)
            if record is None:
                raise IntegrationValidationError(
                    "registro de DLQ não encontrado",
                    code="integration_dlq_record_not_found",
                    field_path="dlq_id",
                )
            if not record.is_retryable_failure:
                raise IntegrationValidationError(
                    "registro de DLQ não elegível para reprocessamento automático",
                    code="integration_dlq_record_not_retryable",
                    field_path="dlq_id",
                )
            plan_fingerprint = _reprocess_plan_fingerprint(
                tenant_id=tenant_id,
                dlq_id=record.dlq_id,
                execution_id=record.execution_id,
                job_id=record.job_id,
                reason_code=reason_code,
            )
            existing_execution = self._integration_execution_store.reserve_or_get(
                tenant_id=tenant_id,
                idempotency_key=idempotency_key,
                plan_fingerprint=plan_fingerprint,
            )
            if existing_execution is None:
                reservation_acquired = True
                _ensure_dlq_has_no_accepted_terminal_reprocess(
                    record=record,
                    execution_store=self._integration_execution_store,
                    tenant_id=tenant_id,
                )
                execution = self._integration_execution_store.get_by_execution_id(
                    tenant_id=tenant_id,
                    execution_id=record.execution_id,
                )
                if execution is None:
                    raise IntegrationValidationError(
                        "execução original da DLQ não encontrada",
                        code="integration_execution_not_found",
                        field_path="dlq_id",
                    )
                job = next((job for job in execution.jobs if job.job_id == record.job_id), None)
                if job is None:
                    raise IntegrationValidationError(
                        "job original da DLQ não encontrado",
                        code="integration_dlq_job_not_found",
                        field_path="dlq_id",
                    )
                adapter = self._mock_adapter_registry.get_adapter(
                    job.integration_class,
                    job.adapter_id,
                )
                if adapter is None:
                    raise IntegrationValidationError(
                        "adapter mock/sandbox não registrado para reprocessamento",
                        code="mock_adapter_not_registered",
                        field_path="adapter_id",
                    )
                reprocess_execution_id = self._execution_id_factory(
                    "|".join((tenant_id, dlq_id, idempotency_key, plan_fingerprint))
                )
                reprocess_started_at = self._clock()
                job_request = IntegrationExecutionJobRequest(
                    job_id=self._job_id_factory(
                        "|".join((reprocess_execution_id, record.job_id, idempotency_key))
                    ),
                    item=_plan_item_from_job(job),
                    scenario=_reprocess_scenario_from_original_execution(
                        execution=execution,
                        job=job,
                    ),
                    adapter=adapter,
                    event_type="creditos.integration.job.reprocess_requested.v1",
                )
                dispatch_result = self._integration_execution_dispatcher.dispatch(
                    execution_id=reprocess_execution_id,
                    job_requests=(job_request,),
                    synthetic_subject_reference="synthetic-reprocess-without-pii",
                    context=context,
                    clock=self._clock,
                )
                for retry_schedule in dispatch_result.retry_schedules:
                    self._log_operation(
                        context=context,
                        operation="integration_execution.retry_scheduled",
                        status="accepted",
                        duration_ms=0.0,
                        payload=command,
                        extra=retry_schedule.to_log_safe_dict(),
                    )
                for dlq_record in dispatch_result.dlq_records:
                    self._log_operation(
                        context=context,
                        operation="integration_execution.dlq_recorded",
                        status="accepted",
                        duration_ms=0.0,
                        payload=command,
                        extra=dlq_record.to_log_safe_dict(),
                    )
                reprocess_execution = IntegrationExecution.create(
                    execution_id=reprocess_execution_id,
                    tenant_id=tenant_id,
                    product_type=record.product_type,
                    plan_fingerprint=plan_fingerprint,
                    idempotency_key=idempotency_key,
                    jobs=dispatch_result.jobs,
                    results=dispatch_result.results,
                    correlation_id=context.correlation_id,
                    trace_id=context.trace_id,
                    started_at=reprocess_started_at,
                    completed_at=self._clock(),
                    duration_ms=_duration_ms(started_at),
                )
                cost_records = _validate_cost_records(
                    execution=reprocess_execution,
                    cost_records=dispatch_result.cost_records,
                )
                self._integration_execution_store.save(reprocess_execution)
                updated_record = self._integration_dlq_store.mark_reprocessed(
                    tenant_id=tenant_id,
                    dlq_id=dlq_id,
                    idempotency_key=idempotency_key,
                    reprocessed_at=self._clock(),
                    reprocess_execution_id=reprocess_execution_id,
                )
                self._log_operation(
                    context=context,
                    operation="integration_execution.cost_recorded",
                    status="accepted",
                    duration_ms=0.0,
                    payload=command,
                    extra=_cost_projection_log_extra(
                        execution=reprocess_execution,
                        cost_records=cost_records,
                    ),
                )
                if self._integration_execution_result_publisher is not None:
                    _publish_integration_execution_events(
                        store=self._integration_execution_store,
                        publisher=self._integration_execution_result_publisher,
                        tenant_id=tenant_id,
                        idempotency_key=idempotency_key,
                        events=_integration_execution_events(
                            reprocess_execution,
                            context=context,
                            cost_records=cost_records,
                            retry_schedules=dispatch_result.retry_schedules,
                            dlq_records=dispatch_result.dlq_records,
                            reprocess_record=updated_record,
                            idempotency_key=idempotency_key,
                        ),
                    )
            else:
                reprocess_execution_id = existing_execution.execution_id
                updated_record = self._integration_dlq_store.mark_reprocessed(
                    tenant_id=tenant_id,
                    dlq_id=dlq_id,
                    idempotency_key=idempotency_key,
                    reprocessed_at=self._clock(),
                    reprocess_execution_id=reprocess_execution_id,
                )
                _publish_pending_integration_execution_events(
                    store=self._integration_execution_store,
                    publisher=self._integration_execution_result_publisher,
                    tenant_id=tenant_id,
                    idempotency_key=idempotency_key,
                )
            assert reprocess_execution_id is not None
            self._audit_publisher.publish(
                IntegrationAuditEvent(
                    tenant_id=tenant_id,
                    operation="integration_execution.reprocess_requested",
                    product_type=updated_record.product_type,
                    integration_class=updated_record.integration_class,
                    adapter_id=updated_record.adapter_id,
                    result="accepted",
                    correlation_id=context.correlation_id,
                    trace_id=context.trace_id,
                    schema_version=updated_record.schema_version,
                    occurred_at=updated_record.last_reprocess_at or self._clock(),
                    dlq_id=updated_record.dlq_id,
                    reprocess_execution_id=reprocess_execution_id,
                )
            )
            self._log_operation(
                context=context,
                operation="integration_execution.reprocess_requested",
                status="accepted",
                duration_ms=_duration_ms(started_at),
                payload=command,
                extra=updated_record.to_log_safe_dict()
                | {
                    "reason_code": reason_code,
                    "reprocess_execution_id": reprocess_execution_id,
                    "idempotency_hit": existing_execution is not None,
                },
            )
            return updated_record
        except Exception as error:
            if reservation_acquired and self._integration_execution_store is not None:
                self._integration_execution_store.release_reservation(
                    tenant_id=tenant_id or "",
                    idempotency_key=idempotency_key,
                    plan_fingerprint=plan_fingerprint,
                )
            self._log_operation(
                context=context,
                operation="integration_execution.reprocess_requested",
                status="rejected",
                duration_ms=_duration_ms(started_at),
                payload=command,
                error_type=type(error).__name__,
                extra={
                    "tenant_id_present": _tenant_id_present(tenant_id),
                    "dlq_id": _audit_safe_dlq_id(dlq_id),
                    "denial_reason": getattr(error, "code", type(error).__name__),
                },
            )
            with suppress(Exception):
                self._audit_publisher.publish(
                    IntegrationAuditEvent(
                        tenant_id=tenant_id or "",
                        operation="integration_execution.reprocess_requested",
                        product_type=record.product_type if record is not None else "",
                        integration_class=record.integration_class if record is not None else "",
                        adapter_id=record.adapter_id if record is not None else "",
                        result="rejected",
                        correlation_id=context.correlation_id,
                        trace_id=context.trace_id,
                        schema_version=record.schema_version if record is not None else "1.0",
                        occurred_at=self._clock(),
                        dlq_id=_audit_safe_dlq_id(dlq_id),
                        reprocess_execution_id=reprocess_execution_id,
                    )
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
        "provider_id": configuration.provider_id,
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
    allowed_scenarios = frozenset(
        {
            MockIntegrationScenario.SYNTHETIC_SUCCESS.value,
            MockIntegrationScenario.SYNTHETIC_PARTIAL.value,
            MockIntegrationScenario.SYNTHETIC_NOT_FOUND.value,
            MockIntegrationScenario.SYNTHETIC_FAILURE.value,
        }
    )
    scenarios = tuple(
        (raw if raw in allowed_scenarios else "invalid")
        for raw in (
            scenario_by_class.get(
                integration_class,
                MockIntegrationScenario.SYNTHETIC_SUCCESS.value,
            )
            for integration_class in item_classes
        )
    )
    return {
        "tenant_id_present": tenant_id_present,
        "product_type": getattr(plan, "product_type", ""),
        "plan_status": getattr(plan, "status", ""),
        "configured_items": len(plan_items),
        "integration_classes": item_classes,
        "adapter_ids": tuple(getattr(item, "adapter_id", "") for item in plan_items),
        "scenarios": scenarios,
        "denial_reason": denial_reason,
    }


def _execution_log_extra(execution: IntegrationExecution) -> dict[str, object]:
    return {
        "execution_id": execution.execution_id,
        "product_type": execution.product_type,
        "execution_status": execution.status,
        "job_count": len(execution.jobs),
        "result_count": len(execution.results),
        "integration_classes": tuple(job.integration_class for job in execution.jobs),
        "adapter_ids": tuple(job.adapter_id for job in execution.jobs),
        "job_statuses": tuple(job.status for job in execution.jobs),
        "result_statuses": tuple(result.status for result in execution.results),
        "schema_version": execution.schema_version,
    }


def _cost_projection_log_extra(
    *,
    execution: IntegrationExecution,
    cost_records: tuple[IntegrationExecutionCostRecord, ...],
) -> dict[str, object]:
    return {
        "execution_id": execution.execution_id,
        "tenant_id": execution.tenant_id,
        "product_type": execution.product_type,
        "execution_status": execution.status,
        "schema_version": execution.schema_version,
        "correlation_id": execution.correlation_id,
        "trace_id": execution.trace_id,
        "cost_projection_type": "creditos.integration.execution.cost_recorded.v1",
        "cost_record_count": len(cost_records),
        "total_estimated_cost_units": sum(record.estimated_cost_units for record in cost_records),
        "total_actual_cost_units": sum(record.actual_cost_units for record in cost_records),
        "records": tuple(record.to_log_safe_dict() for record in cost_records),
    }


def _validate_cost_records(
    *,
    execution: IntegrationExecution,
    cost_records: tuple[IntegrationExecutionCostRecord, ...],
) -> tuple[IntegrationExecutionCostRecord, ...]:
    if len(cost_records) != len(execution.jobs):
        raise IntegrationValidationError(
            "projeção de custo deve conter um registro por job",
            code="invalid_integration_cost_record_count",
            field_path="cost_records",
        )
    job_by_id = {job.job_id: job for job in execution.jobs}
    result_by_id = {result.result_id: result for result in execution.results}
    seen_job_ids: set[str] = set()
    for index, record in enumerate(cost_records):
        if record.job_id in seen_job_ids:
            raise IntegrationValidationError(
                "projeção de custo possui job duplicado",
                code="duplicated_integration_cost_record_job",
                field_path=f"cost_records[{index}].job_id",
            )
        seen_job_ids.add(record.job_id)
        job = job_by_id.get(record.job_id)
        if job is None:
            raise IntegrationValidationError(
                "projeção de custo referencia job ausente",
                code="orphan_integration_cost_record_job",
                field_path=f"cost_records[{index}].job_id",
            )
        if record.execution_id != execution.execution_id:
            raise IntegrationValidationError(
                "projeção de custo referencia outra execução",
                code="cross_execution_cost_record",
                field_path=f"cost_records[{index}].execution_id",
            )
        if record.tenant_id != execution.tenant_id or record.tenant_id != job.tenant_id:
            raise IntegrationValidationError(
                "projeção de custo referencia outro tenant",
                code="cross_tenant_cost_record",
                field_path=f"cost_records[{index}].tenant_id",
            )
        if record.product_type != execution.product_type or record.product_type != job.product_type:
            raise IntegrationValidationError(
                "projeção de custo referencia outro produto",
                code="cross_product_cost_record",
                field_path=f"cost_records[{index}].product_type",
            )
        if record.integration_class != job.integration_class or record.adapter_id != job.adapter_id:
            raise IntegrationValidationError(
                "projeção de custo referencia outra classe ou adapter",
                code="cross_adapter_cost_record",
                field_path=f"cost_records[{index}].adapter_id",
            )
        if record.provider_id != job.provider_id:
            raise IntegrationValidationError(
                "projeção de custo referencia outro provider",
                code="cross_provider_cost_record",
                field_path=f"cost_records[{index}].provider_id",
            )
        if record.fallback_strategy != job.fallback_strategy:
            raise IntegrationValidationError(
                "projeção de custo referencia outro fallback",
                code="cross_fallback_cost_record",
                field_path=f"cost_records[{index}].fallback_strategy",
            )
        if record.estimated_cost_units != job.estimated_cost_units:
            raise IntegrationValidationError(
                "projeção de custo referencia custo estimado divergente",
                code="cross_estimated_cost_record",
                field_path=f"cost_records[{index}].estimated_cost_units",
            )
        if record.attempt_count != job.attempt_count:
            raise IntegrationValidationError(
                "projeção de custo referencia tentativas divergentes",
                code="cross_attempt_count_cost_record",
                field_path=f"cost_records[{index}].attempt_count",
            )
        if record.call_count != job.attempt_count:
            raise IntegrationValidationError(
                "projeção de custo referencia chamadas divergentes",
                code="cross_call_count_cost_record",
                field_path=f"cost_records[{index}].call_count",
            )
        if record.actual_cost_units != record.estimated_cost_units * record.call_count:
            raise IntegrationValidationError(
                "projeção de custo referencia custo real divergente",
                code="cross_actual_cost_record",
                field_path=f"cost_records[{index}].actual_cost_units",
            )
        if (
            record.correlation_id != execution.correlation_id
            or record.trace_id != execution.trace_id
        ):
            raise IntegrationValidationError(
                "projeção de custo referencia rastreabilidade divergente",
                code="cross_context_cost_record",
                field_path=f"cost_records[{index}].trace_context",
            )
        if job.result_id is not None and result_by_id[job.result_id].status != record.result_status:
            raise IntegrationValidationError(
                "projeção de custo referencia status de resultado divergente",
                code="cross_result_status_cost_record",
                field_path=f"cost_records[{index}].result_status",
            )
    return cost_records


def _execution_rejection_log_extra(
    *,
    command: StartIntegrationExecutionCommand,
    tenant_id_present: bool,
    denial_reason: str,
) -> dict[str, object]:
    plan = command.plan
    plan_items = getattr(plan, "items", ())
    return {
        "tenant_id_present": tenant_id_present,
        "product_type": getattr(plan, "product_type", ""),
        "plan_status": getattr(plan, "status", ""),
        "configured_items": len(plan_items),
        "integration_classes": tuple(getattr(item, "integration_class", "") for item in plan_items),
        "adapter_ids": tuple(getattr(item, "adapter_id", "") for item in plan_items),
        "denial_reason": denial_reason,
    }


def _validate_execution_plan(plan: IntegrationPlan, *, tenant_id: str) -> None:
    if plan.tenant_id != tenant_id:
        raise IntegrationValidationError(
            "plano de integração pertence a outro tenant",
            code="cross_tenant_integration_plan",
            field_path="plan.tenant_id",
        )
    if plan.status != IntegrationPlanStatus.READY.value:
        raise IntegrationValidationError(
            "plano de integração não está pronto para execução",
            code="integration_plan_not_ready",
            field_path="plan.status",
        )
    if not plan.items:
        raise IntegrationValidationError(
            "plano de integração não possui itens executáveis",
            code="empty_integration_plan",
            field_path="plan.items",
        )
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


def _validate_scenario_classes(
    *,
    plan: IntegrationPlan,
    scenario_by_class: Mapping[str, str],
) -> None:
    item_classes = {item.integration_class for item in plan.items}
    unknown_scenario_classes = tuple(sorted(set(scenario_by_class) - item_classes))
    if unknown_scenario_classes:
        raise IntegrationValidationError(
            "cenário informado para classe fora do plano",
            code="unknown_integration_execution_scenario_class",
            field_path="scenario_by_class",
            details={"integration_classes": unknown_scenario_classes},
        )
    for integration_class in item_classes:
        parse_mock_scenario(
            scenario_by_class.get(
                integration_class,
                MockIntegrationScenario.SYNTHETIC_SUCCESS.value,
            )
        )


def _normalized_scenario_by_class(
    *,
    plan: IntegrationPlan,
    scenario_by_class: Mapping[str, str],
) -> dict[str, str]:
    return {
        item.integration_class: parse_mock_scenario(
            scenario_by_class.get(
                item.integration_class,
                MockIntegrationScenario.SYNTHETIC_SUCCESS.value,
            )
        )
        for item in sorted(plan.items, key=_plan_item_fingerprint_key)
    }


def _integration_plan_fingerprint(
    *,
    plan: IntegrationPlan,
    scenario_by_class: Mapping[str, str],
    synthetic_subject_reference: str,
) -> str:
    safe_plan = {
        "tenant_id": plan.tenant_id,
        "product_type": plan.product_type,
        "status": plan.status,
        "synthetic_subject_reference": synthetic_subject_reference,
        "scenario_by_class": dict(sorted(scenario_by_class.items())),
        "items": [
            {
                "tenant_id": item.tenant_id,
                "product_type": item.product_type,
                "integration_class": item.integration_class,
                "adapter_id": item.adapter_id,
                "requirement": item.requirement,
                "timeout_ms": item.timeout_ms,
                "max_attempts": item.max_attempts,
                "max_concurrency": item.max_concurrency,
                "estimated_cost_units": item.estimated_cost_units,
                "fallback_strategy": item.fallback_strategy,
                "configuration_id": item.configuration_id,
                "provider_id": item.provider_id,
            }
            for item in sorted(plan.items, key=_plan_item_fingerprint_key)
        ],
    }
    encoded = dumps(safe_plan, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"iplan_{sha256(encoded).hexdigest()}"


def _reprocess_plan_fingerprint(
    *,
    tenant_id: str,
    dlq_id: str,
    execution_id: str,
    job_id: str,
    reason_code: str,
) -> str:
    safe_plan = {
        "operation": "integration_dlq_reprocess",
        "tenant_id": tenant_id,
        "dlq_id": dlq_id,
        "execution_id": execution_id,
        "job_id": job_id,
        "reason_code": reason_code,
        "schema_version": "1.0",
    }
    encoded = dumps(safe_plan, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"iplan_{sha256(encoded).hexdigest()}"


def _ensure_dlq_has_no_accepted_terminal_reprocess(
    *,
    record: IntegrationExecutionDlqRecord,
    execution_store: IntegrationExecutionStore,
    tenant_id: str,
) -> None:
    terminal_reprocess_statuses = {
        IntegrationExecutionStatus.COMPLETED.value,
        IntegrationExecutionStatus.PARTIAL.value,
        IntegrationExecutionStatus.MISSING.value,
    }
    for reprocess_execution_id in record.reprocess_execution_ids:
        reprocess_execution = execution_store.get_by_execution_id(
            tenant_id=tenant_id,
            execution_id=reprocess_execution_id,
        )
        if reprocess_execution is None:
            raise IntegrationValidationError(
                "histórico de reprocessamento da DLQ não encontrado",
                code="integration_dlq_reprocess_history_not_found",
                field_path="dlq_id",
            )
        if reprocess_execution.status in terminal_reprocess_statuses:
            raise IntegrationValidationError(
                "DLQ já possui reprocessamento terminal aceito",
                code="integration_dlq_already_reprocessed_terminal",
                field_path="dlq_id",
            )


def _reprocess_scenario_from_original_execution(
    *,
    execution: IntegrationExecution,
    job,
) -> str:
    if job.result_id is None:
        return MockIntegrationScenario.SYNTHETIC_FAILURE.value
    result = next(
        (result for result in execution.results if result.result_id == job.result_id), None
    )
    if result is None:
        return MockIntegrationScenario.SYNTHETIC_FAILURE.value
    return parse_mock_scenario(result.scenario)


def _audit_safe_dlq_id(dlq_id: str) -> str:
    return dlq_id or "invalid_dlq_id"


def _plan_item_fingerprint_key(item: IntegrationPlanItem) -> tuple[str, str, str, str]:
    return (
        item.integration_class,
        item.requirement,
        item.fallback_strategy,
        item.adapter_id,
    )


def _plan_item_from_job(job) -> IntegrationPlanItem:
    return IntegrationPlanItem(
        tenant_id=job.tenant_id,
        product_type=job.product_type,
        integration_class=job.integration_class,
        adapter_id=job.adapter_id,
        requirement=job.requirement,
        timeout_ms=job.timeout_ms,
        max_attempts=job.max_attempts,
        max_concurrency=job.max_concurrency,
        estimated_cost_units=job.estimated_cost_units,
        fallback_strategy=job.fallback_strategy,
        configuration_id=job.configuration_id,
        provider_id=job.provider_id,
    )


def _integration_execution_event(
    execution: IntegrationExecution,
    *,
    context: ObservabilityContext,
) -> IntegrationExecutionEvent:
    event_type = f"creditos.integration.execution.{execution.status}.v1"
    event_id_seed = "|".join(
        (
            execution.execution_id,
            event_type,
            execution.schema_version,
        )
    )
    return IntegrationExecutionEvent(
        specversion="1.0",
        id=f"evt_{sha256(event_id_seed.encode('utf-8')).hexdigest()[:32]}",
        type=event_type,
        source="creditos://integration",
        subject=f"integration-execution/{execution.execution_id}",
        time=execution.completed_at.isoformat(),
        datacontenttype="application/json",
        dataschema="creditos://contracts/schemas/integration/v1/integration-result.schema.json",
        tenant_id=execution.tenant_id,
        correlation_id=execution.correlation_id,
        trace_id=execution.trace_id,
        schema_version=execution.schema_version,
        tenant_isolation_tier=context.tenant_isolation_tier or "bridge",
        request_id=context.request_id,
        idempotency_key=execution.idempotency_key,
        data=MappingProxyType(
            {
                "execution_id": execution.execution_id,
                "product_type": execution.product_type,
                "status": execution.status,
                "job_count": len(execution.jobs),
                "result_count": len(execution.results),
                "results": _integration_result_projection(execution),
                "schema_version": execution.schema_version,
            }
        ),
    )


def _integration_execution_events(
    execution: IntegrationExecution,
    *,
    context: ObservabilityContext,
    cost_records: tuple[IntegrationExecutionCostRecord, ...],
    retry_schedules: tuple[IntegrationExecutionRetrySchedule, ...] = (),
    dlq_records: tuple[IntegrationExecutionDlqRecord, ...] = (),
    reprocess_record: IntegrationExecutionDlqRecord | None = None,
    idempotency_key: str | None = None,
) -> tuple[IntegrationExecutionEvent, ...]:
    events: list[IntegrationExecutionEvent] = [
        _integration_execution_event(execution, context=context),
        _integration_cost_event(execution, context=context, cost_records=cost_records),
    ]
    events.extend(
        _integration_retry_event(
            schedule, context=context, idempotency_key=execution.idempotency_key
        )
        for schedule in retry_schedules
    )
    events.extend(
        _integration_dlq_event(record, context=context, idempotency_key=execution.idempotency_key)
        for record in dlq_records
    )
    if reprocess_record is not None:
        events.append(
            _integration_reprocess_event(
                reprocess_record,
                context=context,
                idempotency_key=idempotency_key or execution.idempotency_key,
            )
        )
    return tuple(events)


def _publish_integration_execution_events(
    *,
    store: IntegrationExecutionStore,
    publisher: IntegrationExecutionResultPublisher,
    tenant_id: str,
    idempotency_key: str,
    events: tuple[IntegrationExecutionEvent, ...],
) -> None:
    store.stage_execution_events(
        tenant_id=tenant_id,
        idempotency_key=idempotency_key,
        events=events,
    )
    _publish_pending_integration_execution_events(
        store=store,
        publisher=publisher,
        tenant_id=tenant_id,
        idempotency_key=idempotency_key,
    )


def _publish_pending_integration_execution_events(
    *,
    store: IntegrationExecutionStore,
    publisher: IntegrationExecutionResultPublisher | None,
    tenant_id: str,
    idempotency_key: str,
) -> None:
    if publisher is None:
        return
    for event in store.list_unpublished_execution_events(
        tenant_id=tenant_id,
        idempotency_key=idempotency_key,
    ):
        publisher.publish(event)
        store.mark_execution_event_published(
            tenant_id=tenant_id,
            idempotency_key=idempotency_key,
            event_id=event.id,
        )


def _integration_cost_event(
    execution: IntegrationExecution,
    *,
    context: ObservabilityContext,
    cost_records: tuple[IntegrationExecutionCostRecord, ...],
) -> IntegrationExecutionEvent:
    event_type = "creditos.integration.execution.cost_recorded.v1"
    event_id_seed = "|".join(
        (
            execution.execution_id,
            event_type,
            execution.schema_version,
        )
    )
    return IntegrationExecutionEvent(
        specversion="1.0",
        id=f"evt_{sha256(event_id_seed.encode('utf-8')).hexdigest()[:32]}",
        type=event_type,
        source="creditos://integration",
        subject=f"integration-execution/{execution.execution_id}",
        time=execution.completed_at.isoformat(),
        datacontenttype="application/json",
        dataschema="creditos://contracts/schemas/integration/v1/integration-cost.schema.json",
        tenant_id=execution.tenant_id,
        correlation_id=execution.correlation_id,
        trace_id=execution.trace_id,
        schema_version=execution.schema_version,
        tenant_isolation_tier=context.tenant_isolation_tier or "bridge",
        request_id=context.request_id,
        idempotency_key=execution.idempotency_key,
        data=MappingProxyType(
            {
                "execution_id": execution.execution_id,
                "product_type": execution.product_type,
                "status": execution.status,
                "schema_version": execution.schema_version,
                "job_count": len(execution.jobs),
                "result_count": len(execution.results),
                "cost_projection_type": "creditos.integration.execution.cost_recorded.v1",
                "total_estimated_cost_units": sum(
                    record.estimated_cost_units for record in cost_records
                ),
                "total_actual_cost_units": sum(record.actual_cost_units for record in cost_records),
                "cost_records": tuple(record.to_log_safe_dict() for record in cost_records),
            }
        ),
    )


def _integration_retry_event(
    schedule: IntegrationExecutionRetrySchedule,
    *,
    context: ObservabilityContext,
    idempotency_key: str,
) -> IntegrationExecutionEvent:
    event_type = "creditos.integration.job.retry_scheduled.v1"
    return _integration_job_event(
        event_type=event_type,
        subject=f"integration-execution/{schedule.execution_id}/job/{schedule.job_id}",
        occurrence_key=f"attempt:{schedule.attempt_count}",
        occurred_at=schedule.scheduled_at,
        tenant_id=schedule.tenant_id,
        correlation_id=schedule.correlation_id,
        trace_id=schedule.trace_id,
        schema_version=schedule.schema_version,
        context=context,
        idempotency_key=idempotency_key,
        dataschema="creditos://contracts/schemas/integration/v1/integration-retry.schema.json",
        data={
            "execution_id": schedule.execution_id,
            "job_id": schedule.job_id,
            "integration_class": schedule.integration_class,
            "adapter_id": schedule.adapter_id,
            "failure_class": schedule.failure_class,
            "failure_code": schedule.failure_code,
            "attempt_count": schedule.attempt_count,
            "retry_delay_ms": schedule.retry_delay_ms,
            "schema_version": schedule.schema_version,
        },
    )


def _integration_dlq_event(
    record: IntegrationExecutionDlqRecord,
    *,
    context: ObservabilityContext,
    idempotency_key: str,
) -> IntegrationExecutionEvent:
    return _integration_job_event(
        event_type="creditos.integration.job.dlq_recorded.v1",
        subject=f"integration-execution/{record.execution_id}/job/{record.job_id}",
        occurrence_key=f"dlq:{record.dlq_id}",
        occurred_at=record.created_at.isoformat(),
        tenant_id=record.tenant_id,
        correlation_id=record.correlation_id,
        trace_id=record.trace_id,
        schema_version=record.schema_version,
        context=context,
        idempotency_key=idempotency_key,
        dataschema="creditos://contracts/schemas/integration/v1/integration-dlq.schema.json",
        data=_integration_dlq_data(record),
    )


def _integration_reprocess_event(
    record: IntegrationExecutionDlqRecord,
    *,
    context: ObservabilityContext,
    idempotency_key: str,
) -> IntegrationExecutionEvent:
    occurred_at = (
        record.last_reprocess_at.isoformat()
        if record.last_reprocess_at is not None
        else record.created_at.isoformat()
    )
    return _integration_job_event(
        event_type="creditos.integration.job.reprocess_requested.v1",
        subject=f"integration-execution/{record.execution_id}/job/{record.job_id}",
        occurrence_key=f"reprocess:{record.reprocess_count}:{idempotency_key}",
        occurred_at=occurred_at,
        tenant_id=record.tenant_id,
        correlation_id=record.correlation_id,
        trace_id=record.trace_id,
        schema_version=record.schema_version,
        context=context,
        idempotency_key=idempotency_key,
        dataschema="creditos://contracts/schemas/integration/v1/integration-dlq.schema.json",
        data=_integration_dlq_data(record),
    )


def _integration_job_event(
    *,
    event_type: str,
    subject: str,
    occurrence_key: str,
    occurred_at: str,
    tenant_id: str,
    correlation_id: str,
    trace_id: str,
    schema_version: str,
    context: ObservabilityContext,
    idempotency_key: str,
    dataschema: str,
    data: dict[str, object],
) -> IntegrationExecutionEvent:
    event_id_seed = "|".join((subject, event_type, occurrence_key, schema_version))
    return IntegrationExecutionEvent(
        specversion="1.0",
        id=f"evt_{sha256(event_id_seed.encode('utf-8')).hexdigest()[:32]}",
        type=event_type,
        source="creditos://integration",
        subject=subject,
        time=occurred_at,
        datacontenttype="application/json",
        dataschema=dataschema,
        tenant_id=tenant_id,
        correlation_id=correlation_id,
        trace_id=trace_id,
        schema_version=schema_version,
        tenant_isolation_tier=context.tenant_isolation_tier or "bridge",
        request_id=context.request_id,
        idempotency_key=idempotency_key,
        data=MappingProxyType(data),
    )


def _integration_dlq_data(record: IntegrationExecutionDlqRecord) -> dict[str, object]:
    data: dict[str, object] = {
        "execution_id": record.execution_id,
        "job_id": record.job_id,
        "dlq_id": record.dlq_id,
        "integration_class": record.integration_class,
        "adapter_id": record.adapter_id,
        "failure_class": record.failure_class,
        "failure_code": record.failure_code,
        "attempt_count": record.attempt_count,
        "reprocess_count": record.reprocess_count,
        "schema_version": record.schema_version,
    }
    return data


def _integration_result_projection(
    execution: IntegrationExecution,
) -> tuple[dict[str, object], ...]:
    job_by_result_id = {job.result_id: job for job in execution.jobs if job.result_id is not None}
    return tuple(
        {
            "result_id": result.result_id,
            "job_id": job_by_result_id[result.result_id].job_id,
            "integration_class": result.integration_class,
            "adapter_id": result.adapter_id,
            "provider_id": job_by_result_id[result.result_id].provider_id,
            "result_status": result.status,
            "reason_codes": result.reason_codes,
            "synthetic_scenario": result.scenario,
            "duration_ms": int(round(result.duration_ms)),
        }
        for result in execution.results
        if result.result_id in job_by_result_id
    )


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


def _default_execution_id(seed: str) -> str:
    return f"iexec_{sha256(seed.encode('utf-8')).hexdigest()[:32]}"


def _default_job_id(seed: str) -> str:
    return f"ijob_{sha256(seed.encode('utf-8')).hexdigest()[:32]}"


def _duration_ms(started_at: float) -> float:
    return round((perf_counter() - started_at) * 1000, 3)
