from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

ProposalIntakeStatusValue = Literal["submitted"]


@dataclass(frozen=True, slots=True)
class ProposalIntakeStatus:
    tenant_id: str
    proposal_id: str
    external_proposal_id: str
    status: ProposalIntakeStatusValue
    schema_version: str
    product_type: str
    channel: str
    occurred_at: datetime
    reason: str = "proposal_submitted"
