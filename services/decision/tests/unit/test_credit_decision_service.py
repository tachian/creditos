from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime, timedelta

import pytest
from creditos_audit_evidence.adapters.persistence import InMemoryAuditEventRepository
from creditos_audit_evidence.application.service import AuditEvidenceApplicationService
from creditos_decision.adapters.external import AuditEvidenceDecisionAuditPublisher
from creditos_decision.adapters.persistence import (
    InMemoryCreditDecisionRepository,
    InMemoryCreditPolicyRepository,
    InMemoryPolicySimulationRepository,
    InMemoryPublicProposalStatusRepository,
    InMemoryReasonCodeCatalogRepository,
)
from creditos_decision.application.ports import (
    CreditDecisionAuditIntent,
    CreditDecisionRepository,
    CreditPolicyAuditPublisher,
    DecisionAuditIntent,
)
from creditos_decision.application.ports.public_proposal_status_repository import (
    PublicProposalStatusSnapshot,
)
from creditos_decision.application.service import (
    CreateCreditPolicyDraftCommand,
    DecisionApplicationService,
    ExecuteCreditDecisionCommand,
    GetCreditDecisionByProposalCommand,
    GetCreditDecisionCommand,
    GetPublicCreditDecisionByProposalCommand,
    PublishCreditPolicyCommand,
    RunPolicySimulationCommand,
    _bounded_csv,
)
from creditos_decision.domain.entities import CreditPolicy, ReasonCodeCatalog
from creditos_decision.domain.errors import (
    CreditDecisionAuditWriteError,
    CreditDecisionNotFoundError,
    PolicyNotFoundError,
    PolicyTenantContextError,
    PolicyValidationError,
    ReasonCodeCatalogNotFoundError,
)
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
from creditos_observability.context import ObservabilityContext
from creditos_security import PropagatedContext, TrustedContext

NOW = datetime(2026, 8, 30, 12, 0, tzinfo=UTC)


class RecordingAuditPublisher:
    def __init__(self) -> None:
        self.events: list[DecisionAuditIntent] = []

    def publish(self, event: DecisionAuditIntent) -> None:
        self.events.append(event)


def test_bounded_csv_never_truncates_selected_references() -> None:
    first_ref = "a" * 120
    second_ref = "b" * 123
    overflow_ref = "c" * 120

    result = _bounded_csv((first_ref, second_ref, overflow_ref), max_length=250)

    assert result == f"{first_ref},more_2"
    assert second_ref not in result
    assert len(result) <= 250


def test_execute_credit_decision_persists_productive_decision_with_minimized_audit() -> None:
    audit = RecordingAuditPublisher()
    decision_repository = InMemoryCreditDecisionRepository()
    service = _service(audit=audit, decision_repository=decision_repository)
    published_policy = _create_and_publish_policy(service)

    result = service.execute_credit_decision(
        ExecuteCreditDecisionCommand(
            decision_id="decision_personal_credit_001",
            proposal_id="proposal_personal_credit_001",
            product_type="personal_credit",
            channel="api",
            effective_at=NOW + timedelta(days=2),
            field_values=_decision_field_values(),
            integration_result_refs=("integration_income_check_001",),
        ),
        context=_context("tenant_alpha"),
        trusted_context=_trusted_context(scopes=("decision:execute", "policy:read")),
    )

    stored = decision_repository.get(
        tenant_id="tenant_alpha",
        decision_id="decision_personal_credit_001",
    )
    assert stored == result.decision
    assert result.decision.policy_id == published_policy.policy_id
    assert result.decision.policy_version_id == published_policy.policy_version_id
    assert result.decision.policy_revision == published_policy.revision
    assert result.decision.outcome == "approve"
    assert result.explanation.decision_id == result.decision.decision_id
    assert result.explanation.status == "completed"
    assert result.explanation.reason_codes[0].description == (
        "Renda declarada compatível com aprovação"
    )
    assert result.explanation.factors[0].description == "Renda declarada informada para análise"
    assert result.explanation.policy_version_id == published_policy.policy_version_id
    assert result.explanation.decision_fingerprint == result.decision.decision_fingerprint
    assert "300000" not in str(result.explanation)
    assert result.decision.reason_code_refs == ("rc_min_income",)
    assert result.decision.factor_refs == ("factor_monthly_income",)
    assert result.logs[0]["payload"] == "[OMITIDO]"
    assert "fallback_action" not in result.logs[0]["extra"]
    assert "300000" not in str(result.logs[0])
    event = audit.events[-1]
    assert isinstance(event, CreditDecisionAuditIntent)
    assert event.event_type == "credit_decision.completed"
    assert event.tenant_id == "tenant_alpha"
    assert event.decision_id == "decision_personal_credit_001"
    assert event.proposal_id == "proposal_personal_credit_001"
    assert event.reason_code_catalog_id == "rcc_personal_credit_default"
    assert event.reason_code_catalog_version_id == "rccver_personal_credit_default_v1"
    assert event.safe_details["channel"] == "api"
    assert event.safe_details["duration_ms"]
    assert event.safe_details["factor_count"] == "1"
    assert "fallback_action" not in event.safe_details
    assert event.safe_details["fingerprint"] == result.decision.decision_fingerprint
    assert event.safe_details["integration_result_count"] == "1"
    assert event.safe_details["integration_result_refs"] == "integration_income_check_001"
    assert event.safe_details["operation"] == "credit_decision.execute"
    assert event.safe_details["outcome"] == "approve"
    assert event.safe_details["policy_id"] == published_policy.policy_id
    assert event.safe_details["policy_revision"] == str(published_policy.revision)
    assert event.safe_details["policy_version_id"] == published_policy.policy_version_id
    assert event.safe_details["product_type"] == "personal_credit"
    assert event.safe_details["reason_code_catalog_id"] == "rcc_personal_credit_default"
    assert (
        event.safe_details["reason_code_catalog_version_id"] == "rccver_personal_credit_default_v1"
    )
    assert event.safe_details["reason_code_count"] == "1"
    assert event.safe_details["reason_code_refs"] == "rc_min_income"
    assert event.safe_details["status"] == "completed"
    assert event.safe_details["triggered_rule_count"] == "1"
    assert event.safe_details["validation_issue_count"] == "0"


def test_execute_credit_decision_appends_official_audit_event_with_adapter() -> None:
    policy_repository = InMemoryCreditPolicyRepository()
    catalog_repository = _published_catalog_repository()
    simulation_repository = InMemoryPolicySimulationRepository()
    decision_repository = InMemoryCreditDecisionRepository()
    bootstrap_service = _service(
        audit=RecordingAuditPublisher(),
        repository=policy_repository,
        catalog_repository=catalog_repository,
        simulation_repository=simulation_repository,
        decision_repository=decision_repository,
    )
    _create_and_publish_policy(bootstrap_service)
    audit_repository = InMemoryAuditEventRepository()
    audit_service = AuditEvidenceApplicationService(
        repository=audit_repository,
        environment="test",
    )
    decision_service = _service(
        audit=AuditEvidenceDecisionAuditPublisher(
            audit_service=audit_service,
            clock=lambda: NOW,
        ),
        repository=policy_repository,
        catalog_repository=catalog_repository,
        simulation_repository=simulation_repository,
        decision_repository=decision_repository,
    )

    decision_service.execute_credit_decision(
        _execute_command(integration_result_refs=("integration_income_check_001",)),
        context=_context("tenant_alpha"),
        trusted_context=_trusted_context(scopes=("decision:execute", "policy:read")),
    )

    events = audit_repository.list_by_aggregate(
        tenant_id="tenant_alpha",
        aggregate_type="credit_decision",
        aggregate_id="decision_personal_credit_001",
    )
    assert len(events) == 1
    assert events[0].event_type == "credit_decision.completed"
    assert events[0].safe_details["proposal_id"] == "proposal_personal_credit_001"
    assert events[0].safe_details["policy_id"] == "pol_personal_credit_default"
    assert events[0].safe_details["integration_result_count"] == "1"
    assert events[0].safe_details["integration_result_refs"] == "integration_income_check_001"
    assert events[0].safe_details["reason_code_refs"] == "rc_min_income"
    assert events[0].safe_details["triggered_rule_ids"] == "rule_min_income"
    assert events[0].operational_evidence_refs[0].kind == "trace"
    assert "300000" not in str(events[0].safe_details)

    decision_service.execute_credit_decision(
        ExecuteCreditDecisionCommand(
            decision_id="decision_missing_fields_001",
            proposal_id="proposal_missing_fields_001",
            product_type="personal_credit",
            channel="api",
            effective_at=NOW + timedelta(days=2),
            field_values=(
                CreditDecisionInputFieldValue.create(
                    field="requested_amount_units",
                    value=700_000,
                ),
            ),
        ),
        context=_context("tenant_alpha"),
        trusted_context=_trusted_context(scopes=("decision:execute", "policy:read")),
    )
    missing_events = audit_repository.list_by_aggregate(
        tenant_id="tenant_alpha",
        aggregate_type="credit_decision",
        aggregate_id="decision_missing_fields_001",
    )
    assert missing_events[0].safe_details["outcome"] == "request_more_data"
    assert missing_events[0].safe_details["fallback_action"] == "request_more_data"
    assert missing_events[0].safe_details["required_data_count"] == "3"
    assert "700000" not in str(missing_events[0].safe_details)


def test_get_credit_decision_returns_explainable_response_by_id_and_proposal() -> None:
    audit = RecordingAuditPublisher()
    decision_repository = InMemoryCreditDecisionRepository()
    service = _service(audit=audit, decision_repository=decision_repository)
    _create_and_publish_policy(service)
    executed = service.execute_credit_decision(
        _execute_command(),
        context=_context("tenant_alpha"),
        trusted_context=_trusted_context(scopes=("decision:execute", "policy:read")),
    )

    by_id = service.get_credit_decision(
        GetCreditDecisionCommand(decision_id=executed.decision.decision_id),
        context=_context("tenant_alpha"),
        trusted_context=_trusted_context(scopes=("decision:read",)),
    )
    by_proposal = service.get_credit_decision_by_proposal(
        GetCreditDecisionByProposalCommand(proposal_id=executed.decision.proposal_id),
        context=_context("tenant_alpha"),
        trusted_context=_trusted_context(scopes=("decision:read",)),
    )

    assert by_id.explanation == by_proposal.explanation
    assert by_id.explanation.decision_id == "decision_personal_credit_001"
    assert by_id.explanation.proposal_id == "proposal_personal_credit_001"
    assert by_id.explanation.reason_codes[0].code == "rc_min_income"
    assert by_id.explanation.triggered_rule_ids == ("rule_min_income",)
    assert by_id.logs[0]["operation"] == "credit_decision.explanation.get"
    assert by_id.logs[0]["payload"] == "[OMITIDO]"
    assert by_id.logs[0]["extra"]["reason_code_count"] == 1
    assert "300000" not in str(by_id.logs[0])
    assert isinstance(audit.events[-1], CreditDecisionAuditIntent)
    assert audit.events[-1].event_type == "credit_decision.explanation_retrieved"
    assert audit.events[-1].safe_details["operation"] == "credit_decision.explanation.get"
    assert audit.events[-1].safe_details["audience"] == "customer"
    assert audit.events[-1].safe_details["reason_code_count"] == "1"
    assert audit.events[-1].safe_details["factor_count"] == "1"


def test_get_credit_decision_requires_read_scope_and_hides_cross_tenant_decisions() -> None:
    audit = RecordingAuditPublisher()
    decision_repository = InMemoryCreditDecisionRepository()
    service = _service(audit=audit, decision_repository=decision_repository)
    _create_and_publish_policy(service)
    service.execute_credit_decision(
        _execute_command(),
        context=_context("tenant_alpha"),
        trusted_context=_trusted_context(scopes=("decision:execute", "policy:read")),
    )

    with pytest.raises(PolicyTenantContextError, match="escopo obrigatório ausente"):
        service.get_credit_decision(
            GetCreditDecisionCommand(decision_id="decision_personal_credit_001"),
            context=_context("tenant_alpha"),
            trusted_context=_trusted_context(scopes=("policy:read",)),
        )

    with pytest.raises(CreditDecisionNotFoundError):
        service.get_credit_decision(
            GetCreditDecisionCommand(decision_id="decision_personal_credit_001"),
            context=_context("tenant_beta"),
            trusted_context=_trusted_context(
                tenant_id="tenant_beta",
                scopes=("decision:read",),
            ),
        )
    assert service.logged_events[-1]["extra"]["decision_id"] == "decision_personal_credit_001"

    with pytest.raises(CreditDecisionNotFoundError):
        service.get_credit_decision_by_proposal(
            GetCreditDecisionByProposalCommand(proposal_id="proposal_personal_credit_001"),
            context=_context("tenant_beta"),
            trusted_context=_trusted_context(
                tenant_id="tenant_beta",
                scopes=("decision:read",),
            ),
        )
    assert service.logged_events[-1]["extra"]["proposal_id"] == "proposal_personal_credit_001"

    with pytest.raises(PolicyTenantContextError, match="tier de tenant não suportado"):
        service.get_credit_decision(
            GetCreditDecisionCommand(decision_id="decision_personal_credit_001"),
            context=_context("tenant_alpha", tenant_isolation_tier="silo"),
            trusted_context=_trusted_context(
                scopes=("decision:read",),
                tenant_isolation_tier="silo",
            ),
        )


def test_get_public_credit_decision_by_proposal_returns_minimized_response() -> None:
    audit = RecordingAuditPublisher()
    decision_repository = InMemoryCreditDecisionRepository()
    service = _service(audit=audit, decision_repository=decision_repository)
    _create_and_publish_policy(service)
    service.execute_credit_decision(
        _execute_command(),
        context=_context("tenant_alpha"),
        trusted_context=_trusted_context(scopes=("decision:execute", "policy:read")),
    )

    audit_count_after_execution = len(audit.events)

    query_context = _context(
        "tenant_alpha",
        correlation_id="corr_public_query_123456",
        request_id="req_public_query_123456",
        trace_id="2234567890abcdef1234567890abcdef",
    )
    query_trusted_context = _trusted_context(
        scopes=("decision:read",),
        correlation_id="corr_public_query_123456",
        request_id="req_public_query_123456",
        trace_id="2234567890abcdef1234567890abcdef",
    )

    result = service.get_public_credit_decision_by_proposal(
        GetPublicCreditDecisionByProposalCommand(proposal_id="proposal_personal_credit_001"),
        context=query_context,
        trusted_context=query_trusted_context,
    )

    assert result.error is None
    assert result.decision is not None
    assert result.decision.contract_version == "v1"
    assert result.decision.proposal_id == "proposal_personal_credit_001"
    assert result.decision.decision_id == "decision_personal_credit_001"
    assert result.decision.status == "completed"
    assert result.decision.outcome == "approve"
    assert result.decision.correlation_id == "corr_public_query_123456"
    assert result.decision.policy is not None
    assert result.decision.policy.policy_id == "pol_personal_credit_default"
    assert result.decision.policy.policy_version_id == "polver_personal_credit_default_v1"
    assert result.decision.policy.reason_code_catalog_version_id == (
        "rccver_personal_credit_default_v1"
    )
    assert result.decision.reason_codes[0].code == "rc_min_income"
    assert result.decision.factors[0].factor_id == "factor_monthly_income"
    assert len(result.logs) == 1
    assert result.logs[-1]["operation"] == "credit_decision.public_query.get"
    assert result.logs[-1]["payload"] == "[OMITIDO]"
    assert result.logs[-1]["extra"]["contract_version"] == "v1"
    assert "proposal_id" not in result.logs[-1]["extra"]
    assert "decision_id" not in result.logs[-1]["extra"]
    assert "fingerprint" not in result.logs[-1]["extra"]
    assert len(audit.events) == audit_count_after_execution + 1
    assert audit.events[-1].event_type == "credit_decision.public_query_retrieved"
    assert audit.events[-1].safe_details["operation"] == "credit_decision.public_query.get"
    assert "fingerprint" not in audit.events[-1].safe_details
    assert "triggered_rule_ids" not in audit.events[-1].safe_details

    public_payload = asdict(result.decision)
    public_keys = set(_iter_nested_keys(public_payload))
    assert "tenant_id" not in public_keys
    assert "triggered_rule_ids" not in public_keys
    assert "decision_fingerprint" not in public_keys
    assert "input_fingerprint" not in public_keys
    assert "payload" not in public_keys
    assert "field_values" not in public_keys
    assert "required_data_refs" not in public_keys
    assert "validation_issue_codes" not in public_keys
    assert "fallback_action" not in public_keys
    assert "300000" not in str(public_payload)


def test_get_public_credit_decision_by_proposal_returns_governed_submitted_status() -> None:
    audit = RecordingAuditPublisher()
    status_repository = InMemoryPublicProposalStatusRepository()
    status_repository.save(
        PublicProposalStatusSnapshot(
            tenant_id="tenant_alpha",
            proposal_id="proposal_submitted_001",
            status="submitted",
            schema_version="1.0",
            product_type="personal_credit",
            channel="api",
            occurred_at=NOW,
        )
    )
    service = _service(
        audit=audit,
        decision_repository=InMemoryCreditDecisionRepository(),
        public_proposal_status_repository=status_repository,
    )

    result = service.get_public_credit_decision_by_proposal(
        GetPublicCreditDecisionByProposalCommand(proposal_id="proposal_submitted_001"),
        context=_context("tenant_alpha"),
        trusted_context=_trusted_context(scopes=("decision:read",)),
    )

    assert result.error is None
    assert result.decision is not None
    assert result.decision.contract_version == "v1"
    assert result.decision.proposal_id == "proposal_submitted_001"
    assert result.decision.status == "submitted"
    assert result.decision.outcome is None
    assert result.decision.decision_id is None
    assert result.decision.decided_at is None
    assert result.decision.policy is None
    assert result.decision.reason_codes == ()
    assert result.decision.factors == ()
    assert result.decision.message == "análise recebida"
    assert result.logs[-1]["extra"] == {
        "channel": "api",
        "contract_version": "v1",
        "factor_count": 0,
        "product_type": "personal_credit",
        "reason_code_count": 0,
        "status": "submitted",
    }
    assert audit.events[-1].event_type == "credit_decision.public_query_retrieved"
    assert audit.events[-1].safe_details["status"] == "submitted"
    assert "proposal_submitted_001" not in str(audit.events[-1].safe_details)


def test_get_public_credit_decision_audits_distinct_pending_proposals() -> None:
    audit_repository = InMemoryAuditEventRepository()
    audit_service = AuditEvidenceApplicationService(
        repository=audit_repository,
        environment="test",
    )
    publisher = AuditEvidenceDecisionAuditPublisher(
        audit_service=audit_service,
        clock=lambda: NOW,
    )
    status_repository = InMemoryPublicProposalStatusRepository()
    proposal_ids = ("proposal_pending_001", "proposal_pending_002")
    for proposal_id in proposal_ids:
        status_repository.save(
            PublicProposalStatusSnapshot(
                tenant_id="tenant_alpha",
                proposal_id=proposal_id,
                status="submitted",
                schema_version="1.0",
                product_type="personal_credit",
                channel="api",
                occurred_at=NOW,
            )
        )
    service = _service(
        audit=publisher,
        decision_repository=InMemoryCreditDecisionRepository(),
        public_proposal_status_repository=status_repository,
    )

    for proposal_id in proposal_ids:
        service.get_public_credit_decision_by_proposal(
            GetPublicCreditDecisionByProposalCommand(proposal_id=proposal_id),
            context=_context("tenant_alpha"),
            trusted_context=_trusted_context(scopes=("decision:read",)),
        )

    for proposal_id in proposal_ids:
        events = audit_repository.list_by_aggregate(
            tenant_id="tenant_alpha",
            aggregate_type="credit_proposal",
            aggregate_id=proposal_id,
        )
        assert len(events) == 1
        assert events[0].resource_type == "credit_proposal"
        assert events[0].resource_id == proposal_id
        assert proposal_id not in str(events[0].safe_details)


def test_get_public_credit_decision_by_proposal_exposes_versioned_public_messages() -> None:
    scenarios = (
        (
            _service_with_public_policy(outcome="approve"),
            ExecuteCreditDecisionCommand(
                decision_id="decision_public_approve",
                proposal_id="proposal_public_approve",
                product_type="personal_credit",
                channel="api",
                effective_at=NOW + timedelta(days=2),
                field_values=_decision_field_values(),
            ),
            "completed",
            "approve",
            "decisão aprovada",
        ),
        (
            _service_with_public_policy(outcome="reject"),
            ExecuteCreditDecisionCommand(
                decision_id="decision_public_reject",
                proposal_id="proposal_public_reject",
                product_type="personal_credit",
                channel="api",
                effective_at=NOW + timedelta(days=2),
                field_values=_decision_field_values(),
            ),
            "completed",
            "reject",
            "decisão recusada",
        ),
        (
            _service_with_public_policy(outcome="approve_with_changes"),
            ExecuteCreditDecisionCommand(
                decision_id="decision_public_changes",
                proposal_id="proposal_public_changes",
                product_type="personal_credit",
                channel="api",
                effective_at=NOW + timedelta(days=2),
                field_values=_decision_field_values(
                    requested_installments=36,
                    requested_term_days=900,
                ),
            ),
            "completed",
            "approve_with_changes",
            "decisão aprovada com alterações",
        ),
        (
            _service_with_public_policy(outcome="approve"),
            ExecuteCreditDecisionCommand(
                decision_id="decision_public_missing",
                proposal_id="proposal_public_missing",
                product_type="personal_credit",
                channel="api",
                effective_at=NOW + timedelta(days=2),
                field_values=(
                    CreditDecisionInputFieldValue.create(
                        field="requested_amount_units",
                        value=700_000,
                    ),
                ),
            ),
            "requires_input",
            "request_more_data",
            "dados adicionais necessários",
        ),
        (
            _service_with_conflicting_public_policy(),
            ExecuteCreditDecisionCommand(
                decision_id="decision_public_conflict",
                proposal_id="proposal_public_conflict",
                product_type="personal_credit",
                channel="api",
                effective_at=NOW + timedelta(days=2),
                field_values=_decision_field_values(),
            ),
            "unable_to_decide",
            "unable_to_decide",
            "decisão inconclusiva",
        ),
    )

    for service, command, status, outcome, message in scenarios:
        service.execute_credit_decision(
            command,
            context=_context("tenant_alpha"),
            trusted_context=_trusted_context(scopes=("decision:execute", "policy:read")),
        )

        public = service.get_public_credit_decision_by_proposal(
            GetPublicCreditDecisionByProposalCommand(proposal_id=command.proposal_id),
            context=_context("tenant_alpha"),
            trusted_context=_trusted_context(scopes=("decision:read",)),
        )

        assert public.decision is not None
        assert public.decision.status == status
        assert public.decision.outcome == outcome
        assert public.decision.message == message
        assert "stack" not in str(public.decision).lower()
        assert "trace" not in str(public.decision).lower()


def test_get_public_credit_decision_by_proposal_returns_governed_processing_status() -> None:
    audit = RecordingAuditPublisher()
    status_repository = InMemoryPublicProposalStatusRepository()
    status_repository.save(
        PublicProposalStatusSnapshot(
            tenant_id="tenant_alpha",
            proposal_id="proposal_processing_001",
            status="processing",
            schema_version="1.0",
            product_type="personal_credit",
            channel="api",
            occurred_at=NOW,
        )
    )
    service = _service(
        audit=audit,
        decision_repository=InMemoryCreditDecisionRepository(),
        public_proposal_status_repository=status_repository,
    )

    result = service.get_public_credit_decision_by_proposal(
        GetPublicCreditDecisionByProposalCommand(proposal_id="proposal_processing_001"),
        context=_context("tenant_alpha"),
        trusted_context=_trusted_context(scopes=("decision:read",)),
    )

    assert result.error is None
    assert result.decision is not None
    assert result.decision.status == "processing"
    assert result.decision.outcome is None
    assert result.decision.message == "análise em processamento"


def test_get_public_credit_decision_by_proposal_prefers_decision_over_stale_status() -> None:
    class RaceDecisionRepository:
        def __init__(self, inner: InMemoryCreditDecisionRepository) -> None:
            self._inner = inner
            self._proposal_lookup_count = 0

        def save(self, decision, *, before_commit=None):
            self._inner.save(decision, before_commit=before_commit)

        def get(self, *, tenant_id: str, decision_id: str):
            return self._inner.get(tenant_id=tenant_id, decision_id=decision_id)

        def get_by_proposal(self, *, tenant_id: str, proposal_id: str):
            self._proposal_lookup_count += 1
            if self._proposal_lookup_count == 1:
                return None
            return self._inner.get_by_proposal(tenant_id=tenant_id, proposal_id=proposal_id)

    audit = RecordingAuditPublisher()
    policy_repository = InMemoryCreditPolicyRepository()
    decision_repository = InMemoryCreditDecisionRepository()
    status_repository = InMemoryPublicProposalStatusRepository()
    bootstrap_service = _service(
        audit=audit,
        repository=policy_repository,
        decision_repository=decision_repository,
    )
    _create_and_publish_policy(bootstrap_service)
    bootstrap_service.execute_credit_decision(
        _execute_command(),
        context=_context("tenant_alpha"),
        trusted_context=_trusted_context(scopes=("decision:execute", "policy:read")),
    )
    status_repository.save(
        PublicProposalStatusSnapshot(
            tenant_id="tenant_alpha",
            proposal_id="proposal_personal_credit_001",
            status="processing",
            schema_version="1.0",
            product_type="personal_credit",
            channel="api",
            occurred_at=NOW,
        )
    )
    query_service = _service(
        audit=audit,
        repository=policy_repository,
        decision_repository=RaceDecisionRepository(decision_repository),
        public_proposal_status_repository=status_repository,
    )

    result = query_service.get_public_credit_decision_by_proposal(
        GetPublicCreditDecisionByProposalCommand(proposal_id="proposal_personal_credit_001"),
        context=_context("tenant_alpha"),
        trusted_context=_trusted_context(scopes=("decision:read",)),
    )

    assert result.error is None
    assert result.decision is not None
    assert result.decision.status == "completed"
    assert result.decision.outcome == "approve"
    assert result.decision.decision_id == "decision_personal_credit_001"


def test_get_public_credit_decision_by_proposal_standardizes_not_available_errors() -> None:
    audit = RecordingAuditPublisher()
    decision_repository = InMemoryCreditDecisionRepository()
    service = _service(audit=audit, decision_repository=decision_repository)
    _create_and_publish_policy(service)
    service.execute_credit_decision(
        _execute_command(),
        context=_context("tenant_alpha"),
        trusted_context=_trusted_context(scopes=("decision:execute", "policy:read")),
    )

    cross_tenant = service.get_public_credit_decision_by_proposal(
        GetPublicCreditDecisionByProposalCommand(proposal_id="proposal_personal_credit_001"),
        context=_context("tenant_beta"),
        trusted_context=_trusted_context(tenant_id="tenant_beta", scopes=("decision:read",)),
    )
    missing_scope = service.get_public_credit_decision_by_proposal(
        GetPublicCreditDecisionByProposalCommand(proposal_id="proposal_personal_credit_001"),
        context=_context("tenant_alpha"),
        trusted_context=_trusted_context(scopes=("policy:read",)),
    )
    missing_decision = service.get_public_credit_decision_by_proposal(
        GetPublicCreditDecisionByProposalCommand(proposal_id="proposal_unknown_001"),
        context=_context("tenant_alpha"),
        trusted_context=_trusted_context(scopes=("decision:read",)),
    )
    invalid_request = service.get_public_credit_decision_by_proposal(
        GetPublicCreditDecisionByProposalCommand(proposal_id="INVALID:proposal"),
        context=_context("tenant_alpha"),
        trusted_context=_trusted_context(scopes=("decision:read",)),
    )

    for result in (cross_tenant, missing_scope, missing_decision):
        assert result.decision is None
        assert result.error is not None
        assert result.error.error_code == "decision_not_available"
        assert result.error.message == "decisão não disponível"
        assert result.error.correlation_id == "corr_1234567890abcdef"
        assert result.error.status_code == 404
        assert result.logs[-1]["operation"] == "credit_decision.public_query.get"
        assert result.logs[-1]["status"] == "rejected"
        assert result.logs[-1]["payload"] == "[OMITIDO]"

    assert cross_tenant.error == missing_scope.error == missing_decision.error
    assert invalid_request.decision is None
    assert invalid_request.error is not None
    assert invalid_request.error.error_code == "invalid_request"
    assert invalid_request.error.status_code == 400
    assert invalid_request.logs[-1]["extra"] == {
        "contract_version": "v1",
        "error_code": "invalid_request",
        "status_code": 400,
    }


def test_get_public_credit_decision_by_proposal_maps_internal_failures_to_500() -> None:
    audit = RecordingAuditPublisher()
    service = DecisionApplicationService(
        repository=InMemoryCreditPolicyRepository(),
        reason_code_catalog_repository=_published_catalog_repository(),
        policy_simulation_repository=InMemoryPolicySimulationRepository(),
        credit_decision_repository=None,
        audit_publisher=audit,
        environment="test",
        clock=lambda: NOW,
    )

    result = service.get_public_credit_decision_by_proposal(
        GetPublicCreditDecisionByProposalCommand(proposal_id="proposal_personal_credit_001"),
        context=_context("tenant_alpha"),
        trusted_context=_trusted_context(scopes=("decision:read",)),
    )

    assert result.decision is None
    assert result.error is not None
    assert result.error.error_code == "decision_query_failed"
    assert result.error.status_code == 500
    assert result.logs[-1]["status"] == "rejected"
    assert result.logs[-1]["extra"] == {
        "contract_version": "v1",
        "error_code": "decision_query_failed",
        "status_code": 500,
    }
    assert audit.events[-1].event_type == "credit_decision.public_query_rejected"
    assert audit.events[-1].safe_details["rejection_reason"] == "decision_query_failed"


def test_get_public_credit_decision_by_proposal_controls_audit_publisher_failures() -> None:
    class FailingPublicQueryAuditPublisher:
        def publish(self, event: DecisionAuditIntent) -> None:
            if isinstance(event, CreditDecisionAuditIntent):
                raise RuntimeError("audit unavailable")

    policy_repository = InMemoryCreditPolicyRepository()
    catalog_repository = _published_catalog_repository()
    simulation_repository = InMemoryPolicySimulationRepository()
    decision_repository = InMemoryCreditDecisionRepository()
    bootstrap_service = _service(
        audit=RecordingAuditPublisher(),
        repository=policy_repository,
        catalog_repository=catalog_repository,
        simulation_repository=simulation_repository,
        decision_repository=decision_repository,
    )
    _create_and_publish_policy(bootstrap_service)
    bootstrap_service.execute_credit_decision(
        _execute_command(),
        context=_context("tenant_alpha"),
        trusted_context=_trusted_context(scopes=("decision:execute", "policy:read")),
    )
    failing_service = _service(
        audit=FailingPublicQueryAuditPublisher(),
        repository=policy_repository,
        catalog_repository=catalog_repository,
        simulation_repository=simulation_repository,
        decision_repository=decision_repository,
    )

    result = failing_service.get_public_credit_decision_by_proposal(
        GetPublicCreditDecisionByProposalCommand(proposal_id="proposal_personal_credit_001"),
        context=_context("tenant_alpha"),
        trusted_context=_trusted_context(scopes=("decision:read",)),
    )

    assert result.decision is None
    assert result.error is not None
    assert result.error.error_code == "decision_query_failed"
    assert result.error.status_code == 500
    assert result.logs[-1]["operation"] == "credit_decision.public_query.get"
    assert result.logs[-1]["status"] == "rejected"


def test_execute_credit_decision_rejects_divergent_traceability_contexts() -> None:
    service = _service(audit=RecordingAuditPublisher())
    _create_and_publish_policy(service)

    with pytest.raises(PolicyTenantContextError, match="correlation ID divergente"):
        service.execute_credit_decision(
            _execute_command(),
            context=_context("tenant_alpha", correlation_id="corr_divergent123456"),
            trusted_context=_trusted_context(scopes=("decision:execute", "policy:read")),
        )

    with pytest.raises(PolicyTenantContextError, match="request ID divergente"):
        service.execute_credit_decision(
            _execute_command(),
            context=_context("tenant_alpha", request_id="req_divergent123456"),
            trusted_context=_trusted_context(scopes=("decision:execute", "policy:read")),
        )

    with pytest.raises(PolicyTenantContextError, match="trace ID divergente"):
        service.execute_credit_decision(
            _execute_command(),
            context=_context("tenant_alpha", trace_id="2234567890abcdef1234567890abcdef"),
            trusted_context=_trusted_context(scopes=("decision:execute", "policy:read")),
        )


def test_get_credit_decision_blocks_internal_explanation_without_explicit_scope() -> None:
    audit = RecordingAuditPublisher()
    service = _service(audit=audit)
    _create_and_publish_policy(service)
    service.execute_credit_decision(
        _execute_command(),
        context=_context("tenant_alpha"),
        trusted_context=_trusted_context(scopes=("decision:execute", "policy:read")),
    )

    with pytest.raises(PolicyTenantContextError, match="escopo obrigatório ausente"):
        service.get_credit_decision(
            GetCreditDecisionCommand(
                decision_id="decision_personal_credit_001",
                audience="internal",
            ),
            context=_context("tenant_alpha"),
            trusted_context=_trusted_context(scopes=("decision:read",)),
        )

    result = service.get_credit_decision(
        GetCreditDecisionCommand(
            decision_id="decision_personal_credit_001",
            audience="internal",
        ),
        context=_context("tenant_alpha"),
        trusted_context=_trusted_context(
            scopes=("decision:read", "decision:explain:internal"),
        ),
    )

    assert result.explanation.reason_codes[0].description == "Renda declarada atende a política"
    assert result.logs[0]["extra"]["audience"] == "internal"
    assert audit.events[-1].safe_details["audience"] == "internal"


def test_execute_credit_decision_does_not_persist_without_customer_visible_explanation() -> None:
    audit = RecordingAuditPublisher()
    decision_repository = InMemoryCreditDecisionRepository()
    service = _service(
        audit=audit,
        decision_repository=decision_repository,
        catalog_repository=_published_catalog_repository(reason_code_audience="internal"),
    )
    _create_and_publish_policy(service)

    with pytest.raises(PolicyValidationError, match="justificativa governada"):
        service.execute_credit_decision(
            _execute_command(),
            context=_context("tenant_alpha"),
            trusted_context=_trusted_context(scopes=("decision:execute", "policy:read")),
        )

    assert (
        decision_repository.get(
            tenant_id="tenant_alpha",
            decision_id="decision_personal_credit_001",
        )
        is None
    )
    assert audit.events[-1].event_type == "credit_decision.rejected"


def test_get_credit_decision_rejection_after_lookup_keeps_known_safe_metadata() -> None:
    audit = RecordingAuditPublisher()
    decision_repository = InMemoryCreditDecisionRepository()
    bootstrap_service = _service(
        audit=audit,
        decision_repository=decision_repository,
    )
    _create_and_publish_policy(bootstrap_service)
    bootstrap_service.execute_credit_decision(
        _execute_command(),
        context=_context("tenant_alpha"),
        trusted_context=_trusted_context(scopes=("decision:execute", "policy:read")),
    )
    broken_service = _service(
        audit=audit,
        decision_repository=decision_repository,
        catalog_repository=InMemoryReasonCodeCatalogRepository(),
    )

    with pytest.raises(ReasonCodeCatalogNotFoundError):
        broken_service.get_credit_decision(
            GetCreditDecisionCommand(decision_id="decision_personal_credit_001"),
            context=_context("tenant_alpha"),
            trusted_context=_trusted_context(scopes=("decision:read",)),
        )

    event = audit.events[-1]
    assert isinstance(event, CreditDecisionAuditIntent)
    assert event.event_type == "credit_decision.rejected"
    assert event.policy_id == "pol_personal_credit_default"
    assert event.reason_code_catalog_id == "rcc_personal_credit_default"
    assert event.safe_details["outcome"] == "approve"
    assert event.safe_details["reason_code_count"] == "1"
    assert broken_service.logged_events[-1]["extra"]["decision_id"] == (
        "decision_personal_credit_001"
    )
    assert broken_service.logged_events[-1]["extra"]["policy_id"] == "pol_personal_credit_default"


def test_execute_credit_decision_has_stable_fingerprint_and_controls_duplicate_proposal() -> None:
    audit = RecordingAuditPublisher()
    decision_repository = InMemoryCreditDecisionRepository()
    service = _service(audit=audit, decision_repository=decision_repository)
    _create_and_publish_policy(service)
    command = ExecuteCreditDecisionCommand(
        decision_id="decision_personal_credit_001",
        proposal_id="proposal_personal_credit_001",
        product_type="personal_credit",
        channel="api",
        effective_at=NOW + timedelta(days=2),
        field_values=_decision_field_values(),
    )

    first = service.execute_credit_decision(
        command,
        context=_context("tenant_alpha"),
        trusted_context=_trusted_context(scopes=("decision:execute", "policy:read")),
    )

    with pytest.raises(Exception, match="decisão duplicada"):
        service.execute_credit_decision(
            ExecuteCreditDecisionCommand(
                proposal_id="proposal_personal_credit_001",
                product_type="personal_credit",
                channel="api",
                effective_at=NOW + timedelta(days=2),
                field_values=_decision_field_values(),
            ),
            context=_context("tenant_alpha"),
            trusted_context=_trusted_context(scopes=("decision:execute", "policy:read")),
        )
    rejected_event = audit.events[-1]
    assert isinstance(rejected_event, CreditDecisionAuditIntent)
    assert rejected_event.event_type == "credit_decision.rejected"
    assert rejected_event.decision_id.startswith("decision_")
    assert rejected_event.decision_id != "unknown_credit_decision"
    assert rejected_event.proposal_id == "proposal_personal_credit_001"

    recalculated = service.execute_credit_decision(
        ExecuteCreditDecisionCommand(
            decision_id="decision_personal_credit_003",
            proposal_id="proposal_personal_credit_002",
            product_type="personal_credit",
            channel="api",
            effective_at=NOW + timedelta(days=2),
            field_values=_decision_field_values(),
        ),
        context=_context("tenant_alpha"),
        trusted_context=_trusted_context(scopes=("decision:execute", "policy:read")),
    )
    assert first.decision.decision_fingerprint != recalculated.decision.decision_fingerprint


def test_execute_credit_decision_never_approves_missing_fields_or_conflicting_rules() -> None:
    audit = RecordingAuditPublisher()
    service = _service(audit=audit)
    _create_and_publish_policy(service)

    missing = service.execute_credit_decision(
        ExecuteCreditDecisionCommand(
            decision_id="decision_missing_fields_001",
            proposal_id="proposal_missing_fields_001",
            product_type="personal_credit",
            channel="api",
            effective_at=NOW + timedelta(days=2),
            field_values=(
                CreditDecisionInputFieldValue.create(
                    field="requested_amount_units",
                    value=700_000,
                ),
            ),
        ),
        context=_context("tenant_alpha"),
        trusted_context=_trusted_context(scopes=("decision:execute", "policy:read")),
    )
    assert missing.decision.outcome == "request_more_data"
    assert missing.decision.fallback_action == "request_more_data"
    assert missing.decision.required_data_refs == (
        "monthly_income_units",
        "requested_installments",
        "requested_term_days",
    )
    assert missing.decision.reason_code_refs == ()
    assert missing.decision.validation_issues[0].code == "missing_limit_field"
    missing_event = audit.events[-1]
    assert isinstance(missing_event, CreditDecisionAuditIntent)
    assert missing_event.safe_details["fallback_action"] == "request_more_data"
    assert missing_event.safe_details["channel"] == "api"
    assert missing_event.safe_details["policy_id"] == "pol_personal_credit_default"
    assert missing_event.safe_details["required_data_count"] == "3"
    assert missing_event.safe_details["required_data_refs"] == (
        "monthly_income_units,requested_installments,requested_term_days"
    )
    assert missing_event.safe_details["validation_issue_codes"] == (
        "missing_limit_field,missing_rule_field,no_policy_rule_triggered"
    )
    assert "700000" not in str(missing_event.safe_details)
    assert missing.logs[0]["payload"] == "[OMITIDO]"
    assert missing.logs[0]["extra"]["channel"] == "api"
    assert missing.logs[0]["extra"]["fallback_action"] == "request_more_data"
    assert missing.logs[0]["extra"]["required_data_count"] == 3
    assert missing.logs[0]["extra"]["required_data_refs"] == [
        "monthly_income_units",
        "requested_installments",
        "requested_term_days",
    ]
    assert missing.logs[0]["extra"]["validation_issue_codes"] == [
        "missing_limit_field",
        "missing_rule_field",
        "no_policy_rule_triggered",
    ]
    assert "700000" not in str(missing.logs[0])

    conflict_repository = InMemoryCreditPolicyRepository()
    conflict_service = _service(
        audit=RecordingAuditPublisher(),
        repository=conflict_repository,
        catalog_repository=_published_catalog_repository(include_reject=True),
    )
    conflict_repository.save(
        _published_policy_direct(
            rules=(
                _rule(rule_id="rule_reject_income", outcome="reject"),
                _rule(rule_id="rule_approve_income", outcome="approve"),
            ),
        )
    )
    conflict = conflict_service.execute_credit_decision(
        ExecuteCreditDecisionCommand(
            decision_id="decision_conflict_001",
            proposal_id="proposal_conflict_001",
            product_type="personal_credit",
            channel="api",
            effective_at=NOW + timedelta(days=2),
            field_values=_decision_field_values(),
        ),
        context=_context("tenant_alpha"),
        trusted_context=_trusted_context(scopes=("decision:execute", "policy:read")),
    )
    assert conflict.decision.outcome == "unable_to_decide"
    assert conflict.decision.reason_code_refs == ()
    assert conflict.decision.validation_issues[0].code == "conflicting_policy_rule_outcomes"


def test_execute_credit_decision_requires_published_applicable_policy_and_execute_scope() -> None:
    service = _service(audit=RecordingAuditPublisher())
    created = service.create_policy_draft(
        _create_policy_command(),
        context=_context("tenant_alpha"),
        trusted_context=_trusted_context(scopes=("policy:write", "policy:read")),
    )

    with pytest.raises(PolicyTenantContextError, match="escopo obrigatório ausente"):
        service.execute_credit_decision(
            _execute_command(),
            context=_context("tenant_alpha"),
            trusted_context=_trusted_context(scopes=("policy:read",)),
        )

    with pytest.raises(PolicyNotFoundError):
        service.execute_credit_decision(
            _execute_command(effective_at=NOW + timedelta(days=2)),
            context=_context("tenant_alpha"),
            trusted_context=_trusted_context(scopes=("decision:execute", "policy:read")),
        )

    assert created.policy.status == "draft"


def test_execute_credit_decision_is_not_visible_when_audit_fails() -> None:
    class FailingDecisionAuditPublisher:
        def publish(self, event: DecisionAuditIntent) -> None:
            if isinstance(event, CreditDecisionAuditIntent):
                raise RuntimeError("audit unavailable")

    policy_repository = InMemoryCreditPolicyRepository()
    catalog_repository = _published_catalog_repository()
    simulation_repository = InMemoryPolicySimulationRepository()
    decision_repository = InMemoryCreditDecisionRepository()
    bootstrap_service = _service(
        audit=RecordingAuditPublisher(),
        repository=policy_repository,
        catalog_repository=catalog_repository,
        simulation_repository=simulation_repository,
        decision_repository=decision_repository,
    )
    _create_and_publish_policy(bootstrap_service)
    failing_service = _service(
        audit=FailingDecisionAuditPublisher(),
        repository=policy_repository,
        catalog_repository=catalog_repository,
        simulation_repository=simulation_repository,
        decision_repository=decision_repository,
    )

    with pytest.raises(CreditDecisionAuditWriteError) as error:
        failing_service.execute_credit_decision(
            _execute_command(),
            context=_context("tenant_alpha"),
            trusted_context=_trusted_context(scopes=("decision:execute", "policy:read")),
        )
    assert error.value.code == "credit_decision_audit_write_failed"
    assert failing_service.logged_events[-1]["extra"]["error_code"] == (
        "credit_decision_audit_write_failed"
    )

    assert (
        decision_repository.get(
            tenant_id="tenant_alpha",
            decision_id="decision_personal_credit_001",
        )
        is None
    )


def _service_with_public_policy(*, outcome: str) -> DecisionApplicationService:
    policy_repository = InMemoryCreditPolicyRepository()
    policy_repository.save(
        _published_policy_direct(
            rules=(_rule(rule_id=f"rule_public_{outcome}", outcome=outcome),),
        )
    )
    return _service(
        audit=RecordingAuditPublisher(),
        repository=policy_repository,
        catalog_repository=_published_catalog_repository(
            include_reject=outcome == "reject",
            include_approve_with_changes=outcome == "approve_with_changes",
        ),
    )


def _service_with_conflicting_public_policy() -> DecisionApplicationService:
    policy_repository = InMemoryCreditPolicyRepository()
    service = _service(
        audit=RecordingAuditPublisher(),
        repository=policy_repository,
        catalog_repository=_published_catalog_repository(include_reject=True),
    )
    policy_repository.save(
        _published_policy_direct(
            rules=(
                _rule(rule_id="rule_public_reject_income", outcome="reject"),
                _rule(rule_id="rule_public_approve_income", outcome="approve"),
            ),
        )
    )
    return service


def _service(
    *,
    audit: CreditPolicyAuditPublisher,
    repository: InMemoryCreditPolicyRepository | None = None,
    catalog_repository: InMemoryReasonCodeCatalogRepository | None = None,
    simulation_repository: InMemoryPolicySimulationRepository | None = None,
    decision_repository: CreditDecisionRepository | None = None,
    public_proposal_status_repository: InMemoryPublicProposalStatusRepository | None = None,
) -> DecisionApplicationService:
    return DecisionApplicationService(
        repository=repository or InMemoryCreditPolicyRepository(),
        reason_code_catalog_repository=catalog_repository or _published_catalog_repository(),
        policy_simulation_repository=simulation_repository or InMemoryPolicySimulationRepository(),
        credit_decision_repository=decision_repository or InMemoryCreditDecisionRepository(),
        public_proposal_status_repository=public_proposal_status_repository,
        audit_publisher=audit,
        environment="test",
        clock=lambda: NOW,
    )


def _create_and_publish_policy(
    service: DecisionApplicationService,
    *,
    rules: tuple[PolicyRule, ...] | None = None,
):
    created = service.create_policy_draft(
        _create_policy_command(rules=rules),
        context=_context("tenant_alpha"),
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
                        "monthly_income_units": 300_000,
                        "requested_amount_units": 700_000,
                        "requested_installments": 12,
                        "requested_term_days": 360,
                    },
                ),
            ),
        ),
        context=_context("tenant_alpha"),
        trusted_context=_trusted_context(scopes=("policy:write", "policy:read")),
    )
    return service.publish_policy(
        PublishCreditPolicyCommand(
            policy_id=created.policy.policy_id,
            policy_version_id=created.policy.policy_version_id,
            simulation_id=simulation.simulation.simulation_id,
            change_summary="Publicação aprovada após simulação",
        ),
        context=_context("tenant_alpha"),
        trusted_context=_trusted_context(scopes=("policy:publish", "policy:read")),
    ).policy


def _execute_command(
    *,
    effective_at: datetime | None = None,
    integration_result_refs: tuple[str, ...] = (),
) -> ExecuteCreditDecisionCommand:
    return ExecuteCreditDecisionCommand(
        decision_id="decision_personal_credit_001",
        proposal_id="proposal_personal_credit_001",
        product_type="personal_credit",
        channel="api",
        effective_at=effective_at or NOW + timedelta(days=2),
        field_values=_decision_field_values(),
        integration_result_refs=integration_result_refs,
    )


def _decision_field_values(
    *,
    monthly_income_units: int = 300_000,
    requested_amount_units: int = 700_000,
    requested_installments: int = 12,
    requested_term_days: int = 360,
) -> tuple[CreditDecisionInputFieldValue, ...]:
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


def _create_policy_command(
    *,
    rules: tuple[PolicyRule, ...] | None = None,
) -> CreateCreditPolicyDraftCommand:
    return CreateCreditPolicyDraftCommand(
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
            starts_at=NOW + timedelta(days=1),
            ends_at=NOW + timedelta(days=31),
        ),
        rules=rules or (_rule(rule_id="rule_min_income", outcome="approve"),),
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
    )


def _published_policy_direct(*, rules: tuple[PolicyRule, ...]) -> CreditPolicy:
    return CreditPolicy.create_draft(
        policy_id="pol_personal_credit_default",
        policy_version_id="polver_personal_credit_default_v1",
        tenant_id="tenant_alpha",
        owner_subject_id="user_credit_manager",
        product_type="personal_credit",
        reason_code_catalog_id="rcc_personal_credit_default",
        reason_code_catalog_version_id="rccver_personal_credit_default_v1",
        applicability=PolicyApplicability.create(
            channels=("api",),
            starts_at=NOW + timedelta(days=1),
            ends_at=NOW + timedelta(days=31),
        ),
        rules=rules,
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
        now=NOW,
        actor_subject_id="user_credit_manager",
        correlation_id="corr_1234567890abcdef",
        change_summary="Criação direta para teste de conflito produtivo",
    ).publish(
        now=NOW,
        actor_subject_id="user_credit_manager",
        correlation_id="corr_2234567890abcdef",
        change_summary="Publicação direta para teste de conflito produtivo",
    )


def _rule(*, rule_id: str, outcome: str) -> PolicyRule:
    reason_code_by_outcome = {
        "approve": "rc_min_income",
        "reject": "rc_reject_income",
        "approve_with_changes": "rc_approve_with_changes",
    }
    return PolicyRule.create(
        rule_id=rule_id,
        name="Renda mínima declarada",
        source_field="monthly_income_units",
        operator="gte",
        threshold_value=250_000,
        outcome=outcome,
        reason_code_refs=(reason_code_by_outcome.get(outcome, "rc_min_income"),),
    )


def _published_catalog_repository(
    *,
    include_reject: bool = False,
    include_approve_with_changes: bool = False,
    reason_code_audience: str = "both",
) -> InMemoryReasonCodeCatalogRepository:
    repository = InMemoryReasonCodeCatalogRepository()
    draft = ReasonCodeCatalog.create_draft(
        catalog_id="rcc_personal_credit_default",
        catalog_version_id="rccver_personal_credit_default_v1",
        tenant_id="tenant_alpha",
        owner_subject_id="user_credit_manager",
        product_type="personal_credit",
        reason_codes=_reason_codes(
            include_reject=include_reject,
            include_approve_with_changes=include_approve_with_changes,
            reason_code_audience=reason_code_audience,
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
        now=NOW,
        actor_subject_id="user_credit_manager",
        correlation_id="corr_1234567890abcdef",
        change_summary="Criação inicial do catálogo",
    )
    repository.save_with_next_version(
        draft.publish(
            now=NOW,
            actor_subject_id="user_credit_manager",
            correlation_id="corr_2234567890abcdef",
            change_summary="Publicação do catálogo",
        )
    )
    return repository


def _reason_codes(
    *,
    include_reject: bool,
    include_approve_with_changes: bool = False,
    reason_code_audience: str = "both",
) -> tuple[ReasonCode, ...]:
    reason_codes = [
        ReasonCode.create(
            reason_code_id="reason_min_income",
            code="rc_min_income",
            outcome="approve",
            title="Renda mínima",
            internal_description="Renda declarada atende a política",
            external_description="Renda declarada compatível com aprovação",
            factor_refs=("factor_monthly_income",),
            audience=reason_code_audience,
        )
    ]
    if include_reject:
        reason_codes.append(
            ReasonCode.create(
                reason_code_id="reason_reject_income",
                code="rc_reject_income",
                outcome="reject",
                title="Renda insuficiente",
                internal_description="Renda declarada fora da política",
                external_description="Renda declarada insuficiente para aprovação",
                factor_refs=("factor_monthly_income",),
            )
        )
    if include_approve_with_changes:
        reason_codes.append(
            ReasonCode.create(
                reason_code_id="reason_approve_with_changes",
                code="rc_approve_with_changes",
                outcome="approve_with_changes",
                title="Aprovação com ajustes",
                internal_description="A política permite aprovação com termos ajustados",
                external_description="A análise permite aprovação com alterações nas condições",
                factor_refs=("factor_monthly_income",),
            )
        )
    return tuple(reason_codes)


def _context(
    tenant_id: str | None,
    *,
    correlation_id: str = "corr_1234567890abcdef",
    request_id: str = "req_1234567890abcdef",
    tenant_isolation_tier: str = "bridge",
    trace_id: str = "1234567890abcdef1234567890abcdef",
) -> ObservabilityContext:
    return ObservabilityContext.new(
        correlation_id=correlation_id,
        request_id=request_id,
        trace_id=trace_id,
        tenant_id=tenant_id,
        tenant_isolation_tier=tenant_isolation_tier,
    )


def _trusted_context(
    *,
    tenant_id: str = "tenant_alpha",
    tenant_isolation_tier: str = "bridge",
    subject_id: str = "user_credit_manager",
    scopes: tuple[str, ...] = ("decision:execute", "policy:read"),
    correlation_id: str = "corr_1234567890abcdef",
    request_id: str = "req_1234567890abcdef",
    trace_id: str = "1234567890abcdef1234567890abcdef",
) -> PropagatedContext:
    return PropagatedContext(
        trusted=TrustedContext(
            tenant_id=tenant_id,
            tenant_isolation_tier=tenant_isolation_tier,
            subject_id=subject_id,
            scopes=scopes,
            roles=("credit-manager",),
            client_id="client_admin_console",
            principal_type="human",
        ),
        correlation_id=correlation_id,
        request_id=request_id,
        traceparent=f"00-{trace_id}-1234567890abcdef-01",
    )


def _iter_nested_keys(value: object):
    if isinstance(value, dict):
        for key, nested_value in value.items():
            yield str(key)
            yield from _iter_nested_keys(nested_value)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _iter_nested_keys(item)
