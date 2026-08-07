from __future__ import annotations

import pytest
from creditos_identity_tenant.domain.errors import (
    ExpiredTokenError,
    InactiveTenantError,
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
