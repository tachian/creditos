from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

import pytest
from creditos_observability import validate_customer_facing_observability_payload
from creditos_reporting_insights.adapters.persistence import (
    in_memory_business_projection_repository as projection_repositories,
)
from creditos_reporting_insights.application.customer_dashboard_service import (
    CustomerDashboardService,
)
from creditos_reporting_insights.application.ports.business_projection_repository import (
    BusinessProjectionApplyResult,
)
from creditos_reporting_insights.application.service import ReportingInsightsService
from creditos_reporting_insights.domain.entities.business_metrics_projection import (
    BusinessMetricsProjection,
    ProjectionKey,
)
from creditos_reporting_insights.domain.errors import (
    BusinessProjectionNotFoundError,
    BusinessProjectionTenantError,
    CustomerDashboardAuthorizationError,
    CustomerDashboardPrivacyError,
)
from creditos_reporting_insights.domain.value_objects.business_events import (
    BusinessEvent,
    CallbackStatus,
    Channel,
    DecisionOutcome,
    IntegrationStatus,
    ProductType,
    ProposalFunnelStatus,
    ReviewStatus,
    TenantIsolationTier,
)
from creditos_reporting_insights.domain.value_objects.customer_dashboard import (
    CustomerDashboardIncident,
    CustomerDashboardOperationalImpact,
    OperationalImpactStatus,
)
from creditos_reporting_insights.domain.value_objects.customer_dashboard_access import (
    CustomerDashboardAccessContext,
)


def test_builds_customer_dashboard_from_curated_projection_only() -> None:
    repository = projection_repositories.InMemoryBusinessProjectionRepository()
    reporting_service = _reporting_service(repository)
    dashboard_service = CustomerDashboardService(repository=repository)
    occurred_at = _utc_now() - timedelta(seconds=60)

    _record_complete_flow(reporting_service, tenant_id="tenant-alpha", occurred_at=occurred_at)
    reporting_service.record_event(
        _proposal_event(
            event_id="evt-tenant-beta",
            tenant_id="tenant-beta",
            idempotency_key="idem-tenant-beta",
            occurred_at=occurred_at,
        )
    )

    dashboard = dashboard_service.build_dashboard(
        context=CustomerDashboardAccessContext(
            tenant_id="tenant-alpha",
            scopes=frozenset({"dashboard:read"}),
        )
    )
    payload = dashboard.to_dict()
    sections = _sections(payload)
    serialized = json.dumps(payload, sort_keys=True)

    assert payload["tenant_ref"] == "tenant-alpha"
    assert payload["tenant_isolation_tier"] == "bridge"
    assert sections["business_funnel"]["cards"]["received"]["count"] == 1
    assert sections["business_funnel"]["cards"]["decided"]["count"] == 1
    assert sections["decisions"]["cards"]["approved_with_changes"]["count"] == 1
    assert sections["reason_codes"]["cards"]["policy_income_band"]["count"] == 1
    assert sections["integrations"]["cards"]["credit_bureau"]["succeeded"] == 1
    assert sections["reviews"]["cards"]["completed"]["count"] == 1
    assert sections["callbacks"]["cards"]["delivered"]["count"] == 1
    assert sections["costs"]["cards"]["actual_cost_units"]["value"] == 25
    assert sections["latency"]["cards"]["average_latency_ms"]["value"] == 83
    assert sections["errors"]["cards"]["total_errors"]["value"] == 0
    assert sections["freshness"]["cards"]["freshness_status"]["value"] == "fresh"
    assert sections["operational_health"]["cards"]["api"]["status"] == "unknown"
    assert "tenant-beta" not in serialized
    assert all(term not in serialized.lower() for term in _forbidden_terms())


def test_customer_dashboard_output_passes_epic7_exposure_gate() -> None:
    repository = projection_repositories.InMemoryBusinessProjectionRepository()
    reporting_service = _reporting_service(repository)
    dashboard_service = CustomerDashboardService(repository=repository)

    _record_complete_flow(
        reporting_service,
        tenant_id="tenant-alpha",
        occurred_at=_utc_now() - timedelta(seconds=60),
    )

    dashboard = dashboard_service.build_dashboard(
        context=CustomerDashboardAccessContext(
            tenant_id="tenant-alpha",
            scopes=frozenset({"dashboard:read"}),
        )
    )

    validate_customer_facing_observability_payload(
        dashboard.to_dict(),
        expected_tenant_ref="tenant-alpha",
        granted_scopes=frozenset({"dashboard:read"}),
        curated_source="reporting_insights_projection",
    )


def test_customer_dashboard_denies_missing_scope_before_loading_projection() -> None:
    dashboard_service = CustomerDashboardService(repository=_FailingRepository())

    with pytest.raises(CustomerDashboardAuthorizationError) as error_info:
        dashboard_service.build_dashboard(
            context=CustomerDashboardAccessContext(
                tenant_id="tenant-alpha",
                scopes=frozenset({"proposal:read"}),
            )
        )

    assert error_info.value.code == "customer_dashboard_scope_denied"


def test_customer_dashboard_rejects_tenant_override_and_cross_tenant_access() -> None:
    repository = projection_repositories.InMemoryBusinessProjectionRepository()
    reporting_service = _reporting_service(repository)
    dashboard_service = CustomerDashboardService(repository=repository)
    reporting_service.record_event(_proposal_event(tenant_id="tenant-alpha"))

    with pytest.raises(BusinessProjectionTenantError):
        dashboard_service.build_dashboard(
            context=CustomerDashboardAccessContext(
                tenant_id="tenant-alpha",
                scopes=frozenset({"reporting:read"}),
            ),
            requested_tenant_id="tenant-beta",
        )


def test_customer_dashboard_rejects_cross_tenant_snapshot_from_repository() -> None:
    dashboard_service = CustomerDashboardService(repository=_CrossTenantRepository())

    with pytest.raises(BusinessProjectionTenantError) as error_info:
        dashboard_service.build_dashboard(
            context=CustomerDashboardAccessContext(
                tenant_id="tenant-alpha",
                scopes=frozenset({"reporting:read"}),
            )
        )

    assert error_info.value.code == "customer_dashboard_snapshot_tenant_mismatch"


def test_customer_dashboard_returns_safe_not_found_for_empty_tenant() -> None:
    dashboard_service = CustomerDashboardService(
        repository=projection_repositories.InMemoryBusinessProjectionRepository()
    )

    with pytest.raises(BusinessProjectionNotFoundError):
        dashboard_service.build_dashboard(
            context=CustomerDashboardAccessContext(
                tenant_id="tenant-alpha",
                scopes=frozenset({"dashboard:read"}),
            )
        )


def test_customer_dashboard_operational_impacts_are_curated_and_safe() -> None:
    repository = projection_repositories.InMemoryBusinessProjectionRepository()
    reporting_service = _reporting_service(repository)
    reporting_service.record_event(_proposal_event(tenant_id="tenant-alpha"))
    dashboard_service = CustomerDashboardService(
        repository=repository,
        operational_impacts=(
            CustomerDashboardOperationalImpact(
                tenant_id="tenant-alpha",
                component="callbacks",
                status=OperationalImpactStatus.DEGRADED,
                message="callback_timeout_rate_above_threshold",
                incidents=(
                    CustomerDashboardIncident(
                        incident_ref="incident-callbacks-001",
                        status=OperationalImpactStatus.DEGRADED,
                        impact="callback_delivery_delayed",
                        started_at=_utc_now() - timedelta(minutes=10),
                    ),
                ),
            ),
        ),
    )

    dashboard = dashboard_service.build_dashboard(
        context=CustomerDashboardAccessContext(
            tenant_id="tenant-alpha",
            scopes=frozenset({"dashboard:read"}),
        )
    )
    payload = dashboard.to_dict()
    sections = _sections(payload)
    serialized = json.dumps(payload, sort_keys=True)

    assert sections["operational_health"]["cards"]["callbacks"]["status"] == "degraded"
    assert (
        sections["operational_health"]["cards"]["callbacks"]["incidents"][0]["impact"]
        == "callback_delivery_delayed"
    )
    assert "pod" not in serialized.lower()
    assert "cpu" not in serialized.lower()
    assert "trace" not in serialized.lower()


def test_customer_dashboard_merges_operational_impacts_by_highest_severity() -> None:
    repository = projection_repositories.InMemoryBusinessProjectionRepository()
    reporting_service = _reporting_service(repository)
    reporting_service.record_event(_proposal_event(tenant_id="tenant-alpha"))
    now = _utc_now()
    dashboard_service = CustomerDashboardService(
        repository=repository,
        operational_impacts=(
            CustomerDashboardOperationalImpact(
                tenant_id="tenant-alpha",
                component="callbacks",
                status=OperationalImpactStatus.DEGRADED,
                message="callback_delivery_delayed",
                incidents=(
                    CustomerDashboardIncident(
                        incident_ref="incident-callbacks-001",
                        status=OperationalImpactStatus.DEGRADED,
                        impact="callback_delivery_delayed",
                        started_at=now - timedelta(minutes=10),
                    ),
                ),
            ),
            CustomerDashboardOperationalImpact(
                tenant_id="tenant-alpha",
                component="callbacks",
                status=OperationalImpactStatus.UNAVAILABLE,
                message="callback_delivery_unavailable",
                incidents=(
                    CustomerDashboardIncident(
                        incident_ref="incident-callbacks-002",
                        status=OperationalImpactStatus.UNAVAILABLE,
                        impact="callback_delivery_unavailable",
                        started_at=now - timedelta(minutes=5),
                    ),
                ),
            ),
        ),
    )

    dashboard = dashboard_service.build_dashboard(
        context=CustomerDashboardAccessContext(
            tenant_id="tenant-alpha",
            scopes=frozenset({"dashboard:read"}),
        )
    )
    callbacks = _sections(dashboard.to_dict())["operational_health"]["cards"]["callbacks"]

    assert callbacks["status"] == "unavailable"
    assert callbacks["message"] == "callback_delivery_unavailable"
    assert len(callbacks["incidents"]) == 2


@pytest.mark.parametrize(
    "message",
    [
        "provider_payload_timeout",
        "raw_score_available",
        "restricted_evidence_found",
        "internal_endpoint_down",
        "https://internal.local/service",
    ],
)
def test_customer_dashboard_blocks_sensitive_free_text_in_operational_impacts(
    message: str,
) -> None:
    with pytest.raises(CustomerDashboardPrivacyError):
        CustomerDashboardOperationalImpact(
            tenant_id="tenant-alpha",
            component="api",
            status=OperationalImpactStatus.DEGRADED,
            message=message,
        )


def test_customer_dashboard_rejects_invalid_incident_timestamps() -> None:
    now = _utc_now()

    with pytest.raises(CustomerDashboardPrivacyError):
        CustomerDashboardIncident(
            incident_ref="incident-callbacks-001",
            status=OperationalImpactStatus.DEGRADED,
            impact="callback_delivery_delayed",
            started_at=datetime.now(),
        )

    with pytest.raises(CustomerDashboardPrivacyError):
        CustomerDashboardIncident(
            incident_ref="incident-callbacks-002",
            status=OperationalImpactStatus.DEGRADED,
            impact="callback_delivery_delayed",
            started_at=now,
            ended_at=now - timedelta(seconds=1),
        )


def test_customer_dashboard_sections_are_deeply_immutable() -> None:
    repository = projection_repositories.InMemoryBusinessProjectionRepository()
    reporting_service = _reporting_service(repository)
    reporting_service.record_event(_proposal_event(tenant_id="tenant-alpha"))
    dashboard = CustomerDashboardService(repository=repository).build_dashboard(
        context=CustomerDashboardAccessContext(
            tenant_id="tenant-alpha",
            scopes=frozenset({"dashboard:read"}),
        )
    )
    cost_cards = cast("Any", dashboard.sections["costs"]["cards"])

    with pytest.raises(TypeError):
        cost_cards["actual_cost_units"] = {"value": "secret"}


def test_customer_dashboard_rejects_malformed_scopes_safely() -> None:
    with pytest.raises(CustomerDashboardAuthorizationError) as none_error:
        CustomerDashboardAccessContext(
            tenant_id="tenant-alpha",
            scopes=cast("Any", None),
        )
    with pytest.raises(CustomerDashboardAuthorizationError) as item_error:
        CustomerDashboardAccessContext(
            tenant_id="tenant-alpha",
            scopes=cast("Any", frozenset({object()})),
        )

    assert none_error.value.code == "customer_dashboard_invalid_scope_collection"
    assert item_error.value.code == "customer_dashboard_invalid_scope"


def test_customer_dashboard_preserves_missing_integration_latency_as_none() -> None:
    repository = projection_repositories.InMemoryBusinessProjectionRepository()
    reporting_service = _reporting_service(repository)
    reporting_service.record_event(
        BusinessEvent.integration(
            event_id="evt-integration-no-latency",
            source="integration",
            tenant_id="tenant-alpha",
            product_type=ProductType.BNPL,
            occurred_at=_utc_now() - timedelta(seconds=10),
            processed_at=_utc_now(),
            channel=Channel.CHECKOUT,
            integration_class="credit_bureau",
            adapter_id="mock-bureau-v1",
            provider_id="iprv_mock_provider_v1",
            status=IntegrationStatus.SUCCEEDED,
            actual_cost_units=3,
        )
    )

    dashboard = CustomerDashboardService(repository=repository).build_dashboard(
        context=CustomerDashboardAccessContext(
            tenant_id="tenant-alpha",
            scopes=frozenset({"dashboard:read"}),
        )
    )

    assert (
        _sections(dashboard.to_dict())["integrations"]["cards"]["credit_bureau"][
            "average_latency_ms"
        ]
        is None
    )


def test_customer_dashboard_documentation_registers_required_limits() -> None:
    required_markers = {
        "services/reporting-insights/README.md": (
            "dashboard customer-facing curado",
            "prometheus, loki, tempo",
            "bmad-ux",
        ),
        "docs/observability.md": (
            "dashboards customer-facing curados",
            "tenant não pode vir de payload livre",
            "bmad-ux",
        ),
        "docs/observability-dashboards.md": (
            "visão customer-facing curada",
            "não é um dashboard grafana",
            "bmad-ux",
        ),
    }

    for path, markers in required_markers.items():
        content = _repo_file(path).lower()
        for marker in markers:
            assert marker in content


class _FailingRepository:
    def apply_once(
        self,
        event: BusinessEvent,
        *,
        processed_at: datetime,
    ) -> BusinessProjectionApplyResult:
        raise AssertionError("repository must not be used by dashboard tests")

    def list_by_tenant(self, *, tenant_id: str) -> tuple[BusinessMetricsProjection, ...]:
        raise AssertionError("authorization should fail before repository access")


class _CrossTenantRepository:
    def apply_once(
        self,
        event: BusinessEvent,
        *,
        processed_at: datetime,
    ) -> BusinessProjectionApplyResult:
        raise AssertionError("repository mutation must not be used by dashboard tests")

    def list_by_tenant(self, *, tenant_id: str) -> tuple[BusinessMetricsProjection, ...]:
        return (
            BusinessMetricsProjection.empty(
                ProjectionKey(
                    tenant_id="tenant-beta",
                    tenant_isolation_tier=TenantIsolationTier.BRIDGE,
                    product_type=ProductType.BNPL,
                    period="2026-09-29",
                    channel=Channel.CHECKOUT,
                )
            ),
        )


def _record_complete_flow(
    service: ReportingInsightsService,
    *,
    tenant_id: str,
    occurred_at: datetime,
) -> None:
    processed_at = occurred_at + timedelta(seconds=10)
    service.record_event(
        _proposal_event(
            event_id="evt-proposal-alpha",
            tenant_id=tenant_id,
            idempotency_key="idem-proposal-alpha",
            occurred_at=occurred_at,
            processed_at=processed_at,
            funnel_status=ProposalFunnelStatus.RECEIVED,
        )
    )
    service.record_event(
        BusinessEvent.decision(
            event_id="evt-decision-alpha",
            source="decision",
            tenant_id=tenant_id,
            product_type=ProductType.BNPL,
            occurred_at=occurred_at + timedelta(seconds=2),
            processed_at=processed_at + timedelta(seconds=2),
            channel=Channel.CHECKOUT,
            outcome=DecisionOutcome.APPROVED_WITH_CHANGES,
            reason_codes=("policy_income_band",),
            idempotency_key="idem-decision-alpha",
        )
    )
    service.record_event(
        BusinessEvent.integration(
            event_id="evt-integration-alpha",
            source="integration",
            tenant_id=tenant_id,
            product_type=ProductType.BNPL,
            occurred_at=occurred_at + timedelta(seconds=3),
            processed_at=processed_at + timedelta(seconds=3),
            channel=Channel.CHECKOUT,
            integration_class="credit_bureau",
            adapter_id="mock-bureau-v1",
            provider_id="iprv_mock_provider_v1",
            status=IntegrationStatus.SUCCEEDED,
            actual_cost_units=18,
            estimated_cost_units=20,
            latency_ms=120,
        )
    )
    service.record_event(
        BusinessEvent.ai_review(
            event_id="evt-review-alpha",
            source="automated-review",
            tenant_id=tenant_id,
            product_type=ProductType.BNPL,
            occurred_at=occurred_at + timedelta(seconds=4),
            processed_at=processed_at + timedelta(seconds=4),
            channel=Channel.CHECKOUT,
            status=ReviewStatus.COMPLETED,
            actual_cost_units=7,
            latency_ms=90,
        )
    )
    service.record_event(
        BusinessEvent.callback(
            event_id="evt-callback-alpha",
            source="callback-dispatcher",
            tenant_id=tenant_id,
            product_type=ProductType.BNPL,
            occurred_at=occurred_at + timedelta(seconds=5),
            processed_at=processed_at + timedelta(seconds=5),
            channel=Channel.CHECKOUT,
            status=CallbackStatus.DELIVERED,
            latency_ms=40,
        )
    )


def _proposal_event(
    *,
    event_id: str = "evt-proposal-001",
    tenant_id: str = "tenant-alpha",
    idempotency_key: str = "idem-proposal-001",
    occurred_at: datetime | None = None,
    processed_at: datetime | None = None,
    funnel_status: ProposalFunnelStatus = ProposalFunnelStatus.RECEIVED,
) -> BusinessEvent:
    event_time = occurred_at or _utc_now() - timedelta(seconds=10)
    processing_time = processed_at or event_time + timedelta(seconds=1)
    return BusinessEvent.proposal(
        event_id=event_id,
        source="proposal-intake",
        tenant_id=tenant_id,
        product_type=ProductType.BNPL,
        occurred_at=event_time,
        processed_at=processing_time,
        channel=Channel.CHECKOUT,
        funnel_status=funnel_status,
        idempotency_key=idempotency_key,
    )


def _reporting_service(
    repository: projection_repositories.InMemoryBusinessProjectionRepository,
) -> ReportingInsightsService:
    return ReportingInsightsService(
        repository=repository,
        processed_at_factory=_utc_now,
    )


def _forbidden_terms() -> set[str]:
    return {
        "cpf",
        "cnpj",
        "email",
        "payload",
        "provider_payload",
        "token",
        "secret",
        "trace_id",
        "correlation_id",
        "request_id",
        "proposal_id",
        "decision_id",
        "raw_log",
        "raw_trace",
        "prometheus",
        "loki",
        "tempo",
    }


def _sections(payload: dict[str, object]) -> dict[str, Any]:
    return cast("dict[str, Any]", payload["sections"])


def _repo_file(path: str) -> str:
    return (Path(__file__).resolve().parents[4] / path).read_text(encoding="utf-8")


def _utc_now() -> datetime:
    return datetime.now(UTC)
