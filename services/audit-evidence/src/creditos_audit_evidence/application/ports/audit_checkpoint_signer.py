from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class AuditCheckpointSignature:
    signature: str
    key_ref: str
    algorithm: str


class AuditCheckpointSigner(Protocol):
    def sign(self, payload: bytes) -> AuditCheckpointSignature: ...

    def verify(
        self,
        payload: bytes,
        *,
        signature: str,
        key_ref: str,
        algorithm: str,
    ) -> bool: ...
