from __future__ import annotations

import hashlib
import hmac
import re
import unicodedata
from collections.abc import Mapping, Sequence
from typing import Any

OMITTED = "[OMITIDO]"
FINANCIAL_OMITTED = "[DADO_FINANCEIRO_OMITIDO]"

_CNPJ_PATTERN = re.compile(r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b")
_CPF_PATTERN = re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")
_EMAIL_PATTERN = re.compile(
    r"\b([A-Za-z0-9._%+-])([A-Za-z0-9._%+-]*)(@)([A-Za-z0-9.-]+\.[A-Za-z]{2,})\b"
)
_PHONE_PATTERN = re.compile(r"\(?\b\d{2}\)?\s?\d{4,5}-?\d{4}\b")
_BEARER_PATTERN = re.compile(r"(?i)(authorization\s*:\s*bearer\s+)[^\s,;]+")
_SECRET_ASSIGNMENT_PATTERN = re.compile(
    r"""(?ix)
    \b(token|secret|api[_-]?key|password|senha)\b
    \s*[:=]\s*
    (?:
        "[^"]*"
        | '[^']*'
        | [^\r\n,;]+
    )
    """
)
_CONTROL_CHARS_PATTERN = re.compile(r"[\x00-\x1f\x7f\u0085\u2028\u2029]+")
_TECHNICAL_DELIMITER_PATTERN = re.compile(r"""[=:"'`|{}[\]<>;\\]+""")
_MAX_MASKING_DEPTH = 12
_MAX_SAFE_REFERENCE_LENGTH = 160

_SECRET_KEYS = {
    "authorization",
    "api_key",
    "apikey",
    "access_token",
    "refresh_token",
    "token",
    "secret",
    "client_secret",
    "password",
    "senha",
    "cookie",
    "set_cookie",
}
_PAYLOAD_KEYS = {
    "headers",
    "payload",
    "raw_payload",
    "external_payload",
    "provider_payload",
    "request_body",
    "response_body",
    "request_payload",
    "response_payload",
    "request_headers",
    "response_headers",
    "prompt",
    "completion",
    "output",
    "model_output",
    "ai_output",
    "llm_output",
    "provider_output",
    "embedding",
    "document",
    "documento",
    "document_image",
    "imagem",
    "image",
    "biometria",
}
_FINANCIAL_KEYS = {
    "renda",
    "renda_mensal",
    "income",
    "salary",
    "faturamento",
    "revenue",
    "limite_credito",
    "credit_limit",
    "dados_financeiros",
}
_IDENTIFIER_KEYS = {
    "cpf",
    "cnpj",
    "document_number",
    "email",
    "e_mail",
    "phone",
    "telefone",
}
_SAFE_REFERENCE_KEYS = {
    "prompt_fingerprint",
    "output_fingerprint",
    "completion_fingerprint",
    "payload_digest",
    "body_digest",
    "manifest_digest",
}
_SECRET_KEY_FRAGMENTS = (
    "authorization",
    "credential",
    "password",
    "senha",
    "secret",
    "token",
    "cookie",
)
_SECRET_KEY_SUFFIXES = ("api_key", "apikey", "private_key", "public_key")
_PAYLOAD_KEY_FRAGMENTS = (
    "headers",
    "payload",
    "request_body",
    "response_body",
    "provider_payload",
    "prompt",
    "completion",
    "embedding",
    "document",
    "documento",
    "imagem",
    "image",
    "biometria",
    "attachment",
    "anexo",
)
_IDENTIFIER_KEY_FRAGMENTS = (
    "cpf",
    "cnpj",
    "email",
    "e_mail",
    "phone",
    "telefone",
    "document_number",
    "documento_numero",
)
_FINANCIAL_KEY_FRAGMENTS = (
    "renda",
    "income",
    "salary",
    "faturamento",
    "revenue",
    "financial",
    "financeiro",
    "credit_limit",
)


def mask_text(value: str) -> str:
    masked = _CNPJ_PATTERN.sub(_mask_cnpj_match, value)
    masked = _CPF_PATTERN.sub(_mask_cpf_match, masked)
    masked = _EMAIL_PATTERN.sub(_mask_email_match, masked)
    masked = _PHONE_PATTERN.sub(_mask_phone_match, masked)
    masked = _BEARER_PATTERN.sub(r"\1[OMITIDO]", masked)
    masked = _SECRET_ASSIGNMENT_PATTERN.sub(lambda match: f"{match.group(1)}={OMITTED}", masked)
    return sanitize_log_text(masked)


def sanitize_log_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    without_format_controls = "".join(
        "_" if unicodedata.category(character) in {"Cc", "Cf", "Zl", "Zp"} else character
        for character in normalized
    )
    return _CONTROL_CHARS_PATTERN.sub("_", without_format_controls).strip(" _")


def sanitize_technical_field(value: str) -> str:
    safe_value = sanitize_log_text(value)
    safe_value = _TECHNICAL_DELIMITER_PATTERN.sub("_", safe_value)
    safe_value = re.sub(r"\s+", "_", safe_value)
    safe_value = re.sub(r"_+", "_", safe_value)
    return safe_value.strip(" _")


def mask_sensitive_data(value: Any, *, key: str | None = None) -> Any:
    return _mask_sensitive_data(value, key=key, depth=0, seen=set())


def _mask_sensitive_data(
    value: Any,
    *,
    key: str | None,
    depth: int,
    seen: set[int],
) -> Any:
    if depth > _MAX_MASKING_DEPTH:
        return OMITTED

    normalized_key = _normalize_key(key)

    if _is_safe_reference_key(normalized_key):
        if not isinstance(value, str):
            return OMITTED
        return sanitize_technical_field(value)[:_MAX_SAFE_REFERENCE_LENGTH] or OMITTED
    elif (
        _is_secret_key(normalized_key)
        or _is_payload_key(normalized_key)
        or _is_identifier_key(normalized_key)
    ):
        return OMITTED

    if _is_financial_key(normalized_key):
        return FINANCIAL_OMITTED

    if isinstance(value, bytes | bytearray | memoryview):
        return OMITTED

    if isinstance(value, str):
        return mask_text(value)

    if isinstance(value, Mapping):
        value_id = id(value)
        if value_id in seen:
            return OMITTED
        next_seen = {*seen, value_id}
        masked_mapping: dict[str, Any] = {}
        for item_key, item_value in value.items():
            safe_item_key = _safe_mapping_key(item_key)
            output_key = _deduplicated_key(safe_item_key, masked_mapping)
            masked_mapping[output_key] = _mask_sensitive_data(
                item_value,
                key=safe_item_key,
                depth=depth + 1,
                seen=next_seen,
            )
        return masked_mapping

    if isinstance(value, Sequence) and not isinstance(value, bytes | bytearray):
        value_id = id(value)
        if value_id in seen:
            return OMITTED
        next_seen = {*seen, value_id}
        return [
            _mask_sensitive_data(item, key=None, depth=depth + 1, seen=next_seen) for item in value
        ]

    return value


def hmac_sha256_identifier(value: str, *, secret_key: str) -> str:
    if not secret_key:
        raise ValueError("secret_key é obrigatória para hash seguro de identificadores")

    normalized_value = _normalize_identifier(value)
    return hmac.new(
        secret_key.encode("utf-8"),
        normalized_value.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _normalize_key(key: str | None) -> str:
    if key is None:
        return ""
    canonical_key = _canonical_key_text(key)
    snake_key = re.sub(r"(?<!^)(?=[A-Z])", "_", canonical_key.strip())
    return snake_key.lower().replace("-", "_").replace(".", "_")


def _canonical_key_text(key: str) -> str:
    normalized = unicodedata.normalize("NFKC", key)
    without_controls = "".join(
        "" if unicodedata.category(character) in {"Cc", "Cf", "Zl", "Zp"} else character
        for character in normalized
    )
    return without_controls


def _safe_mapping_key(key: Any) -> str:
    safe_key = sanitize_log_text(_canonical_key_text(str(key)))
    if safe_key:
        return safe_key
    return "omitted_key"


def _deduplicated_key(key: str, existing: Mapping[str, Any]) -> str:
    if key not in existing:
        return key
    suffix = 2
    while f"{key}_{suffix}" in existing:
        suffix += 1
    return f"{key}_{suffix}"


def _normalize_identifier(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    if digits:
        return digits
    return value.strip().casefold()


def _mask_cpf_match(match: re.Match[str]) -> str:
    digits = re.sub(r"\D", "", match.group(0))
    return f"***.***.***-{digits[-2:]}"


def _mask_cnpj_match(match: re.Match[str]) -> str:
    digits = re.sub(r"\D", "", match.group(0))
    return f"**.***.***/****-{digits[-2:]}"


def _mask_email_match(match: re.Match[str]) -> str:
    return f"{match.group(1).lower()}***@{match.group(4).lower()}"


def _mask_phone_match(match: re.Match[str]) -> str:
    digits = re.sub(r"\D", "", match.group(0))
    return f"(**) *****-{digits[-4:]}"


def _is_secret_key(normalized_key: str) -> bool:
    return (
        normalized_key in _SECRET_KEYS
        or any(fragment in normalized_key for fragment in _SECRET_KEY_FRAGMENTS)
        or any(normalized_key.endswith(suffix) for suffix in _SECRET_KEY_SUFFIXES)
    )


def _is_payload_key(normalized_key: str) -> bool:
    return normalized_key in _PAYLOAD_KEYS or any(
        fragment in normalized_key for fragment in _PAYLOAD_KEY_FRAGMENTS
    )


def _is_identifier_key(normalized_key: str) -> bool:
    return normalized_key in _IDENTIFIER_KEYS or any(
        fragment in normalized_key for fragment in _IDENTIFIER_KEY_FRAGMENTS
    )


def _is_safe_reference_key(normalized_key: str) -> bool:
    return normalized_key in _SAFE_REFERENCE_KEYS


def _is_financial_key(normalized_key: str) -> bool:
    return normalized_key in _FINANCIAL_KEYS or any(
        fragment in normalized_key for fragment in _FINANCIAL_KEY_FRAGMENTS
    )
