from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class AutomatedReviewExecutionAuditIntent:
    event_type: str
    tenant_id: str
    actor_subject_id: str
    execution_id: str
    proposal_id: str
    review_agent_config_id: str
    review_agent_config_version_id: str
    correlation_id: str
    trace_id: str | None
    occurred_at: str
    safe_details: dict[str, str]


class AutomatedReviewExecutionAuditPublisher(Protocol):
    def publish(self, event: AutomatedReviewExecutionAuditIntent) -> None: ...
