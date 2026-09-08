from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from creditos_automated_review.domain.errors import (
    AutomatedReviewImmutableError,
    AutomatedReviewValidationError,
)
from creditos_automated_review.domain.value_objects import (
    ReviewAgentCapabilities,
    ReviewAgentChangeLogEntry,
    ReviewAgentGuardrails,
    ReviewAgentPrompt,
    ReviewAgentScope,
    ReviewAgentStatus,
    ReviewModelRef,
)
from creditos_automated_review.domain.value_objects.review_agent_config import (
    validate_agent_version,
    validate_correlation_id,
    validate_review_agent_config_id,
    validate_review_agent_config_version_id,
    validate_subject_id,
    validate_tenant_id,
)


@dataclass(frozen=True, slots=True)
class ReviewAgentConfiguration:
    review_agent_config_id: str
    review_agent_config_version_id: str
    tenant_id: str
    owner_subject_id: str
    product_type: str
    agent_version: str
    prompt: ReviewAgentPrompt
    scope: ReviewAgentScope
    guardrails: ReviewAgentGuardrails
    capabilities: ReviewAgentCapabilities
    status: str
    revision: int
    changelog: tuple[ReviewAgentChangeLogEntry, ...]
    model_ref: ReviewModelRef | None = None
    approval_reference: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "review_agent_config_id",
            validate_review_agent_config_id(self.review_agent_config_id),
        )
        object.__setattr__(
            self,
            "review_agent_config_version_id",
            validate_review_agent_config_version_id(self.review_agent_config_version_id),
        )
        object.__setattr__(self, "tenant_id", validate_tenant_id(self.tenant_id))
        object.__setattr__(self, "owner_subject_id", validate_subject_id(self.owner_subject_id))
        object.__setattr__(self, "agent_version", validate_agent_version(self.agent_version))
        if not isinstance(self.prompt, ReviewAgentPrompt):
            raise AutomatedReviewValidationError(
                "prompt inválido",
                code="invalid_review_prompt",
                field_path="prompt",
            )
        if not isinstance(self.scope, ReviewAgentScope):
            raise AutomatedReviewValidationError(
                "escopo inválido",
                code="invalid_review_scope",
                field_path="scope",
            )
        if not isinstance(self.guardrails, ReviewAgentGuardrails):
            raise AutomatedReviewValidationError(
                "guardrails inválidos",
                code="invalid_review_guardrails",
                field_path="guardrails",
            )
        if not isinstance(self.capabilities, ReviewAgentCapabilities):
            raise AutomatedReviewValidationError(
                "capacidades inválidas",
                code="invalid_review_capabilities",
                field_path="capabilities",
            )
        if self.model_ref is not None and not isinstance(self.model_ref, ReviewModelRef):
            raise AutomatedReviewValidationError(
                "referência de modelo inválida",
                code="invalid_review_model_ref",
                field_path="model_ref",
            )
        if self.approval_reference is not None:
            object.__setattr__(
            self,
            "approval_reference",
            validate_agent_version(self.approval_reference, field_path="approval_reference"),
        )
        status = self.status.strip() if isinstance(self.status, str) else ""
        if status not in {item.value for item in ReviewAgentStatus}:
            raise AutomatedReviewValidationError(
                "status de configuração inválido",
                code="invalid_review_config_status",
                field_path="status",
            )
        object.__setattr__(self, "status", status)
        if type(self.revision) is not int or self.revision < 1:
            raise AutomatedReviewValidationError(
                "revisão inválida",
                code="invalid_review_config_revision",
                field_path="revision",
            )
        changelog = tuple(self.changelog)
        if not changelog:
            raise AutomatedReviewValidationError(
                "changelog obrigatório",
                code="empty_review_config_changelog",
                field_path="changelog",
            )
        object.__setattr__(self, "changelog", changelog)
        if self.product_type != self.scope.product_type:
            raise AutomatedReviewValidationError(
                "produto inconsistente com escopo",
                code="review_config_product_scope_mismatch",
                field_path="product_type",
            )
        _validate_changelog_sequence(changelog, self.revision)
        if changelog[-1].resulting_revision != self.revision:
            raise AutomatedReviewValidationError(
                "changelog incompatível com revisão",
                code="review_config_changelog_revision_mismatch",
                field_path="changelog",
            )

    @property
    def is_referenceable_for_review(self) -> bool:
        return self.status == ReviewAgentStatus.PUBLISHED.value

    @classmethod
    def create_draft(
        cls,
        *,
        review_agent_config_id: str,
        review_agent_config_version_id: str,
        tenant_id: str,
        owner_subject_id: str,
        agent_version: str,
        prompt: ReviewAgentPrompt,
        scope: ReviewAgentScope,
        guardrails: ReviewAgentGuardrails,
        capabilities: ReviewAgentCapabilities,
        actor_subject_id: str,
        correlation_id: str,
        change_summary: str,
        now: datetime,
        model_ref: ReviewModelRef | None = None,
    ) -> ReviewAgentConfiguration:
        return cls(
            review_agent_config_id=review_agent_config_id,
            review_agent_config_version_id=review_agent_config_version_id,
            tenant_id=tenant_id,
            owner_subject_id=owner_subject_id,
            product_type=scope.product_type,
            agent_version=agent_version,
            prompt=prompt,
            scope=scope,
            guardrails=guardrails,
            capabilities=capabilities,
            model_ref=model_ref,
            status=ReviewAgentStatus.DRAFT.value,
            revision=1,
            changelog=(
                _change_log_entry(
                    change_type="created",
                    actor_subject_id=actor_subject_id,
                    correlation_id=correlation_id,
                    change_summary=change_summary,
                    previous_revision=0,
                    resulting_revision=1,
                    now=now,
                ),
            ),
        )

    def update_draft(
        self,
        *,
        actor_subject_id: str,
        correlation_id: str,
        change_summary: str,
        now: datetime,
        agent_version: str | None = None,
        prompt: ReviewAgentPrompt | None = None,
        scope: ReviewAgentScope | None = None,
        guardrails: ReviewAgentGuardrails | None = None,
        capabilities: ReviewAgentCapabilities | None = None,
        model_ref: ReviewModelRef | None = None,
        clear_model_ref: bool = False,
    ) -> ReviewAgentConfiguration:
        self._require_draft()
        if clear_model_ref and model_ref is not None:
            raise AutomatedReviewValidationError(
                "remoção e definição de modelo são mutuamente exclusivas",
                code="invalid_model_ref_update",
                field_path="model_ref",
            )
        next_model_ref = (
            None if clear_model_ref else self.model_ref if model_ref is None else model_ref
        )
        next_agent_version = agent_version or self.agent_version
        next_revision = self.revision + 1
        next_scope = scope or self.scope
        next_prompt = prompt or self.prompt
        next_guardrails = guardrails or self.guardrails
        next_capabilities = capabilities or self.capabilities
        if (
            next_agent_version == self.agent_version
            and next_prompt == self.prompt
            and next_scope == self.scope
            and next_guardrails == self.guardrails
            and next_capabilities == self.capabilities
            and next_model_ref == self.model_ref
        ):
            raise AutomatedReviewValidationError(
                "update sem alterações não é permitido",
                code="review_config_no_changes",
                field_path="configuration",
            )
        return ReviewAgentConfiguration(
            review_agent_config_id=self.review_agent_config_id,
            review_agent_config_version_id=self.review_agent_config_version_id,
            tenant_id=self.tenant_id,
            owner_subject_id=self.owner_subject_id,
            product_type=next_scope.product_type,
            agent_version=next_agent_version,
            prompt=next_prompt,
            scope=next_scope,
            guardrails=next_guardrails,
            capabilities=next_capabilities,
            model_ref=next_model_ref,
            approval_reference=None,
            status=self.status,
            revision=next_revision,
            changelog=(
                *self.changelog,
                _change_log_entry(
                    change_type="updated",
                    actor_subject_id=actor_subject_id,
                    correlation_id=correlation_id,
                    change_summary=change_summary,
                    previous_revision=self.revision,
                    resulting_revision=next_revision,
                    now=now,
                ),
            ),
        )

    def publish(
        self,
        *,
        actor_subject_id: str,
        correlation_id: str,
        change_summary: str,
        approval_reference: str,
        now: datetime,
    ) -> ReviewAgentConfiguration:
        self._require_draft()
        next_revision = self.revision + 1
        return ReviewAgentConfiguration(
            review_agent_config_id=self.review_agent_config_id,
            review_agent_config_version_id=self.review_agent_config_version_id,
            tenant_id=self.tenant_id,
            owner_subject_id=self.owner_subject_id,
            product_type=self.product_type,
            agent_version=self.agent_version,
            prompt=self.prompt,
            scope=self.scope,
            guardrails=self.guardrails,
            capabilities=self.capabilities,
            model_ref=self.model_ref,
            approval_reference=approval_reference,
            status=ReviewAgentStatus.PUBLISHED.value,
            revision=next_revision,
            changelog=(
                *self.changelog,
                _change_log_entry(
                    change_type="published",
                    actor_subject_id=actor_subject_id,
                    correlation_id=correlation_id,
                    change_summary=change_summary,
                    previous_revision=self.revision,
                    resulting_revision=next_revision,
                    now=now,
                ),
            ),
        )

    def create_new_version(
        self,
        *,
        new_review_agent_config_version_id: str,
        actor_subject_id: str,
        correlation_id: str,
        change_summary: str,
        now: datetime,
    ) -> ReviewAgentConfiguration:
        if self.status != ReviewAgentStatus.PUBLISHED.value:
            raise AutomatedReviewValidationError(
                "nova versão exige configuração publicada",
                code="review_config_new_version_requires_published",
                field_path="status",
            )
        return ReviewAgentConfiguration(
            review_agent_config_id=self.review_agent_config_id,
            review_agent_config_version_id=new_review_agent_config_version_id,
            tenant_id=self.tenant_id,
            owner_subject_id=self.owner_subject_id,
            product_type=self.product_type,
            agent_version=self.agent_version,
            prompt=self.prompt,
            scope=self.scope,
            guardrails=self.guardrails,
            capabilities=self.capabilities,
            model_ref=self.model_ref,
            approval_reference=None,
            status=ReviewAgentStatus.DRAFT.value,
            revision=1,
            changelog=(
                _change_log_entry(
                    change_type="new_version_created",
                    actor_subject_id=actor_subject_id,
                    correlation_id=correlation_id,
                    change_summary=change_summary,
                    previous_revision=self.revision,
                    resulting_revision=1,
                    now=now,
                ),
            ),
        )

    def _require_draft(self) -> None:
        if self.status != ReviewAgentStatus.DRAFT.value:
            raise AutomatedReviewImmutableError(
                "configuração publicada não pode ser alterada",
                code="automated_review_config_immutable",
                field_path="status",
            )


def _validate_changelog_sequence(
    changelog: tuple[ReviewAgentChangeLogEntry, ...],
    current_revision: int,
) -> None:
    previous_resulting_revision: int | None = None
    for index, entry in enumerate(changelog):
        if not isinstance(entry, ReviewAgentChangeLogEntry):
            raise AutomatedReviewValidationError(
                "entrada de changelog inválida",
                code="invalid_review_changelog_entry",
                field_path=f"changelog[{index}]",
            )
        if index == 0:
            _validate_initial_changelog_entry(entry)
            previous_resulting_revision = entry.resulting_revision
            continue
        if previous_resulting_revision is None:
            raise AutomatedReviewValidationError(
                "sequência de changelog inválida",
                code="invalid_review_changelog_sequence",
                field_path="changelog",
            )
        if (
            entry.previous_revision != previous_resulting_revision
            or entry.resulting_revision != previous_resulting_revision + 1
        ):
            raise AutomatedReviewValidationError(
                "sequência de changelog inválida",
                code="invalid_review_changelog_sequence",
                field_path="changelog",
            )
        previous_resulting_revision = entry.resulting_revision
    if previous_resulting_revision != current_revision:
        raise AutomatedReviewValidationError(
            "changelog incompatível com revisão",
            code="review_config_changelog_revision_mismatch",
            field_path="changelog",
        )


def _validate_initial_changelog_entry(entry: ReviewAgentChangeLogEntry) -> None:
    if (
        entry.change_type == "created"
        and entry.previous_revision == 0
        and entry.resulting_revision == 1
    ):
        return
    if (
        entry.change_type == "new_version_created"
        and entry.previous_revision >= 1
        and entry.resulting_revision == 1
    ):
        return
    raise AutomatedReviewValidationError(
        "entrada inicial de changelog inválida",
        code="invalid_review_changelog_sequence",
        field_path="changelog[0]",
    )


def _change_log_entry(
    *,
    change_type: str,
    actor_subject_id: str,
    correlation_id: str,
    change_summary: str,
    previous_revision: int,
    resulting_revision: int,
    now: datetime,
) -> ReviewAgentChangeLogEntry:
    return ReviewAgentChangeLogEntry(
        change_type=change_type,
        actor_subject_id=validate_subject_id(actor_subject_id),
        occurred_at=now,
        correlation_id=validate_correlation_id(correlation_id),
        change_summary=change_summary,
        previous_revision=previous_revision,
        resulting_revision=resulting_revision,
    )
