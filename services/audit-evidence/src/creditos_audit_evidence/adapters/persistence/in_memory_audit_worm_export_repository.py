from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from threading import RLock

from creditos_audit_evidence.domain.entities import AuditWormExport
from creditos_audit_evidence.domain.errors import AuditEvidenceConflictError
from creditos_audit_evidence.domain.value_objects.audit_worm_export import (
    ensure_not_shortened_retention,
)


class InMemoryAuditWormExportRepository:
    def __init__(self) -> None:
        self._exports: dict[tuple[str, str], AuditWormExport] = {}
        self._by_checkpoint_window: dict[tuple[str, str, datetime, datetime], str] = {}
        self._lock = RLock()

    def append(
        self,
        export: AuditWormExport,
        *,
        before_commit: Callable[[], None] | None = None,
    ) -> AuditWormExport:
        key = _export_key(export.tenant_id, export.export_id)
        window_key = _checkpoint_window_key(
            export.tenant_id,
            export.checkpoint_id,
            export.window_started_at,
            export.window_ended_at,
        )
        with self._lock:
            existing = self._existing_for_keys(key=key, window_key=window_key)
            if existing is not None:
                return _return_existing_or_raise(existing=existing, requested=export)
            if before_commit is not None:
                before_commit()
            existing = self._existing_for_keys(key=key, window_key=window_key)
            if existing is not None:
                return _return_existing_or_raise(existing=existing, requested=export)
            self._exports[key] = export
            self._by_checkpoint_window[window_key] = export.export_id
            return export

    def get(self, *, tenant_id: str, export_id: str) -> AuditWormExport | None:
        with self._lock:
            return self._exports.get(_export_key(tenant_id, export_id))

    def get_by_checkpoint_window(
        self,
        *,
        tenant_id: str,
        checkpoint_id: str,
        window_started_at: datetime,
        window_ended_at: datetime,
    ) -> AuditWormExport | None:
        with self._lock:
            export_id = self._by_checkpoint_window.get(
                _checkpoint_window_key(
                    tenant_id,
                    checkpoint_id,
                    window_started_at,
                    window_ended_at,
                )
            )
            if export_id is None:
                return None
            return self._exports.get(_export_key(tenant_id, export_id))

    def _existing_for_keys(
        self,
        *,
        key: tuple[str, str],
        window_key: tuple[str, str, datetime, datetime],
    ) -> AuditWormExport | None:
        existing = self._exports.get(key)
        if existing is not None:
            return existing
        export_id = self._by_checkpoint_window.get(window_key)
        if export_id is None:
            return None
        return self._exports.get((window_key[0], export_id))


def _return_existing_or_raise(
    *,
    existing: AuditWormExport,
    requested: AuditWormExport,
) -> AuditWormExport:
    ensure_not_shortened_retention(
        existing_retain_until=existing.retain_until,
        requested_retain_until=requested.retain_until,
    )
    comparable_fields_match = (
        existing.export_id == requested.export_id,
        existing.object_key == requested.object_key,
        existing.manifest_digest == requested.manifest_digest,
        existing.retention_class == requested.retention_class,
        existing.retention_mode == requested.retention_mode,
        existing.retain_until == requested.retain_until,
        existing.legal_hold == requested.legal_hold,
        existing.batch_digest == requested.batch_digest,
    )
    if all(comparable_fields_match):
        return existing
    raise AuditEvidenceConflictError(
        "exportação WORM divergente para checkpoint/janela",
        code="conflicting_worm_export",
        field_path="checkpoint_id",
    )


def _export_key(tenant_id: str, export_id: str) -> tuple[str, str]:
    return (tenant_id, export_id)


def _checkpoint_window_key(
    tenant_id: str,
    checkpoint_id: str,
    window_started_at: datetime,
    window_ended_at: datetime,
) -> tuple[str, str, datetime, datetime]:
    return (tenant_id, checkpoint_id, window_started_at, window_ended_at)
