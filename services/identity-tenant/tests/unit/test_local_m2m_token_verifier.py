from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import cast

import pytest
from creditos_identity_tenant.adapters.external.local_m2m_token_verifier import (
    LocalM2MTokenClaims,
    LocalM2MTokenVerifier,
)
from creditos_identity_tenant.application.ports.m2m_token_verifier import (
    TokenVerificationRequest,
)
from creditos_identity_tenant.domain.errors import (
    ExpiredTokenError,
    InvalidTokenAudienceError,
    InvalidTokenError,
    InvalidTokenIssuerError,
    MissingTokenRequiredClaimError,
)

NOW = datetime(2026, 8, 6, 12, 0, tzinfo=UTC)


def test_local_m2m_token_verifier_accepts_configured_token() -> None:
    verifier = LocalM2MTokenVerifier(
        issuer="https://issuer.creditos.local",
        audience="creditos-api",
        trusted_key_ids={"kid-local"},
        tokens={
            "valid-token": _claims(
                token_id="jti-valid",
                client_id="client-alpha",
                tenant_id="tenant_alpha",
            )
        },
    )

    context = verifier.verify(
        TokenVerificationRequest(authorization_header="Bearer valid-token", now=NOW)
    )

    assert context.client_id == "client-alpha"
    assert context.subject == "client-alpha"
    assert context.scopes == frozenset({"proposal:submit", "decision:read"})
    assert context.tenant_id == "tenant_alpha"
    assert context.tenant_isolation_tier == "bridge"
    assert context.token_id == "jti-valid"


def test_local_m2m_token_verifier_rejects_invalid_tokens() -> None:
    cases: tuple[tuple[LocalM2MTokenClaims, type[Exception]], ...] = (
        (
            _claims(token_id="jti-expired", expires_at=NOW - timedelta(seconds=1)),
            ExpiredTokenError,
        ),
        (
            _claims(token_id="jti-issuer", issuer="https://evil.example"),
            InvalidTokenIssuerError,
        ),
        (
            _claims(token_id="jti-audience", audience="other-api"),
            InvalidTokenAudienceError,
        ),
        (
            _claims(token_id="jti-kid", key_id="unknown-kid"),
            InvalidTokenError,
        ),
        (
            _claims(token_id="jti-none", algorithm="none"),
            InvalidTokenError,
        ),
        (
            _claims(token_id="jti-signature", signature_valid=False),
            InvalidTokenError,
        ),
        (
            _claims(token_id="jti-tenant", tenant_id=""),
            MissingTokenRequiredClaimError,
        ),
        (
            _claims(token_id="jti-subject", subject="human-user"),
            InvalidTokenError,
        ),
        (
            _claims(token_id="jti-nbf", not_before=NOW + timedelta(seconds=1)),
            InvalidTokenError,
        ),
        (
            _claims(token_id="jti-iat-future", issued_at=NOW + timedelta(seconds=1)),
            InvalidTokenError,
        ),
        (
            _claims(
                token_id="jti-exp-before-iat",
                issued_at=NOW + timedelta(minutes=5),
                expires_at=NOW + timedelta(minutes=4),
            ),
            InvalidTokenError,
        ),
        (
            _claims(
                token_id="jti-nbf-after-exp",
                not_before=NOW + timedelta(minutes=6),
                expires_at=NOW + timedelta(minutes=5),
            ),
            InvalidTokenError,
        ),
    )

    for claims, expected_error in cases:
        verifier = LocalM2MTokenVerifier(
            issuer="https://issuer.creditos.local",
            audience="creditos-api",
            trusted_key_ids={"kid-local"},
            tokens={"invalid-token": claims},
        )

        with pytest.raises(expected_error):
            verifier.verify(
                TokenVerificationRequest(authorization_header="Bearer invalid-token", now=NOW)
            )


def test_local_m2m_token_verifier_rejects_unknown_token_without_leaking_value() -> None:
    verifier = LocalM2MTokenVerifier(
        issuer="https://issuer.creditos.local",
        audience="creditos-api",
        trusted_key_ids={"kid-local"},
        tokens={},
    )

    with pytest.raises(InvalidTokenError) as error:
        verifier.verify(
            TokenVerificationRequest(authorization_header="Bearer raw-secret-token", now=NOW)
        )

    assert "raw-secret-token" not in str(error.value)


def test_local_m2m_token_verifier_rejects_malformed_claim_types_safely() -> None:
    cases: tuple[LocalM2MTokenClaims, ...] = (
        _claims(token_id="bad-algorithm", algorithm=cast(str, None)),
        _claims(token_id="bad-key", key_id=cast(str, [])),
        _claims(token_id="bad-issued-at", issued_at=cast(datetime, None)),
        _claims(token_id="bad-expires-at", expires_at=cast(datetime, "tomorrow")),
        _claims(token_id="bad-not-before", not_before=cast(datetime, "soon")),
        _claims(token_id="bad-scopes-mapping", scopes=cast(tuple[str, ...], {"scope": "x"})),
        _claims(token_id="bad-scopes-bytes", scopes=cast(tuple[str, ...], b"proposal:submit")),
        _claims(token_id="bad-scopes-item", scopes=cast(tuple[str, ...], ("proposal:submit", 1))),
        _claims(
            token_id="bad-scopes-nested",
            scopes=cast(tuple[str, ...], ("proposal:submit", ("decision:read",))),
        ),
    )

    for claims in cases:
        verifier = LocalM2MTokenVerifier(
            issuer="https://issuer.creditos.local",
            audience="creditos-api",
            trusted_key_ids={"kid-local"},
            tokens={"malformed-token": claims},
        )

        with pytest.raises((InvalidTokenError, MissingTokenRequiredClaimError)):
            verifier.verify(
                TokenVerificationRequest(authorization_header="Bearer malformed-token", now=NOW)
            )


def test_local_m2m_token_verifier_normalizes_required_scopes_string() -> None:
    verifier = LocalM2MTokenVerifier(
        issuer="https://issuer.creditos.local",
        audience="creditos-api",
        trusted_key_ids={"kid-local"},
        required_scopes="proposal:submit decision:read",
        tokens={"valid-token": _claims(token_id="jti-valid")},
    )

    context = verifier.verify(
        TokenVerificationRequest(authorization_header="Bearer valid-token", now=NOW)
    )

    assert context.scopes == frozenset({"proposal:submit", "decision:read"})


def test_local_m2m_token_verifier_rejects_invalid_configuration() -> None:
    with pytest.raises(ValueError, match="clock_skew_seconds"):
        LocalM2MTokenVerifier(
            issuer="https://issuer.creditos.local",
            audience="creditos-api",
            trusted_key_ids={"kid-local"},
            tokens={},
            clock_skew_seconds=-1,
        )


def _claims(
    *,
    token_id: str,
    client_id: str = "client-alpha",
    subject: str | None = None,
    tenant_id: str = "tenant_alpha",
    tenant_isolation_tier: str = "bridge",
    issuer: str = "https://issuer.creditos.local",
    audience: str = "creditos-api",
    scopes: tuple[str, ...] = ("proposal:submit", "decision:read"),
    issued_at: datetime = NOW - timedelta(minutes=1),
    expires_at: datetime = NOW + timedelta(minutes=5),
    not_before: datetime | None = None,
    key_id: str = "kid-local",
    algorithm: str = "RS256",
    signature_valid: bool = True,
) -> LocalM2MTokenClaims:
    return LocalM2MTokenClaims(
        issuer=issuer,
        audience=audience,
        subject=subject or client_id,
        client_id=client_id,
        tenant_id=tenant_id,
        tenant_isolation_tier=tenant_isolation_tier,
        scopes=scopes,
        token_id=token_id,
        issued_at=issued_at,
        expires_at=expires_at,
        not_before=not_before,
        key_id=key_id,
        algorithm=algorithm,
        signature_valid=signature_valid,
    )
