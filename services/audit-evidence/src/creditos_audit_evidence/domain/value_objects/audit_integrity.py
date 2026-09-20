from __future__ import annotations

import re

from creditos_audit_evidence.domain.errors import AuditEvidenceValidationError
from creditos_audit_evidence.domain.value_objects.audit_event import validate_tenant_id

CANONICALIZATION_VERSION = "audit-event-canonical-v1"
HASH_ALGORITHM = "sha256"
GENESIS_PREVIOUS_HASH = "creditos-audit-chain-genesis:v1"
INTEGRITY_SCOPE_TENANT = "tenant"

_SHA256_HEX_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def validate_integrity_scope(value: str) -> str:
    if value != INTEGRITY_SCOPE_TENANT:
        raise AuditEvidenceValidationError(
            "escopo de integridade inválido",
            code="invalid_integrity_scope",
            field_path="integrity_scope",
        )
    return value


def validate_integrity_chain_id(value: str | None, *, tenant_id: str) -> str:
    if value is None:
        return validate_tenant_id(tenant_id)
    normalized_value = validate_tenant_id(value)
    if normalized_value != tenant_id:
        raise AuditEvidenceValidationError(
            "cadeia de integridade divergente do tenant",
            code="integrity_chain_tenant_mismatch",
            field_path="integrity_chain_id",
        )
    return normalized_value


def validate_previous_hash(value: str | None) -> str | None:
    if value is None:
        return None
    if value == GENESIS_PREVIOUS_HASH:
        return value
    return validate_current_hash(value, field_path="previous_hash")


def validate_current_hash(value: str | None, *, field_path: str = "current_hash") -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or _SHA256_HEX_PATTERN.fullmatch(value) is None:
        raise AuditEvidenceValidationError(
            "hash de integridade inválido",
            code="invalid_integrity_hash",
            field_path=field_path,
        )
    return value


def validate_hash_algorithm(value: str) -> str:
    if value != HASH_ALGORITHM:
        raise AuditEvidenceValidationError(
            "algoritmo de hash inválido",
            code="invalid_hash_algorithm",
            field_path="hash_algorithm",
        )
    return value


def validate_canonicalization_version(value: str) -> str:
    if value != CANONICALIZATION_VERSION:
        raise AuditEvidenceValidationError(
            "versão de canonicalização inválida",
            code="invalid_canonicalization_version",
            field_path="canonicalization_version",
        )
    return value
