from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import cast

from creditos_decision.domain.errors import PolicyValidationError
from creditos_decision.domain.value_objects.policy import (
    PolicyOutcome,
    _parse_enum,
    _validate_aware_utc_datetime,
    _validate_policy_field,
    _validate_rule_value,
    _validate_safe_text,
    _validate_technical_id,
    validate_correlation_id,
    validate_policy_id,
    validate_policy_version_id,
    validate_tenant_id,
)
from creditos_decision.domain.value_objects.reason_codes import (
    validate_reason_code_catalog_id,
    validate_reason_code_catalog_version_id,
)


class PolicySimulationStatus(StrEnum):
    COMPLETED = "completed"
    COMPLETED_WITH_ISSUES = "completed_with_issues"


class PolicyValidationSeverity(StrEnum):
    ERROR = "error"
    WARNING = "warning"


def validate_policy_simulation_id(value: str) -> str:
    return _validate_technical_id(value, field_path="simulation_id")


@dataclass(frozen=True, slots=True)
class PolicyValidationIssue:
    code: str
    field_path: str
    message: str
    severity: str = "error"

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "code",
            _validate_technical_id(self.code, field_path="validation_issues.code"),
        )
        object.__setattr__(
            self,
            "field_path",
            _validate_safe_text(
                self.field_path,
                field_path="validation_issues.field_path",
            ),
        )
        object.__setattr__(
            self,
            "message",
            _validate_safe_text(self.message, field_path="validation_issues.message"),
        )
        object.__setattr__(
            self,
            "severity",
            _parse_enum(
                PolicyValidationSeverity,
                self.severity,
                code="unsupported_policy_validation_severity",
                field_path="validation_issues.severity",
            ),
        )

    @classmethod
    def create(
        cls,
        *,
        code: str,
        field_path: str,
        message: str,
        severity: str = "error",
    ) -> PolicyValidationIssue:
        return cls(
            code=code,
            field_path=field_path,
            message=message,
            severity=severity,
        )


@dataclass(frozen=True, slots=True)
class PolicySimulationFieldValue:
    field: str
    value: int

    def __post_init__(self) -> None:
        parsed_field = _validate_policy_field(
            self.field,
            field_path="simulation_cases.fields",
        )
        object.__setattr__(self, "field", parsed_field)
        object.__setattr__(
            self,
            "value",
            _validate_simulation_field_value(
                parsed_field,
                self.value,
                field_path=f"simulation_cases.values.{parsed_field}",
            ),
        )

    @classmethod
    def create(cls, *, field: str, value: int) -> PolicySimulationFieldValue:
        return cls(field=field, value=value)


@dataclass(frozen=True, slots=True)
class PolicySimulationInputCase:
    case_id: str
    field_values: tuple[PolicySimulationFieldValue, ...]

    def __post_init__(self) -> None:
        parsed_case_id = _validate_technical_id(
            self.case_id,
            field_path="simulation_cases.case_id",
        )
        field_values = tuple(self.field_values)
        if not field_values:
            raise PolicyValidationError(
                "caso de simulação sem campos",
                code="empty_policy_simulation_case",
                field_path="simulation_cases.field_values",
            )
        for field_value in field_values:
            if not isinstance(field_value, PolicySimulationFieldValue):
                raise PolicyValidationError(
                    "valor de campo de simulação inválido",
                    code="invalid_policy_simulation_field_value",
                    field_path="simulation_cases.field_values",
                )
        field_names = [field_value.field for field_value in field_values]
        if len(set(field_names)) != len(field_names):
            raise PolicyValidationError(
                "campo duplicado no caso de simulação",
                code="duplicate_policy_simulation_field",
                field_path="simulation_cases.field_values",
            )
        object.__setattr__(self, "case_id", parsed_case_id)
        object.__setattr__(self, "field_values", field_values)

    @classmethod
    def create(
        cls,
        *,
        case_id: str,
        values: Mapping[str, int],
    ) -> PolicySimulationInputCase:
        return cls(
            case_id=case_id,
            field_values=tuple(
                PolicySimulationFieldValue.create(field=field_name, value=field_value)
                for field_name, field_value in values.items()
            ),
        )

    def value_for(self, field_name: str) -> int | None:
        for field_value in self.field_values:
            if field_value.field == field_name:
                return field_value.value
        return None


@dataclass(frozen=True, slots=True)
class PolicySimulationCaseResult:
    case_id: str
    outcome: str
    triggered_rule_ids: tuple[str, ...]
    reason_code_refs: tuple[str, ...]
    factor_refs: tuple[str, ...]
    validation_issues: tuple[PolicyValidationIssue, ...] = ()
    simulation: bool = True
    non_production: bool = True

    def __post_init__(self) -> None:
        if self.simulation is not True or self.non_production is not True:
            raise PolicyValidationError(
                "resultado de simulação deve ser não produtivo",
                code="policy_simulation_case_must_be_non_production",
                field_path="case_results.non_production",
            )
        object.__setattr__(
            self,
            "case_id",
            _validate_technical_id(self.case_id, field_path="case_results.case_id"),
        )
        object.__setattr__(
            self,
            "outcome",
            _parse_enum(
                PolicyOutcome,
                self.outcome,
                code="unsupported_policy_simulation_outcome",
                field_path="case_results.outcome",
            ),
        )
        object.__setattr__(
            self,
            "triggered_rule_ids",
            _validate_unique_ids(
                self.triggered_rule_ids,
                field_path="case_results.triggered_rule_ids",
            ),
        )
        object.__setattr__(
            self,
            "reason_code_refs",
            _validate_unique_ids(
                self.reason_code_refs,
                field_path="case_results.reason_code_refs",
            ),
        )
        object.__setattr__(
            self,
            "factor_refs",
            _validate_unique_ids(self.factor_refs, field_path="case_results.factor_refs"),
        )
        object.__setattr__(
            self,
            "validation_issues",
            _validate_issues(
                self.validation_issues,
                field_path="case_results.validation_issues",
            ),
        )


@dataclass(frozen=True, slots=True)
class PolicySimulationOutcomeCount:
    outcome: str
    count: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "outcome",
            _parse_enum(
                PolicyOutcome,
                self.outcome,
                code="unsupported_policy_simulation_outcome",
                field_path="summary.outcome_counts.outcome",
            ),
        )
        if self.count < 0:
            raise PolicyValidationError(
                "contagem de outcome inválida",
                code="invalid_policy_simulation_outcome_count",
                field_path="summary.outcome_counts.count",
            )


@dataclass(frozen=True, slots=True)
class PolicySimulationSummary:
    total_cases: int
    evaluated_cases: int
    issue_count: int
    outcome_counts: tuple[PolicySimulationOutcomeCount, ...]

    def __post_init__(self) -> None:
        if self.total_cases < 0 or self.evaluated_cases < 0 or self.issue_count < 0:
            raise PolicyValidationError(
                "sumário de simulação inválido",
                code="invalid_policy_simulation_summary",
                field_path="summary",
            )
        if self.evaluated_cases > self.total_cases:
            raise PolicyValidationError(
                "sumário de simulação inconsistente",
                code="inconsistent_policy_simulation_summary",
                field_path="summary.evaluated_cases",
            )
        outcome_counts = tuple(self.outcome_counts)
        for outcome_count in outcome_counts:
            if not isinstance(outcome_count, PolicySimulationOutcomeCount):
                raise PolicyValidationError(
                    "contagem de outcome inválida",
                    code="invalid_policy_simulation_outcome_count",
                    field_path="summary.outcome_counts",
                )
        object.__setattr__(self, "outcome_counts", outcome_counts)

    def count_for(self, outcome: str) -> int:
        parsed_outcome = _parse_enum(
            PolicyOutcome,
            outcome,
            code="unsupported_policy_simulation_outcome",
            field_path="summary.outcome",
        )
        for outcome_count in self.outcome_counts:
            if outcome_count.outcome == parsed_outcome:
                return outcome_count.count
        return 0


@dataclass(frozen=True, slots=True)
class PolicySimulationResult:
    simulation_id: str
    tenant_id: str
    policy_id: str
    policy_version_id: str
    policy_revision: int
    reason_code_catalog_id: str
    reason_code_catalog_version_id: str
    status: str
    non_production: bool
    case_results: tuple[PolicySimulationCaseResult, ...]
    validation_issues: tuple[PolicyValidationIssue, ...]
    correlation_id: str
    created_at: datetime
    simulation: bool = True
    summary: PolicySimulationSummary = field(init=False)

    def __post_init__(self) -> None:
        if self.simulation is not True or self.non_production is not True:
            raise PolicyValidationError(
                "resultado de simulação deve ser não produtivo",
                code="policy_simulation_must_be_non_production",
                field_path="non_production",
            )
        case_results = tuple(self.case_results)
        validation_issues = _validate_issues(
            self.validation_issues,
            field_path="validation_issues",
        )
        for case_result in case_results:
            if not isinstance(case_result, PolicySimulationCaseResult):
                raise PolicyValidationError(
                    "resultado de caso inválido",
                    code="invalid_policy_simulation_case_result",
                    field_path="case_results",
                )
        object.__setattr__(
            self,
            "simulation_id",
            validate_policy_simulation_id(self.simulation_id),
        )
        object.__setattr__(self, "tenant_id", validate_tenant_id(self.tenant_id))
        object.__setattr__(self, "policy_id", validate_policy_id(self.policy_id))
        object.__setattr__(
            self,
            "policy_version_id",
            validate_policy_version_id(self.policy_version_id),
        )
        if not isinstance(self.policy_revision, int) or self.policy_revision < 1:
            raise PolicyValidationError(
                "revisão da política inválida",
                code="invalid_policy_revision",
                field_path="policy_revision",
            )
        object.__setattr__(self, "policy_revision", self.policy_revision)
        object.__setattr__(
            self,
            "reason_code_catalog_id",
            validate_reason_code_catalog_id(self.reason_code_catalog_id),
        )
        object.__setattr__(
            self,
            "reason_code_catalog_version_id",
            validate_reason_code_catalog_version_id(self.reason_code_catalog_version_id),
        )
        object.__setattr__(
            self,
            "status",
            _parse_enum(
                PolicySimulationStatus,
                self.status,
                code="unsupported_policy_simulation_status",
                field_path="status",
            ),
        )
        object.__setattr__(self, "case_results", case_results)
        object.__setattr__(self, "validation_issues", validation_issues)
        object.__setattr__(self, "correlation_id", validate_correlation_id(self.correlation_id))
        object.__setattr__(
            self,
            "created_at",
            _validate_aware_utc_datetime(self.created_at, field_path="created_at"),
        )
        object.__setattr__(
            self,
            "summary",
            _build_summary(
                case_results=case_results,
                validation_issues=validation_issues,
            ),
        )

    @classmethod
    def restore(
        cls,
        *,
        simulation_id: str,
        tenant_id: str,
        policy_id: str,
        policy_version_id: str,
        policy_revision: int,
        reason_code_catalog_id: str,
        reason_code_catalog_version_id: str,
        status: str,
        non_production: bool,
        case_results: tuple[PolicySimulationCaseResult, ...],
        validation_issues: tuple[PolicyValidationIssue, ...],
        correlation_id: str,
        created_at: datetime,
    ) -> PolicySimulationResult:
        return cls(
            simulation_id=simulation_id,
            tenant_id=tenant_id,
            policy_id=policy_id,
            policy_version_id=policy_version_id,
            policy_revision=policy_revision,
            reason_code_catalog_id=reason_code_catalog_id,
            reason_code_catalog_version_id=reason_code_catalog_version_id,
            status=status,
            non_production=non_production,
            case_results=case_results,
            validation_issues=validation_issues,
            correlation_id=correlation_id,
            created_at=created_at,
        )


def _validate_simulation_field_value(
    field_name: str,
    value: int,
    *,
    field_path: str,
) -> int:
    parsed_value = _validate_rule_value(value, field_path=field_path)
    if type(parsed_value) is not int:
        raise PolicyValidationError(
            "valor de simulação incompatível com campo governado",
            code="simulation_value_type_mismatch",
            field_path=field_path,
        )
    _validate_policy_field(field_name, field_path="simulation_cases.fields")
    return cast("int", parsed_value)


def _validate_unique_ids(values: tuple[str, ...], *, field_path: str) -> tuple[str, ...]:
    parsed_values = tuple(_validate_technical_id(value, field_path=field_path) for value in values)
    if len(set(parsed_values)) != len(parsed_values):
        raise PolicyValidationError(
            "identificador duplicado",
            code="duplicate_policy_simulation_identifier",
            field_path=field_path,
        )
    return parsed_values


def _validate_issues(
    issues: tuple[PolicyValidationIssue, ...],
    *,
    field_path: str,
) -> tuple[PolicyValidationIssue, ...]:
    parsed_issues = tuple(issues)
    for issue in parsed_issues:
        if not isinstance(issue, PolicyValidationIssue):
            raise PolicyValidationError(
                "issue de validação inválida",
                code="invalid_policy_validation_issue",
                field_path=field_path,
            )
    return parsed_issues


def _build_summary(
    *,
    case_results: tuple[PolicySimulationCaseResult, ...],
    validation_issues: tuple[PolicyValidationIssue, ...],
) -> PolicySimulationSummary:
    counts = {outcome.value: 0 for outcome in PolicyOutcome}
    for case_result in case_results:
        counts[case_result.outcome] += 1
    total_issues = len(validation_issues) + sum(
        len(case_result.validation_issues) for case_result in case_results
    )
    return PolicySimulationSummary(
        total_cases=len(case_results),
        evaluated_cases=len(case_results),
        issue_count=total_issues,
        outcome_counts=tuple(
            PolicySimulationOutcomeCount(outcome=outcome.value, count=counts[outcome.value])
            for outcome in PolicyOutcome
        ),
    )
