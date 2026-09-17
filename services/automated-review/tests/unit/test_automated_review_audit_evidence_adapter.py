from __future__ import annotations

from datetime import UTC, datetime

import pytest
from creditos_audit_evidence.adapters.persistence import InMemoryAuditEventRepository
from creditos_audit_evidence.application.service import AuditEvidenceApplicationService
from creditos_audit_evidence.domain.errors import AuditEvidenceValidationError
from creditos_automated_review.adapters.external.audit_evidence_publisher import (
    AuditEvidenceAutomatedReviewAuditPublisher,
)
from creditos_automated_review.application.ports import AutomatedReviewAuditIntent

NOW = datetime(2026, 9, 16, 12, 0, tzinfo=UTC)
TRACEPARENT = "00-1234567890abcdef1234567890abcdef-1234567890abcdef-01"


def test_automated_review_config_change_appends_official_audit_event() -> None:
    repository = InMemoryAuditEventRepository()
    audit_service = AuditEvidenceApplicationService(repository=repository, environment="test")
    publisher = AuditEvidenceAutomatedReviewAuditPublisher(
        audit_service=audit_service,
        clock=lambda: NOW,
        occurrence_token_factory=lambda: "occurrence_review_config",
    )

    publisher.publish(_config_intent())

    events = repository.list_by_aggregate(
        tenant_id="tenant_alpha",
        aggregate_type="review_agent_config",
        aggregate_id="rac_personal_credit_default",
    )
    assert len(events) == 1
    event = events[0]
    assert event.event_type == "automated_review.config.published"
    assert event.action == "publish"
    assert event.resource_type == "review_agent_config"
    assert event.resource_id == "racver_personal_credit_default_v1"
    assert event.actor_subject_id == "user_risk_manager"
    assert event.source_service == "automated_review"
    assert event.source_kind == "grpc"
    assert event.result == "accepted"
    assert event.correlation_id == "corr_1234567890abcdef"
    assert event.trace_id == "1234567890abcdef1234567890abcdef"
    assert event.request_id == "req_1234567890abcdef"
    assert event.safe_details["review_agent_config_id"] == "rac_personal_credit_default"
    assert event.safe_details["review_agent_config_version_id"] == (
        "racver_personal_credit_default_v1"
    )
    assert event.safe_details["prompt_fingerprint"] == "a" * 64
    assert event.safe_details["previous_revision"] == "2"
    assert event.safe_details["resulting_revision"] == "3"
    assert event.operational_evidence_refs[0].kind == "trace"


def test_automated_review_audit_adapter_uses_intent_timestamp_and_maps_blocked_result() -> None:
    repository = InMemoryAuditEventRepository()
    audit_service = AuditEvidenceApplicationService(repository=repository, environment="test")
    publisher = AuditEvidenceAutomatedReviewAuditPublisher(
        audit_service=audit_service,
        clock=lambda: datetime(2026, 9, 16, 13, 0, tzinfo=UTC),
        occurrence_token_factory=lambda: "occurrence_review_config_blocked",
    )

    publisher.publish(
        _config_intent(
            safe_details={
                "operation": "automated_review.config.publish",
                "status": "blocked",
            }
        )
    )

    events = repository.list_by_aggregate(
        tenant_id="tenant_alpha",
        aggregate_type="review_agent_config",
        aggregate_id="rac_personal_credit_default",
    )
    assert events[0].occurred_at == NOW
    assert events[0].result == "blocked"


def test_automated_review_audit_adapter_rejects_invalid_traceparent() -> None:
    repository = InMemoryAuditEventRepository()
    audit_service = AuditEvidenceApplicationService(repository=repository, environment="test")
    publisher = AuditEvidenceAutomatedReviewAuditPublisher(
        audit_service=audit_service,
        clock=lambda: NOW,
    )

    with pytest.raises(ValueError, match="traceparent inválido"):
        publisher.publish(_config_intent(traceparent=f"00-{'1' * 32}-{'0' * 16}-01"))


def test_automated_review_audit_adapter_rejects_sensitive_free_payload() -> None:
    repository = InMemoryAuditEventRepository()
    audit_service = AuditEvidenceApplicationService(repository=repository, environment="test")
    publisher = AuditEvidenceAutomatedReviewAuditPublisher(
        audit_service=audit_service,
        clock=lambda: NOW,
    )

    with pytest.raises(AuditEvidenceValidationError):
        publisher.publish(
            _config_intent(
                safe_details={
                    "operation": "automated_review.config.publish",
                    "payload": "prompt bruto secreto",
                }
            )
        )


def test_automated_review_audit_adapter_rejects_authoritative_safe_detail_conflict() -> None:
    repository = InMemoryAuditEventRepository()
    audit_service = AuditEvidenceApplicationService(repository=repository, environment="test")
    publisher = AuditEvidenceAutomatedReviewAuditPublisher(
        audit_service=audit_service,
        clock=lambda: NOW,
    )

    with pytest.raises(ValueError, match="safe_details.review_agent_config_id"):
        publisher.publish(
            _config_intent(
                safe_details={
                    "operation": "automated_review.config.publish",
                    "review_agent_config_id": "rac_other",
                }
            )
        )


def _config_intent(
    *,
    safe_details: dict[str, str] | None = None,
    traceparent: str = TRACEPARENT,
) -> AutomatedReviewAuditIntent:
    return AutomatedReviewAuditIntent(
        event_type="automated_review.config.published",
        tenant_id="tenant_alpha",
        tenant_isolation_tier="bridge",
        actor_subject_id="user_risk_manager",
        review_agent_config_id="rac_personal_credit_default",
        review_agent_config_version_id="racver_personal_credit_default_v1",
        correlation_id="corr_1234567890abcdef",
        request_id="req_1234567890abcdef",
        traceparent=traceparent,
        occurred_at=NOW.isoformat(),
        change_summary="Publicação aprovada",
        previous_revision=2,
        resulting_revision=3,
        safe_details=safe_details
        or {
            "agent_version": "agent_credit_review_v1",
            "approval_reference": "approval_board_001",
            "change_reason": "Publicação aprovada",
            "consultative_only": "true",
            "fallback_action": "return_inconclusive",
            "model_ref": "model_credit_review",
            "model_version": "model_version_001",
            "operation": "automated_review.config.publish",
            "previous_revision": "2",
            "product_type": "personal_credit",
            "prompt_fingerprint": "a" * 64,
            "prompt_version": "prompt_credit_review_v1",
            "provider_ref": "provider_llm_default",
            "resulting_revision": "3",
            "status": "published",
        },
    )
