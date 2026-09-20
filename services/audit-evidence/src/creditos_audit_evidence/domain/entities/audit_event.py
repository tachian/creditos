from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType

from creditos_audit_evidence.domain.errors import AuditEvidenceValidationError
from creditos_audit_evidence.domain.value_objects.audit_event import (
    normalize_safe_details,
    validate_action,
    validate_aggregate_id,
    validate_aggregate_type,
    validate_correlation_id,
    validate_event_id,
    validate_event_type,
    validate_occurred_at,
    validate_request_id,
    validate_resource_id,
    validate_resource_type,
    validate_result,
    validate_source_kind,
    validate_source_service,
    validate_subject_id,
    validate_tenant_id,
    validate_trace_id,
)
from creditos_audit_evidence.domain.value_objects.audit_integrity import (
    CANONICALIZATION_VERSION,
    HASH_ALGORITHM,
    INTEGRITY_SCOPE_TENANT,
    validate_canonicalization_version,
    validate_current_hash,
    validate_hash_algorithm,
    validate_integrity_chain_id,
    validate_integrity_scope,
    validate_previous_hash,
)


@dataclass(frozen=True, slots=True)
class OperationalEvidenceReference:
    kind: str
    reference: str
    source: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", _validate_operational_evidence_kind(self.kind))
        object.__setattr__(
            self,
            "reference",
            validate_resource_id(self.reference, field_path="operational_evidence_refs.reference"),
        )
        object.__setattr__(
            self,
            "source",
            validate_source_service(self.source, field_path="operational_evidence_refs.source"),
        )


@dataclass(frozen=True, slots=True)
class AuditEvent:
    event_id: str
    tenant_id: str
    aggregate_type: str
    aggregate_id: str
    event_type: str
    action: str
    resource_type: str
    resource_id: str
    actor_subject_id: str
    source_service: str
    source_kind: str
    result: str
    occurred_at: datetime
    correlation_id: str
    trace_id: str
    request_id: str | None = None
    safe_details: Mapping[str, str] = field(default_factory=dict)
    operational_evidence_refs: tuple[OperationalEvidenceReference, ...] = field(
        default_factory=tuple
    )
    integrity_scope: str = INTEGRITY_SCOPE_TENANT
    integrity_chain_id: str | None = None
    previous_hash: str | None = None
    current_hash: str | None = None
    hash_algorithm: str = HASH_ALGORITHM
    canonicalization_version: str = CANONICALIZATION_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "event_id", validate_event_id(self.event_id))
        object.__setattr__(self, "tenant_id", validate_tenant_id(self.tenant_id))
        object.__setattr__(self, "aggregate_type", validate_aggregate_type(self.aggregate_type))
        object.__setattr__(self, "aggregate_id", validate_aggregate_id(self.aggregate_id))
        object.__setattr__(self, "event_type", validate_event_type(self.event_type))
        object.__setattr__(self, "action", validate_action(self.action))
        object.__setattr__(self, "resource_type", validate_resource_type(self.resource_type))
        object.__setattr__(self, "resource_id", validate_resource_id(self.resource_id))
        object.__setattr__(
            self,
            "actor_subject_id",
            validate_subject_id(self.actor_subject_id),
        )
        object.__setattr__(self, "source_service", validate_source_service(self.source_service))
        object.__setattr__(self, "source_kind", validate_source_kind(self.source_kind))
        object.__setattr__(self, "result", validate_result(self.result))
        object.__setattr__(self, "occurred_at", validate_occurred_at(self.occurred_at))
        object.__setattr__(self, "correlation_id", validate_correlation_id(self.correlation_id))
        object.__setattr__(self, "trace_id", validate_trace_id(self.trace_id))
        object.__setattr__(self, "request_id", validate_request_id(self.request_id))
        object.__setattr__(
            self,
            "safe_details",
            MappingProxyType(normalize_safe_details(self.safe_details or {})),
        )
        object.__setattr__(
            self,
            "operational_evidence_refs",
            _validate_operational_evidence_refs(self.operational_evidence_refs),
        )
        object.__setattr__(self, "integrity_scope", validate_integrity_scope(self.integrity_scope))
        object.__setattr__(
            self,
            "integrity_chain_id",
            validate_integrity_chain_id(self.integrity_chain_id, tenant_id=self.tenant_id),
        )
        object.__setattr__(self, "previous_hash", validate_previous_hash(self.previous_hash))
        object.__setattr__(self, "current_hash", validate_current_hash(self.current_hash))
        object.__setattr__(self, "hash_algorithm", validate_hash_algorithm(self.hash_algorithm))
        object.__setattr__(
            self,
            "canonicalization_version",
            validate_canonicalization_version(self.canonicalization_version),
        )
        _reject_operational_only_event(
            aggregate_type=self.aggregate_type,
            event_type=self.event_type,
            resource_type=self.resource_type,
        )

    @classmethod
    def create(
        cls,
        *,
        event_id: str,
        tenant_id: str,
        aggregate_type: str,
        aggregate_id: str,
        event_type: str,
        action: str,
        resource_type: str,
        resource_id: str,
        actor_subject_id: str,
        source_service: str,
        source_kind: str,
        result: str,
        occurred_at: datetime,
        correlation_id: str,
        trace_id: str,
        request_id: str | None = None,
        safe_details: Mapping[str, str] | None = None,
        operational_evidence_refs: tuple[OperationalEvidenceReference, ...] = (),
        integrity_scope: str = INTEGRITY_SCOPE_TENANT,
        integrity_chain_id: str | None = None,
        previous_hash: str | None = None,
        current_hash: str | None = None,
        hash_algorithm: str = HASH_ALGORITHM,
        canonicalization_version: str = CANONICALIZATION_VERSION,
    ) -> AuditEvent:
        return cls(
            event_id=event_id,
            tenant_id=tenant_id,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            event_type=event_type,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            actor_subject_id=actor_subject_id,
            source_service=source_service,
            source_kind=source_kind,
            result=result,
            occurred_at=occurred_at,
            correlation_id=correlation_id,
            trace_id=trace_id,
            request_id=request_id,
            safe_details=safe_details or {},
            operational_evidence_refs=operational_evidence_refs,
            integrity_scope=integrity_scope,
            integrity_chain_id=integrity_chain_id,
            previous_hash=previous_hash,
            current_hash=current_hash,
            hash_algorithm=hash_algorithm,
            canonicalization_version=canonicalization_version,
        )


def _validate_operational_evidence_kind(value: str) -> str:
    if value not in {"log", "trace", "message", "metric"}:
        raise AuditEvidenceValidationError(
            "tipo de evidência operacional inválido",
            code="invalid_operational_evidence_kind",
            field_path="operational_evidence_refs.kind",
        )
    return value


def _validate_operational_evidence_refs(
    values: tuple[OperationalEvidenceReference, ...],
) -> tuple[OperationalEvidenceReference, ...]:
    refs = tuple(values)
    if len(refs) > 16:
        raise AuditEvidenceValidationError(
            "referências operacionais excedem o limite",
            code="too_many_operational_evidence_refs",
            field_path="operational_evidence_refs",
        )
    for reference in refs:
        if not isinstance(reference, OperationalEvidenceReference):
            raise AuditEvidenceValidationError(
                "referência operacional inválida",
                code="invalid_operational_evidence_ref",
                field_path="operational_evidence_refs",
            )
    return refs


def _reject_operational_only_event(
    *,
    aggregate_type: str,
    event_type: str,
    resource_type: str,
) -> None:
    if _is_operational_only_token(aggregate_type) or _is_operational_only_token(resource_type):
        raise AuditEvidenceValidationError(
            "logs, traces, métricas e mensagens não substituem auditoria oficial",
            code="operational_evidence_cannot_replace_audit_event",
            field_path="aggregate_type",
        )
    if any(_is_operational_only_token(segment) for segment in event_type.split(".")):
        raise AuditEvidenceValidationError(
            "evento operacional não pode substituir evento oficial",
            code="operational_event_cannot_replace_audit_event",
            field_path="event_type",
        )


def _is_operational_only_token(value: str) -> bool:
    operational_tokens = ("operational_log", "log", "trace", "message", "metric")
    return any(
        value == token
        or value.startswith(f"{token}_")
        or value.endswith(f"_{token}")
        or f"_{token}_" in value
        for token in operational_tokens
    )
