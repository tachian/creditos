from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime

from creditos_identity_tenant.domain.errors import (
    InvalidOperatorError,
    InvalidTenantIdentifierError,
    InvalidTenantNameError,
)
from creditos_identity_tenant.domain.value_objects.tenant_isolation_tier import (
    TenantIsolationTier,
)
from creditos_identity_tenant.domain.value_objects.tenant_status import TenantStatus

_TENANT_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]{2,63}$")
_MAX_TENANT_NAME_LENGTH = 160


@dataclass(frozen=True, slots=True)
class Tenant:
    tenant_id: str
    name: str
    status: TenantStatus
    tenant_isolation_tier: TenantIsolationTier
    created_at: datetime
    updated_at: datetime
    created_by: str
    updated_by: str

    @classmethod
    def create(
        cls,
        *,
        tenant_id: str,
        name: str,
        status: str | TenantStatus,
        operator_id: str,
        tenant_isolation_tier: str | TenantIsolationTier | None = None,
        created_at: datetime | None = None,
    ) -> Tenant:
        normalized_tenant_id = _normalize_tenant_id(tenant_id)
        normalized_name = _normalize_name(name)
        normalized_operator_id = _normalize_operator_id(operator_id)
        normalized_status = TenantStatus.from_value(status)
        normalized_tier = TenantIsolationTier.from_value(tenant_isolation_tier)
        timestamp = created_at or datetime.now(UTC)

        return cls(
            tenant_id=normalized_tenant_id,
            name=normalized_name,
            status=normalized_status,
            tenant_isolation_tier=normalized_tier,
            created_at=timestamp,
            updated_at=timestamp,
            created_by=normalized_operator_id,
            updated_by=normalized_operator_id,
        )

    def to_metadata(self) -> dict[str, str]:
        return {
            "tenant_id": self.tenant_id,
            "name": self.name,
            "status": self.status.value,
            "tenant_isolation_tier": self.tenant_isolation_tier.value,
        }


def _normalize_tenant_id(value: str) -> str:
    if not isinstance(value, str):
        raise InvalidTenantIdentifierError("tenant_id é obrigatório")

    normalized_value = value.strip()
    if not normalized_value:
        raise InvalidTenantIdentifierError("tenant_id é obrigatório")
    if not _TENANT_ID_PATTERN.fullmatch(normalized_value):
        raise InvalidTenantIdentifierError("tenant_id possui formato inválido")
    return normalized_value


def _normalize_name(value: str) -> str:
    if not isinstance(value, str):
        raise InvalidTenantNameError("nome do tenant é obrigatório")

    normalized_value = " ".join(value.strip().split())
    if not normalized_value:
        raise InvalidTenantNameError("nome do tenant é obrigatório")
    if len(normalized_value) > _MAX_TENANT_NAME_LENGTH:
        raise InvalidTenantNameError("nome do tenant excede o tamanho máximo")
    return normalized_value


def _normalize_operator_id(value: str) -> str:
    if not isinstance(value, str):
        raise InvalidOperatorError("operator_id é obrigatório")

    normalized_value = value.strip()
    if not normalized_value:
        raise InvalidOperatorError("operator_id é obrigatório")
    return normalized_value
