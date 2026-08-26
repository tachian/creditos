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
)
from creditos_decision.domain.entities import CreditPolicy
from creditos_decision.domain.errors import PolicyNotFoundError, PolicyTenantContextError
from creditos_decision.domain.value_objects import (
    PolicyApplicability,
    PolicyCriterion,
    PolicyLimit,
    PolicyRule,
    validate_correlation_id,
    validate_policy_id,
    validate_policy_version_id,
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
    owner_subject_id: str | None = None
    product_type: str | None = None
    actor_subject_id: str = ""


@dataclass(frozen=True, slots=True)
class CreditPolicyApplicationResult:
    policy: CreditPolicy
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
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
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
                owner_subject_id=command.owner_subject_id,
                product_type=command.product_type,
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
        tenant_id = (
            trusted_context.trusted.tenant_id
            if isinstance(trusted_context, PropagatedContext)
            else context.tenant_id or "unknown_tenant"
        )
        actor_subject_id = (
            trusted_context.trusted.subject_id
            if isinstance(trusted_context, PropagatedContext)
            else "unknown_actor"
        )
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


def _safe_correlation_id(value: object, *, fallback: str) -> str:
    if not isinstance(value, str):
        return fallback
    try:
        return validate_correlation_id(value)
    except Exception:
        return fallback


def _duration_ms(started_at: float) -> float:
    return round((perf_counter() - started_at) * 1000, 3)
