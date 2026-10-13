from __future__ import annotations

import hmac
import importlib.util
import json
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from hashlib import sha256
from pathlib import Path
from typing import Any

from creditos_audit_evidence.adapters.persistence import InMemoryAuditEventRepository
from creditos_audit_evidence.application.service import (
    AuditEvidenceApplicationService,
    RegisterAuditEventCommand,
)
from creditos_audit_evidence.domain.entities import OperationalEvidenceReference
from creditos_decision.adapters.external.audit_evidence_publisher import (
    AuditEvidenceDecisionAuditPublisher,
)
from creditos_decision.adapters.persistence import (
    InMemoryCreditDecisionRepository,
    InMemoryCreditPolicyRepository,
    InMemoryPolicySimulationRepository,
    InMemoryReasonCodeCatalogRepository,
)
from creditos_decision.application.ports import DecisionAuditIntent
from creditos_decision.application.service import (
    CreateCreditPolicyDraftCommand,
    DecisionApplicationService,
    ExecuteCreditDecisionCommand,
    GetPublicCreditDecisionByProposalCommand,
    PublicCreditDecisionErrorResponse,
    PublicCreditDecisionResponse,
    PublishCreditPolicyCommand,
    RunPolicySimulationCommand,
)
from creditos_decision.domain.entities import ReasonCodeCatalog
from creditos_decision.domain.value_objects import (
    CreditDecisionInputFieldValue,
    ExplainableFactor,
    PolicyApplicability,
    PolicyCriterion,
    PolicyLimit,
    PolicyRule,
    PolicySimulationInputCase,
    ReasonCode,
)
from creditos_integration.adapters.events import (
    InMemoryIntegrationExecutionDispatcher,
    InMemoryWebhookDeliveryDispatcher,
)
from creditos_integration.adapters.external import InMemoryMockIntegrationAdapterRegistry
from creditos_integration.adapters.persistence import (
    InMemoryIntegrationCatalogRepository,
    InMemoryIntegrationDlqStore,
    InMemoryIntegrationExecutionStore,
    InMemoryWebhookConfigurationRepository,
    InMemoryWebhookDeliveryDlqStore,
    InMemoryWebhookDeliveryStore,
)
from creditos_integration.application.ports.adapter_registry import InMemoryAdapterRegistry
from creditos_integration.application.ports.audit_event_publisher import InMemoryAuditEventPublisher
from creditos_integration.application.ports.webhook_delivery import (
    InMemoryWebhookDeliveryAdapter,
    StaticWebhookSigningKeyResolver,
    WebhookDeliveryAdapterResult,
    WebhookDeliveryRequest,
    canonical_webhook_payload,
)
from creditos_integration.application.service import (
    BuildIntegrationPlanCommand,
    ConfigureIntegrationClassCommand,
    ConfigureWebhookCommand,
    DispatchWebhookNotificationCommand,
    ExecuteMockIntegrationCommand,
    IntegrationCatalogApplicationService,
    StartIntegrationExecutionCommand,
)
from creditos_observability.context import ObservabilityContext
from creditos_proposal_intake.adapters.persistence import (
    InMemoryCanonicalProposalRepository,
    InMemoryIdempotentProposalSubmissionRepository,
    InMemoryProposalIntakeStatusRepository,
    InMemoryProposalOutboxRepository,
)
from creditos_proposal_intake.application.service import (
    ProposalIntakeApplicationService,
    SubmitProposalWithInitialStatusCommand,
)
from creditos_reporting_insights.adapters.persistence import (
    in_memory_business_projection_repository as projection_repositories,
)
from creditos_reporting_insights.application.service import ReportingInsightsService
from creditos_reporting_insights.domain.entities.business_metrics_projection import (
    BusinessMetricsSnapshot,
)
from creditos_reporting_insights.domain.value_objects.business_events import (
    BusinessEvent,
    CallbackStatus,
    Channel,
    DecisionOutcome,
    DecisionQueryStatus,
    IntegrationStatus,
    ProductType,
    ProposalFunnelStatus,
)
from creditos_security import PropagatedContext, TrustedContext

_TENANT_ID = "tenant_alpha"
_OTHER_TENANT_ID = "tenant_beta"
_CORRELATION_ID = "corr_e2e_alpha"
_REQUEST_ID = "req_e2e_alpha"
_TRACE_ID = "1234567890abcdef1234567890abcdef"
_SPAN_ID = "1234567890abcdef"
_NOW = datetime(2026, 10, 12, 12, 0, tzinfo=UTC)
_SIGNING_KEY_REF = "wkey_creditos_callback_v1"
_SIGNING_SECRET = b"local-signing-key"
_PUBLIC_CALLBACK_IP = "93.184.216.34"
_SENSITIVE_FINGERPRINT_KEY = "local-test-fingerprint-key-32-chars"
_ROOT = Path(__file__).resolve().parents[1]
_MVP_CLASSES = ("kyc_kyb", "credit_bureau", "anti_fraud", "receivables")
_ADAPTER_BY_CLASS = {
    "kyc_kyb": "mock-kyc-basic-v1",
    "credit_bureau": "mock-credit-bureau-v1",
    "anti_fraud": "mock-antifraud-v1",
    "receivables": "mock-receivables-v1",
}
_SENSITIVE_FRAGMENTS = (
    "00000000191",
    "Pessoa Exemplo",
    "cliente.sensivel@example.com",
    "declared_monthly_income",
    "provider_payload",
    "raw_payload",
    "Authorization",
    "Bearer",
    "access_token",
)
_SENSITIVE_KEY_PARTS = frozenset(
    {
        "authorization",
        "bearer",
        "cnpj",
        "cpf",
        "credential",
        "declared_monthly_income",
        "document",
        "email",
        "name",
        "nome",
        "password",
        "phone",
        "provider_payload",
        "raw_payload",
        "secret",
        "telefone",
        "token",
    }
)
_REQUIRED_TRACEABILITY_STEPS = frozenset(
    {
        "proposal",
        "integration",
        "decision",
        "public_query",
        "webhook",
    }
)


@dataclass(frozen=True, slots=True)
class ProposalHarness:
    service: ProposalIntakeApplicationService
    repository: InMemoryCanonicalProposalRepository
    idempotency_repository: InMemoryIdempotentProposalSubmissionRepository
    intake_status_repository: InMemoryProposalIntakeStatusRepository
    outbox_repository: InMemoryProposalOutboxRepository


@dataclass(frozen=True, slots=True)
class IntegrationHarness:
    service: IntegrationCatalogApplicationService
    webhook_adapter: InMemoryWebhookDeliveryAdapter
    webhook_delivery_store: InMemoryWebhookDeliveryStore


@dataclass(frozen=True, slots=True)
class DecisionSummary:
    status: str
    outcome: str
    policy_version_id: str
    reason_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MockedAnalysisFlowResult:
    correlation_id: str
    proposal_id: str
    replayed_proposal_id: str
    proposal_status: str
    proposal_outbox_type: str
    proposal_created_effect_counts: Mapping[str, int]
    proposal_replayed_effect_counts: Mapping[str, int]
    mock_plan_integrations: tuple[dict[str, object], ...]
    integrations: tuple[dict[str, object], ...]
    integration_execution_status: str
    integration_cost_units: int
    decision_input_fields: Mapping[str, int]
    decision: DecisionSummary
    public_decision: PublicCreditDecisionResponse | None
    webhook_request: WebhookDeliveryRequest | None
    webhook_replay_job_ids: tuple[str, ...]
    webhook_delivery_attempt_count: int
    audit_event_types: frozenset[str]
    critical_evidence_operations: frozenset[str]
    reporting_snapshot: BusinessMetricsSnapshot
    traceability_steps: frozenset[str]
    correlation_ids: frozenset[str]
    observable_payload: Mapping[str, object]
    raw_output_payload: Mapping[str, object]
    cross_tenant_error: PublicCreditDecisionErrorResponse | None
    missing_proposal_error: PublicCreditDecisionErrorResponse | None
    cross_tenant_observable_payload: Mapping[str, object]


class RecordingAuditPublisher:
    def __init__(self) -> None:
        self.events: list[DecisionAuditIntent] = []

    def publish(self, event: DecisionAuditIntent) -> None:
        self.events.append(event)


def run_mocked_analysis_flow() -> MockedAnalysisFlowResult:
    proposal_harness = _proposal_harness()
    proposal_service = proposal_harness.service
    context = _context()

    submitted = proposal_service.submit_with_initial_status_and_outbox(
        _submit_command(payload=_valid_personal_credit_payload()),
        context=context,
    )
    proposal_created_effect_counts = _proposal_effect_counts(proposal_harness)
    replayed = proposal_service.submit_with_initial_status_and_outbox(
        _submit_command(payload=_valid_personal_credit_payload()),
        context=context,
    )
    proposal_replayed_effect_counts = _proposal_effect_counts(proposal_harness)
    proposal_id = submitted.proposal.proposal_id
    assert proposal_id is not None

    integration_audit = InMemoryAuditEventPublisher()
    integration_harness = _integration_harness(audit_publisher=integration_audit)
    integration_service = integration_harness.service
    webhook_adapter = integration_harness.webhook_adapter
    plan = _ready_integration_plan(integration_service)
    mock_plan_results = integration_service.execute_mock_integration_plan(
        ExecuteMockIntegrationCommand(
            plan=plan,
            synthetic_subject_reference="synthetic-reference-e2e-001",
            scopes=("integration_mock:execute",),
        ),
        context=context,
    )
    integration_execution = integration_service.start_integration_execution(
        StartIntegrationExecutionCommand(
            plan=plan,
            idempotency_key="integration-key-e2e-001",
            synthetic_subject_reference="synthetic-reference-e2e-001",
            scopes=("integration_execution:start",),
        ),
        context=context,
    )
    integration_cost_units = sum(job.estimated_cost_units for job in integration_execution.jobs)
    decision_field_values = _decision_field_values_from_artifacts(
        proposal=submitted.proposal,
        integration_results=integration_execution.results,
    )

    decision_service, audit_repository = _decision_service_with_published_policy()
    decision_result = decision_service.execute_credit_decision(
        ExecuteCreditDecisionCommand(
            decision_id="decision_e2e_001",
            proposal_id=proposal_id,
            product_type="personal_credit",
            channel="api",
            effective_at=_NOW + timedelta(days=2),
            field_values=decision_field_values,
            integration_result_refs=tuple(
                result.result_id for result in integration_execution.results
            ),
        ),
        context=context,
        trusted_context=_trusted_context(scopes=("decision:execute", "policy:read")),
    )

    public_query = decision_service.get_public_credit_decision_by_proposal(
        GetPublicCreditDecisionByProposalCommand(proposal_id=proposal_id),
        context=context,
        trusted_context=_trusted_context(scopes=("decision:read",)),
    )

    integration_service.configure_webhook(_configure_webhook_command(), context=context)
    webhook_command = DispatchWebhookNotificationCommand(
        event_id="evt_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        event_type="decision.completed",
        proposal_id=proposal_id,
        decision_status=public_query.decision.status if public_query.decision else "completed",
        decision_outcome=decision_result.decision.outcome,
        occurred_at=_NOW,
        idempotency_key="idem-webhook-delivery-e2e",
        scopes=("webhook_delivery:dispatch",),
        unsafe_payload={
            "cpf": "00000000191",
            "email": "cliente.sensivel@example.com",
        },
    )
    webhook_result = integration_service.dispatch_webhook_notification(
        webhook_command,
        context=context,
    )
    webhook_replay = integration_service.dispatch_webhook_notification(
        webhook_command,
        context=context,
    )

    cross_tenant = decision_service.get_public_credit_decision_by_proposal(
        GetPublicCreditDecisionByProposalCommand(proposal_id=proposal_id),
        context=_context(tenant_id=_OTHER_TENANT_ID),
        trusted_context=_trusted_context(
            tenant_id=_OTHER_TENANT_ID,
            scopes=("decision:read",),
        ),
    )
    missing = decision_service.get_public_credit_decision_by_proposal(
        GetPublicCreditDecisionByProposalCommand(proposal_id="proposal_missing_e2e_001"),
        context=context,
        trusted_context=_trusted_context(scopes=("decision:read",)),
    )

    reporting_snapshot = _record_business_projections(
        proposal_id=proposal_id,
        integration_execution=integration_execution,
        public_query_status=public_query.decision.status if public_query.decision else "unknown",
        webhook_delivered=bool(webhook_result.jobs and webhook_result.jobs[0].status == "sent"),
    )
    decision_audit_events = tuple(
        _audit_event_to_log_safe_dict(event)
        for event in (
            *audit_repository.list_by_aggregate(
                tenant_id=_TENANT_ID,
                aggregate_type="credit_decision",
                aggregate_id="decision_e2e_001",
            ),
            *audit_repository.list_by_aggregate(
                tenant_id=_TENANT_ID,
                aggregate_type="credit_proposal",
                aggregate_id=proposal_id,
            ),
        )
    )
    audit_event_types = frozenset(str(event["event_type"]) for event in decision_audit_events)
    official_evidence_events = _register_official_flow_evidence(
        proposal_id=proposal_id,
        integration_result_count=len(integration_execution.results),
        webhook_delivered=bool(webhook_result.jobs and webhook_result.jobs[0].status == "sent"),
    )
    webhook_request = webhook_adapter.requests[0] if webhook_adapter.requests else None
    integration_audit_events = tuple(event.to_log_safe_dict() for event in integration_audit.events)
    observable_payload = _safe_observability_payload(
        logs=(
            *submitted.logs,
            *replayed.logs,
            *integration_service.logged_events,
            *decision_result.logs,
            *public_query.logs,
        ),
        business_events=public_query.business_events + webhook_result.business_events,
        audit_events=(*integration_audit_events, *decision_audit_events, *official_evidence_events),
    )
    raw_output_payload = {
        "proposal_logs": submitted.logs + replayed.logs,
        "integration_logs": tuple(integration_service.logged_events),
        "decision_logs": decision_result.logs,
        "public_query_logs": public_query.logs,
        "public_decision": public_query.decision,
        "webhook_payload": webhook_request.payload if webhook_request else {},
        "webhook_headers": webhook_request.headers if webhook_request else {},
        "business_events": public_query.business_events + webhook_result.business_events,
        "integration_audit_events": integration_audit_events,
        "decision_audit_events": decision_audit_events,
        "official_evidence_events": official_evidence_events,
    }
    cross_tenant_observable_payload = {
        "cross_tenant_error": cross_tenant.error,
        "missing_error": missing.error,
    }

    return MockedAnalysisFlowResult(
        correlation_id=_CORRELATION_ID,
        proposal_id=proposal_id,
        replayed_proposal_id=replayed.proposal.proposal_id or "",
        proposal_status=submitted.intake_status.status,
        proposal_outbox_type=submitted.outbox_message.event_type,
        proposal_created_effect_counts=proposal_created_effect_counts,
        proposal_replayed_effect_counts=proposal_replayed_effect_counts,
        mock_plan_integrations=tuple(result.to_log_safe_dict() for result in mock_plan_results),
        integrations=tuple(result.to_log_safe_dict() for result in integration_execution.results),
        integration_execution_status=integration_execution.status,
        integration_cost_units=integration_cost_units,
        decision_input_fields={
            field_value.field: field_value.value for field_value in decision_field_values
        },
        decision=DecisionSummary(
            status=decision_result.explanation.status,
            outcome=decision_result.decision.outcome,
            policy_version_id=decision_result.decision.policy_version_id,
            reason_codes=decision_result.decision.reason_code_refs,
        ),
        public_decision=public_query.decision,
        webhook_request=webhook_request,
        webhook_replay_job_ids=tuple(job.job_id for job in webhook_replay.jobs),
        webhook_delivery_attempt_count=len(webhook_adapter.requests),
        audit_event_types=audit_event_types,
        critical_evidence_operations=_critical_evidence_operations(
            official_audit_events=official_evidence_events,
        ),
        reporting_snapshot=reporting_snapshot,
        traceability_steps=_traceability_steps(
            submitted_logs=submitted.logs,
            integration_logs=integration_service.logged_events,
            decision_logs=decision_result.logs,
            public_query_logs=public_query.logs,
            webhook_logs=integration_service.logged_events,
        ),
        correlation_ids=_correlation_ids(
            submitted.logs,
            integration_service.logged_events,
            decision_result.logs,
            public_query.logs,
            webhook_result.business_events,
            integration_audit_events,
            decision_audit_events,
            official_evidence_events,
        ),
        observable_payload=observable_payload,
        raw_output_payload=raw_output_payload,
        cross_tenant_error=cross_tenant.error,
        missing_proposal_error=missing.error,
        cross_tenant_observable_payload=cross_tenant_observable_payload,
    )


def assert_no_sensitive_data(payload: object) -> None:
    _assert_no_sensitive_keys(payload)
    serialized = json.dumps(payload, default=str, ensure_ascii=False, sort_keys=True)
    normalized = serialized.casefold()
    for fragment in _SENSITIVE_FRAGMENTS:
        assert fragment.casefold() not in normalized


def assert_no_public_tenant_leakage(payload: object) -> None:
    serialized = json.dumps(payload, default=str, ensure_ascii=False, sort_keys=True)
    assert _TENANT_ID not in serialized
    assert _OTHER_TENANT_ID not in serialized


def assert_required_traceability(steps: frozenset[str]) -> None:
    assert steps == _REQUIRED_TRACEABILITY_STEPS


def assert_valid_webhook_signature(request: WebhookDeliveryRequest) -> None:
    expected = hmac.new(
        _SIGNING_SECRET,
        canonical_webhook_payload(request.payload),
        sha256,
    ).hexdigest()
    assert hmac.compare_digest(
        request.headers["X-CreditOS-Signature"],
        f"sha256={expected}",
    )


def assert_public_decision_contract_payload(payload: Mapping[str, object]) -> None:
    _assert_contract_shape(
        payload,
        contract_path=_ROOT / "packages/contracts/openapi/public/decision/v1/openapi.json",
        schema_name="DecisionQueryResponse",
    )


def assert_webhook_contract_payload(payload: Mapping[str, object]) -> None:
    _assert_contract_shape(
        payload,
        contract_path=_ROOT / "packages/contracts/openapi/public/webhooks/v1/openapi.json",
        schema_name="WebhookCallbackPayload",
    )
    if payload.get("event_type") == "decision.completed":
        assert payload.get("decision_status") in {"completed", "unable_to_decide"}
        assert "decision_outcome" in payload


def _assert_no_sensitive_keys(payload: object) -> None:
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            normalized_key = str(key).casefold()
            assert not _is_sensitive_key(normalized_key), key
            _assert_no_sensitive_keys(value)
    elif isinstance(payload, (list, tuple, set, frozenset)):
        for value in payload:
            _assert_no_sensitive_keys(value)


def _is_sensitive_key(normalized_key: str) -> bool:
    compact_key = normalized_key.replace(".", "").replace("_", "").replace("-", "").replace(" ", "")
    if compact_key in {"name", "nome", "fullname", "legalname", "borrowername"}:
        return True
    return any(
        part not in {"name", "nome"} and part.replace("_", "") in compact_key
        for part in _SENSITIVE_KEY_PARTS
    )


def _assert_contract_shape(
    payload: Mapping[str, object],
    *,
    contract_path: Path,
    schema_name: str,
) -> None:
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    schema = contract["components"]["schemas"][schema_name]
    normalized_payload = _contract_json_value(payload)
    assert isinstance(normalized_payload, dict)
    errors = _validate_schema_value(schema, normalized_payload, root_schema=contract)
    assert not errors, (
        f"payload diverge do schema OpenAPI {schema_name} em {contract_path}: {errors}"
    )


def _contract_json_value(payload: Mapping[str, object]) -> object:
    return json.loads(json.dumps(payload, default=_contract_json_default, ensure_ascii=False))


def _contract_json_default(value: object) -> str:
    if isinstance(value, datetime | date):
        return value.isoformat()
    return str(value)


def _validate_schema_value(
    schema: dict[str, Any],
    value: object,
    *,
    root_schema: dict[str, Any],
) -> list[str]:
    spec = importlib.util.spec_from_file_location(
        "_creditos_check_contracts",
        _ROOT / "scripts/check_contracts.py",
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    validate = module.__dict__["validate_schema_value"]
    errors = validate(schema, value, root_schema=root_schema)
    assert isinstance(errors, list)
    return [str(error) for error in errors]


def _safe_observability_payload(
    *,
    logs: tuple[dict[str, Any], ...],
    business_events: tuple[dict[str, Any], ...],
    audit_events: tuple[dict[str, object], ...],
) -> Mapping[str, object]:
    return {
        "operation_logs": tuple(_safe_observability_log(log) for log in logs),
        "business_events": business_events,
        "audit_events": tuple(
            _drop_forbidden_observability_fields(event) for event in audit_events
        ),
    }


def _safe_observability_log(log: Mapping[str, Any]) -> Mapping[str, object]:
    safe_log = {
        "service.name": log.get("service.name"),
        "operation": log.get("operation"),
        "status": log.get("status"),
        "tenant_id": log.get("tenant_id"),
        "correlation_id": log.get("correlation_id"),
        "trace_id": log.get("trace_id"),
        "technical_result": log.get("technical_result"),
    }
    extra = log.get("extra")
    if isinstance(extra, Mapping):
        safe_log["extra"] = _drop_forbidden_observability_fields(extra)
    return safe_log


def _drop_forbidden_observability_fields(payload: Mapping[str, Any]) -> Mapping[str, object]:
    forbidden_parts = (
        "proposal_id",
        "decision_id",
        "event_id",
        "headers",
        "telefone",
        "fingerprint",
        "integration_result_refs",
        "operational_evidence_refs",
        "previous_hash",
        "current_hash",
    )
    return {
        key: _drop_forbidden_observability_value(value)
        for key, value in payload.items()
        if not any(part in key.lower() for part in forbidden_parts)
    }


def _drop_forbidden_observability_value(value: object) -> object:
    if isinstance(value, Mapping):
        return _drop_forbidden_observability_fields(value)
    if isinstance(value, (list, tuple, set, frozenset)):
        return tuple(_drop_forbidden_observability_value(item) for item in value)
    return value


def _proposal_harness() -> ProposalHarness:
    repository = InMemoryCanonicalProposalRepository()
    idempotency_repository = InMemoryIdempotentProposalSubmissionRepository()
    intake_status_repository = InMemoryProposalIntakeStatusRepository()
    outbox_repository = InMemoryProposalOutboxRepository()
    service = ProposalIntakeApplicationService(
        repository=repository,
        idempotency_repository=idempotency_repository,
        intake_status_repository=intake_status_repository,
        outbox_repository=outbox_repository,
        sensitive_fingerprint_secret=_SENSITIVE_FINGERPRINT_KEY,
        environment="test",
        clock=lambda: _NOW,
        event_id_factory=lambda seed: f"evt_{seed[-24:]}",
    )
    return ProposalHarness(
        service=service,
        repository=repository,
        idempotency_repository=idempotency_repository,
        intake_status_repository=intake_status_repository,
        outbox_repository=outbox_repository,
    )


def _proposal_effect_counts(harness: ProposalHarness) -> Mapping[str, int]:
    return {
        "proposals": len(harness.repository.list_all()),
        "idempotency_submissions": len(harness.idempotency_repository.list_all()),
        "statuses": len(harness.intake_status_repository.list_all()),
        "outbox_messages": len(harness.outbox_repository.list_all()),
    }


def _submit_command(*, payload: dict[str, Any]) -> SubmitProposalWithInitialStatusCommand:
    return SubmitProposalWithInitialStatusCommand(
        payload=deepcopy(payload),
        headers={
            "Idempotency-Key": "proposal-key-e2e-001",
            "X-Correlation-Id": _CORRELATION_ID,
        },
        technical_client_id="client-app-e2e",
        subject_id="subject-client-app-e2e",
        principal_type="m2m",
        scopes=("proposal:submit",),
    )


def _valid_personal_credit_payload() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "external_proposal_id": "prop-e2e-alpha",
        "person_type": "PF",
        "product_type": "personal_credit",
        "channel": "api",
        "operation": {
            "requested_terms": {
                "amount": 500_000,
                "currency": "BRL",
                "installments": 6,
                "down_payment": 0,
                "first_due_date": "2026-11-15",
            }
        },
        "borrower": {
            "document_type": "CPF",
            "document": "00000000191",
            "name": "Pessoa Exemplo",
            "birth_date": "1990-01-01",
        },
        "provided_data": {
            "financial": {
                "declared_monthly_income": 800_000,
                "declared_monthly_debt": 120_000,
            }
        },
        "risk_context": {},
        "product_data": {
            "personal_credit": {
                "employment_type": "formal",
                "occupation": "analyst",
                "declared_monthly_income": 800_000,
                "declared_monthly_debt": 120_000,
                "income_source": "salary",
            }
        },
        "decision_options": {
            "execution_mode": "sync",
            "review_strategy": "ai_advisory",
            "fallback_action": "request_more_data",
            "max_wait_ms": 3000,
        },
        "callback": {
            "callback_profile_ref": "tenant-default-creditos-webhook",
            "events": ["creditos.proposal.v1.submitted"],
        },
    }


def _integration_harness(
    *,
    audit_publisher: InMemoryAuditEventPublisher,
) -> IntegrationHarness:
    adapter = InMemoryWebhookDeliveryAdapter(
        [WebhookDeliveryAdapterResult.accepted(status_code=202)]
    )
    webhook_delivery_store = InMemoryWebhookDeliveryStore()
    service = IntegrationCatalogApplicationService(
        repository=InMemoryIntegrationCatalogRepository(),
        adapter_registry=InMemoryAdapterRegistry(
            {
                integration_class: {adapter_id}
                for integration_class, adapter_id in _ADAPTER_BY_CLASS.items()
            }
        ),
        mock_adapter_registry=InMemoryMockIntegrationAdapterRegistry.for_mvp_defaults(),
        audit_publisher=audit_publisher,
        environment="test",
        clock=lambda: _NOW,
        integration_execution_store=InMemoryIntegrationExecutionStore(),
        integration_dlq_store=InMemoryIntegrationDlqStore(),
        integration_execution_dispatcher=InMemoryIntegrationExecutionDispatcher(),
        webhook_configuration_repository=InMemoryWebhookConfigurationRepository(),
        webhook_allowed_domains_by_tenant={_TENANT_ID: ("example.com",)},
        webhook_dns_resolver=lambda _hostname: (_PUBLIC_CALLBACK_IP,),
        webhook_delivery_store=webhook_delivery_store,
        webhook_delivery_dlq_store=InMemoryWebhookDeliveryDlqStore(),
        webhook_delivery_dispatcher=InMemoryWebhookDeliveryDispatcher(
            adapter=adapter,
            signing_key_resolver=StaticWebhookSigningKeyResolver(
                {(_TENANT_ID, _SIGNING_KEY_REF): _SIGNING_SECRET}
            ),
        ),
    )
    return IntegrationHarness(
        service=service,
        webhook_adapter=adapter,
        webhook_delivery_store=webhook_delivery_store,
    )


def _ready_integration_plan(service: IntegrationCatalogApplicationService):
    for integration_class in _MVP_CLASSES:
        service.configure_integration_class(
            ConfigureIntegrationClassCommand(
                product_type="personal_credit",
                integration_class=integration_class,
                adapter_id=_ADAPTER_BY_CLASS[integration_class],
                requirement="required",
                timeout_ms=1_500,
                max_attempts=2,
                max_concurrency=3,
                estimated_cost_units=12,
                fallback_strategy="fail_closed",
                scopes=("integration_catalog:write",),
            ),
            context=_context(),
        )
    plan = service.build_integration_plan(
        BuildIntegrationPlanCommand(
            product_type="personal_credit",
            required_classes=_MVP_CLASSES,
        ),
        context=_context(),
    )
    assert plan.status == "ready"
    return plan


def _decision_service_with_published_policy() -> tuple[
    DecisionApplicationService,
    InMemoryAuditEventRepository,
]:
    policy_repository = InMemoryCreditPolicyRepository()
    catalog_repository = _published_catalog_repository()
    simulation_repository = InMemoryPolicySimulationRepository()
    decision_repository = InMemoryCreditDecisionRepository()
    bootstrap = DecisionApplicationService(
        repository=policy_repository,
        reason_code_catalog_repository=catalog_repository,
        policy_simulation_repository=simulation_repository,
        credit_decision_repository=decision_repository,
        audit_publisher=RecordingAuditPublisher(),
        environment="test",
        clock=lambda: _NOW,
    )
    _create_and_publish_policy(bootstrap)
    audit_repository = InMemoryAuditEventRepository()
    audit_service = AuditEvidenceApplicationService(
        repository=audit_repository,
        environment="test",
    )
    service = DecisionApplicationService(
        repository=policy_repository,
        reason_code_catalog_repository=catalog_repository,
        policy_simulation_repository=simulation_repository,
        credit_decision_repository=decision_repository,
        audit_publisher=AuditEvidenceDecisionAuditPublisher(
            audit_service=audit_service,
            clock=lambda: _NOW,
            occurrence_token_factory=lambda: "e2e0000000000001",
        ),
        environment="test",
        clock=lambda: _NOW,
    )
    return service, audit_repository


def _create_and_publish_policy(service: DecisionApplicationService) -> None:
    created = service.create_policy_draft(
        CreateCreditPolicyDraftCommand(
            policy_id="pol_personal_credit_default",
            policy_version_id="polver_personal_credit_default_v1",
            reason_code_catalog_id="rcc_personal_credit_default",
            reason_code_catalog_version_id="rccver_personal_credit_default_v1",
            owner_subject_id="user_credit_manager",
            product_type="personal_credit",
            actor_subject_id="user_credit_manager",
            change_summary="Criação inicial da política padrão",
            applicability=PolicyApplicability.create(
                channels=("api",),
                starts_at=_NOW + timedelta(days=1),
                ends_at=_NOW + timedelta(days=31),
            ),
            rules=(
                PolicyRule.create(
                    rule_id="rule_min_income",
                    name="Renda mínima declarada",
                    source_field="monthly_income_units",
                    operator="gte",
                    threshold_value=250_000,
                    outcome="approve",
                    reason_code_refs=("rc_min_income",),
                ),
            ),
            criteria=(
                PolicyCriterion.create(
                    criterion_id="criterion_requested_amount",
                    field="requested_amount_units",
                    operator="lte",
                    value=1_000_000,
                ),
            ),
            limits=(
                PolicyLimit.create(
                    limit_id="limit_max_installments",
                    limit_type="max_installments",
                    value=24,
                ),
                PolicyLimit.create(
                    limit_id="limit_max_term_days",
                    limit_type="max_term_days",
                    value=720,
                ),
            ),
        ),
        context=_context(),
        trusted_context=_trusted_context(scopes=("policy:write", "policy:read")),
    )
    simulation = service.run_policy_simulation(
        RunPolicySimulationCommand(
            simulation_id=f"sim_{created.policy.policy_version_id}",
            policy_id=created.policy.policy_id,
            policy_version_id=created.policy.policy_version_id,
            cases=(
                PolicySimulationInputCase.create(
                    case_id="case_income_001",
                    values={
                        "monthly_income_units": 800_000,
                        "requested_amount_units": 500_000,
                        "requested_installments": 6,
                        "requested_term_days": 180,
                    },
                ),
            ),
        ),
        context=_context(),
        trusted_context=_trusted_context(scopes=("policy:write", "policy:read")),
    )
    service.publish_policy(
        PublishCreditPolicyCommand(
            policy_id=created.policy.policy_id,
            policy_version_id=created.policy.policy_version_id,
            simulation_id=simulation.simulation.simulation_id,
            change_summary="Publicação aprovada após simulação",
        ),
        context=_context(),
        trusted_context=_trusted_context(scopes=("policy:publish", "policy:read")),
    )


def _published_catalog_repository() -> InMemoryReasonCodeCatalogRepository:
    repository = InMemoryReasonCodeCatalogRepository()
    draft = ReasonCodeCatalog.create_draft(
        catalog_id="rcc_personal_credit_default",
        catalog_version_id="rccver_personal_credit_default_v1",
        tenant_id=_TENANT_ID,
        owner_subject_id="user_credit_manager",
        product_type="personal_credit",
        reason_codes=(
            ReasonCode.create(
                reason_code_id="reason_min_income",
                code="rc_min_income",
                outcome="approve",
                title="Renda mínima",
                internal_description="Renda declarada atende a política",
                external_description="Renda declarada compatível com aprovação",
                factor_refs=("factor_monthly_income",),
                audience="both",
            ),
        ),
        explainable_factors=(
            ExplainableFactor.create(
                factor_id="factor_monthly_income",
                field="monthly_income_units",
                title="Renda declarada",
                internal_description="Renda mensal declarada em unidades monetárias menores",
                external_description="Renda declarada informada para análise",
                required=True,
            ),
        ),
        now=_NOW,
        actor_subject_id="user_credit_manager",
        correlation_id=_CORRELATION_ID,
        change_summary="Criação inicial do catálogo",
    )
    repository.save_with_next_version(
        draft.publish(
            now=_NOW,
            actor_subject_id="user_credit_manager",
            correlation_id=_CORRELATION_ID,
            change_summary="Publicação do catálogo",
        )
    )
    return repository


def _decision_field_values_from_artifacts(
    *,
    proposal: Any,
    integration_results: tuple[Any, ...],
) -> tuple[CreditDecisionInputFieldValue, ...]:
    requested_terms = proposal.requested_terms
    personal_credit = proposal.product_data["personal_credit"]
    requested_amount_units = _required_int(requested_terms["amount"], "requested_terms.amount")
    requested_installments = _required_int(
        requested_terms["installments"],
        "requested_terms.installments",
    )
    requested_term_days = _requested_term_days(
        str(requested_terms["first_due_date"]),
        reference_date=_NOW.date(),
    )
    declared_income_units = _required_int(
        personal_credit["declared_monthly_income"],
        "product_data.personal_credit.declared_monthly_income",
    )
    monthly_income_units = _enriched_monthly_income_units(
        declared_income_units=declared_income_units,
        integration_results=integration_results,
    )
    return (
        CreditDecisionInputFieldValue.create(
            field="monthly_income_units",
            value=monthly_income_units,
        ),
        CreditDecisionInputFieldValue.create(
            field="requested_amount_units",
            value=requested_amount_units,
        ),
        CreditDecisionInputFieldValue.create(
            field="requested_installments",
            value=requested_installments,
        ),
        CreditDecisionInputFieldValue.create(
            field="requested_term_days",
            value=requested_term_days,
        ),
    )


def _required_int(value: object, field_path: str) -> int:
    assert type(value) is int, f"{field_path} deve ser inteiro normalizado"
    return value


def _requested_term_days(value: str, *, reference_date: date) -> int:
    due_date = date.fromisoformat(value)
    term_days = (due_date - reference_date).days
    assert term_days > 0
    return term_days


def _enriched_monthly_income_units(
    *,
    declared_income_units: int,
    integration_results: tuple[Any, ...],
) -> int:
    summaries_by_class = {
        str(result.integration_class): result.summary for result in integration_results
    }
    required_classes = {"credit_bureau", "anti_fraud", "receivables"}
    assert required_classes <= set(summaries_by_class)
    if (
        summaries_by_class["credit_bureau"].get("score_band") == "high"
        and summaries_by_class["credit_bureau"].get("restriction_status") == "clear"
        and summaries_by_class["anti_fraud"].get("risk_band") == "low"
        and summaries_by_class["receivables"].get("eligibility_status") == "eligible"
    ):
        return declared_income_units
    return max(declared_income_units // 2, 0)


def _configure_webhook_command() -> ConfigureWebhookCommand:
    return ConfigureWebhookCommand(
        idempotency_key="idem-webhook-config-e2e",
        endpoint_url="https://callbacks.example.com/creditos/status",
        events=("decision.completed",),
        status="active",
        signing_algorithm="hmac_sha256",
        signing_key_ref=_SIGNING_KEY_REF,
        retry_strategy="standard_exponential_backoff",
        max_attempts=3,
        initial_backoff_ms=250,
        max_backoff_ms=30_000,
        timeout_ms=3_000,
        scopes=("webhook_configuration:write",),
    )


def _record_business_projections(
    *,
    proposal_id: str,
    integration_execution: Any,
    public_query_status: str,
    webhook_delivered: bool,
) -> BusinessMetricsSnapshot:
    reporting = ReportingInsightsService(
        repository=projection_repositories.InMemoryBusinessProjectionRepository(),
        processed_at_factory=lambda: _NOW + timedelta(seconds=30),
    )
    reporting.record_event(
        BusinessEvent.proposal(
            event_id="evt-e2e-proposal-received",
            source="creditos://proposal-intake",
            tenant_id=_TENANT_ID,
            product_type=ProductType.PERSONAL_CREDIT,
            occurred_at=_NOW,
            processed_at=_NOW,
            channel=Channel.API,
            funnel_status=ProposalFunnelStatus.RECEIVED,
            idempotency_key=f"idem-e2e-proposal-received-{proposal_id[-8:]}",
        )
    )
    reporting.record_event(
        BusinessEvent.proposal(
            event_id="evt-e2e-proposal-enriched",
            source="creditos://proposal-intake",
            tenant_id=_TENANT_ID,
            product_type=ProductType.PERSONAL_CREDIT,
            occurred_at=_NOW + timedelta(seconds=1),
            processed_at=_NOW + timedelta(seconds=1),
            channel=Channel.API,
            funnel_status=ProposalFunnelStatus.ENRICHED,
            idempotency_key=f"idem-e2e-proposal-enriched-{proposal_id[-8:]}",
        )
    )
    for cost_record in (
        {
            "integration_class": job.integration_class,
            "adapter_id": job.adapter_id,
            "actual_cost_units": job.estimated_cost_units,
        }
        for job in integration_execution.jobs
    ):
        reporting.record_event(
            BusinessEvent.integration(
                event_id=f"evt-e2e-integration-{cost_record['integration_class']}",
                source="creditos://integration",
                tenant_id=_TENANT_ID,
                product_type=ProductType.PERSONAL_CREDIT,
                occurred_at=_NOW + timedelta(seconds=2),
                processed_at=_NOW + timedelta(seconds=2),
                channel=Channel.API,
                integration_class=str(cost_record["integration_class"]),
                adapter_id=str(cost_record["adapter_id"]),
                provider_id="iprv_mock_provider_v1",
                status=IntegrationStatus.SUCCEEDED,
                estimated_cost_units=int(cost_record["actual_cost_units"]),
                actual_cost_units=int(cost_record["actual_cost_units"]),
                latency_ms=10,
            )
        )
    reporting.record_event(
        BusinessEvent.decision(
            event_id="evt-e2e-decision-approved",
            source="creditos://decision",
            tenant_id=_TENANT_ID,
            product_type=ProductType.PERSONAL_CREDIT,
            occurred_at=_NOW + timedelta(seconds=3),
            processed_at=_NOW + timedelta(seconds=3),
            channel=Channel.API,
            outcome=DecisionOutcome.APPROVED,
            reason_codes=("policy_min_income",),
            idempotency_key="idem-e2e-decision-approved",
        )
    )
    reporting.record_event(
        BusinessEvent.decision_query(
            event_id="evt-e2e-public-query-succeeded",
            source="creditos://decision",
            tenant_id=_TENANT_ID,
            product_type=ProductType.PERSONAL_CREDIT,
            occurred_at=_NOW + timedelta(seconds=4),
            processed_at=_NOW + timedelta(seconds=4),
            channel=Channel.API,
            status=_decision_query_projection_status(public_query_status),
            idempotency_key="idem-e2e-public-query",
            latency_ms=5,
        )
    )
    callback_result = reporting.record_event(
        BusinessEvent.callback(
            event_id="evt-e2e-callback-delivered",
            source="creditos://callback-dispatcher",
            tenant_id=_TENANT_ID,
            product_type=ProductType.PERSONAL_CREDIT,
            occurred_at=_NOW + timedelta(seconds=5),
            processed_at=_NOW + timedelta(seconds=5),
            channel=Channel.API,
            status=CallbackStatus.DELIVERED if webhook_delivered else CallbackStatus.FAILED,
            idempotency_key="idem-e2e-callback",
            latency_ms=7,
            error_count=0 if webhook_delivered else 1,
        )
    )
    return callback_result.snapshot


def _register_official_flow_evidence(
    *,
    proposal_id: str,
    integration_result_count: int,
    webhook_delivered: bool,
) -> tuple[dict[str, object], ...]:
    repository = InMemoryAuditEventRepository()
    service = AuditEvidenceApplicationService(repository=repository, environment="test")
    operations = (
        {
            "event_type": "proposal_intake.submitted",
            "operation": "proposal_intake.submit_with_initial_status_and_outbox",
            "action": "create",
            "resource_type": "credit_proposal",
            "resource_id": proposal_id,
            "source_service": "proposal_intake",
            "result": "accepted",
            "safe_details": {"status": "submitted"},
        },
        {
            "event_type": "integration_mock.plan_executed",
            "operation": "integration_mock.execute_plan",
            "action": "execute",
            "resource_type": "integration_plan",
            "resource_id": f"iplan_{proposal_id[-16:]}",
            "source_service": "integration",
            "result": "accepted",
            "safe_details": {"integration_result_count": str(integration_result_count)},
        },
        {
            "event_type": "integration_execution.completed",
            "operation": "integration_execution.fan_in",
            "action": "execute",
            "resource_type": "integration_execution",
            "resource_id": f"iexec_{proposal_id[-16:]}",
            "source_service": "integration",
            "result": "accepted",
            "safe_details": {"status": "completed"},
        },
        {
            "event_type": "credit_decision.completed",
            "operation": "credit_decision.execute",
            "action": "execute",
            "resource_type": "credit_decision",
            "resource_id": "decision_e2e_001",
            "source_service": "decision",
            "result": "accepted",
            "safe_details": {"status": "completed", "outcome": "approve"},
        },
        {
            "event_type": "credit_decision.public_query_retrieved",
            "operation": "credit_decision.public_query.get",
            "action": "read",
            "resource_type": "credit_proposal",
            "resource_id": proposal_id,
            "source_service": "decision",
            "result": "accepted",
            "safe_details": {"status": "completed", "outcome": "approve"},
        },
        {
            "event_type": "webhook_delivery.sent",
            "operation": "webhook_delivery.sent",
            "action": "send",
            "resource_type": "webhook_delivery",
            "resource_id": f"wdel_{proposal_id[-16:]}",
            "source_service": "integration",
            "result": "accepted" if webhook_delivered else "failed",
            "safe_details": {"status": "sent" if webhook_delivered else "failed"},
        },
    )
    events = []
    trusted_context = _trusted_context(scopes=("audit:write",))
    for index, operation in enumerate(operations, start=1):
        result = service.register_event(
            RegisterAuditEventCommand(
                event_id=_official_evidence_event_id(
                    str(operation["event_type"]),
                    str(operation["resource_id"]),
                ),
                aggregate_type="analysis_flow",
                aggregate_id=proposal_id,
                event_type=str(operation["event_type"]),
                action=str(operation["action"]),
                resource_type=str(operation["resource_type"]),
                resource_id=str(operation["resource_id"]),
                source_service=str(operation["source_service"]),
                source_kind="system",
                result=str(operation["result"]),
                occurred_at=_NOW + timedelta(seconds=index),
                safe_details={
                    "operation": str(operation["operation"]),
                    **dict(operation["safe_details"]),
                },
                operational_evidence_refs=(
                    OperationalEvidenceReference(
                        kind="trace",
                        reference=_TRACE_ID,
                        source="otel",
                    ),
                ),
            ),
            context=_context(),
            trusted_context=trusted_context,
        )
        events.append(_audit_event_to_log_safe_dict(result.event))
    return tuple(events)


def _official_evidence_event_id(event_type: str, resource_id: str) -> str:
    fingerprint = sha256(f"{_CORRELATION_ID}|{event_type}|{resource_id}".encode()).hexdigest()[:24]
    return f"audit_evt_e2e_{fingerprint}"


def _audit_event_to_log_safe_dict(event: Any) -> dict[str, object]:
    return {
        "event_id": event.event_id,
        "tenant_id": event.tenant_id,
        "aggregate_type": event.aggregate_type,
        "aggregate_id": event.aggregate_id,
        "event_type": event.event_type,
        "action": event.action,
        "resource_type": event.resource_type,
        "resource_id": event.resource_id,
        "source_service": event.source_service,
        "source_kind": event.source_kind,
        "result": event.result,
        "occurred_at": event.occurred_at.isoformat(),
        "correlation_id": event.correlation_id,
        "trace_id": event.trace_id,
        "request_id": event.request_id,
        "safe_details": dict(event.safe_details),
        "operational_evidence_refs": tuple(
            {
                "kind": reference.kind,
                "reference": reference.reference,
                "source": reference.source,
            }
            for reference in event.operational_evidence_refs
        ),
        "integrity_scope": event.integrity_scope,
        "integrity_chain_id": event.integrity_chain_id,
        "previous_hash": event.previous_hash,
        "current_hash": event.current_hash,
        "hash_algorithm": event.hash_algorithm,
        "canonicalization_version": event.canonicalization_version,
    }


def _decision_query_projection_status(public_query_status: str) -> DecisionQueryStatus:
    if public_query_status in {
        "submitted",
        "processing",
        "completed",
        "requires_input",
        "unable_to_decide",
    }:
        return DecisionQueryStatus.SUCCEEDED
    if public_query_status == "not_available":
        return DecisionQueryStatus.NOT_AVAILABLE
    return DecisionQueryStatus.FAILED


def _traceability_steps(
    *,
    submitted_logs: tuple[dict[str, Any], ...],
    integration_logs: list[dict[str, Any]],
    decision_logs: tuple[dict[str, Any], ...],
    public_query_logs: tuple[dict[str, Any], ...],
    webhook_logs: list[dict[str, Any]],
) -> frozenset[str]:
    steps: set[str] = set()
    if _has_correlated_operation(
        submitted_logs,
        operation="proposal_intake.submit_with_initial_status_and_outbox",
    ):
        steps.add("proposal")
    if _has_correlated_operation(integration_logs, operation="integration_execution.fan_in"):
        steps.add("integration")
    if _has_correlated_operation(decision_logs, operation="credit_decision.execute"):
        steps.add("decision")
    if _has_correlated_operation(
        public_query_logs,
        operation="credit_decision.public_query.get",
    ):
        steps.add("public_query")
    if _has_correlated_operation(webhook_logs, operation="webhook_delivery.sent"):
        steps.add("webhook")
    return frozenset(steps)


def _has_correlated_operation(
    logs: tuple[dict[str, Any], ...] | list[dict[str, Any]],
    *,
    operation: str,
) -> bool:
    return any(
        log.get("operation") == operation and log.get("correlation_id") == _CORRELATION_ID
        for log in logs
    )


def _critical_evidence_operations(
    *,
    official_audit_events: tuple[dict[str, object], ...],
) -> frozenset[str]:
    operations: set[str] = set()
    for event in official_audit_events:
        if event.get("correlation_id") != _CORRELATION_ID:
            continue
        event_type = event.get("event_type")
        if isinstance(event_type, str):
            operations.add(event_type)
        safe_details = event.get("safe_details")
        if isinstance(safe_details, Mapping):
            operation = safe_details.get("operation")
            if isinstance(operation, str):
                operations.add(operation)
    return frozenset(operations)


def _correlation_ids(*collections: Any) -> frozenset[str]:
    found: set[str] = set()
    for collection in collections:
        serialized = json.loads(json.dumps(collection, default=str))
        _collect_correlation_ids(serialized, found)
    return frozenset(found)


def _collect_correlation_ids(value: object, found: set[str]) -> None:
    if isinstance(value, dict):
        for key, nested_value in value.items():
            if key == "correlation_id" and isinstance(nested_value, str):
                found.add(nested_value)
            _collect_correlation_ids(nested_value, found)
    elif isinstance(value, list):
        for nested_value in value:
            _collect_correlation_ids(nested_value, found)


def _context(tenant_id: str | None = _TENANT_ID) -> ObservabilityContext:
    return ObservabilityContext.new(
        correlation_id=_CORRELATION_ID,
        request_id=_REQUEST_ID,
        trace_id=_TRACE_ID,
        tenant_id=tenant_id,
        tenant_isolation_tier="bridge" if tenant_id is not None else None,
    )


def _trusted_context(
    *,
    tenant_id: str = _TENANT_ID,
    scopes: tuple[str, ...],
) -> PropagatedContext:
    return PropagatedContext(
        trusted=TrustedContext(
            tenant_id=tenant_id,
            tenant_isolation_tier="bridge",
            subject_id="user_credit_manager",
            scopes=scopes,
            roles=("credit-manager",),
            client_id="client_admin_console",
            principal_type="human",
        ),
        correlation_id=_CORRELATION_ID,
        request_id=_REQUEST_ID,
        traceparent=f"00-{_TRACE_ID}-{_SPAN_ID}-01",
    )
