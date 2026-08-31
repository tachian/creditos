from __future__ import annotations

from dataclasses import dataclass

from creditos_decision.domain.errors import PolicyValidationError
from creditos_decision.domain.value_objects.policy import (
    PolicyOutcome,
    _parse_enum,
    _validate_safe_text,
    _validate_technical_id,
)


@dataclass(frozen=True, slots=True)
class PolicyEvaluationIssue:
    code: str
    field_path: str
    message: str
    severity: str = "error"

    def __post_init__(self) -> None:
        if self.severity not in {"error", "warning"}:
            raise PolicyValidationError(
                "severidade inválida",
                code="unsupported_policy_evaluation_severity",
                field_path="validation_issues.severity",
            )
        object.__setattr__(
            self,
            "code",
            _validate_technical_id(self.code, field_path="validation_issues.code"),
        )
        object.__setattr__(
            self,
            "field_path",
            _validate_safe_text(self.field_path, field_path="validation_issues.field_path"),
        )
        object.__setattr__(
            self,
            "message",
            _validate_safe_text(self.message, field_path="validation_issues.message"),
        )

    @classmethod
    def create(
        cls,
        *,
        code: str,
        field_path: str,
        message: str,
        severity: str = "error",
    ) -> PolicyEvaluationIssue:
        return cls(code=code, field_path=field_path, message=message, severity=severity)


@dataclass(frozen=True, slots=True)
class PolicyEvaluationResult:
    evaluation_id: str
    outcome: str
    triggered_rule_ids: tuple[str, ...]
    reason_code_refs: tuple[str, ...]
    factor_refs: tuple[str, ...]
    validation_issues: tuple[PolicyEvaluationIssue, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "evaluation_id",
            _validate_technical_id(self.evaluation_id, field_path="evaluation_id"),
        )
        object.__setattr__(
            self,
            "outcome",
            _parse_enum(
                PolicyOutcome,
                self.outcome,
                code="unsupported_policy_evaluation_outcome",
                field_path="outcome",
            ),
        )
        object.__setattr__(
            self,
            "triggered_rule_ids",
            _validate_unique_ids(self.triggered_rule_ids, field_path="triggered_rule_ids"),
        )
        object.__setattr__(
            self,
            "reason_code_refs",
            _validate_unique_ids(self.reason_code_refs, field_path="reason_code_refs"),
        )
        object.__setattr__(
            self,
            "factor_refs",
            _validate_unique_ids(self.factor_refs, field_path="factor_refs"),
        )
        for issue in self.validation_issues:
            if not isinstance(issue, PolicyEvaluationIssue):
                raise PolicyValidationError(
                    "issue de avaliação inválida",
                    code="invalid_policy_evaluation_issue",
                    field_path="validation_issues",
                )
        object.__setattr__(self, "validation_issues", tuple(self.validation_issues))


def _validate_unique_ids(values: tuple[str, ...], *, field_path: str) -> tuple[str, ...]:
    parsed = tuple(_validate_technical_id(value, field_path=field_path) for value in values)
    if len(set(parsed)) != len(parsed):
        raise PolicyValidationError(
            "identificador duplicado",
            code="duplicate_policy_evaluation_identifier",
            field_path=field_path,
        )
    return parsed
