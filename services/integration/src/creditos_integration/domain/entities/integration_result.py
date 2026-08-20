from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from math import isfinite

from creditos_integration.domain.errors import IntegrationValidationError
from creditos_integration.domain.value_objects.catalog import (
    parse_product_type,
    validate_adapter_id,
)
from creditos_integration.domain.value_objects.result import (
    parse_mock_scenario,
    parse_result_status,
    validate_reason_codes,
    validate_result_id,
    validate_summary,
    validate_supported_mock_integration_class,
)


@dataclass(frozen=True, slots=True)
class IntegrationResult:
    result_id: str
    tenant_id: str
    product_type: str
    integration_class: str
    adapter_id: str
    status: str
    scenario: str
    schema_version: str
    reason_codes: tuple[str, ...]
    summary: Mapping[str, object]
    correlation_id: str
    trace_id: str
    started_at: datetime
    completed_at: datetime
    duration_ms: float

    @classmethod
    def create(
        cls,
        *,
        result_id: str,
        tenant_id: str,
        product_type: str,
        integration_class: str,
        adapter_id: str,
        status: str,
        scenario: str,
        reason_codes: tuple[str, ...],
        summary: Mapping[str, object],
        correlation_id: str,
        trace_id: str,
        started_at: datetime,
        completed_at: datetime,
        duration_ms: float,
        schema_version: str = "1.0",
    ) -> IntegrationResult:
        if schema_version != "1.0":
            raise IntegrationValidationError(
                "schema de resultado de integração não suportado",
                code="unsupported_integration_result_schema_version",
                field_path="schema_version",
            )
        if not isfinite(duration_ms) or duration_ms < 0:
            raise IntegrationValidationError(
                "duração de resultado de integração inválida",
                code="invalid_integration_result_duration",
                field_path="duration_ms",
            )
        if completed_at < started_at:
            raise IntegrationValidationError(
                "janela temporal de resultado de integração inválida",
                code="invalid_integration_result_time_window",
                field_path="completed_at",
            )
        integration_class = validate_supported_mock_integration_class(integration_class)
        return cls(
            result_id=validate_result_id(result_id),
            tenant_id=tenant_id,
            product_type=parse_product_type(product_type),
            integration_class=integration_class,
            adapter_id=validate_adapter_id(adapter_id),
            status=parse_result_status(status),
            scenario=parse_mock_scenario(scenario),
            schema_version=schema_version,
            reason_codes=validate_reason_codes(reason_codes),
            summary=validate_summary(integration_class, summary),
            correlation_id=correlation_id,
            trace_id=trace_id,
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=duration_ms,
        )

    def to_log_safe_dict(self) -> dict[str, object]:
        return {
            "result_id": self.result_id,
            "tenant_id": self.tenant_id,
            "product_type": self.product_type,
            "integration_class": self.integration_class,
            "adapter_id": self.adapter_id,
            "status": self.status,
            "scenario": self.scenario,
            "schema_version": self.schema_version,
            "reason_codes": self.reason_codes,
            "correlation_id": self.correlation_id,
            "trace_id": self.trace_id,
            "duration_ms": self.duration_ms,
        }
