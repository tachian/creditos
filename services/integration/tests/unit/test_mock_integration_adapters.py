from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from creditos_integration.adapters.external import (
    InMemoryMockIntegrationAdapter,
    InMemoryMockIntegrationAdapterRegistry,
)
from creditos_integration.adapters.persistence import InMemoryIntegrationCatalogRepository
from creditos_integration.application.ports.adapter_registry import InMemoryAdapterRegistry
from creditos_integration.application.ports.audit_event_publisher import InMemoryAuditEventPublisher
from creditos_integration.application.ports.mock_integration_adapter import (
    MockIntegrationAdapter,
    MockIntegrationAdapterRegistry,
)
from creditos_integration.application.service import (
    BuildIntegrationPlanCommand,
    ConfigureIntegrationClassCommand,
    ExecuteMockIntegrationCommand,
    IntegrationCatalogApplicationService,
)
from creditos_integration.domain.entities import (
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


def test_executes_four_mvp_classes_with_canonical_versioned_results() -> None:
    mock_registry = InMemoryMockIntegrationAdapterRegistry.for_mvp_defaults()
    service = _service(mock_adapter_registry=mock_registry)
    plan = _ready_plan(service)

    results = service.execute_mock_integration_plan(
        ExecuteMockIntegrationCommand(
            plan=plan,
            scopes=("integration_mock:execute",),
        ),
        context=_context(),
    )

    assert [result.integration_class for result in results] == [
        "anti_fraud",
        "credit_bureau",
        "kyc_kyb",
        "receivables",
    ]
    assert {result.schema_version for result in results} == {"1.0"}
    assert {result.status for result in results} == {"completed"}
    assert {result.scenario for result in results} == {"synthetic_success"}
    assert {result.tenant_id for result in results} == {"tenant-bridge-001"}
    assert any(result.duration_ms > 0 for result in results)
    assert mock_registry.execution_attempts == (
        ("anti_fraud", "mock-antifraud-v1", "synthetic_success"),
        ("credit_bureau", "mock-credit-bureau-v1", "synthetic_success"),
        ("kyc_kyb", "mock-kyc-basic-v1", "synthetic_success"),
        ("receivables", "mock-receivables-v1", "synthetic_success"),
    )
    assert service.logged_events[-1]["operation"] == "integration_mock.execute_plan"
    assert service.logged_events[-1]["status"] == "accepted"
    assert service.logged_events[-1]["extra"]["result_count"] == 4


def test_mock_execution_is_deterministic_for_same_input_and_scenario() -> None:
    service = _service()
    plan = _ready_plan(service)
    command = ExecuteMockIntegrationCommand(
        plan=plan,
        scenario_by_class={"anti_fraud": "synthetic_partial"},
        synthetic_subject_reference="synthetic-reference-001",
        scopes=("integration_mock:execute",),
    )

    first_results = service.execute_mock_integration_plan(command, context=_context())
    second_results = service.execute_mock_integration_plan(command, context=_context())

    assert [result.result_id for result in first_results] == [
        result.result_id for result in second_results
    ]
    assert [result.summary for result in first_results] == [
        result.summary for result in second_results
    ]
    assert [result.reason_codes for result in first_results] == [
        result.reason_codes for result in second_results
    ]


def test_supports_configurable_safe_synthetic_scenarios() -> None:
    service = _service()
    plan = _ready_plan(service)

    results = service.execute_mock_integration_plan(
        ExecuteMockIntegrationCommand(
            plan=plan,
            scenario_by_class={
                "anti_fraud": "synthetic_failure",
                "credit_bureau": "synthetic_not_found",
                "kyc_kyb": "synthetic_success",
                "receivables": "synthetic_partial",
            },
            scopes=("integration_mock:execute",),
        ),
        context=_context(),
    )

    assert {result.integration_class: result.status for result in results} == {
        "anti_fraud": "failed",
        "credit_bureau": "not_found",
        "kyc_kyb": "completed",
        "receivables": "partial",
    }
    assert {result.integration_class: result.reason_codes for result in results} == {
        "anti_fraud": ("synthetic_controlled_failure",),
        "credit_bureau": ("synthetic_subject_not_found",),
        "kyc_kyb": ("synthetic_match",),
        "receivables": ("synthetic_partial_data",),
    }


def test_rejects_prod_environment_before_any_adapter_execution() -> None:
    mock_registry = InMemoryMockIntegrationAdapterRegistry.for_mvp_defaults()
    service = _service(environment="prod", mock_adapter_registry=mock_registry)
    plan = _ready_plan(service)

    with pytest.raises(IntegrationValidationError) as error:
        service.execute_mock_integration_plan(
            ExecuteMockIntegrationCommand(plan=plan, scopes=("integration_mock:execute",)),
            context=_context(),
        )

    assert error.value.code == "mock_execution_not_allowed_in_production"
    assert mock_registry.execution_attempts == ()
    assert service.logged_events[-1]["status"] == "rejected"


@pytest.mark.parametrize("environment", ["production", "prd", "prod-us"])
def test_rejects_production_aliases_before_any_adapter_execution(environment: str) -> None:
    mock_registry = InMemoryMockIntegrationAdapterRegistry.for_mvp_defaults()
    service = _service(environment=environment, mock_adapter_registry=mock_registry)
    plan = _ready_plan(service)

    with pytest.raises(IntegrationValidationError) as error:
        service.execute_mock_integration_plan(
            ExecuteMockIntegrationCommand(plan=plan, scopes=("integration_mock:execute",)),
            context=_context(),
        )

    assert error.value.code == "mock_execution_not_allowed_in_production"
    assert mock_registry.execution_attempts == ()


def test_rejects_non_ready_plan_before_any_adapter_execution() -> None:
    mock_registry = InMemoryMockIntegrationAdapterRegistry.for_mvp_defaults()
    service = _service(mock_adapter_registry=mock_registry)
    plan = service.build_integration_plan(
        BuildIntegrationPlanCommand(
            product_type="personal_credit",
            required_classes=("kyc_kyb",),
        ),
        context=_context(),
    )

    with pytest.raises(IntegrationValidationError) as error:
        service.execute_mock_integration_plan(
            ExecuteMockIntegrationCommand(plan=plan, scopes=("integration_mock:execute",)),
            context=_context(),
        )

    assert error.value.code == "integration_plan_not_ready"
    assert mock_registry.execution_attempts == ()


def test_rejects_cross_tenant_plan_before_any_adapter_execution() -> None:
    mock_registry = InMemoryMockIntegrationAdapterRegistry.for_mvp_defaults()
    service = _service(mock_adapter_registry=mock_registry)
    plan = _ready_plan(service, tenant_id="tenant-bridge-001")

    with pytest.raises(IntegrationValidationError) as error:
        service.execute_mock_integration_plan(
            ExecuteMockIntegrationCommand(plan=plan, scopes=("integration_mock:execute",)),
            context=_context("tenant-bridge-002"),
        )

    assert error.value.code == "cross_tenant_integration_plan"
    assert mock_registry.execution_attempts == ()


def test_rejects_plan_item_from_another_tenant_before_any_adapter_execution() -> None:
    mock_registry = InMemoryMockIntegrationAdapterRegistry.for_mvp_defaults()
    service = _service(mock_adapter_registry=mock_registry)
    plan = _ready_plan(service)
    forged_plan = IntegrationPlan(
        tenant_id=plan.tenant_id,
        product_type=plan.product_type,
        status=plan.status,
        items=(
            IntegrationPlanItem(
                tenant_id="tenant-bridge-999",
                product_type=plan.product_type,
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
        service.execute_mock_integration_plan(
            ExecuteMockIntegrationCommand(plan=forged_plan, scopes=("integration_mock:execute",)),
            context=_context(),
        )

    assert error.value.code == "cross_tenant_integration_plan_item"
    assert mock_registry.execution_attempts == ()


def test_rejects_plan_item_from_another_product_before_any_adapter_execution() -> None:
    mock_registry = InMemoryMockIntegrationAdapterRegistry.for_mvp_defaults()
    service = _service(mock_adapter_registry=mock_registry)
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
        service.execute_mock_integration_plan(
            ExecuteMockIntegrationCommand(plan=forged_plan, scopes=("integration_mock:execute",)),
            context=_context(),
        )

    assert error.value.code == "cross_product_integration_plan_item"
    assert mock_registry.execution_attempts == ()


def test_rejects_unregistered_mock_adapter_before_any_execution() -> None:
    mock_registry = InMemoryMockIntegrationAdapterRegistry(())
    service = _service(mock_adapter_registry=mock_registry)
    plan = _ready_plan(service)

    with pytest.raises(IntegrationValidationError) as error:
        service.execute_mock_integration_plan(
            ExecuteMockIntegrationCommand(plan=plan, scopes=("integration_mock:execute",)),
            context=_context(),
        )

    assert error.value.code == "mock_adapter_not_registered"
    assert mock_registry.execution_attempts == ()


def test_rejects_later_unregistered_mock_adapter_before_partial_execution() -> None:
    first_adapter = InMemoryMockIntegrationAdapter(
        integration_class="anti_fraud",
        adapter_id="mock-antifraud-v1",
    )
    mock_registry = InMemoryMockIntegrationAdapterRegistry((first_adapter,))
    service = _service(mock_adapter_registry=mock_registry)
    plan = _ready_plan(service)

    with pytest.raises(IntegrationValidationError) as error:
        service.execute_mock_integration_plan(
            ExecuteMockIntegrationCommand(plan=plan, scopes=("integration_mock:execute",)),
            context=_context(),
        )

    assert error.value.code == "mock_adapter_not_registered"
    assert mock_registry.execution_attempts == ()


def test_rejects_unknown_scenario_class_and_logs_requested_traceability() -> None:
    mock_registry = InMemoryMockIntegrationAdapterRegistry.for_mvp_defaults()
    service = _service(mock_adapter_registry=mock_registry)
    plan = _ready_plan(service)

    with pytest.raises(IntegrationValidationError) as error:
        service.execute_mock_integration_plan(
            ExecuteMockIntegrationCommand(
                plan=plan,
                scenario_by_class={"open_finance": "synthetic_success"},
                scopes=("integration_mock:execute",),
            ),
            context=_context(),
        )

    assert error.value.code == "unknown_mock_scenario_class"
    assert mock_registry.execution_attempts == ()
    assert service.logged_events[-1]["extra"]["product_type"] == "personal_credit"
    assert service.logged_events[-1]["extra"]["integration_classes"] == [
        "anti_fraud",
        "credit_bureau",
        "kyc_kyb",
        "receivables",
    ]
    assert service.logged_events[-1]["extra"]["adapter_ids"] == [
        "mock-antifraud-v1",
        "mock-credit-bureau-v1",
        "mock-kyc-basic-v1",
        "mock-receivables-v1",
    ]


@pytest.mark.parametrize(
    "synthetic_subject_reference",
    [
        "00000000191",
        "synthetic-token",
        "real.person@example.com",
        "subject-without-prefix",
    ],
)
def test_rejects_non_synthetic_or_sensitive_subject_reference(
    synthetic_subject_reference: str,
) -> None:
    mock_registry = InMemoryMockIntegrationAdapterRegistry.for_mvp_defaults()
    service = _service(mock_adapter_registry=mock_registry)
    plan = _ready_plan(service)

    with pytest.raises(IntegrationValidationError):
        service.execute_mock_integration_plan(
            ExecuteMockIntegrationCommand(
                plan=plan,
                synthetic_subject_reference=synthetic_subject_reference,
                scopes=("integration_mock:execute",),
            ),
            context=_context(),
        )

    assert mock_registry.execution_attempts == ()


def test_rejects_adapter_result_that_does_not_match_plan_context() -> None:
    service = _service(mock_adapter_registry=MaliciousMockAdapterRegistry())
    plan = _ready_plan(service)

    with pytest.raises(IntegrationValidationError) as error:
        service.execute_mock_integration_plan(
            ExecuteMockIntegrationCommand(plan=plan, scopes=("integration_mock:execute",)),
            context=_context(),
        )

    assert error.value.code == "mock_result_tenant_mismatch"


def test_rejects_non_covered_class_before_any_adapter_execution() -> None:
    mock_registry = InMemoryMockIntegrationAdapterRegistry.for_mvp_defaults()
    service = _service(
        adapter_registry=InMemoryAdapterRegistry(
            _allowed_adapters() | {"open_finance": {"mock-open-finance-v1"}}
        ),
        mock_adapter_registry=mock_registry,
    )
    service.configure_integration_class(
        _configure_command(
            integration_class="open_finance",
            adapter_id="mock-open-finance-v1",
        ),
        context=_context(),
    )
    plan = service.build_integration_plan(
        BuildIntegrationPlanCommand(
            product_type="personal_credit",
            required_classes=("open_finance",),
        ),
        context=_context(),
    )

    with pytest.raises(IntegrationValidationError) as error:
        service.execute_mock_integration_plan(
            ExecuteMockIntegrationCommand(plan=plan, scopes=("integration_mock:execute",)),
            context=_context(),
        )

    assert error.value.code == "unsupported_mock_integration_class"
    assert mock_registry.execution_attempts == ()


def test_mock_logs_and_results_do_not_expose_sensitive_or_raw_payload_fragments() -> None:
    service = _service()
    plan = _ready_plan(service)

    results = service.execute_mock_integration_plan(
        ExecuteMockIntegrationCommand(
            plan=plan,
            synthetic_subject_reference="synthetic-reference-without-pii",
            scopes=("integration_mock:execute",),
        ),
        context=_context(),
    )

    serialized = json.dumps(
        {
            "logs": service.logged_events,
            "results": [result.to_log_safe_dict() for result in results],
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
    mock_adapter_registry: MockIntegrationAdapterRegistry | None = None,
    environment: str = "test",
) -> IntegrationCatalogApplicationService:
    return IntegrationCatalogApplicationService(
        repository=repository or InMemoryIntegrationCatalogRepository(),
        adapter_registry=adapter_registry or InMemoryAdapterRegistry(_allowed_adapters()),
        mock_adapter_registry=mock_adapter_registry
        or InMemoryMockIntegrationAdapterRegistry.for_mvp_defaults(),
        audit_publisher=InMemoryAuditEventPublisher(),
        environment=environment,
        clock=lambda: _FIXED_TIME,
        configuration_id_factory=lambda seed: f"icfg_{seed}",
    )


def _ready_plan(
    service: IntegrationCatalogApplicationService,
    *,
    tenant_id: str = "tenant-bridge-001",
) -> IntegrationPlan:
    for integration_class in _MVP_CLASSES:
        service.configure_integration_class(
            _configure_command(
                integration_class=integration_class,
                adapter_id=_ADAPTER_BY_CLASS[integration_class],
            ),
            context=_context(tenant_id),
        )
    plan = service.build_integration_plan(
        BuildIntegrationPlanCommand(
            product_type="personal_credit",
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
) -> ConfigureIntegrationClassCommand:
    return ConfigureIntegrationClassCommand(
        product_type=product_type,
        integration_class=integration_class,
        adapter_id=adapter_id,
        requirement="required",
        timeout_ms=1_500,
        max_attempts=2,
        max_concurrency=3,
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


def _allowed_adapters() -> dict[str, set[str]]:
    return {
        integration_class: {adapter_id}
        for integration_class, adapter_id in _ADAPTER_BY_CLASS.items()
    }


class MaliciousMockAdapterRegistry:
    def __init__(self) -> None:
        self.adapter = MismatchedTenantAdapter()

    def get_adapter(
        self,
        integration_class: str,
        adapter_id: str,
    ) -> MockIntegrationAdapter | None:
        if integration_class == "anti_fraud" and adapter_id == "mock-antifraud-v1":
            return self.adapter
        return InMemoryMockIntegrationAdapterRegistry.for_mvp_defaults().get_adapter(
            integration_class,
            adapter_id,
        )


class MismatchedTenantAdapter:
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
        return IntegrationResult.create(
            result_id="ires_mismatched_tenant_result",
            tenant_id="tenant-bridge-999",
            product_type=item.product_type,
            integration_class=item.integration_class,
            adapter_id=item.adapter_id,
            status="completed",
            scenario=scenario,
            reason_codes=("synthetic_match",),
            summary={
                "synthetic_data_type": "mock_integration_result",
                "risk_band": "low",
                "device_status": "trusted",
                "velocity_status": "normal",
            },
            correlation_id=context.correlation_id,
            trace_id=context.trace_id,
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=duration_ms,
        )
