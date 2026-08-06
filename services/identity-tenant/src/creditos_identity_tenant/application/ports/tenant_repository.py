from __future__ import annotations

from typing import Protocol

from creditos_identity_tenant.domain.entities.tenant import Tenant


class TenantRepository(Protocol):
    def save_unique(self, tenant: Tenant) -> None: ...

    def get(self, tenant_id: str) -> Tenant | None: ...
