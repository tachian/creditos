from __future__ import annotations

from threading import RLock

from creditos_proposal_intake.domain.entities import (
    IdempotencyResolution,
    IdempotencyScope,
    IdempotentProposalSubmission,
)


class InMemoryIdempotentProposalSubmissionRepository:
    def __init__(self) -> None:
        self._submissions: dict[IdempotencyScope, IdempotentProposalSubmission] = {}
        self._lock = RLock()

    def find(
        self,
        scope: IdempotencyScope,
    ) -> IdempotentProposalSubmission | None:
        with self._lock:
            return self._submissions.get(scope)

    def submit_once(
        self,
        submission: IdempotentProposalSubmission,
    ) -> IdempotencyResolution:
        with self._lock:
            existing = self._submissions.get(submission.scope)
            if existing is None:
                self._submissions[submission.scope] = submission
                return IdempotencyResolution(status="created", submission=submission)
            if existing.proposal_fingerprint == submission.proposal_fingerprint:
                return IdempotencyResolution(status="replayed", submission=existing)
            return IdempotencyResolution(status="conflicted", submission=existing)

    def rollback(
        self,
        scope: IdempotencyScope,
        *,
        proposal_fingerprint: str,
    ) -> None:
        with self._lock:
            existing = self._submissions.get(scope)
            if existing is not None and existing.proposal_fingerprint == proposal_fingerprint:
                del self._submissions[scope]

    def list_all(self) -> list[IdempotentProposalSubmission]:
        with self._lock:
            return list(self._submissions.values())
