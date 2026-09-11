from __future__ import annotations

from collections.abc import Callable
from threading import RLock

from creditos_automated_review.domain.entities import ConsultativeEvidence
from creditos_automated_review.domain.errors import AutomatedReviewConflictError


class InMemoryConsultativeEvidenceRepository:
    def __init__(self) -> None:
        self._evidence: dict[tuple[str, str], ConsultativeEvidence] = {}
        self._by_execution: dict[tuple[str, str], str] = {}
        self._by_proposal: dict[tuple[str, str], tuple[str, ...]] = {}
        self._lock = RLock()

    def create(
        self,
        evidence: ConsultativeEvidence,
        *,
        before_commit: Callable[[], None] | None = None,
    ) -> None:
        with self._lock:
            key = (evidence.tenant_id, evidence.consultative_evidence_id)
            execution_key = (evidence.tenant_id, evidence.execution_id)
            if key in self._evidence or execution_key in self._by_execution:
                raise AutomatedReviewConflictError(
                    "evidência consultiva já existe para execução",
                    code="automated_review_consultative_evidence_exists",
                    field_path="execution_id",
                )
            if before_commit is not None:
                before_commit()
            self._evidence[key] = evidence
            self._by_execution[execution_key] = evidence.consultative_evidence_id
            proposal_key = (evidence.tenant_id, evidence.proposal_id)
            self._by_proposal[proposal_key] = (
                *self._by_proposal.get(proposal_key, ()),
                evidence.consultative_evidence_id,
            )

    def get(
        self,
        *,
        tenant_id: str,
        consultative_evidence_id: str,
    ) -> ConsultativeEvidence | None:
        with self._lock:
            return self._evidence.get((tenant_id, consultative_evidence_id))

    def get_by_execution(
        self,
        *,
        tenant_id: str,
        execution_id: str,
    ) -> ConsultativeEvidence | None:
        with self._lock:
            evidence_id = self._by_execution.get((tenant_id, execution_id))
            if evidence_id is None:
                return None
            return self._evidence.get((tenant_id, evidence_id))

    def list_by_proposal(
        self,
        *,
        tenant_id: str,
        proposal_id: str,
    ) -> tuple[ConsultativeEvidence, ...]:
        with self._lock:
            evidence_ids = self._by_proposal.get((tenant_id, proposal_id), ())
            return tuple(
                evidence
                for evidence_id in evidence_ids
                if (evidence := self._evidence.get((tenant_id, evidence_id))) is not None
            )
