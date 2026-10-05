from __future__ import annotations

from threading import RLock

from creditos_decision.application.ports.public_proposal_status_repository import (
    PublicProposalStatusSnapshot,
)


class InMemoryPublicProposalStatusRepository:
    def __init__(self) -> None:
        self._statuses: dict[tuple[str, str], PublicProposalStatusSnapshot] = {}
        self._lock = RLock()

    def save(self, snapshot: PublicProposalStatusSnapshot) -> None:
        with self._lock:
            self._statuses[(snapshot.tenant_id, snapshot.proposal_id)] = snapshot

    def find(self, *, tenant_id: str, proposal_id: str) -> PublicProposalStatusSnapshot | None:
        with self._lock:
            return self._statuses.get((tenant_id, proposal_id))

    def list_all(self) -> list[PublicProposalStatusSnapshot]:
        with self._lock:
            return list(self._statuses.values())
