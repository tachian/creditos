from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from creditos_automated_review.domain.entities.review_agent_configuration import (
    ReviewAgentConfiguration,
)
from creditos_automated_review.domain.errors import AutomatedReviewValidationError
from creditos_automated_review.domain.value_objects.review_agent_config import (
    validate_agent_version,
    validate_review_agent_config_id,
    validate_review_agent_config_version_id,
    validate_subject_id,
    validate_tenant_id,
)
from creditos_automated_review.domain.value_objects.review_execution import (
    InputMinimizationPlan,
    MinimizedReviewInputField,
    ReviewInputCandidate,
    validate_non_sensitive_execution_reference,
    validate_prompt_fingerprint,
    validate_review_technical_token,
)

_EXECUTION_STATUSES = frozenset({"completed", "blocked", "failed", "fallback"})


@dataclass(frozen=True, slots=True)
class AutomatedReviewExecutionRequest:
    execution_id: str
    proposal_id: str
    product_type: str
    channel: str
    review_purpose: str
    candidate_inputs: tuple[ReviewInputCandidate, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "execution_id",
            validate_non_sensitive_execution_reference(
                validate_agent_version(self.execution_id, field_path="execution_id"),
                field_path="execution_id",
            ),
        )
        object.__setattr__(
            self,
            "proposal_id",
            validate_non_sensitive_execution_reference(
                validate_agent_version(self.proposal_id, field_path="proposal_id"),
                field_path="proposal_id",
            ),
        )
        object.__setattr__(
            self,
            "product_type",
            validate_agent_version(self.product_type, field_path="product_type"),
        )
        object.__setattr__(
            self,
            "channel",
            validate_agent_version(self.channel, field_path="channel"),
        )
        object.__setattr__(
            self,
            "review_purpose",
            validate_agent_version(self.review_purpose, field_path="review_purpose"),
        )
        candidate_inputs = tuple(self.candidate_inputs)
        if not candidate_inputs:
            raise AutomatedReviewValidationError(
                "entrada consultiva obrigatória",
                code="automated_review_empty_candidate_inputs",
                field_path="candidate_inputs",
            )
        names = [candidate.field_name for candidate in candidate_inputs]
        if len(set(names)) != len(names):
            raise AutomatedReviewValidationError(
                "campo duplicado na entrada consultiva",
                code="automated_review_duplicate_input_field",
                field_path="candidate_inputs",
            )
        object.__setattr__(self, "candidate_inputs", candidate_inputs)

    @classmethod
    def create(
        cls,
        *,
        execution_id: str,
        proposal_id: str,
        product_type: str,
        channel: str,
        review_purpose: str,
        candidate_inputs: tuple[ReviewInputCandidate, ...],
    ) -> AutomatedReviewExecutionRequest:
        return cls(
            execution_id=execution_id,
            proposal_id=proposal_id,
            product_type=product_type,
            channel=channel,
            review_purpose=review_purpose,
            candidate_inputs=candidate_inputs,
        )

    def build_minimization_plan(
        self,
        config: ReviewAgentConfiguration,
    ) -> InputMinimizationPlan:
        if not config.is_referenceable_for_review:
            raise AutomatedReviewValidationError(
                "configuração não publicada não pode executar revisão",
                code="automated_review_config_not_referenceable",
                field_path="review_agent_config_version_id",
            )
        if self.product_type != config.product_type:
            raise AutomatedReviewValidationError(
                "produto incompatível com configuração de revisão",
                code="automated_review_execution_scope_mismatch",
                field_path="product_type",
            )
        if self.channel not in config.scope.channels:
            raise AutomatedReviewValidationError(
                "canal incompatível com configuração de revisão",
                code="automated_review_execution_scope_mismatch",
                field_path="channel",
            )
        if self.review_purpose not in config.scope.review_purposes:
            raise AutomatedReviewValidationError(
                "propósito incompatível com configuração de revisão",
                code="automated_review_execution_scope_mismatch",
                field_path="review_purpose",
            )
        return InputMinimizationPlan.create(
            policy_ref=config.prompt.prompt_version,
            prompt_fingerprint=config.prompt.prompt_fingerprint,
            allowed_fields=config.prompt.input_allowlist,
            candidates=self.candidate_inputs,
        )


@dataclass(frozen=True, slots=True)
class AutomatedReviewExecutionResult:
    execution_id: str
    tenant_id: str
    proposal_id: str
    review_agent_config_id: str
    review_agent_config_version_id: str
    product_type: str
    channel: str
    review_purpose: str
    minimization_policy_ref: str
    prompt_fingerprint: str
    input_fields: tuple[MinimizedReviewInputField, ...]
    occurred_at: datetime
    classification: str = "consultative"
    status: str = "completed"
    finding_refs: tuple[str, ...] = ()
    limitation_refs: tuple[str, ...] = ()
    final_decision: str | None = None
    approved_terms: str | None = None
    external_actions: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "execution_id",
            validate_non_sensitive_execution_reference(
                validate_agent_version(self.execution_id, field_path="execution_id"),
                field_path="execution_id",
            ),
        )
        object.__setattr__(self, "tenant_id", validate_tenant_id(self.tenant_id))
        object.__setattr__(
            self,
            "proposal_id",
            validate_non_sensitive_execution_reference(
                validate_agent_version(self.proposal_id, field_path="proposal_id"),
                field_path="proposal_id",
            ),
        )
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
        for field_name in ("product_type", "channel", "review_purpose"):
            object.__setattr__(
                self,
                field_name,
                validate_agent_version(getattr(self, field_name), field_path=field_name),
            )
        object.__setattr__(
            self,
            "minimization_policy_ref",
            validate_agent_version(
                self.minimization_policy_ref,
                field_path="minimization_policy_ref",
            ),
        )
        object.__setattr__(
            self,
            "prompt_fingerprint",
            validate_prompt_fingerprint(self.prompt_fingerprint),
        )
        if self.occurred_at.tzinfo is None or self.occurred_at.utcoffset() is None:
            raise AutomatedReviewValidationError(
                "timestamp de execução deve possuir timezone",
                code="automated_review_invalid_execution_timestamp",
                field_path="occurred_at",
            )
        if self.classification != "consultative":
            raise AutomatedReviewValidationError(
                "execução automatizada deve ser consultiva",
                code="automated_review_non_consultative_execution",
                field_path="classification",
            )
        status = validate_review_technical_token(self.status, field_path="status")
        if status not in _EXECUTION_STATUSES:
            raise AutomatedReviewValidationError(
                "status de execução consultiva inválido",
                code="automated_review_invalid_execution_status",
                field_path="status",
            )
        object.__setattr__(self, "status", status)
        if (
            self.final_decision is not None
            or self.approved_terms is not None
            or self.external_actions
        ):
            raise AutomatedReviewValidationError(
                "execução consultiva não pode carregar decisão final ou ação externa",
                code="automated_review_autonomous_execution_output",
                field_path="execution_result",
            )
        object.__setattr__(
            self,
            "input_fields",
            tuple(_persistable_input_field(field) for field in self.input_fields),
        )
        object.__setattr__(
            self,
            "finding_refs",
            tuple(validate_subject_id(item) for item in self.finding_refs),
        )
        object.__setattr__(
            self,
            "limitation_refs",
            tuple(validate_subject_id(item) for item in self.limitation_refs),
        )


def _persistable_input_field(field: MinimizedReviewInputField) -> MinimizedReviewInputField:
    return MinimizedReviewInputField(
        field_name=field.field_name,
        action=field.action,
        safe_value=None,
        reason=field.reason,
    )
