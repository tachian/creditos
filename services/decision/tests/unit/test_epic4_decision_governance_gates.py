from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import pytest
from creditos_decision.adapters.persistence import (
    InMemoryCreditDecisionRepository,
    InMemoryCreditPolicyRepository,
    InMemoryPolicySimulationRepository,
    InMemoryReasonCodeCatalogRepository,
)
from creditos_decision.application.ports import (
    CreditDecisionAuditIntent,
    CreditPolicyAuditIntent,
    CreditPolicyAuditPublisher,
    DecisionAuditIntent,
    PolicySimulationAuditIntent,
)
from creditos_decision.application.service import (
    CreateCreditPolicyDraftCommand,
    DecisionApplicationService,
    ExecuteCreditDecisionCommand,
    GetCreditDecisionCommand,
    PublishCreditPolicyCommand,
    RunPolicySimulationCommand,
)
from creditos_decision.domain.entities import CreditDecision, CreditPolicy, ReasonCodeCatalog
from creditos_decision.domain.errors import (
    CreditDecisionNotFoundError,
    PolicyTenantContextError,
    PolicyValidationError,
)
from creditos_decision.domain.value_objects import (
    CreditDecisionInput,
    CreditDecisionInputFieldValue,
    ExplainableFactor,
    PolicyApplicability,
    PolicyCriterion,
    PolicyEvaluationResult,
    PolicyLimit,
    PolicyRule,
    PolicySimulationInputCase,
    ReasonCode,
)
from creditos_observability.context import ObservabilityContext
from creditos_security import PropagatedContext, TrustedContext

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)


class RecordingAuditPublisher:
    def __init__(self) -> None:
        self.events: list[DecisionAuditIntent] = []

    def publish(self, event: DecisionAuditIntent) -> None:
        self.events.append(event)


def test_epic4_domain_gate_requires_policy_catalog_and_governed_reason_codes() -> None:
    policy = _published_policy()
    catalog = _published_catalog()
    decision = _decision(policy=policy, catalog=catalog)

    assert decision.policy_id == policy.policy_id
    assert decision.policy_version_id == policy.policy_version_id
    assert decision.policy_revision == policy.revision
    assert decision.reason_code_catalog_id == catalog.catalog_id
    assert decision.reason_code_catalog_version_id == catalog.catalog_version_id
    assert decision.reason_code_refs == ("rc_min_income",)
    assert decision.to_explainable_response(catalog=catalog).reason_codes[0].code == "rc_min_income"

    draft_policy = CreditPolicy.create_draft(
        policy_id="pol_personal_credit_default",
        policy_version_id="polver_personal_credit_default_v2",
        tenant_id="tenant_alpha",
        owner_subject_id="user_credit_manager",
        product_type="personal_credit",
        reason_code_catalog_id=catalog.catalog_id,
        reason_code_catalog_version_id=catalog.catalog_version_id,
        applicability=PolicyApplicability.create(channels=("api",), starts_at=NOW),
        rules=(_approval_rule(),),
        criteria=(_amount_criterion(),),
        limits=_policy_limits(),
        now=NOW,
        actor_subject_id="user_credit_manager",
        correlation_id="corr_epic4_domain_gate_001",
        change_summary="Criação de draft para gate",
    )
    with pytest.raises(PolicyValidationError, match="política publicada"):
        _decision(policy=draft_policy, catalog=catalog)

    draft_catalog = _draft_catalog()
    with pytest.raises(PolicyValidationError, match="catálogo publicado"):
        _decision(policy=policy, catalog=draft_catalog)


def test_epic4_determinism_gate_keeps_decision_fingerprint_stable_for_same_inputs() -> None:
    policy = _published_policy()
    catalog = _published_catalog()

    first_decision = _decision(
        decision_id="decision_personal_credit_a",
        decided_at=NOW,
        correlation_id="corr_epic4_determinism_a",
        policy=policy,
        catalog=catalog,
    )
    second_decision = _decision(
        decision_id="decision_personal_credit_b",
        decided_at=NOW + timedelta(minutes=5),
        correlation_id="corr_epic4_determinism_b",
        policy=policy,
        catalog=catalog,
    )

    assert first_decision.decision_fingerprint == second_decision.decision_fingerprint
    assert first_decision.input_fingerprint == second_decision.input_fingerprint
    assert first_decision.outcome == second_decision.outcome == "approve"
    assert first_decision.reason_code_refs == second_decision.reason_code_refs
    assert first_decision.triggered_rule_ids == second_decision.triggered_rule_ids


def test_epic4_simulation_publication_gate_preserves_non_production_and_critical_audit_order() -> (
    None
):
    repository = InMemoryCreditPolicyRepository()

    class VisibilityAuditPublisher(RecordingAuditPublisher):
        def __init__(self) -> None:
            super().__init__()
            self.published_visible_during_audit = False

        def publish(self, event: DecisionAuditIntent) -> None:
            super().publish(event)
            if isinstance(event, CreditPolicyAuditIntent) and event.event_type == (
                "credit_policy.published"
            ):
                self.published_visible_during_audit = bool(
                    repository.list_published_by_product(
                        tenant_id=event.tenant_id,
                        product_type="personal_credit",
                    )
                )

    audit = VisibilityAuditPublisher()
    service = _service(repository=repository, audit=audit)
    created = service.create_policy_draft(
        _create_policy_command(),
        context=_context(),
        trusted_context=_trusted_context(scopes=("policy:write", "policy:read")),
    )
    simulation = service.run_policy_simulation(
        RunPolicySimulationCommand(
            simulation_id="sim_epic4_publication_gate",
            policy_id=created.policy.policy_id,
            policy_version_id=created.policy.policy_version_id,
            cases=(_safe_simulation_case(),),
        ),
        context=_context(),
        trusted_context=_trusted_context(scopes=("policy:write", "policy:read")),
    )

    published = service.publish_policy(
        PublishCreditPolicyCommand(
            policy_id=created.policy.policy_id,
            policy_version_id=created.policy.policy_version_id,
            simulation_id=simulation.simulation.simulation_id,
            change_summary="Publicação aprovada pelo gate",
        ),
        context=_context(),
        trusted_context=_trusted_context(scopes=("policy:publish", "policy:read")),
    )

    assert simulation.simulation.non_production is True
    assert simulation.simulation.status == "completed"
    assert published.policy.status == "published"
    assert audit.published_visible_during_audit is False
    assert any(isinstance(event, PolicySimulationAuditIntent) for event in audit.events)
    assert any(
        isinstance(event, CreditPolicyAuditIntent) and event.event_type == "credit_policy.published"
        for event in audit.events
    )
    assert not any(isinstance(event, CreditDecisionAuditIntent) for event in audit.events)


def test_epic4_explainability_gate_requires_visible_justification_and_safe_output() -> None:
    policy = _published_policy()
    internal_only_catalog = _published_catalog(reason_code_audience="internal")
    decision = _decision(policy=policy, catalog=internal_only_catalog)

    with pytest.raises(PolicyValidationError) as customer_error:
        decision.to_explainable_response(catalog=internal_only_catalog, audience="customer")
    assert customer_error.value.code == "credit_decision_requires_customer_visible_reason_code"

    internal_explanation = decision.to_explainable_response(
        catalog=internal_only_catalog,
        audience="internal",
    )

    assert internal_explanation.reason_codes[0].description == ("Renda declarada atende a política")
    safe_output = _serialized(internal_explanation)
    assert "123.456.789-10" not in safe_output
    assert "cliente@example.com" not in safe_output
    assert "provider_payload" not in safe_output

    with pytest.raises(PolicyValidationError):
        ReasonCode.create(
            reason_code_id="reason_sensitive_description",
            code="rc_sensitive_description",
            outcome="approve",
            title="Justificativa sensível",
            internal_description="CPF 123.456.789-10 validado",
            external_description="cliente@example.com validado",
            factor_refs=("factor_monthly_income",),
            audience="both",
        )


def test_epic4_governance_gate_rejects_ai_or_provider_as_final_decision_authority() -> None:
    with pytest.raises(PolicyValidationError) as ai_rule_error:
        PolicyRule.create(
            rule_id="rule_ai_final_decision",
            name="Decisão final por IA",
            source_field="ai_decision",
            operator="eq",
            threshold_value="approve",
            outcome="approve",
            reason_code_refs=("rc_min_income",),
        )
    assert ai_rule_error.value.code == "unsupported_policy_field"

    with pytest.raises(PolicyValidationError) as provider_input_error:
        CreditDecisionInput.create(
            proposal_id="proposal_provider_direct_decision",
            values={"provider_payload": 1},
        )
    assert provider_input_error.value.code in {
        "sensitive_or_prohibited_policy_field",
        "unsupported_policy_field",
    }

    policy = _published_policy()
    catalog = _published_catalog()
    provider_driven_evaluation = PolicyEvaluationResult(
        evaluation_id="proposal_personal_credit_001",
        outcome="approve",
        triggered_rule_ids=("rule_provider_final",),
        reason_code_refs=("provider_approved",),
        factor_refs=(),
    )
    with pytest.raises(PolicyValidationError) as provider_reason_error:
        CreditDecision.create(
            decision_id="decision_provider_direct_001",
            policy=policy,
            catalog=catalog,
            decision_input=_decision_input(integration_result_refs=("integration_mock_approved",)),
            evaluation=provider_driven_evaluation,
            channel="api",
            correlation_id="corr_epic4_provider_gate",
            decided_at=NOW,
        )
    assert provider_reason_error.value.code == "unknown_reason_code"


def test_epic4_application_gate_enforces_bridge_scope_isolation_and_safe_traces() -> None:
    audit = RecordingAuditPublisher()
    decision_repository = InMemoryCreditDecisionRepository()
    service = _service(audit=audit, decision_repository=decision_repository)
    _create_and_publish_policy(service)

    result = service.execute_credit_decision(
        _execute_command(),
        context=_context(),
        trusted_context=_trusted_context(scopes=("decision:execute", "policy:read")),
    )
    fetched = service.get_credit_decision(
        GetCreditDecisionCommand(decision_id=result.decision.decision_id),
        context=_context(),
        trusted_context=_trusted_context(scopes=("decision:read", "policy:read")),
    )

    assert fetched.explanation.decision_id == result.decision.decision_id
    assert fetched.explanation.policy_id == result.decision.policy_id
    assert fetched.explanation.reason_codes
    assert result.logs[0]["payload"] == "[OMITIDO]"
    assert fetched.logs[0]["payload"] == "[OMITIDO]"
    assert any(
        isinstance(event, CreditDecisionAuditIntent)
        and event.safe_details["reason_code_count"] == "1"
        for event in audit.events
    )

    with pytest.raises(CreditDecisionNotFoundError):
        service.get_credit_decision(
            GetCreditDecisionCommand(decision_id=result.decision.decision_id),
            context=_context(tenant_id="tenant_beta"),
            trusted_context=_trusted_context(
                tenant_id="tenant_beta",
                scopes=("decision:read", "policy:read"),
            ),
        )

    with pytest.raises(PolicyTenantContextError):
        service.get_credit_decision(
            GetCreditDecisionCommand(decision_id=result.decision.decision_id),
            context=_context(),
            trusted_context=_trusted_context(
                scopes=("decision:read", "policy:read"),
                tenant_isolation_tier="silo",
            ),
        )


def _service(
    *,
    audit: CreditPolicyAuditPublisher,
    repository: InMemoryCreditPolicyRepository | None = None,
    catalog_repository: InMemoryReasonCodeCatalogRepository | None = None,
    simulation_repository: InMemoryPolicySimulationRepository | None = None,
    decision_repository: InMemoryCreditDecisionRepository | None = None,
) -> DecisionApplicationService:
    return DecisionApplicationService(
        repository=repository or InMemoryCreditPolicyRepository(),
        reason_code_catalog_repository=catalog_repository or _published_catalog_repository(),
        policy_simulation_repository=simulation_repository or InMemoryPolicySimulationRepository(),
        credit_decision_repository=decision_repository or InMemoryCreditDecisionRepository(),
        audit_publisher=audit,
        environment="test",
        clock=lambda: NOW,
    )


def _create_and_publish_policy(service: DecisionApplicationService) -> CreditPolicy:
    created = service.create_policy_draft(
        _create_policy_command(),
        context=_context(),
        trusted_context=_trusted_context(scopes=("policy:write", "policy:read")),
    )
    simulation = service.run_policy_simulation(
        RunPolicySimulationCommand(
            simulation_id="sim_epic4_execution_gate",
            policy_id=created.policy.policy_id,
            policy_version_id=created.policy.policy_version_id,
            cases=(_safe_simulation_case(),),
        ),
        context=_context(),
        trusted_context=_trusted_context(scopes=("policy:write", "policy:read")),
    )
    return service.publish_policy(
        PublishCreditPolicyCommand(
            policy_id=created.policy.policy_id,
            policy_version_id=created.policy.policy_version_id,
            simulation_id=simulation.simulation.simulation_id,
            change_summary="Publicação para gate de decisão",
        ),
        context=_context(),
        trusted_context=_trusted_context(scopes=("policy:publish", "policy:read")),
    ).policy


def _create_policy_command() -> CreateCreditPolicyDraftCommand:
    return CreateCreditPolicyDraftCommand(
        policy_id="pol_personal_credit_default",
        policy_version_id="polver_personal_credit_default_v1",
        reason_code_catalog_id="rcc_personal_credit_default",
        reason_code_catalog_version_id="rccver_personal_credit_default_v1",
        owner_subject_id="user_credit_manager",
        product_type="personal_credit",
        actor_subject_id="user_credit_manager",
        change_summary="Criação inicial da política padrão",
        applicability=PolicyApplicability.create(
            channels=("api",),
            starts_at=NOW + timedelta(days=1),
            ends_at=NOW + timedelta(days=31),
        ),
        rules=(_approval_rule(),),
        criteria=(_amount_criterion(),),
        limits=_policy_limits(),
    )


def _published_policy() -> CreditPolicy:
    return CreditPolicy.create_draft(
        policy_id="pol_personal_credit_default",
        policy_version_id="polver_personal_credit_default_v1",
        tenant_id="tenant_alpha",
        owner_subject_id="user_credit_manager",
        product_type="personal_credit",
        reason_code_catalog_id="rcc_personal_credit_default",
        reason_code_catalog_version_id="rccver_personal_credit_default_v1",
        applicability=PolicyApplicability.create(channels=("api",), starts_at=NOW),
        rules=(_approval_rule(),),
        criteria=(_amount_criterion(),),
        limits=_policy_limits(),
        now=NOW,
        actor_subject_id="user_credit_manager",
        correlation_id="corr_epic4_policy_create",
        change_summary="Criação inicial da política padrão",
    ).publish(
        now=NOW,
        actor_subject_id="user_credit_manager",
        correlation_id="corr_epic4_policy_publish",
        change_summary="Publicação da política",
    )


def _approval_rule() -> PolicyRule:
    return PolicyRule.create(
        rule_id="rule_min_income",
        name="Renda mínima declarada",
        source_field="monthly_income_units",
        operator="gte",
        threshold_value=250_000,
        outcome="approve",
        reason_code_refs=("rc_min_income",),
    )


def _amount_criterion() -> PolicyCriterion:
    return PolicyCriterion.create(
        criterion_id="criterion_requested_amount",
        field="requested_amount_units",
        operator="lte",
        value=1_000_000,
    )


def _policy_limits() -> tuple[PolicyLimit, ...]:
    return (
        PolicyLimit.create(
            limit_id="limit_max_installments",
            limit_type="max_installments",
            value=24,
        ),
        PolicyLimit.create(
            limit_id="limit_max_term_days",
            limit_type="max_term_days",
            value=720,
        ),
    )


def _published_catalog_repository() -> InMemoryReasonCodeCatalogRepository:
    repository = InMemoryReasonCodeCatalogRepository()
    repository.save_with_next_version(_published_catalog())
    return repository


def _published_catalog(*, reason_code_audience: str = "both") -> ReasonCodeCatalog:
    return _draft_catalog(reason_code_audience=reason_code_audience).publish(
        now=NOW,
        actor_subject_id="user_credit_manager",
        correlation_id="corr_epic4_catalog_publish",
        change_summary="Publicação do catálogo",
    )


def _draft_catalog(*, reason_code_audience: str = "both") -> ReasonCodeCatalog:
    return ReasonCodeCatalog.create_draft(
        catalog_id="rcc_personal_credit_default",
        catalog_version_id="rccver_personal_credit_default_v1",
        tenant_id="tenant_alpha",
        owner_subject_id="user_credit_manager",
        product_type="personal_credit",
        reason_codes=(
            ReasonCode.create(
                reason_code_id="reason_min_income",
                code="rc_min_income",
                outcome="approve",
                title="Renda mínima",
                internal_description="Renda declarada atende a política",
                external_description="Renda declarada compatível com aprovação",
                factor_refs=("factor_monthly_income",),
                audience=reason_code_audience,
            ),
        ),
        explainable_factors=(
            ExplainableFactor.create(
                factor_id="factor_monthly_income",
                field="monthly_income_units",
                title="Renda declarada",
                internal_description="Renda mensal declarada em unidades monetárias menores",
                external_description="Renda declarada informada para análise",
                required=True,
                audience=reason_code_audience,
            ),
        ),
        now=NOW,
        actor_subject_id="user_credit_manager",
        correlation_id="corr_epic4_catalog_create",
        change_summary="Criação inicial do catálogo",
    )


def _decision(
    *,
    policy: CreditPolicy,
    catalog: ReasonCodeCatalog,
    decision_id: str = "decision_personal_credit_001",
    decided_at: datetime = NOW,
    correlation_id: str = "corr_epic4_decision",
) -> CreditDecision:
    return CreditDecision.create(
        decision_id=decision_id,
        policy=policy,
        catalog=catalog,
        decision_input=_decision_input(),
        evaluation=PolicyEvaluationResult(
            evaluation_id="proposal_personal_credit_001",
            outcome="approve",
            triggered_rule_ids=("rule_min_income",),
            reason_code_refs=("rc_min_income",),
            factor_refs=("factor_monthly_income",),
        ),
        channel="api",
        correlation_id=correlation_id,
        decided_at=decided_at,
    )


def _decision_input(
    *,
    integration_result_refs: tuple[str, ...] = (),
) -> CreditDecisionInput:
    return CreditDecisionInput.create(
        proposal_id="proposal_personal_credit_001",
        values={
            "monthly_income_units": 300_000,
            "requested_amount_units": 700_000,
            "requested_installments": 12,
            "requested_term_days": 360,
        },
        integration_result_refs=integration_result_refs,
    )


def _execute_command() -> ExecuteCreditDecisionCommand:
    return ExecuteCreditDecisionCommand(
        decision_id="decision_personal_credit_001",
        proposal_id="proposal_personal_credit_001",
        product_type="personal_credit",
        channel="api",
        effective_at=NOW + timedelta(days=2),
        field_values=(
            CreditDecisionInputFieldValue.create(field="monthly_income_units", value=300_000),
            CreditDecisionInputFieldValue.create(field="requested_amount_units", value=700_000),
            CreditDecisionInputFieldValue.create(field="requested_installments", value=12),
            CreditDecisionInputFieldValue.create(field="requested_term_days", value=360),
        ),
        integration_result_refs=("integration_mock_approved",),
    )


def _safe_simulation_case() -> PolicySimulationInputCase:
    return PolicySimulationInputCase.create(
        case_id="case_income_001",
        values={
            "monthly_income_units": 300_000,
            "requested_amount_units": 700_000,
            "requested_installments": 12,
            "requested_term_days": 360,
        },
    )


def _context(*, tenant_id: str = "tenant_alpha") -> ObservabilityContext:
    return ObservabilityContext.new(
        correlation_id="corr_epic4_context_001",
        request_id="req_epic4_context_001",
        trace_id="1" * 32,
        tenant_id=tenant_id,
        tenant_isolation_tier="bridge",
    )


def _trusted_context(
    *,
    tenant_id: str = "tenant_alpha",
    scopes: tuple[str, ...],
    tenant_isolation_tier: str = "bridge",
) -> PropagatedContext:
    return PropagatedContext(
        trusted=TrustedContext(
            tenant_id=tenant_id,
            tenant_isolation_tier=tenant_isolation_tier,
            subject_id="user_credit_manager",
            scopes=scopes,
            roles=("credit_manager",),
            client_id="client_creditos_tests",
        ),
        correlation_id="corr_epic4_context_001",
        request_id="req_epic4_context_001",
        traceparent=f"00-{'1' * 32}-{'2' * 16}-01",
    )


def _serialized(value: object) -> str:
    serializable = (
        asdict(cast(Any, value)) if is_dataclass(value) and not isinstance(value, type) else value
    )
    return json.dumps(serializable, default=str, sort_keys=True)
