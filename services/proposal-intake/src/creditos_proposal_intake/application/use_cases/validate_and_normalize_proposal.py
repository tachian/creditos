from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from creditos_proposal_intake.application.ports import CanonicalProposalRepository
from creditos_proposal_intake.domain.entities import CanonicalProposal
from creditos_proposal_intake.domain.errors import ProposalValidationError
from creditos_proposal_intake.domain.value_objects.dates import (
    normalize_iso_datetime,
    require_iso_date,
)
from creditos_proposal_intake.domain.value_objects.documents import normalize_document
from creditos_proposal_intake.domain.value_objects.money import require_money_cents

_FORBIDDEN_BODY_FIELDS = frozenset(
    {
        "idempotency_key",
        "tenant_id",
        "selected_plan",
        "plan_id",
        "extra_data",
        "raw_payload",
        "payload",
        "custom",
        "metadata",
        "attributes",
    }
)
_TOP_LEVEL_FIELDS = frozenset(
    {
        "schema_version",
        "external_proposal_id",
        "person_type",
        "product_type",
        "channel",
        "operation",
        "borrower",
        "participants",
        "consents",
        "provided_data",
        "risk_context",
        "product_data",
        "decision_options",
        "callback",
    }
)
_REQUIRED_TOP_LEVEL_FIELDS = frozenset(
    {
        "schema_version",
        "external_proposal_id",
        "person_type",
        "product_type",
        "channel",
        "operation",
        "borrower",
        "product_data",
    }
)
_PRODUCT_TYPES = frozenset({"personal_credit", "bnpl", "business_credit", "receivables"})
_PERSON_TYPES = frozenset({"PF", "PJ"})
_CHANNELS = frozenset({"api", "batch", "portal", "partner", "checkout", "backoffice"})
_CRITICAL_PARTICIPANT_ROLES = frozenset(
    {
        "guarantor",
        "co_borrower",
        "payer",
        "shareholder",
        "legal_representative",
        "beneficial_owner",
    }
)
_PARTICIPANT_ROLES = frozenset(
    {
        "legal_representative",
        "shareholder",
        "guarantor",
        "co_borrower",
        "merchant",
        "seller",
        "payer",
        "assignor",
        "employer",
        "beneficial_owner",
    }
)
_MONEY_FIELDS = frozenset(
    {
        "declared_monthly_income",
        "declared_monthly_debt",
        "declared_monthly_revenue",
        "declared_cash_flow",
        "face_value",
    }
)
_SENSITIVE_IDENTIFIER_PATTERN = re.compile(
    r"(^\d{10,15}$|[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}|"
    r"bearer|token|secret|password|authorization)",
    re.IGNORECASE,
)
_PUBLIC_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,119}$")
_IDEMPOTENCY_KEY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{7,119}$")
_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_MAX_NESTING_DEPTH = 12


@dataclass(frozen=True, slots=True)
class ValidateAndNormalizeProposalCommand:
    payload: Mapping[str, Any]
    headers: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class ValidateAndNormalizeProposalResult:
    proposal: CanonicalProposal


class ValidateAndNormalizeProposal:
    def __init__(self, *, repository: CanonicalProposalRepository) -> None:
        self._repository = repository

    def execute(
        self,
        command: ValidateAndNormalizeProposalCommand,
        *,
        tenant_id: str,
    ) -> ValidateAndNormalizeProposalResult:
        payload = _require_mapping(command.payload, "body")
        idempotency_key = _require_idempotency_key(command.headers)
        _reject_forbidden_body_fields(payload)
        _reject_unknown_fields(payload, _TOP_LEVEL_FIELDS, "body")
        _require_fields(payload, _REQUIRED_TOP_LEVEL_FIELDS, "body")

        schema_version = _require_const(payload["schema_version"], "1.0", "schema_version")
        external_proposal_id = _require_public_identifier(
            payload["external_proposal_id"],
            field_path="external_proposal_id",
            max_length=120,
        )
        person_type = _require_enum(payload["person_type"], _PERSON_TYPES, "person_type")
        product_type = _require_enum(payload["product_type"], _PRODUCT_TYPES, "product_type")
        channel = _require_enum(payload["channel"], _CHANNELS, "channel")

        requested_terms = _normalize_requested_terms(payload["operation"])
        borrower_document_type = _validate_borrower(payload["borrower"], person_type=person_type)
        participants = _normalize_participants(payload.get("participants", []))
        product_data = _normalize_product_data(
            payload["product_data"],
            product_type=product_type,
            participants=participants,
        )
        callback_profile_ref = _normalize_callback(payload.get("callback"))
        optional_structures = _normalize_optional_structures(payload)

        proposal = CanonicalProposal(
            tenant_id=tenant_id,
            idempotency_key=idempotency_key,
            schema_version=schema_version,
            external_proposal_id=external_proposal_id,
            person_type=person_type,
            product_type=product_type,
            channel=channel,
            borrower_document_type=borrower_document_type,
            requested_amount_cents=requested_terms["amount"],
            requested_terms=MappingProxyType(requested_terms),
            product_data=MappingProxyType(product_data),
            participants=tuple(MappingProxyType(participant) for participant in participants),
            risk_context=MappingProxyType(optional_structures["risk_context"]),
            decision_options=MappingProxyType(optional_structures["decision_options"]),
            provided_data_discarded=optional_structures["provided_data_discarded"],
            consents_discarded=optional_structures["consents_discarded"],
            callback_profile_ref=callback_profile_ref,
        )
        self._repository.save(proposal)
        return ValidateAndNormalizeProposalResult(proposal=proposal)


def _require_idempotency_key(headers: Mapping[str, str]) -> str:
    if not isinstance(headers, Mapping):
        raise ProposalValidationError(
            "headers inválidos",
            code="invalid_headers",
            field_path="headers",
        )
    for key, value in headers.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise ProposalValidationError(
                "headers inválidos",
                code="invalid_headers",
                field_path="headers",
            )
    lowered_keys = [key.lower() for key in headers]
    if len(lowered_keys) != len(set(lowered_keys)):
        raise ProposalValidationError(
            "header duplicado",
            code="duplicate_header",
            field_path="headers.Idempotency-Key",
        )
    normalized_headers = {key.lower(): value for key, value in headers.items()}
    value = normalized_headers.get("idempotency-key")
    if value is None:
        raise ProposalValidationError(
            "chave de idempotência ausente",
            code="missing_idempotency_key",
            field_path="headers.Idempotency-Key",
        )
    return _require_public_identifier(
        value,
        field_path="headers.Idempotency-Key",
        max_length=120,
        pattern=_IDEMPOTENCY_KEY_PATTERN,
    )


def _reject_forbidden_body_fields(payload: Mapping[str, Any]) -> None:
    for field_name in _FORBIDDEN_BODY_FIELDS:
        if field_name in payload:
            raise ProposalValidationError(
                "campo não permitido no body público",
                code="forbidden_body_field",
                field_path=field_name,
                details={"field": field_name},
            )


def _normalize_requested_terms(operation: object) -> dict[str, Any]:
    operation_payload = _require_mapping(operation, "operation")
    _reject_unknown_fields(operation_payload, {"requested_terms"}, "operation")
    _require_fields(operation_payload, {"requested_terms"}, "operation")
    requested_terms = _require_mapping(
        operation_payload["requested_terms"], "operation.requested_terms"
    )
    allowed_fields = {"amount", "currency", "installments", "down_payment", "first_due_date"}
    _reject_unknown_fields(requested_terms, allowed_fields, "operation.requested_terms")
    _require_fields(requested_terms, {"amount", "currency"}, "operation.requested_terms")

    amount = require_money_cents(
        requested_terms["amount"],
        field_path="operation.requested_terms.amount",
    )
    currency = _require_const(
        requested_terms["currency"],
        "BRL",
        "operation.requested_terms.currency",
    )
    normalized: dict[str, Any] = {"amount": amount, "currency": currency}
    if "installments" in requested_terms:
        normalized["installments"] = _require_positive_integer(
            requested_terms["installments"],
            field_path="operation.requested_terms.installments",
        )
    if "down_payment" in requested_terms:
        down_payment = require_money_cents(
            requested_terms["down_payment"],
            field_path="operation.requested_terms.down_payment",
            allow_zero=True,
        )
        if down_payment > amount:
            raise ProposalValidationError(
                "entrada não pode exceder o valor solicitado",
                field_path="operation.requested_terms.down_payment",
                details={"rule": "down_payment_lte_amount"},
            )
        normalized["down_payment"] = down_payment
    if "first_due_date" in requested_terms:
        normalized["first_due_date"] = require_iso_date(
            requested_terms["first_due_date"],
            field_path="operation.requested_terms.first_due_date",
        )
    return normalized


def _validate_borrower(borrower: object, *, person_type: str) -> str:
    borrower_payload = _require_mapping(borrower, "borrower")
    allowed_fields = {
        "document_type",
        "document",
        "name",
        "birth_date",
        "legal_name",
        "trade_name",
        "foundation_date",
    }
    _reject_unknown_fields(borrower_payload, allowed_fields, "borrower")
    _require_fields(borrower_payload, {"document_type", "document"}, "borrower")
    expected_document_type = "CPF" if person_type == "PF" else "CNPJ"
    document_type = _require_const(
        borrower_payload["document_type"],
        expected_document_type,
        "borrower.document_type",
    )
    normalize_document(
        borrower_payload["document"],
        document_type=document_type,
        field_path="borrower.document",
    )
    if person_type == "PF":
        _require_text(borrower_payload.get("name"), field_path="borrower.name", max_length=160)
    else:
        _require_text(
            borrower_payload.get("legal_name"),
            field_path="borrower.legal_name",
            max_length=180,
        )
    if "birth_date" in borrower_payload:
        require_iso_date(borrower_payload["birth_date"], field_path="borrower.birth_date")
    if "foundation_date" in borrower_payload:
        require_iso_date(borrower_payload["foundation_date"], field_path="borrower.foundation_date")
    return document_type


def _normalize_participants(value: object) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ProposalValidationError("participantes inválidos", field_path="participants")
    if len(value) > 20:
        raise ProposalValidationError("limite de participantes excedido", field_path="participants")
    normalized_participants: list[dict[str, Any]] = []
    seen_refs: set[str] = set()
    allowed_fields = {
        "participant_ref",
        "role",
        "person_type",
        "document_type",
        "document",
        "name",
        "legal_name",
        "relationship",
        "ownership_percentage",
        "signature_required",
    }
    for index, participant in enumerate(value):
        field_prefix = f"participants[{index}]"
        participant_payload = _require_mapping(participant, field_prefix)
        _reject_unknown_fields(participant_payload, allowed_fields, field_prefix)
        _require_fields(participant_payload, {"participant_ref", "role"}, field_prefix)
        participant_ref = _require_public_identifier(
            participant_payload["participant_ref"],
            field_path=f"{field_prefix}.participant_ref",
            max_length=80,
        )
        if participant_ref in seen_refs:
            raise ProposalValidationError(
                "participant_ref duplicado", field_path=f"{field_prefix}.participant_ref"
            )
        seen_refs.add(participant_ref)
        role = _require_enum(
            participant_payload["role"],
            _PARTICIPANT_ROLES,
            f"{field_prefix}.role",
        )
        normalized: dict[str, Any] = {"participant_ref": participant_ref, "role": role}
        if role in _CRITICAL_PARTICIPANT_ROLES:
            _require_complete_participant_identity(participant_payload, field_prefix)
        for key, item in participant_payload.items():
            if key in {"participant_ref", "role", "document", "name", "legal_name"}:
                continue
            if key == "person_type":
                normalized[key] = _require_enum(item, _PERSON_TYPES, f"{field_prefix}.person_type")
            elif key == "document_type":
                normalized[key] = _require_enum(
                    item,
                    frozenset({"CPF", "CNPJ"}),
                    f"{field_prefix}.document_type",
                )
            elif key == "relationship":
                normalized[key] = _require_text(
                    item,
                    field_path=f"{field_prefix}.relationship",
                    max_length=80,
                )
            elif key == "ownership_percentage":
                normalized[key] = _require_integer_range(
                    item,
                    field_path=f"{field_prefix}.ownership_percentage",
                    minimum=0,
                    maximum=10_000,
                )
            elif key == "signature_required":
                normalized[key] = _require_bool(
                    item,
                    field_path=f"{field_prefix}.signature_required",
                )
        normalized_participants.append(normalized)
    return normalized_participants


def _require_complete_participant_identity(
    participant: Mapping[str, Any],
    field_prefix: str,
) -> None:
    missing = [
        field_name
        for field_name in ("person_type", "document_type", "document")
        if field_name not in participant
    ]
    if missing:
        raise ProposalValidationError(
            "participante crítico sem identificação completa",
            code="incomplete_critical_participant",
            field_path=field_prefix,
            details={"missing": tuple(missing)},
        )
    person_type = _require_enum(
        participant["person_type"],
        _PERSON_TYPES,
        f"{field_prefix}.person_type",
    )
    expected_document_type = "CPF" if person_type == "PF" else "CNPJ"
    document_type = _require_const(
        participant["document_type"],
        expected_document_type,
        f"{field_prefix}.document_type",
    )
    normalize_document(
        participant["document"],
        document_type=document_type,
        field_path=f"{field_prefix}.document",
    )
    required_name_field = "name" if person_type == "PF" else "legal_name"
    if required_name_field not in participant:
        raise ProposalValidationError(
            "participante crítico sem identificação completa",
            code="incomplete_critical_participant",
            field_path=field_prefix,
            details={"missing": (required_name_field,)},
        )
    _require_text(
        participant[required_name_field],
        field_path=f"{field_prefix}.{required_name_field}",
        max_length=160 if required_name_field == "name" else 180,
    )


def _normalize_product_data(
    value: object,
    *,
    product_type: str,
    participants: list[dict[str, Any]],
) -> dict[str, Any]:
    product_data = _require_mapping(value, "product_data")
    if set(product_data) != {product_type}:
        raise ProposalValidationError(
            "product_data incompatível com product_type",
            field_path="product_data",
            details={"expected": product_type},
        )
    product_payload = _require_mapping(product_data[product_type], f"product_data.{product_type}")
    match product_type:
        case "personal_credit":
            return {
                "personal_credit": _normalize_flat_product_data(
                    product_payload,
                    "product_data.personal_credit",
                    allowed_fields={
                        "employment_type",
                        "occupation",
                        "declared_monthly_income",
                        "declared_monthly_debt",
                        "income_source",
                    },
                )
            }
        case "bnpl":
            return {"bnpl": _normalize_bnpl(product_payload)}
        case "business_credit":
            return {
                "business_credit": _normalize_flat_product_data(
                    product_payload,
                    "product_data.business_credit",
                    allowed_fields={
                        "business_activity_code",
                        "declared_monthly_revenue",
                        "declared_monthly_debt",
                        "company_age_months",
                        "requested_collateral",
                    },
                )
            }
        case "receivables":
            return {"receivables": _normalize_receivables(product_payload, participants)}
    raise ProposalValidationError("produto fora do MVP", field_path="product_type")


def _normalize_flat_product_data(
    payload: Mapping[str, Any],
    field_prefix: str,
    *,
    allowed_fields: set[str] | frozenset[str] | None = None,
) -> dict[str, Any]:
    if allowed_fields is not None:
        _reject_unknown_fields(payload, allowed_fields, field_prefix)
    normalized: dict[str, Any] = {}
    for key, item in payload.items():
        if key in _MONEY_FIELDS:
            normalized[key] = require_money_cents(
                item, field_path=f"{field_prefix}.{key}", allow_zero=True
            )
        elif key == "cart_items_count":
            normalized[key] = _require_positive_integer(item, field_path=f"{field_prefix}.{key}")
        elif key.endswith("_months"):
            normalized[key] = _require_non_negative_integer(
                item, field_path=f"{field_prefix}.{key}"
            )
        else:
            normalized[key] = _require_text(
                item, field_path=f"{field_prefix}.{key}", max_length=180
            )
    return normalized


def _normalize_bnpl(payload: Mapping[str, Any]) -> dict[str, Any]:
    allowed_fields = {
        "merchant_reference",
        "order_reference",
        "cart_items_count",
        "delivery_method",
        "shipping_address_ref",
    }
    _reject_unknown_fields(payload, allowed_fields, "product_data.bnpl")
    _require_fields(payload, {"merchant_reference", "order_reference"}, "product_data.bnpl")
    return _normalize_flat_product_data(
        payload,
        "product_data.bnpl",
        allowed_fields=allowed_fields,
    )


def _normalize_receivables(
    payload: Mapping[str, Any],
    participants: list[dict[str, Any]],
) -> dict[str, Any]:
    _reject_unknown_fields(payload, {"receivables"}, "product_data.receivables")
    receivables = payload.get("receivables")
    if not isinstance(receivables, list) or not receivables:
        raise ProposalValidationError(
            "recebíveis são obrigatórios",
            field_path="product_data.receivables.receivables",
        )
    if len(receivables) > 100:
        raise ProposalValidationError(
            "limite de recebíveis excedido",
            field_path="product_data.receivables.receivables",
        )
    payer_refs = {
        participant["participant_ref"]
        for participant in participants
        if participant.get("role") == "payer"
    }
    normalized_receivables: list[dict[str, Any]] = []
    seen_receivable_ids: set[str] = set()
    for index, receivable in enumerate(receivables):
        field_prefix = f"product_data.receivables.receivables[{index}]"
        receivable_payload = _require_mapping(receivable, field_prefix)
        _reject_unknown_fields(
            receivable_payload,
            {"external_receivable_id", "payer_ref", "face_value", "due_date", "document_number"},
            field_prefix,
        )
        _require_fields(
            receivable_payload,
            {"external_receivable_id", "payer_ref", "face_value", "due_date"},
            field_prefix,
        )
        payer_ref = _require_public_identifier(
            receivable_payload["payer_ref"],
            field_path=f"{field_prefix}.payer_ref",
            max_length=80,
        )
        if payer_ref not in payer_refs:
            raise ProposalValidationError(
                "payer_ref sem participante pagador correspondente",
                code="invalid_receivable_payer",
                field_path=f"{field_prefix}.payer_ref",
                details={"role": "payer"},
            )
        external_receivable_id = _require_public_identifier(
            receivable_payload["external_receivable_id"],
            field_path=f"{field_prefix}.external_receivable_id",
            max_length=120,
        )
        if external_receivable_id in seen_receivable_ids:
            raise ProposalValidationError(
                "recebível duplicado",
                field_path=f"{field_prefix}.external_receivable_id",
            )
        seen_receivable_ids.add(external_receivable_id)
        normalized_receivables.append(
            {
                "external_receivable_id": external_receivable_id,
                "payer_ref": payer_ref,
                "face_value": require_money_cents(
                    receivable_payload["face_value"],
                    field_path=f"{field_prefix}.face_value",
                ),
                "due_date": require_iso_date(
                    receivable_payload["due_date"], field_path=f"{field_prefix}.due_date"
                ),
            }
        )
    return {"receivables": tuple(normalized_receivables)}


def _normalize_callback(value: object) -> str | None:
    if value is None:
        return None
    callback = _require_mapping(value, "callback")
    if "url" in callback:
        raise ProposalValidationError(
            "callback não aceita URL livre no payload",
            field_path="callback.url",
            details={"expected": "callback_profile_ref"},
        )
    _reject_unknown_fields(callback, {"callback_profile_ref", "events"}, "callback")
    _require_fields(callback, {"callback_profile_ref"}, "callback")
    callback_profile_ref = _require_public_identifier(
        callback["callback_profile_ref"],
        field_path="callback.callback_profile_ref",
        max_length=120,
    )
    events = callback.get("events", [])
    if not isinstance(events, list):
        raise ProposalValidationError("eventos de callback inválidos", field_path="callback.events")
    if len(events) > 20:
        raise ProposalValidationError("eventos de callback inválidos", field_path="callback.events")
    normalized_events: list[str] = []
    for index, event_name in enumerate(events):
        normalized_events.append(
            _require_public_identifier(
                event_name,
                field_path=f"callback.events[{index}]",
                max_length=120,
            )
        )
    if len(set(normalized_events)) != len(normalized_events):
        raise ProposalValidationError("eventos de callback inválidos", field_path="callback.events")
    return callback_profile_ref


def _normalize_optional_structures(payload: Mapping[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {
        "risk_context": {},
        "decision_options": {},
        "provided_data_discarded": False,
        "consents_discarded": False,
    }
    if "consents" in payload:
        _normalize_consents(payload["consents"])
        normalized["consents_discarded"] = True
    if "provided_data" in payload:
        _normalize_provided_data(payload["provided_data"])
        normalized["provided_data_discarded"] = True
    if "risk_context" in payload:
        normalized["risk_context"] = _normalize_risk_context(payload["risk_context"])
    if "decision_options" in payload:
        normalized["decision_options"] = _normalize_decision_options(payload["decision_options"])
    return normalized


def _normalize_consents(value: object) -> None:
    if not isinstance(value, list):
        raise ProposalValidationError("consentimentos inválidos", field_path="consents")
    if len(value) > 20:
        raise ProposalValidationError("limite de consentimentos excedido", field_path="consents")
    allowed_fields = {
        "subject_ref",
        "basis",
        "purpose",
        "source",
        "granted_at",
        "expires_at",
        "reference_id",
    }
    basis_values = frozenset(
        {
            "consent",
            "contract_execution",
            "legal_obligation",
            "legitimate_interest",
            "credit_protection",
        }
    )
    purpose_values = frozenset(
        {
            "credit_analysis",
            "risk_analysis",
            "fraud_prevention",
            "identity_validation",
            "open_finance_data_access",
            "audit",
        }
    )
    source_values = frozenset({"customer", "open_finance", "bureau", "partner", "internal"})
    for index, consent in enumerate(value):
        field_prefix = f"consents[{index}]"
        consent_payload = _require_mapping(consent, field_prefix)
        _reject_unknown_fields(consent_payload, allowed_fields, field_prefix)
        _require_fields(consent_payload, {"subject_ref", "purpose", "source"}, field_prefix)
        _require_public_identifier(
            consent_payload["subject_ref"],
            field_path=f"{field_prefix}.subject_ref",
            max_length=80,
        )
        _require_enum(consent_payload["purpose"], purpose_values, f"{field_prefix}.purpose")
        _require_enum(consent_payload["source"], source_values, f"{field_prefix}.source")
        if "basis" in consent_payload:
            _require_enum(consent_payload["basis"], basis_values, f"{field_prefix}.basis")
        if "reference_id" in consent_payload:
            _require_public_identifier(
                consent_payload["reference_id"],
                field_path=f"{field_prefix}.reference_id",
                max_length=120,
            )
        for field_name in ("granted_at", "expires_at"):
            if field_name in consent_payload:
                normalize_iso_datetime(
                    consent_payload[field_name],
                    field_path=f"{field_prefix}.{field_name}",
                )


def _normalize_provided_data(value: object) -> None:
    payload = _require_mapping(value, "provided_data")
    allowed_fields = {
        "contact",
        "address",
        "financial",
        "relationship",
        "employment",
        "banking",
        "commerce",
        "documents",
    }
    _reject_unknown_fields(payload, allowed_fields, "provided_data")
    if "contact" in payload:
        contact = _require_mapping(payload["contact"], "provided_data.contact")
        _reject_unknown_fields(contact, {"email", "phone"}, "provided_data.contact")
        if "email" in contact:
            _require_email(contact["email"], field_path="provided_data.contact.email")
        if "phone" in contact:
            _require_text(contact["phone"], field_path="provided_data.contact.phone", max_length=32)
            if len(contact["phone"]) < 8:
                raise ProposalValidationError(
                    "telefone inválido", field_path="provided_data.contact.phone"
                )
    if "financial" in payload:
        _normalize_money_object(
            payload["financial"],
            "provided_data.financial",
            {
                "declared_monthly_income",
                "declared_monthly_revenue",
                "declared_monthly_debt",
                "declared_cash_flow",
            },
        )
    if "relationship" in payload:
        relationship = _require_mapping(payload["relationship"], "provided_data.relationship")
        _reject_unknown_fields(
            relationship,
            {"relationship_months", "internal_score_reference", "days_past_due_last_12m"},
            "provided_data.relationship",
        )
        for key, item in relationship.items():
            if key in {"relationship_months", "days_past_due_last_12m"}:
                _require_non_negative_integer(item, field_path=f"provided_data.relationship.{key}")
            else:
                _require_public_identifier(
                    item,
                    field_path=f"provided_data.relationship.{key}",
                    max_length=120,
                )
    if "address" in payload:
        address = _require_mapping(payload["address"], "provided_data.address")
        _reject_unknown_fields(
            address, {"postal_code", "city", "state", "country"}, "provided_data.address"
        )
        for key, item in address.items():
            if key == "country":
                _require_const(item, "BR", "provided_data.address.country")
            elif key == "state":
                state = _require_text(item, field_path="provided_data.address.state", max_length=2)
                if len(state) != 2:
                    raise ProposalValidationError(
                        "estado inválido", field_path="provided_data.address.state"
                    )
            else:
                _require_text(item, field_path=f"provided_data.address.{key}", max_length=120)
    if "employment" in payload:
        employment = _require_mapping(payload["employment"], "provided_data.employment")
        _reject_unknown_fields(
            employment,
            {"employment_type", "occupation", "employer_ref"},
            "provided_data.employment",
        )
        for key, item in employment.items():
            _require_public_identifier(
                item,
                field_path=f"provided_data.employment.{key}",
                max_length=120,
            )
    if "banking" in payload:
        banking = _require_mapping(payload["banking"], "provided_data.banking")
        _reject_unknown_fields(
            banking, {"account_age_months", "bank_reference"}, "provided_data.banking"
        )
        if "account_age_months" in banking:
            _require_non_negative_integer(
                banking["account_age_months"],
                field_path="provided_data.banking.account_age_months",
            )
        if "bank_reference" in banking:
            _require_public_identifier(
                banking["bank_reference"],
                field_path="provided_data.banking.bank_reference",
                max_length=120,
            )
    if "commerce" in payload:
        commerce = _require_mapping(payload["commerce"], "provided_data.commerce")
        _reject_unknown_fields(
            commerce,
            {"merchant_reference", "order_reference"},
            "provided_data.commerce",
        )
        for key, item in commerce.items():
            _require_public_identifier(
                item,
                field_path=f"provided_data.commerce.{key}",
                max_length=120,
            )
    if "documents" in payload:
        documents = payload["documents"]
        if not isinstance(documents, list) or len(documents) > 50:
            raise ProposalValidationError(
                "referências de documentos inválidas", field_path="provided_data.documents"
            )
        for index, document_ref in enumerate(documents):
            field_prefix = f"provided_data.documents[{index}]"
            document_payload = _require_mapping(document_ref, field_prefix)
            _reject_unknown_fields(
                document_payload, {"document_ref", "document_type", "issuer"}, field_prefix
            )
            _require_fields(document_payload, {"document_ref", "document_type"}, field_prefix)
            _require_public_identifier(
                document_payload["document_ref"],
                field_path=f"{field_prefix}.document_ref",
                max_length=120,
            )
            _require_public_identifier(
                document_payload["document_type"],
                field_path=f"{field_prefix}.document_type",
                max_length=80,
            )
            if "issuer" in document_payload:
                _require_public_identifier(
                    document_payload["issuer"],
                    field_path=f"{field_prefix}.issuer",
                    max_length=120,
                )


def _normalize_risk_context(value: object) -> dict[str, Any]:
    payload = _require_mapping(value, "risk_context")
    allowed_fields = {
        "ip_address",
        "user_agent",
        "device_id",
        "session_id",
        "geo",
        "transaction",
        "customer_provided_signals",
    }
    _reject_unknown_fields(payload, allowed_fields, "risk_context")
    normalized: dict[str, Any] = {}
    for key in ("ip_address", "user_agent", "device_id", "session_id"):
        if key in payload:
            max_length = 512 if key == "user_agent" else 120
            normalized[key] = _require_text(
                payload[key], field_path=f"risk_context.{key}", max_length=max_length
            )
    if "geo" in payload:
        geo = _require_mapping(payload["geo"], "risk_context.geo")
        _reject_unknown_fields(geo, {"country", "state", "city"}, "risk_context.geo")
        normalized["geo"] = {
            key: _require_text(item, field_path=f"risk_context.geo.{key}", max_length=120)
            for key, item in geo.items()
        }
    if "transaction" in payload:
        transaction = _require_mapping(payload["transaction"], "risk_context.transaction")
        _reject_unknown_fields(
            transaction,
            {"transaction_reference", "attempt_number"},
            "risk_context.transaction",
        )
        normalized_transaction: dict[str, Any] = {}
        if "transaction_reference" in transaction:
            normalized_transaction["transaction_reference"] = _require_public_identifier(
                transaction["transaction_reference"],
                field_path="risk_context.transaction.transaction_reference",
                max_length=120,
            )
        if "attempt_number" in transaction:
            normalized_transaction["attempt_number"] = _require_positive_integer(
                transaction["attempt_number"],
                field_path="risk_context.transaction.attempt_number",
            )
        normalized["transaction"] = normalized_transaction
    if "customer_provided_signals" in payload:
        signals = _require_mapping(
            payload["customer_provided_signals"],
            "risk_context.customer_provided_signals",
        )
        _reject_unknown_fields(
            signals,
            {"email_age_days", "device_reputation", "velocity_24h", "billing_shipping_match"},
            "risk_context.customer_provided_signals",
        )
        normalized_signals: dict[str, Any] = {}
        for key in ("email_age_days", "velocity_24h"):
            if key in signals:
                normalized_signals[key] = _require_non_negative_integer(
                    signals[key],
                    field_path=f"risk_context.customer_provided_signals.{key}",
                )
        if "device_reputation" in signals:
            normalized_signals["device_reputation"] = _require_enum(
                signals["device_reputation"],
                frozenset({"unknown", "low", "medium", "high"}),
                "risk_context.customer_provided_signals.device_reputation",
            )
        if "billing_shipping_match" in signals:
            normalized_signals["billing_shipping_match"] = _require_bool(
                signals["billing_shipping_match"],
                field_path="risk_context.customer_provided_signals.billing_shipping_match",
            )
        normalized["customer_provided_signals"] = normalized_signals
    return normalized


def _normalize_decision_options(value: object) -> dict[str, Any]:
    payload = _require_mapping(value, "decision_options")
    allowed_fields = {"execution_mode", "review_strategy", "fallback_action", "max_wait_ms"}
    _reject_unknown_fields(payload, allowed_fields, "decision_options")
    _require_fields(
        payload,
        {"execution_mode", "review_strategy", "fallback_action"},
        "decision_options",
    )
    normalized: dict[str, Any] = {
        "execution_mode": _require_enum(
            payload["execution_mode"],
            frozenset({"sync", "async"}),
            "decision_options.execution_mode",
        ),
        "review_strategy": _require_enum(
            payload["review_strategy"],
            frozenset({"policy_only", "ai_advisory"}),
            "decision_options.review_strategy",
        ),
        "fallback_action": _require_enum(
            payload["fallback_action"],
            frozenset({"request_more_data", "unable_to_decide", "reject_by_policy"}),
            "decision_options.fallback_action",
        ),
    }
    if "max_wait_ms" in payload:
        normalized["max_wait_ms"] = _require_integer_range(
            payload["max_wait_ms"],
            field_path="decision_options.max_wait_ms",
            minimum=1,
            maximum=30_000,
        )
    return normalized


def _normalize_money_object(value: object, field_path: str, allowed_fields: set[str]) -> None:
    payload = _require_mapping(value, field_path)
    _reject_unknown_fields(payload, allowed_fields, field_path)
    for key, item in payload.items():
        if key == "declared_cash_flow":
            if isinstance(item, bool) or not isinstance(item, int):
                raise ProposalValidationError("inteiro inválido", field_path=f"{field_path}.{key}")
        else:
            require_money_cents(item, field_path=f"{field_path}.{key}", allow_zero=True)


def _normalize_generic_nested_payload(value: object, field_path: str, *, depth: int = 0) -> None:
    if depth > _MAX_NESTING_DEPTH:
        raise ProposalValidationError("profundidade excedida", field_path=field_path)
    if isinstance(value, Mapping):
        for key, item in value.items():
            nested_path = f"{field_path}.{key}"
            if key in _FORBIDDEN_BODY_FIELDS:
                raise ProposalValidationError(
                    "campo não permitido no body público",
                    code="forbidden_body_field",
                    field_path=nested_path,
                    details={"field": key},
                )
            _normalize_generic_nested_payload(item, nested_path, depth=depth + 1)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _normalize_generic_nested_payload(item, f"{field_path}[{index}]", depth=depth + 1)
    elif isinstance(value, float):
        raise ProposalValidationError(
            "números decimais não são aceitos em dados canônicos",
            field_path=field_path,
            details={"expected": "integer_or_string"},
        )


def _require_mapping(value: object, field_path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ProposalValidationError("objeto inválido", field_path=field_path)
    return value


def _require_fields(
    payload: Mapping[str, Any], required_fields: set[str] | frozenset[str], field_path: str
) -> None:
    missing = tuple(sorted(required_fields.difference(payload)))
    if missing:
        raise ProposalValidationError(
            "campos obrigatórios ausentes",
            field_path=field_path,
            details={"missing": missing},
        )


def _reject_unknown_fields(
    payload: Mapping[str, Any], allowed_fields: set[str] | frozenset[str], field_path: str
) -> None:
    unknown = tuple(sorted(set(payload).difference(allowed_fields)))
    if unknown:
        raise ProposalValidationError(
            "campo não previsto no contrato",
            field_path=f"{field_path}.{unknown[0]}" if field_path != "body" else unknown[0],
            details={"field": unknown[0]},
        )


def _require_const(value: object, expected: str, field_path: str) -> str:
    if value != expected:
        raise ProposalValidationError(
            "valor fora do contrato",
            field_path=field_path,
            details={"expected": expected},
        )
    return expected


def _require_enum(value: object, allowed_values: frozenset[str], field_path: str) -> str:
    if not isinstance(value, str) or value not in allowed_values:
        raise ProposalValidationError(
            "valor fora do contrato",
            field_path=field_path,
            details={"allowed": tuple(sorted(allowed_values))},
        )
    return value


def _require_text(value: object, *, field_path: str, max_length: int) -> str:
    if not isinstance(value, str):
        raise ProposalValidationError("texto obrigatório inválido", field_path=field_path)
    normalized = value.strip()
    if not normalized or len(normalized) > max_length:
        raise ProposalValidationError("texto obrigatório inválido", field_path=field_path)
    return normalized


def _require_public_identifier(
    value: object,
    *,
    field_path: str,
    max_length: int,
    pattern: re.Pattern[str] | None = None,
) -> str:
    text = _require_text(value, field_path=field_path, max_length=max_length)
    digits_only = re.sub(r"\D", "", text)
    if (
        (pattern is not None and pattern.fullmatch(text) is None)
        or (pattern is None and _PUBLIC_IDENTIFIER_PATTERN.fullmatch(text) is None)
        or _SENSITIVE_IDENTIFIER_PATTERN.search(text)
        or len(digits_only) in range(10, 16)
    ):
        raise ProposalValidationError(
            "identificador público inválido",
            field_path=field_path,
            details={"reason": "unsafe_identifier"},
        )
    return text


def _require_positive_integer(value: object, *, field_path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ProposalValidationError("inteiro positivo inválido", field_path=field_path)
    return value


def _require_non_negative_integer(value: object, *, field_path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ProposalValidationError("inteiro não negativo inválido", field_path=field_path)
    return value


def _require_integer_range(
    value: object,
    *,
    field_path: str,
    minimum: int,
    maximum: int,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum or value > maximum:
        raise ProposalValidationError("inteiro fora dos limites", field_path=field_path)
    return value


def _require_bool(value: object, *, field_path: str) -> bool:
    if not isinstance(value, bool):
        raise ProposalValidationError("booleano inválido", field_path=field_path)
    return value


def _require_email(value: object, *, field_path: str) -> str:
    text = _require_text(value, field_path=field_path, max_length=320)
    if _EMAIL_PATTERN.fullmatch(text) is None:
        raise ProposalValidationError("e-mail inválido", field_path=field_path)
    return text
