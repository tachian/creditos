from __future__ import annotations

from dataclasses import dataclass

from creditos_integration.domain.entities.integration_configuration import IntegrationConfiguration


@dataclass(frozen=True, slots=True)
class IntegrationPlanItem:
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
    configuration_id: str
    provider_id: str | None = None

    @classmethod
    def from_configuration(cls, configuration: IntegrationConfiguration) -> IntegrationPlanItem:
        return cls(
            tenant_id=configuration.tenant_id,
            product_type=configuration.product_type,
            integration_class=configuration.integration_class,
            adapter_id=configuration.adapter_id,
            requirement=configuration.requirement,
            timeout_ms=configuration.timeout_ms,
            max_attempts=configuration.max_attempts,
            max_concurrency=configuration.max_concurrency,
            estimated_cost_units=configuration.estimated_cost_units,
            fallback_strategy=configuration.fallback_strategy,
            configuration_id=configuration.configuration_id,
            provider_id=configuration.provider_id,
        )


@dataclass(frozen=True, slots=True)
class IntegrationPlan:
    tenant_id: str
    product_type: str
    status: str
    items: tuple[IntegrationPlanItem, ...]
    missing_required_classes: tuple[str, ...] = ()
    invalid_configuration_classes: tuple[str, ...] = ()
