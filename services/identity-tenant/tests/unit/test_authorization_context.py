from __future__ import annotations

from typing import cast

import pytest
from creditos_identity_tenant.application.security import (
    AuthorizationOperationDefinition,
    AuthorizationOperationRegistry,
    AuthorizationPolicy,
    AuthorizationRequirement,
    AuthorizationSubject,
    ProtectedResource,
)
from creditos_identity_tenant.domain.errors import (
    AuthorizationError,
    CrossTenantAccessDeniedError,
    InsufficientRoleError,
    InsufficientScopeError,
    InvalidAuthorizationContextError,
    InvalidAuthorizationRequirementError,
)


def test_authorization_subject_normalizes_roles_scopes_and_required_claims() -> None:
    subject = AuthorizationSubject(
        subject_id=" client-alpha ",
        tenant_id=" tenant_alpha ",
        tenant_isolation_tier=" bridge ",
        scopes=("proposal:submit", "decision:read", "proposal:submit"),
        roles=(" tenant-admin ", "service-client", "tenant-admin"),
        client_id=" client-alpha ",
        token_id=" jti-alpha ",
    )

    assert subject.subject_id == "client-alpha"
    assert subject.tenant_id == "tenant_alpha"
    assert subject.tenant_isolation_tier == "bridge"
    assert subject.scopes == frozenset({"proposal:submit", "decision:read"})
    assert subject.roles == frozenset({"tenant-admin", "service-client"})
    assert subject.client_id == "client-alpha"
    assert subject.token_id == "jti-alpha"
    assert subject.to_log_metadata() == {
        "subject_id": "client-alpha",
        "client_id": "client-alpha",
        "tenant_id": "tenant_alpha",
        "tenant_isolation_tier": "bridge",
        "roles": ["service-client", "tenant-admin"],
        "scopes": ["decision:read", "proposal:submit"],
        "principal_type": "m2m",
    }


def test_authorization_subject_is_derived_from_resolved_trusted_context() -> None:
    subject = AuthorizationSubject.from_resolved_tenant_context(
        subject_id="client-alpha",
        tenant_id="tenant_alpha",
        tenant_isolation_tier="bridge",
        scopes=("proposal:submit",),
        trusted_roles=("service-client",),
        client_id="client-alpha",
        token_id="jti-alpha",
    )

    assert subject.subject_id == "client-alpha"
    assert subject.client_id == "client-alpha"
    assert subject.scopes == frozenset({"proposal:submit"})
    assert subject.roles == frozenset({"service-client"})
    assert subject.tenant_id == "tenant_alpha"


def test_authorization_subject_rejects_missing_or_malformed_context() -> None:
    cases = (
        {"subject_id": "", "tenant_id": "tenant_alpha", "scopes": ("proposal:submit",)},
        {"subject_id": "client-alpha", "tenant_id": "", "scopes": ("proposal:submit",)},
        {"subject_id": "client-alpha", "tenant_id": "tenant_alpha", "scopes": ()},
        {
            "subject_id": "client-alpha",
            "tenant_id": "tenant_alpha",
            "scopes": cast(tuple[str, ...], {"scope": "proposal:submit"}),
        },
        {
            "subject_id": "client-alpha",
            "tenant_id": "tenant_alpha",
            "scopes": cast(tuple[str, ...], b"proposal:submit"),
        },
        {
            "subject_id": "client-alpha",
            "tenant_id": "tenant_alpha",
            "scopes": cast(tuple[str, ...], "proposal:submit decision:read"),
        },
        {
            "subject_id": "client-alpha",
            "tenant_id": "tenant_alpha",
            "scopes": cast(tuple[str, ...], ("proposal:submit", 1)),
        },
        {
            "subject_id": "client-alpha",
            "tenant_id": "tenant_alpha",
            "scopes": ("proposal:submit",),
            "roles": cast(tuple[str, ...], ("service-client admin",)),
        },
        {
            "subject_id": "client-alpha",
            "tenant_id": "tenant_alpha",
            "scopes": ("proposal:submit",),
            "principal_type": "anonymous",
        },
        {
            "subject_id": "client-alpha",
            "tenant_id": "tenant_alpha",
            "scopes": ("proposal:submit",),
            "tenant_isolation_tier": "pooled",
        },
        {
            "subject_id": "x" * 129,
            "tenant_id": "tenant_alpha",
            "scopes": ("proposal:submit",),
        },
    )

    for kwargs in cases:
        with pytest.raises(InvalidAuthorizationContextError):
            AuthorizationSubject(
                tenant_isolation_tier=kwargs.pop("tenant_isolation_tier", "bridge"),
                **kwargs,
            )


def test_protected_resource_and_requirement_are_explicit_and_normalized() -> None:
    resource = ProtectedResource(
        resource_type=" proposal ",
        resource_id=" proposal-123 ",
        tenant_id=" tenant_alpha ",
    )
    requirement = AuthorizationRequirement.from_registry(
        operation=" proposal.submit ",
        required_scopes=("proposal:submit", "proposal:submit"),
        required_roles=(" service-client ",),
    )

    assert resource.resource_type == "proposal"
    assert resource.resource_id == "proposal-123"
    assert resource.tenant_id == "tenant_alpha"
    assert requirement.operation == "proposal.submit"
    assert requirement.required_scopes == frozenset({"proposal:submit"})
    assert requirement.required_roles == frozenset({"service-client"})


def test_authorization_requirement_is_deny_by_default_when_empty() -> None:
    with pytest.raises(InvalidAuthorizationRequirementError):
        AuthorizationRequirement(operation="proposal.submit", required_scopes=())

    with pytest.raises(InvalidAuthorizationRequirementError):
        AuthorizationRequirement.from_registry(operation="", required_scopes=("proposal:submit",))

    with pytest.raises(InvalidAuthorizationRequirementError):
        AuthorizationRequirement.from_registry(
            operation="proposal.submit",
            required_scopes=("proposal:submit",),
        )


def test_authorization_registry_allows_explicit_scope_only_operations() -> None:
    registry = AuthorizationOperationRegistry(
        (
            AuthorizationOperationDefinition(
                operation="decision.read",
                required_scopes=("decision:read",),
                allow_scope_only=True,
            ),
        )
    )

    requirement = registry.requirement_for("decision.read")

    assert requirement.required_scopes == frozenset({"decision:read"})
    assert requirement.required_roles == frozenset()
    assert requirement.allow_scope_only is True


def test_authorization_registry_rejects_unknown_or_malformed_operations() -> None:
    registry = AuthorizationOperationRegistry(
        (
            AuthorizationOperationDefinition(
                operation="proposal.submit",
                required_scopes=("proposal:submit",),
                required_roles=("service-client",),
            ),
        )
    )

    with pytest.raises(InvalidAuthorizationRequirementError):
        registry.requirement_for("proposal.delete")

    with pytest.raises(InvalidAuthorizationRequirementError):
        registry.requirement_for("proposal.submit now")


def test_authorization_policy_allows_matching_scope_role_and_tenant() -> None:
    decision = AuthorizationPolicy().authorize(
        subject=_subject(scopes=("proposal:submit", "decision:read"), roles=("service-client",)),
        requirement=AuthorizationRequirement.from_registry(
            operation="proposal.submit",
            required_scopes=("proposal:submit",),
            required_roles=("service-client",),
        ),
        resource=ProtectedResource(
            resource_type="proposal",
            resource_id="proposal-123",
            tenant_id="tenant_alpha",
        ),
    )

    assert decision.granted is True
    assert decision.operation == "proposal.submit"
    assert decision.subject_id == "client-alpha"
    assert decision.tenant_id == "tenant_alpha"
    assert decision.matched_scopes == frozenset({"proposal:submit"})
    assert decision.matched_roles == frozenset({"service-client"})
    assert decision.to_metadata()["resource_id"] == "proposal-123"
    assert decision.to_metadata()["allow_scope_only"] is False


def test_authorization_policy_rejects_missing_required_scope() -> None:
    with pytest.raises(InsufficientScopeError) as error:
        AuthorizationPolicy().authorize(
            subject=_subject(scopes=("decision:read",), roles=("service-client",)),
            requirement=AuthorizationRequirement.from_registry(
                operation="proposal.submit",
                required_scopes=("proposal:submit",),
                required_roles=("service-client",),
            ),
            resource=ProtectedResource(
                resource_type="proposal",
                resource_id="proposal-123",
                tenant_id="tenant_alpha",
            ),
        )

    assert error.value.code == "insufficient_scope"
    assert error.value.safe_message == "autorização negada"
    assert error.value.grpc_status == "PERMISSION_DENIED"


def test_authorization_policy_rejects_missing_required_role() -> None:
    with pytest.raises(InsufficientRoleError) as error:
        AuthorizationPolicy().authorize(
            subject=_subject(scopes=("proposal:submit",), roles=("viewer",)),
            requirement=AuthorizationRequirement.from_registry(
                operation="proposal.submit",
                required_scopes=("proposal:submit",),
                required_roles=("service-client",),
            ),
            resource=ProtectedResource(
                resource_type="proposal",
                resource_id="proposal-123",
                tenant_id="tenant_alpha",
            ),
        )

    assert error.value.code == "insufficient_role"
    assert error.value.safe_message == "autorização negada"


def test_authorization_policy_rejects_cross_tenant_resource_access() -> None:
    with pytest.raises(CrossTenantAccessDeniedError) as error:
        AuthorizationPolicy().authorize(
            subject=_subject(scopes=("proposal:submit",), roles=("service-client",)),
            requirement=AuthorizationRequirement.from_registry(
                operation="proposal.submit",
                required_scopes=("proposal:submit",),
                required_roles=("service-client",),
            ),
            resource=ProtectedResource(
                resource_type="proposal",
                resource_id="proposal-123",
                tenant_id="tenant_beta",
            ),
        )

    assert isinstance(error.value, AuthorizationError)


def _subject(
    *,
    scopes: tuple[str, ...],
    roles: tuple[str, ...] = (),
) -> AuthorizationSubject:
    return AuthorizationSubject(
        subject_id="client-alpha",
        tenant_id="tenant_alpha",
        tenant_isolation_tier="bridge",
        scopes=scopes,
        roles=roles,
        client_id="client-alpha",
        token_id="jti-alpha",
    )
