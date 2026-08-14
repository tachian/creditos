from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any


class ProposalDomainError(ValueError):
    code = "proposal_domain_error"
    safe_message = "erro de domínio de proposta"
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


@dataclass(frozen=True, slots=True)
class SafeValidationIssue:
    code: str
    field_path: str | None = None
    details: MappingProxyType[str, Any] = field(default_factory=lambda: MappingProxyType({}))


class ProposalValidationError(ProposalDomainError):
    code = "proposal_validation_error"
    safe_message = "proposta inválida"
