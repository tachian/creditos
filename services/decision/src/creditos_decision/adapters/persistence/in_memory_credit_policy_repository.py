from __future__ import annotations

from threading import RLock

from creditos_decision.domain.entities import CreditPolicy
from creditos_decision.domain.errors import PolicyConcurrencyError, PolicyValidationError


class InMemoryCreditPolicyRepository:
    def __init__(self) -> None:
        self._policies: dict[tuple[str, str, str], CreditPolicy] = {}
        self._lock = RLock()

    def save(self, policy: CreditPolicy) -> None:
        key = _key(policy.tenant_id, policy.policy_id, policy.policy_version_id)
        with self._lock:
            if key in self._policies:
                raise PolicyValidationError(
                    "política duplicada",
                    code="duplicate_credit_policy",
                    field_path="policy_id",
                )
            self._policies[key] = policy

    def update(self, policy: CreditPolicy, *, expected_revision: int | None = None) -> None:
        key = _key(policy.tenant_id, policy.policy_id, policy.policy_version_id)
        with self._lock:
            existing = self._policies.get(key)
            if existing is None:
                raise PolicyValidationError(
                    "política não encontrada",
                    code="credit_policy_not_found",
                    field_path="policy_id",
                )
            if expected_revision is not None and existing.revision != expected_revision:
                raise PolicyConcurrencyError(
                    "revisão concorrente",
                    field_path="revision",
                    details={
                        "expected_revision": expected_revision,
                        "actual_revision": existing.revision,
                    },
                )
            self._policies[key] = policy

    def delete(self, policy: CreditPolicy) -> None:
        key = _key(policy.tenant_id, policy.policy_id, policy.policy_version_id)
        with self._lock:
            self._policies.pop(key, None)

    def restore(self, policy: CreditPolicy) -> None:
        key = _key(policy.tenant_id, policy.policy_id, policy.policy_version_id)
        with self._lock:
            self._policies[key] = policy

    def restore_if_current(self, policy: CreditPolicy, *, expected_revision: int) -> bool:
        key = _key(policy.tenant_id, policy.policy_id, policy.policy_version_id)
        with self._lock:
            existing = self._policies.get(key)
            if existing is None or existing.revision != expected_revision:
                return False
            self._policies[key] = policy
            return True

    def next_version(self, *, tenant_id: str, policy_id: str) -> int:
        with self._lock:
            tenant_policy_versions = (
                policy.version
                for key, policy in self._policies.items()
                if key[0] == tenant_id and key[1] == policy_id
            )
            return max(tenant_policy_versions, default=0) + 1

    def get(
        self,
        *,
        tenant_id: str,
        policy_id: str,
        policy_version_id: str,
    ) -> CreditPolicy | None:
        with self._lock:
            return self._policies.get(_key(tenant_id, policy_id, policy_version_id))

    def list_by_tenant(self, *, tenant_id: str) -> tuple[CreditPolicy, ...]:
        with self._lock:
            return tuple(policy for key, policy in self._policies.items() if key[0] == tenant_id)


def _key(tenant_id: str, policy_id: str, policy_version_id: str) -> tuple[str, str, str]:
    return (tenant_id, policy_id, policy_version_id)
