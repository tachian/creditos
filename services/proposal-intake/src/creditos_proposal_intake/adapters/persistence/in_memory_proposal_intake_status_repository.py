from __future__ import annotations

from threading import RLock

from creditos_proposal_intake.domain.entities import ProposalIntakeStatus
from creditos_proposal_intake.domain.errors import ProposalValidationError


class InMemoryProposalIntakeStatusRepository:
    def __init__(self) -> None:
        self._statuses: dict[tuple[str, str], ProposalIntakeStatus] = {}
        self._lock = RLock()

    def save_initial(self, status: ProposalIntakeStatus) -> None:
        key = (status.tenant_id, status.proposal_id)
        with self._lock:
            existing = self._statuses.get(key)
            if existing is not None:
                if existing == status:
                    return
                raise ProposalValidationError(
                    "status inicial duplicado",
                    code="duplicate_initial_status",
                    field_path="proposal_id",
                )
            self._statuses[key] = status

    def find(self, tenant_id: str, proposal_id: str) -> ProposalIntakeStatus | None:
        with self._lock:
            return self._statuses.get((tenant_id, proposal_id))

    def delete(self, tenant_id: str, proposal_id: str) -> None:
        with self._lock:
            self._statuses.pop((tenant_id, proposal_id), None)

    def list_all(self) -> list[ProposalIntakeStatus]:
        with self._lock:
            return list(self._statuses.values())
