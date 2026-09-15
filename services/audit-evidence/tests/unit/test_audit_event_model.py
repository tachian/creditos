from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from typing import Any, cast

import pytest
from creditos_audit_evidence.domain.entities import AuditEvent, OperationalEvidenceReference
from creditos_audit_evidence.domain.errors import AuditEvidenceValidationError


def test_audit_event_requires_canonical_utc_append_only_fields() -> None:
    event = AuditEvent.create(
        event_id="audit_evt_001",
        tenant_id="tenant_alpha",
        aggregate_type="credit_decision",
        aggregate_id="decision_001",
        event_type="credit_decision.created",
        action="create",
        resource_type="credit_decision",
        resource_id="decision_001",
        actor_subject_id="client-alpha",
        source_service="decision",
        source_kind="grpc",
        result="accepted",
        occurred_at=datetime(2026, 9, 14, 12, 0, tzinfo=UTC),
        correlation_id="corr-alpha",
        trace_id="4bf92f3577b34da6a3ce929d0e0e4736",
        request_id="req-alpha",
        safe_details={"policy_id": "policy_001", "outcome": "approved"},
        operational_evidence_refs=(
            OperationalEvidenceReference(kind="trace", reference="trace-4bf92f", source="tempo"),
        ),
    )

    assert event.event_id == "audit_evt_001"
    assert event.tenant_id == "tenant_alpha"
    assert event.occurred_at.tzinfo is UTC
    assert event.occurred_at.isoformat() == "2026-09-14T12:00:00+00:00"
    assert event.safe_details == {"policy_id": "policy_001", "outcome": "approved"}
    assert event.operational_evidence_refs[0].kind == "trace"
    with pytest.raises(TypeError):
        cast(Any, event.safe_details)["policy_id"] = "mutated"


@pytest.mark.parametrize(
    "field,value",
    [
        ("event_id", "12345678901"),
        ("aggregate_id", "12.345.678/0001-99"),
        ("tenant_id", "tenant alpha"),
        ("aggregate_type", "credit decision"),
        ("event_type", "credit_decision"),
        ("action", "create now"),
        ("actor_subject_id", "client@example.com"),
        ("source_service", "decision service"),
        ("source_kind", "browser"),
        ("result", "ok"),
        ("correlation_id", "corr alpha"),
        ("trace_id", "not-a-trace-id"),
    ],
)
def test_audit_event_rejects_invalid_identifiers(field: str, value: str) -> None:
    values = _valid_event_values()
    values[field] = value

    with pytest.raises(AuditEvidenceValidationError):
        AuditEvent.create(**values)


def test_audit_event_rejects_non_utc_or_naive_timestamp() -> None:
    values = _valid_event_values()
    values["occurred_at"] = datetime(2026, 9, 14, 12, 0)
    with pytest.raises(AuditEvidenceValidationError):
        AuditEvent.create(**values)

    values = _valid_event_values()
    values["occurred_at"] = datetime(2026, 9, 14, 9, 0, tzinfo=timezone(timedelta(hours=-3)))
    with pytest.raises(AuditEvidenceValidationError):
        AuditEvent.create(**values)

    values = _valid_event_values()
    assert AuditEvent.create(**values).occurred_at.tzinfo is UTC


def test_safe_details_are_allowlisted_bounded_strings_and_mask_sensitive_values() -> None:
    event = AuditEvent.create(
        **{
            **_valid_event_values(),
            "safe_details": {
                "policy_id": "policy_001",
                "outcome": "approved",
                "reason_code": "cpf 123.456.789-09 email person@example.com phone (11) 91234-5678",
            },
        }
    )

    assert event.safe_details["policy_id"] == "policy_001"
    assert event.safe_details["outcome"] == "approved"
    assert "123.456.789-09" not in event.safe_details["reason_code"]
    assert "person@example.com" not in event.safe_details["reason_code"]
    assert "(11) 91234-5678" not in event.safe_details["reason_code"]


@pytest.mark.parametrize(
    "safe_details",
    [
        {"subject_hint": "123.456.789-09"},
        {"authorization": "Bearer secret-token"},
        {"payload": "raw-provider-payload"},
        {"renda_mensal": "100000"},
        {"policy-id": "policy_001", "policy.id": "policy_002"},
    ],
)
def test_safe_details_reject_unknown_sensitive_or_colliding_keys(
    safe_details: dict[str, str],
) -> None:
    with pytest.raises(AuditEvidenceValidationError):
        AuditEvent.create(**{**_valid_event_values(), "safe_details": safe_details})


def test_operational_evidence_reference_cannot_replace_official_event() -> None:
    with pytest.raises(AuditEvidenceValidationError):
        AuditEvent.create(
            **{
                **_valid_event_values(),
                "aggregate_type": "operational_log",
                "aggregate_id": "log_001",
                "event_type": "operational_log.only",
                "resource_type": "log",
                "resource_id": "log_001",
            }
        )

    with pytest.raises(AuditEvidenceValidationError):
        AuditEvent.create(
            **{
                **_valid_event_values(),
                "aggregate_type": "trace_export",
                "event_type": "audit.trace_export",
            }
        )


def _valid_event_values() -> dict[str, Any]:
    return {
        "event_id": "audit_evt_001",
        "tenant_id": "tenant_alpha",
        "aggregate_type": "credit_decision",
        "aggregate_id": "decision_001",
        "event_type": "credit_decision.created",
        "action": "create",
        "resource_type": "credit_decision",
        "resource_id": "decision_001",
        "actor_subject_id": "client-alpha",
        "source_service": "decision",
        "source_kind": "grpc",
        "result": "accepted",
        "occurred_at": datetime(2026, 9, 14, 12, 0, tzinfo=UTC),
        "correlation_id": "corr-alpha",
        "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
        "request_id": "req-alpha",
        "safe_details": {},
        "operational_evidence_refs": (),
    }
