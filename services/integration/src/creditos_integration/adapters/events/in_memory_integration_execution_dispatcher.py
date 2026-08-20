from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from hashlib import sha256
from threading import Lock
from time import perf_counter

from creditos_observability.context import ObservabilityContext

from creditos_integration.application.ports.integration_execution import (
    IntegrationExecutionDispatchResult,
    IntegrationExecutionJobRequest,
)
from creditos_integration.domain.entities import (
    IntegrationExecutionJob,
    IntegrationResult,
)
from creditos_integration.domain.errors import IntegrationValidationError
from creditos_integration.domain.value_objects.execution import IntegrationExecutionJobStatus
from creditos_integration.domain.value_objects.result import (
    IntegrationResultStatus,
    MockIntegrationScenario,
    SyntheticDataType,
)


class InMemoryIntegrationExecutionDispatcher:
    def __init__(self) -> None:
        self.dispatch_count = 0
        self.max_observed_concurrency = 0
        self._active_jobs = 0
        self._lock = Lock()

    def dispatch(
        self,
        *,
        execution_id: str,
        job_requests: tuple[IntegrationExecutionJobRequest, ...],
        synthetic_subject_reference: str,
        context: ObservabilityContext,
        clock: Callable[[], datetime],
    ) -> IntegrationExecutionDispatchResult:
        if not job_requests:
            raise IntegrationValidationError(
                "nenhum job de integração para despachar",
                code="empty_integration_execution_job_requests",
                field_path="job_requests",
            )
        self.dispatch_count += 1
        effective_concurrency = min(
            len(job_requests),
            max(1, min(request.item.max_concurrency for request in job_requests)),
        )
        jobs_by_index: dict[int, IntegrationExecutionJob] = {}
        results_by_index: dict[int, IntegrationResult] = {}
        self._active_jobs = 0
        self.max_observed_concurrency = 0

        with ThreadPoolExecutor(max_workers=effective_concurrency) as executor:
            futures = {
                executor.submit(
                    self._execute_job,
                    execution_id=execution_id,
                    request=request,
                    synthetic_subject_reference=synthetic_subject_reference,
                    context=context,
                    clock=clock,
                ): index
                for index, request in enumerate(job_requests)
            }
            for future, index in futures.items():
                job, result = future.result()
                jobs_by_index[index] = job
                results_by_index[index] = result

        return IntegrationExecutionDispatchResult(
            jobs=tuple(jobs_by_index[index] for index in range(len(job_requests))),
            results=tuple(results_by_index[index] for index in range(len(job_requests))),
            max_observed_concurrency=self.max_observed_concurrency,
        )

    def _execute_job(
        self,
        *,
        execution_id: str,
        request: IntegrationExecutionJobRequest,
        synthetic_subject_reference: str,
        context: ObservabilityContext,
        clock: Callable[[], datetime],
    ) -> tuple[IntegrationExecutionJob, IntegrationResult]:
        self._enter_job()
        try:
            started_at = clock()
            started_perf = perf_counter()
            try:
                raw_result = request.adapter.execute(
                    request.item,
                    scenario=request.scenario,
                    synthetic_subject_reference=synthetic_subject_reference,
                    context=context,
                    started_at=started_at,
                    completed_at=started_at,
                    duration_ms=0.0,
                )
                duration_ms = _duration_ms(started_perf)
                if duration_ms > request.item.timeout_ms:
                    result = _failed_result(
                        execution_id=execution_id,
                        request=request,
                        context=context,
                        started_at=started_at,
                        completed_at=clock(),
                        duration_ms=duration_ms,
                        reason="timed_out",
                    )
                    job_status = IntegrationExecutionJobStatus.TIMED_OUT.value
                else:
                    result = _finalize_result(
                        result=raw_result,
                        completed_at=clock(),
                        duration_ms=duration_ms,
                    )
                    _validate_result(result=result, request=request, context=context)
                    job_status = None
            except Exception:
                result = _failed_result(
                    execution_id=execution_id,
                    request=request,
                    context=context,
                    started_at=started_at,
                    completed_at=clock(),
                    duration_ms=_duration_ms(started_perf),
                    reason="adapter_exception",
                )
                job_status = IntegrationExecutionJobStatus.FAILED.value
            running_job = IntegrationExecutionJob.create(
                job_id=request.job_id,
                execution_id=execution_id,
                item=request.item,
                status=IntegrationExecutionJobStatus.RUNNING.value,
                correlation_id=context.correlation_id,
                trace_id=context.trace_id,
            )
            return running_job.with_result(result, status=job_status), result
        finally:
            self._leave_job()

    def _enter_job(self) -> None:
        with self._lock:
            self._active_jobs += 1
            self.max_observed_concurrency = max(
                self.max_observed_concurrency,
                self._active_jobs,
            )

    def _leave_job(self) -> None:
        with self._lock:
            self._active_jobs -= 1


def _finalize_result(
    *,
    result: IntegrationResult,
    completed_at: datetime,
    duration_ms: float,
) -> IntegrationResult:
    return IntegrationResult.create(
        result_id=result.result_id,
        tenant_id=result.tenant_id,
        product_type=result.product_type,
        integration_class=result.integration_class,
        adapter_id=result.adapter_id,
        status=result.status,
        scenario=result.scenario,
        schema_version=result.schema_version,
        reason_codes=result.reason_codes,
        summary=result.summary,
        correlation_id=result.correlation_id,
        trace_id=result.trace_id,
        started_at=result.started_at,
        completed_at=completed_at,
        duration_ms=duration_ms,
    )


def _validate_result(
    *,
    result: IntegrationResult,
    request: IntegrationExecutionJobRequest,
    context: ObservabilityContext,
) -> None:
    if result.tenant_id != request.item.tenant_id:
        raise IntegrationValidationError(
            "resultado de job pertence a outro tenant",
            code="integration_job_result_tenant_mismatch",
            field_path="result.tenant_id",
        )
    if result.product_type != request.item.product_type:
        raise IntegrationValidationError(
            "resultado de job pertence a outro produto",
            code="integration_job_result_product_mismatch",
            field_path="result.product_type",
        )
    if result.integration_class != request.item.integration_class:
        raise IntegrationValidationError(
            "resultado de job pertence a outra classe",
            code="integration_job_result_class_mismatch",
            field_path="result.integration_class",
        )
    if result.adapter_id != request.item.adapter_id:
        raise IntegrationValidationError(
            "resultado de job pertence a outro adapter",
            code="integration_job_result_adapter_mismatch",
            field_path="result.adapter_id",
        )
    if result.scenario != request.scenario:
        raise IntegrationValidationError(
            "resultado de job pertence a outro cenário",
            code="integration_job_result_scenario_mismatch",
            field_path="result.scenario",
        )
    if result.correlation_id != context.correlation_id:
        raise IntegrationValidationError(
            "resultado de job possui correlation ID divergente",
            code="integration_job_result_correlation_mismatch",
            field_path="result.correlation_id",
        )
    if result.trace_id != context.trace_id:
        raise IntegrationValidationError(
            "resultado de job possui trace ID divergente",
            code="integration_job_result_trace_mismatch",
            field_path="result.trace_id",
        )
    if result.status not in {
        IntegrationResultStatus.COMPLETED.value,
        IntegrationResultStatus.PARTIAL.value,
        IntegrationResultStatus.NOT_FOUND.value,
        IntegrationResultStatus.FAILED.value,
    }:
        raise IntegrationValidationError(
            "status de resultado de job não suportado",
            code="unsupported_integration_job_result_status",
            field_path="result.status",
        )


def _failed_result(
    *,
    execution_id: str,
    request: IntegrationExecutionJobRequest,
    context: ObservabilityContext,
    started_at: datetime,
    completed_at: datetime,
    duration_ms: float,
    reason: str,
) -> IntegrationResult:
    result_seed = f"{execution_id}|{request.job_id}|{reason}"
    result_id = f"ires_{sha256(result_seed.encode()).hexdigest()[:32]}"
    return IntegrationResult.create(
        result_id=result_id,
        tenant_id=request.item.tenant_id,
        product_type=request.item.product_type,
        integration_class=request.item.integration_class,
        adapter_id=request.item.adapter_id,
        status=IntegrationResultStatus.FAILED.value,
        scenario=MockIntegrationScenario.SYNTHETIC_FAILURE.value,
        reason_codes=("synthetic_controlled_failure",),
        summary=_failure_summary_for(request.item.integration_class),
        correlation_id=context.correlation_id,
        trace_id=context.trace_id,
        started_at=started_at,
        completed_at=completed_at,
        duration_ms=duration_ms,
    )


def _failure_summary_for(integration_class: str) -> dict[str, str]:
    synthetic_data_type = SyntheticDataType.MOCK_INTEGRATION_RESULT.value
    return {
        "kyc_kyb": {
            "synthetic_data_type": synthetic_data_type,
            "identity_status": "unavailable",
            "document_status": "unavailable",
            "sanctions_status": "unknown",
        },
        "credit_bureau": {
            "synthetic_data_type": synthetic_data_type,
            "score_band": "unavailable",
            "restriction_status": "unknown",
            "debt_profile": "unknown",
        },
        "anti_fraud": {
            "synthetic_data_type": synthetic_data_type,
            "risk_band": "unavailable",
            "device_status": "unknown",
            "velocity_status": "unknown",
        },
        "receivables": {
            "synthetic_data_type": synthetic_data_type,
            "eligibility_status": "unavailable",
            "coverage_band": "unknown",
            "settlement_status": "unknown",
        },
    }[integration_class]


def _duration_ms(started_at: float) -> float:
    return round((perf_counter() - started_at) * 1000, 3)
