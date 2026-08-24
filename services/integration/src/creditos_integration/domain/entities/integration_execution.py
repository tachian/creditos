from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import isfinite

from creditos_integration.domain.entities.integration_plan import IntegrationPlanItem
from creditos_integration.domain.entities.integration_result import IntegrationResult
from creditos_integration.domain.errors import IntegrationValidationError
from creditos_integration.domain.value_objects.catalog import (
    parse_fallback_strategy,
    parse_product_type,
    parse_requirement,
    validate_adapter_id,
    validate_configuration_id,
    validate_estimated_cost_units,
    validate_max_attempts,
    validate_max_concurrency,
    validate_timeout_ms,
)
from creditos_integration.domain.value_objects.execution import (
    IntegrationExecutionJobStatus,
    IntegrationExecutionStatus,
    IntegrationFailureClass,
    parse_execution_status,
    parse_failure_class,
    parse_job_status,
    validate_attempt_count,
    validate_call_count,
    validate_dlq_id,
    validate_execution_id,
    validate_failure_code,
    validate_idempotency_key,
    validate_integration_cost_units,
    validate_job_id,
    validate_plan_fingerprint,
    validate_provider_id,
    validate_schema_version,
)
from creditos_integration.domain.value_objects.result import (
    IntegrationResultStatus,
    parse_result_status,
    validate_supported_mock_integration_class,
)


@dataclass(frozen=True, slots=True)
class IntegrationExecutionJob:
    job_id: str
    execution_id: str
    tenant_id: str
    product_type: str
    integration_class: str
    adapter_id: str
    configuration_id: str
    requirement: str
    timeout_ms: int
    max_attempts: int
    max_concurrency: int
    estimated_cost_units: int
    fallback_strategy: str
    status: str
    attempt_count: int
    result_id: str | None
    schema_version: str
    correlation_id: str
    trace_id: str
    provider_id: str | None = None

    @classmethod
    def create(
        cls,
        *,
        job_id: str,
        execution_id: str,
        item: IntegrationPlanItem,
        status: str,
        correlation_id: str,
        trace_id: str,
        attempt_count: int = 1,
        result_id: str | None = None,
        schema_version: str = "1.0",
    ) -> IntegrationExecutionJob:
        return cls(
            job_id=validate_job_id(job_id),
            execution_id=validate_execution_id(execution_id),
            tenant_id=item.tenant_id,
            product_type=parse_product_type(item.product_type),
            integration_class=validate_supported_mock_integration_class(item.integration_class),
            adapter_id=validate_adapter_id(item.adapter_id),
            configuration_id=validate_configuration_id(item.configuration_id),
            requirement=parse_requirement(item.requirement),
            timeout_ms=validate_timeout_ms(item.timeout_ms),
            max_attempts=validate_max_attempts(item.max_attempts),
            max_concurrency=validate_max_concurrency(item.max_concurrency),
            estimated_cost_units=validate_estimated_cost_units(item.estimated_cost_units),
            fallback_strategy=parse_fallback_strategy(item.fallback_strategy),
            status=parse_job_status(status),
            attempt_count=validate_attempt_count(attempt_count),
            result_id=result_id,
            schema_version=validate_schema_version(schema_version),
            correlation_id=correlation_id,
            trace_id=trace_id,
            provider_id=validate_provider_id(item.provider_id),
        )

    def with_result(
        self,
        result: IntegrationResult,
        *,
        status: str | None = None,
    ) -> IntegrationExecutionJob:
        return IntegrationExecutionJob.create(
            job_id=self.job_id,
            execution_id=self.execution_id,
            item=IntegrationPlanItem(
                tenant_id=self.tenant_id,
                product_type=self.product_type,
                integration_class=self.integration_class,
                adapter_id=self.adapter_id,
                requirement=self.requirement,
                timeout_ms=self.timeout_ms,
                max_attempts=self.max_attempts,
                max_concurrency=self.max_concurrency,
                estimated_cost_units=self.estimated_cost_units,
                fallback_strategy=self.fallback_strategy,
                configuration_id=self.configuration_id,
                provider_id=self.provider_id,
            ),
            status=status or _job_status_from_result(result),
            attempt_count=self.attempt_count,
            result_id=result.result_id,
            schema_version=self.schema_version,
            correlation_id=self.correlation_id,
            trace_id=self.trace_id,
        )

    def to_log_safe_dict(self) -> dict[str, object]:
        return {
            "job_id": self.job_id,
            "execution_id": self.execution_id,
            "tenant_id": self.tenant_id,
            "product_type": self.product_type,
            "integration_class": self.integration_class,
            "adapter_id": self.adapter_id,
            "configuration_id": self.configuration_id,
            "requirement": self.requirement,
            "timeout_ms": self.timeout_ms,
            "max_attempts": self.max_attempts,
            "max_concurrency": self.max_concurrency,
            "estimated_cost_units": self.estimated_cost_units,
            "fallback_strategy": self.fallback_strategy,
            "status": self.status,
            "attempt_count": self.attempt_count,
            "result_id": self.result_id,
            "schema_version": self.schema_version,
            "correlation_id": self.correlation_id,
            "trace_id": self.trace_id,
            "provider_id": self.provider_id,
        }


@dataclass(frozen=True, slots=True)
class IntegrationExecutionCostRecord:
    execution_id: str
    job_id: str
    tenant_id: str
    product_type: str
    integration_class: str
    adapter_id: str
    provider_id: str | None
    result_status: str
    call_count: int
    attempt_count: int
    fallback_strategy: str
    estimated_cost_units: int
    actual_cost_units: int
    schema_version: str
    correlation_id: str
    trace_id: str

    @classmethod
    def create(
        cls,
        *,
        execution_id: str,
        job_id: str,
        tenant_id: str,
        product_type: str,
        integration_class: str,
        adapter_id: str,
        provider_id: str | None,
        result_status: str,
        call_count: int,
        attempt_count: int,
        fallback_strategy: str,
        estimated_cost_units: int,
        actual_cost_units: int,
        correlation_id: str,
        trace_id: str,
        schema_version: str = "1.0",
    ) -> IntegrationExecutionCostRecord:
        return cls(
            execution_id=validate_execution_id(execution_id),
            job_id=validate_job_id(job_id),
            tenant_id=tenant_id,
            product_type=parse_product_type(product_type),
            integration_class=validate_supported_mock_integration_class(integration_class),
            adapter_id=validate_adapter_id(adapter_id),
            provider_id=validate_provider_id(provider_id),
            result_status=parse_result_status(result_status),
            call_count=validate_call_count(call_count),
            attempt_count=validate_attempt_count(attempt_count),
            fallback_strategy=parse_fallback_strategy(fallback_strategy),
            estimated_cost_units=validate_integration_cost_units(
                estimated_cost_units,
                field_path="estimated_cost_units",
            ),
            actual_cost_units=validate_integration_cost_units(
                actual_cost_units,
                field_path="actual_cost_units",
            ),
            schema_version=validate_schema_version(schema_version),
            correlation_id=correlation_id,
            trace_id=trace_id,
        )

    @classmethod
    def from_job_result(
        cls,
        *,
        job: IntegrationExecutionJob,
        result: IntegrationResult,
        provider_id: str | None = None,
        call_count: int | None = None,
        actual_cost_units: int | None = None,
    ) -> IntegrationExecutionCostRecord:
        _validate_cost_record_boundaries(job=job, result=result)
        effective_call_count = job.attempt_count if call_count is None else call_count
        effective_actual_cost_units = (
            job.estimated_cost_units * effective_call_count
            if actual_cost_units is None
            else actual_cost_units
        )
        return cls.create(
            execution_id=job.execution_id,
            job_id=job.job_id,
            tenant_id=job.tenant_id,
            product_type=job.product_type,
            integration_class=job.integration_class,
            adapter_id=job.adapter_id,
            provider_id=job.provider_id if provider_id is None else provider_id,
            result_status=result.status,
            call_count=effective_call_count,
            attempt_count=job.attempt_count,
            fallback_strategy=job.fallback_strategy,
            estimated_cost_units=job.estimated_cost_units,
            actual_cost_units=effective_actual_cost_units,
            schema_version=job.schema_version,
            correlation_id=job.correlation_id,
            trace_id=job.trace_id,
        )

    def to_log_safe_dict(self) -> dict[str, object]:
        return {
            "execution_id": self.execution_id,
            "job_id": self.job_id,
            "tenant_id": self.tenant_id,
            "product_type": self.product_type,
            "integration_class": self.integration_class,
            "adapter_id": self.adapter_id,
            "provider_id": self.provider_id,
            "result_status": self.result_status,
            "call_count": self.call_count,
            "attempt_count": self.attempt_count,
            "fallback_strategy": self.fallback_strategy,
            "estimated_cost_units": self.estimated_cost_units,
            "actual_cost_units": self.actual_cost_units,
            "schema_version": self.schema_version,
            "correlation_id": self.correlation_id,
            "trace_id": self.trace_id,
        }


@dataclass(frozen=True, slots=True)
class IntegrationExecutionDlqRecord:
    dlq_id: str
    execution_id: str
    job_id: str
    tenant_id: str
    product_type: str
    integration_class: str
    adapter_id: str
    failure_class: str
    failure_code: str
    attempt_count: int
    schema_version: str
    correlation_id: str
    trace_id: str
    created_at: datetime
    reprocess_count: int = 0
    last_reprocess_at: datetime | None = None
    reprocess_execution_ids: tuple[str, ...] = ()

    @classmethod
    def create(
        cls,
        *,
        dlq_id: str,
        execution_id: str,
        job_id: str,
        tenant_id: str,
        product_type: str,
        integration_class: str,
        adapter_id: str,
        failure_class: str,
        failure_code: str,
        attempt_count: int,
        correlation_id: str,
        trace_id: str,
        created_at: datetime,
        reprocess_count: int = 0,
        last_reprocess_at: datetime | None = None,
        reprocess_execution_ids: tuple[str, ...] = (),
        schema_version: str = "1.0",
    ) -> IntegrationExecutionDlqRecord:
        if reprocess_count < 0:
            raise IntegrationValidationError(
                "contador de reprocessamento inválido",
                code="invalid_integration_dlq_reprocess_count",
                field_path="reprocess_count",
            )
        if last_reprocess_at is not None and last_reprocess_at < created_at:
            raise IntegrationValidationError(
                "janela temporal de reprocessamento inválida",
                code="invalid_integration_dlq_reprocess_time_window",
                field_path="last_reprocess_at",
            )
        return cls(
            dlq_id=validate_dlq_id(dlq_id),
            execution_id=validate_execution_id(execution_id),
            job_id=validate_job_id(job_id),
            tenant_id=tenant_id,
            product_type=parse_product_type(product_type),
            integration_class=validate_supported_mock_integration_class(integration_class),
            adapter_id=validate_adapter_id(adapter_id),
            failure_class=parse_failure_class(failure_class),
            failure_code=validate_failure_code(failure_code),
            attempt_count=validate_attempt_count(attempt_count),
            schema_version=validate_schema_version(schema_version),
            correlation_id=correlation_id,
            trace_id=trace_id,
            created_at=created_at,
            reprocess_count=reprocess_count,
            last_reprocess_at=last_reprocess_at,
            reprocess_execution_ids=tuple(
                validate_execution_id(execution_id) for execution_id in reprocess_execution_ids
            ),
        )

    @classmethod
    def from_job(
        cls,
        *,
        dlq_id: str,
        job: IntegrationExecutionJob,
        failure_class: str,
        failure_code: str,
        created_at: datetime,
    ) -> IntegrationExecutionDlqRecord:
        return cls.create(
            dlq_id=dlq_id,
            execution_id=job.execution_id,
            job_id=job.job_id,
            tenant_id=job.tenant_id,
            product_type=job.product_type,
            integration_class=job.integration_class,
            adapter_id=job.adapter_id,
            failure_class=failure_class,
            failure_code=failure_code,
            attempt_count=job.attempt_count,
            schema_version=job.schema_version,
            correlation_id=job.correlation_id,
            trace_id=job.trace_id,
            created_at=created_at,
        )

    def mark_reprocessed(
        self,
        *,
        reprocessed_at: datetime,
        reprocess_execution_id: str,
    ) -> IntegrationExecutionDlqRecord:
        return IntegrationExecutionDlqRecord.create(
            dlq_id=self.dlq_id,
            execution_id=self.execution_id,
            job_id=self.job_id,
            tenant_id=self.tenant_id,
            product_type=self.product_type,
            integration_class=self.integration_class,
            adapter_id=self.adapter_id,
            failure_class=self.failure_class,
            failure_code=self.failure_code,
            attempt_count=self.attempt_count,
            schema_version=self.schema_version,
            correlation_id=self.correlation_id,
            trace_id=self.trace_id,
            created_at=self.created_at,
            reprocess_count=self.reprocess_count + 1,
            last_reprocess_at=reprocessed_at,
            reprocess_execution_ids=(
                *self.reprocess_execution_ids,
                validate_execution_id(reprocess_execution_id),
            ),
        )

    @property
    def is_retryable_failure(self) -> bool:
        return self.failure_class in {
            IntegrationFailureClass.RECOVERABLE.value,
            IntegrationFailureClass.TIMEOUT.value,
        }

    def to_log_safe_dict(self) -> dict[str, object]:
        return {
            "dlq_id": self.dlq_id,
            "execution_id": self.execution_id,
            "job_id": self.job_id,
            "tenant_id": self.tenant_id,
            "product_type": self.product_type,
            "integration_class": self.integration_class,
            "adapter_id": self.adapter_id,
            "failure_class": self.failure_class,
            "failure_code": self.failure_code,
            "attempt_count": self.attempt_count,
            "schema_version": self.schema_version,
            "correlation_id": self.correlation_id,
            "trace_id": self.trace_id,
            "created_at": self.created_at.isoformat(),
            "reprocess_count": self.reprocess_count,
            "last_reprocess_at": self.last_reprocess_at.isoformat()
            if self.last_reprocess_at is not None
            else None,
            "reprocess_execution_ids": self.reprocess_execution_ids,
        }


@dataclass(frozen=True, slots=True)
class IntegrationExecution:
    execution_id: str
    tenant_id: str
    product_type: str
    plan_fingerprint: str
    idempotency_key: str
    status: str
    schema_version: str
    jobs: tuple[IntegrationExecutionJob, ...]
    results: tuple[IntegrationResult, ...]
    correlation_id: str
    trace_id: str
    started_at: datetime
    completed_at: datetime
    duration_ms: float

    @classmethod
    def create(
        cls,
        *,
        execution_id: str,
        tenant_id: str,
        product_type: str,
        plan_fingerprint: str,
        idempotency_key: str,
        jobs: tuple[IntegrationExecutionJob, ...],
        results: tuple[IntegrationResult, ...],
        correlation_id: str,
        trace_id: str,
        started_at: datetime,
        completed_at: datetime,
        duration_ms: float,
        status: str | None = None,
        schema_version: str = "1.0",
    ) -> IntegrationExecution:
        if not jobs:
            raise IntegrationValidationError(
                "execução de integração sem jobs",
                code="empty_integration_execution_jobs",
                field_path="jobs",
            )
        if not isfinite(duration_ms) or duration_ms < 0:
            raise IntegrationValidationError(
                "duração da execução de integração inválida",
                code="invalid_integration_execution_duration",
                field_path="duration_ms",
            )
        if completed_at < started_at:
            raise IntegrationValidationError(
                "janela temporal de execução de integração inválida",
                code="invalid_integration_execution_time_window",
                field_path="completed_at",
            )
        product_type = parse_product_type(product_type)
        execution_status = parse_execution_status(status or _execution_status_from_jobs(jobs))
        for job in jobs:
            if job.execution_id != execution_id:
                raise IntegrationValidationError(
                    "job pertence a outra execução",
                    code="cross_execution_job",
                    field_path="jobs",
                )
            if job.tenant_id != tenant_id:
                raise IntegrationValidationError(
                    "job pertence a outro tenant",
                    code="cross_tenant_execution_job",
                    field_path="jobs",
                )
            if job.product_type != product_type:
                raise IntegrationValidationError(
                    "job pertence a outro produto",
                    code="cross_product_execution_job",
                    field_path="jobs",
                )
        if len({result.result_id for result in results}) != len(results):
            raise IntegrationValidationError(
                "execução de integração possui resultados duplicados",
                code="duplicated_integration_execution_result",
                field_path="results",
            )
        result_by_id = {result.result_id: result for result in results}
        job_result_ids = {job.result_id for job in jobs if job.result_id is not None}
        extra_result_ids = set(result_by_id) - job_result_ids
        if extra_result_ids:
            raise IntegrationValidationError(
                "execução de integração possui resultados órfãos",
                code="orphan_integration_execution_result",
                field_path="results",
            )
        for job in jobs:
            if job.result_id is not None and job.result_id not in result_by_id:
                raise IntegrationValidationError(
                    "job referencia resultado ausente",
                    code="missing_execution_job_result",
                    field_path="jobs.result_id",
                )
            if job.result_id is not None:
                result = result_by_id[job.result_id]
                if result.tenant_id != tenant_id:
                    raise IntegrationValidationError(
                        "resultado pertence a outro tenant",
                        code="cross_tenant_execution_result",
                        field_path="results.tenant_id",
                    )
                if result.product_type != product_type:
                    raise IntegrationValidationError(
                        "resultado pertence a outro produto",
                        code="cross_product_execution_result",
                        field_path="results.product_type",
                    )
                if result.integration_class != job.integration_class:
                    raise IntegrationValidationError(
                        "resultado pertence a outra classe de integração",
                        code="cross_class_execution_result",
                        field_path="results.integration_class",
                    )
                if result.adapter_id != job.adapter_id:
                    raise IntegrationValidationError(
                        "resultado pertence a outro adapter",
                        code="cross_adapter_execution_result",
                        field_path="results.adapter_id",
                    )
                if result.correlation_id != correlation_id or result.trace_id != trace_id:
                    raise IntegrationValidationError(
                        "resultado possui contexto de rastreabilidade divergente",
                        code="cross_context_execution_result",
                        field_path="results.trace_context",
                    )
        return cls(
            execution_id=validate_execution_id(execution_id),
            tenant_id=tenant_id,
            product_type=product_type,
            plan_fingerprint=validate_plan_fingerprint(plan_fingerprint),
            idempotency_key=validate_idempotency_key(idempotency_key),
            status=execution_status,
            schema_version=validate_schema_version(schema_version),
            jobs=jobs,
            results=results,
            correlation_id=correlation_id,
            trace_id=trace_id,
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=duration_ms,
        )

    @property
    def job_ids(self) -> tuple[str, ...]:
        return tuple(job.job_id for job in self.jobs)

    def to_log_safe_dict(self) -> dict[str, object]:
        return {
            "execution_id": self.execution_id,
            "tenant_id": self.tenant_id,
            "product_type": self.product_type,
            "plan_fingerprint": self.plan_fingerprint,
            "status": self.status,
            "schema_version": self.schema_version,
            "job_count": len(self.jobs),
            "result_count": len(self.results),
            "correlation_id": self.correlation_id,
            "trace_id": self.trace_id,
            "duration_ms": self.duration_ms,
        }


def _job_status_from_result(result: IntegrationResult) -> str:
    if result.status == IntegrationResultStatus.COMPLETED.value:
        return IntegrationExecutionJobStatus.COMPLETED.value
    if result.status == IntegrationResultStatus.PARTIAL.value:
        return IntegrationExecutionJobStatus.PARTIAL.value
    if result.status == IntegrationResultStatus.NOT_FOUND.value:
        return IntegrationExecutionJobStatus.MISSING.value
    return IntegrationExecutionJobStatus.FAILED.value


def _validate_cost_record_boundaries(
    *,
    job: IntegrationExecutionJob,
    result: IntegrationResult,
) -> None:
    if job.result_id != result.result_id:
        raise IntegrationValidationError(
            "registro de custo referencia resultado divergente do job",
            code="cross_result_integration_cost_record",
            field_path="result.result_id",
        )
    if result.tenant_id != job.tenant_id:
        raise IntegrationValidationError(
            "registro de custo referencia resultado de outro tenant",
            code="cross_tenant_integration_cost_record",
            field_path="result.tenant_id",
        )
    if result.product_type != job.product_type:
        raise IntegrationValidationError(
            "registro de custo referencia resultado de outro produto",
            code="cross_product_integration_cost_record",
            field_path="result.product_type",
        )
    if result.integration_class != job.integration_class:
        raise IntegrationValidationError(
            "registro de custo referencia resultado de outra classe",
            code="cross_class_integration_cost_record",
            field_path="result.integration_class",
        )
    if result.adapter_id != job.adapter_id:
        raise IntegrationValidationError(
            "registro de custo referencia resultado de outro adapter",
            code="cross_adapter_integration_cost_record",
            field_path="result.adapter_id",
        )
    if result.correlation_id != job.correlation_id or result.trace_id != job.trace_id:
        raise IntegrationValidationError(
            "registro de custo referencia resultado com rastreabilidade divergente",
            code="cross_context_integration_cost_record",
            field_path="result.trace_context",
        )


def _execution_status_from_jobs(jobs: tuple[IntegrationExecutionJob, ...]) -> str:
    statuses = {job.status for job in jobs}
    if statuses & {
        IntegrationExecutionJobStatus.PENDING.value,
        IntegrationExecutionJobStatus.RUNNING.value,
    }:
        raise IntegrationValidationError(
            "execução final possui jobs não finalizados",
            code="non_terminal_integration_execution_jobs",
            field_path="jobs.status",
        )
    if any(
        job.status
        in {
            IntegrationExecutionJobStatus.FAILED.value,
            IntegrationExecutionJobStatus.TIMED_OUT.value,
        }
        and job.requirement == "required"
        and job.fallback_strategy == "fail_closed"
        for job in jobs
    ):
        return IntegrationExecutionStatus.FAILED.value
    if statuses == {IntegrationExecutionJobStatus.MISSING.value}:
        return IntegrationExecutionStatus.MISSING.value
    if statuses == {IntegrationExecutionJobStatus.COMPLETED.value}:
        return IntegrationExecutionStatus.COMPLETED.value
    return IntegrationExecutionStatus.PARTIAL.value
