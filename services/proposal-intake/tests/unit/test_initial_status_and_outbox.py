from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime
from typing import Any

import pytest
from creditos_observability.context import ObservabilityContext
from creditos_proposal_intake.adapters.persistence import (
    InMemoryCanonicalProposalRepository,
    InMemoryIdempotentProposalSubmissionRepository,
    InMemoryProposalIntakeStatusRepository,
    InMemoryProposalOutboxRepository,
)
from creditos_proposal_intake.application.service import (
    ProposalIntakeApplicationService,
    SubmitIdempotentProposalCommand,
    SubmitProposalWithInitialStatusCommand,
)
from creditos_proposal_intake.domain.entities import (
    ProposalIntakeStatus,
    ProposalOutboxMessage,
)
from creditos_proposal_intake.domain.errors import IdempotencyConflictError, ProposalValidationError

_SENSITIVE_FINGERPRINT_SECRET = "segredo-local-de-teste-com-32-caracteres"
_FIXED_TIME = datetime(2026, 8, 16, 12, 30, 45, tzinfo=UTC)


def test_new_submission_creates_initial_status_and_pending_outbox() -> None:
    canonical_repository = InMemoryCanonicalProposalRepository()
    status_repository = InMemoryProposalIntakeStatusRepository()
    outbox_repository = InMemoryProposalOutboxRepository()
    service = _service(
        canonical_repository=canonical_repository,
        status_repository=status_repository,
        outbox_repository=outbox_repository,
    )

    result = service.submit_with_initial_status_and_outbox(
        _submit_command(payload=_valid_personal_credit_payload()),
        context=_context(),
    )

    assert result.idempotency_status == "created"
    assert result.proposal.proposal_id is not None
    assert len(canonical_repository.list_all()) == 1
    assert status_repository.list_all() == [result.intake_status]
    assert outbox_repository.list_all() == [result.outbox_message]
    assert result.intake_status == ProposalIntakeStatus(
        tenant_id="tenant-bridge-001",
        proposal_id=result.proposal.proposal_id,
        external_proposal_id="prop-personal-001",
        status="submitted",
        schema_version="1.0",
        product_type="personal_credit",
        channel="api",
        occurred_at=_FIXED_TIME,
        reason="proposal_submitted",
    )
    assert result.outbox_message.status == "pending"
    assert result.outbox_message.aggregate_type == "proposal"
    assert result.outbox_message.aggregate_id == result.proposal.proposal_id
    assert result.outbox_message.event_type == "creditos.proposal.v1.submitted"
    assert result.outbox_message.subject == f"proposal/{result.proposal.proposal_id}"
    assert result.logs[-1]["status"] == "created"
    assert result.logs[-1]["extra"]["event_type"] == "creditos.proposal.v1.submitted"


def test_replay_returns_existing_status_and_outbox_without_duplicates() -> None:
    status_repository = InMemoryProposalIntakeStatusRepository()
    outbox_repository = InMemoryProposalOutboxRepository()
    service = _service(status_repository=status_repository, outbox_repository=outbox_repository)
    command = _submit_command(payload=_valid_personal_credit_payload())

    first = service.submit_with_initial_status_and_outbox(command, context=_context())
    second = service.submit_with_initial_status_and_outbox(command, context=_context())

    assert second.idempotency_status == "replayed"
    assert second.proposal.proposal_id == first.proposal.proposal_id
    assert second.intake_status == first.intake_status
    assert second.outbox_message == first.outbox_message
    assert len(status_repository.list_all()) == 1
    assert len(outbox_repository.list_all()) == 1
    assert second.logs[-1]["status"] == "replayed"


def test_concurrent_replays_do_not_observe_missing_status_or_outbox() -> None:
    status_repository = InMemoryProposalIntakeStatusRepository()
    outbox_repository = InMemoryProposalOutboxRepository()
    service = _service(status_repository=status_repository, outbox_repository=outbox_repository)
    command = _submit_command(payload=_valid_personal_credit_payload())

    def submit_once() -> str:
        result = service.submit_with_initial_status_and_outbox(command, context=_context())
        return result.idempotency_status

    with ThreadPoolExecutor(max_workers=8) as executor:
        statuses = list(executor.map(lambda _: submit_once(), range(16)))

    assert statuses.count("created") == 1
    assert statuses.count("replayed") == 15
    assert len(status_repository.list_all()) == 1
    assert len(outbox_repository.list_all()) == 1


def test_replay_without_existing_status_or_outbox_is_rejected() -> None:
    canonical_repository = InMemoryCanonicalProposalRepository()
    idempotency_repository = InMemoryIdempotentProposalSubmissionRepository()
    service = _service(
        canonical_repository=canonical_repository,
        idempotency_repository=idempotency_repository,
    )
    command = _submit_command(payload=_valid_personal_credit_payload())
    service.submit_idempotent(
        SubmitIdempotentProposalCommand(
            payload=command.payload,
            headers=command.headers,
            technical_client_id=command.technical_client_id,
        ),
        context=_context(),
    )

    with pytest.raises(ProposalValidationError) as error:
        service.submit_with_initial_status_and_outbox(command, context=_context())

    assert error.value.code == "missing_initial_status_or_outbox"


def test_replay_with_incompatible_outbox_is_rejected() -> None:
    status_repository = InMemoryProposalIntakeStatusRepository()
    outbox_repository = InMemoryProposalOutboxRepository()
    service = _service(status_repository=status_repository, outbox_repository=outbox_repository)
    command = _submit_command(payload=_valid_personal_credit_payload())
    first = service.submit_with_initial_status_and_outbox(command, context=_context())
    outbox_repository.delete(first.outbox_message.tenant_id, first.outbox_message.deduplication_key)
    outbox_repository.save_pending(
        replace(first.outbox_message, event_type="creditos.proposal.v1.invalid")
    )

    with pytest.raises(ProposalValidationError) as error:
        service.submit_with_initial_status_and_outbox(command, context=_context())

    assert error.value.code == "incompatible_status_or_outbox"


def test_idempotency_conflict_does_not_create_status_or_outbox() -> None:
    status_repository = InMemoryProposalIntakeStatusRepository()
    outbox_repository = InMemoryProposalOutboxRepository()
    service = _service(status_repository=status_repository, outbox_repository=outbox_repository)
    service.submit_with_initial_status_and_outbox(
        _submit_command(payload=_valid_personal_credit_payload()),
        context=_context(),
    )
    conflicting_payload = _valid_personal_credit_payload()
    conflicting_payload["operation"]["requested_terms"]["amount"] = 700_000

    with pytest.raises(IdempotencyConflictError):
        service.submit_with_initial_status_and_outbox(
            _submit_command(payload=conflicting_payload),
            context=_context(),
        )

    assert len(status_repository.list_all()) == 1
    assert len(outbox_repository.list_all()) == 1


def test_invalid_event_context_does_not_persist_status_or_outbox() -> None:
    canonical_repository = InMemoryCanonicalProposalRepository()
    idempotency_repository = InMemoryIdempotentProposalSubmissionRepository()
    status_repository = InMemoryProposalIntakeStatusRepository()
    outbox_repository = InMemoryProposalOutboxRepository()
    service = _service(
        canonical_repository=canonical_repository,
        idempotency_repository=idempotency_repository,
        status_repository=status_repository,
        outbox_repository=outbox_repository,
    )

    with pytest.raises(ProposalValidationError) as error:
        service.submit_with_initial_status_and_outbox(
            _submit_command(payload=_valid_personal_credit_payload()),
            context=_context(tenant_isolation_tier="pooled"),
        )

    assert error.value.code == "invalid_tenant_isolation_tier"
    assert canonical_repository.list_all() == []
    assert idempotency_repository.list_all() == []
    assert status_repository.list_all() == []
    assert outbox_repository.list_all() == []


def test_empty_scopes_do_not_create_contract_incompatible_event() -> None:
    canonical_repository = InMemoryCanonicalProposalRepository()
    idempotency_repository = InMemoryIdempotentProposalSubmissionRepository()
    status_repository = InMemoryProposalIntakeStatusRepository()
    outbox_repository = InMemoryProposalOutboxRepository()
    service = _service(
        canonical_repository=canonical_repository,
        idempotency_repository=idempotency_repository,
        status_repository=status_repository,
        outbox_repository=outbox_repository,
    )
    command = _submit_command(payload=_valid_personal_credit_payload(), scopes=())

    with pytest.raises(ProposalValidationError) as error:
        service.submit_with_initial_status_and_outbox(command, context=_context())

    assert error.value.code == "missing_event_scopes"
    assert canonical_repository.list_all() == []
    assert idempotency_repository.list_all() == []
    assert status_repository.list_all() == []
    assert outbox_repository.list_all() == []


def test_same_idempotency_key_isolated_across_tenants_for_status_and_outbox() -> None:
    status_repository = InMemoryProposalIntakeStatusRepository()
    outbox_repository = InMemoryProposalOutboxRepository()
    service = _service(status_repository=status_repository, outbox_repository=outbox_repository)
    tenant_alpha = service.submit_with_initial_status_and_outbox(
        _submit_command(payload=_valid_personal_credit_payload()),
        context=_context(tenant_id="tenant-bridge-001"),
    )
    tenant_beta_payload = _valid_personal_credit_payload()
    tenant_beta_payload["external_proposal_id"] = "prop-personal-002"
    tenant_beta = service.submit_with_initial_status_and_outbox(
        _submit_command(payload=tenant_beta_payload),
        context=_context(tenant_id="tenant-bridge-002"),
    )

    assert tenant_alpha.proposal.proposal_id != tenant_beta.proposal.proposal_id
    assert {status.tenant_id for status in status_repository.list_all()} == {
        "tenant-bridge-001",
        "tenant-bridge-002",
    }
    assert {message.payload["tenantid"] for message in outbox_repository.list_all()} == {
        "tenant-bridge-001",
        "tenant-bridge-002",
    }


def test_same_external_proposal_id_is_isolated_across_tenants_for_status_and_outbox() -> None:
    canonical_repository = InMemoryCanonicalProposalRepository()
    status_repository = InMemoryProposalIntakeStatusRepository()
    outbox_repository = InMemoryProposalOutboxRepository()
    service = _service(
        canonical_repository=canonical_repository,
        status_repository=status_repository,
        outbox_repository=outbox_repository,
    )
    payload = _valid_personal_credit_payload()

    tenant_alpha = service.submit_with_initial_status_and_outbox(
        _submit_command(payload=payload, idempotency_key="proposal-key-alpha"),
        context=_context(tenant_id="tenant-bridge-001"),
    )
    tenant_beta = service.submit_with_initial_status_and_outbox(
        _submit_command(payload=payload, idempotency_key="proposal-key-beta"),
        context=_context(tenant_id="tenant-bridge-002"),
    )

    assert tenant_alpha.proposal.external_proposal_id == tenant_beta.proposal.external_proposal_id
    assert tenant_alpha.proposal.proposal_id != tenant_beta.proposal.proposal_id
    assert len(canonical_repository.list_all()) == 2
    assert {proposal.tenant_id for proposal in canonical_repository.list_all()} == {
        "tenant-bridge-001",
        "tenant-bridge-002",
    }
    assert {status.tenant_id for status in status_repository.list_all()} == {
        "tenant-bridge-001",
        "tenant-bridge-002",
    }
    assert {message.payload["tenantid"] for message in outbox_repository.list_all()} == {
        "tenant-bridge-001",
        "tenant-bridge-002",
    }


def test_missing_trusted_tenant_does_not_persist_any_submission_state() -> None:
    canonical_repository = InMemoryCanonicalProposalRepository()
    idempotency_repository = InMemoryIdempotentProposalSubmissionRepository()
    status_repository = InMemoryProposalIntakeStatusRepository()
    outbox_repository = InMemoryProposalOutboxRepository()
    service = _service(
        canonical_repository=canonical_repository,
        idempotency_repository=idempotency_repository,
        status_repository=status_repository,
        outbox_repository=outbox_repository,
    )

    with pytest.raises(ProposalValidationError) as error:
        service.submit_with_initial_status_and_outbox(
            _submit_command(payload=_valid_personal_credit_payload()),
            context=_context(tenant_id=None),
        )

    assert error.value.code == "missing_trusted_tenant"
    assert canonical_repository.list_all() == []
    assert idempotency_repository.list_all() == []
    assert status_repository.list_all() == []
    assert outbox_repository.list_all() == []


def test_status_failure_rolls_back_canonical_and_idempotency_without_outbox() -> None:
    canonical_repository = InMemoryCanonicalProposalRepository()
    idempotency_repository = InMemoryIdempotentProposalSubmissionRepository()
    outbox_repository = InMemoryProposalOutboxRepository()
    service = _service(
        canonical_repository=canonical_repository,
        idempotency_repository=idempotency_repository,
        status_repository=FailingProposalIntakeStatusRepository(),
        outbox_repository=outbox_repository,
    )

    with pytest.raises(RuntimeError, match="falha simulada no status"):
        service.submit_with_initial_status_and_outbox(
            _submit_command(payload=_valid_personal_credit_payload()),
            context=_context(),
        )

    assert canonical_repository.list_all() == []
    assert idempotency_repository.list_all() == []
    assert outbox_repository.list_all() == []
    assert [
        event["operation"] for event in service.logged_events if event["status"] == "created"
    ] == []


def test_outbox_failure_rolls_back_status_canonical_and_idempotency() -> None:
    canonical_repository = InMemoryCanonicalProposalRepository()
    idempotency_repository = InMemoryIdempotentProposalSubmissionRepository()
    status_repository = InMemoryProposalIntakeStatusRepository()
    service = _service(
        canonical_repository=canonical_repository,
        idempotency_repository=idempotency_repository,
        status_repository=status_repository,
        outbox_repository=FailingProposalOutboxRepository(),
    )

    with pytest.raises(RuntimeError, match="falha simulada na outbox"):
        service.submit_with_initial_status_and_outbox(
            _submit_command(payload=_valid_personal_credit_payload()),
            context=_context(),
        )

    assert canonical_repository.list_all() == []
    assert idempotency_repository.list_all() == []
    assert status_repository.list_all() == []


def test_cloudevent_payload_is_minimized_and_contract_compatible() -> None:
    service = _service()

    result = service.submit_with_initial_status_and_outbox(
        _submit_command(payload=_valid_personal_credit_payload()),
        context=_context(),
    )
    payload = result.outbox_message.payload

    assert payload["specversion"] == "1.0"
    assert payload["type"] == "creditos.proposal.v1.submitted"
    assert payload["source"] == "creditos://proposal-intake"
    assert payload["subject"] == f"proposal/{result.proposal.proposal_id}"
    assert payload["time"] == "2026-08-16T12:30:45Z"
    assert payload["datacontenttype"] == "application/json"
    assert payload["dataschema"] == "creditos://contracts/asyncapi/events/proposal/v1"
    assert payload["tenantid"] == "tenant-bridge-001"
    assert payload["tenanttier"] == "bridge"
    assert payload["subjectid"] == "subject-client-app-001"
    assert payload["clientid"] == "client-app-001"
    assert payload["principaltype"] == "m2m"
    assert payload["scopes"] == "proposal:submit"
    assert payload["correlationid"] == "corr-proposal-001"
    assert payload["requestid"] == "req-proposal-001"
    assert payload["idempotencykey"] == "proposal-key-0001"
    assert payload["schemaversion"] == "v1"
    assert payload["traceparent"].startswith("00-11111111111111111111111111111111-")
    assert payload["data"] == {
        "proposal_id": result.proposal.proposal_id,
        "external_proposal_id": "prop-personal-001",
        "product_type": "personal_credit",
        "schema_version": "1.0",
        "channel": "api",
        "intake_status": "submitted",
        "provided_data_discarded": True,
        "consents_discarded": False,
        "callback_configured": True,
    }
    assert "_" not in "".join(key for key in payload if key not in {"specversion"})


def test_status_outbox_event_and_logs_do_not_expose_sensitive_data() -> None:
    service = _service()

    result = service.submit_with_initial_status_and_outbox(
        _submit_command(payload=_valid_personal_credit_payload()),
        context=_context(),
    )

    serialized = json.dumps(
        {
            "status": result.intake_status,
            "outbox": result.outbox_message.payload,
            "logs": result.logs,
        },
        default=str,
        ensure_ascii=False,
        sort_keys=True,
    )
    assert "00000000191" not in serialized
    assert "Pessoa Exemplo" not in serialized
    assert "cliente.sensivel@example.com" not in serialized
    assert '"provided_data":' not in serialized
    assert '"consents":' not in serialized
    assert "declared_monthly_income" not in serialized
    assert "Authorization" not in serialized
    assert "token" not in serialized.lower()
    assert "secret" not in serialized.lower()
    assert "500000" not in serialized
    with pytest.raises(FrozenInstanceError):
        result.intake_status.status = "mutated"  # type: ignore[misc]
    with pytest.raises(TypeError):
        result.outbox_message.payload["data"]["intake_status"] = "mutated"  # type: ignore[index]


def _service(
    *,
    canonical_repository: InMemoryCanonicalProposalRepository | None = None,
    idempotency_repository: InMemoryIdempotentProposalSubmissionRepository | None = None,
    status_repository: Any | None = None,
    outbox_repository: Any | None = None,
) -> ProposalIntakeApplicationService:
    return ProposalIntakeApplicationService(
        repository=canonical_repository or InMemoryCanonicalProposalRepository(),
        idempotency_repository=idempotency_repository
        or InMemoryIdempotentProposalSubmissionRepository(),
        intake_status_repository=status_repository or InMemoryProposalIntakeStatusRepository(),
        outbox_repository=outbox_repository or InMemoryProposalOutboxRepository(),
        sensitive_fingerprint_secret=_SENSITIVE_FINGERPRINT_SECRET,
        environment="test",
        clock=lambda: _FIXED_TIME,
        event_id_factory=lambda seed: f"evt_{seed[-24:]}",
    )


def _submit_command(
    *,
    payload: dict[str, Any],
    technical_client_id: str = "client-app-001",
    idempotency_key: str = "proposal-key-0001",
    scopes: tuple[str, ...] = ("proposal:submit",),
) -> SubmitProposalWithInitialStatusCommand:
    return SubmitProposalWithInitialStatusCommand(
        payload=deepcopy(payload),
        headers={
            "Idempotency-Key": idempotency_key,
            "X-Correlation-Id": "corr-proposal-001",
        },
        technical_client_id=technical_client_id,
        subject_id="subject-client-app-001",
        principal_type="m2m",
        scopes=scopes,
    )


def _context(
    tenant_id: str | None = "tenant-bridge-001",
    tenant_isolation_tier: str = "bridge",
) -> ObservabilityContext:
    return ObservabilityContext.new(
        correlation_id="corr-proposal-001",
        request_id="req-proposal-001",
        trace_id="11111111111111111111111111111111",
        tenant_id=tenant_id,
        tenant_isolation_tier=tenant_isolation_tier,
    )


def _valid_personal_credit_payload() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "external_proposal_id": "prop-personal-001",
        "person_type": "PF",
        "product_type": "personal_credit",
        "channel": "api",
        "operation": {
            "requested_terms": {
                "amount": 500_000,
                "currency": "BRL",
                "installments": 6,
                "down_payment": 0,
                "first_due_date": "2026-09-15",
            }
        },
        "borrower": {
            "document_type": "CPF",
            "document": "00000000191",
            "name": "Pessoa Exemplo",
            "birth_date": "1990-01-01",
        },
        "provided_data": {
            "financial": {
                "declared_monthly_income": 800_000,
                "declared_monthly_debt": 120_000,
            }
        },
        "risk_context": {},
        "product_data": {
            "personal_credit": {
                "employment_type": "formal",
                "occupation": "analyst",
                "declared_monthly_income": 800_000,
                "declared_monthly_debt": 120_000,
                "income_source": "salary",
            }
        },
        "decision_options": {
            "execution_mode": "sync",
            "review_strategy": "ai_advisory",
            "fallback_action": "request_more_data",
            "max_wait_ms": 3000,
        },
        "callback": {
            "callback_profile_ref": "tenant-default-creditos-webhook",
            "events": ["creditos.proposal.v1.submitted"],
        },
    }


class FailingProposalIntakeStatusRepository:
    def save_initial(self, status: ProposalIntakeStatus) -> None:
        raise RuntimeError("falha simulada no status")

    def find(self, tenant_id: str, proposal_id: str) -> ProposalIntakeStatus | None:
        return None

    def delete(self, tenant_id: str, proposal_id: str) -> None:
        return None

    def list_all(self) -> list[ProposalIntakeStatus]:
        return []


class FailingProposalOutboxRepository:
    def save_pending(self, message: ProposalOutboxMessage) -> None:
        raise RuntimeError("falha simulada na outbox")

    def find_by_deduplication_key(
        self,
        tenant_id: str,
        deduplication_key: str,
    ) -> ProposalOutboxMessage | None:
        return None

    def delete(self, tenant_id: str, deduplication_key: str) -> None:
        return None

    def list_all(self) -> list[ProposalOutboxMessage]:
        return []
