from __future__ import annotations

import hashlib
import json
import re
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
    AuditWormExportRepository,
    AuditWormStorage,
)
from creditos_audit_evidence.domain.entities import (
    AuditEvent,
    AuditIntegrityCheckpoint,
    AuditWormExport,
    AuditWormExportManifest,
    OperationalEvidenceReference,
)
from creditos_audit_evidence.domain.errors import (
    AuditEvidenceConflictError,
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
    calculate_worm_export_manifest_digest,
    canonicalize_worm_export_manifest,
)
from creditos_audit_evidence.domain.value_objects.audit_event import (
    validate_aggregate_id,
    validate_aggregate_type,
    validate_occurred_at,
)
from creditos_audit_evidence.domain.value_objects.audit_integrity import (
    INTEGRITY_SCOPE_TENANT,
)
from creditos_audit_evidence.domain.value_objects.audit_worm_export import (
    WORM_MANIFEST_VERSION,
    AuditWormExportStatus,
    WormRetentionMode,
    ensure_not_shortened_retention,
    validate_legal_hold_reason,
    validate_retain_until,
    validate_retention_class,
    validate_retention_mode,
    validate_worm_object_key,
)

SERVICE_NAME = "audit-evidence"
SERVICE_VERSION = "0.1.0"
CONTRACT = "audit-evidence.application"
CONTRACT_VERSION = "v1"
_WORM_OBJECT_KEY_PATTERN = re.compile(
    r"^tenants/(?P<tenant_id>[A-Za-z0-9][A-Za-z0-9:._/-]{0,127})/"
    r"audit/year=(?P<year>\d{4})/month=(?P<month>\d{2})/"
    r"checkpoint=(?P<checkpoint_id>[A-Za-z0-9][A-Za-z0-9:._/-]{0,127})/manifest\.json$"
)


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
class ExportAuditCheckpointToWormCommand:
    checkpoint_id: str
    occurred_from: datetime
    occurred_to: datetime
    retention_class: str
    retention_mode: WormRetentionMode | str
    retain_until: datetime
    legal_hold: bool
    legal_hold_reason: str | None
    created_at: datetime
    object_key: str | None = None


@dataclass(frozen=True, slots=True)
class ReconcileAuditWormExportCommand:
    export_id: str


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


@dataclass(frozen=True, slots=True)
class AuditWormExportApplicationResult:
    export: AuditWormExport
    logs: tuple[dict[str, Any], ...]


@dataclass(frozen=True, slots=True)
class AuditWormReconciliationIssue:
    code: str
    export_id: str | None = None
    checkpoint_id: str | None = None


@dataclass(frozen=True, slots=True)
class AuditWormReconciliationApplicationResult:
    valid: bool
    status: str
    export_id: str
    checkpoint_id: str
    issues: tuple[AuditWormReconciliationIssue, ...]
    logs: tuple[dict[str, Any], ...]


class AuditEvidenceApplicationService:
    def __init__(
        self,
        *,
        repository: AuditEventRepository,
        checkpoint_repository: AuditIntegrityCheckpointRepository | None = None,
        checkpoint_signer: AuditCheckpointSigner | None = None,
        worm_export_repository: AuditWormExportRepository | None = None,
        worm_storage: AuditWormStorage | None = None,
        environment: str,
    ) -> None:
        self._repository = repository
        self._checkpoint_repository = checkpoint_repository
        self._checkpoint_signer = checkpoint_signer
        self._worm_export_repository = worm_export_repository
        self._worm_storage = worm_storage
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
        if occurred_to >= datetime.now(UTC):
            raise AuditEvidenceValidationError(
                "janela de checkpoint ainda não está fechada",
                code="checkpoint_window_not_closed",
                field_path="occurred_to",
            )
        if created_at <= occurred_to:
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
        try:
            occurred_from, occurred_to = _validate_time_window(
                command.occurred_from, command.occurred_to
            )
        except AuditEvidenceValidationError as exc:
            self._append_integrity_verification_audit_event(
                trusted_context=trusted_context,
                occurred_from=validate_occurred_at(command.occurred_from),
                occurred_to=validate_occurred_at(command.occurred_to),
                checkpoint_id=command.checkpoint_id,
                result="rejected",
                outcome="validation_error",
                event_count=0,
                issue_count=1,
                issue_codes=(exc.code,),
            )
            raise
        try:
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
        except AuditEvidenceValidationError as exc:
            self._append_integrity_verification_audit_event(
                trusted_context=trusted_context,
                occurred_from=occurred_from,
                occurred_to=occurred_to,
                checkpoint_id=command.checkpoint_id,
                result="rejected",
                outcome="validation_error",
                event_count=0,
                issue_count=1,
                issue_codes=(exc.code,),
            )
            raise
        valid = not issues
        verification_event = self._append_integrity_verification_audit_event(
            trusted_context=trusted_context,
            occurred_from=occurred_from,
            occurred_to=occurred_to,
            checkpoint_id=command.checkpoint_id,
            result="accepted" if valid else "rejected",
            outcome="valid" if valid else "invalid",
            event_count=len(events),
            issue_count=len(issues),
            issue_codes=tuple(issue.code for issue in issues),
        )
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
                "verification_event_id": verification_event.event_id,
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

    def export_checkpoint_to_worm(
        self,
        command: ExportAuditCheckpointToWormCommand,
        *,
        context: ObservabilityContext,
        trusted_context: PropagatedContext,
    ) -> AuditWormExportApplicationResult:
        started_at = perf_counter()
        worm_export_repository, worm_storage = self._require_worm_dependencies()
        _require_matching_context(context=context, trusted_context=trusted_context)
        _require_scope(trusted_context=trusted_context, required_scope="audit:worm:write")
        try:
            trusted_now = datetime.now(UTC)
            occurred_from, occurred_to = _validate_time_window(
                command.occurred_from, command.occurred_to
            )
            created_at = validate_occurred_at(command.created_at)
            retain_until = validate_retain_until(command.retain_until, now=trusted_now)
            retention_class = validate_retention_class(command.retention_class)
            retention_mode = validate_retention_mode(command.retention_mode)
            legal_hold_reason = validate_legal_hold_reason(
                command.legal_hold_reason,
                legal_hold=command.legal_hold,
            )
            checkpoint = self._get_checkpoint_for_export(
                tenant_id=trusted_context.trusted.tenant_id,
                checkpoint_id=command.checkpoint_id,
                occurred_from=occurred_from,
                occurred_to=occurred_to,
            )
            manifest = _worm_manifest_from_checkpoint(
                checkpoint=checkpoint,
                retention_class=retention_class,
                retention_mode=retention_mode,
                retain_until=retain_until,
                legal_hold=command.legal_hold,
                legal_hold_reason=legal_hold_reason,
                created_at=created_at,
            )
            manifest_body = canonicalize_worm_export_manifest(manifest)
            manifest_digest = calculate_worm_export_manifest_digest(manifest)
            object_key = _validate_worm_object_key_for_tenant(
                command.object_key
                or _default_worm_object_key(
                    tenant_id=trusted_context.trusted.tenant_id,
                    checkpoint=checkpoint,
                ),
                tenant_id=trusted_context.trusted.tenant_id,
                checkpoint_id=checkpoint.checkpoint_id,
            )
            export_id = _worm_export_id(
                tenant_id=trusted_context.trusted.tenant_id,
                checkpoint_id=checkpoint.checkpoint_id,
                occurred_from=occurred_from,
                occurred_to=occurred_to,
            )
            existing_export = worm_export_repository.get_by_checkpoint_window(
                tenant_id=trusted_context.trusted.tenant_id,
                checkpoint_id=checkpoint.checkpoint_id,
                window_started_at=occurred_from,
                window_ended_at=occurred_to,
            )
            if existing_export is not None:
                ensure_not_shortened_retention(
                    existing_retain_until=existing_export.retain_until,
                    requested_retain_until=retain_until,
                )
                _ensure_existing_export_matches_request(
                    existing=existing_export,
                    manifest_digest=manifest_digest,
                    object_key=object_key,
                    retention_class=retention_class,
                    retention_mode=retention_mode,
                    retain_until=retain_until,
                    legal_hold=command.legal_hold,
                    legal_hold_reason=legal_hold_reason,
                    batch_digest=checkpoint.batch_digest,
                )
                replay_issues = _reconcile_worm_export(
                    export=existing_export,
                    storage_object=worm_storage.head_object(
                        tenant_id=trusted_context.trusted.tenant_id,
                        object_key=existing_export.object_key,
                        object_version_id=existing_export.object_version_id,
                    ),
                    checkpoint=checkpoint,
                )
                if replay_issues:
                    raise AuditEvidenceConflictError(
                        "exportação WORM idempotente diverge do storage",
                        code="idempotent_worm_export_storage_mismatch",
                        field_path="export_id",
                    )
                export = existing_export
                outcome = "idempotent"
            else:
                storage_result = worm_storage.put_object(
                    tenant_id=trusted_context.trusted.tenant_id,
                    object_key=object_key,
                    body=manifest_body,
                    retention_mode=retention_mode,
                    retain_until=retain_until,
                    legal_hold=command.legal_hold,
                    legal_hold_reason=legal_hold_reason,
                )
                _ensure_storage_put_matches_manifest(
                    storage_result=storage_result,
                    object_key=object_key,
                    manifest_digest=manifest_digest,
                    retention_mode=retention_mode,
                    retain_until=retain_until,
                    legal_hold=command.legal_hold,
                    legal_hold_reason=legal_hold_reason,
                )
                export = worm_export_repository.append(
                    AuditWormExport(
                        export_id=export_id,
                        tenant_id=trusted_context.trusted.tenant_id,
                        checkpoint_id=checkpoint.checkpoint_id,
                        window_started_at=occurred_from,
                        window_ended_at=occurred_to,
                        object_key=storage_result.object_key,
                        object_version_id=storage_result.object_version_id,
                        manifest_digest=manifest_digest,
                        manifest_version=WORM_MANIFEST_VERSION,
                        retention_class=retention_class,
                        retention_mode=storage_result.retention_mode,
                        retain_until=storage_result.retain_until,
                        legal_hold=storage_result.legal_hold,
                        legal_hold_reason=storage_result.legal_hold_reason,
                        status=AuditWormExportStatus.ACCEPTED,
                        created_at=created_at,
                        event_count=checkpoint.event_count,
                        batch_digest=checkpoint.batch_digest,
                        safe_metadata={"storage_body_digest": storage_result.body_digest},
                    )
                )
                outcome = "accepted"
        except (AuditEvidenceConflictError, AuditEvidenceValidationError) as exc:
            self._append_worm_export_audit_event(
                trusted_context=trusted_context,
                event_type="audit_worm_export.created",
                action="create",
                result="rejected",
                outcome=exc.code,
                checkpoint_id=command.checkpoint_id,
                export_id=None,
                occurred_from=command.occurred_from,
                occurred_to=command.occurred_to,
                object_key="",
                object_version_id="",
                manifest_digest="",
                legal_hold_reason=command.legal_hold_reason,
                issue_codes=(exc.code,),
            )
            raise
        except Exception as exc:
            self._append_worm_export_audit_event(
                trusted_context=trusted_context,
                event_type="audit_worm_export.created",
                action="create",
                result="technical_failure",
                outcome="worm_export_technical_failure",
                checkpoint_id=command.checkpoint_id,
                export_id=None,
                occurred_from=command.occurred_from,
                occurred_to=command.occurred_to,
                object_key="",
                object_version_id="",
                manifest_digest="",
                legal_hold_reason=command.legal_hold_reason,
                issue_codes=("worm_export_technical_failure",),
            )
            raise AuditEvidenceValidationError(
                "falha técnica controlada na exportação WORM",
                code="worm_export_technical_failure",
                field_path="worm_storage",
            ) from exc
        export_event = self._append_worm_export_audit_event(
            trusted_context=trusted_context,
            event_type="audit_worm_export.created",
            action="create",
            result="accepted",
            outcome=outcome,
            checkpoint_id=export.checkpoint_id,
            export_id=export.export_id,
            occurred_from=export.window_started_at,
            occurred_to=export.window_ended_at,
            object_key=export.object_key,
            object_version_id=export.object_version_id,
            manifest_digest=export.manifest_digest,
            legal_hold_reason=export.legal_hold_reason,
            issue_codes=(),
        )
        log = self._log_operation(
            context=context,
            operation="audit_evidence.worm_export.create",
            status="accepted",
            duration_ms=_duration_ms(started_at),
            payload=command,
            extra=_safe_worm_export_details(export)
            | {
                "outcome": outcome,
                "export_event_id": export_event.event_id,
            },
        )
        return AuditWormExportApplicationResult(export=export, logs=(log,))

    def reconcile_worm_export(
        self,
        command: ReconcileAuditWormExportCommand,
        *,
        context: ObservabilityContext,
        trusted_context: PropagatedContext,
    ) -> AuditWormReconciliationApplicationResult:
        started_at = perf_counter()
        worm_export_repository, worm_storage = self._require_worm_dependencies()
        _require_matching_context(context=context, trusted_context=trusted_context)
        _require_any_scope(
            trusted_context=trusted_context,
            required_scopes=("audit:worm:read", "audit:read"),
        )
        export = worm_export_repository.get(
            tenant_id=trusted_context.trusted.tenant_id,
            export_id=command.export_id,
        )
        if export is None:
            self._append_worm_export_audit_event(
                trusted_context=trusted_context,
                event_type="audit_worm_export.reconciled",
                action="reconcile",
                result="rejected",
                outcome="worm_export_not_found",
                checkpoint_id=command.export_id,
                export_id=command.export_id,
                occurred_from=None,
                occurred_to=None,
                object_key="",
                object_version_id="",
                manifest_digest="",
                legal_hold_reason=None,
                issue_codes=("worm_export_not_found",),
            )
            raise AuditEvidenceValidationError(
                "exportação WORM não encontrada",
                code="worm_export_not_found",
                field_path="export_id",
            )
        try:
            storage_object = worm_storage.get_object(
                tenant_id=trusted_context.trusted.tenant_id,
                object_key=export.object_key,
                object_version_id=export.object_version_id,
            )
            checkpoint = None
            if self._checkpoint_repository is not None:
                checkpoint = self._checkpoint_repository.get(
                    tenant_id=trusted_context.trusted.tenant_id,
                    checkpoint_id=export.checkpoint_id,
                )
        except Exception as exc:
            self._append_worm_export_audit_event(
                trusted_context=trusted_context,
                event_type="audit_worm_export.reconciled",
                action="reconcile",
                result="technical_failure",
                outcome="worm_reconciliation_technical_failure",
                checkpoint_id=export.checkpoint_id,
                export_id=export.export_id,
                occurred_from=export.window_started_at,
                occurred_to=export.window_ended_at,
                object_key=export.object_key,
                object_version_id=export.object_version_id,
                manifest_digest=export.manifest_digest,
                legal_hold_reason=export.legal_hold_reason,
                issue_codes=("worm_reconciliation_technical_failure",),
            )
            raise AuditEvidenceValidationError(
                "falha técnica controlada na reconciliação WORM",
                code="worm_reconciliation_technical_failure",
                field_path="worm_storage",
            ) from exc
        issues = _reconcile_worm_export(
            export=export,
            storage_object=storage_object,
            checkpoint=checkpoint,
        )
        valid = not issues
        reconciliation_event = self._append_worm_export_audit_event(
            trusted_context=trusted_context,
            event_type="audit_worm_export.reconciled",
            action="reconcile",
            result="accepted" if valid else "rejected",
            outcome="valid" if valid else "invalid",
            checkpoint_id=export.checkpoint_id,
            export_id=export.export_id,
            occurred_from=export.window_started_at,
            occurred_to=export.window_ended_at,
            object_key=export.object_key,
            object_version_id=export.object_version_id,
            manifest_digest=export.manifest_digest,
            legal_hold_reason=export.legal_hold_reason,
            issue_codes=tuple(issue.code for issue in issues),
        )
        log = self._log_operation(
            context=context,
            operation="audit_evidence.worm_export.reconcile",
            status="accepted" if valid else "rejected",
            duration_ms=_duration_ms(started_at),
            payload=command,
            extra=_safe_worm_export_details(export)
            | {
                "outcome": "valid" if valid else "invalid",
                "issue_count": str(len(issues)),
                "reconciliation_event_id": reconciliation_event.event_id,
            },
        )
        return AuditWormReconciliationApplicationResult(
            valid=valid,
            status="valid" if valid else "invalid",
            export_id=export.export_id,
            checkpoint_id=export.checkpoint_id,
            issues=tuple(issues),
            logs=(log,),
        )

    def _append_integrity_verification_audit_event(
        self,
        *,
        trusted_context: PropagatedContext,
        occurred_from: datetime,
        occurred_to: datetime,
        checkpoint_id: str | None,
        result: str,
        outcome: str,
        event_count: int,
        issue_count: int,
        issue_codes: tuple[str, ...] = (),
    ) -> AuditEvent:
        verification_resource_id = _verification_window_id(
            tenant_id=trusted_context.trusted.tenant_id,
            occurred_from=occurred_from,
            occurred_to=occurred_to,
            checkpoint_id=checkpoint_id,
        )
        return self._repository.append(
            AuditEvent.create(
                event_id=f"audit_evt_integrity_verify_{uuid4().hex}",
                tenant_id=trusted_context.trusted.tenant_id,
                aggregate_type="audit_integrity",
                aggregate_id=verification_resource_id,
                event_type="audit_integrity.verify",
                action="verify",
                resource_type="audit_integrity",
                resource_id=verification_resource_id,
                actor_subject_id=trusted_context.trusted.subject_id,
                source_service=SERVICE_NAME,
                source_kind="system",
                result=result,
                occurred_at=datetime.now(UTC),
                correlation_id=trusted_context.correlation_id,
                trace_id=trusted_context.trace_id,
                request_id=trusted_context.request_id,
                safe_details={
                    "operation": "audit_evidence.integrity.verify",
                    "outcome": outcome,
                    "event_count": str(event_count),
                    "issue_count": str(issue_count),
                    "validation_issue_count": str(len(issue_codes)),
                    "validation_issue_codes": ",".join(issue_codes) if issue_codes else "none",
                    "resource_type": "audit_integrity",
                    "resource_id": verification_resource_id,
                },
            )
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

    def _require_worm_dependencies(
        self,
    ) -> tuple[AuditWormExportRepository, AuditWormStorage]:
        if self._worm_export_repository is None or self._worm_storage is None:
            raise AuditEvidenceValidationError(
                "dependências de exportação WORM não configuradas",
                code="audit_worm_dependencies_missing",
                field_path="worm_export_repository",
            )
        return self._worm_export_repository, self._worm_storage

    def _get_checkpoint_for_export(
        self,
        *,
        tenant_id: str,
        checkpoint_id: str,
        occurred_from: datetime,
        occurred_to: datetime,
    ) -> AuditIntegrityCheckpoint:
        if self._checkpoint_repository is None:
            raise AuditEvidenceValidationError(
                "repositório de checkpoint não configurado",
                code="audit_integrity_checkpoint_dependencies_missing",
                field_path="checkpoint_repository",
            )
        checkpoint = self._checkpoint_repository.get(
            tenant_id=tenant_id,
            checkpoint_id=checkpoint_id,
        )
        if checkpoint is None:
            raise AuditEvidenceValidationError(
                "checkpoint de auditoria não encontrado para exportação WORM",
                code="worm_checkpoint_not_found",
                field_path="checkpoint_id",
            )
        if (
            checkpoint.window_started_at != occurred_from
            or checkpoint.window_ended_at != occurred_to
        ):
            raise AuditEvidenceValidationError(
                "janela de exportação WORM diverge do checkpoint",
                code="worm_checkpoint_window_mismatch",
                field_path="checkpoint_id",
            )
        return checkpoint

    def _append_worm_export_audit_event(
        self,
        *,
        trusted_context: PropagatedContext,
        event_type: str,
        action: str,
        result: str,
        outcome: str,
        checkpoint_id: str,
        export_id: str | None,
        occurred_from: datetime | None,
        occurred_to: datetime | None,
        object_key: str,
        object_version_id: str,
        manifest_digest: str,
        legal_hold_reason: str | None,
        issue_codes: tuple[str, ...],
    ) -> AuditEvent:
        resource_id = _safe_worm_resource_id(
            tenant_id=trusted_context.trusted.tenant_id,
            candidate=export_id or checkpoint_id,
            action=action,
        )
        return self._repository.append(
            AuditEvent.create(
                event_id=f"audit_evt_worm_export_{uuid4().hex}",
                tenant_id=trusted_context.trusted.tenant_id,
                aggregate_type="audit_worm_export",
                aggregate_id=resource_id,
                event_type=event_type,
                action=action,
                resource_type="audit_worm_export",
                resource_id=resource_id,
                actor_subject_id=trusted_context.trusted.subject_id,
                source_service=SERVICE_NAME,
                source_kind="system",
                result=result,
                occurred_at=datetime.now(UTC),
                correlation_id=trusted_context.correlation_id,
                trace_id=trusted_context.trace_id,
                request_id=trusted_context.request_id,
                safe_details={
                    "operation": f"audit_evidence.worm_export.{action}",
                    "outcome": outcome,
                    "checkpoint_id": _safe_detail_value(checkpoint_id),
                    "export_reference": resource_id,
                    "window_started_at": occurred_from.isoformat() if occurred_from else "",
                    "window_ended_at": occurred_to.isoformat() if occurred_to else "",
                    "object_key": _safe_detail_value(object_key),
                    "object_version_id": _safe_detail_value(object_version_id),
                    "manifest_digest": _safe_detail_value(manifest_digest),
                    "legal_hold_reason": _safe_detail_value(legal_hold_reason or ""),
                    "issue_count": str(len(issue_codes)),
                    "validation_issue_count": str(len(issue_codes)),
                    "validation_issue_codes": ",".join(issue_codes) if issue_codes else "none",
                    "resource_type": "audit_worm_export",
                    "resource_id": resource_id,
                },
            )
        )


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


def _require_any_scope(
    *,
    trusted_context: PropagatedContext,
    required_scopes: tuple[str, ...],
) -> None:
    if not any(scope in trusted_context.trusted.scopes for scope in required_scopes):
        joined_scopes = "_or_".join(scope.replace(":", "_") for scope in required_scopes)
        raise AuditEvidenceTenantContextError(
            f"escopo obrigatório ausente: {' ou '.join(required_scopes)}",
            code=f"audit_evidence_missing_scope_{joined_scopes}",
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
    selected_positions = [
        position
        for position, event in enumerate(tenant_chain)
        if occurred_from <= event.occurred_at <= occurred_to
    ]
    if not selected_positions:
        return (), None
    first_position = selected_positions[0]
    last_position = selected_positions[-1]
    predecessor = tenant_chain[first_position - 1] if first_position > 0 else None
    return tuple(tenant_chain[first_position : last_position + 1]), predecessor


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
        if (
            event.integrity_scope != INTEGRITY_SCOPE_TENANT
            or event.hash_algorithm != HASH_ALGORITHM
            or event.canonicalization_version != CANONICALIZATION_VERSION
        ):
            issues.append(
                AuditIntegrityVerificationIssue(
                    code="audit_event_integrity_metadata_mismatch",
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


def _worm_manifest_from_checkpoint(
    *,
    checkpoint: AuditIntegrityCheckpoint,
    retention_class: str,
    retention_mode: WormRetentionMode,
    retain_until: datetime,
    legal_hold: bool,
    legal_hold_reason: str | None,
    created_at: datetime,
) -> AuditWormExportManifest:
    return AuditWormExportManifest.from_checkpoint(
        tenant_id=checkpoint.tenant_id,
        checkpoint_id=checkpoint.checkpoint_id,
        window_started_at=checkpoint.window_started_at,
        window_ended_at=checkpoint.window_ended_at,
        event_count=checkpoint.event_count,
        first_event_id=checkpoint.first_event_id,
        last_event_id=checkpoint.last_event_id,
        first_event_hash=checkpoint.first_event_hash,
        last_event_hash=checkpoint.last_event_hash,
        batch_digest=checkpoint.batch_digest,
        checkpoint_signature=checkpoint.signature,
        checkpoint_signature_key_ref=checkpoint.signature_key_ref,
        checkpoint_signature_algorithm=checkpoint.signature_algorithm,
        retention_class=retention_class,
        retention_mode=retention_mode,
        retain_until=retain_until,
        legal_hold=legal_hold,
        legal_hold_reason=legal_hold_reason,
        created_at=created_at,
    )


def _default_worm_object_key(
    *,
    tenant_id: str,
    checkpoint: AuditIntegrityCheckpoint,
) -> str:
    return (
        f"tenants/{tenant_id}/audit/"
        f"year={checkpoint.window_ended_at.year:04d}/"
        f"month={checkpoint.window_ended_at.month:02d}/"
        f"checkpoint={checkpoint.checkpoint_id}/manifest.json"
    )


def _worm_export_id(
    *,
    tenant_id: str,
    checkpoint_id: str,
    occurred_from: datetime,
    occurred_to: datetime,
) -> str:
    material = "|".join(
        (
            tenant_id,
            checkpoint_id,
            occurred_from.isoformat(),
            occurred_to.isoformat(),
        )
    )
    return f"audit_worm_export_{hashlib.sha256(material.encode('utf-8')).hexdigest()[:32]}"


def _ensure_existing_export_matches_request(
    *,
    existing: AuditWormExport,
    manifest_digest: str,
    object_key: str,
    retention_class: str,
    retention_mode: WormRetentionMode,
    retain_until: datetime,
    legal_hold: bool,
    legal_hold_reason: str | None,
    batch_digest: str,
) -> None:
    comparable_fields_match = (
        existing.manifest_digest == manifest_digest,
        existing.object_key == object_key,
        existing.retention_class == retention_class,
        existing.retention_mode == retention_mode,
        existing.retain_until == retain_until,
        existing.legal_hold == legal_hold,
        existing.legal_hold_reason == legal_hold_reason,
        existing.batch_digest == batch_digest,
    )
    if not all(comparable_fields_match):
        raise AuditEvidenceConflictError(
            "exportação WORM divergente para checkpoint/janela",
            code="conflicting_worm_export",
            field_path="checkpoint_id",
        )


def _validate_worm_object_key_for_tenant(
    value: str,
    *,
    tenant_id: str,
    checkpoint_id: str,
) -> str:
    object_key = validate_worm_object_key(value)
    match = _WORM_OBJECT_KEY_PATTERN.fullmatch(object_key)
    if (
        match is None
        or match.group("tenant_id") != tenant_id
        or match.group("checkpoint_id") != checkpoint_id
        or not 1 <= int(match.group("month")) <= 12
    ):
        raise AuditEvidenceValidationError(
            "object key WORM diverge do padrão técnico do tenant/checkpoint",
            code="invalid_worm_object_key",
            field_path="object_key",
        )
    return object_key


def _ensure_storage_put_matches_manifest(
    *,
    storage_result: Any,
    object_key: str,
    manifest_digest: str,
    retention_mode: WormRetentionMode,
    retain_until: datetime,
    legal_hold: bool,
    legal_hold_reason: str | None,
) -> None:
    mismatches = (
        storage_result.object_key != object_key,
        storage_result.body_digest != manifest_digest,
        storage_result.retention_mode != retention_mode,
        storage_result.retain_until != retain_until,
        storage_result.legal_hold != legal_hold,
        storage_result.legal_hold_reason != legal_hold_reason,
    )
    if any(mismatches):
        raise AuditEvidenceConflictError(
            "storage WORM retornou metadados divergentes",
            code="worm_storage_metadata_mismatch",
            field_path="worm_storage",
        )


def _reconcile_worm_export(
    *,
    export: AuditWormExport,
    storage_object: Any,
    checkpoint: AuditIntegrityCheckpoint | None,
) -> tuple[AuditWormReconciliationIssue, ...]:
    issues: list[AuditWormReconciliationIssue] = []
    if storage_object is None:
        return (
            AuditWormReconciliationIssue(
                code="worm_object_not_found",
                export_id=export.export_id,
                checkpoint_id=export.checkpoint_id,
            ),
        )
    recomputed_body_digest = hashlib.sha256(storage_object.body.encode("utf-8")).hexdigest()
    if recomputed_body_digest != export.manifest_digest:
        issues.append(
            AuditWormReconciliationIssue(
                code="worm_manifest_digest_mismatch",
                export_id=export.export_id,
                checkpoint_id=export.checkpoint_id,
            )
        )
    if storage_object.body_digest != recomputed_body_digest:
        issues.append(
            AuditWormReconciliationIssue(
                code="worm_storage_digest_mismatch",
                export_id=export.export_id,
                checkpoint_id=export.checkpoint_id,
            )
        )
    try:
        manifest_payload = json.loads(storage_object.body)
    except json.JSONDecodeError:
        manifest_payload = {}
        issues.append(
            AuditWormReconciliationIssue(
                code="worm_manifest_unreadable",
                export_id=export.export_id,
                checkpoint_id=export.checkpoint_id,
            )
        )
    if not isinstance(manifest_payload, dict):
        manifest_payload = {}
        issues.append(
            AuditWormReconciliationIssue(
                code="worm_manifest_unreadable",
                export_id=export.export_id,
                checkpoint_id=export.checkpoint_id,
            )
        )
    if storage_object.object_key != export.object_key:
        issues.append(
            AuditWormReconciliationIssue(
                code="worm_object_key_mismatch",
                export_id=export.export_id,
                checkpoint_id=export.checkpoint_id,
            )
        )
    if storage_object.object_version_id != export.object_version_id:
        issues.append(
            AuditWormReconciliationIssue(
                code="worm_object_version_mismatch",
                export_id=export.export_id,
                checkpoint_id=export.checkpoint_id,
            )
        )
    if manifest_payload.get("manifest_version") != export.manifest_version:
        issues.append(
            AuditWormReconciliationIssue(
                code="worm_manifest_version_mismatch",
                export_id=export.export_id,
                checkpoint_id=export.checkpoint_id,
            )
        )
    if manifest_payload.get("tenant_id") != export.tenant_id:
        issues.append(
            AuditWormReconciliationIssue(
                code="worm_manifest_tenant_mismatch",
                export_id=export.export_id,
                checkpoint_id=export.checkpoint_id,
            )
        )
    if manifest_payload.get("checkpoint_id") != export.checkpoint_id:
        issues.append(
            AuditWormReconciliationIssue(
                code="worm_manifest_checkpoint_mismatch",
                export_id=export.export_id,
                checkpoint_id=export.checkpoint_id,
            )
        )
    if manifest_payload.get("window_started_at") != export.window_started_at.isoformat():
        issues.append(
            AuditWormReconciliationIssue(
                code="worm_manifest_window_mismatch",
                export_id=export.export_id,
                checkpoint_id=export.checkpoint_id,
            )
        )
    if manifest_payload.get("window_ended_at") != export.window_ended_at.isoformat():
        issues.append(
            AuditWormReconciliationIssue(
                code="worm_manifest_window_mismatch",
                export_id=export.export_id,
                checkpoint_id=export.checkpoint_id,
            )
        )
    if manifest_payload.get("event_count") != export.event_count:
        issues.append(
            AuditWormReconciliationIssue(
                code="worm_manifest_event_count_mismatch",
                export_id=export.export_id,
                checkpoint_id=export.checkpoint_id,
            )
        )
    if manifest_payload.get("batch_digest") != export.batch_digest:
        issues.append(
            AuditWormReconciliationIssue(
                code="worm_manifest_batch_digest_mismatch",
                export_id=export.export_id,
                checkpoint_id=export.checkpoint_id,
            )
        )
    if manifest_payload.get("retention_mode") != export.retention_mode.value:
        issues.append(
            AuditWormReconciliationIssue(
                code="worm_manifest_retention_mode_mismatch",
                export_id=export.export_id,
                checkpoint_id=export.checkpoint_id,
            )
        )
    if manifest_payload.get("retain_until") != export.retain_until.isoformat():
        issues.append(
            AuditWormReconciliationIssue(
                code="worm_manifest_retain_until_mismatch",
                export_id=export.export_id,
                checkpoint_id=export.checkpoint_id,
            )
        )
    if manifest_payload.get("legal_hold") != export.legal_hold:
        issues.append(
            AuditWormReconciliationIssue(
                code="worm_manifest_legal_hold_mismatch",
                export_id=export.export_id,
                checkpoint_id=export.checkpoint_id,
            )
        )
    if manifest_payload.get("legal_hold_reason") != export.legal_hold_reason:
        issues.append(
            AuditWormReconciliationIssue(
                code="worm_manifest_legal_hold_reason_mismatch",
                export_id=export.export_id,
                checkpoint_id=export.checkpoint_id,
            )
        )
    if storage_object.retention_mode != export.retention_mode:
        issues.append(
            AuditWormReconciliationIssue(
                code="worm_retention_mode_mismatch",
                export_id=export.export_id,
                checkpoint_id=export.checkpoint_id,
            )
        )
    if storage_object.retain_until != export.retain_until:
        issues.append(
            AuditWormReconciliationIssue(
                code="worm_retain_until_mismatch",
                export_id=export.export_id,
                checkpoint_id=export.checkpoint_id,
            )
        )
    if storage_object.legal_hold != export.legal_hold:
        issues.append(
            AuditWormReconciliationIssue(
                code="worm_legal_hold_mismatch",
                export_id=export.export_id,
                checkpoint_id=export.checkpoint_id,
            )
        )
    if storage_object.legal_hold_reason != export.legal_hold_reason:
        issues.append(
            AuditWormReconciliationIssue(
                code="worm_legal_hold_reason_mismatch",
                export_id=export.export_id,
                checkpoint_id=export.checkpoint_id,
            )
        )
    if checkpoint is None:
        issues.append(
            AuditWormReconciliationIssue(
                code="worm_checkpoint_not_found",
                export_id=export.export_id,
                checkpoint_id=export.checkpoint_id,
            )
        )
    elif (
        checkpoint.batch_digest != export.batch_digest
        or checkpoint.event_count != export.event_count
        or checkpoint.window_started_at != export.window_started_at
        or checkpoint.window_ended_at != export.window_ended_at
    ):
        issues.append(
            AuditWormReconciliationIssue(
                code="worm_checkpoint_metadata_mismatch",
                export_id=export.export_id,
                checkpoint_id=export.checkpoint_id,
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


def _safe_worm_export_details(export: AuditWormExport) -> dict[str, Any]:
    return {
        "export_id": export.export_id,
        "tenant_id": export.tenant_id,
        "checkpoint_id": export.checkpoint_id,
        "object_key": export.object_key,
        "object_version_id": export.object_version_id,
        "manifest_digest": export.manifest_digest,
        "manifest_version": export.manifest_version,
        "retention_class": export.retention_class,
        "retention_mode": export.retention_mode.value,
        "retain_until": export.retain_until.isoformat(),
        "legal_hold": str(export.legal_hold).lower(),
        "legal_hold_reason": export.legal_hold_reason or "",
        "event_count": str(export.event_count),
        "batch_digest": export.batch_digest,
    }


def _safe_worm_resource_id(*, tenant_id: str, candidate: str, action: str) -> str:
    try:
        return validate_aggregate_id(candidate)
    except AuditEvidenceValidationError:
        material = "|".join((tenant_id, action, candidate))
        digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:32]
        return f"audit_worm_{action}_{digest}"


def _safe_detail_value(value: str) -> str:
    if not value:
        return ""
    if "@" in value or len(value) > 256:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()
    return value


def _verification_window_id(
    *,
    tenant_id: str,
    occurred_from: datetime,
    occurred_to: datetime,
    checkpoint_id: str | None,
) -> str:
    if checkpoint_id:
        return checkpoint_id
    material = "|".join(
        (
            tenant_id,
            occurred_from.isoformat(),
            occurred_to.isoformat(),
        )
    )
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:32]
    return f"audit_integrity_window_{digest}"


def _duration_ms(started_at: float) -> float:
    return round((perf_counter() - started_at) * 1000, 3)
