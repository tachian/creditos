from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from creditos_decision.adapters.persistence import (
    InMemoryCreditPolicyRepository,
    InMemoryPolicySimulationRepository,
    InMemoryReasonCodeCatalogRepository,
)
from creditos_decision.application.ports import (
    CreditPolicyAuditIntent,
    CreditPolicyAuditPublisher,
    DecisionAuditIntent,
)
from creditos_decision.application.service import (
    CreateCreditPolicyDraftCommand,
    CreateCreditPolicyVersionCommand,
    DecisionApplicationService,
    GetPublishedCreditPolicyCommand,
    PublishCreditPolicyCommand,
    RunPolicySimulationCommand,
    UpdateCreditPolicyDraftCommand,
)
from creditos_decision.domain.entities import ReasonCodeCatalog
from creditos_decision.domain.errors import (
    PolicyImmutableError,
    PolicyNotFoundError,
    PolicyTenantContextError,
    PolicyValidationError,
)
from creditos_decision.domain.value_objects import (
    ExplainableFactor,
    PolicyApplicability,
    PolicyCriterion,
    PolicyLimit,
    PolicyRule,
    PolicySimulationInputCase,
    ReasonCode,
)
from creditos_observability.context import ObservabilityContext
from creditos_security import PropagatedContext, TrustedContext

NOW = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)


class RecordingAuditPublisher:
    def __init__(self) -> None:
        self.events: list[DecisionAuditIntent] = []

    def publish(self, event: DecisionAuditIntent) -> None:
        self.events.append(event)


def test_publish_policy_requires_published_catalog_simulation_and_publish_scope() -> None:
    audit = RecordingAuditPublisher()
    repository = InMemoryCreditPolicyRepository()
    simulation_repository = InMemoryPolicySimulationRepository()
    service = _service(
        repository=repository,
        catalog_repository=_published_catalog_repository(),
        simulation_repository=simulation_repository,
        audit=audit,
    )
    created = service.create_policy_draft(
        _create_policy_command(),
        context=_context("tenant_alpha"),
        trusted_context=_trusted_context(scopes=("policy:write", "policy:read")),
    )
    simulation = service.run_policy_simulation(
        RunPolicySimulationCommand(
            simulation_id="sim_policy_publication_ready",
            policy_id=created.policy.policy_id,
            policy_version_id=created.policy.policy_version_id,
            cases=(_safe_case(),),
        ),
        context=_context("tenant_alpha"),
        trusted_context=_trusted_context(scopes=("policy:write", "policy:read")),
    )

    result = service.publish_policy(
        PublishCreditPolicyCommand(
            policy_id=created.policy.policy_id,
            policy_version_id=created.policy.policy_version_id,
            simulation_id=simulation.simulation.simulation_id,
            change_summary="Publicação aprovada após simulação",
        ),
        context=_context("tenant_alpha"),
        trusted_context=_trusted_context(scopes=("policy:publish", "policy:read")),
    )

    assert result.policy.status == "published"
    assert result.policy.is_executable_in_production is True
    assert result.policy.applicability.starts_at == NOW + timedelta(days=1)
    assert result.logs[0]["payload"] == "[OMITIDO]"
    event = audit.events[-1]
    assert isinstance(event, CreditPolicyAuditIntent)
    assert event.event_type == "credit_policy.published"
    assert event.tenant_id == "tenant_alpha"
    assert event.actor_subject_id == "user_credit_manager"
    assert event.safe_details == {
        "change_summary": "Publicação aprovada após simulação",
        "effective_ends_at": (NOW + timedelta(days=31)).isoformat(),
        "effective_starts_at": (NOW + timedelta(days=1)).isoformat(),
        "operation": "credit_policy.publish",
        "product_type": "personal_credit",
        "revision": "2",
        "simulation_id": "sim_policy_publication_ready",
        "simulation_issue_count": "0",
        "status": "published",
    }


def test_publish_policy_blocks_draft_catalog_missing_or_problematic_simulation() -> None:
    service_with_draft_catalog = _service(
        catalog_repository=_draft_catalog_repository(),
        audit=RecordingAuditPublisher(),
    )
    created_with_draft_catalog = service_with_draft_catalog.create_policy_draft(
        _create_policy_command(),
        context=_context("tenant_alpha"),
        trusted_context=_trusted_context(scopes=("policy:write", "policy:read")),
    )
    simulation = service_with_draft_catalog.run_policy_simulation(
        RunPolicySimulationCommand(
            simulation_id="sim_policy_publication_draft_catalog",
            policy_id=created_with_draft_catalog.policy.policy_id,
            policy_version_id=created_with_draft_catalog.policy.policy_version_id,
            cases=(_safe_case(),),
        ),
        context=_context("tenant_alpha"),
        trusted_context=_trusted_context(scopes=("policy:write", "policy:read")),
    )

    with pytest.raises(PolicyValidationError, match="catálogo deve estar publicado"):
        service_with_draft_catalog.publish_policy(
            PublishCreditPolicyCommand(
                policy_id=created_with_draft_catalog.policy.policy_id,
                policy_version_id=created_with_draft_catalog.policy.policy_version_id,
                simulation_id=simulation.simulation.simulation_id,
                change_summary="Publicação com catálogo draft",
            ),
            context=_context("tenant_alpha"),
            trusted_context=_trusted_context(scopes=("policy:publish", "policy:read")),
        )

    service_without_simulation = _service(
        catalog_repository=_published_catalog_repository(),
        audit=RecordingAuditPublisher(),
    )
    created_without_simulation = service_without_simulation.create_policy_draft(
        _create_policy_command(policy_version_id="polver_personal_credit_default_v2"),
        context=_context("tenant_alpha"),
        trusted_context=_trusted_context(scopes=("policy:write", "policy:read")),
    )

    with pytest.raises(PolicyValidationError, match="simulação válida obrigatória"):
        service_without_simulation.publish_policy(
            PublishCreditPolicyCommand(
                policy_id=created_without_simulation.policy.policy_id,
                policy_version_id=created_without_simulation.policy.policy_version_id,
                simulation_id="sim_missing_publication_evidence",
                change_summary="Publicação sem simulação",
            ),
            context=_context("tenant_alpha"),
            trusted_context=_trusted_context(scopes=("policy:publish", "policy:read")),
        )

    service_with_issues = _service(
        catalog_repository=_published_catalog_repository(),
        audit=RecordingAuditPublisher(),
    )
    created_with_issues = service_with_issues.create_policy_draft(
        _create_policy_command(policy_version_id="polver_personal_credit_default_v3"),
        context=_context("tenant_alpha"),
        trusted_context=_trusted_context(scopes=("policy:write", "policy:read")),
    )
    problematic_simulation = service_with_issues.run_policy_simulation(
        RunPolicySimulationCommand(
            simulation_id="sim_policy_publication_with_issues",
            policy_id=created_with_issues.policy.policy_id,
            policy_version_id=created_with_issues.policy.policy_version_id,
            cases=(
                PolicySimulationInputCase.create(
                    case_id="case_missing_rule_data",
                    values={
                        "requested_amount_units": 700_000,
                        "requested_installments": 12,
                    },
                ),
            ),
        ),
        context=_context("tenant_alpha"),
        trusted_context=_trusted_context(scopes=("policy:write", "policy:read")),
    )

    with pytest.raises(PolicyValidationError, match="simulação válida obrigatória"):
        service_with_issues.publish_policy(
            PublishCreditPolicyCommand(
                policy_id=created_with_issues.policy.policy_id,
                policy_version_id=created_with_issues.policy.policy_version_id,
                simulation_id=problematic_simulation.simulation.simulation_id,
                change_summary="Publicação com issues",
            ),
            context=_context("tenant_alpha"),
            trusted_context=_trusted_context(scopes=("policy:publish", "policy:read")),
        )


def test_publish_policy_rejects_stale_simulation_after_draft_update() -> None:
    repository = InMemoryCreditPolicyRepository()
    service = _service(
        repository=repository,
        catalog_repository=_published_catalog_repository(),
        audit=RecordingAuditPublisher(),
    )
    created = service.create_policy_draft(
        _create_policy_command(),
        context=_context("tenant_alpha"),
        trusted_context=_trusted_context(scopes=("policy:write", "policy:read")),
    )
    simulation = service.run_policy_simulation(
        RunPolicySimulationCommand(
            simulation_id="sim_policy_publication_before_update",
            policy_id=created.policy.policy_id,
            policy_version_id=created.policy.policy_version_id,
            cases=(_safe_case(),),
        ),
        context=_context("tenant_alpha"),
        trusted_context=_trusted_context(scopes=("policy:write", "policy:read")),
    )

    service.update_policy_draft(
        _update_same_version_command(created.policy.policy_version_id),
        context=_context("tenant_alpha"),
        trusted_context=_trusted_context(scopes=("policy:write", "policy:read")),
    )

    with pytest.raises(PolicyValidationError, match="simulação válida obrigatória"):
        service.publish_policy(
            PublishCreditPolicyCommand(
                policy_id=created.policy.policy_id,
                policy_version_id=created.policy.policy_version_id,
                simulation_id=simulation.simulation.simulation_id,
                change_summary="Publicação com simulação obsoleta",
            ),
            context=_context("tenant_alpha"),
            trusted_context=_trusted_context(scopes=("policy:publish", "policy:read")),
        )


def test_publish_policy_rejects_overlapping_effective_windows_and_supports_lookup() -> None:
    repository = InMemoryCreditPolicyRepository()
    simulation_repository = InMemoryPolicySimulationRepository()
    audit = RecordingAuditPublisher()
    service = _service(
        repository=repository,
        simulation_repository=simulation_repository,
        catalog_repository=_published_catalog_repository(),
        audit=audit,
    )
    first = _create_and_simulate(
        service,
        policy_version_id="polver_personal_credit_default_v1",
        simulation_id="sim_policy_publication_v1",
        starts_at=NOW + timedelta(days=1),
        ends_at=NOW + timedelta(days=31),
    )
    service.publish_policy(
        PublishCreditPolicyCommand(
            policy_id=first.policy.policy_id,
            policy_version_id=first.policy.policy_version_id,
            simulation_id="sim_policy_publication_v1",
            change_summary="Publicação v1",
        ),
        context=_context("tenant_alpha"),
        trusted_context=_trusted_context(scopes=("policy:publish", "policy:read")),
    )
    second = _create_and_simulate(
        service,
        policy_version_id="polver_personal_credit_default_v2",
        simulation_id="sim_policy_publication_v2",
        starts_at=NOW + timedelta(days=15),
        ends_at=NOW + timedelta(days=45),
    )

    with pytest.raises(PolicyValidationError, match="vigência conflitante"):
        service.publish_policy(
            PublishCreditPolicyCommand(
                policy_id=second.policy.policy_id,
                policy_version_id=second.policy.policy_version_id,
                simulation_id="sim_policy_publication_v2",
                change_summary="Publicação conflitante",
            ),
            context=_context("tenant_alpha"),
            trusted_context=_trusted_context(scopes=("policy:publish", "policy:read")),
        )
    rejection_event = audit.events[-1]
    assert isinstance(rejection_event, CreditPolicyAuditIntent)
    assert rejection_event.event_type == "credit_policy.rejected"
    assert rejection_event.safe_details["simulation_id"] == "sim_policy_publication_v2"
    assert rejection_event.safe_details["simulation_issue_count"] == "0"
    assert (
        rejection_event.safe_details["effective_starts_at"]
        == (NOW + timedelta(days=15)).isoformat()
    )

    published = service.get_published_policy(
        GetPublishedCreditPolicyCommand(
            product_type="personal_credit",
            channel="api",
            effective_at=NOW + timedelta(days=2),
        ),
        context=_context("tenant_alpha"),
        trusted_context=_trusted_context(scopes=("policy:read",)),
    )

    assert published.policy_version_id == first.policy.policy_version_id

    with pytest.raises(PolicyNotFoundError):
        service.get_published_policy(
            GetPublishedCreditPolicyCommand(
                product_type="personal_credit",
                channel="api",
                effective_at=NOW + timedelta(days=90),
            ),
            context=_context("tenant_alpha"),
            trusted_context=_trusted_context(scopes=("policy:read",)),
        )


def test_publish_policy_rejects_overlap_when_policy_version_id_is_reused() -> None:
    repository = InMemoryCreditPolicyRepository()
    service = _service(
        repository=repository,
        simulation_repository=InMemoryPolicySimulationRepository(),
        catalog_repository=_published_catalog_repository(),
        audit=RecordingAuditPublisher(),
    )
    first = _create_and_simulate(
        service,
        policy_id="pol_personal_credit_default",
        policy_version_id="polver_personal_credit_shared_v1",
        simulation_id="sim_policy_publication_shared_v1",
        starts_at=NOW + timedelta(days=1),
        ends_at=NOW + timedelta(days=31),
    )
    service.publish_policy(
        PublishCreditPolicyCommand(
            policy_id=first.policy.policy_id,
            policy_version_id=first.policy.policy_version_id,
            simulation_id="sim_policy_publication_shared_v1",
            change_summary="Publicação política principal",
        ),
        context=_context("tenant_alpha"),
        trusted_context=_trusted_context(scopes=("policy:publish", "policy:read")),
    )
    second = _create_and_simulate(
        service,
        policy_id="pol_personal_credit_alternative",
        policy_version_id="polver_personal_credit_shared_v1",
        simulation_id="sim_policy_publication_shared_v2",
        starts_at=NOW + timedelta(days=15),
        ends_at=NOW + timedelta(days=45),
    )

    with pytest.raises(PolicyValidationError, match="vigência conflitante"):
        service.publish_policy(
            PublishCreditPolicyCommand(
                policy_id=second.policy.policy_id,
                policy_version_id=second.policy.policy_version_id,
                simulation_id="sim_policy_publication_shared_v2",
                change_summary="Publicação com version id reutilizado",
            ),
            context=_context("tenant_alpha"),
            trusted_context=_trusted_context(scopes=("policy:publish", "policy:read")),
        )


def test_create_policy_version_from_published_policy_and_keep_original_immutable() -> None:
    repository = InMemoryCreditPolicyRepository()
    audit = RecordingAuditPublisher()
    service = _service(
        repository=repository,
        catalog_repository=_published_catalog_repository(),
        audit=audit,
    )
    created = _create_and_simulate(
        service,
        policy_version_id="polver_personal_credit_default_v1",
        simulation_id="sim_policy_publication_original",
        starts_at=NOW + timedelta(days=1),
        ends_at=NOW + timedelta(days=31),
    )
    published = service.publish_policy(
        PublishCreditPolicyCommand(
            policy_id=created.policy.policy_id,
            policy_version_id=created.policy.policy_version_id,
            simulation_id="sim_policy_publication_original",
            change_summary="Publicação original",
        ),
        context=_context("tenant_alpha"),
        trusted_context=_trusted_context(scopes=("policy:publish", "policy:read")),
    )

    next_version = service.create_policy_version(
        CreateCreditPolicyVersionCommand(
            policy_id=published.policy.policy_id,
            current_policy_version_id=published.policy.policy_version_id,
            new_policy_version_id="polver_personal_credit_default_v2",
            change_summary="Nova versão para ajuste governado",
            rules=(
                PolicyRule.create(
                    rule_id="rule_revised_income",
                    name="Renda revisada",
                    source_field="monthly_income_units",
                    operator="gte",
                    threshold_value=300_000,
                    outcome="approve",
                    reason_code_refs=("rc_min_income",),
                ),
            ),
            criteria=published.policy.criteria,
            limits=published.policy.limits,
            applicability=PolicyApplicability.create(
                channels=("api",),
                starts_at=NOW + timedelta(days=40),
            ),
            reason_code_catalog_id=published.policy.reason_code_catalog_id,
            reason_code_catalog_version_id=published.policy.reason_code_catalog_version_id,
        ),
        context=_context("tenant_alpha"),
        trusted_context=_trusted_context(scopes=("policy:publish", "policy:read")),
    )

    assert next_version.policy.status == "draft"
    assert next_version.policy.version == 2
    assert next_version.policy.policy_version_id == "polver_personal_credit_default_v2"
    assert next_version.policy.changelog[0].change_type == "versioned"
    versioned_event = audit.events[-1]
    assert isinstance(versioned_event, CreditPolicyAuditIntent)
    assert (
        versioned_event.safe_details["effective_starts_at"]
        == (NOW + timedelta(days=40)).isoformat()
    )
    assert versioned_event.safe_details["effective_ends_at"] == ""
    assert (
        repository.get(
            tenant_id="tenant_alpha",
            policy_id=published.policy.policy_id,
            policy_version_id=published.policy.policy_version_id,
        )
        == published.policy
    )

    with pytest.raises(PolicyImmutableError):
        service.update_policy_draft(
            _update_same_version_command(published.policy.policy_version_id),
            context=_context("tenant_alpha"),
            trusted_context=_trusted_context(scopes=("policy:write", "policy:read")),
        )


def test_publication_requires_publish_scope_and_rolls_back_when_audit_fails() -> None:
    class FailingPublicationAuditPublisher:
        def publish(self, event: DecisionAuditIntent) -> None:
            if (
                isinstance(event, CreditPolicyAuditIntent)
                and event.event_type == "credit_policy.published"
            ):
                raise RuntimeError("audit unavailable")

    repository = InMemoryCreditPolicyRepository()
    simulation_repository = InMemoryPolicySimulationRepository()
    service = _service(
        repository=repository,
        catalog_repository=_published_catalog_repository(),
        simulation_repository=simulation_repository,
        audit=RecordingAuditPublisher(),
    )
    created = _create_and_simulate(
        service,
        policy_version_id="polver_personal_credit_default_v1",
        simulation_id="sim_policy_publication_rollback",
        starts_at=NOW + timedelta(days=1),
        ends_at=NOW + timedelta(days=31),
    )

    with pytest.raises(PolicyTenantContextError, match="escopo obrigatório ausente"):
        service.publish_policy(
            PublishCreditPolicyCommand(
                policy_id=created.policy.policy_id,
                policy_version_id=created.policy.policy_version_id,
                simulation_id="sim_policy_publication_rollback",
                change_summary="Publicação sem scope",
            ),
            context=_context("tenant_alpha"),
            trusted_context=_trusted_context(scopes=("policy:write", "policy:read")),
        )

    failing_service = _service(
        repository=repository,
        catalog_repository=_published_catalog_repository(),
        simulation_repository=simulation_repository,
        audit=FailingPublicationAuditPublisher(),
    )

    with pytest.raises(RuntimeError, match="audit unavailable"):
        failing_service.publish_policy(
            PublishCreditPolicyCommand(
                policy_id=created.policy.policy_id,
                policy_version_id=created.policy.policy_version_id,
                simulation_id="sim_policy_publication_rollback",
                change_summary="Publicação com auditoria indisponível",
            ),
            context=_context("tenant_alpha"),
            trusted_context=_trusted_context(scopes=("policy:publish", "policy:read")),
        )

    restored = repository.get(
        tenant_id="tenant_alpha",
        policy_id=created.policy.policy_id,
        policy_version_id=created.policy.policy_version_id,
    )
    assert restored == created.policy
    assert restored is not None
    assert restored.status == "draft"


def test_publication_and_versioning_are_invisible_until_audit_commit() -> None:
    class VisibilityAuditPublisher(RecordingAuditPublisher):
        def __init__(self, repository: InMemoryCreditPolicyRepository) -> None:
            super().__init__()
            self._repository = repository
            self.published_visible_during_audit = False
            self.version_visible_during_audit = False

        def publish(self, event: DecisionAuditIntent) -> None:
            super().publish(event)
            if (
                isinstance(event, CreditPolicyAuditIntent)
                and event.event_type == "credit_policy.published"
            ):
                self.published_visible_during_audit = bool(
                    self._repository.list_published_by_product(
                        tenant_id=event.tenant_id,
                        product_type="personal_credit",
                    )
                )
            if (
                isinstance(event, CreditPolicyAuditIntent)
                and event.event_type == "credit_policy.versioned"
            ):
                self.version_visible_during_audit = (
                    self._repository.get(
                        tenant_id=event.tenant_id,
                        policy_id=event.policy_id,
                        policy_version_id=event.policy_version_id,
                    )
                    is not None
                )

    repository = InMemoryCreditPolicyRepository()
    audit = VisibilityAuditPublisher(repository)
    service = _service(
        repository=repository,
        catalog_repository=_published_catalog_repository(),
        audit=audit,
    )
    created = _create_and_simulate(
        service,
        policy_version_id="polver_personal_credit_default_v1",
        simulation_id="sim_policy_publication_visibility",
        starts_at=NOW + timedelta(days=1),
        ends_at=NOW + timedelta(days=31),
    )
    published = service.publish_policy(
        PublishCreditPolicyCommand(
            policy_id=created.policy.policy_id,
            policy_version_id=created.policy.policy_version_id,
            simulation_id="sim_policy_publication_visibility",
            change_summary="Publicação auditada antes do commit",
        ),
        context=_context("tenant_alpha"),
        trusted_context=_trusted_context(scopes=("policy:publish", "policy:read")),
    )

    service.create_policy_version(
        CreateCreditPolicyVersionCommand(
            policy_id=published.policy.policy_id,
            current_policy_version_id=published.policy.policy_version_id,
            new_policy_version_id="polver_personal_credit_default_v2",
            change_summary="Nova versão invisível até auditoria",
            rules=published.policy.rules,
            criteria=published.policy.criteria,
            limits=published.policy.limits,
            applicability=PolicyApplicability.create(
                channels=("api",),
                starts_at=NOW + timedelta(days=40),
            ),
            reason_code_catalog_id=published.policy.reason_code_catalog_id,
            reason_code_catalog_version_id=published.policy.reason_code_catalog_version_id,
        ),
        context=_context("tenant_alpha"),
        trusted_context=_trusted_context(scopes=("policy:publish", "policy:read")),
    )

    assert audit.published_visible_during_audit is False
    assert audit.version_visible_during_audit is False


def _service(
    *,
    audit: CreditPolicyAuditPublisher,
    repository: InMemoryCreditPolicyRepository | None = None,
    catalog_repository: InMemoryReasonCodeCatalogRepository | None = None,
    simulation_repository: InMemoryPolicySimulationRepository | None = None,
) -> DecisionApplicationService:
    return DecisionApplicationService(
        repository=repository or InMemoryCreditPolicyRepository(),
        reason_code_catalog_repository=catalog_repository or _published_catalog_repository(),
        policy_simulation_repository=simulation_repository or InMemoryPolicySimulationRepository(),
        audit_publisher=audit,
        environment="test",
        clock=lambda: NOW,
    )


def _create_and_simulate(
    service: DecisionApplicationService,
    *,
    policy_id: str = "pol_personal_credit_default",
    policy_version_id: str,
    simulation_id: str,
    starts_at: datetime,
    ends_at: datetime | None,
):
    created = service.create_policy_draft(
        _create_policy_command(
            policy_id=policy_id,
            policy_version_id=policy_version_id,
            applicability=PolicyApplicability.create(
                channels=("api",),
                starts_at=starts_at,
                ends_at=ends_at,
            ),
        ),
        context=_context("tenant_alpha"),
        trusted_context=_trusted_context(scopes=("policy:write", "policy:read")),
    )
    service.run_policy_simulation(
        RunPolicySimulationCommand(
            simulation_id=simulation_id,
            policy_id=created.policy.policy_id,
            policy_version_id=created.policy.policy_version_id,
            cases=(_safe_case(),),
        ),
        context=_context("tenant_alpha"),
        trusted_context=_trusted_context(scopes=("policy:write", "policy:read")),
    )
    return created


def _safe_case() -> PolicySimulationInputCase:
    return PolicySimulationInputCase.create(
        case_id="case_income_001",
        values={
            "monthly_income_units": 300_000,
            "requested_amount_units": 700_000,
            "requested_installments": 12,
        },
    )


def _create_policy_command(
    *,
    policy_id: str = "pol_personal_credit_default",
    policy_version_id: str = "polver_personal_credit_default_v1",
    applicability: PolicyApplicability | None = None,
) -> CreateCreditPolicyDraftCommand:
    return CreateCreditPolicyDraftCommand(
        policy_id=policy_id,
        policy_version_id=policy_version_id,
        reason_code_catalog_id="rcc_personal_credit_default",
        reason_code_catalog_version_id="rccver_personal_credit_default_v1",
        owner_subject_id="user_credit_manager",
        product_type="personal_credit",
        actor_subject_id="user_credit_manager",
        change_summary="Criação inicial da política padrão",
        applicability=applicability
        or PolicyApplicability.create(
            channels=("api", "checkout"),
            starts_at=NOW + timedelta(days=1),
            ends_at=NOW + timedelta(days=31),
        ),
        rules=(
            PolicyRule.create(
                rule_id="rule_min_income",
                name="Renda mínima declarada",
                source_field="monthly_income_units",
                operator="gte",
                threshold_value=250_000,
                outcome="approve",
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


def _update_same_version_command(policy_version_id: str) -> UpdateCreditPolicyDraftCommand:
    return UpdateCreditPolicyDraftCommand(
        policy_id="pol_personal_credit_default",
        policy_version_id=policy_version_id,
        reason_code_catalog_id="rcc_personal_credit_default",
        reason_code_catalog_version_id="rccver_personal_credit_default_v1",
        owner_subject_id="user_credit_manager",
        product_type="personal_credit",
        change_summary="Tentativa de alterar publicada",
        applicability=PolicyApplicability.create(channels=("api",), starts_at=NOW),
        rules=(
            PolicyRule.create(
                rule_id="rule_min_income",
                name="Renda mínima declarada",
                source_field="monthly_income_units",
                operator="gte",
                threshold_value=300_000,
                outcome="approve",
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


def _published_catalog_repository() -> InMemoryReasonCodeCatalogRepository:
    repository = _draft_catalog_repository()
    draft = repository.get(
        tenant_id="tenant_alpha",
        catalog_id="rcc_personal_credit_default",
        catalog_version_id="rccver_personal_credit_default_v1",
    )
    assert draft is not None
    repository.update(
        draft.publish(
            now=NOW,
            actor_subject_id="user_credit_manager",
            correlation_id="corr_1234567890abcdef",
            change_summary="Publicação do catálogo",
        ),
        expected_revision=draft.revision,
    )
    return repository


def _draft_catalog_repository() -> InMemoryReasonCodeCatalogRepository:
    repository = InMemoryReasonCodeCatalogRepository()
    repository.save_with_next_version(
        ReasonCodeCatalog.create_draft(
            catalog_id="rcc_personal_credit_default",
            catalog_version_id="rccver_personal_credit_default_v1",
            tenant_id="tenant_alpha",
            owner_subject_id="user_credit_manager",
            product_type="personal_credit",
            reason_codes=(
                ReasonCode.create(
                    reason_code_id="reason_min_income",
                    code="rc_min_income",
                    outcome="approve",
                    title="Renda mínima",
                    internal_description="Renda declarada atende a política",
                    external_description="Renda declarada compatível com aprovação",
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
            now=NOW,
            actor_subject_id="user_credit_manager",
            correlation_id="corr_1234567890abcdef",
            change_summary="Criação inicial do catálogo",
        )
    )
    return repository


def _context(tenant_id: str | None) -> ObservabilityContext:
    return ObservabilityContext.new(
        correlation_id="corr_1234567890abcdef",
        request_id="req_1234567890abcdef",
        trace_id="1234567890abcdef1234567890abcdef",
        tenant_id=tenant_id,
        tenant_isolation_tier="bridge",
    )


def _trusted_context(
    *,
    tenant_id: str = "tenant_alpha",
    subject_id: str = "user_credit_manager",
    scopes: tuple[str, ...] = ("policy:write", "policy:read", "policy:publish"),
) -> PropagatedContext:
    return PropagatedContext(
        trusted=TrustedContext(
            tenant_id=tenant_id,
            tenant_isolation_tier="bridge",
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
