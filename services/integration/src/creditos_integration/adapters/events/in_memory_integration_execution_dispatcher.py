from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from hashlib import sha256
from threading import Lock
from time import perf_counter

from creditos_observability.context import ObservabilityContext

from creditos_integration.application.ports.integration_execution import (
    IntegrationDlqStore,
    IntegrationExecutionDispatchResult,
    IntegrationExecutionJobRequest,
    IntegrationExecutionRetrySchedule,
    IntegrationRetryEvaluation,
    IntegrationRetryPolicy,
)
from creditos_integration.domain.entities import (
    IntegrationExecutionDlqRecord,
    IntegrationExecutionJob,
    IntegrationResult,
)
from creditos_integration.domain.errors import IntegrationValidationError
from creditos_integration.domain.value_objects.execution import (
    IntegrationExecutionJobStatus,
    IntegrationFailureClass,
    IntegrationRetryDecision,
    validate_backoff_ms,
    validate_failure_code,
    validate_jitter_ms,
)
from creditos_integration.domain.value_objects.result import (
    IntegrationResultStatus,
    MockIntegrationScenario,
    SyntheticDataType,
)


class InMemoryIntegrationExecutionDispatcher:
    def __init__(
        self,
        *,
        retry_policy: IntegrationRetryPolicy | None = None,
        dlq_store: IntegrationDlqStore | None = None,
    ) -> None:
        self.dispatch_count = 0
        self.max_observed_concurrency = 0
        self.retry_schedule_count = 0
        self._active_jobs = 0
        self._lock = Lock()
        self._retry_policy = retry_policy or DeterministicIntegrationRetryPolicy()
        self._dlq_store = dlq_store

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
        retry_schedules_by_index: dict[int, tuple[IntegrationExecutionRetrySchedule, ...]] = {}
        dlq_records_by_index: dict[int, tuple[IntegrationExecutionDlqRecord, ...]] = {}
        with self._lock:
            dispatch_lock = getattr(self, "_dispatch_lock", None)
            if dispatch_lock is None:
                dispatch_lock = Lock()
                self._dispatch_lock = dispatch_lock

        with dispatch_lock:
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
                    job, result, retry_schedules, dlq_records = future.result()
                    jobs_by_index[index] = job
                    results_by_index[index] = result
                    retry_schedules_by_index[index] = retry_schedules
                    dlq_records_by_index[index] = dlq_records

            return IntegrationExecutionDispatchResult(
                jobs=tuple(jobs_by_index[index] for index in range(len(job_requests))),
                results=tuple(results_by_index[index] for index in range(len(job_requests))),
                max_observed_concurrency=self.max_observed_concurrency,
                retry_schedules=tuple(
                    schedule
                    for index in range(len(job_requests))
                    for schedule in retry_schedules_by_index[index]
                ),
                dlq_records=tuple(
                    record
                    for index in range(len(job_requests))
                    for record in dlq_records_by_index[index]
                ),
            )

    def _execute_job(
        self,
        *,
        execution_id: str,
        request: IntegrationExecutionJobRequest,
        synthetic_subject_reference: str,
        context: ObservabilityContext,
        clock: Callable[[], datetime],
    ) -> tuple[
        IntegrationExecutionJob,
        IntegrationResult,
        tuple[IntegrationExecutionRetrySchedule, ...],
        tuple[IntegrationExecutionDlqRecord, ...],
    ]:
        self._enter_job()
        try:
            retry_schedules: list[IntegrationExecutionRetrySchedule] = []
            dlq_records: list[IntegrationExecutionDlqRecord] = []
            max_attempts = request.item.max_attempts
            for attempt_count in range(1, max_attempts + 1):
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
                        failure_class = IntegrationFailureClass.TIMEOUT.value
                        failure_code = "timed_out"
                    else:
                        result = _finalize_result(
                            result=raw_result,
                            completed_at=clock(),
                            duration_ms=duration_ms,
                        )
                        _validate_result(result=result, request=request, context=context)
                        if result.status == IntegrationResultStatus.FAILED.value:
                            failure_class = IntegrationFailureClass.RECOVERABLE.value
                            failure_code = _safe_failure_code(result.reason_codes[0])
                            duration_ms = result.duration_ms
                        else:
                            completed_job = _running_job(
                                execution_id=execution_id,
                                request=request,
                                context=context,
                                attempt_count=attempt_count,
                            ).with_result(result)
                            return completed_job, result, tuple(retry_schedules), tuple(dlq_records)
                except IntegrationValidationError as error:
                    duration_ms = _duration_ms(started_perf)
                    failure_class = IntegrationFailureClass.INVALID_RESULT.value
                    failure_code = _safe_failure_code(getattr(error, "code", "invalid_result"))
                except TimeoutError:
                    duration_ms = _duration_ms(started_perf)
                    failure_class = IntegrationFailureClass.TIMEOUT.value
                    failure_code = "timed_out"
                except PermissionError:
                    duration_ms = _duration_ms(started_perf)
                    failure_class = IntegrationFailureClass.NON_RECOVERABLE.value
                    failure_code = "non_recoverable_adapter_error"
                except Exception:
                    duration_ms = _duration_ms(started_perf)
                    failure_class = IntegrationFailureClass.RECOVERABLE.value
                    failure_code = "adapter_error"

                evaluation = self._retry_policy.evaluate(
                    request=request,
                    attempt_count=attempt_count,
                    failure_class=failure_class,
                    failure_code=failure_code,
                )
                failed_job = _running_job(
                    execution_id=execution_id,
                    request=request,
                    context=context,
                    attempt_count=attempt_count,
                )
                if evaluation.decision == IntegrationRetryDecision.RETRY.value:
                    schedule = _retry_schedule(
                        job=failed_job,
                        evaluation=evaluation,
                        scheduled_at=clock(),
                    )
                    retry_schedules.append(schedule)
                    with self._lock:
                        self.retry_schedule_count += 1
                    continue

                result = _failed_result(
                    execution_id=execution_id,
                    request=request,
                    context=context,
                    started_at=started_at,
                    completed_at=clock(),
                    duration_ms=duration_ms,
                    reason=failure_code,
                )
                job_status = (
                    IntegrationExecutionJobStatus.TIMED_OUT.value
                    if failure_class == IntegrationFailureClass.TIMEOUT.value
                    else IntegrationExecutionJobStatus.FAILED.value
                )
                terminal_job = failed_job.with_result(result, status=job_status)
                if evaluation.decision == IntegrationRetryDecision.SEND_TO_DLQ.value:
                    if self._dlq_store is None:
                        raise IntegrationValidationError(
                            "store de DLQ de integração não configurado",
                            code="integration_dlq_store_not_configured",
                            field_path="dlq_store",
                        )
                    record = _dlq_record(
                        job=terminal_job,
                        failure_class=evaluation.failure_class,
                        failure_code=evaluation.failure_code,
                        created_at=clock(),
                    )
                    dlq_records.append(self._dlq_store.save(record))
                return terminal_job, result, tuple(retry_schedules), tuple(dlq_records)
            raise IntegrationValidationError(
                "política de retry não produziu estado terminal",
                code="integration_retry_policy_non_terminal",
                field_path="retry_policy",
            )
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


class DeterministicIntegrationRetryPolicy:
    def evaluate(
        self,
        *,
        request: IntegrationExecutionJobRequest,
        attempt_count: int,
        failure_class: str,
        failure_code: str,
    ) -> IntegrationRetryEvaluation:
        failure_class = IntegrationFailureClass(failure_class).value
        failure_code = _safe_failure_code(failure_code)
        max_attempts = request.item.max_attempts
        if (
            failure_class
            in {
                IntegrationFailureClass.RECOVERABLE.value,
                IntegrationFailureClass.TIMEOUT.value,
            }
            and attempt_count < max_attempts
        ):
            backoff_ms = _backoff_ms(
                timeout_ms=request.item.timeout_ms,
                attempt_count=attempt_count,
            )
            jitter_ms = _jitter_ms(
                seed="|".join((request.job_id, failure_class, failure_code, str(attempt_count))),
                backoff_ms=backoff_ms,
            )
            return IntegrationRetryEvaluation(
                decision=IntegrationRetryDecision.RETRY.value,
                failure_class=failure_class,
                failure_code=failure_code,
                attempt_count=attempt_count,
                max_attempts=max_attempts,
                backoff_ms=backoff_ms,
                jitter_ms=jitter_ms,
                retry_delay_ms=backoff_ms + jitter_ms,
            )
        decision = (
            IntegrationRetryDecision.SEND_TO_DLQ.value
            if failure_class
            in {
                IntegrationFailureClass.RECOVERABLE.value,
                IntegrationFailureClass.TIMEOUT.value,
                IntegrationFailureClass.NON_RECOVERABLE.value,
                IntegrationFailureClass.INVALID_RESULT.value,
            }
            else IntegrationRetryDecision.FAIL_FAST.value
        )
        return IntegrationRetryEvaluation(
            decision=decision,
            failure_class=failure_class,
            failure_code=failure_code,
            attempt_count=attempt_count,
            max_attempts=max_attempts,
            backoff_ms=0,
            jitter_ms=0,
            retry_delay_ms=0,
        )


def _running_job(
    *,
    execution_id: str,
    request: IntegrationExecutionJobRequest,
    context: ObservabilityContext,
    attempt_count: int,
) -> IntegrationExecutionJob:
    return IntegrationExecutionJob.create(
        job_id=request.job_id,
        execution_id=execution_id,
        item=request.item,
        status=IntegrationExecutionJobStatus.RUNNING.value,
        correlation_id=context.correlation_id,
        trace_id=context.trace_id,
        attempt_count=attempt_count,
    )


def _retry_schedule(
    *,
    job: IntegrationExecutionJob,
    evaluation: IntegrationRetryEvaluation,
    scheduled_at: datetime,
) -> IntegrationExecutionRetrySchedule:
    return IntegrationExecutionRetrySchedule(
        execution_id=job.execution_id,
        job_id=job.job_id,
        tenant_id=job.tenant_id,
        product_type=job.product_type,
        integration_class=job.integration_class,
        adapter_id=job.adapter_id,
        failure_class=evaluation.failure_class,
        failure_code=evaluation.failure_code,
        attempt_count=evaluation.attempt_count,
        next_attempt_count=evaluation.attempt_count + 1,
        backoff_ms=evaluation.backoff_ms,
        jitter_ms=evaluation.jitter_ms,
        retry_delay_ms=evaluation.retry_delay_ms,
        schema_version=job.schema_version,
        correlation_id=job.correlation_id,
        trace_id=job.trace_id,
        scheduled_at=scheduled_at.isoformat(),
    )


def _dlq_record(
    *,
    job: IntegrationExecutionJob,
    failure_class: str,
    failure_code: str,
    created_at: datetime,
) -> IntegrationExecutionDlqRecord:
    seed = "|".join((job.execution_id, job.job_id, failure_class, failure_code))
    return IntegrationExecutionDlqRecord.from_job(
        dlq_id=f"idlq_{sha256(seed.encode()).hexdigest()[:32]}",
        job=job,
        failure_class=failure_class,
        failure_code=failure_code,
        created_at=created_at,
    )


def _backoff_ms(*, timeout_ms: int, attempt_count: int) -> int:
    return validate_backoff_ms(min(timeout_ms, 250 * 2 ** (attempt_count - 1)))


def _jitter_ms(*, seed: str, backoff_ms: int) -> int:
    backoff_ms = validate_backoff_ms(backoff_ms)
    if backoff_ms == 0:
        return 0
    jitter_window = max(1, min(250, backoff_ms // 2))
    jitter = int(sha256(seed.encode()).hexdigest()[:8], 16) % (jitter_window + 1)
    return validate_jitter_ms(jitter, backoff_ms=backoff_ms)


def _safe_failure_code(value: str) -> str:
    try:
        return validate_failure_code(value)
    except IntegrationValidationError:
        return "adapter_error"


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
