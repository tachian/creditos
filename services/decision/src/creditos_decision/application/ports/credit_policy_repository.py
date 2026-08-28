from __future__ import annotations

from typing import Protocol

from creditos_decision.domain.entities import CreditPolicy


class CreditPolicyRepository(Protocol):
    def save(self, policy: CreditPolicy) -> None: ...

    def save_new_version(self, policy: CreditPolicy) -> None: ...

    def update(self, policy: CreditPolicy, *, expected_revision: int | None = None) -> None: ...

    def publish_if_no_window_conflict(
        self,
        policy: CreditPolicy,
        *,
        expected_revision: int,
    ) -> None: ...

    def delete(self, policy: CreditPolicy) -> None: ...

    def delete_if_current(self, policy: CreditPolicy, *, expected_revision: int) -> bool: ...

    def restore(self, policy: CreditPolicy) -> None: ...

    def restore_if_current(self, policy: CreditPolicy, *, expected_revision: int) -> bool: ...

    def next_version(self, *, tenant_id: str, policy_id: str) -> int: ...

    def get(
        self,
        *,
        tenant_id: str,
        policy_id: str,
        policy_version_id: str,
    ) -> CreditPolicy | None: ...

    def list_by_tenant(self, *, tenant_id: str) -> tuple[CreditPolicy, ...]: ...

    def list_published_by_product(
        self,
        *,
        tenant_id: str,
        product_type: str,
    ) -> tuple[CreditPolicy, ...]: ...
