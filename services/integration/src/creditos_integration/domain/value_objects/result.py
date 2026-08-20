from __future__ import annotations

import re
from collections.abc import Mapping
from enum import StrEnum

from creditos_integration.domain.errors import IntegrationValidationError
from creditos_integration.domain.value_objects.catalog import (
    IntegrationClass,
    parse_integration_class,
)


class IntegrationResultStatus(StrEnum):
    COMPLETED = "completed"
    PARTIAL = "partial"
    NOT_FOUND = "not_found"
    FAILED = "failed"


class MockIntegrationScenario(StrEnum):
    SYNTHETIC_SUCCESS = "synthetic_success"
    SYNTHETIC_PARTIAL = "synthetic_partial"
    SYNTHETIC_NOT_FOUND = "synthetic_not_found"
    SYNTHETIC_FAILURE = "synthetic_failure"


class SyntheticDataType(StrEnum):
    MOCK_INTEGRATION_RESULT = "mock_integration_result"


SUPPORTED_MOCK_INTEGRATION_CLASSES = (
    IntegrationClass.KYC_KYB.value,
    IntegrationClass.CREDIT_BUREAU.value,
    IntegrationClass.ANTI_FRAUD.value,
    IntegrationClass.RECEIVABLES.value,
)

_RESULT_ID_PATTERN = re.compile(r"^ires_[a-z0-9_.:-]{3,160}$")
_REASON_CODE_PATTERN = re.compile(r"^[a-z][a-z0-9_]{2,80}$")
_SUMMARY_TOKEN_PATTERN = re.compile(r"^[a-z0-9_.:-]{1,80}$")
_SYNTHETIC_REFERENCE_PATTERN = re.compile(r"^synthetic-[a-z0-9_:-]{3,120}$")
_CPF_PATTERN = re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")
_CNPJ_PATTERN = re.compile(r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b")
_EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_SECRET_PATTERN = re.compile(r"(?i)\b(token|secret|credential|password|senha|bearer)\b")
_SUMMARY_KEYS_BY_CLASS = {
    IntegrationClass.KYC_KYB.value: frozenset(
        {
            "synthetic_data_type",
            "identity_status",
            "document_status",
            "sanctions_status",
        }
    ),
    IntegrationClass.CREDIT_BUREAU.value: frozenset(
        {
            "synthetic_data_type",
            "score_band",
            "restriction_status",
            "debt_profile",
        }
    ),
    IntegrationClass.ANTI_FRAUD.value: frozenset(
        {
            "synthetic_data_type",
            "risk_band",
            "device_status",
            "velocity_status",
        }
    ),
    IntegrationClass.RECEIVABLES.value: frozenset(
        {
            "synthetic_data_type",
            "eligibility_status",
            "coverage_band",
            "settlement_status",
        }
    ),
}
_ALLOWED_REASON_CODES = frozenset(
    {
        "synthetic_match",
        "synthetic_partial_data",
        "synthetic_subject_not_found",
        "synthetic_controlled_failure",
    }
)
_SUMMARY_VALUES_BY_KEY = {
    "synthetic_data_type": frozenset({SyntheticDataType.MOCK_INTEGRATION_RESULT.value}),
    "identity_status": frozenset({"verified", "partial", "not_found", "unavailable"}),
    "document_status": frozenset({"valid", "pending", "not_found", "unavailable"}),
    "sanctions_status": frozenset({"clear", "unknown"}),
    "score_band": frozenset({"high", "medium", "unknown", "unavailable"}),
    "restriction_status": frozenset({"clear", "partial", "not_found", "unknown"}),
    "debt_profile": frozenset({"stable", "limited", "unknown"}),
    "risk_band": frozenset({"low", "medium", "unknown", "unavailable"}),
    "device_status": frozenset({"trusted", "unknown", "not_found"}),
    "velocity_status": frozenset({"normal", "elevated", "unknown"}),
    "eligibility_status": frozenset({"eligible", "partial", "not_found", "unavailable"}),
    "coverage_band": frozenset({"high", "medium", "unknown"}),
    "settlement_status": frozenset({"current", "limited", "unknown"}),
}


def validate_result_id(value: str) -> str:
    if not _RESULT_ID_PATTERN.fullmatch(value):
        raise IntegrationValidationError(
            "identificador de resultado inválido",
            code="invalid_integration_result_id",
            field_path="result_id",
        )
    return value


def parse_result_status(value: str) -> str:
    return _parse_enum(
        IntegrationResultStatus,
        value,
        code="unsupported_integration_result_status",
        field_path="status",
    )


def parse_mock_scenario(value: str) -> str:
    return _parse_enum(
        MockIntegrationScenario,
        value,
        code="unsupported_mock_integration_scenario",
        field_path="scenario",
    )


def validate_supported_mock_integration_class(value: str) -> str:
    integration_class = parse_integration_class(value)
    if integration_class not in SUPPORTED_MOCK_INTEGRATION_CLASSES:
        raise IntegrationValidationError(
            "classe não suportada pelo adapter mock/sandbox nesta story",
            code="unsupported_mock_integration_class",
            field_path="integration_class",
        )
    return integration_class


def validate_reason_codes(values: tuple[str, ...]) -> tuple[str, ...]:
    if len(values) > 16:
        raise IntegrationValidationError(
            "lista de reason codes excede o limite seguro",
            code="too_many_reason_codes",
            field_path="reason_codes",
        )
    for index, value in enumerate(values):
        if not _REASON_CODE_PATTERN.fullmatch(value):
            raise IntegrationValidationError(
                "reason code inválido",
                code="invalid_reason_code",
                field_path=f"reason_codes[{index}]",
            )
        if value not in _ALLOWED_REASON_CODES:
            raise IntegrationValidationError(
                "reason code não permitido para resultado mock/sandbox",
                code="unsupported_reason_code",
                field_path=f"reason_codes[{index}]",
            )
    return values


def validate_summary(integration_class: str, summary: Mapping[str, object]) -> Mapping[str, object]:
    integration_class = validate_supported_mock_integration_class(integration_class)
    allowed_keys = _SUMMARY_KEYS_BY_CLASS[integration_class]
    for key, value in summary.items():
        if key not in allowed_keys:
            raise IntegrationValidationError(
                "campo de resumo não permitido para resultado de integração",
                code="invalid_integration_result_summary_key",
                field_path=f"summary.{key}",
            )
        if type(value) is not str:
            raise IntegrationValidationError(
                "valor de resumo deve ser token sintético seguro",
                code="invalid_integration_result_summary_value",
                field_path=f"summary.{key}",
            )
        if not _SUMMARY_TOKEN_PATTERN.fullmatch(value):
            raise IntegrationValidationError(
                "valor de resumo deve ser token sintético seguro",
                code="invalid_integration_result_summary_value",
                field_path=f"summary.{key}",
            )
        if value not in _SUMMARY_VALUES_BY_KEY[key]:
            raise IntegrationValidationError(
                "valor de resumo não permitido para resultado mock/sandbox",
                code="unsupported_integration_result_summary_value",
                field_path=f"summary.{key}",
            )
    if summary.get("synthetic_data_type") != SyntheticDataType.MOCK_INTEGRATION_RESULT.value:
        raise IntegrationValidationError(
            "tipo de dado sintético ausente ou inválido",
            code="invalid_synthetic_data_type",
            field_path="summary.synthetic_data_type",
        )
    return dict(summary)


def validate_synthetic_subject_reference(value: str) -> str:
    if not _SYNTHETIC_REFERENCE_PATTERN.fullmatch(value):
        raise IntegrationValidationError(
            "referência sintética inválida",
            code="invalid_synthetic_subject_reference",
            field_path="synthetic_subject_reference",
        )
    if _CPF_PATTERN.search(value) or _CNPJ_PATTERN.search(value) or _EMAIL_PATTERN.search(value):
        raise IntegrationValidationError(
            "referência sintética não pode conter identificador pessoal",
            code="sensitive_synthetic_subject_reference",
            field_path="synthetic_subject_reference",
        )
    if _SECRET_PATTERN.search(value):
        raise IntegrationValidationError(
            "referência sintética não pode conter segredo ou credencial",
            code="sensitive_synthetic_subject_reference",
            field_path="synthetic_subject_reference",
        )
    return value


def _parse_enum(
    enum_type: type[StrEnum],
    value: str,
    *,
    code: str,
    field_path: str,
) -> str:
    try:
        return enum_type(value).value
    except ValueError as error:
        raise IntegrationValidationError(
            "valor não suportado",
            code=code,
            field_path=field_path,
        ) from error
