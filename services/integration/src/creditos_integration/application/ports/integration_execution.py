from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import Any, Protocol

from creditos_observability.context import ObservabilityContext

from creditos_integration.application.ports.mock_integration_adapter import MockIntegrationAdapter
from creditos_integration.domain.entities import (
    IntegrationExecution,
    IntegrationExecutionCostRecord,
    IntegrationExecutionDlqRecord,
    IntegrationExecutionJob,
    IntegrationPlanItem,
    IntegrationResult,
)

_EVENT_ID_PATTERN = re.compile(r"^evt_[a-f0-9]{32}$")
_TRACE_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")

INTEGRATION_RESILIENCE_EVENT_TYPES = MappingProxyType(
    {
        "retry_scheduled": "creditos.integration.job.retry_scheduled.v1",
        "dlq_recorded": "creditos.integration.job.dlq_recorded.v1",
        "reprocess_requested": "creditos.integration.job.reprocess_requested.v1",
        "reprocessed": "creditos.integration.job.reprocessed.v1",
    }
)

JETSTREAM_RESILIENCE_MAPPING = MappingProxyType(
    {
        "ack_policy": "explicit",
        "ack_wait_source": "integration_plan_item.timeout_ms",
        "max_deliver_source": "integration_plan_item.max_attempts",
        "backoff_source": "integration_retry_policy.backoff_ms",
        "max_deliver_advisory": "$JS.EVENT.ADVISORY.CONSUMER.MAX_DELIVERIES.{stream}.{consumer}",
        "poison_message_action": "term_and_record_dlq",
    }
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
    cost_records: tuple[IntegrationExecutionCostRecord, ...]
    retry_schedules: tuple[IntegrationExecutionRetrySchedule, ...] = ()
    dlq_records: tuple[IntegrationExecutionDlqRecord, ...] = ()


@dataclass(frozen=True, slots=True)
class IntegrationRetryEvaluation:
    decision: str
    failure_class: str
    failure_code: str
    attempt_count: int
    max_attempts: int
    backoff_ms: int
    jitter_ms: int
    retry_delay_ms: int


@dataclass(frozen=True, slots=True)
class IntegrationExecutionRetrySchedule:
    execution_id: str
    job_id: str
    tenant_id: str
    product_type: str
    integration_class: str
    adapter_id: str
    failure_class: str
    failure_code: str
    attempt_count: int
    next_attempt_count: int
    backoff_ms: int
    jitter_ms: int
    retry_delay_ms: int
    schema_version: str
    correlation_id: str
    trace_id: str
    scheduled_at: str

    def to_log_safe_dict(self) -> dict[str, object]:
        return {
            "execution_id": self.execution_id,
            "job_id": self.job_id,
            "tenant_id": self.tenant_id,
            "product_type": self.product_type,
            "integration_class": self.integration_class,
            "adapter_id": self.adapter_id,
            "failure_class": self.failure_class,
            "failure_code": self.failure_code,
            "attempt_count": self.attempt_count,
            "next_attempt_count": self.next_attempt_count,
            "backoff_ms": self.backoff_ms,
            "jitter_ms": self.jitter_ms,
            "retry_delay_ms": self.retry_delay_ms,
            "schema_version": self.schema_version,
            "correlation_id": self.correlation_id,
            "trace_id": self.trace_id,
            "scheduled_at": self.scheduled_at,
        }


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

    def get_by_execution_id(
        self,
        *,
        tenant_id: str,
        execution_id: str,
    ) -> IntegrationExecution | None: ...

    def release_reservation(
        self,
        *,
        tenant_id: str,
        idempotency_key: str,
        plan_fingerprint: str,
    ) -> None: ...

    def stage_execution_events(
        self,
        *,
        tenant_id: str,
        idempotency_key: str,
        events: tuple[IntegrationExecutionEvent, ...],
    ) -> None: ...

    def list_unpublished_execution_events(
        self,
        *,
        tenant_id: str,
        idempotency_key: str,
    ) -> tuple[IntegrationExecutionEvent, ...]: ...

    def mark_execution_event_published(
        self,
        *,
        tenant_id: str,
        idempotency_key: str,
        event_id: str,
    ) -> None: ...


class IntegrationRetryPolicy(Protocol):
    def evaluate(
        self,
        *,
        request: IntegrationExecutionJobRequest,
        attempt_count: int,
        failure_class: str,
        failure_code: str,
    ) -> IntegrationRetryEvaluation: ...


class IntegrationDlqStore(Protocol):
    def save(self, record: IntegrationExecutionDlqRecord) -> IntegrationExecutionDlqRecord: ...

    def get(
        self,
        *,
        tenant_id: str,
        dlq_id: str,
    ) -> IntegrationExecutionDlqRecord | None: ...

    def list_for_execution(
        self,
        *,
        tenant_id: str,
        execution_id: str,
    ) -> tuple[IntegrationExecutionDlqRecord, ...]: ...

    def mark_reprocessed(
        self,
        *,
        tenant_id: str,
        dlq_id: str,
        idempotency_key: str,
        reprocessed_at: datetime,
        reprocess_execution_id: str,
    ) -> IntegrationExecutionDlqRecord: ...


@dataclass(frozen=True, slots=True)
class IntegrationExecutionEvent:
    specversion: str
    id: str
    type: str
    source: str
    subject: str
    time: str
    datacontenttype: str
    dataschema: str
    tenant_id: str
    correlation_id: str
    trace_id: str
    schema_version: str
    data: MappingProxyType[str, Any]
    tenant_isolation_tier: str = "bridge"
    request_id: str = "missing-request-id"
    idempotency_key: str = "missing-idempotency-key"
    subject_id: str = "integration-service"
    client_id: str = "integration-service"
    principal_type: str = "platform"
    scopes: tuple[str, ...] = ("integration_execution:publish",)

    def __post_init__(self) -> None:
        for field_name in (
            "specversion",
            "id",
            "type",
            "source",
            "subject",
            "time",
            "datacontenttype",
            "dataschema",
            "tenant_id",
            "correlation_id",
            "trace_id",
            "schema_version",
            "tenant_isolation_tier",
            "request_id",
            "idempotency_key",
            "subject_id",
            "client_id",
            "principal_type",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value:
                raise ValueError(f"IntegrationExecutionEvent.{field_name} é obrigatório")
        if self.specversion != "1.0":
            raise ValueError("IntegrationExecutionEvent.specversion deve ser 1.0")
        if not _EVENT_ID_PATTERN.fullmatch(self.id):
            raise ValueError("IntegrationExecutionEvent.id inválido")
        if not _TRACE_ID_PATTERN.fullmatch(self.trace_id):
            raise ValueError("IntegrationExecutionEvent.trace_id inválido")
        if not self.scopes:
            raise ValueError("IntegrationExecutionEvent.scopes é obrigatório")

    def to_log_safe_dict(self) -> dict[str, object]:
        return {
            "specversion": self.specversion,
            "id": self.id,
            "type": self.type,
            "source": self.source,
            "subject": self.subject,
            "time": self.time,
            "datacontenttype": self.datacontenttype,
            "dataschema": self.dataschema,
            "tenant_id": self.tenant_id,
            "correlation_id": self.correlation_id,
            "trace_id": self.trace_id,
            "schema_version": self.schema_version,
            "tenant_isolation_tier": self.tenant_isolation_tier,
            "request_id": self.request_id,
            "idempotency_key": self.idempotency_key,
            "data_keys": tuple(sorted(str(key) for key in self.data)),
        }

    def to_cloudevent_dict(self) -> dict[str, object]:
        return {
            "specversion": self.specversion,
            "id": self.id,
            "source": self.source,
            "type": self.type,
            "subject": self.subject,
            "time": self.time,
            "datacontenttype": self.datacontenttype,
            "dataschema": self.dataschema,
            "tenantid": self.tenant_id,
            "tenanttier": self.tenant_isolation_tier,
            "subjectid": self.subject_id,
            "clientid": self.client_id,
            "principaltype": self.principal_type,
            "scopes": " ".join(self.scopes),
            "correlationid": self.correlation_id,
            "requestid": self.request_id,
            "idempotencykey": self.idempotency_key,
            "schemaversion": f"v{self.schema_version.split('.', maxsplit=1)[0]}",
            "traceparent": f"00-{self.trace_id}-0000000000000001-01",
            "data": dict(self.data),
        }


class IntegrationExecutionResultPublisher(Protocol):
    def publish(self, event: IntegrationExecutionEvent) -> None: ...
