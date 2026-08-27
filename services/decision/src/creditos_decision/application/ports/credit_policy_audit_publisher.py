from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class CreditPolicyAuditIntent:
    event_type: str
    tenant_id: str
    actor_subject_id: str
    policy_id: str
    policy_version_id: str
    correlation_id: str
    safe_details: dict[str, str]


@dataclass(frozen=True, slots=True)
class ReasonCodeCatalogAuditIntent:
    event_type: str
    tenant_id: str
    actor_subject_id: str
    catalog_id: str
    catalog_version_id: str
    correlation_id: str
    safe_details: dict[str, str]


class CreditPolicyAuditPublisher(Protocol):
    def publish(self, event: CreditPolicyAuditIntent | ReasonCodeCatalogAuditIntent) -> None: ...
