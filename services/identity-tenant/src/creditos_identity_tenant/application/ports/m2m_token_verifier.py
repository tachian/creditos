from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol

from creditos_identity_tenant.domain.errors import (
    MissingTokenError,
    MissingTokenRequiredClaimError,
)

_BEARER_AUTHORIZATION_PATTERN = re.compile(r"(?i)^bearer ([A-Za-z0-9._~+/-]+=*)$")
_SCOPE_TOKEN_PATTERN = re.compile(r"^[\x21\x23-\x5B\x5D-\x7E]+$")


@dataclass(frozen=True, slots=True)
class TokenVerificationRequest:
    authorization_header: str | None = field(repr=False)
    now: datetime = field(default_factory=lambda: datetime.now(UTC))
    bearer_token: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "now", _normalize_datetime(self.now))
        object.__setattr__(self, "bearer_token", _extract_bearer_token(self.authorization_header))


@dataclass(frozen=True, slots=True)
class AuthenticatedClientContext:
    client_id: str
    subject: str
    scopes: Iterable[str]
    tenant_id: str
    tenant_isolation_tier: str
    issuer: str
    audience: str
    token_id: str
    issued_at: datetime
    expires_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "client_id", _required_text(self.client_id, "client_id"))
        object.__setattr__(self, "subject", _required_text(self.subject, "subject"))
        object.__setattr__(self, "tenant_id", _required_text(self.tenant_id, "tenant_id"))
        object.__setattr__(
            self,
            "tenant_isolation_tier",
            _required_text(self.tenant_isolation_tier, "tenant_isolation_tier"),
        )
        object.__setattr__(self, "issuer", _required_text(self.issuer, "issuer"))
        object.__setattr__(self, "audience", _required_text(self.audience, "audience"))
        object.__setattr__(self, "token_id", _required_text(self.token_id, "jti"))
        object.__setattr__(self, "scopes", normalize_token_scopes(self.scopes))
        object.__setattr__(self, "issued_at", _normalize_datetime(self.issued_at))
        object.__setattr__(self, "expires_at", _normalize_datetime(self.expires_at))

    def to_metadata(self) -> dict[str, str]:
        return {
            "client_id": self.client_id,
            "subject": self.subject,
            "tenant_id": self.tenant_id,
            "tenant_isolation_tier": self.tenant_isolation_tier,
            "issuer": self.issuer,
            "audience": self.audience,
            "token_id": self.token_id,
            "scopes": " ".join(sorted(self.scopes)),
        }


class M2MTokenVerifier(Protocol):
    def verify(self, request: TokenVerificationRequest) -> AuthenticatedClientContext: ...


def _extract_bearer_token(authorization_header: str | None) -> str:
    if not isinstance(authorization_header, str):
        raise MissingTokenError("token obrigatório")

    match = _BEARER_AUTHORIZATION_PATTERN.fullmatch(authorization_header.strip())
    if match is None:
        raise MissingTokenError("token bearer obrigatório")
    return match.group(1)


def _required_text(value: str, claim_name: str) -> str:
    if not isinstance(value, str):
        raise MissingTokenRequiredClaimError(f"claim obrigatória ausente: {claim_name}")

    normalized_value = value.strip()
    if not normalized_value:
        raise MissingTokenRequiredClaimError(f"claim obrigatória ausente: {claim_name}")
    return normalized_value


def normalize_token_scopes(scopes: Iterable[str]) -> frozenset[str]:
    if isinstance(scopes, str):
        scope_values: Iterable[Any] = scopes.split()
    elif isinstance(scopes, Mapping | bytes | bytearray | memoryview) or not isinstance(
        scopes, Iterable
    ):
        raise MissingTokenRequiredClaimError("claim obrigatória ausente: scope")
    else:
        scope_values = scopes

    normalized_scopes: set[str] = set()
    for scope in scope_values:
        if not isinstance(scope, str):
            raise MissingTokenRequiredClaimError("claim obrigatória ausente: scope")

        normalized_scope = scope.strip()
        if (
            not normalized_scope
            or len(normalized_scope.split()) != 1
            or _SCOPE_TOKEN_PATTERN.fullmatch(normalized_scope) is None
        ):
            raise MissingTokenRequiredClaimError("claim obrigatória ausente: scope")
        normalized_scopes.add(normalized_scope)

    if not normalized_scopes:
        raise MissingTokenRequiredClaimError("claim obrigatória ausente: scope")
    return frozenset(normalized_scopes)


def _normalize_datetime(value: datetime) -> datetime:
    if not isinstance(value, datetime):
        raise MissingTokenRequiredClaimError("claim temporal obrigatória ausente")
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
