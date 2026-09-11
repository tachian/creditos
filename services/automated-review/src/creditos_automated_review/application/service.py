from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from itertools import islice
from time import monotonic
from typing import Any

from creditos_observability.context import ObservabilityContext
from creditos_observability.logging import build_structured_log
from creditos_security import PropagatedContext

from creditos_automated_review.application.ports import (
    AutomatedReviewAuditIntent,
    AutomatedReviewAuditPublisher,
    AutomatedReviewExecutionAuditIntent,
    AutomatedReviewExecutionAuditPublisher,
    ConsultativeEvidenceRepository,
    ConsultativeReviewExecutionInput,
    ConsultativeReviewExecutor,
    ConsultativeReviewOutput,
    ReviewAgentConfigRepository,
    ReviewExecutionRepository,
)
from creditos_automated_review.domain.entities import (
    AutomatedReviewExecutionRequest,
    AutomatedReviewExecutionResult,
    ConsultativeEvidence,
    ReviewAgentConfiguration,
)
from creditos_automated_review.domain.errors import (
    AutomatedReviewConfigNotFoundError,
    AutomatedReviewConflictError,
    AutomatedReviewTenantContextError,
    AutomatedReviewValidationError,
)
from creditos_automated_review.domain.value_objects import (
    InputMinimizationPlan,
    ReviewAgentCapabilities,
    ReviewAgentGuardrails,
    ReviewAgentPrompt,
    ReviewAgentScope,
    ReviewInputCandidate,
    ReviewModelRef,
    ReviewOutputItem,
    ReviewOutputValidationResult,
)
from creditos_automated_review.domain.value_objects.review_agent_config import (
    validate_agent_version,
)
from creditos_automated_review.domain.value_objects.review_execution import (
    validate_non_sensitive_execution_reference,
)

SERVICE_NAME = "automated-review"
SERVICE_VERSION = "0.1.0"
CONTRACT = "automated-review.application"
CONTRACT_VERSION = "v1"
MAX_EXECUTOR_OUTPUT_ITEMS = 32


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
class ExecuteConsultativeReviewCommand:
    execution_id: str
    proposal_id: str
    product_type: str
    channel: str
    review_purpose: str
    candidate_inputs: tuple[ReviewInputCandidate, ...]
    review_agent_config_id: str | None = None
    review_agent_config_version_id: str | None = None


@dataclass(frozen=True, slots=True)
class GetConsultativeEvidenceByExecutionCommand:
    execution_id: str


@dataclass(frozen=True, slots=True)
class ListConsultativeEvidenceByProposalCommand:
    proposal_id: str


@dataclass(frozen=True, slots=True)
class ReviewAgentConfigApplicationResult:
    config: ReviewAgentConfiguration
    logs: tuple[dict[str, Any], ...]


@dataclass(frozen=True, slots=True)
class ReviewExecutionApplicationResult:
    execution: AutomatedReviewExecutionResult
    logs: tuple[dict[str, Any], ...]
    consultative_evidence: ConsultativeEvidence | None = None


@dataclass(frozen=True, slots=True)
class ConsultativeEvidenceApplicationResult:
    evidence: ConsultativeEvidence | None = None
    evidences: tuple[ConsultativeEvidence, ...] = ()
    logs: tuple[dict[str, Any], ...] = ()


class AutomatedReviewApplicationService:
    def __init__(
        self,
        *,
        repository: ReviewAgentConfigRepository,
        audit_publisher: AutomatedReviewAuditPublisher,
        environment: str,
        execution_repository: ReviewExecutionRepository | None = None,
        consultative_evidence_repository: ConsultativeEvidenceRepository | None = None,
        execution_audit_publisher: AutomatedReviewExecutionAuditPublisher | None = None,
        consultative_executor: ConsultativeReviewExecutor | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._audit_publisher = audit_publisher
        self._execution_repository = execution_repository
        self._consultative_evidence_repository = consultative_evidence_repository
        self._execution_audit_publisher = execution_audit_publisher
        self._consultative_executor = consultative_executor
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
        config = self._get_existing(command, trusted_context)
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

    def execute_consultative_review(
        self,
        command: ExecuteConsultativeReviewCommand,
        *,
        context: ObservabilityContext,
        trusted_context: PropagatedContext,
    ) -> ReviewExecutionApplicationResult:
        started = monotonic()
        self._require_scope(trusted_context, "automated_review:execute")
        self._require_context_matches_trusted(context, trusted_context, require_complete=True)
        tenant_id = self._require_bridge_tenant(trusted_context)
        request = AutomatedReviewExecutionRequest.create(
            execution_id=command.execution_id,
            proposal_id=command.proposal_id,
            product_type=command.product_type,
            channel=command.channel,
            review_purpose=command.review_purpose,
            candidate_inputs=command.candidate_inputs,
        )
        execution_repository = self._require_execution_repository()
        config = self._resolve_referenceable_config(command, tenant_id)
        plan = request.build_minimization_plan(config)
        execution_repository.reserve(tenant_id=tenant_id, execution_id=request.execution_id)
        execution_input = ConsultativeReviewExecutionInput(
            tenant_id=tenant_id,
            execution_id=request.execution_id,
            proposal_id=request.proposal_id,
            review_agent_config_id=config.review_agent_config_id,
            review_agent_config_version_id=config.review_agent_config_version_id,
            product_type=request.product_type,
            channel=request.channel,
            review_purpose=request.review_purpose,
            minimization_policy_ref=plan.policy_ref,
            prompt_fingerprint=plan.prompt_fingerprint,
            input_for_execution=plan.input_for_execution,
        )
        executor = self._require_consultative_executor()
        try:
            output = executor.execute(execution_input)
            output_validation = _validate_executor_output(output)
            execution = AutomatedReviewExecutionResult(
                execution_id=request.execution_id,
                tenant_id=tenant_id,
                proposal_id=request.proposal_id,
                review_agent_config_id=config.review_agent_config_id,
                review_agent_config_version_id=config.review_agent_config_version_id,
                product_type=request.product_type,
                channel=request.channel,
                review_purpose=request.review_purpose,
                minimization_policy_ref=plan.policy_ref,
                prompt_fingerprint=plan.prompt_fingerprint,
                input_fields=plan.fields,
                occurred_at=self._clock(),
                status=output.status,
                finding_refs=output_validation.finding_refs,
                limitation_refs=output_validation.limitation_refs,
                output_validation_status=output_validation.status,
                accepted_output_counts_by_type=output_validation.accepted_counts_by_type,
                blocked_output_counts_by_reason=output_validation.blocked_counts_by_reason,
            )
        except AutomatedReviewValidationError as error:
            output_validation = _blocked_output_validation(error)
            execution = _fallback_execution_result(
                request=request,
                config=config,
                plan=plan,
                occurred_at=self._clock(),
                limitation_ref=_fallback_limitation_ref(error),
                fallback_reason_refs=output_validation.limitation_refs,
                output_validation=output_validation,
            )
        except Exception:
            output_validation = ReviewOutputValidationResult.blocked(
                reason_refs=("reason_executor_failure",),
                blocked_counts_by_reason={"reason_executor_failure": 1},
            )
            execution = _fallback_execution_result(
                request=request,
                config=config,
                plan=plan,
                occurred_at=self._clock(),
                limitation_ref="limitation_executor_failure",
                fallback_reason_refs=output_validation.limitation_refs,
                output_validation=output_validation,
            )
        evidence_repository = self._consultative_evidence_repository
        consultative_evidence = (
            _consultative_evidence_from_result(
                execution=execution,
                output_validation=output_validation,
                config=config,
                context=context,
            )
            if evidence_repository is not None
            else None
        )

        def before_execution_commit() -> None:
            if consultative_evidence is not None and evidence_repository is not None:
                evidence_to_create = consultative_evidence
                evidence_repository.create(
                    evidence_to_create,
                    before_commit=lambda: self._publish_consultative_evidence_audit(
                        evidence_to_create,
                        context,
                        trusted_context.trusted.subject_id,
                    ),
                )
            self._publish_execution_audit(
                _execution_event_type(execution),
                execution,
                context,
                trusted_context.trusted.subject_id,
                config=config,
            )

        execution_repository.create(
            execution,
            before_commit=before_execution_commit,
        )
        log = self._log_operation(
            context=context,
            operation="automated_review.execution.execute_consultative",
            status=_execution_log_status(execution),
            duration_ms=_duration_ms(started),
            payload=command,
            extra=_safe_execution_details(
                execution,
                evidence=consultative_evidence,
                config=config,
            ),
        )
        return ReviewExecutionApplicationResult(
            execution=execution,
            logs=(log,),
            consultative_evidence=consultative_evidence,
        )

    def get_consultative_evidence_by_execution(
        self,
        command: GetConsultativeEvidenceByExecutionCommand,
        *,
        context: ObservabilityContext,
        trusted_context: PropagatedContext,
    ) -> ConsultativeEvidenceApplicationResult:
        started = monotonic()
        self._require_scope(trusted_context, "automated_review:read")
        self._require_context_matches_trusted(context, trusted_context, require_complete=True)
        tenant_id = self._require_bridge_tenant(trusted_context)
        execution_id = _validate_evidence_lookup_reference(
            command.execution_id,
            field_path="execution_id",
        )
        evidence = self._require_consultative_evidence_repository().get_by_execution(
            tenant_id=tenant_id,
            execution_id=execution_id,
        )
        log = self._log_operation(
            context=context,
            operation="automated_review.evidence.get_by_execution",
            status="accepted",
            duration_ms=_duration_ms(started),
            payload=command,
            extra=_safe_evidence_lookup_details(evidence),
        )
        return ConsultativeEvidenceApplicationResult(
            evidence=evidence,
            evidences=() if evidence is None else (evidence,),
            logs=(log,),
        )

    def list_consultative_evidences_by_proposal(
        self,
        command: ListConsultativeEvidenceByProposalCommand,
        *,
        context: ObservabilityContext,
        trusted_context: PropagatedContext,
    ) -> ConsultativeEvidenceApplicationResult:
        started = monotonic()
        self._require_scope(trusted_context, "automated_review:read")
        self._require_context_matches_trusted(context, trusted_context, require_complete=True)
        tenant_id = self._require_bridge_tenant(trusted_context)
        proposal_id = _validate_evidence_lookup_reference(
            command.proposal_id,
            field_path="proposal_id",
        )
        evidences = self._require_consultative_evidence_repository().list_by_proposal(
            tenant_id=tenant_id,
            proposal_id=proposal_id,
        )
        log = self._log_operation(
            context=context,
            operation="automated_review.evidence.list_by_proposal",
            status="accepted",
            duration_ms=_duration_ms(started),
            payload=command,
            extra=_safe_evidence_collection_lookup_details(evidences),
        )
        return ConsultativeEvidenceApplicationResult(evidences=evidences, logs=(log,))

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

    def _resolve_referenceable_config(
        self,
        command: ExecuteConsultativeReviewCommand,
        tenant_id: str,
    ) -> ReviewAgentConfiguration:
        configs = self._repository.list_published_by_scope(
            tenant_id=tenant_id,
            product_type=command.product_type,
            channel=command.channel,
            review_purpose=command.review_purpose,
        )
        if command.review_agent_config_id is not None:
            configs = tuple(
                config
                for config in configs
                if config.review_agent_config_id == command.review_agent_config_id
            )
        if command.review_agent_config_version_id is not None:
            configs = tuple(
                config
                for config in configs
                if config.review_agent_config_version_id == command.review_agent_config_version_id
            )
        if not configs:
            raise AutomatedReviewConfigNotFoundError()
        if len(configs) > 1:
            raise AutomatedReviewConflictError(
                "resolução de configuração publicada ambígua",
                code="automated_review_config_resolution_ambiguous",
                field_path="review_agent_config_version_id",
            )
        return sorted(
            configs,
            key=lambda config: (
                config.review_agent_config_id,
                config.review_agent_config_version_id,
            ),
        )[-1]

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
        *,
        require_complete: bool = False,
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
            if require_complete and expected_value is not None and actual_value is None:
                raise AutomatedReviewTenantContextError(
                    "contexto observável incompleto para rastreabilidade",
                    field_path=field_name,
                )
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

    def _publish_execution_audit(
        self,
        event_type: str,
        execution: AutomatedReviewExecutionResult,
        context: ObservabilityContext,
        actor_subject_id: str,
        *,
        config: ReviewAgentConfiguration | None = None,
    ) -> None:
        self._require_execution_audit_publisher().publish(
            AutomatedReviewExecutionAuditIntent(
                event_type=event_type,
                tenant_id=execution.tenant_id,
                actor_subject_id=actor_subject_id,
                execution_id=execution.execution_id,
                proposal_id=execution.proposal_id,
                review_agent_config_id=execution.review_agent_config_id,
                review_agent_config_version_id=execution.review_agent_config_version_id,
                correlation_id=context.correlation_id,
                request_id=context.request_id,
                trace_id=context.trace_id,
                tenant_isolation_tier=context.tenant_isolation_tier or "",
                occurred_at=execution.occurred_at.isoformat(),
                safe_details=_safe_execution_details(execution, config=config),
            )
        )

    def _publish_consultative_evidence_audit(
        self,
        evidence: ConsultativeEvidence,
        context: ObservabilityContext,
        actor_subject_id: str,
    ) -> None:
        self._require_execution_audit_publisher().publish(
            AutomatedReviewExecutionAuditIntent(
                event_type="automated_review.evidence.created",
                tenant_id=evidence.tenant_id,
                actor_subject_id=actor_subject_id,
                execution_id=evidence.execution_id,
                proposal_id=evidence.proposal_id,
                review_agent_config_id=evidence.review_agent_config_id,
                review_agent_config_version_id=evidence.review_agent_config_version_id,
                correlation_id=context.correlation_id,
                request_id=context.request_id,
                trace_id=context.trace_id,
                tenant_isolation_tier=context.tenant_isolation_tier or "",
                occurred_at=evidence.occurred_at.isoformat(),
                safe_details=_safe_consultative_evidence_details(evidence),
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

    def _require_execution_repository(self) -> ReviewExecutionRepository:
        if self._execution_repository is None:
            raise RuntimeError("execution_repository não configurado")
        return self._execution_repository

    def _require_execution_audit_publisher(self) -> AutomatedReviewExecutionAuditPublisher:
        if self._execution_audit_publisher is None:
            raise RuntimeError("execution_audit_publisher não configurado")
        return self._execution_audit_publisher

    def _require_consultative_evidence_repository(self) -> ConsultativeEvidenceRepository:
        if self._consultative_evidence_repository is None:
            raise RuntimeError("consultative_evidence_repository não configurado")
        return self._consultative_evidence_repository

    def _require_consultative_executor(self) -> ConsultativeReviewExecutor:
        if self._consultative_executor is None:
            raise RuntimeError("consultative_executor não configurado")
        return self._consultative_executor


def _fallback_execution_result(
    *,
    request: AutomatedReviewExecutionRequest,
    config: ReviewAgentConfiguration,
    plan: InputMinimizationPlan,
    occurred_at: datetime,
    limitation_ref: str,
    fallback_reason_refs: tuple[str, ...] = (),
    output_validation: ReviewOutputValidationResult | None = None,
) -> AutomatedReviewExecutionResult:
    output_validation = output_validation or ReviewOutputValidationResult.blocked(
        reason_refs=(_fallback_output_reason_ref(limitation_ref),),
        blocked_counts_by_reason={_fallback_output_reason_ref(limitation_ref): 1},
    )
    fallback_reason_refs = fallback_reason_refs or output_validation.limitation_refs
    return AutomatedReviewExecutionResult(
        execution_id=request.execution_id,
        tenant_id=config.tenant_id,
        proposal_id=request.proposal_id,
        review_agent_config_id=config.review_agent_config_id,
        review_agent_config_version_id=config.review_agent_config_version_id,
        product_type=request.product_type,
        channel=request.channel,
        review_purpose=request.review_purpose,
        minimization_policy_ref=plan.policy_ref,
        prompt_fingerprint=plan.prompt_fingerprint,
        input_fields=plan.fields,
        occurred_at=occurred_at,
        status="fallback",
        limitation_refs=(limitation_ref,),
        fallback_action=config.guardrails.fallback_action,
        fallback_reason_refs=fallback_reason_refs,
        output_validation_status=output_validation.status,
        accepted_output_counts_by_type=output_validation.accepted_counts_by_type,
        blocked_output_counts_by_reason=output_validation.blocked_counts_by_reason,
    )


def _consultative_evidence_from_result(
    *,
    execution: AutomatedReviewExecutionResult,
    output_validation: ReviewOutputValidationResult,
    config: ReviewAgentConfiguration,
    context: ObservabilityContext,
) -> ConsultativeEvidence | None:
    if execution.status != "completed" or output_validation.status != "accepted":
        return None
    return ConsultativeEvidence.from_execution(
        execution=execution,
        output_validation=output_validation,
        config=config,
        correlation_id=context.correlation_id,
        trace_id=context.trace_id,
    )


def _validate_evidence_lookup_reference(value: str, *, field_path: str) -> str:
    return validate_non_sensitive_execution_reference(
        validate_agent_version(value, field_path=field_path),
        field_path=field_path,
    )


def _validate_executor_output(output: ConsultativeReviewOutput) -> ReviewOutputValidationResult:
    if output.status != "completed":
        raise AutomatedReviewValidationError(
            "status de saída consultiva inválido",
            code="automated_review_invalid_executor_output_status",
            field_path="executor_output.status",
        )
    if output.finding_refs or output.limitation_refs:
        raise AutomatedReviewValidationError(
            "campos legados de saída consultiva não são permitidos",
            code="automated_review_legacy_output_fields_not_allowed",
            field_path="executor_output",
        )
    raw_items = tuple(islice(output.output_items, MAX_EXECUTOR_OUTPUT_ITEMS + 1))
    if len(raw_items) > MAX_EXECUTOR_OUTPUT_ITEMS:
        raise AutomatedReviewValidationError(
            "quantidade de itens de saída consultiva excede o limite",
            code="automated_review_output_item_limit_exceeded",
            field_path="executor_output.output_items",
        )
    if not raw_items:
        raise AutomatedReviewValidationError(
            "saída consultiva sem itens governados",
            code="automated_review_empty_executor_output",
            field_path="executor_output.output_items",
        )
    items: list[ReviewOutputItem] = []
    for index, item in enumerate(raw_items):
        if isinstance(item, ReviewOutputItem):
            items.append(item)
            continue
        if isinstance(item, Mapping):
            items.append(ReviewOutputItem.from_mapping(item, index=index))
            continue
        raise AutomatedReviewValidationError(
            "item de saída consultiva inválido",
            code="automated_review_invalid_output_item",
            field_path=f"output_items[{index}]",
        )
    return ReviewOutputValidationResult.accepted(items=tuple(items))


def _blocked_output_validation(
    error: AutomatedReviewValidationError,
) -> ReviewOutputValidationResult:
    reason_ref = _output_block_reason_ref(error)
    return ReviewOutputValidationResult.blocked(
        reason_refs=(reason_ref,),
        blocked_counts_by_reason={reason_ref: 1},
    )


_OUTPUT_SCHEMA_ERROR_CODES = frozenset(
    {
        "automated_review_unknown_output_field",
        "automated_review_missing_output_field",
        "automated_review_invalid_output_field",
        "automated_review_invalid_output_item",
        "automated_review_invalid_output_item_type",
        "automated_review_invalid_output_severity",
        "automated_review_invalid_output_confidence",
        "automated_review_invalid_output_summary",
        "automated_review_output_evidence_limit_exceeded",
        "automated_review_duplicate_output_item_ref",
        "automated_review_empty_executor_output",
        "automated_review_output_item_limit_exceeded",
    }
)


def _output_block_reason_ref(error: AutomatedReviewValidationError) -> str:
    if error.code in {
        "automated_review_sensitive_output_content",
        "automated_review_output_prompt_injection",
        "automated_review_autonomous_output_content",
        "automated_review_autonomous_execution_output",
        "automated_review_autonomous_output_reference",
    }:
        return "reason_blocked_output_guardrail"
    if error.code in _OUTPUT_SCHEMA_ERROR_CODES:
        return "reason_invalid_output_schema"
    return "reason_invalid_output_contract"


def _fallback_limitation_ref(error: AutomatedReviewValidationError) -> str:
    reason_ref = _output_block_reason_ref(error)
    if reason_ref == "reason_blocked_output_guardrail":
        return "limitation_output_guardrail_blocked"
    if reason_ref == "reason_invalid_output_schema":
        return "limitation_invalid_output_schema"
    return "limitation_invalid_executor_output"


def _fallback_output_reason_ref(limitation_ref: str) -> str:
    if limitation_ref == "limitation_executor_failure":
        return "reason_executor_failure"
    if limitation_ref == "limitation_invalid_executor_output":
        return "reason_invalid_output_contract"
    if limitation_ref == "limitation_invalid_output_schema":
        return "reason_invalid_output_schema"
    if limitation_ref == "limitation_output_guardrail_blocked":
        return "reason_blocked_output_guardrail"
    return "reason_fallback_execution"


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


def _safe_execution_details(
    execution: AutomatedReviewExecutionResult,
    *,
    evidence: ConsultativeEvidence | None = None,
    config: ReviewAgentConfiguration | None = None,
) -> dict[str, str]:
    counts = _execution_action_counts(execution)
    details = {
        "execution_id": execution.execution_id,
        "proposal_id": execution.proposal_id,
        "review_agent_config_id": execution.review_agent_config_id,
        "review_agent_config_version_id": execution.review_agent_config_version_id,
        "product_type": execution.product_type,
        "channel": execution.channel,
        "review_purpose": execution.review_purpose,
        "classification": execution.classification,
        "status": execution.status,
        "minimization_policy_ref": execution.minimization_policy_ref,
        "prompt_fingerprint": execution.prompt_fingerprint,
        "input_field_count": str(len(execution.input_fields)),
        "included_field_count": str(counts.get("included", 0)),
        "masked_field_count": str(counts.get("masked", 0)),
        "omitted_field_count": str(counts.get("omitted", 0)),
        "referenced_field_count": str(counts.get("referenced", 0)),
        "tokenized_field_count": str(counts.get("tokenized", 0)),
        "output_validation_status": execution.output_validation_status,
        "accepted_output_missing_data_count": str(
            execution.accepted_output_counts_by_type.get("missing_data", 0)
        ),
        "accepted_output_inconsistency_count": str(
            execution.accepted_output_counts_by_type.get("inconsistency", 0)
        ),
        "accepted_output_explainability_factor_count": str(
            execution.accepted_output_counts_by_type.get("explainability_factor", 0)
        ),
        "accepted_output_limitation_count": str(
            execution.accepted_output_counts_by_type.get("limitation", 0)
        ),
        "blocked_output_item_count": str(sum(execution.blocked_output_counts_by_reason.values())),
        "blocked_output_reason_count": str(len(execution.blocked_output_counts_by_reason)),
        "raw_payload_persisted": "false",
        "prompt_payload_persisted": "false",
        "raw_output_persisted": "false",
        "consultative_evidence_created": str(evidence is not None).lower(),
    }
    if execution.fallback_action is not None:
        details["fallback_action"] = execution.fallback_action
        details["fallback_reason_count"] = str(len(execution.fallback_reason_refs))
    if execution.fallback_reason_refs:
        details["fallback_reason_ref"] = execution.fallback_reason_refs[0]
        for index, reason_ref in enumerate(execution.fallback_reason_refs):
            details[f"fallback_reason_ref_{index}"] = reason_ref
    if execution.limitation_refs:
        details["limitation_ref"] = execution.limitation_refs[0]
        for index, limitation_ref in enumerate(execution.limitation_refs):
            details[f"limitation_ref_{index}"] = limitation_ref
    if _config_matches_execution(config, execution) and config is not None and config.model_ref:
        details["provider_ref"] = config.model_ref.provider_ref
        details["model_ref"] = config.model_ref.model_ref
        if config.model_ref.model_version is not None:
            details["model_version"] = config.model_ref.model_version
    if evidence is not None:
        details.update(_safe_consultative_evidence_details(evidence))
    for reason_ref, count in execution.blocked_output_counts_by_reason.items():
        details[f"blocked_output_{reason_ref}_count"] = str(count)
    return details


def _config_matches_execution(
    config: ReviewAgentConfiguration | None,
    execution: AutomatedReviewExecutionResult,
) -> bool:
    if config is None:
        return False
    return (
        config.review_agent_config_id == execution.review_agent_config_id
        and config.review_agent_config_version_id == execution.review_agent_config_version_id
        and config.tenant_id == execution.tenant_id
    )


def _safe_consultative_evidence_details(evidence: ConsultativeEvidence) -> dict[str, str]:
    details = {
        "consultative_evidence_id": evidence.consultative_evidence_id,
        "proposal_id": evidence.proposal_id,
        "execution_id": evidence.execution_id,
        "review_agent_config_id": evidence.review_agent_config_id,
        "review_agent_config_version_id": evidence.review_agent_config_version_id,
        "agent_version": evidence.agent_version,
        "product_type": evidence.product_type,
        "channel": evidence.channel,
        "review_purpose": evidence.review_purpose,
        "classification": evidence.classification,
        "minimization_policy_ref": evidence.minimization_policy_ref,
        "prompt_fingerprint": evidence.prompt_fingerprint,
        "correlation_id": evidence.correlation_id,
        "trace_id_present": str(evidence.trace_id is not None).lower(),
        "consultative_evidence_item_count": str(len(evidence.items)),
        "consultative_evidence_missing_data_count": str(
            evidence.counts_by_type.get("missing_data", 0)
        ),
        "consultative_evidence_inconsistency_count": str(
            evidence.counts_by_type.get("inconsistency", 0)
        ),
        "consultative_evidence_explainability_factor_count": str(
            evidence.counts_by_type.get("explainability_factor", 0)
        ),
        "consultative_evidence_limitation_count": str(evidence.counts_by_type.get("limitation", 0)),
        "consultative_evidence_confidence_present_count": str(evidence.confidence_present_count),
        "raw_payload_persisted": "false",
        "prompt_payload_persisted": "false",
        "raw_output_persisted": "false",
    }
    if evidence.provider_ref is not None:
        details["provider_ref"] = evidence.provider_ref
    if evidence.model_ref is not None:
        details["model_ref"] = evidence.model_ref
    if evidence.model_version is not None:
        details["model_version"] = evidence.model_version
    return details


def _safe_evidence_lookup_details(evidence: ConsultativeEvidence | None) -> dict[str, str]:
    details = {
        "consultative_evidence_found": str(evidence is not None).lower(),
        "raw_payload_persisted": "false",
        "prompt_payload_persisted": "false",
        "raw_output_persisted": "false",
    }
    if evidence is not None:
        details.update(_safe_consultative_evidence_details(evidence))
    return details


def _safe_evidence_collection_lookup_details(
    evidences: tuple[ConsultativeEvidence, ...],
) -> dict[str, str]:
    return {
        "consultative_evidence_count": str(len(evidences)),
        "raw_payload_persisted": "false",
        "prompt_payload_persisted": "false",
        "raw_output_persisted": "false",
    }


def _execution_action_counts(execution: AutomatedReviewExecutionResult) -> dict[str, int]:
    counts: dict[str, int] = {}
    for field in execution.input_fields:
        counts[field.action] = counts.get(field.action, 0) + 1
    return counts


def _execution_event_type(execution: AutomatedReviewExecutionResult) -> str:
    return f"automated_review.execution.{execution.status}"


def _execution_log_status(execution: AutomatedReviewExecutionResult) -> str:
    if execution.status == "completed":
        return "accepted"
    return execution.status


def _duration_ms(started: float) -> float:
    return round((monotonic() - started) * 1000, 3)
