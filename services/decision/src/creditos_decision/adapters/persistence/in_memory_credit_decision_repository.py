from __future__ import annotations

from collections.abc import Callable
from threading import RLock

from creditos_decision.domain.entities.credit_decision import CreditDecision
from creditos_decision.domain.errors import PolicyValidationError


class InMemoryCreditDecisionRepository:
    def __init__(self) -> None:
        self._decisions: dict[tuple[str, str], CreditDecision] = {}
        self._proposal_index: dict[tuple[str, str], str] = {}
        self._lock = RLock()

    def save(
        self,
        decision: CreditDecision,
        *,
        before_commit: Callable[[], None] | None = None,
    ) -> None:
        key = _key(decision.tenant_id, decision.decision_id)
        proposal_key = _proposal_key(decision.tenant_id, decision.proposal_id)
        with self._lock:
            if key in self._decisions or proposal_key in self._proposal_index:
                raise PolicyValidationError(
                    "decisão duplicada",
                    code="duplicate_credit_decision",
                    field_path="decision_id",
                )
            if before_commit is not None:
                before_commit()
            self._decisions[key] = decision
            self._proposal_index[proposal_key] = decision.decision_id

    def get(self, *, tenant_id: str, decision_id: str) -> CreditDecision | None:
        with self._lock:
            return self._decisions.get(_key(tenant_id, decision_id))

    def get_by_proposal(self, *, tenant_id: str, proposal_id: str) -> CreditDecision | None:
        with self._lock:
            decision_id = self._proposal_index.get(_proposal_key(tenant_id, proposal_id))
            if decision_id is None:
                return None
            return self._decisions.get(_key(tenant_id, decision_id))


def _key(tenant_id: str, decision_id: str) -> tuple[str, str]:
    return (tenant_id, decision_id)


def _proposal_key(tenant_id: str, proposal_id: str) -> tuple[str, str]:
    return (tenant_id, proposal_id)
