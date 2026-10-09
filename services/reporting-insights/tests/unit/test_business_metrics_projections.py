from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from creditos_reporting_insights.adapters.persistence import (
    in_memory_business_projection_repository as projection_repositories,
)
from creditos_reporting_insights.application.service import ReportingInsightsService
from creditos_reporting_insights.domain.errors import (
    BusinessEventValidationError,
    BusinessProjectionNotFoundError,
    BusinessProjectionTenantError,
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
    ReviewStatus,
)


def test_projects_business_funnel_decisions_integrations_costs_and_freshness() -> None:
    occurred_at = _utc_now() - timedelta(seconds=30)
    processed_at = occurred_at + timedelta(seconds=10)
    service = _service(processed_at=processed_at + timedelta(seconds=20))

    proposal_result = service.record_event(
        BusinessEvent.proposal(
            event_id="evt-proposal-001",
            source="proposal-intake",
            tenant_id="tenant-alpha",
            product_type=ProductType.PERSONAL_CREDIT,
            occurred_at=occurred_at,
            processed_at=processed_at,
            channel=Channel.API,
            funnel_status=ProposalFunnelStatus.RECEIVED,
            idempotency_key="idem-proposal-001",
        )
    )
    decision_result = service.record_event(
        BusinessEvent.decision(
            event_id="evt-decision-001",
            source="decision",
            tenant_id="tenant-alpha",
            product_type=ProductType.PERSONAL_CREDIT,
            occurred_at=occurred_at + timedelta(seconds=5),
            processed_at=processed_at + timedelta(seconds=5),
            channel=Channel.API,
            outcome=DecisionOutcome.APPROVED_WITH_CHANGES,
            reason_codes=("policy_income_band", "risk_low"),
            idempotency_key="idem-decision-001",
        )
    )
    integration_result = service.record_event(
        BusinessEvent.integration(
            event_id="evt-integration-001",
            source="integration",
            tenant_id="tenant-alpha",
            product_type=ProductType.PERSONAL_CREDIT,
            occurred_at=occurred_at + timedelta(seconds=8),
            processed_at=processed_at + timedelta(seconds=8),
            channel=Channel.API,
            integration_class="credit_bureau",
            adapter_id="mock-bureau-v1",
            provider_id="iprv_mock_provider_v1",
            status=IntegrationStatus.SUCCEEDED,
            estimated_cost_units=20,
            actual_cost_units=18,
            latency_ms=120,
        )
    )
    enriched_result = service.record_event(
        BusinessEvent.proposal(
            event_id="evt-proposal-enriched-001",
            source="creditos://proposal-intake",
            tenant_id="tenant-alpha",
            product_type=ProductType.PERSONAL_CREDIT,
            occurred_at=occurred_at + timedelta(seconds=9),
            processed_at=processed_at + timedelta(seconds=9),
            channel=Channel.API,
            funnel_status=ProposalFunnelStatus.ENRICHED,
            idempotency_key="idem-proposal-enriched-001",
        )
    )
    review_result = service.record_event(
        BusinessEvent.ai_review(
            event_id="evt-review-001",
            source="automated-review",
            tenant_id="tenant-alpha",
            product_type=ProductType.PERSONAL_CREDIT,
            occurred_at=occurred_at + timedelta(seconds=9),
            processed_at=processed_at + timedelta(seconds=9),
            channel=Channel.API,
            status=ReviewStatus.COMPLETED,
            actual_cost_units=7,
            latency_ms=90,
        )
    )
    callback_result = service.record_event(
        BusinessEvent.callback(
            event_id="evt-callback-001",
            source="callback-dispatcher",
            tenant_id="tenant-alpha",
            product_type=ProductType.PERSONAL_CREDIT,
            occurred_at=occurred_at + timedelta(seconds=10),
            processed_at=processed_at + timedelta(seconds=10),
            channel=Channel.API,
            status=CallbackStatus.DELIVERED,
            latency_ms=40,
        )
    )

    snapshot = callback_result.snapshot

    assert proposal_result.applied is True
    assert decision_result.applied is True
    assert integration_result.applied is True
    assert enriched_result.applied is True
    assert review_result.applied is True
    assert callback_result.applied is True
    assert snapshot.funnel_counts["received"] == 1
    assert snapshot.funnel_counts["decided"] == 1
    assert snapshot.funnel_counts["approved_with_changes"] == 1
    assert snapshot.funnel_counts["enriched"] == 1
    assert snapshot.decision_counts["approved_with_changes"] == 1
    assert snapshot.reason_code_counts["policy_income_band"] == 1
    integration_dimension = "credit_bureau|mock-bureau-v1|iprv_mock_provider_v1"
    assert snapshot.integration_counts[f"{integration_dimension}|succeeded"] == 1
    assert snapshot.integration_estimated_cost_units[integration_dimension] == 20
    assert snapshot.integration_actual_cost_units[integration_dimension] == 18
    assert snapshot.integration_total_latency_ms[integration_dimension] == 120
    assert snapshot.integration_latency_event_counts[integration_dimension] == 1
    assert snapshot.review_counts["completed"] == 1
    assert snapshot.callback_counts["delivered"] == 1
    assert snapshot.estimated_cost_units == 20
    assert snapshot.actual_cost_units == 25
    assert snapshot.total_latency_ms == 250
    assert snapshot.latency_event_count == 3
    assert snapshot.freshness.status == "fresh"
    assert snapshot.key.tenant_id == "tenant-alpha"


def test_projects_decision_query_and_callback_dlq_observability_events() -> None:
    occurred_at = _utc_now() - timedelta(seconds=30)
    processed_at = occurred_at + timedelta(seconds=5)
    service = _service(processed_at=processed_at + timedelta(seconds=10))

    query_result = service.record_event(
        BusinessEvent.decision_query(
            event_id="evt-public-query-001",
            source="creditos://decision",
            tenant_id="tenant-alpha",
            product_type=ProductType.PERSONAL_CREDIT,
            occurred_at=occurred_at,
            processed_at=processed_at,
            channel=Channel.API,
            status=DecisionQueryStatus.SUCCEEDED,
            idempotency_key="idem-public-query-001",
            latency_ms=31,
        )
    )
    dlq_result = service.record_event(
        BusinessEvent.callback(
            event_id="evt-callback-dlq-001",
            source="creditos://callback-dispatcher",
            tenant_id="tenant-alpha",
            product_type=ProductType.PERSONAL_CREDIT,
            occurred_at=occurred_at + timedelta(seconds=1),
            processed_at=processed_at + timedelta(seconds=1),
            channel=Channel.API,
            status=CallbackStatus.DLQ,
            idempotency_key="idem-callback-dlq-001",
            latency_ms=52,
            error_count=1,
        )
    )

    snapshot = dlq_result.snapshot

    assert query_result.applied is True
    assert dlq_result.applied is True
    assert snapshot.decision_query_counts["succeeded"] == 1
    assert snapshot.callback_counts["dlq"] == 1
    assert snapshot.error_count == 1
    assert snapshot.total_latency_ms == 83
    assert snapshot.latency_event_count == 2


def test_duplicate_events_are_idempotent_by_source_id_and_idempotency_key() -> None:
    service = _service(processed_at=_utc_now())
    event = _proposal_event(event_id="evt-proposal-dup", idempotency_key="idem-dup")

    first_result = service.record_event(event)
    duplicate_by_source_id = service.record_event(
        _proposal_event(event_id="evt-proposal-dup", idempotency_key="idem-other")
    )
    duplicate_by_idempotency_key = service.record_event(
        _proposal_event(event_id="evt-proposal-other", idempotency_key="idem-dup")
    )

    assert first_result.applied is True
    assert duplicate_by_source_id.duplicate is True
    assert duplicate_by_idempotency_key.duplicate is True
    assert duplicate_by_idempotency_key.snapshot.funnel_counts["received"] == 1
    assert len(service.list_tenant_snapshots(tenant_id="tenant-alpha")) == 1


def test_shared_idempotency_key_is_scoped_by_event_type_and_schema() -> None:
    service = _service(processed_at=_utc_now())

    proposal_result = service.record_event(
        _proposal_event(event_id="evt-shared-proposal", idempotency_key="idem-shared")
    )
    integration_result = service.record_event(
        BusinessEvent.integration(
            event_id="evt-shared-integration",
            source="creditos://integration",
            tenant_id="tenant-alpha",
            product_type=ProductType.BNPL,
            occurred_at=_utc_now() - timedelta(seconds=10),
            processed_at=_utc_now(),
            channel=Channel.CHECKOUT,
            integration_class="credit_bureau",
            adapter_id="mock-bureau-v1",
            provider_id="iprv_mock_provider_v1",
            status=IntegrationStatus.SUCCEEDED,
            idempotency_key="idem-shared",
            actual_cost_units=10,
        )
    )

    assert proposal_result.applied is True
    assert integration_result.applied is True
    assert integration_result.snapshot.funnel_counts["received"] == 1
    assert (
        integration_result.snapshot.integration_counts[
            "credit_bureau|mock-bureau-v1|iprv_mock_provider_v1|succeeded"
        ]
        == 1
    )
    assert integration_result.snapshot.actual_cost_units == 10


def test_duplicate_with_different_projection_key_returns_original_projection() -> None:
    service = _service(processed_at=_utc_now())
    first_result = service.record_event(
        _proposal_event(
            event_id="evt-proposal-original",
            idempotency_key="idem-shared",
            occurred_at=datetime(2026, 9, 27, 10, 0, tzinfo=UTC),
        )
    )
    duplicate_result = service.record_event(
        _proposal_event(
            event_id="evt-proposal-other",
            idempotency_key="idem-shared",
            occurred_at=datetime(2026, 9, 28, 10, 0, tzinfo=UTC),
        )
    )

    assert duplicate_result.duplicate is True
    assert duplicate_result.snapshot.key == first_result.snapshot.key
    assert len(service.list_tenant_snapshots(tenant_id="tenant-alpha")) == 1


def test_global_source_event_id_replay_with_other_tenant_is_rejected() -> None:
    service = _service(processed_at=_utc_now())

    service.record_event(_proposal_event(event_id="evt-global-replay", tenant_id="tenant-alpha"))

    with pytest.raises(BusinessProjectionTenantError):
        service.record_event(_proposal_event(event_id="evt-global-replay", tenant_id="tenant-beta"))


def test_out_of_order_event_counts_without_reducing_freshness() -> None:
    now = _utc_now()
    service = _service(processed_at=now + timedelta(seconds=20))
    latest = _proposal_event(
        event_id="evt-proposal-latest",
        idempotency_key="idem-proposal-latest",
        occurred_at=now - timedelta(seconds=30),
        processed_at=now,
    )
    older = _proposal_event(
        event_id="evt-proposal-older",
        idempotency_key="idem-proposal-older",
        occurred_at=now - timedelta(minutes=10),
        processed_at=now - timedelta(seconds=5),
    )

    latest_result = service.record_event(latest)
    older_result = service.record_event(older)

    assert older_result.late_event is True
    assert older_result.snapshot.late_event_count == 1
    assert older_result.snapshot.funnel_counts["received"] == 2
    assert (
        older_result.snapshot.freshness.last_event_time
        == latest_result.snapshot.freshness.last_event_time
    )
    older_processed_at = older_result.snapshot.freshness.last_processed_at
    latest_processed_at = latest_result.snapshot.freshness.last_processed_at
    assert older_processed_at is not None
    assert latest_processed_at is not None
    assert older_processed_at >= latest_processed_at


@pytest.mark.parametrize("status", [IntegrationStatus.FAILED, IntegrationStatus.SUCCEEDED])
def test_integration_events_do_not_count_as_enriched(status: IntegrationStatus) -> None:
    service = _service(processed_at=_utc_now())

    result = service.record_event(
        BusinessEvent.integration(
            event_id=f"evt-integration-{status.value}",
            source="integration",
            tenant_id="tenant-alpha",
            product_type=ProductType.BNPL,
            occurred_at=_utc_now() - timedelta(seconds=10),
            processed_at=_utc_now(),
            integration_class="credit_bureau",
            adapter_id="mock-bureau-v1",
            provider_id="iprv_mock_provider_v1",
            status=status,
            error_count=1 if status is IntegrationStatus.FAILED else 0,
        )
    )

    assert (
        result.snapshot.integration_counts[
            f"credit_bureau|mock-bureau-v1|iprv_mock_provider_v1|{status.value}"
        ]
        == 1
    )
    assert "enriched" not in result.snapshot.funnel_counts


def test_cross_tenant_queries_do_not_return_other_tenant_projection() -> None:
    service = _service()

    service.record_event(_proposal_event(tenant_id="tenant-alpha"))

    with pytest.raises(BusinessProjectionNotFoundError):
        service.list_tenant_snapshots(tenant_id="tenant-beta")


@pytest.mark.parametrize(
    ("field_name", "field_value"),
    [
        ("tenant_id", "tenant.person@example.com"),
        ("event_id", "cpf_12345678901"),
        ("source", "provider_payload"),
        ("idempotency_key", "token-secret"),
    ],
)
def test_sensitive_or_high_cardinality_dimensions_are_rejected(
    field_name: str,
    field_value: str,
) -> None:
    kwargs: dict[str, Any] = {
        "event_id": "evt-proposal-safe",
        "source": "proposal-intake",
        "tenant_id": "tenant-alpha",
        "idempotency_key": "idem-safe",
    }
    kwargs[field_name] = field_value

    with pytest.raises(BusinessEventValidationError):
        _proposal_event(**kwargs)


@pytest.mark.parametrize("cost_units", [-1, 1.5, True])
def test_cost_units_reject_negative_float_and_bool(cost_units: object) -> None:
    with pytest.raises(BusinessEventValidationError):
        BusinessEvent.integration(
            event_id="evt-integration-cost",
            source="integration",
            tenant_id="tenant-alpha",
            product_type=ProductType.BNPL,
            occurred_at=_utc_now(),
            processed_at=_utc_now(),
            integration_class="credit_bureau",
            adapter_id="mock-bureau-v1",
            status=IntegrationStatus.SUCCEEDED,
            actual_cost_units=cost_units,  # type: ignore[arg-type]
        )


def test_invalid_status_schema_timestamp_and_sensitive_reason_codes_are_rejected() -> None:
    with pytest.raises(ValueError):
        ProposalFunnelStatus("unexpected_status")

    with pytest.raises(BusinessEventValidationError):
        _proposal_event(occurred_at=datetime.now())

    with pytest.raises(BusinessEventValidationError):
        _proposal_event(schema_version="v2")

    with pytest.raises(BusinessEventValidationError):
        _proposal_event(processed_at=_utc_now() - timedelta(days=1))

    with pytest.raises(BusinessEventValidationError):
        BusinessEvent.decision(
            event_id="evt-decision-sensitive",
            source="decision",
            tenant_id="tenant-alpha",
            product_type=ProductType.BNPL,
            occurred_at=_utc_now(),
            processed_at=_utc_now(),
            channel=Channel.CHECKOUT,
            outcome=DecisionOutcome.DECLINED,
            reason_codes=("person@example.com",),
        )

    with pytest.raises(BusinessEventValidationError):
        BusinessEvent.decision(
            event_id="evt-decision-sensitive-reason",
            source="decision",
            tenant_id="tenant-alpha",
            product_type=ProductType.BNPL,
            occurred_at=_utc_now(),
            processed_at=_utc_now(),
            channel=Channel.CHECKOUT,
            outcome=DecisionOutcome.DECLINED,
            reason_codes=("cpf_12345678901",),
        )

    with pytest.raises(BusinessEventValidationError):
        BusinessEvent.decision(
            event_id="evt-decision-ungoverned-reason",
            source="decision",
            tenant_id="tenant-alpha",
            product_type=ProductType.BNPL,
            occurred_at=_utc_now(),
            processed_at=_utc_now(),
            channel=Channel.CHECKOUT,
            outcome=DecisionOutcome.DECLINED,
            reason_codes=("custom_reason",),
        )


def test_integration_dimensions_and_reason_code_cardinality_are_governed() -> None:
    with pytest.raises(BusinessEventValidationError):
        BusinessEvent.integration(
            event_id="evt-integration-unknown-class",
            source="integration",
            tenant_id="tenant-alpha",
            product_type=ProductType.BNPL,
            occurred_at=_utc_now() - timedelta(seconds=10),
            processed_at=_utc_now(),
            integration_class="bureau_credit",
            adapter_id="mock-bureau-v1",
            status=IntegrationStatus.SUCCEEDED,
        )

    with pytest.raises(BusinessEventValidationError):
        BusinessEvent.decision(
            event_id="evt-decision-too-many-reasons",
            source="decision",
            tenant_id="tenant-alpha",
            product_type=ProductType.BNPL,
            occurred_at=_utc_now() - timedelta(seconds=10),
            processed_at=_utc_now(),
            channel=Channel.CHECKOUT,
            outcome=DecisionOutcome.DECLINED,
            reason_codes=tuple(f"reason_{index:02d}" for index in range(21)),
        )


def test_cost_latency_and_error_count_have_operational_ceilings() -> None:
    with pytest.raises(BusinessEventValidationError):
        BusinessEvent.integration(
            event_id="evt-integration-huge-cost",
            source="integration",
            tenant_id="tenant-alpha",
            product_type=ProductType.BNPL,
            occurred_at=_utc_now() - timedelta(seconds=10),
            processed_at=_utc_now(),
            integration_class="credit_bureau",
            adapter_id="mock-bureau-v1",
            status=IntegrationStatus.SUCCEEDED,
            actual_cost_units=1_000_000_001,
        )

    with pytest.raises(BusinessEventValidationError):
        BusinessEvent.integration(
            event_id="evt-integration-huge-latency",
            source="integration",
            tenant_id="tenant-alpha",
            product_type=ProductType.BNPL,
            occurred_at=_utc_now() - timedelta(seconds=10),
            processed_at=_utc_now(),
            integration_class="credit_bureau",
            adapter_id="mock-bureau-v1",
            status=IntegrationStatus.SUCCEEDED,
            latency_ms=120_001,
        )


def _service(*, processed_at: datetime | None = None) -> ReportingInsightsService:
    return ReportingInsightsService(
        repository=projection_repositories.InMemoryBusinessProjectionRepository(),
        processed_at_factory=(lambda: processed_at or _utc_now()),
    )


def _proposal_event(
    *,
    event_id: str = "evt-proposal-001",
    source: str = "proposal-intake",
    tenant_id: str = "tenant-alpha",
    idempotency_key: str = "idem-proposal-001",
    occurred_at: datetime | None = None,
    processed_at: datetime | None = None,
    schema_version: str = "v1",
) -> BusinessEvent:
    event_time = occurred_at or _utc_now() - timedelta(seconds=10)
    processing_time = processed_at or event_time + timedelta(seconds=1)
    return BusinessEvent.proposal(
        event_id=event_id,
        source=source,
        tenant_id=tenant_id,
        product_type=ProductType.BNPL,
        occurred_at=event_time,
        processed_at=processing_time,
        channel=Channel.CHECKOUT,
        funnel_status=ProposalFunnelStatus.RECEIVED,
        schema_version=schema_version,
        idempotency_key=idempotency_key,
    )


def _utc_now() -> datetime:
    return datetime.now(UTC)
