from __future__ import annotations

import re
from dataclasses import dataclass

from creditos_reporting_insights.domain.errors import CustomerDashboardAuthorizationError

_TECHNICAL_REF_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_.-]{1,119}$")
_SCOPE_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_.:-]{1,119}$")
_ALLOWED_DASHBOARD_SCOPES = frozenset({"dashboard:read", "reporting:read"})


@dataclass(frozen=True, slots=True)
class CustomerDashboardAccessContext:
    tenant_id: str
    scopes: frozenset[str]

    def __post_init__(self) -> None:
        if not _TECHNICAL_REF_PATTERN.fullmatch(self.tenant_id):
            raise CustomerDashboardAuthorizationError(
                code="customer_dashboard_invalid_tenant_context",
                field_path="tenant_id",
            )
        if not isinstance(self.scopes, frozenset):
            raise CustomerDashboardAuthorizationError(
                code="customer_dashboard_invalid_scope_collection",
                field_path="scopes",
            )
        invalid_scopes = tuple(
            scope
            for scope in self.scopes
            if not isinstance(scope, str) or not _SCOPE_PATTERN.fullmatch(scope)
        )
        if invalid_scopes:
            raise CustomerDashboardAuthorizationError(
                code="customer_dashboard_invalid_scope",
                field_path="scopes",
            )

    def require_dashboard_read(self) -> None:
        if self.scopes.isdisjoint(_ALLOWED_DASHBOARD_SCOPES):
            raise CustomerDashboardAuthorizationError(
                code="customer_dashboard_scope_denied",
                field_path="scopes",
            )
