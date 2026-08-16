from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal

IdempotencyResolutionStatus = Literal["created", "replayed", "conflicted"]


@dataclass(frozen=True, slots=True)
class IdempotencyScope:
    tenant_id: str
    technical_client_id: str
    idempotency_key: str


@dataclass(frozen=True, slots=True)
class IdempotentProposalSubmission:
    scope: IdempotencyScope
    external_proposal_id: str
    proposal_fingerprint: str
    result: MappingProxyType[str, str]

    @property
    def tenant_id(self) -> str:
        return self.scope.tenant_id

    @property
    def technical_client_id(self) -> str:
        return self.scope.technical_client_id

    @property
    def idempotency_key(self) -> str:
        return self.scope.idempotency_key


@dataclass(frozen=True, slots=True)
class IdempotencyResolution:
    status: IdempotencyResolutionStatus
    submission: IdempotentProposalSubmission

    @property
    def created(self) -> bool:
        return self.status == "created"

    @property
    def replayed(self) -> bool:
        return self.status == "replayed"

    @property
    def conflicted(self) -> bool:
        return self.status == "conflicted"
