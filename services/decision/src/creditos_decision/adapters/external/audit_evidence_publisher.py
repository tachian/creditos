from __future__ import annotations

import hashlib
import json
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

from creditos_decision.application.ports import (
    CreditDecisionAuditIntent,
    CreditPolicyAuditPublisher,
    DecisionAuditIntent,
)

_SERVICE_NAME = "decision"
_AUTHORITATIVE_SAFE_DETAILS = frozenset(
    {
        "decision_id",
        "proposal_id",
        "policy_id",
        "policy_version_id",
        "reason_code_catalog_id",
        "reason_code_catalog_version_id",
    }
)


class CompositeDecisionAuditPublisher:
    def __init__(
        self,
        *,
        decision_publisher: CreditPolicyAuditPublisher,
        fallback_publisher: CreditPolicyAuditPublisher,
    ) -> None:
        self._decision_publisher = decision_publisher
        self._fallback_publisher = fallback_publisher

    def publish(self, event: DecisionAuditIntent) -> None:
        if isinstance(event, CreditDecisionAuditIntent):
            self._decision_publisher.publish(event)
            return
        self._fallback_publisher.publish(event)


class AuditEvidenceDecisionAuditPublisher:
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

    def publish(self, event: DecisionAuditIntent) -> None:
        if not isinstance(event, CreditDecisionAuditIntent):
            raise TypeError("adapter suporta apenas auditoria de decisão de crédito")
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
                aggregate_type="credit_decision",
                aggregate_id=_audit_resource_id(event.decision_id),
                event_type=event.event_type,
                action=_action_for(event),
                resource_type="credit_decision",
                resource_id=_audit_resource_id(event.decision_id),
                source_service=_SERVICE_NAME,
                source_kind=self._source_kind,
                result=_result_for(event),
                occurred_at=self._clock(),
                safe_details=_safe_details_for(event),
                operational_evidence_refs=(
                    OperationalEvidenceReference(
                        kind="trace",
                        reference=trace_id,
                        source="otel",
                    ),
                ),
            ),
            context=context,
            trusted_context=trusted_context,
        )


def _event_id(event: CreditDecisionAuditIntent, *, occurrence_token: str) -> str:
    event_token = event.event_type.replace(".", "_")
    fingerprint = hashlib.sha256(
        json.dumps(
            {
                "correlation_id": event.correlation_id,
                "decision_id": event.decision_id,
                "event_type": event.event_type,
                "operation": event.safe_details.get("operation"),
                "occurrence_token": occurrence_token,
                "request_id": event.request_id,
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
    return f"decision_ref_{fingerprint}"


def _safe_details_for(event: CreditDecisionAuditIntent) -> dict[str, str]:
    authoritative_details = {
        "decision_id": event.decision_id,
        "proposal_id": event.proposal_id,
        "policy_id": event.policy_id,
        "policy_version_id": event.policy_version_id,
        "reason_code_catalog_id": event.reason_code_catalog_id,
        "reason_code_catalog_version_id": event.reason_code_catalog_version_id,
    }
    for key, value in authoritative_details.items():
        if key in event.safe_details and event.safe_details[key] != value:
            raise ValueError(f"safe_details.{key} diverge do campo autoritativo")
    return {**event.safe_details, **authoritative_details}


def _action_for(event: CreditDecisionAuditIntent) -> str:
    operation = event.safe_details.get("operation", "")
    if operation == "credit_decision.explanation.get":
        return "read"
    return "execute"


def _result_for(event: CreditDecisionAuditIntent) -> str:
    if event.event_type in {"credit_decision.completed", "credit_decision.explanation_retrieved"}:
        return "accepted"
    if event.event_type == "credit_decision.rejected":
        if _is_technical_rejection(event.safe_details.get("rejection_reason", "")):
            return "technical_failure"
        return "rejected"
    return "technical_failure"


def _is_technical_rejection(reason: str) -> bool:
    if reason in {
        "credit_decision_audit_write_failed",
        "reason_code_catalog_not_found",
        "RuntimeError",
        "Exception",
    }:
        return True
    return reason.endswith("Error")


def _trace_id_from_traceparent(traceparent: str) -> str:
    parts = traceparent.split("-")
    if len(parts) != 4:
        raise ValueError("traceparent inválido")
    return parts[1]
