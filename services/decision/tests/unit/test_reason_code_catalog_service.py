from __future__ import annotations

from datetime import UTC, datetime

import pytest
from creditos_decision.adapters.persistence import (
    InMemoryCreditPolicyRepository,
    InMemoryReasonCodeCatalogRepository,
)
from creditos_decision.application.ports import (
    DecisionAuditIntent,
    ReasonCodeCatalogAuditIntent,
)
from creditos_decision.application.service import (
    CreateCreditPolicyDraftCommand,
    CreateReasonCodeCatalogDraftCommand,
    DecisionApplicationService,
    UpdateReasonCodeCatalogDraftCommand,
)
from creditos_decision.domain.errors import (
    PolicyTenantContextError,
    PolicyValidationError,
    ReasonCodeCatalogNotFoundError,
)
from creditos_decision.domain.value_objects import (
    ExplainableFactor,
    PolicyApplicability,
    PolicyCriterion,
    PolicyLimit,
    PolicyRule,
    ReasonCode,
)
from creditos_observability.context import ObservabilityContext
from creditos_security import PropagatedContext, TrustedContext

NOW = datetime(2026, 8, 26, 12, 0, tzinfo=UTC)


class RecordingAuditPublisher:
    def __init__(self) -> None:
        self.events: list[DecisionAuditIntent] = []

    def publish(self, event: DecisionAuditIntent) -> None:
        self.events.append(event)


def test_create_reason_code_catalog_uses_trusted_context_and_minimized_audit() -> None:
    audit = RecordingAuditPublisher()
    service = _service(audit=audit)

    result = service.create_reason_code_catalog_draft(
        _create_catalog_command(),
        context=_context("tenant_alpha"),
        trusted_context=_trusted_context(),
    )

    assert result.catalog.tenant_id == "tenant_alpha"
    assert result.catalog.status == "draft"
    assert audit.events[-1] == ReasonCodeCatalogAuditIntent(
        event_type="reason_code_catalog.created",
        tenant_id="tenant_alpha",
        actor_subject_id="user_credit_manager",
        catalog_id="rcc_personal_credit_default",
        catalog_version_id="rccver_personal_credit_default_v1",
        correlation_id="corr_1234567890abcdef",
        safe_details={
            "change_summary": "Criação inicial do catálogo",
            "product_type": "personal_credit",
            "status": "draft",
        },
    )
    assert result.logs[0]["payload"] == "[OMITIDO]"


def test_policy_creation_validates_reason_code_refs_against_catalog_version() -> None:
    audit = RecordingAuditPublisher()
    service = _service(audit=audit)
    service.create_reason_code_catalog_draft(
        _create_catalog_command(),
        context=_context("tenant_alpha"),
        trusted_context=_trusted_context(),
    )

    created = service.create_policy_draft(
        _create_policy_command(),
        context=_context("tenant_alpha"),
        trusted_context=_trusted_context(),
    )

    assert created.policy.rules[0].reason_code_refs == ("rc_min_income",)

    with pytest.raises(PolicyValidationError, match="reason code inexistente"):
        service.create_policy_draft(
            _create_policy_command(
                rule=PolicyRule.create(
                    rule_id="rule_unknown_reason",
                    name="Reason code inexistente",
                    source_field="monthly_income_units",
                    operator="gte",
                    threshold_value=250_000,
                    outcome="reject",
                    reason_code_refs=("rc_unknown",),
                ),
                policy_version_id="polver_personal_credit_default_v2",
            ),
            context=_context("tenant_alpha"),
            trusted_context=_trusted_context(),
        )

    assert audit.events[-1].event_type == "credit_policy.rejected"
    assert audit.events[-1].safe_details["rejection_reason"] == "unknown_reason_code"


def test_reason_code_catalog_operations_reject_cross_tenant_without_revealing_catalog() -> None:
    audit = RecordingAuditPublisher()
    service = _service(audit=audit)
    created = service.create_reason_code_catalog_draft(
        _create_catalog_command(),
        context=_context("tenant_alpha"),
        trusted_context=_trusted_context(),
    )

    with pytest.raises(ReasonCodeCatalogNotFoundError):
        service.update_reason_code_catalog_draft(
            UpdateReasonCodeCatalogDraftCommand(
                catalog_id=created.catalog.catalog_id,
                catalog_version_id=created.catalog.catalog_version_id,
                change_summary="Tentativa cross-tenant",
                reason_codes=created.catalog.reason_codes,
                explainable_factors=created.catalog.explainable_factors,
            ),
            context=_context("tenant_beta"),
            trusted_context=_trusted_context(tenant_id="tenant_beta"),
        )

    assert audit.events[-1].event_type == "reason_code_catalog.rejected"
    assert audit.events[-1].safe_details["rejection_reason"] == "reason_code_catalog_not_found"


def test_catalog_operations_require_policy_write_scope_and_bridge_tier() -> None:
    audit = RecordingAuditPublisher()
    service = _service(audit=audit)

    with pytest.raises(PolicyTenantContextError, match="escopo obrigatório ausente"):
        service.create_reason_code_catalog_draft(
            _create_catalog_command(),
            context=_context("tenant_alpha"),
            trusted_context=_trusted_context(scopes=("policy:read",)),
        )

    with pytest.raises(PolicyTenantContextError, match="tier de tenant não suportado"):
        service.create_reason_code_catalog_draft(
            _create_catalog_command(),
            context=_context("tenant_alpha", tenant_isolation_tier="silo"),
            trusted_context=_trusted_context(tenant_isolation_tier="silo"),
        )

    assert audit.events[-1].event_type == "reason_code_catalog.rejected"
    assert audit.events[-1].safe_details["operation"] == "reason_code_catalog.create_draft"


def test_policy_catalog_validation_does_not_leak_cross_tenant_catalog_existence() -> None:
    service = _service()
    service.create_reason_code_catalog_draft(
        _create_catalog_command(),
        context=_context("tenant_alpha"),
        trusted_context=_trusted_context(),
    )

    with pytest.raises(ReasonCodeCatalogNotFoundError):
        service.create_policy_draft(
            _create_policy_command(),
            context=_context("tenant_beta"),
            trusted_context=_trusted_context(tenant_id="tenant_beta"),
        )


def _service(
    *,
    audit: RecordingAuditPublisher | None = None,
) -> DecisionApplicationService:
    return DecisionApplicationService(
        repository=InMemoryCreditPolicyRepository(),
        reason_code_catalog_repository=InMemoryReasonCodeCatalogRepository(),
        audit_publisher=audit or RecordingAuditPublisher(),
        environment="test",
        clock=lambda: NOW,
    )


def _create_catalog_command() -> CreateReasonCodeCatalogDraftCommand:
    return CreateReasonCodeCatalogDraftCommand(
        catalog_id="rcc_personal_credit_default",
        catalog_version_id="rccver_personal_credit_default_v1",
        owner_subject_id="user_credit_manager",
        product_type="personal_credit",
        change_summary="Criação inicial do catálogo",
        reason_codes=(
            ReasonCode.create(
                reason_code_id="reason_min_income",
                code="rc_min_income",
                outcome="reject",
                title="Renda mínima",
                internal_description="Renda declarada abaixo da política",
                external_description="Renda declarada insuficiente para aprovação",
                factor_refs=("factor_monthly_income",),
            ),
        ),
        explainable_factors=(
            ExplainableFactor.create(
                factor_id="factor_monthly_income",
                field="monthly_income_units",
                title="Renda declarada",
                internal_description="Renda mensal declarada em unidades monetárias menores",
                external_description="Renda declarada informada para análise",
                required=True,
            ),
        ),
    )


def _create_policy_command(
    *,
    rule: PolicyRule | None = None,
    policy_version_id: str = "polver_personal_credit_default_v1",
) -> CreateCreditPolicyDraftCommand:
    return CreateCreditPolicyDraftCommand(
        policy_id="pol_personal_credit_default",
        policy_version_id=policy_version_id,
        reason_code_catalog_id="rcc_personal_credit_default",
        reason_code_catalog_version_id="rccver_personal_credit_default_v1",
        owner_subject_id="user_credit_manager",
        product_type="personal_credit",
        change_summary="Criação inicial da política padrão",
        applicability=PolicyApplicability.create(channels=("api", "checkout")),
        rules=(
            rule
            or PolicyRule.create(
                rule_id="rule_min_income",
                name="Renda mínima declarada",
                source_field="monthly_income_units",
                operator="gte",
                threshold_value=250_000,
                outcome="reject",
                reason_code_refs=("rc_min_income",),
            ),
        ),
        criteria=(
            PolicyCriterion.create(
                criterion_id="criterion_requested_amount",
                field="requested_amount_units",
                operator="lte",
                value=1_000_000,
            ),
        ),
        limits=(
            PolicyLimit.create(
                limit_id="limit_max_installments",
                limit_type="max_installments",
                value=24,
            ),
        ),
    )


def _context(
    tenant_id: str | None,
    *,
    tenant_isolation_tier: str = "bridge",
) -> ObservabilityContext:
    return ObservabilityContext.new(
        correlation_id="corr_1234567890abcdef",
        request_id="req_1234567890abcdef",
        trace_id="1234567890abcdef1234567890abcdef",
        tenant_id=tenant_id,
        tenant_isolation_tier=tenant_isolation_tier,
    )


def _trusted_context(
    *,
    tenant_id: str = "tenant_alpha",
    tenant_isolation_tier: str = "bridge",
    subject_id: str = "user_credit_manager",
    scopes: tuple[str, ...] = ("policy:write", "policy:read"),
) -> PropagatedContext:
    return PropagatedContext(
        trusted=TrustedContext(
            tenant_id=tenant_id,
            tenant_isolation_tier=tenant_isolation_tier,
            subject_id=subject_id,
            scopes=scopes,
            roles=("credit-manager",),
            client_id="client_admin_console",
            principal_type="human",
        ),
        correlation_id="corr_1234567890abcdef",
        request_id="req_1234567890abcdef",
        traceparent="00-1234567890abcdef1234567890abcdef-1234567890abcdef-01",
    )
