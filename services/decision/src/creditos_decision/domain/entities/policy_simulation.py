from __future__ import annotations

from datetime import datetime

from creditos_decision.domain.entities.credit_policy import CreditPolicy
from creditos_decision.domain.entities.reason_code_catalog import ReasonCodeCatalog
from creditos_decision.domain.errors import PolicyValidationError
from creditos_decision.domain.services.policy_evaluator import evaluate_policy_case
from creditos_decision.domain.value_objects.policy_evaluation import PolicyEvaluationIssue
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
            policy_revision=policy.revision,
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
    for simulation_case in cases:
        try:
            evaluate_policy_case(
                policy=policy,
                catalog=catalog,
                evaluation_id=simulation_case.case_id,
                field_values=simulation_case.field_values,
            )
        except PolicyValidationError as error:
            if error.code == "unsupported_policy_evaluation_field_for_policy":
                raise PolicyValidationError(
                    "campo não permitido para a política simulada",
                    code="unsupported_policy_simulation_field_for_policy",
                    field_path=f"simulation_cases.{simulation_case.case_id}.field_values",
                    details=dict(error.details),
                ) from error
            if error.code == "policy_evaluation_catalog_mismatch":
                raise PolicyValidationError(
                    "catálogo incompatível com política simulada",
                    code="policy_simulation_catalog_mismatch",
                    field_path="reason_code_catalog_id",
                ) from error
            if error.code == "policy_evaluation_catalog_provenance_mismatch":
                raise PolicyValidationError(
                    "catálogo diferente da proveniência da política simulada",
                    code="policy_simulation_catalog_provenance_mismatch",
                    field_path="reason_code_catalog_version_id",
                ) from error
            raise


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
    evaluation = evaluate_policy_case(
        policy=policy,
        catalog=catalog,
        evaluation_id=simulation_case.case_id,
        field_values=simulation_case.field_values,
    )
    return PolicySimulationCaseResult(
        case_id=simulation_case.case_id,
        outcome=evaluation.outcome,
        triggered_rule_ids=evaluation.triggered_rule_ids,
        reason_code_refs=evaluation.reason_code_refs,
        factor_refs=evaluation.factor_refs,
        validation_issues=_to_policy_validation_issues(evaluation.validation_issues),
    )


def _to_policy_validation_issues(
    issues: tuple[PolicyEvaluationIssue, ...],
) -> tuple[PolicyValidationIssue, ...]:
    return tuple(
        PolicyValidationIssue.create(
            code=issue.code,
            field_path=issue.field_path,
            message=issue.message,
            severity=issue.severity,
        )
        for issue in issues
    )


def _has_issues(
    case_results: tuple[PolicySimulationCaseResult, ...],
    validation_issues: tuple[PolicyValidationIssue, ...],
) -> bool:
    return bool(validation_issues) or any(
        case_result.validation_issues for case_result in case_results
    )
