from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta

from creditos_security.masking import mask_sensitive_data

from creditos_audit_evidence.domain.errors import AuditEvidenceValidationError

_TECHNICAL_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9:._/-]{0,127}$")
_TECHNICAL_TYPE_PATTERN = re.compile(r"^[a-z][a-z0-9_]{1,63}$")
_EVENT_TYPE_PATTERN = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$")
_TRACE_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")
_SAFE_DETAIL_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_BRAZILIAN_DOCUMENT_PATTERN = re.compile(
    r"^(?:\d{11}|\d{14}|\d{3}\.\d{3}\.\d{3}-\d{2}|\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})$"
)
_SOURCE_KINDS = frozenset({"api", "worker", "job", "grpc", "event_consumer", "system"})
_RESULTS = frozenset({"accepted", "rejected", "blocked", "failed", "technical_failure"})
_ALLOWED_SAFE_DETAIL_KEYS = frozenset(
    {
        "decision_id",
        "event_count",
        "execution_id",
        "idempotency_key",
        "outcome",
        "policy_id",
        "policy_version",
        "proposal_id",
        "reason_code",
        "schema_version",
        "source_event_id",
    }
)
_MAX_SAFE_DETAILS = 32
_MAX_SAFE_DETAIL_VALUE_LENGTH = 256


def validate_event_id(value: str) -> str:
    return _validate_technical_id(value, field_path="event_id")


def validate_tenant_id(value: str) -> str:
    return _validate_technical_id(value, field_path="tenant_id")


def validate_aggregate_type(value: str) -> str:
    return _validate_type_token(value, field_path="aggregate_type")


def validate_aggregate_id(value: str) -> str:
    return _validate_technical_id(value, field_path="aggregate_id")


def validate_event_type(value: str) -> str:
    if not isinstance(value, str):
        raise _validation_error("event_type é obrigatório", "invalid_event_type", "event_type")
    normalized_value = value.strip()
    if _EVENT_TYPE_PATTERN.fullmatch(normalized_value) is None:
        raise _validation_error("event_type inválido", "invalid_event_type", "event_type")
    return normalized_value


def validate_action(value: str) -> str:
    return _validate_type_token(value, field_path="action")


def validate_resource_type(value: str) -> str:
    return _validate_type_token(value, field_path="resource_type")


def validate_resource_id(value: str, *, field_path: str = "resource_id") -> str:
    return _validate_technical_id(value, field_path=field_path)


def validate_subject_id(value: str) -> str:
    return _validate_technical_id(value, field_path="actor_subject_id")


def validate_source_service(value: str, *, field_path: str = "source_service") -> str:
    return _validate_type_token(value, field_path=field_path, allow_dash=True)


def validate_source_kind(value: str) -> str:
    if value not in _SOURCE_KINDS:
        raise _validation_error("origem inválida", "invalid_source_kind", "source_kind")
    return value


def validate_result(value: str) -> str:
    if value not in _RESULTS:
        raise _validation_error("resultado inválido", "invalid_result", "result")
    return value


def validate_occurred_at(value: datetime) -> datetime:
    if not isinstance(value, datetime):
        raise _validation_error("occurred_at é obrigatório", "invalid_occurred_at", "occurred_at")
    if value.tzinfo is None or value.utcoffset() is None:
        raise _validation_error(
            "occurred_at deve ser timezone-aware em UTC",
            "invalid_occurred_at",
            "occurred_at",
        )
    if value.utcoffset() != timedelta(0):
        raise _validation_error(
            "occurred_at deve usar timezone UTC sem normalização silenciosa",
            "non_utc_occurred_at",
            "occurred_at",
        )
    return value.astimezone(UTC)


def validate_correlation_id(value: str) -> str:
    return _validate_technical_id(value, field_path="correlation_id")


def validate_trace_id(value: str) -> str:
    if not isinstance(value, str):
        raise _validation_error("trace_id é obrigatório", "invalid_trace_id", "trace_id")
    normalized_value = value.strip()
    if _TRACE_ID_PATTERN.fullmatch(normalized_value) is None or normalized_value == "0" * 32:
        raise _validation_error("trace_id inválido", "invalid_trace_id", "trace_id")
    return normalized_value


def validate_request_id(value: str | None) -> str | None:
    if value is None:
        return None
    return _validate_technical_id(value, field_path="request_id")


def normalize_safe_details(value: Mapping[str, str]) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise _validation_error("safe_details inválido", "invalid_safe_details", "safe_details")
    if len(value) > _MAX_SAFE_DETAILS:
        raise _validation_error(
            "safe_details excede limite",
            "too_many_safe_details",
            "safe_details",
        )

    normalized_details: dict[str, str] = {}
    for raw_key, raw_value in value.items():
        key = _normalize_safe_detail_key(raw_key)
        if key not in _ALLOWED_SAFE_DETAIL_KEYS:
            raise _validation_error(
                "chave de safe_details não permitida",
                "unsupported_safe_detail_key",
                f"safe_details.{key}",
            )
        if key in normalized_details:
            raise _validation_error(
                "chave de safe_details duplicada após normalização",
                "duplicate_safe_detail_key",
                f"safe_details.{key}",
            )
        if not isinstance(raw_value, str):
            raise _validation_error(
                "safe_details aceita apenas strings",
                "invalid_safe_detail_value",
                f"safe_details.{key}",
            )
        masked_value = str(mask_sensitive_data(raw_value, key=key))
        normalized_details[key] = masked_value[:_MAX_SAFE_DETAIL_VALUE_LENGTH]
    return normalized_details


def _normalize_safe_detail_key(value: str) -> str:
    if not isinstance(value, str):
        raise _validation_error(
            "chave de safe_details inválida",
            "invalid_safe_detail_key",
            "safe_details",
        )
    normalized_key = value.strip().lower().replace("-", "_").replace(".", "_")
    if _SAFE_DETAIL_KEY_PATTERN.fullmatch(normalized_key) is None:
        raise _validation_error(
            "chave de safe_details inválida",
            "invalid_safe_detail_key",
            f"safe_details.{normalized_key}",
        )
    return normalized_key


def _validate_technical_id(value: str, *, field_path: str) -> str:
    if not isinstance(value, str):
        raise _validation_error(f"{field_path} é obrigatório", f"invalid_{field_path}", field_path)
    normalized_value = value.strip()
    if _TECHNICAL_ID_PATTERN.fullmatch(normalized_value) is None:
        raise _validation_error(f"{field_path} inválido", f"invalid_{field_path}", field_path)
    if _contains_brazilian_document(normalized_value) or "@" in normalized_value:
        raise _validation_error(
            f"{field_path} não pode conter dado sensível",
            f"sensitive_{field_path}",
            field_path,
        )
    return normalized_value


def _validate_type_token(
    value: str,
    *,
    field_path: str,
    allow_dash: bool = False,
) -> str:
    if not isinstance(value, str):
        raise _validation_error(f"{field_path} é obrigatório", f"invalid_{field_path}", field_path)
    normalized_value = value.strip()
    if allow_dash:
        normalized_value = normalized_value.replace("-", "_")
    if _TECHNICAL_TYPE_PATTERN.fullmatch(normalized_value) is None:
        raise _validation_error(f"{field_path} inválido", f"invalid_{field_path}", field_path)
    return normalized_value


def _contains_brazilian_document(value: str) -> bool:
    if _BRAZILIAN_DOCUMENT_PATTERN.fullmatch(value) is not None:
        return True
    digits = re.sub(r"\D", "", value)
    return len(digits) in (11, 14)


def _validation_error(message: str, code: str, field_path: str) -> AuditEvidenceValidationError:
    return AuditEvidenceValidationError(message, code=code, field_path=field_path)
