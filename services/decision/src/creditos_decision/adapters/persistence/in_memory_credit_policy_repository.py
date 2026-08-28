from __future__ import annotations

from datetime import UTC, datetime
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

    def save_new_version(self, policy: CreditPolicy) -> None:
        key = _key(policy.tenant_id, policy.policy_id, policy.policy_version_id)
        with self._lock:
            if key in self._policies:
                raise PolicyValidationError(
                    "política duplicada",
                    code="duplicate_credit_policy",
                    field_path="policy_id",
                )
            if any(
                existing.tenant_id == policy.tenant_id
                and existing.policy_id == policy.policy_id
                and existing.version == policy.version
                for existing in self._policies.values()
            ):
                raise PolicyValidationError(
                    "versão de política duplicada",
                    code="duplicate_credit_policy_version",
                    field_path="version",
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

    def publish_if_no_window_conflict(
        self,
        policy: CreditPolicy,
        *,
        expected_revision: int,
    ) -> None:
        key = _key(policy.tenant_id, policy.policy_id, policy.policy_version_id)
        with self._lock:
            existing = self._policies.get(key)
            if existing is None:
                raise PolicyValidationError(
                    "política não encontrada",
                    code="credit_policy_not_found",
                    field_path="policy_id",
                )
            if existing.revision != expected_revision:
                raise PolicyConcurrencyError(
                    "revisão concorrente",
                    field_path="revision",
                    details={
                        "expected_revision": expected_revision,
                        "actual_revision": existing.revision,
                    },
                )
            for published_policy in self._policies.values():
                if published_policy.tenant_id != policy.tenant_id:
                    continue
                if published_policy.product_type != policy.product_type:
                    continue
                if published_policy.status != "published":
                    continue
                if published_policy.policy_version_id == policy.policy_version_id:
                    continue
                if _policy_windows_overlap(policy, published_policy):
                    raise PolicyValidationError(
                        "vigência conflitante",
                        code="conflicting_published_policy_window",
                        field_path="applicability",
                    )
            self._policies[key] = policy

    def delete(self, policy: CreditPolicy) -> None:
        key = _key(policy.tenant_id, policy.policy_id, policy.policy_version_id)
        with self._lock:
            self._policies.pop(key, None)

    def delete_if_current(self, policy: CreditPolicy, *, expected_revision: int) -> bool:
        key = _key(policy.tenant_id, policy.policy_id, policy.policy_version_id)
        with self._lock:
            existing = self._policies.get(key)
            if existing is None or existing.revision != expected_revision:
                return False
            del self._policies[key]
            return True

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

    def list_published_by_product(
        self,
        *,
        tenant_id: str,
        product_type: str,
    ) -> tuple[CreditPolicy, ...]:
        with self._lock:
            return tuple(
                policy
                for key, policy in self._policies.items()
                if key[0] == tenant_id
                and policy.product_type == product_type
                and policy.status == "published"
            )


def _key(tenant_id: str, policy_id: str, policy_version_id: str) -> tuple[str, str, str]:
    return (tenant_id, policy_id, policy_version_id)


def _policy_windows_overlap(candidate: CreditPolicy, existing: CreditPolicy) -> bool:
    if not _policy_channels_overlap(candidate, existing):
        return False
    candidate_start = candidate.applicability.starts_at
    existing_start = existing.applicability.starts_at
    if candidate_start is None or existing_start is None:
        return True
    candidate_end = candidate.applicability.ends_at
    existing_end = existing.applicability.ends_at
    return candidate_start < (existing_end or datetime.max.replace(tzinfo=UTC)) and (
        existing_start < (candidate_end or datetime.max.replace(tzinfo=UTC))
    )


def _policy_channels_overlap(candidate: CreditPolicy, existing: CreditPolicy) -> bool:
    candidate_channels = set(candidate.applicability.channels)
    existing_channels = set(existing.applicability.channels)
    return (
        not candidate_channels
        or not existing_channels
        or bool(candidate_channels & existing_channels)
    )
