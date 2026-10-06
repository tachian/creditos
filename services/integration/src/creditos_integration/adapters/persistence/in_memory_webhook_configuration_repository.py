from __future__ import annotations

from threading import RLock

from creditos_integration.domain.entities.webhook_configuration import WebhookConfiguration


class InMemoryWebhookConfigurationRepository:
    def __init__(self) -> None:
        self._configurations: dict[tuple[str, str], WebhookConfiguration] = {}
        self._lock = RLock()

    def save(self, configuration: WebhookConfiguration) -> None:
        with self._lock:
            key = (configuration.tenant_id, configuration.webhook_configuration_id)
            self._configurations[key] = configuration

    def delete(self, webhook_configuration_id: str, tenant_id: str) -> None:
        with self._lock:
            self._configurations.pop((tenant_id, webhook_configuration_id), None)

    def get(
        self,
        webhook_configuration_id: str,
        tenant_id: str,
    ) -> WebhookConfiguration | None:
        with self._lock:
            return self._configurations.get((tenant_id, webhook_configuration_id))

    def list_for_tenant(self, *, tenant_id: str) -> tuple[WebhookConfiguration, ...]:
        with self._lock:
            return tuple(
                sorted(
                    (
                        configuration
                        for configuration in self._configurations.values()
                        if configuration.tenant_id == tenant_id
                    ),
                    key=lambda configuration: configuration.webhook_configuration_id,
                )
            )

    def list_all(self) -> list[WebhookConfiguration]:
        with self._lock:
            return list(self._configurations.values())
