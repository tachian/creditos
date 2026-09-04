from __future__ import annotations

from datetime import UTC, datetime

import pytest
from creditos_decision.domain.entities import CreditDecision, CreditPolicy, ReasonCodeCatalog
from creditos_decision.domain.errors import PolicyValidationError
from creditos_decision.domain.services.policy_evaluator import evaluate_policy_case
from creditos_decision.domain.value_objects import (
    CreditDecisionApprovedTerms,
    CreditDecisionExplanationResponse,
    CreditDecisionInput,
    CreditDecisionInputFieldValue,
    ExplainableFactor,
    PolicyApplicability,
    PolicyCriterion,
    PolicyEvaluationResult,
    PolicyFallbackAction,
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


def test_credit_decision_fingerprint_changes_with_channel() -> None:
    policy = _published_policy(
        applicability=PolicyApplicability.create(channels=("api", "partner"), starts_at=NOW)
    )
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

    api_decision = CreditDecision.create(
        decision_id="decision_personal_credit_001",
        policy=policy,
        catalog=catalog,
        decision_input=decision_input,
        evaluation=evaluation,
        channel="api",
        correlation_id="corr_1234567890abcdef",
        decided_at=NOW,
    )
    partner_decision = CreditDecision.create(
        decision_id="decision_personal_credit_002",
        policy=policy,
        catalog=catalog,
        decision_input=decision_input,
        evaluation=evaluation,
        channel="partner",
        correlation_id="corr_2234567890abcdef",
        decided_at=NOW.replace(hour=13),
    )

    assert api_decision.decision_fingerprint != partner_decision.decision_fingerprint


def test_credit_decision_allows_approval_terms_even_when_policy_does_not_reference_them() -> None:
    policy = _published_policy(
        criteria=(
            PolicyCriterion.create(
                criterion_id="criterion_min_income",
                field="monthly_income_units",
                operator="gte",
                value=250_000,
            ),
        ),
        limits=(
            PolicyLimit.create(
                limit_id="limit_max_amount",
                limit_type="max_amount_units",
                value=1_000_000,
            ),
        ),
    )
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

    assert decision.outcome == "approve"
    assert decision.approved_terms is not None
    assert decision.approved_terms.approved_installments == 12
    assert decision.approved_terms.approved_term_days == 360


def test_credit_decision_builds_customer_safe_explainable_response() -> None:
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

    explanation = decision.to_explainable_response(catalog=catalog, audience="customer")

    assert explanation.decision_id == "decision_personal_credit_001"
    assert explanation.proposal_id == "proposal_personal_credit_001"
    assert explanation.tenant_id == "tenant_alpha"
    assert explanation.status == "completed"
    assert explanation.outcome == "approve"
    assert explanation.policy_id == policy.policy_id
    assert explanation.policy_version_id == policy.policy_version_id
    assert explanation.reason_code_catalog_version_id == catalog.catalog_version_id
    assert explanation.triggered_rule_ids == ("rule_approval_income",)
    assert explanation.reason_codes[0].code == "rc_min_income"
    assert explanation.reason_codes[0].description == "Renda declarada compatível com aprovação"
    assert "atende a política" not in str(explanation)
    assert explanation.factors[0].factor_id == "factor_monthly_income"
    assert explanation.factors[0].description == "Renda declarada informada para análise"
    assert explanation.approved_terms is not None
    assert explanation.decision_fingerprint == decision.decision_fingerprint
    assert "300000" not in str(explanation)
    assert "field_values" not in str(explanation)


def test_credit_decision_blocks_final_outcome_without_customer_visible_reason_code() -> None:
    policy = _published_policy()
    catalog = _published_catalog(reason_code_audience="internal")
    decision_input = CreditDecisionInput.create(
        proposal_id="proposal_internal_reason_only",
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
    decision = CreditDecision.create(
        decision_id="decision_internal_reason_only",
        policy=policy,
        catalog=catalog,
        decision_input=decision_input,
        evaluation=evaluation,
        channel="api",
        correlation_id="corr_1234567890abcdef",
        decided_at=NOW,
    )

    with pytest.raises(PolicyValidationError, match="justificativa governada"):
        decision.to_explainable_response(catalog=catalog, audience="customer")


def test_credit_decision_blocks_final_outcome_without_governed_justification() -> None:
    policy = _published_policy()
    catalog = _published_catalog()
    decision_input = CreditDecisionInput.create(
        proposal_id="proposal_missing_justification",
        values={
            "monthly_income_units": 300_000,
            "requested_amount_units": 700_000,
            "requested_installments": 12,
            "requested_term_days": 360,
        },
    )
    evaluation = PolicyEvaluationResult(
        evaluation_id=decision_input.proposal_id,
        outcome="approve",
        triggered_rule_ids=("rule_approval_income",),
        reason_code_refs=(),
        factor_refs=(),
    )

    with pytest.raises(PolicyValidationError, match="justificativa governada"):
        CreditDecision.create(
            decision_id="decision_missing_justification",
            policy=policy,
            catalog=catalog,
            decision_input=decision_input,
            evaluation=evaluation,
            channel="api",
            correlation_id="corr_1234567890abcdef",
            decided_at=NOW,
        )


def test_credit_decision_allows_controlled_state_with_equivalent_justification() -> None:
    policy = _published_policy()
    catalog = _published_catalog()
    decision_input = CreditDecisionInput.create(
        proposal_id="proposal_request_more_data",
        values={
            "monthly_income_units": 300_000,
            "requested_amount_units": 700_000,
            "requested_term_days": 360,
        },
    )
    evaluation = evaluate_policy_case(
        policy=policy,
        catalog=catalog,
        evaluation_id=decision_input.proposal_id,
        field_values=decision_input.field_values,
    )
    decision = CreditDecision.create(
        decision_id="decision_request_more_data",
        policy=policy,
        catalog=catalog,
        decision_input=decision_input,
        evaluation=evaluation,
        channel="api",
        correlation_id="corr_1234567890abcdef",
        decided_at=NOW,
    )

    explanation = decision.to_explainable_response(catalog=catalog, audience="customer")

    assert explanation.status == "requires_input"
    assert explanation.outcome == "request_more_data"
    assert explanation.reason_codes == ()
    assert explanation.required_data_refs == ("requested_installments",)
    assert explanation.validation_issue_codes == ("missing_limit_field",)
    assert explanation.fallback_action == "request_more_data"


def test_credit_decision_blocks_controlled_state_without_visible_equivalent_justification() -> None:
    policy = _published_policy()
    catalog = _published_catalog_for_outcome(
        outcome="request_more_data",
        reason_code_ref="rc_request_more_data",
        reason_code_audience="internal",
    )
    decision_input = CreditDecisionInput.create(
        proposal_id="proposal_hidden_controlled_reason",
        values={
            "monthly_income_units": 300_000,
            "requested_amount_units": 700_000,
            "requested_installments": 12,
            "requested_term_days": 360,
        },
    )
    evaluation = PolicyEvaluationResult(
        evaluation_id=decision_input.proposal_id,
        outcome="request_more_data",
        triggered_rule_ids=("rule_request_more_data",),
        reason_code_refs=("rc_request_more_data",),
        factor_refs=("factor_monthly_income",),
    )
    decision = CreditDecision.create(
        decision_id="decision_hidden_controlled_reason",
        policy=policy,
        catalog=catalog,
        decision_input=decision_input,
        evaluation=evaluation,
        channel="api",
        correlation_id="corr_1234567890abcdef",
        decided_at=NOW,
    )

    with pytest.raises(PolicyValidationError, match="justificativa equivalente"):
        decision.to_explainable_response(catalog=catalog, audience="customer")


def test_credit_decision_explanation_rejects_invalid_status_and_detailed_numeric_text() -> None:
    with pytest.raises(PolicyValidationError, match="valor não suportado"):
        CreditDecisionExplanationResponse(
            decision_id="decision_invalid_status",
            proposal_id="proposal_invalid_status",
            tenant_id="tenant_alpha",
            product_type="personal_credit",
            channel="api",
            status="completed_but_wrong",
            outcome="approve",
            decided_at=NOW,
            correlation_id="corr_1234567890abcdef",
            policy_id="pol_personal_credit_default",
            policy_version_id="polver_personal_credit_default_v1",
            policy_revision=1,
            reason_code_catalog_id="rcc_personal_credit_default",
            reason_code_catalog_version_id="rccver_personal_credit_default_v1",
            triggered_rule_ids=("rule_approval_income",),
            reason_codes=(),
            factors=(),
            fallback_action=None,
            required_data_refs=(),
            validation_issue_codes=(),
            validation_issues=(),
            approved_terms=None,
            decision_fingerprint="a" * 64,
        )

    catalog = _published_catalog(external_description="Renda 300000 compatível")
    decision_input = CreditDecisionInput.create(
        proposal_id="proposal_numeric_description",
        values={
            "monthly_income_units": 300_000,
            "requested_amount_units": 700_000,
            "requested_installments": 12,
            "requested_term_days": 360,
        },
    )
    evaluation = evaluate_policy_case(
        policy=_published_policy(),
        catalog=catalog,
        evaluation_id=decision_input.proposal_id,
        field_values=decision_input.field_values,
    )
    decision = CreditDecision.create(
        decision_id="decision_numeric_description",
        policy=_published_policy(),
        catalog=catalog,
        decision_input=decision_input,
        evaluation=evaluation,
        channel="api",
        correlation_id="corr_1234567890abcdef",
        decided_at=NOW,
    )

    with pytest.raises(PolicyValidationError, match="valor numérico detalhado"):
        decision.to_explainable_response(catalog=catalog, audience="customer")


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


def test_credit_decision_blocks_approve_with_changes_without_real_adjustment() -> None:
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

    assert evaluation.outcome == "unable_to_decide"
    assert evaluation.validation_issues[0].code == "approve_with_changes_adjustment_not_available"

    decision = CreditDecision.create(
        decision_id="decision_approve_with_changes_001",
        policy=policy,
        catalog=catalog,
        decision_input=decision_input,
        evaluation=evaluation,
        channel="api",
        correlation_id="corr_1234567890abcdef",
        decided_at=NOW,
    )

    assert decision.outcome == "unable_to_decide"
    assert decision.approved_terms is None


def test_credit_decision_allows_approve_with_changes_with_governed_adjusted_terms() -> None:
    policy = _published_policy(
        rules=(_outcome_rule(outcome="approve_with_changes"),),
        limits=(
            PolicyLimit.create(
                limit_id="limit_max_amount",
                limit_type="max_amount_units",
                value=600_000,
            ),
            PolicyLimit.create(
                limit_id="limit_max_installments",
                limit_type="max_installments",
                value=10,
            ),
            PolicyLimit.create(
                limit_id="limit_max_term_days",
                limit_type="max_term_days",
                value=300,
            ),
        ),
    )
    catalog = _published_catalog_for_outcome(
        outcome="approve_with_changes",
        reason_code_ref="rc_approve_with_changes",
    )
    decision_input = CreditDecisionInput.create(
        proposal_id="proposal_approve_with_changes_adjusted",
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

    decision = CreditDecision.create(
        decision_id="decision_approve_with_changes_001",
        policy=policy,
        catalog=catalog,
        decision_input=decision_input,
        evaluation=evaluation,
        channel="api",
        correlation_id="corr_1234567890abcdef",
        decided_at=NOW,
    )

    assert decision.outcome == "approve_with_changes"
    assert decision.approved_terms is not None
    assert decision.approved_terms.approved_amount_units == 600_000
    assert decision.approved_terms.approved_installments == 10
    assert decision.approved_terms.approved_term_days == 300


@pytest.mark.parametrize(
    ("outcome", "reason_code_ref", "expected_status"),
    (
        ("reject", "rc_reject", "completed"),
        ("approve_with_changes", "rc_approve_with_changes", "completed"),
    ),
)
def test_credit_decision_explanation_supports_final_governed_outcomes(
    outcome: str,
    reason_code_ref: str,
    expected_status: str,
) -> None:
    policy_limits = None
    if outcome == "approve_with_changes":
        policy_limits = (
            PolicyLimit.create(
                limit_id="limit_max_installments",
                limit_type="max_installments",
                value=10,
            ),
        )
    policy = _published_policy(
        rules=(_outcome_rule(outcome=outcome),),
        limits=policy_limits,
    )
    catalog = _published_catalog_for_outcome(outcome=outcome, reason_code_ref=reason_code_ref)
    decision_input = CreditDecisionInput.create(
        proposal_id=f"proposal_{outcome}_explanation",
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
    decision = CreditDecision.create(
        decision_id=f"decision_{outcome}_explanation",
        policy=policy,
        catalog=catalog,
        decision_input=decision_input,
        evaluation=evaluation,
        channel="api",
        correlation_id="corr_1234567890abcdef",
        decided_at=NOW,
    )

    explanation = decision.to_explainable_response(catalog=catalog)

    assert explanation.status == expected_status
    assert explanation.outcome == outcome
    assert explanation.reason_codes[0].code == reason_code_ref
    assert explanation.factors[0].factor_id == "factor_monthly_income"
    assert "300000" not in str(explanation)
    assert "payload" not in str(explanation).lower()


def test_credit_decision_explanation_supports_unable_to_decide_with_safe_fallback() -> None:
    policy = _published_policy(
        fallback_action=PolicyFallbackAction.create(action="unable_to_decide")
    )
    catalog = _published_catalog()
    decision_input = CreditDecisionInput.create(
        proposal_id="proposal_unable_to_decide_explanation",
        values={
            "monthly_income_units": 300_000,
            "requested_amount_units": 700_000,
            "requested_term_days": 360,
        },
    )
    evaluation = evaluate_policy_case(
        policy=policy,
        catalog=catalog,
        evaluation_id=decision_input.proposal_id,
        field_values=decision_input.field_values,
    )
    decision = CreditDecision.create(
        decision_id="decision_unable_to_decide_explanation",
        policy=policy,
        catalog=catalog,
        decision_input=decision_input,
        evaluation=evaluation,
        channel="api",
        correlation_id="corr_1234567890abcdef",
        decided_at=NOW,
    )

    explanation = decision.to_explainable_response(catalog=catalog)

    assert explanation.status == "unable_to_decide"
    assert explanation.reason_codes == ()
    assert explanation.fallback_action == "unable_to_decide"
    assert explanation.validation_issue_codes == ("missing_limit_field",)


def test_credit_decision_adjusted_terms_never_increase_requested_terms() -> None:
    decision_input = CreditDecisionInput.create(
        proposal_id="proposal_no_increase_adjustment",
        values={
            "monthly_income_units": 300_000,
            "requested_amount_units": 700_000,
            "requested_installments": 12,
            "requested_term_days": 360,
        },
    )

    adjusted_terms = CreditDecisionApprovedTerms.adjusted_from_policy_limits(
        decision_input,
        (
            PolicyLimit.create(
                limit_id="limit_min_amount",
                limit_type="min_amount_units",
                value=900_000,
            ),
            PolicyLimit.create(
                limit_id="limit_min_term_days",
                limit_type="min_term_days",
                value=720,
            ),
        ),
    )

    assert adjusted_terms is None


def test_credit_decision_adjusted_terms_rejects_remaining_minimum_limit_violation() -> None:
    decision_input = CreditDecisionInput.create(
        proposal_id="proposal_remaining_min_violation",
        values={
            "monthly_income_units": 300_000,
            "requested_amount_units": 700_000,
            "requested_installments": 12,
            "requested_term_days": 360,
        },
    )

    adjusted_terms = CreditDecisionApprovedTerms.adjusted_from_policy_limits(
        decision_input,
        (
            PolicyLimit.create(
                limit_id="limit_min_amount",
                limit_type="min_amount_units",
                value=800_000,
            ),
            PolicyLimit.create(
                limit_id="limit_max_installments",
                limit_type="max_installments",
                value=10,
            ),
        ),
    )

    assert adjusted_terms is None


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


def test_credit_decision_rejects_restored_manual_fallback_alias() -> None:
    with pytest.raises(PolicyValidationError, match="IA pode atuar apenas"):
        PolicyEvaluationResult(
            evaluation_id="proposal_manual_fallback_alias",
            outcome="unable_to_decide",
            triggered_rule_ids=(),
            reason_code_refs=(),
            factor_refs=(),
            fallback_action="manual_review",
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


def test_policy_evaluator_applies_request_more_data_fallback_for_missing_fields() -> None:
    result = evaluate_policy_case(
        policy=_published_policy(),
        catalog=_published_catalog(),
        evaluation_id="proposal_missing_limit_field",
        field_values=CreditDecisionInput.create(
            proposal_id="proposal_missing_limit_field",
            values={
                "monthly_income_units": 300_000,
                "requested_amount_units": 700_000,
                "requested_term_days": 360,
            },
        ).field_values,
    )

    assert result.outcome == "request_more_data"
    assert result.fallback_action == "request_more_data"
    assert result.required_data_refs == ("requested_installments",)
    assert result.validation_issues[0].code == "missing_limit_field"


def test_policy_evaluator_applies_unable_to_decide_fallback_when_configured() -> None:
    result = evaluate_policy_case(
        policy=_published_policy(
            fallback_action=PolicyFallbackAction.create(action="unable_to_decide")
        ),
        catalog=_published_catalog(),
        evaluation_id="proposal_unable_fallback",
        field_values=CreditDecisionInput.create(
            proposal_id="proposal_unable_fallback",
            values={
                "monthly_income_units": 300_000,
                "requested_amount_units": 700_000,
                "requested_term_days": 360,
            },
        ).field_values,
    )

    assert result.outcome == "unable_to_decide"
    assert result.fallback_action == "unable_to_decide"
    assert result.required_data_refs == ("requested_installments",)


def test_policy_evaluator_treats_missing_exists_true_criterion_as_required_data() -> None:
    result = evaluate_policy_case(
        policy=_published_policy(
            criteria=(
                PolicyCriterion.create(
                    criterion_id="criterion_age_required",
                    field="age_years",
                    operator="exists",
                    value=True,
                ),
            )
        ),
        catalog=_published_catalog(),
        evaluation_id="proposal_missing_exists_true",
        field_values=CreditDecisionInput.create(
            proposal_id="proposal_missing_exists_true",
            values={
                "monthly_income_units": 300_000,
                "requested_amount_units": 700_000,
                "requested_installments": 12,
                "requested_term_days": 360,
            },
        ).field_values,
    )

    assert result.outcome == "request_more_data"
    assert result.required_data_refs == ("age_years",)
    assert result.validation_issues[0].code == "missing_criterion_field"


def test_policy_evaluator_reject_by_policy_never_rejects_missing_fields() -> None:
    result = evaluate_policy_case(
        policy=_published_policy(
            fallback_action=PolicyFallbackAction.create(
                action="reject_by_policy",
                reason_code_refs=("rc_reject_income",),
            )
        ),
        catalog=_published_catalog(include_reject=True),
        evaluation_id="proposal_missing_reject_fallback",
        field_values=CreditDecisionInput.create(
            proposal_id="proposal_missing_reject_fallback",
            values={
                "monthly_income_units": 300_000,
                "requested_amount_units": 700_000,
                "requested_term_days": 360,
            },
        ).field_values,
    )

    assert result.outcome == "unable_to_decide"
    assert result.fallback_action == "reject_by_policy"
    assert result.reason_code_refs == ()
    assert result.required_data_refs == ("requested_installments",)


def test_policy_evaluator_reject_by_policy_rejects_governed_limit_failure() -> None:
    result = evaluate_policy_case(
        policy=_published_policy(
            rules=(_rule(outcome="reject"),),
            fallback_action=PolicyFallbackAction.create(
                action="reject_by_policy",
                reason_code_refs=("rc_reject_income",),
            ),
        ),
        catalog=_published_catalog(include_reject=True),
        evaluation_id="proposal_limit_reject_fallback",
        field_values=CreditDecisionInput.create(
            proposal_id="proposal_limit_reject_fallback",
            values={
                "monthly_income_units": 300_000,
                "requested_amount_units": 700_000,
                "requested_installments": 36,
                "requested_term_days": 360,
            },
        ).field_values,
    )

    assert result.outcome == "reject"
    assert result.fallback_action == "reject_by_policy"
    assert result.triggered_rule_ids == ("rule_min_income",)
    assert result.reason_code_refs == ("rc_reject_income",)
    assert result.factor_refs == ("factor_monthly_income",)
    assert result.required_data_refs == ()


def test_policy_evaluator_reject_by_policy_honors_reject_rule_after_failed_criterion() -> None:
    result = evaluate_policy_case(
        policy=_published_policy(
            rules=(
                PolicyRule.create(
                    rule_id="rule_requested_amount_reject",
                    name="Valor solicitado acima da política",
                    source_field="requested_amount_units",
                    operator="gte",
                    threshold_value=1_000_001,
                    outcome="reject",
                    reason_code_refs=("rc_reject_income",),
                ),
            ),
            fallback_action=PolicyFallbackAction.create(
                action="reject_by_policy",
                reason_code_refs=("rc_reject_income",),
            ),
        ),
        catalog=_published_catalog(include_reject=True),
        evaluation_id="proposal_reject_after_criterion",
        field_values=CreditDecisionInput.create(
            proposal_id="proposal_reject_after_criterion",
            values={
                "requested_amount_units": 1_200_000,
                "requested_installments": 12,
                "requested_term_days": 360,
            },
        ).field_values,
    )

    assert result.outcome == "reject"
    assert result.triggered_rule_ids == ("rule_requested_amount_reject",)
    assert result.reason_code_refs == ("rc_reject_income",)
    assert result.validation_issues[0].code == "policy_criterion_not_satisfied"


def test_policy_evaluator_rejects_approve_with_changes_with_remaining_minimum_limit_violation() -> (
    None
):
    result = evaluate_policy_case(
        policy=_published_policy(
            rules=(_outcome_rule(outcome="approve_with_changes"),),
            limits=(
                PolicyLimit.create(
                    limit_id="limit_min_amount",
                    limit_type="min_amount_units",
                    value=800_000,
                ),
                PolicyLimit.create(
                    limit_id="limit_max_installments",
                    limit_type="max_installments",
                    value=10,
                ),
            ),
        ),
        catalog=_published_catalog_for_outcome(
            outcome="approve_with_changes",
            reason_code_ref="rc_approve_with_changes",
        ),
        evaluation_id="proposal_awc_remaining_min_violation",
        field_values=CreditDecisionInput.create(
            proposal_id="proposal_awc_remaining_min_violation",
            values={
                "monthly_income_units": 300_000,
                "requested_amount_units": 700_000,
                "requested_installments": 12,
                "requested_term_days": 360,
            },
        ).field_values,
    )

    assert result.outcome == "unable_to_decide"
    assert result.reason_code_refs == ()
    assert result.validation_issues[0].code == "policy_limit_not_satisfied"


def test_policy_evaluator_reject_by_policy_does_not_reject_without_explicit_reject_rule() -> None:
    result = evaluate_policy_case(
        policy=_published_policy(
            fallback_action=PolicyFallbackAction.create(
                action="reject_by_policy",
                reason_code_refs=("rc_reject_income",),
            )
        ),
        catalog=_published_catalog(include_reject=True),
        evaluation_id="proposal_limit_reject_without_rule",
        field_values=CreditDecisionInput.create(
            proposal_id="proposal_limit_reject_without_rule",
            values={
                "monthly_income_units": 300_000,
                "requested_amount_units": 700_000,
                "requested_installments": 36,
                "requested_term_days": 360,
            },
        ).field_values,
    )

    assert result.outcome == "unable_to_decide"
    assert result.triggered_rule_ids == ("rule_approval_income",)
    assert result.reason_code_refs == ()
    assert result.validation_issues[0].code == "policy_limit_not_satisfied"


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
    policy_limits = None
    if outcome == "approve_with_changes":
        policy_limits = (
            PolicyLimit.create(
                limit_id="limit_max_installments",
                limit_type="max_installments",
                value=10,
            ),
        )
    result = evaluate_policy_case(
        policy=_published_policy(rules=(_outcome_rule(outcome=outcome),), limits=policy_limits),
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
    criteria: tuple[PolicyCriterion, ...] | None = None,
    limits: tuple[PolicyLimit, ...] | None = None,
    applicability: PolicyApplicability | None = None,
    fallback_action: PolicyFallbackAction | None = None,
) -> CreditPolicy:
    return CreditPolicy.create_draft(
        policy_id="pol_personal_credit_default",
        policy_version_id="polver_personal_credit_default_v1",
        tenant_id="tenant_alpha",
        owner_subject_id="user_credit_manager",
        product_type="personal_credit",
        reason_code_catalog_id="rcc_personal_credit_default",
        reason_code_catalog_version_id="rccver_personal_credit_default_v1",
        applicability=applicability or PolicyApplicability.create(channels=("api",), starts_at=NOW),
        rules=rules or (_approval_rule(),),
        criteria=criteria
        or (
            PolicyCriterion.create(
                criterion_id="criterion_requested_amount",
                field="requested_amount_units",
                operator="lte",
                value=1_000_000,
            ),
        ),
        limits=limits
        or (
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
        fallback_action=fallback_action,
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


def _published_catalog_for_outcome(
    *,
    outcome: str,
    reason_code_ref: str,
    reason_code_audience: str = "both",
) -> ReasonCodeCatalog:
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
    external_description: str = "Renda declarada compatível com aprovação",
    reason_code_audience: str = "both",
) -> ReasonCodeCatalog:
    reason_codes = [
        ReasonCode.create(
            reason_code_id="reason_min_income",
            code="rc_min_income",
            outcome="approve",
            title="Renda mínima",
            internal_description="Renda declarada atende a política",
            external_description=external_description,
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
