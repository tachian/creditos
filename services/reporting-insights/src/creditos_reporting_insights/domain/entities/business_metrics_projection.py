from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import MappingProxyType

from creditos_reporting_insights.domain.errors import BusinessProjectionTenantError
from creditos_reporting_insights.domain.value_objects.business_events import (
    BusinessEvent,
    BusinessEventType,
    CallbackStatus,
    Channel,
    DecisionOutcome,
    IntegrationStatus,
    ProductType,
    ProposalFunnelStatus,
    ReviewStatus,
    TenantIsolationTier,
)

_FRESHNESS_TARGET_SECONDS = 300


@dataclass(frozen=True, slots=True)
class ProjectionKey:
    tenant_id: str
    tenant_isolation_tier: TenantIsolationTier
    product_type: ProductType
    period: str
    channel: Channel | None = None

    @classmethod
    def from_event(cls, event: BusinessEvent) -> ProjectionKey:
        return cls(
            tenant_id=event.tenant_id,
            tenant_isolation_tier=event.tenant_isolation_tier,
            product_type=event.product_type,
            period=event.period,
            channel=event.channel,
        )


@dataclass(frozen=True, slots=True)
class FreshnessSnapshot:
    last_event_time: datetime | None
    last_processed_at: datetime | None
    lag_seconds: int | None
    status: str


@dataclass(frozen=True, slots=True)
class BusinessMetricsSnapshot:
    key: ProjectionKey
    funnel_counts: MappingProxyType[str, int]
    decision_counts: MappingProxyType[str, int]
    reason_code_counts: MappingProxyType[str, int]
    integration_counts: MappingProxyType[str, int]
    integration_estimated_cost_units: MappingProxyType[str, int]
    integration_actual_cost_units: MappingProxyType[str, int]
    integration_total_latency_ms: MappingProxyType[str, int]
    integration_latency_event_counts: MappingProxyType[str, int]
    integration_error_counts: MappingProxyType[str, int]
    review_counts: MappingProxyType[str, int]
    callback_counts: MappingProxyType[str, int]
    estimated_cost_units: int
    actual_cost_units: int
    total_latency_ms: int
    latency_event_count: int
    error_count: int
    late_event_count: int
    freshness: FreshnessSnapshot


@dataclass(slots=True)
class BusinessMetricsProjection:
    key: ProjectionKey
    funnel_counts: dict[str, int] = field(default_factory=dict)
    decision_counts: dict[str, int] = field(default_factory=dict)
    reason_code_counts: dict[str, int] = field(default_factory=dict)
    integration_counts: dict[str, int] = field(default_factory=dict)
    integration_estimated_cost_units: dict[str, int] = field(default_factory=dict)
    integration_actual_cost_units: dict[str, int] = field(default_factory=dict)
    integration_total_latency_ms: dict[str, int] = field(default_factory=dict)
    integration_latency_event_counts: dict[str, int] = field(default_factory=dict)
    integration_error_counts: dict[str, int] = field(default_factory=dict)
    review_counts: dict[str, int] = field(default_factory=dict)
    callback_counts: dict[str, int] = field(default_factory=dict)
    estimated_cost_units: int = 0
    actual_cost_units: int = 0
    total_latency_ms: int = 0
    latency_event_count: int = 0
    error_count: int = 0
    late_event_count: int = 0
    last_event_time: datetime | None = None
    last_processed_at: datetime | None = None

    @classmethod
    def empty(cls, key: ProjectionKey) -> BusinessMetricsProjection:
        return cls(key=key)

    def apply(self, event: BusinessEvent, *, processed_at: datetime | None = None) -> None:
        self._ensure_same_projection(event)
        if self.last_event_time is not None and event.occurred_at < self.last_event_time:
            self.late_event_count += 1

        if event.event_type is BusinessEventType.PROPOSAL:
            self._increment_funnel(event.funnel_status)
        elif event.event_type is BusinessEventType.DECISION:
            self._increment_funnel(ProposalFunnelStatus.DECIDED)
            self._increment_funnel(event.funnel_status)
            self._increment_decision(event.decision_outcome)
            for reason_code in event.reason_codes:
                self._increment(self.reason_code_counts, reason_code)
        elif event.event_type is BusinessEventType.INTEGRATION:
            self._increment_integration(event)
        elif event.event_type is BusinessEventType.AI_REVIEW:
            self._increment_review(event.review_status)
        elif event.event_type is BusinessEventType.CALLBACK:
            self._increment_callback(event.callback_status)

        self.estimated_cost_units += event.estimated_cost_units
        self.actual_cost_units += event.actual_cost_units
        self.error_count += event.error_count
        if event.latency_ms is not None:
            self.total_latency_ms += event.latency_ms
            self.latency_event_count += 1

        self.last_event_time = _max_datetime(self.last_event_time, event.occurred_at)
        self.last_processed_at = _max_datetime(
            self.last_processed_at,
            processed_at or event.processed_at,
        )

    def snapshot(self) -> BusinessMetricsSnapshot:
        return BusinessMetricsSnapshot(
            key=self.key,
            funnel_counts=MappingProxyType(dict(self.funnel_counts)),
            decision_counts=MappingProxyType(dict(self.decision_counts)),
            reason_code_counts=MappingProxyType(dict(self.reason_code_counts)),
            integration_counts=MappingProxyType(dict(self.integration_counts)),
            integration_estimated_cost_units=MappingProxyType(
                dict(self.integration_estimated_cost_units)
            ),
            integration_actual_cost_units=MappingProxyType(
                dict(self.integration_actual_cost_units)
            ),
            integration_total_latency_ms=MappingProxyType(dict(self.integration_total_latency_ms)),
            integration_latency_event_counts=MappingProxyType(
                dict(self.integration_latency_event_counts)
            ),
            integration_error_counts=MappingProxyType(dict(self.integration_error_counts)),
            review_counts=MappingProxyType(dict(self.review_counts)),
            callback_counts=MappingProxyType(dict(self.callback_counts)),
            estimated_cost_units=self.estimated_cost_units,
            actual_cost_units=self.actual_cost_units,
            total_latency_ms=self.total_latency_ms,
            latency_event_count=self.latency_event_count,
            error_count=self.error_count,
            late_event_count=self.late_event_count,
            freshness=self._freshness(),
        )

    def _ensure_same_projection(self, event: BusinessEvent) -> None:
        event_key = ProjectionKey.from_event(event)
        if event_key != self.key:
            raise BusinessProjectionTenantError(
                code="business_projection_key_mismatch",
                field_path="tenant_id",
            )

    def _increment_funnel(self, status: ProposalFunnelStatus | None) -> None:
        if status is not None:
            self._increment(self.funnel_counts, status.value)

    def _increment_decision(self, outcome: DecisionOutcome | None) -> None:
        if outcome is not None:
            self._increment(self.decision_counts, outcome.value)

    def _increment_review(self, status: ReviewStatus | None) -> None:
        if status is not None:
            self._increment(self.review_counts, status.value)

    def _increment_callback(self, status: CallbackStatus | None) -> None:
        if status is not None:
            self._increment(self.callback_counts, status.value)

    def _increment_integration(self, event: BusinessEvent) -> None:
        if event.integration_status is None:
            return
        key_parts = [
            event.integration_class or "unknown",
            event.adapter_id or "unknown",
            event.provider_id or "none",
        ]
        dimension_key = "|".join(key_parts)
        status_key = f"{dimension_key}|{event.integration_status.value}"
        self._increment(self.integration_counts, status_key)
        self._add(
            self.integration_estimated_cost_units,
            dimension_key,
            event.estimated_cost_units,
        )
        self._add(self.integration_actual_cost_units, dimension_key, event.actual_cost_units)
        self._add(self.integration_error_counts, dimension_key, event.error_count)
        if event.latency_ms is not None:
            self._add(self.integration_total_latency_ms, dimension_key, event.latency_ms)
            self._increment(self.integration_latency_event_counts, dimension_key)
        if event.integration_status is IntegrationStatus.SUCCEEDED:
            self._increment_funnel(ProposalFunnelStatus.ENRICHED)

    def _freshness(self) -> FreshnessSnapshot:
        if self.last_event_time is None or self.last_processed_at is None:
            return FreshnessSnapshot(
                last_event_time=None,
                last_processed_at=None,
                lag_seconds=None,
                status="empty",
            )
        last_event_time = self.last_event_time.astimezone(UTC)
        last_processed_at = self.last_processed_at.astimezone(UTC)
        lag_seconds = max(0, int((last_processed_at - last_event_time).total_seconds()))
        status = "fresh" if lag_seconds <= _FRESHNESS_TARGET_SECONDS else "stale"
        return FreshnessSnapshot(
            last_event_time=last_event_time,
            last_processed_at=last_processed_at,
            lag_seconds=lag_seconds,
            status=status,
        )

    @staticmethod
    def _increment(counter: dict[str, int], key: str) -> None:
        counter[key] = counter.get(key, 0) + 1

    @staticmethod
    def _add(counter: dict[str, int], key: str, value: int) -> None:
        counter[key] = counter.get(key, 0) + value


def _max_datetime(current: datetime | None, candidate: datetime) -> datetime:
    normalized_candidate = candidate.astimezone(UTC)
    if current is None:
        return normalized_candidate
    return max(current.astimezone(UTC), normalized_candidate)
