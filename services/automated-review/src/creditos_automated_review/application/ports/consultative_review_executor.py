from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Protocol

from creditos_automated_review.domain.errors import AutomatedReviewValidationError
from creditos_automated_review.domain.value_objects.review_execution import (
    ReviewModelUsage,
    SafeInputValue,
)
from creditos_automated_review.domain.value_objects.review_output import ReviewOutputItem


@dataclass(frozen=True, slots=True)
class ConsultativeReviewExecutionInput:
    tenant_id: str
    execution_id: str
    proposal_id: str
    review_agent_config_id: str
    review_agent_config_version_id: str
    product_type: str
    channel: str
    review_purpose: str
    minimization_policy_ref: str
    prompt_fingerprint: str
    input_for_execution: MappingProxyType[str, SafeInputValue]


@dataclass(frozen=True, slots=True)
class ConsultativeReviewOutput:
    status: str = "completed"
    finding_refs: tuple[str, ...] = ()
    limitation_refs: tuple[str, ...] = ()
    output_items: tuple[ReviewOutputItem | Mapping[str, object], ...] = ()
    model_usage: ReviewModelUsage = field(default_factory=ReviewModelUsage)

    def __post_init__(self) -> None:
        if type(self.model_usage) is not ReviewModelUsage:
            raise AutomatedReviewValidationError(
                "uso/custo do modelo deve usar contrato tipado",
                code="automated_review_invalid_model_usage",
                field_path="model_usage",
            )


class ConsultativeReviewExecutor(Protocol):
    def execute(self, command: ConsultativeReviewExecutionInput) -> ConsultativeReviewOutput: ...
