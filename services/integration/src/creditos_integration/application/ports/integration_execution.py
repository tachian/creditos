from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import Any, Protocol

from creditos_observability.context import ObservabilityContext

from creditos_integration.application.ports.mock_integration_adapter import MockIntegrationAdapter
from creditos_integration.domain.entities import (
    IntegrationExecution,
    IntegrationExecutionJob,
    IntegrationPlanItem,
    IntegrationResult,
)


@dataclass(frozen=True, slots=True)
class IntegrationExecutionJobRequest:
    job_id: str
    item: IntegrationPlanItem
    scenario: str
    adapter: MockIntegrationAdapter
    event_type: str = "creditos.integration.job.requested.v1"
    schema_version: str = "1.0"


@dataclass(frozen=True, slots=True)
class IntegrationExecutionDispatchResult:
    jobs: tuple[IntegrationExecutionJob, ...]
    results: tuple[IntegrationResult, ...]
    max_observed_concurrency: int


class IntegrationExecutionDispatcher(Protocol):
    def dispatch(
        self,
        *,
        execution_id: str,
        job_requests: tuple[IntegrationExecutionJobRequest, ...],
        synthetic_subject_reference: str,
        context: ObservabilityContext,
        clock: Callable[[], datetime],
    ) -> IntegrationExecutionDispatchResult: ...


class IntegrationExecutionStore(Protocol):
    def reserve_or_get(
        self,
        *,
        tenant_id: str,
        idempotency_key: str,
        plan_fingerprint: str,
    ) -> IntegrationExecution | None: ...

    def save(self, execution: IntegrationExecution) -> None: ...

    def release_reservation(
        self,
        *,
        tenant_id: str,
        idempotency_key: str,
        plan_fingerprint: str,
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class IntegrationExecutionEvent:
    specversion: str
    id: str
    type: str
    source: str
    subject: str
    time: str
    datacontenttype: str
    tenant_id: str
    correlation_id: str
    trace_id: str
    schema_version: str
    data: MappingProxyType[str, Any]

    def to_log_safe_dict(self) -> dict[str, object]:
        return {
            "specversion": self.specversion,
            "id": self.id,
            "type": self.type,
            "source": self.source,
            "subject": self.subject,
            "time": self.time,
            "datacontenttype": self.datacontenttype,
            "tenant_id": self.tenant_id,
            "correlation_id": self.correlation_id,
            "trace_id": self.trace_id,
            "schema_version": self.schema_version,
            "data": dict(self.data),
        }


class IntegrationExecutionResultPublisher(Protocol):
    def publish(self, event: IntegrationExecutionEvent) -> None: ...
