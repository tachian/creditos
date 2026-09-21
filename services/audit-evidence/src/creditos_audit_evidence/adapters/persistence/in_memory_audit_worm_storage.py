from __future__ import annotations

import hashlib
from datetime import datetime
from threading import RLock

from creditos_audit_evidence.application.ports import (
    AuditWormStorageObject,
    AuditWormStoragePutResult,
)
from creditos_audit_evidence.domain.errors import (
    AuditEvidenceConflictError,
    AuditEvidenceValidationError,
)
from creditos_audit_evidence.domain.value_objects.audit_event import validate_tenant_id
from creditos_audit_evidence.domain.value_objects.audit_worm_export import (
    WormRetentionMode,
    validate_legal_hold,
    validate_legal_hold_reason,
    validate_retain_until,
    validate_retention_mode,
    validate_worm_object_key,
    validate_worm_object_version,
)


class InMemoryAuditWormStorage:
    def __init__(self) -> None:
        self._objects: dict[tuple[str, str, str], AuditWormStorageObject] = {}
        self._versions_by_object: dict[tuple[str, str], tuple[str, ...]] = {}
        self._lock = RLock()

    def put_object(
        self,
        *,
        tenant_id: str,
        object_key: str,
        body: str,
        retention_mode: WormRetentionMode,
        retain_until: datetime,
        legal_hold: bool,
        legal_hold_reason: str | None,
    ) -> AuditWormStoragePutResult:
        tenant_id = validate_tenant_id(tenant_id)
        object_key = validate_worm_object_key(object_key)
        if not isinstance(body, str) or not body:
            raise AuditEvidenceValidationError(
                "corpo WORM inválido",
                code="invalid_worm_body",
                field_path="body",
            )
        retention_mode = validate_retention_mode(retention_mode)
        retain_until = validate_retain_until(retain_until)
        legal_hold = validate_legal_hold(legal_hold)
        legal_hold_reason = validate_legal_hold_reason(
            legal_hold_reason,
            legal_hold=legal_hold,
        )
        body_digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
        with self._lock:
            object_versions = self._versions_by_object.get((tenant_id, object_key), ())
            for version_id in object_versions:
                stored = self._objects[(tenant_id, object_key, version_id)]
                if stored.body_digest == body_digest:
                    return AuditWormStoragePutResult(
                        object_key=stored.object_key,
                        object_version_id=stored.object_version_id,
                        body_digest=stored.body_digest,
                        retention_mode=stored.retention_mode,
                        retain_until=stored.retain_until,
                        legal_hold=stored.legal_hold,
                        legal_hold_reason=stored.legal_hold_reason,
                    )
            if object_versions:
                raise AuditEvidenceConflictError(
                    "objeto WORM já existe com conteúdo divergente",
                    code="conflicting_worm_object",
                    field_path="object_key",
                )
            object_version_id = validate_worm_object_version(f"v{len(object_versions) + 1:06d}")
            object_value = AuditWormStorageObject(
                object_key=object_key,
                object_version_id=object_version_id,
                body=body,
                body_digest=body_digest,
                retention_mode=retention_mode,
                retain_until=retain_until,
                legal_hold=legal_hold,
                legal_hold_reason=legal_hold_reason,
            )
            self._objects[(tenant_id, object_key, object_version_id)] = object_value
            self._versions_by_object[(tenant_id, object_key)] = (
                *object_versions,
                object_version_id,
            )
            return AuditWormStoragePutResult(
                object_key=object_key,
                object_version_id=object_version_id,
                body_digest=body_digest,
                retention_mode=retention_mode,
                retain_until=retain_until,
                legal_hold=legal_hold,
                legal_hold_reason=legal_hold_reason,
            )

    def head_object(
        self,
        *,
        tenant_id: str,
        object_key: str,
        object_version_id: str,
    ) -> AuditWormStorageObject | None:
        return self.get_object(
            tenant_id=tenant_id,
            object_key=object_key,
            object_version_id=object_version_id,
        )

    def get_object(
        self,
        *,
        tenant_id: str,
        object_key: str,
        object_version_id: str,
    ) -> AuditWormStorageObject | None:
        tenant_id = validate_tenant_id(tenant_id)
        object_key = validate_worm_object_key(object_key)
        object_version_id = validate_worm_object_version(object_version_id)
        with self._lock:
            return self._objects.get((tenant_id, object_key, object_version_id))
