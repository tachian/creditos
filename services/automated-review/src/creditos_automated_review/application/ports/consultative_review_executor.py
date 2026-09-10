from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Protocol

from creditos_automated_review.domain.value_objects.review_execution import SafeInputValue


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


class ConsultativeReviewExecutor(Protocol):
    def execute(self, command: ConsultativeReviewExecutionInput) -> ConsultativeReviewOutput: ...
