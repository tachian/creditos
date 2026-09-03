from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime

from creditos_decision.domain.errors import PolicyValidationError
from creditos_decision.domain.value_objects.policy import (
    PolicyLimit,
    _validate_aware_utc_datetime,
    _validate_policy_field,
    _validate_rule_value,
    _validate_technical_id,
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
        return adjusted_terms


def validate_decided_at(value: datetime) -> datetime:
    return _validate_aware_utc_datetime(value, field_path="decided_at")


def input_fingerprint_for(field_values: tuple[CreditDecisionInputFieldValue, ...]) -> str:
    payload = tuple(
        {"field": field_value.field, "value": field_value.value}
        for field_value in sorted(field_values, key=lambda item: item.field)
    )
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()
