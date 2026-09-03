from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Protocol

from creditos_decision.domain.entities.credit_policy import CreditPolicy
from creditos_decision.domain.entities.reason_code_catalog import ReasonCodeCatalog
from creditos_decision.domain.errors import PolicyValidationError
from creditos_decision.domain.value_objects.policy import (
    PolicyFallbackActionType,
    PolicyOperator,
    PolicyOutcome,
    PolicyRule,
)
from creditos_decision.domain.value_objects.policy_evaluation import (
    PolicyEvaluationIssue,
    PolicyEvaluationResult,
)

APPROVAL_TERM_FIELDS = frozenset(
    {
        "requested_amount_units",
        "requested_installments",
        "requested_term_days",
    }
)


class PolicyFieldValue(Protocol):
    @property
    def field(self) -> str: ...

    @property
    def value(self) -> int: ...


def evaluate_policy_case(
    *,
    policy: CreditPolicy,
    catalog: ReasonCodeCatalog,
    evaluation_id: str,
    field_values: Sequence[PolicyFieldValue],
) -> PolicyEvaluationResult:
    validate_policy_evaluation_scope(
        policy=policy,
        catalog=catalog,
        evaluation_id=evaluation_id,
        field_values=field_values,
    )
    issues: list[PolicyEvaluationIssue] = []
    if not _criteria_are_satisfied(
        policy=policy,
        evaluation_id=evaluation_id,
        field_values=field_values,
        issues=issues,
    ):
        return _fallback_result(
            policy=policy,
            catalog=catalog,
            evaluation_id=evaluation_id,
            issues=tuple(issues),
            allow_reject_by_policy=False,
        )
    limits_are_satisfied = _limits_are_satisfied(
        policy=policy,
        evaluation_id=evaluation_id,
        field_values=field_values,
        issues=issues,
    )
    if not limits_are_satisfied and _has_missing_data_issue(issues):
        return _fallback_result(
            policy=policy,
            catalog=catalog,
            evaluation_id=evaluation_id,
            issues=tuple(issues),
            allow_reject_by_policy=_issues_allow_reject_by_policy(issues),
        )

    triggered_rules = []
    for rule in policy.rules:
        case_value = _value_for(field_values, rule.source_field)
        if case_value is None and _operator_requires_present_field(
            operator=rule.operator,
            expected_value=rule.threshold_value,
        ):
            issues.append(
                PolicyEvaluationIssue.create(
                    code="missing_rule_field",
                    field_path=f"cases.{evaluation_id}.{rule.source_field}",
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
        return _fallback_result(
            policy=policy,
            catalog=catalog,
            evaluation_id=evaluation_id,
            issues=(
                *issues,
                PolicyEvaluationIssue.create(
                    code="no_policy_rule_triggered",
                    field_path=f"cases.{evaluation_id}.rules",
                    message="Nenhuma regra acionada para o caso",
                ),
            ),
            allow_reject_by_policy=False,
        )

    triggered_outcomes = _unique(rule.outcome for rule in triggered_rules)
    if len(triggered_outcomes) > 1:
        return _fallback_result(
            policy=policy,
            catalog=catalog,
            evaluation_id=evaluation_id,
            issues=(
                *issues,
                PolicyEvaluationIssue.create(
                    code="conflicting_policy_rule_outcomes",
                    field_path=f"cases.{evaluation_id}.rules",
                    message="Regras acionadas possuem outcomes conflitantes",
                ),
            ),
            triggered_rules=tuple(triggered_rules),
            allow_reject_by_policy=False,
        )

    if issues:
        if (
            triggered_outcomes == (PolicyOutcome.APPROVE_WITH_CHANGES.value,)
            and _only_limit_issues(issues)
            and _has_complete_approval_terms(field_values)
        ):
            reason_code_refs = _unique(
                reason_code_ref
                for rule in triggered_rules
                for reason_code_ref in rule.reason_code_refs
            )
            return PolicyEvaluationResult(
                evaluation_id=evaluation_id,
                outcome=PolicyOutcome.APPROVE_WITH_CHANGES.value,
                triggered_rule_ids=tuple(rule.rule_id for rule in triggered_rules),
                reason_code_refs=reason_code_refs,
                factor_refs=_factor_refs_for_reason_codes(
                    catalog=catalog,
                    reason_code_refs=reason_code_refs,
                ),
                validation_issues=tuple(issues),
            )
        return _fallback_result(
            policy=policy,
            catalog=catalog,
            evaluation_id=evaluation_id,
            issues=tuple(issues),
            allow_reject_by_policy=_issues_allow_reject_by_policy(issues),
            triggered_rules=tuple(triggered_rules),
        )

    reason_code_refs = _unique(
        reason_code_ref for rule in triggered_rules for reason_code_ref in rule.reason_code_refs
    )
    return PolicyEvaluationResult(
        evaluation_id=evaluation_id,
        outcome=triggered_rules[0].outcome,
        triggered_rule_ids=tuple(rule.rule_id for rule in triggered_rules),
        reason_code_refs=reason_code_refs,
        factor_refs=_factor_refs_for_reason_codes(
            catalog=catalog,
            reason_code_refs=reason_code_refs,
        ),
        validation_issues=tuple(issues),
    )


def validate_policy_evaluation_fields(
    *,
    policy: CreditPolicy,
    field_values: Sequence[PolicyFieldValue],
) -> None:
    allowed_fields = _policy_evaluation_allowed_fields(policy)
    extra_fields = sorted(
        field_value.field for field_value in field_values if field_value.field not in allowed_fields
    )
    if extra_fields:
        raise PolicyValidationError(
            "campo não permitido para a política avaliada",
            code="unsupported_policy_evaluation_field_for_policy",
            field_path="field_values",
            details={"fields": ",".join(extra_fields)},
        )


def validate_policy_evaluation_scope(
    *,
    policy: CreditPolicy,
    catalog: ReasonCodeCatalog,
    evaluation_id: str,
    field_values: Sequence[PolicyFieldValue],
) -> None:
    if not evaluation_id:
        raise PolicyValidationError(
            "identificador de avaliação obrigatório",
            code="missing_policy_evaluation_id",
            field_path="evaluation_id",
        )
    if not field_values:
        raise PolicyValidationError(
            "entrada de avaliação vazia",
            code="empty_policy_evaluation_input",
            field_path="field_values",
        )
    validate_policy_evaluation_fields(policy=policy, field_values=field_values)
    if catalog.tenant_id != policy.tenant_id or catalog.product_type != policy.product_type:
        raise PolicyValidationError(
            "catálogo incompatível com política",
            code="policy_evaluation_catalog_mismatch",
            field_path="reason_code_catalog_id",
        )
    if (
        catalog.catalog_id != policy.reason_code_catalog_id
        or catalog.catalog_version_id != policy.reason_code_catalog_version_id
    ):
        raise PolicyValidationError(
            "catálogo diferente da proveniência da política",
            code="policy_evaluation_catalog_provenance_mismatch",
            field_path="reason_code_catalog_version_id",
        )
    catalog.validate_policy_rules(policy.rules)


def _criteria_are_satisfied(
    *,
    policy: CreditPolicy,
    evaluation_id: str,
    field_values: Sequence[PolicyFieldValue],
    issues: list[PolicyEvaluationIssue],
) -> bool:
    satisfied = True
    for criterion in policy.criteria:
        case_value = _value_for(field_values, criterion.field)
        if case_value is None and _operator_requires_present_field(
            operator=criterion.operator,
            expected_value=criterion.value,
        ):
            issues.append(
                PolicyEvaluationIssue.create(
                    code="missing_criterion_field",
                    field_path=f"cases.{evaluation_id}.{criterion.field}",
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
                PolicyEvaluationIssue.create(
                    code="policy_criterion_not_satisfied",
                    field_path=f"cases.{evaluation_id}.criteria.{criterion.field}",
                    message="Critério de política não satisfeito",
                )
            )
            satisfied = False
    return satisfied


def _limits_are_satisfied(
    *,
    policy: CreditPolicy,
    evaluation_id: str,
    field_values: Sequence[PolicyFieldValue],
    issues: list[PolicyEvaluationIssue],
) -> bool:
    satisfied = True
    for policy_limit in policy.limits:
        mapped = _limit_field_and_operator(policy_limit.limit_type)
        if mapped is None:
            continue
        field_name, operator = mapped
        case_value = _value_for(field_values, field_name)
        if case_value is None:
            issues.append(
                PolicyEvaluationIssue.create(
                    code="missing_limit_field",
                    field_path=f"cases.{evaluation_id}.limits.{field_name}",
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
                PolicyEvaluationIssue.create(
                    code="policy_limit_not_satisfied",
                    field_path=f"cases.{evaluation_id}.limits.{field_name}",
                    message="Limite de política não satisfeito",
                )
            )
            satisfied = False
    return satisfied


def _matches_operator(
    *,
    operator: str,
    case_value: int | None,
    expected_value: int | str | bool,
) -> bool:
    if operator == PolicyOperator.EXISTS.value:
        if type(expected_value) is not bool:
            raise PolicyValidationError(
                "valor incompatível com operador",
                code="operator_value_type_mismatch",
                field_path="operator",
            )
        field_is_present = case_value is not None
        return field_is_present is expected_value
    if case_value is None:
        return False
    if operator == PolicyOperator.GTE.value:
        return type(expected_value) is int and case_value >= expected_value
    if operator == PolicyOperator.LTE.value:
        return type(expected_value) is int and case_value <= expected_value
    if operator == PolicyOperator.EQ.value:
        return type(expected_value) is int and case_value == expected_value
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


def _policy_evaluation_allowed_fields(policy: CreditPolicy) -> set[str]:
    fields = {rule.source_field for rule in policy.rules}
    fields.update(criterion.field for criterion in policy.criteria)
    fields.update(APPROVAL_TERM_FIELDS)
    fields.update(
        mapped[0]
        for policy_limit in policy.limits
        if (mapped := _limit_field_and_operator(policy_limit.limit_type)) is not None
    )
    return fields


def _fallback_result(
    *,
    policy: CreditPolicy,
    catalog: ReasonCodeCatalog,
    evaluation_id: str,
    issues: tuple[PolicyEvaluationIssue, ...],
    allow_reject_by_policy: bool,
    triggered_rules: tuple[PolicyRule, ...] = (),
) -> PolicyEvaluationResult:
    fallback_action = policy.fallback_action.action
    required_data_refs = _required_data_refs_for(issues)
    reject_reason_code_refs = _fallback_reject_reason_code_refs(
        policy=policy,
        triggered_rules=triggered_rules,
    )
    if fallback_action == PolicyFallbackActionType.REQUEST_MORE_DATA.value and required_data_refs:
        outcome = PolicyOutcome.REQUEST_MORE_DATA.value
    elif (
        fallback_action == PolicyFallbackActionType.REJECT_BY_POLICY.value
        and allow_reject_by_policy
        and not _has_missing_data_issue(issues)
        and reject_reason_code_refs
    ):
        outcome = PolicyOutcome.REJECT.value
    else:
        outcome = PolicyOutcome.UNABLE_TO_DECIDE.value
    reason_code_refs = reject_reason_code_refs if outcome == PolicyOutcome.REJECT.value else ()
    return PolicyEvaluationResult(
        evaluation_id=evaluation_id,
        outcome=outcome,
        triggered_rule_ids=tuple(rule.rule_id for rule in triggered_rules),
        reason_code_refs=reason_code_refs,
        factor_refs=_factor_refs_for_reason_codes(
            catalog=catalog, reason_code_refs=reason_code_refs
        ),
        validation_issues=issues,
        fallback_action=fallback_action,
        required_data_refs=required_data_refs,
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


def _issues_allow_reject_by_policy(issues: Sequence[PolicyEvaluationIssue]) -> bool:
    return any(
        issue.code in {"policy_criterion_not_satisfied", "policy_limit_not_satisfied"}
        for issue in issues
    )


def _has_missing_data_issue(issues: Sequence[PolicyEvaluationIssue]) -> bool:
    return any(issue.code.startswith("missing_") for issue in issues)


def _only_limit_issues(issues: Sequence[PolicyEvaluationIssue]) -> bool:
    return all(issue.code == "policy_limit_not_satisfied" for issue in issues)


def _has_complete_approval_terms(field_values: Sequence[PolicyFieldValue]) -> bool:
    return all(
        _value_for(field_values, field_name) is not None for field_name in APPROVAL_TERM_FIELDS
    )


def _operator_requires_present_field(*, operator: str, expected_value: int | str | bool) -> bool:
    return operator != PolicyOperator.EXISTS.value or expected_value is True


def _fallback_reject_reason_code_refs(
    *,
    policy: CreditPolicy,
    triggered_rules: tuple[PolicyRule, ...],
) -> tuple[str, ...]:
    triggered_reject_reason_refs = {
        reason_code_ref
        for rule in triggered_rules
        if rule.outcome == PolicyOutcome.REJECT.value
        for reason_code_ref in rule.reason_code_refs
    }
    return tuple(
        reason_code_ref
        for reason_code_ref in policy.fallback_action.reason_code_refs
        if reason_code_ref in triggered_reject_reason_refs
    )


def _required_data_refs_for(issues: Sequence[PolicyEvaluationIssue]) -> tuple[str, ...]:
    refs: list[str] = []
    for issue in issues:
        if not issue.code.startswith("missing_"):
            continue
        field_ref = issue.field_path.rsplit(".", 1)[-1]
        if field_ref not in {"rules", "criteria", "limits"} and field_ref not in refs:
            refs.append(field_ref)
    return tuple(refs)


def _value_for(field_values: Sequence[PolicyFieldValue], field_name: str) -> int | None:
    for field_value in field_values:
        if field_value.field == field_name:
            return field_value.value
    return None


def _unique(values: Iterable[str]) -> tuple[str, ...]:
    unique_values: list[str] = []
    for value in values:
        if value not in unique_values:
            unique_values.append(value)
    return tuple(unique_values)
