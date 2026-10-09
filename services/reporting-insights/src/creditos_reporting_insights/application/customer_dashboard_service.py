from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from types import MappingProxyType

from creditos_reporting_insights.application.ports.business_projection_repository import (
    BusinessProjectionRepository,
)
from creditos_reporting_insights.domain.entities.business_metrics_projection import (
    BusinessMetricsSnapshot,
)
from creditos_reporting_insights.domain.errors import (
    BusinessProjectionNotFoundError,
    BusinessProjectionTenantError,
)
from creditos_reporting_insights.domain.value_objects.customer_dashboard import (
    CustomerDashboardOperationalImpact,
    CustomerDashboardSnapshot,
    build_section,
    placeholder_operational_impact,
)
from creditos_reporting_insights.domain.value_objects.customer_dashboard_access import (
    CustomerDashboardAccessContext,
)


class CustomerDashboardService:
    def __init__(
        self,
        *,
        repository: BusinessProjectionRepository,
        operational_impacts: Iterable[CustomerDashboardOperationalImpact] = (),
    ) -> None:
        self._repository = repository
        self._operational_impacts = tuple(operational_impacts)

    def build_dashboard(
        self,
        *,
        context: CustomerDashboardAccessContext,
        requested_tenant_id: str | None = None,
    ) -> CustomerDashboardSnapshot:
        context.require_dashboard_read()
        if requested_tenant_id is not None and requested_tenant_id != context.tenant_id:
            raise BusinessProjectionTenantError(
                code="customer_dashboard_tenant_override_denied",
                field_path="tenant_id",
            )

        snapshots = tuple(
            projection.snapshot()
            for projection in self._repository.list_by_tenant(tenant_id=context.tenant_id)
        )
        if not snapshots:
            raise BusinessProjectionNotFoundError(field_path="tenant_id")
        _ensure_snapshot_tenant(snapshots, tenant_id=context.tenant_id)

        return CustomerDashboardSnapshot(
            tenant_ref=context.tenant_id,
            tenant_isolation_tier=_single_or_bridge(
                snapshot.key.tenant_isolation_tier.value for snapshot in snapshots
            ),
            product_types=tuple(
                sorted({snapshot.key.product_type.value for snapshot in snapshots})
            ),
            channels=tuple(
                sorted(
                    {
                        snapshot.key.channel.value
                        for snapshot in snapshots
                        if snapshot.key.channel is not None
                    }
                )
            ),
            periods=tuple(sorted({snapshot.key.period for snapshot in snapshots})),
            sections=MappingProxyType(
                {
                    "business_funnel": build_section(_funnel_cards(snapshots)),
                    "callbacks": build_section(
                        _count_cards(_sum_counts(snapshots, "callback_counts"))
                    ),
                    "costs": build_section(_cost_cards(snapshots)),
                    "decisions": build_section(
                        _count_cards(_sum_counts(snapshots, "decision_counts"))
                    ),
                    "decision_queries": build_section(
                        _count_cards(_sum_counts(snapshots, "decision_query_counts"))
                    ),
                    "errors": build_section(_error_cards(snapshots)),
                    "freshness": build_section(_freshness_cards(snapshots)),
                    "integrations": build_section(_integration_cards(snapshots)),
                    "latency": build_section(_latency_cards(snapshots)),
                    "operational_health": build_section(
                        _operational_health_cards(context.tenant_id, self._operational_impacts)
                    ),
                    "reason_codes": build_section(
                        _count_cards(_sum_counts(snapshots, "reason_code_counts"))
                    ),
                    "reviews": build_section(_count_cards(_sum_counts(snapshots, "review_counts"))),
                }
            ),
        )


def _sum_counts(
    snapshots: tuple[BusinessMetricsSnapshot, ...],
    attribute: str,
) -> dict[str, int]:
    totals: dict[str, int] = defaultdict(int)
    for snapshot in snapshots:
        counters = getattr(snapshot, attribute)
        for key, value in counters.items():
            totals[key] += value
    return dict(totals)


def _count_cards(counts: dict[str, int]) -> dict[str, dict[str, int]]:
    return {key: {"count": value} for key, value in sorted(counts.items())}


def _funnel_cards(
    snapshots: tuple[BusinessMetricsSnapshot, ...],
) -> dict[str, dict[str, int | None]]:
    counts = _sum_counts(snapshots, "funnel_counts")
    received = counts.get("received", 0)
    return {
        key: {
            "count": value,
            "rate_per_10k_received": _rate_per_10k(value, received),
        }
        for key, value in sorted(counts.items())
    }


def _integration_cards(
    snapshots: tuple[BusinessMetricsSnapshot, ...],
) -> dict[str, dict[str, int | None]]:
    cards: dict[str, dict[str, int | None]] = {}
    for snapshot in snapshots:
        for dimension_status, count in snapshot.integration_counts.items():
            dimension_parts = dimension_status.split("|")
            if len(dimension_parts) != 4:
                continue
            integration_class, _, _, status = dimension_parts
            card = cards.setdefault(
                integration_class,
                {
                    "requested": 0,
                    "succeeded": 0,
                    "failed": 0,
                    "timeout": 0,
                    "skipped": 0,
                    "actual_cost_units": 0,
                    "estimated_cost_units": 0,
                    "average_latency_ms": None,
                    "errors": 0,
                },
            )
            _add_card_int(card, status, count)

        for dimension, cost_units in snapshot.integration_actual_cost_units.items():
            integration_class = _integration_class_from_dimension(dimension)
            _add_card_int(
                cards.setdefault(integration_class, _empty_integration_card()),
                "actual_cost_units",
                cost_units,
            )
        for dimension, cost_units in snapshot.integration_estimated_cost_units.items():
            integration_class = _integration_class_from_dimension(dimension)
            _add_card_int(
                cards.setdefault(integration_class, _empty_integration_card()),
                "estimated_cost_units",
                cost_units,
            )
        for dimension, error_count in snapshot.integration_error_counts.items():
            integration_class = _integration_class_from_dimension(dimension)
            _add_card_int(
                cards.setdefault(integration_class, _empty_integration_card()),
                "errors",
                error_count,
            )

    for integration_class, card in cards.items():
        total_latency = 0
        latency_events = 0
        for snapshot in snapshots:
            for dimension, latency_ms in snapshot.integration_total_latency_ms.items():
                if _integration_class_from_dimension(dimension) == integration_class:
                    total_latency += latency_ms
            for dimension, event_count in snapshot.integration_latency_event_counts.items():
                if _integration_class_from_dimension(dimension) == integration_class:
                    latency_events += event_count
        card["average_latency_ms"] = _safe_average(total_latency, latency_events)

    return dict(sorted(cards.items()))


def _cost_cards(snapshots: tuple[BusinessMetricsSnapshot, ...]) -> dict[str, dict[str, int]]:
    return {
        "actual_cost_units": {"value": sum(snapshot.actual_cost_units for snapshot in snapshots)},
        "estimated_cost_units": {
            "value": sum(snapshot.estimated_cost_units for snapshot in snapshots)
        },
    }


def _latency_cards(
    snapshots: tuple[BusinessMetricsSnapshot, ...],
) -> dict[str, dict[str, int | None]]:
    total_latency = sum(snapshot.total_latency_ms for snapshot in snapshots)
    latency_events = sum(snapshot.latency_event_count for snapshot in snapshots)
    return {
        "average_latency_ms": {"value": _safe_average(total_latency, latency_events)},
        "latency_event_count": {"value": latency_events},
    }


def _error_cards(snapshots: tuple[BusinessMetricsSnapshot, ...]) -> dict[str, dict[str, int]]:
    return {
        "late_events": {"value": sum(snapshot.late_event_count for snapshot in snapshots)},
        "total_errors": {"value": sum(snapshot.error_count for snapshot in snapshots)},
    }


def _freshness_cards(
    snapshots: tuple[BusinessMetricsSnapshot, ...],
) -> dict[str, dict[str, int | str | None]]:
    lag_values = [
        snapshot.freshness.lag_seconds
        for snapshot in snapshots
        if snapshot.freshness.lag_seconds is not None
    ]
    statuses = {snapshot.freshness.status for snapshot in snapshots}
    if "stale" in statuses:
        status = "stale"
    elif "fresh" in statuses:
        status = "fresh"
    else:
        status = "empty"
    return {
        "freshness_status": {"value": status},
        "max_lag_seconds": {"value": max(lag_values) if lag_values else None},
    }


def _operational_health_cards(
    tenant_id: str,
    impacts: tuple[CustomerDashboardOperationalImpact, ...],
) -> dict[str, dict[str, object]]:
    cards = {
        component: placeholder_operational_impact(component).to_card()
        for component in ("api", "callbacks", "integrations")
    }
    grouped: dict[str, list[CustomerDashboardOperationalImpact]] = {}
    for impact in impacts:
        if impact.tenant_id == tenant_id:
            grouped.setdefault(impact.component, []).append(impact)
    for component, component_impacts in grouped.items():
        cards[component] = _merge_operational_impacts(component_impacts)
    return cards


def _ensure_snapshot_tenant(
    snapshots: tuple[BusinessMetricsSnapshot, ...],
    *,
    tenant_id: str,
) -> None:
    for snapshot in snapshots:
        if snapshot.key.tenant_id != tenant_id:
            raise BusinessProjectionTenantError(
                code="customer_dashboard_snapshot_tenant_mismatch",
                field_path="tenant_id",
            )


def _merge_operational_impacts(
    impacts: list[CustomerDashboardOperationalImpact],
) -> dict[str, object]:
    ordered_impacts = sorted(
        impacts,
        key=lambda impact: (
            _status_rank(impact.status.value),
            impact.component,
            impact.message,
        ),
        reverse=True,
    )
    selected = ordered_impacts[0]
    incidents = tuple(
        incident
        for impact in sorted(impacts, key=lambda item: (item.component, item.message))
        for incident in impact.incidents
    )
    return {
        "status": selected.status.value,
        "message": selected.message,
        "incidents": tuple(incident.to_dict() for incident in incidents),
    }


def _status_rank(status: str) -> int:
    return {
        "unknown": 0,
        "operational": 1,
        "degraded": 2,
        "unavailable": 3,
    }[status]


def _single_or_bridge(values: Iterable[str]) -> str:
    unique_values = tuple(sorted(set(values)))
    if len(unique_values) == 1:
        return unique_values[0]
    return "bridge"


def _rate_per_10k(numerator: int, denominator: int) -> int | None:
    if denominator <= 0:
        return None
    return (numerator * 10_000) // denominator


def _safe_average(total: int, count: int) -> int | None:
    if count <= 0:
        return None
    return total // count


def _integration_class_from_dimension(dimension: str) -> str:
    return dimension.split("|", maxsplit=1)[0]


def _add_card_int(card: dict[str, int | None], key: str, increment: int) -> None:
    current = card.get(key, 0)
    if current is None:
        current = 0
    card[key] = current + increment


def _empty_integration_card() -> dict[str, int | None]:
    return {
        "requested": 0,
        "succeeded": 0,
        "failed": 0,
        "timeout": 0,
        "skipped": 0,
        "actual_cost_units": 0,
        "estimated_cost_units": 0,
        "average_latency_ms": None,
        "errors": 0,
    }
