from __future__ import annotations

from dataclasses import dataclass

from creditos_identity_tenant.application.security import (
    DEFAULT_AUTHORIZATION_OPERATION_REGISTRY,
    AuthorizationDecision,
    AuthorizationOperationRegistry,
    AuthorizationPolicy,
    AuthorizationRequirement,
    AuthorizationSubject,
    ProtectedResource,
)
from creditos_identity_tenant.domain.errors import InvalidAuthorizationContextError


@dataclass(frozen=True, slots=True)
class AuthorizeOperationCommand:
    subject: AuthorizationSubject
    operation: str
    resource: ProtectedResource


class AuthorizeOperationUseCase:
    def __init__(
        self,
        *,
        policy: AuthorizationPolicy | None = None,
        registry: AuthorizationOperationRegistry = DEFAULT_AUTHORIZATION_OPERATION_REGISTRY,
    ) -> None:
        self._policy = policy or AuthorizationPolicy()
        self._registry = registry

    def execute(self, command: AuthorizeOperationCommand) -> AuthorizationDecision:
        if not isinstance(command, AuthorizeOperationCommand):
            raise InvalidAuthorizationContextError("comando de autorização inválido")
        requirement = self.requirement_for_operation(command.operation)
        return self._policy.authorize(
            subject=command.subject,
            requirement=requirement,
            resource=command.resource,
        )

    def requirement_for_operation(self, operation: str) -> AuthorizationRequirement:
        return self._registry.requirement_for(operation)


class AuthorizedOperationFacade:
    def __init__(self, *, use_case: AuthorizeOperationUseCase | None = None) -> None:
        self._use_case = use_case or AuthorizeOperationUseCase()

    def authorize(self, command: AuthorizeOperationCommand) -> AuthorizationDecision:
        return self._use_case.execute(command)

    def requirement_for_operation(self, operation: str) -> AuthorizationRequirement:
        return self._use_case.requirement_for_operation(operation)
