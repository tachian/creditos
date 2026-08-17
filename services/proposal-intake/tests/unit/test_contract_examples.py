from __future__ import annotations

import json
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
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
    SubmitProposalWithInitialStatusCommand,
)
from creditos_proposal_intake.domain.errors import ProposalValidationError

ROOT = Path(__file__).resolve().parents[4]
PROPOSAL_SCHEMA = (
    ROOT / "packages" / "contracts" / "schemas" / "proposal" / "v1" / ("proposal.schema.json")
)
_SENSITIVE_FINGERPRINT_SECRET = "segredo-local-de-teste-com-32-caracteres"
_FIXED_TIME = datetime(2026, 8, 16, 12, 30, 45, tzinfo=UTC)


def test_public_contract_valid_examples_are_accepted_by_runtime() -> None:
    schema = _proposal_schema()
    accepted_products: set[str] = set()
    accepted_person_types: set[str] = set()

    for index, example in enumerate(schema["examples"]):
        service = _service()
        result = service.submit_with_initial_status_and_outbox(
            _submit_command(payload=example, idempotency_key=f"contract-example-{index:02d}"),
            context=_context(),
        )

        accepted_products.add(result.proposal.product_type)
        accepted_person_types.add(result.proposal.person_type)
        assert result.idempotency_status == "created"
        assert result.proposal.external_proposal_id == example["external_proposal_id"]
        assert result.proposal.tenant_id == "tenant-bridge-001"
        assert result.proposal.schema_version == "1.0"
        assert (
            result.proposal.requested_amount_cents
            == example["operation"]["requested_terms"]["amount"]
        )
        assert set(result.proposal.product_data) == {example["product_type"]}
        assert result.proposal.provided_data_discarded == ("provided_data" in example)
        assert result.proposal.consents_discarded == ("consents" in example)
        assert result.outbox_message.payload["type"] == "creditos.proposal.v1.submitted"
        assert result.outbox_message.payload["data"]["product_type"] == result.proposal.product_type
        assert result.outbox_message.payload["data"]["proposal_id"] == result.proposal.proposal_id

    assert accepted_products == {"personal_credit", "bnpl", "business_credit", "receivables"}
    assert accepted_person_types >= {"PF", "PJ"}


def test_public_contract_invalid_examples_are_rejected_without_persistence() -> None:
    schema = _proposal_schema()

    for index, example in enumerate(schema["x-creditos"]["invalidExamples"]):
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
                _submit_command(payload=example, idempotency_key=f"contract-invalid-{index:02d}"),
                context=_context(),
            )

        assert error.value.code
        assert _serialized(error.value) == _redacted_error_text(error.value)
        assert _serialized(service.logged_events) == _redacted_error_text(service.logged_events)
        assert canonical_repository.list_all() == []
        assert idempotency_repository.list_all() == []
        assert status_repository.list_all() == []
        assert outbox_repository.list_all() == []


def _proposal_schema() -> dict[str, Any]:
    return json.loads(PROPOSAL_SCHEMA.read_text(encoding="utf-8"))


def _service(
    *,
    canonical_repository: InMemoryCanonicalProposalRepository | None = None,
    idempotency_repository: InMemoryIdempotentProposalSubmissionRepository | None = None,
    status_repository: InMemoryProposalIntakeStatusRepository | None = None,
    outbox_repository: InMemoryProposalOutboxRepository | None = None,
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
    idempotency_key: str,
) -> SubmitProposalWithInitialStatusCommand:
    return SubmitProposalWithInitialStatusCommand(
        payload=deepcopy(payload),
        headers={
            "Idempotency-Key": idempotency_key,
            "X-Correlation-Id": "corr-contract-001",
        },
        technical_client_id="client-contract-tests",
        subject_id="subject-client-contract-tests",
        principal_type="m2m",
        scopes=("proposal:submit",),
    )


def _context() -> ObservabilityContext:
    return ObservabilityContext.new(
        correlation_id="corr-contract-001",
        request_id="req-contract-001",
        trace_id="11111111111111111111111111111111",
        tenant_id="tenant-bridge-001",
        tenant_isolation_tier="bridge",
    )


def _serialized(value: object) -> str:
    return json.dumps(value, default=str, ensure_ascii=False, sort_keys=True)


def _redacted_error_text(value: object) -> str:
    serialized = _serialized(value)
    sensitive_fragments = {
        "00000000191",
        "00000000000191",
        "Pessoa Exemplo",
        "Empresa Exemplo",
        "declared_monthly_income",
        "declared_monthly_revenue",
        '"provided_data":',
        '"consents":',
        "Authorization",
        "Bearer",
        "secret",
        "token",
    }
    for fragment in sensitive_fragments:
        assert fragment not in serialized
    return serialized
