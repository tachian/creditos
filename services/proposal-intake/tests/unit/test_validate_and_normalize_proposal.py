from __future__ import annotations

from collections.abc import Callable
from dataclasses import FrozenInstanceError
from types import MappingProxyType
from typing import Any

import pytest
from creditos_observability.context import ObservabilityContext
from creditos_proposal_intake.adapters.persistence.in_memory_canonical_proposal_repository import (
    InMemoryCanonicalProposalRepository,
)
from creditos_proposal_intake.application.service import ProposalIntakeApplicationService
from creditos_proposal_intake.application.use_cases.validate_and_normalize_proposal import (
    ValidateAndNormalizeProposalCommand,
)
from creditos_proposal_intake.domain.entities import CanonicalProposal
from creditos_proposal_intake.domain.errors import ProposalValidationError


def test_valid_pf_personal_credit_normalizes_and_persists_minimal_canonical_proposal() -> None:
    repository = InMemoryCanonicalProposalRepository()
    service = ProposalIntakeApplicationService(repository=repository, environment="test")
    command = _command(payload=_valid_personal_credit_payload())

    result = service.validate_and_normalize(command, context=_context())

    assert result.proposal.external_proposal_id == "prop-personal-001"
    assert result.proposal.tenant_id == "tenant-bridge-001"
    assert result.proposal.idempotency_key == "proposal-key-0001"
    assert result.proposal.requested_amount_cents == 500_000
    assert result.proposal.product_type == "personal_credit"
    assert result.proposal.decision_options == {
        "execution_mode": "sync",
        "fallback_action": "request_more_data",
        "max_wait_ms": 3000,
        "review_strategy": "ai_advisory",
    }
    assert result.proposal.risk_context == {}
    assert result.proposal.provided_data_discarded is True
    assert result.proposal.consents_discarded is False
    assert result.proposal.product_data == {
        "personal_credit": {
            "declared_monthly_debt": 120_000,
            "declared_monthly_income": 800_000,
            "employment_type": "formal",
            "income_source": "salary",
            "occupation": "analyst",
        }
    }
    assert repository.get("tenant-bridge-001", "prop-personal-001") == result.proposal
    assert result.logs[-1]["payload"] == "[OMITIDO]"
    assert result.logs[-1]["tenant_id"] == "tenant-bridge-001"

    with pytest.raises(FrozenInstanceError):
        result.proposal.requested_amount_cents = 1  # type: ignore[misc]
    with pytest.raises(TypeError):
        result.proposal.product_data["personal_credit"]["occupation"] = "mutated"


def test_valid_pj_receivables_requires_payer_participant_and_normalizes() -> None:
    repository = InMemoryCanonicalProposalRepository()
    service = ProposalIntakeApplicationService(repository=repository, environment="test")

    result = service.validate_and_normalize(
        _command(payload=_valid_receivables_payload()),
        context=_context(),
    )

    assert result.proposal.person_type == "PJ"
    assert result.proposal.borrower_document_type == "CNPJ"
    assert result.proposal.product_type == "receivables"
    assert result.proposal.product_data["receivables"]["receivables"][0]["payer_ref"] == "payer-001"
    assert result.proposal.product_data["receivables"]["receivables"][0]["face_value"] == 100_000
    with pytest.raises(TypeError):
        result.proposal.product_data["receivables"]["receivables"][0]["face_value"] = 1


@pytest.mark.parametrize(
    ("forbidden_field", "forbidden_value"),
    [
        ("idempotency_key", "body-key-should-fail"),
        ("tenant_id", "tenant-from-body"),
        ("selected_plan", "plan-001"),
        ("plan_id", "plan-001"),
        ("extra_data", {}),
        ("raw_payload", {}),
        ("payload", {}),
        ("custom", {}),
        ("metadata", {}),
        ("attributes", {}),
    ],
)
def test_rejects_forbidden_public_body_fields(
    forbidden_field: str,
    forbidden_value: object,
) -> None:
    service = ProposalIntakeApplicationService(
        repository=InMemoryCanonicalProposalRepository(),
        environment="test",
    )
    payload = _valid_personal_credit_payload() | {forbidden_field: forbidden_value}

    with pytest.raises(ProposalValidationError) as exc_info:
        service.validate_and_normalize(_command(payload=payload), context=_context())

    assert exc_info.value.code == "forbidden_body_field"
    assert exc_info.value.field_path == forbidden_field
    assert "prop-personal-001" not in exc_info.value.safe_message


@pytest.mark.parametrize(
    "mutate",
    [
        lambda payload: payload["borrower"].update(
            {"document_type": "CNPJ", "document": "00000000000191"}
        ),
        lambda payload: payload.update({"person_type": "PJ"}),
        lambda payload: payload.update({"product_type": "receivables"}),
        lambda payload: payload["operation"]["requested_terms"].update({"down_payment": 600_000}),
        lambda payload: payload["operation"]["requested_terms"].update({"amount": 100.50}),
        lambda payload: payload["operation"]["requested_terms"].update(
            {"amount": 1_000_000_000_001}
        ),
        lambda payload: payload["callback"].update({"url": "https://example.com/hook"}),
        lambda payload: payload["callback"].pop("callback_profile_ref"),
        lambda payload: payload["callback"].update({"events": [{"bad": "event"}]}),
        lambda payload: payload["product_data"]["personal_credit"].update({"unknown": "field"}),
        lambda payload: _make_bnpl_payload(payload, {"cart_items_count": 0}),
        lambda payload: (
            payload["participants"][0].update({"role": "admin"})
            if "participants" in payload
            else payload.update(
                {
                    "participants": [
                        {"participant_ref": "participant-001", "role": "admin"},
                    ]
                }
            )
        ),
        lambda payload: payload.update({"decision_options": {"execution_mode": "sync"}}),
        lambda payload: payload.update({"risk_context": {"unknown": "field"}}),
        lambda payload: payload.update({"provided_data": {"contact": {"email": "invalid-email"}}}),
        lambda payload: payload.update({"consents": [{}]}),
        lambda payload: payload["operation"]["requested_terms"].update(
            {"first_due_date": "20260915"}
        ),
        lambda payload: (
            payload["consents"].append(
                {
                    "subject_ref": "borrower",
                    "purpose": "credit_analysis",
                    "source": "customer",
                    "granted_at": "2026-08-14T12:00:00",
                }
            )
            if "consents" in payload
            else payload.update(
                {
                    "consents": [
                        {
                            "subject_ref": "borrower",
                            "purpose": "credit_analysis",
                            "source": "customer",
                            "granted_at": "2026-08-14T12:00:00",
                        }
                    ]
                }
            )
        ),
    ],
)
def test_rejects_semantically_invalid_payloads(mutate: Callable[[dict[str, Any]], None]) -> None:
    service = ProposalIntakeApplicationService(
        repository=InMemoryCanonicalProposalRepository(),
        environment="test",
    )
    payload = _valid_personal_credit_payload()
    mutate(payload)

    with pytest.raises(ProposalValidationError):
        service.validate_and_normalize(_command(payload=payload), context=_context())


def test_rejects_receivable_without_matching_payer_participant() -> None:
    service = ProposalIntakeApplicationService(
        repository=InMemoryCanonicalProposalRepository(),
        environment="test",
    )
    payload = _valid_receivables_payload()
    payload["participants"] = []

    with pytest.raises(ProposalValidationError) as exc_info:
        service.validate_and_normalize(_command(payload=payload), context=_context())

    assert exc_info.value.code == "invalid_receivable_payer"
    assert exc_info.value.field_path == "product_data.receivables.receivables[0].payer_ref"


def test_rejects_critical_participant_without_complete_identity() -> None:
    service = ProposalIntakeApplicationService(
        repository=InMemoryCanonicalProposalRepository(),
        environment="test",
    )
    payload = _valid_receivables_payload()
    payload["participants"][0].pop("document")

    with pytest.raises(ProposalValidationError) as exc_info:
        service.validate_and_normalize(_command(payload=payload), context=_context())

    assert exc_info.value.code == "incomplete_critical_participant"


@pytest.mark.parametrize(
    ("field_path", "mutate"),
    [
        (
            "external_proposal_id",
            lambda payload: payload.update({"external_proposal_id": "000.000.001-91"}),
        ),
        (
            "callback.callback_profile_ref",
            lambda payload: payload["callback"].update(
                {"callback_profile_ref": "cliente.sensivel@example.com"}
            ),
        ),
        (
            "external_proposal_id",
            lambda payload: payload.update({"external_proposal_id": "prop with spaces"}),
        ),
    ],
)
def test_rejects_sensitive_values_in_public_identifiers(
    field_path: str,
    mutate: Callable[[dict[str, Any]], None],
) -> None:
    service = ProposalIntakeApplicationService(
        repository=InMemoryCanonicalProposalRepository(),
        environment="test",
    )
    payload = _valid_personal_credit_payload()
    mutate(payload)

    with pytest.raises(ProposalValidationError) as exc_info:
        service.validate_and_normalize(_command(payload=payload), context=_context())

    assert exc_info.value.field_path == field_path
    assert exc_info.value.details == {"reason": "unsafe_identifier"}


def test_requires_idempotency_key_header_and_keeps_errors_and_logs_safe() -> None:
    repository = InMemoryCanonicalProposalRepository()
    service = ProposalIntakeApplicationService(repository=repository, environment="test")
    payload = _valid_personal_credit_payload()
    payload["provided_data"] = {
        "contact": {"email": "cliente.sensivel@example.com", "phone": "11999999999"}
    }
    command = _command(payload=payload, headers={"authorization": "Bearer secret-token"})

    with pytest.raises(ProposalValidationError) as exc_info:
        service.validate_and_normalize(command, context=_context())

    assert exc_info.value.code == "missing_idempotency_key"
    assert "cliente.sensivel@example.com" not in exc_info.value.safe_message
    assert "secret-token" not in exc_info.value.safe_message
    assert repository.list_all() == []
    log_text = repr(service.logged_events)
    assert "00000000191" not in log_text
    assert "cliente.sensivel@example.com" not in log_text
    assert "secret-token" not in log_text
    assert "500000" not in log_text


def test_rejects_malformed_headers_with_safe_errors() -> None:
    service = ProposalIntakeApplicationService(
        repository=InMemoryCanonicalProposalRepository(),
        environment="test",
    )

    with pytest.raises(ProposalValidationError) as exc_info:
        service.validate_and_normalize(
            ValidateAndNormalizeProposalCommand(
                payload=_valid_personal_credit_payload(),
                headers=[("Idempotency-Key", "proposal-key-0001")],  # type: ignore[arg-type]
            ),
            context=_context(),
        )

    assert exc_info.value.code == "invalid_headers"
    assert exc_info.value.field_path == "headers"


def test_rejects_case_ambiguous_idempotency_headers() -> None:
    service = ProposalIntakeApplicationService(
        repository=InMemoryCanonicalProposalRepository(),
        environment="test",
    )

    with pytest.raises(ProposalValidationError) as exc_info:
        service.validate_and_normalize(
            _command(
                payload=_valid_personal_credit_payload(),
                headers={
                    "Idempotency-Key": "proposal-key-0001",
                    "idempotency-key": "proposal-key-0002",
                },
            ),
            context=_context(),
        )

    assert exc_info.value.code == "duplicate_header"
    assert exc_info.value.field_path == "headers.Idempotency-Key"


def test_result_logs_are_only_for_current_call() -> None:
    service = ProposalIntakeApplicationService(
        repository=InMemoryCanonicalProposalRepository(),
        environment="test",
    )

    first = service.validate_and_normalize(
        _command(payload=_valid_personal_credit_payload()),
        context=_context(),
    )
    second_payload = _valid_personal_credit_payload()
    second_payload["external_proposal_id"] = "prop-personal-002"
    second = service.validate_and_normalize(_command(payload=second_payload), context=_context())

    assert len(first.logs) == 1
    assert len(second.logs) == 1
    assert len(service.logged_events) == 2


def test_rejects_invalid_brazilian_document_check_digits() -> None:
    service = ProposalIntakeApplicationService(
        repository=InMemoryCanonicalProposalRepository(),
        environment="test",
    )
    payload = _valid_personal_credit_payload()
    payload["borrower"]["document"] = "00000000192"

    with pytest.raises(ProposalValidationError) as exc_info:
        service.validate_and_normalize(_command(payload=payload), context=_context())

    assert exc_info.value.field_path == "borrower.document"


def test_canonical_proposal_deep_freezes_pre_wrapped_mapping_proxy() -> None:
    proposal = service_proposal_with_mapping_proxy()

    with pytest.raises(TypeError):
        proposal.product_data["personal_credit"]["occupation"] = "mutated"


def service_proposal_with_mapping_proxy() -> CanonicalProposal:
    return CanonicalProposal(
        tenant_id="tenant-bridge-001",
        idempotency_key="proposal-key-0001",
        schema_version="1.0",
        external_proposal_id="prop-personal-001",
        person_type="PF",
        product_type="personal_credit",
        channel="api",
        borrower_document_type="CPF",
        requested_amount_cents=500_000,
        requested_terms=MappingProxyType({"amount": 500_000, "currency": "BRL"}),
        product_data=MappingProxyType({"personal_credit": {"occupation": "analyst"}}),
    )


def _context() -> ObservabilityContext:
    return ObservabilityContext.new(
        correlation_id="corr-proposal-001",
        request_id="req-proposal-001",
        tenant_id="tenant-bridge-001",
        tenant_isolation_tier="bridge",
    )


def _command(
    *,
    payload: dict[str, Any],
    headers: dict[str, str] | None = None,
) -> ValidateAndNormalizeProposalCommand:
    return ValidateAndNormalizeProposalCommand(
        payload=payload,
        headers=headers
        if headers is not None
        else {
            "Idempotency-Key": "proposal-key-0001",
            "X-Correlation-Id": "corr-proposal-001",
        },
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


def _make_bnpl_payload(payload: dict[str, Any], extra_bnpl: dict[str, Any]) -> None:
    payload["product_type"] = "bnpl"
    payload["channel"] = "checkout"
    payload["product_data"] = {
        "bnpl": {
            "merchant_reference": "merchant-001",
            "order_reference": "order-001",
            **extra_bnpl,
        }
    }


def _valid_receivables_payload() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "external_proposal_id": "prop-receivables-001",
        "person_type": "PJ",
        "product_type": "receivables",
        "channel": "api",
        "operation": {"requested_terms": {"amount": 200_000, "currency": "BRL"}},
        "borrower": {
            "document_type": "CNPJ",
            "document": "00000000000191",
            "legal_name": "Cedente Exemplo Ltda",
        },
        "participants": [
            {
                "participant_ref": "payer-001",
                "role": "payer",
                "person_type": "PJ",
                "document_type": "CNPJ",
                "document": "00000000000191",
                "legal_name": "Sacado Exemplo Ltda",
            }
        ],
        "product_data": {
            "receivables": {
                "receivables": [
                    {
                        "external_receivable_id": "rec-001",
                        "payer_ref": "payer-001",
                        "face_value": 100_000,
                        "due_date": "2026-10-10",
                    }
                ]
            }
        },
    }
