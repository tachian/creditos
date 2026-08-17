from __future__ import annotations

from typing import Protocol

from creditos_proposal_intake.domain.entities import ProposalOutboxMessage


class ProposalOutboxRepository(Protocol):
    def save_pending(self, message: ProposalOutboxMessage) -> None: ...

    def find_by_deduplication_key(
        self,
        tenant_id: str,
        deduplication_key: str,
    ) -> ProposalOutboxMessage | None: ...

    def delete(self, tenant_id: str, deduplication_key: str) -> None: ...
