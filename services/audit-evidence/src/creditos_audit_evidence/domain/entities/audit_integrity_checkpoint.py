from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from creditos_audit_evidence.domain.errors import AuditEvidenceValidationError
from creditos_audit_evidence.domain.value_objects.audit_event import (
    validate_event_id,
    validate_occurred_at,
    validate_tenant_id,
)
from creditos_audit_evidence.domain.value_objects.audit_integrity import (
    CANONICALIZATION_VERSION,
    HASH_ALGORITHM,
    validate_canonicalization_version,
    validate_current_hash,
    validate_hash_algorithm,
)


@dataclass(frozen=True, slots=True)
class AuditIntegrityCheckpoint:
    checkpoint_id: str
    tenant_id: str
    window_started_at: datetime
    window_ended_at: datetime
    event_count: int
    first_event_id: str
    last_event_id: str
    first_event_hash: str
    last_event_hash: str
    batch_digest: str
    signature: str
    signature_key_ref: str
    hash_algorithm: str = HASH_ALGORITHM
    canonicalization_version: str = CANONICALIZATION_VERSION
    signature_algorithm: str = "hmac-sha256-test"
    created_at: datetime | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "checkpoint_id", validate_event_id(self.checkpoint_id))
        object.__setattr__(self, "tenant_id", validate_tenant_id(self.tenant_id))
        object.__setattr__(
            self,
            "window_started_at",
            validate_occurred_at(self.window_started_at),
        )
        object.__setattr__(self, "window_ended_at", validate_occurred_at(self.window_ended_at))
        if self.window_started_at > self.window_ended_at:
            raise AuditEvidenceValidationError(
                "janela de checkpoint inválida",
                code="invalid_checkpoint_window",
                field_path="window_started_at",
            )
        if self.event_count < 1:
            raise AuditEvidenceValidationError(
                "checkpoint exige ao menos um evento",
                code="empty_checkpoint_window",
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
        if not self.signature or not isinstance(self.signature, str):
            raise AuditEvidenceValidationError(
                "assinatura de checkpoint inválida",
                code="invalid_checkpoint_signature",
                field_path="signature",
            )
        if not self.signature_key_ref or not isinstance(self.signature_key_ref, str):
            raise AuditEvidenceValidationError(
                "referência de chave de checkpoint inválida",
                code="invalid_checkpoint_signature_key_ref",
                field_path="signature_key_ref",
            )
        object.__setattr__(self, "hash_algorithm", validate_hash_algorithm(self.hash_algorithm))
        object.__setattr__(
            self,
            "canonicalization_version",
            validate_canonicalization_version(self.canonicalization_version),
        )
        if self.created_at is not None:
            object.__setattr__(self, "created_at", validate_occurred_at(self.created_at))
