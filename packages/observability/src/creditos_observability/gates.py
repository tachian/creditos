from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Literal

from creditos_observability.telemetry import TelemetryOperationType


class ObservabilitySignal(StrEnum):
    STRUCTURED_LOG = "structured_log"
    METRIC = "metric"
    TRACE_SPAN = "trace_span"
    HEALTH = "health"
    READINESS = "readiness"
    CORRELATION_ID = "correlation_id"


@dataclass(frozen=True, slots=True)
class ObservabilityCapability:
    name: str
    service_name: str
    required_signals: tuple[ObservabilitySignal, ...]
    operation_type: TelemetryOperationType | None = None
    description: str = ""


ExposureKind = Literal["technical_internal", "internal_catalog", "customer_facing"]

_OPERATION_REQUIRED_SIGNALS = frozenset(
    {
        ObservabilitySignal.STRUCTURED_LOG,
        ObservabilitySignal.METRIC,
        ObservabilitySignal.TRACE_SPAN,
        ObservabilitySignal.CORRELATION_ID,
    }
)
_REQUIRED_SERVICE_SIGNALS = frozenset({ObservabilitySignal.HEALTH, ObservabilitySignal.READINESS})
_CRITICAL_SERVICE_NAMES = frozenset(
    {
        "audit-evidence",
        "automated-review",
        "decision",
        "identity-tenant",
        "integration",
        "proposal-intake",
        "reporting-insights",
    }
)
_SAFE_REDACTED_VALUES = frozenset({"[OMITIDO]", "[DADO_FINANCEIRO_OMITIDO]"})
_CUSTOMER_FACING_SCOPES = frozenset({"dashboard:read", "reporting:read"})
_CURATED_CUSTOMER_FACING_SOURCES = frozenset(
    {"reporting_insights_projection", "reporting_insights_curated"}
)
_VALID_EXPOSURES = frozenset({"technical_internal", "internal_catalog", "customer_facing"})
_MAX_SCAN_DEPTH = 12

_RAW_CPF_PATTERN = re.compile(r"(?<!\d)(?:\d{3}\.?\d{3}\.?\d{3}-?\d{2})(?!\d)")
_RAW_CNPJ_PATTERN = re.compile(r"(?<!\d)(?:\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2})(?!\d)")
_RAW_EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_RAW_PHONE_PATTERN = re.compile(r"(?<!\d)(?:\+?55\s*)?(?:\(?\d{2}\)?\s*)?\d{4,5}-?\d{4}(?!\d)")
_SECRET_ASSIGNMENT_PATTERN = re.compile(
    r"(?i)\b(?:api[_-]?key|access[_-]?token|refresh[_-]?token|client[_-]?secret|"
    r"password|senha|secret|token)\s*[:=]\s*[^\s,;]}]+"
)

_TECHNICAL_FORBIDDEN_KEY_TERMS = frozenset(
    {
        "api_key",
        "apikey",
        "authorization",
        "bearer",
        "client_secret",
        "cnpj",
        "cpf",
        "decision_id",
        "email",
        "headers",
        "output",
        "password",
        "payload",
        "prompt",
        "proposal_id",
        "raw_error",
        "secret",
        "senha",
        "token",
    }
)
_INTERNAL_CATALOG_FORBIDDEN_TERMS = frozenset(
    {
        "api_key",
        "bearer",
        "cnpj",
        "correlation_id",
        "cpf",
        "credential",
        "credentials",
        "decision_id",
        "email",
        "logs_raw",
        "password",
        "payload",
        "proposal_id",
        "raw_log",
        "raw_trace",
        "receiver",
        "request_id",
        "secret",
        "tenant_id",
        "token",
        "trace_id",
        "traces_raw",
        "webhook",
    }
)
_CUSTOMER_FACING_FORBIDDEN_TERMS = frozenset(
    {
        "api_key",
        "bank",
        "banco_transacional",
        "bearer",
        "billing",
        "cnpj",
        "correlation_id",
        "cost_currency",
        "cpu",
        "cpf",
        "currency",
        "datasource",
        "decision_id",
        "email",
        "fatura",
        "grafana",
        "host",
        "logs_raw",
        "loki",
        "memory",
        "moeda",
        "node",
        "payload",
        "pod",
        "price",
        "pricing",
        "prometheus",
        "promql",
        "proposal_id",
        "query",
        "raw_log",
        "raw_trace",
        "request_id",
        "secret",
        "stack_trace",
        "stacktrace",
        "tarifa",
        "tempo",
        "token",
        "trace_id",
        "traces_raw",
        "transactional_database",
        "transacional",
    }
)
_SAFE_TECHNICAL_KEYS = frozenset(
    {
        "output_validation_status",
        "payload_digest",
        "prompt_fingerprint",
        "prompt_version",
    }
)
_SAFE_CUSTOMER_TEXT_VALUES = frozenset({"tempo_medio", "tempo_de_resposta", "signal_not_available"})
_SAFE_CUSTOMER_KEY_VALUES = frozenset({"tenant_ref", "tenant_isolation_tier"})


def observability_gate_catalog() -> tuple[ObservabilityCapability, ...]:
    operation_capabilities = tuple(
        ObservabilityCapability(
            name=f"{service_name}_{operation_type.value}_operation",
            service_name=service_name,
            operation_type=operation_type,
            required_signals=tuple(sorted(_OPERATION_REQUIRED_SIGNALS, key=str)),
            description=(
                "Operações críticas devem emitir log estruturado, métrica, span e "
                "correlation ID com validação local por serviço."
            ),
        )
        for service_name in sorted(_CRITICAL_SERVICE_NAMES)
        for operation_type in TelemetryOperationType
    )
    service_capabilities = tuple(
        capability
        for service_name in sorted(_CRITICAL_SERVICE_NAMES)
        for capability in (
            ObservabilityCapability(
                name=f"{service_name}_service_health",
                service_name=service_name,
                required_signals=(ObservabilitySignal.HEALTH,),
                description="Todo serviço deve expor health seguro e minimizado.",
            ),
            ObservabilityCapability(
                name=f"{service_name}_service_readiness",
                service_name=service_name,
                required_signals=(ObservabilitySignal.READINESS,),
                description="Todo serviço deve expor readiness seguro e minimizado.",
            ),
        )
    )
    return operation_capabilities + service_capabilities


def validate_observability_gate_catalog(
    catalog: Iterable[ObservabilityCapability],
) -> None:
    capabilities = tuple(catalog)
    if not capabilities:
        raise ValueError("catálogo de gates de observabilidade não pode ser vazio")

    seen_names: set[str] = set()
    services: set[str] = set()
    signals_by_service: dict[str, set[ObservabilitySignal]] = {}
    operations_by_service: dict[str, set[TelemetryOperationType]] = {}

    for capability in capabilities:
        _validate_capability_metadata(capability, seen_names)
        services.add(capability.service_name)
        signals = frozenset(capability.required_signals)
        service_signals = signals_by_service.setdefault(capability.service_name, set())
        service_signals.update(signals)
        if capability.operation_type is not None:
            operations_by_service.setdefault(capability.service_name, set()).add(
                capability.operation_type
            )
            missing = _OPERATION_REQUIRED_SIGNALS - signals
            if missing:
                raise ValueError(
                    f"capability {capability.name} sem sinais obrigatórios: "
                    f"{', '.join(sorted(signal.value for signal in missing))}"
                )

    missing_services = _CRITICAL_SERVICE_NAMES - services
    if missing_services:
        raise ValueError(f"catálogo sem serviços críticos: {', '.join(sorted(missing_services))}")

    for service_name in sorted(_CRITICAL_SERVICE_NAMES):
        missing_operations = set(TelemetryOperationType) - operations_by_service.get(
            service_name, set()
        )
        if missing_operations:
            raise ValueError(
                f"serviço {service_name} sem coverage para operações: "
                f"{', '.join(sorted(operation.value for operation in missing_operations))}"
            )
        missing_service_signals = _REQUIRED_SERVICE_SIGNALS - signals_by_service.get(
            service_name, set()
        )
        if missing_service_signals:
            raise ValueError(
                f"serviço {service_name} sem sinais de serviço: "
                f"{', '.join(sorted(signal.value for signal in missing_service_signals))}"
            )


def validate_observability_exposure_payload(
    payload: Any,
    *,
    exposure: ExposureKind = "technical_internal",
    expected_tenant_ref: str | None = None,
    granted_scopes: Iterable[str] | None = None,
    curated_source: str | None = None,
) -> None:
    if exposure not in _VALID_EXPOSURES:
        raise ValueError(f"exposure inválido: {exposure}")
    if exposure == "customer_facing":
        validate_customer_facing_observability_payload(
            payload,
            expected_tenant_ref=expected_tenant_ref,
            granted_scopes=granted_scopes,
            curated_source=curated_source,
        )
        return

    findings = tuple(_scan_payload(payload, exposure=exposure, seen=set(), depth=0))
    if findings:
        raise ValueError(_safe_findings_message(findings))


def validate_customer_facing_observability_payload(
    payload: Any,
    *,
    expected_tenant_ref: str | None,
    granted_scopes: Iterable[str] | None,
    curated_source: str | None,
) -> None:
    _validate_customer_access_context(
        payload,
        expected_tenant_ref=expected_tenant_ref,
        granted_scopes=granted_scopes,
        curated_source=curated_source,
    )
    findings = tuple(_scan_payload(payload, exposure="customer_facing", seen=set(), depth=0))
    if findings:
        raise ValueError(_safe_findings_message(findings))


def _validate_customer_access_context(
    payload: Any,
    *,
    expected_tenant_ref: str | None,
    granted_scopes: Iterable[str] | None,
    curated_source: str | None,
) -> None:
    if not isinstance(payload, Mapping):
        raise ValueError("payload customer-facing deve ser mapping serializado")
    if not expected_tenant_ref:
        raise ValueError("expected_tenant_ref é obrigatório para gate customer-facing")
    if payload.get("tenant_ref") != expected_tenant_ref:
        raise ValueError("tenant_ref customer-facing diverge do tenant autorizado")
    scope_set = frozenset(granted_scopes or ())
    if not scope_set & _CUSTOMER_FACING_SCOPES:
        raise ValueError("escopo customer-facing não autorizado")
    if curated_source not in _CURATED_CUSTOMER_FACING_SOURCES:
        raise ValueError("fonte customer-facing curada não comprovada")


def _validate_capability_metadata(
    capability: ObservabilityCapability,
    seen_names: set[str],
) -> None:
    if not capability.name or not capability.name.replace("_", "").replace("-", "").isalnum():
        raise ValueError("capability deve ter nome técnico estável")
    if capability.name in seen_names:
        raise ValueError(f"capability duplicada: {capability.name}")
    seen_names.add(capability.name)
    if not capability.service_name:
        raise ValueError(f"capability {capability.name} sem service_name")
    if not capability.required_signals:
        raise ValueError(f"capability {capability.name} sem sinais obrigatórios")


def _scan_payload(
    payload: Any,
    *,
    exposure: ExposureKind,
    seen: set[int],
    depth: int,
    path: str = "root",
) -> Iterable[str]:
    if depth > _MAX_SCAN_DEPTH:
        yield f"{path}:max_depth"
        return

    if isinstance(payload, Mapping):
        payload_id = id(payload)
        if payload_id in seen:
            yield f"{path}:cycle"
            return
        next_seen = {*seen, payload_id}
        for key, value in payload.items():
            key_text = str(key).lower()
            yield from _scan_key(key_text, value, exposure=exposure, path=path)
            yield from _scan_payload(
                value,
                exposure=exposure,
                seen=next_seen,
                depth=depth + 1,
                path=f"{path}.{key_text}",
            )
        return

    if isinstance(payload, str):
        yield from _scan_text(payload, exposure=exposure, path=path)
        return

    if isinstance(payload, int) and not isinstance(payload, bool):
        yield from _scan_numeric_identifier(payload, path=path)
        return

    if isinstance(payload, bytes | bytearray | memoryview):
        if payload:
            yield f"{path}:bytes"
        return

    if isinstance(payload, Sequence) and not isinstance(payload, str | bytes | bytearray):
        payload_id = id(payload)
        if payload_id in seen:
            yield f"{path}:cycle"
            return
        next_seen = {*seen, payload_id}
        for index, item in enumerate(payload):
            yield from _scan_payload(
                item,
                exposure=exposure,
                seen=next_seen,
                depth=depth + 1,
                path=f"{path}[{index}]",
            )
        return

    if isinstance(payload, set | frozenset):
        yield f"{path}:non_json_iterable"


def _scan_key(key: str, value: Any, *, exposure: ExposureKind, path: str) -> Iterable[str]:
    if exposure == "technical_internal":
        if key == "payload" and isinstance(value, str) and value in _SAFE_REDACTED_VALUES:
            return
        if key in _SAFE_TECHNICAL_KEYS:
            return
        for term in sorted(_TECHNICAL_FORBIDDEN_KEY_TERMS):
            if _matches_forbidden_identifier(key, term):
                yield f"{path}.{key}:{term}"
        return

    if key in _SAFE_CUSTOMER_KEY_VALUES or key in _SAFE_CUSTOMER_TEXT_VALUES:
        return
    forbidden_terms = (
        _INTERNAL_CATALOG_FORBIDDEN_TERMS
        if exposure == "internal_catalog"
        else _CUSTOMER_FACING_FORBIDDEN_TERMS
    )
    for term in sorted(forbidden_terms):
        if _matches_forbidden_identifier(key, term):
            yield f"{path}.{key}:{term}"


def _scan_text(text: str, *, exposure: ExposureKind, path: str) -> Iterable[str]:
    if text in _SAFE_REDACTED_VALUES:
        return

    lowered = text.lower()
    if exposure == "customer_facing" and lowered in _SAFE_CUSTOMER_TEXT_VALUES:
        return

    for pattern, term in (
        (_RAW_CPF_PATTERN, "cpf"),
        (_RAW_CNPJ_PATTERN, "cnpj"),
        (_RAW_EMAIL_PATTERN, "email"),
        (_SECRET_ASSIGNMENT_PATTERN, "secret_assignment"),
    ):
        if pattern.search(text):
            yield f"{path}:{term}"

    for match in _RAW_PHONE_PATTERN.finditer(text):
        if (
            _is_hex_memory_address_match(text, match)
            or _is_hex_identifier_match(text, match)
            or _is_iso_datetime_match(text, match)
        ):
            continue
        yield f"{path}:telefone"
        break

    forbidden_terms: frozenset[str]
    if exposure == "technical_internal":
        forbidden_terms = frozenset(
            {
                "api_key",
                "authorization",
                "bearer",
                "client_secret",
                "output",
                "password",
                "prompt",
                "raw_error",
                "secret",
                "senha",
                "token",
            }
        )
    elif exposure == "internal_catalog":
        forbidden_terms = _INTERNAL_CATALOG_FORBIDDEN_TERMS
    else:
        forbidden_terms = _CUSTOMER_FACING_FORBIDDEN_TERMS

    for term in sorted(forbidden_terms):
        if _matches_forbidden_text(lowered, term):
            yield f"{path}:{term}"


def _is_hex_memory_address_match(text: str, match: re.Match[str]) -> bool:
    start = match.start()
    end = match.end()
    token_start = start
    while token_start > 0 and text[token_start - 1].isalnum():
        token_start -= 1
    token_end = end
    while token_end < len(text) and text[token_end].isalnum():
        token_end += 1
    token = text[token_start:token_end]
    return token.lower().startswith("0x") and all(
        character in "0123456789abcdefABCDEF" for character in token[2:]
    )


def _is_hex_identifier_match(text: str, match: re.Match[str]) -> bool:
    token = _match_token(text, match)
    return (
        len(token) >= 16
        and any(character in "abcdefABCDEF" for character in token)
        and all(character in "0123456789abcdefABCDEF" for character in token)
    )


def _is_iso_datetime_match(text: str, match: re.Match[str]) -> bool:
    window_start = max(0, match.start() - 32)
    window = text[window_start : min(len(text), match.end() + 32)]
    iso_datetime_pattern = re.compile(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}"
        r"(?::\d{2}(?:\.\d{1,6})?)?"
        r"(?:Z|[+-]\d{2}:\d{2})?"
    )
    for datetime_match in iso_datetime_pattern.finditer(window):
        datetime_start = window_start + datetime_match.start()
        datetime_end = window_start + datetime_match.end()
        if match.start() >= datetime_start and match.end() <= datetime_end:
            return True
    return False


def _match_token(text: str, match: re.Match[str]) -> str:
    token_start = match.start()
    while token_start > 0 and text[token_start - 1].isalnum():
        token_start -= 1
    token_end = match.end()
    while token_end < len(text) and text[token_end].isalnum():
        token_end += 1
    return text[token_start:token_end]


def _scan_numeric_identifier(value: int, *, path: str) -> Iterable[str]:
    digits = str(abs(value))
    if len(digits) == 11 and _RAW_CPF_PATTERN.fullmatch(digits):
        yield f"{path}:cpf"
    if len(digits) == 14 and _RAW_CNPJ_PATTERN.fullmatch(digits):
        yield f"{path}:cnpj"


def _matches_forbidden_identifier(value: str, term: str) -> bool:
    if term in _SAFE_CUSTOMER_TEXT_VALUES:
        return False
    normalized_value = _normalize_identifier(value)
    normalized_term = _normalize_identifier(term)
    if normalized_value == normalized_term:
        return True
    if normalized_term in {"token", "secret", "credential", "password"}:
        return normalized_term in normalized_value
    if normalized_term in {"api_key", "apikey", "client_secret"}:
        return normalized_term in normalized_value
    return normalized_term in _identifier_tokens(normalized_value)


def _matches_forbidden_text(lowered_text: str, term: str) -> bool:
    normalized_term = _normalize_identifier(term)
    if normalized_term in {"token", "secret", "password", "bearer", "authorization"}:
        return (
            re.search(rf"(?<![a-z0-9]){re.escape(normalized_term)}(?![a-z0-9])", lowered_text)
            is not None
        )
    if normalized_term == "tempo":
        return re.search(r"(?<![a-z0-9_])tempo(?![_a-z0-9])", lowered_text) is not None
    normalized_text = _normalize_identifier(lowered_text)
    return normalized_term in _identifier_tokens(normalized_text)


def _normalize_identifier(value: str) -> str:
    normalized = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", value).lower()
    normalized = re.sub(r"[^a-z0-9]+", "_", normalized)
    return normalized.strip("_")


def _identifier_tokens(value: str) -> frozenset[str]:
    parts = [token for token in value.split("_") if token]
    tokens = set(parts)
    if len(parts) >= 2:
        tokens.update("_".join(pair) for pair in zip(parts, parts[1:], strict=False))
    return frozenset(tokens)


def _safe_findings_message(findings: tuple[str, ...]) -> str:
    redacted = sorted({finding.rsplit(":", maxsplit=1)[-1] for finding in findings if finding})
    serialized_terms = json.dumps(redacted, ensure_ascii=False)
    return f"payload de observabilidade expõe termos proibidos: {serialized_terms}"
