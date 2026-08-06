from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from uuid import uuid4

from creditos_identity_tenant.application.ports.tenant_repository import TenantRepository
from creditos_identity_tenant.application.security import OperatorContext
from creditos_identity_tenant.domain.entities.tenant import Tenant


@dataclass(frozen=True, slots=True)
class CreateTenantCommand:
    name: str
    status: str
    tenant_isolation_tier: str | None = None


class CreateTenantUseCase:
    def __init__(
        self,
        *,
        repository: TenantRepository,
        tenant_id_generator: Callable[[], str] | None = None,
    ) -> None:
        self._repository = repository
        self._tenant_id_generator = tenant_id_generator or _default_tenant_id

    def execute(self, command: CreateTenantCommand, operator: OperatorContext) -> Tenant:
        operator.require_tenant_catalog_access()
        tenant_id = self._tenant_id_generator()
        tenant = Tenant.create(
            tenant_id=tenant_id,
            name=command.name,
            status=command.status,
            tenant_isolation_tier=command.tenant_isolation_tier,
            operator_id=operator.operator_id,
        )

        self._repository.save_unique(tenant)
        return tenant


def _default_tenant_id() -> str:
    return f"tenant_{uuid4().hex}"
