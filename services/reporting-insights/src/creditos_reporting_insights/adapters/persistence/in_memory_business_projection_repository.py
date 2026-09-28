from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from threading import RLock

from creditos_reporting_insights.application.ports.business_projection_repository import (
    BusinessProjectionApplyResult,
    BusinessProjectionRepository,
)
from creditos_reporting_insights.domain.entities.business_metrics_projection import (
    BusinessMetricsProjection,
    ProjectionKey,
)
from creditos_reporting_insights.domain.errors import BusinessProjectionTenantError
from creditos_reporting_insights.domain.value_objects.business_events import (
    BusinessEvent,
    DeduplicationKey,
)


@dataclass(frozen=True, slots=True)
class _ProcessedEventRecord:
    tenant_id: str
    projection_key: ProjectionKey


class InMemoryBusinessProjectionRepository(BusinessProjectionRepository):
    def __init__(self) -> None:
        self._projections: dict[ProjectionKey, BusinessMetricsProjection] = {}
        self._processed_event_records: dict[DeduplicationKey, _ProcessedEventRecord] = {}
        self._lock = RLock()

    def apply_once(
        self,
        event: BusinessEvent,
        *,
        processed_at: datetime,
    ) -> BusinessProjectionApplyResult:
        projection_key = ProjectionKey.from_event(event)
        with self._lock:
            duplicate_projection = self._duplicate_projection(event)
            if duplicate_projection is not None:
                return BusinessProjectionApplyResult(
                    projection=duplicate_projection,
                    applied=False,
                    duplicate=True,
                    late_event=(
                        duplicate_projection.last_event_time is not None
                        and event.occurred_at < duplicate_projection.last_event_time
                    ),
                )

            projection = self._get_or_create_locked(projection_key)
            was_late = (
                projection.last_event_time is not None
                and event.occurred_at < projection.last_event_time
            )
            projection.apply(event, processed_at=processed_at)
            record = _ProcessedEventRecord(
                tenant_id=event.tenant_id,
                projection_key=projection_key,
            )
            for key in event.deduplication_keys:
                self._processed_event_records[key] = record
            return BusinessProjectionApplyResult(
                projection=projection,
                applied=True,
                duplicate=False,
                late_event=was_late,
            )

    def list_by_tenant(self, *, tenant_id: str) -> tuple[BusinessMetricsProjection, ...]:
        with self._lock:
            return tuple(
                projection
                for projection in self._projections.values()
                if projection.key.tenant_id == tenant_id
            )

    def _get_or_create_locked(self, key: ProjectionKey) -> BusinessMetricsProjection:
        projection = self._projections.get(key)
        if projection is None:
            projection = BusinessMetricsProjection.empty(key)
            self._projections[key] = projection
        return projection

    def _duplicate_projection(self, event: BusinessEvent) -> BusinessMetricsProjection | None:
        for key in event.deduplication_keys:
            record = self._processed_event_records.get(key)
            if record is None:
                continue
            if record.tenant_id != event.tenant_id:
                raise BusinessProjectionTenantError(
                    code="business_event_deduplication_tenant_conflict",
                    field_path="tenant_id",
                )
            projection = self._projections.get(record.projection_key)
            if projection is not None:
                return projection
        return None
