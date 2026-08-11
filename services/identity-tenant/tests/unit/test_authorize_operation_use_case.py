from __future__ import annotations

from typing import cast

import pytest
from creditos_identity_tenant.application.security import (
    AuthorizationSubject,
    ProtectedResource,
)
from creditos_identity_tenant.application.use_cases.authorize_operation import (
    AuthorizedOperationFacade,
    AuthorizeOperationCommand,
    AuthorizeOperationUseCase,
)
from creditos_identity_tenant.domain.errors import (
    InsufficientScopeError,
    InvalidAuthorizationContextError,
    InvalidAuthorizationRequirementError,
)


def test_authorize_operation_use_case_uses_registered_operation_requirements() -> None:
    decision = AuthorizeOperationUseCase().execute(
        AuthorizeOperationCommand(
            subject=_subject(scopes=("proposal:submit",), roles=("service-client",)),
            operation="proposal.submit",
            resource=ProtectedResource(
                resource_type="proposal",
                resource_id="proposal-123",
                tenant_id="tenant_alpha",
            ),
        )
    )

    assert decision.to_metadata() == {
        "operation": "proposal.submit",
        "subject_id": "client-alpha",
        "tenant_id": "tenant_alpha",
        "resource_type": "proposal",
        "resource_id": "proposal-123",
        "granted": True,
        "matched_scopes": ["proposal:submit"],
        "matched_roles": ["service-client"],
        "allow_scope_only": False,
    }


def test_authorize_operation_use_case_allows_scope_only_only_when_registered() -> None:
    decision = AuthorizedOperationFacade().authorize(
        AuthorizeOperationCommand(
            subject=_subject(scopes=("decision:read",)),
            operation="decision.read",
            resource=ProtectedResource(
                resource_type="decision",
                resource_id="decision-123",
                tenant_id="tenant_alpha",
            ),
        )
    )

    assert decision.matched_scopes == frozenset({"decision:read"})
    assert decision.matched_roles == frozenset()
    assert decision.allow_scope_only is True


def test_authorize_operation_use_case_rejects_unknown_operation() -> None:
    with pytest.raises(InvalidAuthorizationRequirementError):
        AuthorizeOperationUseCase().execute(
            AuthorizeOperationCommand(
                subject=_subject(scopes=("proposal:submit",), roles=("service-client",)),
                operation="proposal.submit.unregistered",
                resource=ProtectedResource(
                    resource_type="proposal",
                    resource_id="proposal-123",
                    tenant_id="tenant_alpha",
                ),
            )
        )


def test_authorize_operation_use_case_propagates_safe_authorization_errors() -> None:
    use_case = AuthorizeOperationUseCase()

    with pytest.raises(InsufficientScopeError) as error:
        use_case.execute(
            AuthorizeOperationCommand(
                subject=_subject(scopes=("decision:read",), roles=("service-client",)),
                operation="proposal.submit",
                resource=ProtectedResource(
                    resource_type="proposal",
                    resource_id="proposal-123",
                    tenant_id="tenant_alpha",
                ),
            )
        )

    assert error.value.code == "insufficient_scope"
    assert error.value.safe_message == "autorização negada"
    assert error.value.grpc_status == "PERMISSION_DENIED"


def test_authorize_operation_use_case_rejects_malformed_command_safely() -> None:
    with pytest.raises(InvalidAuthorizationContextError):
        AuthorizeOperationUseCase().execute(cast(AuthorizeOperationCommand, object()))


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
