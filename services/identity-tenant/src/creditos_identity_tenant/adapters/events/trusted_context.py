from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from time import perf_counter

from creditos_observability.context import ObservabilityContext
from creditos_observability.logging import build_structured_log
from creditos_security.context import (
    CloudEventTrustedContext,
    PropagatedContext,
    cloudevent_context_from_attributes,
    context_to_cloudevent_attributes,
)

from creditos_identity_tenant.application.ports.operation_logger import OperationLogger
from creditos_identity_tenant.application.security import AuthorizationSubject
from creditos_identity_tenant.application.trusted_context import (
    ensure_expected_tenant,
    propagated_context_from_authorization_subject,
)

SERVICE_NAME = "identity-tenant"
SERVICE_VERSION = "0.1.0"
CONTRACT = "identity-tenant-trusted-context"
CONTRACT_VERSION = "v1"


def cloudevent_attributes_from_authorization_subject(
    subject: AuthorizationSubject,
    context: ObservabilityContext,
    *,
    idempotency_key: str,
    schema_version: str = "v1",
) -> dict[str, str]:
    return context_to_cloudevent_attributes(
        propagated_context_from_authorization_subject(
            subject,
            context,
            schema_version=schema_version,
        ),
        idempotency_key=idempotency_key,
    )


def propagated_context_from_cloudevent_attributes(
    attributes: Mapping[str, str],
    *,
    expected_tenant_id: str | None = None,
    operation_logger: OperationLogger | None = None,
    observability_context: ObservabilityContext | None = None,
    environment: str = "test",
) -> PropagatedContext:
    return event_context_from_cloudevent_attributes(
        attributes,
        expected_tenant_id=expected_tenant_id,
        operation_logger=operation_logger,
        observability_context=observability_context,
        environment=environment,
    ).context


def event_context_from_cloudevent_attributes(
    attributes: Mapping[str, str],
    *,
    expected_tenant_id: str | None = None,
    operation_logger: OperationLogger | None = None,
    observability_context: ObservabilityContext | None = None,
    environment: str = "test",
) -> CloudEventTrustedContext:
    started_at = perf_counter()
    try:
        event_context = cloudevent_context_from_attributes(attributes)
        ensure_expected_tenant(event_context.context, expected_tenant_id)
        return event_context
    except Exception as error:
        _log_context_rejection(
            operation_logger=operation_logger,
            context=observability_context,
            environment=environment,
            operation="identity_tenant.validate_cloudevent_trusted_context",
            duration_ms=_duration_ms(started_at),
            error=error,
        )
        raise


def _log_context_rejection(
    *,
    operation_logger: OperationLogger | None,
    context: ObservabilityContext | None,
    environment: str,
    operation: str,
    duration_ms: float,
    error: Exception,
) -> None:
    if operation_logger is None or context is None:
        return
    event = build_structured_log(
        context=replace(context, tenant_id=None, tenant_isolation_tier=None),
        service_name=SERVICE_NAME,
        service_version=SERVICE_VERSION,
        environment=environment,
        operation=operation,
        source="trusted-context",
        destination=SERVICE_NAME,
        contract=CONTRACT,
        contract_version=CONTRACT_VERSION,
        status="rejected",
        duration_ms=duration_ms,
        error_type=type(error).__name__,
        payload={"context": "[OMITIDO]"},
        extra={"context_validation": "denied"},
    )
    try:
        operation_logger.log(event)
    except Exception:
        return


def _duration_ms(started_at: float) -> float:
    return round((perf_counter() - started_at) * 1000, 6)
