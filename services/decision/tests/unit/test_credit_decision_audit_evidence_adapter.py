from __future__ import annotations

from datetime import UTC, datetime

import pytest
from creditos_audit_evidence.adapters.persistence import InMemoryAuditEventRepository
from creditos_audit_evidence.application.service import AuditEvidenceApplicationService
from creditos_audit_evidence.domain.errors import AuditEvidenceValidationError
from creditos_decision.adapters.external.audit_evidence_publisher import (
    AuditEvidenceDecisionAuditPublisher,
    CompositeDecisionAuditPublisher,
)
from creditos_decision.application.ports import CreditDecisionAuditIntent, CreditPolicyAuditIntent

NOW = datetime(2026, 9, 16, 12, 0, tzinfo=UTC)
TRACEPARENT = "00-1234567890abcdef1234567890abcdef-1234567890abcdef-01"


def test_credit_decision_completed_intent_appends_official_audit_event() -> None:
    repository = InMemoryAuditEventRepository()
    audit_service = AuditEvidenceApplicationService(repository=repository, environment="test")
    publisher = AuditEvidenceDecisionAuditPublisher(
        audit_service=audit_service,
        clock=lambda: NOW,
    )

    publisher.publish(_decision_intent())

    events = repository.list_by_aggregate(
        tenant_id="tenant_alpha",
        aggregate_type="credit_decision",
        aggregate_id="decision_personal_credit_001",
    )
    assert len(events) == 1
    event = events[0]
    assert event.event_type == "credit_decision.completed"
    assert event.action == "execute"
    assert event.resource_type == "credit_decision"
    assert event.resource_id == "decision_personal_credit_001"
    assert event.actor_subject_id == "user_credit_manager"
    assert event.source_service == "decision"
    assert event.source_kind == "grpc"
    assert event.result == "accepted"
    assert event.correlation_id == "corr_1234567890abcdef"
    assert event.trace_id == "1234567890abcdef1234567890abcdef"
    assert event.request_id == "req_1234567890abcdef"
    assert event.safe_details["decision_id"] == "decision_personal_credit_001"
    assert event.safe_details["proposal_id"] == "proposal_personal_credit_001"
    assert event.safe_details["policy_id"] == "pol_personal_credit_default"
    assert event.safe_details["policy_version_id"] == "polver_personal_credit_default_v1"
    assert event.safe_details["policy_revision"] == "3"
    assert event.safe_details["reason_code_catalog_id"] == "rcc_personal_credit_default"
    assert (
        event.safe_details["reason_code_catalog_version_id"] == "rccver_personal_credit_default_v1"
    )
    assert event.safe_details["reason_code_refs"] == "rc_min_income"
    assert event.safe_details["triggered_rule_ids"] == "rule_min_income"
    assert event.safe_details["fingerprint"] == "fp_decision_001"
    assert event.safe_details["operation"] == "credit_decision.execute"
    assert event.safe_details["status"] == "completed"
    assert event.operational_evidence_refs[0].kind == "trace"
    assert event.operational_evidence_refs[0].reference == ("1234567890abcdef1234567890abcdef")


def test_credit_decision_rejected_intent_maps_to_rejected_official_audit_event() -> None:
    repository = InMemoryAuditEventRepository()
    audit_service = AuditEvidenceApplicationService(repository=repository, environment="test")
    publisher = AuditEvidenceDecisionAuditPublisher(
        audit_service=audit_service,
        clock=lambda: NOW,
    )

    publisher.publish(
        _decision_intent(
            event_type="credit_decision.rejected",
            safe_details={
                "decision_id": "decision_personal_credit_001",
                "operation": "credit_decision.execute",
                "product_type": "personal_credit",
                "proposal_id": "proposal_personal_credit_001",
                "rejection_reason": "credit_decision_not_found",
                "status": "rejected",
            },
        )
    )

    events = repository.list_by_aggregate(
        tenant_id="tenant_alpha",
        aggregate_type="credit_decision",
        aggregate_id="decision_personal_credit_001",
    )
    assert events[0].event_type == "credit_decision.rejected"
    assert events[0].result == "rejected"
    assert events[0].safe_details["rejection_reason"] == "credit_decision_not_found"


def test_credit_decision_technical_rejection_maps_to_technical_failure() -> None:
    repository = InMemoryAuditEventRepository()
    audit_service = AuditEvidenceApplicationService(repository=repository, environment="test")
    publisher = AuditEvidenceDecisionAuditPublisher(
        audit_service=audit_service,
        clock=lambda: NOW,
    )

    publisher.publish(
        _decision_intent(
            event_type="credit_decision.rejected",
            safe_details={
                "decision_id": "decision_personal_credit_001",
                "operation": "credit_decision.execute",
                "product_type": "personal_credit",
                "proposal_id": "proposal_personal_credit_001",
                "rejection_reason": "credit_decision_audit_write_failed",
                "status": "rejected",
            },
        )
    )

    events = repository.list_by_aggregate(
        tenant_id="tenant_alpha",
        aggregate_type="credit_decision",
        aggregate_id="decision_personal_credit_001",
    )
    assert events[0].result == "technical_failure"


def test_credit_decision_explanation_retrieved_maps_to_read_accepted_event() -> None:
    repository = InMemoryAuditEventRepository()
    audit_service = AuditEvidenceApplicationService(repository=repository, environment="test")
    publisher = AuditEvidenceDecisionAuditPublisher(
        audit_service=audit_service,
        clock=lambda: NOW,
    )

    publisher.publish(
        _decision_intent(
            event_type="credit_decision.explanation_retrieved",
            safe_details={
                "audience": "customer",
                "decision_id": "decision_personal_credit_001",
                "operation": "credit_decision.explanation.get",
                "proposal_id": "proposal_personal_credit_001",
                "status": "completed",
            },
        )
    )

    events = repository.list_by_aggregate(
        tenant_id="tenant_alpha",
        aggregate_type="credit_decision",
        aggregate_id="decision_personal_credit_001",
    )
    assert events[0].action == "read"
    assert events[0].result == "accepted"


def test_credit_decision_audit_adapter_generates_compact_distinct_event_ids() -> None:
    repository = InMemoryAuditEventRepository()
    audit_service = AuditEvidenceApplicationService(repository=repository, environment="test")
    occurrence_tokens = iter(("occurrence_001", "occurrence_002"))
    publisher = AuditEvidenceDecisionAuditPublisher(
        audit_service=audit_service,
        clock=lambda: NOW,
        occurrence_token_factory=lambda: next(occurrence_tokens),
    )

    publisher.publish(
        _decision_intent(
            event_type="credit_decision.explanation_retrieved",
            safe_details={
                "audience": "customer",
                "decision_id": "decision_personal_credit_001",
                "operation": "credit_decision.explanation.get",
                "proposal_id": "proposal_personal_credit_001",
                "status": "completed",
            },
        )
    )
    publisher.publish(
        _decision_intent(
            event_type="credit_decision.explanation_retrieved",
            safe_details={
                "audience": "customer",
                "decision_id": "decision_personal_credit_001",
                "operation": "credit_decision.explanation.get",
                "proposal_id": "proposal_personal_credit_001",
                "status": "completed",
            },
        )
    )

    events = repository.list_by_aggregate(
        tenant_id="tenant_alpha",
        aggregate_type="credit_decision",
        aggregate_id="decision_personal_credit_001",
    )
    assert len(events) == 2
    assert events[0].event_id != events[1].event_id
    assert all(len(event.event_id) <= 128 for event in events)


def test_credit_decision_audit_adapter_preserves_safe_details_guardrails() -> None:
    repository = InMemoryAuditEventRepository()
    audit_service = AuditEvidenceApplicationService(repository=repository, environment="test")
    publisher = AuditEvidenceDecisionAuditPublisher(
        audit_service=audit_service,
        clock=lambda: NOW,
    )

    with pytest.raises(AuditEvidenceValidationError):
        publisher.publish(
            _decision_intent(
                safe_details={
                    "decision_id": "decision_personal_credit_001",
                    "payload": "provider_payload_raw",
                },
            )
        )


def test_credit_decision_audit_adapter_compacts_long_decision_id_for_audit_resource() -> None:
    repository = InMemoryAuditEventRepository()
    audit_service = AuditEvidenceApplicationService(repository=repository, environment="test")
    publisher = AuditEvidenceDecisionAuditPublisher(
        audit_service=audit_service,
        clock=lambda: NOW,
    )
    long_decision_id = "decision_" + ("a" * 140)

    publisher.publish(
        _decision_intent(
            decision_id=long_decision_id,
            safe_details={
                "decision_id": long_decision_id,
                "operation": "credit_decision.execute",
                "proposal_id": "proposal_personal_credit_001",
                "status": "completed",
            },
        )
    )

    events = repository.list_by_time_window(
        tenant_id="tenant_alpha",
        occurred_from=NOW,
        occurred_to=NOW,
    )
    assert len(events) == 1
    assert events[0].aggregate_id.startswith("decision_ref_")
    assert len(events[0].aggregate_id) <= 128
    assert events[0].resource_id == events[0].aggregate_id
    assert events[0].safe_details["decision_id"] == long_decision_id


def test_credit_decision_audit_adapter_rejects_conflicting_authoritative_details() -> None:
    repository = InMemoryAuditEventRepository()
    audit_service = AuditEvidenceApplicationService(repository=repository, environment="test")
    publisher = AuditEvidenceDecisionAuditPublisher(
        audit_service=audit_service,
        clock=lambda: NOW,
    )

    with pytest.raises(ValueError, match="safe_details.decision_id"):
        publisher.publish(
            _decision_intent(
                safe_details={
                    "decision_id": "decision_other_001",
                    "operation": "credit_decision.execute",
                    "proposal_id": "proposal_personal_credit_001",
                    "status": "completed",
                },
            )
        )


def test_composite_decision_audit_publisher_routes_decision_and_fallback_events() -> None:
    decision_recorder = _RecordingPublisher()
    fallback_recorder = _RecordingPublisher()
    publisher = CompositeDecisionAuditPublisher(
        decision_publisher=decision_recorder,
        fallback_publisher=fallback_recorder,
    )
    decision_intent = _decision_intent()
    policy_intent = CreditPolicyAuditIntent(
        event_type="credit_policy.created",
        tenant_id="tenant_alpha",
        actor_subject_id="user_credit_manager",
        policy_id="pol_personal_credit_default",
        policy_version_id="polver_personal_credit_default_v1",
        correlation_id="corr_1234567890abcdef",
        safe_details={"policy_id": "pol_personal_credit_default"},
    )

    publisher.publish(decision_intent)
    publisher.publish(policy_intent)

    assert decision_recorder.events == [decision_intent]
    assert fallback_recorder.events == [policy_intent]


class _RecordingPublisher:
    def __init__(self) -> None:
        self.events: list[object] = []

    def publish(self, event: object) -> None:
        self.events.append(event)


def _decision_intent(
    *,
    decision_id: str = "decision_personal_credit_001",
    event_type: str = "credit_decision.completed",
    request_id: str = "req_1234567890abcdef",
    safe_details: dict[str, str] | None = None,
) -> CreditDecisionAuditIntent:
    return CreditDecisionAuditIntent(
        event_type=event_type,
        tenant_id="tenant_alpha",
        tenant_isolation_tier="bridge",
        actor_subject_id="user_credit_manager",
        decision_id=decision_id,
        proposal_id="proposal_personal_credit_001",
        policy_id="pol_personal_credit_default",
        policy_version_id="polver_personal_credit_default_v1",
        reason_code_catalog_id="rcc_personal_credit_default",
        reason_code_catalog_version_id="rccver_personal_credit_default_v1",
        correlation_id="corr_1234567890abcdef",
        request_id=request_id,
        traceparent=TRACEPARENT,
        safe_details=safe_details
        or {
            "channel": "api",
            "decision_id": "decision_personal_credit_001",
            "duration_ms": "12.5",
            "factor_count": "1",
            "fingerprint": "fp_decision_001",
            "operation": "credit_decision.execute",
            "outcome": "approve",
            "policy_id": "pol_personal_credit_default",
            "policy_revision": "3",
            "policy_version_id": "polver_personal_credit_default_v1",
            "product_type": "personal_credit",
            "proposal_id": "proposal_personal_credit_001",
            "reason_code_catalog_id": "rcc_personal_credit_default",
            "reason_code_catalog_version_id": "rccver_personal_credit_default_v1",
            "reason_code_count": "1",
            "reason_code_refs": "rc_min_income",
            "status": "completed",
            "triggered_rule_count": "1",
            "triggered_rule_ids": "rule_min_income",
            "validation_issue_count": "0",
        },
    )
