from __future__ import annotations

from datetime import UTC, datetime

import pytest
from creditos_decision.domain.entities import CreditPolicy, PolicySimulation, ReasonCodeCatalog
from creditos_decision.domain.errors import PolicyValidationError
from creditos_decision.domain.value_objects import (
    ExplainableFactor,
    PolicyApplicability,
    PolicyCriterion,
    PolicyEvaluationResult,
    PolicyLimit,
    PolicyRule,
    PolicySimulationCaseResult,
    PolicySimulationInputCase,
    PolicySimulationResult,
    ReasonCode,
)

NOW = datetime(2026, 8, 27, 12, 0, tzinfo=UTC)


def test_simulation_input_case_accepts_only_governed_minimized_fields() -> None:
    case = PolicySimulationInputCase.create(
        case_id="case_safe_credit_001",
        values={
            "monthly_income_units": 320_000,
            "requested_amount_units": 900_000,
            "requested_installments": 12,
        },
    )

    assert case.value_for("monthly_income_units") == 320_000
    assert case.value_for("unknown_field") is None


def test_simulation_input_case_rejects_invalid_values_and_free_fields() -> None:
    with pytest.raises(PolicyValidationError) as invalid_value_error:
        PolicySimulationInputCase.create(
            case_id="case_invalid_credit_001",
            values={"monthly_income_units": 12_345_678_901},
        )

    with pytest.raises(PolicyValidationError) as free_field_error:
        PolicySimulationInputCase.create(
            case_id="case_free_payload_001",
            values={"provider_payload": 1},
        )

    assert invalid_value_error.value.code == "invalid_policy_value"
    assert free_field_error.value.code in {
        "sensitive_or_prohibited_policy_field",
        "unsupported_policy_field",
    }


def test_simulation_input_case_preserves_governed_numeric_upper_bound() -> None:
    case = PolicySimulationInputCase.create(
        case_id="case_max_amount_001",
        values={"requested_amount_units": 10_000_000_000},
    )

    assert case.value_for("requested_amount_units") == 10_000_000_000


def test_policy_simulation_is_non_production_and_explainable() -> None:
    policy = _policy()
    catalog = _catalog()
    case = PolicySimulationInputCase.create(
        case_id="case_low_income_001",
        values={
            "monthly_income_units": 200_000,
            "requested_amount_units": 700_000,
            "requested_installments": 12,
        },
    )

    result = PolicySimulation.run(
        simulation_id="sim_personal_credit_001",
        policy=policy,
        catalog=catalog,
        cases=(case,),
        correlation_id="corr_1234567890abcdef",
        now=NOW,
    )

    assert result.non_production is True
    assert result.status == "completed"
    assert result.summary.total_cases == 1
    assert result.case_results[0].outcome == "reject"
    assert result.case_results[0].triggered_rule_ids == ("rule_low_income",)
    assert result.case_results[0].reason_code_refs == ("rc_low_income",)
    assert result.case_results[0].factor_refs == ("factor_monthly_income",)
    assert result.policy_id == policy.policy_id
    assert result.reason_code_catalog_version_id == catalog.catalog_version_id


def test_policy_simulation_evaluates_each_case_once(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def recording_evaluate_policy_case(
        *,
        policy: CreditPolicy,
        catalog: ReasonCodeCatalog,
        evaluation_id: str,
        field_values: object,
    ) -> PolicyEvaluationResult:
        calls.append(evaluation_id)
        return PolicyEvaluationResult(
            evaluation_id=evaluation_id,
            outcome="reject",
            triggered_rule_ids=("rule_low_income",),
            reason_code_refs=("rc_low_income",),
            factor_refs=("factor_monthly_income",),
        )

    monkeypatch.setattr(
        "creditos_decision.domain.entities.policy_simulation.evaluate_policy_case",
        recording_evaluate_policy_case,
    )

    result = PolicySimulation.run(
        simulation_id="sim_personal_credit_single_eval",
        policy=_policy(),
        catalog=_catalog(),
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
        correlation_id="corr_1234567890abcdef",
        now=NOW,
    )

    assert calls == ["case_low_income_001"]
    assert result.case_results[0].outcome == "reject"


def test_policy_simulation_result_cannot_be_marked_as_production() -> None:
    with pytest.raises(PolicyValidationError) as error:
        PolicySimulationResult.restore(
            simulation_id="sim_personal_credit_001",
            tenant_id="tenant_alpha",
            policy_id="pol_personal_credit_default",
            policy_version_id="polver_personal_credit_default_v1",
            policy_revision=1,
            reason_code_catalog_id="rcc_personal_credit_default",
            reason_code_catalog_version_id="rccver_personal_credit_default_v1",
            status="completed",
            non_production=False,
            case_results=(),
            validation_issues=(),
            correlation_id="corr_1234567890abcdef",
            created_at=NOW,
        )

    assert error.value.code == "policy_simulation_must_be_non_production"


def test_policy_simulation_rejects_fields_not_used_by_policy() -> None:
    with pytest.raises(PolicyValidationError) as error:
        PolicySimulation.run(
            simulation_id="sim_personal_credit_002",
            policy=_policy(),
            catalog=_catalog(),
            cases=(
                PolicySimulationInputCase.create(
                    case_id="case_extra_field_001",
                    values={
                        "monthly_income_units": 200_000,
                        "requested_amount_units": 700_000,
                        "requested_installments": 12,
                        "age_years": 35,
                    },
                ),
            ),
            correlation_id="corr_1234567890abcdef",
            now=NOW,
        )

    assert error.value.code == "unsupported_policy_simulation_field_for_policy"


def test_policy_simulation_remaps_catalog_mismatch_to_simulation_specific_codes() -> None:
    with pytest.raises(PolicyValidationError) as mismatch_error:
        PolicySimulation.run(
            simulation_id="sim_personal_credit_catalog_mismatch",
            policy=_policy(),
            catalog=_catalog(catalog_id="rcc_personal_credit_alternative"),
            cases=(
                PolicySimulationInputCase.create(
                    case_id="case_catalog_mismatch",
                    values={
                        "monthly_income_units": 300_000,
                        "requested_amount_units": 700_000,
                        "requested_installments": 12,
                    },
                ),
            ),
            correlation_id="corr_1234567890abcdef",
            now=NOW,
        )

    assert mismatch_error.value.code == "policy_simulation_catalog_provenance_mismatch"


def test_policy_simulation_issue_paths_include_case_identity() -> None:
    result = PolicySimulation.run(
        simulation_id="sim_personal_credit_case_paths",
        policy=_policy(),
        catalog=_catalog(),
        cases=(
            PolicySimulationInputCase.create(
                case_id="case_missing_limit_field",
                values={
                    "monthly_income_units": 300_000,
                    "requested_amount_units": 700_000,
                },
            ),
        ),
        correlation_id="corr_1234567890abcdef",
        now=NOW,
    )

    assert result.status == "completed_with_issues"
    assert result.case_results[0].validation_issues[0].field_path == (
        "cases.case_missing_limit_field.limits.requested_installments"
    )


def test_policy_simulation_returns_issue_for_conflicting_rule_outcomes() -> None:
    policy = _policy_with_conflicting_rules()

    result = PolicySimulation.run(
        simulation_id="sim_personal_credit_003",
        policy=policy,
        catalog=_catalog(),
        cases=(
            PolicySimulationInputCase.create(
                case_id="case_conflict_001",
                values={
                    "monthly_income_units": 300_000,
                    "requested_amount_units": 700_000,
                    "requested_installments": 12,
                },
            ),
        ),
        correlation_id="corr_1234567890abcdef",
        now=NOW,
    )

    assert result.status == "completed_with_issues"
    assert result.case_results[0].outcome == "unable_to_decide"
    assert result.case_results[0].triggered_rule_ids == (
        "rule_sufficient_income",
        "rule_low_amount_reject",
    )
    assert result.case_results[0].reason_code_refs == ()
    assert result.case_results[0].validation_issues[0].code == ("conflicting_policy_rule_outcomes")


def test_policy_simulation_rejects_too_many_cases_and_invalid_case_type() -> None:
    cases = tuple(
        PolicySimulationInputCase.create(
            case_id=f"case_bulk_{case_index:03d}",
            values={
                "monthly_income_units": 300_000,
                "requested_amount_units": 700_000,
                "requested_installments": 12,
            },
        )
        for case_index in range(101)
    )

    with pytest.raises(PolicyValidationError) as too_large_error:
        PolicySimulation.run(
            simulation_id="sim_personal_credit_004",
            policy=_policy(),
            catalog=_catalog(),
            cases=cases,
            correlation_id="corr_1234567890abcdef",
            now=NOW,
        )

    with pytest.raises(PolicyValidationError) as invalid_case_error:
        PolicySimulation.run(
            simulation_id="sim_personal_credit_005",
            policy=_policy(),
            catalog=_catalog(),
            cases=("not_a_case",),  # type: ignore[arg-type]
            correlation_id="corr_1234567890abcdef",
            now=NOW,
        )

    assert too_large_error.value.code == "policy_simulation_dataset_too_large"
    assert invalid_case_error.value.code == "invalid_policy_simulation_case"


def test_policy_simulation_returns_fallback_when_any_rule_field_is_missing() -> None:
    result = PolicySimulation.run(
        simulation_id="sim_personal_credit_006",
        policy=_policy_with_missing_rule_risk(),
        catalog=_catalog(),
        cases=(
            PolicySimulationInputCase.create(
                case_id="case_partial_rules_001",
                values={
                    "monthly_income_units": 300_000,
                    "requested_amount_units": 700_000,
                    "requested_installments": 12,
                },
            ),
        ),
        correlation_id="corr_1234567890abcdef",
        now=NOW,
    )

    assert result.status == "completed_with_issues"
    assert result.case_results[0].outcome == "request_more_data"
    assert result.case_results[0].fallback_action == "request_more_data"
    assert result.case_results[0].required_data_refs == ("age_years",)
    assert result.case_results[0].triggered_rule_ids == ("rule_sufficient_income",)
    assert result.case_results[0].reason_code_refs == ()
    assert result.case_results[0].validation_issues[0].code == "missing_rule_field"


def test_policy_simulation_case_result_rejects_manual_fallback_alias() -> None:
    with pytest.raises(PolicyValidationError, match="IA apenas consultiva"):
        PolicySimulationCaseResult(
            case_id="case_manual_fallback_alias",
            outcome="unable_to_decide",
            triggered_rule_ids=(),
            reason_code_refs=(),
            factor_refs=(),
            fallback_action="manual_review",
        )


def test_policy_simulation_evaluates_exists_false_for_missing_field() -> None:
    result = PolicySimulation.run(
        simulation_id="sim_personal_credit_007",
        policy=_policy_with_exists_false(),
        catalog=_catalog(),
        cases=(
            PolicySimulationInputCase.create(
                case_id="case_missing_age_001",
                values={
                    "requested_amount_units": 700_000,
                    "requested_installments": 12,
                },
            ),
        ),
        correlation_id="corr_1234567890abcdef",
        now=NOW,
    )

    assert result.status == "completed"
    assert result.case_results[0].outcome == "reject"
    assert result.case_results[0].triggered_rule_ids == ("rule_age_absent",)
    assert result.case_results[0].reason_code_refs == ("rc_low_income",)


def _policy() -> CreditPolicy:
    return CreditPolicy.create_draft(
        policy_id="pol_personal_credit_default",
        policy_version_id="polver_personal_credit_default_v1",
        tenant_id="tenant_alpha",
        owner_subject_id="user_credit_manager",
        product_type="personal_credit",
        reason_code_catalog_id="rcc_personal_credit_default",
        reason_code_catalog_version_id="rccver_personal_credit_default_v1",
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
        now=NOW,
        actor_subject_id="user_credit_manager",
        correlation_id="corr_1234567890abcdef",
        change_summary="Criação inicial da política",
    )


def _catalog(
    *,
    catalog_id: str = "rcc_personal_credit_default",
    catalog_version_id: str = "rccver_personal_credit_default_v1",
) -> ReasonCodeCatalog:
    return ReasonCodeCatalog.create_draft(
        catalog_id=catalog_id,
        catalog_version_id=catalog_version_id,
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


def _policy_with_conflicting_rules() -> CreditPolicy:
    return CreditPolicy.create_draft(
        policy_id="pol_personal_credit_default",
        policy_version_id="polver_personal_credit_default_v1",
        tenant_id="tenant_alpha",
        owner_subject_id="user_credit_manager",
        product_type="personal_credit",
        reason_code_catalog_id="rcc_personal_credit_default",
        reason_code_catalog_version_id="rccver_personal_credit_default_v1",
        applicability=PolicyApplicability.create(channels=("api", "checkout")),
        rules=(
            PolicyRule.create(
                rule_id="rule_sufficient_income",
                name="Renda suficiente",
                source_field="monthly_income_units",
                operator="gte",
                threshold_value=250_000,
                outcome="approve",
                reason_code_refs=("rc_sufficient_income",),
            ),
            PolicyRule.create(
                rule_id="rule_low_amount_reject",
                name="Valor baixo recusado",
                source_field="requested_amount_units",
                operator="lte",
                threshold_value=700_000,
                outcome="reject",
                reason_code_refs=("rc_low_income",),
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
        now=NOW,
        actor_subject_id="user_credit_manager",
        correlation_id="corr_1234567890abcdef",
        change_summary="Criação inicial da política",
    )


def _policy_with_missing_rule_risk() -> CreditPolicy:
    return CreditPolicy.create_draft(
        policy_id="pol_personal_credit_default",
        policy_version_id="polver_personal_credit_default_v1",
        tenant_id="tenant_alpha",
        owner_subject_id="user_credit_manager",
        product_type="personal_credit",
        reason_code_catalog_id="rcc_personal_credit_default",
        reason_code_catalog_version_id="rccver_personal_credit_default_v1",
        applicability=PolicyApplicability.create(channels=("api", "checkout")),
        rules=(
            PolicyRule.create(
                rule_id="rule_sufficient_income",
                name="Renda suficiente",
                source_field="monthly_income_units",
                operator="gte",
                threshold_value=250_000,
                outcome="approve",
                reason_code_refs=("rc_sufficient_income",),
            ),
            PolicyRule.create(
                rule_id="rule_age_reject",
                name="Idade rejeitada",
                source_field="age_years",
                operator="lte",
                threshold_value=17,
                outcome="reject",
                reason_code_refs=("rc_low_income",),
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
        now=NOW,
        actor_subject_id="user_credit_manager",
        correlation_id="corr_1234567890abcdef",
        change_summary="Criação inicial da política",
    )


def _policy_with_exists_false() -> CreditPolicy:
    return CreditPolicy.create_draft(
        policy_id="pol_personal_credit_default",
        policy_version_id="polver_personal_credit_default_v1",
        tenant_id="tenant_alpha",
        owner_subject_id="user_credit_manager",
        product_type="personal_credit",
        reason_code_catalog_id="rcc_personal_credit_default",
        reason_code_catalog_version_id="rccver_personal_credit_default_v1",
        applicability=PolicyApplicability.create(channels=("api", "checkout")),
        rules=(
            PolicyRule.create(
                rule_id="rule_age_absent",
                name="Idade ausente",
                source_field="age_years",
                operator="exists",
                threshold_value=False,
                outcome="reject",
                reason_code_refs=("rc_low_income",),
            ),
        ),
        criteria=(
            PolicyCriterion.create(
                criterion_id="criterion_age_absent",
                field="age_years",
                operator="exists",
                value=False,
            ),
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
        now=NOW,
        actor_subject_id="user_credit_manager",
        correlation_id="corr_1234567890abcdef",
        change_summary="Criação inicial da política",
    )
