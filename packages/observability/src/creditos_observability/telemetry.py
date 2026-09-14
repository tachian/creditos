from __future__ import annotations

from collections.abc import Mapping
from math import isfinite
from types import TracebackType
from typing import Any

from creditos_security.masking import mask_sensitive_data
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import Span

from creditos_observability.context import ObservabilityContext

_METRIC_ATTRIBUTE_ALLOWLIST = {
    "channel",
    "classification",
    "contract",
    "contract_version",
    "cost_units_present",
    "destination",
    "fallback_action",
    "operation",
    "output_validation_status",
    "product_type",
    "review_purpose",
    "source",
    "status",
    "tenant_isolation_tier",
}
_SPAN_ATTRIBUTE_ALLOWLIST = _METRIC_ATTRIBUTE_ALLOWLIST | {
    "agent_version",
    "correlation_id",
    "model_ref",
    "model_version",
    "prompt_version",
    "provider_ref",
    "review_agent_config_version_id",
    "tenant_id",
}


class InMemoryTelemetry:
    def __init__(
        self,
        *,
        service_name: str,
        service_version: str,
        environment: str = "test",
    ) -> None:
        resource = Resource.create(
            {
                "service.name": service_name,
                "service.version": service_version,
                "deployment.environment": environment,
            }
        )
        self._span_exporter = InMemorySpanExporter()
        self._tracer_provider = TracerProvider(resource=resource)
        self._tracer_provider.add_span_processor(SimpleSpanProcessor(self._span_exporter))
        self._tracer = self._tracer_provider.get_tracer(service_name, service_version)

        self._metric_reader = InMemoryMetricReader()
        self._meter_provider = MeterProvider(
            resource=resource, metric_readers=[self._metric_reader]
        )
        self._meter = self._meter_provider.get_meter(service_name, service_version)
        self._request_counter = self._meter.create_counter("creditos.requests.total")
        self._request_duration = self._meter.create_histogram("creditos.request.duration")
        self._ai_estimated_cost_units = self._meter.create_histogram(
            "creditos.ai.estimated_cost_units"
        )
        self._ai_actual_cost_units = self._meter.create_histogram("creditos.ai.actual_cost_units")
        self._ai_input_model_units = self._meter.create_histogram("creditos.ai.input_model_units")
        self._ai_output_model_units = self._meter.create_histogram("creditos.ai.output_model_units")
        self._ai_total_model_units = self._meter.create_histogram("creditos.ai.total_model_units")

    def start_span(
        self,
        name: str,
        *,
        context: ObservabilityContext,
        attributes: Mapping[str, Any] | None = None,
    ) -> _SpanContextManager:
        safe_attributes = _safe_span_attributes(context, attributes)
        return _SpanContextManager(
            self._tracer.start_as_current_span(
                name,
                attributes=safe_attributes,
                record_exception=False,
                set_status_on_exception=False,
            )
        )

    def record_request(
        self,
        *,
        context: ObservabilityContext,
        operation: str,
        status: str,
        duration_ms: float,
        attributes: Mapping[str, Any] | None = None,
    ) -> None:
        _validate_duration_ms(duration_ms)
        safe_attributes = _safe_metric_attributes(context, attributes)
        safe_attributes["operation"] = operation
        safe_attributes["status"] = status

        self._request_counter.add(1, attributes=safe_attributes)
        self._request_duration.record(duration_ms, attributes=safe_attributes)

    def record_ai_usage(
        self,
        *,
        context: ObservabilityContext,
        operation: str,
        status: str,
        estimated_cost_units: int | None = None,
        actual_cost_units: int | None = None,
        input_model_unit_count: int | None = None,
        output_model_unit_count: int | None = None,
        total_model_unit_count: int | None = None,
        attributes: Mapping[str, Any] | None = None,
    ) -> None:
        safe_attributes = _safe_metric_attributes(context, attributes)
        safe_attributes["operation"] = operation
        safe_attributes["status"] = status
        measurements = (
            (estimated_cost_units, self._ai_estimated_cost_units),
            (actual_cost_units, self._ai_actual_cost_units),
            (input_model_unit_count, self._ai_input_model_units),
            (output_model_unit_count, self._ai_output_model_units),
            (total_model_unit_count, self._ai_total_model_units),
        )
        for value, _instrument in measurements:
            if value is not None:
                _validate_usage_units(value)
        for value, instrument in measurements:
            if value is not None:
                instrument.record(value, attributes=safe_attributes)

    def finished_spans(self) -> tuple[ReadableSpan, ...]:
        return tuple(self._span_exporter.get_finished_spans())

    def metrics_data(self) -> object:
        return self._metric_reader.get_metrics_data()


class _SpanContextManager:
    def __init__(self, span_context_manager: Any) -> None:
        self._span_context_manager = span_context_manager

    def __enter__(self) -> Span:
        return self._span_context_manager.__enter__()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None:
        return self._span_context_manager.__exit__(exc_type, exc_value, traceback)


def _safe_span_attributes(
    context: ObservabilityContext,
    attributes: Mapping[str, Any] | None,
) -> dict[str, str | int | float | bool]:
    base_attributes: dict[str, Any] = dict(attributes or {})
    base_attributes["correlation_id"] = context.correlation_id
    if context.tenant_id:
        base_attributes["tenant_id"] = context.tenant_id
    if context.tenant_isolation_tier:
        base_attributes["tenant_isolation_tier"] = context.tenant_isolation_tier
    return _sanitize_attributes(base_attributes, allowlist=_SPAN_ATTRIBUTE_ALLOWLIST)


def _safe_metric_attributes(
    context: ObservabilityContext,
    attributes: Mapping[str, Any] | None,
) -> dict[str, str | int | float | bool]:
    base_attributes: dict[str, Any] = {}
    if context.tenant_isolation_tier:
        base_attributes["tenant_isolation_tier"] = context.tenant_isolation_tier
    if attributes:
        base_attributes.update(attributes)

    return _sanitize_attributes(base_attributes, allowlist=_METRIC_ATTRIBUTE_ALLOWLIST)


def _sanitize_attributes(
    attributes: Mapping[str, Any],
    *,
    allowlist: set[str],
) -> dict[str, str | int | float | bool]:
    sanitized = mask_sensitive_data(attributes)
    return {
        key: value
        for key, value in sanitized.items()
        if key in allowlist and isinstance(value, str | int | float | bool)
    }


def _validate_duration_ms(duration_ms: float) -> None:
    if not isfinite(duration_ms) or duration_ms < 0:
        raise ValueError("duration_ms deve ser finito e não negativo")


def _validate_usage_units(value: int) -> None:
    if type(value) is not int or value < 0:
        raise ValueError("unidades de uso/custo devem ser inteiras e não negativas")
