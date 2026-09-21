from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import Any

from creditos_audit_evidence.domain.errors import AuditEvidenceValidationError
from creditos_audit_evidence.domain.value_objects.audit_event import (
    validate_event_id,
    validate_occurred_at,
    validate_tenant_id,
)
from creditos_audit_evidence.domain.value_objects.audit_integrity import (
    CANONICALIZATION_VERSION,
    HASH_ALGORITHM,
    validate_current_hash,
)
from creditos_audit_evidence.domain.value_objects.audit_worm_export import (
    WORM_MANIFEST_VERSION,
    AuditWormExportStatus,
    WormRetentionMode,
    validate_legal_hold,
    validate_legal_hold_reason,
    validate_manifest_digest,
    validate_manifest_version,
    validate_retain_until,
    validate_retention_class,
    validate_retention_mode,
    validate_worm_object_key,
    validate_worm_object_version,
)


@dataclass(frozen=True, slots=True)
class AuditWormExportManifest:
    manifest_version: str
    tenant_id: str
    checkpoint_id: str
    window_started_at: datetime
    window_ended_at: datetime
    event_count: int
    first_event_id: str
    last_event_id: str
    first_event_hash: str
    last_event_hash: str
    batch_digest: str
    checkpoint_signature: str
    checkpoint_signature_key_ref: str
    checkpoint_signature_algorithm: str
    hash_algorithm: str
    canonicalization_version: str
    retention_class: str
    retention_mode: WormRetentionMode
    retain_until: datetime
    legal_hold: bool
    legal_hold_reason: str | None
    created_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "manifest_version", validate_manifest_version(self.manifest_version)
        )
        object.__setattr__(self, "tenant_id", validate_tenant_id(self.tenant_id))
        object.__setattr__(self, "checkpoint_id", validate_event_id(self.checkpoint_id))
        object.__setattr__(self, "window_started_at", validate_occurred_at(self.window_started_at))
        object.__setattr__(self, "window_ended_at", validate_occurred_at(self.window_ended_at))
        if self.window_started_at > self.window_ended_at:
            raise AuditEvidenceValidationError(
                "janela de manifesto WORM inválida",
                code="invalid_worm_manifest_window",
                field_path="window_started_at",
            )
        if self.event_count < 1:
            raise AuditEvidenceValidationError(
                "manifesto WORM exige ao menos um evento",
                code="empty_worm_manifest",
                field_path="event_count",
            )
        object.__setattr__(self, "first_event_id", validate_event_id(self.first_event_id))
        object.__setattr__(self, "last_event_id", validate_event_id(self.last_event_id))
        object.__setattr__(
            self,
            "first_event_hash",
            validate_current_hash(self.first_event_hash, field_path="first_event_hash"),
        )
        object.__setattr__(
            self,
            "last_event_hash",
            validate_current_hash(self.last_event_hash, field_path="last_event_hash"),
        )
        object.__setattr__(
            self,
            "batch_digest",
            validate_current_hash(self.batch_digest, field_path="batch_digest"),
        )
        object.__setattr__(
            self,
            "checkpoint_signature",
            _validate_non_empty_string(
                self.checkpoint_signature,
                field_path="checkpoint_signature",
                code="invalid_worm_checkpoint_signature",
            ),
        )
        object.__setattr__(
            self,
            "checkpoint_signature_key_ref",
            _validate_non_empty_string(
                self.checkpoint_signature_key_ref,
                field_path="checkpoint_signature_key_ref",
                code="invalid_worm_checkpoint_signature_key_ref",
            ),
        )
        object.__setattr__(
            self,
            "checkpoint_signature_algorithm",
            _validate_non_empty_string(
                self.checkpoint_signature_algorithm,
                field_path="checkpoint_signature_algorithm",
                code="invalid_worm_checkpoint_signature_algorithm",
            ),
        )
        if self.hash_algorithm != HASH_ALGORITHM:
            raise AuditEvidenceValidationError(
                "algoritmo de hash WORM inválido",
                code="invalid_worm_hash_algorithm",
                field_path="hash_algorithm",
            )
        if self.canonicalization_version != CANONICALIZATION_VERSION:
            raise AuditEvidenceValidationError(
                "versão de canonicalização WORM inválida",
                code="invalid_worm_canonicalization_version",
                field_path="canonicalization_version",
            )
        object.__setattr__(self, "retention_class", validate_retention_class(self.retention_class))
        object.__setattr__(self, "retention_mode", validate_retention_mode(self.retention_mode))
        object.__setattr__(
            self,
            "retain_until",
            validate_retain_until(self.retain_until, now=self.created_at),
        )
        object.__setattr__(self, "legal_hold", validate_legal_hold(self.legal_hold))
        object.__setattr__(
            self,
            "legal_hold_reason",
            validate_legal_hold_reason(self.legal_hold_reason, legal_hold=self.legal_hold),
        )
        object.__setattr__(self, "created_at", validate_occurred_at(self.created_at))

    @classmethod
    def from_checkpoint(
        cls,
        *,
        tenant_id: str,
        checkpoint_id: str,
        window_started_at: datetime,
        window_ended_at: datetime,
        event_count: int,
        first_event_id: str,
        last_event_id: str,
        first_event_hash: str,
        last_event_hash: str,
        batch_digest: str,
        checkpoint_signature: str,
        checkpoint_signature_key_ref: str,
        checkpoint_signature_algorithm: str,
        retention_class: str,
        retention_mode: WormRetentionMode | str,
        retain_until: datetime,
        legal_hold: bool,
        legal_hold_reason: str | None,
        created_at: datetime,
    ) -> AuditWormExportManifest:
        return cls(
            manifest_version=WORM_MANIFEST_VERSION,
            tenant_id=tenant_id,
            checkpoint_id=checkpoint_id,
            window_started_at=window_started_at,
            window_ended_at=window_ended_at,
            event_count=event_count,
            first_event_id=first_event_id,
            last_event_id=last_event_id,
            first_event_hash=first_event_hash,
            last_event_hash=last_event_hash,
            batch_digest=batch_digest,
            checkpoint_signature=checkpoint_signature,
            checkpoint_signature_key_ref=checkpoint_signature_key_ref,
            checkpoint_signature_algorithm=checkpoint_signature_algorithm,
            hash_algorithm=HASH_ALGORITHM,
            canonicalization_version=CANONICALIZATION_VERSION,
            retention_class=retention_class,
            retention_mode=validate_retention_mode(retention_mode),
            retain_until=retain_until,
            legal_hold=legal_hold,
            legal_hold_reason=legal_hold_reason,
            created_at=created_at,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "manifest_version": self.manifest_version,
            "tenant_id": self.tenant_id,
            "checkpoint_id": self.checkpoint_id,
            "window_started_at": self.window_started_at.isoformat(),
            "window_ended_at": self.window_ended_at.isoformat(),
            "event_count": self.event_count,
            "first_event_id": self.first_event_id,
            "last_event_id": self.last_event_id,
            "first_event_hash": self.first_event_hash,
            "last_event_hash": self.last_event_hash,
            "batch_digest": self.batch_digest,
            "checkpoint_signature": self.checkpoint_signature,
            "checkpoint_signature_key_ref": self.checkpoint_signature_key_ref,
            "checkpoint_signature_algorithm": self.checkpoint_signature_algorithm,
            "hash_algorithm": self.hash_algorithm,
            "canonicalization_version": self.canonicalization_version,
            "retention_class": self.retention_class,
            "retention_mode": self.retention_mode.value,
            "retain_until": self.retain_until.isoformat(),
            "legal_hold": self.legal_hold,
            "legal_hold_reason": self.legal_hold_reason,
            "created_at": self.created_at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class AuditWormExport:
    export_id: str
    tenant_id: str
    checkpoint_id: str
    window_started_at: datetime
    window_ended_at: datetime
    object_key: str
    object_version_id: str
    manifest_digest: str
    manifest_version: str
    retention_class: str
    retention_mode: WormRetentionMode
    retain_until: datetime
    legal_hold: bool
    legal_hold_reason: str | None
    status: AuditWormExportStatus
    created_at: datetime
    event_count: int
    batch_digest: str
    safe_metadata: dict[str, str] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "export_id", validate_event_id(self.export_id))
        object.__setattr__(self, "tenant_id", validate_tenant_id(self.tenant_id))
        object.__setattr__(self, "checkpoint_id", validate_event_id(self.checkpoint_id))
        object.__setattr__(self, "window_started_at", validate_occurred_at(self.window_started_at))
        object.__setattr__(self, "window_ended_at", validate_occurred_at(self.window_ended_at))
        object.__setattr__(self, "object_key", validate_worm_object_key(self.object_key))
        object.__setattr__(
            self,
            "object_version_id",
            validate_worm_object_version(self.object_version_id),
        )
        object.__setattr__(self, "manifest_digest", validate_manifest_digest(self.manifest_digest))
        object.__setattr__(
            self, "manifest_version", validate_manifest_version(self.manifest_version)
        )
        object.__setattr__(self, "retention_class", validate_retention_class(self.retention_class))
        object.__setattr__(self, "retention_mode", validate_retention_mode(self.retention_mode))
        object.__setattr__(
            self,
            "retain_until",
            validate_retain_until(self.retain_until, now=self.created_at),
        )
        object.__setattr__(self, "legal_hold", validate_legal_hold(self.legal_hold))
        object.__setattr__(
            self,
            "legal_hold_reason",
            validate_legal_hold_reason(self.legal_hold_reason, legal_hold=self.legal_hold),
        )
        object.__setattr__(self, "status", _validate_status(self.status))
        object.__setattr__(self, "created_at", validate_occurred_at(self.created_at))
        if self.event_count < 1:
            raise AuditEvidenceValidationError(
                "exportação WORM exige ao menos um evento",
                code="empty_worm_export",
                field_path="event_count",
            )
        object.__setattr__(
            self,
            "batch_digest",
            validate_current_hash(self.batch_digest, field_path="batch_digest"),
        )
        object.__setattr__(
            self,
            "safe_metadata",
            MappingProxyType(dict(self.safe_metadata or {})),
        )


def _validate_status(value: AuditWormExportStatus | str) -> AuditWormExportStatus:
    try:
        return (
            value if isinstance(value, AuditWormExportStatus) else AuditWormExportStatus(str(value))
        )
    except ValueError as exc:
        raise AuditEvidenceValidationError(
            "status de exportação WORM inválido",
            code="invalid_worm_export_status",
            field_path="status",
        ) from exc


def _validate_non_empty_string(value: str, *, field_path: str, code: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AuditEvidenceValidationError(
            f"{field_path} inválido",
            code=code,
            field_path=field_path,
        )
    return value.strip()
