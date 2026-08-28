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
    PolicyLimit,
    PolicyRule,
)

NOW = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)


def test_publish_draft_policy_requires_effective_window_and_creates_immutable_snapshot() -> None:
    draft = _draft_policy(
        applicability=PolicyApplicability.create(
            channels=("api", "checkout"),
            starts_at=NOW + timedelta(days=1),
            ends_at=NOW + timedelta(days=31),
        )
    )

    published = draft.publish(
        now=NOW,
        actor_subject_id="user_credit_manager",
        correlation_id="corr_1234567890abcdef",
        change_summary="Publicação aprovada após simulação",
    )

    assert published.status == "published"
    assert published.is_executable_in_production is True
    assert published.policy_id == draft.policy_id
    assert published.policy_version_id == draft.policy_version_id
    assert published.version == draft.version
    assert published.revision == draft.revision + 1
    assert published.changelog[-1].change_type == "published"
    assert published.changelog[-1].previous_revision == draft.revision
    assert published.changelog[-1].resulting_revision == published.revision

    with pytest.raises(PolicyImmutableError):
        published.update_draft(
            rules=published.rules,
            criteria=published.criteria,
            limits=published.limits,
            applicability=published.applicability,
            now=NOW + timedelta(hours=1),
            actor_subject_id="user_credit_manager",
            correlation_id="corr_2234567890abcdef",
            change_summary="Tentativa de alteração",
            reason_code_catalog_id=published.reason_code_catalog_id,
            reason_code_catalog_version_id=published.reason_code_catalog_version_id,
        )
    with pytest.raises(PolicyImmutableError):
        replace(published, owner_subject_id="user_other_manager")


def test_publish_policy_rejects_missing_effective_start_and_non_draft_status() -> None:
    draft_without_start = _draft_policy(applicability=PolicyApplicability.create(channels=("api",)))

    with pytest.raises(PolicyValidationError, match="vigência inicial obrigatória"):
        draft_without_start.publish(
            now=NOW,
            actor_subject_id="user_credit_manager",
            correlation_id="corr_1234567890abcdef",
            change_summary="Publicação sem vigência",
        )

    expired_draft = _draft_policy(
        applicability=PolicyApplicability.create(
            channels=("api",),
            starts_at=NOW - timedelta(days=10),
            ends_at=NOW,
        )
    )

    with pytest.raises(PolicyValidationError, match="vigência expirada"):
        expired_draft.publish(
            now=NOW,
            actor_subject_id="user_credit_manager",
            correlation_id="corr_2234567890abcdef",
            change_summary="Publicação expirada",
        )

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
        revision=2,
        applicability=PolicyApplicability.create(channels=("api",), starts_at=NOW),
        rules=(_rule(),),
        criteria=(_criterion(),),
        limits=(_limit(),),
        changelog=(
            _changelog_entry("created", None, 1),
            _changelog_entry("published", 1, 2),
        ),
        created_at=NOW,
        updated_at=NOW,
    )

    with pytest.raises(PolicyImmutableError, match="política não pode ser alterada"):
        published.publish(
            now=NOW,
            actor_subject_id="user_credit_manager",
            correlation_id="corr_3234567890abcdef",
            change_summary="Republicação indevida",
        )


def test_create_new_version_from_published_policy_preserves_original_snapshot() -> None:
    published = _draft_policy(
        applicability=PolicyApplicability.create(channels=("api",), starts_at=NOW)
    ).publish(
        now=NOW,
        actor_subject_id="user_credit_manager",
        correlation_id="corr_1234567890abcdef",
        change_summary="Publicação aprovada",
    )
    next_rule = PolicyRule.create(
        rule_id="rule_revised_income",
        name="Renda revisada",
        source_field="monthly_income_units",
        operator="gte",
        threshold_value=300_000,
        outcome="approve",
        reason_code_refs=("rc_min_income",),
    )

    next_version = published.create_new_version(
        policy_version_id="polver_personal_credit_default_v2",
        version=2,
        rules=(next_rule,),
        criteria=published.criteria,
        limits=published.limits,
        applicability=PolicyApplicability.create(
            channels=("api",),
            starts_at=NOW + timedelta(days=10),
        ),
        reason_code_catalog_id=published.reason_code_catalog_id,
        reason_code_catalog_version_id=published.reason_code_catalog_version_id,
        now=NOW + timedelta(hours=1),
        actor_subject_id="user_credit_manager",
        correlation_id="corr_4234567890abcdef",
        change_summary="Nova versão para ajuste de renda",
    )

    assert published.status == "published"
    assert published.version == 1
    assert published.rules[0].rule_id == "rule_min_income"
    assert next_version.status == "draft"
    assert next_version.version == 2
    assert next_version.revision == 1
    assert next_version.policy_id == published.policy_id
    assert next_version.policy_version_id == "polver_personal_credit_default_v2"
    assert next_version.rules[0].rule_id == "rule_revised_income"
    assert next_version.changelog[0].change_type == "versioned"


def _draft_policy(*, applicability: PolicyApplicability) -> CreditPolicy:
    return CreditPolicy.create_draft(
        policy_id="pol_personal_credit_default",
        policy_version_id="polver_personal_credit_default_v1",
        tenant_id="tenant_alpha",
        owner_subject_id="user_credit_manager",
        product_type="personal_credit",
        reason_code_catalog_id="rcc_personal_credit_default",
        reason_code_catalog_version_id="rccver_personal_credit_default_v1",
        applicability=applicability,
        rules=(_rule(),),
        criteria=(_criterion(),),
        limits=(_limit(),),
        now=NOW,
        actor_subject_id="user_credit_manager",
        correlation_id="corr_1234567890abcdef",
        change_summary="Criação inicial da política padrão",
    )


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


def _changelog_entry(
    change_type: str,
    previous_revision: int | None,
    resulting_revision: int,
) -> PolicyChangelogEntry:
    return PolicyChangelogEntry.create(
        change_type=change_type,
        actor_subject_id="user_credit_manager",
        changed_at=NOW,
        change_summary="Alteração governada",
        correlation_id="corr_1234567890abcdef",
        previous_revision=previous_revision,
        resulting_revision=resulting_revision,
    )
