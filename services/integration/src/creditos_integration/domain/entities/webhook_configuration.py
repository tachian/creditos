from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from creditos_integration.domain.value_objects.webhook import (
    parse_webhook_events,
    parse_webhook_request_status,
    parse_webhook_retry_strategy,
    parse_webhook_signing_algorithm,
    validate_retry_limits,
    validate_signing_key_ref,
    validate_webhook_configuration_id,
    validate_webhook_endpoint_url,
    webhook_endpoint_host,
)

SCHEMA_VERSION = "1.0"


@dataclass(frozen=True, slots=True)
class WebhookConfiguration:
    webhook_configuration_id: str
    tenant_id: str
    endpoint_url: str
    events: tuple[str, ...]
    status: str
    signing_algorithm: str
    signing_key_ref: str
    retry_strategy: str
    max_attempts: int
    initial_backoff_ms: int
    max_backoff_ms: int
    timeout_ms: int
    contract_version: str
    schema_version: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def create(
        cls,
        *,
        webhook_configuration_id: str,
        tenant_id: str,
        endpoint_url: str,
        events: tuple[str, ...],
        status: str,
        signing_algorithm: str,
        signing_key_ref: str,
        retry_strategy: str,
        max_attempts: int,
        initial_backoff_ms: int,
        max_backoff_ms: int,
        timeout_ms: int,
        now: datetime,
        allowed_domains: tuple[str, ...] = (),
        resolved_addresses: tuple[str, ...] = (),
        created_at: datetime | None = None,
        contract_version: str = "v1",
    ) -> WebhookConfiguration:
        parsed_retry_strategy = parse_webhook_retry_strategy(retry_strategy)
        parsed_limits = validate_retry_limits(
            strategy=parsed_retry_strategy,
            max_attempts=max_attempts,
            initial_backoff_ms=initial_backoff_ms,
            max_backoff_ms=max_backoff_ms,
            timeout_ms=timeout_ms,
        )
        return cls(
            webhook_configuration_id=validate_webhook_configuration_id(webhook_configuration_id),
            tenant_id=tenant_id,
            endpoint_url=validate_webhook_endpoint_url(
                endpoint_url,
                allowed_domains=allowed_domains,
                resolved_addresses=resolved_addresses,
            ),
            events=parse_webhook_events(events),
            status=parse_webhook_request_status(status),
            signing_algorithm=parse_webhook_signing_algorithm(signing_algorithm),
            signing_key_ref=validate_signing_key_ref(signing_key_ref),
            retry_strategy=parsed_retry_strategy,
            max_attempts=parsed_limits[0],
            initial_backoff_ms=parsed_limits[1],
            max_backoff_ms=parsed_limits[2],
            timeout_ms=parsed_limits[3],
            contract_version=contract_version,
            schema_version=SCHEMA_VERSION,
            created_at=created_at or now,
            updated_at=now,
        )

    @property
    def endpoint_host(self) -> str:
        return webhook_endpoint_host(self.endpoint_url)

    def disable(self, *, now: datetime) -> WebhookConfiguration:
        return WebhookConfiguration(
            webhook_configuration_id=self.webhook_configuration_id,
            tenant_id=self.tenant_id,
            endpoint_url=self.endpoint_url,
            events=self.events,
            status="disabled",
            signing_algorithm=self.signing_algorithm,
            signing_key_ref=self.signing_key_ref,
            retry_strategy=self.retry_strategy,
            max_attempts=self.max_attempts,
            initial_backoff_ms=self.initial_backoff_ms,
            max_backoff_ms=self.max_backoff_ms,
            timeout_ms=self.timeout_ms,
            contract_version=self.contract_version,
            schema_version=self.schema_version,
            created_at=self.created_at,
            updated_at=now,
        )

    def to_log_safe_dict(self) -> dict[str, object]:
        return {
            "webhook_configuration_id": self.webhook_configuration_id,
            "endpoint_host": self.endpoint_host,
            "event_types": self.events,
            "webhook_status": self.status,
            "signing_algorithm": self.signing_algorithm,
            "signing_key_ref_present": bool(self.signing_key_ref),
            "retry_strategy": self.retry_strategy,
            "max_attempts": self.max_attempts,
            "initial_backoff_ms": self.initial_backoff_ms,
            "max_backoff_ms": self.max_backoff_ms,
            "timeout_ms": self.timeout_ms,
            "contract_version": self.contract_version,
            "schema_version": self.schema_version,
        }
