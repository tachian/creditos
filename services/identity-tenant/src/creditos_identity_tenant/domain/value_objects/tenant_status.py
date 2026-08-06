from __future__ import annotations

from enum import StrEnum

from creditos_identity_tenant.domain.errors import InvalidTenantStatusError


class TenantStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"

    @classmethod
    def from_value(cls, value: str | TenantStatus) -> TenantStatus:
        if isinstance(value, TenantStatus):
            return value

        if not isinstance(value, str):
            raise InvalidTenantStatusError("status de tenant inválido")

        normalized_value = value.strip().casefold()
        try:
            return cls(normalized_value)
        except ValueError as error:
            raise InvalidTenantStatusError(
                f"status de tenant inválido: {normalized_value or '<vazio>'}"
            ) from error
