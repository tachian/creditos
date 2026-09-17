from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from datetime import UTC, datetime
from secrets import token_hex

from creditos_audit_evidence.application.service import (
    AuditEvidenceApplicationService,
    RegisterAuditEventCommand,
)
from creditos_audit_evidence.domain.entities import OperationalEvidenceReference
from creditos_observability.context import ObservabilityContext
from creditos_security import PropagatedContext, TrustedContext

from creditos_automated_review.application.ports import AutomatedReviewAuditIntent

_SERVICE_NAME = "automated_review"
_TRACE_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")
_SPAN_ID_PATTERN = re.compile(r"^[0-9a-f]{16}$")
_TRACE_FLAGS_PATTERN = re.compile(r"^[0-9a-f]{2}$")


class AuditEvidenceAutomatedReviewAuditPublisher:
    def __init__(
        self,
        *,
        audit_service: AuditEvidenceApplicationService,
        clock: Callable[[], datetime] | None = None,
        occurrence_token_factory: Callable[[], str] | None = None,
        source_kind: str = "grpc",
    ) -> None:
        self._audit_service = audit_service
        self._clock = clock or (lambda: datetime.now(UTC))
        self._occurrence_token_factory = occurrence_token_factory or (lambda: token_hex(8))
        self._source_kind = source_kind

    def publish(self, event: AutomatedReviewAuditIntent) -> None:
        occurrence_token = self._occurrence_token_factory()
        trace_id = _trace_id_from_traceparent(event.traceparent)
        context = ObservabilityContext.new(
            correlation_id=event.correlation_id,
            request_id=event.request_id,
            trace_id=trace_id,
            tenant_id=event.tenant_id,
            tenant_isolation_tier=event.tenant_isolation_tier,
        )
        trusted_context = PropagatedContext(
            trusted=TrustedContext(
                tenant_id=event.tenant_id,
                tenant_isolation_tier=event.tenant_isolation_tier,
                subject_id=event.actor_subject_id,
                scopes=("audit:write",),
                roles=("audit-writer",),
                client_id=_SERVICE_NAME,
                principal_type="m2m",
            ),
            correlation_id=event.correlation_id,
            request_id=event.request_id,
            traceparent=event.traceparent,
        )
        self._audit_service.register_event(
            RegisterAuditEventCommand(
                event_id=_event_id(event, occurrence_token=occurrence_token),
                aggregate_type="review_agent_config",
                aggregate_id=_audit_resource_id(event.review_agent_config_id),
                event_type=event.event_type,
                action=_action_for(event),
                resource_type="review_agent_config",
                resource_id=_audit_resource_id(event.review_agent_config_version_id),
                source_service=_SERVICE_NAME,
                source_kind=self._source_kind,
                result=_result_for(event),
                occurred_at=_occurred_at_for(event),
                safe_details=_safe_details_for(event),
                operational_evidence_refs=(
                    OperationalEvidenceReference(kind="trace", reference=trace_id, source="otel"),
                ),
            ),
            context=context,
            trusted_context=trusted_context,
        )


def _event_id(event: AutomatedReviewAuditIntent, *, occurrence_token: str) -> str:
    event_token = event.event_type.replace(".", "_")
    fingerprint = hashlib.sha256(
        json.dumps(
            {
                "correlation_id": event.correlation_id,
                "event_type": event.event_type,
                "occurrence_token": occurrence_token,
                "request_id": event.request_id,
                "review_agent_config_id": event.review_agent_config_id,
                "review_agent_config_version_id": event.review_agent_config_version_id,
                "traceparent": event.traceparent,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()[:32]
    return f"audit_evt_{event_token}_{fingerprint}"


def _audit_resource_id(value: str) -> str:
    if len(value) <= 128:
        return value
    fingerprint = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return f"review_cfg_ref_{fingerprint}"


def _safe_details_for(event: AutomatedReviewAuditIntent) -> dict[str, str]:
    authoritative_details = {
        "review_agent_config_id": event.review_agent_config_id,
        "review_agent_config_version_id": event.review_agent_config_version_id,
        "change_summary": event.change_summary,
        "previous_revision": str(event.previous_revision),
        "resulting_revision": str(event.resulting_revision),
    }
    for key, value in authoritative_details.items():
        if key in event.safe_details and event.safe_details[key] != value:
            raise ValueError(f"safe_details.{key} diverge do campo autoritativo")
    return {**event.safe_details, **authoritative_details}


def _action_for(event: AutomatedReviewAuditIntent) -> str:
    operation = event.safe_details.get("operation", event.event_type)
    if operation.endswith(".create") or event.event_type.endswith(".created"):
        return "create"
    if operation.endswith(".update") or event.event_type.endswith(".updated"):
        return "update"
    if operation.endswith(".create_version") or event.event_type.endswith(".version_created"):
        return "create"
    if operation.endswith(".publish") or event.event_type.endswith(".published"):
        return "publish"
    if event.event_type.endswith(".rejected"):
        return "execute"
    return "update"


def _result_for(event: AutomatedReviewAuditIntent) -> str:
    status = event.safe_details.get("status", "")
    if status in {"blocked", "failed", "technical_failure"}:
        return status
    if event.event_type.endswith(".blocked"):
        return "blocked"
    if event.event_type.endswith(".failed"):
        return "failed"
    if event.event_type.endswith(".rejected"):
        return "rejected"
    return "accepted"


def _occurred_at_for(event: AutomatedReviewAuditIntent) -> datetime:
    occurred_at = datetime.fromisoformat(event.occurred_at)
    if occurred_at.tzinfo is None:
        raise ValueError("occurred_at deve conter timezone")
    return occurred_at.astimezone(UTC)


def _trace_id_from_traceparent(traceparent: str) -> str:
    parts = traceparent.split("-")
    if (
        len(parts) != 4
        or parts[0] != "00"
        or not _is_valid_trace_id(parts[1])
        or not _is_valid_span_id(parts[2])
        or not _TRACE_FLAGS_PATTERN.fullmatch(parts[3])
    ):
        raise ValueError("traceparent inválido")
    return parts[1]


def _is_valid_trace_id(trace_id: str) -> bool:
    return bool(_TRACE_ID_PATTERN.fullmatch(trace_id) and trace_id != "0" * 32)


def _is_valid_span_id(span_id: str) -> bool:
    return bool(_SPAN_ID_PATTERN.fullmatch(span_id) and span_id != "0" * 16)
