from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from creditos_observability.context import ObservabilityContext
from creditos_observability.logging import build_structured_log

from creditos_reporting_insights.application.ports.business_projection_repository import (
    BusinessProjectionRepository,
)
from creditos_reporting_insights.domain.entities.business_metrics_projection import (
    BusinessMetricsSnapshot,
)
from creditos_reporting_insights.domain.errors import BusinessProjectionNotFoundError
from creditos_reporting_insights.domain.value_objects.business_events import BusinessEvent


@dataclass(frozen=True, slots=True)
class ProjectionUpdateResult:
    snapshot: BusinessMetricsSnapshot
    applied: bool
    duplicate: bool
    late_event: bool


class ReportingInsightsService:
    def __init__(
        self,
        *,
        repository: BusinessProjectionRepository,
        service_version: str = "0.1.0",
        environment: str = "local",
        processed_at_factory: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._service_version = service_version
        self._environment = environment
        self._processed_at_factory = processed_at_factory or (lambda: datetime.now(UTC))

    def record_event(self, event: BusinessEvent) -> ProjectionUpdateResult:
        applied = self._repository.apply_once(
            event,
            processed_at=self._safe_processed_at(event),
        )
        return ProjectionUpdateResult(
            snapshot=applied.projection.snapshot(),
            applied=applied.applied,
            duplicate=applied.duplicate,
            late_event=applied.late_event,
        )

    def list_tenant_snapshots(self, *, tenant_id: str) -> tuple[BusinessMetricsSnapshot, ...]:
        snapshots = tuple(
            projection.snapshot()
            for projection in self._repository.list_by_tenant(tenant_id=tenant_id)
        )
        if not snapshots:
            raise BusinessProjectionNotFoundError(field_path="tenant_id")
        return snapshots

    def build_projection_log(
        self,
        *,
        context: ObservabilityContext,
        result: ProjectionUpdateResult,
    ) -> dict[str, object]:
        return build_structured_log(
            context=context,
            service_name="reporting-insights",
            service_version=self._service_version,
            environment=self._environment,
            operation="business_projection_record_event",
            source="authorized_business_event",
            destination="reporting_read_model",
            contract="internal_business_event_projection",
            contract_version="v1",
            status="ok" if result.applied else "duplicate",
            duration_ms=0.0,
            technical_result="business_projection_updated"
            if result.applied
            else "duplicate_ignored",
            extra={
                "applied": result.applied,
                "duplicate": result.duplicate,
                "late_event": result.late_event,
                "product_type": result.snapshot.key.product_type.value,
                "period": result.snapshot.key.period,
                "freshness_status": result.snapshot.freshness.status,
            },
        )

    def _safe_processed_at(self, event: BusinessEvent) -> datetime:
        processed_at = self._processed_at_factory().astimezone(UTC)
        occurred_at = event.occurred_at.astimezone(UTC)
        if processed_at < occurred_at:
            return occurred_at
        return processed_at
