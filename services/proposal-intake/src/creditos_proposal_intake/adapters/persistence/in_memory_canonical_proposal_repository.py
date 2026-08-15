from __future__ import annotations

from threading import RLock

from creditos_proposal_intake.domain.entities import CanonicalProposal
from creditos_proposal_intake.domain.errors import ProposalValidationError


class InMemoryCanonicalProposalRepository:
    def __init__(self) -> None:
        self._proposals: dict[tuple[str, str], CanonicalProposal] = {}
        self._lock = RLock()

    def save(self, proposal: CanonicalProposal) -> None:
        key = (proposal.tenant_id, proposal.external_proposal_id)
        with self._lock:
            existing = self._proposals.get(key)
            if existing is not None:
                raise ProposalValidationError(
                    "proposta externa duplicada",
                    code="duplicate_external_proposal_id",
                    field_path="external_proposal_id",
                )
            self._proposals[key] = proposal

    def get(self, tenant_id: str, external_proposal_id: str) -> CanonicalProposal | None:
        with self._lock:
            return self._proposals.get((tenant_id, external_proposal_id))

    def list_all(self) -> list[CanonicalProposal]:
        with self._lock:
            return list(self._proposals.values())
