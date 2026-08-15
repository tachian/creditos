from __future__ import annotations

from creditos_proposal_intake.application.ports.canonical_proposal_repository import (
    CanonicalProposalRepository,
)
from creditos_proposal_intake.application.ports.idempotent_proposal_submission_repository import (
    IdempotentProposalSubmissionRepository,
)

__all__ = ["CanonicalProposalRepository", "IdempotentProposalSubmissionRepository"]
