from __future__ import annotations

from typing import Protocol

from creditos_proposal_intake.domain.entities import ProposalIntakeStatus


class ProposalIntakeStatusRepository(Protocol):
    def save_initial(self, status: ProposalIntakeStatus) -> None: ...

    def find(self, tenant_id: str, proposal_id: str) -> ProposalIntakeStatus | None: ...

    def delete(self, tenant_id: str, proposal_id: str) -> None: ...
