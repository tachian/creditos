from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from math import isfinite
from types import MappingProxyType

from creditos_security import mask_text

from creditos_automated_review.domain.errors import AutomatedReviewValidationError
from creditos_automated_review.domain.value_objects.review_agent_config import (
    validate_agent_version,
)

type SafeInputValue = str | int | float | bool

_TECHNICAL_TOKEN_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9_.-]{1,127}")
_TECHNICAL_REF_SECRET_PATTERN = re.compile(
    r"^(?:sk-[A-Za-z0-9_-]{8,}|AKIA[A-Z0-9]{12,}|[A-Za-z0-9_-]{32,})$"
)
_HEX_FINGERPRINT_PATTERN = re.compile(r"[0-9a-f]{64}")
_RAW_PAYLOAD_FIELDS = frozenset(
    {
        "body",
        "payload",
        "raw_payload",
        "provider_payload",
        "external_payload",
        "request_payload",
        "response_payload",
        "request_body",
        "response_body",
        "headers",
        "request_headers",
        "response_headers",
        "authorization",
    }
)
_RAW_PAYLOAD_COMPACT_PARTS = frozenset(
    {
        "payload",
        "rawpayload",
        "providerpayload",
        "externalpayload",
        "requestpayload",
        "responsepayload",
        "requestbody",
        "responsebody",
        "requestheaders",
        "responseheaders",
        "headers",
        "authorization",
    }
)
_SENSITIVE_FIELD_PARTS = (
    "cpf",
    "cnpj",
    "email",
    "phone",
    "telefone",
    "nome",
    "name",
    "address",
    "endereco",
    "endereço",
    "document",
    "documento",
    "token",
    "secret",
    "senha",
    "password",
    "credential",
)
_SENSITIVE_REF_PARTS = _SENSITIVE_FIELD_PARTS + (
    "api_key",
    "apikey",
    "authorization",
    "bearer",
    "cookie",
    "private",
)
_ALLOWED_FIELD_SCHEMAS = {
    "requested_amount_units": (0, 1_000_000_000_000),
    "requested_installments": (1, 600),
    "requested_term_days": (1, 36_500),
    "monthly_income_units": (0, 1_000_000_000_000),
    "declared_revenue_units": (0, 1_000_000_000_000),
    "company_age_months": (0, 2_400),
    "relationship_age_days": (0, 73_000),
}


class ReviewInputAction(StrEnum):
    INCLUDED = "included"
    MASKED = "masked"
    OMITTED = "omitted"
    REFERENCED = "referenced"
    TOKENIZED = "tokenized"


@dataclass(frozen=True, slots=True)
class ReviewInputCandidate:
    field_name: str
    value: SafeInputValue
    source_ref: str | None = None
    token_ref: str | None = None

    def __post_init__(self) -> None:
        field_name = _validate_field_name(self.field_name)
        if _is_raw_payload_field(field_name):
            raise AutomatedReviewValidationError(
                "payload bruto não é aceito como entrada governada",
                code="automated_review_raw_payload_not_allowed",
                field_path="candidate_inputs",
            )
        object.__setattr__(self, "field_name", field_name)
        object.__setattr__(self, "value", _validate_safe_input_value(self.value, field_name))
        if self.source_ref is not None:
            object.__setattr__(
                self,
                "source_ref",
                validate_safe_review_reference(
                    self.source_ref, field_path=f"{field_name}.source_ref"
                ),
            )
        if self.token_ref is not None:
            object.__setattr__(
                self,
                "token_ref",
                validate_safe_review_reference(
                    self.token_ref, field_path=f"{field_name}.token_ref"
                ),
            )
        if self.source_ref is not None and self.token_ref is not None:
            raise AutomatedReviewValidationError(
                "referência e token são mutuamente exclusivos",
                code="automated_review_input_reference_conflict",
                field_path=field_name,
            )

    @classmethod
    def create(
        cls,
        field_name: str,
        value: SafeInputValue,
        *,
        source_ref: str | None = None,
        token_ref: str | None = None,
    ) -> ReviewInputCandidate:
        return cls(
            field_name=field_name,
            value=value,
            source_ref=source_ref,
            token_ref=token_ref,
        )


@dataclass(frozen=True, slots=True)
class MinimizedReviewInputField:
    field_name: str
    action: str
    safe_value: SafeInputValue | None
    reason: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "field_name", _validate_field_name(self.field_name))
        action = self.action.strip() if isinstance(self.action, str) else ""
        if action not in {item.value for item in ReviewInputAction}:
            raise AutomatedReviewValidationError(
                "ação de minimização inválida",
                code="automated_review_invalid_minimization_action",
                field_path=f"{self.field_name}.action",
            )
        object.__setattr__(self, "action", action)
        if self.safe_value is not None:
            object.__setattr__(
                self,
                "safe_value",
                _validate_safe_input_value(self.safe_value, self.field_name),
            )
        object.__setattr__(
            self,
            "reason",
            validate_review_technical_token(self.reason, field_path=f"{self.field_name}.reason"),
        )


@dataclass(frozen=True, slots=True)
class InputMinimizationPlan:
    policy_ref: str
    prompt_fingerprint: str
    fields: tuple[MinimizedReviewInputField, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "policy_ref",
            validate_agent_version(self.policy_ref, field_path="minimization_policy_ref"),
        )
        object.__setattr__(
            self,
            "prompt_fingerprint",
            validate_prompt_fingerprint(self.prompt_fingerprint),
        )
        fields = tuple(self.fields)
        if not fields:
            raise AutomatedReviewValidationError(
                "plano de minimização sem campos",
                code="automated_review_empty_minimization_plan",
                field_path="candidate_inputs",
            )
        names = [field.field_name for field in fields]
        if len(set(names)) != len(names):
            raise AutomatedReviewValidationError(
                "campo duplicado na entrada consultiva",
                code="automated_review_duplicate_input_field",
                field_path="candidate_inputs",
            )
        object.__setattr__(self, "fields", fields)

    @classmethod
    def create(
        cls,
        *,
        policy_ref: str,
        prompt_fingerprint: str,
        allowed_fields: tuple[str, ...],
        candidates: tuple[ReviewInputCandidate, ...],
    ) -> InputMinimizationPlan:
        allowed = frozenset(allowed_fields)
        fields = tuple(_minimize_candidate(candidate, allowed) for candidate in candidates)
        return cls(
            policy_ref=policy_ref,
            prompt_fingerprint=prompt_fingerprint,
            fields=fields,
        )

    @property
    def input_for_execution(self) -> MappingProxyType[str, SafeInputValue]:
        return MappingProxyType(
            {
                field.field_name: field.safe_value
                for field in self.fields
                if field.action == ReviewInputAction.INCLUDED.value and field.safe_value is not None
            }
        )

    @property
    def counts_by_action(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for field in self.fields:
            counts[field.action] = counts.get(field.action, 0) + 1
        return counts

    def action_for(self, field_name: str) -> MinimizedReviewInputField:
        normalized = _validate_field_name(field_name)
        for field in self.fields:
            if field.field_name == normalized:
                return field
        raise AutomatedReviewValidationError(
            "campo não encontrado no plano de minimização",
            code="automated_review_input_field_not_found",
            field_path=normalized,
        )


def _minimize_candidate(
    candidate: ReviewInputCandidate,
    allowed_fields: frozenset[str],
) -> MinimizedReviewInputField:
    if candidate.field_name in allowed_fields:
        if _is_sensitive(candidate.field_name, candidate.value):
            return MinimizedReviewInputField(
                field_name=candidate.field_name,
                action=ReviewInputAction.MASKED.value,
                safe_value=_masked_value(candidate.value),
                reason="allowed_field_sensitive_value_masked",
            )
        return MinimizedReviewInputField(
            field_name=candidate.field_name,
            action=ReviewInputAction.INCLUDED.value,
            safe_value=candidate.value,
            reason="allowed_by_prompt_input_allowlist",
        )
    if candidate.source_ref is not None:
        return MinimizedReviewInputField(
            field_name=candidate.field_name,
            action=ReviewInputAction.REFERENCED.value,
            safe_value=candidate.source_ref,
            reason="not_allowlisted_replaced_by_source_ref",
        )
    if candidate.token_ref is not None:
        return MinimizedReviewInputField(
            field_name=candidate.field_name,
            action=ReviewInputAction.TOKENIZED.value,
            safe_value=candidate.token_ref,
            reason="not_allowlisted_replaced_by_token_ref",
        )
    if _is_sensitive(candidate.field_name, candidate.value):
        return MinimizedReviewInputField(
            field_name=candidate.field_name,
            action=ReviewInputAction.MASKED.value,
            safe_value=_masked_value(candidate.value),
            reason="not_allowlisted_sensitive_value_masked",
        )
    return MinimizedReviewInputField(
        field_name=candidate.field_name,
        action=ReviewInputAction.OMITTED.value,
        safe_value=None,
        reason="not_allowlisted_omitted",
    )


def _validate_field_name(value: str) -> str:
    return validate_review_technical_token(value, field_path="candidate_input.field_name")


def validate_review_technical_token(value: str, *, field_path: str) -> str:
    if not isinstance(value, str):
        raise AutomatedReviewValidationError(
            "identificador técnico inválido",
            code="automated_review_invalid_technical_token",
            field_path=field_path,
        )
    normalized = value.strip()
    if _TECHNICAL_TOKEN_PATTERN.fullmatch(normalized) is None:
        raise AutomatedReviewValidationError(
            "identificador técnico inválido",
            code="automated_review_invalid_technical_token",
            field_path=field_path,
        )
    return normalized


def validate_safe_review_reference(value: str, *, field_path: str) -> str:
    technical_ref = validate_review_technical_token(value, field_path=field_path)
    lowered = technical_ref.casefold()
    if (
        mask_text(technical_ref) != technical_ref
        or any(part in lowered for part in _SENSITIVE_REF_PARTS)
        or _TECHNICAL_REF_SECRET_PATTERN.fullmatch(technical_ref) is not None
    ):
        raise AutomatedReviewValidationError(
            "referência técnica sensível não permitida",
            code="automated_review_sensitive_reference",
            field_path=field_path,
        )
    return technical_ref


def validate_non_sensitive_execution_reference(value: str, *, field_path: str) -> str:
    lowered = value.casefold()
    if (
        mask_text(value) != value
        or any(part in lowered for part in _SENSITIVE_REF_PARTS)
        or _TECHNICAL_REF_SECRET_PATTERN.fullmatch(value) is not None
    ):
        raise AutomatedReviewValidationError(
            "referência de execução sensível não permitida",
            code="automated_review_sensitive_execution_reference",
            field_path=field_path,
        )
    return value


def validate_prompt_fingerprint(value: str) -> str:
    if not isinstance(value, str) or _HEX_FINGERPRINT_PATTERN.fullmatch(value) is None:
        raise AutomatedReviewValidationError(
            "fingerprint inválido",
            code="automated_review_invalid_prompt_fingerprint",
            field_path="prompt_fingerprint",
        )
    return value


def _validate_safe_input_value(value: SafeInputValue, field_path: str) -> SafeInputValue:
    if field_path in _ALLOWED_FIELD_SCHEMAS:
        return _validate_allowed_numeric_input_value(value, field_path)
    if type(value) is bool:
        return value
    if type(value) is int:
        return value
    if type(value) is float:
        if not isfinite(value):
            raise AutomatedReviewValidationError(
                "valor numérico inválido",
                code="automated_review_invalid_input_value",
                field_path=field_path,
            )
        return value
    if type(value) is str:
        normalized = " ".join(value.strip().split())
        if not normalized or len(normalized) > 500:
            raise AutomatedReviewValidationError(
                "valor textual inválido",
                code="automated_review_invalid_input_value",
                field_path=field_path,
            )
        return normalized
    raise AutomatedReviewValidationError(
        "valor de entrada não governado",
        code="automated_review_unsupported_input_value",
        field_path=field_path,
    )


def _validate_allowed_numeric_input_value(value: SafeInputValue, field_path: str) -> int | float:
    minimum, maximum = _ALLOWED_FIELD_SCHEMAS[field_path]
    if type(value) is int or type(value) is float and isfinite(value):
        numeric = value
    else:
        raise AutomatedReviewValidationError(
            "valor numérico governado inválido",
            code="automated_review_invalid_governed_numeric_value",
            field_path=field_path,
        )
    if numeric < minimum or numeric > maximum:
        raise AutomatedReviewValidationError(
            "valor numérico governado fora da faixa permitida",
            code="automated_review_governed_numeric_value_out_of_range",
            field_path=field_path,
        )
    return numeric


def _is_raw_payload_field(field_name: str) -> bool:
    compact = re.sub(r"[^a-z0-9]", "", field_name.casefold())
    return (
        field_name.casefold() in _RAW_PAYLOAD_FIELDS
        or compact in _RAW_PAYLOAD_COMPACT_PARTS
        or any(part in compact for part in _RAW_PAYLOAD_COMPACT_PARTS)
    )


def _is_sensitive(field_name: str, value: SafeInputValue) -> bool:
    normalized_name = field_name.casefold()
    if any(part in normalized_name for part in _SENSITIVE_FIELD_PARTS):
        return True
    if isinstance(value, str):
        return mask_text(value) != value
    return False


def _masked_value(value: SafeInputValue) -> SafeInputValue | None:
    if isinstance(value, str):
        masked = mask_text(value)
        if masked != value:
            return masked
    return None
