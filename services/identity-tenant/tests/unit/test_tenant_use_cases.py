from __future__ import annotations

import pytest
from creditos_identity_tenant.adapters.persistence.in_memory_tenant_repository import (
    InMemoryTenantRepository,
)
from creditos_identity_tenant.application.security import OperatorContext
from creditos_identity_tenant.application.use_cases.create_tenant import (
    CreateTenantCommand,
    CreateTenantUseCase,
)
from creditos_identity_tenant.application.use_cases.get_tenant import (
    GetTenantQuery,
    GetTenantUseCase,
)
from creditos_identity_tenant.domain.errors import (
    CrossTenantAccessDeniedError,
    InvalidTenantNameError,
    InvalidTenantStatusError,
    TenantAlreadyExistsError,
    TenantNotFoundError,
    UnauthorizedOperatorError,
)


def test_create_tenant_persists_unique_tenant_with_default_bridge_tier() -> None:
    repository = InMemoryTenantRepository()
    use_case = CreateTenantUseCase(
        repository=repository,
        tenant_id_generator=lambda: "tenant_alpha",
    )

    tenant = use_case.execute(
        CreateTenantCommand(name="Financeira Alpha", status="active"),
        operator=OperatorContext.platform_operator("operator-platform"),
    )

    assert tenant.tenant_id == "tenant_alpha"
    assert tenant.tenant_isolation_tier.value == "bridge"
    assert repository.get("tenant_alpha") == tenant


def test_create_tenant_rejects_invalid_data_without_partial_state() -> None:
    repository = InMemoryTenantRepository()
    use_case = CreateTenantUseCase(
        repository=repository,
        tenant_id_generator=lambda: "tenant_invalid",
    )

    with pytest.raises(InvalidTenantNameError):
        use_case.execute(
            CreateTenantCommand(name=" ", status="active"),
            operator=OperatorContext.platform_operator("operator-platform"),
        )

    with pytest.raises(InvalidTenantStatusError):
        use_case.execute(
            CreateTenantCommand(name="Financeira Alpha", status="deleted"),
            operator=OperatorContext.platform_operator("operator-platform"),
        )

    assert repository.get("tenant_invalid") is None


def test_create_tenant_rejects_duplicate_identifier_deterministically() -> None:
    repository = InMemoryTenantRepository()
    use_case = CreateTenantUseCase(
        repository=repository,
        tenant_id_generator=lambda: "tenant_duplicate",
    )
    operator = OperatorContext.platform_operator("operator-platform")

    use_case.execute(CreateTenantCommand(name="Primeiro", status="active"), operator=operator)

    with pytest.raises(TenantAlreadyExistsError, match="tenant_duplicate"):
        use_case.execute(CreateTenantCommand(name="Segundo", status="active"), operator=operator)

    assert repository.get("tenant_duplicate") is not None


def test_get_tenant_returns_metadata_and_blocks_cross_tenant_context() -> None:
    repository = InMemoryTenantRepository()
    create_use_case = CreateTenantUseCase(
        repository=repository,
        tenant_id_generator=lambda: "tenant_alpha",
    )
    get_use_case = GetTenantUseCase(repository=repository)
    operator = OperatorContext.platform_operator("operator-platform")

    create_use_case.execute(CreateTenantCommand(name="Financeira Alpha", status="active"), operator)

    metadata = get_use_case.execute(GetTenantQuery(tenant_id="tenant_alpha"), operator=operator)

    assert metadata == {
        "tenant_id": "tenant_alpha",
        "name": "Financeira Alpha",
        "status": "active",
        "tenant_isolation_tier": "bridge",
    }

    with pytest.raises(CrossTenantAccessDeniedError):
        get_use_case.execute(
            GetTenantQuery(tenant_id="tenant_alpha", trusted_context_tenant_id="tenant_beta"),
            operator=operator,
        )

    with pytest.raises(TenantNotFoundError):
        get_use_case.execute(GetTenantQuery(tenant_id="tenant_missing"), operator=operator)


def test_operations_are_deny_by_default_and_require_explicit_authorization() -> None:
    repository = InMemoryTenantRepository()
    create_use_case = CreateTenantUseCase(
        repository=repository,
        tenant_id_generator=lambda: "tenant_alpha",
    )
    get_use_case = GetTenantUseCase(repository=repository)

    with pytest.raises(UnauthorizedOperatorError, match="não autorizado"):
        create_use_case.execute(
            CreateTenantCommand(name="Financeira Alpha", status="active"),
            operator=OperatorContext(operator_id="operator-platform"),
        )

    create_use_case.execute(
        CreateTenantCommand(name="Financeira Alpha", status="active"),
        operator=OperatorContext.platform_operator("operator-platform"),
    )

    with pytest.raises(UnauthorizedOperatorError, match="sem permissão"):
        get_use_case.execute(
            GetTenantQuery(tenant_id="tenant_alpha"),
            operator=OperatorContext.tenant_scoped("client-alpha"),
        )


def test_tenant_scoped_query_requires_matching_trusted_context() -> None:
    repository = InMemoryTenantRepository()
    create_use_case = CreateTenantUseCase(
        repository=repository,
        tenant_id_generator=lambda: "tenant_alpha",
    )
    get_use_case = GetTenantUseCase(repository=repository)
    create_use_case.execute(
        CreateTenantCommand(name="Financeira Alpha", status="active"),
        operator=OperatorContext.platform_operator("operator-platform"),
    )

    metadata = get_use_case.execute(
        GetTenantQuery(tenant_id="tenant_alpha", trusted_context_tenant_id="tenant_alpha"),
        operator=OperatorContext.tenant_scoped("client-alpha"),
    )

    assert metadata["tenant_id"] == "tenant_alpha"
