from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from creditos_integration.domain.value_objects.catalog import (
    parse_fallback_strategy,
    parse_integration_class,
    parse_product_type,
    parse_requirement,
    validate_adapter_id,
    validate_configuration_id,
    validate_estimated_cost_units,
    validate_max_attempts,
    validate_max_concurrency,
    validate_timeout_ms,
)

SCHEMA_VERSION = "1.0"


@dataclass(frozen=True, slots=True)
class IntegrationConfiguration:
    configuration_id: str
    tenant_id: str
    product_type: str
    integration_class: str
    adapter_id: str
    requirement: str
    timeout_ms: int
    max_attempts: int
    max_concurrency: int
    estimated_cost_units: int
    fallback_strategy: str
    enabled: bool
    schema_version: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def create(
        cls,
        *,
        configuration_id: str,
        tenant_id: str,
        product_type: str,
        integration_class: str,
        adapter_id: str,
        requirement: str,
        timeout_ms: int,
        max_attempts: int,
        max_concurrency: int,
        estimated_cost_units: int,
        fallback_strategy: str,
        enabled: bool,
        now: datetime,
        created_at: datetime | None = None,
    ) -> IntegrationConfiguration:
        return cls(
            configuration_id=validate_configuration_id(configuration_id),
            tenant_id=tenant_id,
            product_type=parse_product_type(product_type),
            integration_class=parse_integration_class(integration_class),
            adapter_id=validate_adapter_id(adapter_id),
            requirement=parse_requirement(requirement),
            timeout_ms=validate_timeout_ms(timeout_ms),
            max_attempts=validate_max_attempts(max_attempts),
            max_concurrency=validate_max_concurrency(max_concurrency),
            estimated_cost_units=validate_estimated_cost_units(estimated_cost_units),
            fallback_strategy=parse_fallback_strategy(fallback_strategy),
            enabled=enabled,
            schema_version=SCHEMA_VERSION,
            created_at=created_at or now,
            updated_at=now,
        )

    def to_plan_metadata(self) -> dict[str, object]:
        return {
            "configuration_id": self.configuration_id,
            "tenant_id": self.tenant_id,
            "product_type": self.product_type,
            "integration_class": self.integration_class,
            "adapter_id": self.adapter_id,
            "requirement": self.requirement,
            "timeout_ms": self.timeout_ms,
            "max_attempts": self.max_attempts,
            "max_concurrency": self.max_concurrency,
            "estimated_cost_units": self.estimated_cost_units,
            "fallback_strategy": self.fallback_strategy,
            "schema_version": self.schema_version,
        }
