from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from creditos_integration.domain.errors import IntegrationValidationError
from creditos_integration.domain.value_objects.execution import (
    validate_failure_code,
    validate_idempotency_key,
)
from creditos_integration.domain.value_objects.webhook import (
    WebhookEventType,
    parse_webhook_events,
    validate_webhook_configuration_id,
)

SCHEMA_VERSION = "1.0"

_EVENT_ID_PATTERN = re.compile(r"^evt_[a-f0-9]{32}$")
_JOB_ID_PATTERN = re.compile(r"^wjob_[a-z0-9_.:-]{3,160}$")
_DLQ_ID_PATTERN = re.compile(r"^wdlq_[a-z0-9_.:-]{3,160}$")
_TRACE_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")
_PUBLIC_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{2,160}$")
_EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_CPF_CNPJ_DIGITS = {11, 14}
_SENSITIVE_VALUE_TOKENS = frozenset(
    {
        "authorization",
        "bearer",
        "credential",
        "password",
        "secret",
        "token",
    }
)

_SENSITIVE_PAYLOAD_KEYS = frozenset(
    {
        "authorization",
        "cnpj",
        "cpf",
        "credential",
        "document",
        "email",
        "name",
        "nome",
        "password",
        "phone",
        "raw_payload",
        "secret",
        "telefone",
        "token",
    }
)


@dataclass(frozen=True, slots=True)
class WebhookNotificationEvent:
    event_id: str
    event_type: str
    proposal_id: str
    decision_status: str
    decision_outcome: str | None
    occurred_at: datetime
    correlation_id: str
    trace_id: str
    contract_version: str = "v1"
    schema_version: str = SCHEMA_VERSION

    @classmethod
    def create(
        cls,
        *,
        event_id: str,
        event_type: str,
        proposal_id: str,
        decision_status: str,
        decision_outcome: str | None,
        occurred_at: datetime,
        correlation_id: str,
        trace_id: str,
        contract_version: str = "v1",
        schema_version: str = SCHEMA_VERSION,
    ) -> WebhookNotificationEvent:
        return cls(
            event_id=validate_webhook_event_id(event_id),
            event_type=parse_webhook_events((event_type,))[0],
            proposal_id=_validate_public_identifier(proposal_id, field_path="proposal_id"),
            decision_status=_validate_public_identifier(
                decision_status,
                field_path="decision_status",
            ),
            decision_outcome=_validate_optional_public_identifier(
                decision_outcome,
                field_path="decision_outcome",
            ),
            occurred_at=occurred_at,
            correlation_id=_validate_non_empty(correlation_id, field_path="correlation_id"),
            trace_id=_validate_trace_id(trace_id),
            contract_version=_validate_contract_version(contract_version),
            schema_version=_validate_schema_version(schema_version),
        )

    def public_payload(self, *, idempotency_key: str) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "contract_version": self.contract_version,
            "correlation_id": self.correlation_id,
            "decision_status": self.decision_status,
            "event_id": self.event_id,
            "event_type": self.event_type,
            "idempotency_key": validate_idempotency_key(idempotency_key),
            "occurred_at": self.occurred_at.isoformat(),
            "proposal_id": self.proposal_id,
            "trace_id": self.trace_id,
        }
        if self.decision_outcome is not None:
            payload["decision_outcome"] = self.decision_outcome
        _reject_sensitive_payload(payload)
        return payload

    def to_log_safe_dict(self) -> dict[str, object]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "proposal_id": self.proposal_id,
            "decision_status": self.decision_status,
            "decision_outcome_present": self.decision_outcome is not None,
            "occurred_at": self.occurred_at.isoformat(),
            "correlation_id": self.correlation_id,
            "trace_id": self.trace_id,
            "contract_version": self.contract_version,
            "schema_version": self.schema_version,
        }


@dataclass(frozen=True, slots=True)
class WebhookDeliveryJob:
    job_id: str
    tenant_id: str
    webhook_configuration_id: str
    event_id: str
    event_type: str
    proposal_id: str
    idempotency_key: str
    status: str
    attempt_count: int
    correlation_id: str
    trace_id: str
    created_at: datetime
    updated_at: datetime
    schema_version: str = SCHEMA_VERSION

    @classmethod
    def create(
        cls,
        *,
        job_id: str,
        tenant_id: str,
        webhook_configuration_id: str,
        event: WebhookNotificationEvent,
        idempotency_key: str,
        created_at: datetime,
        status: str = "pending",
        attempt_count: int = 1,
        updated_at: datetime | None = None,
        schema_version: str = SCHEMA_VERSION,
    ) -> WebhookDeliveryJob:
        return cls(
            job_id=validate_webhook_job_id(job_id),
            tenant_id=_validate_non_empty(tenant_id, field_path="tenant_id"),
            webhook_configuration_id=validate_webhook_configuration_id(webhook_configuration_id),
            event_id=event.event_id,
            event_type=event.event_type,
            proposal_id=event.proposal_id,
            idempotency_key=validate_idempotency_key(idempotency_key),
            status=parse_webhook_delivery_status(status),
            attempt_count=validate_webhook_attempt_count(attempt_count),
            correlation_id=event.correlation_id,
            trace_id=event.trace_id,
            created_at=created_at,
            updated_at=updated_at or created_at,
            schema_version=_validate_schema_version(schema_version),
        )

    def with_status(
        self,
        *,
        status: str,
        attempt_count: int,
        updated_at: datetime,
    ) -> WebhookDeliveryJob:
        return WebhookDeliveryJob(
            job_id=self.job_id,
            tenant_id=self.tenant_id,
            webhook_configuration_id=self.webhook_configuration_id,
            event_id=self.event_id,
            event_type=self.event_type,
            proposal_id=self.proposal_id,
            idempotency_key=self.idempotency_key,
            status=parse_webhook_delivery_status(status),
            attempt_count=validate_webhook_attempt_count(attempt_count),
            correlation_id=self.correlation_id,
            trace_id=self.trace_id,
            created_at=self.created_at,
            updated_at=updated_at,
            schema_version=self.schema_version,
        )

    def to_log_safe_dict(self) -> dict[str, object]:
        return {
            "job_id": self.job_id,
            "tenant_id": self.tenant_id,
            "webhook_configuration_id": self.webhook_configuration_id,
            "event_id": self.event_id,
            "event_type": self.event_type,
            "proposal_id": self.proposal_id,
            "idempotency_key_present": bool(self.idempotency_key),
            "status": self.status,
            "attempt_count": self.attempt_count,
            "correlation_id": self.correlation_id,
            "trace_id": self.trace_id,
            "schema_version": self.schema_version,
        }


@dataclass(frozen=True, slots=True)
class WebhookDeliveryRetrySchedule:
    job_id: str
    tenant_id: str
    webhook_configuration_id: str
    event_id: str
    failure_code: str
    attempt_count: int
    next_attempt_count: int
    backoff_ms: int
    jitter_ms: int
    retry_delay_ms: int
    scheduled_at: datetime
    next_attempt_at: datetime
    correlation_id: str
    trace_id: str
    schema_version: str = SCHEMA_VERSION

    def to_log_safe_dict(self) -> dict[str, object]:
        return {
            "job_id": self.job_id,
            "tenant_id": self.tenant_id,
            "webhook_configuration_id": self.webhook_configuration_id,
            "event_id": self.event_id,
            "failure_code": self.failure_code,
            "attempt_count": self.attempt_count,
            "next_attempt_count": self.next_attempt_count,
            "backoff_ms": self.backoff_ms,
            "jitter_ms": self.jitter_ms,
            "retry_delay_ms": self.retry_delay_ms,
            "scheduled_at": self.scheduled_at.isoformat(),
            "next_attempt_at": self.next_attempt_at.isoformat(),
            "correlation_id": self.correlation_id,
            "trace_id": self.trace_id,
            "schema_version": self.schema_version,
        }


@dataclass(frozen=True, slots=True)
class WebhookDeliveryDlqRecord:
    dlq_id: str
    job_id: str
    tenant_id: str
    webhook_configuration_id: str
    event_id: str
    event_type: str
    proposal_id: str
    decision_status: str
    decision_outcome: str | None
    idempotency_key: str
    failure_code: str
    attempt_count: int
    correlation_id: str
    trace_id: str
    occurred_at: datetime
    created_at: datetime
    schema_version: str = SCHEMA_VERSION
    reprocess_count: int = 0
    last_reprocess_at: datetime | None = None
    reprocess_job_ids: tuple[str, ...] = ()

    @classmethod
    def create(
        cls,
        *,
        dlq_id: str,
        job: WebhookDeliveryJob,
        event: WebhookNotificationEvent,
        failure_code: str,
        created_at: datetime,
    ) -> WebhookDeliveryDlqRecord:
        return cls(
            dlq_id=validate_webhook_dlq_id(dlq_id),
            job_id=job.job_id,
            tenant_id=job.tenant_id,
            webhook_configuration_id=job.webhook_configuration_id,
            event_id=event.event_id,
            event_type=event.event_type,
            proposal_id=event.proposal_id,
            decision_status=event.decision_status,
            decision_outcome=event.decision_outcome,
            idempotency_key=job.idempotency_key,
            failure_code=validate_failure_code(failure_code),
            attempt_count=job.attempt_count,
            correlation_id=job.correlation_id,
            trace_id=job.trace_id,
            occurred_at=event.occurred_at,
            created_at=created_at,
        )

    def notification_event(self) -> WebhookNotificationEvent:
        return WebhookNotificationEvent.create(
            event_id=self.event_id,
            event_type=self.event_type,
            proposal_id=self.proposal_id,
            decision_status=self.decision_status,
            decision_outcome=self.decision_outcome,
            occurred_at=self.occurred_at,
            correlation_id=self.correlation_id,
            trace_id=self.trace_id,
        )

    def mark_reprocessed(
        self,
        *,
        reprocessed_at: datetime,
        reprocess_job_id: str,
    ) -> WebhookDeliveryDlqRecord:
        return WebhookDeliveryDlqRecord(
            dlq_id=self.dlq_id,
            job_id=self.job_id,
            tenant_id=self.tenant_id,
            webhook_configuration_id=self.webhook_configuration_id,
            event_id=self.event_id,
            event_type=self.event_type,
            proposal_id=self.proposal_id,
            decision_status=self.decision_status,
            decision_outcome=self.decision_outcome,
            idempotency_key=self.idempotency_key,
            failure_code=self.failure_code,
            attempt_count=self.attempt_count,
            correlation_id=self.correlation_id,
            trace_id=self.trace_id,
            occurred_at=self.occurred_at,
            created_at=self.created_at,
            schema_version=self.schema_version,
            reprocess_count=self.reprocess_count + 1,
            last_reprocess_at=reprocessed_at,
            reprocess_job_ids=(*self.reprocess_job_ids, validate_webhook_job_id(reprocess_job_id)),
        )

    def to_log_safe_dict(self) -> dict[str, object]:
        return {
            "dlq_id": self.dlq_id,
            "job_id": self.job_id,
            "tenant_id": self.tenant_id,
            "webhook_configuration_id": self.webhook_configuration_id,
            "event_id": self.event_id,
            "event_type": self.event_type,
            "proposal_id": self.proposal_id,
            "failure_code": self.failure_code,
            "attempt_count": self.attempt_count,
            "correlation_id": self.correlation_id,
            "trace_id": self.trace_id,
            "created_at": self.created_at.isoformat(),
            "schema_version": self.schema_version,
            "reprocess_count": self.reprocess_count,
            "last_reprocess_at": self.last_reprocess_at.isoformat()
            if self.last_reprocess_at is not None
            else None,
            "reprocess_job_ids": self.reprocess_job_ids,
        }


def validate_webhook_event_id(value: str) -> str:
    if not _EVENT_ID_PATTERN.fullmatch(value):
        raise IntegrationValidationError(
            "identificador de evento de webhook inválido",
            code="invalid_webhook_event_id",
            field_path="event_id",
        )
    return value


def validate_webhook_job_id(value: str) -> str:
    if not _JOB_ID_PATTERN.fullmatch(value):
        raise IntegrationValidationError(
            "identificador de job de webhook inválido",
            code="invalid_webhook_delivery_job_id",
            field_path="job_id",
        )
    return value


def validate_webhook_dlq_id(value: str) -> str:
    if not _DLQ_ID_PATTERN.fullmatch(value):
        raise IntegrationValidationError(
            "identificador de DLQ de webhook inválido",
            code="invalid_webhook_delivery_dlq_id",
            field_path="dlq_id",
        )
    return value


def parse_webhook_delivery_status(value: str) -> str:
    allowed = {"pending", "sent", "retry_scheduled", "failed", "dlq_recorded"}
    if value not in allowed:
        raise IntegrationValidationError(
            "status de entrega de webhook não suportado",
            code="unsupported_webhook_delivery_status",
            field_path="status",
        )
    return value


def public_webhook_event_types() -> tuple[str, ...]:
    return tuple(event.value for event in WebhookEventType)


def validate_webhook_attempt_count(value: int) -> int:
    if type(value) is not int or value < 1 or value > 10:
        raise IntegrationValidationError(
            "contador de tentativas de webhook inválido",
            code="invalid_webhook_delivery_attempt_count",
            field_path="attempt_count",
        )
    return value


def _validate_non_empty(value: str, *, field_path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise IntegrationValidationError(
            "valor obrigatório ausente",
            code="missing_webhook_delivery_field",
            field_path=field_path,
        )
    return value.strip()


def _validate_public_identifier(value: str, *, field_path: str) -> str:
    value = _validate_non_empty(value, field_path=field_path)
    if not _PUBLIC_ID_PATTERN.fullmatch(value):
        raise IntegrationValidationError(
            "identificador público de webhook inválido",
            code="invalid_webhook_public_identifier",
            field_path=field_path,
        )
    if _has_sensitive_public_value(value):
        raise IntegrationValidationError(
            "identificador público de webhook contém dado sensível",
            code="sensitive_webhook_delivery_payload",
            field_path=field_path,
        )
    return value


def _validate_optional_public_identifier(value: str | None, *, field_path: str) -> str | None:
    if value is None:
        return None
    return _validate_public_identifier(value, field_path=field_path)


def _validate_trace_id(value: str) -> str:
    if not _TRACE_ID_PATTERN.fullmatch(value):
        raise IntegrationValidationError(
            "trace id de webhook inválido",
            code="invalid_webhook_trace_id",
            field_path="trace_id",
        )
    return value


def _validate_contract_version(value: str) -> str:
    if value != "v1":
        raise IntegrationValidationError(
            "versão de contrato de webhook não suportada",
            code="unsupported_webhook_contract_version",
            field_path="contract_version",
        )
    return value


def _validate_schema_version(value: str) -> str:
    if value != SCHEMA_VERSION:
        raise IntegrationValidationError(
            "schema de entrega de webhook não suportado",
            code="unsupported_webhook_delivery_schema_version",
            field_path="schema_version",
        )
    return value


def _reject_sensitive_payload(payload: dict[str, Any]) -> None:
    for key, value in payload.items():
        normalized = str(key).replace("_", "").replace("-", "").lower()
        for sensitive_key in _SENSITIVE_PAYLOAD_KEYS:
            if sensitive_key.replace("_", "") in normalized:
                raise IntegrationValidationError(
                    "payload de webhook contém campo sensível",
                    code="sensitive_webhook_delivery_payload",
                    field_path=str(key),
                )
        if isinstance(value, str) and _has_sensitive_public_value(value):
            raise IntegrationValidationError(
                "payload de webhook contém valor sensível",
                code="sensitive_webhook_delivery_payload",
                field_path=str(key),
            )


def _has_sensitive_public_value(value: str) -> bool:
    normalized = value.strip().lower()
    if _EMAIL_PATTERN.search(normalized):
        return True
    digits = re.sub(r"\D", "", normalized)
    if len(digits) in _CPF_CNPJ_DIGITS:
        return True
    return any(token in normalized for token in _SENSITIVE_VALUE_TOKENS)
