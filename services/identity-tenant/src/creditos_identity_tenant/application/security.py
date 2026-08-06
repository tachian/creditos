from __future__ import annotations

from dataclasses import dataclass

from creditos_identity_tenant.domain.errors import InvalidOperatorError, UnauthorizedOperatorError


@dataclass(frozen=True, slots=True)
class OperatorContext:
    operator_id: str
    authorized: bool = False
    can_access_tenant_catalog: bool = False

    @classmethod
    def platform_operator(cls, operator_id: str) -> OperatorContext:
        return cls(
            operator_id=operator_id,
            authorized=True,
            can_access_tenant_catalog=True,
        )

    @classmethod
    def tenant_scoped(cls, operator_id: str) -> OperatorContext:
        return cls(operator_id=operator_id, authorized=True)

    def require_authorized(self) -> None:
        if not isinstance(self.operator_id, str) or not self.operator_id.strip():
            raise InvalidOperatorError("operator_id é obrigatório")
        if not self.authorized:
            raise UnauthorizedOperatorError("operador não autorizado")

    def require_tenant_catalog_access(self) -> None:
        self.require_authorized()
        if not self.can_access_tenant_catalog:
            raise UnauthorizedOperatorError("operador sem permissão de catálogo de tenant")
