from __future__ import annotations

from threading import RLock

from creditos_integration.domain.entities import IntegrationConfiguration


class InMemoryIntegrationCatalogRepository:
    def __init__(self) -> None:
        self._configurations: dict[tuple[str, str], IntegrationConfiguration] = {}
        self._lock = RLock()

    def save(self, configuration: IntegrationConfiguration) -> None:
        with self._lock:
            key = (configuration.tenant_id, configuration.configuration_id)
            self._configurations[key] = configuration

    def delete(self, configuration_id: str, tenant_id: str) -> None:
        with self._lock:
            self._configurations.pop((tenant_id, configuration_id), None)

    def get(self, configuration_id: str, tenant_id: str) -> IntegrationConfiguration | None:
        with self._lock:
            return self._configurations.get((tenant_id, configuration_id))

    def list_for_tenant_product(
        self,
        *,
        tenant_id: str,
        product_type: str,
    ) -> tuple[IntegrationConfiguration, ...]:
        with self._lock:
            return tuple(
                configuration
                for configuration in self._configurations.values()
                if configuration.tenant_id == tenant_id
                and configuration.product_type == product_type
                and configuration.enabled
            )

    def list_all(self) -> list[IntegrationConfiguration]:
        with self._lock:
            return list(self._configurations.values())
