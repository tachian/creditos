from __future__ import annotations

import hmac
from hashlib import sha256

from creditos_audit_evidence.application.ports.audit_checkpoint_signer import (
    AuditCheckpointSignature,
)


class DeterministicAuditCheckpointSigner:
    def __init__(
        self,
        *,
        secret: str,
        key_ref: str = "test-audit-checkpoint-key-v1",
        algorithm: str = "hmac-sha256-test",
    ) -> None:
        self._secret = secret.encode("utf-8")
        self._key_ref = key_ref
        self._algorithm = algorithm

    def sign(self, payload: bytes) -> AuditCheckpointSignature:
        signature = hmac.new(self._secret, payload, sha256).hexdigest()
        return AuditCheckpointSignature(
            signature=signature,
            key_ref=self._key_ref,
            algorithm=self._algorithm,
        )

    def verify(
        self,
        payload: bytes,
        *,
        signature: str,
        key_ref: str,
        algorithm: str,
    ) -> bool:
        if key_ref != self._key_ref or algorithm != self._algorithm:
            return False
        expected_signature = hmac.new(self._secret, payload, sha256).hexdigest()
        return hmac.compare_digest(expected_signature, signature)
