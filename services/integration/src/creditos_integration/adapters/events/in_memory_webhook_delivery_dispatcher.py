from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
from hashlib import sha256

from creditos_observability.context import ObservabilityContext

from creditos_integration.application.ports.webhook_delivery import (
    WebhookDeliveryAdapter,
    WebhookDeliveryDispatchResult,
    WebhookDeliveryRetrySchedule,
    WebhookSigningKeyResolver,
    build_signed_webhook_request,
)
from creditos_integration.domain.entities.webhook_configuration import WebhookConfiguration
from creditos_integration.domain.entities.webhook_delivery import (
    WebhookDeliveryDlqRecord,
    WebhookDeliveryJob,
    WebhookNotificationEvent,
)
from creditos_integration.domain.value_objects.execution import validate_failure_code
from creditos_integration.domain.value_objects.webhook import WebhookRetryStrategy


class InMemoryWebhookDeliveryDispatcher:
    def __init__(
        self,
        *,
        adapter: WebhookDeliveryAdapter,
        signing_key_resolver: WebhookSigningKeyResolver,
    ) -> None:
        self._adapter = adapter
        self._signing_key_resolver = signing_key_resolver

    def dispatch(
        self,
        *,
        job: WebhookDeliveryJob,
        event: WebhookNotificationEvent,
        configuration: WebhookConfiguration,
        context: ObservabilityContext,
        clock: Callable[[], datetime],
        dlq_id_factory: Callable[[str], str],
    ) -> WebhookDeliveryDispatchResult:
        del context
        attempt_count = job.attempt_count
        delivered_at = clock()
        request = build_signed_webhook_request(
            job=job,
            event=event,
            configuration=configuration,
            signing_key_resolver=self._signing_key_resolver,
            delivered_at=delivered_at,
        )
        try:
            result = self._adapter.deliver(request)
        except TimeoutError:
            result_failure_code = "timed_out"
            temporary_failure = True
        except PermissionError:
            result_failure_code = "endpoint_rejected"
            temporary_failure = False
        except Exception:
            result_failure_code = "adapter_error"
            temporary_failure = True
        else:
            if result.outcome == "accepted":
                sent_job = job.with_status(
                    status="sent",
                    attempt_count=attempt_count,
                    updated_at=clock(),
                )
                return WebhookDeliveryDispatchResult(jobs=(sent_job,))
            result_failure_code = validate_failure_code(
                result.failure_code or _failure_code_from_status(result.status_code)
            )
            temporary_failure = result.outcome == "temporary_failure"

        if (
            temporary_failure
            and attempt_count < configuration.max_attempts
            and configuration.retry_strategy != WebhookRetryStrategy.NO_RETRY.value
        ):
            retry_schedule = _retry_schedule(
                job=job,
                configuration=configuration,
                failure_code=result_failure_code,
                attempt_count=attempt_count,
                scheduled_at=clock(),
            )
            retry_job = job.with_status(
                status="retry_scheduled",
                attempt_count=attempt_count,
                updated_at=clock(),
            )
            return WebhookDeliveryDispatchResult(
                jobs=(retry_job,),
                retry_schedules=(retry_schedule,),
            )

        terminal_job = job.with_status(
            status="dlq_recorded",
            attempt_count=attempt_count,
            updated_at=clock(),
        )
        dlq_record = WebhookDeliveryDlqRecord.create(
            dlq_id=dlq_id_factory(
                "|".join((terminal_job.job_id, event.event_id, str(attempt_count)))
            ),
            job=terminal_job,
            event=event,
            failure_code=result_failure_code,
            created_at=clock(),
        )
        return WebhookDeliveryDispatchResult(
            jobs=(terminal_job,),
            dlq_records=(dlq_record,),
        )


def _retry_schedule(
    *,
    job: WebhookDeliveryJob,
    configuration: WebhookConfiguration,
    failure_code: str,
    attempt_count: int,
    scheduled_at: datetime,
) -> WebhookDeliveryRetrySchedule:
    backoff_ms = min(
        configuration.max_backoff_ms,
        configuration.initial_backoff_ms * (2 ** max(0, attempt_count - 1)),
    )
    jitter_ms = _jitter_ms(
        seed="|".join((job.job_id, failure_code, str(attempt_count))),
        backoff_ms=backoff_ms,
    )
    retry_delay_ms = backoff_ms + jitter_ms
    return WebhookDeliveryRetrySchedule(
        job_id=job.job_id,
        tenant_id=job.tenant_id,
        webhook_configuration_id=job.webhook_configuration_id,
        event_id=job.event_id,
        failure_code=validate_failure_code(failure_code),
        attempt_count=attempt_count,
        next_attempt_count=attempt_count + 1,
        backoff_ms=backoff_ms,
        jitter_ms=jitter_ms,
        retry_delay_ms=retry_delay_ms,
        scheduled_at=scheduled_at,
        next_attempt_at=scheduled_at + timedelta(milliseconds=retry_delay_ms),
        correlation_id=job.correlation_id,
        trace_id=job.trace_id,
    )


def _jitter_ms(*, seed: str, backoff_ms: int) -> int:
    if backoff_ms <= 0:
        return 0
    digest = sha256(seed.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % max(1, backoff_ms // 2)


def _failure_code_from_status(status_code: int | None) -> str:
    if status_code is None:
        return "adapter_error"
    if status_code == 408:
        return "request_timeout"
    if status_code == 429:
        return "rate_limited"
    if status_code >= 500:
        return "endpoint_unavailable"
    return "endpoint_rejected"
