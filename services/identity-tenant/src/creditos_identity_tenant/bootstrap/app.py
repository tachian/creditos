from __future__ import annotations

from creditos_identity_tenant.adapters.logging.in_memory_operation_logger import (
    InMemoryOperationLogger,
)
from creditos_identity_tenant.adapters.persistence.in_memory_tenant_repository import (
    InMemoryTenantRepository,
)
from creditos_identity_tenant.application.service import TenantApplicationService


def build_local_tenant_application_service(
    *,
    environment: str = "local",
) -> TenantApplicationService:
    return TenantApplicationService(
        repository=InMemoryTenantRepository(),
        operation_logger=InMemoryOperationLogger(),
        environment=environment,
    )
