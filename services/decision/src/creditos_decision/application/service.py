from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from time import perf_counter
from typing import Any

from creditos_observability.context import ObservabilityContext
from creditos_observability.logging import build_structured_log
from creditos_security import PropagatedContext

from creditos_decision.application.ports import (
    CreditPolicyAuditIntent,
    CreditPolicyAuditPublisher,
    CreditPolicyRepository,
    PolicySimulationAuditIntent,
    PolicySimulationRepository,
    ReasonCodeCatalogAuditIntent,
    ReasonCodeCatalogRepository,
)
from creditos_decision.domain.entities import (
    CreditPolicy,
    PolicySimulation,
    PolicySimulationResult,
    ReasonCodeCatalog,
)
from creditos_decision.domain.errors import (
    PolicyNotFoundError,
    PolicySimulationNotFoundError,
    PolicyTenantContextError,
    PolicyValidationError,
    ReasonCodeCatalogNotFoundError,
)
from creditos_decision.domain.value_objects import (
    ExplainableFactor,
    PolicyApplicability,
    PolicyCriterion,
    PolicyLimit,
    PolicyRule,
    PolicySimulationInputCase,
    ReasonCode,
    validate_correlation_id,
    validate_policy_id,
    validate_policy_simulation_id,
    validate_policy_version_id,
    validate_reason_code_catalog_id,
    validate_reason_code_catalog_version_id,
)

SERVICE_NAME = "decision"
SERVICE_VERSION = "0.1.0"
CONTRACT = "decision-credit-policy-application"
CONTRACT_VERSION = "v1"


@dataclass(frozen=True, slots=True)
class CreateCreditPolicyDraftCommand:
    policy_id: str
    policy_version_id: str
    owner_subject_id: str
    product_type: str
    change_summary: str
    applicability: PolicyApplicability
    rules: tuple[PolicyRule, ...]
    criteria: tuple[PolicyCriterion, ...]
    limits: tuple[PolicyLimit, ...]
    reason_code_catalog_id: str
    reason_code_catalog_version_id: str
    actor_subject_id: str = ""


@dataclass(frozen=True, slots=True)
class UpdateCreditPolicyDraftCommand:
    policy_id: str
    policy_version_id: str
    change_summary: str
    rules: tuple[PolicyRule, ...]
    criteria: tuple[PolicyCriterion, ...]
    limits: tuple[PolicyLimit, ...]
    applicability: PolicyApplicability
    reason_code_catalog_id: str
    reason_code_catalog_version_id: str
    owner_subject_id: str | None = None
    product_type: str | None = None
    actor_subject_id: str = ""


@dataclass(frozen=True, slots=True)
class CreateReasonCodeCatalogDraftCommand:
    catalog_id: str
    catalog_version_id: str
    owner_subject_id: str
    product_type: str
    change_summary: str
    reason_codes: tuple[ReasonCode, ...]
    explainable_factors: tuple[ExplainableFactor, ...]
    actor_subject_id: str = ""


@dataclass(frozen=True, slots=True)
class UpdateReasonCodeCatalogDraftCommand:
    catalog_id: str
    catalog_version_id: str
    change_summary: str
    reason_codes: tuple[ReasonCode, ...]
    explainable_factors: tuple[ExplainableFactor, ...]
    owner_subject_id: str | None = None
    product_type: str | None = None
    actor_subject_id: str = ""


@dataclass(frozen=True, slots=True)
class CreateReasonCodeCatalogVersionCommand:
    catalog_id: str
    current_catalog_version_id: str
    new_catalog_version_id: str
    change_summary: str
    reason_codes: tuple[ReasonCode, ...]
    explainable_factors: tuple[ExplainableFactor, ...]
    owner_subject_id: str | None = None
    product_type: str | None = None
    actor_subject_id: str = ""


@dataclass(frozen=True, slots=True)
class RunPolicySimulationCommand:
    simulation_id: str
    policy_id: str
    policy_version_id: str
    cases: tuple[PolicySimulationInputCase, ...]
    actor_subject_id: str = ""


@dataclass(frozen=True, slots=True)
class GetPolicySimulationCommand:
    simulation_id: str


@dataclass(frozen=True, slots=True)
class CreditPolicyApplicationResult:
    policy: CreditPolicy
    logs: tuple[dict[str, Any], ...]


@dataclass(frozen=True, slots=True)
class ReasonCodeCatalogApplicationResult:
    catalog: ReasonCodeCatalog
    logs: tuple[dict[str, Any], ...]


@dataclass(frozen=True, slots=True)
class PolicySimulationApplicationResult:
    simulation: PolicySimulationResult
    logs: tuple[dict[str, Any], ...]


@dataclass(frozen=True, slots=True)
class _PolicyOperationContext:
    tenant_id: str
    actor_subject_id: str


class DecisionApplicationService:
    def __init__(
        self,
        *,
        repository: CreditPolicyRepository,
        audit_publisher: CreditPolicyAuditPublisher,
        environment: str,
        reason_code_catalog_repository: ReasonCodeCatalogRepository | None = None,
        policy_simulation_repository: PolicySimulationRepository | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._reason_code_catalog_repository = reason_code_catalog_repository
        self._policy_simulation_repository = policy_simulation_repository
        self._audit_publisher = audit_publisher
        self._environment = environment
        self._clock = clock or (lambda: datetime.now(UTC))
        self._logged_events: list[dict[str, Any]] = []

    @property
    def logged_events(self) -> tuple[dict[str, Any], ...]:
        return tuple(self._logged_events)

    def create_policy_draft(
        self,
        command: CreateCreditPolicyDraftCommand,
        *,
        context: ObservabilityContext,
        trusted_context: PropagatedContext,
    ) -> CreditPolicyApplicationResult:
        started_at = perf_counter()
        persisted_policy: CreditPolicy | None = None
        try:
            operation_context = _require_policy_context(
                context=context,
                trusted_context=trusted_context,
                required_scope="policy:write",
            )
            now = self._clock()
            policy = CreditPolicy.create_draft(
                policy_id=command.policy_id,
                policy_version_id=command.policy_version_id,
                tenant_id=operation_context.tenant_id,
                owner_subject_id=command.owner_subject_id,
                product_type=command.product_type,
                reason_code_catalog_id=command.reason_code_catalog_id,
                reason_code_catalog_version_id=command.reason_code_catalog_version_id,
                applicability=command.applicability,
                rules=command.rules,
                criteria=command.criteria,
                limits=command.limits,
                now=now,
                actor_subject_id=operation_context.actor_subject_id,
                correlation_id=context.correlation_id,
                change_summary=command.change_summary,
                version=self._repository.next_version(
                    tenant_id=operation_context.tenant_id,
                    policy_id=command.policy_id,
                ),
            )
            self._validate_policy_reason_code_refs(
                command=command,
                tenant_id=operation_context.tenant_id,
                policy=policy,
            )
            self._repository.save(policy)
            persisted_policy = policy
            try:
                self._publish_audit_intent(
                    policy=policy,
                    event_type="credit_policy.created",
                    actor_subject_id=operation_context.actor_subject_id,
                    correlation_id=context.correlation_id,
                    safe_details={
                        "change_summary": command.change_summary,
                        "product_type": policy.product_type,
                        "status": policy.status,
                    },
                )
            except Exception:
                self._repository.delete(policy)
                persisted_policy = None
                raise
            log = self._log_operation(
                context=context,
                operation="credit_policy.create_draft",
                status="accepted",
                duration_ms=_duration_ms(started_at),
                payload=command,
                extra={
                    "policy_id": policy.policy_id,
                    "policy_version_id": policy.policy_version_id,
                    "product_type": policy.product_type,
                    "status": policy.status,
                },
            )
            return CreditPolicyApplicationResult(policy=policy, logs=(log,))
        except Exception as error:
            self._publish_rejection_intent(
                operation="credit_policy.create_draft",
                command=command,
                context=context,
                trusted_context=trusted_context,
                error=error,
                skip_policy_id=(
                    persisted_policy.policy_id if persisted_policy is not None else None
                ),
            )
            self._log_operation(
                context=context,
                operation="credit_policy.create_draft",
                status="rejected",
                duration_ms=_duration_ms(started_at),
                payload=command,
                error_type=type(error).__name__,
                extra={"error_code": getattr(error, "code", type(error).__name__)},
            )
            raise

    def update_policy_draft(
        self,
        command: UpdateCreditPolicyDraftCommand,
        *,
        context: ObservabilityContext,
        trusted_context: PropagatedContext,
    ) -> CreditPolicyApplicationResult:
        started_at = perf_counter()
        existing_policy: CreditPolicy | None = None
        try:
            operation_context = _require_policy_context(
                context=context,
                trusted_context=trusted_context,
                required_scope="policy:write",
            )
            existing_policy = self._repository.get(
                tenant_id=operation_context.tenant_id,
                policy_id=command.policy_id,
                policy_version_id=command.policy_version_id,
            )
            if existing_policy is None:
                raise PolicyNotFoundError()
            updated_policy = existing_policy.update_draft(
                rules=command.rules,
                criteria=command.criteria,
                limits=command.limits,
                applicability=command.applicability,
                now=self._clock(),
                actor_subject_id=operation_context.actor_subject_id,
                correlation_id=context.correlation_id,
                change_summary=command.change_summary,
                reason_code_catalog_id=command.reason_code_catalog_id,
                reason_code_catalog_version_id=command.reason_code_catalog_version_id,
                owner_subject_id=command.owner_subject_id,
                product_type=command.product_type,
            )
            self._validate_policy_reason_code_refs(
                command=command,
                tenant_id=operation_context.tenant_id,
                policy=updated_policy,
            )
            self._repository.update(updated_policy, expected_revision=existing_policy.revision)
            try:
                self._publish_audit_intent(
                    policy=updated_policy,
                    event_type="credit_policy.updated",
                    actor_subject_id=operation_context.actor_subject_id,
                    correlation_id=context.correlation_id,
                    safe_details={
                        "change_summary": command.change_summary,
                        "product_type": updated_policy.product_type,
                        "revision": str(updated_policy.revision),
                        "status": updated_policy.status,
                    },
                )
            except Exception:
                self._repository.restore_if_current(
                    existing_policy,
                    expected_revision=updated_policy.revision,
                )
                raise
            log = self._log_operation(
                context=context,
                operation="credit_policy.update_draft",
                status="accepted",
                duration_ms=_duration_ms(started_at),
                payload=command,
                extra={
                    "policy_id": updated_policy.policy_id,
                    "policy_version_id": updated_policy.policy_version_id,
                    "product_type": updated_policy.product_type,
                    "revision": updated_policy.revision,
                    "status": updated_policy.status,
                },
            )
            return CreditPolicyApplicationResult(policy=updated_policy, logs=(log,))
        except Exception as error:
            self._publish_rejection_intent(
                operation="credit_policy.update_draft",
                command=command,
                context=context,
                trusted_context=trusted_context,
                error=error,
            )
            self._log_operation(
                context=context,
                operation="credit_policy.update_draft",
                status="rejected",
                duration_ms=_duration_ms(started_at),
                payload=command,
                error_type=type(error).__name__,
                extra={"error_code": getattr(error, "code", type(error).__name__)},
            )
            raise

    def get_policy(
        self,
        *,
        policy_id: str,
        policy_version_id: str,
        context: ObservabilityContext,
        trusted_context: PropagatedContext,
    ) -> CreditPolicy:
        try:
            operation_context = _require_policy_context(
                context=context,
                trusted_context=trusted_context,
                required_scope="policy:read",
            )
            policy = self._repository.get(
                tenant_id=operation_context.tenant_id,
                policy_id=policy_id,
                policy_version_id=policy_version_id,
            )
            if policy is None:
                raise PolicyNotFoundError()
            return policy
        except Exception as error:
            self._publish_rejection_intent(
                operation="credit_policy.get",
                command=_PolicyLookupCommand(
                    policy_id=policy_id,
                    policy_version_id=policy_version_id,
                ),
                context=context,
                trusted_context=trusted_context,
                error=error,
            )
            raise

    def run_policy_simulation(
        self,
        command: RunPolicySimulationCommand,
        *,
        context: ObservabilityContext,
        trusted_context: PropagatedContext,
    ) -> PolicySimulationApplicationResult:
        started_at = perf_counter()
        persisted_simulation: PolicySimulationResult | None = None
        try:
            operation_context = _require_policy_context(
                context=context,
                trusted_context=trusted_context,
                required_scope="policy:write",
            )
            policy = self._repository.get(
                tenant_id=operation_context.tenant_id,
                policy_id=command.policy_id,
                policy_version_id=command.policy_version_id,
            )
            if policy is None:
                raise PolicyNotFoundError()
            catalog = self._require_reason_code_catalog_repository().get(
                tenant_id=operation_context.tenant_id,
                catalog_id=policy.reason_code_catalog_id,
                catalog_version_id=policy.reason_code_catalog_version_id,
            )
            if catalog is None or catalog.product_type != policy.product_type:
                raise ReasonCodeCatalogNotFoundError()
            simulation = PolicySimulation.run(
                simulation_id=command.simulation_id,
                policy=policy,
                catalog=catalog,
                cases=tuple(command.cases),
                correlation_id=context.correlation_id,
                now=self._clock(),
            )
            simulation_repository = self._require_policy_simulation_repository()
            simulation_repository.save(simulation)
            persisted_simulation = simulation
            try:
                self._publish_policy_simulation_audit_intent(
                    simulation=simulation,
                    event_type="policy_simulation.completed",
                    actor_subject_id=operation_context.actor_subject_id,
                    correlation_id=context.correlation_id,
                )
            except Exception:
                simulation_repository.delete(simulation)
                persisted_simulation = None
                raise
            log = self._log_operation(
                context=context,
                operation="policy_simulation.run",
                status="accepted",
                duration_ms=_duration_ms(started_at),
                payload=command,
                extra={
                    "simulation_id": simulation.simulation_id,
                    "policy_id": simulation.policy_id,
                    "policy_version_id": simulation.policy_version_id,
                    "status": simulation.status,
                    "case_count": simulation.summary.total_cases,
                    "issue_count": simulation.summary.issue_count,
                    "non_production": simulation.non_production,
                },
            )
            return PolicySimulationApplicationResult(simulation=simulation, logs=(log,))
        except Exception as error:
            self._publish_policy_simulation_rejection_intent(
                operation="policy_simulation.run",
                command=command,
                context=context,
                trusted_context=trusted_context,
                error=error,
                skip_simulation_id=(
                    persisted_simulation.simulation_id if persisted_simulation is not None else None
                ),
            )
            self._log_operation(
                context=context,
                operation="policy_simulation.run",
                status="rejected",
                duration_ms=_duration_ms(started_at),
                payload=command,
                error_type=type(error).__name__,
                extra={"error_code": getattr(error, "code", type(error).__name__)},
            )
            raise

    def get_policy_simulation(
        self,
        command: GetPolicySimulationCommand,
        *,
        context: ObservabilityContext,
        trusted_context: PropagatedContext,
    ) -> PolicySimulationResult:
        try:
            operation_context = _require_policy_context(
                context=context,
                trusted_context=trusted_context,
                required_scope="policy:read",
            )
            simulation = self._require_policy_simulation_repository().get(
                tenant_id=operation_context.tenant_id,
                simulation_id=command.simulation_id,
            )
            if simulation is None:
                raise PolicySimulationNotFoundError()
            return simulation
        except Exception as error:
            self._publish_policy_simulation_rejection_intent(
                operation="policy_simulation.get",
                command=command,
                context=context,
                trusted_context=trusted_context,
                error=error,
            )
            raise

    def create_reason_code_catalog_draft(
        self,
        command: CreateReasonCodeCatalogDraftCommand,
        *,
        context: ObservabilityContext,
        trusted_context: PropagatedContext,
    ) -> ReasonCodeCatalogApplicationResult:
        started_at = perf_counter()
        repository = self._require_reason_code_catalog_repository()
        persisted_catalog: ReasonCodeCatalog | None = None
        try:
            operation_context = _require_policy_context(
                context=context,
                trusted_context=trusted_context,
                required_scope="policy:write",
            )
            catalog = ReasonCodeCatalog.create_draft(
                catalog_id=command.catalog_id,
                catalog_version_id=command.catalog_version_id,
                tenant_id=operation_context.tenant_id,
                owner_subject_id=command.owner_subject_id,
                product_type=command.product_type,
                reason_codes=command.reason_codes,
                explainable_factors=command.explainable_factors,
                now=self._clock(),
                actor_subject_id=operation_context.actor_subject_id,
                correlation_id=context.correlation_id,
                change_summary=command.change_summary,
            )
            catalog = repository.save_with_next_version(catalog)
            persisted_catalog = catalog
            try:
                self._publish_reason_code_catalog_audit_intent(
                    catalog=catalog,
                    event_type="reason_code_catalog.created",
                    actor_subject_id=operation_context.actor_subject_id,
                    correlation_id=context.correlation_id,
                    safe_details={
                        "change_summary": catalog.changelog[-1].change_summary,
                        "product_type": catalog.product_type,
                        "status": catalog.status,
                    },
                )
            except Exception as audit_error:
                if not repository.delete_if_current(catalog, expected_revision=catalog.revision):
                    raise RuntimeError("rollback de catálogo falhou") from audit_error
                persisted_catalog = None
                raise
            log = self._log_operation(
                context=context,
                operation="reason_code_catalog.create_draft",
                status="accepted",
                duration_ms=_duration_ms(started_at),
                payload=command,
                extra={
                    "catalog_id": catalog.catalog_id,
                    "catalog_version_id": catalog.catalog_version_id,
                    "product_type": catalog.product_type,
                    "status": catalog.status,
                },
            )
            return ReasonCodeCatalogApplicationResult(catalog=catalog, logs=(log,))
        except Exception as error:
            self._publish_reason_code_catalog_rejection_intent(
                operation="reason_code_catalog.create_draft",
                command=command,
                context=context,
                trusted_context=trusted_context,
                error=error,
                skip_catalog_id=(
                    persisted_catalog.catalog_id if persisted_catalog is not None else None
                ),
            )
            self._log_operation(
                context=context,
                operation="reason_code_catalog.create_draft",
                status="rejected",
                duration_ms=_duration_ms(started_at),
                payload=command,
                error_type=type(error).__name__,
                extra={"error_code": getattr(error, "code", type(error).__name__)},
            )
            raise

    def update_reason_code_catalog_draft(
        self,
        command: UpdateReasonCodeCatalogDraftCommand,
        *,
        context: ObservabilityContext,
        trusted_context: PropagatedContext,
    ) -> ReasonCodeCatalogApplicationResult:
        started_at = perf_counter()
        repository = self._require_reason_code_catalog_repository()
        existing_catalog: ReasonCodeCatalog | None = None
        try:
            operation_context = _require_policy_context(
                context=context,
                trusted_context=trusted_context,
                required_scope="policy:write",
            )
            existing_catalog = repository.get(
                tenant_id=operation_context.tenant_id,
                catalog_id=command.catalog_id,
                catalog_version_id=command.catalog_version_id,
            )
            if existing_catalog is None:
                raise ReasonCodeCatalogNotFoundError()
            updated_catalog = existing_catalog.update_draft(
                reason_codes=command.reason_codes,
                explainable_factors=command.explainable_factors,
                now=self._clock(),
                actor_subject_id=operation_context.actor_subject_id,
                correlation_id=context.correlation_id,
                change_summary=command.change_summary,
                owner_subject_id=command.owner_subject_id,
                product_type=command.product_type,
            )
            repository.update(updated_catalog, expected_revision=existing_catalog.revision)
            try:
                self._publish_reason_code_catalog_audit_intent(
                    catalog=updated_catalog,
                    event_type="reason_code_catalog.updated",
                    actor_subject_id=operation_context.actor_subject_id,
                    correlation_id=context.correlation_id,
                    safe_details={
                        "change_summary": updated_catalog.changelog[-1].change_summary,
                        "product_type": updated_catalog.product_type,
                        "revision": str(updated_catalog.revision),
                        "status": updated_catalog.status,
                    },
                )
            except Exception as audit_error:
                if not repository.restore_if_current(
                    existing_catalog,
                    expected_revision=updated_catalog.revision,
                ):
                    raise RuntimeError("rollback de catálogo falhou") from audit_error
                raise
            log = self._log_operation(
                context=context,
                operation="reason_code_catalog.update_draft",
                status="accepted",
                duration_ms=_duration_ms(started_at),
                payload=command,
                extra={
                    "catalog_id": updated_catalog.catalog_id,
                    "catalog_version_id": updated_catalog.catalog_version_id,
                    "product_type": updated_catalog.product_type,
                    "revision": updated_catalog.revision,
                    "status": updated_catalog.status,
                },
            )
            return ReasonCodeCatalogApplicationResult(catalog=updated_catalog, logs=(log,))
        except Exception as error:
            self._publish_reason_code_catalog_rejection_intent(
                operation="reason_code_catalog.update_draft",
                command=command,
                context=context,
                trusted_context=trusted_context,
                error=error,
            )
            self._log_operation(
                context=context,
                operation="reason_code_catalog.update_draft",
                status="rejected",
                duration_ms=_duration_ms(started_at),
                payload=command,
                error_type=type(error).__name__,
                extra={"error_code": getattr(error, "code", type(error).__name__)},
            )
            raise

    def create_reason_code_catalog_version(
        self,
        command: CreateReasonCodeCatalogVersionCommand,
        *,
        context: ObservabilityContext,
        trusted_context: PropagatedContext,
    ) -> ReasonCodeCatalogApplicationResult:
        started_at = perf_counter()
        repository = self._require_reason_code_catalog_repository()
        persisted_catalog: ReasonCodeCatalog | None = None
        try:
            operation_context = _require_policy_context(
                context=context,
                trusted_context=trusted_context,
                required_scope="policy:write",
            )
            current_catalog = repository.get(
                tenant_id=operation_context.tenant_id,
                catalog_id=command.catalog_id,
                catalog_version_id=command.current_catalog_version_id,
            )
            if current_catalog is None:
                raise ReasonCodeCatalogNotFoundError()
            next_catalog = current_catalog.create_new_version(
                catalog_version_id=command.new_catalog_version_id,
                reason_codes=command.reason_codes,
                explainable_factors=command.explainable_factors,
                now=self._clock(),
                actor_subject_id=operation_context.actor_subject_id,
                correlation_id=context.correlation_id,
                change_summary=command.change_summary,
                owner_subject_id=command.owner_subject_id,
                product_type=command.product_type,
            )
            next_catalog = repository.save_with_next_version(next_catalog)
            persisted_catalog = next_catalog
            try:
                self._publish_reason_code_catalog_audit_intent(
                    catalog=next_catalog,
                    event_type="reason_code_catalog.versioned",
                    actor_subject_id=operation_context.actor_subject_id,
                    correlation_id=context.correlation_id,
                    safe_details={
                        "change_summary": next_catalog.changelog[-1].change_summary,
                        "previous_catalog_version_id": current_catalog.catalog_version_id,
                        "product_type": next_catalog.product_type,
                        "status": next_catalog.status,
                    },
                )
            except Exception as audit_error:
                if not repository.delete_if_current(
                    next_catalog,
                    expected_revision=next_catalog.revision,
                ):
                    raise RuntimeError("rollback de catálogo falhou") from audit_error
                persisted_catalog = None
                raise
            log = self._log_operation(
                context=context,
                operation="reason_code_catalog.create_version",
                status="accepted",
                duration_ms=_duration_ms(started_at),
                payload=command,
                extra={
                    "catalog_id": next_catalog.catalog_id,
                    "catalog_version_id": next_catalog.catalog_version_id,
                    "previous_catalog_version_id": current_catalog.catalog_version_id,
                    "product_type": next_catalog.product_type,
                    "status": next_catalog.status,
                },
            )
            return ReasonCodeCatalogApplicationResult(catalog=next_catalog, logs=(log,))
        except Exception as error:
            self._publish_reason_code_catalog_rejection_intent(
                operation="reason_code_catalog.create_version",
                command=command,
                context=context,
                trusted_context=trusted_context,
                error=error,
                skip_catalog_id=(
                    persisted_catalog.catalog_id if persisted_catalog is not None else None
                ),
            )
            self._log_operation(
                context=context,
                operation="reason_code_catalog.create_version",
                status="rejected",
                duration_ms=_duration_ms(started_at),
                payload=command,
                error_type=type(error).__name__,
                extra={"error_code": getattr(error, "code", type(error).__name__)},
            )
            raise

    def get_reason_code_catalog(
        self,
        *,
        catalog_id: str,
        catalog_version_id: str,
        context: ObservabilityContext,
        trusted_context: PropagatedContext,
    ) -> ReasonCodeCatalog:
        try:
            operation_context = _require_policy_context(
                context=context,
                trusted_context=trusted_context,
                required_scope="policy:read",
            )
            catalog = self._require_reason_code_catalog_repository().get(
                tenant_id=operation_context.tenant_id,
                catalog_id=catalog_id,
                catalog_version_id=catalog_version_id,
            )
            if catalog is None:
                raise ReasonCodeCatalogNotFoundError()
            return catalog
        except Exception as error:
            self._publish_reason_code_catalog_rejection_intent(
                operation="reason_code_catalog.get",
                command=_ReasonCodeCatalogLookupCommand(
                    catalog_id=catalog_id,
                    catalog_version_id=catalog_version_id,
                ),
                context=context,
                trusted_context=trusted_context,
                error=error,
            )
            raise

    def _validate_policy_reason_code_refs(
        self,
        *,
        command: CreateCreditPolicyDraftCommand | UpdateCreditPolicyDraftCommand,
        tenant_id: str,
        policy: CreditPolicy,
    ) -> None:
        catalog = self._require_reason_code_catalog_repository().get(
            tenant_id=tenant_id,
            catalog_id=command.reason_code_catalog_id,
            catalog_version_id=command.reason_code_catalog_version_id,
        )
        if catalog is None:
            raise ReasonCodeCatalogNotFoundError()
        if catalog.product_type != policy.product_type:
            raise ReasonCodeCatalogNotFoundError()
        catalog.validate_policy_rules(policy.rules)

    def _require_reason_code_catalog_repository(self) -> ReasonCodeCatalogRepository:
        if self._reason_code_catalog_repository is None:
            raise ReasonCodeCatalogNotFoundError()
        return self._reason_code_catalog_repository

    def _require_policy_simulation_repository(self) -> PolicySimulationRepository:
        if self._policy_simulation_repository is None:
            raise PolicyValidationError(
                "repositório de simulação obrigatório",
                code="policy_simulation_repository_required",
                field_path="policy_simulation_repository",
            )
        return self._policy_simulation_repository

    def _publish_audit_intent(
        self,
        *,
        policy: CreditPolicy,
        event_type: str,
        actor_subject_id: str,
        correlation_id: str,
        safe_details: dict[str, str],
    ) -> None:
        self._audit_publisher.publish(
            CreditPolicyAuditIntent(
                event_type=event_type,
                tenant_id=policy.tenant_id,
                actor_subject_id=actor_subject_id,
                policy_id=policy.policy_id,
                policy_version_id=policy.policy_version_id,
                correlation_id=correlation_id,
                safe_details=safe_details,
            )
        )

    def _publish_reason_code_catalog_audit_intent(
        self,
        *,
        catalog: ReasonCodeCatalog,
        event_type: str,
        actor_subject_id: str,
        correlation_id: str,
        safe_details: dict[str, str],
    ) -> None:
        self._audit_publisher.publish(
            ReasonCodeCatalogAuditIntent(
                event_type=event_type,
                tenant_id=catalog.tenant_id,
                actor_subject_id=actor_subject_id,
                catalog_id=catalog.catalog_id,
                catalog_version_id=catalog.catalog_version_id,
                correlation_id=correlation_id,
                safe_details=safe_details,
            )
        )

    def _publish_policy_simulation_audit_intent(
        self,
        *,
        simulation: PolicySimulationResult,
        event_type: str,
        actor_subject_id: str,
        correlation_id: str,
    ) -> None:
        self._audit_publisher.publish(
            PolicySimulationAuditIntent(
                event_type=event_type,
                tenant_id=simulation.tenant_id,
                actor_subject_id=actor_subject_id,
                simulation_id=simulation.simulation_id,
                policy_id=simulation.policy_id,
                policy_version_id=simulation.policy_version_id,
                correlation_id=correlation_id,
                safe_details=_policy_simulation_safe_details(simulation),
            )
        )

    def _publish_rejection_intent(
        self,
        *,
        operation: str,
        command: Any,
        context: ObservabilityContext,
        trusted_context: PropagatedContext,
        error: Exception,
        skip_policy_id: str | None = None,
    ) -> None:
        policy_id = _safe_policy_identifier(
            getattr(command, "policy_id", None),
            fallback="unknown_policy",
        )
        if skip_policy_id is not None and policy_id == skip_policy_id:
            return
        policy_version_id = _safe_policy_version_identifier(
            getattr(command, "policy_version_id", None),
            fallback="unknown_policy_version",
        )
        tenant_id = _trusted_tenant_id_or_unknown(trusted_context)
        actor_subject_id = _trusted_actor_subject_id_or_unknown(trusted_context)
        correlation_id = _safe_correlation_id(
            context.correlation_id,
            fallback="corr_unknown0000",
        )
        try:
            self._audit_publisher.publish(
                CreditPolicyAuditIntent(
                    event_type="credit_policy.rejected",
                    tenant_id=tenant_id,
                    actor_subject_id=actor_subject_id,
                    policy_id=policy_id,
                    policy_version_id=policy_version_id,
                    correlation_id=correlation_id,
                    safe_details={
                        "operation": operation,
                        "rejection_reason": getattr(error, "code", type(error).__name__),
                        "status": "rejected",
                    },
                )
            )
        except Exception:
            return

    def _publish_policy_simulation_rejection_intent(
        self,
        *,
        operation: str,
        command: Any,
        context: ObservabilityContext,
        trusted_context: PropagatedContext,
        error: Exception,
        skip_simulation_id: str | None = None,
    ) -> None:
        simulation_id = _safe_simulation_identifier(
            getattr(command, "simulation_id", None),
            fallback="unknown_policy_simulation",
        )
        if skip_simulation_id is not None and simulation_id == skip_simulation_id:
            return
        tenant_id = _trusted_tenant_id_or_unknown(trusted_context)
        actor_subject_id = _trusted_actor_subject_id_or_unknown(trusted_context)
        correlation_id = _safe_correlation_id(
            context.correlation_id,
            fallback="corr_unknown0000",
        )
        try:
            self._audit_publisher.publish(
                PolicySimulationAuditIntent(
                    event_type="policy_simulation.rejected",
                    tenant_id=tenant_id,
                    actor_subject_id=actor_subject_id,
                    simulation_id=simulation_id,
                    policy_id=_safe_policy_identifier(
                        getattr(command, "policy_id", None),
                        fallback="unknown_policy",
                    ),
                    policy_version_id=_safe_policy_version_identifier(
                        getattr(command, "policy_version_id", None),
                        fallback="unknown_policy_version",
                    ),
                    correlation_id=correlation_id,
                    safe_details={
                        "case_count": _safe_case_count(command),
                        "non_production": "true",
                        "operation": operation,
                        "rejection_reason": getattr(error, "code", type(error).__name__),
                        "status": "rejected",
                    },
                )
            )
        except Exception:
            return

    def _publish_reason_code_catalog_rejection_intent(
        self,
        *,
        operation: str,
        command: Any,
        context: ObservabilityContext,
        trusted_context: PropagatedContext,
        error: Exception,
        skip_catalog_id: str | None = None,
    ) -> None:
        catalog_id = _safe_reason_code_catalog_identifier(
            getattr(command, "catalog_id", None),
            fallback="unknown_reason_code_catalog",
        )
        if skip_catalog_id is not None and catalog_id == skip_catalog_id:
            return
        catalog_version_id = _safe_reason_code_catalog_version_identifier(
            (
                getattr(command, "catalog_version_id", None)
                or getattr(command, "new_catalog_version_id", None)
                or getattr(command, "current_catalog_version_id", None)
            ),
            fallback="unknown_reason_code_catalog_version",
        )
        tenant_id = _trusted_tenant_id_or_unknown(trusted_context)
        actor_subject_id = _trusted_actor_subject_id_or_unknown(trusted_context)
        correlation_id = _safe_correlation_id(
            context.correlation_id,
            fallback="corr_unknown0000",
        )
        try:
            self._audit_publisher.publish(
                ReasonCodeCatalogAuditIntent(
                    event_type="reason_code_catalog.rejected",
                    tenant_id=tenant_id,
                    actor_subject_id=actor_subject_id,
                    catalog_id=catalog_id,
                    catalog_version_id=catalog_version_id,
                    correlation_id=correlation_id,
                    safe_details={
                        "operation": operation,
                        "rejection_reason": getattr(error, "code", type(error).__name__),
                        "status": "rejected",
                    },
                )
            )
        except Exception:
            return

    def _log_operation(
        self,
        *,
        context: ObservabilityContext,
        operation: str,
        status: str,
        duration_ms: float,
        payload: Any | None = None,
        extra: dict[str, Any] | None = None,
        error_type: str | None = None,
    ) -> dict[str, Any]:
        event = build_structured_log(
            context=context,
            service_name=SERVICE_NAME,
            service_version=SERVICE_VERSION,
            environment=self._environment,
            operation=operation,
            source="decision.application",
            destination="decision.domain",
            contract=CONTRACT,
            contract_version=CONTRACT_VERSION,
            status=status,
            duration_ms=duration_ms,
            error_type=error_type,
            payload=payload,
            extra=extra,
        )
        self._logged_events.append(event)
        return event


@dataclass(frozen=True, slots=True)
class _PolicyLookupCommand:
    policy_id: str
    policy_version_id: str


@dataclass(frozen=True, slots=True)
class _ReasonCodeCatalogLookupCommand:
    catalog_id: str
    catalog_version_id: str


def _require_policy_context(
    *,
    context: ObservabilityContext,
    trusted_context: PropagatedContext,
    required_scope: str,
) -> _PolicyOperationContext:
    if not isinstance(trusted_context, PropagatedContext):
        raise PolicyTenantContextError("contexto confiável é obrigatório")
    trusted = trusted_context.trusted
    if not context.tenant_id or not trusted.tenant_id:
        raise PolicyTenantContextError("tenant confiável é obrigatório")
    if context.tenant_id != trusted.tenant_id:
        raise PolicyTenantContextError(
            "tenant divergente do contexto confiável",
            code="policy_tenant_context_mismatch",
        )
    if context.tenant_isolation_tier != trusted.tenant_isolation_tier:
        raise PolicyTenantContextError(
            "tier de tenant divergente",
            code="policy_tenant_tier_mismatch",
        )
    if trusted.tenant_isolation_tier != "bridge":
        raise PolicyTenantContextError(
            "tier de tenant não suportado",
            code="unsupported_policy_tenant_tier",
        )
    if required_scope not in set(trusted.scopes):
        raise PolicyTenantContextError(
            "escopo obrigatório ausente",
            code="missing_policy_scope",
        )
    return _PolicyOperationContext(
        tenant_id=trusted.tenant_id,
        actor_subject_id=trusted.subject_id,
    )


def _safe_policy_identifier(value: object, *, fallback: str) -> str:
    if not isinstance(value, str):
        return fallback
    try:
        return validate_policy_id(value)
    except Exception:
        return fallback


def _safe_policy_version_identifier(value: object, *, fallback: str) -> str:
    if not isinstance(value, str):
        return fallback
    try:
        return validate_policy_version_id(value)
    except Exception:
        return fallback


def _safe_simulation_identifier(value: object, *, fallback: str) -> str:
    if not isinstance(value, str):
        return fallback
    try:
        return validate_policy_simulation_id(value)
    except Exception:
        return fallback


def _safe_reason_code_catalog_identifier(value: object, *, fallback: str) -> str:
    if not isinstance(value, str):
        return fallback
    try:
        return validate_reason_code_catalog_id(value)
    except Exception:
        return fallback


def _safe_reason_code_catalog_version_identifier(value: object, *, fallback: str) -> str:
    if not isinstance(value, str):
        return fallback
    try:
        return validate_reason_code_catalog_version_id(value)
    except Exception:
        return fallback


def _safe_correlation_id(value: object, *, fallback: str) -> str:
    if not isinstance(value, str):
        return fallback
    try:
        return validate_correlation_id(value)
    except Exception:
        return fallback


def _trusted_tenant_id_or_unknown(trusted_context: object) -> str:
    if not isinstance(trusted_context, PropagatedContext):
        return "unknown_tenant"
    return trusted_context.trusted.tenant_id or "unknown_tenant"


def _trusted_actor_subject_id_or_unknown(trusted_context: object) -> str:
    if not isinstance(trusted_context, PropagatedContext):
        return "unknown_actor"
    return trusted_context.trusted.subject_id or "unknown_actor"


def _duration_ms(started_at: float) -> float:
    return round((perf_counter() - started_at) * 1000, 3)


def _policy_simulation_safe_details(
    simulation: PolicySimulationResult,
) -> dict[str, str]:
    return {
        "case_count": str(simulation.summary.total_cases),
        "issue_count": str(simulation.summary.issue_count),
        "non_production": "true",
        "operation": "policy_simulation.run",
        "outcome_approve": str(simulation.summary.count_for("approve")),
        "outcome_approve_with_changes": str(simulation.summary.count_for("approve_with_changes")),
        "outcome_reject": str(simulation.summary.count_for("reject")),
        "outcome_request_more_data": str(simulation.summary.count_for("request_more_data")),
        "outcome_unable_to_decide": str(simulation.summary.count_for("unable_to_decide")),
        "status": simulation.status,
    }


def _safe_case_count(command: Any) -> str:
    cases = getattr(command, "cases", ())
    try:
        return str(len(cases))
    except Exception:
        return "0"
