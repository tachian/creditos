from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from creditos_identity_tenant.application.ports.m2m_token_verifier import (
    AuthenticatedClientContext,
    TokenVerificationRequest,
)
from creditos_identity_tenant.application.use_cases.resolve_m2m_tenant_context import (
    ResolveM2MTenantContextCommand,
)
from creditos_identity_tenant.domain.errors import (
    MissingTokenError,
    MissingTokenRequiredClaimError,
)


def test_authenticated_client_context_normalizes_required_claims() -> None:
    issued_at = datetime(2026, 8, 6, 12, 0, tzinfo=UTC)
    expires_at = issued_at + timedelta(minutes=5)

    context = AuthenticatedClientContext(
        client_id=" client-alpha ",
        subject=" client-alpha ",
        scopes=("proposal:submit", "decision:read", "proposal:submit"),
        tenant_id=" tenant_alpha ",
        tenant_isolation_tier=" bridge ",
        issuer=" https://issuer.creditos.local ",
        audience=" creditos-api ",
        token_id=" token-123 ",
        issued_at=issued_at,
        expires_at=expires_at,
    )

    assert context.client_id == "client-alpha"
    assert context.subject == "client-alpha"
    assert context.scopes == frozenset({"proposal:submit", "decision:read"})
    assert context.tenant_id == "tenant_alpha"
    assert context.tenant_isolation_tier == "bridge"
    assert context.issuer == "https://issuer.creditos.local"
    assert context.audience == "creditos-api"
    assert context.token_id == "token-123"
    assert context.to_metadata() == {
        "client_id": "client-alpha",
        "subject": "client-alpha",
        "tenant_id": "tenant_alpha",
        "tenant_isolation_tier": "bridge",
        "issuer": "https://issuer.creditos.local",
        "audience": "creditos-api",
        "token_id": "token-123",
        "scopes": "decision:read proposal:submit",
    }


def test_authenticated_client_context_rejects_missing_required_claims() -> None:
    timestamp = datetime(2026, 8, 6, 12, 0, tzinfo=UTC)

    with pytest.raises(MissingTokenRequiredClaimError) as error:
        AuthenticatedClientContext(
            client_id="client-alpha",
            subject="client-alpha",
            scopes=("proposal:submit",),
            tenant_id="",
            tenant_isolation_tier="bridge",
            issuer="https://issuer.creditos.local",
            audience="creditos-api",
            token_id="token-123",
            issued_at=timestamp,
            expires_at=timestamp + timedelta(minutes=5),
        )

    assert error.value.code == "missing_token_required_claim"
    assert error.value.safe_message == "token inválido"
    assert error.value.grpc_status == "UNAUTHENTICATED"


def test_token_verification_request_extracts_bearer_token_without_leaking_header() -> None:
    request = TokenVerificationRequest(
        authorization_header=" Bearer local-token-alpha ",
        now=datetime(2026, 8, 6, 12, 0, tzinfo=UTC),
    )

    assert request.bearer_token == "local-token-alpha"
    assert "local-token-alpha" not in repr(request)


def test_token_verification_request_rejects_missing_or_malformed_token() -> None:
    with pytest.raises(MissingTokenError):
        TokenVerificationRequest(authorization_header=None)

    with pytest.raises(MissingTokenError):
        TokenVerificationRequest(authorization_header="Basic abc")

    with pytest.raises(MissingTokenError):
        TokenVerificationRequest(authorization_header="Bearer abc def")

    with pytest.raises(MissingTokenError):
        TokenVerificationRequest(authorization_header="Bearer abc, Bearer def")

    with pytest.raises(MissingTokenError):
        TokenVerificationRequest(authorization_header="Bearer abc\r\nX-Injected: yes")


def test_resolve_m2m_command_repr_does_not_expose_authorization_header() -> None:
    command = ResolveM2MTenantContextCommand(
        authorization_header="Bearer raw-secret-token",
        payload_tenant_id="tenant_alpha",
    )

    assert "raw-secret-token" not in repr(command)
    assert "authorization_header" not in repr(command)
