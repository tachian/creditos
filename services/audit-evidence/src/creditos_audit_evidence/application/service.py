from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from time import perf_counter
from typing import Any

from creditos_observability import ObservabilityContext
from creditos_observability.logging import build_structured_log
from creditos_security import PropagatedContext

from creditos_audit_evidence.application.ports import AuditEventRepository
from creditos_audit_evidence.domain.entities import AuditEvent, OperationalEvidenceReference
from creditos_audit_evidence.domain.errors import (
    AuditEvidenceTenantContextError,
    AuditEvidenceValidationError,
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
class AuditEventApplicationResult:
    event: AuditEvent
    logs: tuple[dict[str, Any], ...]


@dataclass(frozen=True, slots=True)
class AuditEventListApplicationResult:
    events: tuple[AuditEvent, ...]
    logs: tuple[dict[str, Any], ...]


class AuditEvidenceApplicationService:
    def __init__(
        self,
        *,
        repository: AuditEventRepository,
        environment: str,
    ) -> None:
        self._repository = repository
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
        self._repository.append(event)
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
        event = self._repository.get(
            tenant_id=trusted_context.trusted.tenant_id,
            event_id=command.event_id,
        )
        if event is None:
            return None
        log = self._log_operation(
            context=context,
            operation="audit_evidence.event.get",
            status="accepted",
            duration_ms=_duration_ms(started_at),
            payload=command,
            extra=_safe_event_details(event),
        )
        return AuditEventApplicationResult(event=event, logs=(log,))

    def list_by_aggregate(
        self,
        command: ListAuditEventsByAggregateCommand,
        *,
        context: ObservabilityContext,
        trusted_context: PropagatedContext,
    ) -> AuditEventListApplicationResult:
        started_at = perf_counter()
        _require_matching_context(context=context, trusted_context=trusted_context)
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
        "operational_evidence_ref_count": str(len(event.operational_evidence_refs)),
    }


def _duration_ms(started_at: float) -> float:
    return round((perf_counter() - started_at) * 1000, 3)
