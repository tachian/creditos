from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, replace
from time import perf_counter
from types import MappingProxyType
from typing import Any

from creditos_observability.context import ObservabilityContext
from creditos_observability.logging import build_structured_log
from creditos_security import hmac_sha256_identifier

from creditos_proposal_intake.application.ports import (
    CanonicalProposalRepository,
    IdempotentProposalSubmissionRepository,
)
from creditos_proposal_intake.application.use_cases.validate_and_normalize_proposal import (
    ValidateAndNormalizeProposal,
    ValidateAndNormalizeProposalCommand,
)
from creditos_proposal_intake.domain.entities import (
    CanonicalProposal,
    IdempotencyScope,
    IdempotentProposalSubmission,
)
from creditos_proposal_intake.domain.errors import (
    IdempotencyConflictError,
    ProposalValidationError,
)
from creditos_proposal_intake.domain.value_objects.documents import normalize_document

SERVICE_NAME = "proposal-intake"
SERVICE_VERSION = "0.1.0"
CONTRACT = "proposal-intake-public-application"
CONTRACT_VERSION = "v1"


@dataclass(frozen=True, slots=True)
class ProposalIntakeValidationResult:
    proposal: CanonicalProposal
    logs: tuple[dict[str, Any], ...]


@dataclass(frozen=True, slots=True)
class SubmitIdempotentProposalCommand:
    payload: dict[str, Any]
    headers: dict[str, str]
    technical_client_id: str


@dataclass(frozen=True, slots=True)
class SubmitIdempotentProposalResult:
    proposal: CanonicalProposal
    submission_result: MappingProxyType[str, str]
    idempotency_status: str
    logs: tuple[dict[str, Any], ...]


class ProposalIntakeApplicationService:
    def __init__(
        self,
        *,
        repository: CanonicalProposalRepository,
        environment: str,
        idempotency_repository: IdempotentProposalSubmissionRepository | None = None,
        sensitive_fingerprint_secret: str | None = None,
    ) -> None:
        self._validate_and_normalize = ValidateAndNormalizeProposal(repository=repository)
        self._repository = repository
        self._idempotency_repository = idempotency_repository
        self._sensitive_fingerprint_secret = sensitive_fingerprint_secret
        self._environment = environment
        self._logged_events: list[dict[str, Any]] = []

    @property
    def logged_events(self) -> tuple[dict[str, Any], ...]:
        return tuple(self._logged_events)

    def validate_and_normalize(
        self,
        command: ValidateAndNormalizeProposalCommand,
        *,
        context: ObservabilityContext,
    ) -> ProposalIntakeValidationResult:
        started_at = perf_counter()
        try:
            tenant_id = _require_trusted_tenant(context)
            result = self._validate_and_normalize.execute(command, tenant_id=tenant_id)
            event = self._log_operation(
                context=context,
                status="accepted",
                duration_ms=_duration_ms(started_at),
                extra={
                    "schema_version": result.proposal.schema_version,
                    "product_type": result.proposal.product_type,
                    "channel": result.proposal.channel,
                    "callback_configured": result.proposal.callback_profile_ref is not None,
                },
                payload=command,
            )
            return ProposalIntakeValidationResult(
                proposal=result.proposal,
                logs=(event,),
            )
        except Exception as error:
            self._log_operation(
                context=context,
                status="rejected",
                duration_ms=_duration_ms(started_at),
                extra={
                    "error_code": getattr(error, "code", type(error).__name__),
                    "field_path": getattr(error, "field_path", None),
                },
                payload=command,
                error_type=type(error).__name__,
            )
            raise

    def submit_idempotent(
        self,
        command: SubmitIdempotentProposalCommand,
        *,
        context: ObservabilityContext,
    ) -> SubmitIdempotentProposalResult:
        if self._idempotency_repository is None:
            raise RuntimeError("idempotency_repository é obrigatório para submissão idempotente")
        started_at = perf_counter()
        technical_client_id: str | None = None
        proposal_fingerprint: str | None = None
        existing_proposal_fingerprint: str | None = None
        try:
            tenant_id = _require_trusted_tenant(context)
            technical_client_id = _require_technical_client_id(command.technical_client_id)
            sensitive_fingerprint_secret = _require_sensitive_fingerprint_secret(
                self._sensitive_fingerprint_secret
            )
            validation_result = self._validate_and_normalize.execute(
                ValidateAndNormalizeProposalCommand(
                    payload=command.payload,
                    headers=command.headers,
                ),
                tenant_id=tenant_id,
                persist=False,
            )
            sensitive_identity_fingerprints = _sensitive_identity_fingerprints(
                command.payload,
                secret_key=sensitive_fingerprint_secret,
            )
            proposal_fingerprint = _fingerprint_proposal(
                validation_result.proposal,
                sensitive_identity_fingerprints=sensitive_identity_fingerprints,
            )
            proposal_id = _proposal_id(
                tenant_id=tenant_id,
                technical_client_id=technical_client_id,
                idempotency_key=validation_result.proposal.idempotency_key,
                proposal_fingerprint=proposal_fingerprint,
            )
            proposal = replace(validation_result.proposal, proposal_id=proposal_id)
            submission = IdempotentProposalSubmission(
                scope=IdempotencyScope(
                    tenant_id=tenant_id,
                    technical_client_id=technical_client_id,
                    idempotency_key=proposal.idempotency_key,
                ),
                external_proposal_id=proposal.external_proposal_id,
                proposal_fingerprint=proposal_fingerprint,
                result=MappingProxyType(
                    {
                        "proposal_id": proposal_id,
                        "external_proposal_id": proposal.external_proposal_id,
                        "schema_version": proposal.schema_version,
                        "product_type": proposal.product_type,
                        "status": "accepted",
                    }
                ),
            )
            resolution = self._idempotency_repository.submit_once(submission)
            if resolution.conflicted:
                existing_proposal_fingerprint = resolution.submission.proposal_fingerprint
                raise IdempotencyConflictError(
                    attempted_proposal_fingerprint=proposal_fingerprint,
                    existing_proposal_fingerprint=existing_proposal_fingerprint,
                )
            if resolution.created:
                try:
                    self._repository.save(proposal)
                except Exception:
                    self._idempotency_repository.rollback(
                        submission.scope,
                        proposal_fingerprint=proposal_fingerprint,
                    )
                    raise
                resolved_proposal = proposal
            else:
                resolved_proposal = replace(
                    proposal,
                    proposal_id=resolution.submission.result["proposal_id"],
                )
            event = self._log_operation(
                context=context,
                operation="proposal_intake.submit_idempotent",
                status=resolution.status,
                duration_ms=_duration_ms(started_at),
                extra={
                    "schema_version": resolved_proposal.schema_version,
                    "product_type": resolved_proposal.product_type,
                    "channel": resolved_proposal.channel,
                    "technical_client_id": technical_client_id,
                    "proposal_fingerprint": proposal_fingerprint,
                },
                payload=command,
            )
            return SubmitIdempotentProposalResult(
                proposal=resolved_proposal,
                submission_result=resolution.submission.result,
                idempotency_status=resolution.status,
                logs=(event,),
            )
        except Exception as error:
            self._log_operation(
                context=context,
                operation="proposal_intake.submit_idempotent",
                status="conflicted" if isinstance(error, IdempotencyConflictError) else "rejected",
                duration_ms=_duration_ms(started_at),
                extra={
                    "error_code": getattr(error, "code", type(error).__name__),
                    "field_path": getattr(error, "field_path", None),
                    "technical_client_id": technical_client_id,
                    "attempted_proposal_fingerprint": proposal_fingerprint,
                    "existing_proposal_fingerprint": existing_proposal_fingerprint,
                },
                payload=command,
                error_type=type(error).__name__,
            )
            raise

    def _log_operation(
        self,
        *,
        context: ObservabilityContext,
        operation: str = "proposal_intake.validate_and_normalize",
        status: str,
        duration_ms: float,
        extra: dict[str, Any],
        payload: Any,
        error_type: str | None = None,
    ) -> dict[str, Any]:
        event = build_structured_log(
            context=context,
            service_name=SERVICE_NAME,
            service_version=SERVICE_VERSION,
            environment=self._environment,
            operation=operation,
            source="public-proposal-command",
            destination=SERVICE_NAME,
            contract=CONTRACT,
            contract_version=CONTRACT_VERSION,
            status=status,
            duration_ms=duration_ms,
            error_type=error_type,
            payload=payload,
            extra=extra,
        )
        self._logged_events.append(event)
        return event


def _require_trusted_tenant(context: ObservabilityContext) -> str:
    if not context.tenant_id:
        from creditos_proposal_intake.domain.errors import ProposalValidationError

        raise ProposalValidationError(
            "tenant confiável ausente",
            field_path="context.tenant_id",
        )
    return context.tenant_id


_TECHNICAL_CLIENT_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{2,119}$")
_UNSAFE_IDENTIFIER_PATTERN = re.compile(
    r"(^\d{10,15}$|[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}|"
    r"bearer|token|secret|password|authorization)",
    re.IGNORECASE,
)
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


def _require_technical_client_id(value: str) -> str:
    normalized_value = value.strip() if isinstance(value, str) else ""
    digits_only = re.sub(r"\D", "", normalized_value)
    if (
        not isinstance(value, str)
        or _TECHNICAL_CLIENT_ID_PATTERN.fullmatch(normalized_value) is None
        or _UNSAFE_IDENTIFIER_PATTERN.search(normalized_value) is not None
        or len(digits_only) in range(10, 16)
    ):
        raise ProposalValidationError(
            "cliente técnico inválido",
            code="invalid_technical_client",
            field_path="technical_client_id",
        )
    return normalized_value


def _require_sensitive_fingerprint_secret(value: str | None) -> str:
    if not isinstance(value, str) or len(value.strip()) < 16:
        raise ProposalValidationError(
            "segredo de fingerprint sensível inválido",
            code="invalid_sensitive_fingerprint_secret",
            field_path="sensitive_fingerprint_secret",
        )
    return value


def _fingerprint_proposal(
    proposal: CanonicalProposal,
    *,
    sensitive_identity_fingerprints: tuple[str, ...] = (),
) -> str:
    canonical_payload = {
        "schema_version": proposal.schema_version,
        "external_proposal_id": proposal.external_proposal_id,
        "person_type": proposal.person_type,
        "product_type": proposal.product_type,
        "channel": proposal.channel,
        "borrower_document_type": proposal.borrower_document_type,
        "requested_amount_cents": proposal.requested_amount_cents,
        "requested_terms": _plain_value(proposal.requested_terms),
        "product_data": _plain_value(proposal.product_data),
        "participants": _plain_value(proposal.participants),
        "risk_context": _plain_value(proposal.risk_context),
        "decision_options": _plain_value(proposal.decision_options),
        "provided_data_discarded": proposal.provided_data_discarded,
        "consents_discarded": proposal.consents_discarded,
        "callback_profile_ref": proposal.callback_profile_ref,
        "sensitive_identity_fingerprints": sensitive_identity_fingerprints,
    }
    serialized = json.dumps(
        canonical_payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return f"sha256:{hashlib.sha256(serialized.encode('utf-8')).hexdigest()}"


def _sensitive_identity_fingerprints(
    payload: Mapping[str, Any],
    *,
    secret_key: str,
) -> tuple[str, ...]:
    borrower = payload["borrower"]
    if not isinstance(borrower, Mapping):
        return ()
    fingerprints = [
        _document_fingerprint(
            owner="borrower",
            document=borrower["document"],
            document_type=str(borrower["document_type"]),
            field_path="borrower.document",
            secret_key=secret_key,
        )
    ]
    participants = payload.get("participants", [])
    if isinstance(participants, list):
        for index, participant in enumerate(participants):
            if not isinstance(participant, Mapping):
                continue
            if participant.get("role") not in _CRITICAL_PARTICIPANT_ROLES:
                continue
            participant_ref = str(participant.get("participant_ref", f"participant-{index}"))
            fingerprints.append(
                _document_fingerprint(
                    owner=f"participant:{participant_ref}",
                    document=participant["document"],
                    document_type=str(participant["document_type"]),
                    field_path=f"participants[{index}].document",
                    secret_key=secret_key,
                )
            )
    return tuple(sorted(fingerprints))


def _document_fingerprint(
    *,
    owner: str,
    document: object,
    document_type: str,
    field_path: str,
    secret_key: str,
) -> str:
    normalized_document = normalize_document(
        document,
        document_type=document_type,
        field_path=field_path,
    )
    digest = hmac_sha256_identifier(normalized_document, secret_key=secret_key)
    return f"{owner}:{document_type}:hmac-sha256:{digest}"


def _proposal_id(
    *,
    tenant_id: str,
    technical_client_id: str,
    idempotency_key: str,
    proposal_fingerprint: str,
) -> str:
    seed = "|".join((tenant_id, technical_client_id, idempotency_key, proposal_fingerprint))
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:24]
    return f"proposal_{digest}"


def _plain_value(value: Any) -> Any:
    if isinstance(value, MappingProxyType):
        return {key: _plain_value(item) for key, item in value.items()}
    if isinstance(value, dict):
        return {key: _plain_value(item) for key, item in value.items()}
    if isinstance(value, tuple | list):
        return [_plain_value(item) for item in value]
    return value


def _duration_ms(started_at: float) -> float:
    return round((perf_counter() - started_at) * 1000, 3)
