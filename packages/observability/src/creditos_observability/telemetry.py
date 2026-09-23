from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from math import isfinite
from types import TracebackType
from typing import Any

from creditos_security.masking import mask_sensitive_data, sanitize_technical_field
from opentelemetry.context import Context
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import (
    NonRecordingSpan,
    Span,
    SpanContext,
    TraceFlags,
    TraceState,
    get_current_span,
    set_span_in_context,
)

from creditos_observability.context import ObservabilityContext
from creditos_observability.logging import build_structured_log

_METRIC_ATTRIBUTE_ALLOWLIST = {
    "channel",
    "classification",
    "contract",
    "contract_version",
    "cost_units_present",
    "destination",
    "fallback_action",
    "operation",
    "operation_type",
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
    "request_id",
    "tenant_id",
    "trace_id",
}
_OPERATION_METRIC_ATTRIBUTES = (
    "channel",
    "contract",
    "contract_version",
    "destination",
    "operation",
    "operation_type",
    "product_type",
    "source",
    "status",
    "tenant_isolation_tier",
)
_OPERATION_SPAN_ATTRIBUTES = _OPERATION_METRIC_ATTRIBUTES + (
    "correlation_id",
    "request_id",
    "tenant_id",
    "trace_id",
)
_FORBIDDEN_METRIC_ATTRIBUTES = (
    "tenant_id",
    "correlation_id",
    "request_id",
    "trace_id",
    "proposal_id",
    "decision_id",
    "cpf",
    "cnpj",
    "email",
    "payload",
    "prompt",
    "output",
    "raw_error",
    "token",
    "secret",
)
_RESERVED_CONTEXT_ATTRIBUTES = frozenset(
    {
        "correlation_id",
        "request_id",
        "trace_id",
        "tenant_id",
        "tenant_isolation_tier",
    }
)
_FORBIDDEN_LOG_EXTRA_KEYS = frozenset(
    {
        "authorization",
        "headers",
        "payload",
        "prompt",
        "completion",
        "output",
        "raw_output",
        "raw_error",
        "error_message",
        "exception",
        "tenant_id",
        "tenant_isolation_tier",
        "correlation_id",
        "request_id",
        "trace_id",
        "operation_type",
    }
)
_LOW_CARDINALITY_ATTRIBUTE_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,79}$")
_UUID_LIKE_PATTERN = re.compile(
    r"(?i)^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$"
)
_HEX_IDENTIFIER_PATTERN = re.compile(r"(?i)[a-f0-9]{16,}")
_LONG_DIGIT_RUN_PATTERN = re.compile(r"\d{6,}")
_UNSTABLE_ROUTE_CHARS = frozenset("{}[]/\\")


class TelemetryOperationType(StrEnum):
    HTTP = "http"
    GRPC = "grpc"
    EVENT = "event"
    JOB = "job"
    INTEGRATION = "integration"


@dataclass(frozen=True, slots=True)
class TechnicalSignal:
    name: str
    signal_type: str
    required_attributes: tuple[str, ...]
    allowed_attributes: tuple[str, ...]
    forbidden_attributes: tuple[str, ...]


class InMemoryTelemetry:
    def __init__(
        self,
        *,
        service_name: str,
        service_version: str,
        environment: str = "test",
    ) -> None:
        self._service_name = _safe_required_attribute(service_name, field_name="service_name")
        self._service_version = _safe_required_attribute(
            service_version,
            field_name="service_version",
        )
        self._environment = _safe_required_attribute(environment, field_name="environment")
        resource = Resource.create(
            {
                "service.name": self._service_name,
                "service.version": self._service_version,
                "deployment.environment": self._environment,
            }
        )
        self._span_exporter = InMemorySpanExporter()
        self._tracer_provider = TracerProvider(resource=resource)
        self._tracer_provider.add_span_processor(SimpleSpanProcessor(self._span_exporter))
        self._tracer = self._tracer_provider.get_tracer(self._service_name, self._service_version)

        self._metric_reader = InMemoryMetricReader()
        self._meter_provider = MeterProvider(
            resource=resource, metric_readers=[self._metric_reader]
        )
        self._meter = self._meter_provider.get_meter(self._service_name, self._service_version)
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
        parent_context = _parent_context_from_observability_context(context)
        return _SpanContextManager(
            self._tracer.start_as_current_span(
                name,
                context=parent_context,
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
        safe_attributes["operation"] = _safe_required_attribute(
            operation,
            field_name="operation",
        )
        safe_attributes["status"] = _safe_required_attribute(status, field_name="status")

        self._request_counter.add(1, attributes=safe_attributes)
        self._request_duration.record(duration_ms, attributes=safe_attributes)

    def record_operation(
        self,
        *,
        context: ObservabilityContext,
        operation_type: TelemetryOperationType | str,
        operation: str,
        status: str,
        duration_ms: float,
        source: str,
        destination: str,
        contract: str,
        contract_version: str,
        channel: str | None = None,
        product_type: str | None = None,
        status_code: int | None = None,
        payload: Any | None = None,
        extra: Mapping[str, Any] | None = None,
        attributes: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        operation_type_value = _operation_type_value(operation_type)
        safe_operation = _safe_low_cardinality_attribute(operation, field_name="operation")
        safe_status = _safe_low_cardinality_attribute(status, field_name="status")
        safe_span_attributes = _operation_attributes(
            operation_type=operation_type_value,
            operation=safe_operation,
            status=safe_status,
            source=source,
            destination=destination,
            contract=contract,
            contract_version=contract_version,
            channel=channel,
            product_type=product_type,
            attributes=attributes,
            allowlist=set(_OPERATION_SPAN_ATTRIBUTES),
        )
        safe_metric_attributes = _operation_attributes(
            operation_type=operation_type_value,
            operation=safe_operation,
            status=safe_status,
            source=source,
            destination=destination,
            contract=contract,
            contract_version=contract_version,
            channel=channel,
            product_type=product_type,
            attributes=attributes,
            allowlist=set(_OPERATION_METRIC_ATTRIBUTES),
        )
        safe_log_extra = _safe_operation_log_extra(
            operation_type=operation_type_value,
            extra=extra,
        )
        event = build_structured_log(
            context=context,
            service_name=self._service_name,
            service_version=self._service_version,
            environment=self._environment,
            operation=safe_operation,
            source=source,
            destination=destination,
            contract=contract,
            contract_version=contract_version,
            status=safe_status,
            duration_ms=duration_ms,
            status_code=status_code,
            payload=payload,
            extra=safe_log_extra,
        )

        with self.start_span(
            f"{operation_type_value}.{safe_operation}",
            context=context,
            attributes=safe_span_attributes,
        ):
            self.record_request(
                context=context,
                operation=safe_operation,
                status=safe_status,
                duration_ms=duration_ms,
                attributes=safe_metric_attributes,
            )

        return event

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
        safe_attributes["operation"] = _safe_required_attribute(
            operation,
            field_name="operation",
        )
        safe_attributes["status"] = _safe_required_attribute(status, field_name="status")
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
    base_attributes: dict[str, Any] = _without_reserved_context_attributes(attributes)
    base_attributes["correlation_id"] = context.correlation_id
    base_attributes["request_id"] = context.request_id
    base_attributes["trace_id"] = context.trace_id
    if context.tenant_id:
        base_attributes["tenant_id"] = context.tenant_id
    if context.tenant_isolation_tier:
        base_attributes["tenant_isolation_tier"] = context.tenant_isolation_tier
    return _sanitize_attributes(base_attributes, allowlist=_SPAN_ATTRIBUTE_ALLOWLIST)


def _safe_metric_attributes(
    context: ObservabilityContext,
    attributes: Mapping[str, Any] | None,
) -> dict[str, str | int | float | bool]:
    base_attributes: dict[str, Any] = _without_reserved_context_attributes(attributes)
    if context.tenant_isolation_tier:
        base_attributes["tenant_isolation_tier"] = context.tenant_isolation_tier

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


def technical_signal_taxonomy() -> tuple[TechnicalSignal, ...]:
    required = (
        "service.name",
        "service.version",
        "deployment.environment",
        "operation",
        "status",
        "duration_ms",
        "correlation_id",
        "request_id",
        "trace_id",
    )
    return (
        TechnicalSignal(
            name="operation.log",
            signal_type="log",
            required_attributes=required,
            allowed_attributes=_OPERATION_SPAN_ATTRIBUTES,
            forbidden_attributes=("payload", "headers", "prompt", "output", "raw_error"),
        ),
        TechnicalSignal(
            name="operation.duration",
            signal_type="metric",
            required_attributes=(
                "service.name",
                "service.version",
                "deployment.environment",
                "operation",
                "status",
                "duration_ms",
            ),
            allowed_attributes=_OPERATION_METRIC_ATTRIBUTES,
            forbidden_attributes=_FORBIDDEN_METRIC_ATTRIBUTES,
        ),
        TechnicalSignal(
            name="operation.trace",
            signal_type="trace/span",
            required_attributes=required,
            allowed_attributes=_OPERATION_SPAN_ATTRIBUTES,
            forbidden_attributes=("payload", "headers", "prompt", "output", "raw_error"),
        ),
        TechnicalSignal(
            name="customer-facing.dashboard",
            signal_type="projeção futura",
            required_attributes=("tenant_id", "metric_name", "aggregation_window"),
            allowed_attributes=("tenant_id", "tenant_isolation_tier", "metric_name"),
            forbidden_attributes=("log_raw", "trace_raw", "payload", "headers"),
        ),
    )


def _operation_attributes(
    *,
    operation_type: str,
    operation: str,
    status: str,
    source: str,
    destination: str,
    contract: str,
    contract_version: str,
    channel: str | None,
    product_type: str | None,
    attributes: Mapping[str, Any] | None,
    allowlist: set[str],
) -> dict[str, str | int | float | bool]:
    operation_attributes: dict[str, Any] = _without_reserved_context_attributes(attributes)
    operation_attributes.update(
        {
            "operation_type": operation_type,
            "operation": operation,
            "status": status,
            "source": _safe_low_cardinality_attribute(source, field_name="source"),
            "destination": _safe_low_cardinality_attribute(
                destination,
                field_name="destination",
            ),
            "contract": _safe_low_cardinality_attribute(contract, field_name="contract"),
            "contract_version": _safe_low_cardinality_attribute(
                contract_version,
                field_name="contract_version",
            ),
        }
    )
    if channel is not None:
        operation_attributes["channel"] = _safe_low_cardinality_attribute(
            channel,
            field_name="channel",
        )
    if product_type is not None:
        operation_attributes["product_type"] = _safe_low_cardinality_attribute(
            product_type,
            field_name="product_type",
        )
    return _sanitize_attributes(operation_attributes, allowlist=allowlist)


def _operation_type_value(operation_type: TelemetryOperationType | str) -> str:
    if isinstance(operation_type, TelemetryOperationType):
        return operation_type.value
    try:
        return TelemetryOperationType(operation_type).value
    except ValueError as error:
        raise ValueError("operation_type inválido") from error


def _parent_context_from_observability_context(context: ObservabilityContext) -> Context | None:
    current_span_context = get_current_span().get_span_context()
    if current_span_context.is_valid:
        return None

    parent_span_id = int(context.parent_span_id, 16) if context.parent_span_id else 1
    span_context = SpanContext(
        trace_id=int(context.trace_id, 16),
        span_id=parent_span_id,
        is_remote=True,
        trace_flags=TraceFlags(int(context.trace_flags, 16)),
        trace_state=TraceState(),
    )
    return set_span_in_context(NonRecordingSpan(span_context))


def _safe_required_attribute(value: str, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} deve ser string obrigatória")
    safe_value = sanitize_technical_field(str(mask_sensitive_data(value)))[:160]
    if not safe_value:
        raise ValueError(f"{field_name} é obrigatório")
    return safe_value


def _safe_low_cardinality_attribute(value: str, *, field_name: str) -> str:
    safe_value = _safe_required_attribute(value, field_name=field_name)
    if (
        not _LOW_CARDINALITY_ATTRIBUTE_PATTERN.fullmatch(safe_value)
        or _UUID_LIKE_PATTERN.fullmatch(safe_value)
        or _HEX_IDENTIFIER_PATTERN.search(safe_value)
        or _LONG_DIGIT_RUN_PATTERN.search(safe_value)
        or any(character in value for character in _UNSTABLE_ROUTE_CHARS)
    ):
        raise ValueError(f"{field_name} deve ser valor técnico estável e de baixa cardinalidade")
    return safe_value


def _without_reserved_context_attributes(
    attributes: Mapping[str, Any] | None,
) -> dict[str, Any]:
    return {
        key: value
        for key, value in dict(attributes or {}).items()
        if key not in _RESERVED_CONTEXT_ATTRIBUTES
    }


def _safe_operation_log_extra(
    *,
    operation_type: str,
    extra: Mapping[str, Any] | None,
) -> dict[str, Any]:
    safe_extra = {
        key: value
        for key, value in dict(extra or {}).items()
        if key not in _FORBIDDEN_LOG_EXTRA_KEYS
    }
    safe_extra["operation_type"] = operation_type
    return safe_extra


def _validate_duration_ms(duration_ms: float) -> None:
    if not isfinite(duration_ms) or duration_ms < 0:
        raise ValueError("duration_ms deve ser finito e não negativo")


def _validate_usage_units(value: int) -> None:
    if type(value) is not int or value < 0:
        raise ValueError("unidades de uso/custo devem ser inteiras e não negativas")
