from __future__ import annotations

from collections.abc import Iterable

from creditos_observability.context import ObservabilityContext
from creditos_security.context import (
    InvalidTrustedContextError,
    PropagatedContext,
    TrustedContext,
)

from creditos_identity_tenant.application.security import AuthorizationSubject
from creditos_identity_tenant.application.use_cases.resolve_m2m_tenant_context import (
    ResolvedM2MTenantContext,
)


def propagated_context_from_authorization_subject(
    subject: AuthorizationSubject,
    context: ObservabilityContext,
    *,
    schema_version: str = "v1",
) -> PropagatedContext:
    return PropagatedContext(
        trusted=TrustedContext(
            tenant_id=subject.tenant_id,
            tenant_isolation_tier=subject.tenant_isolation_tier,
            subject_id=subject.subject_id,
            scopes=subject.scopes,
            roles=subject.roles,
            client_id=subject.client_id,
            principal_type=subject.principal_type,
        ),
        correlation_id=context.correlation_id,
        request_id=context.request_id,
        traceparent=context.to_carrier()["traceparent"],
        schema_version=schema_version,
    )


def propagated_context_from_resolved_m2m_context(
    resolved_context: ResolvedM2MTenantContext,
    context: ObservabilityContext,
    *,
    trusted_roles: Iterable[str] = (),
    schema_version: str = "v1",
) -> PropagatedContext:
    return PropagatedContext(
        trusted=TrustedContext(
            tenant_id=resolved_context.tenant_id,
            tenant_isolation_tier=resolved_context.tenant_isolation_tier,
            subject_id=resolved_context.subject,
            scopes=resolved_context.scopes,
            roles=trusted_roles,
            client_id=resolved_context.client_id,
            principal_type="m2m",
        ),
        correlation_id=context.correlation_id,
        request_id=context.request_id,
        traceparent=context.to_carrier()["traceparent"],
        schema_version=schema_version,
    )


def ensure_expected_tenant(
    context: PropagatedContext,
    expected_tenant_id: str | None,
) -> None:
    if expected_tenant_id is None:
        return
    expected = expected_tenant_id.strip() if isinstance(expected_tenant_id, str) else ""
    if not expected or context.trusted.tenant_id != expected:
        raise InvalidTrustedContextError("tenant incompatível com contexto confiável")
