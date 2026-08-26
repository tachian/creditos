from __future__ import annotations

from typing import Protocol

from creditos_decision.domain.entities import CreditPolicy


class CreditPolicyRepository(Protocol):
    def save(self, policy: CreditPolicy) -> None: ...

    def update(self, policy: CreditPolicy, *, expected_revision: int | None = None) -> None: ...

    def delete(self, policy: CreditPolicy) -> None: ...

    def restore(self, policy: CreditPolicy) -> None: ...

    def get(
        self,
        *,
        tenant_id: str,
        policy_id: str,
        policy_version_id: str,
    ) -> CreditPolicy | None: ...

    def list_by_tenant(self, *, tenant_id: str) -> tuple[CreditPolicy, ...]: ...
