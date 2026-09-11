from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType

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
from creditos_automated_review.domain.value_objects.review_output import (
    validate_review_output_reference,
)

_EXECUTION_STATUSES = frozenset({"completed", "blocked", "failed", "fallback"})
_FALLBACK_ACTIONS = frozenset({"continue_without_review", "request_more_data", "unable_to_decide"})


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
    output_validation_status: str = "accepted"
    accepted_output_counts_by_type: Mapping[str, int] = field(
        default_factory=lambda: MappingProxyType({})
    )
    blocked_output_counts_by_reason: Mapping[str, int] = field(
        default_factory=lambda: MappingProxyType({})
    )
    fallback_action: str | None = None
    fallback_reason_refs: tuple[str, ...] = ()
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
        output_validation_status = validate_review_technical_token(
            self.output_validation_status,
            field_path="output_validation_status",
        )
        if output_validation_status not in {"accepted", "blocked"}:
            raise AutomatedReviewValidationError(
                "status de validação de saída inválido",
                code="automated_review_invalid_output_validation_status",
                field_path="output_validation_status",
            )
        object.__setattr__(self, "output_validation_status", output_validation_status)
        object.__setattr__(
            self,
            "accepted_output_counts_by_type",
            MappingProxyType(
                _validate_output_counts(
                    self.accepted_output_counts_by_type,
                    field_path="accepted_output_counts_by_type",
                )
            ),
        )
        object.__setattr__(
            self,
            "blocked_output_counts_by_reason",
            MappingProxyType(
                _validate_output_counts(
                    self.blocked_output_counts_by_reason,
                    field_path="blocked_output_counts_by_reason",
                )
            ),
        )
        fallback_reason_refs = tuple(
            validate_review_output_reference(
                item,
                field_path=f"fallback_reason_refs[{index}]",
            )
            for index, item in enumerate(self.fallback_reason_refs)
        )
        object.__setattr__(self, "fallback_reason_refs", fallback_reason_refs)
        if self.fallback_action is not None:
            fallback_action = validate_review_technical_token(
                self.fallback_action,
                field_path="fallback_action",
            )
            if fallback_action not in _FALLBACK_ACTIONS:
                raise AutomatedReviewValidationError(
                    "ação de fallback consultivo inválida",
                    code="automated_review_invalid_fallback_action",
                    field_path="fallback_action",
                )
            object.__setattr__(self, "fallback_action", fallback_action)
        if status == "fallback":
            if self.fallback_action is None:
                raise AutomatedReviewValidationError(
                    "fallback consultivo exige ação configurada",
                    code="automated_review_missing_fallback_action",
                    field_path="fallback_action",
                )
            if not fallback_reason_refs:
                raise AutomatedReviewValidationError(
                    "fallback consultivo exige motivo técnico",
                    code="automated_review_missing_fallback_reason",
                    field_path="fallback_reason_refs",
                )
            if output_validation_status != "blocked":
                raise AutomatedReviewValidationError(
                    "fallback consultivo exige saída bloqueada",
                    code="automated_review_invalid_fallback_output_status",
                    field_path="output_validation_status",
                )
            if not self.limitation_refs:
                raise AutomatedReviewValidationError(
                    "fallback consultivo exige limitação auditável",
                    code="automated_review_missing_fallback_limitation",
                    field_path="limitation_refs",
                )
            if self.finding_refs:
                raise AutomatedReviewValidationError(
                    "fallback consultivo não pode carregar achados aceitos",
                    code="automated_review_fallback_with_accepted_findings",
                    field_path="finding_refs",
                )
            if any(count > 0 for count in self.accepted_output_counts_by_type.values()):
                raise AutomatedReviewValidationError(
                    "fallback consultivo não pode carregar contagens aceitas",
                    code="automated_review_fallback_with_accepted_counts",
                    field_path="accepted_output_counts_by_type",
                )
            if not self.blocked_output_counts_by_reason:
                raise AutomatedReviewValidationError(
                    "fallback consultivo exige contagem de bloqueio",
                    code="automated_review_missing_fallback_blocked_count",
                    field_path="blocked_output_counts_by_reason",
                )
            for reason_ref in fallback_reason_refs:
                if self.blocked_output_counts_by_reason.get(reason_ref, 0) < 1:
                    raise AutomatedReviewValidationError(
                        "fallback consultivo exige contagem para cada motivo",
                        code="automated_review_missing_fallback_reason_count",
                        field_path=f"blocked_output_counts_by_reason.{reason_ref}",
                    )
        elif self.fallback_action is not None or fallback_reason_refs:
            raise AutomatedReviewValidationError(
                "metadados de fallback só são permitidos para execução em fallback",
                code="automated_review_unexpected_fallback_metadata",
                field_path="fallback_action",
            )


def _persistable_input_field(field: MinimizedReviewInputField) -> MinimizedReviewInputField:
    return MinimizedReviewInputField(
        field_name=field.field_name,
        action=field.action,
        safe_value=None,
        reason=field.reason,
    )


def _validate_output_counts(value: Mapping[str, int], *, field_path: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for key, count in value.items():
        normalized_key = validate_review_technical_token(key, field_path=f"{field_path}.{key}")
        if type(count) is not int or count < 0:
            raise AutomatedReviewValidationError(
                "contagem de saída consultiva inválida",
                code="automated_review_invalid_output_count",
                field_path=f"{field_path}.{normalized_key}",
            )
        counts[normalized_key] = count
    return counts
