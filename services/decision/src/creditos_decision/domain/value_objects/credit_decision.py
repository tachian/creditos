from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from creditos_decision.domain.errors import PolicyValidationError
from creditos_decision.domain.value_objects.policy import (
    PolicyLimit,
    PolicyOutcome,
    _parse_enum,
    _validate_aware_utc_datetime,
    _validate_policy_field,
    _validate_rule_value,
    _validate_safe_text,
    _validate_technical_id,
    parse_policy_fallback_action,
    parse_product_type,
    validate_correlation_id,
    validate_policy_id,
    validate_policy_version_id,
    validate_tenant_id,
)
from creditos_decision.domain.value_objects.reason_codes import (
    ReasonCodeAudience,
    validate_reason_code_catalog_id,
    validate_reason_code_catalog_version_id,
)


def validate_credit_decision_id(value: str) -> str:
    return _validate_technical_id(value, field_path="decision_id")


def validate_proposal_id(value: str) -> str:
    return _validate_technical_id(value, field_path="proposal_id")


@dataclass(frozen=True, slots=True)
class CreditDecisionInputFieldValue:
    field: str
    value: int

    def __post_init__(self) -> None:
        parsed_field = _validate_policy_field(self.field, field_path="decision_input.fields")
        parsed_value = _validate_rule_value(
            self.value,
            field_path=f"decision_input.values.{parsed_field}",
        )
        if type(parsed_value) is not int:
            raise PolicyValidationError(
                "valor produtivo deve ser numérico",
                code="invalid_credit_decision_field_value",
                field_path=f"decision_input.values.{parsed_field}",
            )
        object.__setattr__(self, "field", parsed_field)
        object.__setattr__(self, "value", parsed_value)

    @classmethod
    def create(cls, *, field: str, value: int) -> CreditDecisionInputFieldValue:
        return cls(field=field, value=value)


@dataclass(frozen=True, slots=True)
class CreditDecisionInput:
    proposal_id: str
    field_values: tuple[CreditDecisionInputFieldValue, ...]
    integration_result_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        field_values = tuple(self.field_values)
        if not field_values:
            raise PolicyValidationError(
                "entrada de decisão sem campos",
                code="empty_credit_decision_input",
                field_path="decision_input.field_values",
            )
        for field_value in field_values:
            if not isinstance(field_value, CreditDecisionInputFieldValue):
                raise PolicyValidationError(
                    "valor de campo de decisão inválido",
                    code="invalid_credit_decision_field_value",
                    field_path="decision_input.field_values",
                )
        fields = [field_value.field for field_value in field_values]
        if len(set(fields)) != len(fields):
            raise PolicyValidationError(
                "campo duplicado na entrada de decisão",
                code="duplicate_credit_decision_field",
                field_path="decision_input.field_values",
            )
        integration_refs = tuple(
            _validate_technical_id(reference, field_path="integration_result_refs")
            for reference in self.integration_result_refs
        )
        if len(set(integration_refs)) != len(integration_refs):
            raise PolicyValidationError(
                "referência de integração duplicada",
                code="duplicate_integration_result_ref",
                field_path="integration_result_refs",
            )
        object.__setattr__(self, "proposal_id", validate_proposal_id(self.proposal_id))
        object.__setattr__(self, "field_values", field_values)
        object.__setattr__(self, "integration_result_refs", integration_refs)

    @classmethod
    def create(
        cls,
        *,
        proposal_id: str,
        values: Mapping[str, int],
        integration_result_refs: tuple[str, ...] = (),
    ) -> CreditDecisionInput:
        return cls(
            proposal_id=proposal_id,
            field_values=tuple(
                CreditDecisionInputFieldValue.create(field=field_name, value=field_value)
                for field_name, field_value in values.items()
            ),
            integration_result_refs=integration_result_refs,
        )

    def value_for(self, field_name: str) -> int | None:
        for field_value in self.field_values:
            if field_value.field == field_name:
                return field_value.value
        return None


@dataclass(frozen=True, slots=True)
class CreditDecisionApprovedTerms:
    approved_amount_units: int
    approved_installments: int
    approved_term_days: int

    def __post_init__(self) -> None:
        for field_name, value in (
            ("approved_amount_units", self.approved_amount_units),
            ("approved_installments", self.approved_installments),
            ("approved_term_days", self.approved_term_days),
        ):
            if type(value) is not int or value < 0 or value > 10_000_000_000:
                raise PolicyValidationError(
                    "termo aprovado inválido",
                    code="invalid_approved_term",
                    field_path=field_name,
                )

    @classmethod
    def from_decision_input(
        cls,
        decision_input: CreditDecisionInput,
    ) -> CreditDecisionApprovedTerms | None:
        amount = decision_input.value_for("requested_amount_units")
        installments = decision_input.value_for("requested_installments")
        term_days = decision_input.value_for("requested_term_days")
        if amount is None or installments is None or term_days is None:
            return None
        return cls(
            approved_amount_units=amount,
            approved_installments=installments,
            approved_term_days=term_days,
        )

    @classmethod
    def adjusted_from_policy_limits(
        cls,
        decision_input: CreditDecisionInput,
        limits: tuple[PolicyLimit, ...],
    ) -> CreditDecisionApprovedTerms | None:
        requested_terms = cls.from_decision_input(decision_input)
        if requested_terms is None:
            return None
        amount = requested_terms.approved_amount_units
        installments = requested_terms.approved_installments
        term_days = requested_terms.approved_term_days
        max_amount = None
        max_installments = None
        max_term_days = None
        for policy_limit in limits:
            if policy_limit.limit_type == "max_amount_units":
                max_amount = (
                    policy_limit.value
                    if max_amount is None
                    else min(max_amount, policy_limit.value)
                )
            elif policy_limit.limit_type == "max_installments":
                max_installments = (
                    policy_limit.value
                    if max_installments is None
                    else min(max_installments, policy_limit.value)
                )
            elif policy_limit.limit_type == "max_term_days":
                max_term_days = (
                    policy_limit.value
                    if max_term_days is None
                    else min(max_term_days, policy_limit.value)
                )
        if max_amount is not None:
            amount = min(amount, max_amount)
        if max_installments is not None:
            installments = min(installments, max_installments)
        if max_term_days is not None:
            term_days = min(term_days, max_term_days)
        adjusted_terms = cls(
            approved_amount_units=amount,
            approved_installments=installments,
            approved_term_days=term_days,
        )
        if adjusted_terms == requested_terms:
            return None
        if not _approved_terms_satisfy_policy_limits(adjusted_terms, limits):
            return None
        return adjusted_terms


class CreditDecisionExplanationAudience(StrEnum):
    CUSTOMER = "customer"
    INTERNAL = "internal"


class CreditDecisionExplanationStatus(StrEnum):
    COMPLETED = "completed"
    REQUIRES_INPUT = "requires_input"
    UNABLE_TO_DECIDE = "unable_to_decide"


@dataclass(frozen=True, slots=True)
class CreditDecisionExplanationReasonCode:
    code: str
    title: str
    description: str
    severity: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "code",
            _validate_technical_id(self.code, field_path="reason_codes.code"),
        )
        object.__setattr__(
            self,
            "title",
            _validate_explanation_text(self.title, field_path="reason_codes.title"),
        )
        object.__setattr__(
            self,
            "description",
            _validate_explanation_text(
                self.description,
                field_path="reason_codes.description",
            ),
        )
        object.__setattr__(
            self,
            "severity",
            _validate_technical_id(self.severity, field_path="reason_codes.severity"),
        )


@dataclass(frozen=True, slots=True)
class CreditDecisionExplanationFactor:
    factor_id: str
    field: str
    title: str
    description: str
    required: bool

    def __post_init__(self) -> None:
        if type(self.required) is not bool:
            raise PolicyValidationError(
                "obrigatoriedade inválida",
                code="invalid_credit_decision_explanation_factor_required",
                field_path="factors.required",
            )
        object.__setattr__(
            self,
            "factor_id",
            _validate_technical_id(self.factor_id, field_path="factors.factor_id"),
        )
        object.__setattr__(
            self, "field", _validate_policy_field(self.field, field_path="factors.field")
        )
        object.__setattr__(
            self, "title", _validate_explanation_text(self.title, field_path="factors.title")
        )
        object.__setattr__(
            self,
            "description",
            _validate_explanation_text(self.description, field_path="factors.description"),
        )


@dataclass(frozen=True, slots=True)
class CreditDecisionExplanationIssue:
    code: str
    field_path: str
    message: str

    def __post_init__(self) -> None:
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
            _validate_explanation_text(self.message, field_path="validation_issues.message"),
        )


@dataclass(frozen=True, slots=True)
class CreditDecisionExplanationResponse:
    decision_id: str
    proposal_id: str
    tenant_id: str
    product_type: str
    channel: str
    status: str
    outcome: str
    decided_at: datetime
    correlation_id: str
    policy_id: str
    policy_version_id: str
    policy_revision: int
    reason_code_catalog_id: str
    reason_code_catalog_version_id: str
    triggered_rule_ids: tuple[str, ...]
    reason_codes: tuple[CreditDecisionExplanationReasonCode, ...]
    factors: tuple[CreditDecisionExplanationFactor, ...]
    fallback_action: str | None
    required_data_refs: tuple[str, ...]
    validation_issue_codes: tuple[str, ...]
    validation_issues: tuple[CreditDecisionExplanationIssue, ...]
    approved_terms: CreditDecisionApprovedTerms | None
    decision_fingerprint: str

    def __post_init__(self) -> None:
        if not isinstance(self.policy_revision, int) or self.policy_revision < 1:
            raise PolicyValidationError(
                "revisão de política inválida",
                code="invalid_explanation_policy_revision",
                field_path="policy_revision",
            )
        for reason_code in self.reason_codes:
            if not isinstance(reason_code, CreditDecisionExplanationReasonCode):
                raise PolicyValidationError(
                    "reason code explicável inválido",
                    code="invalid_explanation_reason_code",
                    field_path="reason_codes",
                )
        for factor in self.factors:
            if not isinstance(factor, CreditDecisionExplanationFactor):
                raise PolicyValidationError(
                    "fator explicável inválido",
                    code="invalid_explanation_factor",
                    field_path="factors",
                )
        for issue in self.validation_issues:
            if not isinstance(issue, CreditDecisionExplanationIssue):
                raise PolicyValidationError(
                    "issue explicável inválida",
                    code="invalid_explanation_issue",
                    field_path="validation_issues",
                )
        object.__setattr__(self, "decision_id", validate_credit_decision_id(self.decision_id))
        object.__setattr__(self, "proposal_id", validate_proposal_id(self.proposal_id))
        object.__setattr__(self, "tenant_id", validate_tenant_id(self.tenant_id))
        object.__setattr__(self, "product_type", parse_product_type(self.product_type))
        object.__setattr__(
            self,
            "channel",
            _validate_technical_id(self.channel, field_path="channel"),
        )
        object.__setattr__(
            self,
            "status",
            _parse_enum(
                CreditDecisionExplanationStatus,
                self.status,
                code="unsupported_explanation_status",
                field_path="status",
            ),
        )
        object.__setattr__(
            self,
            "outcome",
            _parse_enum(
                PolicyOutcome,
                self.outcome,
                code="unsupported_explanation_outcome",
                field_path="outcome",
            ),
        )
        object.__setattr__(self, "decided_at", validate_decided_at(self.decided_at))
        object.__setattr__(self, "correlation_id", validate_correlation_id(self.correlation_id))
        object.__setattr__(self, "policy_id", validate_policy_id(self.policy_id))
        object.__setattr__(
            self,
            "policy_version_id",
            validate_policy_version_id(self.policy_version_id),
        )
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
            "triggered_rule_ids",
            _validate_unique_technical_ids(
                self.triggered_rule_ids,
                field_path="triggered_rule_ids",
            ),
        )
        object.__setattr__(self, "reason_codes", tuple(self.reason_codes))
        object.__setattr__(self, "factors", tuple(self.factors))
        if self.fallback_action is not None:
            object.__setattr__(
                self,
                "fallback_action",
                parse_policy_fallback_action(self.fallback_action),
            )
        object.__setattr__(
            self,
            "required_data_refs",
            _validate_unique_technical_ids(
                self.required_data_refs,
                field_path="required_data_refs",
            ),
        )
        object.__setattr__(
            self,
            "validation_issue_codes",
            _validate_unique_technical_ids(
                self.validation_issue_codes,
                field_path="validation_issue_codes",
            ),
        )
        object.__setattr__(self, "validation_issues", tuple(self.validation_issues))
        object.__setattr__(
            self,
            "decision_fingerprint",
            _validate_hex_fingerprint(self.decision_fingerprint),
        )


def parse_credit_decision_explanation_audience(value: str) -> str:
    return _parse_enum(
        CreditDecisionExplanationAudience,
        value,
        code="unsupported_credit_decision_explanation_audience",
        field_path="audience",
    )


def parse_credit_decision_explanation_status(value: str) -> str:
    return _parse_enum(
        CreditDecisionExplanationStatus,
        value,
        code="unsupported_explanation_status",
        field_path="status",
    )


def reason_code_visible_for_audience(*, reason_code_audience: str, audience: str) -> bool:
    if audience == CreditDecisionExplanationAudience.INTERNAL.value:
        return True
    return reason_code_audience in {
        ReasonCodeAudience.CUSTOMER.value,
        ReasonCodeAudience.BOTH.value,
    }


def validate_decided_at(value: datetime) -> datetime:
    return _validate_aware_utc_datetime(value, field_path="decided_at")


def _approved_terms_satisfy_policy_limits(
    approved_terms: CreditDecisionApprovedTerms,
    limits: tuple[PolicyLimit, ...],
) -> bool:
    for policy_limit in limits:
        if (
            policy_limit.limit_type == "max_amount_units"
            and approved_terms.approved_amount_units > policy_limit.value
        ):
            return False
        if (
            policy_limit.limit_type == "min_amount_units"
            and approved_terms.approved_amount_units < policy_limit.value
        ):
            return False
        if (
            policy_limit.limit_type == "max_installments"
            and approved_terms.approved_installments > policy_limit.value
        ):
            return False
        if (
            policy_limit.limit_type == "max_term_days"
            and approved_terms.approved_term_days > policy_limit.value
        ):
            return False
        if (
            policy_limit.limit_type == "min_term_days"
            and approved_terms.approved_term_days < policy_limit.value
        ):
            return False
    return True


def input_fingerprint_for(field_values: tuple[CreditDecisionInputFieldValue, ...]) -> str:
    payload = tuple(
        {"field": field_value.field, "value": field_value.value}
        for field_value in sorted(field_values, key=lambda item: item.field)
    )
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


_DETAILED_NUMERIC_VALUE_PATTERN = re.compile(r"\d[\d_.-]{3,}")


def _validate_explanation_text(value: str, *, field_path: str) -> str:
    parsed = _validate_safe_text(value, field_path=field_path)
    if _DETAILED_NUMERIC_VALUE_PATTERN.search(parsed):
        raise PolicyValidationError(
            "texto explicável não pode conter valor numérico detalhado",
            code="explanation_text_contains_detailed_numeric_value",
            field_path=field_path,
        )
    return parsed


def _validate_unique_technical_ids(values: tuple[str, ...], *, field_path: str) -> tuple[str, ...]:
    parsed = tuple(_validate_technical_id(value, field_path=field_path) for value in values)
    if len(set(parsed)) != len(parsed):
        raise PolicyValidationError(
            "identificador duplicado",
            code="duplicate_credit_decision_explanation_identifier",
            field_path=field_path,
        )
    return parsed


def _validate_hex_fingerprint(value: str) -> str:
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise PolicyValidationError(
            "fingerprint inválido",
            code="invalid_credit_decision_explanation_fingerprint",
            field_path="decision_fingerprint",
        )
    return value
