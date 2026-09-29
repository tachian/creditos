from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from types import MappingProxyType
from typing import Any

from creditos_security import mask_text

from creditos_reporting_insights.domain.errors import CustomerDashboardPrivacyError

_TECHNICAL_REF_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_.-]{1,119}$")
_CURATED_CODE_PATTERN = re.compile(r"^[a-z][a-z0-9_]{2,119}$")
_URL_OR_ENDPOINT_PATTERN = re.compile(r"(://|www\\.|/[a-z0-9_.-]+|:[0-9]{2,5})", re.IGNORECASE)
_MAX_FUTURE_SKEW = timedelta(minutes=5)
_ALLOWED_COMPONENTS = frozenset({"api", "callbacks", "integrations"})
_FORBIDDEN_OUTPUT_TERMS = frozenset(
    {
        "cpf",
        "cnpj",
        "document",
        "document_number",
        "email",
        "name",
        "address",
        "street",
        "payload",
        "provider_payload",
        "prompt",
        "output",
        "raw_score",
        "score",
        "restricted",
        "restricted_evidence",
        "evidence",
        "evidencia",
        "adapter",
        "provider",
        "endpoint",
        "url",
        "token",
        "secret",
        "trace",
        "trace_id",
        "correlation_id",
        "request_id",
        "proposal_id",
        "decision_id",
        "raw_log",
        "raw_trace",
        "prometheus",
        "loki",
        "tempo",
        "cpu",
        "memory",
        "pod",
        "node",
        "host",
        "stack",
    }
)


class OperationalImpactStatus(StrEnum):
    OPERATIONAL = "operational"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class CustomerDashboardIncident:
    incident_ref: str
    status: OperationalImpactStatus
    impact: str
    started_at: datetime
    ended_at: datetime | None = None

    def __post_init__(self) -> None:
        _validate_technical_ref(self.incident_ref, field_path="incident_ref")
        _validate_enum(self.status, OperationalImpactStatus, field_path="status")
        _validate_curated_code(self.impact, field_path="impact")
        _validate_timestamp(self.started_at, field_path="started_at")
        if self.ended_at is not None:
            _validate_timestamp(self.ended_at, field_path="ended_at")
            if self.ended_at.astimezone(UTC) < self.started_at.astimezone(UTC):
                raise CustomerDashboardPrivacyError(
                    code="customer_dashboard_invalid_incident_period",
                    field_path="ended_at",
                )

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "incident_ref": self.incident_ref,
            "status": self.status.value,
            "impact": self.impact,
            "started_at": self.started_at.isoformat(),
        }
        if self.ended_at is not None:
            payload["ended_at"] = self.ended_at.isoformat()
        return payload


@dataclass(frozen=True, slots=True)
class CustomerDashboardOperationalImpact:
    tenant_id: str
    component: str
    status: OperationalImpactStatus
    message: str
    incidents: tuple[CustomerDashboardIncident, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        _validate_technical_ref(self.tenant_id, field_path="tenant_id")
        if self.component not in _ALLOWED_COMPONENTS:
            raise CustomerDashboardPrivacyError(
                code="customer_dashboard_component_not_allowed",
                field_path="component",
            )
        _validate_enum(self.status, OperationalImpactStatus, field_path="status")
        _validate_curated_code(self.message, field_path="message")

    def to_card(self) -> dict[str, object]:
        return {
            "status": self.status.value,
            "message": self.message,
            "incidents": tuple(incident.to_dict() for incident in self.incidents),
        }


@dataclass(frozen=True, slots=True)
class CustomerDashboardSnapshot:
    tenant_ref: str
    tenant_isolation_tier: str
    product_types: tuple[str, ...]
    channels: tuple[str, ...]
    periods: tuple[str, ...]
    sections: MappingProxyType[str, MappingProxyType[str, Any]]

    def __post_init__(self) -> None:
        _validate_technical_ref(self.tenant_ref, field_path="tenant_ref")
        _validate_safe_mapping(self.to_dict())

    def to_dict(self) -> dict[str, object]:
        return {
            "tenant_ref": self.tenant_ref,
            "tenant_isolation_tier": self.tenant_isolation_tier,
            "product_types": self.product_types,
            "channels": self.channels,
            "periods": self.periods,
            "sections": _plain_mapping(self.sections),
        }


def build_section(cards: dict[str, Any]) -> MappingProxyType[str, Any]:
    return MappingProxyType({"cards": _deep_freeze(dict(sorted(cards.items())))})


def placeholder_operational_impact(component: str) -> CustomerDashboardOperationalImpact:
    return CustomerDashboardOperationalImpact(
        tenant_id="tenant-placeholder",
        component=component,
        status=OperationalImpactStatus.UNKNOWN,
        message="curated_signal_not_available",
    )


def _plain_mapping(value: Any) -> Any:
    if isinstance(value, MappingProxyType):
        return {key: _plain_mapping(nested) for key, nested in value.items()}
    if isinstance(value, dict):
        return {key: _plain_mapping(nested) for key, nested in value.items()}
    if isinstance(value, tuple):
        return tuple(_plain_mapping(nested) for nested in value)
    return value


def _deep_freeze(value: Any) -> Any:
    if isinstance(value, MappingProxyType):
        return value
    if isinstance(value, dict):
        return MappingProxyType(
            {key: _deep_freeze(nested) for key, nested in sorted(value.items())}
        )
    if isinstance(value, tuple | list):
        return tuple(_deep_freeze(nested) for nested in value)
    return value


def _validate_safe_mapping(value: Any, *, field_path: str = "dashboard") -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            _validate_safe_text(str(key), field_path=field_path)
            _validate_safe_mapping(nested, field_path=f"{field_path}.{key}")
        return
    if isinstance(value, tuple | list | frozenset):
        for index, nested in enumerate(value):
            _validate_safe_mapping(nested, field_path=f"{field_path}[{index}]")
        return
    if isinstance(value, str):
        _validate_safe_text(value, field_path=field_path)


def _validate_safe_text(value: str, *, field_path: str) -> None:
    lowered = value.lower()
    for forbidden in _FORBIDDEN_OUTPUT_TERMS:
        if forbidden in lowered:
            raise CustomerDashboardPrivacyError(
                code="customer_dashboard_forbidden_term",
                field_path=field_path,
                details={"term": forbidden},
            )
    if field_path.endswith((".started_at", ".ended_at")):
        return
    if _URL_OR_ENDPOINT_PATTERN.search(value) or mask_text(value) != value:
        raise CustomerDashboardPrivacyError(
            code="customer_dashboard_unsafe_text",
            field_path=field_path,
        )


def _validate_curated_code(value: str, *, field_path: str) -> None:
    if not isinstance(value, str) or not _CURATED_CODE_PATTERN.fullmatch(value):
        raise CustomerDashboardPrivacyError(
            code="customer_dashboard_invalid_curated_code",
            field_path=field_path,
        )
    _validate_safe_text(value, field_path=field_path)


def _validate_timestamp(value: datetime, *, field_path: str) -> None:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise CustomerDashboardPrivacyError(
            code="customer_dashboard_invalid_timestamp",
            field_path=field_path,
        )
    if value.astimezone(UTC) > datetime.now(UTC) + _MAX_FUTURE_SKEW:
        raise CustomerDashboardPrivacyError(
            code="customer_dashboard_future_timestamp",
            field_path=field_path,
        )


def _validate_technical_ref(value: str, *, field_path: str) -> None:
    if not _TECHNICAL_REF_PATTERN.fullmatch(value):
        raise CustomerDashboardPrivacyError(
            code="customer_dashboard_invalid_technical_ref",
            field_path=field_path,
        )


def _validate_enum(value: object, enum_type: type[StrEnum], *, field_path: str) -> None:
    if not isinstance(value, enum_type):
        raise CustomerDashboardPrivacyError(
            code="customer_dashboard_invalid_status",
            field_path=field_path,
        )
