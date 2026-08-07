from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from creditos_identity_tenant.adapters.persistence.in_memory_tenant_repository import (
    InMemoryTenantRepository,
)
from creditos_identity_tenant.application.ports.m2m_token_verifier import (
    AuthenticatedClientContext,
    TokenVerificationRequest,
)
from creditos_identity_tenant.application.use_cases.resolve_m2m_tenant_context import (
    ResolveM2MTenantContextCommand,
    ResolveM2MTenantContextUseCase,
)
from creditos_identity_tenant.domain.entities.tenant import Tenant
from creditos_identity_tenant.domain.errors import (
    CrossTenantAccessDeniedError,
    InactiveTenantError,
    InvalidTenantContextError,
)

NOW = datetime(2026, 8, 6, 12, 0, tzinfo=UTC)


class StaticTokenVerifier:
    def __init__(self, context: AuthenticatedClientContext) -> None:
        self.context = context
        self.requests: list[TokenVerificationRequest] = []

    def verify(self, request: TokenVerificationRequest) -> AuthenticatedClientContext:
        self.requests.append(request)
        return self.context


def test_resolve_m2m_tenant_context_uses_authenticated_tenant_and_catalog_tier() -> None:
    repository = InMemoryTenantRepository()
    repository.save_unique(
        Tenant.create(
            tenant_id="tenant_alpha",
            name="Financeira Alpha",
            status="active",
            tenant_isolation_tier="bridge",
            operator_id="operator-platform",
        )
    )
    verifier = StaticTokenVerifier(
        _authenticated_context(tenant_id="tenant_alpha", tenant_isolation_tier="silo")
    )
    use_case = ResolveM2MTenantContextUseCase(repository=repository, token_verifier=verifier)

    resolved = use_case.execute(
        ResolveM2MTenantContextCommand(
            authorization_header="Bearer valid-token",
            payload_tenant_id="tenant_alpha",
        )
    )

    assert verifier.requests[0].bearer_token == "valid-token"
    assert resolved.tenant_id == "tenant_alpha"
    assert resolved.tenant_isolation_tier == "bridge"
    assert resolved.client_id == "client-alpha"
    assert resolved.scopes == frozenset({"proposal:submit"})
    assert resolved.to_metadata()["tenant_isolation_tier"] == "bridge"


def test_resolve_m2m_tenant_context_rejects_payload_tenant_spoofing() -> None:
    repository = InMemoryTenantRepository()
    repository.save_unique(
        Tenant.create(
            tenant_id="tenant_alpha",
            name="Financeira Alpha",
            status="active",
            operator_id="operator-platform",
        )
    )
    use_case = ResolveM2MTenantContextUseCase(
        repository=repository,
        token_verifier=StaticTokenVerifier(_authenticated_context(tenant_id="tenant_alpha")),
    )

    with pytest.raises(CrossTenantAccessDeniedError):
        use_case.execute(
            ResolveM2MTenantContextCommand(
                authorization_header="Bearer valid-token",
                payload_tenant_id="tenant_beta",
            )
        )


def test_resolve_m2m_tenant_context_rejects_missing_or_suspended_tenant() -> None:
    repository = InMemoryTenantRepository()
    repository.save_unique(
        Tenant.create(
            tenant_id="tenant_suspended",
            name="Financeira Suspensa",
            status="suspended",
            operator_id="operator-platform",
        )
    )

    missing_use_case = ResolveM2MTenantContextUseCase(
        repository=repository,
        token_verifier=StaticTokenVerifier(_authenticated_context(tenant_id="tenant_missing")),
    )
    suspended_use_case = ResolveM2MTenantContextUseCase(
        repository=repository,
        token_verifier=StaticTokenVerifier(_authenticated_context(tenant_id="tenant_suspended")),
    )

    with pytest.raises(InvalidTenantContextError):
        missing_use_case.execute(ResolveM2MTenantContextCommand("Bearer missing-token"))

    with pytest.raises(InactiveTenantError):
        suspended_use_case.execute(ResolveM2MTenantContextCommand("Bearer suspended-token"))


def _authenticated_context(
    *,
    tenant_id: str,
    tenant_isolation_tier: str = "bridge",
) -> AuthenticatedClientContext:
    return AuthenticatedClientContext(
        client_id="client-alpha",
        subject="client-alpha",
        scopes=("proposal:submit",),
        tenant_id=tenant_id,
        tenant_isolation_tier=tenant_isolation_tier,
        issuer="https://issuer.creditos.local",
        audience="creditos-api",
        token_id="jti-valid",
        issued_at=NOW - timedelta(minutes=1),
        expires_at=NOW + timedelta(minutes=5),
    )
