from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from creditos_decision.adapters.persistence import (
    InMemoryCreditDecisionRepository,
    InMemoryCreditPolicyRepository,
    InMemoryPolicySimulationRepository,
    InMemoryReasonCodeCatalogRepository,
)
from creditos_decision.application.ports import (
    CreditDecisionAuditIntent,
    CreditPolicyAuditPublisher,
    DecisionAuditIntent,
)
from creditos_decision.application.service import (
    CreateCreditPolicyDraftCommand,
    DecisionApplicationService,
    ExecuteCreditDecisionCommand,
    GetCreditDecisionByProposalCommand,
    GetCreditDecisionCommand,
    PublishCreditPolicyCommand,
    RunPolicySimulationCommand,
)
from creditos_decision.domain.entities import CreditPolicy, ReasonCodeCatalog
from creditos_decision.domain.errors import (
    CreditDecisionNotFoundError,
    PolicyNotFoundError,
    PolicyTenantContextError,
    PolicyValidationError,
    ReasonCodeCatalogNotFoundError,
)
from creditos_decision.domain.value_objects import (
    CreditDecisionInputFieldValue,
    ExplainableFactor,
    PolicyApplicability,
    PolicyCriterion,
    PolicyLimit,
    PolicyRule,
    PolicySimulationInputCase,
    ReasonCode,
)
from creditos_observability.context import ObservabilityContext
from creditos_security import PropagatedContext, TrustedContext

NOW = datetime(2026, 8, 30, 12, 0, tzinfo=UTC)


class RecordingAuditPublisher:
    def __init__(self) -> None:
        self.events: list[DecisionAuditIntent] = []

    def publish(self, event: DecisionAuditIntent) -> None:
        self.events.append(event)


def test_execute_credit_decision_persists_productive_decision_with_minimized_audit() -> None:
    audit = RecordingAuditPublisher()
    decision_repository = InMemoryCreditDecisionRepository()
    service = _service(audit=audit, decision_repository=decision_repository)
    published_policy = _create_and_publish_policy(service)

    result = service.execute_credit_decision(
        ExecuteCreditDecisionCommand(
            decision_id="decision_personal_credit_001",
            proposal_id="proposal_personal_credit_001",
            product_type="personal_credit",
            channel="api",
            effective_at=NOW + timedelta(days=2),
            field_values=_decision_field_values(),
            integration_result_refs=("integration_income_check_001",),
        ),
        context=_context("tenant_alpha"),
        trusted_context=_trusted_context(scopes=("decision:execute", "policy:read")),
    )

    stored = decision_repository.get(
        tenant_id="tenant_alpha",
        decision_id="decision_personal_credit_001",
    )
    assert stored == result.decision
    assert result.decision.policy_id == published_policy.policy_id
    assert result.decision.policy_version_id == published_policy.policy_version_id
    assert result.decision.policy_revision == published_policy.revision
    assert result.decision.outcome == "approve"
    assert result.explanation.decision_id == result.decision.decision_id
    assert result.explanation.status == "completed"
    assert result.explanation.reason_codes[0].description == (
        "Renda declarada compatível com aprovação"
    )
    assert result.explanation.factors[0].description == "Renda declarada informada para análise"
    assert result.explanation.policy_version_id == published_policy.policy_version_id
    assert result.explanation.decision_fingerprint == result.decision.decision_fingerprint
    assert "300000" not in str(result.explanation)
    assert result.decision.reason_code_refs == ("rc_min_income",)
    assert result.decision.factor_refs == ("factor_monthly_income",)
    assert result.logs[0]["payload"] == "[OMITIDO]"
    assert "fallback_action" not in result.logs[0]["extra"]
    assert "300000" not in str(result.logs[0])
    event = audit.events[-1]
    assert isinstance(event, CreditDecisionAuditIntent)
    assert event.event_type == "credit_decision.completed"
    assert event.tenant_id == "tenant_alpha"
    assert event.decision_id == "decision_personal_credit_001"
    assert event.proposal_id == "proposal_personal_credit_001"
    assert event.reason_code_catalog_id == "rcc_personal_credit_default"
    assert event.reason_code_catalog_version_id == "rccver_personal_credit_default_v1"
    assert event.safe_details["channel"] == "api"
    assert event.safe_details["duration_ms"]
    assert event.safe_details["factor_count"] == "1"
    assert "fallback_action" not in event.safe_details
    assert event.safe_details["fingerprint"] == result.decision.decision_fingerprint
    assert event.safe_details["operation"] == "credit_decision.execute"
    assert event.safe_details["outcome"] == "approve"
    assert event.safe_details["policy_id"] == published_policy.policy_id
    assert event.safe_details["policy_revision"] == str(published_policy.revision)
    assert event.safe_details["policy_version_id"] == published_policy.policy_version_id
    assert event.safe_details["product_type"] == "personal_credit"
    assert event.safe_details["reason_code_catalog_id"] == "rcc_personal_credit_default"
    assert (
        event.safe_details["reason_code_catalog_version_id"] == "rccver_personal_credit_default_v1"
    )
    assert event.safe_details["reason_code_count"] == "1"
    assert event.safe_details["reason_code_refs"] == "rc_min_income"
    assert event.safe_details["status"] == "completed"
    assert event.safe_details["triggered_rule_count"] == "1"
    assert event.safe_details["validation_issue_count"] == "0"


def test_get_credit_decision_returns_explainable_response_by_id_and_proposal() -> None:
    audit = RecordingAuditPublisher()
    decision_repository = InMemoryCreditDecisionRepository()
    service = _service(audit=audit, decision_repository=decision_repository)
    _create_and_publish_policy(service)
    executed = service.execute_credit_decision(
        _execute_command(),
        context=_context("tenant_alpha"),
        trusted_context=_trusted_context(scopes=("decision:execute", "policy:read")),
    )

    by_id = service.get_credit_decision(
        GetCreditDecisionCommand(decision_id=executed.decision.decision_id),
        context=_context("tenant_alpha"),
        trusted_context=_trusted_context(scopes=("decision:read",)),
    )
    by_proposal = service.get_credit_decision_by_proposal(
        GetCreditDecisionByProposalCommand(proposal_id=executed.decision.proposal_id),
        context=_context("tenant_alpha"),
        trusted_context=_trusted_context(scopes=("decision:read",)),
    )

    assert by_id.explanation == by_proposal.explanation
    assert by_id.explanation.decision_id == "decision_personal_credit_001"
    assert by_id.explanation.proposal_id == "proposal_personal_credit_001"
    assert by_id.explanation.reason_codes[0].code == "rc_min_income"
    assert by_id.explanation.triggered_rule_ids == ("rule_min_income",)
    assert by_id.logs[0]["operation"] == "credit_decision.explanation.get"
    assert by_id.logs[0]["payload"] == "[OMITIDO]"
    assert by_id.logs[0]["extra"]["reason_code_count"] == 1
    assert "300000" not in str(by_id.logs[0])
    assert isinstance(audit.events[-1], CreditDecisionAuditIntent)
    assert audit.events[-1].event_type == "credit_decision.explanation_retrieved"
    assert audit.events[-1].safe_details["operation"] == "credit_decision.explanation.get"
    assert audit.events[-1].safe_details["audience"] == "customer"
    assert audit.events[-1].safe_details["reason_code_count"] == "1"
    assert audit.events[-1].safe_details["factor_count"] == "1"


def test_get_credit_decision_requires_read_scope_and_hides_cross_tenant_decisions() -> None:
    audit = RecordingAuditPublisher()
    decision_repository = InMemoryCreditDecisionRepository()
    service = _service(audit=audit, decision_repository=decision_repository)
    _create_and_publish_policy(service)
    service.execute_credit_decision(
        _execute_command(),
        context=_context("tenant_alpha"),
        trusted_context=_trusted_context(scopes=("decision:execute", "policy:read")),
    )

    with pytest.raises(PolicyTenantContextError, match="escopo obrigatório ausente"):
        service.get_credit_decision(
            GetCreditDecisionCommand(decision_id="decision_personal_credit_001"),
            context=_context("tenant_alpha"),
            trusted_context=_trusted_context(scopes=("policy:read",)),
        )

    with pytest.raises(CreditDecisionNotFoundError):
        service.get_credit_decision(
            GetCreditDecisionCommand(decision_id="decision_personal_credit_001"),
            context=_context("tenant_beta"),
            trusted_context=_trusted_context(
                tenant_id="tenant_beta",
                scopes=("decision:read",),
            ),
        )
    assert service.logged_events[-1]["extra"]["decision_id"] == "decision_personal_credit_001"

    with pytest.raises(CreditDecisionNotFoundError):
        service.get_credit_decision_by_proposal(
            GetCreditDecisionByProposalCommand(proposal_id="proposal_personal_credit_001"),
            context=_context("tenant_beta"),
            trusted_context=_trusted_context(
                tenant_id="tenant_beta",
                scopes=("decision:read",),
            ),
        )
    assert service.logged_events[-1]["extra"]["proposal_id"] == "proposal_personal_credit_001"

    with pytest.raises(PolicyTenantContextError, match="tier de tenant não suportado"):
        service.get_credit_decision(
            GetCreditDecisionCommand(decision_id="decision_personal_credit_001"),
            context=_context("tenant_alpha", tenant_isolation_tier="silo"),
            trusted_context=_trusted_context(
                scopes=("decision:read",),
                tenant_isolation_tier="silo",
            ),
        )


def test_get_credit_decision_blocks_internal_explanation_without_explicit_scope() -> None:
    audit = RecordingAuditPublisher()
    service = _service(audit=audit)
    _create_and_publish_policy(service)
    service.execute_credit_decision(
        _execute_command(),
        context=_context("tenant_alpha"),
        trusted_context=_trusted_context(scopes=("decision:execute", "policy:read")),
    )

    with pytest.raises(PolicyTenantContextError, match="escopo obrigatório ausente"):
        service.get_credit_decision(
            GetCreditDecisionCommand(
                decision_id="decision_personal_credit_001",
                audience="internal",
            ),
            context=_context("tenant_alpha"),
            trusted_context=_trusted_context(scopes=("decision:read",)),
        )

    result = service.get_credit_decision(
        GetCreditDecisionCommand(
            decision_id="decision_personal_credit_001",
            audience="internal",
        ),
        context=_context("tenant_alpha"),
        trusted_context=_trusted_context(
            scopes=("decision:read", "decision:explain:internal"),
        ),
    )

    assert result.explanation.reason_codes[0].description == "Renda declarada atende a política"
    assert result.logs[0]["extra"]["audience"] == "internal"
    assert audit.events[-1].safe_details["audience"] == "internal"


def test_execute_credit_decision_does_not_persist_without_customer_visible_explanation() -> None:
    audit = RecordingAuditPublisher()
    decision_repository = InMemoryCreditDecisionRepository()
    service = _service(
        audit=audit,
        decision_repository=decision_repository,
        catalog_repository=_published_catalog_repository(reason_code_audience="internal"),
    )
    _create_and_publish_policy(service)

    with pytest.raises(PolicyValidationError, match="justificativa governada"):
        service.execute_credit_decision(
            _execute_command(),
            context=_context("tenant_alpha"),
            trusted_context=_trusted_context(scopes=("decision:execute", "policy:read")),
        )

    assert (
        decision_repository.get(
            tenant_id="tenant_alpha",
            decision_id="decision_personal_credit_001",
        )
        is None
    )
    assert audit.events[-1].event_type == "credit_decision.rejected"


def test_get_credit_decision_rejection_after_lookup_keeps_known_safe_metadata() -> None:
    audit = RecordingAuditPublisher()
    decision_repository = InMemoryCreditDecisionRepository()
    bootstrap_service = _service(
        audit=audit,
        decision_repository=decision_repository,
    )
    _create_and_publish_policy(bootstrap_service)
    bootstrap_service.execute_credit_decision(
        _execute_command(),
        context=_context("tenant_alpha"),
        trusted_context=_trusted_context(scopes=("decision:execute", "policy:read")),
    )
    broken_service = _service(
        audit=audit,
        decision_repository=decision_repository,
        catalog_repository=InMemoryReasonCodeCatalogRepository(),
    )

    with pytest.raises(ReasonCodeCatalogNotFoundError):
        broken_service.get_credit_decision(
            GetCreditDecisionCommand(decision_id="decision_personal_credit_001"),
            context=_context("tenant_alpha"),
            trusted_context=_trusted_context(scopes=("decision:read",)),
        )

    event = audit.events[-1]
    assert isinstance(event, CreditDecisionAuditIntent)
    assert event.event_type == "credit_decision.rejected"
    assert event.policy_id == "pol_personal_credit_default"
    assert event.reason_code_catalog_id == "rcc_personal_credit_default"
    assert event.safe_details["outcome"] == "approve"
    assert event.safe_details["reason_code_count"] == "1"
    assert broken_service.logged_events[-1]["extra"]["decision_id"] == (
        "decision_personal_credit_001"
    )
    assert broken_service.logged_events[-1]["extra"]["policy_id"] == "pol_personal_credit_default"


def test_execute_credit_decision_has_stable_fingerprint_and_controls_duplicate_proposal() -> None:
    audit = RecordingAuditPublisher()
    decision_repository = InMemoryCreditDecisionRepository()
    service = _service(audit=audit, decision_repository=decision_repository)
    _create_and_publish_policy(service)
    command = ExecuteCreditDecisionCommand(
        decision_id="decision_personal_credit_001",
        proposal_id="proposal_personal_credit_001",
        product_type="personal_credit",
        channel="api",
        effective_at=NOW + timedelta(days=2),
        field_values=_decision_field_values(),
    )

    first = service.execute_credit_decision(
        command,
        context=_context("tenant_alpha"),
        trusted_context=_trusted_context(scopes=("decision:execute", "policy:read")),
    )

    with pytest.raises(Exception, match="decisão duplicada"):
        service.execute_credit_decision(
            ExecuteCreditDecisionCommand(
                proposal_id="proposal_personal_credit_001",
                product_type="personal_credit",
                channel="api",
                effective_at=NOW + timedelta(days=2),
                field_values=_decision_field_values(),
            ),
            context=_context("tenant_alpha"),
            trusted_context=_trusted_context(scopes=("decision:execute", "policy:read")),
        )
    rejected_event = audit.events[-1]
    assert isinstance(rejected_event, CreditDecisionAuditIntent)
    assert rejected_event.event_type == "credit_decision.rejected"
    assert rejected_event.decision_id.startswith("decision_")
    assert rejected_event.decision_id != "unknown_credit_decision"
    assert rejected_event.proposal_id == "proposal_personal_credit_001"

    recalculated = service.execute_credit_decision(
        ExecuteCreditDecisionCommand(
            decision_id="decision_personal_credit_003",
            proposal_id="proposal_personal_credit_002",
            product_type="personal_credit",
            channel="api",
            effective_at=NOW + timedelta(days=2),
            field_values=_decision_field_values(),
        ),
        context=_context("tenant_alpha"),
        trusted_context=_trusted_context(scopes=("decision:execute", "policy:read")),
    )
    assert first.decision.decision_fingerprint != recalculated.decision.decision_fingerprint


def test_execute_credit_decision_never_approves_missing_fields_or_conflicting_rules() -> None:
    audit = RecordingAuditPublisher()
    service = _service(audit=audit)
    _create_and_publish_policy(service)

    missing = service.execute_credit_decision(
        ExecuteCreditDecisionCommand(
            decision_id="decision_missing_fields_001",
            proposal_id="proposal_missing_fields_001",
            product_type="personal_credit",
            channel="api",
            effective_at=NOW + timedelta(days=2),
            field_values=(
                CreditDecisionInputFieldValue.create(
                    field="requested_amount_units",
                    value=700_000,
                ),
            ),
        ),
        context=_context("tenant_alpha"),
        trusted_context=_trusted_context(scopes=("decision:execute", "policy:read")),
    )
    assert missing.decision.outcome == "request_more_data"
    assert missing.decision.fallback_action == "request_more_data"
    assert missing.decision.required_data_refs == (
        "monthly_income_units",
        "requested_installments",
        "requested_term_days",
    )
    assert missing.decision.reason_code_refs == ()
    assert missing.decision.validation_issues[0].code == "missing_limit_field"
    missing_event = audit.events[-1]
    assert isinstance(missing_event, CreditDecisionAuditIntent)
    assert missing_event.safe_details["fallback_action"] == "request_more_data"
    assert missing_event.safe_details["channel"] == "api"
    assert missing_event.safe_details["policy_id"] == "pol_personal_credit_default"
    assert missing_event.safe_details["required_data_count"] == "3"
    assert missing_event.safe_details["required_data_refs"] == (
        "monthly_income_units,requested_installments,requested_term_days"
    )
    assert missing_event.safe_details["validation_issue_codes"] == (
        "missing_limit_field,missing_rule_field,no_policy_rule_triggered"
    )
    assert "700000" not in str(missing_event.safe_details)
    assert missing.logs[0]["payload"] == "[OMITIDO]"
    assert missing.logs[0]["extra"]["channel"] == "api"
    assert missing.logs[0]["extra"]["fallback_action"] == "request_more_data"
    assert missing.logs[0]["extra"]["required_data_count"] == 3
    assert missing.logs[0]["extra"]["required_data_refs"] == [
        "monthly_income_units",
        "requested_installments",
        "requested_term_days",
    ]
    assert missing.logs[0]["extra"]["validation_issue_codes"] == [
        "missing_limit_field",
        "missing_rule_field",
        "no_policy_rule_triggered",
    ]
    assert "700000" not in str(missing.logs[0])

    conflict_repository = InMemoryCreditPolicyRepository()
    conflict_service = _service(
        audit=RecordingAuditPublisher(),
        repository=conflict_repository,
        catalog_repository=_published_catalog_repository(include_reject=True),
    )
    conflict_repository.save(
        _published_policy_direct(
            rules=(
                _rule(rule_id="rule_reject_income", outcome="reject"),
                _rule(rule_id="rule_approve_income", outcome="approve"),
            ),
        )
    )
    conflict = conflict_service.execute_credit_decision(
        ExecuteCreditDecisionCommand(
            decision_id="decision_conflict_001",
            proposal_id="proposal_conflict_001",
            product_type="personal_credit",
            channel="api",
            effective_at=NOW + timedelta(days=2),
            field_values=_decision_field_values(),
        ),
        context=_context("tenant_alpha"),
        trusted_context=_trusted_context(scopes=("decision:execute", "policy:read")),
    )
    assert conflict.decision.outcome == "unable_to_decide"
    assert conflict.decision.reason_code_refs == ()
    assert conflict.decision.validation_issues[0].code == "conflicting_policy_rule_outcomes"


def test_execute_credit_decision_requires_published_applicable_policy_and_execute_scope() -> None:
    service = _service(audit=RecordingAuditPublisher())
    created = service.create_policy_draft(
        _create_policy_command(),
        context=_context("tenant_alpha"),
        trusted_context=_trusted_context(scopes=("policy:write", "policy:read")),
    )

    with pytest.raises(PolicyTenantContextError, match="escopo obrigatório ausente"):
        service.execute_credit_decision(
            _execute_command(),
            context=_context("tenant_alpha"),
            trusted_context=_trusted_context(scopes=("policy:read",)),
        )

    with pytest.raises(PolicyNotFoundError):
        service.execute_credit_decision(
            _execute_command(effective_at=NOW + timedelta(days=2)),
            context=_context("tenant_alpha"),
            trusted_context=_trusted_context(scopes=("decision:execute", "policy:read")),
        )

    assert created.policy.status == "draft"


def test_execute_credit_decision_is_not_visible_when_audit_fails() -> None:
    class FailingDecisionAuditPublisher:
        def publish(self, event: DecisionAuditIntent) -> None:
            if isinstance(event, CreditDecisionAuditIntent):
                raise RuntimeError("audit unavailable")

    policy_repository = InMemoryCreditPolicyRepository()
    catalog_repository = _published_catalog_repository()
    simulation_repository = InMemoryPolicySimulationRepository()
    decision_repository = InMemoryCreditDecisionRepository()
    bootstrap_service = _service(
        audit=RecordingAuditPublisher(),
        repository=policy_repository,
        catalog_repository=catalog_repository,
        simulation_repository=simulation_repository,
        decision_repository=decision_repository,
    )
    _create_and_publish_policy(bootstrap_service)
    failing_service = _service(
        audit=FailingDecisionAuditPublisher(),
        repository=policy_repository,
        catalog_repository=catalog_repository,
        simulation_repository=simulation_repository,
        decision_repository=decision_repository,
    )

    with pytest.raises(RuntimeError, match="audit unavailable"):
        failing_service.execute_credit_decision(
            _execute_command(),
            context=_context("tenant_alpha"),
            trusted_context=_trusted_context(scopes=("decision:execute", "policy:read")),
        )

    assert (
        decision_repository.get(
            tenant_id="tenant_alpha",
            decision_id="decision_personal_credit_001",
        )
        is None
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


def _create_and_publish_policy(
    service: DecisionApplicationService,
    *,
    rules: tuple[PolicyRule, ...] | None = None,
):
    created = service.create_policy_draft(
        _create_policy_command(rules=rules),
        context=_context("tenant_alpha"),
        trusted_context=_trusted_context(scopes=("policy:write", "policy:read")),
    )
    simulation = service.run_policy_simulation(
        RunPolicySimulationCommand(
            simulation_id=f"sim_{created.policy.policy_version_id}",
            policy_id=created.policy.policy_id,
            policy_version_id=created.policy.policy_version_id,
            cases=(
                PolicySimulationInputCase.create(
                    case_id="case_income_001",
                    values={
                        "monthly_income_units": 300_000,
                        "requested_amount_units": 700_000,
                        "requested_installments": 12,
                        "requested_term_days": 360,
                    },
                ),
            ),
        ),
        context=_context("tenant_alpha"),
        trusted_context=_trusted_context(scopes=("policy:write", "policy:read")),
    )
    return service.publish_policy(
        PublishCreditPolicyCommand(
            policy_id=created.policy.policy_id,
            policy_version_id=created.policy.policy_version_id,
            simulation_id=simulation.simulation.simulation_id,
            change_summary="Publicação aprovada após simulação",
        ),
        context=_context("tenant_alpha"),
        trusted_context=_trusted_context(scopes=("policy:publish", "policy:read")),
    ).policy


def _execute_command(
    *,
    effective_at: datetime | None = None,
) -> ExecuteCreditDecisionCommand:
    return ExecuteCreditDecisionCommand(
        decision_id="decision_personal_credit_001",
        proposal_id="proposal_personal_credit_001",
        product_type="personal_credit",
        channel="api",
        effective_at=effective_at or NOW + timedelta(days=2),
        field_values=_decision_field_values(),
    )


def _decision_field_values() -> tuple[CreditDecisionInputFieldValue, ...]:
    return (
        CreditDecisionInputFieldValue.create(field="monthly_income_units", value=300_000),
        CreditDecisionInputFieldValue.create(field="requested_amount_units", value=700_000),
        CreditDecisionInputFieldValue.create(field="requested_installments", value=12),
        CreditDecisionInputFieldValue.create(field="requested_term_days", value=360),
    )


def _create_policy_command(
    *,
    rules: tuple[PolicyRule, ...] | None = None,
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
        applicability=PolicyApplicability.create(
            channels=("api",),
            starts_at=NOW + timedelta(days=1),
            ends_at=NOW + timedelta(days=31),
        ),
        rules=rules or (_rule(rule_id="rule_min_income", outcome="approve"),),
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
            PolicyLimit.create(
                limit_id="limit_max_term_days",
                limit_type="max_term_days",
                value=720,
            ),
        ),
    )


def _published_policy_direct(*, rules: tuple[PolicyRule, ...]) -> CreditPolicy:
    return CreditPolicy.create_draft(
        policy_id="pol_personal_credit_default",
        policy_version_id="polver_personal_credit_default_v1",
        tenant_id="tenant_alpha",
        owner_subject_id="user_credit_manager",
        product_type="personal_credit",
        reason_code_catalog_id="rcc_personal_credit_default",
        reason_code_catalog_version_id="rccver_personal_credit_default_v1",
        applicability=PolicyApplicability.create(
            channels=("api",),
            starts_at=NOW + timedelta(days=1),
            ends_at=NOW + timedelta(days=31),
        ),
        rules=rules,
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
            PolicyLimit.create(
                limit_id="limit_max_term_days",
                limit_type="max_term_days",
                value=720,
            ),
        ),
        now=NOW,
        actor_subject_id="user_credit_manager",
        correlation_id="corr_1234567890abcdef",
        change_summary="Criação direta para teste de conflito produtivo",
    ).publish(
        now=NOW,
        actor_subject_id="user_credit_manager",
        correlation_id="corr_2234567890abcdef",
        change_summary="Publicação direta para teste de conflito produtivo",
    )


def _rule(*, rule_id: str, outcome: str) -> PolicyRule:
    return PolicyRule.create(
        rule_id=rule_id,
        name="Renda mínima declarada",
        source_field="monthly_income_units",
        operator="gte",
        threshold_value=250_000,
        outcome=outcome,
        reason_code_refs=("rc_reject_income" if outcome == "reject" else "rc_min_income",),
    )


def _published_catalog_repository(
    *,
    include_reject: bool = False,
    reason_code_audience: str = "both",
) -> InMemoryReasonCodeCatalogRepository:
    repository = InMemoryReasonCodeCatalogRepository()
    draft = ReasonCodeCatalog.create_draft(
        catalog_id="rcc_personal_credit_default",
        catalog_version_id="rccver_personal_credit_default_v1",
        tenant_id="tenant_alpha",
        owner_subject_id="user_credit_manager",
        product_type="personal_credit",
        reason_codes=_reason_codes(
            include_reject=include_reject,
            reason_code_audience=reason_code_audience,
        ),
        explainable_factors=(
            ExplainableFactor.create(
                factor_id="factor_monthly_income",
                field="monthly_income_units",
                title="Renda declarada",
                internal_description="Renda mensal declarada em unidades monetárias menores",
                external_description="Renda declarada informada para análise",
                required=True,
            ),
        ),
        now=NOW,
        actor_subject_id="user_credit_manager",
        correlation_id="corr_1234567890abcdef",
        change_summary="Criação inicial do catálogo",
    )
    repository.save_with_next_version(
        draft.publish(
            now=NOW,
            actor_subject_id="user_credit_manager",
            correlation_id="corr_2234567890abcdef",
            change_summary="Publicação do catálogo",
        )
    )
    return repository


def _reason_codes(
    *,
    include_reject: bool,
    reason_code_audience: str = "both",
) -> tuple[ReasonCode, ...]:
    reason_codes = [
        ReasonCode.create(
            reason_code_id="reason_min_income",
            code="rc_min_income",
            outcome="approve",
            title="Renda mínima",
            internal_description="Renda declarada atende a política",
            external_description="Renda declarada compatível com aprovação",
            factor_refs=("factor_monthly_income",),
            audience=reason_code_audience,
        )
    ]
    if include_reject:
        reason_codes.append(
            ReasonCode.create(
                reason_code_id="reason_reject_income",
                code="rc_reject_income",
                outcome="reject",
                title="Renda insuficiente",
                internal_description="Renda declarada fora da política",
                external_description="Renda declarada insuficiente para aprovação",
                factor_refs=("factor_monthly_income",),
            )
        )
    return tuple(reason_codes)


def _context(
    tenant_id: str | None,
    *,
    tenant_isolation_tier: str = "bridge",
) -> ObservabilityContext:
    return ObservabilityContext.new(
        correlation_id="corr_1234567890abcdef",
        request_id="req_1234567890abcdef",
        trace_id="1234567890abcdef1234567890abcdef",
        tenant_id=tenant_id,
        tenant_isolation_tier=tenant_isolation_tier,
    )


def _trusted_context(
    *,
    tenant_id: str = "tenant_alpha",
    tenant_isolation_tier: str = "bridge",
    subject_id: str = "user_credit_manager",
    scopes: tuple[str, ...] = ("decision:execute", "policy:read"),
) -> PropagatedContext:
    return PropagatedContext(
        trusted=TrustedContext(
            tenant_id=tenant_id,
            tenant_isolation_tier=tenant_isolation_tier,
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
