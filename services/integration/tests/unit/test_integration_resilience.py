from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from typing import Any, cast

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
    INTEGRATION_RESILIENCE_EVENT_TYPES,
    JETSTREAM_RESILIENCE_MAPPING,
)
from creditos_integration.application.service import (
    BuildIntegrationPlanCommand,
    ConfigureIntegrationClassCommand,
    IntegrationCatalogApplicationService,
    ReprocessIntegrationDlqCommand,
    StartIntegrationExecutionCommand,
)
from creditos_integration.domain.entities import (
    IntegrationExecution,
    IntegrationPlanItem,
    IntegrationResult,
)
from creditos_integration.domain.errors import IntegrationValidationError
from creditos_observability.context import ObservabilityContext

_FIXED_TIME = datetime(2026, 8, 21, 10, 0, tzinfo=UTC)


def test_recoverable_failure_retries_with_deterministic_schedule_and_succeeds_without_dlq() -> None:
    first_service = _service_with_adapter(FlakyMockIntegrationAdapter(failures_before_success=1))
    first_execution = _start_single_class_execution(first_service, "resilience-key-retry-ok")

    second_service = _service_with_adapter(FlakyMockIntegrationAdapter(failures_before_success=1))
    _start_single_class_execution(second_service, "resilience-key-retry-ok")

    assert first_execution.status == "completed"
    assert first_execution.jobs[0].attempt_count == 2
    assert first_service.dispatcher.retry_schedule_count == 1
    assert (
        first_service.dlq_store.list_for_execution(
            tenant_id="tenant-bridge-001",
            execution_id=first_execution.execution_id,
        )
        == ()
    )
    first_retry_log = _only_log(first_service.service, "integration_execution.retry_scheduled")
    second_retry_log = _only_log(second_service.service, "integration_execution.retry_scheduled")
    assert first_retry_log["extra"]["backoff_ms"] == 250
    assert first_retry_log["extra"]["jitter_ms"] == second_retry_log["extra"]["jitter_ms"]
    assert first_retry_log["extra"]["retry_delay_ms"] == second_retry_log["extra"]["retry_delay_ms"]


def test_recoverable_failure_exceeding_max_attempts_creates_canonical_dlq() -> None:
    service_bundle = _service_with_adapter(RaisingMockIntegrationAdapter())

    execution = _start_single_class_execution(service_bundle, "resilience-key-dlq-recoverable")

    dlq_records = service_bundle.dlq_store.list_for_execution(
        tenant_id="tenant-bridge-001",
        execution_id=execution.execution_id,
    )
    assert execution.status == "failed"
    assert execution.jobs[0].status == "failed"
    assert execution.jobs[0].attempt_count == 2
    assert service_bundle.dispatcher.retry_schedule_count == 1
    assert len(dlq_records) == 1
    assert dlq_records[0].failure_class == "recoverable"
    assert dlq_records[0].failure_code == "adapter_error"
    assert dlq_records[0].attempt_count == 2
    assert _only_log(service_bundle.service, "integration_execution.dlq_recorded")


def test_non_recoverable_failure_goes_to_dlq_without_retry_extra() -> None:
    service_bundle = _service_with_adapter(NonRecoverableMockIntegrationAdapter())

    execution = _start_single_class_execution(service_bundle, "resilience-key-dlq-final")

    dlq_records = service_bundle.dlq_store.list_for_execution(
        tenant_id="tenant-bridge-001",
        execution_id=execution.execution_id,
    )
    assert execution.status == "failed"
    assert execution.jobs[0].attempt_count == 1
    assert service_bundle.dispatcher.retry_schedule_count == 0
    assert len(dlq_records) == 1
    assert dlq_records[0].failure_class == "non_recoverable"
    assert dlq_records[0].failure_code == "non_recoverable_adapter_error"


def test_timeout_retries_until_limit_and_records_timed_out_dlq() -> None:
    service_bundle = _service_with_adapter(SlowMockIntegrationAdapter(delay_seconds=0.06))

    execution = _start_single_class_execution(
        service_bundle,
        "resilience-key-dlq-timeout",
        timeout_ms=50,
    )

    dlq_records = service_bundle.dlq_store.list_for_execution(
        tenant_id="tenant-bridge-001",
        execution_id=execution.execution_id,
    )
    assert execution.status == "failed"
    assert execution.jobs[0].status == "timed_out"
    assert execution.jobs[0].attempt_count == 2
    assert service_bundle.dispatcher.retry_schedule_count == 1
    assert len(dlq_records) == 1
    assert dlq_records[0].failure_class == "timeout"
    assert dlq_records[0].failure_code == "timed_out"


def test_invalid_result_is_classified_and_sent_to_dlq_without_raw_exception() -> None:
    service_bundle = _service_with_adapter(WrongTraceMockIntegrationAdapter())

    execution = _start_single_class_execution(service_bundle, "resilience-key-dlq-invalid")

    dlq_records = service_bundle.dlq_store.list_for_execution(
        tenant_id="tenant-bridge-001",
        execution_id=execution.execution_id,
    )
    assert execution.status == "failed"
    assert service_bundle.dispatcher.retry_schedule_count == 0
    assert len(dlq_records) == 1
    assert dlq_records[0].failure_class == "invalid_result"
    assert dlq_records[0].failure_code == "integration_job_result_trace_mismatch"


def test_invalid_result_contract_is_classified_and_sent_to_dlq() -> None:
    service_bundle = _service_with_adapter(MalformedResultMockIntegrationAdapter())

    execution = _start_single_class_execution(service_bundle, "resilience-key-dlq-invalid-contract")

    dlq_records = service_bundle.dlq_store.list_for_execution(
        tenant_id="tenant-bridge-001",
        execution_id=execution.execution_id,
    )
    assert execution.status == "failed"
    assert service_bundle.dispatcher.retry_schedule_count == 0
    assert len(dlq_records) == 1
    assert dlq_records[0].failure_class == "invalid_result"
    assert dlq_records[0].failure_code == "integration_job_result_invalid_type"


def test_controlled_failed_result_is_retried_and_sent_to_dlq() -> None:
    service_bundle = _service_with_adapter(
        InMemoryMockIntegrationAdapter(
            integration_class="kyc_kyb",
            adapter_id="mock-kyc-basic-v1",
        )
    )
    service_bundle.service.configure_integration_class(
        _configure_command(max_attempts=2),
        context=_context(),
    )
    plan = service_bundle.service.build_integration_plan(
        BuildIntegrationPlanCommand(product_type="personal_credit", required_classes=("kyc_kyb",)),
        context=_context(),
    )

    execution = service_bundle.service.start_integration_execution(
        StartIntegrationExecutionCommand(
            plan=plan,
            idempotency_key="resilience-key-controlled-failed-result",
            scenario_by_class={"kyc_kyb": "synthetic_failure"},
            synthetic_subject_reference="synthetic-reference-without-pii",
            scopes=("integration_execution:start",),
        ),
        context=_context(),
    )
    dlq_records = service_bundle.dlq_store.list_for_execution(
        tenant_id="tenant-bridge-001",
        execution_id=execution.execution_id,
    )

    assert execution.status == "failed"
    assert execution.jobs[0].attempt_count == 2
    assert service_bundle.dispatcher.retry_schedule_count == 1
    assert len(dlq_records) == 1
    assert dlq_records[0].failure_class == "recoverable"
    assert dlq_records[0].failure_code == "synthetic_controlled_failure"


def test_reprocess_requires_specific_scope_before_marking_dlq() -> None:
    service_bundle = _service_with_adapter(RaisingMockIntegrationAdapter())
    execution = _start_single_class_execution(service_bundle, "resilience-key-reprocess-scope")
    dlq_record = service_bundle.dlq_store.list_for_execution(
        tenant_id="tenant-bridge-001",
        execution_id=execution.execution_id,
    )[0]

    with pytest.raises(IntegrationValidationError) as error:
        service_bundle.service.reprocess_integration_dlq(
            ReprocessIntegrationDlqCommand(
                dlq_id=dlq_record.dlq_id,
                idempotency_key="idempotency-key-reprocess-denied",
            ),
            context=_context(),
        )

    assert error.value.code == "insufficient_scope"
    stored_dlq_record = service_bundle.dlq_store.get(
        tenant_id="tenant-bridge-001",
        dlq_id=dlq_record.dlq_id,
    )
    assert stored_dlq_record is not None
    assert stored_dlq_record.reprocess_count == 0


def test_reprocess_rejects_cross_tenant_dlq_lookup() -> None:
    service_bundle = _service_with_adapter(RaisingMockIntegrationAdapter())
    execution = _start_single_class_execution(service_bundle, "resilience-key-reprocess-tenant")
    dlq_record = service_bundle.dlq_store.list_for_execution(
        tenant_id="tenant-bridge-001",
        execution_id=execution.execution_id,
    )[0]

    with pytest.raises(IntegrationValidationError) as error:
        service_bundle.service.reprocess_integration_dlq(
            ReprocessIntegrationDlqCommand(
                dlq_id=dlq_record.dlq_id,
                idempotency_key="idempotency-key-cross-tenant",
                scopes=("integration_execution:reprocess",),
            ),
            context=_context("tenant-bridge-002"),
        )

    assert error.value.code == "integration_dlq_record_not_found"


def test_reprocess_is_idempotent_and_does_not_duplicate_original_results() -> None:
    service_bundle = _service_with_adapter(RaisingMockIntegrationAdapter())
    execution = _start_single_class_execution(service_bundle, "resilience-key-reprocess-ok")
    dlq_record = service_bundle.dlq_store.list_for_execution(
        tenant_id="tenant-bridge-001",
        execution_id=execution.execution_id,
    )[0]
    command = ReprocessIntegrationDlqCommand(
        dlq_id=dlq_record.dlq_id,
        idempotency_key="idempotency-key-reprocess-ok",
        scopes=("integration_execution:reprocess",),
    )

    first_reprocess = service_bundle.service.reprocess_integration_dlq(command, context=_context())
    second_reprocess = service_bundle.service.reprocess_integration_dlq(command, context=_context())
    stored_execution = service_bundle.execution_store.get_by_execution_id(
        tenant_id="tenant-bridge-001",
        execution_id=execution.execution_id,
    )

    assert first_reprocess.reprocess_count == 1
    assert second_reprocess.reprocess_count == 1
    assert stored_execution is not None
    assert len(stored_execution.results) == 1
    reprocess_log = [
        log
        for log in service_bundle.service.logged_events
        if log["operation"] == "integration_execution.reprocess_requested"
    ][0]
    assert first_reprocess.reprocess_execution_ids == (
        reprocess_log["extra"]["reprocess_execution_id"],
    )
    assert reprocess_log["extra"]["reprocess_execution_id"].startswith("iexec_")
    assert reprocess_log["extra"]["idempotency_hit"] is False
    assert service_bundle.audit_publisher.events[-1].dlq_id == dlq_record.dlq_id
    assert (
        service_bundle.audit_publisher.events[-1].reprocess_execution_id
        == reprocess_log["extra"]["reprocess_execution_id"]
    )


def test_reprocess_rejects_new_key_after_terminal_reprocess() -> None:
    adapter = ControlledFailureThenSuccessMockIntegrationAdapter(failures_before_success=2)
    service_bundle = _service_with_adapter(adapter)
    execution = _start_single_class_execution(
        service_bundle,
        "resilience-key-reprocess-terminal",
        max_attempts=2,
    )
    dlq_record = service_bundle.dlq_store.list_for_execution(
        tenant_id="tenant-bridge-001",
        execution_id=execution.execution_id,
    )[0]

    reprocessed = service_bundle.service.reprocess_integration_dlq(
        ReprocessIntegrationDlqCommand(
            dlq_id=dlq_record.dlq_id,
            idempotency_key="idempotency-key-reprocess-terminal-first",
            scopes=("integration_execution:reprocess",),
        ),
        context=_context(),
    )
    reprocess_execution = service_bundle.execution_store.get_by_execution_id(
        tenant_id="tenant-bridge-001",
        execution_id=reprocessed.reprocess_execution_ids[0],
    )

    assert reprocess_execution is not None
    assert reprocess_execution.status == "completed"
    assert adapter.execute_call_count == 3
    with pytest.raises(IntegrationValidationError) as error:
        service_bundle.service.reprocess_integration_dlq(
            ReprocessIntegrationDlqCommand(
                dlq_id=dlq_record.dlq_id,
                idempotency_key="idempotency-key-reprocess-terminal-second",
                scopes=("integration_execution:reprocess",),
            ),
            context=_context(),
        )

    assert error.value.code == "integration_dlq_already_reprocessed_terminal"
    assert adapter.execute_call_count == 3


def test_reprocess_preserves_original_controlled_failure_scenario() -> None:
    service_bundle = _service_with_adapter(
        InMemoryMockIntegrationAdapter(
            integration_class="kyc_kyb",
            adapter_id="mock-kyc-basic-v1",
        )
    )
    service_bundle.service.configure_integration_class(
        _configure_command(max_attempts=2),
        context=_context(),
    )
    plan = service_bundle.service.build_integration_plan(
        BuildIntegrationPlanCommand(product_type="personal_credit", required_classes=("kyc_kyb",)),
        context=_context(),
    )
    execution = service_bundle.service.start_integration_execution(
        StartIntegrationExecutionCommand(
            plan=plan,
            idempotency_key="resilience-key-reprocess-preserve-scenario",
            scenario_by_class={"kyc_kyb": "synthetic_failure"},
            synthetic_subject_reference="synthetic-reference-without-pii",
            scopes=("integration_execution:start",),
        ),
        context=_context(),
    )
    dlq_record = service_bundle.dlq_store.list_for_execution(
        tenant_id="tenant-bridge-001",
        execution_id=execution.execution_id,
    )[0]

    reprocessed = service_bundle.service.reprocess_integration_dlq(
        ReprocessIntegrationDlqCommand(
            dlq_id=dlq_record.dlq_id,
            idempotency_key="idempotency-key-reprocess-preserve-scenario",
            scopes=("integration_execution:reprocess",),
        ),
        context=_context(),
    )
    reprocess_execution = service_bundle.execution_store.get_by_execution_id(
        tenant_id="tenant-bridge-001",
        execution_id=reprocessed.reprocess_execution_ids[0],
    )

    assert reprocess_execution is not None
    assert reprocess_execution.status == "failed"
    assert reprocess_execution.results[0].scenario == "synthetic_failure"


def test_reprocess_rejects_same_key_with_different_reason_code() -> None:
    service_bundle = _service_with_adapter(RaisingMockIntegrationAdapter())
    execution = _start_single_class_execution(service_bundle, "resilience-key-reprocess-reason")
    dlq_record = service_bundle.dlq_store.list_for_execution(
        tenant_id="tenant-bridge-001",
        execution_id=execution.execution_id,
    )[0]
    first_command = ReprocessIntegrationDlqCommand(
        dlq_id=dlq_record.dlq_id,
        idempotency_key="idempotency-key-reprocess-reason",
        reason_code="operator_requested",
        scopes=("integration_execution:reprocess",),
    )
    second_command = ReprocessIntegrationDlqCommand(
        dlq_id=dlq_record.dlq_id,
        idempotency_key="idempotency-key-reprocess-reason",
        reason_code="operator_override",
        scopes=("integration_execution:reprocess",),
    )

    service_bundle.service.reprocess_integration_dlq(first_command, context=_context())
    with pytest.raises(IntegrationValidationError) as error:
        service_bundle.service.reprocess_integration_dlq(second_command, context=_context())

    assert error.value.code == "integration_execution_idempotency_conflict"


def test_reprocess_rejection_audit_never_persists_raw_invalid_dlq_id() -> None:
    service_bundle = _service_with_adapter(RaisingMockIntegrationAdapter())

    with pytest.raises(IntegrationValidationError) as error:
        service_bundle.service.reprocess_integration_dlq(
            ReprocessIntegrationDlqCommand(
                dlq_id="person@example.com",
                idempotency_key="idempotency-key-invalid-dlq",
                scopes=("integration_execution:reprocess",),
            ),
            context=_context(),
        )

    assert error.value.code == "invalid_integration_execution_dlq_id"
    assert service_bundle.audit_publisher.events[-1].result == "rejected"
    assert service_bundle.audit_publisher.events[-1].dlq_id == "invalid_dlq_id"
    serialized_audit = json.dumps(
        [event.to_log_safe_dict() for event in service_bundle.audit_publisher.events],
        sort_keys=True,
        default=str,
    )
    assert "person@example.com" not in serialized_audit


def test_reprocess_idempotency_key_cannot_be_reused_for_another_dlq() -> None:
    service_bundle = _service_with_adapters(
        (
            RaisingMockIntegrationAdapter(
                integration_class="kyc_kyb",
                adapter_id="mock-kyc-basic-v1",
            ),
            RaisingMockIntegrationAdapter(
                integration_class="anti_fraud",
                adapter_id="mock-antifraud-v1",
            ),
        )
    )
    for integration_class, adapter_id in {
        "kyc_kyb": "mock-kyc-basic-v1",
        "anti_fraud": "mock-antifraud-v1",
    }.items():
        service_bundle.service.configure_integration_class(
            _configure_command(integration_class=integration_class, adapter_id=adapter_id),
            context=_context(),
        )
    plan = service_bundle.service.build_integration_plan(
        BuildIntegrationPlanCommand(
            product_type="personal_credit",
            required_classes=("kyc_kyb", "anti_fraud"),
        ),
        context=_context(),
    )
    execution = service_bundle.service.start_integration_execution(
        StartIntegrationExecutionCommand(
            plan=plan,
            idempotency_key="resilience-key-two-dlqs",
            synthetic_subject_reference="synthetic-reference-without-pii",
            scopes=("integration_execution:start",),
        ),
        context=_context(),
    )
    dlq_records = service_bundle.dlq_store.list_for_execution(
        tenant_id="tenant-bridge-001",
        execution_id=execution.execution_id,
    )
    assert len(dlq_records) == 2

    first_command = ReprocessIntegrationDlqCommand(
        dlq_id=dlq_records[0].dlq_id,
        idempotency_key="idempotency-key-reprocess-shared",
        scopes=("integration_execution:reprocess",),
    )
    second_command = ReprocessIntegrationDlqCommand(
        dlq_id=dlq_records[1].dlq_id,
        idempotency_key="idempotency-key-reprocess-shared",
        scopes=("integration_execution:reprocess",),
    )

    service_bundle.service.reprocess_integration_dlq(first_command, context=_context())
    with pytest.raises(IntegrationValidationError) as error:
        service_bundle.service.reprocess_integration_dlq(second_command, context=_context())

    assert error.value.code == "integration_execution_idempotency_conflict"


def test_non_retryable_dlq_is_not_eligible_for_automatic_reprocess() -> None:
    service_bundle = _service_with_adapter(NonRecoverableMockIntegrationAdapter())
    execution = _start_single_class_execution(service_bundle, "resilience-key-reprocess-denied")
    dlq_record = service_bundle.dlq_store.list_for_execution(
        tenant_id="tenant-bridge-001",
        execution_id=execution.execution_id,
    )[0]

    with pytest.raises(IntegrationValidationError) as error:
        service_bundle.service.reprocess_integration_dlq(
            ReprocessIntegrationDlqCommand(
                dlq_id=dlq_record.dlq_id,
                idempotency_key="idempotency-key-nonretryable",
                scopes=("integration_execution:reprocess",),
            ),
            context=_context(),
        )

    assert error.value.code == "integration_dlq_record_not_retryable"
    assert (
        service_bundle.audit_publisher.events[-1].operation
        == "integration_execution.reprocess_requested"
    )
    assert service_bundle.audit_publisher.events[-1].result == "rejected"
    assert service_bundle.audit_publisher.events[-1].dlq_id == dlq_record.dlq_id


def test_resilience_mapping_documents_future_nats_jetstream_concepts() -> None:
    assert JETSTREAM_RESILIENCE_MAPPING["ack_policy"] == "explicit"
    assert JETSTREAM_RESILIENCE_MAPPING["ack_wait_source"] == "integration_plan_item.timeout_ms"
    assert (
        JETSTREAM_RESILIENCE_MAPPING["max_deliver_source"] == "integration_plan_item.max_attempts"
    )
    assert (
        JETSTREAM_RESILIENCE_MAPPING["max_deliver_advisory"]
        == "$JS.EVENT.ADVISORY.CONSUMER.MAX_DELIVERIES.{stream}.{consumer}"
    )
    assert (
        INTEGRATION_RESILIENCE_EVENT_TYPES["dlq_recorded"]
        == "creditos.integration.job.dlq_recorded.v1"
    )


def test_resilience_logs_and_dlq_records_do_not_expose_sensitive_or_raw_fragments() -> None:
    service_bundle = _service_with_adapter(RaisingMockIntegrationAdapter())
    execution = _start_single_class_execution(service_bundle, "resilience-key-log-safe")
    dlq_records = service_bundle.dlq_store.list_for_execution(
        tenant_id="tenant-bridge-001",
        execution_id=execution.execution_id,
    )

    serialized = json.dumps(
        {
            "logs": service_bundle.service.logged_events,
            "dlq": [record.to_log_safe_dict() for record in dlq_records],
            "execution": execution.to_log_safe_dict(),
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
        "email",
        "Authorization",
        "Bearer",
        "secret",
        "token",
        "raw_payload",
        "provider_response",
        "exception",
        "stack_trace",
        "traceback",
        "credential",
        "password",
    }:
        assert fragment not in serialized


def _start_single_class_execution(
    service_bundle: ServiceBundle,
    idempotency_key: str,
    *,
    timeout_ms: int = 1_500,
    max_attempts: int = 2,
) -> IntegrationExecution:
    service_bundle.service.configure_integration_class(
        _configure_command(timeout_ms=timeout_ms, max_attempts=max_attempts),
        context=_context(),
    )
    plan = service_bundle.service.build_integration_plan(
        BuildIntegrationPlanCommand(product_type="personal_credit", required_classes=("kyc_kyb",)),
        context=_context(),
    )
    return service_bundle.service.start_integration_execution(
        StartIntegrationExecutionCommand(
            plan=plan,
            idempotency_key=idempotency_key,
            synthetic_subject_reference="synthetic-reference-without-pii",
            scopes=("integration_execution:start",),
        ),
        context=_context(),
    )


def _service_with_adapter(adapter: InMemoryMockIntegrationAdapter) -> ServiceBundle:
    return _service_with_adapters((adapter,))


def _service_with_adapters(adapters: tuple[InMemoryMockIntegrationAdapter, ...]) -> ServiceBundle:
    execution_store = InMemoryIntegrationExecutionStore()
    dlq_store = InMemoryIntegrationDlqStore()
    dispatcher = InMemoryIntegrationExecutionDispatcher(dlq_store=dlq_store)
    audit_publisher = InMemoryAuditEventPublisher()
    service = IntegrationCatalogApplicationService(
        repository=InMemoryIntegrationCatalogRepository(),
        adapter_registry=InMemoryAdapterRegistry(
            {
                "kyc_kyb": {"mock-kyc-basic-v1"},
                "anti_fraud": {"mock-antifraud-v1"},
            }
        ),
        mock_adapter_registry=InMemoryMockIntegrationAdapterRegistry(adapters),
        integration_execution_store=execution_store,
        integration_dlq_store=dlq_store,
        integration_execution_dispatcher=dispatcher,
        audit_publisher=audit_publisher,
        environment="test",
        clock=lambda: _FIXED_TIME,
        configuration_id_factory=lambda seed: f"icfg_{seed}",
    )
    return ServiceBundle(
        service=service,
        dispatcher=dispatcher,
        execution_store=execution_store,
        dlq_store=dlq_store,
        audit_publisher=audit_publisher,
    )


def _configure_command(
    *,
    integration_class: str = "kyc_kyb",
    adapter_id: str = "mock-kyc-basic-v1",
    timeout_ms: int = 1_500,
    max_attempts: int = 2,
) -> ConfigureIntegrationClassCommand:
    return ConfigureIntegrationClassCommand(
        product_type="personal_credit",
        integration_class=integration_class,
        adapter_id=adapter_id,
        requirement="required",
        timeout_ms=timeout_ms,
        max_attempts=max_attempts,
        max_concurrency=1,
        estimated_cost_units=12,
        fallback_strategy="fail_closed",
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


def _only_log(
    service: IntegrationCatalogApplicationService,
    operation: str,
) -> dict[str, Any]:
    matches = [log for log in service.logged_events if log["operation"] == operation]
    assert len(matches) == 1
    return matches[0]


class ServiceBundle:
    def __init__(
        self,
        *,
        service: IntegrationCatalogApplicationService,
        dispatcher: InMemoryIntegrationExecutionDispatcher,
        execution_store: InMemoryIntegrationExecutionStore,
        dlq_store: InMemoryIntegrationDlqStore,
        audit_publisher: InMemoryAuditEventPublisher,
    ) -> None:
        self.service = service
        self.dispatcher = dispatcher
        self.execution_store = execution_store
        self.dlq_store = dlq_store
        self.audit_publisher = audit_publisher


class FlakyMockIntegrationAdapter(InMemoryMockIntegrationAdapter):
    def __init__(self, *, failures_before_success: int) -> None:
        super().__init__(integration_class="kyc_kyb", adapter_id="mock-kyc-basic-v1")
        self._remaining_failures = failures_before_success

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
        if self._remaining_failures > 0:
            self._remaining_failures -= 1
            raise RuntimeError("synthetic recoverable outage")
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
    def __init__(
        self,
        *,
        integration_class: str = "kyc_kyb",
        adapter_id: str = "mock-kyc-basic-v1",
    ) -> None:
        super().__init__(integration_class=integration_class, adapter_id=adapter_id)

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
        raise RuntimeError("synthetic recoverable outage")


class ControlledFailureThenSuccessMockIntegrationAdapter(InMemoryMockIntegrationAdapter):
    def __init__(self, *, failures_before_success: int) -> None:
        super().__init__(integration_class="kyc_kyb", adapter_id="mock-kyc-basic-v1")
        self._remaining_failures = failures_before_success
        self.execute_call_count = 0

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
        self.execute_call_count += 1
        result = super().execute(
            item,
            scenario=scenario,
            synthetic_subject_reference=synthetic_subject_reference,
            context=context,
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=duration_ms,
        )
        if self._remaining_failures > 0:
            self._remaining_failures -= 1
            return IntegrationResult.create(
                result_id=result.result_id,
                tenant_id=result.tenant_id,
                product_type=result.product_type,
                integration_class=result.integration_class,
                adapter_id=result.adapter_id,
                status="failed",
                scenario=result.scenario,
                reason_codes=("synthetic_controlled_failure",),
                summary=result.summary,
                correlation_id=result.correlation_id,
                trace_id=result.trace_id,
                started_at=result.started_at,
                completed_at=result.completed_at,
                duration_ms=result.duration_ms,
            )
        return IntegrationResult.create(
            result_id=result.result_id,
            tenant_id=result.tenant_id,
            product_type=result.product_type,
            integration_class=result.integration_class,
            adapter_id=result.adapter_id,
            status="completed",
            scenario=result.scenario,
            reason_codes=("synthetic_match",),
            summary=result.summary,
            correlation_id=result.correlation_id,
            trace_id=result.trace_id,
            started_at=result.started_at,
            completed_at=result.completed_at,
            duration_ms=result.duration_ms,
        )


class NonRecoverableMockIntegrationAdapter(InMemoryMockIntegrationAdapter):
    def __init__(self) -> None:
        super().__init__(integration_class="kyc_kyb", adapter_id="mock-kyc-basic-v1")

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
        raise PermissionError("synthetic non recoverable denial")


class SlowMockIntegrationAdapter(InMemoryMockIntegrationAdapter):
    def __init__(self, *, delay_seconds: float) -> None:
        super().__init__(integration_class="kyc_kyb", adapter_id="mock-kyc-basic-v1")
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


class WrongTraceMockIntegrationAdapter(InMemoryMockIntegrationAdapter):
    def __init__(self) -> None:
        super().__init__(integration_class="kyc_kyb", adapter_id="mock-kyc-basic-v1")

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


class MalformedResultMockIntegrationAdapter(InMemoryMockIntegrationAdapter):
    def __init__(self) -> None:
        super().__init__(integration_class="kyc_kyb", adapter_id="mock-kyc-basic-v1")

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
        return cast(IntegrationResult, {"status": "completed"})
