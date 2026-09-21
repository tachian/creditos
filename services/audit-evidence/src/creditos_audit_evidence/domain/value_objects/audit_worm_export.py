from __future__ import annotations

import re
from datetime import UTC, datetime
from enum import StrEnum

from creditos_audit_evidence.domain.errors import AuditEvidenceValidationError
from creditos_audit_evidence.domain.value_objects.audit_event import validate_occurred_at
from creditos_audit_evidence.domain.value_objects.audit_integrity import validate_current_hash

WORM_MANIFEST_VERSION = "audit-worm-manifest.v1"
WORM_RETENTION_CLASS_REGULATORY = "regulatory"
WORM_RETENTION_CLASS_OPERATIONAL = "operational"

_OBJECT_KEY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._=/-]{0,511}$")
_OBJECT_VERSION_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/+=-]{0,255}$")
_LEGAL_HOLD_REASON_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9:._/-]{0,127}$")
_RETENTION_CLASSES = frozenset({WORM_RETENTION_CLASS_REGULATORY, WORM_RETENTION_CLASS_OPERATIONAL})


class WormRetentionMode(StrEnum):
    GOVERNANCE = "GOVERNANCE"
    COMPLIANCE = "COMPLIANCE"


class AuditWormExportStatus(StrEnum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    RECONCILED = "reconciled"
    INVALID = "invalid"


def validate_manifest_version(value: str) -> str:
    if value != WORM_MANIFEST_VERSION:
        raise AuditEvidenceValidationError(
            "versão de manifesto WORM inválida",
            code="invalid_worm_manifest_version",
            field_path="manifest_version",
        )
    return value


def validate_retention_class(value: str) -> str:
    if not isinstance(value, str):
        raise AuditEvidenceValidationError(
            "classe de retenção WORM é obrigatória",
            code="invalid_worm_retention_class",
            field_path="retention_class",
        )
    normalized_value = value.strip().lower()
    if normalized_value not in _RETENTION_CLASSES:
        raise AuditEvidenceValidationError(
            "classe de retenção WORM inválida",
            code="invalid_worm_retention_class",
            field_path="retention_class",
        )
    return normalized_value


def validate_retention_mode(value: WormRetentionMode | str) -> WormRetentionMode:
    try:
        return value if isinstance(value, WormRetentionMode) else WormRetentionMode(str(value))
    except ValueError as exc:
        raise AuditEvidenceValidationError(
            "modo WORM inválido",
            code="invalid_worm_retention_mode",
            field_path="retention_mode",
        ) from exc


def validate_retain_until(value: datetime, *, now: datetime | None = None) -> datetime:
    valid_value = validate_occurred_at(value)
    reference = validate_occurred_at(now) if now is not None else datetime.now(UTC)
    if valid_value <= reference:
        raise AuditEvidenceValidationError(
            "retenção WORM deve estar no futuro",
            code="expired_worm_retention",
            field_path="retain_until",
        )
    return valid_value


def validate_worm_object_key(value: str) -> str:
    if not isinstance(value, str):
        raise AuditEvidenceValidationError(
            "object key WORM é obrigatório",
            code="invalid_worm_object_key",
            field_path="object_key",
        )
    normalized_value = value.strip()
    if (
        _OBJECT_KEY_PATTERN.fullmatch(normalized_value) is None
        or ".." in normalized_value
        or "@" in normalized_value
    ):
        raise AuditEvidenceValidationError(
            "object key WORM inválido",
            code="invalid_worm_object_key",
            field_path="object_key",
        )
    return normalized_value


def validate_worm_object_version(value: str) -> str:
    if not isinstance(value, str):
        raise AuditEvidenceValidationError(
            "versão de objeto WORM é obrigatória",
            code="invalid_worm_object_version",
            field_path="object_version_id",
        )
    normalized_value = value.strip()
    if _OBJECT_VERSION_PATTERN.fullmatch(normalized_value) is None:
        raise AuditEvidenceValidationError(
            "versão de objeto WORM inválida",
            code="invalid_worm_object_version",
            field_path="object_version_id",
        )
    return normalized_value


def validate_manifest_digest(value: str) -> str:
    digest = validate_current_hash(value, field_path="manifest_digest")
    if digest is None:
        raise AuditEvidenceValidationError(
            "digest de manifesto WORM é obrigatório",
            code="invalid_worm_manifest_digest",
            field_path="manifest_digest",
        )
    return digest


def validate_legal_hold(value: bool) -> bool:
    if not isinstance(value, bool):
        raise AuditEvidenceValidationError(
            "legal hold WORM inválido",
            code="invalid_worm_legal_hold",
            field_path="legal_hold",
        )
    return value


def validate_legal_hold_reason(value: str | None, *, legal_hold: bool) -> str | None:
    if not legal_hold:
        if value is None:
            return None
        normalized_value = value.strip()
        if not normalized_value:
            return None
    else:
        if value is None or not value.strip():
            raise AuditEvidenceValidationError(
                "legal hold exige motivo técnico",
                code="missing_worm_legal_hold_reason",
                field_path="legal_hold_reason",
            )
        normalized_value = value.strip()
    if _LEGAL_HOLD_REASON_PATTERN.fullmatch(normalized_value) is None or "@" in normalized_value:
        raise AuditEvidenceValidationError(
            "motivo técnico de legal hold inválido",
            code="invalid_worm_legal_hold_reason",
            field_path="legal_hold_reason",
        )
    return normalized_value


def ensure_not_shortened_retention(
    *,
    existing_retain_until: datetime,
    requested_retain_until: datetime,
) -> None:
    if requested_retain_until < existing_retain_until:
        raise AuditEvidenceValidationError(
            "retenção WORM não pode ser encurtada silenciosamente",
            code="shortened_worm_retention",
            field_path="retain_until",
        )
