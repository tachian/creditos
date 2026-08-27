from __future__ import annotations

from typing import Protocol

from creditos_decision.domain.entities import PolicySimulationResult


class PolicySimulationRepository(Protocol):
    def save(self, simulation: PolicySimulationResult) -> None: ...

    def delete(self, simulation: PolicySimulationResult) -> None: ...

    def get(self, *, tenant_id: str, simulation_id: str) -> PolicySimulationResult | None: ...

    def list_by_policy(
        self,
        *,
        tenant_id: str,
        policy_id: str,
        policy_version_id: str,
    ) -> tuple[PolicySimulationResult, ...]: ...
