from __future__ import annotations

from dataclasses import dataclass

from creditos_identity_tenant.application.ports.tenant_repository import TenantRepository
from creditos_identity_tenant.application.security import OperatorContext
from creditos_identity_tenant.domain.errors import (
    CrossTenantAccessDeniedError,
    InvalidTenantIdentifierError,
    TenantNotFoundError,
)


@dataclass(frozen=True, slots=True)
class GetTenantQuery:
    tenant_id: str
    trusted_context_tenant_id: str | None = None


class GetTenantUseCase:
    def __init__(self, *, repository: TenantRepository) -> None:
        self._repository = repository

    def execute(self, query: GetTenantQuery, operator: OperatorContext) -> dict[str, str]:
        operator.require_authorized()
        tenant_id = _normalize_tenant_id(query.tenant_id)
        trusted_context_tenant_id = _normalize_optional_tenant_id(query.trusted_context_tenant_id)

        if trusted_context_tenant_id is None:
            operator.require_tenant_catalog_access()
        elif trusted_context_tenant_id != tenant_id:
            raise CrossTenantAccessDeniedError("contexto de tenant não permite esta consulta")

        tenant = self._repository.get(tenant_id)
        if tenant is None:
            raise TenantNotFoundError(f"tenant não encontrado: {tenant_id}")

        return tenant.to_metadata()


def _normalize_tenant_id(value: str) -> str:
    if not isinstance(value, str):
        raise InvalidTenantIdentifierError("tenant_id é obrigatório")

    normalized_value = value.strip()
    if not normalized_value:
        raise InvalidTenantIdentifierError("tenant_id é obrigatório")
    return normalized_value


def _normalize_optional_tenant_id(value: str | None) -> str | None:
    if value is None:
        return None
    return _normalize_tenant_id(value)
