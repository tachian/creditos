from __future__ import annotations

from enum import StrEnum

from creditos_identity_tenant.domain.errors import InvalidTenantIsolationTierError


class TenantIsolationTier(StrEnum):
    BRIDGE = "bridge"
    SILO = "silo"

    @classmethod
    def from_value(cls, value: str | TenantIsolationTier | None) -> TenantIsolationTier:
        if value is None:
            return cls.BRIDGE

        if isinstance(value, TenantIsolationTier):
            return value

        if not isinstance(value, str):
            raise InvalidTenantIsolationTierError("tenant_isolation_tier inválido")

        normalized_value = value.strip().casefold()
        try:
            return cls(normalized_value)
        except ValueError as error:
            raise InvalidTenantIsolationTierError(
                f"tenant_isolation_tier inválido: {normalized_value or '<vazio>'}"
            ) from error
