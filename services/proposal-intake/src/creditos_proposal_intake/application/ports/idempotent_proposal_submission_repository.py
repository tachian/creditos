from __future__ import annotations

from typing import Protocol

from creditos_proposal_intake.domain.entities import (
    IdempotencyResolution,
    IdempotencyScope,
    IdempotentProposalSubmission,
)


class IdempotentProposalSubmissionRepository(Protocol):
    def submit_once(
        self,
        submission: IdempotentProposalSubmission,
    ) -> IdempotencyResolution: ...

    def rollback(
        self,
        scope: IdempotencyScope,
        *,
        proposal_fingerprint: str,
    ) -> None: ...
