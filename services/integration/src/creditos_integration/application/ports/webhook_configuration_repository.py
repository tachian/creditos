from __future__ import annotations

from typing import Protocol

from creditos_integration.domain.entities.webhook_configuration import WebhookConfiguration


class WebhookConfigurationRepository(Protocol):
    def save(self, configuration: WebhookConfiguration) -> None: ...

    def delete(self, webhook_configuration_id: str, tenant_id: str) -> None: ...

    def get(
        self,
        webhook_configuration_id: str,
        tenant_id: str,
    ) -> WebhookConfiguration | None: ...

    def list_for_tenant(self, *, tenant_id: str) -> tuple[WebhookConfiguration, ...]: ...
