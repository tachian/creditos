from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol

from creditos_decision.domain.value_objects.credit_decision import validate_proposal_id
from creditos_decision.domain.value_objects.policy import (
    PolicyApplicability,
    parse_product_type,
    validate_tenant_id,
)

PublicProposalStatusValue = Literal["submitted", "processing"]
PUBLIC_PROPOSAL_STATUS_VALUES = frozenset({"submitted", "processing"})


@dataclass(frozen=True, slots=True)
class PublicProposalStatusSnapshot:
    tenant_id: str
    proposal_id: str
    status: PublicProposalStatusValue
    schema_version: str
    product_type: str
    channel: str
    occurred_at: datetime

    def __post_init__(self) -> None:
        if self.status not in PUBLIC_PROPOSAL_STATUS_VALUES:
            raise ValueError("status público de proposta inválido")
        if not self.schema_version.strip():
            raise ValueError("schema_version obrigatório")
        object.__setattr__(self, "tenant_id", validate_tenant_id(self.tenant_id))
        object.__setattr__(self, "proposal_id", validate_proposal_id(self.proposal_id))
        object.__setattr__(self, "product_type", parse_product_type(self.product_type))
        object.__setattr__(
            self,
            "channel",
            PolicyApplicability.create(channels=(self.channel,)).channels[0],
        )


class PublicProposalStatusRepository(Protocol):
    def find(self, *, tenant_id: str, proposal_id: str) -> PublicProposalStatusSnapshot | None: ...
