from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from creditos_reporting_insights.domain.entities.business_metrics_projection import (
    BusinessMetricsProjection,
)
from creditos_reporting_insights.domain.value_objects.business_events import BusinessEvent


@dataclass(frozen=True, slots=True)
class BusinessProjectionApplyResult:
    projection: BusinessMetricsProjection
    applied: bool
    duplicate: bool
    late_event: bool


class BusinessProjectionRepository(Protocol):
    def apply_once(
        self,
        event: BusinessEvent,
        *,
        processed_at: datetime,
    ) -> BusinessProjectionApplyResult:
        raise NotImplementedError

    def list_by_tenant(self, *, tenant_id: str) -> tuple[BusinessMetricsProjection, ...]:
        raise NotImplementedError
