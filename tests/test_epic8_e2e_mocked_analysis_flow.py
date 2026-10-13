from __future__ import annotations

from dataclasses import asdict

import pytest
from creditos_observability.gates import validate_observability_exposure_payload

from epic8_mocked_analysis_flow_support import (
    assert_no_public_tenant_leakage,
    assert_no_sensitive_data,
    assert_public_decision_contract_payload,
    assert_required_traceability,
    assert_valid_webhook_signature,
    assert_webhook_contract_payload,
    run_mocked_analysis_flow,
)


def test_mocked_analysis_flow_submits_enriches_decides_audits_and_notifies() -> None:
    result = run_mocked_analysis_flow()

    assert result.proposal_id.startswith("proposal_")
    assert result.replayed_proposal_id == result.proposal_id
    assert result.proposal_status == "submitted"
    assert result.proposal_outbox_type == "creditos.proposal.v1.submitted"
    assert result.proposal_created_effect_counts == {
        "proposals": 1,
        "idempotency_submissions": 1,
        "statuses": 1,
        "outbox_messages": 1,
    }
    assert result.proposal_replayed_effect_counts == result.proposal_created_effect_counts

    assert {integration["status"] for integration in result.mock_plan_integrations} == {"completed"}
    assert {integration["schema_version"] for integration in result.mock_plan_integrations} == {
        "1.0"
    }
    assert {integration["status"] for integration in result.integrations} == {"completed"}
    assert {integration["schema_version"] for integration in result.integrations} == {"1.0"}
    assert {integration["correlation_id"] for integration in result.integrations} == {
        result.correlation_id
    }
    assert result.integration_execution_status == "completed"
    assert result.integration_cost_units == 48

    assert result.decision_input_fields == {
        "monthly_income_units": 800_000,
        "requested_amount_units": 500_000,
        "requested_installments": 6,
        "requested_term_days": 34,
    }
    assert result.decision.status == "completed"
    assert result.decision.outcome == "approve"
    assert result.decision.policy_version_id == "polver_personal_credit_default_v1"
    assert result.decision.reason_codes == ("rc_min_income",)

    assert result.public_decision is not None
    public_payload = asdict(result.public_decision)
    assert_public_decision_contract_payload(public_payload)
    assert public_payload["contract_version"] == "v1"
    assert public_payload["status"] == "completed"
    assert public_payload["outcome"] == "approve"
    assert public_payload["correlation_id"] == result.correlation_id
    assert "tenant_id" not in str(public_payload)
    assert "triggered_rule_ids" not in str(public_payload)

    assert result.webhook_request is not None
    assert result.webhook_request.payload["proposal_id"] == result.proposal_id
    assert_webhook_contract_payload(result.webhook_request.payload)
    assert_valid_webhook_signature(result.webhook_request)
    assert result.webhook_request.payload["decision_outcome"] == "approve"
    assert result.webhook_request.headers["X-CreditOS-Correlation-Id"] == result.correlation_id
    assert result.webhook_request.headers["X-CreditOS-Signature"].startswith("sha256=")
    assert result.webhook_request.payload["contract_version"] == "v1"
    assert tuple(result.webhook_replay_job_ids) == (result.webhook_request.job_id,)
    assert result.webhook_delivery_attempt_count == 1
    assert_no_sensitive_data(result.webhook_request.payload)

    assert {
        "credit_decision.completed",
        "credit_decision.public_query_retrieved",
    }.issubset(result.audit_event_types)
    assert {
        "proposal_intake.submit_with_initial_status_and_outbox",
        "integration_mock.execute_plan",
        "integration_execution.fan_in",
        "webhook_delivery.sent",
        "credit_decision.completed",
        "credit_decision.public_query_retrieved",
    }.issubset(result.critical_evidence_operations)
    assert result.reporting_snapshot.funnel_counts["received"] == 1
    assert result.reporting_snapshot.funnel_counts["enriched"] == 1
    assert result.reporting_snapshot.funnel_counts["approved"] == 1
    assert result.reporting_snapshot.decision_counts["approved"] == 1
    assert result.reporting_snapshot.decision_query_counts["succeeded"] == 1
    assert result.reporting_snapshot.callback_counts["delivered"] == 1
    assert result.reporting_snapshot.estimated_cost_units == 48
    assert result.reporting_snapshot.actual_cost_units == 48

    assert_required_traceability(result.traceability_steps)
    assert result.correlation_ids == {result.correlation_id}
    validate_observability_exposure_payload(
        result.observable_payload,
        exposure="technical_internal",
    )
    assert_no_sensitive_data(result.observable_payload)
    assert_no_sensitive_data(result.raw_output_payload)


def test_mocked_analysis_flow_blocks_cross_tenant_public_query_without_leaking_existence() -> None:
    result = run_mocked_analysis_flow()

    assert result.cross_tenant_error is not None
    assert result.missing_proposal_error is not None
    assert result.cross_tenant_error == result.missing_proposal_error
    assert result.cross_tenant_error.error_code == "decision_not_available"
    assert result.cross_tenant_error.status_code == 404
    assert_no_sensitive_data(result.cross_tenant_observable_payload)
    assert_no_public_tenant_leakage(result.cross_tenant_observable_payload)


def test_mocked_analysis_flow_negative_gates_fail_for_security_and_contract_drift() -> None:
    result = run_mocked_analysis_flow()
    assert result.webhook_request is not None

    with pytest.raises(AssertionError):
        assert_required_traceability(result.traceability_steps - {"webhook"})

    with pytest.raises(ValueError, match="termos proibidos"):
        validate_observability_exposure_payload(
            {"events": [{"technical_result": {"cpf": "00000000191"}}]},
            exposure="technical_internal",
        )

    leaky_public_payload = dict(result.webhook_request.payload) | {"cpf": "00000000191"}
    with pytest.raises(AssertionError):
        assert_no_sensitive_data(leaky_public_payload)

    drifted_webhook_payload = dict(result.webhook_request.payload) | {"tenant_id": "tenant_alpha"}
    with pytest.raises(AssertionError):
        assert_webhook_contract_payload(drifted_webhook_payload)

    malformed_webhook_payload = dict(result.webhook_request.payload) | {"event_id": "evt_bad"}
    with pytest.raises(AssertionError):
        assert_webhook_contract_payload(malformed_webhook_payload)
