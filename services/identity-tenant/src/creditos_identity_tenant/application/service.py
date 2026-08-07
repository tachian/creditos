from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import replace
from time import perf_counter
from typing import Any

from creditos_observability.context import ObservabilityContext
from creditos_observability.logging import build_structured_log

from creditos_identity_tenant.application.ports.m2m_token_verifier import M2MTokenVerifier
from creditos_identity_tenant.application.ports.operation_logger import OperationLogger
from creditos_identity_tenant.application.ports.tenant_repository import TenantRepository
from creditos_identity_tenant.application.security import OperatorContext
from creditos_identity_tenant.application.use_cases.create_tenant import (
    CreateTenantCommand,
    CreateTenantUseCase,
)
from creditos_identity_tenant.application.use_cases.get_tenant import (
    GetTenantQuery,
    GetTenantUseCase,
)
from creditos_identity_tenant.application.use_cases.resolve_m2m_tenant_context import (
    ResolveM2MTenantContextCommand,
    ResolveM2MTenantContextUseCase,
)
from creditos_identity_tenant.domain.entities.tenant import Tenant
from creditos_identity_tenant.domain.errors import InvalidTokenError

SERVICE_NAME = "identity-tenant"
SERVICE_VERSION = "0.1.0"
CONTRACT = "identity-tenant-internal-application"
CONTRACT_VERSION = "v1"
_FALLBACK_LOGGER = logging.getLogger("creditos.identity_tenant.operational_log_fallback")


class TenantApplicationService:
    def __init__(
        self,
        *,
        repository: TenantRepository,
        operation_logger: OperationLogger,
        tenant_id_generator: Callable[[], str] | None = None,
        m2m_token_verifier: M2MTokenVerifier | None = None,
        environment: str,
    ) -> None:
        self._operation_logger = operation_logger
        self._environment = environment
        self._resolve_m2m_tenant_context = (
            ResolveM2MTenantContextUseCase(
                repository=repository,
                token_verifier=m2m_token_verifier,
            )
            if m2m_token_verifier is not None
            else None
        )
        self._create_tenant = CreateTenantUseCase(
            repository=repository,
            tenant_id_generator=tenant_id_generator,
        )
        self._get_tenant = GetTenantUseCase(repository=repository)

    def create_tenant(
        self,
        command: CreateTenantCommand,
        *,
        operator: OperatorContext,
        context: ObservabilityContext,
    ) -> dict[str, str]:
        started_at = perf_counter()
        try:
            tenant = self._create_tenant.execute(command, operator)
            log_context = _context_with_tenant(context, tenant)
            self._log_operation(
                context=log_context,
                operation="identity_tenant.create_tenant",
                status="accepted",
                duration_ms=_duration_ms(started_at),
                payload=command,
                extra={"operator_id": operator.operator_id},
            )
            return tenant.to_metadata()
        except Exception as error:
            self._log_operation(
                context=context,
                operation="identity_tenant.create_tenant",
                status="rejected",
                duration_ms=_duration_ms(started_at),
                payload=command,
                error_type=type(error).__name__,
                extra={"operator_id": operator.operator_id},
            )
            raise

    def get_tenant(
        self,
        query: GetTenantQuery,
        *,
        operator: OperatorContext,
        context: ObservabilityContext,
    ) -> dict[str, str]:
        started_at = perf_counter()
        try:
            metadata = self._get_tenant.execute(query, operator)
            log_context = replace(
                context,
                tenant_id=metadata["tenant_id"],
                tenant_isolation_tier=metadata["tenant_isolation_tier"],
            )
            self._log_operation(
                context=log_context,
                operation="identity_tenant.get_tenant",
                status="accepted",
                duration_ms=_duration_ms(started_at),
                payload=query,
                extra={"operator_id": operator.operator_id},
            )
            return metadata
        except Exception as error:
            self._log_operation(
                context=context,
                operation="identity_tenant.get_tenant",
                status="rejected",
                duration_ms=_duration_ms(started_at),
                payload=query,
                error_type=type(error).__name__,
                extra={"operator_id": operator.operator_id},
            )
            raise

    def resolve_m2m_tenant_context(
        self,
        command: ResolveM2MTenantContextCommand,
        *,
        context: ObservabilityContext,
    ) -> dict[str, str]:
        started_at = perf_counter()
        try:
            use_case = self._require_m2m_resolver()
            resolved_context = use_case.execute(command)
            log_context = replace(
                context,
                tenant_id=resolved_context.tenant_id,
                tenant_isolation_tier=resolved_context.tenant_isolation_tier,
            )
            self._log_operation(
                context=log_context,
                operation="identity_tenant.resolve_m2m_tenant_context",
                status="accepted",
                duration_ms=_duration_ms(started_at),
                payload=command,
                extra={
                    "client_id": resolved_context.client_id,
                    "token_id": resolved_context.token_id,
                    "scopes": sorted(resolved_context.scopes),
                },
            )
            return resolved_context.to_metadata()
        except Exception as error:
            self._log_operation(
                context=_context_without_tenant(context),
                operation="identity_tenant.resolve_m2m_tenant_context",
                status="rejected",
                duration_ms=_duration_ms(started_at),
                payload=command,
                error_type=type(error).__name__,
                extra={"auth_failure": True},
            )
            raise

    def _log_operation(
        self,
        *,
        context: ObservabilityContext,
        operation: str,
        status: str,
        duration_ms: float,
        payload: Any,
        extra: dict[str, Any],
        error_type: str | None = None,
    ) -> None:
        event = build_structured_log(
            context=context,
            service_name=SERVICE_NAME,
            service_version=SERVICE_VERSION,
            environment=self._environment,
            operation=operation,
            source="operator-context",
            destination=SERVICE_NAME,
            contract=CONTRACT,
            contract_version=CONTRACT_VERSION,
            status=status,
            duration_ms=duration_ms,
            error_type=error_type,
            payload=payload,
            extra=extra,
        )
        try:
            self._operation_logger.log(event)
        except Exception as error:
            _FALLBACK_LOGGER.warning(
                "operational_log_failed",
                extra={
                    "service_name": SERVICE_NAME,
                    "operation": operation,
                    "error_type": type(error).__name__,
                },
            )

    def _require_m2m_resolver(self) -> ResolveM2MTenantContextUseCase:
        if self._resolve_m2m_tenant_context is None:
            raise InvalidTokenError("verificador M2M não configurado")
        return self._resolve_m2m_tenant_context


def _context_with_tenant(context: ObservabilityContext, tenant: Tenant) -> ObservabilityContext:
    return replace(
        context,
        tenant_id=tenant.tenant_id,
        tenant_isolation_tier=tenant.tenant_isolation_tier.value,
    )


def _context_without_tenant(context: ObservabilityContext) -> ObservabilityContext:
    return replace(context, tenant_id=None, tenant_isolation_tier=None)


def _duration_ms(started_at: float) -> float:
    return round((perf_counter() - started_at) * 1000, 6)
