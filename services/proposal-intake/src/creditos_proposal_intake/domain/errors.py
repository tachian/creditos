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


class IdempotencyConflictError(ProposalDomainError):
    code = "idempotency_conflict"
    safe_message = "conflito de idempotência"

    def __init__(
        self,
        *,
        attempted_proposal_fingerprint: str | None = None,
        existing_proposal_fingerprint: str | None = None,
    ) -> None:
        details = {"reason": "payload_fingerprint_mismatch"}
        if attempted_proposal_fingerprint is not None:
            details["attempted_proposal_fingerprint"] = attempted_proposal_fingerprint
        if existing_proposal_fingerprint is not None:
            details["existing_proposal_fingerprint"] = existing_proposal_fingerprint
        super().__init__(
            self.safe_message,
            field_path="headers.Idempotency-Key",
            details=details,
        )
