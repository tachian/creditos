from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from secrets import token_hex

_TRACE_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")
_SPAN_ID_PATTERN = re.compile(r"^[0-9a-f]{16}$")
_TRACE_FLAGS_PATTERN = re.compile(r"^[0-9a-f]{2}$")


@dataclass(frozen=True, slots=True)
class ObservabilityContext:
    correlation_id: str
    request_id: str
    trace_id: str
    tenant_id: str | None = None
    tenant_isolation_tier: str | None = None

    @classmethod
    def new(
        cls,
        *,
        correlation_id: str | None = None,
        request_id: str | None = None,
        trace_id: str | None = None,
        tenant_id: str | None = None,
        tenant_isolation_tier: str | None = None,
    ) -> ObservabilityContext:
        safe_trace_id = token_hex(16)
        if trace_id is not None and _is_valid_trace_id(trace_id):
            safe_trace_id = trace_id
        return cls(
            correlation_id=correlation_id or token_hex(16),
            request_id=request_id or token_hex(16),
            trace_id=safe_trace_id,
            tenant_id=tenant_id,
            tenant_isolation_tier=tenant_isolation_tier,
        )

    @classmethod
    def from_carrier(
        cls,
        carrier: Mapping[str, str],
        *,
        trusted_tenant: bool = False,
    ) -> ObservabilityContext:
        normalized_carrier = {key.lower(): value for key, value in carrier.items()}
        trace_id = _trace_id_from_traceparent(normalized_carrier.get("traceparent"))
        tenant_id = None
        tenant_isolation_tier = None
        if trusted_tenant:
            tenant_id = (
                normalized_carrier.get("x-creditos-tenant-id")
                or normalized_carrier.get("x-tenant-id")
                or normalized_carrier.get("tenantid")
            )
            tenant_isolation_tier = (
                normalized_carrier.get("x-creditos-tenant-isolation-tier")
                or normalized_carrier.get("x-tenant-isolation-tier")
                or normalized_carrier.get("tenanttier")
            )

        return cls.new(
            correlation_id=normalized_carrier.get("x-correlation-id")
            or normalized_carrier.get("correlationid"),
            request_id=normalized_carrier.get("x-request-id")
            or normalized_carrier.get("requestid"),
            trace_id=trace_id,
            tenant_id=tenant_id,
            tenant_isolation_tier=tenant_isolation_tier,
        )

    @classmethod
    def from_http_headers(cls, headers: Mapping[str, str]) -> ObservabilityContext:
        return cls.from_carrier(headers, trusted_tenant=False)

    @classmethod
    def from_grpc_metadata(
        cls,
        metadata: Mapping[str, str] | Sequence[tuple[str, str]],
    ) -> ObservabilityContext:
        return cls.from_carrier(_metadata_to_mapping(metadata), trusted_tenant=True)

    @classmethod
    def from_cloudevent_attributes(cls, attributes: Mapping[str, str]) -> ObservabilityContext:
        return cls.from_carrier(attributes, trusted_tenant=True)

    def to_log_fields(self) -> dict[str, str]:
        fields = {
            "correlation_id": self.correlation_id,
            "request_id": self.request_id,
            "trace_id": self.trace_id,
        }
        if self.tenant_id:
            fields["tenant_id"] = self.tenant_id
        if self.tenant_isolation_tier:
            fields["tenant_isolation_tier"] = self.tenant_isolation_tier
        return fields

    def to_carrier(self) -> dict[str, str]:
        span_id = token_hex(8)
        carrier = {
            "x-correlation-id": self.correlation_id,
            "x-request-id": self.request_id,
            "traceparent": f"00-{self.trace_id}-{span_id}-01",
        }
        if self.tenant_id:
            carrier["x-tenant-id"] = self.tenant_id
        if self.tenant_isolation_tier:
            carrier["x-tenant-isolation-tier"] = self.tenant_isolation_tier
        return carrier


def _trace_id_from_traceparent(traceparent: str | None) -> str | None:
    if not traceparent:
        return None

    parts = traceparent.split("-")
    if (
        len(parts) == 4
        and parts[0] == "00"
        and _is_valid_trace_id(parts[1])
        and _is_valid_span_id(parts[2])
        and _TRACE_FLAGS_PATTERN.fullmatch(parts[3])
    ):
        return parts[1]

    return None


def _metadata_to_mapping(
    metadata: Mapping[str, str] | Sequence[tuple[str, str]],
) -> Mapping[str, str]:
    if isinstance(metadata, Mapping):
        return metadata
    return {key: value for key, value in metadata}


def _is_valid_trace_id(trace_id: str | None) -> bool:
    return bool(trace_id and _TRACE_ID_PATTERN.fullmatch(trace_id) and trace_id != "0" * 32)


def _is_valid_span_id(span_id: str | None) -> bool:
    return bool(span_id and _SPAN_ID_PATTERN.fullmatch(span_id) and span_id != "0" * 16)
