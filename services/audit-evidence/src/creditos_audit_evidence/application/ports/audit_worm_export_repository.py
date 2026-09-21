from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Protocol

from creditos_audit_evidence.domain.entities import AuditWormExport


class AuditWormExportRepository(Protocol):
    def append(
        self,
        export: AuditWormExport,
        *,
        before_commit: Callable[[], None] | None = None,
    ) -> AuditWormExport: ...

    def get(self, *, tenant_id: str, export_id: str) -> AuditWormExport | None: ...

    def get_by_checkpoint_window(
        self,
        *,
        tenant_id: str,
        checkpoint_id: str,
        window_started_at: datetime,
        window_ended_at: datetime,
    ) -> AuditWormExport | None: ...
