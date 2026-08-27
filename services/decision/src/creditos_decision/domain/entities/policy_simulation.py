from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

from creditos_decision.domain.entities.credit_policy import CreditPolicy
from creditos_decision.domain.entities.reason_code_catalog import ReasonCodeCatalog
from creditos_decision.domain.errors import PolicyValidationError
from creditos_decision.domain.value_objects.policy import PolicyOperator, PolicyOutcome
from creditos_decision.domain.value_objects.policy_simulation import (
    PolicySimulationCaseResult,
    PolicySimulationInputCase,
    PolicySimulationResult,
    PolicyValidationIssue,
)

MAX_POLICY_SIMULATION_CASES = 100


class PolicySimulation:
    @staticmethod
    def run(
        *,
        simulation_id: str,
        policy: CreditPolicy,
        catalog: ReasonCodeCatalog,
        cases: tuple[PolicySimulationInputCase, ...],
        correlation_id: str,
        now: datetime,
    ) -> PolicySimulationResult:
        _validate_simulation_scope(policy=policy, catalog=catalog, cases=cases)
        case_results = tuple(
            _evaluate_case(policy=policy, catalog=catalog, simulation_case=simulation_case)
            for simulation_case in cases
        )
        validation_issues = _validate_policy_for_simulation(policy=policy)
        status = (
            "completed_with_issues" if _has_issues(case_results, validation_issues) else "completed"
        )
        return PolicySimulationResult.restore(
            simulation_id=simulation_id,
            tenant_id=policy.tenant_id,
            policy_id=policy.policy_id,
            policy_version_id=policy.policy_version_id,
            reason_code_catalog_id=catalog.catalog_id,
            reason_code_catalog_version_id=catalog.catalog_version_id,
            status=status,
            non_production=True,
            case_results=case_results,
            validation_issues=validation_issues,
            correlation_id=correlation_id,
            created_at=now,
        )


def _validate_simulation_scope(
    *,
    policy: CreditPolicy,
    catalog: ReasonCodeCatalog,
    cases: tuple[PolicySimulationInputCase, ...],
) -> None:
    if policy.status != "draft":
        raise PolicyValidationError(
            "simulação exige política em draft",
            code="policy_simulation_requires_draft_policy",
            field_path="policy.status",
        )
    if policy.is_executable_in_production:
        raise PolicyValidationError(
            "política produtiva não pode ser simulada nesta operação",
            code="policy_simulation_rejects_production_policy",
            field_path="policy.status",
        )
    if not cases:
        raise PolicyValidationError(
            "dataset de simulação vazio",
            code="empty_policy_simulation_dataset",
            field_path="simulation_cases",
        )
    if len(cases) > MAX_POLICY_SIMULATION_CASES:
        raise PolicyValidationError(
            "dataset de simulação excede limite operacional",
            code="policy_simulation_dataset_too_large",
            field_path="simulation_cases",
            details={"max_cases": MAX_POLICY_SIMULATION_CASES},
        )
    for simulation_case in cases:
        if not isinstance(simulation_case, PolicySimulationInputCase):
            raise PolicyValidationError(
                "caso de simulação inválido",
                code="invalid_policy_simulation_case",
                field_path="simulation_cases",
            )
    case_ids = [simulation_case.case_id for simulation_case in cases]
    if len(set(case_ids)) != len(case_ids):
        raise PolicyValidationError(
            "caso de simulação duplicado",
            code="duplicate_policy_simulation_case",
            field_path="simulation_cases.case_id",
        )
    allowed_fields = _policy_simulation_allowed_fields(policy)
    for simulation_case in cases:
        extra_fields = sorted(
            field_value.field
            for field_value in simulation_case.field_values
            if field_value.field not in allowed_fields
        )
        if extra_fields:
            raise PolicyValidationError(
                "campo não permitido para a política simulada",
                code="unsupported_policy_simulation_field_for_policy",
                field_path=f"simulation_cases.{simulation_case.case_id}.field_values",
                details={"fields": ",".join(extra_fields)},
            )
    if catalog.tenant_id != policy.tenant_id or catalog.product_type != policy.product_type:
        raise PolicyValidationError(
            "catálogo incompatível com política",
            code="policy_simulation_catalog_mismatch",
            field_path="reason_code_catalog_id",
        )
    if (
        catalog.catalog_id != policy.reason_code_catalog_id
        or catalog.catalog_version_id != policy.reason_code_catalog_version_id
    ):
        raise PolicyValidationError(
            "catálogo diferente da proveniência da política",
            code="policy_simulation_catalog_provenance_mismatch",
            field_path="reason_code_catalog_version_id",
        )
    catalog.validate_policy_rules(policy.rules)


def _validate_policy_for_simulation(policy: CreditPolicy) -> tuple[PolicyValidationIssue, ...]:
    issues: list[PolicyValidationIssue] = []
    if not policy.rules:
        issues.append(
            PolicyValidationIssue.create(
                code="missing_policy_rules",
                field_path="rules",
                message="Política sem regras para simulação",
            )
        )
    if not policy.criteria:
        issues.append(
            PolicyValidationIssue.create(
                code="missing_policy_criteria",
                field_path="criteria",
                message="Política sem critérios mínimos",
            )
        )
    if not policy.limits:
        issues.append(
            PolicyValidationIssue.create(
                code="missing_policy_limits",
                field_path="limits",
                message="Política sem limites mínimos",
            )
        )
    return tuple(issues)


def _evaluate_case(
    *,
    policy: CreditPolicy,
    catalog: ReasonCodeCatalog,
    simulation_case: PolicySimulationInputCase,
) -> PolicySimulationCaseResult:
    issues: list[PolicyValidationIssue] = []
    if not _criteria_are_satisfied(policy=policy, simulation_case=simulation_case, issues=issues):
        return _unable_to_decide_result(simulation_case=simulation_case, issues=tuple(issues))
    if not _limits_are_satisfied(policy=policy, simulation_case=simulation_case, issues=issues):
        return _unable_to_decide_result(simulation_case=simulation_case, issues=tuple(issues))

    triggered_rules = []
    for rule in policy.rules:
        case_value = simulation_case.value_for(rule.source_field)
        if case_value is None:
            issues.append(
                PolicyValidationIssue.create(
                    code="missing_rule_field",
                    field_path=f"cases.{simulation_case.case_id}.{rule.source_field}",
                    message="Campo exigido por regra ausente",
                )
            )
            continue
        if _matches_operator(
            operator=rule.operator,
            case_value=case_value,
            expected_value=rule.threshold_value,
        ):
            triggered_rules.append(rule)

    if not triggered_rules:
        return _unable_to_decide_result(
            simulation_case=simulation_case,
            issues=(
                *issues,
                PolicyValidationIssue.create(
                    code="no_policy_rule_triggered",
                    field_path=f"cases.{simulation_case.case_id}.rules",
                    message="Nenhuma regra acionada para o caso",
                ),
            ),
        )

    triggered_outcomes = _unique(rule.outcome for rule in triggered_rules)
    if len(triggered_outcomes) > 1:
        return PolicySimulationCaseResult(
            case_id=simulation_case.case_id,
            outcome=PolicyOutcome.UNABLE_TO_DECIDE.value,
            triggered_rule_ids=tuple(rule.rule_id for rule in triggered_rules),
            reason_code_refs=(),
            factor_refs=(),
            validation_issues=(
                *issues,
                PolicyValidationIssue.create(
                    code="conflicting_policy_rule_outcomes",
                    field_path=f"cases.{simulation_case.case_id}.rules",
                    message="Regras acionadas possuem outcomes conflitantes",
                ),
            ),
        )

    first_rule = triggered_rules[0]
    reason_code_refs = _unique(
        reason_code_ref for rule in triggered_rules for reason_code_ref in rule.reason_code_refs
    )
    return PolicySimulationCaseResult(
        case_id=simulation_case.case_id,
        outcome=first_rule.outcome,
        triggered_rule_ids=tuple(rule.rule_id for rule in triggered_rules),
        reason_code_refs=reason_code_refs,
        factor_refs=_factor_refs_for_reason_codes(
            catalog=catalog,
            reason_code_refs=reason_code_refs,
        ),
        validation_issues=tuple(issues),
    )


def _criteria_are_satisfied(
    *,
    policy: CreditPolicy,
    simulation_case: PolicySimulationInputCase,
    issues: list[PolicyValidationIssue],
) -> bool:
    satisfied = True
    for criterion in policy.criteria:
        case_value = simulation_case.value_for(criterion.field)
        if case_value is None:
            issues.append(
                PolicyValidationIssue.create(
                    code="missing_criterion_field",
                    field_path=f"cases.{simulation_case.case_id}.{criterion.field}",
                    message="Campo exigido por critério ausente",
                )
            )
            satisfied = False
            continue
        if not _matches_operator(
            operator=criterion.operator,
            case_value=case_value,
            expected_value=criterion.value,
        ):
            issues.append(
                PolicyValidationIssue.create(
                    code="policy_criterion_not_satisfied",
                    field_path=f"cases.{simulation_case.case_id}.{criterion.field}",
                    message="Critério de política não satisfeito",
                )
            )
            satisfied = False
    return satisfied


def _limits_are_satisfied(
    *,
    policy: CreditPolicy,
    simulation_case: PolicySimulationInputCase,
    issues: list[PolicyValidationIssue],
) -> bool:
    satisfied = True
    for policy_limit in policy.limits:
        mapped = _limit_field_and_operator(policy_limit.limit_type)
        if mapped is None:
            continue
        field_name, operator = mapped
        case_value = simulation_case.value_for(field_name)
        if case_value is None:
            issues.append(
                PolicyValidationIssue.create(
                    code="missing_limit_field",
                    field_path=f"cases.{simulation_case.case_id}.{field_name}",
                    message="Campo exigido por limite ausente",
                )
            )
            satisfied = False
            continue
        if not _matches_operator(
            operator=operator,
            case_value=case_value,
            expected_value=policy_limit.value,
        ):
            issues.append(
                PolicyValidationIssue.create(
                    code="policy_limit_not_satisfied",
                    field_path=f"cases.{simulation_case.case_id}.{field_name}",
                    message="Limite de política não satisfeito",
                )
            )
            satisfied = False
    return satisfied


def _matches_operator(
    *,
    operator: str,
    case_value: int,
    expected_value: int | str | bool,
) -> bool:
    if operator == PolicyOperator.GTE.value:
        return type(expected_value) is int and case_value >= expected_value
    if operator == PolicyOperator.LTE.value:
        return type(expected_value) is int and case_value <= expected_value
    if operator == PolicyOperator.EQ.value:
        return case_value == expected_value
    if operator == PolicyOperator.EXISTS.value:
        return expected_value is True
    raise PolicyValidationError(
        "operador de política não suportado",
        code="unsupported_policy_operator",
        field_path="operator",
    )


def _limit_field_and_operator(limit_type: str) -> tuple[str, str] | None:
    return {
        "max_amount_units": ("requested_amount_units", PolicyOperator.LTE.value),
        "min_amount_units": ("requested_amount_units", PolicyOperator.GTE.value),
        "max_installments": ("requested_installments", PolicyOperator.LTE.value),
        "max_term_days": ("requested_term_days", PolicyOperator.LTE.value),
        "min_term_days": ("requested_term_days", PolicyOperator.GTE.value),
    }.get(limit_type)


def _policy_simulation_allowed_fields(policy: CreditPolicy) -> set[str]:
    fields = {rule.source_field for rule in policy.rules}
    fields.update(criterion.field for criterion in policy.criteria)
    fields.update(
        mapped[0]
        for policy_limit in policy.limits
        if (mapped := _limit_field_and_operator(policy_limit.limit_type)) is not None
    )
    return fields


def _unable_to_decide_result(
    *,
    simulation_case: PolicySimulationInputCase,
    issues: tuple[PolicyValidationIssue, ...],
) -> PolicySimulationCaseResult:
    return PolicySimulationCaseResult(
        case_id=simulation_case.case_id,
        outcome=PolicyOutcome.UNABLE_TO_DECIDE.value,
        triggered_rule_ids=(),
        reason_code_refs=(),
        factor_refs=(),
        validation_issues=issues,
    )


def _factor_refs_for_reason_codes(
    *,
    catalog: ReasonCodeCatalog,
    reason_code_refs: tuple[str, ...],
) -> tuple[str, ...]:
    by_code = {reason_code.code: reason_code for reason_code in catalog.reason_codes}
    return _unique(
        factor_ref
        for reason_code_ref in reason_code_refs
        for factor_ref in by_code[reason_code_ref].factor_refs
    )


def _unique(values: Iterable[str]) -> tuple[str, ...]:
    unique_values: list[str] = []
    for value in values:
        if value not in unique_values:
            unique_values.append(value)
    return tuple(unique_values)


def _has_issues(
    case_results: tuple[PolicySimulationCaseResult, ...],
    validation_issues: tuple[PolicyValidationIssue, ...],
) -> bool:
    return bool(validation_issues) or any(
        case_result.validation_issues for case_result in case_results
    )
