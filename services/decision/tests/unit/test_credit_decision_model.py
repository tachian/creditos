from __future__ import annotations

from datetime import UTC, datetime

import pytest
from creditos_decision.domain.entities import CreditDecision, CreditPolicy, ReasonCodeCatalog
from creditos_decision.domain.errors import PolicyValidationError
from creditos_decision.domain.services.policy_evaluator import evaluate_policy_case
from creditos_decision.domain.value_objects import (
    CreditDecisionInput,
    CreditDecisionInputFieldValue,
    ExplainableFactor,
    PolicyApplicability,
    PolicyCriterion,
    PolicyEvaluationResult,
    PolicyLimit,
    PolicyRule,
    ReasonCode,
    input_fingerprint_for,
)

NOW = datetime(2026, 8, 30, 12, 0, tzinfo=UTC)


def test_credit_decision_creates_productive_snapshot_with_stable_fingerprint() -> None:
    policy = _published_policy()
    catalog = _published_catalog()
    decision_input = CreditDecisionInput.create(
        proposal_id="proposal_personal_credit_001",
        values={
            "monthly_income_units": 300_000,
            "requested_amount_units": 700_000,
            "requested_installments": 12,
            "requested_term_days": 360,
        },
        integration_result_refs=("integration_income_check_001",),
    )
    evaluation = evaluate_policy_case(
        policy=policy,
        catalog=catalog,
        evaluation_id=decision_input.proposal_id,
        field_values=decision_input.field_values,
    )

    decision = CreditDecision.create(
        decision_id="decision_personal_credit_001",
        policy=policy,
        catalog=catalog,
        decision_input=decision_input,
        evaluation=evaluation,
        channel="api",
        correlation_id="corr_1234567890abcdef",
        decided_at=NOW,
    )
    same_decision = CreditDecision.create(
        decision_id="decision_personal_credit_002",
        policy=policy,
        catalog=catalog,
        decision_input=decision_input,
        evaluation=evaluation,
        channel="api",
        correlation_id="corr_2234567890abcdef",
        decided_at=NOW.replace(hour=13),
    )

    assert decision.decision_id == "decision_personal_credit_001"
    assert decision.tenant_id == "tenant_alpha"
    assert decision.proposal_id == "proposal_personal_credit_001"
    assert decision.product_type == "personal_credit"
    assert decision.channel == "api"
    assert decision.outcome == "approve"
    assert decision.triggered_rule_ids == ("rule_approval_income",)
    assert decision.reason_code_refs == ("rc_min_income",)
    assert decision.factor_refs == ("factor_monthly_income",)
    assert decision.approved_terms is not None
    assert decision.approved_terms.approved_amount_units == 700_000
    assert decision.approved_terms.approved_installments == 12
    assert decision.approved_terms.approved_term_days == 360
    assert decision.decision_fingerprint == same_decision.decision_fingerprint
    assert "decision_personal_credit_001" not in decision.decision_fingerprint
    assert NOW.isoformat() not in decision.decision_fingerprint


def test_credit_decision_fingerprint_changes_with_canonical_input_values() -> None:
    policy = _published_policy()
    catalog = _published_catalog()
    first_input = CreditDecisionInput.create(
        proposal_id="proposal_personal_credit_001",
        values={
            "monthly_income_units": 300_000,
            "requested_amount_units": 700_000,
            "requested_installments": 12,
            "requested_term_days": 360,
        },
    )
    second_input = CreditDecisionInput.create(
        proposal_id="proposal_personal_credit_001",
        values={
            "monthly_income_units": 450_000,
            "requested_amount_units": 700_000,
            "requested_installments": 12,
            "requested_term_days": 360,
        },
    )
    first_evaluation = evaluate_policy_case(
        policy=policy,
        catalog=catalog,
        evaluation_id=first_input.proposal_id,
        field_values=first_input.field_values,
    )
    second_evaluation = evaluate_policy_case(
        policy=policy,
        catalog=catalog,
        evaluation_id=second_input.proposal_id,
        field_values=second_input.field_values,
    )

    first_decision = CreditDecision.create(
        decision_id="decision_personal_credit_001",
        policy=policy,
        catalog=catalog,
        decision_input=first_input,
        evaluation=first_evaluation,
        channel="api",
        correlation_id="corr_1234567890abcdef",
        decided_at=NOW,
    )
    second_decision = CreditDecision.create(
        decision_id="decision_personal_credit_002",
        policy=policy,
        catalog=catalog,
        decision_input=second_input,
        evaluation=second_evaluation,
        channel="api",
        correlation_id="corr_2234567890abcdef",
        decided_at=NOW.replace(hour=13),
    )

    assert first_decision.input_fingerprint != second_decision.input_fingerprint
    assert first_decision.decision_fingerprint != second_decision.decision_fingerprint


def test_credit_decision_rejects_approvals_without_complete_terms() -> None:
    policy = _published_policy()
    catalog = _published_catalog()
    decision_input = CreditDecisionInput.create(
        proposal_id="proposal_personal_credit_001",
        values={
            "monthly_income_units": 300_000,
            "requested_amount_units": 700_000,
            "requested_installments": 12,
        },
    )
    evaluation = PolicyEvaluationResult(
        evaluation_id=decision_input.proposal_id,
        outcome="approve",
        triggered_rule_ids=("rule_approval_income",),
        reason_code_refs=("rc_min_income",),
        factor_refs=("factor_monthly_income",),
    )

    with pytest.raises(PolicyValidationError, match="termos aprovados completos"):
        CreditDecision.create(
            decision_id="decision_personal_credit_001",
            policy=policy,
            catalog=catalog,
            decision_input=decision_input,
            evaluation=evaluation,
            channel="api",
            correlation_id="corr_1234567890abcdef",
            decided_at=NOW,
        )


def test_credit_decision_blocks_approve_with_changes_until_adjustment_model_exists() -> None:
    policy = _published_policy(rules=(_outcome_rule(outcome="approve_with_changes"),))
    catalog = _published_catalog_for_outcome(
        outcome="approve_with_changes",
        reason_code_ref="rc_approve_with_changes",
    )
    decision_input = CreditDecisionInput.create(
        proposal_id="proposal_approve_with_changes",
        values={
            "monthly_income_units": 300_000,
            "requested_amount_units": 700_000,
            "requested_installments": 12,
            "requested_term_days": 360,
        },
    )
    evaluation = evaluate_policy_case(
        policy=policy,
        catalog=catalog,
        evaluation_id=decision_input.proposal_id,
        field_values=decision_input.field_values,
    )

    with pytest.raises(PolicyValidationError, match="termos ajustados"):
        CreditDecision.create(
            decision_id="decision_approve_with_changes_001",
            policy=policy,
            catalog=catalog,
            decision_input=decision_input,
            evaluation=evaluation,
            channel="api",
            correlation_id="corr_1234567890abcdef",
            decided_at=NOW,
        )


def test_credit_decision_validates_catalog_provenance_and_evaluation_identity() -> None:
    policy = _published_policy()
    catalog = _published_catalog()
    decision_input = CreditDecisionInput.create(
        proposal_id="proposal_personal_credit_001",
        values={
            "monthly_income_units": 300_000,
            "requested_amount_units": 700_000,
            "requested_installments": 12,
            "requested_term_days": 360,
        },
    )
    evaluation = evaluate_policy_case(
        policy=policy,
        catalog=catalog,
        evaluation_id=decision_input.proposal_id,
        field_values=decision_input.field_values,
    )

    with pytest.raises(PolicyValidationError, match="proveniência"):
        CreditDecision.create(
            decision_id="decision_personal_credit_001",
            policy=policy,
            catalog=_published_catalog(
                catalog_id="rcc_personal_credit_alternative",
                catalog_version_id="rccver_personal_credit_alternative_v1",
            ),
            decision_input=decision_input,
            evaluation=evaluation,
            channel="api",
            correlation_id="corr_1234567890abcdef",
            decided_at=NOW,
        )

    mismatched_evaluation = PolicyEvaluationResult(
        evaluation_id="proposal_other",
        outcome=evaluation.outcome,
        triggered_rule_ids=evaluation.triggered_rule_ids,
        reason_code_refs=evaluation.reason_code_refs,
        factor_refs=evaluation.factor_refs,
    )
    with pytest.raises(PolicyValidationError, match="não pertence"):
        CreditDecision.create(
            decision_id="decision_personal_credit_002",
            policy=policy,
            catalog=catalog,
            decision_input=decision_input,
            evaluation=mismatched_evaluation,
            channel="api",
            correlation_id="corr_1234567890abcdef",
            decided_at=NOW,
        )


def test_credit_decision_direct_construction_validates_internal_refs() -> None:
    with pytest.raises(PolicyValidationError, match="identificador técnico inválido"):
        CreditDecision(
            decision_id="decision_personal_credit_001",
            tenant_id="tenant_alpha",
            proposal_id="proposal_personal_credit_001",
            product_type="personal_credit",
            channel="api",
            decided_at=NOW,
            policy_id="pol_personal_credit_default",
            policy_version_id="polver_personal_credit_default_v1",
            policy_revision=1,
            reason_code_catalog_id="rcc_personal_credit_default",
            reason_code_catalog_version_id="rccver_personal_credit_default_v1",
            outcome="reject",
            triggered_rule_ids=("rule with spaces",),
            reason_code_refs=(),
            factor_refs=(),
            validation_issues=(),
            integration_result_refs=(),
            input_fingerprint=input_fingerprint_for(
                CreditDecisionInput.create(
                    proposal_id="proposal_personal_credit_001",
                    values={
                        "monthly_income_units": 300_000,
                        "requested_amount_units": 700_000,
                        "requested_installments": 12,
                        "requested_term_days": 360,
                    },
                ).field_values
            ),
            correlation_id="corr_1234567890abcdef",
            decision_fingerprint="0" * 64,
        )


def test_credit_decision_rejects_sensitive_or_non_governed_input() -> None:
    with pytest.raises(PolicyValidationError, match="dado sensível ou campo proibido"):
        CreditDecisionInputFieldValue.create(field="email", value=1)

    with pytest.raises(PolicyValidationError, match="campo de política não governado"):
        CreditDecisionInputFieldValue.create(field="external_score_units", value=650)

    with pytest.raises(PolicyValidationError, match="identificador técnico inválido"):
        CreditDecisionInput.create(
            proposal_id="proposal_personal_credit_001",
            values={"monthly_income_units": 300_000},
            integration_result_refs=("payload 123.456.789-10",),
        )


def test_policy_evaluator_keeps_simulation_and_decision_semantics_aligned() -> None:
    result = evaluate_policy_case(
        policy=_published_policy(rules=(_rule(outcome="reject"), _approval_rule())),
        catalog=_published_catalog(include_reject=True),
        evaluation_id="proposal_conflicting_rules",
        field_values=CreditDecisionInput.create(
            proposal_id="proposal_conflicting_rules",
            values={
                "monthly_income_units": 300_000,
                "requested_amount_units": 700_000,
                "requested_installments": 12,
                "requested_term_days": 360,
            },
        ).field_values,
    )

    assert result.outcome == "unable_to_decide"
    assert result.triggered_rule_ids == ("rule_min_income", "rule_approval_income")
    assert result.reason_code_refs == ()
    assert result.validation_issues[0].code == "conflicting_policy_rule_outcomes"


@pytest.mark.parametrize(
    ("outcome", "reason_code_ref"),
    (
        ("approve", "rc_approve"),
        ("reject", "rc_reject"),
        ("approve_with_changes", "rc_approve_with_changes"),
        ("request_more_data", "rc_request_more_data"),
    ),
)
def test_policy_evaluator_supports_governed_outcomes(
    outcome: str,
    reason_code_ref: str,
) -> None:
    result = evaluate_policy_case(
        policy=_published_policy(rules=(_outcome_rule(outcome=outcome),)),
        catalog=_published_catalog_for_outcome(outcome=outcome, reason_code_ref=reason_code_ref),
        evaluation_id=f"proposal_{outcome}",
        field_values=CreditDecisionInput.create(
            proposal_id=f"proposal_{outcome}",
            values={
                "monthly_income_units": 300_000,
                "requested_amount_units": 700_000,
                "requested_installments": 12,
                "requested_term_days": 360,
            },
        ).field_values,
    )

    assert result.outcome == outcome
    assert result.reason_code_refs == (reason_code_ref,)
    assert result.factor_refs == ("factor_monthly_income",)


def _published_policy(
    *,
    rules: tuple[PolicyRule, ...] | None = None,
) -> CreditPolicy:
    return CreditPolicy.create_draft(
        policy_id="pol_personal_credit_default",
        policy_version_id="polver_personal_credit_default_v1",
        tenant_id="tenant_alpha",
        owner_subject_id="user_credit_manager",
        product_type="personal_credit",
        reason_code_catalog_id="rcc_personal_credit_default",
        reason_code_catalog_version_id="rccver_personal_credit_default_v1",
        applicability=PolicyApplicability.create(channels=("api",), starts_at=NOW),
        rules=rules or (_approval_rule(),),
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
        change_summary="Criação inicial da política padrão",
    ).publish(
        now=NOW,
        actor_subject_id="user_credit_manager",
        correlation_id="corr_2234567890abcdef",
        change_summary="Publicação da política",
    )


def _approval_rule() -> PolicyRule:
    return _rule(outcome="approve")


def _rule(*, outcome: str) -> PolicyRule:
    return PolicyRule.create(
        rule_id="rule_min_income" if outcome == "reject" else "rule_approval_income",
        name="Renda mínima declarada",
        source_field="monthly_income_units",
        operator="gte",
        threshold_value=250_000,
        outcome=outcome,
        reason_code_refs=("rc_min_income" if outcome == "approve" else "rc_reject_income",),
    )


def _outcome_rule(*, outcome: str) -> PolicyRule:
    return PolicyRule.create(
        rule_id=f"rule_{outcome}",
        name="Renda mínima declarada",
        source_field="monthly_income_units",
        operator="gte",
        threshold_value=250_000,
        outcome=outcome,
        reason_code_refs=(f"rc_{outcome}",),
    )


def _published_catalog_for_outcome(*, outcome: str, reason_code_ref: str) -> ReasonCodeCatalog:
    return ReasonCodeCatalog.create_draft(
        catalog_id="rcc_personal_credit_default",
        catalog_version_id="rccver_personal_credit_default_v1",
        tenant_id="tenant_alpha",
        owner_subject_id="user_credit_manager",
        product_type="personal_credit",
        reason_codes=(
            ReasonCode.create(
                reason_code_id=f"reason_{outcome}",
                code=reason_code_ref,
                outcome=outcome,
                title="Resultado governado",
                internal_description="Resultado determinístico governado",
                external_description="Resultado da política de crédito",
                factor_refs=("factor_monthly_income",),
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
            ),
        ),
        now=NOW,
        actor_subject_id="user_credit_manager",
        correlation_id="corr_1234567890abcdef",
        change_summary="Criação inicial do catálogo",
    ).publish(
        now=NOW,
        actor_subject_id="user_credit_manager",
        correlation_id="corr_2234567890abcdef",
        change_summary="Publicação do catálogo",
    )


def _published_catalog(
    *,
    include_reject: bool = False,
    catalog_id: str = "rcc_personal_credit_default",
    catalog_version_id: str = "rccver_personal_credit_default_v1",
) -> ReasonCodeCatalog:
    reason_codes = [
        ReasonCode.create(
            reason_code_id="reason_min_income",
            code="rc_min_income",
            outcome="approve",
            title="Renda mínima",
            internal_description="Renda declarada atende a política",
            external_description="Renda declarada compatível com aprovação",
            factor_refs=("factor_monthly_income",),
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
    return ReasonCodeCatalog.create_draft(
        catalog_id=catalog_id,
        catalog_version_id=catalog_version_id,
        tenant_id="tenant_alpha",
        owner_subject_id="user_credit_manager",
        product_type="personal_credit",
        reason_codes=tuple(reason_codes),
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
    ).publish(
        now=NOW,
        actor_subject_id="user_credit_manager",
        correlation_id="corr_2234567890abcdef",
        change_summary="Publicação do catálogo",
    )
