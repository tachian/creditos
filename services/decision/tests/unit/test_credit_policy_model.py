from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from creditos_decision.domain.entities import CreditPolicy
from creditos_decision.domain.errors import PolicyImmutableError, PolicyValidationError
from creditos_decision.domain.value_objects import (
    PolicyApplicability,
    PolicyChangelogEntry,
    PolicyCriterion,
    PolicyFallbackAction,
    PolicyLimit,
    PolicyRule,
)

NOW = datetime(2026, 8, 26, 12, 0, tzinfo=UTC)


def test_create_draft_policy_with_versioning_and_initial_changelog() -> None:
    policy = CreditPolicy.create_draft(
        policy_id="pol_personal_credit_default",
        policy_version_id="polver_personal_credit_default_v1",
        tenant_id="tenant_alpha",
        owner_subject_id="user_credit_manager",
        product_type="personal_credit",
        reason_code_catalog_id="rcc_personal_credit_default",
        reason_code_catalog_version_id="rccver_personal_credit_default_v1",
        applicability=PolicyApplicability.create(channels=("api", "checkout")),
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
        now=NOW,
        actor_subject_id="user_credit_manager",
        correlation_id="corr_1234567890abcdef",
        change_summary="Criação inicial da política padrão",
    )

    assert policy.status == "draft"
    assert policy.version == 1
    assert policy.revision == 1
    assert policy.product_type == "personal_credit"
    assert policy.is_executable_in_production is False
    assert policy.changelog[0].change_type == "created"
    assert policy.changelog[0].previous_revision is None
    assert policy.changelog[0].resulting_revision == 1


def test_update_draft_policy_preserves_history_and_does_not_mutate_original() -> None:
    original = _draft_policy()

    updated = original.update_draft(
        rules=(
            PolicyRule.create(
                rule_id="rule_min_income",
                name="Renda mínima revisada",
                source_field="monthly_income_units",
                operator="gte",
                threshold_value=300_000,
                outcome="approve",
                reason_code_refs=("rc_min_income",),
            ),
        ),
        criteria=original.criteria,
        limits=original.limits,
        applicability=original.applicability,
        now=NOW.replace(hour=13),
        actor_subject_id="user_credit_manager",
        correlation_id="corr_2234567890abcdef",
        change_summary="Revisão da renda mínima",
        reason_code_catalog_id="rcc_personal_credit_default",
        reason_code_catalog_version_id="rccver_personal_credit_default_v1",
    )

    assert original.revision == 1
    assert len(original.changelog) == 1
    assert updated.revision == 2
    assert len(updated.changelog) == 2
    assert updated.changelog[-1].change_type == "updated"
    assert updated.changelog[-1].previous_revision == 1
    assert updated.changelog[-1].resulting_revision == 2
    assert updated.rules[0].threshold_value == 300_000


def test_published_policy_snapshot_is_immutable() -> None:
    published = CreditPolicy.restore(
        policy_id="pol_personal_credit_default",
        policy_version_id="polver_personal_credit_default_v1",
        tenant_id="tenant_alpha",
        owner_subject_id="user_credit_manager",
        product_type="personal_credit",
        reason_code_catalog_id="rcc_personal_credit_default",
        reason_code_catalog_version_id="rccver_personal_credit_default_v1",
        status="published",
        version=1,
        revision=3,
        applicability=PolicyApplicability.create(channels=("api",)),
        rules=(_rule(),),
        criteria=(_criterion(),),
        limits=(_limit(),),
        changelog=_changelog(3),
        created_at=NOW,
        updated_at=NOW,
    )

    with pytest.raises(PolicyImmutableError, match="política não pode ser alterada"):
        published.update_draft(
            rules=published.rules,
            criteria=published.criteria,
            limits=published.limits,
            applicability=published.applicability,
            now=NOW.replace(hour=14),
            actor_subject_id="user_credit_manager",
            correlation_id="corr_3234567890abcdef",
            change_summary="Tentativa de alteração em publicada",
            reason_code_catalog_id="rcc_personal_credit_default",
            reason_code_catalog_version_id="rccver_personal_credit_default_v1",
        )
    with pytest.raises(PolicyImmutableError, match="política não pode ser alterada"):
        replace(
            published,
            rules=(
                PolicyRule.create(
                    rule_id="rule_requested_amount",
                    name="Valor máximo solicitado",
                    source_field="requested_amount_units",
                    operator="lte",
                    threshold_value=500_000,
                    outcome="approve",
                    reason_code_refs=("rc_min_income",),
                ),
            ),
        )


def test_policy_fallback_action_is_governed_and_fingerprinted() -> None:
    request_more_data = PolicyFallbackAction.create(action="request_more_data")
    unable_to_decide = PolicyFallbackAction.create(action="unable_to_decide")

    assert request_more_data.action == "request_more_data"
    assert unable_to_decide.action == "unable_to_decide"

    default_policy = _draft_policy()
    explicit_same_policy = _draft_policy(fallback_action=request_more_data)
    unable_policy = _draft_policy(fallback_action=unable_to_decide)

    assert default_policy.fallback_action == request_more_data
    assert explicit_same_policy._governed_fingerprint == default_policy._governed_fingerprint
    assert unable_policy._governed_fingerprint != default_policy._governed_fingerprint


@pytest.mark.parametrize(
    "fallback_action",
    [
        "manual_review",
        "human_override",
        "manual_queue",
        "request_additional_data",
    ],
)
def test_policy_fallback_rejects_manual_review_override_and_aliases(
    fallback_action: str,
) -> None:
    with pytest.raises(PolicyValidationError, match="IA apenas consultiva"):
        PolicyFallbackAction.create(action=fallback_action)


def test_policy_fallback_rejects_reason_codes_for_non_reject_actions() -> None:
    with pytest.raises(PolicyValidationError) as error:
        PolicyFallbackAction.create(
            action="request_more_data",
            reason_code_refs=("rc_request_more_data",),
        )

    assert error.value.code == "unsupported_fallback_reason_code_ref"


def test_policy_model_rejects_unsupported_product_and_sensitive_or_arbitrary_fields() -> None:
    with pytest.raises(PolicyValidationError, match="produto não suportado"):
        CreditPolicy.create_draft(
            policy_id="pol_invalid",
            policy_version_id="polver_invalid_v1",
            tenant_id="tenant_alpha",
            owner_subject_id="user_credit_manager",
            product_type="mortgage",
            reason_code_catalog_id="rcc_personal_credit_default",
            reason_code_catalog_version_id="rccver_personal_credit_default_v1",
            applicability=PolicyApplicability.create(channels=("api",)),
            rules=(_rule(),),
            criteria=(_criterion(),),
            limits=(_limit(),),
            now=NOW,
            actor_subject_id="user_credit_manager",
            correlation_id="corr_4234567890abcdef",
            change_summary="Produto fora do MVP",
        )

    with pytest.raises(PolicyValidationError, match="dado sensível ou campo proibido"):
        PolicyRule.create(
            rule_id="rule_raw_payload",
            name="Regra com campo proibido",
            source_field="raw_payload",
            operator="exists",
            threshold_value=True,
            outcome="reject",
            reason_code_refs=("rc_min_income",),
        )

    with pytest.raises(PolicyValidationError, match="dado sensível ou campo proibido"):
        PolicyCriterion.create(
            criterion_id="criterion_email",
            field="email",
            operator="exists",
            value="cliente@example.com",
        )

    with pytest.raises(PolicyValidationError, match="dado sensível ou campo proibido"):
        PolicyChangelogEntry.create(
            change_type="created",
            actor_subject_id="user_credit_manager",
            changed_at=NOW,
            change_summary="Endereço Rua das Flores 123",
            correlation_id="corr_6234567890abcdef",
            previous_revision=None,
            resulting_revision=1,
        )


def test_policy_model_rejects_unknown_fields_formatted_documents_and_pt_br_aliases() -> None:
    with pytest.raises(PolicyValidationError, match="campo de política não governado"):
        PolicyRule.create(
            rule_id="rule_unknown",
            name="Campo desconhecido",
            source_field="unknown_field",
            operator="gte",
            threshold_value=1,
            outcome="approve",
            reason_code_refs=("rc_min_income",),
        )

    with pytest.raises(PolicyValidationError, match="dado sensível ou campo proibido"):
        PolicyRule.create(
            rule_id="rule_nome",
            name="Campo sensível",
            source_field="nome_cliente",
            operator="exists",
            threshold_value=True,
            outcome="reject",
            reason_code_refs=("rc_min_income",),
        )

    with pytest.raises(PolicyValidationError, match="dado sensível ou campo proibido"):
        PolicyCriterion.create(
            criterion_id="criterion_documento",
            field="requested_amount_units",
            operator="eq",
            value="123.456.789-10",
        )


def test_policy_model_rejects_direct_construction_and_inconsistent_changelog_chain() -> None:
    with pytest.raises(PolicyValidationError, match="dado sensível ou campo proibido"):
        PolicyRule(
            rule_id="rule_bypass",
            name="Bypass",
            source_field="raw_payload",
            operator="exists",
            threshold_value=True,
            outcome="reject",
            reason_code_refs=(),
        )

    with pytest.raises(PolicyValidationError, match="changelog inconsistente"):
        CreditPolicy.restore(
            policy_id="pol_personal_credit_default",
            policy_version_id="polver_personal_credit_default_v1",
            tenant_id="tenant_alpha",
            owner_subject_id="user_credit_manager",
            product_type="personal_credit",
            reason_code_catalog_id="rcc_personal_credit_default",
            reason_code_catalog_version_id="rccver_personal_credit_default_v1",
            status="draft",
            version=1,
            revision=3,
            applicability=PolicyApplicability.create(channels=("api",)),
            rules=(_rule(),),
            criteria=(_criterion(),),
            limits=(_limit(),),
            changelog=_draft_policy().changelog,
            created_at=NOW,
            updated_at=NOW,
        )


def test_operator_value_semantics_and_applicability_dates_are_validated() -> None:
    with pytest.raises(PolicyValidationError, match="valor incompatível com operador"):
        PolicyRule.create(
            rule_id="rule_bad_gte",
            name="Operador inválido",
            source_field="monthly_income_units",
            operator="gte",
            threshold_value="alto",
            outcome="approve",
            reason_code_refs=("rc_min_income",),
        )

    with pytest.raises(PolicyValidationError, match="valor incompatível com operador"):
        PolicyCriterion.create(
            criterion_id="criterion_bad_exists",
            field="requested_amount_units",
            operator="exists",
            value=1_000,
        )

    with pytest.raises(PolicyValidationError, match="valor incompatível com operador"):
        PolicyCriterion.create(
            criterion_id="criterion_bad_eq",
            field="age_years",
            operator="eq",
            value="adult",
        )

    with pytest.raises(PolicyValidationError, match="timezone"):
        PolicyApplicability.create(
            channels=("api",),
            starts_at=datetime(2026, 8, 26, 12, 0),
            ends_at=NOW + timedelta(days=1),
        )

    with pytest.raises(PolicyValidationError, match="janela de vigência inválida"):
        PolicyApplicability.create(
            channels=("api",),
            starts_at=NOW + timedelta(days=1),
            ends_at=NOW,
        )


def _draft_policy(
    *,
    fallback_action: PolicyFallbackAction | None = None,
) -> CreditPolicy:
    return CreditPolicy.create_draft(
        policy_id="pol_personal_credit_default",
        policy_version_id="polver_personal_credit_default_v1",
        tenant_id="tenant_alpha",
        owner_subject_id="user_credit_manager",
        product_type="personal_credit",
        reason_code_catalog_id="rcc_personal_credit_default",
        reason_code_catalog_version_id="rccver_personal_credit_default_v1",
        applicability=PolicyApplicability.create(channels=("api",)),
        rules=(_rule(),),
        criteria=(_criterion(),),
        limits=(_limit(),),
        fallback_action=fallback_action,
        now=NOW,
        actor_subject_id="user_credit_manager",
        correlation_id="corr_1234567890abcdef",
        change_summary="Criação inicial",
    )


def _changelog(revision: int) -> tuple[PolicyChangelogEntry, ...]:
    entries = [
        PolicyChangelogEntry.create(
            change_type="created",
            actor_subject_id="user_credit_manager",
            changed_at=NOW,
            change_summary="Criação inicial",
            correlation_id="corr_1234567890abcdef",
            previous_revision=None,
            resulting_revision=1,
        )
    ]
    for current_revision in range(2, revision + 1):
        entries.append(
            PolicyChangelogEntry.create(
                change_type="updated",
                actor_subject_id="user_credit_manager",
                changed_at=NOW + timedelta(minutes=current_revision),
                change_summary="Revisão controlada",
                correlation_id=f"corr_{current_revision}234567890abcdef",
                previous_revision=current_revision - 1,
                resulting_revision=current_revision,
            )
        )
    return tuple(entries)


def _rule() -> PolicyRule:
    return PolicyRule.create(
        rule_id="rule_min_income",
        name="Renda mínima declarada",
        source_field="monthly_income_units",
        operator="gte",
        threshold_value=250_000,
        outcome="approve",
        reason_code_refs=("rc_min_income",),
    )


def _criterion() -> PolicyCriterion:
    return PolicyCriterion.create(
        criterion_id="criterion_requested_amount",
        field="requested_amount_units",
        operator="lte",
        value=1_000_000,
    )


def _limit() -> PolicyLimit:
    return PolicyLimit.create(
        limit_id="limit_max_installments",
        limit_type="max_installments",
        value=24,
    )
