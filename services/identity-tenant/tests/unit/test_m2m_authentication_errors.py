from __future__ import annotations

import pytest
from creditos_identity_tenant.domain.errors import (
    AuthorizationError,
    ExpiredTokenError,
    InactiveTenantError,
    InsufficientRoleError,
    InsufficientScopeError,
    InvalidAuthorizationContextError,
    InvalidAuthorizationRequirementError,
    InvalidTenantContextError,
    InvalidTokenAudienceError,
    InvalidTokenError,
    InvalidTokenIssuerError,
    M2MAuthenticationError,
    MissingTokenError,
    MissingTokenRequiredClaimError,
)


@pytest.mark.parametrize(
    ("error_class", "code"),
    [
        (MissingTokenError, "missing_token"),
        (InvalidTokenError, "invalid_token"),
        (ExpiredTokenError, "expired_token"),
        (InvalidTokenAudienceError, "invalid_token_audience"),
        (InvalidTokenIssuerError, "invalid_token_issuer"),
        (MissingTokenRequiredClaimError, "missing_token_required_claim"),
    ],
)
def test_m2m_authentication_errors_have_stable_safe_public_shape(
    error_class: type[M2MAuthenticationError],
    code: str,
) -> None:
    error = error_class("detalhe interno que não deve ser resposta pública")

    assert error.code == code
    assert error.safe_message == "token inválido"
    assert error.grpc_status == "UNAUTHENTICATED"
    assert "detalhe interno" in str(error)


def test_invalid_tenant_context_errors_are_permission_denied_and_safe() -> None:
    error = InvalidTenantContextError("payload divergente")
    inactive_error = InactiveTenantError("tenant suspenso")

    assert error.code == "invalid_tenant_context"
    assert error.safe_message == "contexto de tenant inválido"
    assert error.grpc_status == "PERMISSION_DENIED"
    assert inactive_error.code == "inactive_tenant"
    assert inactive_error.safe_message == "contexto de tenant inválido"
    assert inactive_error.grpc_status == "PERMISSION_DENIED"


@pytest.mark.parametrize(
    ("error_class", "code", "safe_message"),
    [
        (AuthorizationError, "authorization_error", "autorização negada"),
        (
            InvalidAuthorizationContextError,
            "invalid_authorization_context",
            "contexto de autorização inválido",
        ),
        (
            InvalidAuthorizationRequirementError,
            "invalid_authorization_requirement",
            "requisito de autorização inválido",
        ),
        (InsufficientScopeError, "insufficient_scope", "autorização negada"),
        (InsufficientRoleError, "insufficient_role", "autorização negada"),
    ],
)
def test_authorization_errors_have_stable_safe_public_shape(
    error_class: type[AuthorizationError],
    code: str,
    safe_message: str,
) -> None:
    error = error_class("detalhe interno da policy")

    assert error.code == code
    assert error.safe_message == safe_message
    assert error.grpc_status == "PERMISSION_DENIED"
    assert "detalhe interno" in str(error)
