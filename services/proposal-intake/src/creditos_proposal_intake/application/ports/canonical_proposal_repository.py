from __future__ import annotations

from typing import Protocol

from creditos_proposal_intake.domain.entities import CanonicalProposal


class CanonicalProposalRepository(Protocol):
    def save(self, proposal: CanonicalProposal) -> None: ...

    def delete(self, proposal: CanonicalProposal) -> None: ...

    def get(self, tenant_id: str, external_proposal_id: str) -> CanonicalProposal | None: ...
