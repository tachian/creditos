from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, cast

from creditos_decision.domain.errors import PolicyValidationError


class ProductType(StrEnum):
    PERSONAL_CREDIT = "personal_credit"
    BNPL = "bnpl"
    BUSINESS_CREDIT = "business_credit"
    RECEIVABLES = "receivables"


class PolicyStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class PolicyChangeType(StrEnum):
    CREATED = "created"
    UPDATED = "updated"
    PUBLISHED = "published"
    VERSIONED = "versioned"


class PolicyOperator(StrEnum):
    GTE = "gte"
    LTE = "lte"
    EQ = "eq"
    EXISTS = "exists"


class PolicyOutcome(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"
    APPROVE_WITH_CHANGES = "approve_with_changes"
    REQUEST_MORE_DATA = "request_more_data"
    UNABLE_TO_DECIDE = "unable_to_decide"


class PolicyFallbackActionType(StrEnum):
    REQUEST_MORE_DATA = "request_more_data"
    UNABLE_TO_DECIDE = "unable_to_decide"
    REJECT_BY_POLICY = "reject_by_policy"


_TECHNICAL_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_.-]{2,160}$")
_CORRELATION_ID_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]{8,160}$")
_SAFE_TEXT_PATTERN = re.compile(r"^[A-Za-zÀ-ÿ0-9 .,;:_/()+\\-]{1,240}$")
_EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}")
_FORMATTED_CPF_PATTERN = re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")
_FORMATTED_CNPJ_PATTERN = re.compile(r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b")
_LIKELY_PERSON_NAME_PATTERN = re.compile(
    r"\b[A-ZÁÉÍÓÚÂÊÔÃÕÇ][a-záéíóúâêôãõç]{2,}"
    r"\s+(?:d[aeo]s?|e)\s+"
    r"[A-ZÁÉÍÓÚÂÊÔÃÕÇ][a-záéíóúâêôãõç]{2,}\b"
)
_PROHIBITED_TOKENS = {
    "address",
    "alameda",
    "apartamento",
    "apto",
    "av",
    "avenida",
    "bairro",
    "bloco",
    "cep",
    "authorization",
    "cnpj",
    "cpf",
    "custom",
    "document",
    "documento",
    "endereco",
    "email",
    "headers",
    "metadata",
    "name",
    "nome",
    "payload",
    "provider_payload",
    "provider_response",
    "raw_payload",
    "request_body",
    "response_body",
    "rodovia",
    "rua",
    "secret",
    "segredo",
    "street",
    "token",
    "travessa",
}
_PROHIBITED_COMPACT_TOKENS = {re.sub(r"[^a-z0-9]", "", token) for token in _PROHIBITED_TOKENS}
_GOVERNED_POLICY_FIELDS = {
    "age_years",
    "available_receivables_units",
    "declared_revenue_units",
    "down_payment_units",
    "installment_amount_units",
    "monthly_income_units",
    "requested_amount_units",
    "requested_installments",
    "requested_term_days",
}
_NUMERIC_POLICY_FIELDS = frozenset(_GOVERNED_POLICY_FIELDS)
_ALLOWED_CHANNELS = {"api", "batch", "portal", "partner", "checkout", "backoffice"}
_ALLOWED_LIMIT_TYPES = {
    "max_amount_units",
    "min_amount_units",
    "max_installments",
    "max_term_days",
    "min_term_days",
}


@dataclass(frozen=True, slots=True)
class PolicyApplicability:
    channels: tuple[str, ...] = ()
    starts_at: datetime | None = None
    ends_at: datetime | None = None

    def __post_init__(self) -> None:
        channels, starts_at, ends_at = _normalize_applicability(
            channels=tuple(self.channels),
            starts_at=self.starts_at,
            ends_at=self.ends_at,
        )
        object.__setattr__(self, "channels", channels)
        object.__setattr__(self, "starts_at", starts_at)
        object.__setattr__(self, "ends_at", ends_at)

    @classmethod
    def create(
        cls,
        *,
        channels: tuple[str, ...] = (),
        starts_at: datetime | None = None,
        ends_at: datetime | None = None,
    ) -> PolicyApplicability:
        parsed_channels, starts_at, ends_at = _normalize_applicability(
            channels=channels,
            starts_at=starts_at,
            ends_at=ends_at,
        )
        return cls(
            channels=parsed_channels,
            starts_at=starts_at,
            ends_at=ends_at,
        )


@dataclass(frozen=True, slots=True)
class PolicyRule:
    rule_id: str
    name: str
    source_field: str
    operator: str
    threshold_value: int | str | bool
    outcome: str
    reason_code_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        parsed = _normalize_rule(
            rule_id=self.rule_id,
            name=self.name,
            source_field=self.source_field,
            operator=self.operator,
            threshold_value=self.threshold_value,
            outcome=self.outcome,
            reason_code_refs=tuple(self.reason_code_refs),
        )
        object.__setattr__(self, "rule_id", parsed["rule_id"])
        object.__setattr__(self, "name", parsed["name"])
        object.__setattr__(self, "source_field", parsed["source_field"])
        object.__setattr__(self, "operator", parsed["operator"])
        object.__setattr__(self, "threshold_value", parsed["threshold_value"])
        object.__setattr__(self, "outcome", parsed["outcome"])
        object.__setattr__(self, "reason_code_refs", parsed["reason_code_refs"])

    @classmethod
    def create(
        cls,
        *,
        rule_id: str,
        name: str,
        source_field: str,
        operator: str,
        threshold_value: int | str | bool,
        outcome: str,
        reason_code_refs: tuple[str, ...] = (),
    ) -> PolicyRule:
        parsed = _normalize_rule(
            rule_id=rule_id,
            name=name,
            source_field=source_field,
            operator=operator,
            threshold_value=threshold_value,
            outcome=outcome,
            reason_code_refs=reason_code_refs,
        )
        return cls(
            rule_id=cast("str", parsed["rule_id"]),
            name=cast("str", parsed["name"]),
            source_field=cast("str", parsed["source_field"]),
            operator=cast("str", parsed["operator"]),
            threshold_value=cast("int | str | bool", parsed["threshold_value"]),
            outcome=cast("str", parsed["outcome"]),
            reason_code_refs=cast("tuple[str, ...]", parsed["reason_code_refs"]),
        )


@dataclass(frozen=True, slots=True)
class PolicyFallbackAction:
    action: str = PolicyFallbackActionType.REQUEST_MORE_DATA.value
    reason_code_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        parsed_action, parsed_reason_code_refs = _normalize_fallback_action(
            action=self.action,
            reason_code_refs=tuple(self.reason_code_refs),
        )
        object.__setattr__(self, "action", parsed_action)
        object.__setattr__(self, "reason_code_refs", parsed_reason_code_refs)

    @classmethod
    def create(
        cls,
        *,
        action: str = PolicyFallbackActionType.REQUEST_MORE_DATA.value,
        reason_code_refs: tuple[str, ...] = (),
    ) -> PolicyFallbackAction:
        parsed_action, parsed_reason_code_refs = _normalize_fallback_action(
            action=action,
            reason_code_refs=reason_code_refs,
        )
        return cls(action=parsed_action, reason_code_refs=parsed_reason_code_refs)


@dataclass(frozen=True, slots=True)
class PolicyCriterion:
    criterion_id: str
    field: str
    operator: str
    value: int | str | bool

    def __post_init__(self) -> None:
        parsed = _normalize_criterion(
            criterion_id=self.criterion_id,
            field=self.field,
            operator=self.operator,
            value=self.value,
        )
        object.__setattr__(self, "criterion_id", parsed["criterion_id"])
        object.__setattr__(self, "field", parsed["field"])
        object.__setattr__(self, "operator", parsed["operator"])
        object.__setattr__(self, "value", parsed["value"])

    @classmethod
    def create(
        cls,
        *,
        criterion_id: str,
        field: str,
        operator: str,
        value: int | str | bool,
    ) -> PolicyCriterion:
        parsed = _normalize_criterion(
            criterion_id=criterion_id,
            field=field,
            operator=operator,
            value=value,
        )
        return cls(
            criterion_id=cast("str", parsed["criterion_id"]),
            field=cast("str", parsed["field"]),
            operator=cast("str", parsed["operator"]),
            value=cast("int | str | bool", parsed["value"]),
        )


@dataclass(frozen=True, slots=True)
class PolicyLimit:
    limit_id: str
    limit_type: str
    value: int

    def __post_init__(self) -> None:
        parsed = _normalize_limit(
            limit_id=self.limit_id,
            limit_type=self.limit_type,
            value=self.value,
        )
        object.__setattr__(self, "limit_id", parsed["limit_id"])
        object.__setattr__(self, "limit_type", parsed["limit_type"])
        object.__setattr__(self, "value", parsed["value"])

    @classmethod
    def create(cls, *, limit_id: str, limit_type: str, value: int) -> PolicyLimit:
        parsed = _normalize_limit(limit_id=limit_id, limit_type=limit_type, value=value)
        return cls(
            limit_id=cast("str", parsed["limit_id"]),
            limit_type=cast("str", parsed["limit_type"]),
            value=cast("int", parsed["value"]),
        )


@dataclass(frozen=True, slots=True)
class PolicyChangelogEntry:
    change_type: str
    actor_subject_id: str
    changed_at: datetime
    change_summary: str
    correlation_id: str
    previous_revision: int | None
    resulting_revision: int

    def __post_init__(self) -> None:
        parsed = _normalize_changelog_entry(
            change_type=self.change_type,
            actor_subject_id=self.actor_subject_id,
            changed_at=self.changed_at,
            change_summary=self.change_summary,
            correlation_id=self.correlation_id,
            previous_revision=self.previous_revision,
            resulting_revision=self.resulting_revision,
        )
        object.__setattr__(self, "change_type", parsed["change_type"])
        object.__setattr__(self, "actor_subject_id", parsed["actor_subject_id"])
        object.__setattr__(self, "changed_at", parsed["changed_at"])
        object.__setattr__(self, "change_summary", parsed["change_summary"])
        object.__setattr__(self, "correlation_id", parsed["correlation_id"])
        object.__setattr__(self, "previous_revision", parsed["previous_revision"])
        object.__setattr__(self, "resulting_revision", parsed["resulting_revision"])

    @classmethod
    def create(
        cls,
        *,
        change_type: str,
        actor_subject_id: str,
        changed_at: datetime,
        change_summary: str,
        correlation_id: str,
        previous_revision: int | None,
        resulting_revision: int,
    ) -> PolicyChangelogEntry:
        parsed = _normalize_changelog_entry(
            change_type=change_type,
            actor_subject_id=actor_subject_id,
            changed_at=changed_at,
            change_summary=change_summary,
            correlation_id=correlation_id,
            previous_revision=previous_revision,
            resulting_revision=resulting_revision,
        )
        return cls(
            change_type=cast("str", parsed["change_type"]),
            actor_subject_id=cast("str", parsed["actor_subject_id"]),
            changed_at=cast("datetime", parsed["changed_at"]),
            change_summary=cast("str", parsed["change_summary"]),
            correlation_id=cast("str", parsed["correlation_id"]),
            previous_revision=cast("int | None", parsed["previous_revision"]),
            resulting_revision=cast("int", parsed["resulting_revision"]),
        )


def _normalize_applicability(
    *,
    channels: tuple[str, ...],
    starts_at: datetime | None,
    ends_at: datetime | None,
) -> tuple[tuple[str, ...], datetime | None, datetime | None]:
    parsed_channels = tuple(_validate_channel(channel) for channel in channels)
    if len(set(parsed_channels)) != len(parsed_channels):
        raise PolicyValidationError(
            "canal duplicado",
            code="duplicate_channel",
            field_path="applicability.channels",
        )
    if starts_at is not None:
        _validate_aware_utc_datetime(starts_at, field_path="applicability.starts_at")
    if ends_at is not None:
        _validate_aware_utc_datetime(ends_at, field_path="applicability.ends_at")
    if starts_at is not None and ends_at is not None and starts_at >= ends_at:
        raise PolicyValidationError(
            "janela de vigência inválida",
            code="invalid_applicability_window",
            field_path="applicability",
        )
    return parsed_channels, starts_at, ends_at


def _normalize_rule(
    *,
    rule_id: str,
    name: str,
    source_field: str,
    operator: str,
    threshold_value: int | str | bool,
    outcome: str,
    reason_code_refs: tuple[str, ...],
) -> dict[str, object]:
    parsed_source_field = _validate_policy_field(source_field, field_path="rules.source_field")
    parsed_reason_code_refs = tuple(
        _validate_technical_id(reference, field_path="rules.reason_code_refs")
        for reference in reason_code_refs
    )
    if not parsed_reason_code_refs:
        raise PolicyValidationError(
            "reason code obrigatório",
            code="missing_reason_code_ref",
            field_path="rules.reason_code_refs",
        )
    if len(set(parsed_reason_code_refs)) != len(parsed_reason_code_refs):
        raise PolicyValidationError(
            "reason code duplicado",
            code="duplicate_reason_code_ref",
            field_path="rules.reason_code_refs",
        )
    return {
        "rule_id": _validate_technical_id(rule_id, field_path="rules.rule_id"),
        "name": _validate_safe_text(name, field_path="rules.name"),
        "source_field": parsed_source_field,
        "operator": _parse_enum(
            PolicyOperator,
            operator,
            code="unsupported_policy_operator",
            field_path="rules.operator",
        ),
        "threshold_value": _validate_operator_value(
            operator,
            threshold_value,
            field_path="rules.threshold_value",
            policy_field=parsed_source_field,
        ),
        "outcome": _parse_enum(
            PolicyOutcome,
            outcome,
            code="unsupported_policy_outcome",
            field_path="rules.outcome",
        ),
        "reason_code_refs": parsed_reason_code_refs,
    }


def _normalize_fallback_action(
    *,
    action: str,
    reason_code_refs: tuple[str, ...],
) -> tuple[str, tuple[str, ...]]:
    parsed_action = parse_policy_fallback_action(action)
    parsed_reason_code_refs = tuple(
        _validate_technical_id(reference, field_path="fallback_action.reason_code_refs")
        for reference in reason_code_refs
    )
    if len(set(parsed_reason_code_refs)) != len(parsed_reason_code_refs):
        raise PolicyValidationError(
            "reason code duplicado",
            code="duplicate_fallback_reason_code_ref",
            field_path="fallback_action.reason_code_refs",
        )
    if (
        parsed_action == PolicyFallbackActionType.REJECT_BY_POLICY.value
        and not parsed_reason_code_refs
    ):
        raise PolicyValidationError(
            "reason code obrigatório para reprovação por política",
            code="missing_fallback_reason_code_ref",
            field_path="fallback_action.reason_code_refs",
        )
    if parsed_action != PolicyFallbackActionType.REJECT_BY_POLICY.value and parsed_reason_code_refs:
        raise PolicyValidationError(
            "reason code permitido apenas para reprovação por política",
            code="unsupported_fallback_reason_code_ref",
            field_path="fallback_action.reason_code_refs",
        )
    return parsed_action, parsed_reason_code_refs


def _normalize_criterion(
    *,
    criterion_id: str,
    field: str,
    operator: str,
    value: int | str | bool,
) -> dict[str, object]:
    parsed_field = _validate_policy_field(field, field_path="criteria.field")
    return {
        "criterion_id": _validate_technical_id(
            criterion_id,
            field_path="criteria.criterion_id",
        ),
        "field": parsed_field,
        "operator": _parse_enum(
            PolicyOperator,
            operator,
            code="unsupported_policy_operator",
            field_path="criteria.operator",
        ),
        "value": _validate_operator_value(
            operator,
            value,
            field_path="criteria.value",
            policy_field=parsed_field,
        ),
    }


def _normalize_limit(*, limit_id: str, limit_type: str, value: int) -> dict[str, object]:
    parsed_limit_type = _validate_governed_field(limit_type, field_path="limits.limit_type")
    if parsed_limit_type not in _ALLOWED_LIMIT_TYPES:
        raise PolicyValidationError(
            "tipo de limite não suportado",
            code="unsupported_limit_type",
            field_path="limits.limit_type",
        )
    if type(value) is not int or value < 0 or value > 10_000_000_000:
        raise PolicyValidationError(
            "valor de limite inválido",
            code="invalid_limit_value",
            field_path="limits.value",
        )
    return {
        "limit_id": _validate_technical_id(limit_id, field_path="limits.limit_id"),
        "limit_type": parsed_limit_type,
        "value": value,
    }


def _normalize_changelog_entry(
    *,
    change_type: str,
    actor_subject_id: str,
    changed_at: datetime,
    change_summary: str,
    correlation_id: str,
    previous_revision: int | None,
    resulting_revision: int,
) -> dict[str, object]:
    if previous_revision is not None and previous_revision < 1:
        raise PolicyValidationError(
            "revisão anterior inválida",
            code="invalid_previous_revision",
            field_path="changelog.previous_revision",
        )
    if resulting_revision < 1:
        raise PolicyValidationError(
            "revisão resultante inválida",
            code="invalid_resulting_revision",
            field_path="changelog.resulting_revision",
        )
    _validate_aware_utc_datetime(changed_at, field_path="changelog.changed_at")
    return {
        "change_type": _parse_enum(
            PolicyChangeType,
            change_type,
            code="unsupported_change_type",
            field_path="changelog.change_type",
        ),
        "actor_subject_id": _validate_technical_id(
            actor_subject_id,
            field_path="changelog.actor_subject_id",
        ),
        "changed_at": changed_at,
        "change_summary": _validate_safe_text(
            change_summary,
            field_path="changelog.change_summary",
        ),
        "correlation_id": validate_correlation_id(correlation_id),
        "previous_revision": previous_revision,
        "resulting_revision": resulting_revision,
    }


def parse_product_type(value: str) -> str:
    return _parse_enum(
        ProductType,
        value,
        code="unsupported_product_type",
        field_path="product_type",
        message="produto não suportado",
    )


def parse_policy_status(value: str) -> str:
    return _parse_enum(
        PolicyStatus,
        value,
        code="unsupported_policy_status",
        field_path="status",
    )


def parse_policy_fallback_action(value: str) -> str:
    return _parse_enum(
        PolicyFallbackActionType,
        value,
        code="unsupported_policy_fallback_action",
        field_path="fallback_action",
        message=(
            "fallback de política não suportado; use request_more_data, "
            "unable_to_decide, reject_by_policy ou IA apenas consultiva sem decisão final"
        ),
    )


def validate_policy_id(value: str) -> str:
    return _validate_technical_id(value, field_path="policy_id")


def validate_policy_version_id(value: str) -> str:
    return _validate_technical_id(value, field_path="policy_version_id")


def validate_tenant_id(value: str) -> str:
    return _validate_technical_id(value, field_path="tenant_id")


def validate_subject_id(value: str, *, field_path: str = "subject_id") -> str:
    return _validate_technical_id(value, field_path=field_path)


def validate_correlation_id(value: str) -> str:
    if not _CORRELATION_ID_PATTERN.fullmatch(value):
        raise PolicyValidationError(
            "correlation ID inválido",
            code="invalid_correlation_id",
            field_path="correlation_id",
        )
    _reject_sensitive_or_prohibited(value, field_path="correlation_id")
    return value


def _validate_channel(value: str) -> str:
    parsed = _validate_governed_field(value, field_path="applicability.channels")
    if parsed not in _ALLOWED_CHANNELS:
        raise PolicyValidationError(
            "canal não suportado",
            code="unsupported_channel",
            field_path="applicability.channels",
        )
    return parsed


def _validate_governed_field(value: str, *, field_path: str) -> str:
    parsed = _validate_technical_id(value, field_path=field_path)
    _reject_sensitive_or_prohibited(parsed, field_path=field_path)
    return parsed


def _validate_policy_field(value: str, *, field_path: str) -> str:
    parsed = _validate_governed_field(value, field_path=field_path)
    if parsed not in _GOVERNED_POLICY_FIELDS:
        raise PolicyValidationError(
            "campo de política não governado",
            code="unsupported_policy_field",
            field_path=field_path,
        )
    return parsed


def _validate_operator_value(
    operator: str,
    value: int | str | bool,
    *,
    field_path: str,
    policy_field: str,
) -> int | str | bool:
    parsed_operator = _parse_enum(
        PolicyOperator,
        operator,
        code="unsupported_policy_operator",
        field_path=field_path.rsplit(".", 1)[0] + ".operator",
    )
    parsed_value = _validate_rule_value(value, field_path=field_path)
    if (
        parsed_operator
        in {PolicyOperator.GTE.value, PolicyOperator.LTE.value, PolicyOperator.EQ.value}
        and policy_field in _NUMERIC_POLICY_FIELDS
        and type(parsed_value) is not int
    ):
        raise PolicyValidationError(
            "valor incompatível com operador",
            code="operator_value_type_mismatch",
            field_path=field_path,
        )
    if parsed_operator == PolicyOperator.EXISTS.value and type(parsed_value) is not bool:
        raise PolicyValidationError(
            "valor incompatível com operador",
            code="operator_value_type_mismatch",
            field_path=field_path,
        )
    return parsed_value


def _validate_rule_value(value: int | str | bool, *, field_path: str) -> int | str | bool:
    if type(value) is int:
        if value < 0 or value > 10_000_000_000:
            raise PolicyValidationError(
                "valor fora do intervalo permitido",
                code="invalid_policy_value",
                field_path=field_path,
            )
        return value
    if type(value) is bool:
        return value
    if type(value) is str:
        return _validate_safe_text(value, field_path=field_path)
    raise PolicyValidationError(
        "tipo de valor não suportado",
        code="unsupported_policy_value_type",
        field_path=field_path,
    )


def _validate_technical_id(value: str, *, field_path: str) -> str:
    if not isinstance(value, str) or not _TECHNICAL_ID_PATTERN.fullmatch(value):
        raise PolicyValidationError(
            "identificador técnico inválido",
            code="invalid_technical_id",
            field_path=field_path,
        )
    _reject_sensitive_or_prohibited(value, field_path=field_path)
    return value


def _validate_safe_text(value: str, *, field_path: str) -> str:
    if not isinstance(value, str) or not _SAFE_TEXT_PATTERN.fullmatch(value.strip()):
        raise PolicyValidationError(
            "texto inválido",
            code="invalid_safe_text",
            field_path=field_path,
        )
    parsed = value.strip()
    _reject_sensitive_or_prohibited(parsed, field_path=field_path)
    return parsed


def _reject_sensitive_or_prohibited(value: Any, *, field_path: str) -> None:
    normalized = _normalize_for_sensitive_matching(value)
    compact = re.sub(r"[^a-z0-9]", "", normalized)
    digits = re.sub(r"\D", "", normalized)
    normalized_tokens = set(re.split(r"[^a-z0-9]+", normalized))
    if (
        normalized in _PROHIBITED_TOKENS
        or compact in _PROHIBITED_COMPACT_TOKENS
        or normalized_tokens.intersection(_PROHIBITED_TOKENS)
        or len(digits) in (11, 14)
        or _FORMATTED_CPF_PATTERN.search(str(value))
        or _FORMATTED_CNPJ_PATTERN.search(str(value))
        or _EMAIL_PATTERN.search(str(value))
        or _LIKELY_PERSON_NAME_PATTERN.search(str(value))
    ):
        raise PolicyValidationError(
            "dado sensível ou campo proibido",
            code="sensitive_or_prohibited_policy_field",
            field_path=field_path,
        )


def _normalize_for_sensitive_matching(value: Any) -> str:
    decomposed = unicodedata.normalize("NFKD", str(value).lower())
    return "".join(character for character in decomposed if not unicodedata.combining(character))


def _validate_aware_utc_datetime(value: datetime, *, field_path: str) -> datetime:
    if not isinstance(value, datetime):
        raise PolicyValidationError(
            "datetime inválido",
            code="invalid_datetime",
            field_path=field_path,
        )
    if value.tzinfo is None or value.utcoffset() is None:
        raise PolicyValidationError(
            "datetime deve conter timezone",
            code="naive_datetime",
            field_path=field_path,
        )
    if value.utcoffset() != UTC.utcoffset(value):
        raise PolicyValidationError(
            "datetime deve estar em UTC",
            code="non_utc_datetime",
            field_path=field_path,
        )
    return value


def _parse_enum(
    enum_type: type[StrEnum],
    value: str,
    *,
    code: str,
    field_path: str,
    message: str = "valor não suportado",
) -> str:
    try:
        return enum_type(value).value
    except ValueError as error:
        raise PolicyValidationError(message, code=code, field_path=field_path) from error
