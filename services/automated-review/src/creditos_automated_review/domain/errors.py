from __future__ import annotations

from types import MappingProxyType
from typing import Any


class AutomatedReviewDomainError(ValueError):
    code = "automated_review_domain_error"
    safe_message = "erro de domínio de revisão automatizada"
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


class AutomatedReviewValidationError(AutomatedReviewDomainError):
    code = "automated_review_validation_error"
    safe_message = "configuração de revisão automatizada inválida"


class AutomatedReviewImmutableError(AutomatedReviewDomainError):
    code = "automated_review_config_immutable"
    safe_message = "configuração publicada não pode ser alterada"


class AutomatedReviewConflictError(AutomatedReviewDomainError):
    code = "automated_review_config_conflict"
    safe_message = "configuração de revisão automatizada em conflito"
    grpc_status = "ABORTED"


class AutomatedReviewConfigNotFoundError(AutomatedReviewDomainError):
    code = "automated_review_config_not_found"
    safe_message = "configuração de revisão automatizada não encontrada"


class AutomatedReviewTenantContextError(AutomatedReviewDomainError):
    code = "automated_review_tenant_context_required"
    safe_message = "tenant confiável é obrigatório"
    grpc_status = "PERMISSION_DENIED"
