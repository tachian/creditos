from __future__ import annotations

from datetime import UTC, datetime

import pytest
from creditos_audit_evidence.adapters.external import DeterministicAuditCheckpointSigner
from creditos_audit_evidence.adapters.persistence import (
    InMemoryAuditEventRepository,
    InMemoryAuditIntegrityCheckpointRepository,
)
from creditos_audit_evidence.application.ports import AuditCheckpointSigner
from creditos_audit_evidence.application.service import (
    AuditEvidenceApplicationService,
    GenerateAuditIntegrityCheckpointCommand,
    RegisterAuditEventCommand,
    VerifyAuditIntegrityCommand,
)
from creditos_audit_evidence.domain.errors import (
    AuditEvidenceConflictError,
    AuditEvidenceTenantContextError,
    AuditEvidenceValidationError,
)
from creditos_audit_evidence.domain.services.audit_integrity import (
    GENESIS_PREVIOUS_HASH,
    calculate_audit_event_hash,
    canonicalize_audit_event,
)
from creditos_observability import ObservabilityContext
from creditos_security import PropagatedContext, TrustedContext


def test_canonical_payload_is_stable_and_excludes_current_hash() -> None:
    event_a = _audit_event(
        event_id="audit_evt_001",
        safe_details={"policy_id": "policy_001", "outcome": "approved"},
    )
    event_b = _audit_event(
        event_id="audit_evt_001",
        safe_details={"outcome": "approved", "policy_id": "policy_001"},
    )

    canonical_a = canonicalize_audit_event(event_a, previous_hash=GENESIS_PREVIOUS_HASH)
    canonical_b = canonicalize_audit_event(event_b, previous_hash=GENESIS_PREVIOUS_HASH)

    assert canonical_a == canonical_b
    assert "current_hash" not in canonical_a
    assert "raw" not in canonical_a
    assert calculate_audit_event_hash(event_a, previous_hash=GENESIS_PREVIOUS_HASH) == (
        calculate_audit_event_hash(event_b, previous_hash=GENESIS_PREVIOUS_HASH)
    )


def test_repository_assigns_tenant_scoped_hash_chain_on_append() -> None:
    repository = InMemoryAuditEventRepository()
    first = repository.append(_audit_event(event_id="audit_evt_001"))
    second = repository.append(
        _audit_event(
            event_id="audit_evt_002",
            aggregate_id="decision_002",
            resource_id="decision_002",
            occurred_at=datetime(2026, 9, 14, 12, 1, tzinfo=UTC),
        )
    )
    other_tenant = repository.append(
        _audit_event(
            event_id="audit_evt_003",
            tenant_id="tenant_beta",
            aggregate_id="decision_003",
            resource_id="decision_003",
            occurred_at=datetime(2026, 9, 14, 12, 2, tzinfo=UTC),
        )
    )

    assert first.previous_hash == GENESIS_PREVIOUS_HASH
    assert first.current_hash == calculate_audit_event_hash(
        first, previous_hash=GENESIS_PREVIOUS_HASH
    )
    assert second.previous_hash == first.current_hash
    assert second.current_hash == calculate_audit_event_hash(
        second, previous_hash=first.current_hash
    )
    assert other_tenant.previous_hash == GENESIS_PREVIOUS_HASH


def test_repository_rejects_duplicate_without_recalculating_chain() -> None:
    repository = InMemoryAuditEventRepository()
    first = repository.append(_audit_event(event_id="audit_evt_001"))

    with pytest.raises(AuditEvidenceConflictError):
        repository.append(_audit_event(event_id="audit_evt_001"))

    stored = repository.get(tenant_id="tenant_alpha", event_id="audit_evt_001")
    assert stored == first
    assert stored is not None
    assert stored.previous_hash == GENESIS_PREVIOUS_HASH


def test_checkpoint_generation_and_verification_are_deterministic() -> None:
    service = _service()
    service.register_event(
        _register_command(event_id="audit_evt_001"),
        context=_observability_context(),
        trusted_context=_trusted_context(),
    )
    service.register_event(
        _register_command(
            event_id="audit_evt_002",
            aggregate_id="decision_002",
            resource_id="decision_002",
            occurred_at=datetime(2026, 9, 14, 12, 1, tzinfo=UTC),
        ),
        context=_observability_context(),
        trusted_context=_trusted_context(),
    )

    checkpoint_result = service.generate_integrity_checkpoint(
        GenerateAuditIntegrityCheckpointCommand(
            occurred_from=datetime(2026, 9, 14, 12, 0, tzinfo=UTC),
            occurred_to=datetime(2026, 9, 14, 12, 2, tzinfo=UTC),
            created_at=datetime(2026, 9, 14, 12, 3, tzinfo=UTC),
        ),
        context=_observability_context(),
        trusted_context=_trusted_context(),
    )
    verification_result = service.verify_integrity(
        VerifyAuditIntegrityCommand(
            occurred_from=datetime(2026, 9, 14, 12, 0, tzinfo=UTC),
            occurred_to=datetime(2026, 9, 14, 12, 2, tzinfo=UTC),
            checkpoint_id=checkpoint_result.checkpoint.checkpoint_id,
        ),
        context=_observability_context(),
        trusted_context=_trusted_context(),
    )

    assert checkpoint_result.checkpoint.event_count == 2
    assert checkpoint_result.checkpoint.first_event_id == "audit_evt_001"
    assert checkpoint_result.checkpoint.last_event_id == "audit_evt_002"
    assert checkpoint_result.checkpoint.signature_key_ref == "test-audit-checkpoint-key-v1"
    assert verification_result.valid is True
    assert verification_result.status == "valid"
    assert verification_result.issues == ()
    verification_audit_event = service._repository.list_by_tenant_chain(  # type: ignore[attr-defined]
        tenant_id="tenant_alpha"
    )[-1]
    assert verification_audit_event.event_type == "audit_integrity.verify"
    assert verification_audit_event.result == "accepted"
    assert verification_audit_event.safe_details["outcome"] == "valid"


def test_integrity_verification_accepts_partial_window_with_existing_predecessor() -> None:
    service = _service()
    service.register_event(
        _register_command(event_id="audit_evt_001"),
        context=_observability_context(),
        trusted_context=_trusted_context(),
    )
    service.register_event(
        _register_command(
            event_id="audit_evt_002",
            aggregate_id="decision_002",
            resource_id="decision_002",
            occurred_at=datetime(2026, 9, 14, 12, 1, tzinfo=UTC),
        ),
        context=_observability_context(),
        trusted_context=_trusted_context(),
    )

    verification_result = service.verify_integrity(
        VerifyAuditIntegrityCommand(
            occurred_from=datetime(2026, 9, 14, 12, 1, tzinfo=UTC),
            occurred_to=datetime(2026, 9, 14, 12, 2, tzinfo=UTC),
        ),
        context=_observability_context(),
        trusted_context=_trusted_context(),
    )

    assert verification_result.valid is True
    assert verification_result.issues == ()


def test_integrity_verification_rejects_empty_window_as_unverifiable() -> None:
    service = _service()

    verification_result = service.verify_integrity(
        VerifyAuditIntegrityCommand(
            occurred_from=datetime(2026, 9, 14, 12, 0, tzinfo=UTC),
            occurred_to=datetime(2026, 9, 14, 12, 2, tzinfo=UTC),
        ),
        context=_observability_context(),
        trusted_context=_trusted_context(),
    )

    assert verification_result.valid is False
    assert [issue.code for issue in verification_result.issues] == [
        "audit_window_empty_unverifiable"
    ]


def test_checkpoint_generation_requires_integrity_write_scope() -> None:
    service = _service()
    service.register_event(
        _register_command(event_id="audit_evt_001"),
        context=_observability_context(),
        trusted_context=_trusted_context(scopes=("audit:read", "audit:write")),
    )

    with pytest.raises(AuditEvidenceTenantContextError):
        service.generate_integrity_checkpoint(
            GenerateAuditIntegrityCheckpointCommand(
                occurred_from=datetime(2026, 9, 14, 12, 0, tzinfo=UTC),
                occurred_to=datetime(2026, 9, 14, 12, 2, tzinfo=UTC),
                created_at=datetime(2026, 9, 14, 12, 3, tzinfo=UTC),
            ),
            context=_observability_context(),
            trusted_context=_trusted_context(scopes=("audit:read", "audit:write")),
        )


def test_checkpoint_generation_rejects_open_window() -> None:
    service = _service()
    service.register_event(
        _register_command(event_id="audit_evt_001"),
        context=_observability_context(),
        trusted_context=_trusted_context(),
    )

    with pytest.raises(AuditEvidenceValidationError) as exc_info:
        service.generate_integrity_checkpoint(
            GenerateAuditIntegrityCheckpointCommand(
                occurred_from=datetime(2026, 9, 14, 12, 0, tzinfo=UTC),
                occurred_to=datetime(2026, 9, 14, 12, 2, tzinfo=UTC),
                created_at=datetime(2026, 9, 14, 12, 2, tzinfo=UTC),
            ),
            context=_observability_context(),
            trusted_context=_trusted_context(),
        )

    assert exc_info.value.code == "checkpoint_window_not_closed"


def test_checkpoint_generation_rejects_empty_window() -> None:
    service = _service()

    with pytest.raises(AuditEvidenceValidationError):
        service.generate_integrity_checkpoint(
            GenerateAuditIntegrityCheckpointCommand(
                occurred_from=datetime(2026, 9, 14, 12, 0, tzinfo=UTC),
                occurred_to=datetime(2026, 9, 14, 12, 2, tzinfo=UTC),
                created_at=datetime(2026, 9, 14, 12, 3, tzinfo=UTC),
            ),
            context=_observability_context(),
            trusted_context=_trusted_context(),
        )


def test_checkpoint_generation_rejects_tampered_source_chain() -> None:
    repository = InMemoryAuditEventRepository()
    service = _service(repository=repository)
    result = service.register_event(
        _register_command(event_id="audit_evt_001"),
        context=_observability_context(),
        trusted_context=_trusted_context(),
    )
    object.__setattr__(result.event, "resource_id", "decision_tampered")

    with pytest.raises(AuditEvidenceValidationError) as exc_info:
        service.generate_integrity_checkpoint(
            GenerateAuditIntegrityCheckpointCommand(
                occurred_from=datetime(2026, 9, 14, 12, 0, tzinfo=UTC),
                occurred_to=datetime(2026, 9, 14, 12, 2, tzinfo=UTC),
                created_at=datetime(2026, 9, 14, 12, 3, tzinfo=UTC),
            ),
            context=_observability_context(),
            trusted_context=_trusted_context(),
        )

    assert exc_info.value.code == "invalid_checkpoint_source_chain"


def test_checkpoint_repository_rejects_conflicting_checkpoint_for_same_window() -> None:
    service = _service()
    service.register_event(
        _register_command(event_id="audit_evt_001"),
        context=_observability_context(),
        trusted_context=_trusted_context(),
    )
    command = GenerateAuditIntegrityCheckpointCommand(
        occurred_from=datetime(2026, 9, 14, 12, 0, tzinfo=UTC),
        occurred_to=datetime(2026, 9, 14, 12, 2, tzinfo=UTC),
        created_at=datetime(2026, 9, 14, 12, 3, tzinfo=UTC),
    )
    service.generate_integrity_checkpoint(
        command,
        context=_observability_context(),
        trusted_context=_trusted_context(),
    )

    with pytest.raises(AuditEvidenceConflictError):
        service.generate_integrity_checkpoint(
            command,
            context=_observability_context(),
            trusted_context=_trusted_context(),
        )


def test_integrity_verification_reports_safe_divergence_without_payload() -> None:
    repository = InMemoryAuditEventRepository()
    service = _service(repository=repository)
    result = service.register_event(
        _register_command(event_id="audit_evt_001"),
        context=_observability_context(),
        trusted_context=_trusted_context(),
    )
    object.__setattr__(result.event, "resource_id", "decision_tampered")

    verification_result = service.verify_integrity(
        VerifyAuditIntegrityCommand(
            occurred_from=datetime(2026, 9, 14, 12, 0, tzinfo=UTC),
            occurred_to=datetime(2026, 9, 14, 12, 1, tzinfo=UTC),
        ),
        context=_observability_context(),
        trusted_context=_trusted_context(),
    )

    assert verification_result.valid is False
    assert verification_result.status == "invalid"
    assert verification_result.issues[0].code == "audit_event_hash_mismatch"
    assert verification_result.issues[0].event_id == "audit_evt_001"
    assert "decision_tampered" not in repr(verification_result.issues[0])
    verification_audit_event = repository.list_by_tenant_chain(tenant_id="tenant_alpha")[-1]
    assert verification_audit_event.event_type == "audit_integrity.verify"
    assert verification_audit_event.result == "rejected"
    assert verification_audit_event.safe_details["validation_issue_codes"] == (
        "audit_event_hash_mismatch"
    )


def test_integrity_verification_reports_tenant_predecessor_and_order_issues() -> None:
    repository = InMemoryAuditEventRepository()
    service = _service(repository=repository)
    first = service.register_event(
        _register_command(event_id="audit_evt_001"),
        context=_observability_context(),
        trusted_context=_trusted_context(),
    ).event
    second = service.register_event(
        _register_command(
            event_id="audit_evt_002",
            aggregate_id="decision_002",
            resource_id="decision_002",
            occurred_at=datetime(2026, 9, 14, 12, 1, tzinfo=UTC),
        ),
        context=_observability_context(),
        trusted_context=_trusted_context(),
    ).event
    third = service.register_event(
        _register_command(
            event_id="audit_evt_003",
            aggregate_id="decision_003",
            resource_id="decision_003",
            occurred_at=datetime(2026, 9, 14, 12, 2, tzinfo=UTC),
        ),
        context=_observability_context(),
        trusted_context=_trusted_context(),
    ).event
    object.__setattr__(first, "integrity_chain_id", "tenant_beta")
    object.__setattr__(second, "previous_hash", GENESIS_PREVIOUS_HASH)
    object.__setattr__(third, "previous_hash", "a" * 64)

    verification_result = service.verify_integrity(
        VerifyAuditIntegrityCommand(
            occurred_from=datetime(2026, 9, 14, 12, 0, tzinfo=UTC),
            occurred_to=datetime(2026, 9, 14, 12, 3, tzinfo=UTC),
        ),
        context=_observability_context(),
        trusted_context=_trusted_context(),
    )

    issue_codes = {issue.code for issue in verification_result.issues}
    assert "audit_event_tenant_mismatch" in issue_codes
    assert "audit_event_order_invalid" in issue_codes
    assert "audit_event_predecessor_missing" in issue_codes


def test_checkpoint_verification_detects_metadata_mismatch() -> None:
    service = _service()
    service.register_event(
        _register_command(event_id="audit_evt_001"),
        context=_observability_context(),
        trusted_context=_trusted_context(),
    )
    checkpoint = service.generate_integrity_checkpoint(
        GenerateAuditIntegrityCheckpointCommand(
            occurred_from=datetime(2026, 9, 14, 12, 0, tzinfo=UTC),
            occurred_to=datetime(2026, 9, 14, 12, 2, tzinfo=UTC),
            created_at=datetime(2026, 9, 14, 12, 3, tzinfo=UTC),
        ),
        context=_observability_context(),
        trusted_context=_trusted_context(),
    ).checkpoint
    object.__setattr__(checkpoint, "first_event_id", "audit_evt_other")

    verification_result = service.verify_integrity(
        VerifyAuditIntegrityCommand(
            occurred_from=datetime(2026, 9, 14, 12, 0, tzinfo=UTC),
            occurred_to=datetime(2026, 9, 14, 12, 2, tzinfo=UTC),
            checkpoint_id=checkpoint.checkpoint_id,
        ),
        context=_observability_context(),
        trusted_context=_trusted_context(),
    )

    assert verification_result.valid is False
    assert "audit_checkpoint_metadata_mismatch" in {
        issue.code for issue in verification_result.issues
    }


def test_checkpoint_verification_reports_signer_failure_safely() -> None:
    service = _service(checkpoint_signer=DeterministicAuditCheckpointSigner(secret="test-secret"))
    service.register_event(
        _register_command(event_id="audit_evt_001"),
        context=_observability_context(),
        trusted_context=_trusted_context(),
    )
    checkpoint = service.generate_integrity_checkpoint(
        GenerateAuditIntegrityCheckpointCommand(
            occurred_from=datetime(2026, 9, 14, 12, 0, tzinfo=UTC),
            occurred_to=datetime(2026, 9, 14, 12, 2, tzinfo=UTC),
            created_at=datetime(2026, 9, 14, 12, 3, tzinfo=UTC),
        ),
        context=_observability_context(),
        trusted_context=_trusted_context(),
    ).checkpoint
    failing_service = _service(
        repository=service._repository,  # type: ignore[attr-defined]
        checkpoint_repository=service._checkpoint_repository,  # type: ignore[attr-defined]
        checkpoint_signer=_FailingCheckpointSigner(),
    )

    verification_result = failing_service.verify_integrity(
        VerifyAuditIntegrityCommand(
            occurred_from=datetime(2026, 9, 14, 12, 0, tzinfo=UTC),
            occurred_to=datetime(2026, 9, 14, 12, 2, tzinfo=UTC),
            checkpoint_id=checkpoint.checkpoint_id,
        ),
        context=_observability_context(),
        trusted_context=_trusted_context(),
    )

    assert "audit_checkpoint_signature_unavailable" in {
        issue.code for issue in verification_result.issues
    }


def test_integrity_verification_audits_controlled_validation_failure() -> None:
    repository = InMemoryAuditEventRepository()
    service = _service(repository=repository)

    with pytest.raises(AuditEvidenceValidationError) as exc_info:
        service.verify_integrity(
            VerifyAuditIntegrityCommand(
                occurred_from=datetime(2026, 9, 14, 12, 2, tzinfo=UTC),
                occurred_to=datetime(2026, 9, 14, 12, 0, tzinfo=UTC),
            ),
            context=_observability_context(),
            trusted_context=_trusted_context(),
        )

    assert exc_info.value.code == "audit_evidence_invalid_time_window"
    verification_audit_event = repository.list_by_tenant_chain(tenant_id="tenant_alpha")[-1]
    assert verification_audit_event.event_type == "audit_integrity.verify"
    assert verification_audit_event.result == "rejected"
    assert verification_audit_event.safe_details["outcome"] == "validation_error"
    assert verification_audit_event.safe_details["validation_issue_codes"] == (
        "audit_evidence_invalid_time_window"
    )


def test_list_by_time_window_keeps_chronological_order_for_read_model() -> None:
    repository = InMemoryAuditEventRepository()
    later = repository.append(
        _audit_event(event_id="audit_evt_002", occurred_at=datetime(2026, 9, 14, 12, 2, tzinfo=UTC))
    )
    earlier = repository.append(
        _audit_event(event_id="audit_evt_001", occurred_at=datetime(2026, 9, 14, 12, 1, tzinfo=UTC))
    )

    assert [
        event.event_id
        for event in repository.list_by_time_window(
            tenant_id="tenant_alpha",
            occurred_from=datetime(2026, 9, 14, 12, 0, tzinfo=UTC),
            occurred_to=datetime(2026, 9, 14, 12, 3, tzinfo=UTC),
        )
    ] == [earlier.event_id, later.event_id]
    assert [
        event.event_id for event in repository.list_by_tenant_chain(tenant_id="tenant_alpha")
    ] == [
        later.event_id,
        earlier.event_id,
    ]


def test_repository_fails_closed_when_last_chain_event_loses_hash() -> None:
    repository = InMemoryAuditEventRepository()
    first = repository.append(_audit_event(event_id="audit_evt_001"))
    object.__setattr__(first, "current_hash", None)

    with pytest.raises(AuditEvidenceConflictError):
        repository.append(
            _audit_event(
                event_id="audit_evt_002",
                occurred_at=datetime(2026, 9, 14, 12, 1, tzinfo=UTC),
            )
        )


def _service(
    *,
    repository: InMemoryAuditEventRepository | None = None,
    checkpoint_repository: InMemoryAuditIntegrityCheckpointRepository | None = None,
    checkpoint_signer: AuditCheckpointSigner | None = None,
) -> AuditEvidenceApplicationService:
    return AuditEvidenceApplicationService(
        repository=repository or InMemoryAuditEventRepository(),
        checkpoint_repository=checkpoint_repository or InMemoryAuditIntegrityCheckpointRepository(),
        checkpoint_signer=checkpoint_signer
        or DeterministicAuditCheckpointSigner(secret="test-secret"),
        environment="test",
    )


def _audit_event(
    *,
    event_id: str,
    tenant_id: str = "tenant_alpha",
    aggregate_id: str = "decision_001",
    resource_id: str = "decision_001",
    occurred_at: datetime = datetime(2026, 9, 14, 12, 0, tzinfo=UTC),
    safe_details: dict[str, str] | None = None,
):
    from creditos_audit_evidence.domain.entities import AuditEvent

    return AuditEvent.create(
        event_id=event_id,
        tenant_id=tenant_id,
        aggregate_type="credit_decision",
        aggregate_id=aggregate_id,
        event_type="credit_decision.created",
        action="create",
        resource_type="credit_decision",
        resource_id=resource_id,
        actor_subject_id="client-alpha",
        source_service="decision",
        source_kind="grpc",
        result="accepted",
        occurred_at=occurred_at,
        correlation_id="corr-alpha",
        trace_id="4bf92f3577b34da6a3ce929d0e0e4736",
        request_id="req-alpha",
        safe_details=safe_details or {},
    )


def _register_command(
    *,
    event_id: str,
    aggregate_id: str = "decision_001",
    resource_id: str = "decision_001",
    occurred_at: datetime = datetime(2026, 9, 14, 12, 0, tzinfo=UTC),
) -> RegisterAuditEventCommand:
    return RegisterAuditEventCommand(
        event_id=event_id,
        aggregate_type="credit_decision",
        aggregate_id=aggregate_id,
        event_type="credit_decision.created",
        action="create",
        resource_type="credit_decision",
        resource_id=resource_id,
        source_service="decision",
        source_kind="grpc",
        result="accepted",
        occurred_at=occurred_at,
        safe_details={"policy_id": "policy_001"},
    )


def _observability_context() -> ObservabilityContext:
    return ObservabilityContext.new(
        correlation_id="corr-alpha",
        request_id="req-alpha",
        trace_id="4bf92f3577b34da6a3ce929d0e0e4736",
        tenant_id="tenant_alpha",
        tenant_isolation_tier="bridge",
    )


def _trusted_context(
    *, scopes: tuple[str, ...] = ("audit:read", "audit:write", "audit:integrity:write")
) -> PropagatedContext:
    return PropagatedContext(
        trusted=TrustedContext(
            tenant_id="tenant_alpha",
            tenant_isolation_tier="bridge",
            subject_id="client-alpha",
            scopes=scopes,
            roles=("service-client",),
            client_id="client-alpha",
            principal_type="m2m",
        ),
        correlation_id="corr-alpha",
        request_id="req-alpha",
        traceparent="00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01",
        schema_version="v1",
    )


class _FailingCheckpointSigner:
    def sign(self, payload: bytes):
        raise RuntimeError("indisponível")

    def verify(
        self,
        payload: bytes,
        *,
        signature: str,
        key_ref: str,
        algorithm: str,
    ) -> bool:
        raise RuntimeError("indisponível")
