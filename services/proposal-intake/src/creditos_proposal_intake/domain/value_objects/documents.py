from __future__ import annotations

import re

from creditos_proposal_intake.domain.errors import ProposalValidationError

_DIGITS_PATTERN = re.compile(r"\D")


def normalize_document(value: object, *, document_type: str, field_path: str) -> str:
    if not isinstance(value, str):
        raise ProposalValidationError(
            "documento inválido",
            field_path=field_path,
            details={"expected": document_type},
        )
    digits = _DIGITS_PATTERN.sub("", value)
    expected_length = 11 if document_type == "CPF" else 14 if document_type == "CNPJ" else 0
    if len(digits) != expected_length or not _has_valid_check_digits(digits, document_type):
        raise ProposalValidationError(
            "documento incompatível com o tipo informado",
            field_path=field_path,
            details={"expected": document_type},
        )
    return digits


def _has_valid_check_digits(digits: str, document_type: str) -> bool:
    if len(set(digits)) == 1:
        return False
    if document_type == "CPF":
        return _valid_cpf(digits)
    if document_type == "CNPJ":
        return _valid_cnpj(digits)
    return False


def _valid_cpf(digits: str) -> bool:
    first = sum(
        int(digit) * weight for digit, weight in zip(digits[:9], range(10, 1, -1), strict=True)
    )
    first_digit = 0 if first % 11 < 2 else 11 - (first % 11)
    second = sum(
        int(digit) * weight for digit, weight in zip(digits[:10], range(11, 1, -1), strict=True)
    )
    second_digit = 0 if second % 11 < 2 else 11 - (second % 11)
    return digits[-2:] == f"{first_digit}{second_digit}"


def _valid_cnpj(digits: str) -> bool:
    first_weights = (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)
    second_weights = (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)
    first_sum = sum(
        int(digit) * weight for digit, weight in zip(digits[:12], first_weights, strict=True)
    )
    first_digit = 0 if first_sum % 11 < 2 else 11 - (first_sum % 11)
    second_sum = sum(
        int(digit) * weight for digit, weight in zip(digits[:13], second_weights, strict=True)
    )
    second_digit = 0 if second_sum % 11 < 2 else 11 - (second_sum % 11)
    return digits[-2:] == f"{first_digit}{second_digit}"
