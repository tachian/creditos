from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from creditos_identity_tenant.application.ports.m2m_token_verifier import (
    AuthenticatedClientContext,
    M2MTokenVerifier,
    TokenVerificationRequest,
    normalize_token_scopes,
)
from creditos_identity_tenant.domain.errors import (
    ExpiredTokenError,
    InvalidTokenAudienceError,
    InvalidTokenError,
    InvalidTokenIssuerError,
    MissingTokenRequiredClaimError,
)


@dataclass(frozen=True, slots=True)
class LocalM2MTokenClaims:
    issuer: str
    audience: str
    subject: str
    client_id: str
    tenant_id: str
    tenant_isolation_tier: str
    scopes: Iterable[str]
    token_id: str
    issued_at: datetime
    expires_at: datetime
    not_before: datetime | None = None
    key_id: str = "local-key"
    algorithm: str = "RS256"
    signature_valid: bool = True


class LocalM2MTokenVerifier(M2MTokenVerifier):
    def __init__(
        self,
        *,
        issuer: str,
        audience: str,
        tokens: Mapping[str, LocalM2MTokenClaims],
        trusted_key_ids: Iterable[str],
        allowed_algorithms: Iterable[str] = ("RS256",),
        required_scopes: Iterable[str] = (),
        clock_skew_seconds: int = 0,
    ) -> None:
        if clock_skew_seconds < 0:
            raise ValueError("clock_skew_seconds deve ser maior ou igual a zero")

        self._issuer = issuer
        self._audience = audience
        self._tokens = dict(tokens)
        self._trusted_key_ids = frozenset(trusted_key_ids)
        self._allowed_algorithms = frozenset(allowed_algorithms)
        self._required_scopes = (
            normalize_token_scopes(required_scopes) if required_scopes else frozenset()
        )
        self._clock_skew = timedelta(seconds=clock_skew_seconds)

    def verify(self, request: TokenVerificationRequest) -> AuthenticatedClientContext:
        claims = self._tokens.get(request.bearer_token)
        if claims is None:
            raise InvalidTokenError("token inválido")

        self._validate_header(claims)
        self._validate_issuer(claims)
        self._validate_audience(claims)
        self._validate_temporal_claims(claims, request.now)

        context = AuthenticatedClientContext(
            client_id=claims.client_id,
            subject=claims.subject,
            scopes=claims.scopes,
            tenant_id=claims.tenant_id,
            tenant_isolation_tier=claims.tenant_isolation_tier,
            issuer=claims.issuer,
            audience=claims.audience,
            token_id=claims.token_id,
            issued_at=claims.issued_at,
            expires_at=claims.expires_at,
        )
        if context.subject != context.client_id:
            raise InvalidTokenError("sujeito M2M incompatível com cliente técnico")
        if not self._required_scopes.issubset(context.scopes):
            raise InvalidTokenError("token sem scopes mínimos")
        return context

    def _validate_header(self, claims: LocalM2MTokenClaims) -> None:
        if not isinstance(claims.algorithm, str) or not isinstance(claims.key_id, str):
            raise InvalidTokenError("header de token inválido")
        if not isinstance(claims.signature_valid, bool) or not claims.signature_valid:
            raise InvalidTokenError("assinatura de token inválida")

        is_disallowed_algorithm = (
            claims.algorithm.casefold() == "none"
            or claims.algorithm not in self._allowed_algorithms
        )
        if is_disallowed_algorithm:
            raise InvalidTokenError("algoritmo de token inválido")
        if claims.key_id not in self._trusted_key_ids:
            raise InvalidTokenError("chave de token inválida")

    def _validate_issuer(self, claims: LocalM2MTokenClaims) -> None:
        if claims.issuer != self._issuer:
            raise InvalidTokenIssuerError("issuer inválido")

    def _validate_audience(self, claims: LocalM2MTokenClaims) -> None:
        if claims.audience != self._audience:
            raise InvalidTokenAudienceError("audience inválida")

    def _validate_temporal_claims(self, claims: LocalM2MTokenClaims, now: datetime) -> None:
        normalized_now = _as_utc_claim(now, "now")
        issued_at = _as_utc_claim(claims.issued_at, "iat")
        expires_at = _as_utc_claim(claims.expires_at, "exp")
        not_before = (
            _as_utc_claim(claims.not_before, "nbf") if claims.not_before is not None else None
        )

        if expires_at <= normalized_now - self._clock_skew:
            raise ExpiredTokenError("token expirado")
        if expires_at < issued_at:
            raise InvalidTokenError("janela temporal de token inválida")
        if not_before is not None and not_before > expires_at:
            raise InvalidTokenError("janela temporal de token inválida")
        if issued_at > normalized_now + self._clock_skew:
            raise InvalidTokenError("token emitido no futuro")
        if not_before is not None and not_before > normalized_now + self._clock_skew:
            raise InvalidTokenError("token ainda não válido")


def _as_utc_claim(value: datetime, claim_name: str) -> datetime:
    if not isinstance(value, datetime):
        raise MissingTokenRequiredClaimError(f"claim temporal obrigatória ausente: {claim_name}")
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
