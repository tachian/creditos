from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from creditos_audit_evidence.domain.value_objects.audit_worm_export import WormRetentionMode


@dataclass(frozen=True, slots=True)
class AuditWormStorageObject:
    object_key: str
    object_version_id: str
    body: str
    body_digest: str
    retention_mode: WormRetentionMode
    retain_until: datetime
    legal_hold: bool
    legal_hold_reason: str | None


@dataclass(frozen=True, slots=True)
class AuditWormStoragePutResult:
    object_key: str
    object_version_id: str
    body_digest: str
    retention_mode: WormRetentionMode
    retain_until: datetime
    legal_hold: bool
    legal_hold_reason: str | None


class AuditWormStorage(Protocol):
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
    ) -> AuditWormStoragePutResult: ...

    def head_object(
        self,
        *,
        tenant_id: str,
        object_key: str,
        object_version_id: str,
    ) -> AuditWormStorageObject | None: ...

    def get_object(
        self,
        *,
        tenant_id: str,
        object_key: str,
        object_version_id: str,
    ) -> AuditWormStorageObject | None: ...
