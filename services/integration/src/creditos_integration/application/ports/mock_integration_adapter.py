from __future__ import annotations

from datetime import datetime
from typing import Protocol

from creditos_observability.context import ObservabilityContext

from creditos_integration.domain.entities import IntegrationPlanItem, IntegrationResult


class MockIntegrationAdapter(Protocol):
    def execute(
        self,
        item: IntegrationPlanItem,
        *,
        scenario: str,
        synthetic_subject_reference: str,
        context: ObservabilityContext,
        started_at: datetime,
        completed_at: datetime,
        duration_ms: float,
    ) -> IntegrationResult: ...


class MockIntegrationAdapterRegistry(Protocol):
    def get_adapter(
        self,
        integration_class: str,
        adapter_id: str,
    ) -> MockIntegrationAdapter | None: ...
