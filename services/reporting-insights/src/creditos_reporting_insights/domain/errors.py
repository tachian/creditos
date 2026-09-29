from __future__ import annotations

from types import MappingProxyType
from typing import Any


class ReportingInsightsDomainError(ValueError):
    code = "reporting_insights_domain_error"
    safe_message = "erro de domínio de reporting e insights"
    grpc_status = "INVALID_ARGUMENT"

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        field_path: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.code = code or self.code
        self.field_path = field_path
        self.details = MappingProxyType(details or {})
        self.message = message or self.safe_message
        super().__init__(self.message)


class BusinessEventValidationError(ReportingInsightsDomainError):
    code = "business_event_validation_error"
    safe_message = "evento de negócio inválido"


class BusinessProjectionTenantError(ReportingInsightsDomainError):
    code = "business_projection_tenant_error"
    safe_message = "consulta de projeção fora do tenant permitido"
    grpc_status = "PERMISSION_DENIED"


class BusinessProjectionNotFoundError(ReportingInsightsDomainError):
    code = "business_projection_not_found"
    safe_message = "projeção de negócio não encontrada"


class CustomerDashboardAuthorizationError(ReportingInsightsDomainError):
    code = "customer_dashboard_authorization_error"
    safe_message = "acesso ao dashboard customer-facing negado"
    grpc_status = "PERMISSION_DENIED"


class CustomerDashboardPrivacyError(ReportingInsightsDomainError):
    code = "customer_dashboard_privacy_error"
    safe_message = "dashboard customer-facing contém dado não permitido"
