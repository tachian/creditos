from __future__ import annotations

import re
from enum import StrEnum

from creditos_integration.domain.errors import IntegrationValidationError


class IntegrationExecutionStatus(StrEnum):
    ACCEPTED = "accepted"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL = "partial"
    MISSING = "missing"
    FAILED = "failed"


class IntegrationExecutionJobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL = "partial"
    MISSING = "missing"
    FAILED = "failed"
    TIMED_OUT = "timed_out"


_EXECUTION_ID_PATTERN = re.compile(r"^iexec_[a-z0-9_.:-]{3,160}$")
_JOB_ID_PATTERN = re.compile(r"^ijob_[a-z0-9_.:-]{3,160}$")
_PLAN_FINGERPRINT_PATTERN = re.compile(r"^iplan_[a-f0-9]{32,64}$")
_IDEMPOTENCY_KEY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{7,119}$")
_SENSITIVE_IDENTIFIER_PATTERN = re.compile(
    r"([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}|"
    r"bearer|token|secret|password|authorization|credential)",
    re.IGNORECASE,
)


def validate_execution_id(value: str) -> str:
    if not _EXECUTION_ID_PATTERN.fullmatch(value):
        raise IntegrationValidationError(
            "identificador de execução inválido",
            code="invalid_integration_execution_id",
            field_path="execution_id",
        )
    return value


def validate_job_id(value: str) -> str:
    if not _JOB_ID_PATTERN.fullmatch(value):
        raise IntegrationValidationError(
            "identificador de job inválido",
            code="invalid_integration_execution_job_id",
            field_path="job_id",
        )
    return value


def validate_plan_fingerprint(value: str) -> str:
    if not _PLAN_FINGERPRINT_PATTERN.fullmatch(value):
        raise IntegrationValidationError(
            "fingerprint do plano de integração inválido",
            code="invalid_integration_plan_fingerprint",
            field_path="plan_fingerprint",
        )
    return value


def validate_idempotency_key(value: str) -> str:
    if not _IDEMPOTENCY_KEY_PATTERN.fullmatch(value):
        raise IntegrationValidationError(
            "chave de idempotência inválida",
            code="invalid_integration_execution_idempotency_key",
            field_path="idempotency_key",
        )
    if _SENSITIVE_IDENTIFIER_PATTERN.search(value):
        raise IntegrationValidationError(
            "chave de idempotência não pode conter identificador sensível",
            code="sensitive_integration_execution_idempotency_key",
            field_path="idempotency_key",
        )
    digits_only = re.sub(r"\D", "", value)
    if len(digits_only) in {11, 14}:
        raise IntegrationValidationError(
            "chave de idempotência não pode conter identificador sensível",
            code="sensitive_integration_execution_idempotency_key",
            field_path="idempotency_key",
        )
    return value


def parse_execution_status(value: str) -> str:
    return _parse_enum(
        IntegrationExecutionStatus,
        value,
        code="unsupported_integration_execution_status",
        field_path="status",
    )


def parse_job_status(value: str) -> str:
    return _parse_enum(
        IntegrationExecutionJobStatus,
        value,
        code="unsupported_integration_execution_job_status",
        field_path="status",
    )


def validate_schema_version(value: str) -> str:
    if value != "1.0":
        raise IntegrationValidationError(
            "schema de execução de integração não suportado",
            code="unsupported_integration_execution_schema_version",
            field_path="schema_version",
        )
    return value


def validate_attempt_count(value: int) -> int:
    if type(value) is not int or value < 1 or value > 5:
        raise IntegrationValidationError(
            "contador de tentativas inválido",
            code="invalid_integration_execution_attempt_count",
            field_path="attempt_count",
        )
    return value


def _parse_enum(
    enum_type: type[StrEnum],
    value: str,
    *,
    code: str,
    field_path: str,
) -> str:
    try:
        return enum_type(value).value
    except ValueError as error:
        raise IntegrationValidationError(
            "valor não suportado",
            code=code,
            field_path=field_path,
        ) from error
