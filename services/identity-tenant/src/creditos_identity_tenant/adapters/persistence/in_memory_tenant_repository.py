from __future__ import annotations

from threading import RLock

from creditos_identity_tenant.domain.entities.tenant import Tenant
from creditos_identity_tenant.domain.errors import TenantAlreadyExistsError


class InMemoryTenantRepository:
    def __init__(self) -> None:
        self._tenants: dict[str, Tenant] = {}
        self._lock = RLock()

    def exists(self, tenant_id: str) -> bool:
        with self._lock:
            return tenant_id in self._tenants

    def save_unique(self, tenant: Tenant) -> None:
        with self._lock:
            if tenant.tenant_id in self._tenants:
                raise TenantAlreadyExistsError(f"tenant já existe: {tenant.tenant_id}")
            self._tenants[tenant.tenant_id] = tenant

    def get(self, tenant_id: str) -> Tenant | None:
        with self._lock:
            return self._tenants.get(tenant_id)
