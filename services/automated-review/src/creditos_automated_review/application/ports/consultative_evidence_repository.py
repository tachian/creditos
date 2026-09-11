from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from creditos_automated_review.domain.entities import ConsultativeEvidence


class ConsultativeEvidenceRepository(Protocol):
    def create(
        self,
        evidence: ConsultativeEvidence,
        *,
        before_commit: Callable[[], None] | None = None,
    ) -> None: ...

    def get(
        self,
        *,
        tenant_id: str,
        consultative_evidence_id: str,
    ) -> ConsultativeEvidence | None: ...

    def get_by_execution(
        self,
        *,
        tenant_id: str,
        execution_id: str,
    ) -> ConsultativeEvidence | None: ...

    def list_by_proposal(
        self,
        *,
        tenant_id: str,
        proposal_id: str,
    ) -> tuple[ConsultativeEvidence, ...]: ...
