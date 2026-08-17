from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from threading import RLock
from time import perf_counter
from types import MappingProxyType
from typing import Any

from creditos_observability.context import ObservabilityContext
from creditos_observability.logging import build_structured_log
from creditos_security import hmac_sha256_identifier

from creditos_proposal_intake.application.ports import (
    CanonicalProposalRepository,
    IdempotentProposalSubmissionRepository,
    ProposalIntakeStatusRepository,
    ProposalOutboxRepository,
)
from creditos_proposal_intake.application.use_cases.validate_and_normalize_proposal import (
    ValidateAndNormalizeProposal,
    ValidateAndNormalizeProposalCommand,
)
from creditos_proposal_intake.domain.entities import (
    CanonicalProposal,
    IdempotencyResolution,
    IdempotencyScope,
    IdempotentProposalSubmission,
    ProposalIntakeStatus,
    ProposalOutboxMessage,
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
class SubmitProposalWithInitialStatusCommand:
    payload: dict[str, Any]
    headers: dict[str, str]
    technical_client_id: str
    subject_id: str
    scopes: tuple[str, ...]
    principal_type: str = "m2m"
    roles: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SubmitIdempotentProposalResult:
    proposal: CanonicalProposal
    submission_result: MappingProxyType[str, str]
    idempotency_status: str
    logs: tuple[dict[str, Any], ...]


@dataclass(frozen=True, slots=True)
class SubmitProposalWithInitialStatusResult:
    proposal: CanonicalProposal
    submission_result: MappingProxyType[str, str]
    idempotency_status: str
    intake_status: ProposalIntakeStatus
    outbox_message: ProposalOutboxMessage
    logs: tuple[dict[str, Any], ...]


@dataclass(frozen=True, slots=True)
class _EventContext:
    tenant_isolation_tier: str
    subject_id: str
    client_id: str
    principal_type: str
    scopes: tuple[str, ...]
    roles: tuple[str, ...]


class ProposalIntakeApplicationService:
    def __init__(
        self,
        *,
        repository: CanonicalProposalRepository,
        environment: str,
        idempotency_repository: IdempotentProposalSubmissionRepository | None = None,
        intake_status_repository: ProposalIntakeStatusRepository | None = None,
        outbox_repository: ProposalOutboxRepository | None = None,
        sensitive_fingerprint_secret: str | None = None,
        clock: Callable[[], datetime] | None = None,
        event_id_factory: Callable[[str], str] | None = None,
    ) -> None:
        self._validate_and_normalize = ValidateAndNormalizeProposal(repository=repository)
        self._repository = repository
        self._idempotency_repository = idempotency_repository
        self._intake_status_repository = intake_status_repository
        self._outbox_repository = outbox_repository
        self._sensitive_fingerprint_secret = sensitive_fingerprint_secret
        self._environment = environment
        self._clock = clock or (lambda: datetime.now(UTC))
        self._event_id_factory = event_id_factory or _event_id
        self._initial_status_outbox_lock = RLock()
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
        emit_log: bool = True,
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
            existing_submission = self._idempotency_repository.find(submission.scope)
            if existing_submission is not None:
                if existing_submission.proposal_fingerprint != proposal_fingerprint:
                    existing_proposal_fingerprint = existing_submission.proposal_fingerprint
                    raise IdempotencyConflictError(
                        attempted_proposal_fingerprint=proposal_fingerprint,
                        existing_proposal_fingerprint=existing_proposal_fingerprint,
                    )
                resolved_proposal = replace(
                    proposal,
                    proposal_id=existing_submission.result["proposal_id"],
                )
                resolution = IdempotencyResolution(
                    status="replayed",
                    submission=existing_submission,
                )
            else:
                self._repository.save(proposal)
                resolution = self._idempotency_repository.submit_once(submission)
                if resolution.conflicted:
                    existing_proposal_fingerprint = resolution.submission.proposal_fingerprint
                    try:
                        self._repository.delete(proposal)
                    finally:
                        self._idempotency_repository.rollback(
                            submission.scope,
                            proposal_fingerprint=proposal_fingerprint,
                        )
                    raise IdempotencyConflictError(
                        attempted_proposal_fingerprint=proposal_fingerprint,
                        existing_proposal_fingerprint=existing_proposal_fingerprint,
                    )
                resolved_proposal = (
                    proposal
                    if resolution.created
                    else replace(
                        proposal,
                        proposal_id=resolution.submission.result["proposal_id"],
                    )
                )
            logs: tuple[dict[str, Any], ...] = ()
            if emit_log:
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
                logs = (event,)
            return SubmitIdempotentProposalResult(
                proposal=resolved_proposal,
                submission_result=resolution.submission.result,
                idempotency_status=resolution.status,
                logs=logs,
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

    def submit_with_initial_status_and_outbox(
        self,
        command: SubmitProposalWithInitialStatusCommand,
        *,
        context: ObservabilityContext,
    ) -> SubmitProposalWithInitialStatusResult:
        if self._idempotency_repository is None:
            raise RuntimeError("idempotency_repository é obrigatório para submissão idempotente")
        if self._intake_status_repository is None:
            raise RuntimeError("intake_status_repository é obrigatório para status inicial")
        if self._outbox_repository is None:
            raise RuntimeError("outbox_repository é obrigatório para outbox de proposta")

        idempotency_repository = self._idempotency_repository
        started_at = perf_counter()
        proposal: CanonicalProposal | None = None
        status_record: ProposalIntakeStatus | None = None
        outbox_message: ProposalOutboxMessage | None = None
        idempotency_status: str | None = None
        proposal_fingerprint: str | None = None
        try:
            with self._initial_status_outbox_lock:
                event_context = _require_event_context(command, context)
                idempotent_result = self.submit_idempotent(
                    SubmitIdempotentProposalCommand(
                        payload=command.payload,
                        headers=command.headers,
                        technical_client_id=command.technical_client_id,
                    ),
                    context=context,
                    emit_log=False,
                )
                proposal = idempotent_result.proposal
                idempotency_status = idempotent_result.idempotency_status
                proposal_id = _require_proposal_id(proposal)
                deduplication_key = _proposal_submitted_deduplication_key(
                    tenant_id=proposal.tenant_id,
                    proposal_id=proposal_id,
                )

                if idempotent_result.idempotency_status == "replayed":
                    status_record = self._intake_status_repository.find(
                        proposal.tenant_id,
                        proposal_id,
                    )
                    outbox_message = self._outbox_repository.find_by_deduplication_key(
                        proposal.tenant_id,
                        deduplication_key,
                    )
                    if status_record is None or outbox_message is None:
                        raise ProposalValidationError(
                            "submissão idempotente sem status inicial ou outbox",
                            code="missing_initial_status_or_outbox",
                            field_path="proposal_id",
                        )
                    _require_matching_status_and_outbox(
                        proposal=proposal,
                        proposal_id=proposal_id,
                        status_record=status_record,
                        outbox_message=outbox_message,
                    )
                else:
                    try:
                        occurred_at = _utc_datetime(self._clock())
                        status_record = _build_initial_status(proposal, occurred_at=occurred_at)
                        outbox_message = _build_proposal_submitted_outbox_message(
                            proposal,
                            status_record=status_record,
                            context=context,
                            event_context=event_context,
                            created_at=occurred_at,
                            message_id=self._event_id_factory(deduplication_key),
                            deduplication_key=deduplication_key,
                        )
                        self._intake_status_repository.save_initial(status_record)
                        self._outbox_repository.save_pending(outbox_message)
                    except Exception:
                        proposal_fingerprint = _fingerprint_for_rollback(
                            command,
                            proposal,
                            sensitive_fingerprint_secret=_require_sensitive_fingerprint_secret(
                                self._sensitive_fingerprint_secret
                            ),
                        )
                        self._outbox_repository.delete(proposal.tenant_id, deduplication_key)
                        self._intake_status_repository.delete(proposal.tenant_id, proposal_id)
                        idempotency_repository.rollback(
                            IdempotencyScope(
                                tenant_id=proposal.tenant_id,
                                technical_client_id=_require_technical_client_id(
                                    command.technical_client_id
                                ),
                                idempotency_key=proposal.idempotency_key,
                            ),
                            proposal_fingerprint=proposal_fingerprint,
                        )
                        self._repository.delete(proposal)
                        raise

                event = self._log_operation(
                    context=context,
                    operation="proposal_intake.submit_with_initial_status_and_outbox",
                    status=idempotency_status,
                    duration_ms=_duration_ms(started_at),
                    extra={
                        "proposal_id": proposal_id,
                        "external_proposal_id": proposal.external_proposal_id,
                        "product_type": proposal.product_type,
                        "channel": proposal.channel,
                        "intake_status": status_record.status,
                        "event_id": outbox_message.message_id,
                        "event_type": outbox_message.event_type,
                        "outbox_status": outbox_message.status,
                    },
                    payload=command,
                )
                return SubmitProposalWithInitialStatusResult(
                    proposal=proposal,
                    submission_result=idempotent_result.submission_result,
                    idempotency_status=idempotency_status,
                    intake_status=status_record,
                    outbox_message=outbox_message,
                    logs=(event,),
                )
        except Exception as error:
            self._log_operation(
                context=context,
                operation="proposal_intake.submit_with_initial_status_and_outbox",
                status="rejected",
                duration_ms=_duration_ms(started_at),
                extra={
                    "error_code": getattr(error, "code", type(error).__name__),
                    "field_path": getattr(error, "field_path", None),
                    "proposal_id": proposal.proposal_id if proposal is not None else None,
                    "idempotency_status": idempotency_status,
                    "proposal_fingerprint": proposal_fingerprint,
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


def _require_event_context(
    command: SubmitProposalWithInitialStatusCommand,
    context: ObservabilityContext,
) -> _EventContext:
    if context.tenant_isolation_tier not in {"bridge", "silo"}:
        raise ProposalValidationError(
            "tier de isolamento confiável inválido",
            code="invalid_tenant_isolation_tier",
            field_path="context.tenant_isolation_tier",
        )
    if command.principal_type not in {"m2m", "human", "platform"}:
        raise ProposalValidationError(
            "tipo de principal inválido",
            code="invalid_principal_type",
            field_path="principal_type",
        )
    if not command.scopes:
        raise ProposalValidationError(
            "escopos do evento ausentes",
            code="missing_event_scopes",
            field_path="scopes",
        )
    return _EventContext(
        tenant_isolation_tier=context.tenant_isolation_tier,
        subject_id=_require_safe_context_value(command.subject_id, field_path="subject_id"),
        client_id=_require_technical_client_id(command.technical_client_id),
        principal_type=command.principal_type,
        scopes=tuple(
            _require_safe_context_value(scope, field_path="scopes") for scope in command.scopes
        ),
        roles=tuple(
            _require_safe_context_value(role, field_path="roles") for role in command.roles
        ),
    )


def _require_safe_context_value(value: str, *, field_path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ProposalValidationError(
            "contexto de evento inválido",
            code="invalid_event_context",
            field_path=field_path,
        )
    normalized_value = value.strip()
    if re.search(r"\s", normalized_value) or _UNSAFE_IDENTIFIER_PATTERN.search(normalized_value):
        raise ProposalValidationError(
            "contexto de evento inválido",
            code="invalid_event_context",
            field_path=field_path,
        )
    return normalized_value


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


def _build_initial_status(
    proposal: CanonicalProposal,
    *,
    occurred_at: datetime,
) -> ProposalIntakeStatus:
    return ProposalIntakeStatus(
        tenant_id=proposal.tenant_id,
        proposal_id=_require_proposal_id(proposal),
        external_proposal_id=proposal.external_proposal_id,
        status="submitted",
        schema_version=proposal.schema_version,
        product_type=proposal.product_type,
        channel=proposal.channel,
        occurred_at=occurred_at,
    )


def _require_matching_status_and_outbox(
    *,
    proposal: CanonicalProposal,
    proposal_id: str,
    status_record: ProposalIntakeStatus,
    outbox_message: ProposalOutboxMessage,
) -> None:
    expected_subject = f"proposal/{proposal_id}"
    if (
        status_record.tenant_id != proposal.tenant_id
        or status_record.proposal_id != proposal_id
        or status_record.status != "submitted"
        or outbox_message.tenant_id != proposal.tenant_id
        or outbox_message.aggregate_type != "proposal"
        or outbox_message.aggregate_id != proposal_id
        or outbox_message.event_type != "creditos.proposal.v1.submitted"
        or outbox_message.subject != expected_subject
        or outbox_message.status != "pending"
        or outbox_message.payload.get("subject") != expected_subject
        or outbox_message.payload.get("type") != "creditos.proposal.v1.submitted"
        or _event_data_proposal_id(outbox_message) != proposal_id
    ):
        raise ProposalValidationError(
            "replay idempotente com status ou outbox incompatível",
            code="incompatible_status_or_outbox",
            field_path="proposal_id",
        )


def _event_data_proposal_id(outbox_message: ProposalOutboxMessage) -> str | None:
    data = outbox_message.payload.get("data")
    if not isinstance(data, Mapping):
        return None
    proposal_id = data.get("proposal_id")
    return proposal_id if isinstance(proposal_id, str) else None


def _build_proposal_submitted_outbox_message(
    proposal: CanonicalProposal,
    *,
    status_record: ProposalIntakeStatus,
    context: ObservabilityContext,
    event_context: _EventContext,
    created_at: datetime,
    message_id: str,
    deduplication_key: str,
) -> ProposalOutboxMessage:
    proposal_id = _require_proposal_id(proposal)
    event_type = "creditos.proposal.v1.submitted"
    subject = f"proposal/{proposal_id}"
    payload = {
        "specversion": "1.0",
        "id": message_id,
        "source": "creditos://proposal-intake",
        "type": event_type,
        "subject": subject,
        "time": _format_event_time(created_at),
        "datacontenttype": "application/json",
        "dataschema": "creditos://contracts/asyncapi/events/proposal/v1",
        "tenantid": proposal.tenant_id,
        "tenanttier": event_context.tenant_isolation_tier,
        "subjectid": event_context.subject_id,
        "clientid": event_context.client_id,
        "principaltype": event_context.principal_type,
        "scopes": " ".join(sorted(event_context.scopes)),
        "correlationid": context.correlation_id,
        "requestid": context.request_id,
        "idempotencykey": proposal.idempotency_key,
        "schemaversion": "v1",
        "traceparent": context.to_carrier()["traceparent"],
        "data": {
            "proposal_id": proposal_id,
            "external_proposal_id": proposal.external_proposal_id,
            "product_type": proposal.product_type,
            "schema_version": proposal.schema_version,
            "channel": proposal.channel,
            "intake_status": status_record.status,
            "provided_data_discarded": proposal.provided_data_discarded,
            "consents_discarded": proposal.consents_discarded,
            "callback_configured": proposal.callback_profile_ref is not None,
        },
    }
    if event_context.roles:
        payload["roles"] = " ".join(sorted(event_context.roles))
    return ProposalOutboxMessage(
        tenant_id=proposal.tenant_id,
        message_id=message_id,
        aggregate_type="proposal",
        aggregate_id=proposal_id,
        event_type=event_type,
        subject=subject,
        payload=MappingProxyType(payload),
        status="pending",
        created_at=created_at,
        deduplication_key=deduplication_key,
    )


def _require_proposal_id(proposal: CanonicalProposal) -> str:
    if not proposal.proposal_id:
        raise ProposalValidationError(
            "proposal_id ausente",
            code="missing_proposal_id",
            field_path="proposal_id",
        )
    return proposal.proposal_id


def _proposal_submitted_deduplication_key(*, tenant_id: str, proposal_id: str) -> str:
    seed = f"{tenant_id}|{proposal_id}|creditos.proposal.v1.submitted"
    return f"proposal-submitted:{hashlib.sha256(seed.encode('utf-8')).hexdigest()}"


def _fingerprint_for_rollback(
    command: SubmitProposalWithInitialStatusCommand,
    proposal: CanonicalProposal,
    *,
    sensitive_fingerprint_secret: str,
) -> str:
    sensitive_identity_fingerprints = _sensitive_identity_fingerprints(
        command.payload,
        secret_key=sensitive_fingerprint_secret,
    )
    return _fingerprint_proposal(
        proposal,
        sensitive_identity_fingerprints=sensitive_identity_fingerprints,
    )


def _event_id(seed: str) -> str:
    return f"evt_{hashlib.sha256(seed.encode('utf-8')).hexdigest()[:24]}"


def _utc_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _format_event_time(value: datetime) -> str:
    return _utc_datetime(value).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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
