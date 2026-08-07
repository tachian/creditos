from __future__ import annotations

from collections.abc import Callable

from creditos_identity_tenant.adapters.logging.in_memory_operation_logger import (
    InMemoryOperationLogger,
)
from creditos_identity_tenant.adapters.persistence.in_memory_tenant_repository import (
    InMemoryTenantRepository,
)
from creditos_identity_tenant.application.ports.m2m_token_verifier import M2MTokenVerifier
from creditos_identity_tenant.application.service import TenantApplicationService


def build_local_tenant_application_service(
    *,
    environment: str = "local",
    tenant_id_generator: Callable[[], str] | None = None,
    m2m_token_verifier: M2MTokenVerifier | None = None,
) -> TenantApplicationService:
    return TenantApplicationService(
        repository=InMemoryTenantRepository(),
        operation_logger=InMemoryOperationLogger(),
        tenant_id_generator=tenant_id_generator,
        m2m_token_verifier=m2m_token_verifier,
        environment=environment,
    )
