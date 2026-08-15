from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import FrozenInstanceError
from time import sleep
from typing import Any

import pytest
from creditos_observability.context import ObservabilityContext
from creditos_proposal_intake.adapters.persistence import (
    InMemoryCanonicalProposalRepository,
    InMemoryIdempotentProposalSubmissionRepository,
)
from creditos_proposal_intake.application.service import (
    ProposalIntakeApplicationService,
    SubmitIdempotentProposalCommand,
)
from creditos_proposal_intake.domain.entities import CanonicalProposal
from creditos_proposal_intake.domain.errors import (
    IdempotencyConflictError,
    ProposalValidationError,
)

_SENSITIVE_FINGERPRINT_SECRET = "segredo-local-de-teste-com-32-caracteres"


def test_new_idempotent_submission_creates_one_proposal_and_documented_result() -> None:
    canonical_repository = InMemoryCanonicalProposalRepository()
    idempotency_repository = InMemoryIdempotentProposalSubmissionRepository()
    service = ProposalIntakeApplicationService(
        repository=canonical_repository,
        idempotency_repository=idempotency_repository,
        sensitive_fingerprint_secret=_SENSITIVE_FINGERPRINT_SECRET,
        environment="test",
    )

    result = service.submit_idempotent(
        _submit_command(payload=_valid_personal_credit_payload()),
        context=_context(),
    )

    assert result.idempotency_status == "created"
    assert result.submission_result["proposal_id"].startswith("proposal_")
    assert result.submission_result == {
        "proposal_id": result.submission_result["proposal_id"],
        "external_proposal_id": "prop-personal-001",
        "schema_version": "1.0",
        "product_type": "personal_credit",
        "status": "accepted",
    }
    assert result.proposal.proposal_id == result.submission_result["proposal_id"]
    assert len(canonical_repository.list_all()) == 1
    assert len(idempotency_repository.list_all()) == 1
    assert idempotency_repository.list_all()[0].technical_client_id == "client-app-001"
    assert idempotency_repository.list_all()[0].proposal_fingerprint.startswith("sha256:")
    assert result.logs[-1]["status"] == "created"
    assert result.logs[-1]["extra"]["technical_client_id"] == "client-app-001"
    assert result.logs[-1]["payload"] == "[OMITIDO]"


def test_equivalent_retry_returns_original_result_without_saving_new_proposal() -> None:
    canonical_repository = InMemoryCanonicalProposalRepository()
    service = ProposalIntakeApplicationService(
        repository=canonical_repository,
        idempotency_repository=InMemoryIdempotentProposalSubmissionRepository(),
        sensitive_fingerprint_secret=_SENSITIVE_FINGERPRINT_SECRET,
        environment="test",
    )
    command = _submit_command(payload=_valid_personal_credit_payload())

    first = service.submit_idempotent(command, context=_context())
    second = service.submit_idempotent(command, context=_context())

    assert second.idempotency_status == "replayed"
    assert second.submission_result == first.submission_result
    assert second.proposal == first.proposal
    assert len(canonical_repository.list_all()) == 1
    assert second.logs[-1]["status"] == "replayed"


def test_same_key_with_incompatible_payload_raises_safe_conflict_and_does_not_save() -> None:
    canonical_repository = InMemoryCanonicalProposalRepository()
    service = ProposalIntakeApplicationService(
        repository=canonical_repository,
        idempotency_repository=InMemoryIdempotentProposalSubmissionRepository(),
        sensitive_fingerprint_secret=_SENSITIVE_FINGERPRINT_SECRET,
        environment="test",
    )
    service.submit_idempotent(
        _submit_command(payload=_valid_personal_credit_payload()),
        context=_context(),
    )
    conflicting_payload = _valid_personal_credit_payload()
    conflicting_payload["operation"]["requested_terms"]["amount"] = 700_000

    with pytest.raises(IdempotencyConflictError) as exc_info:
        service.submit_idempotent(
            _submit_command(payload=conflicting_payload),
            context=_context(),
        )

    assert exc_info.value.code == "idempotency_conflict"
    assert exc_info.value.safe_message == "conflito de idempotência"
    assert exc_info.value.field_path == "headers.Idempotency-Key"
    assert len(canonical_repository.list_all()) == 1
    assert service.logged_events[-1]["extra"]["attempted_proposal_fingerprint"].startswith(
        "sha256:"
    )
    assert service.logged_events[-1]["extra"]["existing_proposal_fingerprint"].startswith("sha256:")
    log_text = repr(service.logged_events)
    assert "00000000191" not in log_text
    assert "Pessoa Exemplo" not in log_text
    assert "700000" not in log_text
    assert "500000" not in log_text


def test_same_key_does_not_collide_across_tenants_or_technical_clients() -> None:
    canonical_repository = InMemoryCanonicalProposalRepository()
    idempotency_repository = InMemoryIdempotentProposalSubmissionRepository()
    service = ProposalIntakeApplicationService(
        repository=canonical_repository,
        idempotency_repository=idempotency_repository,
        sensitive_fingerprint_secret=_SENSITIVE_FINGERPRINT_SECRET,
        environment="test",
    )

    tenant_alpha = service.submit_idempotent(
        _submit_command(payload=_valid_personal_credit_payload()),
        context=_context(tenant_id="tenant-bridge-001"),
    )
    tenant_beta_payload = _valid_personal_credit_payload()
    tenant_beta_payload["external_proposal_id"] = "prop-personal-002"
    tenant_beta = service.submit_idempotent(
        _submit_command(payload=tenant_beta_payload),
        context=_context(tenant_id="tenant-bridge-002"),
    )
    client_beta_payload = _valid_personal_credit_payload()
    client_beta_payload["external_proposal_id"] = "prop-personal-003"
    client_beta = service.submit_idempotent(
        _submit_command(payload=client_beta_payload, technical_client_id="client-app-002"),
        context=_context(tenant_id="tenant-bridge-001"),
    )

    assert tenant_alpha.idempotency_status == "created"
    assert tenant_beta.idempotency_status == "created"
    assert client_beta.idempotency_status == "created"
    assert len(idempotency_repository.list_all()) == 3
    assert len(canonical_repository.list_all()) == 3


def test_rejects_missing_or_unsafe_technical_client_id() -> None:
    service = ProposalIntakeApplicationService(
        repository=InMemoryCanonicalProposalRepository(),
        idempotency_repository=InMemoryIdempotentProposalSubmissionRepository(),
        sensitive_fingerprint_secret=_SENSITIVE_FINGERPRINT_SECRET,
        environment="test",
    )

    with pytest.raises(ProposalValidationError) as exc_info:
        service.submit_idempotent(
            _submit_command(
                payload=_valid_personal_credit_payload(),
                technical_client_id="cliente.sensivel@example.com",
            ),
            context=_context(),
        )

    assert exc_info.value.code == "invalid_technical_client"
    assert exc_info.value.field_path == "technical_client_id"
    log_text = repr(service.logged_events)
    assert "cliente.sensivel@example.com" not in log_text


def test_rejects_technical_client_id_with_embedded_document() -> None:
    service = ProposalIntakeApplicationService(
        repository=InMemoryCanonicalProposalRepository(),
        idempotency_repository=InMemoryIdempotentProposalSubmissionRepository(),
        sensitive_fingerprint_secret=_SENSITIVE_FINGERPRINT_SECRET,
        environment="test",
    )

    with pytest.raises(ProposalValidationError):
        service.submit_idempotent(
            _submit_command(
                payload=_valid_personal_credit_payload(),
                technical_client_id="client-00000000191",
            ),
            context=_context(),
        )


def test_same_key_with_different_borrower_document_is_conflict_without_raw_document() -> None:
    service = ProposalIntakeApplicationService(
        repository=InMemoryCanonicalProposalRepository(),
        idempotency_repository=InMemoryIdempotentProposalSubmissionRepository(),
        sensitive_fingerprint_secret=_SENSITIVE_FINGERPRINT_SECRET,
        environment="test",
    )
    service.submit_idempotent(
        _submit_command(payload=_valid_personal_credit_payload()),
        context=_context(),
    )
    conflicting_payload = _valid_personal_credit_payload()
    conflicting_payload["borrower"]["document"] = "00000000272"

    with pytest.raises(IdempotencyConflictError):
        service.submit_idempotent(
            _submit_command(payload=conflicting_payload),
            context=_context(),
        )

    log_text = repr(service.logged_events)
    assert "00000000191" not in log_text
    assert "00000000272" not in log_text


def test_empty_discarded_optional_blocks_are_equivalent_for_idempotency() -> None:
    service = ProposalIntakeApplicationService(
        repository=InMemoryCanonicalProposalRepository(),
        idempotency_repository=InMemoryIdempotentProposalSubmissionRepository(),
        sensitive_fingerprint_secret=_SENSITIVE_FINGERPRINT_SECRET,
        environment="test",
    )
    payload_with_empty_blocks = _valid_personal_credit_payload()
    payload_with_empty_blocks["provided_data"] = {}
    payload_with_empty_blocks["consents"] = []
    first = service.submit_idempotent(
        _submit_command(payload=payload_with_empty_blocks),
        context=_context(),
    )
    payload_without_blocks = _valid_personal_credit_payload()
    payload_without_blocks.pop("provided_data")

    second = service.submit_idempotent(
        _submit_command(payload=payload_without_blocks),
        context=_context(),
    )

    assert second.idempotency_status == "replayed"
    assert second.submission_result == first.submission_result


def test_new_key_with_existing_external_proposal_id_is_rejected_without_overwrite() -> None:
    canonical_repository = InMemoryCanonicalProposalRepository()
    service = ProposalIntakeApplicationService(
        repository=canonical_repository,
        idempotency_repository=InMemoryIdempotentProposalSubmissionRepository(),
        sensitive_fingerprint_secret=_SENSITIVE_FINGERPRINT_SECRET,
        environment="test",
    )
    first = service.submit_idempotent(
        _submit_command(payload=_valid_personal_credit_payload()),
        context=_context(),
    )

    with pytest.raises(ProposalValidationError) as exc_info:
        service.submit_idempotent(
            _submit_command(
                payload=_valid_personal_credit_payload(),
                idempotency_key="proposal-key-0002",
            ),
            context=_context(),
        )

    assert exc_info.value.code == "duplicate_external_proposal_id"
    assert canonical_repository.get("tenant-bridge-001", "prop-personal-001") == first.proposal


def test_idempotency_record_rolls_back_when_canonical_save_fails() -> None:
    canonical_repository = FailingCanonicalProposalRepository()
    idempotency_repository = InMemoryIdempotentProposalSubmissionRepository()
    service = ProposalIntakeApplicationService(
        repository=canonical_repository,
        idempotency_repository=idempotency_repository,
        sensitive_fingerprint_secret=_SENSITIVE_FINGERPRINT_SECRET,
        environment="test",
    )

    with pytest.raises(RuntimeError, match="falha simulada"):
        service.submit_idempotent(
            _submit_command(payload=_valid_personal_credit_payload()),
            context=_context(),
        )

    assert idempotency_repository.list_all() == []


def test_in_memory_idempotency_adapter_returns_single_created_under_concurrency() -> None:
    service = ProposalIntakeApplicationService(
        repository=InMemoryCanonicalProposalRepository(),
        idempotency_repository=InMemoryIdempotentProposalSubmissionRepository(),
        sensitive_fingerprint_secret=_SENSITIVE_FINGERPRINT_SECRET,
        environment="test",
    )

    def submit() -> str:
        result = service.submit_idempotent(
            _submit_command(payload=_valid_personal_credit_payload()),
            context=_context(),
        )
        return result.idempotency_status

    with ThreadPoolExecutor(max_workers=8) as executor:
        statuses = list(executor.map(lambda _: submit(), range(8)))

    assert statuses.count("created") == 1
    assert statuses.count("replayed") == 7


def test_idempotent_submission_domain_objects_are_immutable() -> None:
    service = ProposalIntakeApplicationService(
        repository=InMemoryCanonicalProposalRepository(),
        idempotency_repository=InMemoryIdempotentProposalSubmissionRepository(),
        sensitive_fingerprint_secret=_SENSITIVE_FINGERPRINT_SECRET,
        environment="test",
    )

    result = service.submit_idempotent(
        _submit_command(payload=_valid_personal_credit_payload()),
        context=_context(),
    )

    with pytest.raises(FrozenInstanceError):
        result.proposal.proposal_id = "mutated"  # type: ignore[misc]
    submission_result: Any = result.submission_result
    with pytest.raises(TypeError):
        submission_result["status"] = "mutated"


def _submit_command(
    *,
    payload: dict[str, Any],
    technical_client_id: str = "client-app-001",
    idempotency_key: str = "proposal-key-0001",
) -> SubmitIdempotentProposalCommand:
    return SubmitIdempotentProposalCommand(
        payload=deepcopy(payload),
        headers={
            "Idempotency-Key": idempotency_key,
            "X-Correlation-Id": "corr-proposal-001",
        },
        technical_client_id=technical_client_id,
    )


def _context(tenant_id: str = "tenant-bridge-001") -> ObservabilityContext:
    return ObservabilityContext.new(
        correlation_id="corr-proposal-001",
        request_id="req-proposal-001",
        tenant_id=tenant_id,
        tenant_isolation_tier="bridge",
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


class FailingCanonicalProposalRepository:
    def save(self, proposal: CanonicalProposal) -> None:
        raise RuntimeError("falha simulada")

    def get(self, tenant_id: str, external_proposal_id: str) -> CanonicalProposal | None:
        return None


