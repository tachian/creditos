from __future__ import annotations

from threading import RLock

from creditos_proposal_intake.domain.entities import ProposalOutboxMessage
from creditos_proposal_intake.domain.errors import ProposalValidationError


class InMemoryProposalOutboxRepository:
    def __init__(self) -> None:
        self._messages: dict[tuple[str, str], ProposalOutboxMessage] = {}
        self._lock = RLock()

    def save_pending(self, message: ProposalOutboxMessage) -> None:
        key = (message.tenant_id, message.deduplication_key)
        with self._lock:
            existing = self._messages.get(key)
            if existing is not None:
                if existing == message:
                    return
                raise ProposalValidationError(
                    "mensagem de outbox duplicada",
                    code="duplicate_outbox_message",
                    field_path="deduplication_key",
                )
            self._messages[key] = message

    def find_by_deduplication_key(
        self,
        tenant_id: str,
        deduplication_key: str,
    ) -> ProposalOutboxMessage | None:
        with self._lock:
            return self._messages.get((tenant_id, deduplication_key))

    def delete(self, tenant_id: str, deduplication_key: str) -> None:
        with self._lock:
            self._messages.pop((tenant_id, deduplication_key), None)

    def list_all(self) -> list[ProposalOutboxMessage]:
        with self._lock:
            return list(self._messages.values())
