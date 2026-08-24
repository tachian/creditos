from __future__ import annotations

import json
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import pytest
from creditos_integration.adapters.events import InMemoryIntegrationExecutionDispatcher
from creditos_integration.adapters.external import (
    InMemoryMockIntegrationAdapter,
    InMemoryMockIntegrationAdapterRegistry,
)
from creditos_integration.adapters.persistence import (
    InMemoryIntegrationCatalogRepository,
    InMemoryIntegrationDlqStore,
    InMemoryIntegrationExecutionStore,
)
from creditos_integration.application.ports.adapter_registry import InMemoryAdapterRegistry
from creditos_integration.application.ports.audit_event_publisher import InMemoryAuditEventPublisher
from creditos_integration.application.ports.integration_execution import (
    IntegrationExecutionDispatchResult,
    IntegrationExecutionEvent,
    IntegrationExecutionJobRequest,
)
from creditos_integration.application.service import (
    BuildIntegrationPlanCommand,
    ConfigureIntegrationClassCommand,
    IntegrationCatalogApplicationService,
    StartIntegrationExecutionCommand,
)
from creditos_integration.domain.entities import (
    IntegrationExecutionCostRecord,
    IntegrationPlan,
    IntegrationPlanItem,
    IntegrationResult,
)
from creditos_integration.domain.errors import IntegrationValidationError
from creditos_observability.context import ObservabilityContext

_FIXED_TIME = datetime(2026, 8, 20, 10, 0, tzinfo=UTC)
_MVP_CLASSES = ("kyc_kyb", "credit_bureau", "anti_fraud", "receivables")
_ADAPTER_BY_CLASS = {
    "kyc_kyb": "mock-kyc-basic-v1",
    "credit_bureau": "mock-credit-bureau-v1",
    "anti_fraud": "mock-antifraud-v1",
    "receivables": "mock-receivables-v1",
}


def test_start_execution_creates_jobs_results_and_completed_fan_in() -> None:
    dispatcher = InMemoryIntegrationExecutionDispatcher()
    service = _service(dispatcher=dispatcher)
    plan = _ready_plan(service)

    execution = service.start_integration_execution(
        StartIntegrationExecutionCommand(
            plan=plan,
            idempotency_key="integration-key-0001",
            scopes=("integration_execution:start",),
        ),
        context=_context(),
    )

    assert execution.execution_id.startswith("iexec_")
    assert execution.status == "completed"
    assert execution.schema_version == "1.0"
    assert execution.tenant_id == "tenant-bridge-001"
    assert execution.product_type == "personal_credit"
    assert execution.correlation_id == "corr-integration-001"
    assert execution.trace_id == "22222222222222222222222222222222"
    assert len(execution.jobs) == 4
    assert len(execution.results) == 4
    assert execution.job_ids == tuple(job.job_id for job in execution.jobs)
    assert {job.status for job in execution.jobs} == {"completed"}
    assert {job.attempt_count for job in execution.jobs} == {1}
    assert {job.schema_version for job in execution.jobs} == {"1.0"}
    assert {result.status for result in execution.results} == {"completed"}
    for job, item in zip(execution.jobs, plan.items, strict=True):
        assert job.tenant_id == item.tenant_id
        assert job.product_type == item.product_type
        assert job.integration_class == item.integration_class
        assert job.adapter_id == item.adapter_id
        assert job.timeout_ms == item.timeout_ms
        assert job.max_attempts == item.max_attempts
        assert job.max_concurrency == item.max_concurrency
        assert job.correlation_id == "corr-integration-001"
        assert job.trace_id == "22222222222222222222222222222222"
    assert dispatcher.dispatch_count == 1
    assert service.logged_events[-1]["operation"] == "integration_execution.fan_in"
    assert service.logged_events[-1]["extra"]["execution_status"] == "completed"


def test_in_memory_dispatcher_respects_effective_concurrency_limit() -> None:
    adapters = tuple(
        SlowMockIntegrationAdapter(
            integration_class=integration_class,
            adapter_id=adapter_id,
            delay_seconds=0.03,
        )
        for integration_class, adapter_id in _ADAPTER_BY_CLASS.items()
    )
    dispatcher = InMemoryIntegrationExecutionDispatcher()
    service = _service(
        dispatcher=dispatcher,
        mock_adapter_registry=InMemoryMockIntegrationAdapterRegistry(adapters),
    )
    plan = _ready_plan(service)

    execution = service.start_integration_execution(
        StartIntegrationExecutionCommand(
            plan=plan,
            idempotency_key="integration-key-0002",
            scopes=("integration_execution:start",),
        ),
        context=_context(),
    )

    assert execution.status == "completed"
    assert dispatcher.max_observed_concurrency == 3


def test_idempotency_replays_same_execution_without_dispatching_duplicate_jobs() -> None:
    dispatcher = InMemoryIntegrationExecutionDispatcher()
    service = _service(dispatcher=dispatcher)
    plan = _ready_plan(service)
    command = StartIntegrationExecutionCommand(
        plan=plan,
        idempotency_key="integration-key-0003",
        scopes=("integration_execution:start",),
    )

    first_execution = service.start_integration_execution(command, context=_context())
    second_execution = service.start_integration_execution(command, context=_context())

    assert second_execution == first_execution
    assert dispatcher.dispatch_count == 1
    assert service.logged_events[-1]["operation"] == "integration_execution.idempotency_hit"
    assert service.logged_events[-1]["extra"]["execution_id"] == first_execution.execution_id
    assert service.logged_events[-1]["extra"]["idempotency_hit"] is True


def test_concurrent_idempotency_reserves_once_and_waits_for_existing_execution() -> None:
    adapters = tuple(
        SlowMockIntegrationAdapter(
            integration_class=integration_class,
            adapter_id=adapter_id,
            delay_seconds=0.03,
        )
        for integration_class, adapter_id in _ADAPTER_BY_CLASS.items()
    )
    dispatcher = InMemoryIntegrationExecutionDispatcher()
    service = _service(
        dispatcher=dispatcher,
        mock_adapter_registry=InMemoryMockIntegrationAdapterRegistry(adapters),
    )
    plan = _ready_plan(service)
    command = StartIntegrationExecutionCommand(
        plan=plan,
        idempotency_key="integration-key-concurrent",
        scopes=("integration_execution:start",),
    )

    with ThreadPoolExecutor(max_workers=2) as executor:
        executions = tuple(
            future.result()
            for future in (
                executor.submit(service.start_integration_execution, command, context=_context()),
                executor.submit(service.start_integration_execution, command, context=_context()),
            )
        )

    assert executions[0] == executions[1]
    assert dispatcher.dispatch_count == 1


def test_rejects_formatted_document_as_idempotency_key_before_dispatch() -> None:
    dispatcher = InMemoryIntegrationExecutionDispatcher()
    service = _service(dispatcher=dispatcher)
    plan = _ready_plan(service)

    with pytest.raises(IntegrationValidationError) as error:
        service.start_integration_execution(
            StartIntegrationExecutionCommand(
                plan=plan,
                idempotency_key="doc:000.000.001-91",
                scopes=("integration_execution:start",),
            ),
            context=_context(),
        )

    assert error.value.code == "sensitive_integration_execution_idempotency_key"
    assert dispatcher.dispatch_count == 0


def test_default_and_explicit_success_scenarios_share_same_idempotency_fingerprint() -> None:
    dispatcher = InMemoryIntegrationExecutionDispatcher()
    service = _service(dispatcher=dispatcher)
    plan = _ready_plan(service)
    implicit_execution = service.start_integration_execution(
        StartIntegrationExecutionCommand(
            plan=plan,
            idempotency_key="integration-key-defaults",
            scopes=("integration_execution:start",),
        ),
        context=_context(),
    )

    explicit_execution = service.start_integration_execution(
        StartIntegrationExecutionCommand(
            plan=plan,
            idempotency_key="integration-key-defaults",
            scenario_by_class={
                integration_class: "synthetic_success" for integration_class in _MVP_CLASSES
            },
            scopes=("integration_execution:start",),
        ),
        context=_context(),
    )

    assert explicit_execution == implicit_execution
    assert dispatcher.dispatch_count == 1


def test_idempotency_key_conflict_rejects_different_plan_fingerprint() -> None:
    dispatcher = InMemoryIntegrationExecutionDispatcher()
    service = _service(dispatcher=dispatcher)
    first_plan = _ready_plan(service)
    second_plan = _ready_plan(service, product_type="bnpl")

    service.start_integration_execution(
        StartIntegrationExecutionCommand(
            plan=first_plan,
            idempotency_key="integration-key-0004",
            scopes=("integration_execution:start",),
        ),
        context=_context(),
    )

    with pytest.raises(IntegrationValidationError) as error:
        service.start_integration_execution(
            StartIntegrationExecutionCommand(
                plan=second_plan,
                idempotency_key="integration-key-0004",
                scopes=("integration_execution:start",),
            ),
            context=_context(),
        )

    assert error.value.code == "integration_execution_idempotency_conflict"
    assert dispatcher.dispatch_count == 1


def test_idempotency_key_conflict_rejects_changed_plan_cost() -> None:
    dispatcher = InMemoryIntegrationExecutionDispatcher()
    service = _service(dispatcher=dispatcher)
    plan = _ready_plan(service)
    changed_cost_plan = IntegrationPlan(
        tenant_id=plan.tenant_id,
        product_type=plan.product_type,
        status=plan.status,
        items=tuple(
            IntegrationPlanItem(
                tenant_id=item.tenant_id,
                product_type=item.product_type,
                integration_class=item.integration_class,
                adapter_id=item.adapter_id,
                requirement=item.requirement,
                timeout_ms=item.timeout_ms,
                max_attempts=item.max_attempts,
                max_concurrency=item.max_concurrency,
                estimated_cost_units=item.estimated_cost_units + 1,
                fallback_strategy=item.fallback_strategy,
                configuration_id=item.configuration_id,
            )
            for item in plan.items
        ),
    )

    service.start_integration_execution(
        StartIntegrationExecutionCommand(
            plan=plan,
            idempotency_key="integration-key-cost-conflict",
            scopes=("integration_execution:start",),
        ),
        context=_context(),
    )

    with pytest.raises(IntegrationValidationError) as error:
        service.start_integration_execution(
            StartIntegrationExecutionCommand(
                plan=changed_cost_plan,
                idempotency_key="integration-key-cost-conflict",
                scopes=("integration_execution:start",),
            ),
            context=_context(),
        )

    assert error.value.code == "integration_execution_idempotency_conflict"
    assert dispatcher.dispatch_count == 1


def test_preflight_rejects_invalid_plan_before_dispatching_any_job() -> None:
    dispatcher = InMemoryIntegrationExecutionDispatcher()
    mock_registry = InMemoryMockIntegrationAdapterRegistry.for_mvp_defaults()
    service = _service(dispatcher=dispatcher, mock_adapter_registry=mock_registry)
    plan = _ready_plan(service)
    forged_plan = IntegrationPlan(
        tenant_id=plan.tenant_id,
        product_type=plan.product_type,
        status=plan.status,
        items=(
            IntegrationPlanItem(
                tenant_id=plan.tenant_id,
                product_type="bnpl",
                integration_class="kyc_kyb",
                adapter_id="mock-kyc-basic-v1",
                requirement="required",
                timeout_ms=1_500,
                max_attempts=2,
                max_concurrency=3,
                estimated_cost_units=12,
                fallback_strategy="fail_closed",
                configuration_id="icfg_forged",
            ),
        ),
    )

    with pytest.raises(IntegrationValidationError) as error:
        service.start_integration_execution(
            StartIntegrationExecutionCommand(
                plan=forged_plan,
                idempotency_key="integration-key-0005",
                scopes=("integration_execution:start",),
            ),
            context=_context(),
        )

    assert error.value.code == "cross_product_integration_plan_item"
    assert dispatcher.dispatch_count == 0
    assert mock_registry.execution_attempts == ()
    assert service.logged_events[-1]["status"] == "rejected"


@pytest.mark.parametrize(
    ("scenario_by_class", "expected_status"),
    [
        ({}, "completed"),
        ({"anti_fraud": "synthetic_partial"}, "partial"),
        (
            {
                "anti_fraud": "synthetic_not_found",
                "credit_bureau": "synthetic_not_found",
                "kyc_kyb": "synthetic_not_found",
                "receivables": "synthetic_not_found",
            },
            "missing",
        ),
        ({"credit_bureau": "synthetic_failure"}, "failed"),
    ],
)
def test_fan_in_returns_canonical_execution_statuses(
    scenario_by_class: dict[str, str],
    expected_status: str,
) -> None:
    service = _service(dispatcher=InMemoryIntegrationExecutionDispatcher())
    plan = _ready_plan(service)

    execution = service.start_integration_execution(
        StartIntegrationExecutionCommand(
            plan=plan,
            idempotency_key=f"integration-key-status-{expected_status}",
            scenario_by_class=scenario_by_class,
            scopes=("integration_execution:start",),
        ),
        context=_context(),
    )

    assert execution.status == expected_status


def test_adapter_exception_is_converted_to_canonical_failed_result() -> None:
    dispatcher = InMemoryIntegrationExecutionDispatcher()
    service = _service(
        dispatcher=dispatcher,
        mock_adapter_registry=InMemoryMockIntegrationAdapterRegistry(
            (
                RaisingMockIntegrationAdapter(
                    integration_class="kyc_kyb",
                    adapter_id="mock-kyc-basic-v1",
                ),
            )
        ),
    )
    service.configure_integration_class(
        _configure_command(integration_class="kyc_kyb", adapter_id="mock-kyc-basic-v1"),
        context=_context(),
    )
    plan = service.build_integration_plan(
        BuildIntegrationPlanCommand(product_type="personal_credit", required_classes=("kyc_kyb",)),
        context=_context(),
    )

    execution = service.start_integration_execution(
        StartIntegrationExecutionCommand(
            plan=plan,
            idempotency_key="integration-key-exception",
            scopes=("integration_execution:start",),
        ),
        context=_context(),
    )

    assert execution.status == "failed"
    assert execution.jobs[0].status == "failed"
    assert execution.results[0].status == "failed"


def test_job_timeout_is_mapped_to_terminal_failed_execution() -> None:
    dispatcher = InMemoryIntegrationExecutionDispatcher()
    service = _service(
        dispatcher=dispatcher,
        mock_adapter_registry=InMemoryMockIntegrationAdapterRegistry(
            (
                SlowMockIntegrationAdapter(
                    integration_class="kyc_kyb",
                    adapter_id="mock-kyc-basic-v1",
                    delay_seconds=0.06,
                ),
            )
        ),
    )
    service.configure_integration_class(
        _configure_command(
            integration_class="kyc_kyb",
            adapter_id="mock-kyc-basic-v1",
            timeout_ms=50,
        ),
        context=_context(),
    )
    plan = service.build_integration_plan(
        BuildIntegrationPlanCommand(product_type="personal_credit", required_classes=("kyc_kyb",)),
        context=_context(),
    )

    execution = service.start_integration_execution(
        StartIntegrationExecutionCommand(
            plan=plan,
            idempotency_key="integration-key-timeout",
            scopes=("integration_execution:start",),
        ),
        context=_context(),
    )

    assert execution.status == "failed"
    assert execution.jobs[0].status == "timed_out"
    assert execution.results[0].status == "failed"


def test_optional_failure_with_allow_partial_keeps_execution_partial() -> None:
    dispatcher = InMemoryIntegrationExecutionDispatcher()
    service = _service(dispatcher=dispatcher)
    service.configure_integration_class(
        _configure_command(integration_class="kyc_kyb", adapter_id="mock-kyc-basic-v1"),
        context=_context(),
    )
    service.configure_integration_class(
        _configure_command(
            integration_class="anti_fraud",
            adapter_id="mock-antifraud-v1",
            requirement="optional",
            fallback_strategy="allow_partial",
        ),
        context=_context(),
    )
    plan = service.build_integration_plan(
        BuildIntegrationPlanCommand(
            product_type="personal_credit",
            required_classes=("kyc_kyb",),
            optional_classes=("anti_fraud",),
        ),
        context=_context(),
    )

    execution = service.start_integration_execution(
        StartIntegrationExecutionCommand(
            plan=plan,
            idempotency_key="integration-key-optional",
            scenario_by_class={"anti_fraud": "synthetic_failure"},
            scopes=("integration_execution:start",),
        ),
        context=_context(),
    )

    assert execution.status == "partial"
    assert {job.integration_class: job.status for job in execution.jobs} == {
        "kyc_kyb": "completed",
        "anti_fraud": "failed",
    }


def test_result_trace_context_mismatch_is_converted_to_failed_result() -> None:
    dispatcher = InMemoryIntegrationExecutionDispatcher()
    service = _service(
        dispatcher=dispatcher,
        mock_adapter_registry=InMemoryMockIntegrationAdapterRegistry(
            (
                WrongTraceMockIntegrationAdapter(
                    integration_class="kyc_kyb",
                    adapter_id="mock-kyc-basic-v1",
                ),
            )
        ),
    )
    service.configure_integration_class(
        _configure_command(integration_class="kyc_kyb", adapter_id="mock-kyc-basic-v1"),
        context=_context(),
    )
    plan = service.build_integration_plan(
        BuildIntegrationPlanCommand(product_type="personal_credit", required_classes=("kyc_kyb",)),
        context=_context(),
    )

    execution = service.start_integration_execution(
        StartIntegrationExecutionCommand(
            plan=plan,
            idempotency_key="integration-key-wrong-trace",
            scopes=("integration_execution:start",),
        ),
        context=_context(),
    )

    assert execution.status == "failed"
    assert execution.results[0].trace_id == "22222222222222222222222222222222"


def test_result_publisher_receives_internal_event_envelope() -> None:
    publisher = CapturingIntegrationExecutionResultPublisher()
    service = _service(
        dispatcher=InMemoryIntegrationExecutionDispatcher(),
        result_publisher=publisher,
    )
    plan = _ready_plan(service)

    execution = service.start_integration_execution(
        StartIntegrationExecutionCommand(
            plan=plan,
            idempotency_key="integration-key-event",
            scopes=("integration_execution:start",),
        ),
        context=_context(),
    )

    assert len(publisher.events) == 1
    event = publisher.events[0]
    assert event.specversion == "1.0"
    assert event.id.startswith("evt_")
    assert event.type == "creditos.integration.execution.completed.v1"
    assert event.source == "integration"
    assert event.subject == f"integration-execution/{execution.execution_id}"
    assert event.datacontenttype == "application/json"
    assert event.tenant_id == execution.tenant_id
    assert event.correlation_id == execution.correlation_id
    assert event.trace_id == execution.trace_id
    assert event.data["execution_id"] == execution.execution_id
    assert event.data["job_count"] == len(execution.jobs)


def test_cost_projection_records_integer_units_and_minimized_event() -> None:
    publisher = CapturingIntegrationExecutionResultPublisher()
    service = _service(
        dispatcher=InMemoryIntegrationExecutionDispatcher(),
        result_publisher=publisher,
    )
    plan = _ready_plan(service)

    execution = service.start_integration_execution(
        StartIntegrationExecutionCommand(
            plan=plan,
            idempotency_key="integration-key-cost-event",
            scopes=("integration_execution:start",),
        ),
        context=_context(),
    )

    assert {job.estimated_cost_units for job in execution.jobs} == {12}
    assert len(publisher.events) == 1
    event = publisher.events[0]
    records = event.data["cost_records"]
    assert event.data["cost_projection_type"] == "creditos.integration.execution.cost_recorded.v1"
    assert event.data["total_estimated_cost_units"] == 48
    assert event.data["total_actual_cost_units"] == 48
    assert len(records) == 4
    assert {
        (
            record["tenant_id"],
            record["product_type"],
            record["integration_class"],
            record["adapter_id"],
            record["provider_id"],
            record["result_status"],
            record["call_count"],
            record["attempt_count"],
            record["estimated_cost_units"],
            record["actual_cost_units"],
            record["correlation_id"],
            record["trace_id"],
        )
        for record in records
    } == {
        (
            "tenant-bridge-001",
            "personal_credit",
            item.integration_class,
            item.adapter_id,
            None,
            "completed",
            1,
            1,
            12,
            12,
            "corr-integration-001",
            "22222222222222222222222222222222",
        )
        for item in plan.items
    }
    serialized = json.dumps(event.to_log_safe_dict(), ensure_ascii=False, sort_keys=True)
    assert "summary" not in serialized
    assert "synthetic_data_type" not in serialized


def test_cost_projection_preserves_configured_provider_id() -> None:
    publisher = CapturingIntegrationExecutionResultPublisher()
    service = _service(
        dispatcher=InMemoryIntegrationExecutionDispatcher(),
        result_publisher=publisher,
    )
    service.configure_integration_class(
        _configure_command(
            integration_class="kyc_kyb",
            adapter_id="mock-kyc-basic-v1",
            provider_id="iprv_mock_provider_v1",
        ),
        context=_context(),
    )
    plan = service.build_integration_plan(
        BuildIntegrationPlanCommand(product_type="personal_credit", required_classes=("kyc_kyb",)),
        context=_context(),
    )

    execution = service.start_integration_execution(
        StartIntegrationExecutionCommand(
            plan=plan,
            idempotency_key="integration-key-cost-provider",
            scopes=("integration_execution:start",),
        ),
        context=_context(),
    )

    assert execution.jobs[0].provider_id == "iprv_mock_provider_v1"
    assert publisher.events[0].data["cost_records"][0]["provider_id"] == "iprv_mock_provider_v1"


def test_rejects_dispatch_result_without_one_cost_record_per_job() -> None:
    dispatcher = MissingCostRecordDispatcher()
    service = _service(dispatcher=dispatcher)
    plan = _ready_plan(service)

    with pytest.raises(IntegrationValidationError) as error:
        service.start_integration_execution(
            StartIntegrationExecutionCommand(
                plan=plan,
                idempotency_key="integration-key-missing-costs",
                scopes=("integration_execution:start",),
            ),
            context=_context(),
        )

    assert error.value.code == "invalid_integration_cost_record_count"


def test_rejects_dispatch_result_with_inconsistent_call_count_or_actual_cost() -> None:
    dispatcher = InconsistentCostRecordDispatcher()
    service = _service(dispatcher=dispatcher)
    plan = _ready_plan(service)

    with pytest.raises(IntegrationValidationError) as error:
        service.start_integration_execution(
            StartIntegrationExecutionCommand(
                plan=plan,
                idempotency_key="integration-key-inconsistent-costs",
                scopes=("integration_execution:start",),
            ),
            context=_context(),
        )

    assert error.value.code == "cross_call_count_cost_record"


def test_cost_projection_is_not_duplicated_on_idempotency_hit() -> None:
    publisher = CapturingIntegrationExecutionResultPublisher()
    service = _service(
        dispatcher=InMemoryIntegrationExecutionDispatcher(),
        result_publisher=publisher,
    )
    plan = _ready_plan(service)
    command = StartIntegrationExecutionCommand(
        plan=plan,
        idempotency_key="integration-key-cost-idempotency",
        scopes=("integration_execution:start",),
    )

    first_execution = service.start_integration_execution(command, context=_context())
    second_execution = service.start_integration_execution(command, context=_context())

    assert second_execution == first_execution
    assert len(publisher.events) == 1
    cost_logs = [
        log
        for log in service.logged_events
        if log["operation"] == "integration_execution.cost_recorded"
    ]
    assert len(cost_logs) == 1
    assert cost_logs[0]["extra"]["total_actual_cost_units"] == 48


def test_cost_record_rejects_sensitive_provider_identifier() -> None:
    service = _service(dispatcher=InMemoryIntegrationExecutionDispatcher())
    plan = _ready_plan(service)
    execution = service.start_integration_execution(
        StartIntegrationExecutionCommand(
            plan=plan,
            idempotency_key="integration-key-provider-sensitive",
            scopes=("integration_execution:start",),
        ),
        context=_context(),
    )

    with pytest.raises(IntegrationValidationError) as error:
        IntegrationExecutionCostRecord.from_job_result(
            job=execution.jobs[0],
            result=execution.results[0],
            provider_id="provider-person@example.com",
        )

    assert error.value.code == "sensitive_integration_provider_id"


def test_rejects_missing_execution_scope_before_dispatch() -> None:
    dispatcher = InMemoryIntegrationExecutionDispatcher()
    service = _service(dispatcher=dispatcher)
    plan = _ready_plan(service)

    with pytest.raises(IntegrationValidationError) as error:
        service.start_integration_execution(
            StartIntegrationExecutionCommand(plan=plan, idempotency_key="integration-key-0006"),
            context=_context(),
        )

    assert error.value.code == "insufficient_scope"
    assert dispatcher.dispatch_count == 0


def test_execution_logs_and_results_do_not_expose_sensitive_or_raw_payload_fragments() -> None:
    service = _service(dispatcher=InMemoryIntegrationExecutionDispatcher())
    plan = _ready_plan(service)

    execution = service.start_integration_execution(
        StartIntegrationExecutionCommand(
            plan=plan,
            idempotency_key="integration-key-0007",
            synthetic_subject_reference="synthetic-reference-without-pii",
            scopes=("integration_execution:start",),
        ),
        context=_context(),
    )

    serialized = json.dumps(
        {
            "logs": service.logged_events,
            "execution": execution.to_log_safe_dict(),
            "jobs": [job.to_log_safe_dict() for job in execution.jobs],
            "results": [result.to_log_safe_dict() for result in execution.results],
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
        "nome",
        "email",
        "Authorization",
        "Bearer",
        "secret",
        "token",
        "raw_payload",
        "payload_bruto",
        "provider_response",
        "external_response",
        "credential",
    }:
        assert fragment not in serialized


def _service(
    *,
    repository: InMemoryIntegrationCatalogRepository | None = None,
    adapter_registry: InMemoryAdapterRegistry | None = None,
    mock_adapter_registry: InMemoryMockIntegrationAdapterRegistry | None = None,
    execution_store: InMemoryIntegrationExecutionStore | None = None,
    dispatcher: InMemoryIntegrationExecutionDispatcher,
    result_publisher: CapturingIntegrationExecutionResultPublisher | None = None,
    environment: str = "test",
) -> IntegrationCatalogApplicationService:
    dlq_store = InMemoryIntegrationDlqStore()
    dispatcher._dlq_store = dlq_store
    return IntegrationCatalogApplicationService(
        repository=repository or InMemoryIntegrationCatalogRepository(),
        adapter_registry=adapter_registry or InMemoryAdapterRegistry(_allowed_adapters()),
        mock_adapter_registry=mock_adapter_registry
        or InMemoryMockIntegrationAdapterRegistry.for_mvp_defaults(),
        integration_execution_store=execution_store or InMemoryIntegrationExecutionStore(),
        integration_dlq_store=dlq_store,
        integration_execution_dispatcher=dispatcher,
        integration_execution_result_publisher=result_publisher,
        audit_publisher=InMemoryAuditEventPublisher(),
        environment=environment,
        clock=lambda: _FIXED_TIME,
        configuration_id_factory=lambda seed: f"icfg_{seed}",
    )


def _ready_plan(
    service: IntegrationCatalogApplicationService,
    *,
    tenant_id: str = "tenant-bridge-001",
    product_type: str = "personal_credit",
) -> IntegrationPlan:
    for integration_class in _MVP_CLASSES:
        service.configure_integration_class(
            _configure_command(
                product_type=product_type,
                integration_class=integration_class,
                adapter_id=_ADAPTER_BY_CLASS[integration_class],
            ),
            context=_context(tenant_id),
        )
    plan = service.build_integration_plan(
        BuildIntegrationPlanCommand(
            product_type=product_type,
            required_classes=_MVP_CLASSES,
        ),
        context=_context(tenant_id),
    )
    assert plan.status == "ready"
    return plan


def _configure_command(
    *,
    product_type: str = "personal_credit",
    integration_class: str = "kyc_kyb",
    adapter_id: str = "mock-kyc-basic-v1",
    requirement: str = "required",
    timeout_ms: int = 1_500,
    max_concurrency: int = 3,
    fallback_strategy: str = "fail_closed",
    provider_id: str | None = None,
) -> ConfigureIntegrationClassCommand:
    return ConfigureIntegrationClassCommand(
        product_type=product_type,
        integration_class=integration_class,
        adapter_id=adapter_id,
        requirement=requirement,
        timeout_ms=timeout_ms,
        max_attempts=2,
        max_concurrency=max_concurrency,
        estimated_cost_units=12,
        fallback_strategy=fallback_strategy,
        provider_id=provider_id,
        scopes=("integration_catalog:write",),
    )


def _context(tenant_id: str = "tenant-bridge-001") -> ObservabilityContext:
    return ObservabilityContext.new(
        correlation_id="corr-integration-001",
        request_id="req-integration-001",
        trace_id="22222222222222222222222222222222",
        tenant_id=tenant_id,
        tenant_isolation_tier="bridge",
    )


def _allowed_adapters() -> dict[str, set[str]]:
    return {
        integration_class: {adapter_id}
        for integration_class, adapter_id in _ADAPTER_BY_CLASS.items()
    }


class SlowMockIntegrationAdapter(InMemoryMockIntegrationAdapter):
    def __init__(
        self,
        *,
        integration_class: str,
        adapter_id: str,
        delay_seconds: float,
    ) -> None:
        super().__init__(integration_class=integration_class, adapter_id=adapter_id)
        self._delay_seconds = delay_seconds

    def execute(
        self,
        item: IntegrationPlanItem,
        *,
        scenario: str,
        synthetic_subject_reference: str,
        context: ObservabilityContext,
        started_at: datetime,
        completed_at: datetime,
        duration_ms: float,
    ) -> IntegrationResult:
        time.sleep(self._delay_seconds)
        return super().execute(
            item,
            scenario=scenario,
            synthetic_subject_reference=synthetic_subject_reference,
            context=context,
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=duration_ms,
        )


class RaisingMockIntegrationAdapter(InMemoryMockIntegrationAdapter):
    def execute(
        self,
        item: IntegrationPlanItem,
        *,
        scenario: str,
        synthetic_subject_reference: str,
        context: ObservabilityContext,
        started_at: datetime,
        completed_at: datetime,
        duration_ms: float,
    ) -> IntegrationResult:
        raise RuntimeError("synthetic adapter outage")


class WrongTraceMockIntegrationAdapter(InMemoryMockIntegrationAdapter):
    def execute(
        self,
        item: IntegrationPlanItem,
        *,
        scenario: str,
        synthetic_subject_reference: str,
        context: ObservabilityContext,
        started_at: datetime,
        completed_at: datetime,
        duration_ms: float,
    ) -> IntegrationResult:
        result = super().execute(
            item,
            scenario=scenario,
            synthetic_subject_reference=synthetic_subject_reference,
            context=context,
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=duration_ms,
        )
        return IntegrationResult.create(
            result_id=result.result_id,
            tenant_id=result.tenant_id,
            product_type=result.product_type,
            integration_class=result.integration_class,
            adapter_id=result.adapter_id,
            status=result.status,
            scenario=result.scenario,
            reason_codes=result.reason_codes,
            summary=result.summary,
            correlation_id=result.correlation_id,
            trace_id="33333333333333333333333333333333",
            started_at=result.started_at,
            completed_at=result.completed_at,
            duration_ms=result.duration_ms,
        )


class CapturingIntegrationExecutionResultPublisher:
    def __init__(self) -> None:
        self.events: list[IntegrationExecutionEvent] = []

    def publish(self, event: IntegrationExecutionEvent) -> None:
        self.events.append(event)


class MissingCostRecordDispatcher(InMemoryIntegrationExecutionDispatcher):
    def dispatch(
        self,
        *,
        execution_id: str,
        job_requests: tuple[IntegrationExecutionJobRequest, ...],
        synthetic_subject_reference: str,
        context: ObservabilityContext,
        clock: Callable[[], datetime],
    ) -> IntegrationExecutionDispatchResult:
        dispatch_result = super().dispatch(
            execution_id=execution_id,
            job_requests=job_requests,
            synthetic_subject_reference=synthetic_subject_reference,
            context=context,
            clock=clock,
        )
        return IntegrationExecutionDispatchResult(
            jobs=dispatch_result.jobs,
            results=dispatch_result.results,
            max_observed_concurrency=dispatch_result.max_observed_concurrency,
            cost_records=(),
            retry_schedules=dispatch_result.retry_schedules,
            dlq_records=dispatch_result.dlq_records,
        )


class InconsistentCostRecordDispatcher(InMemoryIntegrationExecutionDispatcher):
    def dispatch(
        self,
        *,
        execution_id: str,
        job_requests: tuple[IntegrationExecutionJobRequest, ...],
        synthetic_subject_reference: str,
        context: ObservabilityContext,
        clock: Callable[[], datetime],
    ) -> IntegrationExecutionDispatchResult:
        dispatch_result = super().dispatch(
            execution_id=execution_id,
            job_requests=job_requests,
            synthetic_subject_reference=synthetic_subject_reference,
            context=context,
            clock=clock,
        )
        first_record = dispatch_result.cost_records[0]
        forged_record = IntegrationExecutionCostRecord.create(
            execution_id=first_record.execution_id,
            job_id=first_record.job_id,
            tenant_id=first_record.tenant_id,
            product_type=first_record.product_type,
            integration_class=first_record.integration_class,
            adapter_id=first_record.adapter_id,
            provider_id=first_record.provider_id,
            result_status=first_record.result_status,
            call_count=0,
            attempt_count=first_record.attempt_count,
            fallback_strategy=first_record.fallback_strategy,
            estimated_cost_units=first_record.estimated_cost_units,
            actual_cost_units=999,
            schema_version=first_record.schema_version,
            correlation_id=first_record.correlation_id,
            trace_id=first_record.trace_id,
        )
        return IntegrationExecutionDispatchResult(
            jobs=dispatch_result.jobs,
            results=dispatch_result.results,
            max_observed_concurrency=dispatch_result.max_observed_concurrency,
            cost_records=(forged_record, *dispatch_result.cost_records[1:]),
            retry_schedules=dispatch_result.retry_schedules,
            dlq_records=dispatch_result.dlq_records,
        )
