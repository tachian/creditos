from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from creditos_identity_tenant.application.ports.m2m_token_verifier import (
    M2MTokenVerifier,
    TokenVerificationRequest,
)
from creditos_identity_tenant.application.ports.tenant_repository import TenantRepository
from creditos_identity_tenant.application.security import OperatorContext
from creditos_identity_tenant.application.use_cases.get_tenant import (
    GetTenantQuery,
    GetTenantUseCase,
)
from creditos_identity_tenant.domain.errors import (
    CrossTenantAccessDeniedError,
    InactiveTenantError,
    InvalidTenantContextError,
    TenantNotFoundError,
)

_ACTIVE_TENANT_STATUS = "active"


@dataclass(frozen=True, slots=True)
class ResolveM2MTenantContextCommand:
    authorization_header: str | None = field(repr=False)
    payload_tenant_id: str | None = None
    now: datetime | None = None


@dataclass(frozen=True, slots=True)
class ResolvedM2MTenantContext:
    tenant_id: str
    tenant_isolation_tier: str
    client_id: str
    subject: str
    scopes: frozenset[str]
    issuer: str
    audience: str
    token_id: str

    def to_metadata(self) -> dict[str, str]:
        return {
            "tenant_id": self.tenant_id,
            "tenant_isolation_tier": self.tenant_isolation_tier,
            "client_id": self.client_id,
            "subject": self.subject,
            "issuer": self.issuer,
            "audience": self.audience,
            "token_id": self.token_id,
            "scopes": " ".join(sorted(self.scopes)),
        }


class ResolveM2MTenantContextUseCase:
    def __init__(
        self,
        *,
        repository: TenantRepository,
        token_verifier: M2MTokenVerifier,
    ) -> None:
        self._get_tenant = GetTenantUseCase(repository=repository)
        self._token_verifier = token_verifier

    def execute(self, command: ResolveM2MTenantContextCommand) -> ResolvedM2MTenantContext:
        verification_request = (
            TokenVerificationRequest(authorization_header=command.authorization_header)
            if command.now is None
            else TokenVerificationRequest(
                authorization_header=command.authorization_header,
                now=command.now,
            )
        )
        authenticated_context = self._token_verifier.verify(verification_request)
        payload_tenant_id = _normalize_optional_payload_tenant_id(command.payload_tenant_id)
        if payload_tenant_id is not None and payload_tenant_id != authenticated_context.tenant_id:
            raise CrossTenantAccessDeniedError("payload não é fonte confiável de tenant")

        try:
            tenant_metadata = self._get_tenant.execute(
                GetTenantQuery(
                    tenant_id=authenticated_context.tenant_id,
                    trusted_context_tenant_id=authenticated_context.tenant_id,
                ),
                operator=OperatorContext.tenant_scoped(authenticated_context.client_id),
            )
        except TenantNotFoundError as error:
            raise InvalidTenantContextError("contexto de tenant inválido") from error
        if tenant_metadata["status"] != _ACTIVE_TENANT_STATUS:
            raise InactiveTenantError("tenant não está ativo")

        return ResolvedM2MTenantContext(
            tenant_id=tenant_metadata["tenant_id"],
            tenant_isolation_tier=tenant_metadata["tenant_isolation_tier"],
            client_id=authenticated_context.client_id,
            subject=authenticated_context.subject,
            scopes=frozenset(authenticated_context.scopes),
            issuer=authenticated_context.issuer,
            audience=authenticated_context.audience,
            token_id=authenticated_context.token_id,
        )


def _normalize_optional_payload_tenant_id(value: str | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise InvalidTenantContextError("tenant_id do payload inválido")

    normalized_value = value.strip()
    if not normalized_value:
        raise InvalidTenantContextError("tenant_id do payload inválido")
    return normalized_value
