from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from time import perf_counter
from typing import Any
from uuid import uuid4

from creditos_observability import ObservabilityContext
from creditos_observability.logging import build_structured_log
from creditos_security import PropagatedContext

from creditos_audit_evidence.application.ports import (
    AuditCheckpointSigner,
    AuditEventRepository,
    AuditIntegrityCheckpointRepository,
)
from creditos_audit_evidence.domain.entities import (
    AuditEvent,
    AuditIntegrityCheckpoint,
    OperationalEvidenceReference,
)
from creditos_audit_evidence.domain.errors import (
    AuditEvidenceTenantContextError,
    AuditEvidenceValidationError,
)
from creditos_audit_evidence.domain.services.audit_integrity import (
    CANONICALIZATION_VERSION,
    GENESIS_PREVIOUS_HASH,
    HASH_ALGORITHM,
    calculate_audit_event_hash,
    calculate_checkpoint_digest,
    calculate_checkpoint_id,
)
from creditos_audit_evidence.domain.value_objects.audit_event import (
    validate_aggregate_id,
    validate_aggregate_type,
    validate_occurred_at,
)

SERVICE_NAME = "audit-evidence"
SERVICE_VERSION = "0.1.0"
CONTRACT = "audit-evidence.application"
CONTRACT_VERSION = "v1"


@dataclass(frozen=True, slots=True)
class RegisterAuditEventCommand:
    event_id: str
    aggregate_type: str
    aggregate_id: str
    event_type: str
    action: str
    resource_type: str
    resource_id: str
    source_service: str
    source_kind: str
    result: str
    occurred_at: datetime
    safe_details: dict[str, str] | None = None
    operational_evidence_refs: tuple[OperationalEvidenceReference, ...] = ()


@dataclass(frozen=True, slots=True)
class GetAuditEventCommand:
    event_id: str


@dataclass(frozen=True, slots=True)
class ListAuditEventsByAggregateCommand:
    aggregate_type: str
    aggregate_id: str


@dataclass(frozen=True, slots=True)
class ListAuditEventsByTimeWindowCommand:
    occurred_from: datetime
    occurred_to: datetime


@dataclass(frozen=True, slots=True)
class GenerateAuditIntegrityCheckpointCommand:
    occurred_from: datetime
    occurred_to: datetime
    created_at: datetime


@dataclass(frozen=True, slots=True)
class VerifyAuditIntegrityCommand:
    occurred_from: datetime
    occurred_to: datetime
    checkpoint_id: str | None = None


@dataclass(frozen=True, slots=True)
class AuditEventApplicationResult:
    event: AuditEvent
    logs: tuple[dict[str, Any], ...]


@dataclass(frozen=True, slots=True)
class AuditEventListApplicationResult:
    events: tuple[AuditEvent, ...]
    logs: tuple[dict[str, Any], ...]


@dataclass(frozen=True, slots=True)
class AuditIntegrityCheckpointApplicationResult:
    checkpoint: AuditIntegrityCheckpoint
    logs: tuple[dict[str, Any], ...]


@dataclass(frozen=True, slots=True)
class AuditIntegrityVerificationIssue:
    code: str
    event_id: str | None = None
    checkpoint_id: str | None = None


@dataclass(frozen=True, slots=True)
class AuditIntegrityVerificationApplicationResult:
    valid: bool
    status: str
    event_count: int
    checkpoint_id: str | None
    issues: tuple[AuditIntegrityVerificationIssue, ...]
    logs: tuple[dict[str, Any], ...]


class AuditEvidenceApplicationService:
    def __init__(
        self,
        *,
        repository: AuditEventRepository,
        checkpoint_repository: AuditIntegrityCheckpointRepository | None = None,
        checkpoint_signer: AuditCheckpointSigner | None = None,
        environment: str,
    ) -> None:
        self._repository = repository
        self._checkpoint_repository = checkpoint_repository
        self._checkpoint_signer = checkpoint_signer
        self._environment = environment
        self._logged_events: list[dict[str, Any]] = []

    @property
    def logged_events(self) -> tuple[dict[str, Any], ...]:
        return tuple(self._logged_events)

    def register_event(
        self,
        command: RegisterAuditEventCommand,
        *,
        context: ObservabilityContext,
        trusted_context: PropagatedContext,
    ) -> AuditEventApplicationResult:
        started_at = perf_counter()
        _require_matching_context(context=context, trusted_context=trusted_context)
        _require_scope(trusted_context=trusted_context, required_scope="audit:write")
        event = AuditEvent.create(
            event_id=command.event_id,
            tenant_id=trusted_context.trusted.tenant_id,
            aggregate_type=command.aggregate_type,
            aggregate_id=command.aggregate_id,
            event_type=command.event_type,
            action=command.action,
            resource_type=command.resource_type,
            resource_id=command.resource_id,
            actor_subject_id=trusted_context.trusted.subject_id,
            source_service=command.source_service,
            source_kind=command.source_kind,
            result=command.result,
            occurred_at=command.occurred_at,
            correlation_id=trusted_context.correlation_id,
            trace_id=trusted_context.trace_id,
            request_id=trusted_context.request_id,
            safe_details=command.safe_details or {},
            operational_evidence_refs=command.operational_evidence_refs,
        )
        event = self._repository.append(event)
        log = self._log_operation(
            context=context,
            operation="audit_evidence.event.append",
            status="accepted",
            duration_ms=_duration_ms(started_at),
            payload=command,
            extra=_safe_event_details(event),
        )
        return AuditEventApplicationResult(event=event, logs=(log,))

    def get_event(
        self,
        command: GetAuditEventCommand,
        *,
        context: ObservabilityContext,
        trusted_context: PropagatedContext,
    ) -> AuditEventApplicationResult | None:
        started_at = perf_counter()
        _require_matching_context(context=context, trusted_context=trusted_context)
        _require_scope(trusted_context=trusted_context, required_scope="audit:read")
        event = self._repository.get(
            tenant_id=trusted_context.trusted.tenant_id,
            event_id=command.event_id,
        )
        if event is None:
            self._append_read_audit_event(
                command=command, trusted_context=trusted_context, result="not_found"
            )
            self._log_operation(
                context=context,
                operation="audit_evidence.event.get",
                status="not_found",
                duration_ms=_duration_ms(started_at),
                payload=command,
                extra={"source_event_id": command.event_id, "outcome": "not_found"},
            )
            return None
        self._append_read_audit_event(
            command=command, trusted_context=trusted_context, result="accepted"
        )
        log = self._log_operation(
            context=context,
            operation="audit_evidence.event.get",
            status="accepted",
            duration_ms=_duration_ms(started_at),
            payload=command,
            extra=_safe_event_details(event),
        )
        return AuditEventApplicationResult(event=event, logs=(log,))

    def _append_read_audit_event(
        self,
        *,
        command: GetAuditEventCommand,
        trusted_context: PropagatedContext,
        result: str,
    ) -> None:
        self._repository.append(
            AuditEvent.create(
                event_id=f"audit_evt_read_{uuid4().hex}",
                tenant_id=trusted_context.trusted.tenant_id,
                aggregate_type="audit_event",
                aggregate_id=command.event_id,
                event_type="audit_event.read",
                action="read",
                resource_type="audit_event",
                resource_id=command.event_id,
                actor_subject_id=trusted_context.trusted.subject_id,
                source_service=SERVICE_NAME,
                source_kind="system",
                result=result,
                occurred_at=datetime.now(UTC),
                correlation_id=trusted_context.correlation_id,
                trace_id=trusted_context.trace_id,
                request_id=trusted_context.request_id,
                safe_details={"source_event_id": command.event_id, "outcome": result},
            )
        )

    def list_by_aggregate(
        self,
        command: ListAuditEventsByAggregateCommand,
        *,
        context: ObservabilityContext,
        trusted_context: PropagatedContext,
    ) -> AuditEventListApplicationResult:
        started_at = perf_counter()
        _require_matching_context(context=context, trusted_context=trusted_context)
        _require_scope(trusted_context=trusted_context, required_scope="audit:read")
        aggregate_type = validate_aggregate_type(command.aggregate_type)
        aggregate_id = validate_aggregate_id(command.aggregate_id)
        events = self._repository.list_by_aggregate(
            tenant_id=trusted_context.trusted.tenant_id,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
        )
        log = self._log_operation(
            context=context,
            operation="audit_evidence.event.list_by_aggregate",
            status="accepted",
            duration_ms=_duration_ms(started_at),
            payload=command,
            extra={
                "aggregate_type": aggregate_type,
                "aggregate_id": aggregate_id,
                "event_count": str(len(events)),
            },
        )
        return AuditEventListApplicationResult(events=events, logs=(log,))

    def list_by_time_window(
        self,
        command: ListAuditEventsByTimeWindowCommand,
        *,
        context: ObservabilityContext,
        trusted_context: PropagatedContext,
    ) -> AuditEventListApplicationResult:
        started_at = perf_counter()
        _require_matching_context(context=context, trusted_context=trusted_context)
        _require_scope(trusted_context=trusted_context, required_scope="audit:read")
        occurred_from = validate_occurred_at(command.occurred_from)
        occurred_to = validate_occurred_at(command.occurred_to)
        if occurred_from > occurred_to:
            raise AuditEvidenceValidationError(
                "janela temporal de auditoria inválida",
                code="audit_evidence_invalid_time_window",
                field_path="occurred_from",
            )
        events = self._repository.list_by_time_window(
            tenant_id=trusted_context.trusted.tenant_id,
            occurred_from=occurred_from,
            occurred_to=occurred_to,
        )
        log = self._log_operation(
            context=context,
            operation="audit_evidence.event.list_by_time_window",
            status="accepted",
            duration_ms=_duration_ms(started_at),
            payload=command,
            extra={
                "occurred_from": occurred_from.isoformat(),
                "occurred_to": occurred_to.isoformat(),
                "event_count": str(len(events)),
            },
        )
        return AuditEventListApplicationResult(events=events, logs=(log,))

    def generate_integrity_checkpoint(
        self,
        command: GenerateAuditIntegrityCheckpointCommand,
        *,
        context: ObservabilityContext,
        trusted_context: PropagatedContext,
    ) -> AuditIntegrityCheckpointApplicationResult:
        started_at = perf_counter()
        checkpoint_repository, checkpoint_signer = self._require_checkpoint_dependencies()
        _require_matching_context(context=context, trusted_context=trusted_context)
        _require_scope(trusted_context=trusted_context, required_scope="audit:integrity:write")
        occurred_from, occurred_to = _validate_time_window(
            command.occurred_from, command.occurred_to
        )
        created_at = validate_occurred_at(command.created_at)
if created_at <= occurred_to or occurred_to >= datetime.now(UTC):
            raise AuditEvidenceValidationError(
                "janela de checkpoint ainda não está fechada",
                code="checkpoint_window_not_closed",
                field_path="created_at",
            )
        tenant_chain = self._repository.list_by_tenant_chain(
            tenant_id=trusted_context.trusted.tenant_id
        )
        events, predecessor = _select_integrity_window(
            tenant_chain=tenant_chain,
            occurred_from=occurred_from,
            occurred_to=occurred_to,
        )
        if not events:
            raise AuditEvidenceValidationError(
                "janela de checkpoint sem eventos",
                code="empty_checkpoint_window",
                field_path="occurred_from",
            )
        chain_issues = _verify_event_chain(
            events,
            tenant_id=trusted_context.trusted.tenant_id,
            predecessor=predecessor,
        )
        if chain_issues:
            raise AuditEvidenceValidationError(
                "cadeia de auditoria inválida para checkpoint",
                code="invalid_checkpoint_source_chain",
                field_path="previous_hash",
            )
        batch_digest = calculate_checkpoint_digest(
            tenant_id=trusted_context.trusted.tenant_id,
            window_started_at=occurred_from,
            window_ended_at=occurred_to,
            events=events,
        )
        checkpoint_id = calculate_checkpoint_id(
            tenant_id=trusted_context.trusted.tenant_id,
            window_started_at=occurred_from,
            window_ended_at=occurred_to,
            batch_digest=batch_digest,
        )
        signature = checkpoint_signer.sign(batch_digest.encode("utf-8"))
        first_event = events[0]
        last_event = events[-1]
        checkpoint = checkpoint_repository.append(
            AuditIntegrityCheckpoint(
                checkpoint_id=checkpoint_id,
                tenant_id=trusted_context.trusted.tenant_id,
                window_started_at=occurred_from,
                window_ended_at=occurred_to,
                event_count=len(events),
                first_event_id=first_event.event_id,
                last_event_id=last_event.event_id,
                first_event_hash=first_event.current_hash or "",
                last_event_hash=last_event.current_hash or "",
                batch_digest=batch_digest,
                signature=signature.signature,
                signature_key_ref=signature.key_ref,
                signature_algorithm=signature.algorithm,
                created_at=created_at,
            )
        )
        log = self._log_operation(
            context=context,
            operation="audit_evidence.integrity_checkpoint.generate",
            status="accepted",
            duration_ms=_duration_ms(started_at),
            payload=command,
            extra=_safe_checkpoint_details(checkpoint),
        )
        return AuditIntegrityCheckpointApplicationResult(checkpoint=checkpoint, logs=(log,))

    def verify_integrity(
        self,
        command: VerifyAuditIntegrityCommand,
        *,
        context: ObservabilityContext,
        trusted_context: PropagatedContext,
    ) -> AuditIntegrityVerificationApplicationResult:
        started_at = perf_counter()
        _require_matching_context(context=context, trusted_context=trusted_context)
        _require_scope(trusted_context=trusted_context, required_scope="audit:read")
        occurred_from, occurred_to = _validate_time_window(
            command.occurred_from, command.occurred_to
        )
        tenant_chain = self._repository.list_by_tenant_chain(
            tenant_id=trusted_context.trusted.tenant_id
        )
        events, predecessor = _select_integrity_window(
            tenant_chain=tenant_chain,
            occurred_from=occurred_from,
            occurred_to=occurred_to,
        )
        issues = list(
            _verify_event_chain(
                events,
                tenant_id=trusted_context.trusted.tenant_id,
                predecessor=predecessor,
            )
        )
        checkpoint = None
        if command.checkpoint_id is not None:
            checkpoint_repository, checkpoint_signer = self._require_checkpoint_dependencies()
            checkpoint = checkpoint_repository.get(
                tenant_id=trusted_context.trusted.tenant_id,
                checkpoint_id=command.checkpoint_id,
            )
            issues.extend(
                _verify_checkpoint(
                    tenant_id=trusted_context.trusted.tenant_id,
                    occurred_from=occurred_from,
                    occurred_to=occurred_to,
                    events=events,
                    checkpoint=checkpoint,
                    checkpoint_id=command.checkpoint_id,
                    checkpoint_signer=checkpoint_signer,
                )
            )
        valid = not issues
        log = self._log_operation(
            context=context,
            operation="audit_evidence.integrity.verify",
            status="accepted" if valid else "rejected",
            duration_ms=_duration_ms(started_at),
            payload=command,
            extra={
                "occurred_from": occurred_from.isoformat(),
                "occurred_to": occurred_to.isoformat(),
                "event_count": str(len(events)),
                "issue_count": str(len(issues)),
                "checkpoint_id": command.checkpoint_id or "",
                "outcome": "valid" if valid else "invalid",
            },
        )
        return AuditIntegrityVerificationApplicationResult(
            valid=valid,
            status="valid" if valid else "invalid",
            event_count=len(events),
            checkpoint_id=checkpoint.checkpoint_id
            if checkpoint is not None
            else command.checkpoint_id,
            issues=tuple(issues),
            logs=(log,),
        )

    def _log_operation(
        self,
        *,
        context: ObservabilityContext,
        operation: str,
        status: str,
        duration_ms: float,
        payload: Any,
        extra: dict[str, Any],
    ) -> dict[str, Any]:
        log = build_structured_log(
            context=context,
            service_name=SERVICE_NAME,
            service_version=SERVICE_VERSION,
            environment=self._environment,
            operation=operation,
            source=SERVICE_NAME,
            destination="audit_event_repository",
            contract=CONTRACT,
            contract_version=CONTRACT_VERSION,
            status=status,
            duration_ms=duration_ms,
            payload=payload,
            extra=extra,
        )
        self._logged_events.append(log)
        return log

    def _require_checkpoint_dependencies(
        self,
    ) -> tuple[AuditIntegrityCheckpointRepository, AuditCheckpointSigner]:
        if self._checkpoint_repository is None or self._checkpoint_signer is None:
            raise AuditEvidenceValidationError(
                "dependências de checkpoint não configuradas",
                code="audit_integrity_checkpoint_dependencies_missing",
                field_path="checkpoint_repository",
            )
        return self._checkpoint_repository, self._checkpoint_signer


def _require_matching_context(
    *,
    context: ObservabilityContext,
    trusted_context: PropagatedContext,
) -> None:
    if context.tenant_id and context.tenant_id != trusted_context.trusted.tenant_id:
        raise AuditEvidenceTenantContextError(
            "tenant divergente entre observabilidade e contexto confiável",
            code="audit_evidence_tenant_context_mismatch",
            field_path="tenant_id",
        )
    if (
        context.tenant_isolation_tier
        and context.tenant_isolation_tier != trusted_context.trusted.tenant_isolation_tier
    ):
        raise AuditEvidenceTenantContextError(
            "tier de isolamento divergente",
            code="audit_evidence_tenant_tier_mismatch",
            field_path="tenant_isolation_tier",
        )
    if context.correlation_id != trusted_context.correlation_id:
        raise AuditEvidenceTenantContextError(
            "correlation_id divergente",
            code="audit_evidence_correlation_context_mismatch",
            field_path="correlation_id",
        )
    if context.request_id != trusted_context.request_id:
        raise AuditEvidenceTenantContextError(
            "request_id divergente",
            code="audit_evidence_request_context_mismatch",
            field_path="request_id",
        )
    if context.trace_id != trusted_context.trace_id:
        raise AuditEvidenceTenantContextError(
            "trace_id divergente",
            code="audit_evidence_trace_context_mismatch",
            field_path="trace_id",
        )


def _require_scope(*, trusted_context: PropagatedContext, required_scope: str) -> None:
    if required_scope not in trusted_context.trusted.scopes:
        raise AuditEvidenceTenantContextError(
            f"escopo obrigatório ausente: {required_scope}",
            code=f"audit_evidence_missing_scope_{required_scope.replace(':', '_')}",
            field_path="scopes",
        )


def _validate_time_window(
    occurred_from: datetime, occurred_to: datetime
) -> tuple[datetime, datetime]:
    valid_from = validate_occurred_at(occurred_from)
    valid_to = validate_occurred_at(occurred_to)
    if valid_from > valid_to:
        raise AuditEvidenceValidationError(
            "janela temporal de auditoria inválida",
            code="audit_evidence_invalid_time_window",
            field_path="occurred_from",
        )
    return valid_from, valid_to


def _select_integrity_window(
    *,
    tenant_chain: tuple[AuditEvent, ...],
    occurred_from: datetime,
    occurred_to: datetime,
) -> tuple[tuple[AuditEvent, ...], AuditEvent | None]:
    selected: list[AuditEvent] = []
    predecessor: AuditEvent | None = None
    for event in tenant_chain:
        if occurred_from <= event.occurred_at <= occurred_to:
            selected.append(event)
        elif event.occurred_at < occurred_from:
            predecessor = event
    return tuple(selected), predecessor


def _verify_event_chain(
    events: tuple[AuditEvent, ...],
    *,
    tenant_id: str,
    predecessor: AuditEvent | None = None,
) -> tuple[AuditIntegrityVerificationIssue, ...]:
    issues: list[AuditIntegrityVerificationIssue] = []
    if not events:
        return (AuditIntegrityVerificationIssue(code="audit_window_empty_unverifiable"),)
    expected_previous_hash = (
        predecessor.current_hash
        if predecessor is not None and predecessor.current_hash is not None
        else GENESIS_PREVIOUS_HASH
    )
    seen_hashes = {GENESIS_PREVIOUS_HASH}
    if predecessor is not None and predecessor.current_hash is not None:
        seen_hashes.add(predecessor.current_hash)
    for event in events:
        if event.tenant_id != tenant_id or event.integrity_chain_id != tenant_id:
            issues.append(
                AuditIntegrityVerificationIssue(
                    code="audit_event_tenant_mismatch",
                    event_id=event.event_id,
                )
            )
        if event.previous_hash != expected_previous_hash:
            code = "audit_event_previous_hash_mismatch"
            if event.previous_hash and event.previous_hash not in seen_hashes:
                code = "audit_event_predecessor_missing"
            elif event.previous_hash in seen_hashes:
                code = "audit_event_order_invalid"
            issues.append(
                AuditIntegrityVerificationIssue(
                    code=code,
                    event_id=event.event_id,
                )
            )
        expected_current_hash = calculate_audit_event_hash(
            event,
            previous_hash=event.previous_hash or expected_previous_hash,
        )
        if event.current_hash != expected_current_hash:
            issues.append(
                AuditIntegrityVerificationIssue(
                    code="audit_event_hash_mismatch",
                    event_id=event.event_id,
                )
            )
        if event.current_hash is not None:
            seen_hashes.add(event.current_hash)
            expected_previous_hash = event.current_hash
    return tuple(issues)


def _verify_checkpoint(
    *,
    tenant_id: str,
    occurred_from: datetime,
    occurred_to: datetime,
    events: tuple[AuditEvent, ...],
    checkpoint: AuditIntegrityCheckpoint | None,
    checkpoint_id: str,
    checkpoint_signer: AuditCheckpointSigner,
) -> tuple[AuditIntegrityVerificationIssue, ...]:
    if checkpoint is None:
        return (
            AuditIntegrityVerificationIssue(
                code="audit_checkpoint_not_found",
                checkpoint_id=checkpoint_id,
            ),
        )
    batch_digest = calculate_checkpoint_digest(
        tenant_id=tenant_id,
        window_started_at=occurred_from,
        window_ended_at=occurred_to,
        events=events,
    )
    issues: list[AuditIntegrityVerificationIssue] = []
    expected_checkpoint_id = calculate_checkpoint_id(
        tenant_id=tenant_id,
        window_started_at=occurred_from,
        window_ended_at=occurred_to,
        batch_digest=batch_digest,
    )
    first_event = events[0] if events else None
    last_event = events[-1] if events else None
    metadata_mismatches = (
        checkpoint.tenant_id != tenant_id,
        checkpoint.window_started_at != occurred_from,
        checkpoint.window_ended_at != occurred_to,
        checkpoint.event_count != len(events),
        checkpoint.checkpoint_id != expected_checkpoint_id,
        checkpoint.hash_algorithm != HASH_ALGORITHM,
        checkpoint.canonicalization_version != CANONICALIZATION_VERSION,
        first_event is None or checkpoint.first_event_id != first_event.event_id,
        first_event is None or checkpoint.first_event_hash != first_event.current_hash,
        last_event is None or checkpoint.last_event_id != last_event.event_id,
        last_event is None or checkpoint.last_event_hash != last_event.current_hash,
    )
    if any(metadata_mismatches):
        issues.append(
            AuditIntegrityVerificationIssue(
                code="audit_checkpoint_metadata_mismatch",
                checkpoint_id=checkpoint.checkpoint_id,
            )
        )
    if checkpoint.batch_digest != batch_digest:
        issues.append(
            AuditIntegrityVerificationIssue(
                code="audit_checkpoint_digest_mismatch",
                checkpoint_id=checkpoint.checkpoint_id,
            )
        )
    try:
        signature_valid = checkpoint_signer.verify(
            checkpoint.batch_digest.encode("utf-8"),
            signature=checkpoint.signature,
            key_ref=checkpoint.signature_key_ref,
            algorithm=checkpoint.signature_algorithm,
        )
    except Exception:
        issues.append(
            AuditIntegrityVerificationIssue(
                code="audit_checkpoint_signature_unavailable",
                checkpoint_id=checkpoint.checkpoint_id,
            )
        )
        signature_valid = False
    if not signature_valid:
        issues.append(
            AuditIntegrityVerificationIssue(
                code="audit_checkpoint_signature_mismatch",
                checkpoint_id=checkpoint.checkpoint_id,
            )
        )
    return tuple(issues)


def _safe_event_details(event: AuditEvent) -> dict[str, Any]:
    return {
        "event_id": event.event_id,
        "tenant_id": event.tenant_id,
        "aggregate_type": event.aggregate_type,
        "aggregate_id": event.aggregate_id,
        "event_type": event.event_type,
        "action": event.action,
        "resource_type": event.resource_type,
        "resource_id": event.resource_id,
        "source_service": event.source_service,
        "source_kind": event.source_kind,
        "result": event.result,
        "correlation_id": event.correlation_id,
        "trace_id": event.trace_id,
        "previous_hash": event.previous_hash,
        "current_hash": event.current_hash,
        "operational_evidence_ref_count": str(len(event.operational_evidence_refs)),
    }


def _safe_checkpoint_details(checkpoint: AuditIntegrityCheckpoint) -> dict[str, Any]:
    return {
        "checkpoint_id": checkpoint.checkpoint_id,
        "tenant_id": checkpoint.tenant_id,
        "event_count": str(checkpoint.event_count),
        "first_event_id": checkpoint.first_event_id,
        "last_event_id": checkpoint.last_event_id,
        "batch_digest": checkpoint.batch_digest,
        "signature_key_ref": checkpoint.signature_key_ref,
    }


def _duration_ms(started_at: float) -> float:
    return round((perf_counter() - started_at) * 1000, 3)
