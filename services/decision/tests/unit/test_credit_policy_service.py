from __future__ import annotations

from datetime import UTC, datetime

import pytest
from creditos_decision.adapters.persistence import InMemoryCreditPolicyRepository
from creditos_decision.application.ports import CreditPolicyAuditIntent
from creditos_decision.application.service import (
    CreateCreditPolicyDraftCommand,
    DecisionApplicationService,
    UpdateCreditPolicyDraftCommand,
)
from creditos_decision.domain.errors import (
    PolicyConcurrencyError,
    PolicyNotFoundError,
    PolicyTenantContextError,
)
from creditos_decision.domain.value_objects import (
    PolicyApplicability,
    PolicyCriterion,
    PolicyLimit,
    PolicyRule,
)
from creditos_observability.context import ObservabilityContext
from creditos_security import PropagatedContext, TrustedContext

NOW = datetime(2026, 8, 26, 12, 0, tzinfo=UTC)


class RecordingAuditPublisher:
    def __init__(self) -> None:
        self.events: list[CreditPolicyAuditIntent] = []

    def publish(self, event: CreditPolicyAuditIntent) -> None:
        self.events.append(event)


def test_create_policy_uses_trusted_context_and_publishes_minimized_audit_intent() -> None:
    audit = RecordingAuditPublisher()
    service = DecisionApplicationService(
        repository=InMemoryCreditPolicyRepository(),
        audit_publisher=audit,
        environment="test",
        clock=lambda: NOW,
    )

    result = service.create_policy_draft(
        _create_command(),
        context=_context("tenant_alpha"),
        trusted_context=_trusted_context(),
    )

    assert result.policy.tenant_id == "tenant_alpha"
    assert result.policy.status == "draft"
    assert result.policy.is_executable_in_production is False
    assert len(audit.events) == 1
    assert audit.events[0].event_type == "credit_policy.created"
    assert audit.events[0].tenant_id == "tenant_alpha"
    assert audit.events[0].actor_subject_id == "user_credit_manager"
    assert audit.events[0].policy_id == result.policy.policy_id
    assert audit.events[0].policy_version_id == result.policy.policy_version_id
    assert audit.events[0].safe_details == {
        "change_summary": "Criação inicial da política padrão",
        "product_type": "personal_credit",
        "status": "draft",
    }
    assert "payload" not in audit.events[0].safe_details
    assert result.logs[0]["payload"] == "[OMITIDO]"


def test_policy_queries_and_updates_reject_cross_tenant_without_revealing_policy() -> None:
    audit = RecordingAuditPublisher()
    repository = InMemoryCreditPolicyRepository()
    service = DecisionApplicationService(
        repository=repository,
        audit_publisher=audit,
        environment="test",
        clock=lambda: NOW,
    )
    created = service.create_policy_draft(
        _create_command(),
        context=_context("tenant_alpha"),
        trusted_context=_trusted_context(),
    )

    with pytest.raises(PolicyNotFoundError):
        service.get_policy(
            policy_id=created.policy.policy_id,
            policy_version_id=created.policy.policy_version_id,
            context=_context("tenant_beta"),
            trusted_context=_trusted_context(tenant_id="tenant_beta"),
        )

    with pytest.raises(PolicyNotFoundError):
        service.update_policy_draft(
            UpdateCreditPolicyDraftCommand(
                policy_id=created.policy.policy_id,
                policy_version_id=created.policy.policy_version_id,
                change_summary="Tentativa cross-tenant",
                rules=created.policy.rules,
                criteria=created.policy.criteria,
                limits=created.policy.limits,
                applicability=created.policy.applicability,
            ),
            context=_context("tenant_beta"),
            trusted_context=_trusted_context(tenant_id="tenant_beta"),
        )

    assert audit.events[-1].event_type == "credit_policy.rejected"
    assert audit.events[-1].safe_details["rejection_reason"] == "credit_policy_not_found"


def test_update_policy_draft_records_history_and_audit_intent() -> None:
    audit = RecordingAuditPublisher()
    service = DecisionApplicationService(
        repository=InMemoryCreditPolicyRepository(),
        audit_publisher=audit,
        environment="test",
        clock=lambda: NOW,
    )
    created = service.create_policy_draft(
        _create_command(),
        context=_context("tenant_alpha"),
        trusted_context=_trusted_context(),
    )

    updated = service.update_policy_draft(
        UpdateCreditPolicyDraftCommand(
            policy_id=created.policy.policy_id,
            policy_version_id=created.policy.policy_version_id,
            change_summary="Revisão da renda mínima",
            rules=(
                PolicyRule.create(
                    rule_id="rule_min_income",
                    name="Renda mínima revisada",
                    source_field="monthly_income_units",
                    operator="gte",
                    threshold_value=300_000,
                    outcome="approve",
                ),
            ),
            criteria=created.policy.criteria,
            limits=created.policy.limits,
            applicability=created.policy.applicability,
        ),
        context=_context("tenant_alpha"),
        trusted_context=_trusted_context(),
    )

    assert updated.policy.revision == 2
    assert updated.policy.changelog[-1].previous_revision == 1
    assert updated.policy.changelog[-1].resulting_revision == 2
    assert audit.events[-1].event_type == "credit_policy.updated"
    assert audit.events[-1].safe_details["revision"] == "2"


def test_create_policy_requires_matching_trusted_tenant_context() -> None:
    service = DecisionApplicationService(
        repository=InMemoryCreditPolicyRepository(),
        audit_publisher=RecordingAuditPublisher(),
        environment="test",
        clock=lambda: NOW,
    )

    with pytest.raises(PolicyTenantContextError, match="tenant confiável é obrigatório"):
        service.create_policy_draft(
            _create_command(),
            context=_context(None),
            trusted_context=_trusted_context(tenant_id="tenant_alpha"),
        )


def test_policy_operations_require_policy_write_scope_and_bridge_tier() -> None:
    audit = RecordingAuditPublisher()
    service = DecisionApplicationService(
        repository=InMemoryCreditPolicyRepository(),
        audit_publisher=audit,
        environment="test",
        clock=lambda: NOW,
    )

    with pytest.raises(PolicyTenantContextError, match="escopo obrigatório ausente"):
        service.create_policy_draft(
            _create_command(),
            context=_context("tenant_alpha"),
            trusted_context=_trusted_context(scopes=("policy:read",)),
        )

    with pytest.raises(PolicyTenantContextError, match="tier de tenant não suportado"):
        service.create_policy_draft(
            _create_command(),
            context=_context("tenant_alpha", tenant_isolation_tier="silo"),
            trusted_context=_trusted_context(tenant_isolation_tier="silo"),
        )

    assert audit.events[-1].event_type == "credit_policy.rejected"
    assert audit.events[-1].safe_details["operation"] == "credit_policy.create_draft"


def test_command_actor_is_ignored_in_favor_of_trusted_context_subject() -> None:
    audit = RecordingAuditPublisher()
    service = DecisionApplicationService(
        repository=InMemoryCreditPolicyRepository(),
        audit_publisher=audit,
        environment="test",
        clock=lambda: NOW,
    )

    result = service.create_policy_draft(
        _create_command(actor_subject_id="forged_actor"),
        context=_context("tenant_alpha"),
        trusted_context=_trusted_context(subject_id="real_actor"),
    )

    assert result.policy.changelog[0].actor_subject_id == "real_actor"
    assert audit.events[0].actor_subject_id == "real_actor"


def test_audit_failure_rolls_back_policy_creation_and_update() -> None:
    class FailingAuditPublisher:
        def publish(self, event: CreditPolicyAuditIntent) -> None:
            raise RuntimeError("audit unavailable")

    repository = InMemoryCreditPolicyRepository()
    service = DecisionApplicationService(
        repository=repository,
        audit_publisher=FailingAuditPublisher(),
        environment="test",
        clock=lambda: NOW,
    )

    with pytest.raises(RuntimeError, match="audit unavailable"):
        service.create_policy_draft(
            _create_command(),
            context=_context("tenant_alpha"),
            trusted_context=_trusted_context(),
        )

    assert (
        repository.get(
            tenant_id="tenant_alpha",
            policy_id="pol_personal_credit_default",
            policy_version_id="polver_personal_credit_default_v1",
        )
        is None
    )

    audit = RecordingAuditPublisher()
    service = DecisionApplicationService(
        repository=repository,
        audit_publisher=audit,
        environment="test",
        clock=lambda: NOW,
    )
    created = service.create_policy_draft(
        _create_command(),
        context=_context("tenant_alpha"),
        trusted_context=_trusted_context(),
    )
    service_with_failing_audit = DecisionApplicationService(
        repository=repository,
        audit_publisher=FailingAuditPublisher(),
        environment="test",
        clock=lambda: NOW,
    )

    with pytest.raises(RuntimeError, match="audit unavailable"):
        service_with_failing_audit.update_policy_draft(
            UpdateCreditPolicyDraftCommand(
                policy_id=created.policy.policy_id,
                policy_version_id=created.policy.policy_version_id,
                change_summary="Falha de auditoria",
                rules=created.policy.rules,
                criteria=created.policy.criteria,
                limits=created.policy.limits,
                applicability=created.policy.applicability,
            ),
            context=_context("tenant_alpha"),
            trusted_context=_trusted_context(),
        )

    persisted = repository.get(
        tenant_id="tenant_alpha",
        policy_id=created.policy.policy_id,
        policy_version_id=created.policy.policy_version_id,
    )
    assert persisted is not None
    assert persisted.revision == 1


def test_repository_rejects_stale_updates_with_expected_revision() -> None:
    repository = InMemoryCreditPolicyRepository()
    service = DecisionApplicationService(
        repository=repository,
        audit_publisher=RecordingAuditPublisher(),
        environment="test",
        clock=lambda: NOW,
    )
    created = service.create_policy_draft(
        _create_command(),
        context=_context("tenant_alpha"),
        trusted_context=_trusted_context(),
    )
    stale_update = created.policy.update_draft(
        rules=created.policy.rules,
        criteria=created.policy.criteria,
        limits=created.policy.limits,
        applicability=created.policy.applicability,
        now=NOW,
        actor_subject_id="user_credit_manager",
        correlation_id="corr_9234567890abcdef",
        change_summary="Atualização stale",
    )
    concurrent_update = created.policy.update_draft(
        rules=created.policy.rules,
        criteria=created.policy.criteria,
        limits=created.policy.limits,
        applicability=created.policy.applicability,
        now=NOW,
        actor_subject_id="user_credit_manager",
        correlation_id="corr_8234567890abcdef",
        change_summary="Atualização concorrente",
    )

    repository.update(concurrent_update, expected_revision=1)

    with pytest.raises(PolicyConcurrencyError, match="revisão concorrente"):
        repository.update(stale_update, expected_revision=1)


def _create_command(
    actor_subject_id: str = "user_credit_manager",
) -> CreateCreditPolicyDraftCommand:
    return CreateCreditPolicyDraftCommand(
        policy_id="pol_personal_credit_default",
        policy_version_id="polver_personal_credit_default_v1",
        owner_subject_id="user_credit_manager",
        product_type="personal_credit",
        actor_subject_id=actor_subject_id,
        change_summary="Criação inicial da política padrão",
        applicability=PolicyApplicability.create(channels=("api", "checkout")),
        rules=(
            PolicyRule.create(
                rule_id="rule_min_income",
                name="Renda mínima declarada",
                source_field="monthly_income_units",
                operator="gte",
                threshold_value=250_000,
                outcome="approve",
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
