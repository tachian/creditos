from __future__ import annotations

from datetime import UTC, datetime

import pytest
from creditos_identity_tenant.domain.entities.tenant import Tenant
from creditos_identity_tenant.domain.errors import (
    InvalidTenantIdentifierError,
    InvalidTenantIsolationTierError,
    InvalidTenantNameError,
)
from creditos_identity_tenant.domain.value_objects.tenant_isolation_tier import TenantIsolationTier
from creditos_identity_tenant.domain.value_objects.tenant_status import TenantStatus


def test_tenant_creation_defaults_to_bridge_and_records_metadata() -> None:
    created_at = datetime(2026, 8, 4, 12, 0, tzinfo=UTC)

    tenant = Tenant.create(
        tenant_id="tenant_alpha",
        name="Financeira Alpha",
        status="active",
        operator_id="operator-platform",
        created_at=created_at,
    )

    assert tenant.tenant_id == "tenant_alpha"
    assert tenant.name == "Financeira Alpha"
    assert tenant.status is TenantStatus.ACTIVE
    assert tenant.tenant_isolation_tier is TenantIsolationTier.BRIDGE
    assert tenant.created_at == created_at
    assert tenant.updated_at == created_at
    assert tenant.created_by == "operator-platform"
    assert tenant.updated_by == "operator-platform"


def test_tenant_accepts_valid_silo_tier_for_future_isolation_path() -> None:
    tenant = Tenant.create(
        tenant_id="tenant_silo",
        name="Tenant Silo",
        status=TenantStatus.SUSPENDED,
        tenant_isolation_tier="silo",
        operator_id="operator-platform",
    )

    assert tenant.status is TenantStatus.SUSPENDED
    assert tenant.tenant_isolation_tier is TenantIsolationTier.SILO


def test_tenant_rejects_pooled_tier_for_sensitive_transactional_data() -> None:
    with pytest.raises(InvalidTenantIsolationTierError, match="tenant_isolation_tier"):
        Tenant.create(
            tenant_id="tenant_pooled",
            name="Tenant Pooled",
            status="active",
            tenant_isolation_tier="pooled",
            operator_id="operator-platform",
        )


def test_tenant_rejects_none_and_invalid_identifier_inputs() -> None:
    with pytest.raises(InvalidTenantNameError):
        Tenant.create(
            tenant_id="tenant_alpha",
            name=None,  # type: ignore[arg-type]
            status="active",
            operator_id="operator-platform",
        )

    with pytest.raises(InvalidTenantIdentifierError):
        Tenant.create(
            tenant_id="TENANT/ALPHA",
            name="Financeira Alpha",
            status="active",
            operator_id="operator-platform",
        )


def test_domain_errors_expose_stable_safe_codes() -> None:
    error = InvalidTenantNameError("nome do tenant é obrigatório")

    assert error.code == "invalid_tenant_name"
    assert error.safe_message == "nome do tenant inválido"
    assert error.grpc_status == "INVALID_ARGUMENT"
    assert str(error) == "nome do tenant é obrigatório"
