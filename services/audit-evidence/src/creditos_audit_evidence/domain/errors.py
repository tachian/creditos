from __future__ import annotations


class AuditEvidenceError(ValueError):
    code = "audit_evidence_error"
    safe_message = "erro de auditoria"

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        field_path: str | None = None,
    ) -> None:
        self.message = message or self.safe_message
        self.code = code or self.code
        self.field_path = field_path
        super().__init__(self.message)


class AuditEvidenceValidationError(AuditEvidenceError):
    code = "audit_evidence_validation_error"
    safe_message = "evento de auditoria inválido"


class AuditEvidenceConflictError(AuditEvidenceError):
    code = "audit_evidence_conflict"
    safe_message = "conflito de auditoria"


class AuditEvidenceTenantContextError(AuditEvidenceError):
    code = "audit_evidence_tenant_context_error"
    safe_message = "contexto confiável de auditoria inválido"
