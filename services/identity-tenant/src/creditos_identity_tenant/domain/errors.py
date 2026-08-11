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


class AuthorizationError(TenantDomainError):
    code = "authorization_error"
    safe_message = "autorização negada"
    grpc_status = "PERMISSION_DENIED"


class CrossTenantAccessDeniedError(AuthorizationError):
    code = "cross_tenant_access_denied"
    safe_message = "acesso cross-tenant negado"


class M2MAuthenticationError(TenantDomainError):
    code = "m2m_authentication_error"
    safe_message = "token inválido"
    grpc_status = "UNAUTHENTICATED"


class MissingTokenError(M2MAuthenticationError):
    code = "missing_token"


class InvalidTokenError(M2MAuthenticationError):
    code = "invalid_token"


class ExpiredTokenError(M2MAuthenticationError):
    code = "expired_token"


class InvalidTokenAudienceError(M2MAuthenticationError):
    code = "invalid_token_audience"


class InvalidTokenIssuerError(M2MAuthenticationError):
    code = "invalid_token_issuer"


class MissingTokenRequiredClaimError(M2MAuthenticationError):
    code = "missing_token_required_claim"


class InvalidTenantContextError(TenantDomainError):
    code = "invalid_tenant_context"
    safe_message = "contexto de tenant inválido"
    grpc_status = "PERMISSION_DENIED"


class InactiveTenantError(InvalidTenantContextError):
    code = "inactive_tenant"


class InvalidAuthorizationContextError(AuthorizationError):
    code = "invalid_authorization_context"
    safe_message = "contexto de autorização inválido"


class InvalidAuthorizationRequirementError(AuthorizationError):
    code = "invalid_authorization_requirement"
    safe_message = "requisito de autorização inválido"


class InsufficientScopeError(AuthorizationError):
    code = "insufficient_scope"


class InsufficientRoleError(AuthorizationError):
    code = "insufficient_role"
