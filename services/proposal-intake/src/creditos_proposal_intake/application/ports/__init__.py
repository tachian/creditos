from __future__ import annotations

from creditos_proposal_intake.application.ports.canonical_proposal_repository import (
    CanonicalProposalRepository,
)
from creditos_proposal_intake.application.ports.idempotent_proposal_submission_repository import (
    IdempotentProposalSubmissionRepository,
)
from creditos_proposal_intake.application.ports.proposal_intake_status_repository import (
    ProposalIntakeStatusRepository,
)
from creditos_proposal_intake.application.ports.proposal_outbox_repository import (
    ProposalOutboxRepository,
)

__all__ = [
    "CanonicalProposalRepository",
    "IdempotentProposalSubmissionRepository",
    "ProposalIntakeStatusRepository",
    "ProposalOutboxRepository",
]
