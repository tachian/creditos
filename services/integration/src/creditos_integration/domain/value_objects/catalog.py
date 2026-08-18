from __future__ import annotations

import re
from enum import StrEnum

from creditos_integration.domain.errors import IntegrationValidationError


class IntegrationClass(StrEnum):
    KYC_KYB = "kyc_kyb"
    CREDIT_BUREAU = "credit_bureau"
    ANTI_FRAUD = "anti_fraud"
    RECEIVABLES = "receivables"
    OPEN_FINANCE = "open_finance"
    WEBHOOK_CALLBACK = "webhook_callback"


class ProductType(StrEnum):
    PERSONAL_CREDIT = "personal_credit"
    BNPL = "bnpl"
    BUSINESS_CREDIT = "business_credit"
    RECEIVABLES = "receivables"


class IntegrationRequirement(StrEnum):
    REQUIRED = "required"
    OPTIONAL = "optional"
    CONDITIONAL = "conditional"


class FallbackStrategy(StrEnum):
    FAIL_CLOSED = "fail_closed"
    ALLOW_PARTIAL = "allow_partial"
    SKIP_OPTIONAL = "skip_optional"


class IntegrationPlanStatus(StrEnum):
    READY = "ready"
    MISSING_REQUIRED_CONFIGURATION = "missing_required_configuration"
    NO_APPLICABLE_INTEGRATIONS = "no_applicable_integrations"
    INVALID_CONFIGURATION = "invalid_configuration"


_ADAPTER_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_.-]{2,80}$")
_CONFIGURATION_ID_PATTERN = re.compile(r"^icfg_[a-z0-9_.:-]{3,160}$")


def parse_product_type(value: str) -> str:
    return _parse_enum(
        ProductType,
        value,
        code="unsupported_product_type",
        field_path="product_type",
    )


def parse_integration_class(value: str) -> str:
    return _parse_enum(
        IntegrationClass,
        value,
        code="unsupported_integration_class",
        field_path="integration_class",
    )


def parse_requirement(value: str) -> str:
    return _parse_enum(
        IntegrationRequirement,
        value,
        code="unsupported_requirement",
        field_path="requirement",
    )


def parse_fallback_strategy(value: str) -> str:
    return _parse_enum(
        FallbackStrategy,
        value,
        code="unsupported_fallback_strategy",
        field_path="fallback_strategy",
    )


def validate_adapter_id(value: str) -> str:
    if not _ADAPTER_ID_PATTERN.fullmatch(value):
        raise IntegrationValidationError(
            "adapter inválido",
            code="invalid_adapter_id",
            field_path="adapter_id",
        )
    return value


def validate_configuration_id(value: str) -> str:
    if not _CONFIGURATION_ID_PATTERN.fullmatch(value):
        raise IntegrationValidationError(
            "identificador de configuração inválido",
            code="invalid_configuration_id",
            field_path="configuration_id",
        )
    return value


def validate_timeout_ms(value: int) -> int:
    if type(value) is not int:
        raise IntegrationValidationError(
            "timeout inválido",
            code="invalid_timeout",
            field_path="timeout_ms",
        )
    if value < 50 or value > 120_000:
        raise IntegrationValidationError(
            "timeout inválido",
            code="invalid_timeout",
            field_path="timeout_ms",
        )
    return value


def validate_max_attempts(value: int) -> int:
    if type(value) is not int:
        raise IntegrationValidationError(
            "limite de tentativas inválido",
            code="invalid_attempt_limit",
            field_path="max_attempts",
        )
    if value < 1 or value > 5:
        raise IntegrationValidationError(
            "limite de tentativas inválido",
            code="invalid_attempt_limit",
            field_path="max_attempts",
        )
    return value


def validate_max_concurrency(value: int) -> int:
    if type(value) is not int:
        raise IntegrationValidationError(
            "limite de concorrência inválido",
            code="invalid_concurrency_limit",
            field_path="max_concurrency",
        )
    if value < 1 or value > 50:
        raise IntegrationValidationError(
            "limite de concorrência inválido",
            code="invalid_concurrency_limit",
            field_path="max_concurrency",
        )
    return value


def validate_estimated_cost_units(value: int) -> int:
    if type(value) is not int:
        raise IntegrationValidationError(
            "limite de custo inválido",
            code="invalid_cost_limit",
            field_path="estimated_cost_units",
        )
    if value < 0 or value > 1_000_000:
        raise IntegrationValidationError(
            "limite de custo inválido",
            code="invalid_cost_limit",
            field_path="estimated_cost_units",
        )
    return value


def _parse_enum(enum_type: type[StrEnum], value: str, *, code: str, field_path: str) -> str:
    try:
        return enum_type(value).value
    except ValueError as error:
        raise IntegrationValidationError(
            "valor não suportado",
            code=code,
            field_path=field_path,
        ) from error
