from __future__ import annotations

import re
from datetime import UTC, datetime
from math import isfinite
from typing import Any

from creditos_security.masking import (
    mask_sensitive_data,
    sanitize_log_text,
    sanitize_technical_field,
)

from creditos_observability.context import ObservabilityContext

_SAFE_ERROR_TYPE_PATTERN = re.compile(r"[^A-Za-z0-9_.-]")
_MAX_TECHNICAL_FIELD_LENGTH = 160


def build_structured_log(
    *,
    context: ObservabilityContext,
    service_name: str,
    service_version: str,
    environment: str,
    operation: str,
    source: str,
    destination: str,
    contract: str,
    contract_version: str,
    status: str,
    duration_ms: float,
    status_code: int | None = None,
    error_type: str | None = None,
    technical_result: str | None = None,
    payload: Any | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    _validate_duration_ms(duration_ms)
    if status_code is not None:
        _validate_status_code(status_code)

    event: dict[str, Any] = {
        "timestamp": datetime.now(UTC).isoformat(),
        "service.name": _safe_required_field(service_name, field_name="service_name"),
        "service.version": _safe_required_field(service_version, field_name="service_version"),
        "deployment.environment": _safe_required_field(environment, field_name="environment"),
        "operation": _safe_required_field(operation, field_name="operation"),
        "source": _safe_required_field(source, field_name="source"),
        "destination": _safe_required_field(destination, field_name="destination"),
        "contract": _safe_required_field(contract, field_name="contract"),
        "contract_version": _safe_required_field(
            contract_version,
            field_name="contract_version",
        ),
        "status": _safe_required_field(status, field_name="status"),
        "technical_result": _safe_required_field(
            technical_result or status,
            field_name="technical_result",
        ),
        "duration_ms": duration_ms,
        **context.to_log_fields(),
    }

    if status_code is not None:
        event["status_code"] = status_code

    if error_type:
        event["error_type"] = _safe_error_type(error_type)

    if payload is not None:
        event["payload"] = "[OMITIDO]"

    if extra:
        event["extra"] = mask_sensitive_data(extra)

    return mask_sensitive_data(event)


def _validate_duration_ms(duration_ms: float) -> None:
    if not isfinite(duration_ms) or duration_ms < 0:
        raise ValueError("duration_ms deve ser finito e não negativo")


def _validate_status_code(status_code: int) -> None:
    if status_code < 100 or status_code > 599:
        raise ValueError("status_code HTTP deve estar entre 100 e 599")


def _safe_required_field(value: str, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} deve ser string obrigatória")

    safe_value = sanitize_technical_field(str(mask_sensitive_data(value)))[
        :_MAX_TECHNICAL_FIELD_LENGTH
    ]
    if not safe_value:
        raise ValueError(f"{field_name} é obrigatório")
    return safe_value


def _safe_error_type(error_type: str) -> str:
    masked = str(mask_sensitive_data(error_type))
    safe_value = _SAFE_ERROR_TYPE_PATTERN.sub("_", sanitize_log_text(masked))[:120]
    return safe_value or "error"
