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

from creditos_decision.application.ports import (
    CreditDecisionAuditIntent,
    CreditPolicyAuditIntent,
    CreditPolicyAuditPublisher,
    DecisionAuditIntent,
    PolicySimulationAuditIntent,
    ReasonCodeCatalogAuditIntent,
)

_SERVICE_NAME = "decision"
_TRACE_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")
_SPAN_ID_PATTERN = re.compile(r"^[0-9a-f]{16}$")
_TRACE_FLAGS_PATTERN = re.compile(r"^[0-9a-f]{2}$")


class CompositeDecisionAuditPublisher:
    def __init__(
        self,
        *,
        decision_publisher: CreditPolicyAuditPublisher,
        fallback_publisher: CreditPolicyAuditPublisher,
        sensitive_change_publisher: CreditPolicyAuditPublisher | None = None,
    ) -> None:
        self._decision_publisher = decision_publisher
        self._sensitive_change_publisher = sensitive_change_publisher
        self._fallback_publisher = fallback_publisher

    def publish(self, event: DecisionAuditIntent) -> None:
        if isinstance(event, CreditDecisionAuditIntent):
            self._decision_publisher.publish(event)
            return
        if isinstance(
            event,
            CreditPolicyAuditIntent | ReasonCodeCatalogAuditIntent | PolicySimulationAuditIntent,
        ):
            if self._sensitive_change_publisher is None:
                raise RuntimeError("publisher oficial de alterações sensíveis não configurado")
            self._sensitive_change_publisher.publish(event)
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


class AuditEvidenceDecisionSensitiveChangeAuditPublisher:
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
        if isinstance(event, CreditDecisionAuditIntent):
            raise TypeError("adapter suporta apenas alterações sensíveis de governança")
        if not isinstance(
            event,
            CreditPolicyAuditIntent | ReasonCodeCatalogAuditIntent | PolicySimulationAuditIntent,
        ):
            raise TypeError("intent de auditoria sensível não suportada")
        occurrence_token = self._occurrence_token_factory()
        trace_id = _trace_id_from_traceparent(event.traceparent)
        context = _observability_context_for(event, trace_id=trace_id)
        trusted_context = _trusted_context_for(event)
        self._audit_service.register_event(
            RegisterAuditEventCommand(
                event_id=_sensitive_change_event_id(event, occurrence_token=occurrence_token),
                aggregate_type=_sensitive_change_aggregate_type(event),
                aggregate_id=_sensitive_change_aggregate_id(event),
                event_type=event.event_type,
                action=_sensitive_change_action_for(event),
                resource_type=_sensitive_change_resource_type(event),
                resource_id=_sensitive_change_resource_id(event),
                source_service=_SERVICE_NAME,
                source_kind=self._source_kind,
                result=_sensitive_change_result_for(event),
                occurred_at=self._clock(),
                safe_details=_sensitive_change_safe_details_for(event),
                operational_evidence_refs=(
                    OperationalEvidenceReference(kind="trace", reference=trace_id, source="otel"),
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


def _sensitive_change_event_id(
    event: CreditPolicyAuditIntent | ReasonCodeCatalogAuditIntent | PolicySimulationAuditIntent,
    *,
    occurrence_token: str,
) -> str:
    event_token = event.event_type.replace(".", "_")
    fingerprint = hashlib.sha256(
        json.dumps(
            {
                "correlation_id": event.correlation_id,
                "event_type": event.event_type,
                "occurrence_token": occurrence_token,
                "operation": event.safe_details.get("operation"),
                "request_id": event.request_id,
                "resource_id": _sensitive_change_resource_id(event),
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


def _sensitive_change_safe_details_for(
    event: CreditPolicyAuditIntent | ReasonCodeCatalogAuditIntent | PolicySimulationAuditIntent,
) -> dict[str, str]:
    if isinstance(event, CreditPolicyAuditIntent):
        authoritative_details = {
            "policy_id": event.policy_id,
            "policy_version_id": event.policy_version_id,
        }
    elif isinstance(event, ReasonCodeCatalogAuditIntent):
        authoritative_details = {
            "catalog_id": event.catalog_id,
            "catalog_version_id": event.catalog_version_id,
        }
    else:
        authoritative_details = {
            "simulation_id": event.simulation_id,
            "policy_id": event.policy_id,
            "policy_version_id": event.policy_version_id,
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


def _sensitive_change_action_for(
    event: CreditPolicyAuditIntent | ReasonCodeCatalogAuditIntent | PolicySimulationAuditIntent,
) -> str:
    operation = event.safe_details.get("operation", event.event_type)
    if operation.endswith(".create_draft") or event.event_type.endswith(".created"):
        return "create"
    if operation.endswith(".update_draft") or event.event_type.endswith(".updated"):
        return "update"
    if operation.endswith(".create_version") or event.event_type.endswith(".versioned"):
        return "create"
    if operation.endswith(".publish") or event.event_type.endswith(".published"):
        return "publish"
    if "simulation" in event.event_type:
        return "execute"
    if event.event_type.endswith(".rejected"):
        return "execute"
    return "update"


def _result_for(event: CreditDecisionAuditIntent) -> str:
    if event.event_type in {"credit_decision.completed", "credit_decision.explanation_retrieved"}:
        return "accepted"
    if event.event_type == "credit_decision.rejected":
        if _is_technical_rejection(event.safe_details.get("rejection_reason", "")):
            return "technical_failure"
        return "rejected"
    return "technical_failure"


def _sensitive_change_result_for(
    event: CreditPolicyAuditIntent | ReasonCodeCatalogAuditIntent | PolicySimulationAuditIntent,
) -> str:
    status = event.safe_details.get("status", "")
    if status in {"blocked", "failed", "technical_failure"}:
        return status
    if event.event_type.endswith(".blocked"):
        return "blocked"
    if event.event_type.endswith(".failed"):
        return "failed"
    if event.event_type.endswith(".rejected"):
        reason = event.safe_details.get("rejection_reason", "")
        if _is_technical_rejection(reason):
            return "technical_failure"
        return "rejected"
    return "accepted"


def _sensitive_change_aggregate_type(
    event: CreditPolicyAuditIntent | ReasonCodeCatalogAuditIntent | PolicySimulationAuditIntent,
) -> str:
    if isinstance(event, CreditPolicyAuditIntent):
        return "credit_policy"
    if isinstance(event, ReasonCodeCatalogAuditIntent):
        return "reason_code_catalog"
    return "policy_simulation"


def _sensitive_change_aggregate_id(
    event: CreditPolicyAuditIntent | ReasonCodeCatalogAuditIntent | PolicySimulationAuditIntent,
) -> str:
    if isinstance(event, CreditPolicyAuditIntent):
        return _audit_resource_id(event.policy_id)
    if isinstance(event, ReasonCodeCatalogAuditIntent):
        return _audit_resource_id(event.catalog_id)
    return _audit_resource_id(event.simulation_id)


def _sensitive_change_resource_type(
    event: CreditPolicyAuditIntent | ReasonCodeCatalogAuditIntent | PolicySimulationAuditIntent,
) -> str:
    if isinstance(event, CreditPolicyAuditIntent):
        return "credit_policy"
    if isinstance(event, ReasonCodeCatalogAuditIntent):
        return "reason_code_catalog"
    return "policy_simulation"


def _sensitive_change_resource_id(
    event: CreditPolicyAuditIntent | ReasonCodeCatalogAuditIntent | PolicySimulationAuditIntent,
) -> str:
    if isinstance(event, CreditPolicyAuditIntent):
        return _audit_resource_id(event.policy_version_id)
    if isinstance(event, ReasonCodeCatalogAuditIntent):
        return _audit_resource_id(event.catalog_version_id)
    return _audit_resource_id(event.simulation_id)


def _observability_context_for(
    event: CreditDecisionAuditIntent
    | CreditPolicyAuditIntent
    | ReasonCodeCatalogAuditIntent
    | PolicySimulationAuditIntent,
    *,
    trace_id: str,
) -> ObservabilityContext:
    return ObservabilityContext.new(
        correlation_id=event.correlation_id,
        request_id=event.request_id,
        trace_id=trace_id,
        tenant_id=event.tenant_id,
        tenant_isolation_tier=event.tenant_isolation_tier,
    )


def _trusted_context_for(
    event: CreditDecisionAuditIntent
    | CreditPolicyAuditIntent
    | ReasonCodeCatalogAuditIntent
    | PolicySimulationAuditIntent,
) -> PropagatedContext:
    return PropagatedContext(
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
