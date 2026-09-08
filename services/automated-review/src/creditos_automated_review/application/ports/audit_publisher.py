from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class AutomatedReviewAuditIntent:
    event_type: str
    tenant_id: str
    actor_subject_id: str
    review_agent_config_id: str
    review_agent_config_version_id: str
    correlation_id: str
    occurred_at: str
    change_summary: str
    previous_revision: int
    resulting_revision: int
    safe_details: dict[str, str]


class AutomatedReviewAuditPublisher(Protocol):
    def publish(self, event: AutomatedReviewAuditIntent) -> None: ...
