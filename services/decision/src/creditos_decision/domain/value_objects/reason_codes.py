from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import cast

from creditos_decision.domain.errors import PolicyValidationError
from creditos_decision.domain.value_objects.policy import (
    PolicyOutcome,
    _parse_enum,
    _validate_policy_field,
    _validate_safe_text,
    _validate_technical_id,
)


class ReasonCodeStatus(StrEnum):
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


class ReasonCodeSeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ReasonCodeAudience(StrEnum):
    INTERNAL = "internal"
    CUSTOMER = "customer"
    BOTH = "both"


class ReasonCodeCatalogStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class ReasonCodeCatalogChangeType(StrEnum):
    CREATED = "created"
    UPDATED = "updated"
    PUBLISHED = "published"
    VERSIONED = "versioned"


@dataclass(frozen=True, slots=True)
class ExplainableFactor:
    factor_id: str
    field: str
    title: str
    internal_description: str
    external_description: str
    audience: str = "both"
    required: bool = False

    def __post_init__(self) -> None:
        parsed = _normalize_explainable_factor(
            factor_id=self.factor_id,
            field=self.field,
            title=self.title,
            internal_description=self.internal_description,
            external_description=self.external_description,
            audience=self.audience,
            required=self.required,
        )
        object.__setattr__(self, "factor_id", parsed["factor_id"])
        object.__setattr__(self, "field", parsed["field"])
        object.__setattr__(self, "title", parsed["title"])
        object.__setattr__(self, "internal_description", parsed["internal_description"])
        object.__setattr__(self, "external_description", parsed["external_description"])
        object.__setattr__(self, "audience", parsed["audience"])
        object.__setattr__(self, "required", parsed["required"])

    @classmethod
    def create(
        cls,
        *,
        factor_id: str,
        field: str,
        title: str,
        internal_description: str,
        external_description: str,
        audience: str = "both",
        required: bool = False,
    ) -> ExplainableFactor:
        parsed = _normalize_explainable_factor(
            factor_id=factor_id,
            field=field,
            title=title,
            internal_description=internal_description,
            external_description=external_description,
            audience=audience,
            required=required,
        )
        return cls(
            factor_id=cast("str", parsed["factor_id"]),
            field=cast("str", parsed["field"]),
            title=cast("str", parsed["title"]),
            internal_description=cast("str", parsed["internal_description"]),
            external_description=cast("str", parsed["external_description"]),
            audience=cast("str", parsed["audience"]),
            required=cast("bool", parsed["required"]),
        )


@dataclass(frozen=True, slots=True)
class ReasonCode:
    reason_code_id: str
    code: str
    outcome: str
    title: str
    internal_description: str
    external_description: str
    factor_refs: tuple[str, ...]
    status: str = "active"
    severity: str = "medium"
    audience: str = "both"

    def __post_init__(self) -> None:
        parsed = _normalize_reason_code(
            reason_code_id=self.reason_code_id,
            code=self.code,
            outcome=self.outcome,
            title=self.title,
            internal_description=self.internal_description,
            external_description=self.external_description,
            factor_refs=tuple(self.factor_refs),
            status=self.status,
            severity=self.severity,
            audience=self.audience,
        )
        object.__setattr__(self, "reason_code_id", parsed["reason_code_id"])
        object.__setattr__(self, "code", parsed["code"])
        object.__setattr__(self, "outcome", parsed["outcome"])
        object.__setattr__(self, "title", parsed["title"])
        object.__setattr__(self, "internal_description", parsed["internal_description"])
        object.__setattr__(self, "external_description", parsed["external_description"])
        object.__setattr__(self, "factor_refs", parsed["factor_refs"])
        object.__setattr__(self, "status", parsed["status"])
        object.__setattr__(self, "severity", parsed["severity"])
        object.__setattr__(self, "audience", parsed["audience"])

    @classmethod
    def create(
        cls,
        *,
        reason_code_id: str,
        code: str,
        outcome: str,
        title: str,
        internal_description: str,
        external_description: str,
        factor_refs: tuple[str, ...],
        status: str = "active",
        severity: str = "medium",
        audience: str = "both",
    ) -> ReasonCode:
        parsed = _normalize_reason_code(
            reason_code_id=reason_code_id,
            code=code,
            outcome=outcome,
            title=title,
            internal_description=internal_description,
            external_description=external_description,
            factor_refs=factor_refs,
            status=status,
            severity=severity,
            audience=audience,
        )
        return cls(
            reason_code_id=cast("str", parsed["reason_code_id"]),
            code=cast("str", parsed["code"]),
            outcome=cast("str", parsed["outcome"]),
            title=cast("str", parsed["title"]),
            internal_description=cast("str", parsed["internal_description"]),
            external_description=cast("str", parsed["external_description"]),
            factor_refs=cast("tuple[str, ...]", parsed["factor_refs"]),
            status=cast("str", parsed["status"]),
            severity=cast("str", parsed["severity"]),
            audience=cast("str", parsed["audience"]),
        )

    def validate_factor_refs(self, *, known_factor_ids: set[str]) -> None:
        missing = sorted(set(self.factor_refs) - known_factor_ids)
        if missing:
            raise PolicyValidationError(
                "fator explicável inexistente",
                code="unknown_explainable_factor",
                field_path="reason_codes.factor_refs",
                details={"missing_factor_refs": ",".join(missing)},
            )

    def is_semantically_compatible_with(self, other: ReasonCode) -> bool:
        return (
            self.code == other.code
            and self.outcome == other.outcome
            and self.title == other.title
            and self.external_description == other.external_description
            and self.factor_refs == other.factor_refs
            and self.status == other.status
            and self.audience == other.audience
        )


def parse_reason_code_catalog_status(value: str) -> str:
    return _parse_enum(
        ReasonCodeCatalogStatus,
        value,
        code="unsupported_reason_code_catalog_status",
        field_path="status",
    )


def parse_reason_code_catalog_change_type(value: str) -> str:
    return _parse_enum(
        ReasonCodeCatalogChangeType,
        value,
        code="unsupported_reason_code_catalog_change_type",
        field_path="changelog.change_type",
    )


def validate_reason_code_catalog_id(value: str) -> str:
    return _validate_technical_id(value, field_path="catalog_id")


def validate_reason_code_catalog_version_id(value: str) -> str:
    return _validate_technical_id(value, field_path="catalog_version_id")


def _normalize_explainable_factor(
    *,
    factor_id: str,
    field: str,
    title: str,
    internal_description: str,
    external_description: str,
    audience: str,
    required: bool,
) -> dict[str, object]:
    if type(required) is not bool:
        raise PolicyValidationError(
            "obrigatoriedade inválida",
            code="invalid_explainable_factor_required",
            field_path="explainable_factors.required",
        )
    return {
        "factor_id": _validate_technical_id(
            factor_id,
            field_path="explainable_factors.factor_id",
        ),
        "field": _validate_policy_field(field, field_path="explainable_factors.field"),
        "title": _validate_safe_text(title, field_path="explainable_factors.title"),
        "internal_description": _validate_safe_text(
            internal_description,
            field_path="explainable_factors.internal_description",
        ),
        "external_description": _validate_safe_text(
            external_description,
            field_path="explainable_factors.external_description",
        ),
        "audience": _parse_enum(
            ReasonCodeAudience,
            audience,
            code="unsupported_reason_code_audience",
            field_path="explainable_factors.audience",
        ),
        "required": required,
    }


def _normalize_reason_code(
    *,
    reason_code_id: str,
    code: str,
    outcome: str,
    title: str,
    internal_description: str,
    external_description: str,
    factor_refs: tuple[str, ...],
    status: str,
    severity: str,
    audience: str,
) -> dict[str, object]:
    parsed_factor_refs = tuple(
        _validate_technical_id(reference, field_path="reason_codes.factor_refs")
        for reference in factor_refs
    )
    if not parsed_factor_refs:
        raise PolicyValidationError(
            "fator explicável obrigatório",
            code="missing_explainable_factor_ref",
            field_path="reason_codes.factor_refs",
        )
    if len(set(parsed_factor_refs)) != len(parsed_factor_refs):
        raise PolicyValidationError(
            "fator explicável duplicado",
            code="duplicate_explainable_factor_ref",
            field_path="reason_codes.factor_refs",
        )
    return {
        "reason_code_id": _validate_technical_id(
            reason_code_id,
            field_path="reason_codes.reason_code_id",
        ),
        "code": _validate_technical_id(code, field_path="reason_codes.code"),
        "outcome": _parse_enum(
            PolicyOutcome,
            outcome,
            code="unsupported_reason_code_outcome",
            field_path="reason_codes.outcome",
        ),
        "title": _validate_safe_text(title, field_path="reason_codes.title"),
        "internal_description": _validate_safe_text(
            internal_description,
            field_path="reason_codes.internal_description",
        ),
        "external_description": _validate_safe_text(
            external_description,
            field_path="reason_codes.external_description",
        ),
        "factor_refs": parsed_factor_refs,
        "status": _parse_enum(
            ReasonCodeStatus,
            status,
            code="unsupported_reason_code_status",
            field_path="reason_codes.status",
        ),
        "severity": _parse_enum(
            ReasonCodeSeverity,
            severity,
            code="unsupported_reason_code_severity",
            field_path="reason_codes.severity",
        ),
        "audience": _parse_enum(
            ReasonCodeAudience,
            audience,
            code="unsupported_reason_code_audience",
            field_path="reason_codes.audience",
        ),
    }
