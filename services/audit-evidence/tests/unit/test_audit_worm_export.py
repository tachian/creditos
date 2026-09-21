from __future__ import annotations

from datetime import UTC, datetime

import pytest
from creditos_audit_evidence.adapters.external import DeterministicAuditCheckpointSigner
from creditos_audit_evidence.adapters.persistence import (
    InMemoryAuditEventRepository,
    InMemoryAuditIntegrityCheckpointRepository,
    InMemoryAuditWormExportRepository,
    InMemoryAuditWormStorage,
)
from creditos_audit_evidence.application.service import (
    AuditEvidenceApplicationService,
    ExportAuditCheckpointToWormCommand,
    GenerateAuditIntegrityCheckpointCommand,
    ReconcileAuditWormExportCommand,
    RegisterAuditEventCommand,
)
from creditos_audit_evidence.domain.errors import (
    AuditEvidenceConflictError,
    AuditEvidenceTenantContextError,
    AuditEvidenceValidationError,
)
from creditos_audit_evidence.domain.value_objects.audit_worm_export import (
    WORM_MANIFEST_VERSION,
    WormRetentionMode,
)
from creditos_observability import ObservabilityContext
from creditos_security import PropagatedContext, TrustedContext


def test_exports_signed_checkpoint_to_minimized_worm_manifest() -> None:
    service = _service()
    checkpoint_id = _create_checkpoint(service)

    result = service.export_checkpoint_to_worm(
        _export_command(checkpoint_id=checkpoint_id),
        context=_observability_context(),
        trusted_context=_trusted_context(),
    )

    export = result.export
    assert export.manifest_version == WORM_MANIFEST_VERSION
    assert export.retention_mode == WormRetentionMode.COMPLIANCE
    assert export.object_key == (
        f"tenants/tenant_alpha/audit/year=2026/month=09/checkpoint={checkpoint_id}/manifest.json"
    )
    assert export.object_version_id == "v000001"
    assert export.event_count == 2
    assert result.logs[0]["payload"] == "[OMITIDO]"
    assert result.logs[0]["extra"]["manifest_digest"] == export.manifest_digest
    assert (
        _audit_events(service, event_type="audit_worm_export.created")[-1].safe_details["outcome"]
        == "accepted"
    )


def test_export_replay_is_idempotent_for_same_manifest_and_rejects_divergence() -> None:
    service = _service()
    checkpoint_id = _create_checkpoint(service)
    command = _export_command(checkpoint_id=checkpoint_id)

    first = service.export_checkpoint_to_worm(
        command,
        context=_observability_context(),
        trusted_context=_trusted_context(),
    ).export
    second = service.export_checkpoint_to_worm(
        command,
        context=_observability_context(),
        trusted_context=_trusted_context(),
    ).export

    assert second == first
    with pytest.raises(AuditEvidenceConflictError) as exc_info:
        service.export_checkpoint_to_worm(
            _export_command(
                checkpoint_id=checkpoint_id,
                object_key=f"tenants/tenant_alpha/audit/year=2026/month=10/checkpoint={checkpoint_id}/manifest.json",
            ),
            context=_observability_context(),
            trusted_context=_trusted_context(),
        )
    assert exc_info.value.code == "conflicting_worm_export"


def test_export_rejects_expired_retention_missing_checkpoint_and_missing_scope() -> None:
    service = _service()
    checkpoint_id = _create_checkpoint(service)

    with pytest.raises(AuditEvidenceValidationError) as retention_error:
        service.export_checkpoint_to_worm(
            _export_command(
                checkpoint_id=checkpoint_id,
                retain_until=datetime(2026, 9, 14, 12, 4, tzinfo=UTC),
            ),
            context=_observability_context(),
            trusted_context=_trusted_context(),
        )
    assert retention_error.value.code == "expired_worm_retention"
    assert _audit_events(service, event_type="audit_worm_export.created")[-1].result == "rejected"

    with pytest.raises(AuditEvidenceValidationError) as checkpoint_error:
        service.export_checkpoint_to_worm(
            _export_command(checkpoint_id="audit_chk_missing"),
            context=_observability_context(),
            trusted_context=_trusted_context(),
        )
    assert checkpoint_error.value.code == "worm_checkpoint_not_found"

    with pytest.raises(AuditEvidenceTenantContextError):
        service.export_checkpoint_to_worm(
            _export_command(checkpoint_id=checkpoint_id),
            context=_observability_context(),
            trusted_context=_trusted_context(scopes=("audit:read",)),
        )
    assert (
        _audit_events(service, event_type="audit_worm_export.created")[-1].safe_details[
            "validation_issue_codes"
        ]
        == "audit_evidence_missing_scope_audit_worm_write"
    )


def test_export_verifies_checkpoint_integrity_before_worm_write() -> None:
    checkpoint_repository = InMemoryAuditIntegrityCheckpointRepository()
    worm_storage = InMemoryAuditWormStorage()
    service = _service(
        checkpoint_repository=checkpoint_repository,
        worm_storage=worm_storage,
    )
    checkpoint_id = _create_checkpoint(service)
    checkpoint = checkpoint_repository.get(tenant_id="tenant_alpha", checkpoint_id=checkpoint_id)
    assert checkpoint is not None
    object.__setattr__(checkpoint, "signature", "tampered-signature")

    with pytest.raises(AuditEvidenceValidationError) as exc_info:
        service.export_checkpoint_to_worm(
            _export_command(checkpoint_id=checkpoint_id),
            context=_observability_context(),
            trusted_context=_trusted_context(),
        )

    assert exc_info.value.code == "invalid_worm_checkpoint_integrity"
    assert (
        worm_storage.get_object(
            tenant_id="tenant_alpha",
            object_key=(
                "tenants/tenant_alpha/audit/year=2026/month=09/"
                f"checkpoint={checkpoint_id}/manifest.json"
            ),
            object_version_id="v000001",
        )
        is None
    )


def test_reconciliation_reports_valid_object_and_official_audit_event() -> None:
    service = _service()
    checkpoint_id = _create_checkpoint(service)
    export = service.export_checkpoint_to_worm(
        _export_command(checkpoint_id=checkpoint_id),
        context=_observability_context(),
        trusted_context=_trusted_context(),
    ).export

    result = service.reconcile_worm_export(
        ReconcileAuditWormExportCommand(export_id=export.export_id),
        context=_observability_context(),
        trusted_context=_trusted_context(scopes=("audit:worm:read",)),
    )

    assert result.valid is True
    assert result.issues == ()
    reconciliation_event = _audit_events(service, event_type="audit_worm_export.reconciled")[-1]
    assert reconciliation_event.safe_details["outcome"] == "valid"
    assert reconciliation_event.safe_details["checkpoint_id"] == checkpoint_id
    assert reconciliation_event.safe_details["window_started_at"] == "2026-09-14T12:00:00+00:00"
    assert reconciliation_event.safe_details["window_ended_at"] == "2026-09-14T12:02:00+00:00"


def test_reconciliation_requires_worm_scope_and_audits_denial() -> None:
    service = _service()
    checkpoint_id = _create_checkpoint(service)
    export = service.export_checkpoint_to_worm(
        _export_command(checkpoint_id=checkpoint_id),
        context=_observability_context(),
        trusted_context=_trusted_context(),
    ).export

    with pytest.raises(AuditEvidenceTenantContextError):
        service.reconcile_worm_export(
            ReconcileAuditWormExportCommand(export_id=export.export_id),
            context=_observability_context(),
            trusted_context=_trusted_context(scopes=("audit:write",)),
        )

    reconciliation_event = _audit_events(service, event_type="audit_worm_export.reconciled")[-1]
    assert reconciliation_event.result == "rejected"
    assert reconciliation_event.safe_details["validation_issue_codes"] == (
        "audit_evidence_missing_scope_audit_worm_read_or_audit_read"
    )


def test_reconciliation_detects_tampered_checkpoint_proof_after_export() -> None:
    checkpoint_repository = InMemoryAuditIntegrityCheckpointRepository()
    service = _service(checkpoint_repository=checkpoint_repository)
    checkpoint_id = _create_checkpoint(service)
    export = service.export_checkpoint_to_worm(
        _export_command(checkpoint_id=checkpoint_id),
        context=_observability_context(),
        trusted_context=_trusted_context(),
    ).export
    checkpoint = checkpoint_repository.get(tenant_id="tenant_alpha", checkpoint_id=checkpoint_id)
    assert checkpoint is not None
    object.__setattr__(checkpoint, "signature_key_ref", "tampered-key-ref")

    result = service.reconcile_worm_export(
        ReconcileAuditWormExportCommand(export_id=export.export_id),
        context=_observability_context(),
        trusted_context=_trusted_context(scopes=("audit:worm:read",)),
    )

    issue_codes = {issue.code for issue in result.issues}
    assert "worm_manifest_checkpoint_proof_mismatch" in issue_codes
    assert "worm_checkpoint_signature_mismatch" in issue_codes


def test_reconciliation_reports_safe_divergence_without_payload() -> None:
    repository = InMemoryAuditEventRepository()
    checkpoint_repository = InMemoryAuditIntegrityCheckpointRepository()
    worm_export_repository = InMemoryAuditWormExportRepository()
    worm_storage = InMemoryAuditWormStorage()
    service = _service(
        repository=repository,
        checkpoint_repository=checkpoint_repository,
        worm_export_repository=worm_export_repository,
        worm_storage=worm_storage,
    )
    checkpoint_id = _create_checkpoint(service)
    export = service.export_checkpoint_to_worm(
        _export_command(checkpoint_id=checkpoint_id),
        context=_observability_context(),
        trusted_context=_trusted_context(),
    ).export
    stored = worm_storage.get_object(
        tenant_id="tenant_alpha",
        object_key=export.object_key,
        object_version_id=export.object_version_id,
    )
    assert stored is not None
    object.__setattr__(stored, "body_digest", "0" * 64)

    result = service.reconcile_worm_export(
        ReconcileAuditWormExportCommand(export_id=export.export_id),
        context=_observability_context(),
        trusted_context=_trusted_context(scopes=("audit:read",)),
    )

    assert result.valid is False
    assert {issue.code for issue in result.issues} == {"worm_storage_digest_mismatch"}
    assert "12345678909" not in repr(result.issues)
    assert "cliente@example.com" not in repr(result.issues)
    reconciliation_event = _audit_events(service, event_type="audit_worm_export.reconciled")[-1]
    assert reconciliation_event.result == "rejected"
    assert reconciliation_event.safe_details["validation_issue_codes"] == (
        "worm_storage_digest_mismatch"
    )


def test_export_rejects_cross_tenant_object_key_and_backdated_retention() -> None:
    service = _service()
    checkpoint_id = _create_checkpoint(service)

    with pytest.raises(AuditEvidenceValidationError) as object_key_error:
        service.export_checkpoint_to_worm(
            _export_command(
                checkpoint_id=checkpoint_id,
                object_key=f"tenants/tenant_beta/audit/year=2026/month=09/checkpoint={checkpoint_id}/manifest.json",
            ),
            context=_observability_context(),
            trusted_context=_trusted_context(),
        )
    assert object_key_error.value.code == "invalid_worm_object_key"

    with pytest.raises(AuditEvidenceValidationError) as retention_error:
        service.export_checkpoint_to_worm(
            _export_command(
                checkpoint_id=checkpoint_id,
                retain_until=datetime(2026, 9, 20, 12, 0, tzinfo=UTC),
            ),
            context=_observability_context(),
            trusted_context=_trusted_context(),
        )
    assert retention_error.value.code == "expired_worm_retention"


def test_legal_hold_requires_reason() -> None:
    service = _service()
    checkpoint_id = _create_checkpoint(service)

    with pytest.raises(AuditEvidenceValidationError) as exc_info:
        service.export_checkpoint_to_worm(
            _export_command(checkpoint_id=checkpoint_id, legal_hold_reason=None),
            context=_observability_context(),
            trusted_context=_trusted_context(),
        )

    assert exc_info.value.code == "missing_worm_legal_hold_reason"


def test_reconciliation_validates_manifest_schema_and_governed_metadata() -> None:
    worm_storage = InMemoryAuditWormStorage()
    service = _service(worm_storage=worm_storage)
    checkpoint_id = _create_checkpoint(service)
    export = service.export_checkpoint_to_worm(
        _export_command(checkpoint_id=checkpoint_id),
        context=_observability_context(),
        trusted_context=_trusted_context(),
    ).export
    stored = worm_storage.get_object(
        tenant_id="tenant_alpha",
        object_key=export.object_key,
        object_version_id=export.object_version_id,
    )
    assert stored is not None
    object.__setattr__(stored, "body", "[]")
    object.__setattr__(stored, "body_digest", "0" * 64)

    result = service.reconcile_worm_export(
        ReconcileAuditWormExportCommand(export_id=export.export_id),
        context=_observability_context(),
        trusted_context=_trusted_context(scopes=("audit:worm:read",)),
    )

    issue_codes = {issue.code for issue in result.issues}
    assert "worm_manifest_unreadable" in issue_codes
    assert "worm_manifest_digest_mismatch" in issue_codes
    assert "worm_manifest_tenant_mismatch" in issue_codes


def test_replay_idempotent_requires_existing_storage_object() -> None:
    worm_storage = InMemoryAuditWormStorage()
    service = _service(worm_storage=worm_storage)
    checkpoint_id = _create_checkpoint(service)
    export = service.export_checkpoint_to_worm(
        _export_command(checkpoint_id=checkpoint_id),
        context=_observability_context(),
        trusted_context=_trusted_context(),
    ).export
    stored = worm_storage.get_object(
        tenant_id="tenant_alpha",
        object_key=export.object_key,
        object_version_id=export.object_version_id,
    )
    assert stored is not None
    object.__setattr__(stored, "retention_mode", WormRetentionMode.GOVERNANCE)

    with pytest.raises(AuditEvidenceConflictError) as exc_info:
        service.export_checkpoint_to_worm(
            _export_command(checkpoint_id=checkpoint_id),
            context=_observability_context(),
            trusted_context=_trusted_context(),
        )

    assert exc_info.value.code == "idempotent_worm_export_storage_mismatch"


def test_export_results_logs_and_audit_do_not_leak_sensitive_raw_values() -> None:
    service = _service()
    checkpoint_id = _create_checkpoint(service)

    result = service.export_checkpoint_to_worm(
        _export_command(checkpoint_id=checkpoint_id),
        context=_observability_context(),
        trusted_context=_trusted_context(),
    )
    serialized_result = repr(result)
    serialized_logs = repr(service.logged_events)
    serialized_audit_events = repr(
        [
            event.safe_details
            for event in _audit_events(service, event_type="audit_worm_export.created")
        ]
    )

    for forbidden_value in (
        "12345678909",
        "12.345.678/0001-95",
        "cliente@example.com",
        "Bearer",
        "raw_payload",
    ):
        assert forbidden_value not in serialized_result
        assert forbidden_value not in serialized_logs
        assert forbidden_value not in serialized_audit_events


def _service(
    *,
    repository: InMemoryAuditEventRepository | None = None,
    checkpoint_repository: InMemoryAuditIntegrityCheckpointRepository | None = None,
    worm_export_repository: InMemoryAuditWormExportRepository | None = None,
    worm_storage: InMemoryAuditWormStorage | None = None,
) -> AuditEvidenceApplicationService:
    return AuditEvidenceApplicationService(
        repository=repository or InMemoryAuditEventRepository(),
        checkpoint_repository=checkpoint_repository or InMemoryAuditIntegrityCheckpointRepository(),
        checkpoint_signer=DeterministicAuditCheckpointSigner(secret="test-secret"),
        worm_export_repository=worm_export_repository or InMemoryAuditWormExportRepository(),
        worm_storage=worm_storage or InMemoryAuditWormStorage(),
        environment="test",
    )


def _create_checkpoint(service: AuditEvidenceApplicationService) -> str:
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
    return service.generate_integrity_checkpoint(
        GenerateAuditIntegrityCheckpointCommand(
            occurred_from=datetime(2026, 9, 14, 12, 0, tzinfo=UTC),
            occurred_to=datetime(2026, 9, 14, 12, 2, tzinfo=UTC),
            created_at=datetime(2026, 9, 14, 12, 3, tzinfo=UTC),
        ),
        context=_observability_context(),
        trusted_context=_trusted_context(),
    ).checkpoint.checkpoint_id


def _export_command(
    *,
    checkpoint_id: str,
    retain_until: datetime = datetime(2027, 9, 14, 12, 0, tzinfo=UTC),
    object_key: str | None = None,
    legal_hold_reason: str | None = "legal_hold_case_001",
) -> ExportAuditCheckpointToWormCommand:
    return ExportAuditCheckpointToWormCommand(
        checkpoint_id=checkpoint_id,
        occurred_from=datetime(2026, 9, 14, 12, 0, tzinfo=UTC),
        occurred_to=datetime(2026, 9, 14, 12, 2, tzinfo=UTC),
        retention_class="regulatory",
        retention_mode=WormRetentionMode.COMPLIANCE,
        retain_until=retain_until,
        legal_hold=True,
        legal_hold_reason=legal_hold_reason,
        created_at=datetime(2026, 9, 14, 12, 4, tzinfo=UTC),
        object_key=object_key,
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
    *,
    scopes: tuple[str, ...] = (
        "audit:read",
        "audit:write",
        "audit:integrity:write",
        "audit:worm:write",
        "audit:worm:read",
    ),
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


def _audit_events(
    service: AuditEvidenceApplicationService,
    *,
    event_type: str,
):
    return tuple(
        event
        for event in service._repository.list_by_tenant_chain(  # type: ignore[attr-defined]
            tenant_id="tenant_alpha"
        )
        if event.event_type == event_type
    )
