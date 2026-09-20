from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from threading import RLock

from creditos_audit_evidence.domain.entities import AuditIntegrityCheckpoint
from creditos_audit_evidence.domain.errors import AuditEvidenceConflictError


class InMemoryAuditIntegrityCheckpointRepository:
    def __init__(self) -> None:
        self._checkpoints: dict[tuple[str, str], AuditIntegrityCheckpoint] = {}
        self._by_window: dict[tuple[str, datetime, datetime], str] = {}
        self._lock = RLock()

    def append(
        self,
        checkpoint: AuditIntegrityCheckpoint,
        *,
        before_commit: Callable[[], None] | None = None,
    ) -> AuditIntegrityCheckpoint:
        key = _checkpoint_key(checkpoint.tenant_id, checkpoint.checkpoint_id)
        window_key = _window_key(
            checkpoint.tenant_id,
            checkpoint.window_started_at,
            checkpoint.window_ended_at,
        )
        with self._lock:
            if key in self._checkpoints or window_key in self._by_window:
                raise AuditEvidenceConflictError(
                    "checkpoint de integridade duplicado",
                    code="duplicate_audit_integrity_checkpoint",
                    field_path="checkpoint_id",
                )
            if before_commit is not None:
                before_commit()
            if key in self._checkpoints or window_key in self._by_window:
                raise AuditEvidenceConflictError(
                    "checkpoint de integridade duplicado",
                    code="duplicate_audit_integrity_checkpoint",
                    field_path="checkpoint_id",
                )
            self._checkpoints[key] = checkpoint
            self._by_window[window_key] = checkpoint.checkpoint_id
            return checkpoint

    def get(self, *, tenant_id: str, checkpoint_id: str) -> AuditIntegrityCheckpoint | None:
        with self._lock:
            return self._checkpoints.get(_checkpoint_key(tenant_id, checkpoint_id))

    def get_by_window(
        self,
        *,
        tenant_id: str,
        window_started_at: datetime,
        window_ended_at: datetime,
    ) -> AuditIntegrityCheckpoint | None:
        with self._lock:
            checkpoint_id = self._by_window.get(
                _window_key(tenant_id, window_started_at, window_ended_at)
            )
            if checkpoint_id is None:
                return None
            return self._checkpoints.get(_checkpoint_key(tenant_id, checkpoint_id))


def _checkpoint_key(tenant_id: str, checkpoint_id: str) -> tuple[str, str]:
    return (tenant_id, checkpoint_id)


def _window_key(
    tenant_id: str,
    window_started_at: datetime,
    window_ended_at: datetime,
) -> tuple[str, datetime, datetime]:
    return (tenant_id, window_started_at, window_ended_at)
