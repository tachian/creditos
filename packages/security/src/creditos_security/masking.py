from __future__ import annotations

import hashlib
import hmac
import re
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
    r"(?i)\b(token|secret|api[_-]?key|password|senha)\b\s*[:=]\s*[^\s,;]+"
)

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
}
_PAYLOAD_KEYS = {
    "payload",
    "raw_payload",
    "external_payload",
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
_SECRET_KEY_FRAGMENTS = ("authorization", "credential", "password", "senha", "secret", "token")
_SECRET_KEY_SUFFIXES = ("api_key", "apikey", "private_key", "public_key")
_PAYLOAD_KEY_FRAGMENTS = (
    "payload",
    "document",
    "documento",
    "imagem",
    "image",
    "biometria",
    "attachment",
    "anexo",
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
    return _SECRET_ASSIGNMENT_PATTERN.sub(lambda match: f"{match.group(1)}={OMITTED}", masked)


def mask_sensitive_data(value: Any, *, key: str | None = None) -> Any:
    normalized_key = _normalize_key(key)

    if _is_secret_key(normalized_key) or _is_payload_key(normalized_key):
        return OMITTED

    if _is_financial_key(normalized_key):
        return FINANCIAL_OMITTED

    if isinstance(value, bytes | bytearray | memoryview):
        return OMITTED

    if isinstance(value, str):
        return mask_text(value)

    if isinstance(value, Mapping):
        return {
            str(item_key): mask_sensitive_data(item_value, key=str(item_key))
            for item_key, item_value in value.items()
        }

    if isinstance(value, Sequence) and not isinstance(value, bytes | bytearray):
        return [mask_sensitive_data(item) for item in value]

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
    snake_key = re.sub(r"(?<!^)(?=[A-Z])", "_", key.strip())
    return snake_key.lower().replace("-", "_").replace(".", "_")


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


def _is_financial_key(normalized_key: str) -> bool:
    return normalized_key in _FINANCIAL_KEYS or any(
        fragment in normalized_key for fragment in _FINANCIAL_KEY_FRAGMENTS
    )
