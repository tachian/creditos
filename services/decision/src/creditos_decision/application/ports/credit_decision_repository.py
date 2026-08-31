from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from creditos_decision.domain.entities.credit_decision import CreditDecision


class CreditDecisionRepository(Protocol):
    def save(
        self,
        decision: CreditDecision,
        *,
        before_commit: Callable[[], None] | None = None,
    ) -> None: ...

    def get(self, *, tenant_id: str, decision_id: str) -> CreditDecision | None: ...

    def get_by_proposal(self, *, tenant_id: str, proposal_id: str) -> CreditDecision | None: ...
