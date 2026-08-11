from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

from creditos_identity_tenant.domain.errors import (
    CrossTenantAccessDeniedError,
    InsufficientRoleError,
    InsufficientScopeError,
    InvalidAuthorizationContextError,
    InvalidAuthorizationRequirementError,
    InvalidOperatorError,
    UnauthorizedOperatorError,
)

_AUTHORIZATION_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9:._/-]{0,127}$")
_AUTHORIZATION_TEXT_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9:._/-]{0,127}$")
_TENANT_ISOLATION_TIERS = frozenset({"bridge", "silo"})
_PRINCIPAL_TYPES = frozenset({"m2m", "human", "platform"})
_MAX_AUTHORIZATION_TOKENS = 64


@dataclass(frozen=True, slots=True)
class OperatorContext:
    operator_id: str
    authorized: bool = False
    can_access_tenant_catalog: bool = False

    @classmethod
    def platform_operator(cls, operator_id: str) -> OperatorContext:
        return cls(
            operator_id=operator_id,
            authorized=True,
            can_access_tenant_catalog=True,
        )

    @classmethod
    def tenant_scoped(cls, operator_id: str) -> OperatorContext:
        return cls(operator_id=operator_id, authorized=True)

    def require_authorized(self) -> None:
        if not isinstance(self.operator_id, str) or not self.operator_id.strip():
            raise InvalidOperatorError("operator_id é obrigatório")
        if not self.authorized:
            raise UnauthorizedOperatorError("operador não autorizado")

    def require_tenant_catalog_access(self) -> None:
        self.require_authorized()
        if not self.can_access_tenant_catalog:
            raise UnauthorizedOperatorError("operador sem permissão de catálogo de tenant")


@dataclass(frozen=True, slots=True)
class AuthorizationSubject:
    subject_id: str
    tenant_id: str
    tenant_isolation_tier: str
    scopes: Iterable[str]
    roles: Iterable[str] = ()
    client_id: str | None = None
    token_id: str | None = field(default=None, repr=False)
    principal_type: str = "m2m"

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "subject_id",
            _required_authorization_text(self.subject_id, "subject_id"),
        )
        object.__setattr__(
            self,
            "tenant_id",
            _required_authorization_text(self.tenant_id, "tenant_id"),
        )
        object.__setattr__(
            self,
            "tenant_isolation_tier",
            _required_tenant_isolation_tier(self.tenant_isolation_tier),
        )
        object.__setattr__(self, "scopes", _normalize_required_authorization_tokens(self.scopes))
        object.__setattr__(self, "roles", _normalize_optional_authorization_tokens(self.roles))
        object.__setattr__(
            self,
            "client_id",
            _optional_authorization_text(self.client_id, "client_id"),
        )
        object.__setattr__(
            self,
            "token_id",
            _optional_authorization_text(self.token_id, "token_id"),
        )
        object.__setattr__(self, "principal_type", _required_principal_type(self.principal_type))

    @classmethod
    def from_resolved_tenant_context(
        cls,
        *,
        subject_id: str,
        tenant_id: str,
        tenant_isolation_tier: str,
        scopes: Iterable[str],
        trusted_roles: Iterable[str] = (),
        client_id: str | None = None,
        token_id: str | None = None,
        principal_type: str = "m2m",
    ) -> AuthorizationSubject:
        return cls(
            subject_id=subject_id,
            tenant_id=tenant_id,
            tenant_isolation_tier=tenant_isolation_tier,
            scopes=scopes,
            roles=trusted_roles,
            client_id=client_id,
            token_id=token_id,
            principal_type=principal_type,
        )

    def to_log_metadata(self) -> dict[str, object]:
        metadata: dict[str, object] = {
            "subject_id": self.subject_id,
            "tenant_id": self.tenant_id,
            "tenant_isolation_tier": self.tenant_isolation_tier,
            "roles": sorted(self.roles),
            "scopes": sorted(self.scopes),
            "principal_type": self.principal_type,
        }
        if self.client_id is not None:
            metadata["client_id"] = self.client_id
        return metadata


@dataclass(frozen=True, slots=True)
class ProtectedResource:
    resource_type: str
    resource_id: str
    tenant_id: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "resource_type",
            _required_authorization_text(self.resource_type, "resource_type"),
        )
        object.__setattr__(
            self,
            "resource_id",
            _required_authorization_text(self.resource_id, "resource_id"),
        )
        object.__setattr__(
            self,
            "tenant_id",
            _required_authorization_text(self.tenant_id, "tenant_id"),
        )


@dataclass(frozen=True, slots=True)
class AuthorizationRequirement:
    operation: str
    required_scopes: Iterable[str]
    required_roles: Iterable[str] = ()
    allow_scope_only: bool = False
    _registry_bound: bool = field(default=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        if not self._registry_bound:
            raise InvalidAuthorizationRequirementError("requisito deve vir da registry")
        object.__setattr__(
            self,
            "operation",
            _required_requirement_text(self.operation, "operation"),
        )
        object.__setattr__(
            self,
            "required_scopes",
            _normalize_required_requirement_tokens(self.required_scopes),
        )
        object.__setattr__(
            self,
            "required_roles",
            _normalize_optional_requirement_tokens(self.required_roles),
        )
        object.__setattr__(self, "allow_scope_only", _normalize_scope_only(self.allow_scope_only))
        if not self.required_roles and not self.allow_scope_only:
            raise InvalidAuthorizationRequirementError("role obrigatória ausente")

    @classmethod
    def from_registry(
        cls,
        *,
        operation: str,
        required_scopes: Iterable[str],
        required_roles: Iterable[str] = (),
        allow_scope_only: bool = False,
    ) -> AuthorizationRequirement:
        return cls(
            operation=operation,
            required_scopes=required_scopes,
            required_roles=required_roles,
            allow_scope_only=allow_scope_only,
            _registry_bound=True,
        )


@dataclass(frozen=True, slots=True)
class AuthorizationOperationDefinition:
    operation: str
    required_scopes: Iterable[str]
    required_roles: Iterable[str] = ()
    allow_scope_only: bool = False

    def to_requirement(self) -> AuthorizationRequirement:
        return AuthorizationRequirement.from_registry(
            operation=self.operation,
            required_scopes=self.required_scopes,
            required_roles=self.required_roles,
            allow_scope_only=self.allow_scope_only,
        )


class AuthorizationOperationRegistry:
    def __init__(self, definitions: Iterable[AuthorizationOperationDefinition]) -> None:
        requirements: dict[str, AuthorizationRequirement] = {}
        for definition in definitions:
            requirement = definition.to_requirement()
            if requirement.operation in requirements:
                raise InvalidAuthorizationRequirementError("operação de autorização duplicada")
            requirements[requirement.operation] = requirement
        if not requirements:
            raise InvalidAuthorizationRequirementError("registry de autorização vazia")
        self._requirements = requirements

    def requirement_for(self, operation: str) -> AuthorizationRequirement:
        operation_name = _required_requirement_text(operation, "operation")
        requirement = self._requirements.get(operation_name)
        if requirement is None:
            raise InvalidAuthorizationRequirementError("operação de autorização desconhecida")
        return requirement


@dataclass(frozen=True, slots=True)
class AuthorizationDecision:
    operation: str
    subject_id: str
    tenant_id: str
    resource_type: str
    resource_id: str
    granted: bool
    matched_scopes: frozenset[str]
    matched_roles: frozenset[str]
    allow_scope_only: bool

    def to_metadata(self) -> dict[str, object]:
        return {
            "operation": self.operation,
            "subject_id": self.subject_id,
            "tenant_id": self.tenant_id,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "granted": self.granted,
            "matched_scopes": sorted(self.matched_scopes),
            "matched_roles": sorted(self.matched_roles),
            "allow_scope_only": self.allow_scope_only,
        }


class AuthorizationPolicy:
    def authorize(
        self,
        *,
        subject: AuthorizationSubject,
        requirement: AuthorizationRequirement,
        resource: ProtectedResource,
    ) -> AuthorizationDecision:
        if not isinstance(subject, AuthorizationSubject):
            raise InvalidAuthorizationContextError("contexto de autorização inválido")
        if not isinstance(requirement, AuthorizationRequirement):
            raise InvalidAuthorizationRequirementError("requisito de autorização inválido")
        if not isinstance(resource, ProtectedResource):
            raise InvalidAuthorizationContextError("recurso protegido inválido")

        if subject.tenant_id != resource.tenant_id:
            raise CrossTenantAccessDeniedError("contexto de tenant não permite este recurso")

        required_scopes = frozenset(requirement.required_scopes)
        subject_scopes = frozenset(subject.scopes)
        missing_scopes = required_scopes - subject_scopes
        if missing_scopes:
            raise InsufficientScopeError("scope obrigatório ausente")

        required_roles = frozenset(requirement.required_roles)
        subject_roles = frozenset(subject.roles)
        missing_roles = required_roles - subject_roles
        if missing_roles:
            raise InsufficientRoleError("role obrigatória ausente")

        return AuthorizationDecision(
            operation=requirement.operation,
            subject_id=subject.subject_id,
            tenant_id=subject.tenant_id,
            resource_type=resource.resource_type,
            resource_id=resource.resource_id,
            granted=True,
            matched_scopes=required_scopes,
            matched_roles=required_roles,
            allow_scope_only=requirement.allow_scope_only,
        )


def _required_authorization_text(value: str, field_name: str) -> str:
    return _required_text(
        value,
        field_name,
        error_class=InvalidAuthorizationContextError,
    )


def _required_requirement_text(value: str, field_name: str) -> str:
    return _required_text(
        value,
        field_name,
        error_class=InvalidAuthorizationRequirementError,
    )


def _optional_authorization_text(value: str | None, field_name: str) -> str | None:
    if value is None:
        return None
    return _required_authorization_text(value, field_name)


def _required_tenant_isolation_tier(value: str) -> str:
    tier = _required_authorization_text(value, "tenant_isolation_tier")
    if tier not in _TENANT_ISOLATION_TIERS:
        raise InvalidAuthorizationContextError("tier de isolamento inválido")
    return tier


def _required_principal_type(value: str) -> str:
    principal_type = _required_authorization_text(value, "principal_type")
    if principal_type not in _PRINCIPAL_TYPES:
        raise InvalidAuthorizationContextError("tipo de principal inválido")
    return principal_type


def _normalize_scope_only(value: bool) -> bool:
    if not isinstance(value, bool):
        raise InvalidAuthorizationRequirementError("scope-only inválido")
    return value


def _required_text(
    value: str,
    field_name: str,
    *,
    error_class: type[InvalidAuthorizationContextError | InvalidAuthorizationRequirementError],
) -> str:
    if not isinstance(value, str):
        raise error_class(f"{field_name} é obrigatório")
    normalized_value = value.strip()
    if not normalized_value:
        raise error_class(f"{field_name} é obrigatório")
    if _AUTHORIZATION_TEXT_PATTERN.fullmatch(normalized_value) is None:
        raise error_class(f"{field_name} inválido")
    return normalized_value


def _normalize_required_authorization_tokens(values: Iterable[str]) -> frozenset[str]:
    return _normalize_tokens(
        values,
        required=True,
        error_class=InvalidAuthorizationContextError,
    )


def _normalize_optional_authorization_tokens(values: Iterable[str]) -> frozenset[str]:
    return _normalize_tokens(
        values,
        required=False,
        error_class=InvalidAuthorizationContextError,
    )


def _normalize_required_requirement_tokens(values: Iterable[str]) -> frozenset[str]:
    return _normalize_tokens(
        values,
        required=True,
        error_class=InvalidAuthorizationRequirementError,
    )


def _normalize_optional_requirement_tokens(values: Iterable[str]) -> frozenset[str]:
    return _normalize_tokens(
        values,
        required=False,
        error_class=InvalidAuthorizationRequirementError,
    )


def _normalize_tokens(
    values: Iterable[str],
    *,
    required: bool,
    error_class: type[InvalidAuthorizationContextError | InvalidAuthorizationRequirementError],
) -> frozenset[str]:
    if isinstance(values, str | Mapping | bytes | bytearray | memoryview) or not isinstance(
        values,
        Iterable,
    ):
        raise error_class("tokens de autorização inválidos")

    normalized_tokens: set[str] = set()
    token_count = 0
    for value in values:
        token_count += 1
        if token_count > _MAX_AUTHORIZATION_TOKENS:
            raise error_class("tokens de autorização excedem limite")
        if not isinstance(value, str):
            raise error_class("tokens de autorização inválidos")
        normalized_value = value.strip()
        if _AUTHORIZATION_TOKEN_PATTERN.fullmatch(normalized_value) is None:
            raise error_class("tokens de autorização inválidos")
        normalized_tokens.add(normalized_value)

    if required and not normalized_tokens:
        raise error_class("tokens de autorização obrigatórios")
    return frozenset(normalized_tokens)


DEFAULT_AUTHORIZATION_OPERATION_REGISTRY = AuthorizationOperationRegistry(
    definitions=(
        AuthorizationOperationDefinition(
            operation="proposal.submit",
            required_scopes=("proposal:submit",),
            required_roles=("service-client",),
        ),
        AuthorizationOperationDefinition(
            operation="decision.read",
            required_scopes=("decision:read",),
            allow_scope_only=True,
        ),
        AuthorizationOperationDefinition(
            operation="tenant.catalog.read",
            required_scopes=("tenant:admin",),
            required_roles=("tenant-admin",),
        ),
    )
)
