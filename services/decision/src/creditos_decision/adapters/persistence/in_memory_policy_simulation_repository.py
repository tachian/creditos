from __future__ import annotations

from threading import RLock

from creditos_decision.domain.entities import PolicySimulationResult
from creditos_decision.domain.errors import PolicyValidationError


class InMemoryPolicySimulationRepository:
    def __init__(self) -> None:
        self._simulations: dict[tuple[str, str], PolicySimulationResult] = {}
        self._lock = RLock()

    def save(self, simulation: PolicySimulationResult) -> None:
        key = _key(simulation.tenant_id, simulation.simulation_id)
        with self._lock:
            if key in self._simulations:
                raise PolicyValidationError(
                    "simulação duplicada",
                    code="duplicate_policy_simulation",
                    field_path="simulation_id",
                )
            self._simulations[key] = simulation

    def delete(self, simulation: PolicySimulationResult) -> None:
        key = _key(simulation.tenant_id, simulation.simulation_id)
        with self._lock:
            self._simulations.pop(key, None)

    def get(self, *, tenant_id: str, simulation_id: str) -> PolicySimulationResult | None:
        with self._lock:
            return self._simulations.get(_key(tenant_id, simulation_id))

    def list_by_policy(
        self,
        *,
        tenant_id: str,
        policy_id: str,
        policy_version_id: str,
    ) -> tuple[PolicySimulationResult, ...]:
        with self._lock:
            return tuple(
                simulation
                for key, simulation in self._simulations.items()
                if key[0] == tenant_id
                and simulation.policy_id == policy_id
                and simulation.policy_version_id == policy_version_id
            )


def _key(tenant_id: str, simulation_id: str) -> tuple[str, str]:
    return (tenant_id, simulation_id)
