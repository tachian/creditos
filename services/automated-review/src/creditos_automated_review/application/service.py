from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from time import monotonic
from typing import Any

from creditos_observability.context import ObservabilityContext
from creditos_observability.logging import build_structured_log
from creditos_security import PropagatedContext

from creditos_automated_review.application.ports import (
    AutomatedReviewAuditIntent,
    AutomatedReviewAuditPublisher,
    ReviewAgentConfigRepository,
)
from creditos_automated_review.domain.entities import ReviewAgentConfiguration
from creditos_automated_review.domain.errors import (
    AutomatedReviewConfigNotFoundError,
    AutomatedReviewConflictError,
    AutomatedReviewTenantContextError,
)
from creditos_automated_review.domain.value_objects import (
    ReviewAgentCapabilities,
    ReviewAgentGuardrails,
    ReviewAgentPrompt,
    ReviewAgentScope,
    ReviewModelRef,
)
from creditos_automated_review.domain.value_objects.review_agent_config import (
    validate_agent_version,
)

SERVICE_NAME = "automated-review"
SERVICE_VERSION = "0.1.0"
CONTRACT = "automated-review.application"
CONTRACT_VERSION = "v1"


@dataclass(frozen=True, slots=True)
class CreateReviewAgentConfigCommand:
    review_agent_config_id: str
    review_agent_config_version_id: str
    agent_version: str
    prompt: ReviewAgentPrompt
    scope: ReviewAgentScope
    guardrails: ReviewAgentGuardrails
    capabilities: ReviewAgentCapabilities
    change_summary: str
    model_ref: ReviewModelRef | None = None


@dataclass(frozen=True, slots=True)
class UpdateReviewAgentConfigCommand:
    review_agent_config_id: str
    review_agent_config_version_id: str
    change_summary: str
    agent_version: str | None = None
    prompt: ReviewAgentPrompt | None = None
    scope: ReviewAgentScope | None = None
    guardrails: ReviewAgentGuardrails | None = None
    capabilities: ReviewAgentCapabilities | None = None
    model_ref: ReviewModelRef | None = None
    clear_model_ref: bool = False


@dataclass(frozen=True, slots=True)
class PublishReviewAgentConfigCommand:
    review_agent_config_id: str
    review_agent_config_version_id: str
    approval_reference: str
    change_summary: str


@dataclass(frozen=True, slots=True)
class CreateReviewAgentConfigVersionCommand:
    review_agent_config_id: str
    current_review_agent_config_version_id: str
    new_review_agent_config_version_id: str
    change_summary: str


@dataclass(frozen=True, slots=True)
class GetReviewAgentConfigCommand:
    review_agent_config_id: str
    review_agent_config_version_id: str


@dataclass(frozen=True, slots=True)
class ReviewAgentConfigApplicationResult:
    config: ReviewAgentConfiguration
    logs: tuple[dict[str, Any], ...]


class AutomatedReviewApplicationService:
    def __init__(
        self,
        *,
        repository: ReviewAgentConfigRepository,
        audit_publisher: AutomatedReviewAuditPublisher,
        environment: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._audit_publisher = audit_publisher
        self._environment = environment
        self._clock = clock or (lambda: datetime.now(UTC))
        self._logged_events: list[dict[str, Any]] = []

    def create_config(
        self,
        command: CreateReviewAgentConfigCommand,
        *,
        context: ObservabilityContext,
        trusted_context: PropagatedContext,
    ) -> ReviewAgentConfigApplicationResult:
        started = monotonic()
        self._require_scope(trusted_context, "automated_review:write")
        self._require_context_matches_trusted(context, trusted_context)
        tenant_id = self._require_bridge_tenant(trusted_context)
        actor_subject_id = trusted_context.trusted.subject_id
        config = ReviewAgentConfiguration.create_draft(
            review_agent_config_id=command.review_agent_config_id,
            review_agent_config_version_id=command.review_agent_config_version_id,
            tenant_id=tenant_id,
            owner_subject_id=actor_subject_id,
            agent_version=command.agent_version,
            prompt=command.prompt,
            scope=command.scope,
            guardrails=command.guardrails,
            capabilities=command.capabilities,
            model_ref=command.model_ref,
            actor_subject_id=actor_subject_id,
            correlation_id=context.correlation_id,
            change_summary=command.change_summary,
            now=self._clock(),
        )
        self._repository.create(
            config,
            before_commit=lambda: self._publish_audit(
                "automated_review.config.created",
                config,
                context,
                actor_subject_id,
            ),
        )
        log = self._log_operation(
            context=context,
            operation="automated_review.config.create",
            status="accepted",
            duration_ms=_duration_ms(started),
            payload=command,
            extra=_safe_config_details(config),
        )
        return ReviewAgentConfigApplicationResult(config=config, logs=(log,))

    def update_config(
        self,
        command: UpdateReviewAgentConfigCommand,
        *,
        context: ObservabilityContext,
        trusted_context: PropagatedContext,
    ) -> ReviewAgentConfigApplicationResult:
        started = monotonic()
        self._require_scope(trusted_context, "automated_review:write")
        self._require_context_matches_trusted(context, trusted_context)
        config = self._get_existing(command, trusted_context)
        updated = config.update_draft(
            agent_version=command.agent_version,
            prompt=command.prompt,
            scope=command.scope,
            guardrails=command.guardrails,
            capabilities=command.capabilities,
            model_ref=command.model_ref,
            clear_model_ref=command.clear_model_ref,
            actor_subject_id=trusted_context.trusted.subject_id,
            correlation_id=context.correlation_id,
            change_summary=command.change_summary,
            now=self._clock(),
        )
        self._repository.save_existing(
            updated,
            expected_revision=config.revision,
            expected_status=config.status,
            before_commit=lambda: self._publish_audit(
                "automated_review.config.updated",
                updated,
                context,
                trusted_context.trusted.subject_id,
            ),
        )
        log = self._log_operation(
            context=context,
            operation="automated_review.config.update",
            status="accepted",
            duration_ms=_duration_ms(started),
            payload=command,
            extra=_safe_config_details(updated),
        )
        return ReviewAgentConfigApplicationResult(config=updated, logs=(log,))

    def publish_config(
        self,
        command: PublishReviewAgentConfigCommand,
        *,
        context: ObservabilityContext,
        trusted_context: PropagatedContext,
    ) -> ReviewAgentConfigApplicationResult:
        started = monotonic()
        self._require_scope(trusted_context, "automated_review:publish")
        self._require_context_matches_trusted(context, trusted_context)
        approval_reference = validate_agent_version(
            command.approval_reference, field_path="approval_reference"
        )
        published = config.publish(
            actor_subject_id=trusted_context.trusted.subject_id,
            correlation_id=context.correlation_id,
            change_summary=command.change_summary,
            approval_reference=approval_reference,
            now=self._clock(),
        )
        self._repository.save_existing(
            published,
            expected_revision=config.revision,
            expected_status=config.status,
            before_commit=lambda: self._publish_audit(
                "automated_review.config.published",
                published,
                context,
                trusted_context.trusted.subject_id,
            ),
        )
        log = self._log_operation(
            context=context,
            operation="automated_review.config.publish",
            status="accepted",
            duration_ms=_duration_ms(started),
            payload=command,
            extra=_safe_config_details(published),
        )
        return ReviewAgentConfigApplicationResult(config=published, logs=(log,))

    def create_config_version(
        self,
        command: CreateReviewAgentConfigVersionCommand,
        *,
        context: ObservabilityContext,
        trusted_context: PropagatedContext,
    ) -> ReviewAgentConfigApplicationResult:
        started = monotonic()
        self._require_scope(trusted_context, "automated_review:write")
        self._require_context_matches_trusted(context, trusted_context)
        tenant_id = self._require_bridge_tenant(trusted_context)
        config = self._repository.get(
            tenant_id=tenant_id,
            review_agent_config_id=command.review_agent_config_id,
            review_agent_config_version_id=command.current_review_agent_config_version_id,
        )
        if config is None:
            raise AutomatedReviewConfigNotFoundError()
        if (
            self._repository.get(
                tenant_id=tenant_id,
                review_agent_config_id=command.review_agent_config_id,
                review_agent_config_version_id=command.new_review_agent_config_version_id,
            )
            is not None
        ):
            raise AutomatedReviewConflictError(
                "nova versão já existe",
                code="automated_review_config_version_exists",
                field_path="new_review_agent_config_version_id",
            )
        next_version = config.create_new_version(
            new_review_agent_config_version_id=command.new_review_agent_config_version_id,
            actor_subject_id=trusted_context.trusted.subject_id,
            correlation_id=context.correlation_id,
            change_summary=command.change_summary,
            now=self._clock(),
        )
        self._publish_audit(
            "automated_review.config.version_created",
            next_version,
            context,
            trusted_context.trusted.subject_id,
        )
        self._repository.create(next_version)
        log = self._log_operation(
            context=context,
            operation="automated_review.config.create_version",
            status="accepted",
            duration_ms=_duration_ms(started),
            payload=command,
            extra=_safe_config_details(next_version),
        )
        return ReviewAgentConfigApplicationResult(config=next_version, logs=(log,))

    def get_config(
        self,
        command: GetReviewAgentConfigCommand,
        *,
        context: ObservabilityContext,
        trusted_context: PropagatedContext,
    ) -> ReviewAgentConfigApplicationResult:
        started = monotonic()
        self._require_scope(trusted_context, "automated_review:read")
        self._require_context_matches_trusted(context, trusted_context)
        config = self._get_existing(command, trusted_context)
        log = self._log_operation(
            context=context,
            operation="automated_review.config.get",
            status="accepted",
            duration_ms=_duration_ms(started),
            payload=command,
            extra=_safe_config_details(config),
        )
        return ReviewAgentConfigApplicationResult(config=config, logs=(log,))

    def _get_existing(
        self,
        command: (
            UpdateReviewAgentConfigCommand
            | PublishReviewAgentConfigCommand
            | GetReviewAgentConfigCommand
        ),
        trusted_context: PropagatedContext,
    ) -> ReviewAgentConfiguration:
        tenant_id = self._require_bridge_tenant(trusted_context)
        config = self._repository.get(
            tenant_id=tenant_id,
            review_agent_config_id=command.review_agent_config_id,
            review_agent_config_version_id=command.review_agent_config_version_id,
        )
        if config is None:
            raise AutomatedReviewConfigNotFoundError()
        return config

    def _require_bridge_tenant(self, trusted_context: PropagatedContext) -> str:
        if trusted_context.trusted.tenant_isolation_tier != "bridge":
            raise AutomatedReviewTenantContextError(
                "Automated Review suporta apenas tenant_isolation_tier=bridge no MVP",
                field_path="tenant_isolation_tier",
            )
        return trusted_context.trusted.tenant_id

    def _require_scope(self, trusted_context: PropagatedContext, required_scope: str) -> None:
        if required_scope not in trusted_context.trusted.scopes:
            raise PermissionError("escopo insuficiente")

    def _require_context_matches_trusted(
        self,
        context: ObservabilityContext,
        trusted_context: PropagatedContext,
    ) -> None:
        expected = {
            "tenant_id": trusted_context.trusted.tenant_id,
            "tenant_isolation_tier": trusted_context.trusted.tenant_isolation_tier,
            "correlation_id": trusted_context.correlation_id,
            "request_id": trusted_context.request_id,
            "trace_id": trusted_context.trace_id,
        }
        actual = {
            "tenant_id": context.tenant_id,
            "tenant_isolation_tier": context.tenant_isolation_tier,
            "correlation_id": context.correlation_id,
            "request_id": context.request_id,
            "trace_id": context.trace_id,
        }
        for field_name, expected_value in expected.items():
            actual_value = actual[field_name]
            if actual_value is not None and actual_value != expected_value:
                raise AutomatedReviewTenantContextError(
                    "contexto observável diverge do contexto confiável",
                    field_path=field_name,
                )

    def _publish_audit(
        self,
        event_type: str,
        config: ReviewAgentConfiguration,
        context: ObservabilityContext,
        actor_subject_id: str,
    ) -> None:
        last_change = config.changelog[-1]
        self._audit_publisher.publish(
            AutomatedReviewAuditIntent(
                event_type=event_type,
                tenant_id=config.tenant_id,
                actor_subject_id=actor_subject_id,
                review_agent_config_id=config.review_agent_config_id,
                review_agent_config_version_id=config.review_agent_config_version_id,
                correlation_id=context.correlation_id,
                occurred_at=last_change.occurred_at.isoformat(),
                change_summary=last_change.change_summary,
                previous_revision=last_change.previous_revision,
                resulting_revision=last_change.resulting_revision,
                safe_details=_safe_config_details(config),
            )
        )

    def _log_operation(
        self,
        *,
        context: ObservabilityContext,
        operation: str,
        status: str,
        duration_ms: float,
        payload: Any | None = None,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        event = build_structured_log(
            context=context,
            service_name=SERVICE_NAME,
            service_version=SERVICE_VERSION,
            environment=self._environment,
            operation=operation,
            source="automated_review.application",
            destination="automated_review.domain",
            contract=CONTRACT,
            contract_version=CONTRACT_VERSION,
            status=status,
            duration_ms=duration_ms,
            payload=payload,
            extra=extra,
        )
        self._logged_events.append(event)
        return event


def _safe_config_details(config: ReviewAgentConfiguration) -> dict[str, str]:
    details = {
        "review_agent_config_id": config.review_agent_config_id,
        "review_agent_config_version_id": config.review_agent_config_version_id,
        "status": config.status,
        "revision": str(config.revision),
        "product_type": config.product_type,
        "agent_version": config.agent_version,
        "prompt_version": config.prompt.prompt_version,
        "prompt_fingerprint": config.prompt.prompt_fingerprint,
        "channel_count": str(len(config.scope.channels)),
        "review_purpose_count": str(len(config.scope.review_purposes)),
        "consultative_only": str(config.capabilities.consultative_only).lower(),
        "fallback_action": config.guardrails.fallback_action,
    }
    if config.approval_reference is not None:
        details["approval_reference"] = config.approval_reference
    if config.model_ref is not None:
        details["provider_ref"] = config.model_ref.provider_ref
        details["model_ref"] = config.model_ref.model_ref
        if config.model_ref.model_version is not None:
            details["model_version"] = config.model_ref.model_version
    return details


def _duration_ms(started: float) -> float:
    return round((monotonic() - started) * 1000, 3)
