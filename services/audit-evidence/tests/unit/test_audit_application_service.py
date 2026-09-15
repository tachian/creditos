from __future__ import annotations

from datetime import UTC, datetime

import pytest
from creditos_audit_evidence.adapters.persistence import InMemoryAuditEventRepository
from creditos_audit_evidence.application.service import (
    AuditEvidenceApplicationService,
    ListAuditEventsByAggregateCommand,
    ListAuditEventsByTimeWindowCommand,
    RegisterAuditEventCommand,
)
from creditos_audit_evidence.domain.entities import AuditEvent
from creditos_audit_evidence.domain.errors import (
    AuditEvidenceConflictError,
    AuditEvidenceTenantContextError,
    AuditEvidenceValidationError,
)
from creditos_observability import ObservabilityContext
from creditos_security import PropagatedContext, TrustedContext


def test_register_audit_event_uses_trusted_context_and_appends_once() -> None:
    repository = InMemoryAuditEventRepository()
    service = AuditEvidenceApplicationService(repository=repository, environment="test")

    result = service.register_event(
        RegisterAuditEventCommand(
            event_id="audit_evt_001",
            aggregate_type="credit_decision",
            aggregate_id="decision_001",
            event_type="credit_decision.created",
            action="create",
            resource_type="credit_decision",
            resource_id="decision_001",
            source_service="decision",
            source_kind="grpc",
            result="accepted",
            occurred_at=datetime(2026, 9, 14, 12, 0, tzinfo=UTC),
            safe_details={"policy_id": "policy_001"},
        ),
        context=_observability_context(),
        trusted_context=_trusted_context(),
    )

    assert result.event.tenant_id == "tenant_alpha"
    assert result.event.actor_subject_id == "client-alpha"
    assert result.event.correlation_id == "corr-alpha"
    assert result.event.trace_id == "4bf92f3577b34da6a3ce929d0e0e4736"
    assert result.logs[0]["payload"] == "[OMITIDO]"
    assert repository.get(tenant_id="tenant_alpha", event_id="audit_evt_001") == result.event


def test_register_audit_event_rejects_observability_context_tenant_spoofing() -> None:
    service = AuditEvidenceApplicationService(
        repository=InMemoryAuditEventRepository(),
        environment="test",
    )

    with pytest.raises(AuditEvidenceTenantContextError):
        service.register_event(
            RegisterAuditEventCommand(
                event_id="audit_evt_001",
                aggregate_type="credit_decision",
                aggregate_id="decision_001",
                event_type="credit_decision.created",
                action="create",
                resource_type="credit_decision",
                resource_id="decision_001",
                source_service="decision",
                source_kind="grpc",
                result="accepted",
                occurred_at=datetime(2026, 9, 14, 12, 0, tzinfo=UTC),
            ),
            context=ObservabilityContext.new(
                correlation_id="corr-alpha",
                request_id="req-alpha",
                trace_id="4bf92f3577b34da6a3ce929d0e0e4736",
                tenant_id="tenant_beta",
                tenant_isolation_tier="bridge",
            ),
            trusted_context=_trusted_context(),
        )


def test_repository_is_append_only_and_rejects_duplicate_event_id() -> None:
    repository = InMemoryAuditEventRepository()
    service = AuditEvidenceApplicationService(repository=repository, environment="test")
    command = RegisterAuditEventCommand(
        event_id="audit_evt_001",
        aggregate_type="credit_decision",
        aggregate_id="decision_001",
        event_type="credit_decision.created",
        action="create",
        resource_type="credit_decision",
        resource_id="decision_001",
        source_service="decision",
        source_kind="grpc",
        result="accepted",
        occurred_at=datetime(2026, 9, 14, 12, 0, tzinfo=UTC),
    )

    service.register_event(
        command, context=_observability_context(), trusted_context=_trusted_context()
    )

    with pytest.raises(AuditEvidenceConflictError):
        service.register_event(
            command, context=_observability_context(), trusted_context=_trusted_context()
        )

    assert not hasattr(repository, "update")
    assert not hasattr(repository, "delete")
    assert not hasattr(repository, "remove")
    assert not hasattr(repository, "replace")


def test_repository_revalidates_duplicate_after_before_commit() -> None:
    repository = InMemoryAuditEventRepository()
    event = _audit_event(event_id="audit_evt_001")

    with pytest.raises(AuditEvidenceConflictError):
        repository.append(event, before_commit=lambda: repository.append(event))

    assert repository.get(tenant_id="tenant_alpha", event_id="audit_evt_001") == event
    assert [
        item.event_id
        for item in repository.list_by_aggregate(
            tenant_id="tenant_alpha",
            aggregate_type="credit_decision",
            aggregate_id="decision_001",
        )
    ] == ["audit_evt_001"]


def test_list_by_aggregate_is_tenant_scoped_and_does_not_return_cross_tenant() -> None:
    repository = InMemoryAuditEventRepository()
    service = AuditEvidenceApplicationService(repository=repository, environment="test")
    service.register_event(
        RegisterAuditEventCommand(
            event_id="audit_evt_001",
            aggregate_type="credit_decision",
            aggregate_id="decision_001",
            event_type="credit_decision.created",
            action="create",
            resource_type="credit_decision",
            resource_id="decision_001",
            source_service="decision",
            source_kind="grpc",
            result="accepted",
            occurred_at=datetime(2026, 9, 14, 12, 0, tzinfo=UTC),
        ),
        context=_observability_context(),
        trusted_context=_trusted_context(),
    )

    result = service.list_by_aggregate(
        ListAuditEventsByAggregateCommand(
            aggregate_type="credit_decision",
            aggregate_id="decision_001",
        ),
        context=_observability_context(),
        trusted_context=_trusted_context(),
    )

    assert [event.event_id for event in result.events] == ["audit_evt_001"]
    assert result.events[0].tenant_id == "tenant_alpha"


def test_list_by_time_window_is_tenant_scoped_and_ordered() -> None:
    repository = InMemoryAuditEventRepository()
    service = AuditEvidenceApplicationService(repository=repository, environment="test")
    service.register_event(
        RegisterAuditEventCommand(
            event_id="audit_evt_001",
            aggregate_type="credit_decision",
            aggregate_id="decision_001",
            event_type="credit_decision.created",
            action="create",
            resource_type="credit_decision",
            resource_id="decision_001",
            source_service="decision",
            source_kind="grpc",
            result="accepted",
            occurred_at=datetime(2026, 9, 14, 12, 0, tzinfo=UTC),
        ),
        context=_observability_context(),
        trusted_context=_trusted_context(),
    )
    service.register_event(
        RegisterAuditEventCommand(
            event_id="audit_evt_002",
            aggregate_type="credit_decision",
            aggregate_id="decision_002",
            event_type="credit_decision.created",
            action="create",
            resource_type="credit_decision",
            resource_id="decision_002",
            source_service="decision",
            source_kind="grpc",
            result="accepted",
            occurred_at=datetime(2026, 9, 14, 12, 5, tzinfo=UTC),
        ),
        context=_observability_context(),
        trusted_context=_trusted_context(),
    )

    result = service.list_by_time_window(
        ListAuditEventsByTimeWindowCommand(
            occurred_from=datetime(2026, 9, 14, 11, 59, tzinfo=UTC),
            occurred_to=datetime(2026, 9, 14, 12, 1, tzinfo=UTC),
        ),
        context=_observability_context(),
        trusted_context=_trusted_context(),
    )

    assert [event.event_id for event in result.events] == ["audit_evt_001"]
    assert result.logs[0]["payload"] == "[OMITIDO]"


def test_list_by_time_window_rejects_invalid_window() -> None:
    service = AuditEvidenceApplicationService(
        repository=InMemoryAuditEventRepository(), environment="test"
    )

    with pytest.raises(AuditEvidenceValidationError):
        service.list_by_time_window(
            ListAuditEventsByTimeWindowCommand(
                occurred_from=datetime(2026, 9, 14, 12, 1, tzinfo=UTC),
                occurred_to=datetime(2026, 9, 14, 12, 0, tzinfo=UTC),
            ),
            context=_observability_context(),
            trusted_context=_trusted_context(),
        )


def test_rejects_message_or_trace_without_official_audit_event() -> None:
    service = AuditEvidenceApplicationService(
        repository=InMemoryAuditEventRepository(), environment="test"
    )

    with pytest.raises(AuditEvidenceValidationError):
        service.register_event(
            RegisterAuditEventCommand(
                event_id="audit_evt_001",
                aggregate_type="trace",
                aggregate_id="trace_001",
                event_type="trace.only",
                action="observe",
                resource_type="trace",
                resource_id="trace_001",
                source_service="observability",
                source_kind="system",
                result="accepted",
                occurred_at=datetime(2026, 9, 14, 12, 0, tzinfo=UTC),
            ),
            context=_observability_context(),
            trusted_context=_trusted_context(),
        )


def _audit_event(*, event_id: str) -> AuditEvent:
    return AuditEvent.create(
        event_id=event_id,
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
    )


def _observability_context() -> ObservabilityContext:
    return ObservabilityContext.new(
        correlation_id="corr-alpha",
        request_id="req-alpha",
        trace_id="4bf92f3577b34da6a3ce929d0e0e4736",
        tenant_id="tenant_alpha",
        tenant_isolation_tier="bridge",
    )


def _trusted_context() -> PropagatedContext:
    return PropagatedContext(
        trusted=TrustedContext(
            tenant_id="tenant_alpha",
            tenant_isolation_tier="bridge",
            subject_id="client-alpha",
            scopes=("audit:write",),
            roles=("service-client",),
            client_id="client-alpha",
            principal_type="m2m",
        ),
        correlation_id="corr-alpha",
        request_id="req-alpha",
        traceparent="00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01",
        schema_version="v1",
    )
