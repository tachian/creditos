from __future__ import annotations

from types import MappingProxyType
from typing import Any


class IntegrationDomainError(ValueError):
    code = "integration_domain_error"
    safe_message = "erro de domínio de integração"

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


class IntegrationValidationError(IntegrationDomainError):
    code = "integration_validation_error"
    safe_message = "configuração de integração inválida"
