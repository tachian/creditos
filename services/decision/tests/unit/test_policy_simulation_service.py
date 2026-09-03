from __future__ import annotations

from datetime import UTC, datetime

import pytest
from creditos_decision.adapters.persistence import (
    InMemoryCreditPolicyRepository,
    InMemoryPolicySimulationRepository,
    InMemoryReasonCodeCatalogRepository,
)
from creditos_decision.application.ports import (
    CreditPolicyAuditPublisher,
    DecisionAuditIntent,
    PolicySimulationAuditIntent,
)
from creditos_decision.application.service import (
    CreateCreditPolicyDraftCommand,
    DecisionApplicationService,
    GetPolicySimulationCommand,
    RunPolicySimulationCommand,
)
from creditos_decision.domain.entities import ReasonCodeCatalog
from creditos_decision.domain.errors import (
    PolicyNotFoundError,
    PolicySimulationNotFoundError,
    PolicyTenantContextError,
    PolicyValidationError,
)
from creditos_decision.domain.value_objects import (
    ExplainableFactor,
    PolicyApplicability,
    PolicyCriterion,
    PolicyFallbackAction,
    PolicyLimit,
    PolicyRule,
    PolicySimulationInputCase,
    ReasonCode,
)
from creditos_observability.context import ObservabilityContext
from creditos_security import PropagatedContext, TrustedContext

NOW = datetime(2026, 8, 27, 12, 0, tzinfo=UTC)


class RecordingAuditPublisher:
    def __init__(self) -> None:
        self.events: list[DecisionAuditIntent] = []

    def publish(self, event: DecisionAuditIntent) -> None:
        self.events.append(event)


def test_run_policy_simulation_persists_non_production_result_and_minimized_audit() -> None:
    audit = RecordingAuditPublisher()
    simulation_repository = InMemoryPolicySimulationRepository()
    service = _service(audit=audit, simulation_repository=simulation_repository)
    created = service.create_policy_draft(
        _create_policy_command(),
        context=_context("tenant_alpha"),
        trusted_context=_trusted_context(),
    )

    result = service.run_policy_simulation(
        RunPolicySimulationCommand(
            simulation_id="sim_personal_credit_001",
            policy_id=created.policy.policy_id,
            policy_version_id=created.policy.policy_version_id,
            cases=(
                PolicySimulationInputCase.create(
                    case_id="case_low_income_001",
                    values={
                        "monthly_income_units": 200_000,
                        "requested_amount_units": 700_000,
                        "requested_installments": 12,
                    },
                ),
            ),
        ),
        context=_context("tenant_alpha"),
        trusted_context=_trusted_context(),
    )

    stored = simulation_repository.get(
        tenant_id="tenant_alpha",
        simulation_id="sim_personal_credit_001",
    )
    assert stored == result.simulation
    assert result.simulation.non_production is True
    assert result.simulation.case_results[0].outcome == "reject"
    assert result.simulation.case_results[0].reason_code_refs == ("rc_low_income",)
    assert isinstance(audit.events[-1], PolicySimulationAuditIntent)
    assert audit.events[-1].event_type == "policy_simulation.completed"
    assert audit.events[-1].safe_details == {
        "case_count": "1",
        "fallback_action_request_more_data": "0",
        "fallback_action_reject_by_policy": "0",
        "fallback_action_unable_to_decide": "0",
        "fallback_applied_count": "0",
        "issue_count": "0",
        "non_production": "true",
        "operation": "policy_simulation.run",
        "outcome_approve": "0",
        "outcome_approve_with_changes": "0",
        "outcome_reject": "1",
        "outcome_request_more_data": "0",
        "outcome_unable_to_decide": "0",
        "required_data_case_count": "0",
        "status": "completed",
    }
    assert result.logs[0]["payload"] == "[OMITIDO]"
    assert "200000" not in str(result.logs[0])


def test_run_policy_simulation_counts_only_safely_applied_fallbacks() -> None:
    audit = RecordingAuditPublisher()
    service = _service(audit=audit)
    created = service.create_policy_draft(
        _create_policy_command(
            fallback_action=PolicyFallbackAction.create(
                action="reject_by_policy",
                reason_code_refs=("rc_low_income",),
            )
        ),
        context=_context("tenant_alpha"),
        trusted_context=_trusted_context(),
    )

    result = service.run_policy_simulation(
        RunPolicySimulationCommand(
            simulation_id="sim_reject_fallback_downgraded",
            policy_id=created.policy.policy_id,
            policy_version_id=created.policy.policy_version_id,
            cases=(
                PolicySimulationInputCase.create(
                    case_id="case_missing_limit_for_reject_fallback",
                    values={
                        "monthly_income_units": 300_000,
                        "requested_amount_units": 700_000,
                    },
                ),
            ),
        ),
        context=_context("tenant_alpha"),
        trusted_context=_trusted_context(),
    )

    assert result.simulation.case_results[0].outcome == "unable_to_decide"
    assert result.simulation.case_results[0].fallback_action == "reject_by_policy"
    assert result.simulation.case_results[0].required_data_refs == ("requested_installments",)
    assert isinstance(audit.events[-1], PolicySimulationAuditIntent)
    assert audit.events[-1].safe_details["fallback_applied_count"] == "0"
    assert audit.events[-1].safe_details["fallback_action_reject_by_policy"] == "0"
    assert audit.events[-1].safe_details["outcome_unable_to_decide"] == "1"
    assert audit.events[-1].safe_details["required_data_case_count"] == "1"


def test_run_policy_simulation_rejects_empty_dataset_with_log_safe_audit() -> None:
    audit = RecordingAuditPublisher()
    service = _service(audit=audit)
    created = service.create_policy_draft(
        _create_policy_command(),
        context=_context("tenant_alpha"),
        trusted_context=_trusted_context(),
    )

    with pytest.raises(PolicyValidationError) as error:
        service.run_policy_simulation(
            RunPolicySimulationCommand(
                simulation_id="sim_personal_credit_002",
                policy_id=created.policy.policy_id,
                policy_version_id=created.policy.policy_version_id,
                cases=(),
            ),
            context=_context("tenant_alpha"),
            trusted_context=_trusted_context(),
        )

    assert error.value.code == "empty_policy_simulation_dataset"
    assert isinstance(audit.events[-1], PolicySimulationAuditIntent)
    assert audit.events[-1].event_type == "policy_simulation.rejected"
    assert audit.events[-1].safe_details["case_count"] == "0"
    assert audit.events[-1].safe_details["non_production"] == "true"
    assert audit.events[-1].safe_details["rejection_reason"] == "empty_policy_simulation_dataset"
    assert audit.events[-1].safe_details["status"] == "rejected"


def test_run_policy_simulation_rejects_cross_tenant_without_revealing_policy() -> None:
    audit = RecordingAuditPublisher()
    simulation_repository = InMemoryPolicySimulationRepository()
    service = _service(audit=audit, simulation_repository=simulation_repository)
    created = service.create_policy_draft(
        _create_policy_command(),
        context=_context("tenant_alpha"),
        trusted_context=_trusted_context(),
    )

    with pytest.raises(PolicyNotFoundError):
        service.run_policy_simulation(
            RunPolicySimulationCommand(
                simulation_id="sim_cross_tenant_001",
                policy_id=created.policy.policy_id,
                policy_version_id=created.policy.policy_version_id,
                cases=(
                    PolicySimulationInputCase.create(
                        case_id="case_low_income_001",
                        values={
                            "monthly_income_units": 200_000,
                            "requested_amount_units": 700_000,
                            "requested_installments": 12,
                        },
                    ),
                ),
            ),
            context=_context("tenant_beta"),
            trusted_context=_trusted_context(tenant_id="tenant_beta"),
        )

    assert (
        simulation_repository.get(
            tenant_id="tenant_beta",
            simulation_id="sim_cross_tenant_001",
        )
        is None
    )
    assert audit.events[-1].event_type == "policy_simulation.rejected"
    assert audit.events[-1].safe_details["rejection_reason"] == "credit_policy_not_found"


def test_policy_simulation_rejection_audit_does_not_trust_unverified_tenant() -> None:
    audit = RecordingAuditPublisher()
    service = _service(audit=audit)

    with pytest.raises(PolicyTenantContextError):
        service.run_policy_simulation(
            RunPolicySimulationCommand(
                simulation_id="sim_untrusted_context_001",
                policy_id="pol_personal_credit_default",
                policy_version_id="polver_personal_credit_default_v1",
                cases=(_safe_case(),),
            ),
            context=_context("tenant_forged"),
            trusted_context=object(),  # type: ignore[arg-type]
        )

    assert isinstance(audit.events[-1], PolicySimulationAuditIntent)
    assert audit.events[-1].tenant_id == "unknown_tenant"
    assert audit.events[-1].actor_subject_id == "unknown_actor"
    assert audit.events[-1].safe_details["rejection_reason"] == ("policy_tenant_context_required")


def test_policy_simulation_is_removed_when_audit_publish_fails() -> None:
    audit = FailingSimulationAuditPublisher()
    simulation_repository = InMemoryPolicySimulationRepository()
    service = _service(audit=audit, simulation_repository=simulation_repository)
    created = service.create_policy_draft(
        _create_policy_command(),
        context=_context("tenant_alpha"),
        trusted_context=_trusted_context(),
    )

    with pytest.raises(RuntimeError, match="audit unavailable"):
        service.run_policy_simulation(
            RunPolicySimulationCommand(
                simulation_id="sim_personal_credit_rollback",
                policy_id=created.policy.policy_id,
                policy_version_id=created.policy.policy_version_id,
                cases=(_safe_case(),),
            ),
            context=_context("tenant_alpha"),
            trusted_context=_trusted_context(),
        )

    assert (
        simulation_repository.get(
            tenant_id="tenant_alpha",
            simulation_id="sim_personal_credit_rollback",
        )
        is None
    )


def test_get_policy_simulation_requires_policy_read_and_tenant_scope() -> None:
    audit = RecordingAuditPublisher()
    simulation_repository = InMemoryPolicySimulationRepository()
    service = _service(audit=audit, simulation_repository=simulation_repository)
    created = service.create_policy_draft(
        _create_policy_command(),
        context=_context("tenant_alpha"),
        trusted_context=_trusted_context(),
    )
    created_simulation = service.run_policy_simulation(
        RunPolicySimulationCommand(
            simulation_id="sim_personal_credit_read",
            policy_id=created.policy.policy_id,
            policy_version_id=created.policy.policy_version_id,
            cases=(_safe_case(),),
        ),
        context=_context("tenant_alpha"),
        trusted_context=_trusted_context(),
    )

    retrieved = service.get_policy_simulation(
        GetPolicySimulationCommand(simulation_id="sim_personal_credit_read"),
        context=_context("tenant_alpha"),
        trusted_context=_trusted_context(scopes=("policy:read",)),
    )

    assert retrieved == created_simulation.simulation
    with pytest.raises(PolicySimulationNotFoundError):
        service.get_policy_simulation(
            GetPolicySimulationCommand(simulation_id="sim_personal_credit_read"),
            context=_context("tenant_beta"),
            trusted_context=_trusted_context(
                tenant_id="tenant_beta",
                scopes=("policy:read",),
            ),
        )
    assert audit.events[-1].event_type == "policy_simulation.rejected"
    assert audit.events[-1].safe_details["rejection_reason"] == "policy_simulation_not_found"


class FailingSimulationAuditPublisher:
    def publish(self, event: DecisionAuditIntent) -> None:
        if (
            isinstance(event, PolicySimulationAuditIntent)
            and event.event_type == "policy_simulation.completed"
        ):
            raise RuntimeError("audit unavailable")


def _service(
    *,
    audit: CreditPolicyAuditPublisher,
    simulation_repository: InMemoryPolicySimulationRepository | None = None,
) -> DecisionApplicationService:
    return DecisionApplicationService(
        repository=InMemoryCreditPolicyRepository(),
        reason_code_catalog_repository=_reason_code_catalog_repository(),
        policy_simulation_repository=(
            simulation_repository or InMemoryPolicySimulationRepository()
        ),
        audit_publisher=audit,
        environment="test",
        clock=lambda: NOW,
    )


def _safe_case() -> PolicySimulationInputCase:
    return PolicySimulationInputCase.create(
        case_id="case_low_income_001",
        values={
            "monthly_income_units": 200_000,
            "requested_amount_units": 700_000,
            "requested_installments": 12,
        },
    )


def _create_policy_command(
    *,
    fallback_action: PolicyFallbackAction | None = None,
) -> CreateCreditPolicyDraftCommand:
    return CreateCreditPolicyDraftCommand(
        policy_id="pol_personal_credit_default",
        policy_version_id="polver_personal_credit_default_v1",
        reason_code_catalog_id="rcc_personal_credit_default",
        reason_code_catalog_version_id="rccver_personal_credit_default_v1",
        owner_subject_id="user_credit_manager",
        product_type="personal_credit",
        actor_subject_id="user_credit_manager",
        change_summary="Criação inicial da política padrão",
        applicability=PolicyApplicability.create(channels=("api", "checkout")),
        rules=(
            PolicyRule.create(
                rule_id="rule_low_income",
                name="Renda baixa",
                source_field="monthly_income_units",
                operator="lte",
                threshold_value=249_999,
                outcome="reject",
                reason_code_refs=("rc_low_income",),
            ),
            PolicyRule.create(
                rule_id="rule_sufficient_income",
                name="Renda suficiente",
                source_field="monthly_income_units",
                operator="gte",
                threshold_value=250_000,
                outcome="approve",
                reason_code_refs=("rc_sufficient_income",),
            ),
        ),
        criteria=(
            PolicyCriterion.create(
                criterion_id="criterion_requested_amount",
                field="requested_amount_units",
                operator="lte",
                value=1_000_000,
            ),
        ),
        limits=(
            PolicyLimit.create(
                limit_id="limit_max_installments",
                limit_type="max_installments",
                value=24,
            ),
        ),
        fallback_action=fallback_action,
    )


def _reason_code_catalog_repository() -> InMemoryReasonCodeCatalogRepository:
    repository = InMemoryReasonCodeCatalogRepository()
    repository.save_with_next_version(
        ReasonCodeCatalog.create_draft(
            catalog_id="rcc_personal_credit_default",
            catalog_version_id="rccver_personal_credit_default_v1",
            tenant_id="tenant_alpha",
            owner_subject_id="user_credit_manager",
            product_type="personal_credit",
            reason_codes=(
                ReasonCode.create(
                    reason_code_id="reason_low_income",
                    code="rc_low_income",
                    outcome="reject",
                    title="Renda baixa",
                    internal_description="Renda declarada abaixo da política",
                    external_description="Renda declarada insuficiente para aprovação",
                    factor_refs=("factor_monthly_income",),
                ),
                ReasonCode.create(
                    reason_code_id="reason_sufficient_income",
                    code="rc_sufficient_income",
                    outcome="approve",
                    title="Renda suficiente",
                    internal_description="Renda declarada atende a política",
                    external_description="Renda declarada compatível com aprovação",
                    factor_refs=("factor_monthly_income",),
                ),
            ),
            explainable_factors=(
                ExplainableFactor.create(
                    factor_id="factor_monthly_income",
                    field="monthly_income_units",
                    title="Renda declarada",
                    internal_description=("Renda mensal declarada em unidades monetárias menores"),
                    external_description="Renda declarada informada para análise",
                    required=True,
                ),
            ),
            now=NOW,
            actor_subject_id="user_credit_manager",
            correlation_id="corr_1234567890abcdef",
            change_summary="Criação inicial do catálogo",
        )
    )
    return repository


def _context(tenant_id: str | None) -> ObservabilityContext:
    return ObservabilityContext.new(
        correlation_id="corr_1234567890abcdef",
        request_id="req_1234567890abcdef",
        trace_id="1234567890abcdef1234567890abcdef",
        tenant_id=tenant_id,
        tenant_isolation_tier="bridge",
    )


def _trusted_context(
    *,
    tenant_id: str = "tenant_alpha",
    subject_id: str = "user_credit_manager",
    scopes: tuple[str, ...] = ("policy:write", "policy:read"),
) -> PropagatedContext:
    return PropagatedContext(
        trusted=TrustedContext(
            tenant_id=tenant_id,
            tenant_isolation_tier="bridge",
            subject_id=subject_id,
            scopes=scopes,
            roles=("credit-manager",),
            client_id="client_admin_console",
            principal_type="human",
        ),
        correlation_id="corr_1234567890abcdef",
        request_id="req_1234567890abcdef",
        traceparent="00-1234567890abcdef1234567890abcdef-1234567890abcdef-01",
    )
