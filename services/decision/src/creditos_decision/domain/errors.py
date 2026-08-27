from __future__ import annotations

from types import MappingProxyType
from typing import Any


class DecisionDomainError(ValueError):
    code = "decision_domain_error"
    safe_message = "erro de domínio de decisão"
    grpc_status = "INVALID_ARGUMENT"

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        field_path: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.code = code or self.code
        self.field_path = field_path
        self.details = MappingProxyType(details or {})
        self.message = message or self.safe_message
        super().__init__(self.message)


class PolicyValidationError(DecisionDomainError):
    code = "policy_validation_error"
    safe_message = "política inválida"


class PolicyImmutableError(DecisionDomainError):
    code = "policy_immutable"
    safe_message = "política não pode ser alterada"


class PolicyTenantContextError(DecisionDomainError):
    code = "policy_tenant_context_required"
    safe_message = "tenant confiável é obrigatório"
    grpc_status = "PERMISSION_DENIED"


class PolicyNotFoundError(DecisionDomainError):
    code = "credit_policy_not_found"
    safe_message = "política não encontrada"


class PolicyConcurrencyError(DecisionDomainError):
    code = "policy_concurrent_revision"
    safe_message = "revisão concorrente"


class ReasonCodeCatalogNotFoundError(DecisionDomainError):
    code = "reason_code_catalog_not_found"
    safe_message = "catálogo de reason codes não encontrado"


class ReasonCodeCatalogVersioningError(DecisionDomainError):
    code = "reason_code_catalog_requires_new_version"
    safe_message = "mudança incompatível exige nova versão"
