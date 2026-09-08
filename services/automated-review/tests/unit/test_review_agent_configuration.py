from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from creditos_automated_review.adapters.persistence import InMemoryReviewAgentConfigRepository
from creditos_automated_review.application.ports import (
    AutomatedReviewAuditIntent,
    AutomatedReviewAuditPublisher,
)
from creditos_automated_review.application.service import (
    AutomatedReviewApplicationService,
    CreateReviewAgentConfigCommand,
    CreateReviewAgentConfigVersionCommand,
    GetReviewAgentConfigCommand,
    PublishReviewAgentConfigCommand,
    UpdateReviewAgentConfigCommand,
)
from creditos_automated_review.domain.entities import ReviewAgentConfiguration
from creditos_automated_review.domain.errors import (
    AutomatedReviewConfigNotFoundError,
    AutomatedReviewConflictError,
    AutomatedReviewImmutableError,
    AutomatedReviewTenantContextError,
    AutomatedReviewValidationError,
)
from creditos_automated_review.domain.value_objects import (
    ReviewAgentCapabilities,
    ReviewAgentGuardrails,
    ReviewAgentPrompt,
    ReviewAgentScope,
    ReviewModelRef,
)
from creditos_observability.context import ObservabilityContext
from creditos_security import PropagatedContext, TrustedContext

NOW = datetime(2026, 9, 7, 12, 0, tzinfo=UTC)


class RecordingAuditPublisher:
    def __init__(self) -> None:
        self.events: list[AutomatedReviewAuditIntent] = []

    def publish(self, event: AutomatedReviewAuditIntent) -> None:
        self.events.append(event)


def test_review_agent_config_draft_records_versioned_governed_fields() -> None:
    config = _draft_config()

    assert config.review_agent_config_id == "rac_personal_credit_default"
    assert config.review_agent_config_version_id == "racver_personal_credit_default_v1"
    assert config.revision == 1
    assert config.status == "draft"
    assert config.tenant_id == "tenant_alpha"
    assert config.owner_subject_id == "user_risk_manager"
    assert config.product_type == "personal_credit"
    assert config.scope.channels == ("api",)
    assert config.agent_version == "agent_credit_review_v1"
    assert config.prompt.prompt_version == "prompt_credit_review_v1"
    assert config.prompt.prompt_fingerprint
    assert config.model_ref is not None
    assert config.model_ref.provider_ref == "provider_llm_default"
    assert config.guardrails.block_final_decision is True
    assert config.capabilities.consultative_only is True
    assert config.changelog[0].change_type == "created"
    assert config.is_referenceable_for_review is False


def test_review_agent_config_update_tracks_revision_and_preserves_published_version() -> None:
    draft = _draft_config()
    updated = draft.update_draft(
        prompt=_prompt(instructions="Avalie lacunas e inconsistências de forma consultiva"),
        model_ref=_model_ref(model_version="model_version_002"),
        guardrails=_guardrails(max_prompt_tokens=3500),
        actor_subject_id="user_risk_manager",
        correlation_id="corr_review_update",
        change_summary="Ajuste controlado de prompt e limites",
        now=NOW + timedelta(minutes=1),
    )

    assert updated.revision == 2
    assert updated.prompt.prompt_fingerprint != draft.prompt.prompt_fingerprint
    assert updated.model_ref is not None
    assert updated.model_ref.model_version == "model_version_002"
    assert updated.guardrails.max_prompt_tokens == 3500
    assert updated.changelog[-1].change_type == "updated"
    assert updated.changelog[-1].previous_revision == 1
    assert updated.changelog[-1].resulting_revision == 2

    published = updated.publish(
        actor_subject_id="user_risk_manager",
        correlation_id="corr_review_publish",
        change_summary="Publicação aprovada",
        approval_reference="approval_board_001",
        now=NOW + timedelta(minutes=2),
    )

    with pytest.raises(AutomatedReviewImmutableError):
        published.update_draft(
            prompt=_prompt(instructions="Tente mutar versão publicada"),
            actor_subject_id="user_risk_manager",
            correlation_id="corr_review_mutate",
            change_summary="Mutação proibida",
            now=NOW + timedelta(minutes=3),
        )

    next_version = published.create_new_version(
        new_review_agent_config_version_id="racver_personal_credit_default_v2",
        actor_subject_id="user_risk_manager",
        correlation_id="corr_review_new_version",
        change_summary="Nova versão para ajustes",
        now=NOW + timedelta(minutes=4),
    )

    assert published.status == "published"
    assert published.revision == 3
    assert next_version.status == "draft"
    assert next_version.revision == 1
    assert next_version.review_agent_config_id == published.review_agent_config_id
    assert next_version.review_agent_config_version_id == "racver_personal_credit_default_v2"
    assert next_version.prompt == published.prompt
    assert next_version.changelog[0].change_type == "new_version_created"


def test_review_agent_config_rejects_autonomous_or_sensitive_configuration() -> None:
    with pytest.raises(AutomatedReviewValidationError) as autonomous_error:
        ReviewAgentCapabilities.create(can_approve=True)
    assert autonomous_error.value.code == "automated_review_autonomous_capability"

    with pytest.raises(AutomatedReviewValidationError) as prompt_error:
        _prompt(instructions="Analisar CPF e e-mail informados pelo solicitante")
    assert prompt_error.value.code == "sensitive_prompt_content"

    with pytest.raises(AutomatedReviewValidationError) as provider_secret_error:
        _model_ref(provider_ref="provider_token_secret")
    assert provider_secret_error.value.code == "sensitive_model_reference"

    with pytest.raises(AutomatedReviewValidationError) as raw_payload_error:
        ReviewAgentScope.create(
            product_type="personal_credit",
            channels=("api",),
            review_purposes=("raw_payload",),
        )
    assert raw_payload_error.value.code == "unsupported_review_purpose"

    with pytest.raises(AutomatedReviewValidationError) as name_error:
        _prompt(instructions="Avaliar nome completo informado pelo solicitante")
    assert name_error.value.code == "sensitive_prompt_content"

    with pytest.raises(AutomatedReviewValidationError) as street_error:
        _prompt(instructions="Avaliar endereço residencial informado")
    assert street_error.value.code == "sensitive_prompt_content"

    with pytest.raises(AutomatedReviewValidationError) as fingerprint_error:
        ReviewAgentPrompt(
            prompt_version="prompt_credit_review_v1",
            instructions="Avalie lacunas e inconsistências sem decidir crédito",
            input_allowlist=("requested_amount_units", "requested_installments"),
            output_schema_ref="automated_review_output_v1",
            prompt_fingerprint="0" * 64,
        )
    assert fingerprint_error.value.code == "prompt_fingerprint_mismatch"

    with pytest.raises(AutomatedReviewValidationError) as api_key_error:
        _model_ref(provider_ref="sk-abc123456789")
    assert api_key_error.value.code == "sensitive_model_reference"


def test_review_agent_application_publishes_after_audit_and_rolls_back_on_audit_failure() -> None:
    audit = RecordingAuditPublisher()
    repository = InMemoryReviewAgentConfigRepository()
    service = _service(repository=repository, audit=audit)

    created = service.create_config(
        _create_command(),
        context=_context(),
        trusted_context=_trusted_context(scopes=("automated_review:write",)),
    )
    updated = service.update_config(
        UpdateReviewAgentConfigCommand(
            review_agent_config_id=created.config.review_agent_config_id,
            review_agent_config_version_id=created.config.review_agent_config_version_id,
            prompt=_prompt(instructions="Avalie inconsistências e lacunas consultivas"),
            change_summary="Atualização governada antes da publicação",
        ),
        context=_context(),
        trusted_context=_trusted_context(scopes=("automated_review:write",)),
    )
    published = service.publish_config(
        PublishReviewAgentConfigCommand(
            review_agent_config_id=updated.config.review_agent_config_id,
            review_agent_config_version_id=updated.config.review_agent_config_version_id,
            approval_reference="approval_board_001",
            change_summary="Publicação controlada para revisão consultiva",
        ),
        context=_context(),
        trusted_context=_trusted_context(scopes=("automated_review:publish",)),
    )

    assert published.config.status == "published"
    persisted_published = repository.get(
        tenant_id="tenant_alpha",
        review_agent_config_id=updated.config.review_agent_config_id,
        review_agent_config_version_id=updated.config.review_agent_config_version_id,
    )
    assert persisted_published is not None
    assert persisted_published.status == "published"
    assert [event.event_type for event in audit.events] == [
        "automated_review.config.created",
        "automated_review.config.updated",
        "automated_review.config.published",
    ]
    assert audit.events[-1].safe_details["prompt_fingerprint"] == (
        published.config.prompt.prompt_fingerprint
    )
    assert audit.events[-1].safe_details["approval_reference"] == "approval_board_001"
    assert audit.events[-1].change_summary == "Publicação controlada para revisão consultiva"
    assert audit.events[-1].previous_revision == updated.config.revision
    assert audit.events[-1].resulting_revision == published.config.revision
    assert "Avalie lacunas" not in str(audit.events)
    assert published.logs[0]["payload"] == "[OMITIDO]"

    class FailingPublishAudit(RecordingAuditPublisher):
        def publish(self, event: AutomatedReviewAuditIntent) -> None:
            if event.event_type == "automated_review.config.published":
                raise RuntimeError("audit sink unavailable")
            super().publish(event)

    failing_repository = InMemoryReviewAgentConfigRepository()
    failing_service = _service(repository=failing_repository, audit=FailingPublishAudit())
    created_for_failure = failing_service.create_config(
        _create_command(review_agent_config_id="rac_failure_case"),
        context=_context(),
        trusted_context=_trusted_context(scopes=("automated_review:write",)),
    )

    with pytest.raises(RuntimeError, match="audit sink unavailable"):
        failing_service.publish_config(
            PublishReviewAgentConfigCommand(
                review_agent_config_id=created_for_failure.config.review_agent_config_id,
                review_agent_config_version_id=created_for_failure.config.review_agent_config_version_id,
                approval_reference="approval_board_002",
                change_summary="Publicação deve preservar atomicidade",
            ),
            context=_context(),
            trusted_context=_trusted_context(scopes=("automated_review:publish",)),
        )

    persisted_after_audit_failure = failing_repository.get(
        tenant_id="tenant_alpha",
        review_agent_config_id=created_for_failure.config.review_agent_config_id,
        review_agent_config_version_id=created_for_failure.config.review_agent_config_version_id,
    )
    assert persisted_after_audit_failure is not None
    assert persisted_after_audit_failure.status == "draft"


def test_review_agent_application_versions_and_preserves_historical_published_config() -> None:
    audit = RecordingAuditPublisher()
    service = _service(audit=audit)
    created = service.create_config(
        _create_command(),
        context=_context(),
        trusted_context=_trusted_context(scopes=("automated_review:write",)),
    )
    published = service.publish_config(
        PublishReviewAgentConfigCommand(
            review_agent_config_id=created.config.review_agent_config_id,
            review_agent_config_version_id=created.config.review_agent_config_version_id,
            approval_reference="approval_board_001",
            change_summary="Publicação inicial",
        ),
        context=_context(),
        trusted_context=_trusted_context(scopes=("automated_review:publish",)),
    )
    next_version = service.create_config_version(
        CreateReviewAgentConfigVersionCommand(
            review_agent_config_id=published.config.review_agent_config_id,
            current_review_agent_config_version_id=published.config.review_agent_config_version_id,
            new_review_agent_config_version_id="racver_personal_credit_default_v2",
            change_summary="Nova versão governada",
        ),
        context=_context(),
        trusted_context=_trusted_context(scopes=("automated_review:write",)),
    )

    assert next_version.config.status == "draft"
    assert next_version.config.review_agent_config_version_id == "racver_personal_credit_default_v2"

    historical = service.get_config(
        GetReviewAgentConfigCommand(
            review_agent_config_id=published.config.review_agent_config_id,
            review_agent_config_version_id=published.config.review_agent_config_version_id,
        ),
        context=_context(),
        trusted_context=_trusted_context(scopes=("automated_review:read",)),
    )

    assert historical.config.status == "published"
    assert historical.config.review_agent_config_version_id == (
        published.config.review_agent_config_version_id
    )
    assert audit.events[-1].event_type == "automated_review.config.version_created"


def test_review_agent_repository_rejects_overwrite_and_filters_published_by_scope() -> None:
    repository = InMemoryReviewAgentConfigRepository()
    config = _draft_config()
    repository.create(config)

    with pytest.raises(AutomatedReviewConflictError):
        repository.create(config)

    published = config.publish(
        actor_subject_id="user_risk_manager",
        correlation_id="corr_review_publish",
        change_summary="Publicação aprovada",
        approval_reference="approval_board_001",
        now=NOW + timedelta(minutes=1),
    )
    repository.save_existing(
        published,
        expected_revision=config.revision,
        expected_status=config.status,
    )

    assert repository.list_published_by_scope(
        tenant_id="tenant_alpha",
        product_type="personal_credit",
        channel="api",
        review_purpose="missing_data",
    ) == (published,)
    assert (
        repository.list_published_by_scope(
            tenant_id="tenant_alpha",
            product_type="personal_credit",
            channel="batch",
            review_purpose="missing_data",
        )
        == ()
    )


def test_review_agent_config_rejects_noop_clears_model_and_validates_restore_integrity() -> None:
    draft = _draft_config()

    with pytest.raises(AutomatedReviewValidationError) as noop_error:
        draft.update_draft(
            actor_subject_id="user_risk_manager",
            correlation_id="corr_review_noop",
            change_summary="Tentativa sem mudanças",
            now=NOW + timedelta(minutes=1),
        )
    assert noop_error.value.code == "review_config_no_changes"

    without_model = draft.update_draft(
        clear_model_ref=True,
        actor_subject_id="user_risk_manager",
        correlation_id="corr_review_clear_model",
        change_summary="Remoção governada de modelo",
        now=NOW + timedelta(minutes=2),
    )
    assert without_model.model_ref is None

    with pytest.raises(AutomatedReviewValidationError) as product_error:
        ReviewAgentConfiguration(
            review_agent_config_id=draft.review_agent_config_id,
            review_agent_config_version_id=draft.review_agent_config_version_id,
            tenant_id=draft.tenant_id,
            owner_subject_id=draft.owner_subject_id,
            product_type="bnpl",
            agent_version=draft.agent_version,
            prompt=draft.prompt,
            scope=draft.scope,
            guardrails=draft.guardrails,
            capabilities=draft.capabilities,
            status=draft.status,
            revision=draft.revision,
            changelog=draft.changelog,
            model_ref=draft.model_ref,
        )
    assert product_error.value.code == "review_config_product_scope_mismatch"

    with pytest.raises(AutomatedReviewValidationError) as changelog_error:
        ReviewAgentConfiguration(
            review_agent_config_id=draft.review_agent_config_id,
            review_agent_config_version_id=draft.review_agent_config_version_id,
            tenant_id=draft.tenant_id,
            owner_subject_id=draft.owner_subject_id,
            product_type=draft.product_type,
            agent_version=draft.agent_version,
            prompt=draft.prompt,
            scope=draft.scope,
            guardrails=draft.guardrails,
            capabilities=draft.capabilities,
            status=draft.status,
            revision=2,
            changelog=draft.changelog,
            model_ref=draft.model_ref,
        )
    assert changelog_error.value.code == "review_config_changelog_revision_mismatch"


def test_review_agent_application_enforces_scopes_bridge_tenant_and_not_found_cross_tenant() -> (
    None
):
    service = _service(audit=RecordingAuditPublisher())

    with pytest.raises(AutomatedReviewTenantContextError):
        service.create_config(
            _create_command(),
            context=_context(),
            trusted_context=_trusted_context(
                scopes=("automated_review:write",),
                tenant_isolation_tier="silo",
            ),
        )

    with pytest.raises(PermissionError):
        service.create_config(
            _create_command(),
            context=_context(),
            trusted_context=_trusted_context(scopes=("automated_review:read",)),
        )

    created = service.create_config(
        _create_command(),
        context=_context(),
        trusted_context=_trusted_context(scopes=("automated_review:write",)),
    )
    assert created.config.owner_subject_id == "user_risk_manager"

    with pytest.raises(AutomatedReviewTenantContextError):
        service.create_config(
            _create_command(review_agent_config_id="rac_context_mismatch"),
            context=_context(tenant_id="tenant_beta"),
            trusted_context=_trusted_context(scopes=("automated_review:write",)),
        )

    with pytest.raises(AutomatedReviewConfigNotFoundError):
        service.get_config(
            GetReviewAgentConfigCommand(
                review_agent_config_id=created.config.review_agent_config_id,
                review_agent_config_version_id=created.config.review_agent_config_version_id,
            ),
            context=_context(tenant_id="tenant_beta"),
            trusted_context=_trusted_context(
                tenant_id="tenant_beta",
                scopes=("automated_review:read",),
            ),
        )


def test_review_agent_logs_are_minimized_and_do_not_expose_prompt_or_sensitive_values() -> None:
    audit = RecordingAuditPublisher()
    service = _service(audit=audit)

    result = service.create_config(
        _create_command(),
        context=_context(),
        trusted_context=_trusted_context(scopes=("automated_review:write",)),
    )
    log_text = str(result.logs)
    audit_text = str(audit.events)

    assert result.logs[0]["payload"] == "[OMITIDO]"
    assert result.logs[0]["extra"]["prompt_fingerprint"] == result.config.prompt.prompt_fingerprint
    assert "Avalie lacunas" not in log_text
    assert "CPF_EXEMPLO" not in log_text
    assert "EMAIL_EXEMPLO" not in log_text
    assert "Authorization" not in log_text
    assert "Avalie lacunas" not in audit_text


def _service(
    *,
    audit: AutomatedReviewAuditPublisher,
    repository: InMemoryReviewAgentConfigRepository | None = None,
) -> AutomatedReviewApplicationService:
    return AutomatedReviewApplicationService(
        repository=repository or InMemoryReviewAgentConfigRepository(),
        audit_publisher=audit,
        environment="test",
        clock=lambda: NOW,
    )


def _create_command(
    *,
    review_agent_config_id: str = "rac_personal_credit_default",
) -> CreateReviewAgentConfigCommand:
    return CreateReviewAgentConfigCommand(
        review_agent_config_id=review_agent_config_id,
        review_agent_config_version_id=f"{review_agent_config_id}_v1",
        agent_version="agent_credit_review_v1",
        prompt=_prompt(),
        scope=_scope(),
        guardrails=_guardrails(),
        capabilities=_capabilities(),
        model_ref=_model_ref(),
        change_summary="Criação da configuração consultiva",
    )


def _draft_config(
    *,
    capabilities: ReviewAgentCapabilities | None = None,
) -> ReviewAgentConfiguration:
    return ReviewAgentConfiguration.create_draft(
        review_agent_config_id="rac_personal_credit_default",
        review_agent_config_version_id="racver_personal_credit_default_v1",
        tenant_id="tenant_alpha",
        owner_subject_id="user_risk_manager",
        agent_version="agent_credit_review_v1",
        prompt=_prompt(),
        scope=_scope(),
        guardrails=_guardrails(),
        capabilities=capabilities or _capabilities(),
        model_ref=_model_ref(),
        actor_subject_id="user_risk_manager",
        correlation_id="corr_review_create",
        change_summary="Criação da configuração consultiva",
        now=NOW,
    )


def _scope() -> ReviewAgentScope:
    return ReviewAgentScope.create(
        product_type="personal_credit",
        channels=("api",),
        review_purposes=("missing_data", "inconsistency", "explainability_factor"),
    )


def _prompt(
    *, instructions: str = "Avalie lacunas e inconsistências sem decidir crédito"
) -> ReviewAgentPrompt:
    return ReviewAgentPrompt.create(
        prompt_version="prompt_credit_review_v1",
        instructions=instructions,
        input_allowlist=("requested_amount_units", "requested_installments"),
        output_schema_ref="automated_review_output_v1",
    )


def _guardrails(*, max_prompt_tokens: int = 3000) -> ReviewAgentGuardrails:
    return ReviewAgentGuardrails.create(
        require_schema_validation=True,
        require_input_minimization=True,
        block_sensitive_data=True,
        block_final_decision=True,
        block_tool_use=True,
        fallback_action="continue_without_review",
        max_prompt_tokens=max_prompt_tokens,
        max_output_tokens=1000,
    )


def _capabilities() -> ReviewAgentCapabilities:
    return ReviewAgentCapabilities.create(
        can_suggest_missing_data=True,
        can_suggest_inconsistencies=True,
        can_suggest_explainability_factors=True,
    )


def _model_ref(
    *, provider_ref: str = "provider_llm_default", model_version: str = "model_v1"
) -> ReviewModelRef:
    return ReviewModelRef.create(
        provider_ref=provider_ref,
        model_ref="model_credit_review_default",
        model_version=model_version,
    )


def _context(*, tenant_id: str = "tenant_alpha") -> ObservabilityContext:
    return ObservabilityContext.new(
        correlation_id="corr_review_context",
        request_id="req_review_context",
        trace_id="1" * 32,
        tenant_id=tenant_id,
        tenant_isolation_tier="bridge",
    )


def _trusted_context(
    *,
    tenant_id: str = "tenant_alpha",
    scopes: tuple[str, ...],
    tenant_isolation_tier: str = "bridge",
) -> PropagatedContext:
    return PropagatedContext(
        trusted=TrustedContext(
            tenant_id=tenant_id,
            tenant_isolation_tier=tenant_isolation_tier,
            subject_id="user_risk_manager",
            scopes=scopes,
            roles=("risk_manager",),
            client_id="client_creditos_tests",
        ),
        correlation_id="corr_review_context",
        request_id="req_review_context",
        traceparent=f"00-{'1' * 32}-{'2' * 16}-01",
    )
