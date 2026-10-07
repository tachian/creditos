from __future__ import annotations

import ipaddress
import re
import socket
from enum import StrEnum
from urllib.parse import parse_qsl, urlsplit, urlunsplit

from creditos_integration.domain.errors import IntegrationValidationError


class WebhookEventType(StrEnum):
    DECISION_STATUS_CHANGED = "decision.status_changed"
    DECISION_COMPLETED = "decision.completed"


class WebhookStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"
    PENDING_VERIFICATION = "pending_verification"
    REJECTED = "rejected"


class WebhookSigningAlgorithm(StrEnum):
    HMAC_SHA256 = "hmac_sha256"


class WebhookRetryStrategy(StrEnum):
    STANDARD_EXPONENTIAL_BACKOFF = "standard_exponential_backoff"
    NO_RETRY = "no_retry"


_WEBHOOK_CONFIGURATION_ID_PATTERN = re.compile(r"^wcfg_[a-z0-9_.:-]{3,160}$")
_SIGNING_KEY_REF_PATTERN = re.compile(r"^wkey_[a-z0-9_.:-]{3,160}$")
_SENSITIVE_QUERY_TOKENS = {"authorization", "auth", "key", "password", "secret", "token"}
_SENSITIVE_QUERY_SUBSTRINGS = {
    "apikey",
    "api_key",
    "accesskey",
    "access_key",
    "access_token",
    "auth_token",
    "client_secret",
    "id_token",
    "refresh_token",
    "secret_key",
    "x_api_key",
}
_SENSITIVE_QUERY_COMPACT_SUBSTRINGS = {
    value.replace("_", "") for value in _SENSITIVE_QUERY_SUBSTRINGS
}
_LOCAL_HOSTNAMES = {"localhost", "localhost.localdomain"}
_ALLOWED_WEBHOOK_PORTS = {443}


def validate_webhook_configuration_id(value: str) -> str:
    if not _WEBHOOK_CONFIGURATION_ID_PATTERN.fullmatch(value):
        raise IntegrationValidationError(
            "identificador de configuração de webhook inválido",
            code="invalid_webhook_configuration_id",
            field_path="webhook_configuration_id",
        )
    return value


def parse_webhook_events(values: tuple[str, ...]) -> tuple[str, ...]:
    if not values:
        raise IntegrationValidationError(
            "eventos de webhook ausentes",
            code="missing_webhook_events",
            field_path="events",
        )
    parsed: set[str] = set()
    for value in values:
        try:
            parsed.add(WebhookEventType(value).value)
        except ValueError as error:
            raise IntegrationValidationError(
                "evento de webhook não suportado",
                code="unsupported_webhook_event",
                field_path="events",
            ) from error
    return tuple(sorted(parsed))


def parse_webhook_status(value: str) -> str:
    try:
        return WebhookStatus(value).value
    except ValueError as error:
        raise IntegrationValidationError(
            "status de webhook não suportado",
            code="unsupported_webhook_status",
            field_path="status",
        ) from error


def parse_webhook_request_status(value: str) -> str:
    parsed = parse_webhook_status(value)
    if parsed == WebhookStatus.REJECTED.value:
        raise IntegrationValidationError(
            "status de webhook não permitido para configuração",
            code="unsupported_webhook_status",
            field_path="status",
        )
    return parsed


def parse_webhook_signing_algorithm(value: str) -> str:
    try:
        return WebhookSigningAlgorithm(value).value
    except ValueError as error:
        raise IntegrationValidationError(
            "algoritmo de assinatura de webhook não suportado",
            code="unsupported_webhook_signing_algorithm",
            field_path="signing_algorithm",
        ) from error


def validate_signing_key_ref(value: str) -> str:
    if not _SIGNING_KEY_REF_PATTERN.fullmatch(value):
        raise IntegrationValidationError(
            "referência de chave de assinatura inválida",
            code="invalid_webhook_signing_key_ref",
            field_path="signing_key_ref",
        )
    return value


def parse_webhook_retry_strategy(value: str) -> str:
    try:
        return WebhookRetryStrategy(value).value
    except ValueError as error:
        raise IntegrationValidationError(
            "estratégia de retry de webhook não suportada",
            code="unsupported_webhook_retry_strategy",
            field_path="retry_strategy",
        ) from error


def validate_webhook_endpoint_url(
    value: str,
    *,
    allowed_domains: tuple[str, ...] = (),
    resolved_addresses: tuple[str, ...] = (),
) -> str:
    try:
        parsed = urlsplit(value.strip())
        hostname = (parsed.hostname or "").strip().lower().rstrip(".")
        port = parsed.port
    except ValueError as error:
        raise _insecure_endpoint() from error
    if parsed.scheme != "https" or not hostname or parsed.username or parsed.password:
        raise _insecure_endpoint()
    if port is not None and port not in _ALLOWED_WEBHOOK_PORTS:
        raise _insecure_endpoint()
    if hostname in _LOCAL_HOSTNAMES or hostname.endswith(".localhost"):
        raise _insecure_endpoint()
    _reject_unsafe_ip_literal(hostname)
    _reject_resolved_addresses(resolved_addresses)
    _reject_sensitive_query(parsed.query)
    normalized_allowed_domains = tuple(
        domain.strip().lower().rstrip(".") for domain in allowed_domains if domain.strip()
    )
    if normalized_allowed_domains and not any(
        hostname == domain or hostname.endswith(f".{domain}")
        for domain in normalized_allowed_domains
    ):
        raise IntegrationValidationError(
            "endpoint de webhook fora da allowlist",
            code="webhook_endpoint_not_allowed",
            field_path="endpoint_url",
        )
    return urlunsplit(
        ("https", _normalized_netloc(hostname, port), parsed.path or "/", parsed.query, "")
    )


def resolve_webhook_endpoint_addresses(hostname: str) -> tuple[str, ...]:
    try:
        records = socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
    except socket.gaierror as error:
        raise IntegrationValidationError(
            "host de webhook não resolvido",
            code="webhook_endpoint_unresolvable",
            field_path="endpoint_url",
        ) from error
    addresses = tuple(
        sorted(
            address for address in (str(record[4][0]) for record in records if record[4]) if address
        )
    )
    if not addresses:
        raise IntegrationValidationError(
            "host de webhook não resolvido",
            code="webhook_endpoint_unresolvable",
            field_path="endpoint_url",
        )
    return addresses


def webhook_endpoint_host(endpoint_url: str) -> str:
    return (urlsplit(endpoint_url).hostname or "").lower().rstrip(".")


def validate_retry_limits(
    *,
    strategy: str,
    max_attempts: int,
    initial_backoff_ms: int,
    max_backoff_ms: int,
    timeout_ms: int,
) -> tuple[int, int, int, int]:
    if type(max_attempts) is not int or max_attempts < 1 or max_attempts > 10:
        raise IntegrationValidationError(
            "limite de tentativas de webhook inválido",
            code="invalid_webhook_attempt_limit",
            field_path="max_attempts",
        )
    if strategy == WebhookRetryStrategy.NO_RETRY.value and max_attempts != 1:
        raise IntegrationValidationError(
            "no_retry exige tentativa única",
            code="invalid_webhook_attempt_limit",
            field_path="max_attempts",
        )
    if (
        type(initial_backoff_ms) is not int
        or initial_backoff_ms < 100
        or initial_backoff_ms > 60_000
    ):
        raise IntegrationValidationError(
            "backoff inicial de webhook inválido",
            code="invalid_webhook_backoff",
            field_path="initial_backoff_ms",
        )
    if (
        type(max_backoff_ms) is not int
        or max_backoff_ms < initial_backoff_ms
        or max_backoff_ms > 300_000
    ):
        raise IntegrationValidationError(
            "backoff máximo de webhook inválido",
            code="invalid_webhook_backoff",
            field_path="max_backoff_ms",
        )
    if type(timeout_ms) is not int or timeout_ms < 500 or timeout_ms > 30_000:
        raise IntegrationValidationError(
            "timeout de webhook inválido",
            code="invalid_webhook_timeout",
            field_path="timeout_ms",
        )
    return max_attempts, initial_backoff_ms, max_backoff_ms, timeout_ms


def _reject_unsafe_ip_literal(hostname: str) -> None:
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        return
    _reject_unsafe_address(address)


def _reject_resolved_addresses(addresses: tuple[str, ...]) -> None:
    for value in addresses:
        try:
            address = ipaddress.ip_address(value)
        except ValueError as error:
            raise _insecure_endpoint() from error
        _reject_unsafe_address(address)


def _reject_unsafe_address(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> None:
    if not address.is_global or address.is_multicast:
        raise _insecure_endpoint()


def _reject_sensitive_query(query: str) -> None:
    for key, _ in parse_qsl(query, keep_blank_values=True):
        normalized_key = re.sub(r"[^a-z0-9]+", "_", key.strip().lower()).strip("_")
        query_key_tokens = set(normalized_key.split("_"))
        compact_key = normalized_key.replace("_", "")
        if (
            query_key_tokens & _SENSITIVE_QUERY_TOKENS
            or compact_key in _SENSITIVE_QUERY_COMPACT_SUBSTRINGS
            or normalized_key in _SENSITIVE_QUERY_SUBSTRINGS
        ):
            raise IntegrationValidationError(
                "query string de webhook contém chave sensível",
                code="sensitive_webhook_query",
                field_path="endpoint_url",
            )


def _normalized_netloc(hostname: str, port: int | None) -> str:
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        host = hostname
    else:
        host = f"[{hostname}]" if address.version == 6 else hostname
    return host if port is None else f"{host}:{port}"


def _insecure_endpoint() -> IntegrationValidationError:
    return IntegrationValidationError(
        "endpoint de webhook inseguro",
        code="insecure_webhook_endpoint",
        field_path="endpoint_url",
    )
