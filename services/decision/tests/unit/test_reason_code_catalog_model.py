from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest
from creditos_decision.domain.entities import ReasonCodeCatalog
from creditos_decision.domain.errors import (
    PolicyImmutableError,
    PolicyValidationError,
    ReasonCodeCatalogVersioningError,
)
from creditos_decision.domain.value_objects import (
    ExplainableFactor,
    PolicyRule,
    ReasonCode,
)

NOW = datetime(2026, 8, 26, 12, 0, tzinfo=UTC)


def test_create_draft_reason_code_catalog_with_versioning_and_changelog() -> None:
    catalog = _draft_catalog()

    assert catalog.status == "draft"
    assert catalog.version == 1
    assert catalog.revision == 1
    assert catalog.is_referenceable_for_final_decisions is False
    assert catalog.is_referenceable_for_policy_draft is True
    assert catalog.changelog[0].change_type == "created"
    assert catalog.reason_codes[0].code == "rc_min_income"
    assert catalog.explainable_factors[0].field == "monthly_income_units"


def test_reason_codes_and_explainable_factors_reject_sensitive_or_free_form_data() -> None:
    with pytest.raises(PolicyValidationError, match="dado sensível ou campo proibido"):
        ExplainableFactor.create(
            factor_id="factor_email",
            field="email",
            title="E-mail",
            internal_description="Idade do e-mail",
            external_description="E-mail do cliente",
        )

    with pytest.raises(PolicyValidationError, match="dado sensível ou campo proibido"):
        ReasonCode.create(
            reason_code_id="reason_sensitive",
            code="rc_sensitive",
            outcome="reject",
            title="CPF inconsistente",
            internal_description="CPF 123.456.789-10 inconsistente",
            external_description="Documento sensível inconsistente",
            factor_refs=("factor_monthly_income",),
        )

    with pytest.raises(PolicyValidationError, match="campo de política não governado"):
        ExplainableFactor.create(
            factor_id="factor_unknown_score",
            field="unknown_score_units",
            title="Score externo",
            internal_description="Score externo",
            external_description="Score externo",
        )


def test_catalog_rejects_duplicate_reason_codes_and_factor_refs() -> None:
    reason_code = _reason_code()

    with pytest.raises(PolicyValidationError, match="reason code duplicado"):
        ReasonCodeCatalog.create_draft(
            catalog_id="rcc_personal_credit_default",
            catalog_version_id="rccver_personal_credit_default_v1",
            tenant_id="tenant_alpha",
            owner_subject_id="user_credit_manager",
            product_type="personal_credit",
            reason_codes=(reason_code, reason_code),
            explainable_factors=(_factor(),),
            now=NOW,
            actor_subject_id="user_credit_manager",
            correlation_id="corr_1234567890abcdef",
            change_summary="Criação inicial do catálogo",
        )

    with pytest.raises(PolicyValidationError, match="fator explicável inexistente"):
        ReasonCode.create(
            reason_code_id="reason_missing_factor",
            code="rc_missing_factor",
            outcome="reject",
            title="Fator inexistente",
            internal_description="Fator inexistente",
            external_description="Fator inexistente",
            factor_refs=("factor_missing",),
        ).validate_factor_refs(known_factor_ids={"factor_monthly_income"})


def test_catalog_validates_policy_reason_refs_are_active_and_outcome_compatible() -> None:
    catalog = _draft_catalog()

    catalog.validate_policy_rules(
        (
            PolicyRule.create(
                rule_id="rule_min_income",
                name="Renda mínima declarada",
                source_field="monthly_income_units",
                operator="gte",
                threshold_value=250_000,
                outcome="reject",
                reason_code_refs=("rc_min_income",),
            ),
        )
    )

    with pytest.raises(PolicyValidationError, match="reason code incompatível"):
        catalog.validate_policy_rules(
            (
                PolicyRule.create(
                    rule_id="rule_outcome_mismatch",
                    name="Resultado incompatível",
                    source_field="monthly_income_units",
                    operator="gte",
                    threshold_value=250_000,
                    outcome="approve",
                    reason_code_refs=("rc_min_income",),
                ),
            )
        )

    with pytest.raises(ReasonCodeCatalogVersioningError, match="nova versão"):
        catalog.update_draft(
            reason_codes=(replace(catalog.reason_codes[0], status="archived"),),
            explainable_factors=catalog.explainable_factors,
            now=NOW.replace(hour=13),
            actor_subject_id="user_credit_manager",
            correlation_id="corr_2234567890abcdef",
            change_summary="Arquivamento controlado",
        )


def test_policy_rule_requires_reason_code_refs_and_rejects_duplicates() -> None:
    with pytest.raises(PolicyValidationError, match="reason code obrigatório"):
        PolicyRule.create(
            rule_id="rule_missing_reason",
            name="Sem reason code",
            source_field="monthly_income_units",
            operator="gte",
            threshold_value=250_000,
            outcome="reject",
        )

    with pytest.raises(PolicyValidationError, match="reason code duplicado"):
        PolicyRule.create(
            rule_id="rule_duplicate_reason",
            name="Reason code duplicado",
            source_field="monthly_income_units",
            operator="gte",
            threshold_value=250_000,
            outcome="reject",
            reason_code_refs=("rc_min_income", "rc_min_income"),
        )


def test_incompatible_catalog_change_requires_new_version_and_preserves_old_snapshot() -> None:
    catalog = _draft_catalog()

    with pytest.raises(ReasonCodeCatalogVersioningError, match="nova versão"):
        catalog.update_draft(
            reason_codes=(
                ReasonCode.create(
                    reason_code_id="reason_min_income",
                    code="rc_min_income",
                    outcome="approve",
                    title="Renda mínima",
                    internal_description="Renda declarada abaixo da política",
                    external_description="Renda declarada insuficiente para aprovação",
                    factor_refs=("factor_monthly_income",),
                ),
            ),
            explainable_factors=catalog.explainable_factors,
            now=NOW.replace(hour=13),
            actor_subject_id="user_credit_manager",
            correlation_id="corr_3234567890abcdef",
            change_summary="Troca incompatível de resultado",
        )

    next_version = catalog.create_new_version(
        catalog_version_id="rccver_personal_credit_default_v2",
        reason_codes=(
            ReasonCode.create(
                reason_code_id="reason_min_income",
                code="rc_min_income",
                outcome="approve",
                title="Renda mínima",
                internal_description="Renda declarada abaixo da política",
                external_description="Renda declarada insuficiente para aprovação",
                factor_refs=("factor_monthly_income",),
            ),
        ),
        explainable_factors=catalog.explainable_factors,
        now=NOW.replace(hour=13),
        actor_subject_id="user_credit_manager",
        correlation_id="corr_4234567890abcdef",
        change_summary="Nova versão por mudança incompatível",
    )

    assert catalog.version == 1
    assert catalog.reason_codes[0].outcome == "reject"
    assert next_version.version == 2
    assert next_version.catalog_version_id == "rccver_personal_credit_default_v2"
    assert next_version.reason_codes[0].outcome == "approve"


def test_published_reason_code_catalog_snapshot_is_immutable() -> None:
    published = _draft_catalog().publish(
        now=NOW.replace(hour=13),
        actor_subject_id="user_credit_manager",
        correlation_id="corr_5234567890abcdef",
        change_summary="Publicação do catálogo",
    )

    assert published.status == "published"
    assert published.is_referenceable_for_final_decisions is True

    with pytest.raises(PolicyImmutableError, match="catálogo não pode ser alterado"):
        published.update_draft(
            reason_codes=published.reason_codes,
            explainable_factors=published.explainable_factors,
            now=NOW.replace(hour=14),
            actor_subject_id="user_credit_manager",
            correlation_id="corr_6234567890abcdef",
            change_summary="Tentativa de alteração publicada",
        )
    with pytest.raises(PolicyImmutableError, match="catálogo não pode ser alterado"):
        replace(
            published,
            reason_codes=(
                ReasonCode.create(
                    reason_code_id="reason_high_amount",
                    code="rc_high_amount",
                    outcome="reject",
                    title="Valor alto",
                    internal_description="Valor solicitado acima da política",
                    external_description="Valor solicitado acima do permitido",
                    factor_refs=("factor_monthly_income",),
                ),
            ),
        )
    with pytest.raises(PolicyImmutableError, match="catálogo não pode ser alterado"):
        replace(published, tenant_id="tenant_beta")
    with pytest.raises(PolicyImmutableError, match="catálogo não pode ser alterado"):
        replace(published, version=2)


def test_catalog_changelog_rejects_sensitive_change_summary() -> None:
    with pytest.raises(PolicyValidationError, match="dado sensível ou campo proibido"):
        ReasonCodeCatalog.create_draft(
            catalog_id="rcc_personal_credit_default",
            catalog_version_id="rccver_personal_credit_default_v1",
            tenant_id="tenant_alpha",
            owner_subject_id="user_credit_manager",
            product_type="personal_credit",
            reason_codes=(_reason_code(),),
            explainable_factors=(_factor(),),
            now=NOW,
            actor_subject_id="user_credit_manager",
            correlation_id="corr_1234567890abcdef",
            change_summary="CPF 123.456.789-10 no catálogo",
        )


def test_product_type_and_audience_changes_require_new_catalog_version() -> None:
    catalog = _draft_catalog()

    with pytest.raises(ReasonCodeCatalogVersioningError, match="nova versão"):
        catalog.update_draft(
            reason_codes=catalog.reason_codes,
            explainable_factors=catalog.explainable_factors,
            now=NOW.replace(hour=13),
            actor_subject_id="user_credit_manager",
            correlation_id="corr_7234567890abcdef",
            change_summary="Troca incompatível de produto",
            product_type="bnpl",
        )

    with pytest.raises(ReasonCodeCatalogVersioningError, match="nova versão"):
        catalog.update_draft(
            reason_codes=(replace(catalog.reason_codes[0], audience="customer"),),
            explainable_factors=catalog.explainable_factors,
            now=NOW.replace(hour=13),
            actor_subject_id="user_credit_manager",
            correlation_id="corr_8234567890abcdef",
            change_summary="Troca incompatível de audiência",
        )


def test_restoring_non_draft_catalog_requires_persisted_fingerprint() -> None:
    published = _draft_catalog().publish(
        now=NOW.replace(hour=13),
        actor_subject_id="user_credit_manager",
        correlation_id="corr_9234567890abcdef",
        change_summary="Publicação do catálogo",
    )

    with pytest.raises(PolicyImmutableError, match="catálogo não pode ser alterado"):
        ReasonCodeCatalog.restore(
            catalog_id=published.catalog_id,
            catalog_version_id=published.catalog_version_id,
            tenant_id=published.tenant_id,
            owner_subject_id=published.owner_subject_id,
            product_type=published.product_type,
            status=published.status,
            version=published.version,
            revision=published.revision,
            reason_codes=published.reason_codes,
            explainable_factors=published.explainable_factors,
            changelog=published.changelog,
            created_at=published.created_at,
            updated_at=published.updated_at,
        )

    restored = ReasonCodeCatalog.restore(
        catalog_id=published.catalog_id,
        catalog_version_id=published.catalog_version_id,
        tenant_id=published.tenant_id,
        owner_subject_id=published.owner_subject_id,
        product_type=published.product_type,
        status=published.status,
        version=published.version,
        revision=published.revision,
        reason_codes=published.reason_codes,
        explainable_factors=published.explainable_factors,
        changelog=published.changelog,
        created_at=published.created_at,
        updated_at=published.updated_at,
        governed_fingerprint=published.governed_fingerprint,
    )

    assert restored.governed_fingerprint == published.governed_fingerprint


def _draft_catalog() -> ReasonCodeCatalog:
    return ReasonCodeCatalog.create_draft(
        catalog_id="rcc_personal_credit_default",
        catalog_version_id="rccver_personal_credit_default_v1",
        tenant_id="tenant_alpha",
        owner_subject_id="user_credit_manager",
        product_type="personal_credit",
        reason_codes=(_reason_code(),),
        explainable_factors=(_factor(),),
        now=NOW,
        actor_subject_id="user_credit_manager",
        correlation_id="corr_1234567890abcdef",
        change_summary="Criação inicial do catálogo",
    )


def _reason_code() -> ReasonCode:
    return ReasonCode.create(
        reason_code_id="reason_min_income",
        code="rc_min_income",
        outcome="reject",
        title="Renda mínima",
        internal_description="Renda declarada abaixo da política",
        external_description="Renda declarada insuficiente para aprovação",
        factor_refs=("factor_monthly_income",),
    )


def _factor() -> ExplainableFactor:
    return ExplainableFactor.create(
        factor_id="factor_monthly_income",
        field="monthly_income_units",
        title="Renda declarada",
        internal_description="Renda mensal declarada em unidades monetárias menores",
        external_description="Renda declarada informada para análise",
        required=True,
    )
