from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from time import perf_counter
from typing import Any
from uuid import uuid4

from creditos_observability.context import ObservabilityContext
from creditos_observability.logging import build_structured_log
from creditos_security import PropagatedContext

from creditos_decision.application.ports import (
    CreditDecisionAuditIntent,
    CreditDecisionRepository,
    CreditPolicyAuditIntent,
    CreditPolicyAuditPublisher,
    CreditPolicyRepository,
    PolicySimulationAuditIntent,
    PolicySimulationRepository,
    ReasonCodeCatalogAuditIntent,
    ReasonCodeCatalogRepository,
)
from creditos_decision.domain.entities import (
    CreditDecision,
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
from creditos_decision.domain.services.policy_evaluator import evaluate_policy_case
from creditos_decision.domain.value_objects import (
    CreditDecisionInput,
    CreditDecisionInputFieldValue,
    ExplainableFactor,
    PolicyApplicability,
    PolicyCriterion,
    PolicyFallbackAction,
    PolicyLimit,
    PolicyRule,
    PolicySimulationInputCase,
    ReasonCode,
    validate_correlation_id,
    validate_credit_decision_id,
    validate_policy_id,
    validate_policy_simulation_id,
    validate_policy_version_id,
    validate_proposal_id,
    validate_reason_code_catalog_id,
    validate_reason_code_catalog_version_id,
)
from creditos_decision.domain.value_objects.policy import (
    PolicyFallbackActionType,
    parse_product_type,
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
    fallback_action: PolicyFallbackAction | None = None
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
    fallback_action: PolicyFallbackAction | None = None
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
class PublishCreditPolicyCommand:
    policy_id: str
    policy_version_id: str
    simulation_id: str
    change_summary: str
    actor_subject_id: str = ""


@dataclass(frozen=True, slots=True)
class CreateCreditPolicyVersionCommand:
    policy_id: str
    current_policy_version_id: str
    new_policy_version_id: str
    change_summary: str
    rules: tuple[PolicyRule, ...]
    criteria: tuple[PolicyCriterion, ...]
    limits: tuple[PolicyLimit, ...]
    applicability: PolicyApplicability
    reason_code_catalog_id: str
    reason_code_catalog_version_id: str
    fallback_action: PolicyFallbackAction | None = None
    owner_subject_id: str | None = None
    product_type: str | None = None
    actor_subject_id: str = ""


@dataclass(frozen=True, slots=True)
class GetPublishedCreditPolicyCommand:
    product_type: str
    channel: str
    effective_at: datetime


@dataclass(frozen=True, slots=True)
class ExecuteCreditDecisionCommand:
    proposal_id: str
    product_type: str
    channel: str
    effective_at: datetime
    field_values: tuple[CreditDecisionInputFieldValue, ...]
    integration_result_refs: tuple[str, ...] = ()
    decision_id: str = ""
    actor_subject_id: str = ""


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
class CreditDecisionApplicationResult:
    decision: CreditDecision
    logs: tuple[dict[str, Any], ...]


@dataclass(frozen=True, slots=True)
class _PolicyOperationContext:
    tenant_id: str
    actor_subject_id: str


@dataclass(frozen=True, slots=True)
class _PolicyReasonCodeReference:
    outcome: str
    reason_code_refs: tuple[str, ...]


class DecisionApplicationService:
    def __init__(
        self,
        *,
        repository: CreditPolicyRepository,
        audit_publisher: CreditPolicyAuditPublisher,
        environment: str,
        reason_code_catalog_repository: ReasonCodeCatalogRepository | None = None,
        policy_simulation_repository: PolicySimulationRepository | None = None,
        credit_decision_repository: CreditDecisionRepository | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._reason_code_catalog_repository = reason_code_catalog_repository
        self._policy_simulation_repository = policy_simulation_repository
        self._credit_decision_repository = credit_decision_repository
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
                fallback_action=command.fallback_action,
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
                fallback_action=command.fallback_action,
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

    def publish_policy(
        self,
        command: PublishCreditPolicyCommand,
        *,
        context: ObservabilityContext,
        trusted_context: PropagatedContext,
    ) -> CreditPolicyApplicationResult:
        started_at = perf_counter()
        existing_policy: CreditPolicy | None = None
        published_policy: CreditPolicy | None = None
        simulation: PolicySimulationResult | None = None
        try:
            operation_context = _require_policy_context(
                context=context,
                trusted_context=trusted_context,
                required_scope="policy:publish",
            )
            existing_policy = self._repository.get(
                tenant_id=operation_context.tenant_id,
                policy_id=command.policy_id,
                policy_version_id=command.policy_version_id,
            )
            if existing_policy is None:
                raise PolicyNotFoundError()
            simulation = self._require_publication_simulation(
                tenant_id=operation_context.tenant_id,
                policy=existing_policy,
                simulation_id=command.simulation_id,
            )
            self._validate_policy_catalog_for_publication(
                tenant_id=operation_context.tenant_id,
                policy=existing_policy,
            )
            published_policy = existing_policy.publish(
                now=self._clock(),
                actor_subject_id=operation_context.actor_subject_id,
                correlation_id=context.correlation_id,
                change_summary=command.change_summary,
            )

            def publish_audit_before_commit() -> None:
                assert published_policy is not None
                assert simulation is not None
                self._publish_audit_intent(
                    policy=published_policy,
                    event_type="credit_policy.published",
                    actor_subject_id=operation_context.actor_subject_id,
                    correlation_id=context.correlation_id,
                    safe_details=_policy_publication_safe_details(
                        policy=published_policy,
                        change_summary=command.change_summary,
                        simulation=simulation,
                    ),
                )

            self._repository.publish_if_no_window_conflict(
                published_policy,
                expected_revision=existing_policy.revision,
                before_commit=publish_audit_before_commit,
            )
            log = self._log_operation(
                context=context,
                operation="credit_policy.publish",
                status="accepted",
                duration_ms=_duration_ms(started_at),
                payload=command,
                extra={
                    "policy_id": published_policy.policy_id,
                    "policy_version_id": published_policy.policy_version_id,
                    "product_type": published_policy.product_type,
                    "status": published_policy.status,
                },
            )
            return CreditPolicyApplicationResult(policy=published_policy, logs=(log,))
        except Exception as error:
            self._publish_rejection_intent(
                operation="credit_policy.publish",
                command=command,
                context=context,
                trusted_context=trusted_context,
                error=error,
                safe_details=(
                    _policy_publication_rejection_safe_details(
                        policy=published_policy or existing_policy,
                        simulation=simulation,
                    )
                    if existing_policy is not None and simulation is not None
                    else None
                ),
            )
            self._log_operation(
                context=context,
                operation="credit_policy.publish",
                status="rejected",
                duration_ms=_duration_ms(started_at),
                payload=command,
                error_type=type(error).__name__,
                extra={"error_code": getattr(error, "code", type(error).__name__)},
            )
            raise

    def create_policy_version(
        self,
        command: CreateCreditPolicyVersionCommand,
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
                required_scope="policy:publish",
            )
            current_policy = self._repository.get(
                tenant_id=operation_context.tenant_id,
                policy_id=command.policy_id,
                policy_version_id=command.current_policy_version_id,
            )
            if current_policy is None:
                raise PolicyNotFoundError()
            next_policy = current_policy.create_new_version(
                policy_version_id=command.new_policy_version_id,
                version=self._repository.next_version(
                    tenant_id=operation_context.tenant_id,
                    policy_id=command.policy_id,
                ),
                rules=command.rules,
                criteria=command.criteria,
                limits=command.limits,
                applicability=command.applicability,
                reason_code_catalog_id=command.reason_code_catalog_id,
                reason_code_catalog_version_id=command.reason_code_catalog_version_id,
                now=self._clock(),
                actor_subject_id=operation_context.actor_subject_id,
                correlation_id=context.correlation_id,
                change_summary=command.change_summary,
                owner_subject_id=command.owner_subject_id,
                product_type=command.product_type,
                fallback_action=command.fallback_action,
            )
            self._validate_policy_reason_code_refs(
                command=_VersionedPolicyReasonCodeValidationCommand(
                    reason_code_catalog_id=command.reason_code_catalog_id,
                    reason_code_catalog_version_id=command.reason_code_catalog_version_id,
                ),
                tenant_id=operation_context.tenant_id,
                policy=next_policy,
            )

            def publish_versioned_audit_before_commit() -> None:
                self._publish_audit_intent(
                    policy=next_policy,
                    event_type="credit_policy.versioned",
                    actor_subject_id=operation_context.actor_subject_id,
                    correlation_id=context.correlation_id,
                    safe_details={
                        "change_summary": next_policy.changelog[-1].change_summary,
                        "operation": "credit_policy.create_version",
                        "previous_policy_version_id": current_policy.policy_version_id,
                        "product_type": next_policy.product_type,
                        "status": next_policy.status,
                        "version": str(next_policy.version),
                        "effective_ends_at": (
                            next_policy.applicability.ends_at.isoformat()
                            if next_policy.applicability.ends_at is not None
                            else ""
                        ),
                        "effective_starts_at": (
                            next_policy.applicability.starts_at.isoformat()
                            if next_policy.applicability.starts_at is not None
                            else ""
                        ),
                    },
                )

            self._repository.save_new_version(
                next_policy,
                before_commit=publish_versioned_audit_before_commit,
            )
            persisted_policy = next_policy
            log = self._log_operation(
                context=context,
                operation="credit_policy.create_version",
                status="accepted",
                duration_ms=_duration_ms(started_at),
                payload=command,
                extra={
                    "policy_id": next_policy.policy_id,
                    "policy_version_id": next_policy.policy_version_id,
                    "previous_policy_version_id": current_policy.policy_version_id,
                    "product_type": next_policy.product_type,
                    "status": next_policy.status,
                },
            )
            return CreditPolicyApplicationResult(policy=next_policy, logs=(log,))
        except Exception as error:
            self._publish_rejection_intent(
                operation="credit_policy.create_version",
                command=_PolicyLookupCommand(
                    policy_id=command.policy_id,
                    policy_version_id=command.new_policy_version_id,
                ),
                context=context,
                trusted_context=trusted_context,
                error=error,
                skip_policy_id=(
                    persisted_policy.policy_id if persisted_policy is not None else None
                ),
            )
            self._log_operation(
                context=context,
                operation="credit_policy.create_version",
                status="rejected",
                duration_ms=_duration_ms(started_at),
                payload=command,
                error_type=type(error).__name__,
                extra={"error_code": getattr(error, "code", type(error).__name__)},
            )
            raise

    def get_published_policy(
        self,
        command: GetPublishedCreditPolicyCommand,
        *,
        context: ObservabilityContext,
        trusted_context: PropagatedContext,
    ) -> CreditPolicy:
        try:
            operation_context = _require_policy_context(
                context=context,
                trusted_context=trusted_context,
                required_scope="policy:read",
            )
            return self._select_published_policy(
                tenant_id=operation_context.tenant_id,
                product_type=command.product_type,
                channel=command.channel,
                effective_at=command.effective_at,
            )
        except Exception as error:
            self._publish_rejection_intent(
                operation="credit_policy.get_published",
                command=_PolicyLookupCommand(
                    policy_id="unknown_policy",
                    policy_version_id="unknown_policy_version",
                ),
                context=context,
                trusted_context=trusted_context,
                error=error,
            )
            raise

    def execute_credit_decision(
        self,
        command: ExecuteCreditDecisionCommand,
        *,
        context: ObservabilityContext,
        trusted_context: PropagatedContext,
    ) -> CreditDecisionApplicationResult:
        started_at = perf_counter()
        decision: CreditDecision | None = None
        generated_decision_id: str | None = None
        decision_audit_completed = False
        try:
            operation_context = _require_policy_context(
                context=context,
                trusted_context=trusted_context,
                required_scope="decision:execute",
            )
            policy = self._select_published_policy(
                tenant_id=operation_context.tenant_id,
                product_type=command.product_type,
                channel=command.channel,
                effective_at=command.effective_at,
            )
            catalog = self._require_reason_code_catalog_repository().get(
                tenant_id=operation_context.tenant_id,
                catalog_id=policy.reason_code_catalog_id,
                catalog_version_id=policy.reason_code_catalog_version_id,
            )
            if catalog is None or catalog.product_type != policy.product_type:
                raise ReasonCodeCatalogNotFoundError()
            if not catalog.is_referenceable_for_final_decisions:
                raise PolicyValidationError(
                    "decisão exige catálogo publicado",
                    code="credit_decision_requires_published_catalog",
                    field_path="reason_code_catalog_version_id",
                )
            decision_input = CreditDecisionInput(
                proposal_id=command.proposal_id,
                field_values=tuple(command.field_values),
                integration_result_refs=tuple(command.integration_result_refs),
            )
            evaluation = evaluate_policy_case(
                policy=policy,
                catalog=catalog,
                evaluation_id=decision_input.proposal_id,
                field_values=decision_input.field_values,
            )
            generated_decision_id = command.decision_id or f"decision_{uuid4().hex}"
            decision = CreditDecision.create(
                decision_id=generated_decision_id,
                policy=policy,
                catalog=catalog,
                decision_input=decision_input,
                evaluation=evaluation,
                channel=command.channel,
                correlation_id=context.correlation_id,
                decided_at=self._clock(),
            )
            repository = self._require_credit_decision_repository()

            def publish_audit_before_commit() -> None:
                nonlocal decision_audit_completed
                assert decision is not None
                self._publish_credit_decision_audit_intent(
                    decision=decision,
                    event_type="credit_decision.completed",
                    actor_subject_id=operation_context.actor_subject_id,
                    correlation_id=context.correlation_id,
                    duration_ms=duration_ms,
                )
                decision_audit_completed = True

            duration_ms = _duration_ms(started_at)
            repository.save(decision, before_commit=publish_audit_before_commit)
            log = self._log_operation(
                context=context,
                operation="credit_decision.execute",
                status="accepted",
                duration_ms=duration_ms,
                payload=command,
                extra={
                    "channel": decision.channel,
                    "decision_id": decision.decision_id,
                    "fallback_action": decision.fallback_action or "",
                    "proposal_id": decision.proposal_id,
                    "policy_id": decision.policy_id,
                    "policy_version_id": decision.policy_version_id,
                    "product_type": decision.product_type,
                    "reason_code_catalog_id": decision.reason_code_catalog_id,
                    "reason_code_catalog_version_id": decision.reason_code_catalog_version_id,
                    "reason_code_refs": tuple(sorted(decision.reason_code_refs)),
                    "required_data_count": len(decision.required_data_refs),
                    "required_data_refs": tuple(sorted(decision.required_data_refs)),
                    "outcome": decision.outcome,
                    "fingerprint": decision.decision_fingerprint,
                    "validation_issue_codes": tuple(
                        sorted({issue.code for issue in decision.validation_issues})
                    ),
                },
            )
            return CreditDecisionApplicationResult(decision=decision, logs=(log,))
        except Exception as error:
            skip_decision_id = (
                decision.decision_id if decision_audit_completed and decision is not None else None
            )
            self._publish_credit_decision_rejection_intent(
                operation="credit_decision.execute",
                command=command,
                context=context,
                trusted_context=trusted_context,
                error=error,
                skip_decision_id=skip_decision_id,
                fallback_decision_id=generated_decision_id,
            )
            self._log_operation(
                context=context,
                operation="credit_decision.execute",
                status="rejected",
                duration_ms=_duration_ms(started_at),
                payload=command,
                error_type=type(error).__name__,
                extra={"error_code": getattr(error, "code", type(error).__name__)},
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
        command: (
            CreateCreditPolicyDraftCommand
            | UpdateCreditPolicyDraftCommand
            | _VersionedPolicyReasonCodeValidationCommand
        ),
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
        _validate_fallback_reason_code_refs(policy=policy, catalog=catalog)

    def _validate_policy_catalog_for_publication(
        self,
        *,
        tenant_id: str,
        policy: CreditPolicy,
    ) -> None:
        catalog = self._require_reason_code_catalog_repository().get(
            tenant_id=tenant_id,
            catalog_id=policy.reason_code_catalog_id,
            catalog_version_id=policy.reason_code_catalog_version_id,
        )
        if catalog is None or catalog.product_type != policy.product_type:
            raise ReasonCodeCatalogNotFoundError()
        if not catalog.is_referenceable_for_final_decisions:
            raise PolicyValidationError(
                "catálogo deve estar publicado",
                code="policy_publication_requires_published_catalog",
                field_path="reason_code_catalog_version_id",
            )
        catalog.validate_policy_rules(policy.rules)
        _validate_fallback_reason_code_refs(policy=policy, catalog=catalog)

    def _require_publication_simulation(
        self,
        *,
        tenant_id: str,
        policy: CreditPolicy,
        simulation_id: str,
    ) -> PolicySimulationResult:
        simulation = self._require_policy_simulation_repository().get(
            tenant_id=tenant_id,
            simulation_id=simulation_id,
        )
        if (
            simulation is None
            or simulation.tenant_id != policy.tenant_id
            or simulation.policy_id != policy.policy_id
            or simulation.policy_version_id != policy.policy_version_id
            or simulation.policy_revision != policy.revision
            or simulation.reason_code_catalog_id != policy.reason_code_catalog_id
            or simulation.reason_code_catalog_version_id != policy.reason_code_catalog_version_id
            or simulation.status != "completed"
            or simulation.summary.issue_count != 0
        ):
            raise PolicyValidationError(
                "simulação válida obrigatória",
                code="policy_publication_requires_clean_simulation",
                field_path="simulation_id",
            )
        return simulation

    def _raise_if_publication_window_conflicts(self, candidate: CreditPolicy) -> None:
        for published_policy in self._repository.list_published_by_product(
            tenant_id=candidate.tenant_id,
            product_type=candidate.product_type,
        ):
            if published_policy.policy_version_id == candidate.policy_version_id:
                continue
            if _policy_windows_overlap(candidate, published_policy):
                raise PolicyValidationError(
                    "vigência conflitante",
                    code="conflicting_published_policy_window",
                    field_path="applicability",
                )

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

    def _require_credit_decision_repository(self) -> CreditDecisionRepository:
        if self._credit_decision_repository is None:
            raise PolicyValidationError(
                "repositório de decisão obrigatório",
                code="credit_decision_repository_required",
                field_path="credit_decision_repository",
            )
        return self._credit_decision_repository

    def _select_published_policy(
        self,
        *,
        tenant_id: str,
        product_type: str,
        channel: str,
        effective_at: datetime,
    ) -> CreditPolicy:
        parsed_product_type = parse_product_type(product_type)
        parsed_channel = PolicyApplicability.create(channels=(channel,)).channels[0]
        parsed_effective_at = PolicyApplicability.create(starts_at=effective_at).starts_at
        if parsed_effective_at is None:
            raise PolicyNotFoundError()
        matches = tuple(
            policy
            for policy in self._repository.list_published_by_product(
                tenant_id=tenant_id,
                product_type=parsed_product_type,
            )
            if _policy_applies_to_channel(policy, parsed_channel)
            and _policy_is_effective(policy, parsed_effective_at)
        )
        if len(matches) != 1:
            if len(matches) > 1:
                raise PolicyValidationError(
                    "vigência conflitante",
                    code="conflicting_published_policy_window",
                    field_path="applicability",
                )
            raise PolicyNotFoundError()
        return matches[0]

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

    def _publish_credit_decision_audit_intent(
        self,
        *,
        decision: CreditDecision,
        event_type: str,
        actor_subject_id: str,
        correlation_id: str,
        duration_ms: float | None = None,
    ) -> None:
        self._audit_publisher.publish(
            CreditDecisionAuditIntent(
                event_type=event_type,
                tenant_id=decision.tenant_id,
                actor_subject_id=actor_subject_id,
                decision_id=decision.decision_id,
                proposal_id=decision.proposal_id,
                policy_id=decision.policy_id,
                policy_version_id=decision.policy_version_id,
                reason_code_catalog_id=decision.reason_code_catalog_id,
                reason_code_catalog_version_id=decision.reason_code_catalog_version_id,
                correlation_id=correlation_id,
                safe_details=_credit_decision_safe_details(
                    decision,
                    duration_ms=duration_ms,
                ),
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
        safe_details: dict[str, str] | None = None,
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
        rejection_safe_details = {
            "operation": operation,
            "rejection_reason": getattr(error, "code", type(error).__name__),
            "status": "rejected",
        }
        if safe_details is not None:
            rejection_safe_details.update(safe_details)
        try:
            self._audit_publisher.publish(
                CreditPolicyAuditIntent(
                    event_type="credit_policy.rejected",
                    tenant_id=tenant_id,
                    actor_subject_id=actor_subject_id,
                    policy_id=policy_id,
                    policy_version_id=policy_version_id,
                    correlation_id=correlation_id,
                    safe_details=rejection_safe_details,
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

    def _publish_credit_decision_rejection_intent(
        self,
        *,
        operation: str,
        command: Any,
        context: ObservabilityContext,
        trusted_context: PropagatedContext,
        error: Exception,
        skip_decision_id: str | None = None,
        fallback_decision_id: str | None = None,
    ) -> None:
        decision_id = _safe_credit_decision_identifier(
            getattr(command, "decision_id", None) or fallback_decision_id,
            fallback="unknown_credit_decision",
        )
        if skip_decision_id is not None and decision_id == skip_decision_id:
            return
        tenant_id = _trusted_tenant_id_or_unknown(trusted_context)
        actor_subject_id = _trusted_actor_subject_id_or_unknown(trusted_context)
        correlation_id = _safe_correlation_id(
            context.correlation_id,
            fallback="corr_unknown0000",
        )
        try:
            self._audit_publisher.publish(
                CreditDecisionAuditIntent(
                    event_type="credit_decision.rejected",
                    tenant_id=tenant_id,
                    actor_subject_id=actor_subject_id,
                    decision_id=decision_id,
                    proposal_id=_safe_proposal_identifier(
                        getattr(command, "proposal_id", None),
                        fallback="unknown_proposal",
                    ),
                    policy_id="unknown_policy",
                    policy_version_id="unknown_policy_version",
                    reason_code_catalog_id="unknown_reason_code_catalog",
                    reason_code_catalog_version_id="unknown_reason_code_catalog_version",
                    correlation_id=correlation_id,
                    safe_details={
                        "operation": operation,
                        "product_type": _safe_product_type_value(
                            getattr(command, "product_type", None),
                        ),
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


@dataclass(frozen=True, slots=True)
class _VersionedPolicyReasonCodeValidationCommand:
    reason_code_catalog_id: str
    reason_code_catalog_version_id: str


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


def _safe_credit_decision_identifier(value: object, *, fallback: str) -> str:
    if not isinstance(value, str) or not value:
        return fallback
    try:
        return validate_credit_decision_id(value)
    except Exception:
        return fallback


def _safe_proposal_identifier(value: object, *, fallback: str) -> str:
    if not isinstance(value, str):
        return fallback
    try:
        return validate_proposal_id(value)
    except Exception:
        return fallback


def _safe_product_type_value(value: object) -> str:
    if not isinstance(value, str):
        return "unknown_product"
    try:
        return parse_product_type(value)
    except Exception:
        return "unknown_product"


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
    fallback_actions = tuple(
        case_result.fallback_action
        for case_result in simulation.case_results
        if case_result.fallback_action is not None
    )
    required_data_case_count = sum(
        1 for case_result in simulation.case_results if case_result.required_data_refs
    )
    return {
        "case_count": str(simulation.summary.total_cases),
        "fallback_action_request_more_data": str(
            fallback_actions.count(PolicyFallbackActionType.REQUEST_MORE_DATA.value)
        ),
        "fallback_action_reject_by_policy": str(
            fallback_actions.count(PolicyFallbackActionType.REJECT_BY_POLICY.value)
        ),
        "fallback_action_unable_to_decide": str(
            fallback_actions.count(PolicyFallbackActionType.UNABLE_TO_DECIDE.value)
        ),
        "fallback_applied_count": str(len(fallback_actions)),
        "issue_count": str(simulation.summary.issue_count),
        "non_production": "true",
        "operation": "policy_simulation.run",
        "outcome_approve": str(simulation.summary.count_for("approve")),
        "outcome_approve_with_changes": str(simulation.summary.count_for("approve_with_changes")),
        "outcome_reject": str(simulation.summary.count_for("reject")),
        "outcome_request_more_data": str(simulation.summary.count_for("request_more_data")),
        "outcome_unable_to_decide": str(simulation.summary.count_for("unable_to_decide")),
        "required_data_case_count": str(required_data_case_count),
        "status": simulation.status,
    }


def _credit_decision_safe_details(
    decision: CreditDecision,
    *,
    duration_ms: float | None = None,
) -> dict[str, str]:
    details = {
        "channel": decision.channel,
        "factor_count": str(len(decision.factor_refs)),
        "fingerprint": decision.decision_fingerprint,
        "operation": "credit_decision.execute",
        "outcome": decision.outcome,
        "policy_id": decision.policy_id,
        "reason_code_catalog_id": decision.reason_code_catalog_id,
        "reason_code_catalog_version_id": decision.reason_code_catalog_version_id,
        "policy_revision": str(decision.policy_revision),
        "policy_version_id": decision.policy_version_id,
        "product_type": decision.product_type,
        "reason_code_count": str(len(decision.reason_code_refs)),
        "status": "completed",
        "triggered_rule_count": str(len(decision.triggered_rule_ids)),
        "validation_issue_count": str(len(decision.validation_issues)),
    }
    if duration_ms is not None:
        details["duration_ms"] = str(duration_ms)
    if decision.fallback_action is not None:
        details["fallback_action"] = decision.fallback_action
    if decision.reason_code_refs:
        details["reason_code_refs"] = ",".join(sorted(decision.reason_code_refs))
    if decision.required_data_refs:
        details["required_data_count"] = str(len(decision.required_data_refs))
        details["required_data_refs"] = ",".join(sorted(decision.required_data_refs))
    if decision.validation_issues:
        details["validation_issue_codes"] = ",".join(
            sorted({issue.code for issue in decision.validation_issues})
        )
    return details


def _validate_fallback_reason_code_refs(
    *,
    policy: CreditPolicy,
    catalog: ReasonCodeCatalog,
) -> None:
    if policy.fallback_action.action != PolicyFallbackActionType.REJECT_BY_POLICY.value:
        return
    catalog.validate_policy_rules(
        (
            _PolicyReasonCodeReference(
                outcome="reject",
                reason_code_refs=policy.fallback_action.reason_code_refs,
            ),
        )
    )


def _safe_case_count(command: Any) -> str:
    cases = getattr(command, "cases", ())
    try:
        return str(len(cases))
    except Exception:
        return "0"


def _policy_publication_safe_details(
    *,
    policy: CreditPolicy,
    change_summary: str,
    simulation: PolicySimulationResult,
) -> dict[str, str]:
    return {
        "change_summary": change_summary,
        "effective_ends_at": (
            policy.applicability.ends_at.isoformat()
            if policy.applicability.ends_at is not None
            else ""
        ),
        "effective_starts_at": (
            policy.applicability.starts_at.isoformat()
            if policy.applicability.starts_at is not None
            else ""
        ),
        "operation": "credit_policy.publish",
        "product_type": policy.product_type,
        "revision": str(policy.revision),
        "simulation_id": simulation.simulation_id,
        "simulation_issue_count": str(simulation.summary.issue_count),
        "status": policy.status,
    }


def _policy_publication_rejection_safe_details(
    *,
    policy: CreditPolicy,
    simulation: PolicySimulationResult,
) -> dict[str, str]:
    return {
        "effective_ends_at": (
            policy.applicability.ends_at.isoformat()
            if policy.applicability.ends_at is not None
            else ""
        ),
        "effective_starts_at": (
            policy.applicability.starts_at.isoformat()
            if policy.applicability.starts_at is not None
            else ""
        ),
        "policy_revision": str(policy.revision),
        "product_type": policy.product_type,
        "simulation_id": simulation.simulation_id,
        "simulation_issue_count": str(simulation.summary.issue_count),
        "simulation_policy_revision": str(simulation.policy_revision),
    }


def _policy_applies_to_channel(policy: CreditPolicy, channel: str) -> bool:
    return not policy.applicability.channels or channel in policy.applicability.channels


def _policy_is_effective(policy: CreditPolicy, effective_at: datetime) -> bool:
    starts_at = policy.applicability.starts_at
    ends_at = policy.applicability.ends_at
    if starts_at is None or effective_at < starts_at:
        return False
    return ends_at is None or effective_at < ends_at


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
