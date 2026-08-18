from __future__ import annotations

from typing import Protocol

from creditos_integration.domain.entities import IntegrationConfiguration


class IntegrationCatalogRepository(Protocol):
    def save(self, configuration: IntegrationConfiguration) -> None: ...

    def delete(self, configuration_id: str, tenant_id: str) -> None: ...

    def get(self, configuration_id: str, tenant_id: str) -> IntegrationConfiguration | None: ...

    def list_for_tenant_product(
        self,
        *,
        tenant_id: str,
        product_type: str,
    ) -> tuple[IntegrationConfiguration, ...]: ...
