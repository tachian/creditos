from __future__ import annotations


class TenantDomainError(ValueError):
    code = "tenant_domain_error"
    safe_message = "erro de domínio de tenant"
    grpc_status = "INVALID_ARGUMENT"

    def __init__(self, message: str | None = None) -> None:
        self.message = message or self.safe_message
        super().__init__(self.message)


class InvalidTenantIdentifierError(TenantDomainError):
    code = "invalid_tenant_identifier"
    safe_message = "identificador de tenant inválido"


class InvalidTenantNameError(TenantDomainError):
    code = "invalid_tenant_name"
    safe_message = "nome do tenant inválido"


class InvalidTenantStatusError(TenantDomainError):
    code = "invalid_tenant_status"
    safe_message = "status de tenant inválido"


class InvalidTenantIsolationTierError(TenantDomainError):
    code = "invalid_tenant_isolation_tier"
    safe_message = "tier de isolamento de tenant inválido"


class InvalidOperatorError(TenantDomainError):
    code = "invalid_operator"
    safe_message = "operador inválido"


class UnauthorizedOperatorError(TenantDomainError):
    code = "unauthorized_operator"
    safe_message = "operador não autorizado"
    grpc_status = "PERMISSION_DENIED"


class TenantAlreadyExistsError(TenantDomainError):
    code = "tenant_already_exists"
    safe_message = "tenant já existe"
    grpc_status = "ALREADY_EXISTS"


class TenantNotFoundError(TenantDomainError):
    code = "tenant_not_found"
    safe_message = "tenant não encontrado"
    grpc_status = "NOT_FOUND"


class CrossTenantAccessDeniedError(TenantDomainError):
    code = "cross_tenant_access_denied"
    safe_message = "acesso cross-tenant negado"
    grpc_status = "PERMISSION_DENIED"
