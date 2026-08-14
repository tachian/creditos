from __future__ import annotations

from creditos_proposal_intake.domain.entities import CanonicalProposal


class InMemoryCanonicalProposalRepository:
    def __init__(self) -> None:
        self._proposals: dict[tuple[str, str], CanonicalProposal] = {}

    def save(self, proposal: CanonicalProposal) -> None:
        self._proposals[(proposal.tenant_id, proposal.external_proposal_id)] = proposal

    def get(self, tenant_id: str, external_proposal_id: str) -> CanonicalProposal | None:
        return self._proposals.get((tenant_id, external_proposal_id))

    def list_all(self) -> list[CanonicalProposal]:
        return list(self._proposals.values())
